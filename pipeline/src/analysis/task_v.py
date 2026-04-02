import logging
from typing import Optional
from src.analysis.context_builder import build_task_iv_v_context
from src.analysis.models import TaskIIOutput, TaskIIIOutput, TaskVOutput, FeedbackSignal
from src.analysis.prompts import TASK_V_SYSTEM_PROMPT, task_v_user_prompt
from src.document_processing.component_store import ComponentSections
from src.document_processing.domain_store import DomainKnowledgeStore
from src.llm.validation import run_llm_task
from src.config import ANALYSIS_MODEL
logger = logging.getLogger(__name__)

def run_task_v(pair_id: str, netlist_data: dict, task_ii_output: TaskIIOutput, task_iii_output: TaskIIIOutput, component_store: dict[str, ComponentSections], domain_store: Optional[DomainKnowledgeStore]=None) -> list[FeedbackSignal]:
    feedback_signals = _get_feedback_signals(task_ii_output, task_iii_output)
    if not feedback_signals:
        logger.info(f'  Task V: No feedback signals for {pair_id} — skipping')
        return []
    logger.info(f'  Task V: Documenting {len(feedback_signals)} feedback signals for {pair_id}')
    endpoint_a, endpoint_b, docs_a, docs_b, domain_knowledge = build_task_iv_v_context(pair_id, netlist_data, component_store, domain_store, task_type='feedback')
    user_prompt = task_v_user_prompt(pair_id=pair_id, endpoint_a=endpoint_a, endpoint_b=endpoint_b, feedback_signals=feedback_signals, docs_a=docs_a, docs_b=docs_b, domain_knowledge=domain_knowledge)
    result = run_llm_task(system_prompt=TASK_V_SYSTEM_PROMPT, user_prompt=user_prompt, output_model=TaskVOutput, model=ANALYSIS_MODEL)
    if result:
        logger.info(f'    → {len(result.feedback_signals)} feedback signals documented')
        return result.feedback_signals
    else:
        logger.warning(f'    → Feedback signal documentation failed for {pair_id}')
        return []

def _get_feedback_signals(task_ii_output: TaskIIOutput, task_iii_output: TaskIIIOutput) -> list[dict]:
    classifications = {}
    for c in task_iii_output.classifications:
        classifications[c.signal_name] = {'classification': c.classification.value, 'reasoning': c.reasoning}
    feedback_sigs = []
    for signal in task_ii_output.signals:
        cls = classifications.get(signal.signal_name, {})
        if cls.get('classification') == 'feedback_signal':
            feedback_sigs.append({'signal_name': signal.signal_name, 'description': signal.description, 'driven_by': signal.driven_by, 'received_by': signal.received_by, 'reasoning': cls.get('reasoning', '')})
    return feedback_sigs