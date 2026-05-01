"""
isolate_hardware.py (Story 4)

Isolate all hardware components from a KiCad .net file.

Usage: python isolate_hardware.py <input_netlist> <output_json>

Author: Alex Kolyaskin 2-22-26
"""

import json
import os
import sys
from typing import Any, Dict, List
from kinparse import parse_netlist
from pyparsing.exceptions import ParseException


class NetlistParseError(Exception):
    """
    Raised when a netlist cannot be parsed properly.
    """
    pass


def component_to_dict(p: Any) -> Dict[str, Any]:
    """
    Convert a kinparse part object into a standardized structure.
    """
    fields = {}
    for f in getattr(p, "fields", []):
        fields[getattr(f, "name", "")] = getattr(f, "value", "")

    sheetpath = None
    sp = getattr(p, "sheetpath", None)
    if sp:
        sheetpath = {
            "names": getattr(sp, "names", None),
            "tstamps": getattr(sp, "tstamps", None),
        }

    return {
        "ref": getattr(p, "ref", None),
        "value": getattr(p, "value", None),
        "footprint": getattr(p, "footprint", None),
        "datasheet": getattr(p, "datasheet", None),
        "lib": getattr(p, "lib", None),
        "name": getattr(p, "name", None),
        "desc": getattr(p, "desc", None),
        "tstamp": getattr(p, "tstamp", None),
        "sheetpath": sheetpath,
        "fields": fields,
    }


def extract_components_from_netlist(net_path: str) -> List[Dict[str, Any]]:
    """
    Parse a KiCad .net file and extract all hardware components.

    Returns:
        A list of dictionaries, where each dictionary represents a component
    """
    try:
        nlst = parse_netlist(net_path)
    except ParseException as e:
        raise NetlistParseError(f"Netlist parse error: {e}") from e
    except Exception as e:
        raise NetlistParseError(f"Unexpected parsing failure: {e}") from e

    parts = getattr(nlst, "parts", None)
    if parts is None:
        raise NetlistParseError("Parsed netlist but found no component list (nlst.parts missing).")

    return [component_to_dict(p) for p in parts]

def extract_components_from_netlist_with_whitelist(net_path: str, whitelist: list) -> List[Dict[str, Any]]:
    """
    Parse a KiCad .net file and extract all hardware components.

    Returns:
        A list of dictionaries, where each dictionary represents a component
    """
    try:
        nlst = parse_netlist(net_path)
    except ParseException as e:
        raise NetlistParseError(f"Netlist parse error: {e}") from e
    except Exception as e:
        raise NetlistParseError(f"Unexpected parsing failure: {e}") from e

    parts = getattr(nlst, "parts", None)
    if parts is None:
        raise NetlistParseError("Parsed netlist but found no component list (nlst.parts missing).")
    newparts = []
    for p in parts:
        if p.name in whitelist:
            newparts.append(p)

    return [component_to_dict(p) for p in newparts]


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) != 2:
        print("Usage: python isolate_hardware.py <netlist_filename> <output_filename>")
        sys.exit(1)

    input_net = args[0]
    output_json = args[1]

    if not os.path.isfile(input_net):
        print(f"Error: input netlist file not found: {input_net}", file=sys.stderr)
        sys.exit(1)

    try:
        components = extract_components_from_netlist(input_net)

        out_obj = {
            "input": input_net,
            "component_count": len(components),
            "components": components,
        }

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(out_obj, f, indent=2)

        print(f"Wrote {len(components)} components to {output_json}")

    except NetlistParseError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)