"""Settings API — read/write runtime configuration."""

import os
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.model_catalog import find_provider, provider_catalog, resolve_llm_client_config

router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
_ENV_WRITE_LOCK = threading.Lock()


class ApiKeyStatus(BaseModel):
    has_key: bool
    key_preview: str  # sk-****xxxx
    llm_provider: str
    llm_model: str
    llm_base_url: str | None = None
    embedding_provider: str
    embedding_model: str


class ApiKeyUpdate(BaseModel):
    api_key: str


class ApiKeyUpdateResponse(BaseModel):
    success: bool
    message: str


class ModelSelectionUpdate(BaseModel):
    llm_provider: str
    llm_model: str
    llm_base_url: str | None = None
    api_key: str | None = None


class ModelSelectionResponse(BaseModel):
    success: bool
    message: str
    llm_provider: str
    llm_model: str
    llm_base_url: str | None = None


def _read_env_key(key: str) -> str:
    """Read a key from the .env file."""
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip()
    return ""


def _write_env_values(updates: dict[str, str]) -> None:
    """Atomically update .env values and keep secrets private to the owner."""
    if any("\n" in value or "\r" in value for value in updates.values()):
        raise ValueError("Environment values cannot contain line breaks")
    with _ENV_WRITE_LOCK:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
        remaining = dict(updates)
        output: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                output.append(line)
                continue
            key, _ = stripped.split("=", 1)
            key = key.strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
            else:
                output.append(line)

        output.extend(f"{key}={value}" for key, value in remaining.items())
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{ENV_FILE.name}.", dir=ENV_FILE.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                temp_file.write("\n".join(output) + "\n")
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, ENV_FILE)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def _write_env_key(key: str, value: str) -> None:
    _write_env_values({key: value})


def _validate_base_url(value: str) -> str:
    """Accept only absolute HTTP(S) API endpoints without embedded credentials."""
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Base URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise HTTPException(
            status_code=400,
            detail="Base URL cannot contain credentials or a fragment",
        )
    return value.rstrip("/")


def _validate_single_line(value: str, field_name: str) -> str:
    if "\n" in value or "\r" in value:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot contain line breaks")
    return value


def _mask_key(key: str) -> str:
    """Mask an API key for safe display: sk-09e6...aee0 → sk-****aee0"""
    if not key or len(key) < 8:
        return "****" if key else ""
    return f"{key[:3]}****{key[-4:]}"


def _apply_runtime_llm_settings() -> None:
    """Refresh the in-memory generator after model settings change."""
    import app.main as main_module
    from app.config import get_settings
    from app.services.generator import Generator

    settings = get_settings()
    llm_config = resolve_llm_client_config(settings)
    if main_module.rag_pipeline is not None:
        main_module.rag_pipeline.generator = Generator(
            provider=llm_config["provider"] or "openai",
            model=llm_config["model"] or settings.llm_model,
            api_key=llm_config["api_key"] or "",
            base_url=llm_config["base_url"],
        )


@router.get("/api-key", response_model=ApiKeyStatus)
async def get_api_key_status():
    """Get current API key status (masked)."""
    from app.config import get_settings

    settings = get_settings()

    llm_config = resolve_llm_client_config(settings)
    key_env = str(llm_config["api_key_env"] or "OPENAI_API_KEY")
    key = str(llm_config["api_key"] or "") or _read_env_key(key_env)

    return ApiKeyStatus(
        has_key=bool(key),
        key_preview=_mask_key(key),
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        llm_base_url=str(llm_config["base_url"] or "") or None,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
    )


@router.post("/api-key", response_model=ApiKeyUpdateResponse)
async def update_api_key(body: ApiKeyUpdate):
    """Update the OpenAI API key. Writes to .env and updates runtime env."""
    key = body.api_key.strip()
    if not key:
        return ApiKeyUpdateResponse(success=False, message="API Key 不能为空")
    _validate_single_line(key, "API key")

    # Write to .env file
    _write_env_key("OPENAI_API_KEY", key)

    # Update runtime environment variable so it takes effect immediately
    os.environ["OPENAI_API_KEY"] = key

    return ApiKeyUpdateResponse(
        success=True,
        message=f"API Key 已更新（{_mask_key(key)}）。部分功能可能需要刷新页面后生效。",
    )


@router.get("/models")
async def get_model_catalog():
    """Return built-in LLM provider and model presets."""
    from app.config import get_settings

    settings = get_settings()
    llm_config = resolve_llm_client_config(settings)
    return {
        "providers": provider_catalog(),
        "current": {
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "llm_base_url": str(llm_config["base_url"] or "") or None,
        },
    }


@router.post("/model", response_model=ModelSelectionResponse)
async def update_model_selection(body: ModelSelectionUpdate):
    """Update LLM provider/model settings in .env and refresh runtime generator."""
    from app.config import get_settings

    provider = find_provider(body.llm_provider)
    if provider is None:
        raise HTTPException(status_code=400, detail=f"Unknown LLM provider: {body.llm_provider}")
    model = _validate_single_line(body.llm_model.strip(), "Model")
    if not model:
        raise HTTPException(status_code=400, detail="Model cannot be empty")

    base_url = _validate_base_url((body.llm_base_url or provider.base_url or "").strip())
    if provider.id == "custom" and not base_url:
        raise HTTPException(status_code=400, detail="Custom providers require a Base URL")
    env_updates = {
        "ASA_LLM_PROVIDER": provider.id,
        "ASA_LLM_MODEL": model,
        "ASA_LLM_BASE_URL": base_url,
    }
    if body.api_key and body.api_key.strip():
        api_key = _validate_single_line(body.api_key.strip(), "API key")
        env_updates[provider.api_key_env] = api_key
        if provider.id == "openai":
            env_updates["OPENAI_API_KEY"] = api_key

    _write_env_values(env_updates)

    if body.api_key and body.api_key.strip():
        os.environ[provider.api_key_env] = api_key
        if provider.id == "openai":
            os.environ["OPENAI_API_KEY"] = api_key
    os.environ["ASA_LLM_PROVIDER"] = provider.id
    os.environ["ASA_LLM_MODEL"] = model
    os.environ["ASA_LLM_BASE_URL"] = base_url

    settings = get_settings()
    settings.llm_provider = provider.id
    settings.llm_model = model
    settings.llm_base_url = base_url
    _apply_runtime_llm_settings()

    return ModelSelectionResponse(
        success=True,
        message=f"Model updated to {provider.label} / {model}",
        llm_provider=provider.id,
        llm_model=model,
        llm_base_url=base_url or None,
    )
