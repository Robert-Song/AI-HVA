import logging
from typing import Optional
from src.analysis.context_builder import build_task_i_context
from src.analysis.models import TaskIOutput
from src.analysis.prompts import TASK_I_SYSTEM_PROMPT, task_i_user_prompt
from src.document_processing.component_store import ComponentSections
from src.document_processing.domain_store import DomainKnowledgeStore
from src.llm.validation import run_llm_task
from src.config import ANALYSIS_MODEL
logger = logging.getLogger(__name__)

def run_task_i(modeled_components: list[str], netlist_data: dict, component_store: dict[str, ComponentSections], domain_store: Optional[DomainKnowledgeStore]=None) -> dict[str, TaskIOutput]:
    logger.info('=' * 60)
    logger.info(f'TASK I: Component Classification ({len(modeled_components)} components)')
    logger.info('=' * 60)
    results: dict[str, TaskIOutput] = {}
    for i, comp_id in enumerate(modeled_components):
        comp = netlist_data['components'].get(comp_id, {})
        part_number = comp.get('part_number', comp.get('value', ''))
        logger.info(f'  [{i + 1}/{len(modeled_components)}] Classifying {comp_id} ({part_number})')
        connections_text, component_docs, domain_knowledge = build_task_i_context(comp_id, netlist_data, component_store, domain_store)
        user_prompt = task_i_user_prompt(component_id=comp_id, part_number=part_number, connections_text=connections_text, component_docs=component_docs, domain_knowledge=domain_knowledge)
        result = run_llm_task(system_prompt=TASK_I_SYSTEM_PROMPT, user_prompt=user_prompt, output_model=TaskIOutput, model=ANALYSIS_MODEL)
        if result:
            results[comp_id] = result
            logger.info(f'    → {result.component_class.value} | safety_critical={result.safety_critical}')
        else:
            logger.warning(f'    → Classification failed for {comp_id}')
    logger.info(f'Task I complete: {len(results)}/{len(modeled_components)} classified')
    return results