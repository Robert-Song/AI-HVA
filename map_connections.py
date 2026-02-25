"""
map_connections.py (Story 6 + 10)

Map how essential components are connected via nets/pins in a KiCad .net file (kinparse).
Optionally exclude user-specified components from the output.

Usage: python map_connections.py <input_netlist> <output_json> [exclude_file]

Author: Alex Kolyaskin 2-22-26
"""

import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple
from kinparse import parse_netlist
from pyparsing.exceptions import ParseException


class NetlistParseError(Exception):
    """
    Raised when a netlist cannot be parsed properly.
    """
    pass


def load_exclusions(exclude_path: str) -> Set[str]:
    """
    Load excluded component refs from a file.
    Lines starting with '#' are comments.
    """
    excluded: Set[str] = set()
    if not exclude_path:
        return excluded

    if not os.path.isfile(exclude_path):
        raise NetlistParseError(f"Exclude file not found: {exclude_path}")

    with open(exclude_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            excluded.add(line)
    return excluded


def ref_prefix(ref: str) -> str:
    """
    Extract the alphabetic prefix from a component reference designator.
        "U304" -> "U"
        "R15" -> "R"
    """
    if not ref:
        return ""
    out = []
    for ch in ref:
        if ch.isalpha() or ch in ["_", "-"]:
            out.append(ch)
        else:
            break
    return "".join(out).upper()


def build_essential_set(nlst: Any, excluded_prefixes: Set[str]) -> Set[str]:
    """
    Build a set of essential component reference designators from a parsed netlist.

    Returns:
        A set of reference designators -> {"U304", "U307"}
    """
    essential: Set[str] = set()
    for p in getattr(nlst, "parts", []):
        r = getattr(p, "ref", None)
        if isinstance(r, str) and ref_prefix(r) not in excluded_prefixes:
            essential.add(r)
    return essential


def pin_ref_num(pin_obj: Any) -> Tuple[str, str]:
    """
    Extract the component reference and pin number from a kinparse net pin object.

    the kinparse net pin objects have:
      - pin_obj.ref (U304)
      - pin_obj.num (1)
      - pin_obj.type (power_in / passive)
    """
    r = getattr(pin_obj, "ref", "") or ""
    n = getattr(pin_obj, "num", "") or ""
    return str(r), str(n)


def map_connections(net_path: str, essential_only: bool = True, excluded_refs: Set[str] = None) -> Dict[str, Any]:
    """
    Parse a KiCad netlist and generate a connectivity mapping between components.

    Returns:
        A dictionary containing connection and metadata information.
    """
    if excluded_refs is None:
        excluded_refs = set()

    try:
        nlst = parse_netlist(net_path)
    except ParseException as e:
        raise NetlistParseError(f"Netlist parse error: {e}") from e
    except Exception as e:
        raise NetlistParseError(f"Unexpected parsing failure: {e}") from e

    nets = getattr(nlst, "nets", None)
    if nets is None:
        raise NetlistParseError("Parsed netlist but found no net list (nlst.nets missing).")

    excluded_prefixes = {"C", "R"} # optional exclusions "L", "D", "FB", "TP", "F"
    essential_refs = build_essential_set(nlst, excluded_prefixes) if essential_only else set()

    # Apply user exclusions to essential set (Story 10)
    if essential_only and excluded_refs:
        essential_refs = {r for r in essential_refs if r not in excluded_refs}

    connections: List[Dict[str, Any]] = []
    adjacency: Dict[str, Set[str]] = defaultdict(set)

    # Dedup key includes pins so you still “show which pins”
    seen_edges: Set[Tuple[str, str, str, str, str]] = set()
    # (net_name, a_ref, a_pin, b_ref, b_pin) with refs ordered for stability

    for net in nets:
        net_name = getattr(net, "name", None)
        net_code = getattr(net, "code", None)

        pins = getattr(net, "pins", None)
        if not pins:
            continue

        refpins = [pin_ref_num(p) for p in pins]

        if essential_only:
            refpins = [(r, p) for (r, p) in refpins if r in essential_refs]
        else:
            # if mapping all, still honor explicit exclusions
            if excluded_refs:
                refpins = [(r, p) for (r, p) in refpins if r not in excluded_refs]

        # ignore redundant connections
        if len(refpins) < 2:
            continue

        for i in range(len(refpins)):
            for j in range(i + 1, len(refpins)):
                a_ref, a_pin = refpins[i]
                b_ref, b_pin = refpins[j]

                # Skip self-connections
                if a_ref == b_ref:
                    continue

                # Canonical ordering
                if (b_ref, b_pin) < (a_ref, a_pin):
                    a_ref, a_pin, b_ref, b_pin = b_ref, b_pin, a_ref, a_pin

                key = (str(net_name), a_ref, a_pin, b_ref, b_pin)
                if key in seen_edges:
                    continue
                seen_edges.add(key)

                adjacency[a_ref].add(b_ref)
                adjacency[b_ref].add(a_ref)

                connections.append(
                    {
                        "net": {"name": net_name, "code": net_code},
                        "a": {"ref": a_ref, "pin": a_pin},
                        "b": {"ref": b_ref, "pin": b_pin},
                    }
                )

    return {
        "input": net_path,
        "essential_only": essential_only,
        "essential_component_count": len(build_essential_set(nlst, excluded_prefixes)) if essential_only else None,
        "excluded_components": sorted(list(excluded_refs)) if excluded_refs else [],
        "included_essential_component_count": len(essential_refs) if essential_only else None,
        "connections_count": len(connections),
        "connections": connections,
        "adjacency": {k: sorted(v) for k, v in adjacency.items()},
        "excluded_prefixes": sorted(excluded_prefixes) if essential_only else None,
    }


if __name__ == "__main__":

    args = sys.argv[1:]

    if len(args) not in (2, 3):
        print("Usage: python map_connections.py <netlist_filename> <output_json_filename> [exclude_file]")
        sys.exit(1)

    input_net = args[0]
    output_json = args[1]
    exclude_file = args[2] if len(args) == 3 else ""

    try:
        excluded_refs = load_exclusions(exclude_file) if exclude_file else set()
        result = map_connections(input_net, essential_only=True, excluded_refs=excluded_refs)

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        print(f"Wrote {result['connections_count']} connections to {output_json}")

    except NetlistParseError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
