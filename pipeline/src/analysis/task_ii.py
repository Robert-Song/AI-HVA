import logging
from typing import Optional
from src.analysis.context_builder import build_task_ii_context
from src.analysis.models import TaskIOutput, TaskIIOutput
from src.analysis.prompts import TASK_II_SYSTEM_PROMPT, task_ii_user_prompt
from src.document_processing.component_store import ComponentSections
from src.document_processing.domain_store import DomainKnowledgeStore
from src.llm.validation import run_llm_task
from src.config import ANALYSIS_MODEL
logger = logging.getLogger(__name__)

def run_task_ii(pair_id: str, netlist_data: dict, task_i_results: dict[str, TaskIOutput], component_store: dict[str, ComponentSections], domain_store: Optional[DomainKnowledgeStore]=None) -> Optional[TaskIIOutput]:
    pair = netlist_data['connection_pairs'][pair_id]
    logger.info(f'  Task II: Signal identification for {pair_id}')
    endpoint_a, endpoint_b, task_i_a, task_i_b, docs_a, docs_b, domain_knowledge = build_task_ii_context(pair_id, netlist_data, task_i_results, component_store, domain_store)
    user_prompt = task_ii_user_prompt(pair_id=pair_id, endpoint_a=endpoint_a, endpoint_b=endpoint_b, net_names=pair['net_names'], task_i_a=task_i_a, task_i_b=task_i_b, docs_a=docs_a, docs_b=docs_b, domain_knowledge=domain_knowledge)
    result = run_llm_task(system_prompt=TASK_II_SYSTEM_PROMPT, user_prompt=user_prompt, output_model=TaskIIOutput, model=ANALYSIS_MODEL)
    if result:
        logger.info(f'    → Interface: {result.physical_interface} | {len(result.signals)} signals identified')
    else:
        logger.warning(f'    → Signal identification failed for {pair_id}')
    return result