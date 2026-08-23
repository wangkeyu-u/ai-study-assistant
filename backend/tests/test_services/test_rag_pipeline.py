from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.database import get_connection
from app.services.generator import GenerationResult, Generator
from app.services.rag import RAGPipeline
from app.services.vectorstore import VectorSearchResult


@pytest.mark.asyncio
async def test_query_rejects_vector_only_context_with_zero_query_coverage(tmp_db):
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1, 0.2]
    vector_store = MagicMock()
    vector_store.search.return_value = [
        VectorSearchResult(
            chunk_id="irrelevant",
            text="机器学习主要分为监督学习、无监督学习和强化学习。",
            score=0.8,
            metadata={
                "doc_id": "doc-ml",
                "doc_name": "ml.pdf",
                "page_num": 1,
                "chunk_index": 0,
            },
        )
    ]
    generator = Generator(api_key="test")
    pipeline = RAGPipeline(embedder=embedder, vector_store=vector_store, generator=generator)

    result, debug = await pipeline.query("请对比火星天气和量子电池的差异")

    assert "没有找到足够的信息" in result.content
    assert debug.confidence_rejected is True
    assert debug.rejection_reason == "context_coverage_below_threshold"
    assert debug.context_chunks_before == 1
    assert debug.context_chunks_after == 0
    assert debug.top_k_chunks == []
    assert debug.token_usage.total_tokens == 0


@pytest.mark.asyncio
async def test_chinese_question_retrieves_english_document_and_answers_in_english(tmp_db):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO documents
               (id, filename, file_type, file_path, file_size, status)
               VALUES ('doc-en', 'rag.md', 'md', '/tmp/rag.md', 100, 'ready')"""
        )
        conn.execute(
            """INSERT INTO chunks
               (id, doc_id, chunk_index, text, heading, token_count)
               VALUES (
                   'chunk-en', 'doc-en', 0,
                   'Retrieval augmented generation combines semantic search with grounded generation.',
                   'RAG architecture', 12
               )"""
        )
        conn.commit()

    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1, 0.2]
    vector_store = MagicMock()
    vector_store.search.return_value = [
        VectorSearchResult(
            chunk_id="chunk-en",
            text=(
                "Retrieval augmented generation combines semantic search with grounded generation."
            ),
            score=0.82,
            metadata={
                "doc_id": "doc-en",
                "doc_name": "rag.md",
                "heading": "RAG architecture",
                "chunk_index": 0,
            },
        )
    ]
    generator = MagicMock()
    generator.translate_query_for_retrieval = AsyncMock(
        return_value="What is retrieval augmented generation?"
    )
    generator.generate_hypothetical_passage = AsyncMock(return_value="")
    generator.generate = AsyncMock(
        return_value=GenerationResult(
            content="RAG combines retrieval with grounded generation[1].",
            final_prompt="prompt",
        )
    )
    generator.rewrite_query = AsyncMock(side_effect=lambda query, _history: query)

    pipeline = RAGPipeline(embedder=embedder, vector_store=vector_store, generator=generator)
    result, debug = await pipeline.query(
        "什么是检索增强生成？",
        document_ids=["doc-en"],
        answer_language="en",
    )

    assert result.content.startswith("RAG combines")
    generator.translate_query_for_retrieval.assert_awaited_once_with(
        "什么是检索增强生成？",
        "en",
    )
    assert "What is retrieval augmented generation?" in debug.retrieval_queries
    assert debug.query_language == "zh"
    assert debug.corpus_languages == ["en"]
    assert debug.answer_language == "en"
    assert generator.generate.await_args.kwargs["answer_language"] == "en"


def test_reindex_preserves_historical_citation_chunks(tmp_db, tmp_path):
    source_path = tmp_path / "guide.md"
    source_path.write_text(
        "# Retrieval Pipeline\n\nDense and lexical retrieval are fused before generation.",
        encoding="utf-8",
    )
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO documents
               (id, filename, file_type, file_path, file_size, chunk_count, status)
               VALUES ('doc', 'guide.md', 'md', ?, 100, 1, 'ready')""",
            (str(source_path),),
        )
        conn.execute(
            """INSERT INTO chunks
               (id, doc_id, chunk_index, text, token_count)
               VALUES ('old-chunk', 'doc', 0, 'Old chunk text.', 4)"""
        )
        conn.execute("INSERT INTO chat_sessions (id, title) VALUES ('session', 'test')")
        conn.execute(
            """INSERT INTO chat_messages (id, session_id, role, content)
               VALUES ('message', 'session', 'assistant', 'Historical answer[1].')"""
        )
        conn.execute(
            """INSERT INTO citations
               (id, message_id, doc_id, chunk_id, doc_name, chunk_index, text_preview)
               VALUES ('citation', 'message', 'doc', 'old-chunk', 'guide.md', 0, 'Old chunk text.')"""
        )
        conn.commit()

    embedder = MagicMock()
    embedder.embed.return_value = [[0.1, 0.2]]
    vector_store = MagicMock()
    vector_store.delete_chunks.side_effect = lambda chunk_ids: len(chunk_ids)
    pipeline = RAGPipeline(embedder=embedder, vector_store=vector_store, generator=MagicMock())

    result = pipeline.reindex_document("doc")

    assert result["success"] is True
    with get_connection() as conn:
        old_chunk = conn.execute("SELECT is_active FROM chunks WHERE id='old-chunk'").fetchone()
        active_chunk = conn.execute(
            """SELECT heading, text FROM chunks
               WHERE doc_id='doc' AND is_active=1"""
        ).fetchone()
        citation = conn.execute("SELECT chunk_id FROM citations WHERE id='citation'").fetchone()
    assert old_chunk["is_active"] == 0
    assert active_chunk["heading"] == "Retrieval Pipeline"
    assert "Dense and lexical retrieval" in active_chunk["text"]
    assert citation["chunk_id"] == "old-chunk"
    vector_store.delete_chunks.assert_any_call(["old-chunk"])
