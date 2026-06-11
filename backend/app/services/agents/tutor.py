"""Tutor Agent — specializes in deep, structured concept explanations.

Uses the existing RAG pipeline to retrieve relevant content, then asks the LLM
to produce a thorough, well-structured explanation with headings, examples,
and citations.
"""

from __future__ import annotations

import logging

from app.services.agents.base import BaseAgent, AgentResponse
from app.services.rag import RAGPipeline

logger = logging.getLogger(__name__)

TUTOR_SYSTEM_PROMPT = """你是一位资深导师（Tutor Agent）。你的任务是基于提供的参考资料，对用户提出的概念进行深入、结构化的解释。

回答要求：
1. 使用清晰的层级结构（标题、子标题、列表）。
2. 先给出简短定义，再逐步深入。
3. 在适当时提供类比或示例来帮助理解。
4. 每个事实性陈述后标注引用来源 [编号]。
5. 最后给出一个"核心要点"总结。
6. 如果参考资料不足以完整解释，明确说明缺失的部分。

参考资料：
{context}"""

CONTEXT_TEMPLATE = """[{index}] 文档: {doc_name}{page_info}
{heading_info}---
{chunk_text}
"""


class TutorAgent(BaseAgent):
    """Explains concepts in depth using RAG-retrieved context."""

    def __init__(self):
        super().__init__(name="Tutor")

    async def process(self, query: str, context: dict | None = None) -> AgentResponse:
        context = context or {}
        pipeline: RAGPipeline | None = context.get("pipeline")
        history = context.get("history")
        collection_id = context.get("collection_id")

        if pipeline is None:
            return AgentResponse(
                content="Tutor Agent 暂时不可用（RAG pipeline 未初始化）。",
                agent_name=self.name,
            )

        try:
            # Step 1: Retrieve relevant chunks via RAG pipeline components
            rewritten_query = query
            if history and len(history) >= 2:
                rewritten_query = await pipeline.generator.rewrite_query(query, history)

            from app.services.retriever import Retriever

            retriever = Retriever(
                vector_store=pipeline.vector_store,
                embedder=pipeline.embedder,
                top_k=pipeline.settings.top_k,
                similarity_threshold=pipeline.settings.similarity_threshold,
            )
            retrieval_result = retriever.retrieve(rewritten_query, collection_id=collection_id)

            if not retrieval_result.chunks:
                return AgentResponse(
                    content="根据现有资料，没有找到足够的信息来解释这个概念。请上传相关资料后再试。",
                    agent_name=self.name,
                    metadata={"retrieved_chunks": 0},
                )

            # Step 2: Build tutor-specific prompt
            context_text = self._build_context(retrieval_result.chunks)
            system_msg = TUTOR_SYSTEM_PROMPT.format(context=context_text)

            messages = [{"role": "system", "content": system_msg}]
            if history:
                for msg in history[-10:]:
                    messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": query})

            # Step 3: Call LLM
            response = await pipeline.generator.client.chat.completions.create(
                model=pipeline.generator.model,
                messages=messages,
                temperature=0.3,
            )

            content = response.choices[0].message.content or ""
            usage = response.usage

            return AgentResponse(
                content=content,
                agent_name=self.name,
                metadata={
                    "retrieved_chunks": len(retrieval_result.chunks),
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                },
            )

        except Exception as e:
            logger.exception("TutorAgent failed, falling back to default RAG")
            return await self._fallback(pipeline, query, history, collection_id, error=e)

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _build_context(chunks: list) -> str:
        parts = []
        for i, chunk in enumerate(chunks, 1):
            page_info = f", 第{chunk.page_num}页" if chunk.page_num else ""
            heading_info = f"标题: {chunk.heading}\n" if chunk.heading else ""
            parts.append(
                CONTEXT_TEMPLATE.format(
                    index=i,
                    doc_name=chunk.doc_name,
                    page_info=page_info,
                    heading_info=heading_info,
                    chunk_text=chunk.text,
                )
            )
        return "\n".join(parts)

    @staticmethod
    async def _fallback(
        pipeline: RAGPipeline,
        query: str,
        history: list[dict] | None,
        collection_id: str | None,
        error: Exception,
    ) -> AgentResponse:
        """Fall back to the standard RAG pipeline when the tutor-specific flow fails."""
        try:
            gen_result, _debug = await pipeline.query(query, history=history, collection_id=collection_id)
            return AgentResponse(
                content=gen_result.content,
                agent_name="Tutor (fallback)",
                metadata={"fallback_reason": str(error)},
            )
        except Exception as fallback_err:
            logger.exception("Tutor fallback also failed")
            return AgentResponse(
                content=f"处理请求时出错: {fallback_err}",
                agent_name="Tutor (error)",
            )
