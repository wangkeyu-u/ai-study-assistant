"""Application configuration with pydantic-settings."""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Paths ──────────────────────────────────────────────
    app_data_dir: str = os.path.expanduser("~/.ai-study-assistant")
    documents_dir: str = ""  # filled in model_post_init
    chroma_dir: str = ""
    db_path: str = ""

    # ── Embedding ──────────────────────────────────────────
    embedding_provider: str = "openai"  # "openai" | "local"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # ── LLM ────────────────────────────────────────────────
    llm_provider: str = "openai"  # "openai" | "ollama"
    llm_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434/v1"
    openai_base_url: str = ""  # custom base URL (e.g. DeepSeek)

    # ── RAG ────────────────────────────────────────────────
    chunk_size: int = 512  # target tokens per chunk
    chunk_overlap: int = 64  # overlap tokens
    top_k: int = 5  # retrieval top-k
    similarity_threshold: float = 0.3  # min similarity to include
    hybrid_search_enabled: bool = True
    retrieval_candidate_multiplier: int = 4
    rrf_k: int = 60
    retrieval_confidence_gate_enabled: bool = True
    vector_only_min_score: float = 0.46
    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_n: int = 12

    # ── Upload ─────────────────────────────────────────────
    max_upload_size_mb: int = 50
    supported_extensions: list[str] = [".pdf", ".txt", ".md"]

    # ── Server ─────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8000

    model_config = {"env_prefix": "ASA_", "env_file": ".env", "extra": "ignore"}

    @property
    def openai_api_key(self) -> str:
        """Read OPENAI_API_KEY directly from environment (no ASA_ prefix)."""
        return os.getenv("OPENAI_API_KEY", "")

    def model_post_init(self, __context):
        os.makedirs(self.app_data_dir, exist_ok=True)
        self.documents_dir = os.path.join(self.app_data_dir, "data", "documents")
        self.chroma_dir = os.path.join(self.app_data_dir, "data", "chroma_db")
        self.db_path = os.path.join(self.app_data_dir, "data", "app.db")
        for d in [self.documents_dir, self.chroma_dir]:
            os.makedirs(d, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
