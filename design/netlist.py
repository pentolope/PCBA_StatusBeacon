from __future__ import annotations

import os

LED_COUNT = 12

PROJECT_NAME = "status_beacon"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SYMBOL_LIBRARY_PATHS = (
    os.path.join(_REPO_ROOT, "library"),
    "/usr/share/kicad/symbols",
)


def _part(lib_id, footprint, value, mpn=None, manufacturer=None, lcsc=None,
          datasheet="", in_bom=True, on_board=True):
    return {
        "lib_id": lib_id,
        "footprint": footprint,
        "value": value,
        "mpn": mpn,
        "manufacturer": manufacturer,
        "lcsc": lcsc,
        "datasheet": datasheet,
        "in_bom": in_bom,
        "on_board": on_board,
    }


def _parts():
    parts = {
        "J1": _part(
            "Connector:USB_C_Receptacle_USB2.0_16P",
            "StatusBeacon:USB_C_Receptacle_HRO_TYPE-C-31-M-12_LCSC",
            "USB_C_16P", "TYPE-C-31-M-12", "Korean Hroparts Elec",
            "C165948"),
        "J2": _part(
            "Connector_Generic:Conn_02x03_Odd_Even",
            "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical",
            "SWD_TC2030", None, None, None, in_bom=False),
        "U1": _part(
            "StatusBeacon:PY32F003F1xPx",
            "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm",
            "PY32F003F18P6TU", "PY32F003F18P6TU", "Puya", "C5379864"),
        "SW1": _part(
            "Switch:SW_Push",
            "Button_Switch_SMD:SW_SPST_SKQG_WithoutStem",
            "K2-1187SQ-A4SW-06", "K2-1187SQ-A4SW-06",
            "Korean Hroparts Elec", "C92584"),
        "R1": _part("Device:R", "Resistor_SMD:R_0402_1005Metric", "5.1k",
                    lcsc="C25905"),
        "R2": _part("Device:R", "Resistor_SMD:R_0402_1005Metric", "5.1k",
                    lcsc="C25905"),
        "R4": _part("Device:R", "Resistor_SMD:R_0402_1005Metric", "33R",
                    lcsc="C25105"),
        "R5": _part("Device:R", "Resistor_SMD:R_0402_1005Metric", "1k",
                    lcsc="C11702"),
        "R6": _part("Device:R", "Resistor_SMD:R_0402_1005Metric", "10k",
                    lcsc="C25744"),
        "C1": _part("Device:C", "Capacitor_SMD:C_0805_2012Metric", "4.7uF",
                    lcsc="C1779"),
    }
    for index in (2, 3, 4):
        parts["C%d" % index] = _part(
            "Device:C", "Capacitor_SMD:C_0402_1005Metric", "100nF",
            lcsc="C1525")
    for index in range(LED_COUNT):
        parts["D%d" % (index + 1)] = _part(
            "LED:WS2812B",
            "LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm",
            "WS2812B-V5/W", "WS2812B-V5/W", "Worldsemi", "C2874885")
        parts["C%d" % (index + 5)] = _part(
            "Device:C", "Capacitor_SMD:C_0402_1005Metric", "100nF",
            lcsc="C1525")
    parts["U2"] = _part(
        "StatusBeacon:ME6211C50", "Package_TO_SOT_SMD:SOT-23-5",
        "ME6211C50M5G-N", "ME6211C50M5G-N", "MICRONE", "C236670")
    parts["C17"] = _part(
        "Device:C", "Capacitor_SMD:C_0805_2012Metric", "4.7uF",
        lcsc="C1779")
    for ref in ("D13", "D14", "D15", "D16"):
        parts[ref] = _part(
            "StatusBeacon:TPD1E10B06", "StatusBeacon:TI_X1SON-2_1.0x0.6mm_P0.65mm",
            "TPD1E10B06DPYR", "TPD1E10B06DPYR", "Texas Instruments", "C48260")
    for index in range(1, 18):
        parts["TP%d" % index] = _part(
            "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.0mm",
            "TestPoint", in_bom=False)
    for index in (1, 3):
        parts["#FLG%d" % index] = _part(
            "power:PWR_FLAG", "", "PWR_FLAG", in_bom=False, on_board=False)
    return parts


PARTS = _parts()


