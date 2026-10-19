"""Transporte HTTPX nativo, aislamiento estricto de secretos y presupuestos acotados (A01, A02, AC-10, AC-11, AC-12, AC-15)."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from qa_agent.evidence import redact_text


class QACredentialsMissingError(Exception):
    """Lanzada cuando se solicita modo live a un proveedor pero su variable de entorno no está configurada."""


class QABudgetExceededError(Exception):
    """Lanzada cuando se excede el número máximo de peticiones o el deadline total."""


class QAHTTPTransport:
    """Cliente HTTP síncrono acotado por número de peticiones, timeout y deadline total."""

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 60.0,
        deadline_seconds: float = 120.0,
        max_requests: int = 3,
        verify_tls: bool = True,
    ) -> None:
        if not api_key or not api_key.strip():
            raise QACredentialsMissingError("La clave de API no puede estar vacía.")
        self.api_key = api_key.strip()
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.deadline_seconds = max(1.0, float(deadline_seconds))
        self.max_requests = max(1, int(max_requests))
        self.verify_tls = verify_tls

        self.request_count: int = 0
        self._start_time: float | None = None

    def _check_budget(self) -> float:
        now = time.monotonic()
        if self._start_time is None:
            self._start_time = now

        elapsed = now - self._start_time
        if elapsed >= self.deadline_seconds:
            raise QABudgetExceededError(
                f"Deadline total de IA ({self.deadline_seconds}s) excedido (transcurrido: {elapsed:.2f}s)."
            )

        if self.request_count >= self.max_requests:
            raise QABudgetExceededError(
                f"Presupuesto de solicitudes IA excedido (máximo permitido: {self.max_requests})."
            )

        remaining_time = max(1.0, min(self.timeout_seconds, self.deadline_seconds - elapsed))
        return remaining_time

    def send(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        remaining_timeout = self._check_budget()
        self.request_count += 1

        with httpx.Client(timeout=remaining_timeout, verify=self.verify_tls) as client:
            try:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_body,
                )
                return response
            except httpx.TimeoutException as exc:
                raise TimeoutError(f"Tiempo de espera agotado al consultar proveedor IA: {exc}") from exc
            except httpx.RequestError as exc:
                raise ConnectionError(f"Error de red o conexión al consultar proveedor IA: {exc}") from exc
