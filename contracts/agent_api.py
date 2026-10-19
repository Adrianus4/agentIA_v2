from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from contracts.models import (
    FileContent,
    GenerationRequest,
    RepairRequest,
    RepairResult,
    RunnerRequest,
    UniformErrorBody,
    VerificationResult,
)


class TraceEnvelope(BaseModel):
    trace_id: str = Field(min_length=1)
    workflow_state: dict[str, Any] = Field(default_factory=dict)


class ValidationAgentRequest(TraceEnvelope):
    blueprint: dict[str, Any] = Field(default_factory=dict)


class ValidationAgentResponse(TraceEnvelope):
    validation: UniformErrorBody
    normalized_blueprint: dict[str, Any] = Field(default_factory=dict)


class GenerationAgentRequest(TraceEnvelope):
    generation: GenerationRequest


class GenerationAgentResponse(TraceEnvelope):
    files: list[FileContent] = Field(default_factory=list)


class VerifierAgentRequest(TraceEnvelope):
    runner: RunnerRequest
    # When files are sent, the verifier builds them in its own scratch workspace and ignores
    # runner.workspace_path, so verifier and orchestrator never need to share a filesystem.
    files: list[FileContent] = Field(default_factory=list)


class VerifierAgentResponse(TraceEnvelope):
    verification: VerificationResult


class RepairAgentRequest(TraceEnvelope):
    repair: RepairRequest


class RepairAgentResponse(TraceEnvelope):
    repair_result: RepairResult
