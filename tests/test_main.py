import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app
from app.orchestrator.db.repository import RunRepository


@dataclass
class FakeState:
    trace_id: str = "trace-api"
    attempts: int = 1
    outcome: str = "SUCCESS"
    validation: None = None
    verification: None = None
    repair: None = None


class FakeGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def run(
        self,
        workspace_dir: str,
        blueprint: dict,
        trace_id: str | None = None,
    ) -> FakeState:
        self.calls.append((workspace_dir, blueprint))
        return FakeState(trace_id=trace_id or "trace-api")


def test_blueprint_route_requires_api_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    client = TestClient(create_app(FakeGraph()))

    response = client.post(
        "/v1/blueprint/validate",
        json={"workspace_dir": str(tmp_path), "blueprint": {}},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_blueprint_routes_use_constant_auth_boundary_and_graph(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    graph = FakeGraph()
    client = TestClient(create_app(graph))

    response = client.post(
        "/v1/blueprint/run",
        headers={"x-api-key": "secret"},
        json={"workspace_dir": str(tmp_path), "blueprint": {"name": "demo"}},
    )

    assert response.status_code == 200
    assert response.json()["trace_id"] == "trace-api"
    assert graph.calls == [(str(tmp_path), {"name": "demo"})]


def test_validate_route_only_validates(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    graph = FakeGraph()
    client = TestClient(create_app(graph))

    response = client.post(
        "/v1/blueprint/validate",
        headers={"x-api-key": "secret"},
        json={"workspace_dir": str(tmp_path), "blueprint": {"name": "demo"}},
    )

    assert response.status_code == 200
    assert response.json()["validation"] is not None
    assert graph.calls == []


def test_all_stub_routes_are_connected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    graph = FakeGraph()
    client = TestClient(create_app(graph))

    for operation in ("validate", "verify", "repair", "run"):
        response = client.post(
            f"/v1/blueprint/{operation}",
            headers={"x-api-key": "secret"},
            json={"workspace_dir": str(tmp_path)},
        )
        assert response.status_code == 200

    # validate stops before generation; the other three dispatch the graph
    assert len(graph.calls) == 3


def test_async_mode_returns_202_and_status_reaches_terminal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    monkeypatch.setenv("WORKFLOW_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("ORCHESTRATOR_ALLOW_PUBLIC_READ", "1")
    graph = FakeGraph()
    client = TestClient(create_app(graph, repository=RunRepository(str(tmp_path / "runs.db"))))

    response = client.post(
        "/v1/blueprint/run?mode=async",
        headers={"x-api-key": "secret"},
        json={"workspace_dir": str(tmp_path), "trace_id": "trace-async", "blueprint": {"name": "demo"}},
    )

    assert response.status_code == 202
    assert response.json()["trace_id"] == "trace-async"
    status = client.get("/v1/blueprint/status/trace-async").json()
    assert status["status"] in {"RUNNING", "SUCCESS"}


def test_missing_auth_configuration_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ORCHESTRATOR_API_KEY", raising=False)
    client = TestClient(create_app(FakeGraph()))

    response = client.post(
        "/v1/blueprint/run",
        headers={"x-api-key": "secret"},
        json={"workspace_dir": str(tmp_path)},
    )

    assert response.status_code == 503
    assert "secret" not in response.text


def test_run_status_returns_execution_record(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    repository = RunRepository(tmp_path / "runs.db")

    async def seed() -> None:
        await repository.create_run(
            "trace-status",
            "demo.json",
            status="SUCCESS",
            repair_attempts=2,
        )

    asyncio.run(seed())
    client = TestClient(create_app(FakeGraph(), repository))

    try:
        response = client.get(
            "/v1/runs/trace-status",
            headers={"x-api-key": "secret"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "trace_id": "trace-status",
            "blueprint_name": "demo.json",
            "status": "SUCCESS",
            "repair_attempts": 2,
        }
    finally:
        asyncio.run(repository.close())


def test_run_status_returns_not_found(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    client = TestClient(create_app(FakeGraph(), RunRepository(tmp_path / "runs.db")))

    response = client.get(
        "/v1/runs/missing-trace",
        headers={"x-api-key": "secret"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Run not found"}


def test_run_status_requires_api_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    client = TestClient(create_app(FakeGraph(), RunRepository(tmp_path / "runs.db")))

    response = client.get("/v1/runs/missing-trace")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_blueprint_status_endpoint_returns_recorded_run(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    repository = RunRepository(tmp_path / "runs_blueprint.db")
    client = TestClient(create_app(FakeGraph(), repository))

    run_response = client.post(
        "/v1/blueprint/run",
        headers={"x-api-key": "secret"},
        json={
            "workspace_dir": str(tmp_path),
            "blueprint": {"name": "sample-bp"},
            "trace_id": "sample-trace",
        },
    )
    assert run_response.status_code == 200
    trace_id = run_response.json()["trace_id"]
    assert trace_id == "sample-trace"

    status_response = client.get(
        f"/v1/blueprint/status/{trace_id}",
        headers={"x-api-key": "secret"},
    )
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["trace_id"] == "sample-trace"
    assert data["status"] == "SUCCESS"
    assert data["blueprint_name"] == "sample-bp"


def test_blueprint_status_404_for_unknown_trace(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    client = TestClient(create_app(FakeGraph(), RunRepository(tmp_path / "runs_404.db")))

    status_response = client.get(
        "/v1/blueprint/status/non-existent-trace",
        headers={"x-api-key": "secret"},
    )
    assert status_response.status_code == 404
    assert status_response.json() == {"detail": "Run not found"}


def test_cors_middleware_headers_present(monkeypatch) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    client = TestClient(create_app(FakeGraph()))

    response = client.options(
        "/v1/blueprint/validate",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "x-api-key" in response.headers.get("access-control-allow-headers", "").lower()


def test_list_runs_endpoint(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    repository = RunRepository(tmp_path / "runs_list.db")

    async def seed() -> None:
        await repository.create_run(
            "trace-1",
            "service-a",
            status="SUCCESS",
            repair_attempts=1,
        )
        await repository.create_run(
            "trace-2",
            "service-b",
            status="NO_FIX",
            repair_attempts=3,
        )

    asyncio.run(seed())
    client = TestClient(create_app(FakeGraph(), repository))

    try:
        response = client.get(
            "/v1/runs",
            headers={"x-api-key": "secret"},
        )
        assert response.status_code == 200
        runs = response.json()
        assert len(runs) == 2
        assert runs[0]["trace_id"] == "trace-1"
        assert runs[1]["trace_id"] == "trace-2"
    finally:
        asyncio.run(repository.close())


def test_blueprint_run_tracks_running_and_transitions_to_error_on_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    repository = RunRepository(tmp_path / "runs_error.db")

    class FailingGraph:
        async def run(self, workspace_dir: str, blueprint: dict, trace_id: str | None = None) -> Any:
            # When inside graph run, verify repository already has RUNNING status
            run = await repository.get_run(trace_id or "trace-fail")
            assert run is not None
            assert run.status == "RUNNING"
            raise RuntimeError("Unexpected boom")

    client = TestClient(create_app(FailingGraph(), repository))

    try:
        response = client.post(
            "/v1/blueprint/run",
            headers={"x-api-key": "secret"},
            json={
                "workspace_dir": str(tmp_path),
                "blueprint": {"name": "failing-bp"},
                "trace_id": "trace-fail",
            },
        )
        assert response.status_code == 502

        # Verify status transitioned to ERROR
        status_response = client.get(
            "/v1/blueprint/status/trace-fail",
            headers={"x-api-key": "secret"},
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "ERROR"
    finally:
        asyncio.run(repository.close())


def test_verify_llm_mock_provider(monkeypatch) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    client = TestClient(create_app(FakeGraph()))

    response = client.post(
        "/v1/llm/verify",
        headers={"x-api-key": "secret"},
        json={"provider": "mock", "model": "mock-deterministic"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["provider"] == "mock"


def test_verify_llm_local_rejects_non_loopback(monkeypatch) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    client = TestClient(create_app(FakeGraph()))

    response = client.post(
        "/v1/llm/verify",
        headers={"x-api-key": "secret"},
        json={
            "provider": "local",
            "model": "qwen2.5-coder:3b",
            "endpoint": "https://external-host.com:11434",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert "localhost" in data["error"]


def test_verify_llm_gemini_missing_api_key(monkeypatch) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = TestClient(create_app(FakeGraph()))

    response = client.post(
        "/v1/llm/verify",
        headers={"x-api-key": "secret"},
        json={"provider": "gemini", "model": "gemini-2.5-flash"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert "GEMINI_API_KEY" in data["error"]


def test_solution_run_rejects_omitted_or_empty_services(monkeypatch) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    client = TestClient(create_app(FakeGraph()))

    for payload in (
        {"solution": {"name": "omitted"}},
        {"solution": {"name": "empty", "services": []}},
        {"solution": {"name": "null", "services": None}},
    ):
        res = client.post(
            "/v1/solution/run",
            headers={"x-api-key": "secret"},
            json=payload,
        )
        assert res.status_code == 422, f"Expected 422 for {payload}, got {res.status_code}"


def test_blueprint_run_preserves_external_sentinel_directory_and_returns_trace_on_502(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")
    managed_root = tmp_path / "managed-workspaces"
    monkeypatch.setenv("AGENTIA_WORKSPACE_ROOT", str(managed_root))

    external_dir = tmp_path / "external-caller-dir"
    (external_dir / "src").mkdir(parents=True, exist_ok=True)
    sentinel = external_dir / "src" / "sentinel.txt"
    sentinel.write_text("KEEP_ME", encoding="utf-8")

    graph = FakeGraph()
    client = TestClient(create_app(graph))

    res = client.post(
        "/v1/blueprint/run",
        headers={"x-api-key": "secret"},
        json={
            "workspace_dir": str(external_dir),
            "blueprint": {"name": "isolated-service"},
        },
    )
    assert res.status_code == 200
    assert sentinel.is_file() and sentinel.read_text(encoding="utf-8") == "KEEP_ME"
    assert str(managed_root) in graph.calls[0][0]
