"""Settings API — read/write runtime configuration."""

import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class ApiKeyStatus(BaseModel):
    has_key: bool
    key_preview: str  # sk-****xxxx
    llm_provider: str
    llm_model: str
    embedding_provider: str
    embedding_model: str


class ApiKeyUpdate(BaseModel):
    api_key: str


class ApiKeyUpdateResponse(BaseModel):
    success: bool
    message: str


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


def _write_env_key(key: str, value: str) -> None:
    """Write or update a key in the .env file."""
    lines: list[str] = []
    found = False

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                lines.append(line)
                continue
            k, _ = stripped.split("=", 1)
            if k.strip() == key:
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)

    if not found:
        lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(lines) + "\n")


def _mask_key(key: str) -> str:
    """Mask an API key for safe display: sk-09e6...aee0 → sk-****aee0"""
    if not key or len(key) < 8:
        return "****" if key else ""
    return f"{key[:3]}****{key[-4:]}"


@router.get("/api-key", response_model=ApiKeyStatus)
async def get_api_key_status():
    """Get current API key status (masked)."""
    from app.config import get_settings

    settings = get_settings()

    key = settings.openai_api_key or _read_env_key("OPENAI_API_KEY")

    return ApiKeyStatus(
        has_key=bool(key),
        key_preview=_mask_key(key),
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
    )


@router.post("/api-key", response_model=ApiKeyUpdateResponse)
async def update_api_key(body: ApiKeyUpdate):
    """Update the OpenAI API key. Writes to .env and updates runtime env."""
    key = body.api_key.strip()
    if not key:
        return ApiKeyUpdateResponse(success=False, message="API Key 不能为空")

    # Write to .env file
    _write_env_key("OPENAI_API_KEY", key)

    # Update runtime environment variable so it takes effect immediately
    os.environ["OPENAI_API_KEY"] = key

    return ApiKeyUpdateResponse(
        success=True,
        message=f"API Key 已更新（{_mask_key(key)}）。部分功能可能需要刷新页面后生效。",
    )
