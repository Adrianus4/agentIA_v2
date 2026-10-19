from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from contracts.models import DiagnosticIssue, RunnerRequest, VerificationResult
from qa_scenarios.support.network_guard import (
    append_telemetry_event,
    install_loopback_only_socket_guard,
)

_CALL_COUNTERS: dict[str, int] = {
    "verifier": 0,
    "repair_llm": 0,
    "spec_llm": 0,
}


def read_control_config() -> dict[str, Any]:
    path_raw = os.environ.get("QA_SCENARIO_CONTROL_FILE")
    if not path_raw:
        return {}
    path = Path(path_raw)
    if not path.is_file():
        return {}
    with contextlib.suppress(OSError, json.JSONDecodeError):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    return {}


class ControlledRepairLLMClient:
    """Doble de frontera determinista únicamente para el cliente LLM (nunca salta ScopedRepairService ni G1-G8)."""

    def __init__(self, role: str = "repair") -> None:
        self.role = role

    def generate(self, prompt: str) -> str:
        ctrl = read_control_config()
        idx = _CALL_COUNTERS["repair_llm"]
        _CALL_COUNTERS["repair_llm"] = idx + 1
        append_telemetry_event(
            {
                "event": "llm_boundary_call",
                "boundary": self.role,
                "call_index": idx,
                "llm_mode": "double",
                "prompt_len": len(prompt),
            }
        )
        if ctrl.get("forbid_llm_calls", False):
            append_telemetry_event({"event": "unexpected_llm_call", "boundary": self.role})
            raise RuntimeError("Llamada LLM no permitida en este escenario.")

        if ctrl.get("repair_llm_error"):
            raise RuntimeError(str(ctrl["repair_llm_error"]))

        responses = ctrl.get("repair_llm_responses")
        if isinstance(responses, list) and responses:
            chosen = responses[min(idx, len(responses) - 1)]
            return str(chosen)

        if "repair_llm_response" in ctrl:
            return str(ctrl["repair_llm_response"])

        raise RuntimeError("No hay respuesta configurada en el doble de frontera LLM.")


