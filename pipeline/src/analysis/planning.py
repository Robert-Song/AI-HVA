import logging
from typing import Optional
from src.analysis.context_builder import build_planning_context
from src.analysis.models import PlanningOutput
from src.analysis.prompts import PLANNING_SYSTEM_PROMPT, planning_user_prompt
from src.document_processing.domain_store import DomainKnowledgeStore
from src.llm.validation import run_llm_task
from src.config import ANALYSIS_MODEL
logger = logging.getLogger(__name__)

def run_planning_pass(system_name: str, netlist_file: str, netlist_data: dict, domain_store: Optional[DomainKnowledgeStore]=None) -> Optional[PlanningOutput]:
    logger.info('=' * 60)
    logger.info('STEP 0: Planning Pass')
    logger.info('=' * 60)
    domain_knowledge = build_planning_context(netlist_data, domain_store)
    user_prompt = planning_user_prompt(system_name=system_name, netlist_file=netlist_file, components=netlist_data['components'], connection_pairs=netlist_data['connection_pairs'], domain_knowledge=domain_knowledge)
    result = run_llm_task(system_prompt=PLANNING_SYSTEM_PROMPT, user_prompt=user_prompt, output_model=PlanningOutput, model=ANALYSIS_MODEL)
    if result:
        logger.info(f'Planning complete: {len(result.modeled_components)} modeled, {len(result.excluded_components)} excluded, {len(result.connection_pairs_to_analyze)} pairs to analyze')
    else:
        logger.error('Planning pass failed')
    return result