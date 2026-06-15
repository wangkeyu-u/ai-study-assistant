"""Base agent interface for the Multi-Agent system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field


@dataclass
class AgentResponse:
    """Standardized response from any agent.

    Attributes:
        content: The main text response.
        agent_name: Name of the agent that handled the request.
        metadata: Optional extra data (citations, quiz payload, token usage, etc.)
    """

    content: str
    agent_name: str
    metadata: dict = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base class that all specialist agents must implement."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def process(self, query: str, context: dict | None = None) -> AgentResponse:
        """Process a user query and return a response.

        Args:
            query: The user's natural-language query.
            context: Optional runtime context (conversation history, collection_id,
                     RAG pipeline reference, etc.).

        Returns:
            An AgentResponse with content and metadata.
        """
        ...  # pragma: no cover

    async def process_stream(
        self, query: str, context: dict | None = None
    ) -> AsyncGenerator[dict, None]:
        """Stream the agent's response, yielding token/citation/done events.

        Default implementation wraps the non-streaming process() method:
        renders the full response as a single token event then a done event.
        Subclasses can override for true streaming with citation extraction.
        """
        response = await self.process(query, context)
        yield {"type": "token", "text": response.content}
        yield {
            "type": "done",
            "agent_name": response.agent_name,
            "content": response.content,
            "metadata": response.metadata,
        }
