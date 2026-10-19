from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SAFE_TRACE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
_SENSITIVE_KEYS = ("api_key", "apikey", "secret", "password", "token")


def _strip_secrets(data: Any) -> Any:
    if isinstance(data, dict):
        cleaned: dict[str, Any] = {}
        for k, v in data.items():
            if any(term in str(k).lower() for term in _SENSITIVE_KEYS):
                continue
            cleaned[k] = _strip_secrets(v)
        return cleaned
    if isinstance(data, list):
        return [_strip_secrets(item) for item in data]
    return data


class WorkflowStore:
    """Filesystem-backed shared state store for stateless agent microservices."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, trace_id: str) -> Path:
        norm_id = str(trace_id or "").strip()
        if (
            not norm_id
            or ".." in norm_id
            or "/" in norm_id
            or "\\" in norm_id
            or not _SAFE_TRACE_ID_RE.fullmatch(norm_id)
        ):
            raise ValueError(f"Invalid or unsafe trace_id: {trace_id!r}")
        run_dir = (self.base_dir / norm_id).resolve()
        try:
            run_dir.relative_to(self.base_dir)
        except ValueError as exc:
            raise ValueError(f"trace_id escapes workflow store base_dir: {trace_id!r}") from exc
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def load_state(self, trace_id: str) -> dict[str, Any]:
        state_path = self._run_dir(trace_id) / "state.json"
        if not state_path.exists():
            return {"trace_id": trace_id, "artifacts": {}, "events": []}
        return json.loads(state_path.read_text(encoding="utf-8"))

    def save_state(self, trace_id: str, state: dict[str, Any]) -> dict[str, Any]:
        state_path = self._run_dir(trace_id) / "state.json"
        sanitized_state = _strip_secrets(state)
        state_path.write_text(
            json.dumps(sanitized_state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return sanitized_state

    def merge_state(self, trace_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        state = self.load_state(trace_id)
        state.update(patch)
        return self.save_state(trace_id, state)

    def append_event(self, trace_id: str, event: dict[str, Any]) -> dict[str, Any]:
        state = self.load_state(trace_id)
        events = state.setdefault("events", [])
        if isinstance(events, list):
            events.append(event)
        return self.save_state(trace_id, state)
