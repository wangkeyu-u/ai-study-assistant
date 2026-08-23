"""RAG capability and readiness endpoints for interview/demo mode."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.db.database import get_db
from app.dependencies import get_rag_pipeline

router = APIRouter(prefix="/api/rag", tags=["rag"])


def _status(enabled: bool) -> str:
    return "enabled" if enabled else "optional"


@router.get("/readiness")
async def get_rag_readiness():
    """Return an interview-friendly overview of the RAG system.

    This is deliberately read-only and cheap: it summarizes the live pipeline,
    data footprint, architectural modules, quality gates, and demo talking points
    without calling an LLM.
    """
    settings = get_settings()
    pipeline = get_rag_pipeline()
    vector_store = pipeline.vector_store

    with get_db() as conn:
        total_docs = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()["c"]
        ready_docs = conn.execute(
            "SELECT COUNT(*) AS c FROM documents WHERE status='ready'"
        ).fetchone()["c"]
        total_chunks = conn.execute(
            "SELECT COUNT(*) AS c FROM chunks WHERE is_active=1"
        ).fetchone()["c"]
        total_sessions = conn.execute("SELECT COUNT(*) AS c FROM chat_sessions").fetchone()["c"]
        total_citations = conn.execute("SELECT COUNT(*) AS c FROM citations").fetchone()["c"]

    feature_checks = [
        ("Document ingestion", ready_docs > 0),
        ("Hybrid retrieval", settings.hybrid_search_enabled),
        ("Query planning", settings.query_decomposition_enabled),
        ("Cross-language retrieval", settings.cross_language_retrieval_enabled),
        ("Intent-aware prompting", settings.intent_aware_prompt_enabled),
        ("Context optimization", settings.context_max_chunks > 0),
        ("Coverage gate", settings.context_min_coverage_score > 0),
        ("Citation validation", True),
        ("Debug observability", True),
        ("Local-first storage", True),
    ]
    readiness_score = round(
        sum(1 for _name, enabled in feature_checks if enabled) / len(feature_checks),
        3,
    )

    modules = [
        {
            "id": "ingestion",
            "label": "Ingestion",
            "status": "enabled",
            "summary": "Parse PDFs, Markdown, TXT, and notes into overlapping chunks with metadata.",
            "talking_points": [
                "Local-first document storage",
                "PDF typography and document headings define semantic chunk boundaries",
                "Chunk metadata keeps page, heading, document, and collection context",
                "Chunk quality scoring deprioritizes low-information text",
            ],
        },
        {
            "id": "multilingual",
            "label": "Multilingual Retrieval",
            "status": _status(settings.cross_language_retrieval_enabled),
            "summary": "Retrieve across Chinese and English sources independently from the answer language.",
            "talking_points": [
                "Corpus language is detected inside the active document scope",
                "Original and translated queries are fused with RRF",
                "Users can force a Chinese or English answer without changing retrieval",
            ],
        },
        {
            "id": "retrieval",
            "label": "Hybrid Retrieval",
            "status": _status(settings.hybrid_search_enabled),
            "summary": "Combine ChromaDB dense vectors with SQLite FTS5 lexical search and RRF fusion.",
            "talking_points": [
                "Dense retrieval handles semantic questions",
                "FTS5 and exact-term matching recover keywords, acronyms, and IDs",
                "RRF fuses rankings without overfitting to one retriever",
            ],
        },
        {
            "id": "planning",
            "label": "Query Planning",
            "status": _status(settings.query_decomposition_enabled),
            "summary": "Rewrite follow-up questions, classify intent, and decompose compound tasks.",
            "talking_points": [
                "Comparison, summary, process, definition, and evidence-first intents",
                "Multi-hop questions are split into focused subqueries",
                "The original user wording is preserved for final generation",
            ],
        },
        {
            "id": "context",
            "label": "Context Optimization",
            "status": "enabled",
            "summary": "Select compact evidence with intent-aware MMR, document coverage, and token budgeting.",
            "talking_points": [
                f"Retrieval candidates: {settings.context_candidate_top_k}",
                f"Generation context cap: {settings.context_max_chunks} chunks / {settings.context_max_chars} chars",
                f"Adjacent evidence expansion: up to {settings.context_max_neighbors} chunks",
                "Coverage gate rejects weak vector-only context before LLM spend",
            ],
        },
        {
            "id": "generation",
            "label": "Grounded Generation",
            "status": "enabled",
            "summary": "Answer with task-specific structure while enforcing citation rules.",
            "talking_points": [
                "Comparison questions become evidence-backed tables",
                "Process questions become step-by-step explanations",
                "Every factual sentence must cite retrieved evidence",
            ],
        },
        {
            "id": "observability",
            "label": "Observability",
            "status": "enabled",
            "summary": "Expose query rewriting, subqueries, intent, context strategy, scores, latency, and token usage.",
            "talking_points": [
                "Debug Panel makes RAG behavior inspectable",
                "Coverage and confidence decisions are visible",
                "Token and latency breakdown supports cost/performance tradeoffs",
            ],
        },
    ]

    quality_gates = [
        {
            "name": "Confidence gate",
            "enabled": settings.retrieval_confidence_gate_enabled,
            "description": "Rejects low-confidence vector-only retrieval results.",
        },
        {
            "name": "Context coverage gate",
            "enabled": settings.context_min_coverage_score > 0,
            "description": "Rejects context whose lexical anchors do not cover the user query.",
        },
        {
            "name": "Citation validation",
            "enabled": True,
            "description": "Rejects answers with missing or out-of-range sentence-level citations.",
        },
        {
            "name": "Offline evaluation",
            "enabled": True,
            "description": "Includes retrieval and answer-quality eval scripts for regression checks.",
        },
    ]

    demo_script = [
        {
            "title": "Grounded Q&A",
            "prompt": "这个系统通过哪些机制降低 RAG 回答中的幻觉风险？",
            "what_to_show": "Citations, source preview, and Debug Panel retrieval sources.",
        },
        {
            "title": "Multi-hop synthesis",
            "prompt": "混合检索、多跳查询和质量评估是如何协同工作的？",
            "what_to_show": "Retrieval subqueries, RRF fusion, and intent-aware context strategy.",
        },
        {
            "title": "Cross-language Q&A",
            "prompt": "用中文询问英文资料，并分别切换中文和英文回答。",
            "what_to_show": "Translated retrieval query, corpus language, and answer-language control.",
        },
        {
            "title": "Safe refusal",
            "prompt": "资料是否说明量子计算会在 2028 年全面替代 GPU？",
            "what_to_show": "No-answer behavior, confidence/coverage gate, and zero-citation response.",
        },
    ]

    return {
        "readiness_score": readiness_score,
        "data": {
            "documents_total": total_docs,
            "documents_ready": ready_docs,
            "chunks": total_chunks,
            "vectors": vector_store.count(),
            "sessions": total_sessions,
            "citations": total_citations,
        },
        "runtime": {
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "vector_store_healthy": vector_store.health_check(),
        },
        "modules": modules,
        "quality_gates": quality_gates,
        "demo_script": demo_script,
    }
