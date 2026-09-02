from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from design import (build, cost, evidence, ksym, libraries,  # noqa: E402
                    netlist, physical, rules, sexpr, simulation)

KNOWN_OPEN_FAILURES = set()

SCHEMATIC_ONLY_PREFIXES = ("#FLG",)


class DesignSource(unittest.TestCase):
    def test_pin_assignment_is_unique(self):
        mapping = netlist.pin_to_net()
        self.assertEqual(len(mapping),
                         sum(len(pins) for pins in netlist.NETS.values()))

    def test_every_symbol_pin_is_connected_or_declared_no_connect(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        mapping = netlist.pin_to_net()
        declared = set(netlist.NO_CONNECT)
        unresolved = []
        for reference, part in netlist.PARTS.items():
            for number in library.pins(part["lib_id"]):
                pin_ref = "%s.%s" % (reference, number)
                if pin_ref not in mapping and pin_ref not in declared:
                    unresolved.append(pin_ref)
        self.assertEqual(unresolved, [])

    def test_declared_pins_exist_on_the_symbol(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        missing = []
        for pin_ref in list(netlist.pin_to_net()) + list(netlist.NO_CONNECT):
            reference, _, number = pin_ref.partition(".")
            lib_id = netlist.PARTS[reference]["lib_id"]
            if number not in library.pins(lib_id):
                missing.append(pin_ref)
        self.assertEqual(missing, [])

    def test_led_chain_is_a_single_daisy_chain(self):
        mapping = netlist.pin_to_net()
        for index in range(1, netlist.LED_COUNT + 1):
            self.assertEqual(mapping["D%d.4" % index],
                             "LED_CH%d" % (index - 1))
            self.assertEqual(mapping["D%d.2" % index], "LED_CH%d" % index)

    def test_every_led_has_local_decoupling(self):
        mapping = netlist.pin_to_net()
        for index in range(netlist.LED_COUNT):
            reference = "C%d" % (index + 5)
            self.assertEqual(mapping[reference + ".1"], "+5V")
            self.assertEqual(mapping[reference + ".2"], "GND")


class GeneratedSchematic(unittest.TestCase):
    def test_committed_schematic_matches_the_generator(self):
        with open(build.schematic_path(), "r", encoding="utf-8") as handle:
            committed = handle.read()
        self.assertEqual(committed, build.generate_schematic_text())

    def test_generation_is_deterministic(self):
        self.assertEqual(build.generate_schematic_text(),
                         build.generate_schematic_text())

    def test_exported_netlist_matches_the_design_source(self):
        with tempfile.TemporaryDirectory() as workdir:
            target = os.path.join(workdir, "exported.net")
            subprocess.run(
                ["kicad-cli", "sch", "export", "netlist", "--format",
                 "kicadsexpr", "-o", target, build.schematic_path()],
                check=True, capture_output=True)
            with open(target, "r", encoding="utf-8") as handle:
                tree = sexpr.parse(handle.read())
        exported = {}
        for net in sexpr.find_all(sexpr.find(tree, "nets") or [], "net"):
            name = str(sexpr.find(net, "name")[1])
            exported[name] = {
                "%s.%s" % (str(sexpr.find(node, "ref")[1]),
                           str(sexpr.find(node, "pin")[1]))
                for node in sexpr.find_all(net, "node")}
        for name, pins in netlist.NETS.items():
            expected = {pin for pin in pins
                        if not pin.startswith(SCHEMATIC_ONLY_PREFIXES)}
            self.assertIn(name, exported)
            self.assertEqual(exported[name], expected, name)


class FrozenEvidence(unittest.TestCase):
    def test_index_matches_the_committed_documents(self):
        self.assertEqual(evidence.verify(), [])

    def test_index_is_current(self):
        self.assertEqual(evidence.load_index(), evidence.compute_index())

    def test_every_cited_document_is_frozen(self):
        documents = set(evidence.load_index()["documents"])
        cited = set()

        def collect(node):
            if isinstance(node, dict):
                if "document" in node:
                    cited.add(node["document"])
                for value in node.values():
                    collect(value)
            elif isinstance(node, list):
                for value in node:
                    collect(value)

        collect(rules.load_parameters())
        self.assertEqual(sorted(cited - documents), [])

    def test_every_parameter_record_names_a_selected_part(self):
        selected = {part["mpn"] for part in netlist.PARTS.values()
                    if part["mpn"]}
        declared = set(rules.load_parameters()["parts"])
        self.assertEqual(sorted(declared - selected), [])
        self.assertEqual(sorted(selected - declared), [])

    def test_every_frozen_document_applies_to_a_selected_part(self):
        selected = {part["mpn"] for part in netlist.PARTS.values()
                    if part["mpn"]}
        for name, entry in evidence.load_index()["documents"].items():
            self.assertTrue(set(entry["applies_to"]) & selected, name)


class ElectricalRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = rules.evaluate_all()
        cls.by_key = {(item["id"], item["identity"]): item
                      for item in cls.results}

    def test_no_unexpected_failure(self):
        failures = {key for key, item in self.by_key.items()
                    if item["verdict"]["result"] == "FAIL"}
        self.assertEqual(failures - KNOWN_OPEN_FAILURES, set())

    def test_known_open_failures_are_still_open(self):
        for key in KNOWN_OPEN_FAILURES:
            self.assertEqual(self.by_key[key]["verdict"]["result"], "FAIL")

    def test_unknown_knowledge_carries_no_number(self):
        """A claim that knows nothing states nothing."""
        for item in self.results:
            if item["claim"]["knowledge"] == "unknown":
                self.assertEqual(item["claim"]["quantity"], {},
                                 item["identity"])

    def test_a_bounded_claim_may_be_undecided_yet_still_carry_a_number(self):
        """An UNDECIDED verdict is not the same as an UNKNOWN claim.

        A bound that falls the wrong side of its requirement measures
        something real and still cannot settle the question: the margin is
        at least this, which neither proves the requirement met nor proves
        it broken. Collapsing the two would either hide the number or
        report a failure the evidence does not support.
        """
        undecided = [item for item in self.results
                     if item["verdict"]["result"] == "UNKNOWN"
                     and item["claim"]["knowledge"] != "unknown"]
        for item in undecided:
            self.assertIn(item["claim"]["knowledge"],
                          ("lower_bound", "upper_bound", "approximate"),
                          item["identity"])
            self.assertIn("value", item["claim"]["quantity"],
                          item["identity"])

    def test_mcu_drives_the_led_chain(self):
        item = self.by_key[("logic_high_margin", "U1.20->D1.4")]
        self.assertEqual(item["verdict"]["result"], "PASS")
        self.assertEqual(item["verdict"]["knowledge_basis"]["kind"], "direct")
        self.assertGreater(item["claim"]["quantity"]["value"], 0.0)

    def test_supply_current_budget_remains_assumption_dependent(self):
        item = self.by_key[("supply_current_budget", "board_vbus_current")]
        self.assertEqual(item["verdict"]["result"], "PASS")
        self.assertEqual(item["verdict"]["knowledge_basis"]["kind"], "assumed")
        self.assertLessEqual(item["claim"]["quantity"]["value"],
                             netlist.PORT_BUDGET_A)

    def test_vbus_bypass_capacitance_within_usb_limit(self):
        item = self.by_key[("vbus_bypass_capacitance", "vbus_domain")]
        self.assertEqual(item["verdict"]["result"], "PASS")
        self.assertLessEqual(item["claim"]["quantity"]["value"],
                             netlist.VBUS_CAPACITANCE_LIMIT_F)

    def test_structural_rules_pass(self):
        for identifier in ("typec_sink_cc_terminations",
                           "esd_protection_coverage",
                           "esd_standoff_above_rail",
                           "probe_access",
                           "assembly_footprints_resolve",
                           "connector_contact_assignment",
                           "through_hole_soldered_parts",
                           "debug_connector_contract"):
            matches = [item for item in self.results
                       if item["id"] == identifier]
            self.assertTrue(matches, identifier)
            for item in matches:
                self.assertEqual(item["verdict"]["result"], "PASS",
                                 (identifier, item.get("violations")))

    def test_footprints_match_their_package_drawings(self):
        matches = [item for item in self.results
                   if item["id"] == "footprint_land_pattern"]
        self.assertTrue(matches)
        for item in matches:
            self.assertEqual(item["verdict"]["result"], "PASS",
                             (item["identity"], item.get("violations")))

    def test_every_footprint_geometry_is_document_backed(self):
        parameters = rules.load_parameters()
        for mpn, spec in parameters["parts"].items():
            land = spec.get("land_pattern")
            if land is None:
                continue
            self.assertNotEqual(land.get("pad_geometry_verified"), False, mpn)
            self.assertIn("document", land)

    def test_through_hole_soldering_stays_within_the_declared_allowance(self):
        item = self.by_key[("through_hole_soldered_parts", "assembly_process")]
        self.assertEqual(item["verdict"]["result"], "PASS")
        self.assertLessEqual(
            item["claim"]["quantity"]["value"],
            netlist.ASSEMBLY_POLICY["max_through_hole_soldered_parts"])

    def test_connector_ratings_cover_the_rail(self):
        matches = [item for item in self.results
                   if item["id"] == "contact_voltage_rating_margin"]
        self.assertTrue(matches)
        for item in matches:
            self.assertEqual(item["verdict"]["result"], "PASS",
                             item["identity"])
            self.assertGreaterEqual(item["claim"]["quantity"]["value"], 0.0)

    def test_every_result_carries_a_requirement(self):
        for item in self.results:
            self.assertIsNotNone(item["claim"]["requirement"])
            self.assertEqual(item["claim"]["requirement"]["source"],
                             "BRIEF.md")


class ToolkitManifest(unittest.TestCase):
    def test_manifest_declares_the_generated_sources(self):
        path = os.path.join(REPO_ROOT, "board", "manifest.json")
        with open(path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertEqual(manifest["sources"]["schematic"],
                         os.path.basename(build.schematic_path()))
        self.assertEqual(manifest["sources"]["project"],
                         os.path.basename(build.project_path()))
        self.assertEqual(manifest["board_id"], netlist.PROJECT_NAME)


class GeneratedLibraries(unittest.TestCase):
    def test_committed_libraries_match_the_generator(self):
        for path, text in libraries.artifacts().items():
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), text, path)

    def test_generated_symbol_pins_match_the_declared_pin_table(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        pins = library.pins("StatusBeacon:" + libraries.PY32_SYMBOL_NAME)
        declared = {number: name
                    for number, name, _ in libraries.PY32F003F1XPX_PINS}
        self.assertEqual(sorted(pins), sorted(declared))
        for number, name in declared.items():
            self.assertEqual(pins[number][0].name, name)


class BomCost(unittest.TestCase):
    def test_every_bom_part_is_in_the_frozen_catalogue(self):
        catalog = cost.load_catalog()["parts"]
        self.assertEqual(sorted(set(cost.line_items()) - set(catalog)), [])

    def test_catalogue_entries_match_the_selected_parts(self):
        catalog = cost.load_catalog()["parts"]
        for reference, part in netlist.PARTS.items():
            code = part.get("lcsc")
            if not code or not part["in_bom"]:
                continue
            if part["mpn"]:
                self.assertEqual(catalog[code]["mpn"], part["mpn"], reference)

    def test_cost_decreases_with_build_quantity(self):
        costs = [cost.bom_cost(quantity)["per_board_usd"]
                 for quantity in cost.DEFAULT_BUILD_QUANTITIES]
        self.assertEqual(costs, sorted(costs, reverse=True))

    def test_every_passive_is_a_basic_part(self):
        catalog = cost.load_catalog()["parts"]
        for reference, part in netlist.PARTS.items():
            if reference[0] not in ("R", "C") or not part["in_bom"]:
                continue
            self.assertEqual(catalog[part["lcsc"]]["library_type"],
                             cost.BASIC_LIBRARY_TYPE, reference)

    def test_stock_supports_a_prototype_build(self):
        for code, boards in cost.stock_limited_boards().items():
            self.assertGreaterEqual(boards, 50, code)


class BoardLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from design import layout
        cls.layout = layout
        cls.board = layout.pcbnew.LoadBoard(layout.BOARD_PATH)
        cls.footprints = {fp.GetReference(): fp
                          for fp in cls.board.GetFootprints()}

    def test_every_on_board_part_is_placed(self):
        expected = {ref for ref, part in netlist.PARTS.items()
                    if part["on_board"] and part["footprint"]}
        self.assertEqual(set(self.footprints), expected)

    def test_led_ring_is_on_its_polar_grid(self):
        import math
        for index in range(netlist.LED_COUNT):
            footprint = self.footprints["D%d" % (index + 1)]
            position = footprint.GetPosition()
            x = self.layout.pcbnew.ToMM(position.x) - self.layout.ORIGIN_MM[0]
            y = self.layout.ORIGIN_MM[1] - self.layout.pcbnew.ToMM(position.y)
            self.assertAlmostEqual(math.hypot(x, y),
                                   self.layout.LED_RING_RADIUS_MM, places=3)
            angle = math.degrees(math.atan2(y, x)) % 360.0
            pitch = self.layout.LED_PITCH_DEG
            nearest = round(angle / pitch) * pitch
            error = abs(((angle - nearest + 180.0) % 360.0) - 180.0)
            self.assertLess(error, 0.01)

    def test_board_carries_both_reference_planes(self):
        zones = {(z.GetNetname(), z.GetLayer()) for z in self.board.Zones()}
        self.assertIn(("GND", self.layout.pcbnew.B_Cu), zones)
        self.assertIn(("+5V", self.layout.pcbnew.F_Cu), zones)

    def test_every_pad_carries_a_net(self):
        unnetted = [
            "%s.%s" % (ref, pad.GetNumber())
            for ref, fp in self.footprints.items() for pad in fp.Pads()
            if pad.GetNumber() and not pad.GetNetname()]
        self.assertEqual(unnetted, [])

    def _routing_record(self):
        with open(os.path.join(REPO_ROOT, "generated", "routing.json"),
                  "r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_routing_record_satisfies_the_toolkit_contract(self):
        sys.path.insert(0, os.path.join(REPO_ROOT, "tooling",
                                        "PCBA_AutoDesignAndTest"))
        from pcbqa import routing_record
        record = self._routing_record()
        self.assertIsNotNone(routing_record.validate(record))
        self.assertEqual(
            routing_record.compare_to_board(
                record, self._board_digest()), [])

    def _board_digest(self):
        import hashlib
        with open(self.layout.BOARD_PATH, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    def test_provenance_binds_to_the_authoritative_board(self):
        record = self._routing_record()
        self.assertEqual(record["adopted_sha256"], self._board_digest())

    def test_every_attempt_started_from_the_same_source(self):
        record = self._routing_record()
        sources = {attempt["source_sha256"] for attempt in record["attempts"]}
        self.assertEqual(sources, {record["source_sha256"]})

    def test_every_post_router_transform_is_declared(self):
        sys.path.insert(0, os.path.join(REPO_ROOT, "tooling",
                                        "PCBA_AutoDesignAndTest"))
        from pcbqa import routing_record
        for stage in routing_record.transforms(self._routing_record()):
            self.assertTrue(str(stage["transform"]).strip())
            self.assertTrue(stage["effects"])

    def test_the_router_was_the_vendored_submodule(self):
        record = self._routing_record()
        self.assertEqual(record["context"]["resolution"]["origin"],
                         "vendored submodule")
        self.assertIn("+5V", record["context"]["routed_nets"])


class TestSuiteIsWhole(unittest.TestCase):
    """Every test in this file must actually be collected.

    unittest.main() calls sys.exit(), so a __main__ block anywhere but the
    end silently stops the module being read - the classes after it are
    never even defined, and the run reports OK for the ones that were.
    """

    def test_the_entry_point_is_the_last_statement(self):
        import ast

        with open(os.path.abspath(__file__), encoding="utf-8") as handle:
            body = ast.parse(handle.read()).body
        guards = [index for index, node in enumerate(body)
                  if isinstance(node, ast.If)
                  and "__main__" in ast.unparse(node.test)]
        self.assertEqual(len(guards), 1)
        self.assertEqual(guards[0], len(body) - 1,
                         "the __main__ guard must be last; anything after it "
                         "is never collected")

    def test_every_declared_test_runs(self):
        import ast

        with open(os.path.abspath(__file__), encoding="utf-8") as handle:
            body = ast.parse(handle.read()).body
        declared = 0
        for node in body:
            if isinstance(node, ast.ClassDef):
                declared += sum(
                    1 for member in node.body
                    if isinstance(member, ast.FunctionDef)
                    and member.name.startswith("test_"))
        loaded = unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__])
        self.assertEqual(declared, loaded.countTestCases())


class SimulationInputs(unittest.TestCase):
    """The scenarios must describe this board, from frozen evidence."""

    @classmethod
    def setUpClass(cls):
        cls.parameters = rules.load_parameters()
        with open(os.path.join(REPO_ROOT, "board", "manifest.json"),
                  encoding="utf-8") as handle:
            cls.manifest = json.load(handle)

    def _scenarios(self):
        for stage, files in sorted(
                self.manifest["simulation"]["stages"].items()):
            for relative in files:
                with open(os.path.join(REPO_ROOT, relative),
                          encoding="utf-8") as handle:
                    yield stage, relative, json.load(handle)

    def test_every_declared_scenario_exists_and_is_current(self):
        written = {os.path.relpath(path, REPO_ROOT).replace("\\", "/")
                   for path in simulation.write()}
        declared = {relative for _stage, files in
                    self.manifest["simulation"]["stages"].items()
                    for relative in files}
        self.assertEqual(declared, written)

    def test_the_generator_is_deterministic(self):
        first = {}
        for path in simulation.write():
            with open(path, encoding="utf-8") as handle:
                first[path] = handle.read()
        for path in simulation.write():
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), first[path], path)

    def test_every_required_stage_is_declared(self):
        for stage in self.manifest["simulation"]["required_stages"]:
            self.assertIn(stage, self.manifest["simulation"]["stages"])
            self.assertTrue(self.manifest["simulation"]["stages"][stage])

    def test_passive_values_come_from_the_netlist(self):
        wanted = {simulation._resistor_ohms("R4"),
                  simulation._resistor_ohms("R5"),
                  simulation._resistor_ohms("R6"),
                  simulation._sum_capacitance("+5V"),
                  simulation._sum_capacitance("BTN_SW")}
        seen = set()
        for _stage, _relative, scenario in self._scenarios():
            for element in scenario["elements"]:
                if "value" in element:
                    seen.add(element["value"])
        self.assertTrue(wanted <= seen, sorted(wanted - seen))

    def test_thresholds_come_from_the_frozen_datasheets(self):
        led = simulation.led(self.parameters)
        mcu = simulation.mcu(self.parameters)
        rail = netlist.RAILS["+5V"]["max_v"]
        allowed = {
            led["supply"]["abs_min_v"]["value"],
            led["supply"]["abs_max_v"]["value"],
            mcu["supply"]["characterised_max_v"]["value"],
            led["digital_inputs"]["4"]["vih_min"]["factor_of_supply"] * rail,
            mcu["digital_inputs"]["19"]["vih_min"]["factor_of_supply"] * rail,
        }
        asserted = 0
        for _stage, relative, scenario in self._scenarios():
            for measurement in scenario["measurements"]:
                assertion = measurement.get("assertion")
                if assertion is None:
                    continue
                asserted += 1
                self.assertIn(assertion["value"], allowed,
                              "%s asserts %r, which no frozen parameter "
                              "states" % (relative, assertion["value"]))
        self.assertGreater(asserted, 0)

    def test_every_ideal_element_declares_what_it_stands_in_for(self):
        for _stage, relative, scenario in self._scenarios():
            ideal = {element["name"] for element in scenario["elements"]
                     if element["kind"] != "model_instance"}
            self.assertEqual(set(scenario["assumptions"]), ideal, relative)

    def test_the_extracted_model_is_referenced_by_its_manifest_alias(self):
        aliases = set(
            self.manifest["simulation"]["extracted_models"]["paths"])
        referenced = {element["model"]
                      for _stage, _relative, scenario in self._scenarios()
                      for element in scenario["elements"]
                      if element["kind"] == "model_instance"}
        self.assertTrue(referenced <= aliases, sorted(referenced - aliases))
        self.assertIn(simulation.EXTRACTED_MODEL_ALIAS, aliases)


