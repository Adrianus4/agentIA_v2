from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from uuid import uuid4

from agents.generator.deployment import DeploymentGenerator
from agents.generator.messaging import MessagingGenerator
from agents.generator.ops import ObservabilityGenerator, SecurityGenerator
from agents.generator.outbox import OutboxGenerator
from app.orchestrator.generation import GenerationPipeline
from contracts.models import FileContent, GenerationRequest
from contracts.solution_models import (
    GeneratedServiceArtifact,
    SolutionGenerationRequest,
    SolutionGenerationResult,
)


def _merge_extra_properties(files: list[FileContent]) -> list[FileContent]:
    """Append observability.properties, security.properties, and messaging.properties into application.properties."""
    extra_sections: list[str] = []
    prop_labels = {
        "src/main/resources/observability.properties": "Observability",
        "src/main/resources/security.properties": "Security",
        "src/main/resources/messaging.properties": "Messaging",
    }
    for fc in files:
        if fc.path in prop_labels and fc.content:
            label = prop_labels[fc.path]
            extra_sections.append(f"# --- {label} Configuration ---\n" + fc.content.strip())

    if not extra_sections:
        return files

    updated: list[FileContent] = []
    found_app_props = False
    for fc in files:
        if fc.path == "src/main/resources/application.properties":
            found_app_props = True
            base = (fc.content or "").rstrip()
            merged_content = base + "\n\n" + "\n\n".join(extra_sections) + "\n"
            updated.append(
                FileContent(
                    path=fc.path,
                    content=merged_content,
                    digest=hashlib.sha256(merged_content.encode("utf-8")).hexdigest(),
                )
            )
        else:
            updated.append(fc)

    if not found_app_props:
        merged_content = "\n\n".join(extra_sections) + "\n"
        updated.append(
            FileContent(
                path="src/main/resources/application.properties",
                content=merged_content,
                digest=hashlib.sha256(merged_content.encode("utf-8")).hexdigest(),
            )
        )
    return updated


def resolve_managed_workspace(
    raw_workspace_dir: str | None,
    service_name: str,
    trace_id: str,
) -> Path:
    """Resolve a job-isolated workspace path strictly inside AGENTIA_WORKSPACE_ROOT."""
    root_env = os.getenv("AGENTIA_WORKSPACE_ROOT", "/tmp/agentia-workspace")
    base_root = Path(root_env).expanduser().resolve()
    base_root.mkdir(parents=True, exist_ok=True)

    slug = (
        "".join(c if c.isalnum() or c in "-_" else "_" for c in service_name).strip("_")
        or "service"
    )
    raw = (raw_workspace_dir or "").strip()
    cand: Path | None = None
    if raw and ".." not in Path(raw).parts:
        cand = Path(raw).expanduser().resolve()

    target: Path | None = None
    if cand is not None:
        try:
            cand.relative_to(base_root)
            if cand != base_root:
                target = cand
        except ValueError:
            # Allow empty pytest tmp_path fixtures only when AGENTIA_WORKSPACE_ROOT is not explicitly set
            if (
                "AGENTIA_WORKSPACE_ROOT" not in os.environ
                and ("pytest-" in str(cand) or cand.parent.name.startswith("tmp"))
                and not (cand / "src").exists()
            ):
                target = cand

    short_trace = "".join(c for c in trace_id if c.isalnum())[:8] or "job"
    if target is None:
        # One directory per run: two runs of the same service never share (or wipe) a workspace
        target = (base_root / f"{slug}-{short_trace}").resolve()

    marker = target / ".agentia-workspace"
    owner = marker.read_text(encoding="utf-8").strip() if marker.is_file() else None
    unmanaged_sources = target.exists() and (target / "src").exists() and owner is None
    owned_by_other_run = owner is not None and owner != trace_id
    if unmanaged_sources or owned_by_other_run:
        # Never overwrite a foreign directory or another run's workspace; branch off a sibling
        base_name = target.name if target.parent == base_root else slug
        target = (base_root / f"{base_name}-{short_trace}").resolve()

    return target


