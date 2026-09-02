from __future__ import annotations

import hashlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(REPO_ROOT, "evidence", "index.json")
DATASHEET_DIR = os.path.join(REPO_ROOT, "evidence", "datasheets")

SOURCES = {
    "ws2812b_worldsemi": {
        "file": "datasheets/ws2812b_worldsemi.pdf",
        "url": "https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf",
        "retrieved": "2026-09-01",
        "applies_to": ["WS2812B-B/T"],
    },
    "ws2812b_luxalight": {
        "file": "datasheets/ws2812b_luxalight.pdf",
        "url": "https://www.luxalight.eu/sites/default/files/downloads/"
               "2020-03/Datasheet_WS2812B.pdf",
        "retrieved": "2026-09-01",
        "applies_to": ["WS2812B-B/T"],
    },
    "py32f003_puya": {
        "file": "datasheets/py32f003_puya.pdf",
        "url": "https://download.py32.org/Datasheet/en/"
               "PY32F003_Datasheet_Rev1.7.pdf",
        "retrieved": "2026-09-01",
        "document_id": "PY32F003 Datasheet Rev1.7",
        "applies_to": ["PY32F003F18P6TU"],
    },
    "tpd1e10b06_ti": {
        "file": "datasheets/tpd1e10b06_ti.pdf",
        "url": "https://www.ti.com/lit/ds/symlink/tpd1e10b06.pdf",
        "retrieved": "2026-09-01",
        "document_id": "SLLSEB1G",
        "applies_to": ["TPD1E10B06DPYR"],
    },
    "typec31m12_hro": {
        "file": "datasheets/typec31m12_hro.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2205251630_Korean-Hroparts-Elec-TYPE-C-31-M-12_C165948.pdf",
        "retrieved": "2026-09-01",
        "applies_to": ["TYPE-C-31-M-12"],
    },
    "typec31m12_lcsc_landpattern": {
        "file": "datasheets/typec31m12_lcsc_landpattern.json",
        "url": "https://easyeda.com/api/products/C165948/svgs",
        "retrieved": "2026-09-01",
        "document_id": "LCSC C165948 footprint, docType 4",
        "applies_to": ["TYPE-C-31-M-12"],
    },
    "k2_1187sq_hro": {
        "file": "datasheets/k2_1187sq_hro.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2304140030_Korean-Hroparts-Elec-K2-1187SQ-A4SW-06_C92584.pdf",
        "retrieved": "2026-09-01",
        "applies_to": ["K2-1187SQ-A4SW-06"],
    },
}


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_index():
    entries = {}
    for name in sorted(SOURCES):
        source = SOURCES[name]
        path = os.path.join(REPO_ROOT, "evidence", source["file"])
        entry = dict(source)
        entry["sha256"] = digest(path)
        entry["bytes"] = os.path.getsize(path)
        entries[name] = entry
    return {"schema_version": 1, "documents": entries}


def load_index():
    with open(INDEX_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_index():
    with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(compute_index(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return INDEX_PATH


def verify():
    recorded = load_index()["documents"]
    present = {
        name for name in os.listdir(DATASHEET_DIR)
        if name.endswith((".pdf", ".json"))}
    referenced = {os.path.basename(entry["file"])
                  for entry in recorded.values()}
    problems = []
    for name in sorted(referenced - present):
        problems.append(("missing_file", name))
    for name in sorted(present - referenced):
        problems.append(("unreferenced_file", name))
    for name in sorted(recorded):
        entry = recorded[name]
        path = os.path.join(REPO_ROOT, "evidence", entry["file"])
        if not os.path.isfile(path):
            continue
        if digest(path) != entry["sha256"]:
            problems.append(("digest_mismatch", name))
    return problems


if __name__ == "__main__":
    sys.stdout.write(write_index() + "\n")