class ControlledBoundaryVerifierRunner:
    """
    Doble de frontera del compilador para la suite `platform` (`http=real`, `compiler=double`).
    Inspecciona los archivos materializados reales enviados por el orquestador al servicio `verifier`.
    """

    def run(self, request: RunnerRequest) -> VerificationResult:
        ctrl = read_control_config()
        idx = _CALL_COUNTERS["verifier"]
        _CALL_COUNTERS["verifier"] = idx + 1

        workspace = Path(request.workspace_path)
        files_found = sorted(
            str(p.relative_to(workspace)).replace("\\", "/")
            for p in workspace.rglob("*")
            if p.is_file()
        )
        append_telemetry_event(
            {
                "event": "compiler_boundary_call",
                "call_index": idx,
                "compiler_mode": "double",
                "command": list(request.command),
                "file_count": len(files_found),
            }
        )

        # Punto de sincronización opcional para observar RUNNING de forma determinista (P03)
        hold_file_raw = ctrl.get("hold_signal_file")
        if hold_file_raw:
            hold_path = Path(str(hold_file_raw))
            import time

            deadline = time.perf_counter() + float(ctrl.get("hold_max_seconds", 8.0))
            while hold_path.exists() and time.perf_counter() < deadline:
                time.sleep(0.04)

        # Inspeccionar si un archivo requerido debe contener un texto específico para aprobar (ciclo de reparación real)
        required_substr_map = ctrl.get("verifier_require_file_substring")
        if isinstance(required_substr_map, dict):
            for rel_path, expected_substr in required_substr_map.items():
                target_file = workspace / str(rel_path)
                content = (
                    target_file.read_text(encoding="utf-8", errors="replace")
                    if target_file.is_file()
                    else ""
                )
                if str(expected_substr) not in content:
                    issue_line = int(ctrl.get("verifier_issue_line", 8))
                    return VerificationResult(
                        success=False,
                        exit_code=1,
                        timed_out=False,
                        wall_time_seconds=0.05,
                        issues=[
                            DiagnosticIssue(
                                file_path=str(rel_path),
                                line_number=issue_line,
                                column_number=1,
                                error_type="COMPILATION_ERROR",
                                message=f"expected '{expected_substr}' in {rel_path}",
                            )
                        ],
                        raw_output=(
                            f"[ERROR] COMPILATION ERROR :\n"
                            f"[ERROR] /workspace/{rel_path}:[{issue_line},1] error: expected '{expected_substr}'\n"
                            f"[INFO] 1 error\n"
                        ),
                        raw_output_truncated=False,
                        runner_name="ControlledBoundaryVerifierRunner",
                        image="double",
                    )

        # Secuencia explícita de resultados de verificación si el escenario la define
        sequence = ctrl.get("verifier_sequence")
        if isinstance(sequence, list) and sequence:
            step_cfg = sequence[min(idx, len(sequence) - 1)]
            if isinstance(step_cfg, dict) and not step_cfg.get("success", True):
                rel_path = str(
                    step_cfg.get(
                        "file_path",
                        "src/main/java/com/agentia/generated/CustomerResource.java",
                    )
                )
                line_no = int(step_cfg.get("line_number", 8))
                msg = str(step_cfg.get("message", "cannot find symbol"))
                err_type = str(step_cfg.get("error_type", "COMPILATION_ERROR"))
                return VerificationResult(
                    success=False,
                    exit_code=1,
                    timed_out=bool(step_cfg.get("timed_out", False)),
                    wall_time_seconds=0.05,
                    issues=[
                        DiagnosticIssue(
                            file_path=rel_path,
                            line_number=line_no,
                            column_number=1,
                            error_type=err_type,
                            message=msg,
                        )
                    ],
                    raw_output=(
                        f"[ERROR] COMPILATION ERROR :\n"
                        f"[ERROR] /workspace/{rel_path}:[{line_no},1] error: {msg}\n"
                        f"[INFO] 1 error\n"
                    ),
                    raw_output_truncated=False,
                    runner_name="ControlledBoundaryVerifierRunner",
                    image="double",
                )

        return VerificationResult(
            success=True,
            exit_code=0,
            timed_out=False,
            wall_time_seconds=0.04,
            issues=[],
            raw_output="[INFO] BUILD SUCCESS (controlled compiler boundary double)\n",
            raw_output_truncated=False,
            runner_name="ControlledBoundaryVerifierRunner",
            image="double",
        )


class ScenarioTelemetryAndFaultMiddleware(BaseHTTPMiddleware):
    """
    Registra el orden real de pasos HTTP entre servicios y permite provocar fallos de transporte/HTTP
    en servicios downstream específicos cuando el escenario de `P04` lo solicita.
    """

    def __init__(self, app: Any, role: str) -> None:
        super().__init__(app)
        self.role = role

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        path = request.url.path
        if path != "/health":
            append_telemetry_event(
                {
                    "event": "http_request",
                    "service": self.role,
                    "method": request.method,
                    "path": path,
                }
            )
            ctrl = read_control_config()
            faults = ctrl.get("service_faults")
            if isinstance(faults, dict) and self.role in faults:
                fault_spec = faults[self.role]
                fault_type = (
                    fault_spec.get("type")
                    if isinstance(fault_spec, dict)
                    else str(fault_spec)
                )
                if fault_type == "http_503":
                    return JSONResponse(
                        status_code=503,
                        content={"detail": f"Simulated 503 failure in {self.role}"},
                    )
                if fault_type == "http_500":
                    return JSONResponse(
                        status_code=500,
                        content={"detail": f"Simulated 500 error in {self.role}"},
                    )
                if fault_type == "malformed_json":
                    return Response(
                        content=b'{"broken_json": true, "unterminated": ',
                        status_code=200,
                        media_type="application/json",
                    )
                if fault_type == "invalid_contract":
                    return JSONResponse(
                        status_code=200,
                        content={"unexpected_schema": "missing_required_fields"},
                    )
                if fault_type == "timeout":
                    sleep_s = (
                        float(fault_spec.get("sleep_seconds", 2.5))
                        if isinstance(fault_spec, dict)
                        else 2.5
                    )
                    await asyncio.sleep(sleep_s)
                    return JSONResponse(
                        status_code=504,
                        content={"detail": f"Simulated timeout in {self.role}"},
                    )
                if fault_type == "crash":
                    os._exit(99)

        return await call_next(request)


