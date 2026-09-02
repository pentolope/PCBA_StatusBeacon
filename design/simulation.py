from __future__ import annotations

import hashlib
import json
import os
import sys

from . import layout, netlist

sys.path.insert(0, os.path.join(layout.REPO_ROOT, "tooling",
                                "PCBA_AutoDesignAndTest"))

from pcbqa import extract, geom, headless  # noqa: E402
from pcbqa.fabricators.store import CatalogStore  # noqa: E402

REPO_ROOT = layout.REPO_ROOT
SIM_DIR = os.path.join(REPO_ROOT, "sim")
REQUIREMENTS_PATH = os.path.join(REPO_ROOT, "fab", "requirements.json")
CATALOG_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest",
                            "profiles", "jlcpcb")
PARAMETERS_PATH = os.path.join(REPO_ROOT, "components", "parameters.json")

CHORD_ERROR_MM = 0.001

EXTRACTED_PATHS = (("LED_DATA", "U1.20", "R4.1"),)

SUPPLY_PATH_BUDGET_OHM = 0.1
LED_INPUT_CAPACITANCE_F = 10e-12
MCU_INPUT_CAPACITANCE_F = 5e-12
WS2812B_SHORTEST_HIGH_S = 400e-9


def _parameters():
    with open(PARAMETERS_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _sum_capacitance(net):
    total = 0.0
    for pin_ref in netlist.NETS[net]:
        reference = pin_ref.split(".", 1)[0]
        part = netlist.PARTS.get(reference)
        if part is None or not reference.startswith("C"):
            continue
        value = part["value"]
        if value.endswith("uF"):
            total += float(value[:-2]) * 1e-6
        elif value.endswith("nF"):
            total += float(value[:-2]) * 1e-9
        else:
            raise ValueError("capacitor {} carries the unparsable value "
                             "{!r}".format(reference, value))
    return total


def _resistor_ohms(reference):
    value = netlist.PARTS[reference]["value"]
    if value.endswith("k"):
        return float(value[:-1]) * 1e3
    if value.endswith("R"):
        return float(value[:-1])
    raise ValueError("resistor {} carries the unparsable value {!r}".format(
        reference, value))


def _board_digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def extracted_models():
    """Simulation models measured from the routed copper, not declared."""
    import pcbnew

    headless.suppress_blocking_ui()
    geom.configure(CHORD_ERROR_MM)
    with open(REQUIREMENTS_PATH, "rb") as handle:
        raw = handle.read()
    requirements = json.loads(raw)
    requirements.setdefault("inner_copper_oz", None)
    requirements_digest = hashlib.sha256(raw).hexdigest()

    board = pcbnew.LoadBoard(layout.BOARD_PATH)
    board_sha256 = _board_digest(layout.BOARD_PATH)
    stack = [board.GetLayerName(layer)
             for layer in board.GetEnabledLayers().CuStack()]
    copper = extract.approved_finished_copper(
        CatalogStore(CATALOG_ROOT).approved(),
        extract.copper_assignments_from_requirements(requirements, stack))
    physical = {
        "copper_thickness_mm": copper,
        "board_thickness_mm": extract.requirements_board_thickness(
            requirements, requirements_digest),
    }
    models = []
    for net, from_pad, to_pad in EXTRACTED_PATHS:
        record = extract.path_resistance(board, net, from_pad, to_pad, copper)
        models.append(extract.interconnect_model_from_path(
            record, board_sha256, physical))
    return models


def _ideal(records):
    return {name: {"stands_in_for": detail,
                   "accepted_for_design_decision": True}
            for name, detail in records.items()}


def _measurement(name, kind, node, op, value):
    return {"name": name, "kind": kind, "node": node,
            "assertion": {"op": op, "value": value}}


def rail_droop_scenario(parameters):
    led = parameters["parts"]["WS2812B-B/T"]
    source_v = parameters["usb"]["vsafe5v_min_v"]
    step_a = (netlist.LED_COUNT * led["supply_current_max_a"]["value"]
              * netlist.FIRMWARE_GLOBAL_BRIGHTNESS_LIMIT)
    return {
        "name": "rail_droop_on_led_turn_on",
        "elements": [
            {"kind": "vsource_dc", "name": "SRC", "nodes": ["src", "0"],
             "value": source_v},
            {"kind": "resistor", "name": "RPATH", "nodes": ["src", "rail"],
             "value": SUPPLY_PATH_BUDGET_OHM},
            {"kind": "capacitor", "name": "CBULK", "nodes": ["rail", "0"],
             "value": _sum_capacitance("+5V")},
            {"kind": "resistor", "name": "RLED", "nodes": ["rail", "sink"],
             "value": source_v / step_a},
            {"kind": "vsource_pulse", "name": "SWITCH",
             "nodes": ["sink", "0"],
             "pulse": {"v1": source_v, "v2": 0.0, "delay_s": 1e-4,
                       "rise_s": 1e-9, "fall_s": 1e-9, "width_s": 1e-3,
                       "period_s": 2e-3}},
        ],
        "analyses": [{"kind": "tran", "step_s": 1e-7, "stop_s": 1.1e-3}],
        "measurements": [
            _measurement("rail_excursion_min", "tran_min_voltage", "rail",
                         ">=", led["supply"]["characterised_min_v"]["value"]),
            _measurement("rail_excursion_max", "tran_max_voltage", "rail",
                         "<=", led["supply"]["abs_max_v"]["value"]),
        ],
        "assumptions": _ideal({
            "SRC": "the USB-C source as an ideal voltage source held at "
                   "vSafe5V minimum, with no output impedance of its own",
            "RPATH": "the series resistance of the cable, the receptacle "
                     "contacts and the board copper between the receptacle "
                     "and the LED ring, as a design budget",
            "CBULK": "every bulk and decoupling capacitance on the rail as "
                     "one ideal capacitor, with no ESR, no ESL and no DC "
                     "bias derating",
            "RLED": "the LED array's aggregate draw as a fixed resistance "
                    "at its worst-case current; a constant-current load "
                    "droops no further than this",
            "SWITCH": "the instant at which firmware turns the whole ring "
                      "on, as an ideal switch with no on-resistance",
        }),
    }


def button_release_scenario(parameters):
    mcu = parameters["parts"]["PY32F003F18P6TU"]
    rail_v = netlist.RAILS["+5V"]["max_v"]
    vih = mcu["digital_inputs"]["19"]["vih_min"]["factor_of_supply"] * rail_v
    return {
        "name": "button_release_detection",
        "elements": [
            {"kind": "vsource_pulse", "name": "RAIL", "nodes": ["rail", "0"],
             "pulse": {"v1": 0.0, "v2": rail_v, "delay_s": 0.0,
                       "rise_s": 1e-9, "fall_s": 1e-9,
                       "width_s": netlist.BUTTON_RELEASE_DETECT_S,
                       "period_s": 2 * netlist.BUTTON_RELEASE_DETECT_S}},
            {"kind": "resistor", "name": "RPULLUP", "nodes": ["rail", "btn"],
             "value": _resistor_ohms("R6")},
            {"kind": "capacitor", "name": "CFILTER", "nodes": ["btn", "0"],
             "value": _sum_capacitance("BTN_SW")},
            {"kind": "resistor", "name": "RSERIES", "nodes": ["btn", "mcu"],
             "value": _resistor_ohms("R5")},
            {"kind": "capacitor", "name": "CPIN", "nodes": ["mcu", "0"],
             "value": MCU_INPUT_CAPACITANCE_F},
        ],
        "analyses": [{"kind": "tran", "step_s": 1e-6,
                      "stop_s": netlist.BUTTON_RELEASE_DETECT_S}],
        "measurements": [
            _measurement("mcu_input_at_deadline", "tran_final_voltage", "mcu",
                         ">=", vih),
            _measurement("mcu_input_peak", "tran_max_voltage", "mcu",
                         "<=", mcu["supply"]["characterised_max_v"]["value"]),
        ],
        "assumptions": _ideal({
            "RAIL": "the switch contact held closed long enough for the "
                    "filter capacitor to reach the reference node, then "
                    "opening at t=0; stepping the pull-up's source is the "
                    "same waveform as releasing the contact",
            "RPULLUP": "the pull-up resistor at its nominal value, with no "
                       "tolerance and no temperature coefficient",
            "CFILTER": "the debounce capacitance as an ideal capacitor, "
                       "with no ESR and no DC bias derating",
            "RSERIES": "the series protection resistor at its nominal "
                       "value",
            "CPIN": "the MCU input pin's capacitance and the ESD clamp's "
                    "off-state loading",
        }),
    }


def led_data_edge_scenario(parameters, model_identity=None):
    """The shortest protocol high time, driven through the series resistor.

    Two forms of the same question. Without an extracted model the
    interconnect is an ideal wire and every series value is a nominal
    component value, so the node voltage is exact and the receiver
    threshold is decidable. With the extracted model the copper carries a
    LOWER-bound resistance - the extraction omits via barrel resistance -
    and a larger series resistance can only lower the node voltage, so the
    simulated value bounds the true one from ABOVE. An upper bound settles
    "never exceeds the absolute maximum" and cannot settle "reaches the
    input threshold", so each form asserts only what its evidence carries.
    """
    mcu = parameters["parts"]["PY32F003F18P6TU"]
    led = parameters["parts"]["WS2812B-B/T"]
    rail_v = netlist.RAILS["+5V"]["max_v"]
    voh = rail_v + mcu["digital_outputs"]["20"]["voh_min"][
        "offset_from_supply"]
    vih = led["digital_inputs"]["4"]["vih_min"]["factor_of_supply"] * rail_v
    extracted = model_identity is not None
    driver_node = "rin" if not extracted else "drv"
    elements = [
        {"kind": "vsource_pulse", "name": "DRIVER",
         "nodes": [driver_node, "0"],
         "pulse": {"v1": 0.0, "v2": voh, "delay_s": 0.0,
                   "rise_s": 1e-9, "fall_s": 1e-9,
                   "width_s": WS2812B_SHORTEST_HIGH_S,
                   "period_s": 2 * WS2812B_SHORTEST_HIGH_S}},
    ]
    if extracted:
        elements.append({"kind": "model_instance", "name": "COPPER",
                         "nodes": ["drv", "rin"], "model": model_identity})
    elements.extend([
        {"kind": "resistor", "name": "RSERIES", "nodes": ["rin", "din"],
         "value": _resistor_ohms("R4")},
        {"kind": "capacitor", "name": "CDIN", "nodes": ["din", "0"],
         "value": LED_INPUT_CAPACITANCE_F},
    ])
    ideal = {
        "DRIVER": "the MCU output as an ideal source stepping to its "
                  "worst-case output high level, with no output impedance "
                  "and no package parasitics",
        "RSERIES": "the series termination resistor at its nominal value",
        "CDIN": "the LED data input's capacitance and the ESD clamp's "
                "off-state loading",
    }
    scenario = {
        "name": ("led_data_edge_over_extracted_copper" if extracted
                 else "led_data_edge_over_ideal_interconnect"),
        "elements": elements,
        "analyses": [{"kind": "tran", "step_s": 1e-10,
                      "stop_s": WS2812B_SHORTEST_HIGH_S}],
        "assumptions": _ideal(ideal),
    }
    if not extracted:
        scenario["measurements"] = [
            _measurement("din_at_shortest_high_end", "tran_final_voltage",
                         "din", ">=", vih),
            _measurement("din_peak", "tran_max_voltage", "din", "<=",
                         led["supply"]["abs_max_v"]["value"]),
        ]
        return scenario
    bound = {
        "kind": "upper_bound",
        "basis": {
            "kind": "assumed",
            "detail": "the extracted copper resistance is a lower bound - "
                      "via barrel resistance is omitted by the extraction - "
                      "and the node voltage falls monotonically with series "
                      "resistance, so the simulated value bounds the true "
                      "one from above",
        },
    }
    peak = _measurement("din_peak", "tran_max_voltage", "din", "<=",
                        led["supply"]["abs_max_v"]["value"])
    peak["knowledge"] = bound
    settled = {"name": "din_at_shortest_high_end",
               "kind": "tran_final_voltage", "node": "din",
               "knowledge": bound}
    scenario["measurements"] = [peak, settled]
    scenario["required_coverage"] = {
        "interconnect_dc": ["geometry-derived", "quasi-static-extracted",
                            "full-wave-extracted", "measured"]}
    return scenario


def _write(path, document):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def write():
    parameters = _parameters()
    models = extracted_models()
    written = [_write(os.path.join(SIM_DIR, "models.json"), models)]
    for name, document in (
            ("pre_layout_rail_droop.json", rail_droop_scenario(parameters)),
            ("pre_layout_button_release.json",
             button_release_scenario(parameters)),
            ("pre_layout_led_data_edge.json",
             led_data_edge_scenario(parameters)),
            ("post_layout_led_data_edge.json",
             led_data_edge_scenario(parameters, models[0]["identity"]))):
        written.append(_write(os.path.join(SIM_DIR, name), document))
    return written


if __name__ == "__main__":
    for written in write():
        sys.stdout.write(written + "\n")
