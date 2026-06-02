import re
from collections import defaultdict
from typing import Any


def ref_prefix(component_id: str) -> str:
    match = re.match(r"^[A-Za-z]+", component_id or "")
    return match.group(0).upper() if match else "Other"


def group_components(components: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for component_id in components:
        grouped[ref_prefix(component_id)].append(component_id)
    return {prefix: sorted(ids) for prefix, ids in sorted(grouped.items())}


def component_label(component_id: str, component: dict[str, Any]) -> str:
    value = component.get("value") or component.get("part_number") or ""
    footprint = component.get("footprint") or ""
    if footprint:
        return f"{component_id}  {value}  [{footprint}]"
    return f"{component_id}  {value}"
