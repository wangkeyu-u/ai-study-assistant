"""Rule-based query understanding for the RAG pipeline.

The goal is not to replace an LLM planner. It gives the pipeline a cheap,
deterministic first pass so retrieval, context selection, and prompting can use
the same interpretation of the user's task.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.retriever import extract_cjk_phrases

_EN_TERM_RE = re.compile(r"[A-Za-z0-9_]{2,}")
_QUESTION_WORDS = {
    "什么",
    "哪些",
    "哪个",
    "如何",
    "怎样",
    "是否",
    "请问",
    "说明",
    "解释",
    "介绍",
    "总结",
}
_STOP_TERMS = {
    "the",
    "and",
    "for",
    "with",
    "what",
    "how",
    "why",
    "请问",
    "说明",
    "解释",
    "介绍",
    "总结",
    "这个",
    "这些",
    "资料",
    "文档",
}


@dataclass(frozen=True)
class QueryProfile:
    """Structured understanding of a user question."""

    intent: str = "qa"
    answer_style: str = "grounded"
    keywords: list[str] = field(default_factory=list)
    requires_comparison: bool = False
    requires_summary: bool = False
    requires_steps: bool = False
    requires_evidence: bool = False


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def extract_keywords(query: str, max_terms: int = 12) -> list[str]:
    """Extract stable lexical anchors from mixed Chinese/English queries."""
    terms: list[str] = []

    def add(term: str) -> None:
        normalized = term.strip().lower()
        if not normalized or normalized in _STOP_TERMS or normalized in terms:
            return
        if any(word in normalized for word in _QUESTION_WORDS):
            return
        terms.append(normalized)

    for term in _EN_TERM_RE.findall(query):
        add(term)

    for phrase in extract_cjk_phrases(query):
        if len(phrase) <= 10:
            add(phrase)
            continue
        for width in (4, 3):
            for index in range(len(phrase) - width + 1):
                add(phrase[index : index + width])
                if len(terms) >= max_terms:
                    return terms

    return terms[:max_terms]


def analyze_query(query: str) -> QueryProfile:
    """Classify the query into a small set of RAG answer intents."""
    is_comparison = _contains_any(
        query,
        ("对比", "比较", "区别", "差异", "共同", "冲突", "compare", "difference", "versus", "vs"),
    )
    is_summary = _contains_any(query, ("总结", "概括", "摘要", "梳理", "summary", "summarize"))
    is_process = _contains_any(
        query,
        ("步骤", "流程", "过程", "怎么做", "如何实现", "pipeline", "workflow", "step"),
    )
    is_definition = _contains_any(
        query,
        ("是什么", "定义", "概念", "含义", "what is", "define", "definition"),
    )
    is_evidence = _contains_any(
        query,
        ("依据", "证据", "引用", "原文", "来源", "根据", "evidence", "source", "citation"),
    )

    if is_comparison:
        intent = "comparison"
        answer_style = "compare"
    elif is_summary:
        intent = "summary"
        answer_style = "brief_then_detail"
    elif is_process:
        intent = "process"
        answer_style = "steps"
    elif is_definition:
        intent = "definition"
        answer_style = "define_then_explain"
    elif is_evidence:
        intent = "evidence"
        answer_style = "evidence_first"
    else:
        intent = "qa"
        answer_style = "grounded"

    return QueryProfile(
        intent=intent,
        answer_style=answer_style,
        keywords=extract_keywords(query),
        requires_comparison=is_comparison,
        requires_summary=is_summary,
        requires_steps=is_process,
        requires_evidence=is_evidence,
    )


def build_response_instructions(profile: QueryProfile) -> str:
    """Return prompt instructions tailored to the detected task."""
    common = (
        "回答必须直接服务于用户问题。所有事实性句子仍必须在句末给出 [编号] 引用。"
        "如果证据不足，请明确说出缺口，不要补常识。"
    )
    style_map = {
        "compare": (
            "请优先用对比表回答，包含相同点、差异点、冲突或不确定处、综合结论。"
            "每个表格单元格或要点都要带引用。"
        ),
        "brief_then_detail": "先给 3 条以内结论摘要，再展开关键依据和限制。",
        "steps": "按步骤说明流程，每一步说明输入、处理、输出或目的。",
        "define_then_explain": "先用一句话定义，再说明组成部分、作用和资料中的例子。",
        "evidence_first": "先列出可验证证据，再给结论，并单独说明资料没有覆盖的部分。",
        "grounded": "用短段落或项目符号回答，优先保留资料中的关键术语。",
    }
    return f"{common}\n回答结构：{style_map.get(profile.answer_style, style_map['grounded'])}"