def _nets():
    ground = [
        "J1.A1", "J1.A12", "J1.B1", "J1.B12", "J1.SH", "R1.2", "R2.2",
        "U1.7", "SW1.2", "J2.5",
        "C1.2", "C2.2", "C3.2", "C4.2", "C17.2", "U2.2",
        "D13.1", "D14.1", "D15.1", "D16.1", "TP3.1", "#FLG3.1",
    ]
    five_volt = [
        "U2.5", "C1.1", "C2.1", "U1.9", "J2.1", "R6.1",
        "TP2.1",
    ]
    for index in range(LED_COUNT):
        ground.append("D%d.3" % (index + 1))
        ground.append("C%d.2" % (index + 5))
        five_volt.append("D%d.1" % (index + 1))
        five_volt.append("C%d.1" % (index + 5))

    nets = {
        "GND": ground,
        "VBUS": ["J1.A4", "J1.A9", "J1.B4", "J1.B9", "D13.2",
                 "U2.1", "U2.3", "C17.1", "TP1.1", "#FLG1.1"],
        "+5V": five_volt,
        "CC1": ["J1.A5", "R1.1", "D14.2"],
        "CC2": ["J1.B5", "R2.1", "D15.2"],
        "NRST": ["U1.18", "C3.1", "J2.3"],
        "SWDIO": ["U1.10", "J2.2"],
        "SWCLK": ["U1.11", "J2.4"],
        "BTN_SW": ["SW1.1", "R6.2", "C4.1", "D16.2", "R5.1"],
        "BTN_MCU": ["R5.2", "U1.19"],
        "LED_DATA": ["U1.20", "R4.1", "TP4.1"],
    }
    nets["LED_CH0"] = ["R4.2", "D1.4", "TP5.1"]
    for index in range(1, LED_COUNT):
        nets["LED_CH%d" % index] = [
            "D%d.2" % index, "D%d.4" % (index + 1), "TP%d.1" % (index + 5)]
    nets["LED_CH%d" % LED_COUNT] = [
        "D%d.2" % LED_COUNT, "TP%d.1" % (LED_COUNT + 5)]
    return nets


NETS = _nets()

NO_CONNECT = tuple(
    ["U1.%d" % pin for pin in
     (1, 2, 3, 4, 5, 6, 8, 12, 13, 14, 15, 16, 17)]
    + ["J1.A6", "J1.A7", "J1.A8", "J1.B6", "J1.B7", "J1.B8", "J2.6",
       "U2.4"])


#: The regulator's specified output band, and the dropout that decides the
#: rail when the source is too low for it to regulate. The datasheet states
#: dropout as a TYPICAL at 100 mA and 200 mA only, so the figure carried here
#: extrapolates that slope to the declared port budget and adds the pass
#: device's rise with temperature.
LDO_OUTPUT_TOLERANCE = 0.01
LDO_OUTPUT_NOMINAL_V = 5.0
LDO_DROPOUT_AT_BUDGET_V = 0.70

RAILS = {
    "VBUS": {"min_v": 4.75, "max_v": 5.5},
    "+5V": {"min_v": 4.75 - LDO_DROPOUT_AT_BUDGET_V,
            "max_v": LDO_OUTPUT_NOMINAL_V * (1.0 + LDO_OUTPUT_TOLERANCE)},
    "GND": {"min_v": 0.0, "max_v": 0.0},
}

NODE_VOLTAGE_RANGES = {
    "BTN_SW": {"min_v": 0.0, "max_v": RAILS["+5V"]["max_v"]},
    "CC1": {"min_v": 0.0, "max_v": RAILS["VBUS"]["max_v"]},
    "CC2": {"min_v": 0.0, "max_v": RAILS["VBUS"]["max_v"]},
}

ASSEMBLY_POLICY = {
    "reflow_passes": 1,
    "placement_sides": 1,
    "max_through_hole_soldered_parts": 1,
}

CONNECTOR_FUNCTION_NETS = {
    "J1": {"GND": "GND", "VBUS": "VBUS", "CC1": "CC1", "CC2": "CC2",
           "SHIELD": "GND"},
}

PORT_BUDGET_A = 0.5

FIRMWARE_GLOBAL_BRIGHTNESS_LIMIT = 0.65

BUTTON_RELEASE_DETECT_S = 3e-3

VBUS_CAPACITANCE_LIMIT_F = 10.0e-6


def pin_to_net():
    mapping = {}
    for net_name, pin_refs in NETS.items():
        for pin_ref in pin_refs:
            if pin_ref in mapping:
                raise ValueError(
                    "pin %s assigned to both %s and %s"
                    % (pin_ref, mapping[pin_ref], net_name))
            mapping[pin_ref] = net_name
    for pin_ref in NO_CONNECT:
        if pin_ref in mapping:
            raise ValueError(
                "pin %s is both no-connect and on net %s"
                % (pin_ref, mapping[pin_ref]))
    return mapping
