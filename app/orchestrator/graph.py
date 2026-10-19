"""LangGraph orchestrator: validate -> generate -> verify -> (repair -> apply_patch -> verify)* -> outcome.

Each node delegates to an injected callable (an HTTP agent client in production, a fake in tests),
so the graph only owns routing, the repair budget and the orchestrator-side workspace.
"""
from __future__ import annotations

import hashlib
import inspect
import os
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from agents.blueprint.normalize import normalize_blueprint
from app.orchestrator.patching import PatchApplicationError, apply_patch
from contracts.models import (
    DiagnosticIssue,
    FileContent,
    FrameworkProfile,
    GenerationRequest,
    GuardReport,
    RepairResult,
    RunOutcome,
    UniformErrorBody,
    VerificationResult,
)

# Repair budget: up to MAX_REPAIR_ATTEMPTS repairs, hence up to MAX_ATTEMPTS verifications
MAX_REPAIR_ATTEMPTS = 3
MAX_ATTEMPTS = MAX_REPAIR_ATTEMPTS + 1
MAX_REPAIR_FILE_CHARS = 50_000
Node = Callable[..., Any]
ProgressCallback = Callable[[str, "OrchestrationState"], Awaitable[None] | None]

# Transient in-memory LLM credential store keyed by trace_id (never persisted to disk or blueprint)
_TRANSIENT_LLM_CONFIGS: dict[str, dict[str, Any]] = {}


def register_transient_llm_config(trace_id: str, llm_config: Any | None) -> None:
    if not trace_id or llm_config is None:
        return
    entry: dict[str, Any] = {}
    if isinstance(llm_config, Mapping):
        for k in ("provider", "model", "endpoint", "api_key", "apiKey"):
            if llm_config.get(k):
                entry[k] = llm_config[k]
    else:
        for attr in ("provider", "model", "endpoint", "api_key"):
            val = getattr(llm_config, attr, None)
            if val:
                entry[attr] = val
    if "apiKey" in entry and "api_key" not in entry:
        entry["api_key"] = entry["apiKey"]
    if entry:
        _TRANSIENT_LLM_CONFIGS[trace_id] = entry


def get_transient_llm_config(trace_id: str) -> dict[str, Any]:
    return dict(_TRANSIENT_LLM_CONFIGS.get(trace_id, {}))


def clear_transient_llm_config(trace_id: str) -> None:
    _TRANSIENT_LLM_CONFIGS.pop(trace_id, None)


def default_max_repair_attempts() -> int:
    raw = os.getenv("AGENTIA_MAX_REPAIR_ATTEMPTS", "").strip()
    try:
        return max(0, min(int(raw), 3)) if raw else MAX_REPAIR_ATTEMPTS
    except ValueError:
        return MAX_REPAIR_ATTEMPTS


class GraphContractError(TypeError):
    """Raised when a Track 2 node does not return its required contract."""


@dataclass
class OrchestrationState:
    workspace_dir: str
    blueprint: Mapping[str, Any]
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    attempts: int = 0
    validation: UniformErrorBody | None = None
    verification: VerificationResult | None = None
    repair: RepairResult | None = None
    generated_files: list[FileContent] = field(default_factory=list)
    outcome: RunOutcome | None = None
    profile: FrameworkProfile | None = None
    stage: str = "pending"
    history: list[dict[str, Any]] = field(default_factory=list)


class _GraphState(TypedDict):
    run: OrchestrationState


