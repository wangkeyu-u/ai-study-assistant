"""Structure-aware text chunking for Chinese and English documents."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """A chunk of text with source metadata."""

    text: str
    chunk_index: int
    page_num: int | None = None
    heading: str | None = None
    token_count: int = 0

    @property
    def embedding_text(self) -> str:
        """Include the section title in embeddings without duplicating citation text."""
        return f"{self.heading}\n{self.text}" if self.heading else self.text


@dataclass(frozen=True)
class _TextAtom:
    text: str
    heading: str | None


_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_NUMBERED_HEADING_RE = re.compile(
    r"^(?:chapter\s+\d+|section\s+\d+|\d+(?:\.\d+){0,4}|"
    r"第[一二三四五六七八九十百0-9]+[章节部分]|[一二三四五六七八九十]+[、.])"
    r"(?:\s+|(?=[^\d.]))(.+)$",
    re.IGNORECASE,
)
_BULLET_RE = re.compile(r"^(?:[-*•·]\s+|\d+[.)]\s+|[A-Za-z][.)]\s+)")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？!?])\s*|(?<=\.)(?=\s+[A-Z0-9])")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


class TextChunker:
    """Split documents on structure and sentence boundaries with clean overlap.

    The chunker treats headings, paragraphs, and list items as semantic boundaries.
    Overlap is copied as complete sentences instead of raw character tails, avoiding
    clipped words and half-sentences that reduce retrieval and answer quality.
    """

    def __init__(self, chunk_size: int = 384, chunk_overlap: int = 64):
        self.chunk_size = max(16, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size // 2))

    def chunk_text(
        self,
        text: str,
        page_num: int | None = None,
        heading: str | None = None,
    ) -> list[Chunk]:
        """Split a text block while preserving inferred and explicit headings."""
        atoms = self._build_atoms(text, heading)
        if not atoms:
            return []

        chunks: list[Chunk] = []
        current: list[_TextAtom] = []
        current_tokens = 0

        for atom in atoms:
            atom_tokens = self._estimate_tokens(atom.text)
            if current and atom.heading != current[-1].heading:
                chunks.append(self._make_chunk(current, len(chunks), page_num))
                current = []
                current_tokens = 0

            if current and current_tokens + atom_tokens > self.chunk_size:
                chunks.append(self._make_chunk(current, len(chunks), page_num))
                overlap = self._overlap_atoms(current)
                overlap_tokens = sum(self._estimate_tokens(item.text) for item in overlap)
                if overlap_tokens + atom_tokens > self.chunk_size:
                    overlap = []
                    overlap_tokens = 0
                current = overlap
                current_tokens = overlap_tokens

            current.append(atom)
            current_tokens += atom_tokens

        if current:
            chunks.append(self._make_chunk(current, len(chunks), page_num))

        return chunks

    def chunk_segments(self, segments: list) -> list[Chunk]:
        """Chunk parsed segments and assign document-global indices."""
        all_chunks: list[Chunk] = []
        for segment in segments:
            all_chunks.extend(
                self.chunk_text(
                    text=segment.text,
                    page_num=segment.page_num,
                    heading=segment.heading,
                )
            )
        for index, chunk in enumerate(all_chunks):
            chunk.chunk_index = index
        return all_chunks

    def _build_atoms(self, text: str, default_heading: str | None) -> list[_TextAtom]:
        atoms: list[_TextAtom] = []
        for paragraph, paragraph_heading in self._extract_paragraphs(text, default_heading):
            for sentence in self._split_sentences(paragraph):
                for piece in self._split_oversized_atom(sentence):
                    if piece.strip():
                        atoms.append(_TextAtom(piece.strip(), paragraph_heading))
        return atoms

    def _extract_paragraphs(
        self, text: str, default_heading: str | None
    ) -> list[tuple[str, str | None]]:
        """Normalize PDF line wrapping and preserve visible structural boundaries."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        paragraphs: list[tuple[str, str | None]] = []
        buffer: list[str] = []
        active_heading = default_heading

        def flush() -> None:
            if not buffer:
                return
            joined = self._join_wrapped_lines(buffer).strip()
            if joined:
                paragraphs.append((joined, active_heading))
            buffer.clear()

        for raw_line in text.split("\n"):
            line = re.sub(r"[ \t]+", " ", raw_line).strip()
            if not line:
                flush()
                continue

            inferred_heading = self._detect_heading(line)
            if inferred_heading:
                flush()
                active_heading = inferred_heading
                continue

            if _BULLET_RE.match(line):
                flush()
                paragraphs.append((line, active_heading))
                continue

            buffer.append(line)

        flush()
        return paragraphs

    @staticmethod
    def _detect_heading(line: str) -> str | None:
        markdown_match = _MARKDOWN_HEADING_RE.match(line)
        if markdown_match:
            return markdown_match.group(1).strip()

        if len(line) <= 100 and _NUMBERED_HEADING_RE.match(line):
            return line.strip(" #:：")

        letters = [character for character in line if character.isascii() and character.isalpha()]
        if (
            2 <= len(letters) <= 60
            and len(line.split()) <= 10
            and not _CJK_RE.search(line)
            and all(character.isupper() for character in letters)
        ):
            return line.strip(" #:：")
        return None

    @staticmethod
    def _join_wrapped_lines(lines: list[str]) -> str:
        if not lines:
            return ""
        result = lines[0]
        for line in lines[1:]:
            if result.endswith("-") and line[:1].isalpha():
                result = f"{result[:-1]}{line}"
                continue
            left_is_cjk = bool(result and _CJK_RE.match(result[-1]))
            right_is_cjk = bool(line and _CJK_RE.match(line[0]))
            separator = "" if left_is_cjk and right_is_cjk else " "
            result = f"{result}{separator}{line}"
        return result

    @staticmethod
    def _split_sentences(paragraph: str) -> list[str]:
        if _BULLET_RE.match(paragraph):
            return [paragraph]
        return [part.strip() for part in _SENTENCE_BOUNDARY_RE.split(paragraph) if part.strip()]

    def _split_oversized_atom(self, text: str) -> list[str]:
        if self._estimate_tokens(text) <= self.chunk_size:
            return [text]

        words = re.findall(r"\S+\s*", text)
        if len(words) > 1:
            pieces: list[str] = []
            current = ""
            for word in words:
                candidate = f"{current}{word}"
                if current and self._estimate_tokens(candidate) > self.chunk_size:
                    pieces.append(current.strip())
                    current = word
                else:
                    current = candidate
            if current.strip():
                pieces.append(current.strip())
            if all(self._estimate_tokens(piece) <= self.chunk_size for piece in pieces):
                return pieces

        # A long unspaced CJK sentence or identifier stream needs a hard fallback.
        char_budget = max(1, int(self.chunk_size * 1.45))
        return [text[index : index + char_budget] for index in range(0, len(text), char_budget)]

    def _overlap_atoms(self, atoms: list[_TextAtom]) -> list[_TextAtom]:
        if self.chunk_overlap <= 0:
            return []
        selected: list[_TextAtom] = []
        tokens = 0
        for atom in reversed(atoms):
            atom_tokens = self._estimate_tokens(atom.text)
            if atom_tokens > self.chunk_overlap or tokens + atom_tokens > self.chunk_overlap:
                break
            selected.append(atom)
            tokens += atom_tokens
        return list(reversed(selected))

    def _make_chunk(self, atoms: list[_TextAtom], index: int, page_num: int | None) -> Chunk:
        text = "\n".join(atom.text for atom in atoms).strip()
        return Chunk(
            text=text,
            chunk_index=index,
            page_num=page_num,
            heading=atoms[0].heading if atoms else None,
            token_count=self._estimate_tokens(text),
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimate multilingual tokens without requiring a model-specific tokenizer."""
        chinese_chars = len(_CJK_RE.findall(text))
        other_chars = len(text) - chinese_chars
        return max(0, int(chinese_chars / 1.5 + other_chars / 4))
