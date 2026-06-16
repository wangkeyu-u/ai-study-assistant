"""Tests for Generator — citation extraction and prompt building."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

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


class FakeStream:
    """Minimal async stream matching OpenAI chunk shape."""

    def __init__(self, texts):
        self._texts = iter(texts)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            text = next(self._texts)
        except StopIteration as error:
            raise StopAsyncIteration from error
        return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


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


class TestCitationValidation:
    """Tests for post-generation citation safety gate."""

    @pytest.mark.asyncio
    async def test_generate_replaces_uncited_factual_answer(self, generator, sample_chunks):
        generator.client.chat.completions.create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content="这是一个没有引用的事实。"))
                ],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
        )

        result = await generator.generate("测试问题", sample_chunks)

        assert result.citation_validation_failed is True
        assert result.citations == []
        assert "可靠引用" in result.content

    @pytest.mark.asyncio
    async def test_generate_keeps_fully_cited_answer(self, generator, sample_chunks):
        generator.client.chat.completions.create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="这是有引用的事实[1]。"))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
        )

        result = await generator.generate("测试问题", sample_chunks)

        assert result.citation_validation_failed is False
        assert result.citations[0].chunk_id == "c1"
        assert result.content == "这是有引用的事实[1]。"

    @pytest.mark.asyncio
    async def test_generate_stream_buffers_until_citation_validation(
        self, generator, sample_chunks
    ):
        generator.client.chat.completions.create = AsyncMock(
            return_value=FakeStream(["这是一个", "没有引用的事实。"])
        )

        events = [event async for event in generator.generate_stream("测试问题", sample_chunks)]

        assert events[0]["type"] == "citation_validation"
        assert events[1]["type"] == "token"
        assert "可靠引用" in events[1]["text"]
        assert all(event.get("text") != "这是一个" for event in events)

    @pytest.mark.asyncio
    async def test_generate_stream_emits_citations_after_valid_answer(
        self, generator, sample_chunks
    ):
        generator.client.chat.completions.create = AsyncMock(
            return_value=FakeStream(["这是有引用", "的事实[1]。"])
        )

        events = [event async for event in generator.generate_stream("测试问题", sample_chunks)]

        assert events[0] == {"type": "token", "text": "这是有引用"}
        assert events[1] == {"type": "token", "text": "的事实[1]。"}
        assert events[2]["type"] == "citations"
        assert events[2]["citations"][0]["chunk_id"] == "c1"

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
