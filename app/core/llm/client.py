"""
Core LLM client abstractions and provider implementations.

Supports:
- FakeLLMClient (deterministic offline testing)
- GeminiLLMClient (Google Generative AI SDK)
- OpenAICompatibleClient (Corporate/Cloud OpenAI-compatible endpoints)
- LocalOpenAICompatibleClient (Local Vulkan llama-server :8080 and Ollama :11434)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx


_DEFAULT_LOCAL_LLM_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"}


def local_llm_allowed_hosts() -> set[str]:
    """Hosts a "local" LLM may live on: loopback, the Docker host, or names listed in LOCAL_LLM_ALLOWED_HOSTS."""
    extra = {h.strip() for h in os.getenv("LOCAL_LLM_ALLOWED_HOSTS", "").split(",") if h.strip()}
    return _DEFAULT_LOCAL_LLM_HOSTS | extra


class GeminiConfigurationError(RuntimeError):
    """Raised when Gemini settings are missing or invalid."""


class OpenAICompatibleConfigurationError(RuntimeError):
    """Raised when an OpenAI-compatible provider fails or is misconfigured."""


class LocalLLMConfigurationError(OpenAICompatibleConfigurationError):
    """Raised when a local LLM provider fails or is misconfigured."""


@dataclass(frozen=True)
class LLMResponse:
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMClient(Protocol):
    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse: ...


class FakeLLMClient:
    def __init__(self, response: str = "") -> None:
        self.response = response

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        del prompt, kwargs
        return LLMResponse(content=self.response)


class OpenAICompatibleClient:
    """Adapter for OpenAI-compatible servers exposing /v1/chat/completions."""

    def __init__(
        self,
        *,
        endpoint: str,
        model_name: str,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
        verify: bool | str | None = None,
    ) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"}:
            raise OpenAICompatibleConfigurationError(
                "openai-compatible endpoint must use http or https"
            )
        if not model_name.strip():
            raise OpenAICompatibleConfigurationError(
                "openai-compatible model must be set"
            )

        cleaned_endpoint = endpoint.rstrip("/")
        cleaned_endpoint = cleaned_endpoint.removesuffix("/v1")

        self._endpoint = cleaned_endpoint
        self._model_name = model_name.strip()
        self._api_key = (api_key or "").strip() or None
        self._client = client
        default_timeout = float(os.getenv("OPENAI_COMPAT_TIMEOUT", "300.0"))
        self._timeout = timeout if timeout is not None else default_timeout
        self._verify = self._resolve_verify_setting(verify)

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        max_tokens = kwargs.get("max_tokens") or int(
            os.getenv("OPENAI_COMPAT_MAX_TOKENS", "4096")
        )
        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        temperature = kwargs.get("temperature")
        if temperature is None:
            temperature = self._default_temperature_for_model()
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            return await self._send_request(payload, headers, verify_override=None)
        except httpx.ConnectError as exc:
            if not self._should_retry_without_tls_verify(exc):
                raise OpenAICompatibleConfigurationError(
                    f"openai-compatible request to {self._endpoint} failed: {type(exc).__name__}: {exc}"
                ) from exc
            try:
                return await self._send_request(payload, headers, verify_override=False)
            except httpx.HTTPStatusError as retry_exc:
                raise self._format_http_status_error(retry_exc) from retry_exc
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as retry_exc:
                raise OpenAICompatibleConfigurationError(
                    f"openai-compatible request to {self._endpoint} failed after TLS fallback: {type(retry_exc).__name__}: {retry_exc}"
                ) from retry_exc
        except httpx.HTTPStatusError as exc:
            raise self._format_http_status_error(exc) from exc
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise OpenAICompatibleConfigurationError(
                f"openai-compatible request to {self._endpoint} failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _default_temperature_for_model(self) -> float | None:
        lowered = self._model_name.lower()
        if "gpt-5" in lowered:
            return 1.0
        return 0.1

    async def _send_request(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        verify_override: bool | str | None,
    ) -> LLMResponse:
        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(
                timeout=self._timeout,
                verify=self._verify if verify_override is None else verify_override,
            )
        try:
            response = await client.post(
                f"{self._endpoint}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise OpenAICompatibleConfigurationError(
                    "openai-compatible provider returned no textual response"
                )
            usage = data.get("usage") or {}
            return LLMResponse(
                content=content,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )
        finally:
            if owns_client:
                await client.aclose()

    def _format_http_status_error(
        self, exc: httpx.HTTPStatusError
    ) -> OpenAICompatibleConfigurationError:
        response_text = ""
        try:
            response_text = exc.response.text.strip()
        except Exception:
            response_text = ""

        response_json: Any = None
        try:
            response_json = exc.response.json()
        except Exception:
            response_json = None

        detail_parts = []
        if response_json is not None:
            detail_parts.append(f"response json: {response_json}")
        elif response_text:
            detail_parts.append(f"response body: {response_text[:1000]}")

        detail_suffix = f" ({'; '.join(detail_parts)})" if detail_parts else ""
        return OpenAICompatibleConfigurationError(
            f"openai-compatible request to {self._endpoint} failed with HTTP {exc.response.status_code}{detail_suffix}"
        )

    def _resolve_verify_setting(
        self, explicit_verify: bool | str | None
    ) -> bool | str:
        if explicit_verify is not None:
            return explicit_verify

        ca_bundle = (
            os.getenv("OPENAI_CA_BUNDLE")
            or os.getenv("REQUESTS_CA_BUNDLE")
            or os.getenv("SSL_CERT_FILE")
        )
        if ca_bundle:
            return ca_bundle

        if os.getenv("OPENAI_TLS_VERIFY") is not None:
            return _env_flag_enabled("OPENAI_TLS_VERIFY")

        return True

    def _should_retry_without_tls_verify(self, exc: httpx.ConnectError) -> bool:
        if self._client is not None:
            return False
        if not self._endpoint.lower().startswith("https://"):
            return False
        if self._verify is False:
            return False
        if not _env_flag_enabled("OPENAI_TLS_FALLBACK_INSECURE", default=True):
            return False
        message = str(exc).upper()
        return "CERTIFICATE_VERIFY_FAILED" in message or "SSL" in message


class LocalOpenAICompatibleClient(OpenAICompatibleClient):
    """Adapter for local Ollama/llama.cpp servers exposing /v1/chat/completions."""

    def __init__(
        self,
        *,
        endpoint: str,
        model_name: str,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
    ) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in local_llm_allowed_hosts():
            raise LocalLLMConfigurationError(
                "local LLM endpoint must target localhost"
            )
        if not model_name.strip():
            raise LocalLLMConfigurationError("local LLM model must be set")
        super().__init__(
            endpoint=endpoint,
            model_name=model_name,
            api_key=api_key,
            client=client,
            timeout=timeout,
        )

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        try:
            return await super().generate(prompt, **kwargs)
        except OpenAICompatibleConfigurationError as first_exc:
            # If a custom transport client was injected (unit test), do not probe fallback ports
            if self._client is not None:
                raise LocalLLMConfigurationError(str(first_exc)) from first_exc
            # Try alternate local Qwen/Ollama ports (e.g. :8080 vs :11434) automatically
            fallbacks: list[str] = []
            env_ep = (os.getenv("LOCAL_LLM_ENDPOINT") or os.getenv("OLLAMA_BASE_URL") or "").strip().rstrip("/").removesuffix("/v1")
            if env_ep and env_ep != self._endpoint:
                fallbacks.append(env_ep)
            for alt in ("http://127.0.0.1:8080", "http://127.0.0.1:11434"):
                if alt != self._endpoint and alt not in fallbacks:
                    fallbacks.append(alt)
            orig_ep = self._endpoint
            for cand_ep in fallbacks:
                try:
                    self._endpoint = cand_ep
                    return await super().generate(prompt, **kwargs)
                except OpenAICompatibleConfigurationError:
                    continue
                finally:
                    self._endpoint = orig_ep
            raise LocalLLMConfigurationError(str(first_exc)) from first_exc


class GeminiLLMClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        model: Any = None,
    ) -> None:
        self.api_key = (
            api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
        ).strip()
        self.model_name = (
            model_name if model_name is not None else os.getenv("LLM_MODEL", "")
        ).strip()
        if not self.api_key:
            raise GeminiConfigurationError("GEMINI_API_KEY must be set")
        if not self.model_name:
            raise GeminiConfigurationError("LLM_MODEL must be set")
        self._model = model

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        if self._model is None:
            # Disable the SDK's own retry loop: a 429 must surface once instead of burning the quota
            kwargs.setdefault(
                "request_options",
                {"retry": None, "timeout": float(os.getenv("GEMINI_TIMEOUT_SECONDS", "180"))},
            )
        model = self._model or self._build_model()
        result = model.generate_content(prompt, **kwargs)
        if hasattr(result, "__await__"):
            result = await result
        content = getattr(result, "text", None)
        if not isinstance(content, str):
            raise TypeError("Gemini returned no textual response")
        usage = getattr(result, "usage_metadata", None)
        return LLMResponse(
            content=content,
            prompt_tokens=_usage_value(usage, "prompt_token_count"),
            completion_tokens=_usage_value(usage, "candidates_token_count"),
        )

    def _build_model(self) -> Any:
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as exc:
            raise GeminiConfigurationError(
                "The Gemini provider package is required to use GeminiLLMClient"
            ) from exc
        genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(self.model_name)


def _env_flag_enabled(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _usage_value(usage: Any, name: str) -> int | None:
    if usage is None:
        return None
    if isinstance(usage, dict):
        value = usage.get(name)
    else:
        value = getattr(usage, name, None)
    return value if isinstance(value, int) else None