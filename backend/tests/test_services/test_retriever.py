"""Tests for vector + FTS5 hybrid retrieval."""

from unittest.mock import MagicMock

import pytest

from app.db.database import get_connection
from app.services.retriever import (
    RetrievedChunk,
    Retriever,
    build_fts_query,
    extract_query_boost_terms,
    extract_short_terms,
    reciprocal_rank_fusion,
)
from app.services.vectorstore import VectorSearchResult


def _insert_chunk(
    doc_id: str,
    chunk_id: str,
    text: str,
    *,
    filename: str = "source.pdf",
    collection_id: str | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO documents
               (id, filename, file_type, file_path, file_size, status, collection_id)
               VALUES (?, ?, 'pdf', ?, 100, 'ready', ?)""",
            (doc_id, filename, f"/tmp/{filename}", collection_id),
        )
        conn.execute(
            """INSERT INTO chunks
               (id, doc_id, chunk_index, text, page_num, heading, token_count)
               VALUES (?, ?, 0, ?, 1, '测试章节', 20)""",
            (chunk_id, doc_id, text),
        )
        conn.commit()


def test_build_fts_query_supports_mixed_chinese_and_english():
    query = build_fts_query("RAG 中的向量检索是什么？")

    assert query is not None
    assert '"rag"' in query
    assert '"向量检"' in query


def test_reciprocal_rank_fusion_rewards_results_found_by_both_sources():
    scores = reciprocal_rank_fusion([["shared", "vector"], ["shared", "fts"]], rrf_k=60)

    assert scores["shared"] > scores["vector"]
    assert scores["shared"] > scores["fts"]


def test_extract_short_terms_supports_terms_trigram_fts_cannot_index():
    assert extract_short_terms("F1 和 AI 指标") == ["f1", "ai"]
    assert extract_short_terms("What is AI and ML used for?") == ["ai", "ml"]


def test_extract_query_boost_terms_filters_question_noise():
    terms = extract_query_boost_terms("监督学习使用什么样的训练数据？")

    assert "监督学习" in terms
    assert "训练数据" in terms
    assert all("什么" not in term for term in terms)


def test_hybrid_retrieval_recovers_exact_keyword_match(tmp_db):
    _insert_chunk("doc-keyword", "chunk-keyword", "量子纠缠机制是量子力学的重要现象。")

    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1, 0.2]
    vector_store = MagicMock()
    vector_store.search.return_value = [
        VectorSearchResult(
            chunk_id="chunk-vector",
            text="这是一个只有语义相似度的结果。",
            score=0.8,
            metadata={
                "doc_id": "doc-vector",
                "doc_name": "vector.pdf",
                "chunk_index": 0,
            },
        )
    ]
    retriever = Retriever(
        vector_store=vector_store,
        embedder=embedder,
        top_k=2,
        similarity_threshold=0.3,
    )

    result = retriever.retrieve("量子纠缠机制")

    assert result.mode == "hybrid"
    assert {chunk.chunk_id for chunk in result.chunks} == {"chunk-vector", "chunk-keyword"}
    lexical = next(chunk for chunk in result.chunks if chunk.chunk_id == "chunk-keyword")
    assert lexical.retrieval_sources == ["fts"]
    assert lexical.lexical_score is not None


def test_lexical_retrieval_respects_collection_filter(tmp_db):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO collections (id, name) VALUES ('collection-a', 'A'), ('collection-b', 'B')"
        )
        conn.commit()
    _insert_chunk(
        "doc-a",
        "chunk-a",
        "神经网络反向传播算法",
        filename="a.pdf",
        collection_id="collection-a",
    )
    _insert_chunk(
        "doc-b",
        "chunk-b",
        "神经网络反向传播算法",
        filename="b.pdf",
        collection_id="collection-b",
    )

    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1]
    vector_store = MagicMock()
    vector_store.search.return_value = []
    retriever = Retriever(vector_store, embedder, top_k=5)

    result = retriever.retrieve("神经网络反向传播", collection_id="collection-a")

    assert [chunk.chunk_id for chunk in result.chunks] == ["chunk-a"]
    vector_store.search.assert_called_once_with(
        query_embedding=[0.1],
        top_k=20,
        where_filter={"collection_id": "collection-a"},
    )


def test_hybrid_retrieval_recovers_short_exact_term(tmp_db):
    _insert_chunk("doc-f1", "chunk-f1", "F1分数是精确率和召回率的调和平均数。")
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1]
    vector_store = MagicMock()
    vector_store.search.return_value = []

    result = Retriever(vector_store, embedder).retrieve("F1分数是如何定义的？")

    assert [chunk.chunk_id for chunk in result.chunks] == ["chunk-f1"]
    assert "exact" in result.chunks[0].retrieval_sources


def test_short_exact_term_does_not_match_inside_longer_word(tmp_db):
    _insert_chunk("doc-training", "chunk-training", "Training improves model quality.")
    _insert_chunk("doc-ai", "chunk-ai", "AI can support personalized learning.")
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1]
    vector_store = MagicMock()
    vector_store.search.return_value = []

    result = Retriever(vector_store, embedder).retrieve("AI")

    assert [chunk.chunk_id for chunk in result.chunks] == ["chunk-ai"]
    assert result.chunks[0].retrieval_sources == ["exact"]


def test_confidence_gate_rejects_weak_vector_only_fallback(tmp_db):
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1]
    vector_store = MagicMock()
    vector_store.search.return_value = [
        VectorSearchResult(
            chunk_id="weak",
            text="不相关内容",
            score=0.45,
            metadata={"doc_id": "doc", "doc_name": "source.pdf", "chunk_index": 0},
        )
    ]

    result = Retriever(vector_store, embedder, vector_only_min_score=0.46).retrieve("火星天气")

    assert result.chunks == []
    assert result.confidence_rejected is True
    assert result.confidence_score == 0.45
    assert result.rejection_reason == "vector_only_score_below_threshold"


def test_confidence_gate_keeps_strong_vector_only_fallback(tmp_db):
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1]
    vector_store = MagicMock()
    vector_store.search.return_value = [
        VectorSearchResult(
            chunk_id="strong",
            text="语义相关内容",
            score=0.7,
            metadata={"doc_id": "doc", "doc_name": "source.pdf", "chunk_index": 0},
        )
    ]

    result = Retriever(vector_store, embedder, vector_only_min_score=0.46).retrieve("相关问题")

    assert [chunk.chunk_id for chunk in result.chunks] == ["strong"]
    assert result.confidence_rejected is False


def test_optional_reranker_controls_final_candidate_order(tmp_db):
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1]
    vector_store = MagicMock()
    vector_store.search.return_value = [
        VectorSearchResult(
            chunk_id="first",
            text="first result",
            score=0.8,
            metadata={"doc_id": "doc", "doc_name": "source.pdf", "chunk_index": 0},
        ),
        VectorSearchResult(
            chunk_id="second",
            text="second result",
            score=0.7,
            metadata={"doc_id": "doc", "doc_name": "source.pdf", "chunk_index": 1},
        ),
    ]
    reranker = MagicMock()

    def reverse_candidates(_query, chunks):
        chunks[0].rerank_score = 0.1
        chunks[1].rerank_score = 0.9
        return list(reversed(chunks))

    reranker.rerank.side_effect = reverse_candidates
    result = Retriever(
        vector_store,
        embedder,
        hybrid_search_enabled=False,
        reranker=reranker,
    ).retrieve("query")

    assert [chunk.chunk_id for chunk in result.chunks] == ["second", "first"]
    assert result.mode == "vector_rerank"


def test_answerability_penalty_deprioritizes_meta_negative_chunks(tmp_db):
    relevant = RetrievedChunk(
        chunk_id="relevant",
        text="F1分数是精确率和召回率的调和平均值。",
        score=0.9,
        doc_id="doc",
        doc_name="source.pdf",
        page_num=1,
        chunk_index=0,
        heading=None,
    )
    distractor = RetrievedChunk(
        chunk_id="distractor",
        text="本文只说明监控字段需要被采集和告警，不定义F1分数。",
        score=1.0,
        doc_id="doc",
        doc_name="source.pdf",
        page_num=1,
        chunk_index=1,
        heading=None,
        lexical_score=1.0,
    )

    Retriever._apply_answerability_penalty([relevant, distractor])

    assert distractor.score < relevant.score
    assert distractor.lexical_score == 0.55


def test_query_coverage_boost_rewards_more_query_fragments(tmp_db):
    partial = RetrievedChunk(
        chunk_id="partial",
        text="训练数据上表现很好，但泛化到新数据较差。",
        score=1.0,
        doc_id="doc",
        doc_name="source.pdf",
        page_num=1,
        chunk_index=0,
        heading=None,
    )
    covered = RetrievedChunk(
        chunk_id="covered",
        text="监督学习通常使用带标签的训练数据。",
        score=0.98,
        doc_id="doc",
        doc_name="source.pdf",
        page_num=1,
        chunk_index=1,
        heading=None,
    )

    Retriever._apply_query_coverage_boost(
        "监督学习使用什么样的训练数据？",
        [partial, covered],
    )

    assert covered.score > partial.score


def test_chunks_fts_is_rebuilt_for_existing_rows(tmp_path):
    from app.db.database import init_db

    db_path = tmp_path / "rebuild.db"
    init_db(str(db_path))
    _insert_chunk("doc-rebuild", "chunk-rebuild", "检索增强生成系统")

    # Reinitialization simulates upgrading an existing local database.
    init_db(str(db_path))
    with get_connection() as conn:
        row = conn.execute(
            """SELECT c.id FROM chunks_fts
               JOIN chunks c ON c.rowid = chunks_fts.rowid
               WHERE chunks_fts MATCH '"检索增"'"""
        ).fetchone()

    assert row["id"] == "chunk-rebuild"


@pytest.mark.parametrize("query", ["", "a", "中文"])
def test_short_queries_skip_fts(query):
    assert build_fts_query(query) is None
