from __future__ import annotations

import json
import os
import math
import shutil
import subprocess
import sys

import pcbnew

from . import build, layout, netlist

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tooling", "PCBA_AutoDesignAndTest"))

from pcbqa import routing_record  # noqa: E402

REPO_ROOT = layout.REPO_ROOT
CANDIDATE_ROOT = os.path.join(REPO_ROOT, "candidates")
CANDIDATE_NAME = "route-current"
PROVENANCE_PATH = os.path.join(REPO_ROOT, "generated", "routing.json")

ROUTED_NETS = ("VBUS", "+5V", "LED_DATA", "NRST", "SWDIO", "SWCLK",
               "BTN_SW", "BTN_MCU")

ROUTER_OPTIONS = (
    "--track-width", str(layout.TRACK_WIDTH_MM),
    "--clearance", str(layout.CLEARANCE_MM),
    "--via-size", str(layout.VIA_DIAMETER_MM),
    "--via-drill", str(layout.VIA_DRILL_MM),
    "--board-edge-clearance", "0.45",
    "--hole-to-hole-clearance", "0.3",
    "--same-net-pad-clearance", "0.3",
)


def _krt():
    sys.path.insert(0, os.path.join(REPO_ROOT, "tooling",
                                    "PCBA_AutoDesignAndTest"))
    from pcbqa import krt
    return krt


# The router is deterministic for a fixed input, so a bare retry explores
# nothing. Each attempt varies the net-ordering strategy instead, which is
# what actually produces a different candidate.
ATTEMPT_ORDERINGS = ("mps", "inside_out", "original")
MAX_ATTEMPTS = len(ATTEMPT_ORDERINGS)

MANIFEST = os.path.join(REPO_ROOT, "board", "manifest.json")
VALIDATOR = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest",
                         "run.py")


def _route_once(krt, resolved, candidate, attempt, placed_pcb):
    stage_dir = os.path.join(candidate, "attempt-%02d" % attempt)
    os.makedirs(stage_dir, exist_ok=True)
    source_pcb = os.path.join(stage_dir, "source.kicad_pcb")
    shutil.copy(placed_pcb, source_pcb)
    shutil.copy(os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_pro"),
                os.path.join(stage_dir, "source.kicad_pro"))
    routed_pcb = os.path.join(stage_dir, "routed.kicad_pcb")
    command = [sys.executable,
               os.path.join(resolved["path"], "py_router", "route.py"),
               source_pcb, routed_pcb, "--nets"] + list(ROUTED_NETS) \
        + list(ROUTER_OPTIONS) \
        + ["--ordering", ATTEMPT_ORDERINGS[attempt - 1]]
    completed = subprocess.run(command, capture_output=True, text=True)
    summary = _summary(completed.stdout)
    if completed.returncode != 0 or summary.get("failed"):
        raise RuntimeError("routing failed: rc=%s summary=%s"
                           % (completed.returncode, summary))
    tidied_pcb = os.path.join(stage_dir, "tidied.kicad_pcb")
    shutil.copy(routed_pcb, tidied_pcb)
    transform = tidy(tidied_pcb)
    return {
        "attempt": attempt,
        "source_sha256": krt_digest(source_pcb),
        "accepted": False,
        "stages": [
            {"stage": "routed", "produced_by": "router",
             "sha256": krt_digest(routed_pcb)},
            {"stage": "tidied", "produced_by": "transform",
             "sha256": krt_digest(tidied_pcb),
             "transform": "snap track endpoints onto same-net via centres; "
                          "prune dangling track ends, keeping any removal "
                          "only while connectivity is unchanged",
             "effects": transform,
             "parameters": {"snap_tolerance_mm": SNAP_TOLERANCE_MM,
                            "touch_tolerance_mm": TOUCH_TOLERANCE_MM}},
        ],
        "context": {"router_summary": summary,
                    "ordering": ATTEMPT_ORDERINGS[attempt - 1]},
        "board": tidied_pcb,
    }


def _gates_pass():
    completed = subprocess.run(
        [sys.executable, VALIDATOR, "validate", MANIFEST],
        capture_output=True, text=True, cwd=REPO_ROOT)
    return completed.returncode == 0