async def _invoke(node: Node, *args: Any, **kwargs: Any) -> Any:
    result = node(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


def _require(value: Any, expected: type[Any], name: str) -> Any:
    if not isinstance(value, expected):
        raise GraphContractError(f"{name} node returned {type(value).__name__}, expected {expected.__name__}")
    return value


def _default_validate(blueprint: Mapping[str, Any], trace_id: str) -> UniformErrorBody:
    del blueprint, trace_id
    return UniformErrorBody(valid=True, diagnostics=[])


def _default_verify(state: OrchestrationState) -> VerificationResult:
    del state
    return VerificationResult(
        success=True,
        wall_time_seconds=0.0,
        issues=[],
        raw_output="",
        runner_name="dummy",
        image="dummy",
    )


def _default_repair(state: OrchestrationState) -> RepairResult:
    return RepairResult(
        outcome="NO_FIX",
        classification="UNKNOWN",
        hypothesis="No dummy repair is available",
        patches=[],
        files_touched=[],
        guard_report=GuardReport(passed=False, failed_guards=["dummy"]),
        attempts_used=state.attempts,
        trace_id=state.trace_id,
    )


def _compute_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


_normalize_blueprint = normalize_blueprint


def _write_generated_files(workspace_dir: str, files: list[FileContent]) -> None:
    workspace_path = Path(workspace_dir).expanduser()
    workspace_path.mkdir(parents=True, exist_ok=True)
    workspace = workspace_path.resolve(strict=True)
    if not workspace.is_dir():
        raise GraphContractError(f"generation workspace is not a directory: {workspace_dir}")

    for file in files:
        if file.content is None:
            raise GraphContractError(f"generated file has no content: {file.path}")
        target = (workspace / file.path).resolve()
        try:
            target.relative_to(workspace)
        except ValueError as exc:
            raise GraphContractError(f"generated path escapes workspace: {file.path}") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file.content, encoding="utf-8")
        if not file.digest:
            file.digest = _compute_digest(file.content)


def _refresh_generated_files(
    workspace_dir: str,
    existing_files: list[FileContent],
    touched_paths: list[str] | None = None,
) -> list[FileContent]:
    """Re-read workspace files after patching so state.generated_files always reflects repaired disk state."""
    workspace_path = Path(workspace_dir).expanduser()
    if not workspace_path.is_dir():
        return existing_files
    workspace = workspace_path.resolve(strict=True)

    updated: list[FileContent] = []
    seen_paths: set[str] = set()

    for fc in existing_files:
        seen_paths.add(fc.path)
        candidate = (workspace / fc.path).resolve()
        try:
            candidate.relative_to(workspace)
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8", errors="replace")
                updated.append(FileContent(path=fc.path, content=text, digest=_compute_digest(text)))
            else:
                updated.append(fc)
        except ValueError:
            updated.append(fc)

    for rel_path in touched_paths or []:
        norm_rel = rel_path.lstrip("/").removeprefix("./")
        if norm_rel in seen_paths:
            continue
        candidate_extra = (workspace / norm_rel).resolve()
        try:
            candidate_extra.relative_to(workspace)
            if candidate_extra.is_file():
                extra_text = candidate_extra.read_text(encoding="utf-8", errors="replace")
                updated.append(
                    FileContent(
                        path=candidate_extra.relative_to(workspace).as_posix(),
                        content=extra_text,
                        digest=_compute_digest(extra_text),
                    )
                )
                seen_paths.add(norm_rel)
        except ValueError:
            continue

    return updated


def _load_file(workspace: Path, rel_path: str) -> FileContent:
    candidate = (workspace / rel_path).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise GraphContractError(f"diagnostic path escapes workspace: {rel_path}") from exc
    if not candidate.is_file():
        raise GraphContractError(f"diagnostic file does not exist: {rel_path}")
    content = candidate.read_text(encoding="utf-8", errors="replace")
    return FileContent(
        path=candidate.relative_to(workspace).as_posix(),
        content=content[:MAX_REPAIR_FILE_CHARS],
        digest=_compute_digest(content),
    )


def load_repair_file(workspace_dir: str, issues: list[DiagnosticIssue]) -> FileContent:
    workspace_path = Path(workspace_dir).expanduser()
    workspace_path.mkdir(parents=True, exist_ok=True)
    workspace = workspace_path.resolve(strict=True)
    issue = next((item for item in issues if item.file_path.strip()), None)
    if issue is None:
        raise GraphContractError("verification did not identify a failing file")
    return _load_file(workspace, issue.file_path)


