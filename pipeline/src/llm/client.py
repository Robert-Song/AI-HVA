import logging
from typing import Optional
from openai import OpenAI
from src.config import (
    OPENAI_API_KEY, LLM_BASE_URL,
    EXTRACTION_API_KEY, EXTRACTION_BASE_URL, EXTRACTION_MODEL,
    ANALYSIS_API_KEY, ANALYSIS_BASE_URL, ANALYSIS_MODEL,
    EMBEDDING_API_KEY, EMBEDDING_BASE_URL
)
logger = logging.getLogger(__name__)

_clients = {}

def _get_client(model: str = "") -> OpenAI:
    if model == EXTRACTION_MODEL:
        api_key = EXTRACTION_API_KEY
        base_url = EXTRACTION_BASE_URL
    elif model == ANALYSIS_MODEL:
        api_key = ANALYSIS_API_KEY
        base_url = ANALYSIS_BASE_URL
    elif model == "embedding":
        api_key = EMBEDDING_API_KEY
        base_url = EMBEDDING_BASE_URL
    else:
        api_key = OPENAI_API_KEY
        base_url = LLM_BASE_URL
        
    key = f"{base_url}_{api_key}"
    if key not in _clients:
        _clients[key] = OpenAI(api_key=api_key, base_url=base_url)
    return _clients[key]

def call_llm(system_prompt: str, user_prompt: str, model: str, temperature: float=0.0, max_tokens: int=4096) -> str:
    client = _get_client(model)
    logger.info(f'LLM call: model={model}, system_prompt_len={len(system_prompt)}, user_prompt_len={len(user_prompt)}')
    response = client.chat.completions.create(model=model, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], temperature=temperature, max_tokens=max_tokens)
    result = response.choices[0].message.content
    logger.info(f'LLM response: {len(result)} chars')
    return result

def count_tokens(text: str, model: str='gpt-4o') -> int:
    try:
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding('cl100k_base')
        return len(encoding.encode(text))
    except ImportError:
        return len(text) // 4