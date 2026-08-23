"""Context selection and compression for retrieved RAG chunks."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.query_intelligence import QueryProfile
from app.services.retriever import (
    RetrievedChunk,
    ensure_document_coverage,
    extract_query_boost_terms,
)


@dataclass(frozen=True)
class ContextSelection:
    """Diagnostics for the selected context sent to generation."""

    chunks: list[RetrievedChunk]
    original_count: int
    selected_count: int
    coverage_score: float
    strategy: str


def _token_set(text: str) -> set[str]:
    return set(extract_query_boost_terms(text, max_terms=48))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _text_query_coverage(query_terms: set[str], context: str) -> float:
    """Measure anchor coverage directly so long chunks cannot truncate late terms."""
    if not query_terms:
        return 1.0
    lowered = context.lower()
    return sum(term in lowered for term in query_terms) / len(query_terms)


def _intent_boost(chunk: RetrievedChunk, profile: QueryProfile) -> float:
    haystack = f"{chunk.heading or ''}\n{chunk.text}".lower()
    boost = 0.0

    for keyword in profile.keywords:
        if keyword.lower() in haystack:
            boost += 0.025

    if profile.requires_comparison and chunk.doc_name:
        boost += 0.02
    if profile.requires_summary and len(chunk.text) > 240:
        boost += 0.02
    if profile.requires_steps and any(
        marker in haystack for marker in ("步骤", "流程", "step", "first")
    ):
        boost += 0.04
    if profile.requires_evidence and chunk.retrieval_sources:
        boost += 0.025

    return min(boost, 0.16)


def _chunk_relevance(chunk: RetrievedChunk, profile: QueryProfile) -> float:
    score = chunk.score
    if chunk.rerank_score is not None:
        score = max(score, min(max(chunk.rerank_score, 0.0), 1.0))
    if chunk.lexical_score is not None:
        score += min(chunk.lexical_score, 1.0) * 0.08
    if chunk.vector_score is not None:
        score += min(chunk.vector_score, 1.0) * 0.05
    return score + _intent_boost(chunk, profile)


def _fit_char_budget(chunks: list[RetrievedChunk], max_chars: int) -> list[RetrievedChunk]:
    if max_chars <= 0:
        return chunks

    total = 0
    fitted: list[RetrievedChunk] = []
    for chunk in chunks:
        next_total = total + len(chunk.text)
        if fitted and next_total > max_chars:
            break
        fitted.append(chunk)
        total = next_total
    return fitted


def optimize_context_chunks(
    query: str,
    chunks: list[RetrievedChunk],
    *,
    profile: QueryProfile,
    max_chunks: int,
    max_chars: int,
    document_ids: list[str] | None = None,
    diversity_lambda: float = 0.72,
    coverage_queries: list[str] | None = None,
) -> ContextSelection:
    """Select a compact, diverse set of chunks for the generator.

    Uses a lightweight MMR-style pass: relevance comes from the retriever scores
    plus intent-aware boosts, while redundancy is estimated with lexical overlap.
    """
    if not chunks:
        return ContextSelection([], 0, 0, 0.0, "empty")

    original_count = len(chunks)
    max_chunks = max(1, max_chunks)
    diversity_lambda = min(max(diversity_lambda, 0.0), 1.0)

    effective_queries = list(dict.fromkeys([query, *(coverage_queries or [])]))
    query_term_sets = [_token_set(item) for item in effective_queries]
    query_term_sets = [terms for terms in query_term_sets if terms]
    chunk_terms = {
        chunk.chunk_id: _token_set(f"{chunk.heading or ''}\n{chunk.text}") for chunk in chunks
    }
    chunk_texts = {chunk.chunk_id: f"{chunk.heading or ''}\n{chunk.text}" for chunk in chunks}

    selected: list[RetrievedChunk] = []
    remaining = list(chunks)

    if document_ids:
        covered = ensure_document_coverage(chunks, document_ids, min(len(document_ids), max_chunks))
        for chunk in covered:
            if chunk not in selected:
                selected.append(chunk)
        remaining = [chunk for chunk in remaining if chunk not in selected]

    while remaining and len(selected) < max_chunks:
        best_chunk = None
        best_score = float("-inf")
        for chunk in remaining:
            relevance = _chunk_relevance(chunk, profile)
            query_overlap = max(
                (
                    _text_query_coverage(terms, chunk_texts[chunk.chunk_id])
                    for terms in query_term_sets
                ),
                default=0.0,
            )
            redundancy = max(
                (
                    _jaccard(chunk_terms[chunk.chunk_id], chunk_terms[item.chunk_id])
                    for item in selected
                ),
                default=0.0,
            )
            mmr_score = (
                diversity_lambda * (relevance + query_overlap * 0.12)
                - (1.0 - diversity_lambda) * redundancy
            )
            if mmr_score > best_score:
                best_score = mmr_score
                best_chunk = chunk

        if best_chunk is None:
            break
        selected.append(best_chunk)
        remaining.remove(best_chunk)

    selected = _fit_char_budget(selected, max_chars)
    covered_text = "\n".join(chunk_texts[chunk.chunk_id] for chunk in selected)
    coverage_score = max(
        (_text_query_coverage(terms, covered_text) for terms in query_term_sets),
        default=1.0,
    )

    return ContextSelection(
        chunks=selected,
        original_count=original_count,
        selected_count=len(selected),
        coverage_score=coverage_score,
        strategy=f"intent_mmr:{profile.intent}",
    )
