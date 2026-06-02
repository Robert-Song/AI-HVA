import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = REPO_ROOT / "pipeline"

if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


def load_components(netlist_path: Path) -> dict[str, Any]:
    from src.ingestion.netlist_loader import load_netlist

    return load_netlist(str(netlist_path))


def run_pipeline_from_config(config) -> dict[str, Any]:
    from src.main import run_pipeline

    return run_pipeline(
        netlist_path=str(config.netlist_path),
        system_name=config.system_name or "Run",
        ignored_parts=sorted(config.ignored_parts),
        enable_subgrouping=config.enable_subgrouping,
        max_connection_hops=config.max_connection_hops,
        output_dir=str(config.output_dir) if config.output_dir else "",
        production=False,
    )
