"""Document parser for PDF, TXT, and Markdown files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedSegment:
    """A segment of parsed text with optional metadata."""
    text: str
    page_num: int | None = None
    heading: str | None = None


@dataclass
class ParseResult:
    """Result of parsing a document file."""
    segments: list[ParsedSegment] = field(default_factory=list)
    error: str | None = None

    @property
    def full_text(self) -> str:
        return "\n".join(s.text for s in self.segments if s.text.strip())

    @property
    def is_empty(self) -> bool:
        return not any(s.text.strip() for s in self.segments)


class DocumentParser:
    """Parse PDF, TXT, and Markdown files into text segments."""

    def parse(self, file_path: str, file_type: str) -> ParseResult:
        parsers = {
            "pdf": self._parse_pdf,
            "txt": self._parse_txt,
            "md": self._parse_markdown,
            "note": self._parse_txt,       # notes use the same plain-text parser
        }
        parser_fn = parsers.get(file_type)
        if parser_fn is None:
            return ParseResult(error=f"Unsupported file type: {file_type}")
        try:
            result = parser_fn(file_path)
            if result.is_empty:
                result.error = "文档内容为空"
            return result
        except Exception as e:
            return ParseResult(error=f"解析失败: {e}")

    # ── PDF ────────────────────────────────────────────────

    def _parse_pdf(self, file_path: str) -> ParseResult:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        segments: list[ParsedSegment] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                segments.append(ParsedSegment(
                    text=text.strip(),
                    page_num=page_num + 1,
                ))

        doc.close()

        if not segments:
            return ParseResult(error="该 PDF 为扫描版或内容为空，暂不支持 OCR，请上传文字版 PDF")

        return ParseResult(segments=segments)

    # ── TXT ────────────────────────────────────────────────

    def _parse_txt(self, file_path: str) -> ParseResult:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        if not text.strip():
            return ParseResult(segments=[])

        return ParseResult(segments=[ParsedSegment(text=text.strip())])

    # ── Markdown ───────────────────────────────────────────

    def _parse_markdown(self, file_path: str) -> ParseResult:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        if not text.strip():
            return ParseResult(segments=[])

        segments: list[ParsedSegment] = []
        current_heading: str | None = None
        current_lines: list[str] = []

        for line in text.split("\n"):
            heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
            if heading_match:
                # Flush previous section
                if current_lines:
                    block = "\n".join(current_lines).strip()
                    if block:
                        segments.append(ParsedSegment(
                            text=block,
                            heading=current_heading,
                        ))
                current_heading = heading_match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        # Flush last section
        if current_lines:
            block = "\n".join(current_lines).strip()
            if block:
                segments.append(ParsedSegment(
                    text=block,
                    heading=current_heading,
                ))

        # If no headings found, treat entire file as one segment
        if not segments:
            segments = [ParsedSegment(text=text.strip())]

        return ParseResult(segments=segments)
