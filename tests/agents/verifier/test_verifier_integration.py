from pathlib import Path

from agents.verifier.runner import LocalDockerRunner
from contracts.models import RunnerRequest, VerificationResult

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures"


def test_end_to_end_dry_run_pipeline(tmp_path: Path) -> None:
    # 1. Create a simulated project workspace
    src_dir = tmp_path / "src" / "main" / "java" / "org" / "acme"
    src_dir.mkdir(parents=True)
    (src_dir / "GreetingResource.java").write_text("package org.acme;\npublic class GreetingResource {}\n")

    # 2. Set mock output
    mock_stdout = (FIXTURES_DIR / "maven_compile_error.txt").read_text()
    runner = LocalDockerRunner(
        dry_run=True,
        mock_output=mock_stdout,
        mock_exit_code=1,
    )

    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "compile"],
        timeout_seconds=20,
    )

    result = runner.run(request)

    assert isinstance(result, VerificationResult)
    assert result.success is False
    assert result.exit_code == 1
    assert result.timed_out is False
    assert len(result.issues) == 1
    assert result.issues[0].file_path == "src/main/java/org/acme/GreetingResource.java"
    assert result.issues[0].line_number == 14
    assert result.issues[0].error_type == "COMPILE_ERROR"


def test_end_to_end_clean_pipeline(tmp_path: Path) -> None:
    mock_clean = (FIXTURES_DIR / "maven_clean.txt").read_text()
    runner = LocalDockerRunner(
        dry_run=True,
        mock_output=mock_clean,
        mock_exit_code=0,
    )

    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "test"],
        timeout_seconds=20,
    )

    result = runner.run(request)

    assert isinstance(result, VerificationResult)
    assert result.success is True
    assert result.exit_code == 0
    assert result.timed_out is False
    assert len(result.issues) == 0
