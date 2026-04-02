import logging
from typing import Optional
from src.analysis.context_builder import build_task_iii_context
from src.analysis.models import TaskIOutput, TaskIIOutput, TaskIIIOutput
from src.analysis.prompts import TASK_III_SYSTEM_PROMPT, task_iii_user_prompt
from src.document_processing.component_store import ComponentSections
from src.document_processing.domain_store import DomainKnowledgeStore
from src.llm.validation import run_llm_task
from src.config import ANALYSIS_MODEL
logger = logging.getLogger(__name__)

def run_task_iii(pair_id: str, netlist_data: dict, task_i_results: dict[str, TaskIOutput], task_ii_output: TaskIIOutput, component_store: dict[str, ComponentSections], domain_store: Optional[DomainKnowledgeStore]=None) -> Optional[TaskIIIOutput]:
    logger.info(f'  Task III: Control/feedback classification for {pair_id}')
    task_ii_dict = task_ii_output.model_dump() if task_ii_output else {}
    endpoint_a, endpoint_b, task_i_a, task_i_b, docs_a, docs_b, domain_knowledge = build_task_iii_context(pair_id, netlist_data, task_i_results, task_ii_dict, component_store, domain_store)
    user_prompt = task_iii_user_prompt(pair_id=pair_id, endpoint_a=endpoint_a, endpoint_b=endpoint_b, task_i_a=task_i_a, task_i_b=task_i_b, task_ii_output=task_ii_dict, docs_a=docs_a, docs_b=docs_b, domain_knowledge=domain_knowledge)
    result = run_llm_task(system_prompt=TASK_III_SYSTEM_PROMPT, user_prompt=user_prompt, output_model=TaskIIIOutput, model=ANALYSIS_MODEL)
    if result:
        ctrl_count = sum((1 for c in result.classifications if c.classification.value == 'control_action'))
        fb_count = sum((1 for c in result.classifications if c.classification.value == 'feedback_signal'))
        logger.info(f'    → {ctrl_count} control actions, {fb_count} feedback signals, {len(result.classifications) - ctrl_count - fb_count} other')
    else:
        logger.warning(f'    → Classification failed for {pair_id}')
    return result