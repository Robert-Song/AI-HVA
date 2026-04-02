import json
import logging
from itertools import combinations
from pathlib import Path
from typing import Any
logger = logging.getLogger(__name__)

def load_netlist(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f'Netlist file not found: {path}')
    if p.suffix.lower() == '.net':
        raw = _load_kicad_net(p)
    elif p.suffix.lower() == '.json':
        raw = _load_json(p)
    else:
        content = p.read_text(encoding='utf-8', errors='replace')[:100].strip()
        if content.startswith('(export'):
            raw = _load_kicad_net(p)
        elif content.startswith('{'):
            raw = _load_json(p)
        else:
            raise ValueError(f'Unknown netlist format for {path}. Expected .net (KiCad S-expression) or .json')
    netlist = _validate_and_normalize(raw)
    logger.info(f"Loaded netlist: {len(netlist['components'])} components, {len(netlist['nets'])} nets, {len(netlist['connection_pairs'])} connection pairs")
    return netlist

def _load_kicad_net(p: Path) -> dict:
    from src.ingestion.kicad_parser import parse_kicad_netlist
    return parse_kicad_netlist(str(p))

def _load_json(p: Path) -> dict:
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

def _validate_and_normalize(raw: dict) -> dict[str, Any]:
    if 'components' not in raw:
        raise ValueError("Netlist data must have a 'components' key")
    components = raw['components']
    if 'nets' not in raw:
        raise ValueError("Netlist data must have a 'nets' key")
    nets = raw['nets']
    for comp_id in components:
        components[comp_id].setdefault('connected_to', [])
    for net in nets:
        comp_ids_in_net = [pin['component_id'] for pin in net['pins']]
        for cid in comp_ids_in_net:
            if cid not in components:
                continue
            for other_cid in comp_ids_in_net:
                if other_cid != cid and other_cid not in components[cid].get('connected_to', []):
                    components[cid]['connected_to'].append(other_cid)
    if 'connection_pairs' in raw and raw['connection_pairs']:
        connection_pairs = raw['connection_pairs']
    else:
        connection_pairs = _derive_connection_pairs(nets)
    return {'components': components, 'nets': nets, 'connection_pairs': connection_pairs}

def _derive_connection_pairs(nets: list[dict]) -> dict[str, dict]:
    pair_nets: dict[tuple[str, str], list[str]] = {}
    for net in nets:
        comp_ids = list(set((pin['component_id'] for pin in net['pins'])))
        for a, b in combinations(sorted(comp_ids), 2):
            key = (a, b)
            if key not in pair_nets:
                pair_nets[key] = []
            pair_nets[key].append(net['net_name'])
    connection_pairs = {}
    for (a, b), net_names in pair_nets.items():
        pair_id = f'{a}__{b}'
        connection_pairs[pair_id] = {'endpoints': [a, b], 'net_count': len(net_names), 'net_names': net_names}
    logger.info(f'Derived {len(connection_pairs)} connection pairs from nets')
    return connection_pairs