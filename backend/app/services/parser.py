"""Document parser for PDF, TXT, and Markdown files."""

from __future__ import annotations

import re
import statistics
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
            "note": self._parse_txt,  # notes use the same plain-text parser
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

        with fitz.open(file_path) as doc:
            segments: list[ParsedSegment] = []
            page_dicts = [doc[page_num].get_text("dict", sort=True) for page_num in range(len(doc))]
            font_sizes = [
                float(span.get("size", 0))
                for page_data in page_dicts
                for block in page_data.get("blocks", [])
                if block.get("type") == 0
                for line in block.get("lines", [])
                for span in line.get("spans", [])
                if str(span.get("text", "")).strip() and float(span.get("size", 0)) > 0
            ]
            body_font_size = statistics.median(font_sizes) if font_sizes else 0.0
            active_heading: str | None = None

            for page_num, page_data in enumerate(page_dicts, start=1):
                page_parts: list[str] = []

                def flush_page_parts(
                    heading: str | None,
                    parts: list[str] = page_parts,
                    current_page: int = page_num,
                ) -> None:
                    if not parts:
                        return
                    text = "\n\n".join(parts).strip()
                    if text:
                        segments.append(
                            ParsedSegment(
                                text=text,
                                page_num=current_page,
                                heading=heading,
                            )
                        )
                    parts.clear()

                for block in page_data.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    lines = block.get("lines", [])
                    line_texts = [
                        "".join(str(span.get("text", "")) for span in line.get("spans", [])).strip()
                        for line in lines
                    ]
                    block_text = "\n".join(text for text in line_texts if text).strip()
                    if not block_text:
                        continue

                    spans = [span for line in lines for span in line.get("spans", [])]
                    max_font_size = max(
                        (float(span.get("size", 0)) for span in spans),
                        default=0.0,
                    )
                    is_bold = any("bold" in str(span.get("font", "")).lower() for span in spans)
                    if self._looks_like_pdf_heading(
                        block_text,
                        max_font_size=max_font_size,
                        body_font_size=body_font_size,
                        is_bold=is_bold,
                    ):
                        flush_page_parts(active_heading)
                        active_heading = re.sub(r"\s+", " ", block_text).strip()
                    else:
                        page_parts.append(block_text)

                flush_page_parts(active_heading)

        if not segments:
            return ParseResult(error="该 PDF 为扫描版或内容为空，暂不支持 OCR，请上传文字版 PDF")

        return ParseResult(segments=segments)

    @staticmethod
    def _looks_like_pdf_heading(
        text: str,
        *,
        max_font_size: float,
        body_font_size: float,
        is_bold: bool,
    ) -> bool:
        """Use PDF typography as a strong heading signal without overfitting text."""
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized or len(normalized) > 160 or normalized.count("\n") > 1:
            return False
        if normalized.endswith(("。", "！", "？", ".", "!", "?", ";", "；")):
            return False
        if body_font_size <= 0:
            return False
        is_larger = max_font_size >= body_font_size * 1.18
        is_bold_and_larger = is_bold and max_font_size >= body_font_size * 1.05
        return is_larger or is_bold_and_larger

    # ── TXT ────────────────────────────────────────────────

    def _parse_txt(self, file_path: str) -> ParseResult:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            text = f.read()

        if not text.strip():
            return ParseResult(segments=[])

        return ParseResult(segments=[ParsedSegment(text=text.strip())])

    # ── Markdown ───────────────────────────────────────────

    def _parse_markdown(self, file_path: str) -> ParseResult:
        with open(file_path, encoding="utf-8", errors="replace") as f:
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
                        segments.append(
                            ParsedSegment(
                                text=block,
                                heading=current_heading,
                            )
                        )
                current_heading = heading_match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        # Flush last section
        if current_lines:
            block = "\n".join(current_lines).strip()
            if block:
                segments.append(
                    ParsedSegment(
                        text=block,
                        heading=current_heading,
                    )
                )

        # If no headings found, treat entire file as one segment
        if not segments:
            segments = [ParsedSegment(text=text.strip())]

        return ParseResult(segments=segments)
