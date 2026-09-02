from __future__ import annotations

import math
import os
import sys

from . import layout, netlist

REPO_ROOT = layout.REPO_ROOT

#: Still air, board mounted horizontally, no enclosure and no forced air.
#: These are the boundary conditions the estimate is valid for; §24 of the
#: agent specification requires that a simple estimate say so rather than
#: present itself as a junction temperature.
AMBIENT_DECLARED_C = 40.0
EMISSIVITY = 0.90
STEFAN_BOLTZMANN = 5.670374419e-8

#: McAdams' correlation for a heated horizontal plate facing up in still
#: air, h = 1.32 * (dT / L)^0.25, with L the characteristic length A/P.
#: Both faces of the disc radiate and convect; nothing else sinks heat.
CONVECTION_COEFFICIENT = 1.32
RADIATING_FACES = 2

#: The MCU's own draw is the one supply current the frozen parameters carry
#: on an assumed basis, so the dissipation it contributes is assumed too.
MCU_REFERENCE = "U1"
REGULATOR_REFERENCE = "U2"


def _board_area_m2():
    radius_m = layout.BOARD_RADIUS_MM / 1000.0
    return RADIATING_FACES * math.pi * radius_m ** 2


def _characteristic_length_m():
    radius_m = layout.BOARD_RADIUS_MM / 1000.0
    return (math.pi * radius_m ** 2) / (2.0 * math.pi * radius_m)


def dissipation(parameters, brightness=None):
    """Watts per reference, and the total, at a given brightness fraction.

    Everything a part draws from the rail is dissipated in its package: the
    LED dice and the constant-current sink that feeds them sit in the same
    5050 body, so the split between them does not change the heat.
    """
    if brightness is None:
        brightness = netlist.FIRMWARE_GLOBAL_BRIGHTNESS_LIMIT
    led = parameters["parts"]["WS2812B-V5/W"]
    per_led_a = led["supply_current_max_a"]["value"] * brightness
    rail_v = netlist.RAILS["+5V"]["max_v"]
    source_v = netlist.RAILS["VBUS"]["max_v"]

    mcu_a = parameters["parts"][
        netlist.PARTS[MCU_REFERENCE]["mpn"]]["supply_current_max_a"]["value"]
    load_a = netlist.LED_COUNT * per_led_a + mcu_a

    parts = {}
    for index in range(netlist.LED_COUNT):
        parts["D%d" % (index + 1)] = rail_v * per_led_a
    parts[MCU_REFERENCE] = rail_v * mcu_a
    # The regulator drops the source down to the rail at the full load
    # current, whether it is regulating or sitting in dropout.
    parts[REGULATOR_REFERENCE] = (source_v - rail_v) * load_a
    return parts, sum(parts.values()), load_a


def board_rise_k(watts, ambient_c=AMBIENT_DECLARED_C):
    """Board-average rise over ambient, convection plus radiation.

    Solved by iteration because both coefficients depend on the rise they
    are being used to find.
    """
    area = _board_area_m2()
    length = _characteristic_length_m()
    ambient_k = ambient_c + 273.15
    rise = 1.0
    for _ in range(200):
        surface_k = ambient_k + rise
        h_conv = CONVECTION_COEFFICIENT * (max(rise, 1e-6) / length) ** 0.25
        h_rad = (EMISSIVITY * STEFAN_BOLTZMANN
                 * (surface_k ** 2 + ambient_k ** 2)
                 * (surface_k + ambient_k))
        nxt = watts / ((h_conv + h_rad) * area)
        if abs(nxt - rise) < 1e-9:
            rise = nxt
            break
        rise = 0.5 * (rise + nxt)
    return rise, h_conv, h_rad


def regulator_allowable_w(parameters, ambient_c):
    """The regulator's derated dissipation limit at an ambient.

    Its datasheet states PD by package and a maximum junction temperature
    but no thermal resistance, so the resistance is the one implied by
    those two numbers. The SOT-23-5 this board fits is not among the
    packages listed; the smallest five-pin package that is, SOT-353, is
    used instead, which errs low.
    """
    spec = parameters["parts"][netlist.PARTS[REGULATOR_REFERENCE]["mpn"]]
    thermal = spec["thermal"]
    pd_w = thermal["package_power_dissipation_w"]["value"]
    tj_max = thermal["junction_max_c"]["value"]
    rated_at = thermal["package_power_rated_at_c"]["value"]
    theta = (tj_max - rated_at) / pd_w
    return max(0.0, (tj_max - ambient_c) / theta), theta


