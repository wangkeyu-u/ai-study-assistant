"""Tests for TextChunker — pure logic, no external dependencies."""

import pytest

from app.services.chunker import TextChunker


@pytest.fixture
def chunker():
    """Default chunker with small chunk size for testing."""
    return TextChunker(chunk_size=50, chunk_overlap=10)


class TestChunkText:
    """Tests for chunk_text method."""

    def test_empty_text_returns_empty(self, chunker):
        assert chunker.chunk_text("") == []

    def test_whitespace_only_returns_empty(self, chunker):
        assert chunker.chunk_text("   \n\n  \n  ") == []

    def test_short_text_single_chunk(self, chunker):
        text = "这是一段很短的文本。"
        chunks = chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0

    def test_long_text_split_into_chunks(self, chunker):
        paragraphs = [
            "这是一段较长的测试文字内容，包含多个句子来确保分块功能正常工作。" for _ in range(8)
        ]
        text = "\n\n".join(paragraphs)
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 2

    def test_chunks_have_sequential_indices(self, chunker):
        text = "\n\n".join(f"段落{i}，包含一些测试文字。" for i in range(10))
        chunks = chunker.chunk_text(text)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_page_num_preserved(self, chunker):
        chunks = chunker.chunk_text("测试内容段落", page_num=3)
        assert all(c.page_num == 3 for c in chunks)

    def test_heading_preserved(self, chunker):
        chunks = chunker.chunk_text("测试内容段落", heading="第一章")
        assert all(c.heading == "第一章" for c in chunks)

    def test_token_count_positive(self, chunker):
        chunks = chunker.chunk_text("这是一段测试文本，应该有足够的长度。")
        assert all(c.token_count > 0 for c in chunks)


class TestChunkSegments:
    """Tests for chunk_segments method."""

    def test_multiple_segments_global_index(self, chunker):
        """Chunks from multiple segments should have global sequential indices."""
        from dataclasses import dataclass

        @dataclass
        class FakeSegment:
            text: str
            page_num: int | None = None
            heading: str | None = None

        segments = [
            FakeSegment("第一段内容，足够长的文字来测试分块功能。" * 3, page_num=1),
            FakeSegment("第二段内容，同样需要足够长的文字。" * 3, page_num=2),
        ]
        chunks = chunker.chunk_segments(segments)
        assert len(chunks) >= 2
        # Global indexing
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_empty_segments(self, chunker):
        assert chunker.chunk_segments([]) == []


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_chinese_text(self):
        """Chinese characters should estimate ~1.5 chars per token."""
        tokens = TextChunker._estimate_tokens("你好世界测试文本")
        assert tokens > 0

    def test_english_text(self):
        """English characters should estimate ~4 chars per token."""
        tokens = TextChunker._estimate_tokens("Hello world this is a test")
        assert tokens > 0

    def test_empty_text(self):
        assert TextChunker._estimate_tokens("") == 0

    def test_mixed_text(self):
        """Mixed Chinese and English should combine estimates."""
        tokens = TextChunker._estimate_tokens("Hello你好world世界")
        assert tokens > 0
