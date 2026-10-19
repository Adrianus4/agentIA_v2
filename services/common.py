"""Shared plumbing for the agent microservices: gateway auth, health probe, app factory."""
from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, status

SECRET_STATE_KEYS = ("llm_api_key",)


def verify_gateway_auth(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """Accept the shared gateway key or bearer token; open when neither is configured (local MVP)."""
    expected_key = (
        os.getenv("AGENT_GATEWAY_API_KEY")
        or os.getenv("ORCHESTRATOR_API_KEY")
        or os.getenv("API_KEY")
        or ""
    ).strip()
    expected_bearer = (
        os.getenv("AGENT_GATEWAY_BEARER_TOKEN")
        or os.getenv("ORCHESTRATOR_BEARER_TOKEN")
        or ""
    ).strip()
    if not expected_key and not expected_bearer:
        return
    supplied_key = (x_api_key or "").strip()
    if expected_key and supplied_key and hmac.compare_digest(supplied_key, expected_key):
        return
    if expected_bearer and authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if hmac.compare_digest(token, expected_bearer):
            return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized agent service request",
    )


def public_state(workflow_state: dict[str, Any]) -> dict[str, Any]:
    """Copy of the envelope state without transient secrets."""
    cleaned = dict(workflow_state)
    for key in SECRET_STATE_KEYS:
        cleaned.pop(key, None)
    return cleaned


def create_service_app(title: str, service: str) -> FastAPI:
    app = FastAPI(title=title, version="v1")

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": service}

    return app
