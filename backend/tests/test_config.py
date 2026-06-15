"""Tests for app.config — Settings initialization and defaults."""

import os

from app.config import Settings


def test_settings_defaults(monkeypatch):
    """Settings should have sensible defaults when no env vars are set."""
    # Clear any ASA_ prefixed env vars that might override defaults
    for key in list(os.environ):
        if key.startswith("ASA_"):
            monkeypatch.delenv(key, raising=False)
    # Disable .env file loading to test true defaults
    s = Settings(_env_file=None)
    assert s.chunk_size == 512
    assert s.chunk_overlap == 64
    assert s.top_k == 5
    assert s.similarity_threshold == 0.3
    assert s.hybrid_search_enabled is True
    assert s.retrieval_candidate_multiplier == 4
    assert s.rrf_k == 60
    assert s.retrieval_confidence_gate_enabled is True
    assert s.vector_only_min_score == 0.46
    assert s.reranker_enabled is False
    assert s.reranker_model == "BAAI/bge-reranker-v2-m3"
    assert s.reranker_top_n == 12
    assert s.embedding_provider == "openai"
    assert s.llm_provider == "openai"
    assert s.max_upload_size_mb == 50
    assert ".pdf" in s.supported_extensions


def test_settings_post_init_creates_dirs(tmp_path, monkeypatch):
    """model_post_init should create required directories."""
    data_dir = str(tmp_path / "test_data")
    monkeypatch.setenv("ASA_APP_DATA_DIR", data_dir)

    s = Settings()
    assert os.path.isdir(s.documents_dir)
    assert os.path.isdir(s.chroma_dir)
    assert s.db_path.endswith("app.db")


def test_settings_env_override(monkeypatch):
    """Environment variables with ASA_ prefix should override defaults."""
    monkeypatch.setenv("ASA_CHUNK_SIZE", "256")
    monkeypatch.setenv("ASA_TOP_K", "10")
    monkeypatch.setenv("ASA_LLM_MODEL", "gpt-4o")

    s = Settings()
    assert s.chunk_size == 256
    assert s.top_k == 10
    assert s.llm_model == "gpt-4o"


def test_openai_api_key_from_env(monkeypatch):
    """openai_api_key should read OPENAI_API_KEY (no ASA_ prefix)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    s = Settings()
    assert s.openai_api_key == "sk-test-123"


def test_openai_api_key_empty_when_not_set(monkeypatch):
    """openai_api_key should return empty string when not set."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = Settings()
    assert s.openai_api_key == ""
