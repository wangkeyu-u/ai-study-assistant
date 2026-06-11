"""Embedding generation — supports OpenAI API and local sentence-transformers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseEmbedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, return list of vectors."""
        ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed a single query."""
        ...


class OpenAIEmbedder(BaseEmbedder):
    """Use OpenAI API for embeddings (also works with any OpenAI-compatible endpoint)."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", base_url: str | None = None):
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in resp.data]

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]


class LocalEmbedder(BaseEmbedder):
    """Use sentence-transformers for local embedding (no API key needed)."""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
        logger.info("Loading local embedding model: %s", model_name)
        self.model = SentenceTransformer(model_name)
        logger.info("Local embedding model loaded.")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        # BGE models benefit from a query prefix
        return self.embed([f"为这个句子生成表示以用于检索: {query}"])[0]


def create_embedder(provider: str, **kwargs) -> BaseEmbedder:
    """Factory function to create an embedder based on config."""
    if provider == "openai":
        return OpenAIEmbedder(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "text-embedding-3-small"),
            base_url=kwargs.get("base_url"),
        )
    elif provider == "local":
        return LocalEmbedder(
            model_name=kwargs.get("model", "BAAI/bge-small-zh-v1.5"),
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
