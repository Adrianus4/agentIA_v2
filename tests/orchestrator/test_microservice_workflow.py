"""Workflow behaviour of the LangGraph orchestrator and the decoupled agent services."""
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from agents.verifier.parser import parse_maven_output
from app.core.llm.factory import resolve_llm_settings
from app.orchestrator.clients.agent_client_microservice import AgentClient, AgentHTTPError
from app.orchestrator.execution_nodes_microservice import (
    _related_dependencies,
    collect_workspace_files,
    merge_repair_results,
)
from app.orchestrator.graph import OrchestrationState, OrchestratorGraph
from contracts.models import (
    DiagnosticIssue,
    FileContent,
    GuardReport,
    RepairResult,
    UniformErrorBody,
    VerificationResult,
)


def _failed(issue_type: str = "COMPILE_ERROR") -> VerificationResult:
    return VerificationResult(
        success=False,
        wall_time_seconds=0.1,
        issues=[DiagnosticIssue(file_path="src/A.java", error_type=issue_type, message="boom")],
        raw_output="",
        runner_name="fake",
        image="fake",
    )


def _ok() -> VerificationResult:
    return VerificationResult(success=True, wall_time_seconds=0.1, issues=[], raw_output="", runner_name="fake", image="fake")


def _repair(outcome: str, trace: str = "t", patches: list[str] | None = None) -> RepairResult:
    return RepairResult(
        outcome=outcome,
        classification="COMPILE_ERROR",
        hypothesis=outcome,
        patches=patches if patches is not None else (["patch"] if outcome == "PATCHED" else []),
        files_touched=["src/A.java"],
        guard_report=GuardReport(passed=outcome == "PATCHED", failed_guards=[] if outcome == "PATCHED" else ["G1"]),
        attempts_used=1,
        trace_id=trace,
    )


async def _valid(*_):
    return UniformErrorBody(valid=True, diagnostics=[])


@pytest.mark.asyncio
async def test_patch_failure_goes_back_to_repair_without_reverifying(tmp_path: Path) -> None:
    calls: list[str] = []
    verifications = iter([_failed(), _ok()])
    seen_issue_types: list[list[str]] = []

    async def verify(state):
        calls.append("verify")
        return next(verifications)

    async def repair(state):
        calls.append("repair")
        seen_issue_types.append([i.error_type for i in state.verification.issues])
        return _repair("PATCHED", state.trace_id)

    patch_calls = 0

    def patcher(workspace, patch):
        nonlocal patch_calls
        patch_calls += 1
        calls.append("apply")
        if patch_calls == 1:
            raise RuntimeError("hunk does not apply")

    state = await OrchestratorGraph(
        validate_node=_valid, verify_node=verify, repair_node=repair, patcher=patcher
    ).run(str(tmp_path), {})

    assert state.outcome == "SUCCESS"
    assert calls == ["verify", "repair", "apply", "repair", "apply", "verify"]
    assert "PATCH_APPLICATION_ERROR" in seen_issue_types[1]
    assert state.attempts == 2


@pytest.mark.asyncio
async def test_guard_rejection_retries_repair_with_feedback(tmp_path: Path) -> None:
    repairs = iter([_repair("REJECTED_BY_GUARD"), _repair("PATCHED")])
    verifications = iter([_failed(), _ok()])
    feedback: list[list[str]] = []

    async def verify(state):
        return next(verifications)

    async def repair(state):
        feedback.append([i.error_type for i in state.verification.issues])
        return next(repairs)

    state = await OrchestratorGraph(
        validate_node=_valid, verify_node=verify, repair_node=repair, patcher=lambda *_: None
    ).run(str(tmp_path), {})

    assert state.outcome == "SUCCESS"
    assert feedback[1][-1] == "GUARD_REJECTED"
    assert state.attempts == 2


@pytest.mark.asyncio
async def test_llm_error_ends_run_as_error(tmp_path: Path) -> None:
    async def verify(state):
        return _failed()

    async def repair(state):
        return _repair("ERROR")

    state = await OrchestratorGraph(validate_node=_valid, verify_node=verify, repair_node=repair).run(str(tmp_path), {})
    assert state.outcome == "ERROR"


@pytest.mark.asyncio
async def test_verify_only_budget_never_repairs(tmp_path: Path) -> None:
    repair_calls = 0

    async def verify(state):
        return _failed()

    async def repair(state):
        nonlocal repair_calls
        repair_calls += 1
        return _repair("PATCHED")

    stages: list[str] = []
    state = await OrchestratorGraph(validate_node=_valid, verify_node=verify, repair_node=repair).run(
        str(tmp_path), {}, max_repair_attempts=0, progress=lambda stage, _s: stages.append(stage)
    )
    assert state.outcome == "NO_FIX"
    assert repair_calls == 0
    assert stages == ["validate", "verify", "exhausted"]


def test_merge_prefers_patches_then_guard_rejection() -> None:
    state = OrchestrationState(workspace_dir=".", blueprint={}, trace_id="t")
    merged = merge_repair_results(state, [_repair("NO_FIX"), _repair("PATCHED", patches=["p1"]), _repair("PATCHED", patches=["p2"])])
    assert merged.outcome == "PATCHED"
    assert merged.patches == ["p1", "p2"]
    assert merge_repair_results(state, [_repair("NO_FIX"), _repair("REJECTED_BY_GUARD")]).outcome == "REJECTED_BY_GUARD"


