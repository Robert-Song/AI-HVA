import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional
from src.analysis.models import PlanningOutput, TaskIOutput, TaskIIOutput, TaskIIIOutput, ControlAction, FeedbackSignal
from src.assembly.graph_analysis import compute_graph_analysis
from src.config import OUTPUT_DIR
logger = logging.getLogger(__name__)

def assemble_stpa_json(system_name: str, netlist_source: str, netlist_data: dict, planning_output: PlanningOutput, task_i_results: dict[str, TaskIOutput], task_ii_results: dict[str, TaskIIOutput], task_iii_results: dict[str, TaskIIIOutput], task_iv_results: dict[str, list[ControlAction]], task_v_results: dict[str, list[FeedbackSignal]], notes: dict[str, str]=None) -> dict:
    logger.info('=' * 60)
    logger.info('PHASE 4: Assembling STPA JSON')
    logger.info('=' * 60)
    notes = notes or {}
    stpa = {'system_metadata': {'system_name': system_name, 'netlist_source': netlist_source, 'analysis_date': date.today().isoformat()}, 'connection_pairs': {}, 'components': {}, 'connection_details': {}, 'graph_analysis': {}}
    for pair_id in planning_output.connection_pairs_to_analyze:
        pair = netlist_data['connection_pairs'].get(pair_id)
        if pair:
            stpa['connection_pairs'][pair_id] = {'endpoints': pair['endpoints'], 'net_count': pair['net_count'], 'net_names': pair['net_names']}
    for comp_id in planning_output.modeled_components:
        comp = netlist_data['components'].get(comp_id, {})
        task_i = task_i_results.get(comp_id)
        comp_name = comp.get('name', comp.get('part_number', comp_id))
        stpa['components'][comp_name] = {'component_id': comp_id, 'component_class': task_i.component_class.value if task_i else 'passive', 'functional_description': task_i.functional_description if task_i else '', 'safety_critical': task_i.safety_critical if task_i else False, 'connected_to': comp.get('connected_to', [])}
    for pair_id in planning_output.connection_pairs_to_analyze:
        pair = netlist_data['connection_pairs'].get(pair_id)
        if not pair:
            continue
        task_ii = task_ii_results.get(pair_id)
        task_iv = task_iv_results.get(pair_id, [])
        task_v = task_v_results.get(pair_id, [])
        control_actions_serialized = [ca.model_dump(by_alias=True) for ca in task_iv]
        feedback_signals_serialized = [fs.model_dump(by_alias=True) for fs in task_v]
        all_sources = _collect_sources(task_iv, task_v)
        stpa['connection_details'][pair_id] = {'endpoints': pair['endpoints'], 'physical_interface': task_ii.physical_interface if task_ii else 'unknown', 'control_actions': control_actions_serialized, 'feedback_signals': feedback_signals_serialized, 'source': all_sources, 'notes': notes.get(pair_id, '')}
    stpa['graph_analysis'] = compute_graph_analysis(stpa)
    logger.info(f"Assembly complete: {len(stpa['components'])} components, {len(stpa['connection_details'])} connections")
    return stpa

def save_stpa_json(stpa: dict, system_name: str, output_dir: str='') -> str:
    out_dir = Path(output_dir or OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = ''.join((c if c.isalnum() or c in '-_' else '_' for c in system_name))
    filename = f'stpa_{safe_name}_{date.today().isoformat()}.json'
    filepath = out_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stpa, f, indent=2, ensure_ascii=False)
    logger.info(f'STPA JSON saved to: {filepath}')
    return str(filepath)

def _collect_sources(control_actions: list[ControlAction], feedback_signals: list[FeedbackSignal]) -> list[str]:
    sources = set()
    sources.add('schematic_netlist')
    for ca in control_actions:
        if hasattr(ca, 'source') and ca.source:
            sources.update(ca.source)
    for fs in feedback_signals:
        if hasattr(fs, 'source') and fs.source:
            sources.update(fs.source)
    return sorted(sources)