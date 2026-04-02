import argparse
import json
import logging
import sys
from pathlib import Path
from src.config import COMPONENT_STORE_PATH, DATASHEET_DIR, DOMAIN_CORPUS_DIR, DOMAIN_KB_PATH, OUTPUT_DIR
logger = logging.getLogger('stpa_pipeline')

def setup_logging(verbose: bool=False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')

def run_pipeline(netlist_path: str, system_name: str, skip_phase_2a: bool=False, skip_phase_2b: bool=False) -> dict:
    from src.ingestion.netlist_loader import load_netlist
    from src.document_processing.component_store import build_component_store, save_store, load_store
    from src.document_processing.domain_store import DomainKnowledgeStore
    from src.analysis.planning import run_planning_pass
    from src.analysis.task_i import run_task_i
    from src.analysis.task_ii import run_task_ii
    from src.analysis.task_iii import run_task_iii
    from src.analysis.task_iv import run_task_iv
    from src.analysis.task_v import run_task_v
    from src.analysis.task_vi import compile_notes
    from src.assembly.stpa_assembler import assemble_stpa_json, save_stpa_json
    logger.info('=' * 60)
    logger.info('PHASE 1: Loading netlist data')
    logger.info('=' * 60)
    netlist_data = load_netlist(netlist_path)
    logger.info('=' * 60)
    logger.info('PHASE 2A: Component Document Store')
    logger.info('=' * 60)
    if skip_phase_2a and Path(COMPONENT_STORE_PATH).exists():
        logger.info(f'Loading existing component store from {COMPONENT_STORE_PATH}')
        component_store = load_store(COMPONENT_STORE_PATH)
    else:
        component_store = build_component_store(netlist_data['components'], DATASHEET_DIR)
        save_store(component_store, COMPONENT_STORE_PATH)
    logger.info('=' * 60)
    logger.info('PHASE 2B: Domain Knowledge Store')
    logger.info('=' * 60)
    domain_store = DomainKnowledgeStore()
    if not skip_phase_2b:
        corpus_dir = Path(DOMAIN_CORPUS_DIR)
        if corpus_dir.exists() and any(corpus_dir.glob('*.md')) or any(corpus_dir.glob('*.txt')):
            n_chunks = domain_store.build_index(DOMAIN_CORPUS_DIR)
            logger.info(f'Domain knowledge index built: {n_chunks} chunks')
        else:
            logger.warning(f'No domain documents found in {DOMAIN_CORPUS_DIR}. Proceeding without domain knowledge RAG.')
            domain_store = None
    elif Path(DOMAIN_KB_PATH).exists():
        logger.info('Using existing domain knowledge index')
    else:
        logger.warning('No domain knowledge index found — proceeding without RAG')
        domain_store = None
    planning_output = run_planning_pass(system_name=system_name, netlist_file=netlist_path, netlist_data=netlist_data, domain_store=domain_store)
    if planning_output is None:
        logger.error('Planning pass failed — cannot proceed')
        sys.exit(1)
    task_i_results = run_task_i(modeled_components=planning_output.modeled_components, netlist_data=netlist_data, component_store=component_store, domain_store=domain_store)
    logger.info('=' * 60)
    logger.info(f'TASKS II–V: Processing {len(planning_output.connection_pairs_to_analyze)} connection pairs')
    logger.info('=' * 60)
    task_ii_results = {}
    task_iii_results = {}
    task_iv_results = {}
    task_v_results = {}
    notes = {}
    for i, pair_id in enumerate(planning_output.connection_pairs_to_analyze):
        logger.info(f"\n{'─' * 40}\nConnection pair [{i + 1}/{len(planning_output.connection_pairs_to_analyze)}]: {pair_id}\n{'─' * 40}")
        task_ii = run_task_ii(pair_id=pair_id, netlist_data=netlist_data, task_i_results=task_i_results, component_store=component_store, domain_store=domain_store)
        if task_ii is None:
            logger.warning(f'Skipping remaining tasks for {pair_id} (Task II failed)')
            continue
        task_ii_results[pair_id] = task_ii
        task_iii = run_task_iii(pair_id=pair_id, netlist_data=netlist_data, task_i_results=task_i_results, task_ii_output=task_ii, component_store=component_store, domain_store=domain_store)
        if task_iii is None:
            logger.warning(f'Skipping Tasks IV/V for {pair_id} (Task III failed)')
            continue
        task_iii_results[pair_id] = task_iii
        control_actions = run_task_iv(pair_id=pair_id, netlist_data=netlist_data, task_ii_output=task_ii, task_iii_output=task_iii, component_store=component_store, domain_store=domain_store)
        task_iv_results[pair_id] = control_actions
        feedback_signals = run_task_v(pair_id=pair_id, netlist_data=netlist_data, task_ii_output=task_ii, task_iii_output=task_iii, component_store=component_store, domain_store=domain_store)
        task_v_results[pair_id] = feedback_signals
        pair_notes = compile_notes(pair_id=pair_id, task_ii_output=task_ii, task_iii_output=task_iii, task_iv_actions=control_actions, task_v_signals=feedback_signals)
        if pair_notes:
            notes[pair_id] = pair_notes
    stpa = assemble_stpa_json(system_name=system_name, netlist_source=netlist_path, netlist_data=netlist_data, planning_output=planning_output, task_i_results=task_i_results, task_ii_results=task_ii_results, task_iii_results=task_iii_results, task_iv_results=task_iv_results, task_v_results=task_v_results, notes=notes)
    output_path = save_stpa_json(stpa, system_name)
    logger.info(f"\n{'=' * 60}")
    logger.info(f'PIPELINE COMPLETE')
    logger.info(f'Output: {output_path}')
    logger.info(f"{'=' * 60}")
    return stpa

def main():
    parser = argparse.ArgumentParser(description='STPA AI Pipeline — Hardware Vulnerability Analysis')
    parser.add_argument('--netlist', '-n', required=True, help='Path to netlist JSON file (Phase 1 output)')
    parser.add_argument('--system', '-s', required=True, help='System name for the analysis')
    parser.add_argument('--skip-2a', action='store_true', help='Skip Phase 2A rebuild — use existing component_store.json')
    parser.add_argument('--skip-2b', action='store_true', help='Skip Phase 2B rebuild — use existing domain knowledge index')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    setup_logging(args.verbose)
    run_pipeline(netlist_path=args.netlist, system_name=args.system, skip_phase_2a=args.skip_2a, skip_phase_2b=args.skip_2b)
if __name__ == '__main__':
    main()