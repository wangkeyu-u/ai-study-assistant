"""Deterministic citation coverage checks for generated answers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CITATION_RE = re.compile(r"\[(\d+)\]")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？!?])")
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+")
_MARKDOWN_RULE_RE = re.compile(r"^\s*(?:[-*_]\s*){3,}$")
_TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
_EMPHASIZED_LABEL_RE = re.compile(r"^(?:\*\*|__)[^*_]+(?:\*\*|__)[:：]?$", re.DOTALL)
_REFUSAL_MARKERS = (
    "没有找到足够的信息",
    "无法根据现有资料",
    "资料不足",
    "无法生成带有可靠引用",
    "could not find enough evidence",
    "could not produce an answer with reliable source citations",
    "insufficient evidence",
)


@dataclass
class CitationValidationResult:
    """Sentence-level citation validation summary."""

    valid: bool
    factual_sentence_count: int = 0
    cited_sentence_count: int = 0
    invalid_citation_count: int = 0
    missing_citation_sentences: list[str] = field(default_factory=list)

    @property
    def citation_completeness(self) -> float:
        if self.factual_sentence_count == 0:
            return 1.0
        return self.cited_sentence_count / self.factual_sentence_count


def is_refusal(answer: str) -> bool:
    """Return whether an answer is an explicit insufficient-context refusal."""
    lowered = answer.lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


def citation_refs(text: str) -> list[int]:
    """Extract all numeric citation references from answer text."""
    return [int(value) for value in _CITATION_RE.findall(text)]


def _is_table_row(line: str) -> bool:
    return "|" in line and len(line.strip("| ").split("|")) >= 2


def _is_table_separator(line: str) -> bool:
    if not _is_table_row(line):
        return False
    cells = [cell.strip() for cell in line.strip("| ").split("|")]
    return bool(cells) and all(_TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells)


def _next_content_line(lines: list[str], start: int) -> str:
    for line in lines[start:]:
        if line.strip():
            return line.strip()
    return ""


def split_factual_sentences(answer: str) -> list[str]:
    """Split factual prose while ignoring Markdown structure and code blocks.

    Models often format comparison answers as tables. Headings, table headers,
    separators, and labels are presentation structure rather than factual claims;
    counting them as uncited sentences causes valid grounded answers to be refused.
    """
    sentences: list[str] = []
    lines = answer.splitlines()
    in_code_block = False

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if not line or in_code_block:
            continue
        if _MARKDOWN_HEADING_RE.match(line) or _MARKDOWN_RULE_RE.fullmatch(line):
            continue
        if _EMPHASIZED_LABEL_RE.fullmatch(line):
            continue
        if _is_table_separator(line):
            continue
        if _is_table_row(line):
            next_line = _next_content_line(lines, index + 1)
            if _is_table_separator(next_line):
                continue
            parts = [line]
        else:
            # Lines such as "核心区别：" introduce the facts that follow.
            if line.endswith(("：", ":")) and not citation_refs(line):
                continue
            parts = _SENTENCE_BOUNDARY_RE.split(line)

        for part in parts:
            sentence = part.strip().lstrip("-•* ")
            sentence = re.sub(r"^\d+[.)、]\s*", "", sentence)
            content = _CITATION_RE.sub("", sentence).strip().strip("|").strip()
            if len(content) < 4 or is_refusal(content):
                continue
            sentences.append(sentence)
    return sentences


def validate_citation_coverage(answer: str, context_count: int) -> CitationValidationResult:
    """Validate that every factual sentence cites an in-range context."""
    refs = citation_refs(answer)
    invalid_count = sum(1 for ref in refs if ref < 1 or ref > context_count)
    if is_refusal(answer):
        return CitationValidationResult(
            valid=invalid_count == 0,
            invalid_citation_count=invalid_count,
        )

    factual_sentences = split_factual_sentences(answer)
    cited_sentence_count = 0
    missing_sentences = []
    for sentence in factual_sentences:
        sentence_refs = citation_refs(sentence)
        has_valid_ref = any(1 <= ref <= context_count for ref in sentence_refs)
        if has_valid_ref:
            cited_sentence_count += 1
        else:
            missing_sentences.append(sentence)

    return CitationValidationResult(
        valid=invalid_count == 0 and not missing_sentences,
        factual_sentence_count=len(factual_sentences),
        cited_sentence_count=cited_sentence_count,
        invalid_citation_count=invalid_count,
        missing_citation_sentences=missing_sentences,
    )
