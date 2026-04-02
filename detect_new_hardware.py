"""
detect_new_hardware.py (Story 12)

Detect newly added hardware by comparing parsed components from a KiCad .net file
against a stored component database (JSON file).

Usage: python detect_new_hardware.py <input_netlist> <component_db.json> <report.json>

Author: Alex Kolyaskin 2-24-26
"""

import json
import os
import sys
from typing import Any, Dict, List, Set

from isolate_hardware import extract_components_from_netlist, NetlistParseError


def load_db(db_path: str) -> Dict[str, Any]:
    """
    Load the component database JSON. If it doesn't exist, return an empty DB.
    """
    if not os.path.isfile(db_path):
        return {"known_refs": [], "metadata_by_ref": {}}

    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # tolerate older formats
    if "known_refs" not in data:
        data["known_refs"] = []
    if "metadata_by_ref" not in data:
        data["metadata_by_ref"] = {}

    return data


def save_db(db_path: str, data: Dict[str, Any]) -> None:
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def refs_from_components(components: List[Dict[str, Any]]) -> Set[str]:
    refs: Set[str] = set()
    for c in components:
        r = c.get("ref")
        if isinstance(r, str) and r.strip():
            refs.add(r.strip())
    return refs


def build_metadata(comp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Store a small amount of useful metadata for future comparison/debugging.
    """
    return {
        "value": comp.get("value"),
        "footprint": comp.get("footprint"),
        "lib": comp.get("lib"),
        "name": comp.get("name"),
    }


def detect_new_hardware(net_path: str, db_path: str) -> Dict[str, Any]:
    """
    Compare current netlist components to a stored DB and return a report.
    """
    components = extract_components_from_netlist(net_path)
    current_refs = refs_from_components(components)

    db = load_db(db_path)
    known_refs = set(db.get("known_refs", []))

    new_refs = sorted(list(current_refs - known_refs))
    known_in_current = sorted(list(current_refs & known_refs))

    # Optional: detect removed components (not required by acceptance criteria)
    removed_refs = sorted(list(known_refs - current_refs))

    # Update DB: add new refs + metadata
    meta = db.get("metadata_by_ref", {})
    for comp in components:
        r = comp.get("ref")
        if isinstance(r, str) and r in current_refs:
            meta[r] = build_metadata(comp)

    db["known_refs"] = sorted(list(known_refs | current_refs))
    db["metadata_by_ref"] = meta
    save_db(db_path, db)

    return {
        "input": net_path,
        "db_path": db_path,
        "current_component_count": len(current_refs),
        "new_components_count": len(new_refs),
        "new_components": new_refs,
        "known_components_count": len(known_in_current),
        "removed_components": removed_refs,  # optional info
        "notification": (
            "New hardware detected!" if new_refs else "No new hardware detected."
        ),
    }


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) != 3:
        print("Usage: python detect_new_hardware.py <netlist_filename> <component_db.json> <report.json>")
        sys.exit(1)

    input_net, db_path, report_path = args

    try:
        report = detect_new_hardware(input_net, db_path)

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        # “Notification” to user (console)
        print(report["notification"])
        if report["new_components"]:
            print("New components:")
            for r in report["new_components"]:
                print(f"  - {r}")

        print(f"Wrote report to {report_path}")
        sys.exit(0)

    except NetlistParseError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)