from __future__ import annotations

import math
import os
import sys

from . import ksym, netlist

_TOOLKIT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tooling", "PCBA_AutoDesignAndTest")
if _TOOLKIT not in sys.path:
    sys.path.insert(0, _TOOLKIT)

from pcbqa import headless  # noqa: E402

headless.suppress_blocking_ui()

import pcbnew  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD_PATH = os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_pcb")

FOOTPRINT_SEARCH_PATHS = (
    os.path.join(REPO_ROOT, "library"),
    "/usr/share/kicad/footprints",
)

ORIGIN_MM = (100.0, 100.0)

BOARD_RADIUS_MM = 32.5
CONNECTOR_EDGE_Y_MM = -32.0
CONNECTOR_PAD_INSET_MM = 1.64

LED_RING_RADIUS_MM = 17.0
LED_CAP_RADIUS_MM = 12.5
LED_RING_PHASE_DEG = 0.0
LED_PITCH_DEG = 360.0 / netlist.LED_COUNT
LED_ROTATION_OFFSET_DEG = 90.0

CHAIN_TESTPOINT_RADIUS_MM = 21.2
CHAIN_STUB_MM = 3.2
SERVICE_RADIUS_MM = 26.5

POWER_ZONE_INNER_MM = 11.5
POWER_ZONE_OUTER_MM = 20.0
ZONE_INSET_MM = 1.2

EDGE_WIDTH_MM = 0.1
TRACK_WIDTH_MM = 0.25
POWER_TRACK_WIDTH_MM = 1.0
STITCH_TRACK_WIDTH_MM = 0.4
CLEARANCE_MM = 0.15
EDGE_CLEARANCE_MM = 0.3
VIA_DIAMETER_MM = 0.6
VIA_DRILL_MM = 0.3
STITCH_GAP_MM = 0.35

CENTRE_PLACEMENT = {
    "SW1": (0.0, 0.0, 0.0),
    "U1": (0.0, 7.2, 0.0),
    "J2": (0.0, -7.2, 0.0),
    "C2": (-5.8, 6.0, 90.0),
    "C3": (5.8, 6.4, 90.0),
    "R4": (5.8, 4.0, 0.0),
    "R5": (-5.8, 4.0, 0.0),
    "R6": (-5.8, 2.2, 0.0),
    "C4": (2.9, -3.6, 0.0),
    "D16": (-2.9, -3.6, 0.0),
    "TP4": (8.2, 5.6, 0.0),
}

SERVICE_PLACEMENT = {
    "TP3": (230.0, 0.0),
    "R3": (219.0, 0.0),
    "C1": (208.0, 0.0),
    "TP2": (197.0, 0.0),
    "D13": (310.0, 0.0),
    "TP1": (321.0, 0.0),
}

CHAIN_ENTRY_RADIUS_MM = 13.0

CC_PLACEMENT = {
    "R1": (6.5, -24.5, 0.0),
    "D14": (9.8, -24.5, 180.0),
    "R2": (-6.5, -24.5, 180.0),
    "D15": (-9.8, -24.5, 0.0),
}

STITCH_OVERRIDE = {"J2": (1.27, -9.9)}


def to_board(x_mm, y_mm):
    return (ORIGIN_MM[0] + x_mm, ORIGIN_MM[1] - y_mm)


def _vector(x_mm, y_mm):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def _point(x_mm, y_mm):
    return _vector(*to_board(x_mm, y_mm))


def led_angle_deg(index):
    return (LED_RING_PHASE_DEG - LED_PITCH_DEG * index) % 360.0


def polar(radius_mm, angle_deg):
    radians = math.radians(angle_deg)
    return (radius_mm * math.cos(radians), radius_mm * math.sin(radians))


def connector_pad_y_mm():
    return CONNECTOR_EDGE_Y_MM + CONNECTOR_PAD_INSET_MM


def fixed_placements():
    placed = {}
    for index in range(netlist.LED_COUNT):
        angle = led_angle_deg(index)
        x, y = polar(LED_RING_RADIUS_MM, angle)
        placed["D%d" % (index + 1)] = (
            x, y, (angle + LED_ROTATION_OFFSET_DEG) % 360.0)
        cx, cy = polar(LED_CAP_RADIUS_MM, angle)
        placed["C%d" % (index + 5)] = (
            cx, cy, (angle + LED_ROTATION_OFFSET_DEG) % 360.0)
    placed.update(CENTRE_PLACEMENT)
    placed.update(CC_PLACEMENT)
    for reference, (angle, rotation) in SERVICE_PLACEMENT.items():
        x, y = polar(SERVICE_RADIUS_MM, angle)
        placed[reference] = (x, y, rotation)
    placed["J1"] = (0.0, connector_pad_y_mm(), 180.0)
    return placed


