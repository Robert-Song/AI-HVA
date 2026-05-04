import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')

EXTRACTION_API_KEY = os.getenv('EXTRACTION_API_KEY', OPENAI_API_KEY)
EXTRACTION_BASE_URL = os.getenv('EXTRACTION_BASE_URL', LLM_BASE_URL)
EXTRACTION_MODEL = os.getenv('EXTRACTION_MODEL', 'gpt-4o-mini')

ANALYSIS_API_KEY = os.getenv('ANALYSIS_API_KEY', OPENAI_API_KEY)
ANALYSIS_BASE_URL = os.getenv('ANALYSIS_BASE_URL', LLM_BASE_URL)
ANALYSIS_MODEL = os.getenv('ANALYSIS_MODEL', 'gpt-4o')

EMBEDDING_API_KEY = os.getenv('EMBEDDING_API_KEY', OPENAI_API_KEY)
EMBEDDING_BASE_URL = os.getenv('EMBEDDING_BASE_URL', LLM_BASE_URL)

EMBEDDING_BACKEND = os.getenv('EMBEDDING_BACKEND', 'minilm')
EMBEDDING_MODELS = {
    'minilm': {'name': 'all-MiniLM-L6-v2', 'dimension': 384, 'instruction_prefix': False, 'type': 'local'}, 
    'qwen3': {'name': 'Qwen/Qwen3-Embedding-0.6B', 'dimension': 1024, 'instruction_prefix': True, 'type': 'local'},
    'server': {'name': os.getenv('EMBEDDING_MODEL_NAME', 'qwen3-embedding:8b-q8_0'), 'dimension': 1024, 'instruction_prefix': False, 'type': 'server'}
}

def get_embedding_config() -> dict:
    return EMBEDDING_MODELS.get(EMBEDDING_BACKEND, EMBEDDING_MODELS['minilm'])
DOMAIN_KB_PATH = os.getenv('DOMAIN_KB_PATH', str(PROJECT_ROOT / 'domain_knowledge_db'))
DOMAIN_KB_COLLECTION = 'domain_knowledge'
RETRIEVAL_TOP_K = int(os.getenv('RETRIEVAL_TOP_K', '5'))
COMPONENT_STORE_PATH = os.getenv('COMPONENT_STORE_PATH', str(PROJECT_ROOT / 'component_store.json'))
DATASHEET_DIR = os.getenv('DATASHEET_DIR', str(PROJECT_ROOT / 'datasheets'))
DOMAIN_CORPUS_DIR = os.getenv('DOMAIN_CORPUS_DIR', str(PROJECT_ROOT / 'domain_docs'))
OUTPUT_DIR = os.getenv('OUTPUT_DIR', str(PROJECT_ROOT / 'output'))
MAX_LLM_RETRIES = int(os.getenv('MAX_LLM_RETRIES', '2'))