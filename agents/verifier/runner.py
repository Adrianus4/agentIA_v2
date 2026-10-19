"""
Hermetic Docker Runner for Maven builds.

Executes Maven commands in an isolated Docker container with --network none,
read-only m2 cache mount, and workspace volume isolation.
"""

import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path

from agents.verifier.parser import parse_maven_output
from contracts.models import DiagnosticIssue, RunnerRequest, VerificationResult

MAX_RAW_OUTPUT_LENGTH = 100_000


class BaseVerifierRunner(ABC):
    """Abstract base contract for verification runners."""

    @abstractmethod
    def run(self, request: RunnerRequest) -> VerificationResult:
        raise NotImplementedError

    @staticmethod
    def _locate_surefire_dir(workspace_path: str) -> str | None:
        """Locates the Surefire reports directory under target/surefire-reports."""
        standard_path = Path(workspace_path) / "target" / "surefire-reports"
        if standard_path.is_dir():
            return str(standard_path)

        for found in Path(workspace_path).glob("**/target/**/surefire-reports"):
            if found.is_dir():
                return str(found)

        return None


class LocalDockerRunner(BaseVerifierRunner):
    """
    Hermetic Docker runner executing Maven commands in isolated containers.
    """

    def __init__(
        self,
        image: str = "maven:3.9-eclipse-temurin-21",
        m2_repo_path: str | None = None,
        dry_run: bool = False,
        mock_output: str | None = None,
        mock_exit_code: int | None = 0,
        mock_timed_out: bool = False,
    ) -> None:
        self.image = image
        self.m2_repo_path = m2_repo_path
        self.dry_run = dry_run or os.environ.get(
            "VERIFIER_DRY_RUN", ""
        ).lower() in ("1", "true", "yes")
        self.mock_output = mock_output
        self.mock_exit_code = mock_exit_code
        self.mock_timed_out = mock_timed_out

    def run(self, request: RunnerRequest) -> VerificationResult:
        """
        Executes the requested Maven command in a hermetic Docker container.
        Enforces execution timeout and offline networking.
        Parses outputs into a VerificationResult.

        Args:
            request: RunnerRequest specification.

        Returns:
            VerificationResult: Complete outcome of verification.
        """
        workspace_abs = os.path.abspath(request.workspace_path)
        m2_abs = os.path.abspath(
            os.path.expanduser(self.m2_repo_path or "~/.m2/repository")
        )
        os.makedirs(m2_abs, exist_ok=True)

        # Hermetic Docker command construction
        # Flags:
        # --rm: Clean up container after exit
        # --network none: Offline isolation
        # -v workspace:/workspace:z: Workspace bind mount with SELinux label
        # -v ~/.m2/repository:/root/.m2/repository:ro,z: Read-only local m2 cache
        # -w /workspace: Working directory
        docker_cmd: list[str] = [
            "docker",
            "run",
            "--rm",
            "--network",
            request.network_policy,
            "-v",
            f"{workspace_abs}:/workspace:z",
            "-v",
            f"{m2_abs}:/root/.m2/repository:ro,z",
            "-w",
            "/workspace",
            self.image,
            *request.command,
        ]

        wall_time: float
        exit_code: int | None
        timed_out: bool = False
        raw_output: str

        if self.dry_run:
            start_time = time.perf_counter()
            timed_out = self.mock_timed_out
            exit_code = None if timed_out else self.mock_exit_code
            raw_output = (
                self.mock_output
                if self.mock_output is not None
                else (
                    "[INFO] BUILD SUCCESS\n"
                    if exit_code == 0
                    else "[ERROR] BUILD FAILURE\n"
                )
            )
            wall_time = round(time.perf_counter() - start_time, 3)
        else:
            start_time = time.perf_counter()
            try:
                proc = subprocess.run(
                    docker_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=request.timeout_seconds,
                    check=False,
                )
                wall_time = time.perf_counter() - start_time
                exit_code = proc.returncode
                raw_output = proc.stdout or ""
                timed_out = False
            except subprocess.TimeoutExpired as exc:
                elapsed = time.perf_counter() - start_time
                wall_time = max(elapsed, float(request.timeout_seconds))
                timed_out = True
                exit_code = None
                output_val = exc.stdout or ""
                raw_output = (
                    output_val
                    if isinstance(output_val, str)
                    else output_val.decode("utf-8", errors="replace")
                )
            except FileNotFoundError as exc:
                wall_time = time.perf_counter() - start_time
                timed_out = False
                exit_code = 127
                raw_output = f"Docker executable not found: {exc}\n"

        # Locate surefire reports directory if present
        surefire_dir = self._locate_surefire_dir(workspace_abs)

        # Parse issues from raw output and Surefire XML reports
        issues = parse_maven_output(
            raw_stdout=raw_output,
            surefire_dir=surefire_dir,
            workspace_root=workspace_abs,
        )

        # If execution timed out, add an explicit TIMEOUT diagnostic issue
        if timed_out:
            issues.append(
                DiagnosticIssue(
                    file_path="",
                    line_number=None,
                    column_number=None,
                    error_type="TIMEOUT",
                    message=f"Execution timed out after {request.timeout_seconds} seconds",
                )
            )

        # Check for output truncation
        raw_output_truncated = False
        if len(raw_output) > MAX_RAW_OUTPUT_LENGTH:
            # Keep the tail: Maven prints the errors and the build summary last
            raw_output = raw_output[-MAX_RAW_OUTPUT_LENGTH:]
            raw_output_truncated = True

        success = (exit_code == 0) and not timed_out and len(issues) == 0

        return VerificationResult(
            success=success,
            exit_code=exit_code,
            timed_out=timed_out,
            wall_time_seconds=round(wall_time, 3),
            issues=issues,
            raw_output=raw_output,
            raw_output_truncated=raw_output_truncated,
            runner_name=self.__class__.__name__,
            image=self.image,
        )


