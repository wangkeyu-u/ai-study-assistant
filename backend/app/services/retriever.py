"""Hybrid retriever combining dense vectors and SQLite FTS5 with RRF."""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field

from app.db.database import get_db
from app.services.embedder import BaseEmbedder
from app.services.reranker import BaseReranker
from app.services.vectorstore import VectorStore

logger = logging.getLogger(__name__)

_ENGLISH_TERM_RE = re.compile(r"[A-Za-z0-9_]{3,}")
_SHORT_ENGLISH_TERM_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z0-9_]{2}(?![A-Za-z0-9_])")
_CJK_RUN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]{3,}")
_CJK_QUERY_MARKERS = (
    "什么",
    "哪些",
    "哪个",
    "哪类",
    "如何",
    "是否",
    "怎样",
    "多少",
    "请问",
)
_CJK_GENERIC_BOOST_TERMS = {
    "使用",
    "通过",
    "主要",
    "文档",
    "资料",
    "教材",
    "解释",
    "说明",
    "对应",
}
_META_NEGATION_RE = re.compile(
    r"(不解释|不说明|不定义|不讨论|不会说明|只(?:是|列出|讨论|说明).{0,24}不|"
    r"does\s+not\s+(?:explain|define|discuss)|"
    r"do\s+not\s+(?:explain|define|discuss))",
    re.IGNORECASE,
)


@dataclass
class RetrievalResult:
    """Result of a retrieval operation."""

    query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    retrieval_time_ms: float = 0.0
    query_embedding: list[float] = field(default_factory=list)
    mode: str = "vector"
    confidence_rejected: bool = False
    confidence_score: float | None = None
    rejection_reason: str | None = None


@dataclass
class RetrievedChunk:
    """A retrieved chunk with fused score and source-specific diagnostics."""

    chunk_id: str
    text: str
    score: float
    doc_id: str
    doc_name: str
    page_num: int | None
    chunk_index: int
    heading: str | None
    vector_score: float | None = None
    lexical_score: float | None = None
    rerank_score: float | None = None
    retrieval_sources: list[str] = field(default_factory=list)


def build_fts_query(query: str, max_terms: int = 32) -> str | None:
    """Build a safe trigram FTS5 OR query from mixed Chinese/English text."""
    terms: list[str] = []

    for term in _ENGLISH_TERM_RE.findall(query):
        normalized = term.lower()
        if normalized not in terms:
            terms.append(normalized)

    for run in _CJK_RUN_RE.findall(query):
        # Trigrams provide useful recall for natural-language Chinese questions,
        # where the full question rarely appears verbatim in the source text.
        for index in range(len(run) - 2):
            term = run[index : index + 3]
            if term not in terms:
                terms.append(term)

    if not terms:
        return None

    return " OR ".join(f'"{term}"' for term in terms[:max_terms])


def extract_short_terms(query: str, max_terms: int = 8) -> list[str]:
    """Extract exact two-character ASCII terms unsupported by trigram FTS."""
    terms: list[str] = []
    for term in _SHORT_ENGLISH_TERM_RE.findall(query):
        # Two-letter lowercase words are usually English stop words. Preserve
        # acronyms and digit-bearing terms such as AI, ML, F1, and L2.
        if not term.isupper() and not any(character.isdigit() for character in term):
            continue
        normalized = term.lower()
        if normalized not in terms:
            terms.append(normalized)
    return terms[:max_terms]


def extract_query_boost_terms(query: str, max_terms: int = 24) -> list[str]:
    """Extract distinctive query fragments used as a small ranking tie-breaker."""
    terms: list[str] = []

    def add(term: str) -> None:
        normalized = term.lower()
        if normalized and normalized not in terms:
            terms.append(normalized)

    for term in _ENGLISH_TERM_RE.findall(query):
        add(term)
    for term in extract_short_terms(query):
        add(term)

    for run in _CJK_RUN_RE.findall(query):
        for width in (4, 3):
            if len(run) < width:
                continue
            for index in range(len(run) - width + 1):
                term = run[index : index + width]
                if term in _CJK_GENERIC_BOOST_TERMS:
                    continue
                if any(marker in term for marker in _CJK_QUERY_MARKERS):
                    continue
                add(term)
                if len(terms) >= max_terms:
                    return terms

    return terms[:max_terms]