class FabricationRequirements(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(REPO_ROOT, "fab", "requirements.json"),
                  encoding="utf-8") as handle:
            self.requirements = json.load(handle)
        with open(os.path.join(REPO_ROOT, "board", "manifest.json"),
                  encoding="utf-8") as handle:
            self.manifest = json.load(handle)

    def test_the_declared_minima_are_what_the_layout_uses(self):
        self.assertLessEqual(self.requirements["min_track_mm"],
                             __import__("design.layout", fromlist=["layout"])
                             .TRACK_WIDTH_MM)
        layout = __import__("design.layout", fromlist=["layout"])
        self.assertLessEqual(self.requirements["min_space_mm"],
                             layout.CLEARANCE_MM)
        self.assertLessEqual(self.requirements["min_drill_mm"],
                             layout.VIA_DRILL_MM)
        self.assertLessEqual(self.requirements["min_via_diameter_mm"],
                             layout.VIA_DIAMETER_MM)

    def test_the_selection_is_feasible_and_rejects_nothing(self):
        with open(os.path.join(REPO_ROOT, "fab", "selection.json"),
                  encoding="utf-8") as handle:
            selection = json.load(handle)
        self.assertTrue(selection["feasible"])
        self.assertEqual(selection["rejections"], [])

    def test_the_frozen_physical_inputs_still_agree_with_the_catalog(self):
        self.assertEqual(physical.verify(), [])

    def test_the_frozen_physical_inputs_are_regenerable(self):
        with open(physical.PHYSICAL_PATH, encoding="utf-8") as handle:
            committed = json.load(handle)
        self.assertEqual(committed, physical.resolve())

    def test_every_physical_input_is_approved_evidence(self):
        with open(physical.PHYSICAL_PATH, encoding="utf-8") as handle:
            document = json.load(handle)
        records = list(document["copper_thickness_mm"].values())
        records.append(document["board_thickness_mm"])
        for record in records:
            self.assertIn(record["source_type"],
                          ("approved-evidence", "derived"))

    def test_the_layer_count_matches_the_declared_stackup(self):
        expected = self.manifest["stackup"]["expected"]
        self.assertEqual(self.requirements["copper_layers"], len(expected))