def _footprint_dir(footprint):
    library, _, name = footprint.partition(":")
    for base in FOOTPRINT_SEARCH_PATHS:
        candidate = os.path.join(base, library + ".pretty")
        if os.path.isfile(os.path.join(candidate, name + ".kicad_mod")):
            return candidate, name
    raise FileNotFoundError(footprint)


def _load(board, reference, part, x, y, rotation, pin_net, nets):
    library_dir, name = _footprint_dir(part["footprint"])
    footprint = pcbnew.FootprintLoad(library_dir, name)
    if footprint is None:
        raise RuntimeError("could not load " + part["footprint"])
    library = part["footprint"].partition(":")[0]
    footprint.SetFPID(pcbnew.LIB_ID(library, name))
    footprint.SetPosition(_point(x, y))
    footprint.SetOrientationDegrees(rotation)
    footprint.SetReference(reference)
    footprint.SetValue(part["value"])
    footprint.Reference().SetLayer(pcbnew.F_Fab)
    footprint.Value().SetLayer(pcbnew.F_Fab)
    for key, value in (("MPN", part["mpn"]), ("LCSC", part["lcsc"]),
                       ("Manufacturer", part["manufacturer"])):
        if not value:
            continue
        footprint.SetField(key, value)
        for field in footprint.GetFields():
            if field.GetName() == key:
                field.SetLayer(pcbnew.F_Fab)
                field.SetVisible(False)
    if not part["in_bom"]:
        footprint.SetExcludedFromBOM(True)
    for pad in footprint.Pads():
        number = pad.GetNumber()
        if not number:
            continue
        net_name = pin_net.get("%s.%s" % (reference, number))
        if net_name:
            pad.SetNet(nets[net_name])
        else:
            pad.SetNet(_floating_net(board, reference, pad, number))
    board.Add(footprint)
    return footprint


_RETAINED = []


_PIN_NAMES = {}


def _pin_name(lib_id, number):
    if lib_id not in _PIN_NAMES:
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        _PIN_NAMES[lib_id] = {
            key: pins[0].name for key, pins in library.pins(lib_id).items()}
    return _PIN_NAMES[lib_id].get(number, "")


def _floating_net(board, reference, pad, number):
    lib_id = netlist.PARTS[reference]["lib_id"]
    name = "unconnected-(%s-%s-Pad%s)" % (
        reference, _pin_name(lib_id, number).replace("/", "{slash}"), number)
    existing = board.GetNetInfo().GetNetItem(name)
    if existing is not None and existing.GetNetCode() != 0:
        return existing
    net = pcbnew.NETINFO_ITEM(board, name)
    board.Add(net)
    return net


def _nets(board):
    created = {}
    for name in sorted(netlist.NETS):
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        created[name] = net
    return created


def _design_settings(board):
    board.SetCopperLayerCount(2)
    settings = board.GetDesignSettings()
    settings.m_TrackMinWidth = pcbnew.FromMM(0.15)
    settings.m_ViasMinSize = pcbnew.FromMM(0.45)
    settings.m_MinThroughDrill = pcbnew.FromMM(0.25)
    settings.m_CopperEdgeClearance = pcbnew.FromMM(EDGE_CLEARANCE_MM)
    settings.m_HoleClearance = pcbnew.FromMM(0.25)
    settings.m_HoleToHoleMin = pcbnew.FromMM(0.25)
    settings.m_ViasMinAnnularWidth = pcbnew.FromMM(0.1)
    settings.m_MinClearance = pcbnew.FromMM(CLEARANCE_MM)
    default_class = settings.m_NetSettings.GetDefaultNetclass()
    default_class.SetClearance(pcbnew.FromMM(CLEARANCE_MM))
    default_class.SetTrackWidth(pcbnew.FromMM(TRACK_WIDTH_MM))
    default_class.SetViaDiameter(pcbnew.FromMM(VIA_DIAMETER_MM))
    default_class.SetViaDrill(pcbnew.FromMM(VIA_DRILL_MM))


