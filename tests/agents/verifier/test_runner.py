import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents.verifier.runner import LocalDockerRunner
from contracts.models import RunnerRequest, VerificationResult

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures"


def test_dry_run_success(tmp_path: Path) -> None:
    runner = LocalDockerRunner(dry_run=True)
    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "compile"],
        timeout_seconds=30,
        network_policy="none",
    )
    result = runner.run(request)

    assert isinstance(result, VerificationResult)
    assert result.success is True
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.runner_name == "LocalDockerRunner"
    assert result.image == "maven:3.9-eclipse-temurin-21"
    assert len(result.issues) == 0


def test_docker_command_construction(tmp_path: Path) -> None:
    runner = LocalDockerRunner()
    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "clean", "test"],
        timeout_seconds=45,
        network_policy="none",
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[INFO] BUILD SUCCESS\n",
            stderr="",
        )

        result = runner.run(request)

        assert result.success is True
        assert mock_run.called
        call_args = mock_run.call_args[0][0]

        # Verify hermetic docker command structure
        assert call_args[0] == "docker"
        assert call_args[1] == "run"
        assert "--rm" in call_args
        assert "--network" in call_args
        net_idx = call_args.index("--network")
        assert call_args[net_idx + 1] == "none"

        # Check volume mounts
        workspace_mount = f"{os.path.abspath(str(tmp_path))}:/workspace:z"
        assert workspace_mount in call_args

        m2_mount_suffix = ":/root/.m2/repository:ro,z"
        assert any(arg.endswith(m2_mount_suffix) for arg in call_args)

        # Check working directory and image
        w_idx = call_args.index("-w")
        assert call_args[w_idx + 1] == "/workspace"
        assert "maven:3.9-eclipse-temurin-21" in call_args

        # Check requested command appended
        assert call_args[-3:] == ["mvn", "clean", "test"]

        # Check timeout was passed
        kwargs = mock_run.call_args[1]
        assert kwargs.get("timeout") == 45


def test_compilation_error_execution(tmp_path: Path) -> None:
    runner = LocalDockerRunner()
    compile_err_txt = (FIXTURES_DIR / "maven_compile_error.txt").read_text()

    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "compile"],
        timeout_seconds=30,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=compile_err_txt,
            stderr="",
        )

        result = runner.run(request)

        assert result.success is False
        assert result.exit_code == 1
        assert result.timed_out is False
        assert len(result.issues) == 1
        assert result.issues[0].file_path == "src/main/java/org/acme/GreetingResource.java"
        assert result.issues[0].line_number == 14
        assert result.issues[0].error_type == "COMPILE_ERROR"


def test_test_failure_execution_with_surefire_dir(tmp_path: Path) -> None:
    # Set up workspace with target/surefire-reports
    target_surefire = tmp_path / "target" / "surefire-reports"
    target_surefire.mkdir(parents=True)
    shutil.copy(
        FIXTURES_DIR / "surefire-reports" / "TEST-org.acme.GreetingResourceTest.xml",
        target_surefire / "TEST-org.acme.GreetingResourceTest.xml",
    )

    runner = LocalDockerRunner()
    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "test"],
        timeout_seconds=30,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="[INFO] BUILD FAILURE\n[ERROR] There are test failures.\n",
            stderr="",
        )

        result = runner.run(request)

        assert result.success is False
        assert result.exit_code == 1
        assert len(result.issues) == 1
        assert result.issues[0].file_path == "src/test/java/org/acme/GreetingResourceTest.java"
        assert result.issues[0].line_number == 24
        assert result.issues[0].error_type == "org.opentest4j.AssertionFailedError"


def test_timeout_execution(tmp_path: Path) -> None:
    runner = LocalDockerRunner()
    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "test"],
        timeout_seconds=5,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["docker", "run"],
            timeout=5,
            output="[INFO] Compiling...",
        )

        result = runner.run(request)

        assert result.success is False
        assert result.timed_out is True
        assert result.exit_code is None
        assert result.wall_time_seconds >= 5 or result.wall_time_seconds > 0
        assert any(i.error_type == "TIMEOUT" for i in result.issues)


def test_large_output_truncation(tmp_path: Path) -> None:
    runner = LocalDockerRunner()
    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "test"],
        timeout_seconds=30,
    )

    huge_output = "[INFO] Logging...\n" * 15000  # ~270,000 characters

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=huge_output,
            stderr="",
        )

        result = runner.run(request)

        assert result.raw_output_truncated is True
        assert len(result.raw_output) <= 100_000


def test_missing_docker_returns_structured_failure_without_host_fallback(tmp_path: Path) -> None:
    runner = LocalDockerRunner()
    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "test"],
        timeout_seconds=30,
    )

    with patch("subprocess.run", side_effect=FileNotFoundError("No such file or directory: 'docker'")):
        result = runner.run(request)

        assert result.success is False
        assert result.exit_code == 127
        assert "Docker executable not found" in result.raw_output
        assert result.runner_name == "LocalDockerRunner"
        assert result.image == "maven:3.9-eclipse-temurin-21"


def test_local_subprocess_runner_dry_run_success(tmp_path: Path) -> None:
    from agents.verifier.runner import LocalSubprocessRunner

    runner = LocalSubprocessRunner(dry_run=True)
    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "test"],
        timeout_seconds=30,
    )
    result = runner.run(request)

    assert result.success is True
    assert result.exit_code == 0
    assert result.runner_name == "LocalSubprocessRunner"
    assert result.image == "host"


def test_local_subprocess_runner_execution_and_diagnostics(tmp_path: Path) -> None:
    from agents.verifier.runner import LocalSubprocessRunner

    runner = LocalSubprocessRunner()
    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "test"],
        timeout_seconds=30,
    )

    failing_output = """
[ERROR] /workspace/src/main/java/org/acme/Order.java:[15,10] cannot find symbol
[ERROR]   symbol:   class Item
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=failing_output,
            stderr="",
        )
        result = runner.run(request)

        assert result.success is False
        assert result.exit_code == 1
        assert result.runner_name == "LocalSubprocessRunner"
        assert result.image == "host"
        assert len(result.issues) == 1
        assert result.issues[0].file_path == "src/main/java/org/acme/Order.java"
        assert result.issues[0].line_number == 15
        assert mock_run.call_args[1]["cwd"] == str(tmp_path.resolve())


def test_local_subprocess_runner_timeout(tmp_path: Path) -> None:
    from agents.verifier.runner import LocalSubprocessRunner

    runner = LocalSubprocessRunner()
    request = RunnerRequest(
        workspace_path=str(tmp_path),
        command=["mvn", "test"],
        timeout_seconds=5,
    )

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["mvn"], timeout=5, output="timeout")):
        result = runner.run(request)

        assert result.success is False
        assert result.timed_out is True
        assert any(i.error_type == "TIMEOUT" for i in result.issues)
