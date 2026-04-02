import logging
from typing import Optional
from src.analysis.context_builder import build_task_iv_v_context
from src.analysis.models import TaskIIOutput, TaskIIIOutput, TaskIVOutput, ControlAction
from src.analysis.prompts import TASK_IV_SYSTEM_PROMPT, task_iv_user_prompt
from src.document_processing.component_store import ComponentSections
from src.document_processing.domain_store import DomainKnowledgeStore
from src.llm.validation import run_llm_task
from src.config import ANALYSIS_MODEL
logger = logging.getLogger(__name__)

def run_task_iv(pair_id: str, netlist_data: dict, task_ii_output: TaskIIOutput, task_iii_output: TaskIIIOutput, component_store: dict[str, ComponentSections], domain_store: Optional[DomainKnowledgeStore]=None) -> list[ControlAction]:
    control_signals = _get_control_signals(task_ii_output, task_iii_output)
    if not control_signals:
        logger.info(f'  Task IV: No control actions for {pair_id} — skipping')
        return []
    logger.info(f'  Task IV: Documenting {len(control_signals)} control actions for {pair_id}')
    endpoint_a, endpoint_b, docs_a, docs_b, domain_knowledge = build_task_iv_v_context(pair_id, netlist_data, component_store, domain_store, task_type='control')
    user_prompt = task_iv_user_prompt(pair_id=pair_id, endpoint_a=endpoint_a, endpoint_b=endpoint_b, control_signals=control_signals, docs_a=docs_a, docs_b=docs_b, domain_knowledge=domain_knowledge)
    result = run_llm_task(system_prompt=TASK_IV_SYSTEM_PROMPT, user_prompt=user_prompt, output_model=TaskIVOutput, model=ANALYSIS_MODEL)
    if result:
        logger.info(f'    → {len(result.control_actions)} control actions documented')
        return result.control_actions
    else:
        logger.warning(f'    → Control action documentation failed for {pair_id}')
        return []

def _get_control_signals(task_ii_output: TaskIIOutput, task_iii_output: TaskIIIOutput) -> list[dict]:
    classifications = {}
    for c in task_iii_output.classifications:
        classifications[c.signal_name] = {'classification': c.classification.value, 'reasoning': c.reasoning}
    control_signals = []
    for signal in task_ii_output.signals:
        cls = classifications.get(signal.signal_name, {})
        if cls.get('classification') == 'control_action':
            control_signals.append({'signal_name': signal.signal_name, 'description': signal.description, 'driven_by': signal.driven_by, 'received_by': signal.received_by, 'reasoning': cls.get('reasoning', '')})
    return control_signals