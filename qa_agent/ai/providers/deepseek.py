"""Adaptador HTTPX nativo para DeepSeek API (A02, AC-10)."""

from __future__ import annotations

import json
import time
from typing import Any

from contracts.models import QAProviderRequest, QAProviderResponse
from qa_agent.ai.transport import QAHTTPTransport
from qa_agent.evidence import redact_text


class DeepSeekProviderAdapter:
    """Adaptador para DeepSeek Chat Completions con JSON Output y validación local de esquema."""

    def __init__(self, transport: QAHTTPTransport, model: str = "deepseek-chat") -> None:
        self.transport = transport
        self.model = model

    def send_request(self, req: QAProviderRequest) -> QAProviderResponse:
        t0 = time.perf_counter()
        url = "https://api.deepseek.com/chat/completions"
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
            "response_format": {"type": "json_object"},
        }

        try:
            resp = self.transport.send("POST", url=url, headers=headers, json_body=json_body)
        except Exception as exc:
            dur = time.perf_counter() - t0
            return QAProviderResponse(
                provider="deepseek",
                model=self.model,
                duration_seconds=dur,
                error_type="NETWORK_ERROR",
                error_message=str(exc),
            )

        dur = time.perf_counter() - t0
        clean_text = redact_text(resp.text, extra_secrets=[self.transport.api_key])

        if resp.status_code in (401, 403):
            return QAProviderResponse(
                provider="deepseek",
                model=self.model,
                duration_seconds=dur,
                error_type="AUTHENTICATION_ERROR",
                error_message=f"Credenciales DeepSeek inválidas ({resp.status_code}): {clean_text}",
            )

        if resp.status_code == 429:
            return QAProviderResponse(
                provider="deepseek",
                model=self.model,
                duration_seconds=dur,
                error_type="RATE_LIMIT_ERROR",
                error_message=f"Límite de cuota DeepSeek excedido (429): {clean_text}",
            )

        if resp.status_code != 200:
            return QAProviderResponse(
                provider="deepseek",
                model=self.model,
                duration_seconds=dur,
                error_type="API_ERROR",
                error_message=f"Error DeepSeek HTTP {resp.status_code}: {clean_text}",
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
                provider="deepseek",
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
                provider="deepseek",
                model=self.model,
                duration_seconds=dur,
                error_type="PARSE_ERROR",
                error_message=f"Error parseando respuesta JSON de DeepSeek: {exc}",
            )
