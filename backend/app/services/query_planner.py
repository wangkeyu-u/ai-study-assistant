"""Lightweight query decomposition and result fusion for multi-hop retrieval."""

from __future__ import annotations

import copy
import re

from app.services.retriever import (
    RetrievalResult,
    RetrievedChunk,
    Retriever,
    ensure_document_coverage,
    reciprocal_rank_fusion,
)

_CONNECTOR_RE = re.compile(r"(?:以及|并且|同时|另外|还有|和|与|及|、|,|，|;|；)")
_QUESTION_NOISE_RE = re.compile(
    r"(请问|分别|比较|对比|说明|解释|介绍|是什么|有哪些|有什么|什么|如何|怎样|多少|吗|呢|？|\?)"
)
_TRAILING_RELATION_RE = re.compile(
    r"(之间)?的?(区别|差异|关系|联系|特点|应用|任务|用途|定义|表现)$"
)
_MULTI_HOP_MARKERS = (
    "分别",
    "区别",
    "差异",
    "对比",
    "比较",
    "关系",
    "联系",
    "以及",
    "并且",
    "同时",
    "另外",
    "还有",
    "、",
    ",",
    "，",
    ";",
    "；",
)


def _clean_part(part: str) -> str:
    cleaned = _QUESTION_NOISE_RE.sub("", part)
    cleaned = _TRAILING_RELATION_RE.sub("", cleaned)
    cleaned = cleaned.strip(" \t\r\n。.!！:：-")
    return cleaned


def _clean_suffix(suffix: str) -> str:
    return suffix.strip(" \t\r\n。.!！:：-？?")


def _split_terms(text: str) -> list[str]:
    terms: list[str] = []
    for raw_part in _CONNECTOR_RE.split(text):
        part = _clean_part(raw_part)
        if len(part) >= 2 and part not in terms:
            terms.append(part)
    return terms


def decompose_query(query: str, max_subqueries: int = 3) -> list[str]:
    """Split a compound query into focused retrieval subqueries when safe."""
    if max_subqueries <= 0 or not any(marker in query for marker in _MULTI_HOP_MARKERS):
        return []

    candidates: list[str] = []
    if "分别" in query:
        prefix, suffix = query.split("分别", maxsplit=1)
        terms = _split_terms(prefix)
        suffix = _clean_suffix(suffix)
        for term in terms:
            candidate = f"{term}{suffix}" if suffix else term
            if candidate not in candidates:
                candidates.append(candidate)
        if len(candidates) >= 2:
            return candidates[:max_subqueries]

    for term in _split_terms(query):
        if term not in candidates:
            candidates.append(term)

    return candidates[:max_subqueries]


def build_retrieval_queries(query: str, max_subqueries: int = 3) -> list[str]:
    """Return the original query plus focused subqueries for recall-oriented retrieval."""
    queries = [query]
    for subquery in decompose_query(query, max_subqueries=max_subqueries):
        if subquery != query and subquery not in queries:
            queries.append(subquery)
    return queries


def merge_retrieval_results(
    query: str,
    results: list[RetrievalResult],
    *,
    top_k: int,
    rrf_k: int = 60,
    document_ids: list[str] | None = None,
) -> RetrievalResult:
    """Merge ranked retrieval results with RRF while preserving chunk metadata."""
    if not results:
        return RetrievalResult(query=query, mode="multi_hop_empty")
    if len(results) == 1:
        return results[0]

    rankings = [[chunk.chunk_id for chunk in result.chunks] for result in results]
    fused_scores = reciprocal_rank_fusion(rankings, rrf_k=rrf_k)
    max_score = len(rankings) / (rrf_k + 1)
    chunks_by_id: dict[str, RetrievedChunk] = {}
    best_original_score: dict[str, float] = {}
    first_seen: dict[str, tuple[int, int]] = {}

    for result_index, result in enumerate(results):
        for rank, chunk in enumerate(result.chunks):
            existing = chunks_by_id.get(chunk.chunk_id)
            if existing is None:
                chunks_by_id[chunk.chunk_id] = copy.copy(chunk)
                first_seen[chunk.chunk_id] = (result_index, rank)
                best_original_score[chunk.chunk_id] = chunk.score
            else:
                existing.retrieval_sources = sorted(
                    set(existing.retrieval_sources) | set(chunk.retrieval_sources)
                )
                best_original_score[chunk.chunk_id] = max(
                    best_original_score[chunk.chunk_id],
                    chunk.score,
                )

    for chunk_id, chunk in chunks_by_id.items():
        chunk.score = min(fused_scores[chunk_id] / max_score, 1.0)

    chunks = sorted(
        chunks_by_id.values(),
        key=lambda chunk: (
            chunk.score,
            best_original_score[chunk.chunk_id],
            -first_seen[chunk.chunk_id][0],
            -first_seen[chunk.chunk_id][1],
        ),
        reverse=True,
    )
    chunks = ensure_document_coverage(chunks, document_ids or [], top_k)

    confidence_scores = [result.confidence_score for result in results if result.confidence_score]
    modes = {result.mode for result in results}
    mode = f"multi_hop_{next(iter(modes))}" if len(modes) == 1 else "multi_hop_mixed"
    return RetrievalResult(
        query=query,
        chunks=chunks,
        retrieval_time_ms=sum(result.retrieval_time_ms for result in results),
        query_embedding=results[0].query_embedding,
        mode=mode,
        confidence_rejected=all(result.confidence_rejected for result in results),
        confidence_score=max(confidence_scores, default=None),
        rejection_reason=(
            results[0].rejection_reason
            if all(result.confidence_rejected for result in results)
            else None
        ),
    )


def retrieve_with_query_plan(
    retriever: Retriever,
    query: str,
    *,
    collection_id: str | None = None,
    document_ids: list[str] | None = None,
    max_subqueries: int = 3,
) -> tuple[RetrievalResult, list[str]]:
    """Run original + decomposed queries and return one fused retrieval result."""
    retrieval_queries = build_retrieval_queries(query, max_subqueries=max_subqueries)
    results = [
        retriever.retrieve(
            retrieval_query,
            collection_id=collection_id,
            document_ids=document_ids,
        )
        for retrieval_query in retrieval_queries
    ]
    if len(results) == 1:
        return results[0], retrieval_queries
    return (
        merge_retrieval_results(
            query,
            results,
            top_k=retriever.top_k,
            rrf_k=retriever.rrf_k,
            document_ids=document_ids,
        ),
        retrieval_queries,
    )
