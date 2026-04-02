import re

def clean_ocr_text(text: str) -> str:
    symbol_map = {'(cid:2)': 'Ω', '(cid:3)': '°', '(cid:4)': 'μ', '(cid:5)': 'Δ'}
    for old, new in symbol_map.items():
        text = text.replace(old, new)
    text = re.sub(' {3,}', '  ', text)
    text = re.sub('\\n{4,}', '\n\n\n', text)
    boilerplate_markers = ['IMPORTANT NOTICE', 'ORDERING INFORMATION', 'PACKAGE MARKING AND ORDERING', 'Mailing Address: Texas Instruments', 'onsemi reserves the right to make changes', 'MECHANICAL CASE OUTLINE', 'TAPE AND REEL']
    tail_threshold = int(len(text) * 0.6)
    earliest_cut = len(text)
    for marker in boilerplate_markers:
        idx = text.find(marker)
        if idx != -1 and idx >= tail_threshold and (idx < earliest_cut):
            earliest_cut = idx
    if earliest_cut < len(text):
        text = text[:earliest_cut]
    return text.strip()

def is_multi_component_doc(text: str) -> bool:
    if len(text) > 30000:
        indicators = ['Selection Table', 'Cross-Reference', 'Product Family', 'Guide', 'Selector Guide']
        hits = sum((1 for ind in indicators if ind.lower() in text.lower()))
        if hits >= 2:
            return True
    return False