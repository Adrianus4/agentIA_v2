from __future__ import annotations

import types
from typing import Any, Self

import httpx
from pydantic import ValidationError

from contracts.agent_api import (
    GenerationAgentResponse,
    RepairAgentResponse,
    ValidationAgentResponse,
    VerifierAgentResponse,
)


class AgentClientError(RuntimeError):
    """Base error for remote agent adapter failures."""


class AgentTimeoutError(AgentClientError):
    """Raised when a remote agent exceeds the request timeout."""


class AgentHTTPError(AgentClientError):
    """Raised when a remote agent returns an unsuccessful HTTP status."""


class AgentResponseError(AgentClientError):
    """Raised when a remote response is not valid for its contract."""


class AgentClient:
    def __init__(
        self,
        *,
        validator_url: str,
        generator_url: str,
        verifier_url: str,
        repair_url: str,
        validate_path: str = "/v1/validate",
        generate_path: str = "/v1/generate",
        verify_path: str = "/v1/verify",
        repair_path: str = "/v1/repair",
        timeout: float = 30.0,
        max_retries: int = 2,
        api_key: str | None = None,
        bearer_token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self._validator_url = validator_url.rstrip("/")
        self._generator_url = generator_url.rstrip("/")
        self._verifier_url = verifier_url.rstrip("/")
        self._repair_url = repair_url.rstrip("/")
        self._validate_path = validate_path
        self._generate_path = generate_path
        self._verify_path = verify_path
        self._repair_path = repair_path
        self._timeout = timeout
        self._max_retries = max_retries
        self._api_key = api_key
        self._bearer_token = bearer_token
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> Self:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def validate_blueprint(
        self, payload: dict[str, Any]
    ) -> ValidationAgentResponse:
        data = await self._post(self._validator_url, self._validate_path, payload)
        return self._parse(data, ValidationAgentResponse, "validator")

    async def generate_code(self, payload: dict[str, Any]) -> GenerationAgentResponse:
        data = await self._post(self._generator_url, self._generate_path, payload, retries=0)
        return self._parse(data, GenerationAgentResponse, "generator")

    async def verify_workspace(self, payload: dict[str, Any]) -> VerifierAgentResponse:
        data = await self._post(self._verifier_url, self._verify_path, payload, retries=0)
        return self._parse(data, VerifierAgentResponse, "verifier")

    async def repair_code(self, payload: dict[str, Any]) -> RepairAgentResponse:
        data = await self._post(self._repair_url, self._repair_path, payload, retries=0)
        return self._parse(data, RepairAgentResponse, "repair")

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        return headers

    async def _post(
        self,
        base_url: str,
        path: str,
        payload: dict[str, Any],
        *,
        retries: int | None = None,
    ) -> dict[str, Any]:
        """POST with 5xx retries; expensive non-idempotent calls (LLM, Maven) pass retries=0."""
        max_retries = self._max_retries if retries is None else retries
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        client = self._client
        created_here = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout)
        try:
            for attempt in range(max_retries + 1):
                try:
                    response = await client.post(
                        f"{base_url}/{path.lstrip('/')}",
                        json=payload,
                        headers=self._headers(),
                    )
                except httpx.TimeoutException as exc:
                    raise AgentTimeoutError("agent request timed out") from exc
                except httpx.HTTPError as exc:
                    raise AgentClientError("agent request failed") from exc
                if response.status_code >= 500 and attempt < max_retries:
                    continue
                if response.status_code >= 400:
                    detail = response.text[:500] if response.text else ""
                    raise AgentHTTPError(f"agent returned HTTP {response.status_code}: {detail}")
                try:
                    data = response.json()
                except ValueError as exc:
                    raise AgentResponseError("agent returned invalid JSON") from exc
                if not isinstance(data, dict):
                    raise AgentResponseError("agent response must be a JSON object")
                return data
            raise AgentHTTPError("agent request failed after retries")
        finally:
            if created_here:
                await client.aclose()

    @staticmethod
    def _parse(data: dict[str, Any], schema: type[Any], service: str) -> Any:
        try:
            if hasattr(schema, "model_validate"):
                return schema.model_validate(data)
            return schema.parse_obj(data)
        except ValidationError as exc:
            raise AgentResponseError(
                f"{service} response failed schema validation"
            ) from exc