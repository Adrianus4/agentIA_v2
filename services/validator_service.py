from __future__ import annotations

from fastapi import Depends

from agents.blueprint import normalize_blueprint, validate_blueprint
from contracts.agent_api import ValidationAgentRequest, ValidationAgentResponse
from services.common import create_service_app, public_state, verify_gateway_auth

app = create_service_app("AgentIA Validator Service", "validator")


@app.post(
    "/v1/validate",
    response_model=ValidationAgentResponse,
    dependencies=[Depends(verify_gateway_auth)],
)
async def validate(request: ValidationAgentRequest) -> ValidationAgentResponse:
    normalized = normalize_blueprint(request.blueprint)
    validation = validate_blueprint(normalized)
    workflow_state = public_state(request.workflow_state)
    workflow_state["validation"] = validation.model_dump()
    return ValidationAgentResponse(
        trace_id=request.trace_id,
        workflow_state=workflow_state,
        validation=validation,
        normalized_blueprint=normalized,
    )
