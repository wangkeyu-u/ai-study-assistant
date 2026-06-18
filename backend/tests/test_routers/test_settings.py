"""Tests for provider and model settings updates."""

import os
import stat
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.config as config_module
import app.routers.settings as settings_router
from app.routers.settings import ModelSelectionUpdate


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    runtime_settings = SimpleNamespace(
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_base_url="",
        ollama_base_url="http://localhost:11434/v1",
        openai_base_url="",
        openai_api_key="",
    )
    monkeypatch.setattr(settings_router, "ENV_FILE", env_file)
    monkeypatch.setattr(config_module, "_settings", runtime_settings)
    monkeypatch.setattr(settings_router, "_apply_runtime_llm_settings", lambda: None)
    return env_file, runtime_settings


@pytest.mark.asyncio
async def test_model_update_writes_provider_key_atomically(isolated_settings, monkeypatch):
    env_file, runtime_settings = isolated_settings
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    response = await settings_router.update_model_selection(
        ModelSelectionUpdate(
            llm_provider="deepseek",
            llm_model="deepseek-chat",
            api_key="deepseek-secret",
        )
    )

    contents = env_file.read_text(encoding="utf-8")
    assert response.success is True
    assert "ASA_LLM_PROVIDER=deepseek" in contents
    assert "ASA_LLM_MODEL=deepseek-chat" in contents
    assert "ASA_LLM_BASE_URL=https://api.deepseek.com" in contents
    assert "DEEPSEEK_API_KEY=deepseek-secret" in contents
    assert "OPENAI_API_KEY" not in contents
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert runtime_settings.llm_provider == "deepseek"
    assert os.environ["DEEPSEEK_API_KEY"] == "deepseek-secret"


@pytest.mark.asyncio
async def test_model_update_rejects_unknown_provider_without_writing(isolated_settings):
    env_file, _ = isolated_settings

    with pytest.raises(HTTPException, match="Unknown LLM provider") as exc_info:
        await settings_router.update_model_selection(
            ModelSelectionUpdate(llm_provider="typo-provider", llm_model="some-model")
        )

    assert exc_info.value.status_code == 400
    assert not env_file.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url",
    ["file:///etc/passwd", "api.example.com/v1", "https://user:pass@example.com/v1"],
)
async def test_model_update_rejects_unsafe_base_url(isolated_settings, base_url):
    env_file, _ = isolated_settings

    with pytest.raises(HTTPException):
        await settings_router.update_model_selection(
            ModelSelectionUpdate(
                llm_provider="custom",
                llm_model="custom-model",
                llm_base_url=base_url,
            )
        )

    assert not env_file.exists()


@pytest.mark.asyncio
async def test_model_update_rejects_env_line_injection(isolated_settings):
    env_file, _ = isolated_settings

    with pytest.raises(HTTPException, match="cannot contain line breaks"):
        await settings_router.update_model_selection(
            ModelSelectionUpdate(
                llm_provider="openai",
                llm_model="gpt-4o-mini\nINJECTED=value",
            )
        )

    assert not env_file.exists()


@pytest.mark.asyncio
async def test_custom_provider_requires_base_url(isolated_settings):
    env_file, _ = isolated_settings

    with pytest.raises(HTTPException, match="require a Base URL"):
        await settings_router.update_model_selection(
            ModelSelectionUpdate(llm_provider="custom", llm_model="custom-model")
        )

    assert not env_file.exists()