def _outline_points(radius_mm, flat_y_mm, step_deg=1.0):
    half_width = math.sqrt(max(radius_mm ** 2 - flat_y_mm ** 2, 0.0))
    start = math.degrees(math.atan2(flat_y_mm, half_width)) % 360.0
    end = math.degrees(math.atan2(flat_y_mm, -half_width)) % 360.0
    points = []
    angle = start
    limit = end + 360.0 if end < start else end
    while angle < limit:
        points.append(polar(radius_mm, angle))
        angle += step_deg
    points.append(polar(radius_mm, end))
    return points


def _add_outline(board):
    points = _outline_points(BOARD_RADIUS_MM, CONNECTOR_EDGE_Y_MM)
    closed = points + [points[0]]
    for start, end in zip(closed, closed[1:]):
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
        shape.SetStart(_point(*start))
        shape.SetEnd(_point(*end))
        shape.SetLayer(pcbnew.Edge_Cuts)
        shape.SetWidth(pcbnew.FromMM(EDGE_WIDTH_MM))
        board.Add(shape)


def _add_board_zone(board, net, layer, priority):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(net)
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in _outline_points(BOARD_RADIUS_MM - ZONE_INSET_MM,
                                CONNECTOR_EDGE_Y_MM + ZONE_INSET_MM,
                                step_deg=2.0):
        bx, by = to_board(x, y)
        outline.Append(pcbnew.FromMM(bx), pcbnew.FromMM(by))
    _zone_style(zone, priority)
    board.Add(zone)
    return zone


def _add_ring_zone(board, net, layer, priority):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(net)
    outline = zone.Outline()
    outline.NewOutline()
    steps = 180
    for step in range(steps):
        x, y = polar(POWER_ZONE_OUTER_MM, 360.0 * step / steps)
        bx, by = to_board(x, y)
        outline.Append(pcbnew.FromMM(bx), pcbnew.FromMM(by))
    hole = []
    for step in range(steps):
        x, y = polar(POWER_ZONE_INNER_MM, -360.0 * step / steps)
        hole.append(to_board(x, y))
    outline.NewHole(0)
    for bx, by in hole:
        outline.Append(pcbnew.FromMM(bx), pcbnew.FromMM(by), 0, 0)
    _zone_style(zone, priority)
    board.Add(zone)
    return zone


def _zone_style(zone, priority):
    zone.SetAssignedPriority(priority)
    zone.SetLocalClearance(pcbnew.FromMM(CLEARANCE_MM))
    zone.SetMinThickness(pcbnew.FromMM(0.2))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    zone.SetThermalReliefGap(pcbnew.FromMM(0.3))
    zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.4))


def _add_track(board, start, end, layer, net, width_mm=TRACK_WIDTH_MM):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetLayer(layer)
    track.SetNet(net)
    track.SetWidth(pcbnew.FromMM(width_mm))
    board.Add(track)
    return track


def _add_via(board, position, net):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(position)
    via.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(VIA_DIAMETER_MM))
    via.SetDrill(pcbnew.FromMM(VIA_DRILL_MM))
    via.SetNet(net)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(via)
    return via


def pad_of(footprint, number):
    for pad in footprint.Pads():
        if pad.GetNumber() == number:
            return pad
    raise KeyError("%s has no pad %s" % (footprint.GetReference(), number))


def pad_xy(footprint, number):
    position = pad_of(footprint, number).GetPosition()
    return (pcbnew.ToMM(position.x) - ORIGIN_MM[0],
            ORIGIN_MM[1] - pcbnew.ToMM(position.y))


def local_xy(footprint, lx, ly):
    angle = math.radians(footprint.GetOrientationDegrees())
    rx = lx * math.cos(angle) - ly * math.sin(angle)
    ry = lx * math.sin(angle) + ly * math.cos(angle)
    centre = footprint.GetPosition()
    return (pcbnew.ToMM(centre.x) - ORIGIN_MM[0] + rx,
            ORIGIN_MM[1] - pcbnew.ToMM(centre.y) + ry)


def _route(board, net, points, width_mm=TRACK_WIDTH_MM, layer=None):
    layer = pcbnew.F_Cu if layer is None else layer
    for start, end in zip(points, points[1:]):
        if start == end:
            continue
        _add_track(board, _point(*start), _point(*end), layer, net, width_mm)


