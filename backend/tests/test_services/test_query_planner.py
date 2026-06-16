"""Tests for query decomposition and multi-hop retrieval fusion."""

from unittest.mock import MagicMock

from app.services.query_planner import (
    build_retrieval_queries,
    merge_retrieval_results,
    retrieve_with_query_plan,
)
from app.services.retriever import RetrievalResult, RetrievedChunk


def _chunk(chunk_id: str, score: float = 1.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=f"{chunk_id} text",
        score=score,
        doc_id="doc",
        doc_name="source.pdf",
        page_num=1,
        chunk_index=0,
        heading=None,
        retrieval_sources=["fts"],
    )


def test_build_retrieval_queries_splits_respective_question():
    queries = build_retrieval_queries("CNN和RNN分别用于什么任务？", max_subqueries=3)

    assert queries == ["CNN和RNN分别用于什么任务？", "CNN用于什么任务", "RNN用于什么任务"]


def test_build_retrieval_queries_splits_comma_joined_question():
    queries = build_retrieval_queries("RAG如何减少幻觉，HNSW用于什么检索？", max_subqueries=3)

    assert queries == [
        "RAG如何减少幻觉，HNSW用于什么检索？",
        "RAG减少幻觉",
        "HNSW用于检索",
    ]


def test_merge_retrieval_results_uses_rrf_and_deduplicates_chunks():
    first = RetrievalResult(query="q", chunks=[_chunk("shared"), _chunk("a")], mode="hybrid")
    second = RetrievalResult(query="q2", chunks=[_chunk("b"), _chunk("shared")], mode="hybrid")

    merged = merge_retrieval_results("q", [first, second], top_k=3)

    assert merged.mode == "multi_hop_hybrid"
    assert [chunk.chunk_id for chunk in merged.chunks] == ["shared", "b", "a"]


def test_retrieve_with_query_plan_runs_original_and_subqueries():
    retriever = MagicMock()
    retriever.top_k = 3
    retriever.rrf_k = 60
    retriever.retrieve.side_effect = [
        RetrievalResult(query="q", chunks=[_chunk("original")], mode="hybrid"),
        RetrievalResult(query="CNN用于什么任务", chunks=[_chunk("cnn")], mode="hybrid"),
        RetrievalResult(query="RNN用于什么任务", chunks=[_chunk("rnn")], mode="hybrid"),
    ]

    result, queries = retrieve_with_query_plan(
        retriever,
        "CNN和RNN分别用于什么任务？",
        max_subqueries=2,
    )

    assert queries == ["CNN和RNN分别用于什么任务？", "CNN用于什么任务", "RNN用于什么任务"]
    assert retriever.retrieve.call_count == 3
    assert {chunk.chunk_id for chunk in result.chunks} == {"original", "cnn", "rnn"}
