"""Tests for the built-in LLM provider catalog."""

from types import SimpleNamespace

import app.services.model_catalog as catalog_module
from app.services.model_catalog import get_provider, provider_catalog, resolve_llm_client_config


def test_provider_catalog_includes_mainstream_api_providers():
    provider_ids = {provider["id"] for provider in provider_catalog()}

    assert {
        "openai",
        "gemini",
        "deepseek",
        "qwen",
        "kimi",
        "mistral",
        "zhipu",
        "xai",
        "openrouter",
        "ollama",
        "custom",
    } <= provider_ids


def test_get_provider_falls_back_to_openai_for_unknown_provider():
    assert get_provider("missing").id == "openai"


def test_resolve_llm_client_config_uses_provider_specific_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    settings = SimpleNamespace(
        llm_provider="deepseek",
        llm_model="deepseek-v4-flash",
        llm_base_url="",
        ollama_base_url="http://localhost:11434/v1",
        openai_base_url="",
        openai_api_key="openai-key",
    )

    config = resolve_llm_client_config(settings)

    assert config["provider"] == "openai"
    assert config["model"] == "deepseek-v4-flash"
    assert config["api_key"] == "deepseek-key"
    assert config["base_url"] == "https://api.deepseek.com"


def test_resolve_llm_client_config_reads_provider_key_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=gemini-from-file\n", encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(catalog_module, "ENV_FILE", env_file)
    settings = SimpleNamespace(
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        llm_base_url="",
        ollama_base_url="http://localhost:11434/v1",
        openai_base_url="",
        openai_api_key="",
    )

    config = resolve_llm_client_config(settings)

    assert config["api_key"] == "gemini-from-file"


def test_resolve_llm_client_config_supports_ollama_without_real_key():
    settings = SimpleNamespace(
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
        llm_base_url="",
        ollama_base_url="http://localhost:11434/v1",
        openai_base_url="",
        openai_api_key="",
    )

    config = resolve_llm_client_config(settings)

    assert config["provider"] == "ollama"
    assert config["api_key"] == "ollama"
    assert config["base_url"] == "http://localhost:11434/v1"
