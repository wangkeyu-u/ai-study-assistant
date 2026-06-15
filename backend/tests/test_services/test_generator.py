"""Tests for Generator — citation extraction and prompt building."""

import pytest

from app.services.generator import Generator


@pytest.fixture
def generator():
    """Generator with no real API (we only test non-API methods)."""
    return Generator(provider="openai", api_key="fake-key", model="test-model")


class FakeChunk:
    """Minimal chunk-like object for testing."""

    def __init__(self, chunk_id, doc_name, page_num, chunk_index, text, heading=None):
        self.chunk_id = chunk_id
        self.doc_name = doc_name
        self.page_num = page_num
        self.chunk_index = chunk_index
        self.text = text
        self.heading = heading


@pytest.fixture
def sample_chunks():
    return [
        FakeChunk("c1", "doc1.pdf", 1, 0, "这是第一个文档的内容。"),
        FakeChunk("c2", "doc1.pdf", 2, 1, "这是第二个段落的内容。"),
        FakeChunk("c3", "doc2.pdf", 5, 0, "这是另一个文档的内容。"),
    ]


class TestExtractCitations:
    """Tests for extract_citations method."""

    def test_explicit_citations(self, generator, sample_chunks):
        text = "根据资料[1]，某些内容。另外[2]也提到了。"
        citations = generator.extract_citations(text, sample_chunks)
        assert len(citations) == 2
        assert citations[0].ref_index == 1
        assert citations[0].chunk_id == "c1"
        assert citations[1].ref_index == 2
        assert citations[1].chunk_id == "c2"

    def test_no_explicit_citations_returns_empty(self, generator, sample_chunks):
        text = "没有引用标记的回答。"
        citations = generator.extract_citations(text, sample_chunks)
        assert citations == []

    def test_duplicate_citations_deduplicated(self, generator, sample_chunks):
        text = "引用[1]，再引用[1]，还有[2]。"
        citations = generator.extract_citations(text, sample_chunks)
        assert len(citations) == 2

    def test_out_of_range_citation_ignored(self, generator, sample_chunks):
        text = "引用[99]不存在。"
        citations = generator.extract_citations(text, sample_chunks)
        assert citations == []

    def test_empty_chunks(self, generator):
        text = "某些回答[1]。"
        citations = generator.extract_citations(text, [])
        assert citations == []


class TestBuildMessages:
    """Tests for _build_messages method."""

    def test_no_history(self, generator, sample_chunks):
        messages = generator._build_messages("测试问题", sample_chunks)
        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "测试问题"

    def test_with_history(self, generator, sample_chunks):
        history = [
            {"role": "user", "content": "之前的问题"},
            {"role": "assistant", "content": "之前的回答"},
        ]
        messages = generator._build_messages("新问题", sample_chunks, history)
        # system + 2 history + 1 current
        assert len(messages) == 4
        assert messages[-1]["content"] == "新问题"

    def test_history_capped_at_10(self, generator, sample_chunks):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"} for i in range(20)
        ]
        messages = generator._build_messages("当前问题", sample_chunks, history)
        # system + 10 (capped) + 1 current
        assert len(messages) == 12


class TestBuildContextText:
    """Tests for _build_context_text static method."""

    def test_context_includes_doc_info(self, generator, sample_chunks):
        text = generator._build_context_text(sample_chunks)
        assert "[1]" in text
        assert "doc1.pdf" in text
        assert "第1页" in text
        assert "doc2.pdf" in text

    def test_empty_chunks(self, generator):
        text = generator._build_context_text([])
        assert text == ""
