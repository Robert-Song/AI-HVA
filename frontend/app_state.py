from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineConfig:
    kicad_cli_path: Path | None = None
    input_path: Path | None = None
    netlist_path: Path | None = None
    output_dir: Path | None = None
    system_name: str = "Run"
    selected_components: set[str] = field(default_factory=set)
    ignored_parts: set[str] = field(default_factory=set)
    enable_subgrouping: bool = False
    max_connection_hops: int = 0


@dataclass
class DatasheetResult:
    component_id: str
    status: str
    message: str
    pdf_path: Path | None = None
    text_path: Path | None = None