def test_related_dependencies_only_include_referenced_classes() -> None:
    failing = FileContent(path="src/UserResource.java", content="class UserResource { UserRepository r; User u; }")
    files = [
        FileContent(path="src/User.java", content="class User {}"),
        FileContent(path="src/UserRepository.java", content="class UserRepository {}"),
        FileContent(path="src/Product.java", content="class Product {}"),
        failing,
    ]
    assert [f.path for f in _related_dependencies(failing, files)] == ["src/User.java", "src/UserRepository.java"]


def test_collect_workspace_files_skips_build_output(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "A.java").write_text("class A {}", encoding="utf-8")
    (tmp_path / "target" / "classes").mkdir(parents=True)
    (tmp_path / "target" / "classes" / "A.class").write_text("x", encoding="utf-8")
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    (tmp_path / ".agentia-workspace").write_text("trace", encoding="utf-8")
    assert [f.path for f in collect_workspace_files(str(tmp_path))] == ["pom.xml", "src/A.java"]


def test_verifier_service_builds_files_in_its_own_scratch_dir(monkeypatch, tmp_path: Path) -> None:
    from services import verifier_service

    monkeypatch.setenv("VERIFIER_DRY_RUN", "1")
    monkeypatch.setenv("VERIFIER_SCRATCH_DIR", str(tmp_path))
    monkeypatch.delenv("AGENT_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("ORCHESTRATOR_API_KEY", raising=False)
    client = TestClient(verifier_service.app)
    response = client.post(
        "/v1/verify",
        json={
            "trace_id": "trace-files",
            "runner": {"workspace_path": "/does/not/exist", "command": ["mvn", "-B", "test"]},
            "files": [{"path": "pom.xml", "content": "<project/>"}],
        },
    )
    assert response.status_code == 200
    assert response.json()["verification"]["success"] is True
    # scratch workspace is removed after the build
    assert list((tmp_path / "agentia-verify").iterdir()) == []
    assert client.get("/health").json() == {"status": "ok", "service": "verifier"}


def test_repair_service_turns_llm_rate_limit_into_typed_error(monkeypatch) -> None:
    from services import repair_service

    def raise_quota(*_args, **_kwargs):
        raise RuntimeError("429 You exceeded your current quota")

    monkeypatch.setattr(repair_service, "build_llm_client", raise_quota)
    monkeypatch.delenv("AGENT_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("ORCHESTRATOR_API_KEY", raising=False)
    client = TestClient(repair_service.app)
    response = client.post(
        "/v1/repair",
        json={
            "trace_id": "trace-429",
            "workflow_state": {"llm_api_key": "k"},
            "repair": {
                "framework": "quarkus",
                "framework_version": "3.15",
                "failing_file": {"path": "src/A.java", "content": "class A {}"},
                "issues": [{"file_path": "src/A.java", "error_type": "COMPILE_ERROR", "message": "x"}],
                "allowed_paths": ["src/A.java"],
                "test_baseline": {"test_count": 0, "assertion_count": 0, "disabled_count": 0},
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["repair_result"]["outcome"] == "ERROR"
    assert body["repair_result"]["guard_report"]["failed_guards"] == ["LLM_RATE_LIMITED"]
    assert "llm_api_key" not in body["workflow_state"]


@pytest.mark.asyncio
@respx.mock
async def test_agent_client_does_not_retry_expensive_calls() -> None:
    route = respx.post("http://gen/v1/generate").mock(return_value=httpx.Response(500, text="boom"))
    async with AgentClient(validator_url="http://val", generator_url="http://gen", verifier_url="http://ver", repair_url="http://rep") as client:
        with pytest.raises(AgentHTTPError):
            await client.generate_code({"trace_id": "t"})
    assert route.call_count == 1


def test_llm_settings_resolution(monkeypatch) -> None:
    for var in ("LLM_PROVIDER", "LLM_MODEL", "GEMINI_API_KEY", "LOCAL_LLM_ENDPOINT", "OLLAMA_BASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert resolve_llm_settings()["provider"] == "local"
    gemini = resolve_llm_settings(provider="gemini", api_key="k")
    assert gemini["model"] == "gemini-flash-latest"
    # a model from another provider family is replaced by the provider default
    assert resolve_llm_settings(provider="local", model="gpt-4o")["model"] == "qwen2.5-coder:7b"
    monkeypatch.setenv("LOCAL_LLM_ENDPOINT", "http://127.0.0.1:11434")
    assert resolve_llm_settings(provider="gemini")["provider"] == "local"


def test_parser_keeps_one_issue_per_compiler_error_with_details() -> None:
    stdout = """
[ERROR] COMPILATION ERROR :
[ERROR] /workspace/src/main/java/A.java:[3,5] cannot find symbol
[INFO] 1 error
[ERROR] Failed to execute goal ... Compilation failure
[ERROR] /workspace/src/main/java/A.java:[3,5] cannot find symbol
[ERROR]   symbol:   variable Page
[ERROR]   location: class A
"""
    issues = parse_maven_output(stdout)
    assert len(issues) == 1
    assert "variable Page" in issues[0].message