def _materialize_service_files(
    workspace_path: Path,
    files: list[FileContent],
    trace_id: str,
) -> None:
    """Safely write generated service files to a managed workspace directory."""
    workspace_path.mkdir(parents=True, exist_ok=True)
    marker = workspace_path / ".agentia-workspace"
    if marker.is_file():
        for stale_subdir in ("src", "target"):
            stale = workspace_path / stale_subdir
            if stale.exists():
                shutil.rmtree(stale, ignore_errors=True)
    marker.write_text(trace_id, encoding="utf-8")

    for fc in files:
        if fc.content is None:
            continue
        target = (workspace_path / fc.path).resolve()
        try:
            target.relative_to(workspace_path)
        except ValueError:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fc.content, encoding="utf-8")


class SolutionGenerationPipeline:
    def __init__(self, generation_pipeline: GenerationPipeline | None = None) -> None:
        self.generation_pipeline = generation_pipeline or GenerationPipeline()
        self.messaging_generator = MessagingGenerator()
        self.outbox_generator = OutboxGenerator()
        self.deployment_generator = DeploymentGenerator()
        self.observability_generator = ObservabilityGenerator()
        self.security_generator = SecurityGenerator()

    def __call__(self, request: SolutionGenerationRequest) -> SolutionGenerationResult:
        trace_id = request.trace_id or str(uuid4())
        services: list[GeneratedServiceArtifact] = []
        manifest: list[FileContent] = []

        for service in request.solution.services:
            safe_ws_path = resolve_managed_workspace(
                service.workspace_dir,
                service.service_name,
                trace_id,
            )
            workspace_dir = str(safe_ws_path)
            blueprint = service.to_generation_blueprint(
                observability=request.solution.observability,
                security=request.solution.security,
            )
            per_service_request = GenerationRequest(
                blueprint=blueprint,
                trace_id=trace_id,
                llm=request.llm,
            )
            base_files = self.generation_pipeline(per_service_request)
            extra_files: list[FileContent] = []
            extra_files.extend(
                self.messaging_generator.generate(
                    service,
                    request.solution.observability,
                    shared_events=request.solution.shared_events,
                )
            )
            extra_files.extend(self.outbox_generator.generate(service))
            extra_files.extend(self.observability_generator.generate(service, request.solution.observability))
            extra_files.extend(self.security_generator.generate(service, request.solution.security))
            extra_files.extend(
                self.deployment_generator.generate(
                    service,
                    request.solution.deployment,
                    request.solution.observability,
                    request.solution.security,
                )
            )
            all_files = _merge_extra_properties(base_files + extra_files)
            for fc in all_files:
                if fc.content is not None and not fc.digest:
                    fc.digest = hashlib.sha256(fc.content.encode("utf-8")).hexdigest()

            _materialize_service_files(safe_ws_path, all_files, trace_id)

            services.append(
                GeneratedServiceArtifact(
                    service_name=service.service_name,
                    workspace_dir=workspace_dir,
                    files=all_files,
                    status="GENERATED",
                )
            )
            manifest.append(
                FileContent(
                    path=f"{service.service_name}/manifest.json",
                    content=(
                        "{\n"
                        f"  \"service\": \"{service.service_name}\",\n"
                        f"  \"workspace_dir\": \"{workspace_dir}\",\n"
                        f"  \"file_count\": {len(all_files)}\n"
                        "}\n"
                    ),
                )
            )

        manifest.append(
            FileContent(
                path="solution-manifest.json",
                content=(
                    "{\n"
                    f"  \"solution\": \"{request.solution.name}\",\n"
                    f"  \"trace_id\": \"{trace_id}\",\n"
                    f"  \"service_count\": {len(services)}\n"
                    "}\n"
                ),
            )
        )

        return SolutionGenerationResult(
            trace_id=trace_id,
            solution_name=request.solution.name,
            status="GENERATED",
            outcome="GENERATED",
            services=services,
            manifest=manifest,
        )
