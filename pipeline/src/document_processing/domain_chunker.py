import logging
import re
from pathlib import Path
from typing import Optional
logger = logging.getLogger(__name__)

def chunk_domain_document(text: str, source_id: str, max_chunk_tokens: int=512, overlap_tokens: int=64) -> list[dict]:
    sections = _split_on_headings(text)
    chunks = []
    chunk_counter = 0
    for section_title, section_text in sections:
        section_text = section_text.strip()
        if not section_text:
            continue
        estimated_tokens = _estimate_tokens(section_text)
        if estimated_tokens <= max_chunk_tokens:
            chunk_counter += 1
            chunks.append(_make_chunk(text=section_text, source_id=source_id, section_title=section_title, chunk_num=chunk_counter))
        else:
            sub_chunks = _split_large_section(section_text, section_title, source_id, max_chunk_tokens, overlap_tokens, start_num=chunk_counter + 1)
            chunk_counter += len(sub_chunks)
            chunks.extend(sub_chunks)
    logger.info(f"Chunked document '{source_id}': {len(sections)} sections → {len(chunks)} chunks")
    return chunks

def chunk_all_documents(corpus_dir: str) -> list[dict]:
    dir_path = Path(corpus_dir)
    if not dir_path.exists():
        logger.warning(f'Corpus directory not found: {corpus_dir}')
        return []
    all_chunks = []
    supported_extensions = {'.md', '.txt', '.rst'}
    for file_path in sorted(dir_path.iterdir()):
        if file_path.suffix.lower() in supported_extensions and file_path.name != 'README.md':
            source_id = file_path.stem
            text = file_path.read_text(encoding='utf-8', errors='replace')
            chunks = chunk_domain_document(text, source_id)
            all_chunks.extend(chunks)
    logger.info(f'Total chunks from corpus: {len(all_chunks)}')
    return all_chunks

def _split_on_headings(text: str) -> list[tuple[str, str]]:
    heading_pattern = re.compile('^(#{2,3})\\s+(.+)$', re.MULTILINE)
    matches = list(heading_pattern.finditer(text))
    if not matches:
        return [('document', text)]
    sections = []
    if matches[0].start() > 0:
        preamble = text[:matches[0].start()].strip()
        if preamble:
            sections.append(('introduction', preamble))
    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((title, content))
    return sections

def _split_large_section(text: str, section_title: str, source_id: str, max_tokens: int, overlap_tokens: int, start_num: int) -> list[dict]:
    paragraphs = re.split('\\n\\s*\\n', text)
    chunks = []
    current_text = ''
    chunk_num = start_num
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        candidate = (current_text + '\n\n' + para).strip() if current_text else para
        if _estimate_tokens(candidate) <= max_tokens:
            current_text = candidate
        elif current_text:
            chunks.append(_make_chunk(text=current_text, source_id=source_id, section_title=section_title, chunk_num=chunk_num))
            chunk_num += 1
            overlap_text = _get_tail_tokens(current_text, overlap_tokens)
            current_text = (overlap_text + '\n\n' + para).strip()
        else:
            sentence_chunks = _split_on_sentences(para, section_title, source_id, max_tokens, overlap_tokens, chunk_num)
            chunks.extend(sentence_chunks)
            chunk_num += len(sentence_chunks)
            current_text = ''
    if current_text:
        chunks.append(_make_chunk(text=current_text, source_id=source_id, section_title=section_title, chunk_num=chunk_num))
    return chunks

def _split_on_sentences(text: str, section_title: str, source_id: str, max_tokens: int, overlap_tokens: int, start_num: int) -> list[dict]:
    sentences = re.split('(?<=[.!?])\\s+', text)
    chunks = []
    current_text = ''
    chunk_num = start_num
    for sentence in sentences:
        candidate = (current_text + ' ' + sentence).strip() if current_text else sentence
        if _estimate_tokens(candidate) <= max_tokens:
            current_text = candidate
        elif current_text:
            chunks.append(_make_chunk(text=current_text, source_id=source_id, section_title=section_title, chunk_num=chunk_num))
            chunk_num += 1
            overlap_text = _get_tail_tokens(current_text, overlap_tokens)
            current_text = (overlap_text + ' ' + sentence).strip()
        else:
            chunks.append(_make_chunk(text=sentence, source_id=source_id, section_title=section_title, chunk_num=chunk_num))
            chunk_num += 1
            current_text = ''
    if current_text:
        chunks.append(_make_chunk(text=current_text, source_id=source_id, section_title=section_title, chunk_num=chunk_num))
    return chunks

def _make_chunk(text: str, source_id: str, section_title: str, chunk_num: int) -> dict:
    return {'chunk_id': f'{source_id}_chunk_{chunk_num:03d}', 'source_id': source_id, 'source_type': 'domain_knowledge', 'section_title': section_title, 'text': text, 'token_count': _estimate_tokens(text)}

def _estimate_tokens(text: str) -> int:
    return len(text) // 4

def _get_tail_tokens(text: str, n_tokens: int) -> str:
    char_count = n_tokens * 4
    if len(text) <= char_count:
        return text
    return '...' + text[-char_count:]