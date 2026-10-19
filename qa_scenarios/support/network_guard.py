from __future__ import annotations

import contextlib
import json
import os
import socket
import time
from pathlib import Path
from typing import Any

LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0"})

PROVIDER_ENV_KEYS: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    "OLLAMA_API_KEY",
    "DEEPSEEK_API_KEY",
    "LLM_API_KEY",
)

_GUARD_INSTALLED = False
_ORIGINAL_SOCKET_CONNECT = socket.socket.connect
_ORIGINAL_CREATE_CONNECTION = socket.create_connection


def append_telemetry_event(event: dict[str, Any]) -> None:
    """Registra un evento de telemetría en el archivo JSONL compartido del harness."""
    telemetry_path_raw = os.environ.get("QA_SCENARIO_TELEMETRY_FILE")
    if not telemetry_path_raw:
        return
    path = Path(telemetry_path_raw)
    payload = {"ts": time.time(), "role": os.environ.get("QA_SERVICE_ROLE", "unknown"), **event}
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def strip_external_provider_keys() -> None:
    """Elimina cualquier clave real de proveedor LLM del entorno del proceso."""
    for key in PROVIDER_ENV_KEYS:
        os.environ.pop(key, None)


def _is_loopback_address(address: Any) -> bool:
    if isinstance(address, tuple) and len(address) >= 1:
        host = str(address[0]).strip().lower()
        if host in LOOPBACK_HOSTS or host.startswith("127."):
            return True
        return False
    # Unix domain sockets / named pipes
    return True


def install_loopback_only_socket_guard() -> None:
    """
    Bloquea cualquier intento de conexión TCP saliente hacia hosts no loopback (`127.0.0.1` / `::1`)
    y registra el intento en la telemetría del escenario para hacer fallar inmediatamente el caso (RF-305).
    """
    global _GUARD_INSTALLED
    strip_external_provider_keys()
    if _GUARD_INSTALLED:
        return

    def _guarded_connect(self: socket.socket, address: Any) -> Any:
        if not _is_loopback_address(address):
            append_telemetry_event(
                {
                    "event": "blocked_external_connection",
                    "target": repr(address),
                }
            )
            raise RuntimeError(
                f"QA Network Guard: conexión externa bloqueada hacia {address!r}. Solo se permite loopback 127.0.0.1."
            )
        return _ORIGINAL_SOCKET_CONNECT(self, address)

    def _guarded_create_connection(
        address: tuple[str | None, int],
        timeout: float | None = socket._GLOBAL_DEFAULT_TIMEOUT,  # type: ignore[attr-defined]
        source_address: tuple[str, int] | None = None,
        *,
        all_errors: bool = False,
    ) -> socket.socket:
        if not _is_loopback_address(address):
            append_telemetry_event(
                {
                    "event": "blocked_external_connection",
                    "target": repr(address),
                }
            )
            raise RuntimeError(
                f"QA Network Guard: conexión externa bloqueada hacia {address!r}. Solo se permite loopback 127.0.0.1."
            )
        return _ORIGINAL_CREATE_CONNECTION(
            address,
            timeout=timeout,
            source_address=source_address,
            all_errors=all_errors,
        )

    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
    socket.create_connection = _guarded_create_connection  # type: ignore[assignment]
    _GUARD_INSTALLED = True