def maximum_ambient_c(parameters, brightness=None):
    """The highest ambient at which every part stays inside its rating."""
    _parts, total_w, _load = dissipation(parameters, brightness)
    led_limit = parameters["parts"]["WS2812B-V5/W"][
        "thermal"]["operating_max_c"]["value"]
    low, high = -40.0, 150.0
    for _ in range(200):
        mid = 0.5 * (low + high)
        rise, _hc, _hr = board_rise_k(total_w, mid)
        allowed, _theta = regulator_allowable_w(parameters, mid + rise)
        reg_w = _parts[REGULATOR_REFERENCE]
        if mid + rise <= led_limit and reg_w <= allowed:
            low = mid
        else:
            high = mid
    return low


def maximum_brightness(parameters, ambient_c=None):
    """The highest global brightness the declared ambient supports.

    The firmware limit has to be at or below this, otherwise the limit is
    not what keeps the regulator inside its derated dissipation.
    """
    if ambient_c is None:
        ambient_c = AMBIENT_DECLARED_C
    led_limit = parameters["parts"]["WS2812B-V5/W"][
        "thermal"]["operating_max_c"]["value"]
    low, high = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (low + high)
        parts, total_w, _load = dissipation(parameters, mid)
        rise, _hc, _hr = board_rise_k(total_w, ambient_c)
        allowed, _theta = regulator_allowable_w(parameters, ambient_c + rise)
        if (ambient_c + rise <= led_limit
                and parts[REGULATOR_REFERENCE] <= allowed):
            low = mid
        else:
            high = mid
    return low


def report(parameters, brightness=None):
    parts, total_w, load_a = dissipation(parameters, brightness)
    rise, h_conv, h_rad = board_rise_k(total_w)
    allowed, theta = regulator_allowable_w(
        parameters, AMBIENT_DECLARED_C + rise)
    led_limit = parameters["parts"]["WS2812B-V5/W"][
        "thermal"]["operating_max_c"]["value"]
    return {
        "brightness": (netlist.FIRMWARE_GLOBAL_BRIGHTNESS_LIMIT
                       if brightness is None else brightness),
        "load_a": load_a,
        "dissipation_w": parts,
        "total_w": total_w,
        "board_area_m2": _board_area_m2(),
        "h_convection": h_conv,
        "h_radiation": h_rad,
        "board_theta_c_per_w": rise / total_w if total_w else None,
        "board_rise_k": rise,
        "ambient_declared_c": AMBIENT_DECLARED_C,
        "board_temperature_c": AMBIENT_DECLARED_C + rise,
        "led_operating_max_c": led_limit,
        "regulator_w": parts[REGULATOR_REFERENCE],
        "regulator_allowable_w": allowed,
        "regulator_theta_c_per_w": theta,
        "maximum_ambient_c": maximum_ambient_c(parameters, brightness),
        "maximum_brightness": maximum_brightness(parameters),
    }


if __name__ == "__main__":
    sys.path.insert(0, REPO_ROOT)
    from design import rules

    p = rules.load_parameters()
    for label, b in (("full brightness", 1.0),
                     ("firmware limit",
                      netlist.FIRMWARE_GLOBAL_BRIGHTNESS_LIMIT)):
        r = report(p, b)
        sys.stdout.write(
            "%-16s load %.3f A  total %.2f W  theta %.1f C/W  rise %.1f K  "
            "board %.1f C  reg %.0f/%.0f mW  max ambient %.1f C\n"
            % (label, r["load_a"], r["total_w"], r["board_theta_c_per_w"],
               r["board_rise_k"], r["board_temperature_c"],
               r["regulator_w"] * 1e3, r["regulator_allowable_w"] * 1e3,
               r["maximum_ambient_c"]))
