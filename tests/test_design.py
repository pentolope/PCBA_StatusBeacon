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
                    netlist, rules, sexpr)

KNOWN_OPEN_FAILURES = {("usb_source_range_coverage",
                        "vbus_declared_vs_vsafe5v")}

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

    def test_unknown_results_carry_no_number(self):
        for item in self.results:
            if item["verdict"]["result"] == "UNKNOWN":
                self.assertEqual(item["claim"]["quantity"], {})

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


if __name__ == "__main__":
    unittest.main()


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