def _sqlite_regexp(pattern: str, value: str | None) -> int:
    return int(value is not None and re.search(pattern, value, flags=re.IGNORECASE) is not None)


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    rrf_k: int = 60,
) -> dict[str, float]:
    """Fuse ranked chunk IDs using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return scores


class Retriever:
    """Retrieve chunks using vector search, FTS5, or a hybrid of both."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: BaseEmbedder,
        top_k: int = 5,
        similarity_threshold: float = 0.3,
        hybrid_search_enabled: bool = True,
        candidate_multiplier: int = 4,
        rrf_k: int = 60,
        confidence_gate_enabled: bool = True,
        vector_only_min_score: float = 0.46,
        reranker: BaseReranker | None = None,
        rerank_top_n: int = 12,
    ):
        self.vector_store = vector_store
        self.embedder = embedder
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.hybrid_search_enabled = hybrid_search_enabled
        self.candidate_multiplier = max(candidate_multiplier, 1)
        self.rrf_k = max(rrf_k, 1)
        self.confidence_gate_enabled = confidence_gate_enabled
        self.vector_only_min_score = vector_only_min_score
        self.reranker = reranker
        self.rerank_top_n = max(rerank_top_n, top_k)

    def retrieve(self, query: str, collection_id: str | None = None) -> RetrievalResult:
        """Retrieve chunks for a query, optionally restricted to a collection."""
        start = time.time()
        candidate_k = max(self.top_k * self.candidate_multiplier, self.top_k)
        query_embedding = self.embedder.embed_query(query)

        where_filter = {"collection_id": collection_id} if collection_id else None
        vector_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=candidate_k,
            where_filter=where_filter,
        )
        vector_chunks: list[RetrievedChunk] = []
        for result in vector_results:
            if result.score < self.similarity_threshold:
                continue
            meta = result.metadata
            vector_chunks.append(
                RetrievedChunk(
                    chunk_id=result.chunk_id,
                    text=result.text,
                    score=result.score,
                    doc_id=meta.get("doc_id", ""),
                    doc_name=meta.get("doc_name", ""),
                    page_num=meta.get("page_num") or None,
                    chunk_index=meta.get("chunk_index", 0),
                    heading=meta.get("heading") or None,
                    vector_score=result.score,
                    retrieval_sources=["vector"],
                )
            )

        lexical_chunks = (
            self._lexical_search(query, candidate_k, collection_id)
            if self.hybrid_search_enabled
            else []
        )

        if lexical_chunks:
            chunks = self._fuse(vector_chunks, lexical_chunks)
            mode = "hybrid"
        else:
            chunks = vector_chunks[: self.top_k]
            mode = "vector"

        self._apply_quality_penalty(chunks)
        self._apply_query_coverage_boost(query, chunks)
        self._apply_answerability_penalty(chunks)
        chunks.sort(key=lambda chunk: chunk.score, reverse=True)
        if self.reranker and chunks:
            chunks = self.reranker.rerank(query, chunks[: self.rerank_top_n])
            mode = f"{mode}_rerank"
        chunks = chunks[: self.top_k]

        confidence_rejected = False
        confidence_score = max(
            (chunk.vector_score or 0.0 for chunk in chunks),
            default=None,
        )
        rejection_reason = None
        has_lexical_evidence = bool(chunks) and any(
            source in {"fts", "exact"} for source in chunks[0].retrieval_sources
        )
        if (
            self.hybrid_search_enabled
            and self.confidence_gate_enabled
            and chunks
            and not has_lexical_evidence
            and (confidence_score or 0.0) < self.vector_only_min_score
        ):
            confidence_rejected = True
            rejection_reason = "vector_only_score_below_threshold"
            chunks = []

        elapsed = (time.time() - start) * 1000
        logger.info(
            "Retrieved %d chunks (mode=%s, vector=%d, lexical=%d, rejected=%s) in %.1fms",
            len(chunks),
            mode,
            len(vector_chunks),
            len(lexical_chunks),
            confidence_rejected,
            elapsed,
        )
        return RetrievalResult(
            query=query,
            chunks=chunks,
            retrieval_time_ms=elapsed,
            query_embedding=query_embedding,
            mode=mode,
            confidence_rejected=confidence_rejected,
            confidence_score=confidence_score,
            rejection_reason=rejection_reason,
        )

    def _lexical_search(
        self,
        query: str,
        limit: int,
        collection_id: str | None,
    ) -> list[RetrievedChunk]:
        fts_query = build_fts_query(query)
        short_terms = extract_short_terms(query)
        if not fts_query and not short_terms:
            return []

        collection_clause = " AND d.collection_id = ?" if collection_id else ""
        rows_by_id: dict[str, tuple[sqlite3.Row, float, list[str]]] = {}

        try:
            with get_db() as conn:
                if fts_query:
                    params: list[str | int] = [fts_query]
                    if collection_id:
                        params.append(collection_id)
                    params.append(limit)
                    rows = conn.execute(
                        f"""SELECT c.id, c.doc_id, c.text, c.page_num, c.heading,
                                   c.chunk_index, d.filename AS doc_name,
                                   bm25(chunks_fts, 1.0, 1.5) AS bm25_score
                            FROM chunks_fts
                            JOIN chunks c ON c.rowid = chunks_fts.rowid
                            JOIN documents d ON d.id = c.doc_id
                            WHERE chunks_fts MATCH ? AND d.status = 'ready'
                                  {collection_clause}
                            ORDER BY bm25_score
                            LIMIT ?""",
                        params,
                    ).fetchall()
                    for row in rows:
                        lexical_score = round(1.0 / (1.0 + abs(row["bm25_score"])), 6)
                        rows_by_id[row["id"]] = (row, lexical_score, ["fts"])

                if short_terms:
                    conn.create_function("regexp", 2, _sqlite_regexp)
                    alternatives = "|".join(re.escape(term) for term in short_terms)
                    exact_pattern = rf"(?<![A-Za-z0-9_])(?:{alternatives})(?![A-Za-z0-9_])"
                    exact_params: list[str | int] = [exact_pattern]
                    if collection_id:
                        exact_params.append(collection_id)
                    exact_params.append(limit)
                    exact_rows = conn.execute(
                        f"""SELECT c.id, c.doc_id, c.text, c.page_num, c.heading,
                                   c.chunk_index, d.filename AS doc_name
                            FROM chunks c
                            JOIN documents d ON d.id = c.doc_id
                            WHERE (COALESCE(c.heading, '') || CHAR(10) || c.text) REGEXP ?
                                  AND d.status = 'ready'
                                  {collection_clause}
                            ORDER BY c.chunk_index
                            LIMIT ?""",
                        exact_params,
                    ).fetchall()
                    for row in exact_rows:
                        existing = rows_by_id.get(row["id"])
                        if existing:
                            existing[2].append("exact")
                        else:
                            rows_by_id[row["id"]] = (row, 1.0, ["exact"])
        except sqlite3.OperationalError as error:
            logger.warning("FTS5 chunk search unavailable, using vectors only: %s", error)
            return []

        return [
            RetrievedChunk(
                chunk_id=row["id"],
                text=row["text"],
                score=0.0,
                doc_id=row["doc_id"],
                doc_name=row["doc_name"],
                page_num=row["page_num"],
                chunk_index=row["chunk_index"],
                heading=row["heading"],
                lexical_score=lexical_score,
                retrieval_sources=sources,
            )
            for row, lexical_score, sources in list(rows_by_id.values())[:limit]
        ]

    def _fuse(
        self,
        vector_chunks: list[RetrievedChunk],
        lexical_chunks: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        rankings = [
            [chunk.chunk_id for chunk in vector_chunks],
            [chunk.chunk_id for chunk in lexical_chunks],
        ]
        fused_scores = reciprocal_rank_fusion(rankings, self.rrf_k)
        max_score = 2.0 / (self.rrf_k + 1)

        by_id = {chunk.chunk_id: chunk for chunk in lexical_chunks}
        for chunk in vector_chunks:
            existing = by_id.get(chunk.chunk_id)
            if existing:
                existing.vector_score = chunk.vector_score
                existing.retrieval_sources = ["vector", *existing.retrieval_sources]
            else:
                by_id[chunk.chunk_id] = chunk

        for chunk_id, chunk in by_id.items():
            chunk.score = min(fused_scores[chunk_id] / max_score, 1.0)
        return list(by_id.values())

    @staticmethod
    def _apply_quality_penalty(chunks: list[RetrievedChunk]) -> None:
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        if not chunk_ids:
            return

        try:
            with get_db() as conn:
                placeholders = ",".join("?" for _ in chunk_ids)
                rows = conn.execute(
                    f"""SELECT chunk_id, is_low_quality
                        FROM chunk_quality
                        WHERE chunk_id IN ({placeholders})""",
                    chunk_ids,
                ).fetchall()
            low_quality_ids = {row["chunk_id"] for row in rows if row["is_low_quality"]}
            for chunk in chunks:
                if chunk.chunk_id in low_quality_ids:
                    chunk.score *= 0.8
        except Exception as error:
            logger.debug("Quality scoring skipped (non-critical): %s", error)

    @staticmethod
    def _apply_query_coverage_boost(query: str, chunks: list[RetrievedChunk]) -> None:
        """Nudge chunks that preserve more distinctive words from the user query."""
        terms = extract_query_boost_terms(query)
        if not terms:
            return

        for chunk in chunks:
            haystack = f"{chunk.heading or ''}\n{chunk.text}".lower()
            matched_count = sum(1 for term in terms if term in haystack)
            if matched_count:
                chunk.score *= min(1.0 + matched_count * 0.06, 1.24)

    @staticmethod
    def _apply_answerability_penalty(chunks: list[RetrievedChunk]) -> None:
        """Deprioritize meta-text that says it does not answer the topic."""
        for chunk in chunks:
            if _META_NEGATION_RE.search(chunk.text):
                chunk.score *= 0.55
                if chunk.lexical_score is not None:
                    chunk.lexical_score *= 0.55