def _write_record(placed_pcb, attempts, accepted, krt, resolved):
    record = {
        "kind": routing_record.KIND,
        "source_sha256": krt_digest(placed_pcb),
        "attempts": attempts,
        "accepted_attempt": accepted["attempt"] if accepted else None,
        "adopted_sha256": (krt_digest(layout.BOARD_PATH)
                           if accepted else None),
        "context": {
            "router": krt.provenance(resolved["path"], sys.executable),
            "resolution": resolved,
            "routed_nets": list(ROUTED_NETS),
            "options": list(ROUTER_OPTIONS),
            "reproducibility": "the router is not bit-reproducible; "
                               "candidates are generated until one passes "
                               "the board gates and every attempt is "
                               "recorded here",
        },
    }
    routing_record.validate(record)
    os.makedirs(os.path.dirname(PROVENANCE_PATH), exist_ok=True)
    with open(PROVENANCE_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    return record


def run():
    krt = _krt()
    resolved = krt.resolve()
    candidate = os.path.join(CANDIDATE_ROOT, CANDIDATE_NAME)
    shutil.rmtree(candidate, ignore_errors=True)
    os.makedirs(candidate, exist_ok=True)
    layout.write()
    placed_pcb = os.path.join(candidate, "placed.kicad_pcb")
    shutil.copy(layout.BOARD_PATH, placed_pcb)

    attempts = []
    accepted = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = _route_once(krt, resolved, candidate, attempt, placed_pcb)
        entry = {key: value for key, value in result.items() if key != "board"}
        shutil.copy(result["board"], layout.BOARD_PATH)
        build.write_project()
        # The record must describe the board the gates are about to judge,
        # ROUTE.PROVENANCE included, so it is written before the judgement
        # and rewritten if the candidate is rejected.
        entry["accepted"] = True
        _write_record(placed_pcb, attempts + [entry], entry, krt, resolved)
        if _gates_pass():
            accepted = entry
            attempts.append(entry)
            break
        entry["accepted"] = False
        attempts.append(entry)

    if accepted is None:
        shutil.copy(placed_pcb, layout.BOARD_PATH)
        build.write_project()
        _write_record(placed_pcb, attempts, None, krt, resolved)
        raise RuntimeError(
            "no routing candidate passed the board gates in %d attempts; "
            "the placed, unrouted board has been restored so no failing "
            "copper stays in the tree" % MAX_ATTEMPTS)
    return layout.BOARD_PATH, PROVENANCE_PATH


SNAP_TOLERANCE_MM = 0.25
TOUCH_TOLERANCE_MM = 0.01


def _endpoints(track):
    return (track.GetStart(), track.GetEnd())


def _supported(point, track, board, vias, tracks, epsilon):
    for via in vias:
        if via.GetNetCode() != track.GetNetCode():
            continue
        centre = via.GetPosition()
        if math.hypot(point.x - centre.x, point.y - centre.y) <= epsilon:
            return True
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetCode() != track.GetNetCode():
                continue
            if pad.HitTest(point, 0):
                return True
    for other in tracks:
        if str(other.m_Uuid) == str(track.m_Uuid):
            continue
        if other.GetNetCode() != track.GetNetCode():
            continue
        if other.Type() == pcbnew.PCB_VIA_T:
            continue
        if other.GetLayer() != track.GetLayer():
            continue
        if other.HitTest(point, int(epsilon)):
            return True
    return False


def tidy(path):
    board = pcbnew.LoadBoard(path)
    epsilon = pcbnew.FromMM(TOUCH_TOLERANCE_MM)
    snapped = 0
    for _ in range(4):
        vias = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
        moved = 0
        for track in board.GetTracks():
            if track.Type() == pcbnew.PCB_VIA_T:
                continue
            for get, set_ in ((track.GetStart, track.SetStart),
                              (track.GetEnd, track.SetEnd)):
                point = get()
                for via in vias:
                    if via.GetNetCode() != track.GetNetCode():
                        continue
                    centre = via.GetPosition()
                    distance = math.hypot(point.x - centre.x,
                                          point.y - centre.y)
                    if epsilon < distance <= pcbnew.FromMM(SNAP_TOLERANCE_MM):
                        set_(centre)
                        moved += 1
                        break
        snapped += moved
        if not moved:
            break

    removed = 0
    for _ in range(8):
        board.BuildConnectivity()
        baseline = board.GetConnectivity().GetUnconnectedCount(True)
        vias = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
        tracks = [t for t in board.GetTracks()
                  if t.Type() != pcbnew.PCB_VIA_T]
        victim = None
        for track in tracks:
            if track.GetLength() == 0:
                victim = track
                break
            if all(_supported(point, track, board, vias, tracks, epsilon)
                   for point in _endpoints(track)):
                continue
            victim = track
            break
        if victim is None:
            break
        board.Remove(victim)
        board.BuildConnectivity()
        if board.GetConnectivity().GetUnconnectedCount(True) > baseline:
            board.Add(victim)
            board.BuildConnectivity()
            break
        removed += 1

    pcbnew.SaveBoard(path, board)
    return {"endpoints_snapped": snapped,
            "dangling_tracks_removed": removed}


def krt_digest(path):
    import hashlib
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _summary(text):
    for line in text.splitlines():
        if line.strip().startswith("JSON_SUMMARY_MIN:"):
            return json.loads(line.split("JSON_SUMMARY_MIN:", 1)[1])
    return {}


if __name__ == "__main__":
    for path in run():
        sys.stdout.write(path + "\n")
