import json
import logging
from typing import Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from src.config import MAX_LLM_RETRIES, ANALYSIS_MODEL
from src.llm.client import call_llm
logger = logging.getLogger(__name__)
T = TypeVar('T', bound=BaseModel)

def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith('```'):
        first_newline = text.find('\n')
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.rstrip().endswith('```'):
            text = text.rstrip()[:-3]
    return text.strip()

def validate_llm_output(response_text: str, model_class: Type[T]) -> T:
    text = _strip_markdown_fences(response_text)
    data = json.loads(text)
    return model_class.model_validate(data)

def run_llm_task(system_prompt: str, user_prompt: str, output_model: Type[T], model: str='', temperature: float=0.0, max_tokens: int=4096) -> Optional[T]:
    if not model:
        model = ANALYSIS_MODEL
    current_user_prompt = user_prompt
    for attempt in range(MAX_LLM_RETRIES + 1):
        try:
            response = call_llm(system_prompt=system_prompt, user_prompt=current_user_prompt, model=model, temperature=temperature, max_tokens=max_tokens)
            result = validate_llm_output(response, output_model)
            logger.info(f'LLM task validated on attempt {attempt + 1}')
            return result
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f'LLM task validation failed (attempt {attempt + 1}/{MAX_LLM_RETRIES + 1}): {e}')
            if attempt < MAX_LLM_RETRIES:
                current_user_prompt = user_prompt + f'\n\n[RETRY] Your previous response failed validation:\n{e}\n' + 'Please fix and return valid JSON matching the schema.'
            else:
                logger.error(f'LLM task failed after {MAX_LLM_RETRIES + 1} attempts: {e}')
                return None
    return None