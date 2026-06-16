"""Curated LLM provider and model presets for OpenAI-compatible chat APIs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelPreset:
    id: str
    label: str
    notes: str = ""


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    label: str
    base_url: str | None
    api_key_env: str
    docs_url: str
    models: tuple[ModelPreset, ...]
    openai_compatible: bool = True


PROVIDERS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        id="openai",
        label="OpenAI",
        base_url=None,
        api_key_env="OPENAI_API_KEY",
        docs_url="https://platform.openai.com/docs/models",
        models=(
            ModelPreset("gpt-5.5", "GPT-5.5", "frontier"),
            ModelPreset("gpt-5.4", "GPT-5.4", "balanced frontier"),
            ModelPreset("gpt-5.4-mini", "GPT-5.4 mini", "fast/cost efficient"),
            ModelPreset("gpt-4.1", "GPT-4.1", "strong instruction following"),
            ModelPreset("gpt-4.1-mini", "GPT-4.1 mini", "fast general model"),
            ModelPreset("gpt-4o-mini", "GPT-4o mini", "legacy low-cost default"),
        ),
    ),
    ProviderPreset(
        id="gemini",
        label="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        docs_url="https://ai.google.dev/gemini-api/docs/openai",
        models=(
            ModelPreset("gemini-2.5-pro", "Gemini 2.5 Pro", "reasoning"),
            ModelPreset("gemini-2.5-flash", "Gemini 2.5 Flash", "fast multimodal"),
            ModelPreset("gemini-2.0-flash", "Gemini 2.0 Flash", "fast general model"),
        ),
    ),
    ProviderPreset(
        id="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        docs_url="https://api-docs.deepseek.com/",
        models=(
            ModelPreset("deepseek-v4-flash", "DeepSeek V4 Flash", "current chat/reasoning"),
            ModelPreset("deepseek-chat", "DeepSeek Chat", "legacy alias"),
            ModelPreset("deepseek-reasoner", "DeepSeek Reasoner", "legacy reasoning alias"),
        ),
    ),
    ProviderPreset(
        id="qwen",
        label="Alibaba Qwen / DashScope",
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        docs_url="https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions",
        models=(
            ModelPreset("qwen-max", "Qwen Max", "flagship"),
            ModelPreset("qwen-plus", "Qwen Plus", "balanced"),
            ModelPreset("qwen-turbo", "Qwen Turbo", "fast"),
            ModelPreset("qwen-long", "Qwen Long", "long context"),
        ),
    ),
    ProviderPreset(
        id="kimi",
        label="Moonshot Kimi",
        base_url="https://api.moonshot.ai/v1",
        api_key_env="MOONSHOT_API_KEY",
        docs_url="https://platform.kimi.ai/docs/api/overview",
        models=(
            ModelPreset("moonshot-v1-128k", "Moonshot v1 128K", "long context"),
            ModelPreset("moonshot-v1-32k", "Moonshot v1 32K", "balanced"),
            ModelPreset("moonshot-v1-8k", "Moonshot v1 8K", "fast"),
        ),
    ),
    ProviderPreset(
        id="mistral",
        label="Mistral AI",
        base_url="https://api.mistral.ai/v1",
        api_key_env="MISTRAL_API_KEY",
        docs_url="https://docs.mistral.ai/models",
        models=(
            ModelPreset("mistral-large-latest", "Mistral Large", "flagship"),
            ModelPreset("mistral-medium-latest", "Mistral Medium", "balanced"),
            ModelPreset("mistral-small-latest", "Mistral Small", "fast"),
            ModelPreset("codestral-latest", "Codestral", "coding"),
        ),
    ),
    ProviderPreset(
        id="zhipu",
        label="Zhipu / Z.ai GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key_env="ZHIPU_API_KEY",
        docs_url="https://open.bigmodel.cn/dev/api",
        models=(
            ModelPreset("glm-4.5", "GLM-4.5", "reasoning/coding"),
            ModelPreset("glm-4.5-air", "GLM-4.5 Air", "fast"),
            ModelPreset("glm-4-plus", "GLM-4 Plus", "general"),
        ),
    ),
    ProviderPreset(
        id="xai",
        label="xAI Grok",
        base_url="https://api.x.ai/v1",
        api_key_env="XAI_API_KEY",
        docs_url="https://docs.x.ai/",
        models=(
            ModelPreset("grok-4.3", "Grok 4.3", "flagship"),
            ModelPreset("grok-build-0.1", "Grok Build 0.1", "coding"),
            ModelPreset("grok-4", "Grok 4", "reasoning"),
        ),
    ),
    ProviderPreset(
        id="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        docs_url="https://openrouter.ai/docs/quickstart",
        models=(
            ModelPreset("anthropic/claude-sonnet-4.5", "Claude Sonnet 4.5", "via OpenRouter"),
            ModelPreset("anthropic/claude-opus-4.1", "Claude Opus 4.1", "via OpenRouter"),
            ModelPreset("google/gemini-2.5-pro", "Gemini 2.5 Pro", "via OpenRouter"),
            ModelPreset("x-ai/grok-4", "Grok 4", "via OpenRouter"),
            ModelPreset("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B", "via OpenRouter"),
            ModelPreset("mistralai/mistral-large", "Mistral Large", "via OpenRouter"),
        ),
    ),
    ProviderPreset(
        id="ollama",
        label="Ollama Local",
        base_url="http://localhost:11434/v1",
        api_key_env="OLLAMA_API_KEY",
        docs_url="https://ollama.com/library",
        models=(
            ModelPreset("qwen2.5:7b", "Qwen 2.5 7B", "local"),
            ModelPreset("llama3.1:8b", "Llama 3.1 8B", "local"),
            ModelPreset("deepseek-r1:7b", "DeepSeek R1 7B", "local reasoning"),
            ModelPreset("mistral:7b", "Mistral 7B", "local"),
        ),
    ),
    ProviderPreset(
        id="custom",
        label="Custom OpenAI-Compatible",
        base_url=None,
        api_key_env="ASA_LLM_API_KEY",
        docs_url="",
        models=(ModelPreset("custom-model", "Custom model", "replace with provider model id"),),
    ),
)

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _read_env_file_key(key: str) -> str:
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() == key:
            return value.strip()
    return ""


def get_provider(provider_id: str) -> ProviderPreset:
    return next((provider for provider in PROVIDERS if provider.id == provider_id), PROVIDERS[0])


def provider_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": provider.id,
            "label": provider.label,
            "base_url": provider.base_url,
            "api_key_env": provider.api_key_env,
            "docs_url": provider.docs_url,
            "openai_compatible": provider.openai_compatible,
            "models": [model.__dict__ for model in provider.models],
        }
        for provider in PROVIDERS
    ]


def resolve_llm_client_config(settings: Any) -> dict[str, str | None]:
    provider = get_provider(settings.llm_provider)
    base_url = (
        settings.ollama_base_url
        if provider.id == "ollama"
        else settings.llm_base_url
        or (settings.openai_base_url if provider.id == "openai" else "")
        or provider.base_url
    )
    api_key = (
        "ollama"
        if provider.id == "ollama"
        else os.getenv(provider.api_key_env)
        or _read_env_file_key(provider.api_key_env)
        or os.getenv("ASA_LLM_API_KEY")
        or _read_env_file_key("ASA_LLM_API_KEY")
        or settings.openai_api_key
        or ""
    )
    return {
        "provider": "ollama" if provider.id == "ollama" else "openai",
        "model": settings.llm_model,
        "api_key": api_key,
        "base_url": base_url,
        "api_key_env": provider.api_key_env,
    }
