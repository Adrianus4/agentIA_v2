import pytest

from app.core.llm.client import (
    FakeLLMClient,
    GeminiConfigurationError,
    GeminiLLMClient,
    LLMResponse,
    LocalOpenAICompatibleClient,
)
from contracts.models import LLMConfiguration, SpecDraftRequest
import httpx


@pytest.mark.asyncio
async def test_fake_client_returns_deterministic_response() -> None:
    client = FakeLLMClient(response="offline result")

    first = await client.generate("same prompt")
    second = await client.generate("same prompt")

    assert first == second == LLMResponse(content="offline result")


def test_llm_response_contains_optional_usage_fields() -> None:
    response = LLMResponse(
        content="generated",
        prompt_tokens=12,
        completion_tokens=7,
    )

    assert response.content == "generated"
    assert response.prompt_tokens == 12
    assert response.completion_tokens == 7


def test_gemini_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_MODEL", "test-model")

    with pytest.raises(GeminiConfigurationError, match="GEMINI_API_KEY"):
        GeminiLLMClient()


def test_local_llm_configuration_requires_loopback_endpoint() -> None:
    with pytest.raises(ValueError, match="localhost"):
        LLMConfiguration(
            provider="local",
            model="qwen2.5-coder:3b",
            endpoint="https://example.com/v1",
        )


def test_spec_directive_rejects_embedded_secret() -> None:
    with pytest.raises(ValueError, match="secret"):
        SpecDraftRequest(
            directive="Create a service with api_key=super-secret-value",
        )


@pytest.mark.asyncio
async def test_local_llm_client_parses_openai_compatible_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LocalOpenAICompatibleClient(
            endpoint="http://127.0.0.1:11434",
            model_name="qwen2.5-coder:3b",
            client=http_client,
        )
        response = await client.generate("Return JSON")

    assert response.content == '{"ok": true}'
    assert response.prompt_tokens == 3
    assert response.completion_tokens == 2
