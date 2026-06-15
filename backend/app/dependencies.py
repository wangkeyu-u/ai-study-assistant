"""Shared FastAPI dependencies — lazy-load singletons to avoid circular imports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.rag import RAGPipeline


def get_rag_pipeline() -> RAGPipeline:
    """Lazy-import the global RAG pipeline singleton.

    This avoids circular imports between app.main (which creates rag_pipeline)
    and router modules (which use it).  Call this at the top of every endpoint
    that needs the pipeline.
    """
    from app.main import rag_pipeline

    assert rag_pipeline is not None, "RAG pipeline not initialized"
    return rag_pipeline
