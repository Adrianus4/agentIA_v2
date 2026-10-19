"""
Execution nodes factory for hermetic verification and bounded surgical repair.

Wires LocalDockerRunner / LocalSubprocessRunner and ScopedRepairService
into the canonical OrchestratorGraph.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agents.blueprint.validate import validate_blueprint
from agents.generator.common import resolve_generation
from agents.profiles.loader import get_profile
from agents.repair.service import ScopedRepairService
from agents.verifier.runner import (
    BaseVerifierRunner,
    LocalDockerRunner,
    LocalSubprocessRunner,
)
from app.core.llm.factory import LLMUnavailableError, build_llm_client
from app.orchestrator.generation import GenerationPipeline
from app.orchestrator.graph import (
    MAX_REPAIR_ATTEMPTS,
    GraphContractError,
    OrchestrationState,
    OrchestratorGraph,
    get_transient_llm_config,
    load_repair_file,
    normalize_blueprint,
)
from contracts.models import (
    DiagnosticIssue,
    GuardReport,
    RepairRequest,
    RepairResult,
    RunnerRequest,
    TestBaseline,
    VerificationResult,
)


def compute_test_baseline(workspace_dir: str) -> TestBaseline:
    """Scan workspace src/test/java files to compute actual test and assertion baseline counts."""
    test_root = Path(workspace_dir).expanduser() / "src" / "test"
    if not test_root.is_dir():
        return TestBaseline(test_count=0, assertion_count=0, disabled_count=0)

    test_count = 0
    assertion_count = 0
    disabled_count = 0
    assertion_re = re.compile(r"\b(?:assert[A-Z]\w*|statusCode|body)\s*\(")

    for java_file in test_root.rglob("*.java"):
        if not java_file.is_file():
            continue
        text = java_file.read_text(encoding="utf-8", errors="replace")
        test_count += len(re.findall(r"@Test\b", text))
        disabled_count += len(re.findall(r"@(?:Disabled|Ignore)\b", text))
        assertion_count += len(assertion_re.findall(text))

    return TestBaseline(
        test_count=test_count,
        assertion_count=assertion_count,
        disabled_count=disabled_count,
    )


def _resolve_llm_client(state: OrchestrationState) -> Any:
    """Per-run LLM settings (transient config, then blueprint llm block), resolved by the shared factory."""
    transient = get_transient_llm_config(state.trace_id)
    llm_meta = state.blueprint.get("llm") if isinstance(state.blueprint, dict) else None
    meta = dict(llm_meta) if isinstance(llm_meta, dict) else {}
    if not (meta or transient or os.getenv("LLM_PROVIDER") or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")):
        return None
    try:
        return build_llm_client(
            provider=transient.get("provider") or meta.get("provider"),
            model=transient.get("model") or meta.get("model"),
            endpoint=transient.get("endpoint") or meta.get("endpoint"),
            api_key=transient.get("api_key") or meta.get("apiKey") or meta.get("api_key"),
        )
    except LLMUnavailableError:
        return None


def resolve_default_runner() -> BaseVerifierRunner:
    """Select the best verifier runner available on the system."""
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


def resolve_verifier_command() -> list[str]:
    """Resolve the Maven verification command, defaulting to full test execution with isolated port."""
    cmd_env = os.getenv("VERIFIER_COMMAND", "").strip()
    if cmd_env:
        return cmd_env.split()
    compile_only = os.getenv("VERIFIER_COMPILE_ONLY", "").strip().lower() in ("1", "true", "yes")
    full_test_env = os.getenv("VERIFIER_FULL_TEST", "").strip().lower()
    if compile_only or full_test_env in ("0", "false", "no"):
        return ["mvn", "-B", "--no-transfer-progress", "test-compile"]
    return ["mvn", "-B", "--no-transfer-progress", "test", "-Dquarkus.http.test-port=0"]


def build_verifier_node(
    runner: BaseVerifierRunner | None = None,
) -> Callable[[OrchestrationState], Any]:
    active_runner = runner or resolve_default_runner()

    async def verify_node(state: OrchestrationState) -> VerificationResult:
        workspace = Path(state.workspace_dir).expanduser().resolve(strict=False)
        pom_path = workspace / "pom.xml"

        if not pom_path.is_file():
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
                runner_name=active_runner.__class__.__name__,
                image="none",
            )

        command = resolve_verifier_command()
        timeout_sec = int(os.getenv("VERIFIER_TIMEOUT_SECONDS", "600"))
        request = RunnerRequest(
            workspace_path=str(workspace),
            command=command,
            timeout_seconds=timeout_sec,
        )

        return await asyncio.to_thread(active_runner.run, request)

    return verify_node


def build_repair_node(
    repair_service: ScopedRepairService | None = None,
) -> Callable[[OrchestrationState], Any]:
    async def repair_node(state: OrchestrationState) -> RepairResult:
        if state.verification is None or state.verification.success:
            return RepairResult(
                outcome="NO_FIX",
                classification="UNKNOWN",
                hypothesis="Verification passed; no repair required",
                patches=[],
                files_touched=[],
                guard_report=GuardReport(passed=True, failed_guards=[]),
                attempts_used=state.attempts,
                trace_id=state.trace_id,
            )

        issues = state.verification.issues or []
        if not issues:
            return RepairResult(
                outcome="NO_FIX",
                classification="UNKNOWN",
                hypothesis="Verification failed but produced no diagnostic issues",
                patches=[],
                files_touched=[],
                guard_report=GuardReport(passed=False, failed_guards=["NO_DIAGNOSTICS"]),
                attempts_used=state.attempts,
                trace_id=state.trace_id,
            )

        try:
            failing_file = load_repair_file(state.workspace_dir, issues)
        except (GraphContractError, OSError, ValueError) as exc:
            return RepairResult(
                outcome="NO_FIX",
                classification="UNKNOWN",
                hypothesis=f"Could not load repair target: {exc}",
                patches=[],
                files_touched=[],
                guard_report=GuardReport(passed=False, failed_guards=["LOAD_FILE_ERROR"]),
                attempts_used=state.attempts,
                trace_id=state.trace_id,
            )

        framework = str(state.blueprint.get("framework", "quarkus"))
        version = str(state.blueprint.get("version", state.blueprint.get("frameworkVersion", "3.15")))
        profile = state.profile or get_profile(framework, version)

        active_service: ScopedRepairService | None = repair_service
        if active_service is None:
            llm_client = _resolve_llm_client(state)
            if llm_client is None:
                return RepairResult(
                    outcome="NO_FIX",
                    classification="UNKNOWN",
                    hypothesis="No LLM client configured for AST repair generation",
                    patches=[],
                    files_touched=[],
                    guard_report=GuardReport(passed=False, failed_guards=["NO_LLM"]),
                    attempts_used=state.attempts,
                    trace_id=state.trace_id,
                )
            active_service = ScopedRepairService(
                patch_generator=lambda prompt: resolve_generation(llm_client, prompt)
            )

        issue_paths = {issue.file_path for issue in issues if issue.file_path.strip()}
        allowed_paths = {failing_file.path}
        allowed_paths.update(issue_paths)

        dependencies = [
            f for f in (state.generated_files or [])
            if f.path != failing_file.path and f.content
        ]

        entities_list = state.blueprint.get("entities", []) if isinstance(state.blueprint, dict) else []
        repair_request = RepairRequest(
            framework=profile.framework,
            framework_version=profile.framework_version,
            failing_file=failing_file,
            issues=issues,
            dependencies=dependencies,
            allowed_paths=sorted(allowed_paths),
            attempt_budget=MAX_REPAIR_ATTEMPTS,
            test_baseline=compute_test_baseline(state.workspace_dir),
            blueprint_entities=entities_list if isinstance(entities_list, list) else [],
        )

        return await asyncio.to_thread(active_service.repair, profile, repair_request, state.trace_id)

    return repair_node


def create_orchestrator_graph(
    generation_pipeline: GenerationPipeline | None = None,
    runner: BaseVerifierRunner | None = None,
    repair_service: ScopedRepairService | None = None,
    validate_node: Any | None = None,
) -> OrchestratorGraph:
    """Build a production OrchestratorGraph with real generation, verification, and repair nodes."""

    def _default_prod_validate(blueprint: Any, trace_id: str) -> Any:
        del trace_id
        normalized = normalize_blueprint(blueprint)
        return validate_blueprint(normalized)

    val_node = validate_node or _default_prod_validate
    gen_node = generation_pipeline or GenerationPipeline()
    ver_node = build_verifier_node(runner)
    rep_node = build_repair_node(repair_service)

    return OrchestratorGraph(
        validate_node=val_node,
        generation_node=gen_node,
        verify_node=ver_node,
        repair_node=rep_node,
    )
