"""Repair agent: one failing file + diagnostics in, a guard-checked patch out."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import Depends

from agents.generator.common import resolve_generation
from agents.profiles.loader import get_profile
from agents.repair.service import ScopedRepairService
from app.core.llm.factory import build_llm_client
from contracts.agent_api import RepairAgentRequest, RepairAgentResponse
from contracts.models import GuardReport, RepairResult
from services.common import create_service_app, public_state, verify_gateway_auth

app = create_service_app("AgentIA Repair Service", "repair")


def _build_repair_llm_client(workflow_state: dict[str, Any]) -> Any:
    return build_llm_client(
        provider=workflow_state.get("llm_provider"),
        model=workflow_state.get("llm_model"),
        endpoint=workflow_state.get("llm_endpoint"),
        api_key=workflow_state.get("llm_api_key"),
    )


def _llm_failure(request: RepairAgentRequest, exc: Exception) -> RepairResult:
    """An unavailable or rate-limited LLM is a terminal ERROR, never an HTTP 500 the client would retry."""
    text = str(exc)
    rate_limited = "429" in text or "quota" in text.lower() or "ResourceExhausted" in type(exc).__name__
    return RepairResult(
        outcome="ERROR",
        classification="UNKNOWN",
        hypothesis=f"LLM {'rate limited' if rate_limited else 'unavailable'}: {type(exc).__name__}: {text[:400]}",
        patches=[],
        files_touched=[],
        guard_report=GuardReport(
            passed=False,
            failed_guards=["LLM_RATE_LIMITED" if rate_limited else "LLM_UNAVAILABLE"],
        ),
        attempts_used=0,
        trace_id=request.trace_id,
    )


@app.post(
    "/v1/repair",
    response_model=RepairAgentResponse,
    dependencies=[Depends(verify_gateway_auth)],
)
async def repair(request: RepairAgentRequest) -> RepairAgentResponse:
    profile = get_profile(request.repair.framework, request.repair.framework_version)
    try:
        llm_client = _build_repair_llm_client(request.workflow_state)
        service = ScopedRepairService(patch_generator=lambda prompt: resolve_generation(llm_client, prompt))
        repair_result = await asyncio.to_thread(service.repair, profile, request.repair, request.trace_id)
    except Exception as exc:  # noqa: BLE001 - every LLM failure becomes a typed result
        repair_result = _llm_failure(request, exc)
    workflow_state = public_state(request.workflow_state)
    workflow_state["repair"] = repair_result.model_dump()
    return RepairAgentResponse(
        trace_id=request.trace_id,
        workflow_state=workflow_state,
        repair_result=repair_result,
    )
