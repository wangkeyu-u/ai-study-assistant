"""Controls isolate retrieval components and avoid flattering refusal metrics."""

from unittest.mock import MagicMock

from app.evaluation.ablation import extended_metrics
from app.services.retriever import RetrievedChunk, Retriever


def chunk(cid):
    return RetrievedChunk(
        cid,
        "evidence",
        0.8,
        cid,
        cid,
        None,
        0,
        None,
        vector_score=0.8,
        retrieval_sources=["vector"],
    )


def test_fts_only_never_calls_embedding_or_vector_store(tmp_db):
    embedder, store = MagicMock(), MagicMock()
    r = Retriever(
        store,
        embedder,
        vector_search_enabled=False,
        query_coverage_enabled=False,
        score_penalties_enabled=False,
    )
    r._lexical_search = MagicMock(return_value=[chunk("lexical")])
    result = r.retrieve("term")
    assert result.chunks[0].chunk_id == "lexical"
    embedder.embed_query.assert_not_called()
    store.search.assert_not_called()


def test_interleave_and_rrf_have_different_duplicate_rank_effects():
    vector = [chunk("a"), chunk("shared")]
    lexical = [chunk("b"), chunk("shared")]
    rrf = Retriever(MagicMock(), MagicMock())
    merged = Retriever(MagicMock(), MagicMock(), fusion_method="interleave")
    assert max(rrf._fuse(vector, lexical), key=lambda c: c.score).chunk_id == "shared"
    assert max(merged._fuse(vector, lexical), key=lambda c: c.score).chunk_id == "a"


def test_refusal_is_not_correct_hard_negative_retrieval():
    row = dict(
        reciprocal_rank=0.0,
        hit_at_1=0.0,
        recall_at_1=0.0,
        hard_negative_free_at_1=1.0,
        latency_ms=1.0,
        has_hard_negatives=True,
        expect_no_results=False,
        retrieved=[],
    )
    unsupported = dict(row, expect_no_results=True, has_hard_negatives=False, no_answer_correct=1.0)
    metrics = extended_metrics([row, unsupported], [1])
    assert metrics["hard_negative_queries"] == 1
    assert metrics["hard_negative_accuracy"] == 0.0
    assert metrics["no_answer_accuracy"] == 1.0
    assert metrics["answerable_refusal_rate"] == 1.0
