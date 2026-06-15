"""Shared test fixtures for the AI Study Assistant backend."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.database import init_db


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database with full schema."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


@pytest.fixture
def mock_embedder():
    """Mock embedder that returns deterministic fake vectors."""
    embedder = MagicMock()
    embedder.embed.return_value = [[0.1] * 1536 for _ in range(10)]
    embedder.embed_query.return_value = [0.1] * 1536
    return embedder


@pytest.fixture
def mock_generator():
    """Mock generator that returns controlled responses."""
    from app.services.generator import GenerationResult

    gen = MagicMock()
    gen.generate = AsyncMock(
        return_value=GenerationResult(
            content="这是测试回答[1]。",
            final_prompt="test prompt",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
    )
    gen.rewrite_query = AsyncMock(return_value="rewritten query")
    gen.client = MagicMock()
    gen.model = "test-model"
    return gen


@pytest.fixture
def mock_vector_store():
    """Mock vector store with controlled behavior."""
    vs = MagicMock()
    vs.add_chunks.return_value = None
    vs.count.return_value = 0
    vs.delete_by_doc_id.return_value = 5
    vs.health_check.return_value = True
    return vs


@pytest.fixture
def mock_rag_pipeline(mock_embedder, mock_generator, mock_vector_store):
    """Mock RAG pipeline with all components mocked."""
    from app.models.schemas import DebugInfo, RetrievedChunkInfo, TokenUsage
    from app.services.generator import CitationMark, GenerationResult

    pipeline = MagicMock()
    pipeline.embedder = mock_embedder
    pipeline.generator = mock_generator
    pipeline.vector_store = mock_vector_store

    # Mock query return
    gen_result = GenerationResult(
        content="这是测试回答[1]。",
        citations=[
            CitationMark(
                ref_index=1,
                chunk_id="chunk-1",
                doc_name="test.pdf",
                page_num=1,
                chunk_index=0,
                text_preview="测试内容",
            )
        ],
        final_prompt="test prompt",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )
    debug_info = DebugInfo(
        query="测试问题",
        embedding_model="test-model",
        top_k_chunks=[
            RetrievedChunkInfo(
                chunk_id="chunk-1",
                text_preview="测试内容",
                similarity_score=0.95,
                doc_name="test.pdf",
                page_num=1,
            )
        ],
        final_prompt="test prompt",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        retrieval_time_ms=50.0,
        generation_time_ms=200.0,
    )
    pipeline.query = AsyncMock(return_value=(gen_result, debug_info))
    pipeline.last_debug_info = debug_info

    return pipeline


@pytest.fixture
def test_app(tmp_db, mock_rag_pipeline):
    """Create a FastAPI TestClient with dependency overrides.

    Creates a minimal app WITHOUT the real lifespan (which would try to
    connect to OpenAI/ChromaDB). Routers are included manually.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import app.main as main_module
    from app.dependencies import get_rag_pipeline
    from app.routers import (
        chat,
        documents,
    )
    from app.routers import (
        collections as collections_router,
    )

    # Override the global rag_pipeline so get_rag_pipeline() returns our mock
    main_module.rag_pipeline = mock_rag_pipeline

    # Create a minimal test app (no lifespan)
    test_app = FastAPI()
    test_app.include_router(documents.router)
    test_app.include_router(chat.router)
    test_app.include_router(collections_router.router)

    # Health endpoint is defined in main.py, not a router — add it here
    @test_app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "vector_store_healthy": True,
            "vector_count": 0,
            "embedding_provider": "test",
            "llm_provider": "test",
            "llm_model": "test-model",
        }

    test_app.dependency_overrides[get_rag_pipeline] = lambda: mock_rag_pipeline

    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client

    # Cleanup
    test_app.dependency_overrides.clear()
    main_module.rag_pipeline = None