def load_repair_targets(
    workspace_dir: str,
    issues: list[DiagnosticIssue],
    max_files: int = 3,
) -> list[tuple[FileContent, list[DiagnosticIssue]]]:
    """Group diagnostics by failing file (first-seen order) so one attempt can repair several files."""
    workspace_path = Path(workspace_dir).expanduser()
    workspace_path.mkdir(parents=True, exist_ok=True)
    workspace = workspace_path.resolve(strict=True)
    grouped: dict[str, list[DiagnosticIssue]] = {}
    for issue in issues:
        path = issue.file_path.strip()
        if path:
            grouped.setdefault(path, []).append(issue)
    targets: list[tuple[FileContent, list[DiagnosticIssue]]] = []
    for path, file_issues in grouped.items():
        try:
            targets.append((_load_file(workspace, path), file_issues))
        except GraphContractError:
            continue
        if len(targets) >= max_files:
            break
    if not targets:
        raise GraphContractError("verification did not identify a loadable failing file")
    return targets


def _invoke_patcher(
    patcher: Callable[..., None],
    workspace_dir: str,
    patch_content: str,
    allowed_paths: list[str] | None,
) -> None:
    try:
        sig = inspect.signature(patcher)
        if "allowed_paths" in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        ):
            patcher(workspace_dir, patch_content, allowed_paths=allowed_paths)
            return
    except (ValueError, TypeError):
        pass
    patcher(workspace_dir, patch_content)


def _snapshot(workspace_dir: str, rel_paths: list[str]) -> dict[str, str]:
    """Digest of each existing file, used to detect patches that change nothing."""
    workspace = Path(workspace_dir).expanduser().resolve()
    digests: dict[str, str] = {}
    for rel in rel_paths:
        candidate = (workspace / rel.lstrip("/")).resolve()
        if candidate.is_file() and candidate.is_relative_to(workspace):
            digests[rel] = _compute_digest(candidate.read_text(encoding="utf-8", errors="replace"))
    return digests


def _feedback_verification(
    previous: VerificationResult | None,
    file_path: str,
    error_type: str,
    message: str,
    runner_name: str,
) -> VerificationResult:
    """Keep the original diagnostics and append why the last repair did not land, for the next attempt."""
    issues = list(previous.issues) if previous else []
    issues.append(DiagnosticIssue(file_path=file_path, error_type=error_type, message=message))
    return VerificationResult(
        success=False,
        exit_code=previous.exit_code if previous else None,
        wall_time_seconds=0.0,
        issues=issues,
        raw_output=message,
        runner_name=runner_name,
        image="none",
    )


