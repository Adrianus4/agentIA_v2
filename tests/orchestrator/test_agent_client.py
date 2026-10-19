import httpx
import pytest
import respx

from app.orchestrator.clients.agent_client import (
    AgentClient,
    AgentHTTPError,
    AgentResponseError,
    AgentTimeoutError,
)
from contracts.models import RepairResult, VerificationResult

VERIFICATION = {
    "success": True,
    "wall_time_seconds": 0.2,
    "issues": [],
    "raw_output": "ok",
    "runner_name": "verifier",
    "image": "test",
}
REPAIR = {
    "outcome": "PATCHED",
    "classification": "CODE_BUG",
    "hypothesis": "fixed",
    "patches": ["diff"],
    "files_touched": ["src/app.py"],
    "guard_report": {"passed": True, "failed_guards": []},
    "attempts_used": 1,
    "trace_id": "trace-1",
}


@pytest.mark.asyncio
@respx.mock
async def test_verify_blueprint_maps_response_to_contract() -> None:
    route = respx.post("http://verifier.test/verify").mock(
        return_value=httpx.Response(200, json=VERIFICATION)
    )

    async with AgentClient("http://verifier.test") as client:
        result = await client.verify_blueprint({"workspace": "demo"})

    assert route.call_count == 1
    assert isinstance(result, VerificationResult)
    assert result.success is True


@pytest.mark.asyncio
@respx.mock
async def test_repair_code_maps_response_to_contract() -> None:
    respx.post("http://repair.test/repair").mock(
        return_value=httpx.Response(200, json=REPAIR)
    )

    async with AgentClient("http://repair.test") as client:
        result = await client.repair_code({"issue": "compile"})

    assert isinstance(result, RepairResult)
    assert result.patches == ["diff"]


@pytest.mark.asyncio
@respx.mock
async def test_retries_two_server_errors_then_succeeds() -> None:
    route = respx.post("http://verifier.test/verify").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(500),
            httpx.Response(200, json=VERIFICATION),
        ]
    )

    async with AgentClient("http://verifier.test") as client:
        result = await client.verify_blueprint({})

    assert route.call_count == 3
    assert result.success is True


@pytest.mark.asyncio
@respx.mock
async def test_stops_after_two_retries() -> None:
    route = respx.post("http://repair.test/repair").mock(
        return_value=httpx.Response(503)
    )

    async with AgentClient("http://repair.test") as client:
        with pytest.raises(AgentHTTPError):
            await client.repair_code({})

    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_invalid_json_schema_raises_response_error() -> None:
    respx.post("http://verifier.test/verify").mock(
        return_value=httpx.Response(200, json={"success": "not-a-bool"})
    )

    async with AgentClient("http://verifier.test") as client:
        with pytest.raises(AgentResponseError):
            await client.verify_blueprint({})


@pytest.mark.asyncio
@respx.mock
async def test_timeout_is_reported_without_unbounded_retry() -> None:
    route = respx.post("http://verifier.test/verify").mock(
        side_effect=httpx.ReadTimeout("timed out")
    )

    async with AgentClient("http://verifier.test") as client:
        with pytest.raises(AgentTimeoutError):
            await client.verify_blueprint({})

    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_client_error_is_not_retried() -> None:
    route = respx.post("http://repair.test/repair").mock(
        return_value=httpx.Response(400, json={"error": "invalid"})
    )

    async with AgentClient("http://repair.test") as client:
        with pytest.raises(AgentHTTPError):
            await client.repair_code({})

    assert route.call_count == 1
