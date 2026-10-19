"""Adaptador HTTPX nativo para Google Gemini API v1beta (A02, AC-10)."""

from __future__ import annotations

import json
import time
from typing import Any

from contracts.models import QAProviderRequest, QAProviderResponse
from qa_agent.ai.transport import QAHTTPTransport
from qa_agent.evidence import redact_text


class GeminiProviderAdapter:
    """Adaptador para Gemini API utilizando endpoint nativo generateContent con salida estructurada."""

    def __init__(self, transport: QAHTTPTransport, model: str = "gemini-2.5-flash") -> None:
        self.transport = transport
        self.model = model

    def send_request(self, req: QAProviderRequest) -> QAProviderResponse:
        t0 = time.perf_counter()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.transport.api_key,
        }

        # Convertir mensajes a contents de Gemini
        contents: list[dict[str, Any]] = []
        for msg in req.messages:
            role = "user" if msg.get("role") in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

        json_body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": req.temperature,
                "maxOutputTokens": req.max_tokens,
                "responseMimeType": "application/json",
            },
        }
        if req.system_instruction:
            json_body["systemInstruction"] = {
                "parts": [{"text": req.system_instruction}]
            }

        try:
            resp = self.transport.send("POST", url=url, headers=headers, json_body=json_body)
        except Exception as exc:
            dur = time.perf_counter() - t0
            return QAProviderResponse(
                provider="gemini",
                model=self.model,
                duration_seconds=dur,
                error_type="NETWORK_ERROR",
                error_message=str(exc),
            )

        dur = time.perf_counter() - t0
        clean_text = redact_text(resp.text, extra_secrets=[self.transport.api_key])

        if resp.status_code in (401, 403):
            return QAProviderResponse(
                provider="gemini",
                model=self.model,
                duration_seconds=dur,
                error_type="AUTHENTICATION_ERROR",
                error_message=f"Credenciales Gemini inválidas ({resp.status_code}): {clean_text}",
            )

        if resp.status_code == 429:
            return QAProviderResponse(
                provider="gemini",
                model=self.model,
                duration_seconds=dur,
                error_type="RATE_LIMIT_ERROR",
                error_message=f"Límite de cuota Gemini excedido (429): {clean_text}",
            )

        if resp.status_code != 200:
            return QAProviderResponse(
                provider="gemini",
                model=self.model,
                duration_seconds=dur,
                error_type="API_ERROR",
                error_message=f"Error Gemini HTTP {resp.status_code}: {clean_text}",
            )

        try:
            data = resp.json()
            candidates = data.get("candidates", [])
            content_text = ""
            finish_reason = None
            if candidates:
                cand = candidates[0]
                finish_reason = cand.get("finishReason")
                parts = cand.get("content", {}).get("parts", [])
                if parts:
                    content_text = parts[0].get("text", "")

            usage = data.get("usageMetadata", {})
            return QAProviderResponse(
                provider="gemini",
                model=self.model,
                content=content_text,
                prompt_tokens=usage.get("promptTokenCount"),
                completion_tokens=usage.get("candidatesTokenCount"),
                total_tokens=usage.get("totalTokenCount"),
                duration_seconds=dur,
                raw_finish_reason=finish_reason,
            )
        except Exception as exc:
            return QAProviderResponse(
                provider="gemini",
                model=self.model,
                duration_seconds=dur,
                error_type="PARSE_ERROR",
                error_message=f"Error parseando respuesta JSON de Gemini: {exc}",
            )
