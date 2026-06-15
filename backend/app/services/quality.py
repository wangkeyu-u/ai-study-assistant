"""Chunk quality scoring — evaluates information density of text chunks.

Low-quality chunks (table of contents, copyright notices, blank pages, headers/footers)
are flagged so they can be deprioritized during retrieval.

Scoring criteria:
- Text length (too short = low quality)
- Character diversity (repetitive text = low quality)
- Stop word ratio (very high ratio = low quality)
- Digit/special char ratio (very high = likely page numbers, headers)
"""

import logging
import re

logger = logging.getLogger(__name__)

# Common Chinese stop words (abbreviated)
STOP_WORDS_ZH = set("的了是在不有我他她它们这那和与或而且如果虽然但是因为所以")
STOP_WORDS_EN = set(
    "the a an is are was were be been being have has had do does did will would shall should may might can could i you he she it we they me him her us them my your his its our their this that these those and or but not no nor so yet"
)


def score_chunk_quality(text: str) -> dict:
    """Score a chunk's information density.

    Returns:
        dict with:
        - info_density: float 0.0-1.0 (higher = better quality)
        - is_low_quality: bool (True if chunk should be deprioritized)
        - reason: str | None (why it's low quality, if applicable)
    """
    if not text or not text.strip():
        return {"info_density": 0.0, "is_low_quality": True, "reason": "空文本"}

    stripped = text.strip()
    text_len = len(stripped)

    # Rule 1: Too short (< 20 chars)
    if text_len < 20:
        return {"info_density": 0.1, "is_low_quality": True, "reason": "文本过短"}

    # Rule 2: Character diversity
    unique_chars = len(set(stripped))
    diversity = unique_chars / min(text_len, 200)  # normalize

    # Rule 3: Digit/special char ratio (page numbers, headers/footers)
    digit_count = sum(1 for c in stripped if c.isdigit())
    special_count = sum(1 for c in stripped if not c.isalnum() and not c.isspace())
    digit_ratio = digit_count / text_len
    special_ratio = special_count / text_len

    # Rule 4: Repetition detection
    lines = stripped.split("\n")
    unique_lines = set(line.strip() for line in lines if line.strip())
    line_repetition = 1 - (len(unique_lines) / max(len(lines), 1))

    # Rule 5: Common low-quality patterns
    low_quality_patterns = [
        r"^\s*目\s*录\s*$",
        r"^\s*contents?\s*$",
        r"^\s*copyright",
        r"^\s*©\s",
        r"^\s*all rights reserved",
        r"^\s*isbn[\s\d-]+$",
        r"^\s*第\s*\d+\s*页",
        r"^\s*page\s*\d+",
    ]
    for pattern in low_quality_patterns:
        if re.search(pattern, stripped, re.IGNORECASE | re.MULTILINE):
            return {
                "info_density": 0.1,
                "is_low_quality": True,
                "reason": "匹配低质量模式（目录/版权/页码）",
            }

    # Composite score
    score = 0.5  # base score
    score += diversity * 0.3  # reward diversity
    score -= digit_ratio * 0.5  # penalize high digit ratio
    score -= line_repetition * 0.3  # penalize repetition
    score += min(text_len / 500, 0.2)  # reward reasonable length (cap at 500)

    # Penalize very high special char ratio (formulas/tables are ok but headers aren't)
    if special_ratio > 0.3 and text_len < 100:
        score -= 0.3

    info_density = max(0.0, min(1.0, score))
    is_low_quality = info_density < 0.25

    reason = None
    if is_low_quality:
        if diversity < 0.1:
            reason = "字符重复率过高"
        elif digit_ratio > 0.3:
            reason = "数字占比过高"
        elif line_repetition > 0.7:
            reason = "行重复率过高"
        else:
            reason = "信息密度低于阈值"

    return {
        "info_density": round(info_density, 3),
        "is_low_quality": is_low_quality,
        "reason": reason,
    }


def batch_score_chunks(chunk_texts: list[str]) -> list[dict]:
    """Score multiple chunks at once."""
    return [score_chunk_quality(text) for text in chunk_texts]
