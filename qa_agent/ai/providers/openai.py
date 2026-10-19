"""Adaptador HTTPX nativo para OpenAI API (A02, AC-10)."""

from __future__ import annotations

import json
import time
from typing import Any

from contracts.models import QAProviderRequest, QAProviderResponse
from qa_agent.ai.transport import QAHTTPTransport
from qa_agent.evidence import redact_text


class OpenAIProviderAdapter:
    """Adaptador para OpenAI Chat Completions con soporte de salidas estructuradas JSON Schema."""

    def __init__(self, transport: QAHTTPTransport, model: str = "gpt-4o-mini") -> None:
        self.transport = transport
        self.model = model

    def send_request(self, req: QAProviderRequest) -> QAProviderResponse:
        t0 = time.perf_counter()
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.transport.api_key}",
        }

        messages: list[dict[str, str]] = []
        if req.system_instruction:
            messages.append({"role": "system", "content": req.system_instruction})
        for msg in req.messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        json_body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "qa_analysis",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "hypotheses": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "cause": {"type": "string"},
                                        "likelihood": {
                                            "type": "string",
                                            "enum": ["likely", "possible", "unlikely"],
                                        },
                                        "referenced_evidence": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "suggested_action": {"type": "string"},
                                    },
                                    "required": [
                                        "cause",
                                        "likelihood",
                                        "referenced_evidence",
                                        "suggested_action",
                                    ],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["hypotheses"],
                        "additionalProperties": False,
                    },
                },
            },
        }

        try:
            resp = self.transport.send("POST", url=url, headers=headers, json_body=json_body)
        except Exception as exc:
            dur = time.perf_counter() - t0
            return QAProviderResponse(
                provider="openai",
                model=self.model,
                duration_seconds=dur,
                error_type="NETWORK_ERROR",
                error_message=str(exc),
            )

        dur = time.perf_counter() - t0
        clean_text = redact_text(resp.text, extra_secrets=[self.transport.api_key])

        if resp.status_code in (401, 403):
            return QAProviderResponse(
                provider="openai",
                model=self.model,
                duration_seconds=dur,
                error_type="AUTHENTICATION_ERROR",
                error_message=f"Credenciales OpenAI inválidas ({resp.status_code}): {clean_text}",
            )

        if resp.status_code == 429:
            return QAProviderResponse(
                provider="openai",
                model=self.model,
                duration_seconds=dur,
                error_type="RATE_LIMIT_ERROR",
                error_message=f"Límite de cuota OpenAI excedido (429): {clean_text}",
            )

        if resp.status_code != 200:
            return QAProviderResponse(
                provider="openai",
                model=self.model,
                duration_seconds=dur,
                error_type="API_ERROR",
                error_message=f"Error OpenAI HTTP {resp.status_code}: {clean_text}",
            )

        try:
            data = resp.json()
            choices = data.get("choices", [])
            content_text = ""
            finish_reason = None
            if choices:
                ch = choices[0]
                finish_reason = ch.get("finish_reason")
                content_text = ch.get("message", {}).get("content", "")

            usage = data.get("usage", {})
            return QAProviderResponse(
                provider="openai",
                model=self.model,
                content=content_text,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
                duration_seconds=dur,
                raw_finish_reason=finish_reason,
            )
        except Exception as exc:
            return QAProviderResponse(
                provider="openai",
                model=self.model,
                duration_seconds=dur,
                error_type="PARSE_ERROR",
                error_message=f"Error parseando respuesta JSON de OpenAI: {exc}",
            )
