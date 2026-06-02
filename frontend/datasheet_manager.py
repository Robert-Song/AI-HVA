import shutil
import sys
from pathlib import Path
from typing import Any

from frontend.app_state import DatasheetResult


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = REPO_ROOT / "pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


def process_component_datasheets(
    components: dict[str, dict[str, Any]],
    selected_ids: set[str],
    netlist_path: Path,
    system_name: str,
    output_dir: Path,
) -> list[DatasheetResult]:
    pdf_dir, txt_dir = _run_datasheet_dirs(netlist_path, system_name, output_dir)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)
    results: list[DatasheetResult] = []
    for component_id in sorted(selected_ids):
        component = components.get(component_id, {})
        result = process_one_datasheet(component_id, component, pdf_dir, txt_dir)
        results.append(result)
    return results


def process_one_datasheet(
    component_id: str,
    component: dict[str, Any],
    pdf_dir: Path,
    txt_dir: Path,
) -> DatasheetResult:
    txt_path = txt_dir / f"{component_id}.txt"
    if txt_path.exists() and txt_path.stat().st_size > 0:
        return DatasheetResult(component_id, "ok", "text already exists", text_path=txt_path)

    pdf_path = pdf_dir / f"{component_id}.pdf"
    if not pdf_path.exists():
        url = str(component.get("datasheet_url") or "").strip()
        if not url or url == "~":
            return DatasheetResult(component_id, "failed", "no datasheet URL")
        try:
            _download_pdf(url, pdf_path)
        except Exception as exc:
            return DatasheetResult(component_id, "failed", f"download failed: {exc}")

    try:
        _validate_pdf(pdf_path)
        _extract_pdf_text(pdf_path, txt_path)
    except Exception as exc:
        return DatasheetResult(component_id, "failed", f"text extraction failed: {exc}", pdf_path=pdf_path)

    return DatasheetResult(component_id, "ok", "downloaded and extracted", pdf_path=pdf_path, text_path=txt_path)


def attach_manual_pdf(
    component_id: str,
    source_pdf: Path,
    netlist_path: Path,
    system_name: str,
    output_dir: Path,
) -> DatasheetResult:
    pdf_dir, txt_dir = _run_datasheet_dirs(netlist_path, system_name, output_dir)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{component_id}.pdf"
    txt_path = txt_dir / f"{component_id}.txt"
    shutil.copy2(source_pdf, pdf_path)
    try:
        _validate_pdf(pdf_path)
        _extract_pdf_text(pdf_path, txt_path)
    except Exception as exc:
        return DatasheetResult(component_id, "failed", f"manual PDF extraction failed: {exc}", pdf_path=pdf_path)
    return DatasheetResult(component_id, "ok", "manual PDF attached", pdf_path=pdf_path, text_path=txt_path)


def _download_pdf(url: str, destination: Path) -> None:
    import requests

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    destination.write_bytes(response.content)
    _validate_pdf(destination)


def _validate_pdf(path: Path) -> None:
    with path.open("rb") as handle:
        if not handle.read(5).startswith(b"%PDF-"):
            raise ValueError("file is not a valid PDF")


def _extract_pdf_text(pdf_path: Path, txt_path: Path) -> None:
    import pdfplumber

    full_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
    txt_path.write_text("\n\n".join(full_text), encoding="utf-8")


def _run_datasheet_dirs(
    netlist_path: Path,
    system_name: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    from src.runtime_paths import datasheet_dirs

    return datasheet_dirs(str(netlist_path), system_name or "Run", str(output_dir))
