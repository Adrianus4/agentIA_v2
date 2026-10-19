"""Graph nodes that delegate every agent step to its FastAPI microservice over HTTP.

The orchestrator owns the workspace and the workflow store; agents receive everything they need
in the request (blueprint, files, diagnostics), so no service shares a filesystem with another.
"""
from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agents.profiles.loader import get_profile
from agents.verifier.runner import (
    BaseVerifierRunner,
    LocalDockerRunner,
    LocalSubprocessRunner,
)
from app.orchestrator.clients.agent_client_microservice import AgentClient
from app.orchestrator.clients.workflow_store import WorkflowStore
from app.orchestrator.execution_nodes import (
    compute_test_baseline,
    resolve_verifier_command,
)
from app.orchestrator.graph import (
    MAX_REPAIR_ATTEMPTS,
    GraphContractError,
    OrchestrationState,
    OrchestratorGraph,
    get_transient_llm_config,
    load_repair_targets,
    register_transient_llm_config,
)
from contracts.agent_api import (
    GenerationAgentRequest,
    RepairAgentRequest,
    ValidationAgentRequest,
    VerifierAgentRequest,
)
from contracts.models import (
    DiagnosticIssue,
    FileContent,
    GenerationRequest,
    GuardReport,
    RepairRequest,
    RepairResult,
    RunnerRequest,
    UniformErrorBody,
    VerificationResult,
)

_SKIPPED_DIRS = {"target", ".git", "node_modules", ".idea", ".vscode", ".mvn"}
_MAX_SYNC_FILE_BYTES = 512_000
MAX_REPAIR_FILES_PER_ATTEMPT = 3
MAX_REPAIR_DEPENDENCIES = 6


def _workflow_store() -> WorkflowStore:
    return WorkflowStore(os.getenv("WORKFLOW_STATE_DIR", ".agentia-state"))


def _service_client() -> AgentClient:
    api_key = (
        os.getenv("AGENT_GATEWAY_API_KEY")
        or os.getenv("ORCHESTRATOR_API_KEY")
        or os.getenv("API_KEY")
    )
    bearer_token = (
        os.getenv("AGENT_GATEWAY_BEARER_TOKEN")
        or os.getenv("ORCHESTRATOR_BEARER_TOKEN")
    )
    timeout_val = float(
        os.getenv(
            "AGENT_CLIENT_TIMEOUT_SECONDS",
            os.getenv("VERIFIER_TIMEOUT_SECONDS", "900.0"),
        )
    )
    return AgentClient(
        validator_url=os.getenv("BLUEPRINT_VALIDATOR_URL", "http://127.0.0.1:8003"),
        generator_url=os.getenv("GENERATOR_URL", "http://127.0.0.1:8004"),
        verifier_url=os.getenv("VERIFIER_URL", "http://127.0.0.1:8001"),
        repair_url=os.getenv("REPAIR_URL", "http://127.0.0.1:8002"),
        timeout=timeout_val,
        api_key=api_key,
        bearer_token=bearer_token,
    )


def resolve_default_runner() -> BaseVerifierRunner:
    runner_env = os.getenv("VERIFIER_RUNNER", "").strip().lower()
    dry_run = os.environ.get("VERIFIER_DRY_RUN", "").lower() in ("1", "true", "yes")
    if dry_run:
        return LocalSubprocessRunner(dry_run=True)
    if runner_env == "docker":
        return LocalDockerRunner()
    if runner_env == "host":
        return LocalSubprocessRunner()
    if shutil.which("mvn"):
        return LocalSubprocessRunner()
    if shutil.which("docker") or shutil.which("podman"):
        return LocalDockerRunner()
    return LocalSubprocessRunner(dry_run=False)


def collect_workspace_files(workspace_dir: str) -> list[FileContent]:
    """Snapshot the source tree (not build output) so it can be shipped to a remote verifier."""
    workspace = Path(workspace_dir).expanduser().resolve()
    files: list[FileContent] = []
    for path in sorted(workspace.rglob("*")):
        rel = path.relative_to(workspace)
        if not path.is_file() or any(part in _SKIPPED_DIRS for part in rel.parts):
            continue
        if path.name == ".agentia-workspace" or path.stat().st_size > _MAX_SYNC_FILE_BYTES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append(FileContent(path=rel.as_posix(), content=content))
    return files


def _framework_and_version(state: OrchestrationState) -> tuple[str, str]:
    framework = str(state.blueprint.get("framework", "quarkus"))
    version = str(state.blueprint.get("version", state.blueprint.get("frameworkVersion", "3.15")))
    return framework, version


