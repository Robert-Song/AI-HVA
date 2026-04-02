"""
STPA AI Pipeline — Main Orchestrator

CLI entrypoint that runs the full pipeline:
  Phase 1 (load) → Phase 2A (CAG) → Phase 2B (RAG) →
  Phase 3 (LLM analysis) → Phase 4 (assembly)

Usage:
    python -m src.main --netlist path/to/netlist.json --system "System Name"
    python -m src.main -n netlist.net -s "My System" -p   # production mode (progress bar)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from src.config import (
    COMPONENT_STORE_PATH,
    DATASHEET_DIR,
    DOMAIN_CORPUS_DIR,
    DOMAIN_KB_PATH,
    OUTPUT_DIR,
)

logger = logging.getLogger("stpa_pipeline")

# PROGRESS BAR

class ProgressBar:
    """Simple CLI progress bar for production mode."""

    def __init__(self, total: int, bar_width: int = 40):
        self.total = max(total, 1)
        self.current = 0
        self.bar_width = bar_width
        self._last_percent = -1

    def update(self, step_name: str = "") -> None:
        """Advance the progress bar by one step."""
        self.current += 1
        percent = int(100 * self.current / self.total)

        # Only redraw if percent changed (avoids flicker)
        if percent == self._last_percent:
            return
        self._last_percent = percent

        filled = int(self.bar_width * self.current / self.total)
        bar = "█" * filled + "░" * (self.bar_width - filled)
        step_display = f"  {step_name}" if step_name else ""

        sys.stdout.write(f"\r  [{bar}] {percent:3d}%{step_display:<40}")
        sys.stdout.flush()

        if self.current >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()


class NoOpProgress:
    """Dummy progress bar that does nothing (for verbose/default mode)."""
    def update(self, step_name: str = "") -> None:
        pass


# LOGGING SETUP

def setup_logging(verbose: bool = False, production: bool = False) -> None:
    """Configure logging for the pipeline."""
    if production:
        # Production mode: suppress all logging
        logging.basicConfig(level=logging.CRITICAL + 1)
    elif verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )


# PIPELINE

def run_pipeline(
    netlist_path: str,
    system_name: str,
    skip_phase_2a: bool = False,
    skip_phase_2b: bool = False,
    production: bool = False,
) -> dict:
    """
    Execute the full STPA analysis pipeline.

    Args:
        netlist_path: Path to the netlist file (.net or .json).
        system_name: Name of the system being analyzed.
        skip_phase_2a: If True, load existing component store instead of rebuilding.
        skip_phase_2b: If True, skip domain knowledge index rebuild.
        production: If True, show only start/end messages and a progress bar.

    Returns:
        The assembled STPA JSON dict.
    """
    # Lazy imports to avoid loading everything upfront
    from src.ingestion.netlist_loader import load_netlist
    from src.document_processing.component_store import (
        build_component_store, save_store, load_store,
    )
    from src.document_processing.domain_store import DomainKnowledgeStore
    from src.analysis.planning import run_planning_pass
    from src.analysis.task_i import run_task_i
    from src.analysis.task_ii import run_task_ii
    from src.analysis.task_iii import run_task_iii
    from src.analysis.task_iv import run_task_iv
    from src.analysis.task_v import run_task_v
    from src.analysis.task_vi import compile_notes
    from src.assembly.stpa_assembler import assemble_stpa_json, save_stpa_json

    if production:
        print(f"STPA Pipeline starting: \"{system_name}\"")
        print(f"  Netlist: {netlist_path}")

    # --- Phase 1: Load netlist ---
    logger.info("=" * 60)
    logger.info("PHASE 1: Loading netlist data")
    logger.info("=" * 60)

    netlist_data = load_netlist(netlist_path)

    # --- Phase 2A: Component document store (CAG) ---
    logger.info("=" * 60)
    logger.info("PHASE 2A: Component Document Store")
    logger.info("=" * 60)

    if skip_phase_2a and Path(COMPONENT_STORE_PATH).exists():
        logger.info(f"Loading existing component store from {COMPONENT_STORE_PATH}")
        component_store = load_store(COMPONENT_STORE_PATH)
    else:
        component_store = build_component_store(
            netlist_data["components"], DATASHEET_DIR
        )
        save_store(component_store, COMPONENT_STORE_PATH)

    # --- Phase 2B: Domain knowledge store (RAG) ---
    logger.info("=" * 60)
    logger.info("PHASE 2B: Domain Knowledge Store")
    logger.info("=" * 60)

    domain_store = DomainKnowledgeStore()

    if not skip_phase_2b:
        corpus_dir = Path(DOMAIN_CORPUS_DIR)
        if corpus_dir.exists() and any(corpus_dir.glob("*.md")) or any(corpus_dir.glob("*.txt")):
            n_chunks = domain_store.build_index(DOMAIN_CORPUS_DIR)
            logger.info(f"Domain knowledge index built: {n_chunks} chunks")
        else:
            logger.warning(
                f"No domain documents found in {DOMAIN_CORPUS_DIR}. "
                "Proceeding without domain knowledge RAG."
            )
            domain_store = None
    else:
        # Check if index already exists
        if Path(DOMAIN_KB_PATH).exists():
            logger.info("Using existing domain knowledge index")
        else:
            logger.warning("No domain knowledge index found — proceeding without RAG")
            domain_store = None

    # --- Phase 3: LLM Analysis ---

    # Step 0: Planning pass
    planning_output = run_planning_pass(
        system_name=system_name,
        netlist_file=netlist_path,
        netlist_data=netlist_data,
        domain_store=domain_store,
    )

    if planning_output is None:
        logger.error("Planning pass failed — cannot proceed")
        if production:
            print("ERROR: Planning pass failed. Run with -v for details.")
        sys.exit(1)

    # --- Calculate total steps for progress bar ---
    # Steps: planning(done) + task_I(N components) + per-pair(tasks II-V = 4 each) + assembly
    n_components = len(planning_output.modeled_components)
    n_pairs = len(planning_output.connection_pairs_to_analyze)
    # Already done: Phase 1 + 2A + 2B + planning = 4
    # Remaining: Task I (n_components) + Tasks II-V per pair (4 * n_pairs) + assembly (1)
    total_steps = 4 + n_components + (4 * n_pairs) + 1
    progress = ProgressBar(total_steps) if production else NoOpProgress()

    # Mark phases 1, 2A, 2B, planning as done
    progress.update("Phase 1: Netlist loaded")
    progress.update("Phase 2A: Datasheets processed")
    progress.update("Phase 2B: Domain knowledge indexed")
    progress.update("Step 0: Planning complete")

    # Task I: Component classification (ALL must complete first)
    task_i_results = run_task_i(
        modeled_components=planning_output.modeled_components,
        netlist_data=netlist_data,
        component_store=component_store,
        domain_store=domain_store,
    )

    # Update progress for each classified component
    for comp_id in planning_output.modeled_components:
        progress.update(f"Task I: {comp_id}")

    # Tasks II–V: Per connection pair
    logger.info("=" * 60)
    logger.info(
        f"TASKS II–V: Processing {len(planning_output.connection_pairs_to_analyze)} "
        "connection pairs"
    )
    logger.info("=" * 60)

    task_ii_results = {}
    task_iii_results = {}
    task_iv_results = {}
    task_v_results = {}
    notes = {}

    for i, pair_id in enumerate(planning_output.connection_pairs_to_analyze):
        logger.info(
            f"\n{'-' * 40}\n"
            f"Connection pair [{i+1}/{len(planning_output.connection_pairs_to_analyze)}]: "
            f"{pair_id}\n"
            f"{'-' * 40}"
        )

        # Task II: Signal identification
        task_ii = run_task_ii(
            pair_id=pair_id,
            netlist_data=netlist_data,
            task_i_results=task_i_results,
            component_store=component_store,
            domain_store=domain_store,
        )
        progress.update(f"Task II: {pair_id}")

        if task_ii is None:
            logger.warning(f"Skipping remaining tasks for {pair_id} (Task II failed)")
            # Still count remaining tasks for this pair
            progress.update(f"Task III: {pair_id} (skipped)")
            progress.update(f"Task IV: {pair_id} (skipped)")
            progress.update(f"Task V: {pair_id} (skipped)")
            continue

        task_ii_results[pair_id] = task_ii

        # Task III: Control vs feedback classification
        task_iii = run_task_iii(
            pair_id=pair_id,
            netlist_data=netlist_data,
            task_i_results=task_i_results,
            task_ii_output=task_ii,
            component_store=component_store,
            domain_store=domain_store,
        )
        progress.update(f"Task III: {pair_id}")

        if task_iii is None:
            logger.warning(f"Skipping Tasks IV/V for {pair_id} (Task III failed)")
            progress.update(f"Task IV: {pair_id} (skipped)")
            progress.update(f"Task V: {pair_id} (skipped)")
            continue

        task_iii_results[pair_id] = task_iii

        # Task IV: Control action details
        control_actions = run_task_iv(
            pair_id=pair_id,
            netlist_data=netlist_data,
            task_ii_output=task_ii,
            task_iii_output=task_iii,
            component_store=component_store,
            domain_store=domain_store,
        )
        task_iv_results[pair_id] = control_actions
        progress.update(f"Task IV: {pair_id}")

        # Task V: Feedback signal details
        feedback_signals = run_task_v(
            pair_id=pair_id,
            netlist_data=netlist_data,
            task_ii_output=task_ii,
            task_iii_output=task_iii,
            component_store=component_store,
            domain_store=domain_store,
        )
        task_v_results[pair_id] = feedback_signals
        progress.update(f"Task V: {pair_id}")

        # Task VI: Notes compilation (no LLM call, not counted in progress)
        pair_notes = compile_notes(
            pair_id=pair_id,
            task_ii_output=task_ii,
            task_iii_output=task_iii,
            task_iv_actions=control_actions,
            task_v_signals=feedback_signals,
        )
        if pair_notes:
            notes[pair_id] = pair_notes

    # --- Phase 4: Assembly ---
    stpa = assemble_stpa_json(
        system_name=system_name,
        netlist_source=netlist_path,
        netlist_data=netlist_data,
        planning_output=planning_output,
        task_i_results=task_i_results,
        task_ii_results=task_ii_results,
        task_iii_results=task_iii_results,
        task_iv_results=task_iv_results,
        task_v_results=task_v_results,
        notes=notes,
    )

    # Save output
    output_path = save_stpa_json(stpa, system_name)
    progress.update("Assembly complete")

    logger.info(f"\n{'=' * 60}")
    logger.info(f"PIPELINE COMPLETE")
    logger.info(f"Output: {output_path}")
    logger.info(f"{'=' * 60}")

    if production:
        print(f"Pipeline complete. Output: {output_path}")

    return stpa


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="STPA AI Pipeline — Hardware Vulnerability Analysis"
    )
    parser.add_argument(
        "--netlist", "-n",
        required=True,
        help="Path to netlist file (.net or .json)",
    )
    parser.add_argument(
        "--system", "-s",
        required=True,
        help="System name for the analysis",
    )
    parser.add_argument(
        "--skip-2a",
        action="store_true",
        help="Skip Phase 2A rebuild — use existing component_store.json",
    )
    parser.add_argument(
        "--skip-2b",
        action="store_true",
        help="Skip Phase 2B rebuild — use existing domain knowledge index",
    )
    parser.add_argument(
        "--production", "-p",
        action="store_true",
        help="Production mode: suppress logs, show progress bar only",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()
    setup_logging(verbose=args.verbose, production=args.production)

    run_pipeline(
        netlist_path=args.netlist,
        system_name=args.system,
        skip_phase_2a=args.skip_2a,
        skip_phase_2b=args.skip_2b,
        production=args.production,
    )


if __name__ == "__main__":
    main()