def _stitch_radial(board, pad, gnd_net, reach_mm):
    position = pad.GetPosition()
    origin = _point(0.0, 0.0)
    dx = position.x - origin.x
    dy = position.y - origin.y
    length = math.hypot(dx, dy) or 1.0
    via_position = pcbnew.VECTOR2I(
        int(position.x + dx / length * pcbnew.FromMM(reach_mm)),
        int(position.y + dy / length * pcbnew.FromMM(reach_mm)))
    _add_via(board, via_position, gnd_net)
    _add_track(board, position, via_position, pcbnew.F_Cu, gnd_net,
               STITCH_TRACK_WIDTH_MM)


def _stitch(board, footprint, pad, gnd_net):
    position = pad.GetPosition()
    size = pad.GetSize()
    angle = math.radians(footprint.GetOrientationDegrees())
    long_axis_x = size.x >= size.y
    reach = (pcbnew.ToMM(size.x if long_axis_x else size.y) / 2.0
             + VIA_DIAMETER_MM / 2.0 + STITCH_GAP_MM)
    centre = footprint.GetPosition()
    delta_x = position.x - centre.x
    delta_y = position.y - centre.y
    if long_axis_x:
        axis = (math.cos(angle), math.sin(angle))
    else:
        axis = (-math.sin(angle), math.cos(angle))
    projection = axis[0] * delta_x + axis[1] * delta_y
    if abs(projection) < pcbnew.FromMM(0.05):
        others = [other.GetPosition() for other in footprint.Pads()
                  if other.GetNumber() != pad.GetNumber()]
        if others:
            nearest = min(others, key=lambda point: (
                (point.x - position.x) ** 2 + (point.y - position.y) ** 2))
            away_x = position.x - nearest.x
            away_y = position.y - nearest.y
        else:
            origin = _point(0.0, 0.0)
            away_x = position.x - origin.x
            away_y = position.y - origin.y
        length = math.hypot(away_x, away_y) or 1.0
        axis = (away_x / length, away_y / length)
    elif projection < 0:
        axis = (-axis[0], -axis[1])
    via_position = pcbnew.VECTOR2I(
        int(position.x + axis[0] * pcbnew.FromMM(reach)),
        int(position.y + axis[1] * pcbnew.FromMM(reach)))
    _add_via(board, via_position, gnd_net)
    _add_track(board, position, via_position, pcbnew.F_Cu, gnd_net,
               STITCH_TRACK_WIDTH_MM)


def build():
    board = pcbnew.CreateEmptyBoard()
    _design_settings(board)
    nets = _nets(board)
    pin_net = netlist.pin_to_net()
    placed = fixed_placements()

    footprints = {}
    for reference, (x, y, rotation) in sorted(placed.items()):
        part = netlist.PARTS[reference]
        footprints[reference] = _load(
            board, reference, part, x, y, rotation, pin_net, nets)

    chain = _chain_testpoints(footprints)
    for reference, (x, y) in sorted(chain.items()):
        footprints[reference] = _load(
            board, reference, netlist.PARTS[reference], x, y, 0.0,
            pin_net, nets)

    _add_outline(board)
    _add_board_zone(board, nets["GND"], pcbnew.B_Cu, 0)
    _add_board_zone(board, nets["+5V"], pcbnew.F_Cu, 0)

    _route_led_chain(board, footprints, nets)
    _route_cc(board, footprints, nets)

    _bond_connector_ground(board, footprints["J1"], nets["GND"])
    for reference, footprint in sorted(footprints.items()):
        if reference == "J1":
            continue
        led = (reference.startswith("D")
               and reference not in ("D13", "D14", "D15", "D16"))
        for pad in footprint.Pads():
            if pad.GetNetname() != "GND":
                continue
            if pad.GetAttribute() not in (pcbnew.PAD_ATTRIB_SMD,
                                          pcbnew.PAD_ATTRIB_CONN):
                continue
            if reference in STITCH_OVERRIDE:
                target = _point(*STITCH_OVERRIDE[reference])
                _add_via(board, target, nets["GND"])
                _add_track(board, pad.GetPosition(), target, pcbnew.F_Cu,
                           nets["GND"], STITCH_TRACK_WIDTH_MM)
            elif led:
                _stitch_radial(board, pad, nets["GND"], 1.25)
            else:
                _stitch(board, footprint, pad, nets["GND"])
    return board, footprints