def build_role_asgi_app(role: str, mode: str) -> Any:
    install_loopback_only_socket_guard()

    # Parchear fronteras LLM en todos los procesos para evitar salidas a proveedores externos
    import app.core.llm.factory as llm_factory

    def _controlled_build_llm_client(*args: Any, **kwargs: Any) -> Any:
        return ControlledRepairLLMClient(role=role)

    llm_factory.build_llm_client = _controlled_build_llm_client

    if role == "validator":
        from services.validator_service import app as validator_app

        validator_app.add_middleware(ScenarioTelemetryAndFaultMiddleware, role="validator")
        return validator_app

    if role == "generator":
        from services.generator_service import app as generator_app

        generator_app.add_middleware(ScenarioTelemetryAndFaultMiddleware, role="generator")
        return generator_app

    if role == "verifier":
        import services.verifier_service as verifier_mod

        if mode == "platform":
            verifier_mod._runner = lambda: ControlledBoundaryVerifierRunner()  # type: ignore[assignment,return-value]
        else:
            # En modo java (Trabajo 4 / 5), usar el runner host real registrando telemetría de frontera real
            orig_runner_fn = verifier_mod._runner

            class _TrackedRealRunner:
                def __init__(self) -> None:
                    self._inner = orig_runner_fn()

                def run(self, request: RunnerRequest) -> VerificationResult:
                    append_telemetry_event(
                        {
                            "event": "compiler_boundary_call",
                            "compiler_mode": "real",
                            "workspace_path": request.workspace_path,
                            "command": list(request.command),
                        }
                    )
                    res = self._inner.run(request)
                    append_telemetry_event(
                        {
                            "event": "compiler_boundary_result",
                            "compiler_mode": "real",
                            "workspace_path": request.workspace_path,
                            "success": res.success,
                            "exit_code": res.exit_code,
                            "issue_count": len(res.issues),
                        }
                    )
                    return res

            verifier_mod._runner = lambda: _TrackedRealRunner()  # type: ignore[assignment,return-value]

        verifier_mod.app.add_middleware(ScenarioTelemetryAndFaultMiddleware, role="verifier")
        return verifier_mod.app

    if role == "repair":
        import services.repair_service as repair_mod

        repair_mod._build_repair_llm_client = lambda wf_state: ControlledRepairLLMClient(role="repair")
        repair_mod.app.add_middleware(ScenarioTelemetryAndFaultMiddleware, role="repair")
        return repair_mod.app

    if role == "orchestrator":
        import app.main as main_mod
        import app.orchestrator.execution_nodes as exec_nodes_mod

        if mode == "platform":
            exec_nodes_mod.resolve_default_runner = lambda: ControlledBoundaryVerifierRunner()  # type: ignore[assignment,return-value]
            main_mod.resolve_default_runner = lambda: ControlledBoundaryVerifierRunner()  # type: ignore[assignment,return-value]

        orchestrator_app = main_mod.create_app()
        orchestrator_app.add_middleware(ScenarioTelemetryAndFaultMiddleware, role="orchestrator")
        return orchestrator_app

    raise ValueError(f"Rol de servicio desconocido: {role!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Runner de nodo de servicio QA para AgentIA")
    parser.add_argument(
        "--role",
        required=True,
        choices=["validator", "generator", "verifier", "repair", "orchestrator"],
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--mode", default="platform", choices=["platform", "java"])
    args = parser.parse_args(argv)

    if os.environ.get("QA_FORCE_STARTUP_FAIL_ROLE") == args.role:
        sys.stderr.write(f"Fallo de arranque simulado para el rol '{args.role}'.\n")
        sys.stderr.flush()
        return 1

    asgi_app = build_role_asgi_app(args.role, args.mode)
    config = uvicorn.Config(
        app=asgi_app,
        host=args.host,
        port=args.port,
        log_level="warning",
        access_log=False,
        lifespan="on",
    )
    server = uvicorn.Server(config)
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
