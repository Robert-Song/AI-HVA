import logging
logger = logging.getLogger(__name__)

def compile_notes(pair_id: str, task_ii_output=None, task_iii_output=None, task_iv_actions: list=None, task_v_signals: list=None) -> str:
    notes_parts = []
    if task_iii_output:
        reasonings = []
        for c in task_iii_output.classifications:
            if c.reasoning:
                reasonings.append(f'  - {c.signal_name}: {c.reasoning}')
        if reasonings:
            notes_parts.append('Signal classification reasoning:\n' + '\n'.join(reasonings))
    if task_iv_actions:
        sources = set()
        for ca in task_iv_actions:
            if hasattr(ca, 'source') and ca.source:
                sources.update(ca.source)
        if sources:
            notes_parts.append('Control action sources: ' + ', '.join(sorted(sources)))
    if task_v_signals:
        sources = set()
        for fs in task_v_signals:
            if hasattr(fs, 'source') and fs.source:
                sources.update(fs.source)
        if sources:
            notes_parts.append('Feedback signal sources: ' + ', '.join(sorted(sources)))
    compiled = '\n\n'.join(notes_parts) if notes_parts else ''
    if compiled:
        logger.debug(f'  Task VI: Compiled {len(notes_parts)} note sections for {pair_id}')
    return compiled