class OrchestratorGraph:
    def __init__(
        self,
        *,
        validate_node: Node = _default_validate,
        generation_node: Node | None = None,
        verify_node: Node = _default_verify,
        repair_node: Node = _default_repair,
        patcher: Callable[..., None] = apply_patch,
        generated_file_writer: Callable[[str, list[FileContent]], None] = _write_generated_files,
        max_repair_attempts: int | None = None,
    ) -> None:
        self.validate_node = validate_node
        self.generation_node = generation_node
        self.verify_node = verify_node
        self.repair_node = repair_node
        self.patcher = patcher
        self.generated_file_writer = generated_file_writer
        self.max_repair_attempts = (
            default_max_repair_attempts() if max_repair_attempts is None else max_repair_attempts
        )

    # ------------------------------------------------------------------ graph
    def build(
        self,
        progress: ProgressCallback | None = None,
        llm_config: Any | None = None,
        max_repair_attempts: int | None = None,
    ) -> Any:
        """Compile the LangGraph state machine for one run."""
        budget = self.max_repair_attempts if max_repair_attempts is None else max_repair_attempts

        async def emit(stage: str, run: OrchestrationState, **detail: Any) -> None:
            run.stage = stage
            run.history.append({"stage": stage, "attempts": run.attempts, **detail})
            if progress is not None:
                await _invoke(progress, stage, run)

        async def validate(gs: _GraphState) -> _GraphState:
            run = gs["run"]
            await emit("validate", run)
            run.validation = _require(
                await _invoke(self.validate_node, run.blueprint, run.trace_id),
                UniformErrorBody,
                "validate",
            )
            if not run.validation.valid:
                run.outcome = "ERROR"
            return {"run": run}

        async def generate(gs: _GraphState) -> _GraphState:
            run = gs["run"]
            await emit("generate", run)
            assert self.generation_node is not None
            generated = _require(
                await _invoke(
                    self.generation_node,
                    GenerationRequest(blueprint=dict(run.blueprint), trace_id=run.trace_id, llm=llm_config),
                    run,
                ),
                list,
                "generate",
            )
            if not all(isinstance(file, FileContent) for file in generated):
                raise GraphContractError("generate node returned a list containing a non-FileContent value")
            run.generated_files = generated
            self.generated_file_writer(run.workspace_dir, generated)
            return {"run": run}

        async def verify(gs: _GraphState) -> _GraphState:
            run = gs["run"]
            await emit("verify", run)
            run.verification = _require(await _invoke(self.verify_node, run), VerificationResult, "verify")
            if run.verification.success:
                run.generated_files = _refresh_generated_files(
                    run.workspace_dir,
                    run.generated_files,
                    run.repair.files_touched if run.repair else None,
                )
                run.outcome = "SUCCESS"
            return {"run": run}

        async def repair(gs: _GraphState) -> _GraphState:
            run = gs["run"]
            await emit("repair", run)
            run.repair = _require(await _invoke(self.repair_node, run), RepairResult, "repair")
            if run.repair.outcome == "REJECTED_BY_GUARD":
                # A rejected patch spends one attempt and goes back to the repairer with the reason
                run.attempts += 1
                target = run.repair.files_touched[0] if run.repair.files_touched else (
                    run.verification.issues[0].file_path if run.verification and run.verification.issues else ""
                )
                run.verification = _feedback_verification(
                    run.verification,
                    target,
                    "GUARD_REJECTED",
                    f"Previous patch was rejected by guards {run.repair.guard_report.failed_guards}: "
                    "edit only the failing file and keep every existing test assertion.",
                    "Guards",
                )
            elif run.repair.outcome != "PATCHED" or not run.repair.patches:
                run.outcome = "ERROR" if run.repair.outcome == "ERROR" else "NO_FIX"
            return {"run": run}

        async def apply(gs: _GraphState) -> _GraphState:
            run = gs["run"]
            await emit("apply_patch", run)
            assert run.repair is not None
            run.attempts += 1
            issue_paths = [
                iss.file_path.strip()
                for iss in (run.verification.issues if run.verification else [])
                if iss.file_path and iss.file_path.strip()
            ]
            allowed_for_patch = sorted({*(run.repair.files_touched or []), *issue_paths}) or None
            before = _snapshot(run.workspace_dir, allowed_for_patch or [])
            try:
                for patch_content in run.repair.patches:
                    _invoke_patcher(self.patcher, run.workspace_dir, patch_content, allowed_for_patch)
                if self.patcher is apply_patch and before and before == _snapshot(
                    run.workspace_dir, allowed_for_patch or []
                ):
                    # The patch left every file byte-identical; Maven would only repeat the same errors
                    raise PatchApplicationError(
                        "patch applied but changed nothing; the failing code is still identical"
                    )
                run.generated_files = _refresh_generated_files(
                    run.workspace_dir, run.generated_files, run.repair.files_touched
                )
                run.stage = "patched"
            except (PatchApplicationError, OSError, ValueError, RuntimeError) as exc:
                message = f"Patch application failed: {exc}"
                failing_path = run.repair.files_touched[0] if run.repair.files_touched else "unknown"
                run.repair = RepairResult(
                    outcome="NO_FIX",
                    classification="UNKNOWN",
                    hypothesis=message,
                    patches=run.repair.patches,
                    files_touched=run.repair.files_touched,
                    guard_report=GuardReport(passed=False, failed_guards=["PATCH_APPLICATION"]),
                    attempts_used=run.attempts,
                    trace_id=run.trace_id,
                )
                # Feed the failure straight back to the repairer: the code on disk did not change,
                # so re-running Maven would only repeat the previous diagnostics.
                run.verification = _feedback_verification(
                    run.verification, failing_path, "PATCH_APPLICATION_ERROR", message, "Patcher"
                )
                run.stage = "patch_failed"
            return {"run": run}

        async def exhausted(gs: _GraphState) -> _GraphState:
            run = gs["run"]
            run.outcome = "NO_FIX"
            await emit("exhausted", run)
            return {"run": run}

        def after_validate(gs: _GraphState) -> str:
            if gs["run"].outcome == "ERROR":
                return END
            return "generate" if self.generation_node is not None else "verify"

        def after_verify(gs: _GraphState) -> str:
            run = gs["run"]
            if run.outcome == "SUCCESS":
                return END
            return "repair" if run.attempts < budget else "exhausted"

        def after_repair(gs: _GraphState) -> str:
            run = gs["run"]
            if run.outcome is not None:
                return END
            if run.repair is not None and run.repair.outcome == "REJECTED_BY_GUARD":
                return "repair" if run.attempts < budget else "exhausted"
            return "apply_patch"

        def after_apply(gs: _GraphState) -> str:
            run = gs["run"]
            if run.stage == "patch_failed":
                return "repair" if run.attempts < budget else "exhausted"
            return "verify"

        graph = StateGraph(_GraphState)
        graph.add_node("validate", validate)
        graph.add_node("generate", generate)
        graph.add_node("verify", verify)
        graph.add_node("repair", repair)
        graph.add_node("apply_patch", apply)
        graph.add_node("exhausted", exhausted)
        graph.add_edge(START, "validate")
        graph.add_conditional_edges("validate", after_validate, ["generate", "verify", END])
        graph.add_edge("generate", "verify")
        graph.add_conditional_edges("verify", after_verify, ["repair", "exhausted", END])
        graph.add_conditional_edges("repair", after_repair, ["apply_patch", "repair", "exhausted", END])
        graph.add_conditional_edges("apply_patch", after_apply, ["verify", "repair", "exhausted"])
        graph.add_edge("exhausted", END)
        return graph.compile()

    async def run(
        self,
        workspace_dir: str,
        blueprint: Mapping[str, Any] | None = None,
        *,
        trace_id: str | None = None,
        llm_config: Any | None = None,
        progress: ProgressCallback | None = None,
        max_repair_attempts: int | None = None,
    ) -> OrchestrationState:
        Path(workspace_dir).expanduser().mkdir(parents=True, exist_ok=True)
        state = OrchestrationState(
            workspace_dir=workspace_dir,
            blueprint=_normalize_blueprint(blueprint or {}),
            trace_id=trace_id or str(uuid4()),
        )
        register_transient_llm_config(state.trace_id, llm_config)
        try:
            budget = self.max_repair_attempts if max_repair_attempts is None else max_repair_attempts
            compiled = self.build(progress=progress, llm_config=llm_config, max_repair_attempts=budget)
            # Each repair cycle is at most 3 node visits; leave generous headroom
            limit = 10 + 4 * (budget + 1)
            final = await compiled.ainvoke({"run": state}, config={"recursion_limit": limit})
            result: OrchestrationState = final["run"]
            result.stage = "done"
            return result
        finally:
            clear_transient_llm_config(state.trace_id)
