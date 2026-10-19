"""Generator agent: blueprint in, source tree out (templates first, LLM only as fallback)."""
from __future__ import annotations

import asyncio

from fastapi import Depends, HTTPException, status

from agents.generator.pipeline import GenerationPipeline
from app.core.llm.factory import LLMUnavailableError
from contracts.agent_api import GenerationAgentRequest, GenerationAgentResponse
from services.common import create_service_app, public_state, verify_gateway_auth

app = create_service_app("AgentIA Generator Service", "generator")


@app.post(
    "/v1/generate",
    response_model=GenerationAgentResponse,
    dependencies=[Depends(verify_gateway_auth)],
)
async def generate(request: GenerationAgentRequest) -> GenerationAgentResponse:
    pipeline = GenerationPipeline()
    try:
        files = await asyncio.to_thread(pipeline, request.generation)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    workflow_state = public_state(request.workflow_state)
    # Keep the envelope small: the files travel in the response body, the state only records paths
    workflow_state["generated_paths"] = [file.path for file in files]
    return GenerationAgentResponse(
        trace_id=request.trace_id,
        workflow_state=workflow_state,
        files=files,
    )
