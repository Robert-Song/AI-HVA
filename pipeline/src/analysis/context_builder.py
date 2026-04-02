import logging
from typing import Optional
from src.document_processing.component_store import ComponentSections
from src.document_processing.domain_store import DomainKnowledgeStore, build_planning_query, build_classify_query, build_signals_query, build_control_feedback_query, build_control_details_query, build_feedback_details_query
logger = logging.getLogger(__name__)

def get_component_connections_text(component_id: str, netlist_data: dict) -> str:
    comp = netlist_data['components'].get(component_id, {})
    connected_to = comp.get('connected_to', [])
    lines = []
    for other_id in connected_to:
        other = netlist_data['components'].get(other_id, {})
        other_part = other.get('part_number', other.get('value', 'unknown'))
        lines.append(f'  - {other_id} ({other_part})')
    for net in netlist_data.get('nets', []):
        comp_ids_in_net = [pin['component_id'] for pin in net['pins']]
        if component_id in comp_ids_in_net:
            others = [cid for cid in comp_ids_in_net if cid != component_id]
            if others:
                lines.append(f"    via net: {net['net_name']} → {', '.join(others)}")
    return 'Connected to:\n' + '\n'.join(lines) if lines else 'No connections found.'

def build_planning_context(netlist_data: dict, domain_store: Optional[DomainKnowledgeStore]) -> str:
    if domain_store is None:
        return ''
    query = build_planning_query()
    results = domain_store.query(query)
    return domain_store.format_for_prompt(results)

def build_task_i_context(component_id: str, netlist_data: dict, component_store: dict[str, ComponentSections], domain_store: Optional[DomainKnowledgeStore]) -> tuple[str, str, str]:
    comp = netlist_data['components'].get(component_id, {})
    part_number = comp.get('part_number', comp.get('value', ''))
    connections_text = get_component_connections_text(component_id, netlist_data)
    cs = component_store.get(component_id)
    component_docs = cs.sections_for_task('classify') if cs else ''
    domain_knowledge = ''
    if domain_store:
        query = build_classify_query(part_number)
        results = domain_store.query(query)
        domain_knowledge = domain_store.format_for_prompt(results)
    return (connections_text, component_docs, domain_knowledge)

def build_task_ii_context(pair_id: str, netlist_data: dict, task_i_results: dict, component_store: dict[str, ComponentSections], domain_store: Optional[DomainKnowledgeStore]) -> tuple[dict, dict, dict, dict, str, str, str]:
    pair = netlist_data['connection_pairs'][pair_id]
    ep_a_id, ep_b_id = pair['endpoints']
    endpoint_a = netlist_data['components'].get(ep_a_id, {'component_id': ep_a_id})
    endpoint_b = netlist_data['components'].get(ep_b_id, {'component_id': ep_b_id})
    task_i_a = _task_i_to_dict(task_i_results.get(ep_a_id))
    task_i_b = _task_i_to_dict(task_i_results.get(ep_b_id))
    cs_a = component_store.get(ep_a_id)
    cs_b = component_store.get(ep_b_id)
    docs_a = cs_a.sections_for_task('signals') if cs_a else ''
    docs_b = cs_b.sections_for_task('signals') if cs_b else ''
    domain_knowledge = ''
    if domain_store:
        part_a = endpoint_a.get('part_number', endpoint_a.get('value', ''))
        part_b = endpoint_b.get('part_number', endpoint_b.get('value', ''))
        interface_hint = ''
        query = build_signals_query(part_a, part_b, interface_hint)
        results = domain_store.query(query)
        domain_knowledge = domain_store.format_for_prompt(results)
    return (endpoint_a, endpoint_b, task_i_a, task_i_b, docs_a, docs_b, domain_knowledge)

def build_task_iii_context(pair_id: str, netlist_data: dict, task_i_results: dict, task_ii_output: dict, component_store: dict[str, ComponentSections], domain_store: Optional[DomainKnowledgeStore]) -> tuple[dict, dict, dict, dict, str, str, str]:
    pair = netlist_data['connection_pairs'][pair_id]
    ep_a_id, ep_b_id = pair['endpoints']
    endpoint_a = netlist_data['components'].get(ep_a_id, {'component_id': ep_a_id})
    endpoint_b = netlist_data['components'].get(ep_b_id, {'component_id': ep_b_id})
    task_i_a = _task_i_to_dict(task_i_results.get(ep_a_id))
    task_i_b = _task_i_to_dict(task_i_results.get(ep_b_id))
    cs_a = component_store.get(ep_a_id)
    cs_b = component_store.get(ep_b_id)
    docs_a = cs_a.sections_for_task('control_feedback') if cs_a else ''
    docs_b = cs_b.sections_for_task('control_feedback') if cs_b else ''
    domain_knowledge = ''
    if domain_store:
        interface_type = task_ii_output.get('physical_interface', '')
        signal_names = [s['signal_name'] for s in task_ii_output.get('signals', [])]
        query = build_control_feedback_query(' '.join(signal_names[:3]), interface_type)
        results = domain_store.query(query)
        domain_knowledge = domain_store.format_for_prompt(results)
    return (endpoint_a, endpoint_b, task_i_a, task_i_b, docs_a, docs_b, domain_knowledge)

def build_task_iv_v_context(pair_id: str, netlist_data: dict, component_store: dict[str, ComponentSections], domain_store: Optional[DomainKnowledgeStore], task_type: str='control') -> tuple[dict, dict, str, str, str]:
    pair = netlist_data['connection_pairs'][pair_id]
    ep_a_id, ep_b_id = pair['endpoints']
    endpoint_a = netlist_data['components'].get(ep_a_id, {'component_id': ep_a_id})
    endpoint_b = netlist_data['components'].get(ep_b_id, {'component_id': ep_b_id})
    cs_a = component_store.get(ep_a_id)
    cs_b = component_store.get(ep_b_id)
    docs_a = cs_a.sections_for_task('signal_details') if cs_a else ''
    docs_b = cs_b.sections_for_task('signal_details') if cs_b else ''
    domain_knowledge = ''
    if domain_store:
        if task_type == 'control':
            query = build_control_details_query('enable disable command', '')
        else:
            query = build_feedback_details_query('measurement status', '')
        results = domain_store.query(query)
        domain_knowledge = domain_store.format_for_prompt(results)
    return (endpoint_a, endpoint_b, docs_a, docs_b, domain_knowledge)

def _task_i_to_dict(task_i_output) -> dict:
    if task_i_output is None:
        return {'component_class': 'unknown', 'functional_description': 'unknown', 'safety_critical': False}
    if hasattr(task_i_output, 'model_dump'):
        return task_i_output.model_dump()
    if isinstance(task_i_output, dict):
        return task_i_output
    return {'component_class': 'unknown', 'functional_description': 'unknown', 'safety_critical': False}