def _related_dependencies(failing: FileContent, files: list[FileContent]) -> list[FileContent]:
    """Only the files the failing file actually references (by class name), capped, as repair context."""
    source = failing.content or ""
    related: list[FileContent] = []
    for candidate in files:
        if candidate.path == failing.path or not candidate.content or not candidate.path.endswith(".java"):
            continue
        if re.search(rf"\b{re.escape(Path(candidate.path).stem)}\b", source):
            related.append(candidate)
        if len(related) >= MAX_REPAIR_DEPENDENCIES:
            break
    return related


def _llm_state(state: OrchestrationState, workflow_state: dict[str, Any]) -> dict[str, Any]:
    """Merge per-run LLM settings into the request envelope in memory only (never persisted)."""
    transient_state = dict(workflow_state)
    llm_meta = state.blueprint.get("llm") if isinstance(state.blueprint, dict) else None
    if isinstance(llm_meta, dict):
        for src, dst in (("provider", "llm_provider"), ("model", "llm_model"), ("endpoint", "llm_endpoint")):
            if llm_meta.get(src):
                transient_state[dst] = llm_meta[src]
        if llm_meta.get("apiKey") or llm_meta.get("api_key"):
            transient_state["llm_api_key"] = llm_meta.get("apiKey") or llm_meta.get("api_key")
    transient_cfg = get_transient_llm_config(state.trace_id)
    for src, dst in (("provider", "llm_provider"), ("model", "llm_model"), ("endpoint", "llm_endpoint"), ("api_key", "llm_api_key")):
        if transient_cfg.get(src):
            transient_state[dst] = transient_cfg[src]
    return transient_state


def _no_fix(state: OrchestrationState, hypothesis: str, guard: str, passed: bool = False) -> RepairResult:
    return RepairResult(
        outcome="NO_FIX",
        classification="UNKNOWN",
        hypothesis=hypothesis,
        patches=[],
        files_touched=[],
        guard_report=GuardReport(passed=passed, failed_guards=[] if passed else [guard]),
        attempts_used=state.attempts,
        trace_id=state.trace_id,
    )


def merge_repair_results(state: OrchestrationState, results: list[RepairResult]) -> RepairResult:
    """Combine per-file repairs: any patch wins; otherwise guard rejection, then LLM error, then no fix."""
    patched = [r for r in results if r.outcome == "PATCHED" and r.patches]
    if patched:
        touched = sorted({path for r in patched for path in r.files_touched})
        return RepairResult(
            outcome="PATCHED",
            classification=patched[0].classification,
            hypothesis=" | ".join(r.hypothesis for r in patched),
            patches=[patch for r in patched for patch in r.patches],
            files_touched=touched,
            guard_report=GuardReport(passed=True, failed_guards=[]),
            attempts_used=1,
            trace_id=state.trace_id,
        )
    for outcome in ("REJECTED_BY_GUARD", "ERROR", "NO_FIX"):
        match = next((r for r in results if r.outcome == outcome), None)
        if match is not None:
            return match
    return _no_fix(state, "Repair produced no result", "NO_RESULT")


def build_validator_node() -> Callable[[dict[str, Any], str], Any]:
    async def validate_node(blueprint: dict[str, Any], trace_id: str) -> UniformErrorBody:
        store = _workflow_store()
        workflow_state = store.load_state(trace_id)
        async with _service_client() as client:
            response = await client.validate_blueprint(
                ValidationAgentRequest(
                    trace_id=trace_id,
                    workflow_state=workflow_state,
                    blueprint=blueprint,
                ).model_dump()
            )
        store.save_state(trace_id, response.workflow_state)
        return response.validation

    return validate_node


def build_generation_node() -> Callable[[GenerationRequest, OrchestrationState], Any]:
    async def generation_node(request: GenerationRequest, state: OrchestrationState) -> list[Any]:
        store = _workflow_store()
        workflow_state = store.load_state(state.trace_id)
        if request.llm is not None:
            register_transient_llm_config(state.trace_id, request.llm)
            workflow_state["llm_provider"] = request.llm.provider
            workflow_state["llm_model"] = request.llm.model
            if request.llm.endpoint:
                workflow_state["llm_endpoint"] = request.llm.endpoint
        async with _service_client() as client:
            response = await client.generate_code(
                GenerationAgentRequest(
                    trace_id=state.trace_id,
                    workflow_state=workflow_state,
                    generation=request,
                ).model_dump()
            )
        store.save_state(state.trace_id, response.workflow_state)
        framework, version = _framework_and_version(state)
        state.profile = get_profile(framework, version)
        return response.files

    return generation_node


