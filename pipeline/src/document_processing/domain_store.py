import logging
from pathlib import Path
from typing import Optional
import chromadb
from src.config import DOMAIN_KB_PATH, DOMAIN_KB_COLLECTION, RETRIEVAL_TOP_K, EMBEDDING_BACKEND, get_embedding_config
from src.document_processing.domain_chunker import chunk_all_documents
logger = logging.getLogger(__name__)

class DomainKnowledgeStore:

    def __init__(self, db_path: Optional[str]=None):
        self.db_path = db_path or DOMAIN_KB_PATH
        self.embedding_config = get_embedding_config()
        self._client = None
        self._collection = None
        self._embedding_model = None

    @property
    def client(self) -> chromadb.ClientAPI:
        if self._client is None:
            Path(self.db_path).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.db_path)
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            if EMBEDDING_BACKEND == 'minilm':
                self._collection = self.client.get_or_create_collection(name=DOMAIN_KB_COLLECTION, metadata={'hnsw:space': 'cosine'})
            else:
                self._collection = self.client.get_or_create_collection(name=DOMAIN_KB_COLLECTION, metadata={'hnsw:space': 'cosine'})
        return self._collection

    def _get_embedding_model(self):
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer
            model_name = self.embedding_config['name']
            logger.info(f'Loading embedding model: {model_name}')
            self._embedding_model = SentenceTransformer(model_name)
        return self._embedding_model

    def _embed_texts(self, texts: list[str], is_query: bool=False) -> list[list[float]]:
        model = self._get_embedding_model()
        if self.embedding_config.get('instruction_prefix'):
            if is_query:
                texts = [f'Instruct: Retrieve documents about hardware safety analysis\nQuery: {t}' for t in texts]
            else:
                texts = [f'Instruct: Represent this document for retrieval\nDocument: {t}' for t in texts]
        embeddings = model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

    def build_index(self, corpus_dir: str) -> int:
        chunks = chunk_all_documents(corpus_dir)
        if not chunks:
            logger.warning('No chunks to index — corpus may be empty')
            return 0
        logger.info(f'Indexing {len(chunks)} chunks into domain knowledge store')
        texts = [c['text'] for c in chunks]
        embeddings = self._embed_texts(texts, is_query=False)
        self.collection.add(ids=[c['chunk_id'] for c in chunks], documents=texts, metadatas=[{'source_id': c['source_id'], 'section_title': c['section_title'], 'source_type': c['source_type']} for c in chunks], embeddings=embeddings)
        logger.info(f"Indexed {len(chunks)} chunks into '{DOMAIN_KB_COLLECTION}'")
        return len(chunks)

    def query(self, query_text: str, n_results: Optional[int]=None, where: Optional[dict]=None) -> list[dict]:
        n = n_results or RETRIEVAL_TOP_K
        if self.collection.count() == 0:
            logger.warning('Domain knowledge store is empty — no results returned')
            return []
        query_embedding = self._embed_texts([query_text], is_query=True)[0]
        kwargs = {'query_embeddings': [query_embedding], 'n_results': min(n, self.collection.count())}
        if where:
            kwargs['where'] = where
        results = self.collection.query(**kwargs)
        formatted = []
        if results['ids'] and results['ids'][0]:
            for i, chunk_id in enumerate(results['ids'][0]):
                formatted.append({'chunk_id': chunk_id, 'text': results['documents'][0][i], 'source_id': results['metadatas'][0][i].get('source_id', ''), 'section_title': results['metadatas'][0][i].get('section_title', ''), 'distance': results['distances'][0][i] if results.get('distances') else None})
        return formatted

    def format_for_prompt(self, results: list[dict]) -> str:
        if not results:
            return ''
        parts = ['[DOMAIN KNOWLEDGE]']
        for r in results:
            parts.append(f"--- Source: {r['source_id']} | Section: {r['section_title']} ---\n{r['text']}")
        return '\n\n'.join(parts)

def build_planning_query() -> str:
    return 'STPA component abstraction level selection control structure modeling'

def build_classify_query(part_number: str) -> str:
    return f'{part_number} STPA component classification controller actuator sensor'

def build_signals_query(comp_a: str, comp_b: str, interface_type: str='') -> str:
    query = f'signals between {comp_a} and {comp_b}'
    if interface_type:
        query = f'{interface_type} {query}'
    return query

def build_control_feedback_query(signal_name: str, interface_type: str='') -> str:
    return f'{signal_name} control action feedback signal classification {interface_type}'.strip()

def build_control_details_query(action_type: str, interface_type: str='') -> str:
    return f'{action_type} timing constraint {interface_type} enable disable'.strip()

def build_feedback_details_query(feedback_type: str, interface_type: str='') -> str:
    return f'{feedback_type} update rate measurement status {interface_type}'.strip()