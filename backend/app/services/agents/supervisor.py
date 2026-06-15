"""Supervisor Agent — classifies user intent and routes to specialist agents.

The Supervisor uses a single lightweight LLM call to determine the user's
intent, then delegates to one of four specialist agents:

  - **Tutor**: deep concept explanations  (intent = 'explain' | 'qa')
  - **Examiner**: quiz / test generation  (intent = 'quiz')
  - **Summarizer**: document summaries    (intent = 'summary')

If classification fails or the LLM is unavailable, the Supervisor falls back
to the Tutor agent (which itself degrades to the standard RAG pipeline).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from app.services.agents.base import AgentResponse, BaseAgent
from app.services.agents.examiner import ExaminerAgent
from app.services.agents.summarizer import SummarizerAgent
from app.services.agents.tutor import TutorAgent
from app.services.rag import RAGPipeline

logger = logging.getLogger(__name__)

# ── Intent classification prompt ────────────────────────────────
INTENT_PROMPT = """你是一个意图分类器。根据用户的查询，判断用户意图并返回一个分类标签。

分类标签（只能返回以下四个之一）：
- qa：普通问答，用户想查询某个具体事实或信息
- quiz：用户想要测验、测试、出题、检验学习成果
- summary：用户想要摘要、总结、概述文档内容
- explain：用户想要深入解释、详细说明某个概念或原理

判断规则：
1. 如果用户明确提到"测验""测试""出题""考考我"等 → quiz
2. 如果用户明确提到"摘要""总结""概述""概括"等 → summary
3. 如果用户明确提到"解释""详细说明""是什么""原理""概念"等 → explain
4. 其他情况（提问、查询具体信息）→ qa

用户查询：{query}

请只返回一个标签（qa/quiz/summary/explain），不要返回任何其他文字。"""

# Map intent → agent class (lazy instantiated)
INTENT_AGENT_MAP = {
    "qa": "tutor",
    "explain": "tutor",
    "quiz": "examiner",
    "summary": "summarizer",
}


class SupervisorAgent:
    """Top-level coordinator: classifies intent → routes to specialist agent.

    This is NOT a BaseAgent subclass because it never generates content itself;
    it only delegates.
    """

    def __init__(self):
        self.tutor = TutorAgent()
        self.examiner = ExaminerAgent()
        self.summarizer = SummarizerAgent()
        self._agent_map = {
            "tutor": self.tutor,
            "examiner": self.examiner,
            "summarizer": self.summarizer,
        }

    async def route(
        self,
        query: str,
        pipeline: RAGPipeline,
        history: list[dict] | None = None,
        collection_id: str | None = None,
    ) -> AgentResponse:
        """Classify intent and delegate to the appropriate specialist agent.

        Args:
            query: User's natural-language query.
            pipeline: The shared RAGPipeline instance.
            history: Conversation history for multi-turn context.
            collection_id: Optional knowledge-base filter.

        Returns:
            AgentResponse from the chosen specialist agent.
        """
        # Step 1: Classify intent
        intent = await self._classify_intent(query, pipeline)
        logger.info("Supervisor classified intent: '%s' for query: '%s'", intent, query[:80])

        # Step 2: Select agent
        agent_name = INTENT_AGENT_MAP.get(intent, "tutor")
        agent: BaseAgent = self._agent_map[agent_name]

        # Step 3: Build context for the agent
        context = {
            "pipeline": pipeline,
            "history": history,
            "collection_id": collection_id,
            "intent": intent,
        }

        # Step 4: Delegate
        response = await agent.process(query, context)

        # Attach classification info to metadata
        response.metadata["classified_intent"] = intent
        return response

    async def route_stream(
        self,
        query: str,
        pipeline: RAGPipeline,
        history: list[dict] | None = None,
        collection_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Classify intent and stream from the appropriate specialist agent.

        Yields SSE-compatible events: {"type": "token"/"citations"/"done", ...}
        """
        # Step 1: Classify intent
        intent = await self._classify_intent(query, pipeline)
        logger.info("Supervisor classified intent: '%s' for query: '%s'", intent, query[:80])

        # Step 2: Select agent
        agent_name = INTENT_AGENT_MAP.get(intent, "tutor")
        agent: BaseAgent = self._agent_map[agent_name]

        # Step 3: Build context for the agent
        context = {
            "pipeline": pipeline,
            "history": history,
            "collection_id": collection_id,
            "intent": intent,
        }

        # Step 4: Stream from the specialist agent
        async for event in agent.process_stream(query, context):
            # Attach classification info
            if event.get("type") == "done":
                if "metadata" not in event:
                    event["metadata"] = {}
                event["metadata"]["classified_intent"] = intent
            yield event

    # ── Intent classification ─────────────────────────────────

    async def _classify_intent(self, query: str, pipeline: RAGPipeline) -> str:
        """Use LLM to classify user intent. Falls back to 'qa' on failure."""
        prompt = INTENT_PROMPT.format(query=query)

        try:
            response = await pipeline.generator.client.chat.completions.create(
                model=pipeline.generator.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=20,
            )
            raw = (response.choices[0].message.content or "").strip().lower()

            # Validate the returned label
            valid_intents = {"qa", "quiz", "summary", "explain"}
            if raw in valid_intents:
                return raw

            # The LLM might return extra text; try to extract a valid label
            for intent in valid_intents:
                if intent in raw:
                    return intent

            logger.warning("Unexpected intent label from LLM: '%s', defaulting to 'qa'", raw)
            return "qa"

        except Exception as e:
            logger.warning("Intent classification LLM call failed: %s, defaulting to 'qa'", e)
            return self._rule_based_fallback(query)

    @staticmethod
    def _rule_based_fallback(query: str) -> str:
        """Simple keyword-based fallback when LLM classification is unavailable."""
        q = query.lower()

        quiz_keywords = ["测验", "测试", "出题", "考考我", "quiz", "题", "考试", "练习"]
        summary_keywords = ["摘要", "总结", "概述", "概括", "summarize", "summary", "归纳"]
        explain_keywords = ["解释", "详细说明", "原理", "概念", "是什么", "explain", "how", "why"]

        if any(kw in q for kw in quiz_keywords):
            return "quiz"
        if any(kw in q for kw in summary_keywords):
            return "summary"
        if any(kw in q for kw in explain_keywords):
            return "explain"
        return "qa"