def _bond_connector_ground(board, connector, gnd_net):
    posts = [pad for pad in connector.Pads()
             if pad.GetNumber() == "SH"]
    bonded = set()
    for pad in connector.Pads():
        if pad.GetNumber() == "SH":
            continue
        if pad.GetNetname() != "GND":
            continue
        position = pad.GetPosition()
        nearest = min(posts, key=lambda post: (
            (post.GetPosition().x - position.x) ** 2
            + (post.GetPosition().y - position.y) ** 2))
        key = (position.x, position.y, nearest.GetPosition().x,
               nearest.GetPosition().y)
        if key in bonded:
            continue
        bonded.add(key)
        _add_track(board, position, nearest.GetPosition(), pcbnew.F_Cu,
                   gnd_net, STITCH_TRACK_WIDTH_MM)


def _chain_testpoints(footprints):
    positions = {}
    hop_points = []
    for index in range(1, netlist.LED_COUNT):
        source = pad_xy(footprints["D%d" % index], "2")
        target = pad_xy(footprints["D%d" % (index + 1)], "4")
        hop_points.append(((source[0] + target[0]) / 2.0,
                           (source[1] + target[1]) / 2.0))
    entry = polar(CHAIN_ENTRY_RADIUS_MM,
                  led_angle_deg(0) + LED_PITCH_DEG / 2.0)
    exit_point = _pad_approach(
        footprints["D%d" % netlist.LED_COUNT], "2", CHAIN_STUB_MM)
    for index, (x, y) in enumerate(hop_points):
        angle = math.degrees(math.atan2(y, x))
        positions["TP%d" % (index + 6)] = polar(
            CHAIN_TESTPOINT_RADIUS_MM, angle)
    positions["TP5"] = entry
    positions["TP%d" % (netlist.LED_COUNT + 5)] = exit_point
    return positions


def _pad_approach(footprint, number, distance_mm):
    pad = pad_xy(footprint, number)
    centre = footprint.GetPosition()
    cx = pcbnew.ToMM(centre.x) - ORIGIN_MM[0]
    cy = ORIGIN_MM[1] - pcbnew.ToMM(centre.y)
    dx, dy = pad[0] - cx, pad[1] - cy
    length = math.hypot(dx, dy) or 1.0
    return (pad[0] + dx / length * distance_mm,
            pad[1] + dy / length * distance_mm)


def _route_cc(board, footprints, nets):
    j1 = footprints["J1"]
    for pad_number, net_name, resistor, protector in (
            ("A5", "CC1", "R1", "D14"), ("B5", "CC2", "R2", "D15")):
        start = pad_xy(j1, pad_number)
        sign = 1.0 if start[0] >= 0 else -1.0
        corridor = (sign * 1.35, CONNECTOR_EDGE_Y_MM + 9.5)
        _route(board, nets[net_name], [start, corridor])
        _route(board, nets[net_name],
               [corridor, pad_xy(footprints[resistor], "1")])
        protector_pad = pad_xy(footprints[protector], "2")
        _route(board, nets[net_name],
               [corridor, (protector_pad[0], corridor[1]), protector_pad])


def _route_led_chain(board, footprints, nets):
    for index in range(1, netlist.LED_COUNT):
        net = nets["LED_CH%d" % index]
        source = pad_xy(footprints["D%d" % index], "2")
        target = pad_xy(footprints["D%d" % (index + 1)], "4")
        testpoint = pad_xy(footprints["TP%d" % (index + 5)], "1")
        _route(board, net, [source, testpoint, target])
    entry = pad_xy(footprints["D1"], "4")
    _route(board, nets["LED_CH0"],
           [pad_xy(footprints["R4"], "2"),
            pad_xy(footprints["TP5"], "1"), entry])
    exit_pad = pad_xy(footprints["D%d" % netlist.LED_COUNT], "2")
    _route(board, nets["LED_CH%d" % netlist.LED_COUNT],
           [exit_pad, pad_xy(footprints["TP17"], "1")])


