from __future__ import annotations

import json
import os
import re
import sys

from . import netlist

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMETERS_PATH = os.path.join(REPO_ROOT, "components", "parameters.json")
TOOLKIT_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest")
FOOTPRINT_ROOT = "/usr/share/kicad/footprints"

if TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, TOOLKIT_ROOT)

from pcbqa import claim  # noqa: E402

DIRECT = "direct"
ASSUMED = "assumed"
DERIVED = "derived"

CAPACITOR_TOLERANCE = 0.20

SERIES_PASSIVE_PREFIXES = ("R", "L", "FB")

EXPOSED_CONTACT_REFERENCE = "J1"

PROBE_REQUIRED_NETS = ("VBUS", "GND", "+5V", "LED_DATA")

DEBUG_CONTRACT = {
    "J2.1": "+5V",
    "J2.2": "SWDIO",
    "J2.3": "NRST",
    "J2.4": "SWCLK",
    "J2.5": "GND",
}


class Quantity:
    __slots__ = ("value", "basis", "documents")

    def __init__(self, value, basis, documents=()):
        self.value = value
        self.basis = basis
        self.documents = tuple(documents)

    @property
    def known(self):
        return self.value is not None


UNKNOWN = Quantity(None, None)


def load_parameters():
    with open(PARAMETERS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _quantity(record, supply_v=None):
    if not isinstance(record, dict):
        return UNKNOWN
    if record.get("knowledge") == "unknown":
        return UNKNOWN
    documents = (record["document"],) if record.get("document") else ()
    basis = record.get("basis", ASSUMED)
    if "factor_of_supply" in record:
        if supply_v is None:
            return UNKNOWN
        return Quantity(record["factor_of_supply"] * supply_v, basis,
                        documents)
    if "offset_from_supply" in record:
        if supply_v is None:
            return UNKNOWN
        return Quantity(record["offset_from_supply"] + supply_v, basis,
                        documents)
    if "value" in record:
        return Quantity(record["value"], basis, documents)
    return UNKNOWN


def _combine(*quantities):
    basis = DIRECT
    documents = []
    for quantity in quantities:
        if not quantity.known:
            return None, None, ()
        if quantity.basis == ASSUMED:
            basis = ASSUMED
        elif quantity.basis == DERIVED and basis != ASSUMED:
            basis = DERIVED
        documents.extend(quantity.documents)
    return True, basis, tuple(sorted(set(documents)))


def _mpn(reference):
    part = netlist.PARTS[reference]
    return part["mpn"]


def _part_parameters(parameters, reference):
    return parameters["parts"].get(_mpn(reference))


def _pin_map():
    mapping = {}
    for net_name, pin_refs in netlist.NETS.items():
        for pin_ref in pin_refs:
            mapping[pin_ref] = net_name
    return mapping


def _net_pins():
    return {name: list(pins) for name, pins in netlist.NETS.items()}


EVIDENCE_CLASSES = {
    DIRECT: "datasheet-behavioral",
    ASSUMED: "assumed-behavioral",
    DERIVED: "design-source",
}


def _evidence(basis, documents, assumptions=(), omissions=()):
    provenance = {
        "source": "components/parameters.json",
        "documents": list(documents),
    }
    return claim.evidence(
        "device_electrical", EVIDENCE_CLASSES.get(basis, "design-source"),
        provenance, assumptions=list(assumptions),
        omitted_contributions=list(omissions))


def _claim(identity, units, significance, value, basis, documents,
           requirement, knowledge, scope_level="net", assumptions=(),
           omissions=()):
    if value is None:
        return claim.claim(
            scope_level, identity, units, claim.UNKNOWN, {},
            _evidence(basis, documents, assumptions, omissions),
            significance, None, requirement)
    knowledge_basis = None
    if knowledge != claim.EXACT:
        knowledge_basis = claim.knowledge_basis(
            basis, "datasheet_limit" if basis == DIRECT else basis)
    quantity = {"value": value}
    return claim.claim(
        scope_level, identity, units, knowledge, quantity,
        _evidence(basis, documents, assumptions, omissions),
        significance, knowledge_basis, requirement)


def _requirement(name, op, value):
    return claim.requirement(name, "BRIEF.md", {"op": op, "value": value})


def _series_graph():
    graph = {}
    for reference, part in netlist.PARTS.items():
        prefix = reference.rstrip("0123456789")
        if prefix not in SERIES_PASSIVE_PREFIXES:
            continue
        graph.setdefault(reference + ".1", set()).add(reference + ".2")
        graph.setdefault(reference + ".2", set()).add(reference + ".1")
    return graph


def _reachable_nets(start_net, pin_map, net_pins):
    graph = _series_graph()
    seen = {start_net}
    frontier = [start_net]
    series_refs = []
    while frontier:
        net_name = frontier.pop()
        for pin_ref in net_pins.get(net_name, ()):
            for other in graph.get(pin_ref, ()):
                other_net = pin_map.get(other)
                if other_net and other_net not in seen:
                    seen.add(other_net)
                    series_refs.append(pin_ref.split(".")[0])
                    frontier.append(other_net)
    return seen, series_refs


def logic_links(parameters):
    pin_map = _pin_map()
    net_pins = _net_pins()
    links = []
    for reference, part in sorted(netlist.PARTS.items()):
        spec = _part_parameters(parameters, reference)
        if not spec:
            continue
        for pin_number, output in sorted(spec.get("digital_outputs",
                                                  {}).items()):
            driver_pin = "%s.%s" % (reference, pin_number)
            driver_net = pin_map.get(driver_pin)
            if driver_net is None:
                continue
            nets, series_refs = _reachable_nets(driver_net, pin_map, net_pins)
            receivers = []
            for net_name in sorted(nets):
                for pin_ref in net_pins.get(net_name, ()):
                    if pin_ref == driver_pin:
                        continue
                    other_ref, _, other_pin = pin_ref.partition(".")
                    other_spec = _part_parameters(parameters, other_ref)
                    if not other_spec:
                        continue
                    entry = other_spec.get("digital_inputs", {}).get(other_pin)
                    if entry is not None:
                        receivers.append((pin_ref, other_ref, entry))
            if receivers:
                links.append((driver_pin, reference, output, driver_net,
                              receivers, series_refs))
    return links


def _supply_range(reference, pin_number, spec, parameters):
    pin_map = _pin_map()
    supply_pin = spec.get("digital_outputs", {}).get(pin_number, {}).get(
        "reference_supply_pin")
    if supply_pin is None:
        supply_pin = spec.get("digital_inputs", {}).get(pin_number, {}).get(
            "reference_supply_pin")
    if supply_pin is None:
        supply_pins = spec.get("supply_pins") or []
        supply_pin = supply_pins[0] if supply_pins else None
    if supply_pin is None:
        return None
    rail = pin_map.get("%s.%s" % (reference, supply_pin))
    return netlist.RAILS.get(rail)


def _series_resistance(series_refs):
    total = 0.0
    for reference in series_refs:
        value = netlist.PARTS[reference]["value"]
        match = re.match(r"^([\d.]+)R?$", value.replace("k", "e3"))
        if not match:
            return None
        total += float(match.group(1))
    return total


def evaluate_logic_levels(parameters):
    results = []
    for (driver_pin, driver_ref, output, driver_net, receivers,
         series_refs) in logic_links(parameters):
        driver_rail = _supply_range(
            driver_ref, driver_pin.split(".")[1],
            _part_parameters(parameters, driver_ref), parameters)
        resistance = _series_resistance(series_refs)
        for receiver_pin, receiver_ref, entry in receivers:
            identity = "%s->%s" % (driver_pin, receiver_pin)
            receiver_rail = _supply_range(
                receiver_ref, receiver_pin.split(".")[1],
                _part_parameters(parameters, receiver_ref), parameters)
            margin, basis, documents, assumptions = _high_level_margin(
                output, entry, driver_rail, receiver_rail, resistance)
            results.append({
                "id": "logic_high_margin",
                "identity": identity,
                "claim": _claim(
                    identity, "V", "logic_high_noise_margin", margin, basis,
                    documents, _requirement(
                        "drive_meets_receiver_threshold", ">=", 0.0),
                    claim.LOWER_BOUND if margin is not None else claim.UNKNOWN,
                    assumptions=assumptions),
            })
    return results


def _high_level_margin(output, entry, driver_rail, receiver_rail, resistance):
    if driver_rail is None or receiver_rail is None:
        return None, None, (), ()
    voh_record = output.get("voh_min", {})
    vih_record = entry.get("vih_min", {})
    valid_min = voh_record.get("valid_supply_min_v")
    if valid_min is not None and driver_rail["min_v"] < valid_min:
        return None, None, (), ()
    worst = None
    basis = DIRECT
    documents = ()
    assumptions = []
    for rail_v in (receiver_rail["min_v"], receiver_rail["max_v"]):
        vih = _quantity(vih_record, rail_v)
        voh = _quantity(voh_record, driver_rail["min_v"])
        known, combined_basis, combined_documents = _combine(vih, voh)
        if not known:
            return None, None, (), ()
        drop = 0.0
        if resistance:
            current = entry.get("input_current_max_a")
            if current is None:
                assumptions.append("series_drop_omitted")
            else:
                drop = resistance * current
        margin = voh.value - drop - vih.value
        if worst is None or margin < worst:
            worst = margin
            basis = combined_basis
            documents = combined_documents
    return worst, basis, documents, tuple(sorted(set(assumptions)))


def evaluate_supply_current(parameters):
    total = 0.0
    basis = DIRECT
    documents = []
    unknown = False
    contributions = {}
    for reference in sorted(netlist.PARTS):
        spec = _part_parameters(parameters, reference)
        if not spec:
            continue
        quantity = _quantity(spec.get("supply_current_max_a", {}))
        if not quantity.known:
            unknown = True
            continue
        current = quantity.value
        if spec.get("current_scales_with_brightness_limit"):
            current *= netlist.FIRMWARE_GLOBAL_BRIGHTNESS_LIMIT
        total += current
        contributions[reference] = current
        if quantity.basis == ASSUMED:
            basis = ASSUMED
        documents.extend(quantity.documents)
    value = None if unknown else total
    return {
        "id": "supply_current_budget",
        "identity": "board_vbus_current",
        "contributions": contributions,
        "claim": _claim(
            "board_vbus_current", "A", "port_current_budget", value, basis,
            tuple(sorted(set(documents))),
            _requirement("within_declared_port_budget", "<=",
                         netlist.PORT_BUDGET_A),
            claim.UPPER_BOUND if value is not None else claim.UNKNOWN,
            scope_level="board"),
    }


def _capacitance_farads(value):
    match = re.match(r"^([\d.]+)(p|n|u)F$", value)
    if not match:
        return None
    scale = {"p": 1e-12, "n": 1e-9, "u": 1e-6}[match.group(2)]
    return float(match.group(1)) * scale


def evaluate_vbus_capacitance(parameters):
    pin_map = _pin_map()
    domain = {"VBUS", "+5V"}
    total = 0.0
    included = {}
    for reference, part in sorted(netlist.PARTS.items()):
        if not reference.startswith("C"):
            continue
        pins = {pin_map.get("%s.1" % reference),
                pin_map.get("%s.2" % reference)}
        if not pins & domain:
            continue
        farads = _capacitance_farads(part["value"])
        if farads is None:
            return {"id": "vbus_bypass_capacitance",
                    "identity": "vbus_domain",
                    "claim": _claim(
                        "vbus_domain", "F", "usb_inrush_capacitance", None,
                        None, (), _requirement(
                            "within_usb_bypass_capacitance_limit", "<=",
                            netlist.VBUS_CAPACITANCE_LIMIT_F),
                        claim.UNKNOWN, scope_level="board")}
        included[reference] = farads
        total += farads * (1.0 + CAPACITOR_TOLERANCE)
    return {
        "id": "vbus_bypass_capacitance",
        "identity": "vbus_domain",
        "included": included,
        "claim": _claim(
            "vbus_domain", "F", "usb_inrush_capacitance", total, DERIVED, (),
            _requirement("within_usb_bypass_capacitance_limit", "<=",
                         netlist.VBUS_CAPACITANCE_LIMIT_F),
            claim.UPPER_BOUND, scope_level="board"),
    }


def evaluate_absolute_maximum(parameters):
    pin_map = _pin_map()
    results = []
    for reference in sorted(netlist.PARTS):
        spec = _part_parameters(parameters, reference)
        if not spec:
            continue
        for supply_pin in spec.get("supply_pins", []):
            rail_name = pin_map.get("%s.%s" % (reference, supply_pin))
            rail = netlist.RAILS.get(rail_name)
            if rail is None:
                continue
            identity = "%s.%s@%s" % (reference, supply_pin, rail_name)
            abs_max = _quantity(spec.get("supply", {}).get("abs_max_v", {}))
            if abs_max.known:
                margin = abs_max.value - rail["max_v"]
                knowledge = claim.LOWER_BOUND
                basis = abs_max.basis
                documents = abs_max.documents
            else:
                margin, knowledge, basis, documents = (
                    None, claim.UNKNOWN, None, ())
            results.append({
                "id": "supply_absolute_maximum_margin",
                "identity": identity,
                "claim": _claim(
                    identity, "V", "device_absolute_maximum_margin", margin,
                    basis, documents,
                    _requirement("rail_within_absolute_maximum", ">=", 0.0),
                    knowledge, scope_level="measurement"),
            })
    return results


def evaluate_source_range_coverage(parameters):
    vsafe5v_max = parameters["usb"]["vsafe5v_max_v"]
    declared_max = netlist.RAILS["VBUS"]["max_v"]
    return {
        "id": "usb_source_range_coverage",
        "identity": "vbus_declared_vs_vsafe5v",
        "claim": _claim(
            "vbus_declared_vs_vsafe5v", "V",
            "declared_range_covers_source_range",
            declared_max - vsafe5v_max, DERIVED, (),
            _requirement("covers_usb_c_vsafe5v_maximum", ">=", 0.0),
            claim.EXACT,
            scope_level="board"),
    }


def _structural_claim(identity, significance, violations, requirement_name):
    return _claim(
        identity, "count", significance, float(len(violations)), DIRECT, (),
        _requirement(requirement_name, "<=", 0.0), claim.EXACT,
        scope_level="board")


def evaluate_cc_terminations(parameters):
    pin_map = _pin_map()
    net_pins = _net_pins()
    wanted = parameters["usb"]["sink_cc_termination_ohms"]
    tolerance = parameters["usb"]["sink_cc_termination_tolerance"]
    violations = []
    for net_name in ("CC1", "CC2"):
        terminators = []
        for pin_ref in net_pins.get(net_name, ()):
            reference = pin_ref.split(".")[0]
            if not reference.startswith("R"):
                continue
            other = "%s.%s" % (
                reference, "2" if pin_ref.endswith(".1") else "1")
            if pin_map.get(other) != "GND":
                continue
            ohms = _resistance_ohms(netlist.PARTS[reference]["value"])
            terminators.append((reference, ohms))
        if len(terminators) != 1:
            violations.append((net_name, "termination_count",
                               len(terminators)))
            continue
        reference, ohms = terminators[0]
        if ohms is None or abs(ohms - wanted) > wanted * tolerance:
            violations.append((net_name, "termination_value", ohms))
    return {
        "id": "typec_sink_cc_terminations",
        "identity": "cc_terminations",
        "violations": violations,
        "claim": _structural_claim(
            "cc_terminations", "typec_sink_advertisement", violations,
            "cc_pins_present_sink_terminations"),
    }


def _resistance_ohms(value):
    match = re.match(r"^([\d.]+)([kM]?)R?$", value)
    if not match:
        return None
    scale = {"": 1.0, "k": 1e3, "M": 1e6}[match.group(2)]
    return float(match.group(1)) * scale


def evaluate_esd_coverage(parameters):
    pin_map = _pin_map()
    net_pins = _net_pins()
    protected = set()
    for reference, part in netlist.PARTS.items():
        spec = parameters["parts"].get(part["mpn"] or "")
        if not spec or "reverse_standoff_v" not in spec:
            continue
        nets = {pin_map.get("%s.1" % reference),
                pin_map.get("%s.2" % reference)}
        if "GND" in nets:
            protected |= {name for name in nets if name and name != "GND"}
    exposed = set()
    for pin_ref in net_pins_of_reference(net_pins, EXPOSED_CONTACT_REFERENCE):
        net_name = pin_map.get(pin_ref)
        if net_name and net_name != "GND":
            exposed.add(net_name)
    exposed.add("BTN_SW")
    violations = sorted(exposed - protected)
    standoff_violations = []
    unevaluated = []
    for reference, part in sorted(netlist.PARTS.items()):
        spec = parameters["parts"].get(part["mpn"] or "")
        if not spec or "reverse_standoff_v" not in spec:
            continue
        standoff = _quantity(spec["reverse_standoff_v"])
        for pin_number in ("1", "2"):
            node = pin_map.get("%s.%s" % (reference, pin_number))
            if node == "GND":
                continue
            span = netlist.RAILS.get(node) or \
                netlist.NODE_VOLTAGE_RANGES.get(node)
            if span is None or not standoff.known:
                unevaluated.append("%s.%s" % (reference, pin_number))
                continue
            if span["max_v"] > standoff.value:
                standoff_violations.append((reference, span["max_v"]))
    standoff_claim = _structural_claim(
        "esd_standoff", "esd_device_not_conducting_in_operation",
        standoff_violations, "standoff_above_rail_maximum")
    if unevaluated:
        standoff_claim = _claim(
            "esd_standoff", "count",
            "esd_device_not_conducting_in_operation", None, None, (),
            _requirement("standoff_above_rail_maximum", "<=", 0.0),
            claim.UNKNOWN, scope_level="board")
    return [{
        "id": "esd_protection_coverage",
        "identity": "exposed_contacts",
        "violations": violations,
        "claim": _structural_claim(
            "exposed_contacts", "esd_protection_present", violations,
            "exposed_contacts_protected_to_ground"),
    }, {
        "id": "esd_standoff_above_rail",
        "identity": "esd_standoff",
        "violations": standoff_violations,
        "unevaluated": unevaluated,
        "claim": standoff_claim,
    }]


def net_pins_of_reference(net_pins, reference):
    prefix = reference + "."
    return [pin_ref for pins in net_pins.values() for pin_ref in pins
            if pin_ref.startswith(prefix)]


def evaluate_probe_access(parameters):
    pin_map = _pin_map()
    test_point_nets = set()
    for reference in netlist.PARTS:
        if reference.startswith("TP"):
            net_name = pin_map.get(reference + ".1")
            if net_name:
                test_point_nets.add(net_name)
    required = set(PROBE_REQUIRED_NETS)
    required |= {name for name in netlist.NETS if name.startswith("LED_CH")}
    violations = sorted(required - test_point_nets)
    links = []
    for reference in netlist.PARTS:
        if not reference.startswith("R"):
            continue
        nets = {pin_map.get(reference + ".1"), pin_map.get(reference + ".2")}
        if nets == {"VBUS", "+5V"}:
            links.append(reference)
    if len(links) != 1:
        violations.append("supply_current_link")
    return {
        "id": "probe_access",
        "identity": "probe_points",
        "violations": violations,
        "series_links": links,
        "claim": _structural_claim(
            "probe_points", "bring_up_probe_access", violations,
            "required_nets_probeable"),
    }


FOOTPRINT_SEARCH_PATHS = (
    os.path.join(REPO_ROOT, "library"),
    FOOTPRINT_ROOT,
)


def _footprint_path(footprint):
    library, _, name = footprint.partition(":")
    for base in FOOTPRINT_SEARCH_PATHS:
        candidate = os.path.join(base, library + ".pretty",
                                 name + ".kicad_mod")
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(FOOTPRINT_ROOT, library + ".pretty",
                        name + ".kicad_mod")


def evaluate_assembly_process(parameters):
    missing = []
    through_hole = []
    for reference, part in sorted(netlist.PARTS.items()):
        if not part["in_bom"] or not part["footprint"]:
            continue
        path = _footprint_path(part["footprint"])
        if not os.path.isfile(path):
            missing.append((reference, "footprint_missing"))
            continue
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        if re.findall(r'\(pad "[^"]*" thru_hole ', text):
            through_hole.append(reference)
    limit = netlist.ASSEMBLY_POLICY["max_through_hole_soldered_parts"]
    results = [{
        "id": "assembly_footprints_resolve",
        "identity": "assembly_footprints",
        "violations": missing,
        "claim": _structural_claim(
            "assembly_footprints", "every_bom_footprint_resolves", missing,
            "bom_footprints_resolve"),
    }, {
        "id": "through_hole_soldered_parts",
        "identity": "assembly_process",
        "parts": through_hole,
        "claim": _claim(
            "assembly_process", "count",
            "through_hole_soldering_steps", float(len(through_hole)),
            DIRECT, (),
            _requirement("within_declared_through_hole_allowance", "<=",
                         float(limit)),
            claim.EXACT, scope_level="board"),
    }]
    return results


def evaluate_connector_contacts(parameters):
    pin_map = _pin_map()
    results = []
    for reference in sorted(netlist.PARTS):
        spec = _part_parameters(parameters, reference)
        if not spec or "contact_assignment" not in spec:
            continue
        expected_nets = netlist.CONNECTOR_FUNCTION_NETS.get(reference, {})
        declared = spec["contact_assignment"]["map"]
        violations = []
        for contact, function in sorted(declared.items()):
            pin_ref = "%s.%s" % (reference, contact)
            actual = pin_map.get(pin_ref)
            if function in expected_nets:
                if actual != expected_nets[function]:
                    violations.append((contact, function, actual))
            elif actual is not None:
                violations.append((contact, function, actual))
        results.append({
            "id": "connector_contact_assignment",
            "identity": "%s:%s" % (reference, _mpn(reference)),
            "violations": violations,
            "claim": _structural_claim(
                "%s_contacts" % reference,
                "connector_contacts_match_drawing", violations,
                "contacts_carry_their_declared_function"),
        })
    return results


def evaluate_contact_ratings(parameters):
    results = []
    for reference in sorted(netlist.PARTS):
        spec = _part_parameters(parameters, reference)
        if not spec or "contact_voltage_max_v" not in spec:
            continue
        rating = _quantity(spec["contact_voltage_max_v"])
        rail_max = max(rail["max_v"] for rail in netlist.RAILS.values())
        identity = "%s:%s" % (reference, _mpn(reference))
        margin = rating.value - rail_max if rating.known else None
        results.append({
            "id": "contact_voltage_rating_margin",
            "identity": identity,
            "claim": _claim(
                identity, "V", "connector_rating_covers_rail", margin,
                rating.basis, rating.documents,
                _requirement("rating_at_or_above_rail_maximum", ">=", 0.0),
                claim.LOWER_BOUND if margin is not None else claim.UNKNOWN,
                scope_level="measurement"),
        })
    return results


def _footprint_pads(path):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    pads = []
    for match in re.finditer(
            r'\(pad "([^"]*)" (\w+) \w+\s*\(at ([-\d.]+) ([-\d.]+)'
            r'[^)]*\)\s*\(size ([-\d.]+) ([-\d.]+)\)', text, re.S):
        number, kind, x, y, width, height = match.groups()
        pads.append({"number": number, "kind": kind,
                     "x": float(x), "y": float(y),
                     "size": (float(width), float(height))})
    return pads


def evaluate_land_patterns(parameters, tolerance_mm=0.001):
    results = []
    for reference in sorted(netlist.PARTS):
        spec = _part_parameters(parameters, reference)
        if not spec or "land_pattern" not in spec:
            continue
        declared = spec["land_pattern"]
        identity = "%s:%s" % (reference, _mpn(reference))
        if declared.get("pad_geometry_verified") is False:
            results.append({
                "id": "footprint_land_pattern",
                "identity": identity,
                "violations": [],
                "claim": _claim(
                    identity, "count", "footprint_matches_package_drawing",
                    None, None, (),
                    _requirement("footprint_land_pattern_matches_document",
                                 "<=", 0.0),
                    claim.UNKNOWN, scope_level="board"),
            })
            continue
        path = _footprint_path(netlist.PARTS[reference]["footprint"])
        if not os.path.isfile(path):
            results.append(_land_pattern_result(
                identity, [("footprint_missing", path)]))
            continue
        all_pads = _footprint_pads(path)
        if "pads" in declared:
            results.append(_land_pattern_result(
                identity, _compare_pad_list(declared["pads"], all_pads,
                                            tolerance_mm)))
            continue
        pads = [pad for pad in all_pads if pad["kind"] == "smd"]
        problems = []
        if len(pads) != declared["pad_count"]:
            problems.append(("pad_count", len(pads), declared["pad_count"]))
        if "pad_size_mm" in declared:
            wanted = tuple(declared["pad_size_mm"])
            for pad in pads:
                if max(abs(pad["size"][0] - wanted[0]),
                       abs(pad["size"][1] - wanted[1])) > tolerance_mm:
                    problems.append(("pad_size", pad["number"], pad["size"]))
        if "pad_centres_mm" in declared:
            wanted_centres = sorted(
                (round(x, 4), round(y, 4))
                for x, y in declared["pad_centres_mm"])
            actual = sorted((round(pad["x"], 4), round(pad["y"], 4))
                            for pad in pads)
            if len(actual) != len(wanted_centres) or any(
                    max(abs(a[0] - b[0]), abs(a[1] - b[1])) > tolerance_mm
                    for a, b in zip(actual, wanted_centres)):
                problems.append(("pad_centres", actual, wanted_centres))
        if "pitch_mm" in declared and len(pads) > 1:
            spacings = sorted(
                {round(abs(a["y"] - b["y"]) or abs(a["x"] - b["x"]), 4)
                 for a, b in zip(pads, pads[1:])})
            if not any(abs(value - declared["pitch_mm"]) <= tolerance_mm
                       for value in spacings):
                problems.append(("pitch", spacings, declared["pitch_mm"]))
        results.append(_land_pattern_result(identity, problems))
    return results


def _compare_pad_list(declared_pads, actual_pads, tolerance_mm):
    def key(entry):
        return (entry["number"], round(entry["x"], 4), round(entry["y"], 4))

    problems = []
    actual = {}
    for pad in actual_pads:
        actual.setdefault(pad["number"], []).append(pad)
    for want in declared_pads:
        matches = actual.get(want["number"], [])
        hit = None
        for pad in matches:
            if (abs(pad["x"] - want["x"]) <= tolerance_mm
                    and abs(pad["y"] - want["y"]) <= tolerance_mm):
                hit = pad
                break
        if hit is None:
            problems.append(("missing_pad", want["number"],
                             want["x"], want["y"]))
            continue
        matches.remove(hit)
        if (abs(hit["size"][0] - want["w"]) > tolerance_mm
                or abs(hit["size"][1] - want["h"]) > tolerance_mm):
            problems.append(("pad_size", want["number"], hit["size"],
                             (want["w"], want["h"])))
        if hit["kind"] != want["kind"]:
            problems.append(("pad_kind", want["number"], hit["kind"],
                             want["kind"]))
    for number, leftover in actual.items():
        for pad in leftover:
            problems.append(("undeclared_pad", number, pad["x"], pad["y"]))
    return problems


def _land_pattern_result(identity, problems):
    return {
        "id": "footprint_land_pattern",
        "identity": identity,
        "violations": problems,
        "claim": _structural_claim(
            identity, "footprint_matches_package_drawing", problems,
            "footprint_land_pattern_matches_document"),
    }


def evaluate_debug_contract(parameters):
    pin_map = _pin_map()
    violations = []
    for pin_ref, expected in sorted(DEBUG_CONTRACT.items()):
        if pin_map.get(pin_ref) != expected:
            violations.append((pin_ref, pin_map.get(pin_ref), expected))
    return {
        "id": "debug_connector_contract",
        "identity": "swd_connector",
        "violations": violations,
        "claim": _structural_claim(
            "swd_connector", "in_circuit_program_and_halt", violations,
            "debug_connector_carries_swd_contract"),
    }


#: Signal propagation in FR-4 microstrip, the slower (longer, and so more
#: permissive of a discontinuity) end of the usual range; using the faster
#: end would make the derived limit larger.
MICROSTRIP_VELOCITY_MM_PER_S = 1.4e11

#: A discontinuity below a tenth of the rise-time length is electrically
#: short: the reflection it produces has not developed before the edge is
#: over. The tenth is the customary engineering margin, not a measurement.
ELECTRICALLY_SHORT_FRACTION = 0.1


def evaluate_reference_gap_limit(parameters):
    """Is the declared unreferenced-run limit electrically short?

    A gap in the reference conductor forces the return current to detour.
    Whether that matters is set by the edge, not by the trace: the limit
    the board declares must be short against the length the fastest edge
    occupies while it is rising. The rise time is the design's own - the
    series resistor into the receiver's input capacitance - so this rule
    reads the layout limit back against the parts that set it.
    """
    from . import simulation
    manifest_path = os.path.join(REPO_ROOT, "board", "manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        interfaces = json.load(handle)["timing"]["interfaces"]
    rise_s = (2.2 * simulation._resistor_ohms("R4")
              * simulation.LED_INPUT_CAPACITANCE_F)
    allowed_mm = (ELECTRICALLY_SHORT_FRACTION * rise_s
                  * MICROSTRIP_VELOCITY_MM_PER_S)
    violations = []
    for name, declared in sorted(interfaces.items()):
        limit = declared.get("max_unreferenced_mm")
        if limit is None or limit > allowed_mm:
            violations.append((name, limit, allowed_mm))
    return {
        "id": "reference_gap_limit_is_electrically_short",
        "identity": "led_data",
        "violations": violations,
        "claim": _structural_claim(
            "led_data", "return_path_discontinuity", violations,
            "declared_unreferenced_run_is_electrically_short"),
    }


def evaluate_all():
    parameters = load_parameters()
    results = []
    results.extend(evaluate_logic_levels(parameters))
    results.append(evaluate_supply_current(parameters))
    results.append(evaluate_vbus_capacitance(parameters))
    results.extend(evaluate_absolute_maximum(parameters))
    results.append(evaluate_source_range_coverage(parameters))
    results.append(evaluate_cc_terminations(parameters))
    results.extend(evaluate_esd_coverage(parameters))
    results.append(evaluate_probe_access(parameters))
    results.extend(evaluate_assembly_process(parameters))
    results.extend(evaluate_connector_contacts(parameters))
    results.extend(evaluate_contact_ratings(parameters))
    results.extend(evaluate_land_patterns(parameters))
    results.append(evaluate_debug_contract(parameters))
    results.append(evaluate_reference_gap_limit(parameters))
    for result in results:
        result["verdict"] = claim.verdict(result["claim"])
    return results


def summarise(results):
    counts = {}
    for result in results:
        outcome = result["verdict"]["result"]
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


if __name__ == "__main__":
    evaluated = evaluate_all()
    for result in sorted(evaluated, key=lambda item: (
            item["verdict"]["result"], item["id"], item["identity"])):
        quantity = result["claim"]["quantity"]
        value = quantity.get("value")
        rendered = "-" if value is None else "%.6g" % value
        basis = result["verdict"]["knowledge_basis"]
        sys.stdout.write("%-9s %-9s %-32s %-28s %10s %s\n" % (
            result["verdict"]["result"],
            basis["kind"] if basis else "-",
            result["id"], result["identity"], rendered,
            result["claim"]["units"]))
    sys.stdout.write("\n" + json.dumps(summarise(evaluated),
                                       sort_keys=True) + "\n")
