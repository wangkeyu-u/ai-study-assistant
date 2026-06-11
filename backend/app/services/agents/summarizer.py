"""Summarizer Agent — generates document summaries using RAG context.

Reuses the existing RAG retrieval pipeline to gather content and then asks
the LLM to produce a concise, structured summary.
"""

from __future__ import annotations

import logging

from app.db.database import get_connection
from app.services.agents.base import BaseAgent, AgentResponse
from app.services.rag import RAGPipeline

logger = logging.getLogger(__name__)

SUMMARIZER_SYSTEM_PROMPT = """你是一位摘要专家（Summarizer Agent）。你的任务是基于提供的文档内容，生成一份清晰、结构化的摘要。

摘要要求：
1. 首先给出一段总体概述（2-3 句话）。
2. 然后列出关键要点（使用编号列表，5-10 个要点）。
3. 最后给出一个简短的"一句话总结"。
4. 保持客观、准确，不要添加文档中没有的信息。
5. 引用来源用 [编号] 标注。

文档内容：
{context}"""

CONTEXT_TEMPLATE = """[{index}] 文档: {doc_name}{page_info}
{heading_info}---
{chunk_text}
"""


class SummarizerAgent(BaseAgent):
    """Generates document or topic summaries from RAG-retrieved content."""

    def __init__(self):
        super().__init__(name="Summarizer")

    async def process(self, query: str, context: dict | None = None) -> AgentResponse:
        context = context or {}
        pipeline: RAGPipeline | None = context.get("pipeline")
        collection_id = context.get("collection_id")
        doc_ids = context.get("doc_ids")

        if pipeline is None:
            return AgentResponse(
                content="Summarizer Agent 暂时不可用（RAG pipeline 未初始化）。",
                agent_name=self.name,
            )

        try:
            # Determine the source of content: specific docs or query-based retrieval
            if doc_ids:
                chunks = self._fetch_chunks_by_doc_ids(doc_ids)
            else:
                chunks = await self._retrieve_chunks(pipeline, query, collection_id)

            if not chunks:
                return AgentResponse(
                    content="根据现有资料，没有找到足够的信息来生成摘要。请上传相关资料后再试。",
                    agent_name=self.name,
                    metadata={"retrieved_chunks": 0},
                )

            # Build context text
            context_text = self._build_context(chunks)

            system_msg = SUMMARIZER_SYSTEM_PROMPT.format(context=context_text)
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"请为以下内容生成结构化摘要：{query}"},
            ]

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
                    "retrieved_chunks": len(chunks),
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                },
            )

        except Exception as e:
            logger.exception("SummarizerAgent failed, falling back to default RAG")
            return await self._fallback(pipeline, query, context.get("history"), collection_id, error=e)

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    async def _retrieve_chunks(
        pipeline: RAGPipeline,
        query: str,
        collection_id: str | None,
    ) -> list:
        """Retrieve chunks via the RAG retriever."""
        from app.services.retriever import Retriever

        retriever = Retriever(
            vector_store=pipeline.vector_store,
            embedder=pipeline.embedder,
            top_k=max(pipeline.settings.top_k, 8),
            similarity_threshold=pipeline.settings.similarity_threshold,
        )
        result = retriever.retrieve(query, collection_id=collection_id)
        return result.chunks

    @staticmethod
    def _fetch_chunks_by_doc_ids(doc_ids: list[str]) -> list:
        """Fetch chunks directly from SQLite for specific documents."""
        conn = get_connection()
        try:
            placeholders = ",".join("?" for _ in doc_ids)
            rows = conn.execute(
                f"SELECT text, doc_id FROM chunks WHERE doc_id IN ({placeholders}) "
                f"ORDER BY chunk_index LIMIT 20",
                doc_ids,
            ).fetchall()

            # Wrap rows in simple objects so _build_context can access attributes
            class _Chunk:
                def __init__(self, row):
                    self.text = row["text"]
                    self.doc_name = row["doc_id"]  # fallback to doc_id
                    self.page_num = None
                    self.heading = None

            return [_Chunk(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def _build_context(chunks: list) -> str:
        parts = []
        for i, chunk in enumerate(chunks, 1):
            page_info = f", 第{chunk.page_num}页" if getattr(chunk, "page_num", None) else ""
            heading_info = f"标题: {chunk.heading}\n" if getattr(chunk, "heading", None) else ""
            parts.append(
                CONTEXT_TEMPLATE.format(
                    index=i,
                    doc_name=getattr(chunk, "doc_name", "未知文档"),
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
        """Fall back to standard RAG pipeline on failure."""
        try:
            gen_result, _debug = await pipeline.query(query, history=history, collection_id=collection_id)
            return AgentResponse(
                content=gen_result.content,
                agent_name="Summarizer (fallback)",
                metadata={"fallback_reason": str(error)},
            )
        except Exception as fallback_err:
            logger.exception("Summarizer fallback also failed")
            return AgentResponse(
                content=f"处理请求时出错: {fallback_err}",
                agent_name="Summarizer (error)",
            )
