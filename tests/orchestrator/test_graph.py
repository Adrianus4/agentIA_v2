from pathlib import Path

import pytest

from app.orchestrator.graph import MAX_ATTEMPTS, MAX_REPAIR_ATTEMPTS, OrchestratorGraph
from contracts.models import (
    DiagnosticIssue,
    FileContent,
    GuardReport,
    RepairResult,
    UniformErrorBody,
    VerificationResult,
)


def verification(success: bool) -> VerificationResult:
    return VerificationResult(
        success=success,
        wall_time_seconds=0.01,
        issues=[] if success else [
            DiagnosticIssue(file_path="src/main.py", error_type="compile", message="failed")
        ],
        raw_output="",
        runner_name="fake",
        image="fake",
    )


def repair(trace_id: str, patch: str) -> RepairResult:
    return RepairResult(
        outcome="PATCHED",
        classification="COMPILE_ERROR",
        hypothesis="fix",
        patches=[patch],
        files_touched=["src/main.py"],
        guard_report=GuardReport(passed=True),
        attempts_used=1,
        trace_id=trace_id,
    )


@pytest.mark.asyncio
async def test_successful_run_skips_repair(tmp_path: Path) -> None:
    calls: list[str] = []

    async def validate(*args):
        calls.append("validate")
        return UniformErrorBody(valid=True, diagnostics=[])

    async def verify(*args):
        calls.append("verify")
        return verification(True)

    async def repair_node(*args):
        calls.append("repair")
        return repair("trace", "unused")

    graph = OrchestratorGraph(validate_node=validate, verify_node=verify, repair_node=repair_node)
    state = await graph.run(str(tmp_path), {})

    assert state.outcome == "SUCCESS"
    assert calls == ["validate", "verify"]
    assert state.attempts == 0


@pytest.mark.asyncio
async def test_failed_verify_repairs_then_verifies_again(tmp_path: Path) -> None:
    calls: list[str] = []
    results = iter([verification(False), verification(True)])

    async def validate(*args):
        return UniformErrorBody(valid=True, diagnostics=[])

    async def verify(*args):
        calls.append("verify")
        return next(results)

    async def repair_node(state):
        calls.append("repair")
        return repair(state.trace_id, "diff")

    def patcher(workspace: str, content: str) -> None:
        calls.append("apply")

    state = await OrchestratorGraph(
        validate_node=validate,
        verify_node=verify,
        repair_node=repair_node,
        patcher=patcher,
    ).run(str(tmp_path), {})

    assert state.outcome == "SUCCESS"
    assert state.attempts == 1
    assert calls == ["verify", "repair", "apply", "verify"]


@pytest.mark.asyncio
async def test_exhausted_repair_budget_ends_in_no_fix(tmp_path: Path) -> None:
    verify_calls = 0
    repair_calls = 0

    async def validate(*args):
        return UniformErrorBody(valid=True, diagnostics=[])

    async def verify(*args):
        nonlocal verify_calls
        verify_calls += 1
        return verification(False)

    async def repair_node(state):
        nonlocal repair_calls
        repair_calls += 1
        return repair(state.trace_id, "diff")

    state = await OrchestratorGraph(
        validate_node=validate,
        verify_node=verify,
        repair_node=repair_node,
        patcher=lambda *_: None,
    ).run(str(tmp_path), {})

    assert state.outcome == "NO_FIX"
    assert state.attempts == MAX_REPAIR_ATTEMPTS
    assert verify_calls == MAX_ATTEMPTS
    assert repair_calls == MAX_REPAIR_ATTEMPTS


@pytest.mark.asyncio
async def test_generation_runs_before_verification_and_writes_files(tmp_path: Path) -> None:
    calls: list[str] = []

    async def validate(blueprint, trace_id):
        calls.append("validate")
        assert blueprint["entities"] == [{"name": "Invoice"}]
        return UniformErrorBody(valid=True, diagnostics=[])

    async def generate(request, state):
        calls.append("generate")
        assert request.blueprint["entities"] == [{"name": "Invoice"}]
        return [FileContent(path="src/main.java", content="class Invoice {}")]

    async def verify(state):
        calls.append("verify")
        assert (tmp_path / "src/main.java").read_text() == "class Invoice {}"
        return verification(True)

    state = await OrchestratorGraph(
        validate_node=validate,
        generation_node=generate,
        verify_node=verify,
    ).run(
        str(tmp_path),
        {
            "serviceName": "billing",
            "packageName": "com.example",
            "domainModels": [{"name": "Invoice"}],
            "userStories": [],
        },
    )

    assert state.outcome == "SUCCESS"
    assert [file.path for file in state.generated_files] == ["src/main.java"]
    assert calls == ["validate", "generate", "verify"]


@pytest.mark.asyncio
async def test_nonexistent_workspace_is_created_automatically(tmp_path: Path) -> None:
    non_existent_workspace = tmp_path / "deep" / "nested" / "service-workspace"
    assert not non_existent_workspace.exists()

    async def validate(blueprint, trace_id):
        return UniformErrorBody(valid=True, diagnostics=[])

    async def generate(request, state):
        return [FileContent(path="src/Main.java", content="class Main {}")]

    async def verify(state):
        return verification(True)

    state = await OrchestratorGraph(
        validate_node=validate,
        generation_node=generate,
        verify_node=verify,
    ).run(
        str(non_existent_workspace),
        {"name": "test-service"},
    )

    assert state.outcome == "SUCCESS"
    assert non_existent_workspace.is_dir()
    assert (non_existent_workspace / "src/Main.java").read_text() == "class Main {}"