class LocalSubprocessRunner(BaseVerifierRunner):
    """
    Explicit host subprocess runner executing build/test commands directly on the host machine.
    Enforces workspace containment, timeouts, stdout/stderr capture, and diagnostic extraction.
    Never activated implicitly: must be selected intentionally via typed mode or config.
    """

    def __init__(
        self,
        *,
        dry_run: bool = False,
        mock_output: str | None = None,
        mock_exit_code: int | None = 0,
        mock_timed_out: bool = False,
    ) -> None:
        self.dry_run = dry_run or os.environ.get(
            "VERIFIER_DRY_RUN", ""
        ).lower() in ("1", "true", "yes")
        self.mock_output = mock_output
        self.mock_exit_code = mock_exit_code
        self.mock_timed_out = mock_timed_out

    def run(self, request: RunnerRequest) -> VerificationResult:
        workspace_abs = os.path.abspath(request.workspace_path)
        workspace_path = Path(workspace_abs).resolve()
        if not workspace_path.is_dir():
            return VerificationResult(
                success=False,
                exit_code=1,
                timed_out=False,
                wall_time_seconds=0.0,
                issues=[
                    DiagnosticIssue(
                        file_path="",
                        line_number=None,
                        column_number=None,
                        error_type="WORKSPACE_ERROR",
                        message=f"Workspace path does not exist or is not a directory: {workspace_abs}",
                    )
                ],
                raw_output=f"Workspace does not exist: {workspace_abs}\n",
                raw_output_truncated=False,
                runner_name=self.__class__.__name__,
                image="host",
            )

        wall_time: float
        exit_code: int | None
        timed_out: bool = False
        raw_output: str

        if self.dry_run:
            start_time = time.perf_counter()
            timed_out = self.mock_timed_out
            exit_code = None if timed_out else self.mock_exit_code
            raw_output = (
                self.mock_output
                if self.mock_output is not None
                else (
                    "[INFO] BUILD SUCCESS\n"
                    if exit_code == 0
                    else "[ERROR] BUILD FAILURE\n"
                )
            )
            wall_time = round(time.perf_counter() - start_time, 3)
        else:
            start_time = time.perf_counter()
            # Resolve the executable via PATH/PATHEXT so Windows finds wrappers such as mvn.cmd
            command = list(request.command)
            if command:
                command[0] = shutil.which(command[0], path=os.environ.get("PATH")) or command[0]
            try:
                proc = subprocess.run(
                    command,
                    cwd=workspace_abs,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=request.timeout_seconds,
                    check=False,
                )
                wall_time = time.perf_counter() - start_time
                exit_code = proc.returncode
                raw_output = proc.stdout or ""
                timed_out = False
            except subprocess.TimeoutExpired as exc:
                elapsed = time.perf_counter() - start_time
                wall_time = max(elapsed, float(request.timeout_seconds))
                timed_out = True
                exit_code = None
                output_val = exc.stdout or ""
                raw_output = (
                    output_val
                    if isinstance(output_val, str)
                    else output_val.decode("utf-8", errors="replace")
                )
            except FileNotFoundError as exc:
                wall_time = time.perf_counter() - start_time
                timed_out = False
                exit_code = 127
                raw_output = f"Executable not found on host: {exc}\n"

        surefire_dir = self._locate_surefire_dir(workspace_abs)
        issues = parse_maven_output(
            raw_stdout=raw_output,
            surefire_dir=surefire_dir,
            workspace_root=workspace_abs,
        )

        if timed_out:
            issues.append(
                DiagnosticIssue(
                    file_path="",
                    line_number=None,
                    column_number=None,
                    error_type="TIMEOUT",
                    message=f"Execution timed out after {request.timeout_seconds} seconds",
                )
            )

        raw_output_truncated = False
        if len(raw_output) > MAX_RAW_OUTPUT_LENGTH:
            # Keep the tail: Maven prints the errors and the build summary last
            raw_output = raw_output[-MAX_RAW_OUTPUT_LENGTH:]
            raw_output_truncated = True

        success = (exit_code == 0) and not timed_out and len(issues) == 0

        return VerificationResult(
            success=success,
            exit_code=exit_code,
            timed_out=timed_out,
            wall_time_seconds=round(wall_time, 3),
            issues=issues,
            raw_output=raw_output,
            raw_output_truncated=raw_output_truncated,
            runner_name=self.__class__.__name__,
            image="host",
        )
