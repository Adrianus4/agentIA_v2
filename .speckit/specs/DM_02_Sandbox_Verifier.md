# Feature Specification: DM_02_Sandbox_Verifier

**Feature Identifier**: `DM_02_Sandbox_Verifier`  
**Feature Branch**: `streamB/dm2-verifier`  
**Target Artifacts**:  
- `agents/verifier/__init__.py`  
- `agents/verifier/parser.py`  
- `agents/verifier/runner.py`  
**Contract Authority**: `contracts/models.py` (`RunnerRequest`, `VerificationResult`, `DiagnosticIssue`)  
**Status**: In Progress  
**Date**: 2026-10-11  

---

## 1. Executive Summary & Purpose

The **DM-2 Sandbox Verifier** is the hermetic execution and diagnostic component of the AgentIA v2 pipeline. It provides a secure, deterministic verification environment for Java/Maven projects and parses compilation and test execution results into typed data models.

In strict accordance with:
- **Constitution Rule 3** (*Contracts first: All agent components communicate strictly via typed Pydantic models in contracts/models.py*)
- **Constitution Rule 4** (*Deterministic over generative: Use static parsing and compiler outputs*)
- **Constitution Rule 5** (*Measurable claims only: Every verification step must yield a concrete, parseable metric or exit code*)
- **Constitution Rule 10** (*Hermetic verification: The compiler runner must run offline (`--network none`) using a read-only Maven cache (`:ro`) and an isolated, temporary copy of the target workspace*)

The verifier executes Maven commands inside an isolated Docker container (`maven:3.9-eclipse-temurin-21`), captures stdout/stderr with strict timeouts, and deterministically transforms raw compiler logs and Surefire XML test reports into structured `DiagnosticIssue` objects within a `VerificationResult`.

---

## 2. API Contracts & Signatures

### 2.1 Parser (`agents/verifier/parser.py`)

```python
from typing import List, Optional
from contracts.models import DiagnosticIssue

def parse_maven_output(
    raw_stdout: str,
    surefire_dir: Optional[str] = None,
    workspace_root: Optional[str] = None
) -> List[DiagnosticIssue]:
    """
    Parses compilation errors from Maven raw stdout and test failure/error reports
    from Surefire XML files, mapping them to DiagnosticIssue models.

    Args:
        raw_stdout: Captured stdout and stderr from Maven build execution.
        surefire_dir: Path to directory containing Surefire XML reports (e.g., target/surefire-reports).
        workspace_root: Optional root path of the workspace to normalize absolute paths to relative.

    Returns:
        List[DiagnosticIssue]: Extracted diagnostic issues with workspace-relative file paths.
    """
```

### 2.2 Runner (`agents/verifier/runner.py`)

```python
from typing import Optional
from contracts.models import RunnerRequest, VerificationResult

class LocalDockerRunner:
    """
    Hermetic Docker runner executing Maven commands in isolated containers.
    """
    def __init__(
        self,
        image: str = "maven:3.9-eclipse-temurin-21",
        m2_repo_path: Optional[str] = None,
        dry_run: bool = False,
        mock_output: Optional[str] = None,
        mock_exit_code: Optional[int] = 0,
        mock_timed_out: bool = False,
    ) -> None:
        ...

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
```

---

## 3. Requirements & Acceptance Criteria

### 3.1 Maven Output & Surefire Parsing
- **FR-001**: System MUST parse Maven compilation errors matching `[ERROR] <file>:[<line>,<col>] <message>` and extract file path, line number, column number, and error message.
- **FR-002**: System MUST capture compilation error continuation lines (e.g., `symbol: ...`, `location: ...`) and associate them with the relevant error message.
- **FR-003**: System MUST parse Surefire XML reports (`TEST-*.xml`) in `surefire_dir`, extracting `<failure>` and `<error>` tags.
- **FR-004**: System MUST extract failure type, message, stack trace, and failing source line number from Surefire XML reports.
- **FR-005**: System MUST normalize all diagnostic issue file paths to workspace-relative paths (stripping `/workspace/` or host `workspace_root`).
- **FR-006**: System MUST assign `error_type="COMPILE_ERROR"` for compilation issues, and the exception class name or test error type for test failures.

### 3.2 Docker Hermetic Execution
- **FR-007**: System MUST construct the Docker command with:
  - `--rm`
  - `--network none`
  - `-v <workspace_path>:/workspace:z`
  - `-v <m2_repo_path>:/root/.m2/repository:ro,z`
  - `-w /workspace`
  - `maven:3.9-eclipse-temurin-21`
  - `<request.command>`
- **FR-008**: System MUST enforce timeout via `request.timeout_seconds`. If exceeded, `timed_out` MUST be set to `True`, `exit_code` to `None`, and `success` to `False`.
- **FR-009**: System MUST support dry-run/mock mode when Docker daemon is not accessible or when `dry_run=True` / `VERIFIER_DRY_RUN=1`.
- **FR-010**: System MUST truncate `raw_output` if it exceeds safe bounds (e.g., 100,000 characters) and set `raw_output_truncated=True`.
- **FR-011**: System MUST record wall time in seconds with high-precision timing.
- **FR-012**: System MUST identify `surefire-reports` directory automatically under `target/surefire-reports` within `request.workspace_path`.

---

## 4. Test Strategy

1. **Parser Tests (`tests/agents/verifier/test_parser.py`)**:
   - Single and multiple compilation errors from fixture files.
   - Compilation errors with multiline continuation (symbol/location).
   - Surefire XML failure parsing (AssertionFailedError, line extraction, stack trace).
   - Surefire XML error parsing (NullPointerException).
   - Clean output with no issues.
   - Path normalization to workspace-relative paths.

2. **Runner Tests (`tests/agents/verifier/test_runner.py`)**:
   - Docker CLI command formulation (hermetic flags: `--network none`, `:ro,z`, `:z`, `-w /workspace`).
   - Successful build execution (dry run and mocked subprocess).
   - Compilation failure execution and issue mapping.
   - Test failure execution with Surefire report discovery.
   - Execution timeout handling (`timed_out=True`, `exit_code=None`).
   - Output truncation on large logs.

3. **End-to-End Integration Tests (`tests/agents/verifier/test_verifier_integration.py`)**:
   - End-to-end execution of `RunnerRequest` returning `VerificationResult`.
