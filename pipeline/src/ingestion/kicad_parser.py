import logging
import re
from pathlib import Path
from typing import Any, Optional
logger = logging.getLogger(__name__)

def _tokenize(text: str) -> list[str]:
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in ' \t\n\r':
            i += 1
            continue
        if c == '(':
            tokens.append('(')
            i += 1
            continue
        if c == ')':
            tokens.append(')')
            i += 1
            continue
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == '\\':
                    j += 1
                j += 1
            token = text[i + 1:j]
            tokens.append(token)
            i = j + 1
            continue
        j = i
        while j < n and text[j] not in ' \t\n\r()"':
            j += 1
        tokens.append(text[i:j])
        i = j
    return tokens

def _parse_sexpr(tokens: list[str], pos: int=0) -> tuple[Any, int]:
    if pos >= len(tokens):
        return (None, pos)
    token = tokens[pos]
    if token == '(':
        result = []
        pos += 1
        while pos < len(tokens) and tokens[pos] != ')':
            value, pos = _parse_sexpr(tokens, pos)
            if value is not None:
                result.append(value)
        pos += 1
        return (result, pos)
    elif token == ')':
        return (None, pos + 1)
    else:
        return (token, pos + 1)

def parse_sexpr_string(text: str) -> Any:
    tokens = _tokenize(text)
    result, _ = _parse_sexpr(tokens, 0)
    return result

def _find_node(sexpr: list, tag: str) -> Optional[list]:
    if not isinstance(sexpr, list):
        return None
    for item in sexpr:
        if isinstance(item, list) and len(item) > 0 and (item[0] == tag):
            return item
    return None

def _find_all_nodes(sexpr: list, tag: str) -> list[list]:
    if not isinstance(sexpr, list):
        return []
    return [item for item in sexpr if isinstance(item, list) and len(item) > 0 and (item[0] == tag)]

def _get_value(sexpr: list, tag: str, default: str='') -> str:
    node = _find_node(sexpr, tag)
    if node and len(node) > 1:
        return str(node[1])
    return default

def _get_field_value(sexpr: list, field_name: str) -> str:
    fields_node = _find_node(sexpr, 'fields')
    if fields_node is None:
        return ''
    for field in _find_all_nodes(fields_node, 'field'):
        name_node = _find_node(field, 'name')
        if name_node and len(name_node) > 1 and (name_node[1] == field_name):
            for item in field[1:]:
                if isinstance(item, str):
                    return item
                if isinstance(item, list) and item[0] != 'name':
                    return str(item[1]) if len(item) > 1 else ''
            return ''
    return ''

def parse_kicad_netlist(filepath: str) -> dict[str, Any]:
    path = Path(filepath)
    text = path.read_text(encoding='utf-8', errors='replace')
    tree = parse_sexpr_string(text)
    if not isinstance(tree, list) or tree[0] != 'export':
        raise ValueError(f'Not a valid KiCad netlist: expected (export ...), got {(tree[0] if isinstance(tree, list) else type(tree))}')
    libparts = _extract_libparts(tree)
    components = _extract_components(tree, libparts)
    nets = _extract_nets(tree)
    logger.info(f'Parsed KiCad netlist: {len(components)} components, {len(nets)} nets from {path.name}')
    return {'components': components, 'nets': nets}

def _extract_libparts(tree: list) -> dict[str, dict]:
    libparts_node = _find_node(tree, 'libparts')
    if libparts_node is None:
        return {}
    result = {}
    for lp in _find_all_nodes(libparts_node, 'libpart'):
        lib = _get_value(lp, 'lib')
        part = _get_value(lp, 'part')
        key = f'{lib}::{part}'
        description = _get_value(lp, 'description')
        docs = _get_value(lp, 'docs')
        footprint = _get_field_value(lp, 'Footprint')
        pins = []
        pins_node = _find_node(lp, 'pins')
        if pins_node:
            for pin in _find_all_nodes(pins_node, 'pin'):
                pins.append({'pin_number': _get_value(pin, 'num'), 'pin_name': _get_value(pin, 'name'), 'pin_type': _get_value(pin, 'type')})
        result[key] = {'part': part, 'description': description, 'datasheet_url': docs, 'footprint': footprint, 'pins': pins}
    return result

def _extract_components(tree: list, libparts: dict) -> dict[str, dict]:
    components_node = _find_node(tree, 'components')
    if components_node is None:
        return {}
    result = {}
    for comp in _find_all_nodes(components_node, 'comp'):
        ref = _get_value(comp, 'ref')
        value = _get_value(comp, 'value')
        libsource = _find_node(comp, 'libsource')
        lib_name = _get_value(libsource, 'lib') if libsource else ''
        lib_part = _get_value(libsource, 'part') if libsource else ''
        lib_desc = _get_value(libsource, 'description') if libsource else ''
        libpart_key = f'{lib_name}::{lib_part}'
        libpart = libparts.get(libpart_key, {})
        part_number = _get_field_value(comp, 'Part Number') or (value if value and value != '~' else '') or lib_part
        footprint = _get_value(comp, 'footprint') or _get_field_value(comp, 'Footprint') or libpart.get('footprint', '')
        datasheet_url = _get_value(comp, 'datasheet') or _get_field_value(comp, 'Datasheet') or libpart.get('datasheet_url', '')
        description = lib_desc or libpart.get('description', '')
        name = part_number if part_number else ref
        result[ref] = {'component_id': ref, 'part_number': part_number, 'value': value if value != '~' else part_number, 'footprint': footprint, 'name': name, 'description': description, 'datasheet_url': datasheet_url, 'lib_part': lib_part, 'pins': libpart.get('pins', [])}
    return result

def _extract_nets(tree: list) -> list[dict]:
    nets_node = _find_node(tree, 'nets')
    if nets_node is None:
        return []
    result = []
    for net in _find_all_nodes(nets_node, 'net'):
        net_name = _get_value(net, 'name')
        pins = []
        for node in _find_all_nodes(net, 'node'):
            pins.append({'component_id': _get_value(node, 'ref'), 'pin_number': _get_value(node, 'pin'), 'pin_function': _get_value(node, 'pinfunction'), 'pin_type': _get_value(node, 'pintype')})
        if pins:
            result.append({'net_name': net_name, 'pins': pins})
    return result