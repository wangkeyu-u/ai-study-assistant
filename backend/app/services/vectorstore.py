"""ChromaDB vector store wrapper — handles storage and retrieval of embeddings."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "study_assistant"


@dataclass
class VectorSearchResult:
    """A single search result from the vector store."""
    chunk_id: str
    text: str
    score: float                       # similarity score (0-1, higher is better)
    metadata: dict


class VectorStore:
    """Wrapper around ChromaDB persistent client."""

    def __init__(self, persist_dir: str, embedding_dimension: int = 1536):
        self.persist_dir = persist_dir
        self.embedding_dimension = embedding_dimension
        self._client: chromadb.ClientAPI | None = None
        self._collection = None

    def _ensure_client(self):
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "ChromaDB initialized at %s, %d vectors stored",
                self.persist_dir,
                self._collection.count(),
            )

    # ── Write ──────────────────────────────────────────────

    def add_chunks(
        self,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        """Add chunks with their embeddings to the vector store."""
        self._ensure_client()
        if not chunk_ids:
            return

        # ChromaDB has a batch limit; insert in batches of 500
        batch_size = 500
        for i in range(0, len(chunk_ids), batch_size):
            end = i + batch_size
            self._collection.add(
                ids=chunk_ids[i:end],
                embeddings=embeddings[i:end],
                documents=texts[i:end],
                metadatas=metadatas[i:end],
            )
        logger.info("Added %d chunks to vector store", len(chunk_ids))

    # ── Search ─────────────────────────────────────────────

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where_filter: dict | None = None,
    ) -> list[VectorSearchResult]:
        """Search for the most similar chunks to the query embedding."""
        self._ensure_client()

        if self._collection.count() == 0:
            return []

        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, self._collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = self._collection.query(**query_kwargs)

        search_results: list[VectorSearchResult] = []
        if results["ids"] and results["ids"][0]:
            for idx, chunk_id in enumerate(results["ids"][0]):
                # ChromaDB cosine distance: 0 = identical, 2 = opposite
                # Convert to similarity: 1 - distance
                distance = results["distances"][0][idx]
                similarity = 1.0 - distance

                search_results.append(VectorSearchResult(
                    chunk_id=chunk_id,
                    text=results["documents"][0][idx],
                    score=similarity,
                    metadata=results["metadatas"][0][idx],
                ))

        return search_results

    # ── Delete ─────────────────────────────────────────────

    def delete_by_doc_id(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document."""
        self._ensure_client()

        # Get all chunk IDs for this document
        try:
            existing = self._collection.get(
                where={"doc_id": doc_id},
                include=[],
            )
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
                logger.info(
                    "Deleted %d chunks for doc_id=%s",
                    len(existing["ids"]),
                    doc_id,
                )
                return len(existing["ids"])
        except Exception as e:
            logger.warning("Error deleting chunks for doc %s: %s", doc_id, e)
        return 0

    def count(self) -> int:
        """Return the total number of vectors in the store."""
        self._ensure_client()
        return self._collection.count()

    def health_check(self) -> bool:
        """Basic health check — try to access the collection."""
        try:
            self._ensure_client()
            self._collection.count()
            return True
        except Exception:
            return False
