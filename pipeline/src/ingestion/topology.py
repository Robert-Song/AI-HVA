import copy
import logging
import re
from itertools import combinations
from typing import Any

logger = logging.getLogger(__name__)

POWER_NET_KEYWORDS = (
    "GND",
    "GNDA",
    "DGND",
    "AGND",
    "PGND",
    "VCC",
    "VDD",
    "VSS",
    "VEE",
    "+3V3",
    "+5V",
    "+12V",
    "-12V",
    "VBAT",
    "VIN",
)

PASSIVE_PREFIXES = ("R", "C", "L", "FB", "F", "D", "TP")
SHUNT_PREFIXES = ("C", "D", "TVS")
SERIES_PREFIXES = ("R", "L", "FB", "F", "JP", "J")


def apply_topology_options(
    raw: dict[str, Any],
    ignored_parts: list[str] | None = None,
    max_connection_hops: int = 0,
) -> dict[str, Any]:
    """Apply user-selected topology transforms before netlist normalization."""
    ignored = {part.strip() for part in ignored_parts or [] if part.strip()}
    max_hops = max(0, min(int(max_connection_hops or 0), 10))
    transformed = copy.deepcopy(raw)
    metadata = {
        "ignored_parts": sorted(ignored),
        "bridged_parts": {},
        "removed_parts": {},
        "max_connection_hops": max_hops,
    }

    if ignored:
        transformed, metadata = bridge_ignored_parts(transformed, ignored, metadata)

    if max_hops > 0:
        transformed["connection_pairs"] = derive_hop_connection_pairs(
            transformed.get("components", {}),
            transformed.get("nets", []),
            max_hops,
        )

    transformed["topology_transform"] = metadata
    return transformed


