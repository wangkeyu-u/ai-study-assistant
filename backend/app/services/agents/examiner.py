"""Examiner Agent — generates quiz questions from document content.

Reuses the quiz-generation logic from the existing quiz router but wraps it
in the Agent interface so the Supervisor can route to it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from app.services.agents.base import AgentResponse, BaseAgent
from app.services.rag import RAGPipeline

logger = logging.getLogger(__name__)

EXAMINER_SYSTEM_PROMPT = """你是一位出题专家（Examiner Agent）。根据提供的学习资料，生成测验题目来帮助用户检验理解。

要求：
- 生成 {count} 道题目
- 混合选择题（choice）和判断题（true_false）
- 选择题必须有恰好 4 个选项
- 每道题必须有解析（explanation）
- 严格使用以下 JSON 格式输出，不要附加额外文字：
{{"questions": [{{"type": "choice"|"true_false", "question": "题目文本", "options": ["A选项","B选项","C选项","D选项"], "answer": "正确答案（选择题用A/B/C/D，判断题用true/false）", "explanation": "解析"}}]}}

学习资料：
{context}"""


class ExaminerAgent(BaseAgent):
    """Generates quizzes based on document content and conversation context."""

    def __init__(self):
        super().__init__(name="Examiner")

    async def process(self, query: str, context: dict | None = None) -> AgentResponse:
        context = context or {}
        pipeline: RAGPipeline | None = context.get("pipeline")
        history = context.get("history")
        collection_id = context.get("collection_id")
        question_count = context.get("question_count", 5)

        if pipeline is None:
            return AgentResponse(
                content="Examiner Agent 暂时不可用（RAG pipeline 未初始化）。",
                agent_name=self.name,
            )

        try:
            # Step 1: Retrieve relevant chunks for quiz generation
            rewritten_query = query
            if history and len(history) >= 2:
                rewritten_query = await pipeline.generator.rewrite_query(query, history)

            from app.services.retriever import Retriever

            retriever = Retriever(
                vector_store=pipeline.vector_store,
                embedder=pipeline.embedder,
                top_k=max(pipeline.settings.top_k, 8),
                similarity_threshold=pipeline.settings.similarity_threshold,
                hybrid_search_enabled=pipeline.settings.hybrid_search_enabled,
                candidate_multiplier=pipeline.settings.retrieval_candidate_multiplier,
                rrf_k=pipeline.settings.rrf_k,
                confidence_gate_enabled=pipeline.settings.retrieval_confidence_gate_enabled,
                vector_only_min_score=pipeline.settings.vector_only_min_score,
                reranker=pipeline.reranker,
                rerank_top_n=pipeline.settings.reranker_top_n,
            )
            retrieval_result = retriever.retrieve(rewritten_query, collection_id=collection_id)

            if not retrieval_result.chunks:
                return AgentResponse(
                    content="根据现有资料，无法生成相关测验题目。请上传相关资料后再试。",
                    agent_name=self.name,
                    metadata={"retrieved_chunks": 0},
                )

            # Step 2: Build context text from chunks
            context_text = "\n\n".join(
                f"[{i + 1}] {c.text[:500]}" for i, c in enumerate(retrieval_result.chunks)
            )[:4000]

            count = min(question_count, 10)

            # Step 3: Generate quiz via LLM
            system_msg = EXAMINER_SYSTEM_PROMPT.format(count=count, context=context_text)
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"请根据以上资料，生成{count}道测验题目。"},
            ]

            response = await pipeline.generator.client.chat.completions.create(
                model=pipeline.generator.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=0.7,
            )

            raw_text = response.choices[0].message.content or ""
            usage = response.usage

            # Step 4: Parse JSON from LLM response
            quiz_data = self._parse_quiz_json(raw_text)

            if quiz_data is None:
                return AgentResponse(
                    content="生成测验失败，LLM 返回了无效的格式。请重试。",
                    agent_name=self.name,
                    metadata={"raw_response": raw_text[:500]},
                )

            questions = quiz_data.get("questions", [])
            if not questions:
                return AgentResponse(
                    content="未能生成任何测验题目，请重试。",
                    agent_name=self.name,
                )

            # Format a human-readable summary
            summary_lines = [f"已生成 {len(questions)} 道测验题目：\n"]
            for i, q in enumerate(questions, 1):
                q_type = "选择题" if q.get("type") == "choice" else "判断题"
                summary_lines.append(f"{i}. [{q_type}] {q.get('question', 'N/A')}")
                if q.get("options"):
                    for opt in q["options"]:
                        summary_lines.append(f"   {opt}")
                summary_lines.append(f"   答案: {q.get('answer', 'N/A')}")
                summary_lines.append(f"   解析: {q.get('explanation', 'N/A')}\n")

            return AgentResponse(
                content="\n".join(summary_lines),
                agent_name=self.name,
                metadata={
                    "questions": questions,
                    "question_count": len(questions),
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                },
            )

        except Exception as e:
            logger.exception("ExaminerAgent failed")
            return AgentResponse(
                content=f"生成测验时出错: {e}",
                agent_name=self.name,
            )

    async def process_stream(
        self, query: str, context: dict | None = None
    ) -> AsyncGenerator[dict, None]:
        """Stream examiner quiz generation with token-by-token output.

        Yields events: {"type": "token", "text": "..."}, {"type": "done", "agent_name": "...", "content": "...", "metadata": {...}}
        Citations are not applicable for quiz generation.
        """
        context = context or {}
        pipeline: RAGPipeline | None = context.get("pipeline")
        history = context.get("history")
        collection_id = context.get("collection_id")
        question_count = context.get("question_count", 5)

        if pipeline is None:
            yield {"type": "token", "text": "Examiner Agent 暂时不可用（RAG pipeline 未初始化）。"}
            yield {"type": "done", "agent_name": self.name, "content": "", "metadata": {}}
            return

        try:
            # Step 1: Retrieve relevant chunks
            rewritten_query = query
            if history and len(history) >= 2:
                rewritten_query = await pipeline.generator.rewrite_query(query, history)

            from app.services.retriever import Retriever

            retriever = Retriever(
                vector_store=pipeline.vector_store,
                embedder=pipeline.embedder,
                top_k=max(pipeline.settings.top_k, 8),
                similarity_threshold=pipeline.settings.similarity_threshold,
                hybrid_search_enabled=pipeline.settings.hybrid_search_enabled,
                candidate_multiplier=pipeline.settings.retrieval_candidate_multiplier,
                rrf_k=pipeline.settings.rrf_k,
                confidence_gate_enabled=pipeline.settings.retrieval_confidence_gate_enabled,
                vector_only_min_score=pipeline.settings.vector_only_min_score,
                reranker=pipeline.reranker,
                rerank_top_n=pipeline.settings.reranker_top_n,
            )
            retrieval_result = retriever.retrieve(rewritten_query, collection_id=collection_id)

            if not retrieval_result.chunks:
                yield {
                    "type": "token",
                    "text": "根据现有资料，无法生成相关测验题目。请上传相关资料后再试。",
                }
                yield {
                    "type": "done",
                    "agent_name": self.name,
                    "content": "",
                    "metadata": {"retrieved_chunks": 0},
                }
                return

            # Step 2: Build context and prompt
            context_text = "\n\n".join(
                f"[{i + 1}] {c.text[:500]}" for i, c in enumerate(retrieval_result.chunks)
            )[:4000]
            count = min(question_count, 10)

            system_msg = EXAMINER_SYSTEM_PROMPT.format(count=count, context=context_text)
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"请根据以上资料，生成{count}道测验题目。"},
            ]

            # Step 3: Stream LLM response
            full_text = ""
            stream = await pipeline.generator.client.chat.completions.create(
                model=pipeline.generator.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=0.7,
                stream=True,
            )

            async for chunk in stream:  # type: ignore[union-attr]
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_text += text
                    yield {"type": "token", "text": text}

            # Step 4: Parse quiz JSON and format
            quiz_data = self._parse_quiz_json(full_text)
            if quiz_data is None:
                yield {
                    "type": "done",
                    "agent_name": self.name,
                    "content": "生成测验失败，LLM 返回了无效的格式。请重试。",
                    "metadata": {"raw_response": full_text[:500]},
                }
                return

            questions = quiz_data.get("questions", [])
            if not questions:
                yield {
                    "type": "done",
                    "agent_name": self.name,
                    "content": "未能生成任何测验题目，请重试。",
                    "metadata": {},
                }
                return

            # Format human-readable summary
            summary_lines = [f"已生成 {len(questions)} 道测验题目：\n"]
            for i, q in enumerate(questions, 1):
                q_type = "选择题" if q.get("type") == "choice" else "判断题"
                summary_lines.append(f"{i}. [{q_type}] {q.get('question', 'N/A')}")
                if q.get("options"):
                    for opt in q["options"]:
                        summary_lines.append(f"   {opt}")
                summary_lines.append(f"   答案: {q.get('answer', 'N/A')}")
                summary_lines.append(f"   解析: {q.get('explanation', 'N/A')}\n")

            formatted = "\n".join(summary_lines)

            yield {
                "type": "done",
                "agent_name": self.name,
                "content": formatted,
                "metadata": {
                    "questions": questions,
                    "question_count": len(questions),
                },
            }

        except Exception as e:
            logger.exception("ExaminerAgent streaming failed")
            yield {
                "type": "done",
                "agent_name": self.name,
                "content": f"生成测验时出错: {e}",
                "metadata": {"error": str(e)},
            }

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _parse_quiz_json(raw_text: str) -> dict | None:
        """Extract and parse quiz JSON from LLM response (handles markdown code blocks)."""
        try:
            if "```json" in raw_text:
                json_str = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                json_str = raw_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = raw_text.strip()
            return json.loads(json_str)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, IndexError) as e:
            logger.error("Failed to parse quiz JSON: %s", e)
            return None
