import subprocess
from pathlib import Path


def export_netlist(kicad_cli_path: Path, schematic_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    netlist_path = output_dir / f"{schematic_path.stem}.net"
    command = [
        str(kicad_cli_path),
        "sch",
        "export",
        "netlist",
        "-o",
        str(netlist_path),
        str(schematic_path),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"kicad-cli export failed: {stderr}")
    if not netlist_path.exists():
        raise FileNotFoundError(f"kicad-cli did not create {netlist_path}")
    return netlist_path


def resolve_input_netlist(
    input_path: Path,
    kicad_cli_path: Path | None,
    work_dir: Path,
) -> Path:
    suffix = input_path.suffix.lower()
    if suffix == ".net":
        return input_path
    if suffix == ".kicad_sch":
        if not kicad_cli_path:
            raise ValueError("A kicad-cli executable is required for schematic export.")
        return export_netlist(kicad_cli_path, input_path, work_dir)
    raise ValueError("Expected a .kicad_sch schematic or exported .net netlist.")