def _route_centre(board, footprints, nets):
    u1 = footprints["U1"]
    _route(board, nets["LED_DATA"],
           [pad_xy(u1, "20"), pad_xy(footprints["TP4"], "1"),
            pad_xy(footprints["R4"], "1")])
    entry_angle = math.degrees(math.atan2(*reversed(
        pad_xy(footprints["D1"], "4"))))
    _route(board, nets["LED_CH0"],
           [pad_xy(footprints["R4"], "2"),
            polar(LED_CAP_RADIUS_MM + 2.0, entry_angle + 6.0),
            pad_xy(footprints["TP5"], "1")])
    _route(board, nets["NRST"],
           [pad_xy(u1, "18"), pad_xy(footprints["C3"], "1")])
    _route(board, nets["NRST"],
           [pad_xy(footprints["C3"], "1"), (-4.4, -1.2),
            pad_xy(footprints["J2"], "3")])
    _route(board, nets["SWDIO"],
           [pad_xy(u1, "10"), (-3.2, 1.6), (-3.2, -5.2),
            pad_xy(footprints["J2"], "2")])
    _route(board, nets["SWCLK"],
           [pad_xy(u1, "11"), (3.2, 1.6), (3.2, -5.2),
            pad_xy(footprints["J2"], "4")])
    _route(board, nets["BTN_SW"],
           [pad_xy(footprints["SW1"], "1"), pad_xy(footprints["C4"], "1")])
    _route(board, nets["BTN_SW"],
           [pad_xy(footprints["SW1"], "1"), (-4.6, -1.85),
            pad_xy(footprints["R6"], "2")])
    _route(board, nets["BTN_SW"],
           [pad_xy(footprints["R6"], "2"), pad_xy(footprints["R5"], "1")])
    _route(board, nets["BTN_SW"],
           [pad_xy(footprints["SW1"], "1"), (-4.6, -1.85),
            pad_xy(footprints["D16"], "2")])
    _route(board, nets["BTN_MCU"],
           [pad_xy(footprints["R5"], "2"), (-2.0, 4.0),
            pad_xy(u1, "19")])


def _route_connector(board, footprints, nets):
    j1 = footprints["J1"]
    escape = 6.6
    for pad_number, target_ref, target_pad, net_name in (
            ("A5", "R1", "1", "CC1"),
            ("B5", "R2", "1", "CC2")):
        start = pad_xy(j1, pad_number)
        lx = -1.9 if net_name == "CC1" else 1.9
        waypoint = local_xy(j1, lx, escape)
        _route(board, nets[net_name], [start, waypoint])
        _route(board, nets[net_name],
               [waypoint, pad_xy(footprints[target_ref], target_pad)])
    for pad_number, sign in (("A4", -1.0), ("B4", 1.0)):
        start = pad_xy(j1, pad_number)
        waypoint = local_xy(j1, sign * 0.8, escape)
        _route(board, nets["VBUS"], [start, waypoint],
               POWER_TRACK_WIDTH_MM)
    left = local_xy(j1, -0.8, escape)
    right = local_xy(j1, 0.8, escape)
    _route(board, nets["VBUS"], [left, right], POWER_TRACK_WIDTH_MM)
    _route(board, nets["VBUS"],
           [left, pad_xy(footprints["D13"], "2")], POWER_TRACK_WIDTH_MM)
    _route(board, nets["VBUS"],
           [pad_xy(footprints["D13"], "2"),
            pad_xy(footprints["TP1"], "1")], POWER_TRACK_WIDTH_MM)
    _route(board, nets["VBUS"],
           [right, pad_xy(footprints["R3"], "1")], POWER_TRACK_WIDTH_MM)
    _route(board, nets["+5V"],
           [pad_xy(footprints["R3"], "2"),
            pad_xy(footprints["C1"], "1")], POWER_TRACK_WIDTH_MM)
    _route(board, nets["+5V"],
           [pad_xy(footprints["C1"], "1"),
            pad_xy(footprints["TP2"], "1")], POWER_TRACK_WIDTH_MM)
    inner = polar(POWER_ZONE_OUTER_MM - 0.6, 215.0)
    _route(board, nets["+5V"],
           [pad_xy(footprints["TP2"], "1"), inner], POWER_TRACK_WIDTH_MM)
    _route(board, nets["CC1"],
           [pad_xy(footprints["R1"], "1"),
            pad_xy(footprints["D14"], "2")])
    _route(board, nets["CC2"],
           [pad_xy(footprints["R2"], "1"),
            pad_xy(footprints["D15"], "2")])


def write():
    board, _ = build()
    pcbnew.SaveBoard(BOARD_PATH, board)
    return BOARD_PATH


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
