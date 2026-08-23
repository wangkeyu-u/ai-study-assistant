"""Language detection and response-language helpers for multilingual RAG."""

from __future__ import annotations

import re
from typing import Literal

from app.db.database import get_db

LanguageCode = Literal["zh", "en", "mixed", "unknown"]
AnswerLanguage = Literal["auto", "zh", "en"]

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_text_language(text: str) -> LanguageCode:
    """Detect whether meaningful text is primarily Chinese, English, or mixed."""
    cjk_count = len(_CJK_RE.findall(text))
    latin_count = len(_LATIN_RE.findall(text))
    meaningful = cjk_count + latin_count
    if meaningful < 2:
        return "unknown"

    cjk_ratio = cjk_count / meaningful
    if cjk_ratio >= 0.6:
        return "zh"
    if cjk_ratio <= 0.15:
        return "en"
    return "mixed"


def detect_corpus_languages(
    collection_id: str | None = None,
    document_ids: list[str] | None = None,
    *,
    sample_limit: int = 64,
) -> list[LanguageCode]:
    """Sample indexed chunks in the active scope and return their languages."""
    clauses = ["d.status = 'ready'"]
    params: list[str | int] = []
    if collection_id:
        clauses.append("d.collection_id = ?")
        params.append(collection_id)
    unique_document_ids = list(dict.fromkeys(document_ids or []))
    if unique_document_ids:
        placeholders = ",".join("?" for _ in unique_document_ids)
        clauses.append(f"d.id IN ({placeholders})")
        params.extend(unique_document_ids)
    params.append(max(1, sample_limit))

    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT c.text
                FROM documents d
                JOIN chunks c ON c.doc_id = d.id
                    AND c.is_active = 1
                    AND c.chunk_index = (
                        SELECT MIN(c2.chunk_index) FROM chunks c2
                        WHERE c2.doc_id = d.id AND c2.is_active = 1
                    )
                WHERE {" AND ".join(clauses)}
                ORDER BY d.created_at DESC, c.chunk_index
                LIMIT ?""",
            params,
        ).fetchall()

    languages: list[LanguageCode] = []
    for row in rows:
        language = detect_text_language(row["text"])
        if language != "unknown" and language not in languages:
            languages.append(language)
    return languages


def translation_targets(
    query_language: LanguageCode, corpus_languages: list[LanguageCode]
) -> list[str]:
    """Return useful target languages for cross-language retrieval expansion."""
    targets: list[str] = []
    corpus_has_english = any(language in {"en", "mixed"} for language in corpus_languages)
    corpus_has_chinese = any(language in {"zh", "mixed"} for language in corpus_languages)
    if query_language == "zh" and corpus_has_english:
        targets.append("en")
    elif query_language == "en" and corpus_has_chinese:
        targets.append("zh")
    return targets


def resolve_answer_language(requested: AnswerLanguage, query: str) -> Literal["zh", "en"]:
    """Resolve auto mode to the user's question language."""
    if requested in {"zh", "en"}:
        return requested
    return "en" if detect_text_language(query) == "en" else "zh"


def answer_language_instruction(requested: AnswerLanguage, query: str) -> str:
    """Build an explicit instruction independent from the source language."""
    resolved = resolve_answer_language(requested, query)
    if resolved == "en":
        return (
            "Answer entirely in English, even when the source material is Chinese. "
            "Keep names, numbers, code, and technical terms faithful to the source."
        )
    return (
        "请全部使用中文回答，即使参考资料是英文。专有名词首次出现时可保留英文原文，"
        "数字、代码和技术含义必须忠实于资料。"
    )


def insufficient_context_message(requested: AnswerLanguage, query: str) -> str:
    if resolve_answer_language(requested, query) == "en":
        return (
            "I could not find enough evidence in the current sources to answer this question. "
            "Please add relevant material or rephrase the question."
        )
    return "根据现有资料，没有找到足够的信息来回答这个问题。请补充相关资料或换一种问法。"
