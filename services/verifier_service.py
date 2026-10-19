"""Verifier agent: builds and tests a source tree with Maven.

The orchestrator sends the files in the request; the verifier materializes them in its own
scratch directory, so this service needs no volume shared with any other service.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import Depends

from agents.verifier.runner import (
    BaseVerifierRunner,
    LocalDockerRunner,
    LocalSubprocessRunner,
)
from contracts.agent_api import VerifierAgentRequest, VerifierAgentResponse
from contracts.models import (
    DiagnosticIssue,
    FileContent,
    RunnerRequest,
    VerificationResult,
)
from services.common import create_service_app, public_state, verify_gateway_auth

app = create_service_app("AgentIA Verifier Service", "verifier")

_ALLOWED_MAVEN_BINARIES = {"mvn", "./mvnw", "mvnw", "mvnw.cmd", "mvn.cmd"}


def _rejected(command: list[str]) -> VerificationResult:
    return VerificationResult(
        success=False,
        exit_code=126,
        timed_out=False,
        wall_time_seconds=0.0,
        issues=[
            DiagnosticIssue(
                file_path="pom.xml",
                error_type="UNAUTHORIZED_COMMAND",
                message=f"Verifier rejected non-Maven command: {command[0] if command else '<empty>'}",
            )
        ],
        raw_output="Verifier only permits authorized Maven build commands.",
        runner_name="Guard",
        image="none",
    )


def _materialize(files: list[FileContent], trace_id: str) -> Path:
    root = Path(os.getenv("VERIFIER_SCRATCH_DIR") or tempfile.gettempdir()) / "agentia-verify"
    # Short directory names keep Windows builds under MAX_PATH
    workspace = (root / f"{trace_id[:12]}-{uuid.uuid4().hex[:6]}").resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    for file in files:
        if file.content is None:
            continue
        target = (workspace / file.path).resolve()
        try:
            target.relative_to(workspace)
        except ValueError:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file.content, encoding="utf-8")
    return workspace


def _runner() -> BaseVerifierRunner:
    mode = os.getenv("VERIFIER_RUNNER", "host").strip().lower()
    return LocalDockerRunner() if mode == "docker" else LocalSubprocessRunner()


@app.post(
    "/v1/verify",
    response_model=VerifierAgentResponse,
    dependencies=[Depends(verify_gateway_auth)],
)
async def verify(request: VerifierAgentRequest) -> VerifierAgentResponse:
    cmd = request.runner.command
    if not cmd or Path(cmd[0]).name not in _ALLOWED_MAVEN_BINARIES:
        verification = _rejected(cmd)
    elif request.files:
        workspace = await asyncio.to_thread(_materialize, request.files, request.trace_id)
        try:
            runner_request = RunnerRequest(
                workspace_path=str(workspace),
                command=cmd,
                timeout_seconds=request.runner.timeout_seconds,
            )
            verification = await asyncio.to_thread(_runner().run, runner_request)
        finally:
            if os.getenv("VERIFIER_KEEP_WORKSPACE", "").lower() not in {"1", "true", "yes"}:
                shutil.rmtree(workspace, ignore_errors=True)
    else:
        verification = await asyncio.to_thread(_runner().run, request.runner)

    workflow_state = public_state(request.workflow_state)
    workflow_state["verification"] = verification.model_dump(exclude={"raw_output"})
    return VerifierAgentResponse(
        trace_id=request.trace_id,
        workflow_state=workflow_state,
        verification=verification,
    )
