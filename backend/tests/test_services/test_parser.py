"""Tests for document structure extraction."""

from app.services.parser import DocumentParser


def test_pdf_heading_detection_uses_typography():
    assert DocumentParser._looks_like_pdf_heading(
        "Retrieval Architecture",
        max_font_size=16,
        body_font_size=11,
        is_bold=True,
    )


def test_pdf_heading_detection_rejects_body_sentence():
    assert not DocumentParser._looks_like_pdf_heading(
        "Retrieval combines dense and lexical search.",
        max_font_size=11,
        body_font_size=11,
        is_bold=False,
    )
