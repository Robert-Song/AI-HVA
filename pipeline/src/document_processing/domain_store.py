import logging
import threading
from pathlib import Path
from typing import Optional

import chromadb

from src.config import (
    DOMAIN_KB_COLLECTION,
    DOMAIN_KB_PATH,
    EMBEDDING_BACKEND,
    RETRIEVAL_TOP_K,
    get_embedding_config,
)
from src.document_processing.domain_chunker import chunk_all_documents

logger = logging.getLogger(__name__)


class DomainKnowledgeStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DOMAIN_KB_PATH
        self.embedding_config = get_embedding_config()
        self._client = None
        self._collection = None
        self._embedding_model = None
        self._lock = threading.RLock()

    @property
    def client(self) -> chromadb.ClientAPI:
        with self._lock:
            if self._client is None:
                Path(self.db_path).mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(path=self.db_path)
            return self._client

    @property
    def collection(self) -> chromadb.Collection:
        with self._lock:
            if self._collection is None:
                self._collection = self.client.get_or_create_collection(
                    name=DOMAIN_KB_COLLECTION,
                    metadata=self._collection_metadata(),
                )
            return self._collection

    def _collection_metadata(self, dimension: Optional[int] = None) -> dict:
        metadata = {
            "hnsw:space": "cosine",
            "embedding_backend": EMBEDDING_BACKEND,
            "embedding_model": self.embedding_config["name"],
        }
        if dimension is not None:
            metadata["embedding_dimension"] = dimension
        return metadata

    def _recreate_collection(self, dimension: int) -> chromadb.Collection:
        with self._lock:
            try:
                self.client.delete_collection(name=DOMAIN_KB_COLLECTION)
            except Exception:
                pass
            self._collection = self.client.create_collection(
                name=DOMAIN_KB_COLLECTION,
                metadata=self._collection_metadata(dimension),
            )
            return self._collection

    def _get_embedding_model(self):
        with self._lock:
            if self._embedding_model is None:
                from sentence_transformers import SentenceTransformer

                model_name = self.embedding_config["name"]
                logger.info("Loading embedding model: %s", model_name)
                self._embedding_model = SentenceTransformer(model_name)
            return self._embedding_model

    def _embed_texts(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        if self.embedding_config.get("instruction_prefix"):
            if is_query:
                texts = [
                    f"Instruct: Retrieve documents about hardware safety analysis\nQuery: {text}"
                    for text in texts
                ]
            else:
                texts = [
                    f"Instruct: Represent this document for retrieval\nDocument: {text}"
                    for text in texts
                ]

        if self.embedding_config.get("type") == "server":
            from src.llm.client import _get_client

            client = _get_client("embedding")
            response = client.embeddings.create(
                model=self.embedding_config["name"],
                input=texts,
            )
            return [data.embedding for data in response.data]

        model = self._get_embedding_model()
        embeddings = model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

    def build_index(self, corpus_dir: str) -> int:
        chunks = chunk_all_documents(corpus_dir)
        if not chunks:
            logger.warning("No chunks to index; corpus may be empty")
            return 0
        logger.info("Indexing %s chunks into domain knowledge store", len(chunks))
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self._embed_texts(texts, is_query=False)
        if not embeddings:
            logger.warning("No embeddings generated for domain knowledge chunks")
            return 0
        collection = self._recreate_collection(len(embeddings[0]))
        collection.add(
            ids=[chunk["chunk_id"] for chunk in chunks],
            documents=texts,
            metadatas=[
                {
                    "source_id": chunk["source_id"],
                    "section_title": chunk["section_title"],
                    "source_type": chunk["source_type"],
                }
                for chunk in chunks
            ],
            embeddings=embeddings,
        )
        logger.info("Indexed %s chunks into '%s'", len(chunks), DOMAIN_KB_COLLECTION)
        return len(chunks)

    def query(
        self,
        query_text: str,
        n_results: Optional[int] = None,
        where: Optional[dict] = None,
    ) -> list[dict]:
        with self._lock:
            n = n_results or RETRIEVAL_TOP_K
            collection = self.collection
            count = collection.count()
            if count == 0:
                logger.warning("Domain knowledge store is empty; no results returned")
                return []
            query_embedding = self._embed_texts([query_text], is_query=True)[0]
            kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": min(n, count),
            }
            if where:
                kwargs["where"] = where
            results = collection.query(**kwargs)

        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                formatted.append(
                    {
                        "chunk_id": chunk_id,
                        "text": results["documents"][0][i],
                        "source_id": results["metadatas"][0][i].get("source_id", ""),
                        "section_title": results["metadatas"][0][i].get("section_title", ""),
                        "distance": results["distances"][0][i]
                        if results.get("distances")
                        else None,
                    }
                )
        return formatted

    def format_for_prompt(self, results: list[dict]) -> str:
        if not results:
            return ""
        parts = ["[DOMAIN KNOWLEDGE]"]
        for result in results:
            parts.append(
                f"--- Source: {result['source_id']} | Section: {result['section_title']} ---\n"
                f"{result['text']}"
            )
        return "\n\n".join(parts)


def build_planning_query() -> str:
    return "STPA component abstraction level selection control structure modeling"


def build_classify_query(part_number: str) -> str:
    return f"{part_number} STPA component classification controller actuator sensor"


def build_signals_query(comp_a: str, comp_b: str, interface_type: str = "") -> str:
    query = f"signals between {comp_a} and {comp_b}"
    if interface_type:
        query = f"{interface_type} {query}"
    return query


def build_control_feedback_query(signal_name: str, interface_type: str = "") -> str:
    return f"{signal_name} control action feedback signal classification {interface_type}".strip()


def build_control_details_query(action_type: str, interface_type: str = "") -> str:
    return f"{action_type} timing constraint {interface_type} enable disable".strip()


def build_feedback_details_query(feedback_type: str, interface_type: str = "") -> str:
    return f"{feedback_type} update rate measurement status {interface_type}".strip()
