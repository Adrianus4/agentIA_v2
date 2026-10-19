from __future__ import annotations

from agents.verifier.runner import BaseVerifierRunner, LocalDockerRunner
from contracts.models import RunnerRequest, VerificationResult


def verify_scaffold(
    workspace_path: str,
    runner: BaseVerifierRunner | LocalDockerRunner,
    *,
    timeout_seconds: int = 300,
) -> VerificationResult:
    return runner.run(
        RunnerRequest(
            workspace_path=workspace_path,
            command=["mvn", "-o", "-q", "test-compile"],
            timeout_seconds=timeout_seconds,
            network_policy="none",
        )
    )
