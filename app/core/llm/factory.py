"""Single place that turns request/env LLM settings into a client, shared by every agent service."""

from __future__ import annotations

import os
from typing import Any

from app.core.llm.client import (
    GeminiLLMClient,
    LocalOpenAICompatibleClient,
    OpenAICompatibleClient,
)

DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_LOCAL_MODEL = "qwen2.5-coder:7b"
DEFAULT_LOCAL_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_OPENAI_ENDPOINT = "https://api.openai.com/v1"
DEFAULT_DEEPSEEK_ENDPOINT = "https://api.deepseek.com"


class LLMUnavailableError(RuntimeError):
    """Raised when no usable LLM provider can be configured."""


def _model_family(model: str) -> str:
    lowered = model.lower()
    if lowered.startswith("gemini"):
        return "gemini"
    if lowered.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    if lowered.startswith("deepseek"):
        return "deepseek"
    return "local"


def local_endpoint(explicit: str | None = None) -> str:
    return (
        explicit
        or os.getenv("LOCAL_LLM_ENDPOINT")
        or os.getenv("OLLAMA_BASE_URL")
        or DEFAULT_LOCAL_ENDPOINT
    )


def resolve_llm_settings(
    provider: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Resolve provider, model, endpoint and key from the request first, then the environment."""
    env_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    chosen = (provider or env_provider or ("gemini" if (api_key or os.getenv("GEMINI_API_KEY")) else "local")).strip().lower()

    if chosen == "gemini":
        key = api_key or os.getenv("GEMINI_API_KEY")
    elif chosen == "openai":
        key = api_key or os.getenv("OPENAI_API_KEY")
    elif chosen == "deepseek":
        key = api_key or os.getenv("DEEPSEEK_API_KEY")
    else:
        key = api_key

    # A cloud provider without credentials falls back to a configured local model
    if chosen in {"gemini", "openai", "deepseek"} and not key and (env_provider == "local" or os.getenv("LOCAL_LLM_ENDPOINT")):
        chosen, model, endpoint = "local", None, None

    env_model = os.getenv("LLM_MODEL", "").strip()
    defaults = {
        "gemini": DEFAULT_GEMINI_MODEL,
        "openai": DEFAULT_OPENAI_MODEL,
        "deepseek": DEFAULT_DEEPSEEK_MODEL,
        "local": DEFAULT_LOCAL_MODEL,
    }
    resolved_model = (model or "").strip()
    if not resolved_model or _model_family(resolved_model) != chosen:
        resolved_model = env_model if env_model and _model_family(env_model) == chosen else defaults.get(chosen, DEFAULT_LOCAL_MODEL)

    if chosen == "local":
        resolved_endpoint = local_endpoint(endpoint)
    elif chosen == "openai":
        resolved_endpoint = endpoint or os.getenv("OPENAI_API_BASE") or DEFAULT_OPENAI_ENDPOINT
    elif chosen == "deepseek":
        resolved_endpoint = endpoint or os.getenv("DEEPSEEK_API_BASE") or DEFAULT_DEEPSEEK_ENDPOINT
    else:
        resolved_endpoint = None

    return {"provider": chosen, "model": resolved_model, "endpoint": resolved_endpoint, "api_key": key}


def build_llm_client(
    provider: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> Any:
    settings = resolve_llm_settings(provider, model, endpoint, api_key)
    chosen = settings["provider"]
    if chosen == "gemini":
        if not settings["api_key"]:
            raise LLMUnavailableError("Gemini requires GEMINI_API_KEY or a request api_key")
        return GeminiLLMClient(api_key=settings["api_key"], model_name=settings["model"])
    if chosen == "openai":
        if not settings["api_key"]:
            raise LLMUnavailableError("OpenAI requires OPENAI_API_KEY or a request api_key")
        return OpenAICompatibleClient(
            endpoint=settings["endpoint"], model_name=settings["model"], api_key=settings["api_key"]
        )
    if chosen == "deepseek":
        if not settings["api_key"]:
            raise LLMUnavailableError("DeepSeek requires DEEPSEEK_API_KEY or a request api_key")
        return OpenAICompatibleClient(
            endpoint=settings["endpoint"], model_name=settings["model"], api_key=settings["api_key"]
        )
    if chosen == "local":
        return LocalOpenAICompatibleClient(
            endpoint=settings["endpoint"], model_name=settings["model"], api_key=settings["api_key"]
        )
    raise LLMUnavailableError(f"Unsupported LLM provider: {chosen}")
