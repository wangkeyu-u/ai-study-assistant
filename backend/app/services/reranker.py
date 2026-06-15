"""Optional cross-encoder reranking for retrieved candidates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.services.retriever import RetrievedChunk


class BaseReranker(Protocol):
    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]: ...


class CrossEncoderReranker:
    """Rerank query-document pairs with a local sentence-transformers model."""

    def __init__(self, model_name: str, max_length: int = 512):
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as error:
            raise ImportError(
                "sentence-transformers is required when reranking is enabled"
            ) from error
        self.model_name = model_name
        self.model = CrossEncoder(model_name, max_length=max_length)

    def warmup(self) -> None:
        self.model.predict([("warmup query", "warmup document")], show_progress_bar=False)

    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not chunks:
            return []
        scores = self.model.predict(
            [(query, chunk.text) for chunk in chunks],
            show_progress_bar=False,
        )
        for chunk, score in zip(chunks, scores, strict=True):
            chunk.rerank_score = float(score)
        return sorted(
            chunks,
            key=lambda chunk: (chunk.rerank_score or 0.0, chunk.score),
            reverse=True,
        )
