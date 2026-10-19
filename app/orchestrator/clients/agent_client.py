import types
from typing import Any, Self

import httpx
from pydantic import ValidationError

from contracts.models import RepairResult, VerificationResult


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
        base_url: str,
        *,
        verifier_path: str = "/verify",
        repair_path: str = "/repair",
        timeout: float = 30.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self._base_url = base_url.rstrip("/")
        self._verifier_path = verifier_path
        self._repair_path = repair_path
        self._timeout = timeout
        self._max_retries = max_retries
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

    async def verify_blueprint(self, payload: dict) -> VerificationResult:
        data = await self._post(self._verifier_path, payload)
        return self._parse(data, VerificationResult, "verifier")

    async def repair_code(self, payload: dict) -> RepairResult:
        data = await self._post(self._repair_path, payload)
        return self._parse(data, RepairResult, "repair")

    async def _post(self, path: str, payload: dict) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        client = self._client
        created_here = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout)
        try:
            for attempt in range(self._max_retries + 1):
                try:
                    response = await client.post(
                        f"{self._base_url}/{path.lstrip('/')}",
                        json=payload,
                    )
                except httpx.TimeoutException as exc:
                    raise AgentTimeoutError("agent request timed out") from exc
                except httpx.HTTPError as exc:
                    raise AgentClientError("agent request failed") from exc
                if response.status_code >= 500 and attempt < self._max_retries:
                    continue
                if response.status_code >= 400:
                    raise AgentHTTPError(
                        f"agent returned HTTP {response.status_code}"
                    )
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
