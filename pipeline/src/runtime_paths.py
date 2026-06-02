import hashlib
from pathlib import Path

from src.config import PROJECT_ROOT


def safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)


def build_run_id(netlist_path: str, system_name: str) -> str:
    path = Path(netlist_path)
    digest = hashlib.sha256()
    digest.update(str(path.resolve()).encode("utf-8", errors="replace"))
    if path.exists():
        digest.update(path.read_bytes())
    stem = safe_name(path.stem or "netlist")
    return f"{stem}_{digest.hexdigest()[:12]}"


def run_artifact_dir(
    netlist_path: str,
    system_name: str,
    output_dir: str = "",
) -> Path:
    return PROJECT_ROOT / "hardware_runs" / build_run_id(netlist_path, system_name)


def datasheet_dirs(
    netlist_path: str,
    system_name: str,
    output_dir: str = "",
) -> tuple[Path, Path]:
    root = run_artifact_dir(netlist_path, system_name, output_dir)
    return root / "pdf_datasheets", root / "datasheets"


def component_store_path(
    netlist_path: str,
    system_name: str,
    output_dir: str = "",
) -> Path:
    return run_artifact_dir(netlist_path, system_name, output_dir) / "component_store.json"
