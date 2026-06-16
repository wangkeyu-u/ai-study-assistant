"""Deterministic citation coverage checks for generated answers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CITATION_RE = re.compile(r"\[(\d+)\]")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？!?])|\n+")
_REFUSAL_MARKERS = ("没有找到足够的信息", "无法根据现有资料", "资料不足")


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
    return any(marker in answer for marker in _REFUSAL_MARKERS)


def citation_refs(text: str) -> list[int]:
    """Extract all numeric citation references from answer text."""
    return [int(value) for value in _CITATION_RE.findall(text)]


def split_factual_sentences(answer: str) -> list[str]:
    """Split answer prose while excluding headings and explicit refusals."""
    sentences = []
    for part in _SENTENCE_BOUNDARY_RE.split(answer):
        sentence = part.strip().lstrip("-•*# ")
        content = _CITATION_RE.sub("", sentence).strip()
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