def bridge_ignored_parts(
    raw: dict[str, Any],
    ignored_parts: set[str],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    components = raw.get("components", {})
    nets = raw.get("nets", [])
    parent: dict[str, str] = {}

    def find(name: str) -> str:
        parent.setdefault(name, name)
        if parent[name] != name:
            parent[name] = find(parent[name])
        return parent[name]

    def union(a: str, b: str) -> None:
        root_a = find(a)
        root_b = find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    comp_nets = _component_net_index(nets)
    for comp_id in sorted(ignored_parts):
        unique_nets = sorted(set(comp_nets.get(comp_id, [])))
        comp = components.get(comp_id, {"component_id": comp_id})
        if _should_bridge(comp_id, comp, unique_nets):
            union(unique_nets[0], unique_nets[1])
            metadata["bridged_parts"][comp_id] = {
                "from_nets": unique_nets,
                "reason": "ignored_two_terminal_series_component",
            }
        else:
            metadata["removed_parts"][comp_id] = {
                "nets": unique_nets,
                "reason": _removal_reason(comp_id, comp, unique_nets),
            }

    merged_nets: dict[str, dict[str, Any]] = {}
    for net in nets:
        net_name = net.get("net_name", "")
        root = find(net_name)
        pins = [
            pin
            for pin in net.get("pins", [])
            if pin.get("component_id") not in ignored_parts
        ]
        if not pins:
            continue
        entry = merged_nets.setdefault(
            root,
            {"net_name": root, "pins": [], "_aliases": set()},
        )
        entry["_aliases"].add(net_name)
        entry["pins"].extend(pins)

    rebuilt_nets = []
    for net in merged_nets.values():
        aliases = sorted(net.pop("_aliases"))
        if len(aliases) > 1:
            net["net_name"] = "__BRIDGED__".join(aliases)
        net["pins"] = _dedupe_pins(net["pins"])
        rebuilt_nets.append(net)

    raw["components"] = {
        cid: comp for cid, comp in components.items() if cid not in ignored_parts
    }
    raw["nets"] = rebuilt_nets
    raw.pop("connection_pairs", None)
    return raw, metadata


def derive_hop_connection_pairs(
    components: dict[str, dict[str, Any]],
    nets: list[dict[str, Any]],
    max_hops: int,
) -> dict[str, dict[str, Any]]:
    try:
        import networkx as nx
    except ImportError:
        logger.warning("NetworkX unavailable; falling back to direct connection pairs")
        return _derive_direct_pairs(nets)

    direct_pairs = _derive_direct_pairs(nets)
    graph = nx.Graph()
    graph.add_nodes_from(components.keys())
    edge_nets: dict[tuple[str, str], set[str]] = {}

    for pair in direct_pairs.values():
        a, b = pair["endpoints"]
        key = tuple(sorted((a, b)))
        edge_nets.setdefault(key, set()).update(pair.get("net_names", []))
        graph.add_edge(a, b)

    connection_pairs = dict(direct_pairs)
    major_components = sorted(
        cid for cid, comp in components.items() if not _is_passive_component(cid, comp)
    )

    for a, b in combinations(major_components, 2):
        pair_id = _pair_id(a, b)
        if pair_id in connection_pairs:
            connection_pairs[pair_id]["hop_count"] = 0
            connection_pairs[pair_id]["path"] = [a, b]
            connection_pairs[pair_id]["intermediate_components"] = []
            continue
        try:
            path = nx.shortest_path(graph, a, b)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue

        intermediate = path[1:-1]
        if len(intermediate) > max_hops:
            continue
        if not all(_is_passive_component(cid, components.get(cid, {})) for cid in intermediate):
            continue

        net_names = _nets_for_path(path, edge_nets)
        connection_pairs[pair_id] = {
            "endpoints": [a, b],
            "net_count": len(net_names),
            "net_names": net_names,
            "hop_count": len(intermediate),
            "path": path,
            "intermediate_components": intermediate,
            "derived_by": "max_connection_hops",
        }

    logger.info(
        "Derived %s connection pairs with max_hops=%s",
        len(connection_pairs),
        max_hops,
    )
    return connection_pairs


def _derive_direct_pairs(nets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    pair_nets: dict[tuple[str, str], list[str]] = {}
    for net in nets:
        comp_ids = sorted({pin["component_id"] for pin in net.get("pins", [])})
        for a, b in combinations(comp_ids, 2):
            pair_nets.setdefault((a, b), []).append(net.get("net_name", ""))
    return {
        _pair_id(a, b): {
            "endpoints": [a, b],
            "net_count": len(net_names),
            "net_names": net_names,
            "hop_count": 0,
            "path": [a, b],
            "intermediate_components": [],
        }
        for (a, b), net_names in pair_nets.items()
    }


def _component_net_index(nets: list[dict[str, Any]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for net in nets:
        for pin in net.get("pins", []):
            comp_id = pin.get("component_id")
            if comp_id:
                index.setdefault(comp_id, []).append(net.get("net_name", ""))
    return index


def _should_bridge(comp_id: str, comp: dict[str, Any], unique_nets: list[str]) -> bool:
    if len(unique_nets) != 2:
        return False
    prefix = _ref_prefix(comp_id)
    if prefix in SHUNT_PREFIXES:
        return False
    if _looks_like_shunt_to_supply(prefix, comp, unique_nets):
        return False
    if prefix in SERIES_PREFIXES:
        return True
    return _value_suggests_short(comp)


def _looks_like_shunt_to_supply(
    prefix: str,
    comp: dict[str, Any],
    unique_nets: list[str],
) -> bool:
    supply_count = sum(1 for net in unique_nets if _is_power_net(net))
    if prefix in SHUNT_PREFIXES and supply_count:
        return True
    if prefix == "R" and supply_count == 1 and not _value_suggests_short(comp):
        return True
    return supply_count == 2 and prefix in SHUNT_PREFIXES


def _removal_reason(comp_id: str, comp: dict[str, Any], unique_nets: list[str]) -> str:
    prefix = _ref_prefix(comp_id)
    if len(unique_nets) != 2:
        return "ignored_component_not_two_terminal"
    if prefix in SHUNT_PREFIXES or any(_is_power_net(net) for net in unique_nets):
        return "parallel_or_supply_shunt"
    if not (prefix in SERIES_PREFIXES or _value_suggests_short(comp)):
        return "ambiguous_ignored_component"
    return "removed_without_bridging"


def _dedupe_pins(pins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for pin in pins:
        key = (pin.get("component_id"), pin.get("pin_number"), pin.get("pin_function"))
        if key in seen:
            continue
        seen.add(key)
        result.append(pin)
    return result


def _nets_for_path(path: list[str], edge_nets: dict[tuple[str, str], set[str]]) -> list[str]:
    names: list[str] = []
    for a, b in zip(path, path[1:]):
        names.extend(sorted(edge_nets.get(tuple(sorted((a, b))), set())))
    return sorted(set(names))


def _is_passive_component(comp_id: str, comp: dict[str, Any]) -> bool:
    prefix = _ref_prefix(comp_id)
    if prefix in PASSIVE_PREFIXES:
        return True
    lib_part = str(comp.get("lib_part", "")).upper().strip()
    value = str(comp.get("value", "")).upper()
    passive_libparts = {"R", "C", "L", "FUSE", "INDUCTOR", "CAPACITOR", "RESISTOR"}
    return lib_part in passive_libparts or value in passive_libparts


def _is_power_net(net_name: str) -> bool:
    name = str(net_name).upper()
    return any(keyword in name for keyword in POWER_NET_KEYWORDS)


def _value_suggests_short(comp: dict[str, Any]) -> bool:
    value = str(comp.get("value", "") or comp.get("part_number", "")).upper()
    return bool(
        re.search(r"\b0\s*(R|OHM|OHMS|OMEGA)?\b", value)
        or "JUMPER" in value
        or "SHORT" in value
        or value in {"0", "0R"}
    )


def _ref_prefix(comp_id: str) -> str:
    match = re.match(r"^[A-Za-z]+", comp_id or "")
    return match.group(0).upper() if match else ""


def _pair_id(a: str, b: str) -> str:
    first, second = sorted((a, b))
    return f"{first}__{second}"