def build_verifier_node(
    runner: BaseVerifierRunner | None = None,
) -> Callable[[OrchestrationState], Any]:
    del runner  # verification always runs in the verifier service

    async def verify_node(state: OrchestrationState) -> VerificationResult:
        workspace = Path(state.workspace_dir).expanduser().resolve(strict=False)
        if not (workspace / "pom.xml").is_file():
            return VerificationResult(
                success=False,
                exit_code=1,
                timed_out=False,
                wall_time_seconds=0.01,
                issues=[
                    DiagnosticIssue(
                        file_path="pom.xml",
                        error_type="MISSING_POM",
                        message="Verification failed: pom.xml was not found in workspace.",
                    )
                ],
                raw_output="Verification failed: pom.xml was not generated or found in workspace.",
                runner_name="Orchestrator",
                image="none",
            )
        request = RunnerRequest(
            workspace_path=str(workspace),
            command=resolve_verifier_command(),
            timeout_seconds=int(os.getenv("VERIFIER_TIMEOUT_SECONDS", "900")),
        )
        store = _workflow_store()
        workflow_state = store.load_state(state.trace_id)
        async with _service_client() as client:
            response = await client.verify_workspace(
                VerifierAgentRequest(
                    trace_id=state.trace_id,
                    workflow_state=workflow_state,
                    runner=request,
                    files=collect_workspace_files(str(workspace)),
                ).model_dump()
            )
        store.save_state(state.trace_id, response.workflow_state)
        return response.verification

    return verify_node


def build_repair_node(
    repair_service: Any | None = None,
) -> Callable[[OrchestrationState], Any]:
    del repair_service

    async def repair_node(state: OrchestrationState) -> RepairResult:
        if state.verification is None or state.verification.success:
            return _no_fix(state, "Verification passed; no repair required", "", passed=True)
        issues = state.verification.issues or []
        if not issues:
            return _no_fix(state, "Verification failed but produced no diagnostic issues", "NO_DIAGNOSTICS")
        try:
            targets = load_repair_targets(state.workspace_dir, issues, MAX_REPAIR_FILES_PER_ATTEMPT)
        except (GraphContractError, OSError, ValueError) as exc:
            return _no_fix(state, f"Could not load repair target: {exc}", "LOAD_FILE_ERROR")

        framework, version = _framework_and_version(state)
        profile = state.profile or get_profile(framework, version)
        workspace_files = collect_workspace_files(state.workspace_dir)
        baseline = compute_test_baseline(state.workspace_dir)
        entities = state.blueprint.get("entities", []) if isinstance(state.blueprint, dict) else []
        store = _workflow_store()
        transient_state = _llm_state(state, store.load_state(state.trace_id))

        results: list[RepairResult] = []
        async with _service_client() as client:
            # One repair call per failing file; sequential so a rate-limited LLM is hit once, not N times
            for failing_file, file_issues in targets:
                repair_request = RepairRequest(
                    framework=profile.framework,
                    framework_version=profile.framework_version,
                    failing_file=failing_file,
                    issues=file_issues,
                    dependencies=_related_dependencies(failing_file, workspace_files),
                    allowed_paths=sorted({failing_file.path}),
                    attempt_budget=MAX_REPAIR_ATTEMPTS,
                    test_baseline=baseline,
                    blueprint_entities=entities if isinstance(entities, list) else [],
                )
                response = await client.repair_code(
                    RepairAgentRequest(
                        trace_id=state.trace_id,
                        workflow_state=transient_state,
                        repair=repair_request,
                    ).model_dump()
                )
                store.save_state(state.trace_id, response.workflow_state)
                results.append(response.repair_result)
                if response.repair_result.outcome == "ERROR":
                    break
        return merge_repair_results(state, results)

    return repair_node


def create_orchestrator_graph(
    generation_pipeline: Any | None = None,
    runner: BaseVerifierRunner | None = None,
    repair_service: Any | None = None,
    validate_node: Any | None = None,
) -> OrchestratorGraph:
    del generation_pipeline, repair_service
    return OrchestratorGraph(
        validate_node=validate_node or build_validator_node(),
        generation_node=build_generation_node(),
        verify_node=build_verifier_node(runner),
        repair_node=build_repair_node(),
    )