class DeclaredContracts(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(REPO_ROOT, "board", "manifest.json"),
                  encoding="utf-8") as handle:
            self.manifest = json.load(handle)

    def _pin_map(self, reference):
        mapping = {}
        for net, pins in netlist.NETS.items():
            for pin_ref in pins:
                if pin_ref.startswith(reference + "."):
                    mapping[pin_ref.split(".", 1)[1]] = net
        for pin_ref in netlist.NO_CONNECT:
            if pin_ref.startswith(reference + "."):
                mapping[pin_ref.split(".", 1)[1]] = None
        return mapping

    def test_every_connector_contract_matches_the_netlist(self):
        contracts = self.manifest["connector_contracts"]
        self.assertTrue(contracts)
        for contract in contracts:
            reference = contract["reference"]
            expected = self._pin_map(reference)
            self.assertEqual(contract["pin_map"], expected, reference)
            self.assertEqual(contract["required_positions"], len(expected),
                             reference)

    def test_the_routing_acceptance_set_excludes_release_artifact_gates(self):
        accepted = set(self.manifest["routing"]["acceptance_gates"])
        for gate in ("ARCH.CONTENTS", "ARCH.PROVENANCE", "BOM.NATIVE_PARITY",
                     "CPL.NATIVE_PARITY", "STACK.GERBER_PARITY",
                     "PROV.REPORT_FRESHNESS"):
            self.assertNotIn(gate, accepted)

    def test_every_mandatory_gate_is_one_the_last_validation_passed(self):
        with open(os.path.join(REPO_ROOT, "generated", "release",
                               "validation.json"), encoding="utf-8") as handle:
            validation = json.load(handle)
        passed = {entry["gate"] for entry in validation["gates"]
                  if entry["status"] == "PASS"}
        self.assertTrue(
            set(self.manifest["release_profile"]["mandatory_gates"]) <= passed)

    def test_the_reference_gap_limit_is_electrically_short(self):
        result = rules.evaluate_reference_gap_limit(rules.load_parameters())
        self.assertEqual(result["violations"], [])


if __name__ == "__main__":
    unittest.main()
