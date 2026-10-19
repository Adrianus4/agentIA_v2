from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from agents.blueprint.validate import validate_blueprint
from agents.generator import EntityGenerator, ResourceGenerator, TestGenerator
from agents.profiles.loader import get_profile
from agents.repair.service import ScopedRepairService
from agents.scaffolder.extensions import derive_extensions
from agents.scaffolder.safety import validate_request
from agents.scaffolder.service import Scaffolder
from agents.scaffolder.verification import verify_scaffold
from agents.verifier.runner import LocalDockerRunner
from app.orchestrator.graph import (
    MAX_REPAIR_ATTEMPTS,
    GraphContractError,
    OrchestrationState,
    OrchestratorGraph,
    _normalize_blueprint,
    _write_generated_files,
    load_repair_file,
)
from app.orchestrator.patching import apply_patch
from contracts.models import (
    FileContent,
    FrameworkProfile,
    GenerationRequest,
    GuardReport,
    RepairRequest,
    RepairResult,
    RunnerRequest,
    RunOutcome,
    ScaffoldRequest,
    TestBaseline,
    UniformErrorBody,
    VerificationResult,
)


def _run_sync(coro: Any) -> Any:
    """Safely execute a coroutine from synchronous caller, even if an event loop is already running."""
    loop: asyncio.AbstractEventLoop | None = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


@dataclass
class PipelineState:
    workspace_dir: str
    blueprint: dict[str, Any]
    trace_id: str
    attempts: int = 0
    profile: FrameworkProfile | None = None
    generated_files: list[FileContent] | None = None
    validation: UniformErrorBody | None = None
    verification: VerificationResult | None = None
    repair: RepairResult | None = None
    outcome: RunOutcome | None = None


class PipelineGraph:
    """Concrete synchronous compatibility path for the orchestration graph."""

    def __init__(
        self,
        llm_client: Any,
        *,
        runner: LocalDockerRunner | None = None,
        repair_service: ScopedRepairService | None = None,
        patcher: Callable[[str, str], None] = apply_patch,
        writer: Callable[[str, list[FileContent]], None] = _write_generated_files,
        scaffolder: Scaffolder | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.runner = runner or LocalDockerRunner()
        self.repair_service = repair_service or ScopedRepairService()
        self.patcher = patcher
        self.writer = writer
        self.entity_generator = EntityGenerator()
        self.resource_generator = ResourceGenerator()
        self.test_generator = TestGenerator()
        self.scaffolder = scaffolder

    def run(self, workspace_dir: str, blueprint: Mapping[str, Any], trace_id: str) -> PipelineState:
        normalized_blueprint = _normalize_blueprint(blueprint)

        framework = str(normalized_blueprint.get("framework", "quarkus"))
        version = str(
            normalized_blueprint.get("version", normalized_blueprint.get("frameworkVersion", "3"))
        ).split(".", 1)[0]
        profile = get_profile(framework, version)

        async def _validate(bp: Mapping[str, Any], tid: str) -> UniformErrorBody:
            return validate_blueprint(dict(bp))

        async def _generate(request: GenerationRequest, state: OrchestrationState) -> list[FileContent]:
            state.profile = profile
            if state.blueprint.get("scaffold"):
                if self.scaffolder is None or profile.scaffold is None:
                    raise GraphContractError("scaffolding requested but no scaffolder or scaffold profile configured")
                scaffold_config = state.blueprint.get("scaffold")
                if isinstance(scaffold_config, dict):
                    group_id = str(scaffold_config.get("groupId", "com.example"))
                    artifact_id = str(scaffold_config.get("artifactId", framework))
                else:
                    group_id = "com.example"
                    artifact_id = str(state.blueprint.get("serviceName", framework))
                scaffold_request = ScaffoldRequest(
                    group_id=group_id,
                    artifact_id=artifact_id,
                    package_name=str(state.blueprint["packageName"]),
                    java_version=profile.java_version,
                    extensions=derive_extensions(dict(state.blueprint), profile),
                    workspace_path=workspace_dir,
                )
                validate_request(scaffold_request)
                scaffold_result = self.scaffolder.scaffold(scaffold_request, profile)
                if not scaffold_result.success:
                    raise RuntimeError("scaffold generation failed")
                scaffold_verification = verify_scaffold(
                    workspace_dir, self.runner, timeout_seconds=scaffold_request.timeout_seconds
                )
                if not scaffold_verification.success:
                    state.verification = scaffold_verification
                    raise RuntimeError("scaffold verification failed")

                gen_req = GenerationRequest(blueprint=dict(state.blueprint), trace_id=state.trace_id)
            else:
                gen_req = request

            return (
                self.entity_generator.generate(gen_req, profile, self.llm_client)
                + self.resource_generator.generate(gen_req, profile, self.llm_client)
                + self.test_generator.generate(gen_req, profile, self.llm_client)
            )

        async def _verify(state: OrchestrationState) -> VerificationResult:
            return self.runner.run(
                RunnerRequest(workspace_path=workspace_dir, command=["mvn", "clean", "test"])
            )

        async def _repair(state: OrchestrationState) -> RepairResult:
            try:
                issues = state.verification.issues if state.verification else []
                failing_file = load_repair_file(workspace_dir, issues)
            except (GraphContractError, OSError, ValueError, TypeError):
                return RepairResult(
                    outcome="NO_FIX",
                    classification="UNKNOWN",
                    hypothesis="Could not load repair file",
                    patches=[],
                    files_touched=[],
                    guard_report=GuardReport(passed=False, failed_guards=["LOAD_FILE"]),
                    attempts_used=state.attempts,
                    trace_id=trace_id,
                )
            allowed_paths = {file.path for file in state.generated_files}
            allowed_paths.add(failing_file.path)
            return self.repair_service.repair(
                profile,
                RepairRequest(
                    framework=profile.framework,
                    framework_version=profile.framework_version,
                    failing_file=failing_file,
                    issues=state.verification.issues if state.verification else [],
                    allowed_paths=sorted(allowed_paths),
                    attempt_budget=MAX_REPAIR_ATTEMPTS,
                    test_baseline=TestBaseline(test_count=0, assertion_count=0, disabled_count=0),
                    blueprint_entities=list(state.blueprint.get("entities", [])) if isinstance(state.blueprint.get("entities"), list) else [],
                ),
                trace_id,
            )

        orchestrator = OrchestratorGraph(
            validate_node=_validate,
            generation_node=_generate,
            verify_node=_verify,
            repair_node=_repair,
            patcher=self.patcher,
            generated_file_writer=self.writer,
        )

        try:
            orch_state = _run_sync(
                orchestrator.run(
                    workspace_dir,
                    normalized_blueprint,
                    trace_id=trace_id,
                )
            )
        except (GraphContractError, RuntimeError, ValueError, OSError):
            # Handle scaffold or configuration failures gracefully
            return PipelineState(
                workspace_dir=workspace_dir,
                blueprint=dict(normalized_blueprint),
                trace_id=trace_id,
                attempts=0,
                profile=profile,
                outcome="ERROR",
            )

        return PipelineState(
            workspace_dir=orch_state.workspace_dir,
            blueprint=dict(orch_state.blueprint),
            trace_id=orch_state.trace_id,
            attempts=orch_state.attempts,
            profile=profile,
            generated_files=orch_state.generated_files,
            validation=orch_state.validation,
            verification=orch_state.verification,
            repair=orch_state.repair,
            outcome=orch_state.outcome,
        )
