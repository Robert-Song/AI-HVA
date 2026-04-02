import logging
from typing import Optional
from openai import OpenAI
from src.config import OPENAI_API_KEY, LLM_BASE_URL
logger = logging.getLogger(__name__)
_client: Optional[OpenAI] = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY, base_url=LLM_BASE_URL)
    return _client

def call_llm(system_prompt: str, user_prompt: str, model: str, temperature: float=0.0, max_tokens: int=4096) -> str:
    client = _get_client()
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