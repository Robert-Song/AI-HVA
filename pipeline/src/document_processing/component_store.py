import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
logger = logging.getLogger(__name__)

@dataclass
class ComponentSections:
    component_id: str
    part_number: str
    identity: Optional[str] = None
    function: Optional[str] = None
    pin_config: Optional[str] = None
    electrical_key: Optional[str] = None
    timing: Optional[str] = None
    interface_protocol: Optional[str] = None
    application_circuit: Optional[str] = None

    def sections_for_task(self, task: str) -> str:
        task_section_map = {'classify': ['identity', 'function', 'pin_config'], 'signals': ['identity', 'function', 'pin_config', 'electrical_key', 'interface_protocol'], 'control_feedback': ['function', 'pin_config', 'electrical_key', 'interface_protocol'], 'signal_details': ['pin_config', 'electrical_key', 'timing', 'interface_protocol', 'application_circuit']}
        sections = task_section_map.get(task, [])
        parts = []
        for s in sections:
            val = getattr(self, s, None)
            if val:
                parts.append(f'[{s.upper()}]\n{val}')
        return '\n\n'.join(parts)

def save_store(store: dict[str, ComponentSections], path: str) -> None:
    data = {cid: asdict(cs) for cid, cs in store.items()}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f'Saved component store: {len(store)} components → {path}')

def load_store(path: str) -> dict[str, ComponentSections]:
    p = Path(path)
    if not p.exists():
        logger.warning(f'Component store not found: {path}. Returning empty store.')
        return {}
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
    store = {}
    for cid, fields in data.items():
        store[cid] = ComponentSections(**fields)
    logger.info(f'Loaded component store: {len(store)} components from {path}')
    return store

def build_component_store(components: dict, datasheet_dir: str) -> dict[str, ComponentSections]:
    from src.document_processing.section_extractor import extract_sections
    store: dict[str, ComponentSections] = {}
    ds_dir = Path(datasheet_dir)
    for comp_id, comp_data in components.items():
        part_number = comp_data.get('part_number', comp_data.get('value', ''))
        if not part_number:
            logger.warning(f'{comp_id}: No part number found, skipping')
            continue
        datasheet_url = comp_data.get('datasheet_url', '')
        text_file = _find_datasheet_file(ds_dir, part_number, datasheet_url)
        if text_file is None:
            logger.warning(f'{comp_id}: No datasheet text file found for {part_number}')
            continue
        raw_text = text_file.read_text(encoding='utf-8', errors='replace')
        sections = extract_sections(comp_id, part_number, raw_text)
        if sections:
            store[comp_id] = sections
    logger.info(f'Built component store: {len(store)}/{len(components)} components processed')
    return store

def _find_datasheet_file(ds_dir: Path, part_number: str, datasheet_url: str='') -> Optional[Path]:
    if not ds_dir.exists():
        return None
    candidates = [f'{part_number}.txt', f'{part_number}Plumber.txt', f'{part_number}-D.txt', f'{part_number}-DPlumber.txt', f'{part_number.lower()}.txt', f'{part_number.lower()}Plumber.txt']
    if datasheet_url:
        from urllib.parse import urlparse
        url_path = urlparse(datasheet_url).path
        pdf_stem = Path(url_path).stem
        if pdf_stem and pdf_stem.lower() != part_number.lower():
            candidates.extend([f'{pdf_stem}.txt', f'{pdf_stem}Plumber.txt', f'{pdf_stem.lower()}.txt', f'{pdf_stem.lower()}Plumber.txt'])
    for candidate in candidates:
        p = ds_dir / candidate
        if p.exists():
            return p
    for p in ds_dir.glob('*.txt'):
        if part_number.lower() in p.stem.lower():
            return p
    return None