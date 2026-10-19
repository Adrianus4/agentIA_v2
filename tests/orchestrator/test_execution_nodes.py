from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.orchestrator.execution_nodes import (
    build_repair_node,
    build_verifier_node,
    create_orchestrator_graph,
    resolve_default_runner,
)
from app.orchestrator.graph import OrchestrationState
from contracts.models import (
    DiagnosticIssue,
    FileContent,
    GuardReport,
    RepairResult,
    VerificationResult,
)


def test_resolve_default_runner(monkeypatch) -> None:
    monkeypatch.setenv("VERIFIER_RUNNER", "host")
    runner = resolve_default_runner()
    assert runner.__class__.__name__ == "LocalSubprocessRunner"

    monkeypatch.setenv("VERIFIER_RUNNER", "docker")
    runner_docker = resolve_default_runner()
    assert runner_docker.__class__.__name__ == "LocalDockerRunner"


@pytest.mark.asyncio
async def test_verifier_node_bypasses_when_no_pom_xml(tmp_path: Path) -> None:
    verify = build_verifier_node()
    state = OrchestrationState(
        workspace_dir=str(tmp_path),
        blueprint={"serviceName": "demo"},
        trace_id="trc-no-pom",
    )
    result = await verify(state)
    assert result.success is False
    assert result.exit_code == 1
    assert "pom.xml" in result.raw_output



@pytest.mark.asyncio
async def test_verifier_node_executes_runner_when_pom_xml_exists(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<project/>")
    mock_runner = MagicMock()
    mock_runner.run.return_value = VerificationResult(
        success=True,
        exit_code=0,
        wall_time_seconds=1.2,
        issues=[],
        raw_output="BUILD SUCCESS",
        runner_name="MockRunner",
        image="none",
    )

    verify = build_verifier_node(runner=mock_runner)
    state = OrchestrationState(
        workspace_dir=str(tmp_path),
        blueprint={"serviceName": "demo"},
        trace_id="trc-pom",
    )

    result = await verify(state)
    assert result.success is True
    assert mock_runner.run.called
    assert mock_runner.run.call_args[0][0].workspace_path == str(tmp_path.resolve())


@pytest.mark.asyncio
async def test_repair_node_returns_no_fix_when_verification_passed(tmp_path: Path) -> None:
    repair = build_repair_node()
    state = OrchestrationState(
        workspace_dir=str(tmp_path),
        blueprint={"serviceName": "demo"},
        trace_id="trc-pass",
    )
    state.verification = VerificationResult(
        success=True,
        wall_time_seconds=0.0,
        issues=[],
        raw_output="",
        runner_name="mock",
        image="none",
    )

    res = await repair(state)
    assert res.outcome == "NO_FIX"


@pytest.mark.asyncio
async def test_repair_node_generates_patch_on_failure(tmp_path: Path) -> None:
    file_to_fix = tmp_path / "src" / "main" / "java" / "com" / "example" / "Item.java"
    file_to_fix.parent.mkdir(parents=True, exist_ok=True)
    file_to_fix.write_text("class Item { int x = ; }")

    mock_service = MagicMock()
    mock_service.repair.return_value = RepairResult(
        outcome="PATCHED",
        classification="COMPILE_ERROR",
        hypothesis="Fixed syntax",
        patches=["--- src/main/java/com/example/Item.java\n+++ src/main/java/com/example/Item.java\n"],
        files_touched=["src/main/java/com/example/Item.java"],
        guard_report=GuardReport(passed=True),
        attempts_used=1,
        trace_id="trc-repair",
    )

    repair = build_repair_node(repair_service=mock_service)
    state = OrchestrationState(
        workspace_dir=str(tmp_path),
        blueprint={"serviceName": "demo"},
        trace_id="trc-repair",
    )
    state.verification = VerificationResult(
        success=False,
        exit_code=1,
        wall_time_seconds=0.5,
        issues=[
            DiagnosticIssue(
                file_path="src/main/java/com/example/Item.java",
                line_number=1,
                error_type="COMPILE_ERROR",
                message="syntax error",
            )
        ],
        raw_output="BUILD FAILURE",
        runner_name="mock",
        image="none",
    )
    state.generated_files = [FileContent(path="src/main/java/com/example/Item.java", content="")]

    result = await repair(state)
    assert result.outcome == "PATCHED"
    assert len(result.patches) == 1
    assert mock_service.repair.called


def test_create_orchestrator_graph() -> None:
    graph = create_orchestrator_graph()
    assert graph.generation_node is not None
    assert graph.verify_node is not None
    assert graph.repair_node is not None

