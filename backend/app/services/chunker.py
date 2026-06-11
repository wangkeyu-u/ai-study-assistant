"""Text chunker with paragraph awareness and token-count fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """A chunk of text with metadata."""
    text: str
    chunk_index: int
    page_num: int | None = None
    heading: str | None = None
    token_count: int = 0


class TextChunker:
    """Split parsed text into overlapping chunks.

    Strategy:
      1. Split text into paragraphs (by double newline or single newline).
      2. Accumulate paragraphs into a chunk until token budget is exceeded.
      3. If a single paragraph exceeds the budget, split it by sentences.
      4. Add overlap from the tail of the previous chunk.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(
        self,
        text: str,
        page_num: int | None = None,
        heading: str | None = None,
    ) -> list[Chunk]:
        """Split a single text block into chunks."""
        paragraphs = self._split_paragraphs(text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        if not paragraphs:
            return []

        chunks: list[Chunk] = []
        current_parts: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)

            # If a single paragraph exceeds chunk_size, split by sentences
            if para_tokens > self.chunk_size:
                # Flush current buffer first
                if current_parts:
                    chunks.append(self._make_chunk(
                        current_parts, len(chunks), page_num, heading,
                    ))
                    current_parts = []
                    current_tokens = 0

                # Split long paragraph by sentences
                sentence_chunks = self._split_long_paragraph(
                    para, page_num, heading, len(chunks),
                )
                chunks.extend(sentence_chunks)
                continue

            # Would this paragraph push us over the budget?
            if current_tokens + para_tokens > self.chunk_size and current_parts:
                chunks.append(self._make_chunk(
                    current_parts, len(chunks), page_num, heading,
                ))
                # Keep overlap: tail of current chunk
                overlap_text = self._get_overlap_text(current_parts)
                current_parts = [overlap_text] if overlap_text else []
                current_tokens = self._estimate_tokens(
                    current_parts[0]
                ) if current_parts else 0

            current_parts.append(para)
            current_tokens += para_tokens

        # Flush remaining
        if current_parts:
            chunks.append(self._make_chunk(
                current_parts, len(chunks), page_num, heading,
            ))

        # Re-index sequentially
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        return chunks

    def chunk_segments(
        self,
        segments: list,   # list of ParsedSegment
    ) -> list[Chunk]:
        """Chunk multiple segments (from a parsed document) with global indexing."""
        all_chunks: list[Chunk] = []
        for seg in segments:
            seg_chunks = self.chunk_text(
                text=seg.text,
                page_num=seg.page_num,
                heading=seg.heading,
            )
            all_chunks.extend(seg_chunks)

        # Re-index globally
        for i, chunk in enumerate(all_chunks):
            chunk.chunk_index = i

        return all_chunks

    # ── Internal helpers ───────────────────────────────────

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text by double newline (paragraph breaks)."""
        return re.split(r"\n\s*\n", text)

    def _split_long_paragraph(
        self,
        text: str,
        page_num: int | None,
        heading: str | None,
        start_index: int,
    ) -> list[Chunk]:
        """Split a long paragraph by sentence boundaries."""
        # Chinese and English sentence endings
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks: list[Chunk] = []
        current_parts: list[str] = []
        current_tokens = 0

        for sent in sentences:
            sent_tokens = self._estimate_tokens(sent)

            if current_tokens + sent_tokens > self.chunk_size and current_parts:
                chunks.append(self._make_chunk(
                    current_parts, start_index + len(chunks), page_num, heading,
                ))
                overlap_text = self._get_overlap_text(current_parts)
                current_parts = [overlap_text] if overlap_text else []
                current_tokens = self._estimate_tokens(
                    current_parts[0]
                ) if current_parts else 0

            current_parts.append(sent)
            current_tokens += sent_tokens

        if current_parts:
            chunks.append(self._make_chunk(
                current_parts, start_index + len(chunks), page_num, heading,
            ))

        return chunks

    def _make_chunk(
        self,
        parts: list[str],
        index: int,
        page_num: int | None,
        heading: str | None,
    ) -> Chunk:
        text = "\n".join(parts)
        return Chunk(
            text=text,
            chunk_index=index,
            page_num=page_num,
            heading=heading,
            token_count=self._estimate_tokens(text),
        )

    def _get_overlap_text(self, parts: list[str]) -> str:
        """Get the tail of the current chunk for overlap."""
        full_text = "\n".join(parts)
        # Take last N tokens worth of characters (rough estimate)
        overlap_chars = self.chunk_overlap * 2  # ~2 chars per token for Chinese
        if len(full_text) <= overlap_chars:
            return full_text
        return full_text[-overlap_chars:]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation: ~2 chars per token for Chinese, ~4 for English."""
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
