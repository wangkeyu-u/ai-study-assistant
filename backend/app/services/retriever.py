"""Retriever — combines vector search with threshold filtering."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.services.vectorstore import VectorStore
from app.services.embedder import BaseEmbedder

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result of a retrieval operation."""
    query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    retrieval_time_ms: float = 0.0
    query_embedding: list[float] = field(default_factory=list)


@dataclass
class RetrievedChunk:
    """A single retrieved chunk with score and metadata."""
    chunk_id: str
    text: str
    score: float
    doc_id: str
    doc_name: str
    page_num: int | None
    chunk_index: int
    heading: str | None


class Retriever:
    """Retrieve relevant chunks for a query using vector similarity."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: BaseEmbedder,
        top_k: int = 5,
        similarity_threshold: float = 0.3,
    ):
        self.vector_store = vector_store
        self.embedder = embedder
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    def retrieve(self, query: str, collection_id: str | None = None) -> RetrievalResult:
        """Retrieve relevant chunks for the given query.

        Args:
            query: The search query text.
            collection_id: Optional collection ID to restrict search to a specific knowledge base.
        """
        start = time.time()

        # 1. Embed the query
        query_embedding = self.embedder.embed_query(query)

        # 2. Vector search (optionally filtered by collection)
        where_filter = None
        if collection_id:
            where_filter = {"collection_id": collection_id}

        search_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=self.top_k,
            where_filter=where_filter,
        )

        # 3. Filter by similarity threshold
        filtered: list[RetrievedChunk] = []
        for r in search_results:
            if r.score < self.similarity_threshold:
                continue

            meta = r.metadata
            filtered.append(RetrievedChunk(
                chunk_id=r.chunk_id,
                text=r.text,
                score=r.score,
                doc_id=meta.get("doc_id", ""),
                doc_name=meta.get("doc_name", ""),
                page_num=meta.get("page_num"),
                chunk_index=meta.get("chunk_index", 0),
                heading=meta.get("heading"),
            ))

        # 4. Apply quality score adjustment (Phase 4)
        # Low quality chunks get their score reduced by 20%
        conn = None
        try:
            from app.db.database import get_connection
            conn = get_connection()
            chunk_ids = [c.chunk_id for c in filtered]
            if chunk_ids:
                placeholders = ",".join("?" for _ in chunk_ids)
                quality_rows = conn.execute(
                    f"SELECT chunk_id, info_density, is_low_quality FROM chunk_quality WHERE chunk_id IN ({placeholders})",
                    chunk_ids,
                ).fetchall()
                quality_map = {r["chunk_id"]: r for r in quality_rows}
                for chunk in filtered:
                    q = quality_map.get(chunk.chunk_id)
                    if q and q["is_low_quality"]:
                        chunk.score *= 0.8  # penalize low quality chunks
                # Re-sort by adjusted score
                filtered.sort(key=lambda c: c.score, reverse=True)
        except Exception:
            pass  # Quality scoring is optional enhancement
        finally:
            if conn:
                conn.close()

        elapsed = (time.time() - start) * 1000

        logger.info(
            "Retrieved %d chunks (threshold=%.2f) in %.1fms",
            len(filtered),
            self.similarity_threshold,
            elapsed,
        )

        return RetrievalResult(
            query=query,
            chunks=filtered,
            retrieval_time_ms=elapsed,
            query_embedding=query_embedding,
        )
