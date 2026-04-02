import logging
from typing import Optional
from src.config import EXTRACTION_MODEL
from src.document_processing.ocr_cleanup import clean_ocr_text, is_multi_component_doc
from src.document_processing.component_store import ComponentSections
from src.llm.client import call_llm, count_tokens
logger = logging.getLogger(__name__)
SECTION_EXTRACTION_SYSTEM_PROMPT = 'You are a technical document parser for hardware datasheets. Your job is to extract and categorize sections from OCR\'d datasheet text that are relevant to system-level safety and control analysis (STPA).\n\nYou will receive raw OCR text from a component datasheet. The text may contain OCR artifacts (e.g., garbled symbols, broken tables, formatting issues). Work through the noise — do not refuse or complain about text quality.\n\nExtract ONLY the sections listed below. If a section is not present in the document, omit it from your output. Do not fabricate content.\n\n## Sections to Extract\n\n1. **identity**\n   What it is. Component name, part number, manufacturer, package type.\n   Look for: title block, header, "General Description", "Features" (first few lines only).\n\n2. **function**\n   What it does and why you\'d use it. Functional description, application context, typical use cases.\n   Look for: "General Description", "Description", "Application", "Overview", "Features" (functional features only, not electrical specs).\n\n3. **pin_config**\n   Pin names, pin numbers, pin functions, and pin behavior descriptions.\n   Look for: "Pin Assignment", "Pin Description", "Pin Configuration", "Pin Functions", "Pin Diagram", any pin-labeled diagrams or tables.\n\n4. **electrical_key**\n   Key electrical parameters needed to understand the component\'s operating behavior. Focus on:\n   - Operating voltage/current ranges\n   - Threshold voltages (e.g., VGS(th) for MOSFETs, logic thresholds for ICs)\n   - On-resistance, forward voltage, or equivalent "how it behaves when active" parameters\n   - Input/output characteristics\n   DO NOT include: full parametric tables, every test condition, temperature coefficients, or noise specs unless they are critical to understanding control behavior.\n\n5. **timing**\n   Switching speed, propagation delay, rise/fall times, turn-on/turn-off delays, gate charge, and any timing constraints.\n   Look for: "Switching Characteristics", "Dynamic Characteristics", "Timing", "Propagation Delay", "Gate Charge".\n\n6. **interface_protocol**\n   Communication protocol details if applicable: I2C addresses, SPI modes, UART baud rates, bus specifications, register maps, command sets.\n   Look for: "Interface", "Communication", "Register Map", "Protocol", "Serial", "I2C", "SPI", "UART", "Bus".\n   NOTE: Many simple components (resistors, MOSFETs, diodes, basic regulators) have no protocol — omit this section entirely for those.\n\n7. **application_circuit**\n   Typical application circuits, reference designs, or recommended usage configurations.\n   Look for: "Typical Application", "Application Circuit", "Application Information", "Reference Design", "Typical Connection".\n\n## Output Format\n\nReturn a JSON object. Each key is a section name from above. Each value is the extracted text for that section, cleaned up for readability but preserving technical accuracy. Preserve exact electrical values, pin names, and technical specifications verbatim. Summarize verbose marketing language.\n\nIf a section has no relevant content in the document, omit the key entirely.\n\nDo not include any text outside the JSON object. No preamble, no explanation, no markdown fences.'
SINGLE_COMPONENT_USER_TEMPLATE = 'Component reference designator: {component_id}\nExpected part number (from netlist): {part_number}\n\n--- BEGIN OCR TEXT ---\n{cleaned_ocr_text}\n--- END OCR TEXT ---'
MULTI_COMPONENT_USER_TEMPLATE = 'Component reference designator: {component_id}\nExpected part number (from netlist): {part_number}\n\nThis document covers a product family or multiple components.\nExtract sections ONLY for the specific part: {part_number}\nIf the exact part is not detailed individually, extract the information\nfor its technology family (e.g., LVC, AUP, AUC) that applies to it.\n\n--- BEGIN OCR TEXT ---\n{cleaned_ocr_text}\n--- END OCR TEXT ---'

def extract_sections(component_id: str, part_number: str, raw_ocr_text: str) -> Optional[ComponentSections]:
    raw_tokens = count_tokens(raw_ocr_text)
    cleaned = clean_ocr_text(raw_ocr_text)
    is_multi = is_multi_component_doc(cleaned)
    if is_multi:
        logger.info(f'{component_id}: Multi-component document detected, using targeted prompt')
        user_prompt = MULTI_COMPONENT_USER_TEMPLATE.format(component_id=component_id, part_number=part_number, cleaned_ocr_text=cleaned)
    else:
        user_prompt = SINGLE_COMPONENT_USER_TEMPLATE.format(component_id=component_id, part_number=part_number, cleaned_ocr_text=cleaned)
    logger.info(f'{component_id}: Extracting sections ({raw_tokens} raw tokens)')
    try:
        response = call_llm(system_prompt=SECTION_EXTRACTION_SYSTEM_PROMPT, user_prompt=user_prompt, model=EXTRACTION_MODEL)
    except Exception as e:
        logger.error(f'{component_id}: LLM call failed: {e}')
        return None
    import json
    try:
        text = response.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        sections = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f'{component_id}: Failed to parse LLM response as JSON: {e}')
        return None
    result = ComponentSections(component_id=component_id, part_number=part_number, identity=sections.get('identity'), function=sections.get('function'), pin_config=sections.get('pin_config'), electrical_key=sections.get('electrical_key'), timing=sections.get('timing'), interface_protocol=sections.get('interface_protocol'), application_circuit=sections.get('application_circuit'))
    filtered_text = result.sections_for_task('signals')
    filtered_tokens = count_tokens(filtered_text) if filtered_text else 0
    logger.info(f'{component_id}: Extraction complete. Raw: {raw_tokens} tokens → Filtered: {filtered_tokens} tokens ({100 * filtered_tokens / max(raw_tokens, 1):.0f}% retained)')
    return result