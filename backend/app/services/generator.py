"""LLM response generator with streaming and citation extraction."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.services.citation_validator import validate_citation_coverage
from app.services.context_utils import build_context_text

logger = logging.getLogger(__name__)


@dataclass
class CitationMark:
    """A citation reference found in the generated text."""

    ref_index: int  # [1] → 1, [2] → 2
    chunk_id: str
    doc_name: str
    page_num: int | None
    chunk_index: int
    text_preview: str


@dataclass
class GenerationResult:
    """Result of LLM generation."""

    content: str
    citations: list[CitationMark] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    generation_time_ms: float = 0.0
    final_prompt: str = ""
    citation_validation_failed: bool = False
    citation_validation_errors: list[str] = field(default_factory=list)


SYSTEM_PROMPT = """你是一个学习助手。你的任务是基于提供的参考资料来回答用户的问题。

规则：
1. 只能基于提供的参考资料回答，不要使用你自己的知识。
2. 如果参考资料中没有足够信息来回答问题，请明确告知："根据现有资料，没有找到足够的信息来回答这个问题。"
3. 每个事实性陈述所在的完整句子末尾必须标注引用来源，使用 [编号] 格式。例如："这个概念最早在1990年提出[1]。"
4. 引用编号对应下方参考资料中的序号。
5. 回答要简洁、准确、有条理。
{history_note}
参考资料：
{context}"""

HISTORY_NOTE = """6. 用户可能在之前的对话中问过相关问题，请参考对话上下文来理解用户的意图，但回答内容仍然必须基于参考资料。"""


class Generator:
    """Generate answers using LLM with retrieved context."""

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: str = "",
        base_url: str | None = None,
    ):
        if provider == "ollama":
            self.client = AsyncOpenAI(
                api_key="ollama",
                base_url=base_url or "http://localhost:11434/v1",
            )
            self.model = model
        else:
            kwargs: dict = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = AsyncOpenAI(**kwargs)  # type: ignore[arg-type]
            self.model = model

    def build_prompt(self, query: str, chunks: list, history: list[dict] | None = None) -> str:
        """Build the full prompt with context from retrieved chunks."""
        context = build_context_text(chunks)
        history_note = HISTORY_NOTE if history else ""
        return SYSTEM_PROMPT.format(history_note=history_note, context=context)

    async def generate(
        self, query: str, chunks: list, history: list[dict] | None = None
    ) -> GenerationResult:
        """Generate a complete answer (non-streaming).

        Args:
            query: User's question.
            chunks: Retrieved chunks from vector store.
            history: Conversation history as [{"role": "user"/"assistant", "content": "..."}]
        """
        if not chunks:
            return GenerationResult(
                content="根据现有资料，没有找到足够的信息来回答这个问题。请上传相关资料后再试。",
                final_prompt="(no context)",
            )

        prompt = self.build_prompt(query, chunks, history)
        messages = self._build_messages(query, chunks, history)
        start = time.time()

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=0.3,
            )
        except Exception as e:
            logger.error("LLM API call failed: %s", e)
            return GenerationResult(
                content=f"生成回答失败: {e}。请检查模型服务是否正常运行。",
                final_prompt=prompt,
            )

        elapsed = (time.time() - start) * 1000
        content = response.choices[0].message.content or ""
        usage = response.usage

        validation = validate_citation_coverage(content, len(chunks))
        citation_validation_errors = []
        citation_validation_failed = not validation.valid
        if citation_validation_failed:
            citation_validation_errors = [
                f"invalid_citations={validation.invalid_citation_count}",
                f"citation_completeness={validation.citation_completeness:.3f}",
            ]
            logger.warning(
                "Generated answer failed citation validation: %s",
                ", ".join(citation_validation_errors),
            )
            content = "根据现有资料，我无法生成带有可靠引用的回答。请换一种问法或检查资料后再试。"
            citations = []
        else:
            citations = self.extract_citations(content, chunks)

        return GenerationResult(
            content=content,
            citations=citations,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            generation_time_ms=elapsed,
            final_prompt=prompt,
            citation_validation_failed=citation_validation_failed,
            citation_validation_errors=citation_validation_errors,
        )

    async def generate_stream(
        self,
        query: str,
        chunks: list,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Generate answer with streaming tokens."""
        if not chunks:
            yield {
                "type": "token",
                "text": "根据现有资料，没有找到足够的信息来回答这个问题。请上传相关资料后再试。",
            }
            yield {"type": "done"}
            return

        messages = self._build_messages(query, chunks, history)
        full_text = ""
        streamed_parts: list[str] = []

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=0.3,
                stream=True,
            )

            async for chunk in stream:  # type: ignore[union-attr]
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_text += text
                    streamed_parts.append(text)

        except Exception as e:
            logger.error("LLM streaming failed: %s", e)
            yield {"type": "token", "text": f"\n\n生成回答失败: {e}"}
            yield {"type": "done"}
            return

        validation = validate_citation_coverage(full_text, len(chunks))
        if not validation.valid:
            yield {
                "type": "citation_validation",
                "valid": False,
                "invalid_citation_count": validation.invalid_citation_count,
                "citation_completeness": validation.citation_completeness,
            }
            yield {
                "type": "token",
                "text": "根据现有资料，我无法生成带有可靠引用的回答。请换一种问法或检查资料后再试。",
            }
        else:
            # Buffer until citation validation so unsafe uncited text is never emitted.
            for text in streamed_parts:
                yield {"type": "token", "text": text}

        # After streaming complete, extract citations
        citations = self.extract_citations(full_text, chunks) if validation.valid else []
        yield {
            "type": "citations",
            "citations": [
                {
                    "doc_name": c.doc_name,
                    "page_num": c.page_num,
                    "chunk_id": c.chunk_id,
                    "chunk_index": c.chunk_index,
                    "text_preview": c.text_preview,
                }
                for c in citations
            ],
        }

        yield {"type": "done"}

    # ── Citation extraction ────────────────────────────────

    def extract_citations(
        self,
        text: str,
        chunks: list,
    ) -> list[CitationMark]:
        """Extract [N] citation markers from generated text and map to chunks."""
        # Find all [N] references
        refs = re.findall(r"\[(\d+)\]", text)
        seen: set[int] = set()
        citations: list[CitationMark] = []

        for ref_str in refs:
            ref_idx = int(ref_str)
            if ref_idx in seen:
                continue
            # ref_idx is 1-based, map to chunks list (0-based)
            chunk_pos = ref_idx - 1
            if 0 <= chunk_pos < len(chunks):
                chunk = chunks[chunk_pos]
                citations.append(
                    CitationMark(
                        ref_index=ref_idx,
                        chunk_id=chunk.chunk_id,
                        doc_name=chunk.doc_name,
                        page_num=chunk.page_num,
                        chunk_index=chunk.chunk_index,
                        text_preview=chunk.text[:200],
                    )
                )
                seen.add(ref_idx)

        return citations

    @staticmethod
    def _build_context_text(chunks: list) -> str:
        """Build context text for the system prompt."""
        parts = []
        for i, chunk in enumerate(chunks, 1):
            page_info = f", 第{chunk.page_num}页" if chunk.page_num else ""
            heading_info = f" (标题: {chunk.heading})" if chunk.heading else ""
            parts.append(f"[{i}] 文档: {chunk.doc_name}{page_info}{heading_info}\n{chunk.text}")
        return "\n\n---\n\n".join(parts)

    def _build_messages(
        self,
        query: str,
        chunks: list,
        history: list[dict] | None = None,
    ) -> list[dict]:
        """Build the OpenAI messages array for the chat completion API.

        Message structure:
        ```
        [system]  Rules + retrieved context (with citation instructions)
        [user]    Turn 1 question          ← from history (if exists)
        [assistant] Turn 1 answer          ← from history (if exists)
        [user]    Turn 2 question          ← from history (if exists)
        [assistant] Turn 2 answer          ← from history (if exists)
        ...
        [user]    Current question         ← always last
        ```

        Token budget management:
        - System prompt (rules + context): ~1500 tokens (depends on chunk count)
        - History (last 10 messages): ~2000 tokens
        - Current query: ~100 tokens
        - Total input: ~3600 tokens → leaves ~400 for output in gpt-4o-mini's 4K context

        Why last 10 messages (5 turns):
        - Provides enough context for the LLM to understand conversation flow
        - Stays within token limits even with verbose previous answers
        - 5 turns covers most follow-up scenarios without information loss

        When history exists, an extra rule is added to the system prompt
        (HISTORY_NOTE) telling the LLM to reference conversation context
        when understanding the user's intent.
        """
        has_history = bool(history and len(history) > 0)
        # Only include the "reference history" instruction when there IS history
        history_note = HISTORY_NOTE if has_history else ""

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(
                    context=self._build_context_text(chunks),
                    history_note=history_note,
                ),
            },
        ]

        # Inject conversation history for multi-turn context
        # Capped at 10 messages (5 turns) to control token usage
        if has_history:
            for msg in history[-10:]:  # type: ignore[index]
                messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )

        # Current user query is always the last message
        messages.append({"role": "user", "content": query})

        return messages

    async def rewrite_query(
        self,
        query: str,
        history: list[dict] | None = None,
    ) -> str:
        """Rewrite the user's query considering conversation history.

        Purpose:
            In multi-turn conversations, users often ask follow-up questions that
            are ambiguous without context (e.g., "那第二章呢？", "能详细解释吗？").
            This method uses an LLM call to rewrite such queries into self-contained
            queries that can be effectively searched in the vector store.

        When it triggers:
            Only when history has ≥2 messages (at least 1 complete turn).
            First questions in a session are already self-contained.

        How it works:
            1. Takes the last 6 messages (3 turns) as conversation context
            2. Truncates each message to 200 chars to stay within token budget
            3. Asks LLM to rewrite the query to be self-contained
            4. Falls back to original query if LLM call fails

        Example:
            History: [user: "RAG的分块策略有哪些？", assistant: "常见的有..."]
            Query: "第二种呢？"
            → Rewritten: "RAG系统中递归字符分块策略的详细原理是什么？"

        Trade-offs:
            + Significantly improves retrieval for follow-up questions
            - Adds ~500ms latency for one extra LLM call
            - Costs extra tokens (~200 prompt + ~50 completion)

        Returns:
            The rewritten query string, or the original if rewrite fails/skipped.
        """
        # No history = first question, already self-contained
        if not history or len(history) < 2:
            return query

        # Take last 3 turns (6 messages) as context
        # This provides enough context without exceeding token limits
        recent = history[-6:]
        conv_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '助手'}: {m['content'][:200]}" for m in recent
        )

        rewrite_prompt = (
            "你是一个查询改写助手。根据对话历史和用户最新的问题，"
            "将用户的问题改写为一个完整、独立的查询，使其不依赖对话上下文也能被理解。\n\n"
            f"对话历史：\n{conv_text}\n\n"
            f"用户最新问题：{query}\n\n"
            "请直接输出改写后的查询，不要加任何解释："
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": rewrite_prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            rewritten = (response.choices[0].message.content or "").strip()
            logger.info("Query rewritten: '%s' -> '%s'", query, rewritten)
            return rewritten
        except Exception as e:
            logger.warning("Query rewrite failed, using original: %s", e)
            return query
