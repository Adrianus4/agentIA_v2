from __future__ import annotations

import asyncio
import hmac
import inspect
import os
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agents.blueprint.validate import validate_blueprint
from app.core.llm.client import (
    GeminiLLMClient,
    LocalOpenAICompatibleClient,
    OpenAICompatibleClient,
)
from app.core.llm.factory import resolve_llm_settings
from app.orchestrator.clients.workflow_store import WorkflowStore
from app.orchestrator.db.repository import (
    ExecutionRun,
    ExecutionRunRepository,
)
from app.orchestrator.execution_nodes import (
    resolve_default_runner,
    resolve_verifier_command,
)
from app.orchestrator.execution_nodes_microservice import create_orchestrator_graph
from app.orchestrator.graph import (
    OrchestrationState,
    OrchestratorGraph,
    normalize_blueprint,
)
from app.orchestrator.solution_generation import (
    SolutionGenerationPipeline,
    resolve_managed_workspace,
)
from app.orchestrator.spec_agent import SpecDraftingAgent, SpecDraftingError
from contracts.models import (
    LLMConfiguration,
    LLMVerifyRequest,
    RunnerRequest,
    SpecDraftRequest,
)
from contracts.solution_models import SolutionGenerationRequest

API_KEY_ENV = "ORCHESTRATOR_API_KEY"
DATABASE_PATH_ENV = "ORCHESTRATOR_DATABASE_PATH"
PUBLIC_READ_ENV = "ORCHESTRATOR_ALLOW_PUBLIC_READ"
GENERATION_ENABLED_ENV = "ORCHESTRATOR_GENERATION_ENABLED"

_DEFAULT_ALLOWED_OPENAI_HOSTS = {"genailab.tcs.in", "api.openai.com", "localhost", "127.0.0.1", "::1"}


class BlueprintRequest(BaseModel):
    workspace_dir: str = Field(min_length=1)
    blueprint: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = Field(default=None, min_length=1)
    llm_api_key: str | None = Field(default=None, repr=False)


def _require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv(API_KEY_ENV, "").strip()
    supplied = (x_api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


def _require_read_access(x_api_key: str | None = Header(default=None)) -> None:
    if os.getenv(PUBLIC_READ_ENV, "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    _require_api_key(x_api_key)


def _sanitize_dict(data: Any) -> Any:
    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            if any(
                secret_term in k.lower()
                for secret_term in ("api_key", "apikey", "secret", "password", "token")
            ):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_dict(v)
        return sanitized
    if isinstance(data, list):
        return [_sanitize_dict(item) for item in data]
    return data


def _serialize_state(state: OrchestrationState) -> dict[str, Any]:
    return _sanitize_dict(asdict(state))


def _openai_models_url(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return f"{base}/models"


def _is_trusted_openai_endpoint(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    allowed_hosts = set(_DEFAULT_ALLOWED_OPENAI_HOSTS)
    configured_base = os.getenv("OPENAI_API_BASE", "").strip()
    if configured_base:
        cfg_host = urlparse(configured_base).hostname
        if cfg_host:
            allowed_hosts.add(cfg_host.lower())
    extra_hosts = os.getenv("ALLOWED_OPENAI_HOSTS", "").strip()
    if extra_hosts:
        for h in extra_hosts.split(","):
            if h.strip():
                allowed_hosts.add(h.strip().lower())
    return host in allowed_hosts


async def _fetch_openai_models(endpoint: str, api_key: str) -> list[str]:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("El endpoint OpenAI-compatible debe usar http o https.")
    if not _is_trusted_openai_endpoint(endpoint):
        raise ValueError(
            f"Untrusted model discovery endpoint host '{parsed.hostname}'. "
            "Configure OPENAI_API_BASE or ALLOWED_OPENAI_HOSTS."
        )

    url = _openai_models_url(endpoint)
    tls_verify = os.getenv("OPENAI_TLS_VERIFY", "true").strip().lower() not in {"0", "false", "no"}

    async with httpx.AsyncClient(timeout=20.0, verify=tls_verify) as client:
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []

    models: list[str] = []
    for item in data:
        if isinstance(item, dict):
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                models.append(model_id.strip())

    return sorted(set(models))


def create_app(
    graph: Any = None,
    repository: Any = None,
    spec_agent: Any = None,
) -> FastAPI:
    application = FastAPI(title="AgentIA Orchestrator", version="v1")
    application.state.graph = graph or create_orchestrator_graph()
    application.state.repository = repository or ExecutionRunRepository(
        os.getenv(DATABASE_PATH_ENV, "runs.db")
    )
    application.state.spec_agent = spec_agent or SpecDraftingAgent()
    application.state.solution_pipeline = SolutionGenerationPipeline()
    application.state.runs = {}
    application.state.tasks = set()

    @application.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "orchestrator"}

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _state_store() -> WorkflowStore:
        return WorkflowStore(os.getenv("WORKFLOW_STATE_DIR", ".agentia-state"))

    async def _persist_run_status(
        trace_id: str,
        blueprint_name: str,
        status_val: str,
        repair_attempts: int = 0,
    ) -> None:
        repo = getattr(application.state, "repository", None)
        if repo is None:
            return
        try:
            existing = await repo.get_run(trace_id)
            if existing is None:
                await repo.create_run(
                    trace_id,
                    blueprint_name,
                    status=status_val,
                    repair_attempts=repair_attempts,
                )
            else:
                await repo.update_run(
                    trace_id,
                    status=status_val,
                    repair_attempts=repair_attempts,
                )
        except Exception:  # noqa: BLE001
            pass

    async def draft_spec(request: SpecDraftRequest) -> dict[str, Any]:
        try:
            response = await application.state.spec_agent.draft(request)
        except SpecDraftingError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        return response.model_dump()

    application.post(
        "/v1/spec/draft",
        dependencies=[Depends(_require_read_access)],
        name="draft_spec",
    )(draft_spec)

    async def generate_solution(request: SolutionGenerationRequest) -> dict[str, Any]:
        trace_id = request.trace_id or str(uuid4())
        sol_name = request.solution.name or "solution"
        await _persist_run_status(trace_id, sol_name, "RUNNING", 0)
        try:
            req_with_trace = (
                request.model_copy(update={"trace_id": trace_id})
                if hasattr(request, "model_copy")
                else SolutionGenerationRequest(
                    solution=request.solution,
                    trace_id=trace_id,
                    llm=request.llm,
                )
            )
            result = await asyncio.to_thread(application.state.solution_pipeline, req_with_trace)
        except Exception as exc:
            await _persist_run_status(trace_id, sol_name, "ERROR", 0)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Solution generation failed (trace_id={trace_id}): {exc}",
                headers={"X-Trace-Id": trace_id},
            ) from exc

        # Verify each generated service when Maven is available and pom.xml is a full Quarkus POM
        verify_enabled = os.getenv("SOLUTION_VERIFY_ENABLED", "1").strip().lower() not in {
            "0",
            "false",
            "no",
        }
        dry_run = os.getenv("VERIFIER_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        has_mvn = shutil.which("mvn") is not None
        verified_count = 0
        failed_count = 0

        if verify_enabled and has_mvn and not dry_run:
            runner = resolve_default_runner()
            cmd = resolve_verifier_command()
            timeout_sec = int(os.getenv("VERIFIER_TIMEOUT_SECONDS", "600"))
            for svc_artifact in result.services:
                ws_dir = Path(svc_artifact.workspace_dir)
                pom_file = ws_dir / "pom.xml"
                if pom_file.is_file() and "<project" in pom_file.read_text(encoding="utf-8", errors="replace"):
                    ver_res = await asyncio.to_thread(
                        runner.run,
                        RunnerRequest(
                            workspace_path=str(ws_dir),
                            command=cmd,
                            timeout_seconds=timeout_sec,
                        ),
                    )
                    svc_artifact.verification = ver_res
                    if ver_res.success:
                        svc_artifact.status = "VERIFIED"
                        verified_count += 1
                    else:
                        svc_artifact.status = "FAILED"
                        failed_count += 1

        if failed_count > 0:
            result.status = "FAILED"
            result.outcome = "NO_FIX"
            final_db_status = "NO_FIX"
        elif verified_count > 0 and verified_count == len(result.services):
            result.status = "SUCCESS"
            result.outcome = "SUCCESS"
            final_db_status = "SUCCESS"
        else:
            result.status = "GENERATED"
            result.outcome = "GENERATED"
            final_db_status = "GENERATED"

        await _persist_run_status(trace_id, sol_name, final_db_status, 0)
        serialized = _sanitize_dict(result.model_dump())
        try:
            _state_store().save_state(trace_id, serialized)
        except Exception:  # noqa: BLE001
            pass
        application.state.runs[trace_id] = {
            "trace_id": trace_id,
            "blueprint_name": sol_name,
            "status": final_db_status,
            "repair_attempts": 0,
            "outcome": result.outcome,
            "state": serialized,
        }
        return serialized

    application.post(
        "/v1/solution/run",
        dependencies=[Depends(_require_api_key)],
        name="solution_run",
    )(generate_solution)

    async def list_llm_models(
        provider: str = Query(..., min_length=1),
        endpoint: str | None = Query(default=None),
    ) -> dict[str, Any]:
        provider_value = provider.strip().lower()

        if provider_value != "openai":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only provider=openai is currently supported for model discovery",
            )

        resolved_endpoint = (
            endpoint or os.getenv("OPENAI_API_BASE") or "https://genailab.tcs.in/v1"
        )
        if not _is_trusted_openai_endpoint(resolved_endpoint):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Untrusted model discovery endpoint host",
            )

        api_key = os.getenv("OPENAI_API_KEY", "").strip()

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OPENAI_API_KEY no fue configurada en el backend para listar modelos",
            )

        try:
            models = await _fetch_openai_models(resolved_endpoint, api_key)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"No se pudieron consultar los modelos OpenAI-compatible: {exc}",
            ) from exc

        return {
            "provider": "openai",
            "endpoint": resolved_endpoint,
            "models": models,
            "count": len(models),
        }

    application.get(
        "/v1/llm/models",
        dependencies=[Depends(_require_read_access)],
        name="list_llm_models",
    )(list_llm_models)

    async def verify_llm_endpoint(request: LLMVerifyRequest) -> dict[str, Any]:
        start_time = time.perf_counter()
        provider = request.provider
        model = request.model or "qwen2.5-coder:3b"
        endpoint = request.endpoint

        if provider == "mock":
            return {
                "ok": True,
                "provider": "mock",
                "model": model,
                "latency_ms": 5,
                "message": "Motor offline listo (modo simulado)",
                "error": None,
            }

        if provider == "local":
            if not endpoint or not endpoint.strip():
                endpoint = (
                    os.getenv("LOCAL_LLM_ENDPOINT")
                    or os.getenv("OLLAMA_BASE_URL")
                    or "http://127.0.0.1:8080"
                )
            try:
                parsed = urlparse(endpoint)
                if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
                    "localhost",
                    "127.0.0.1",
                    "::1",
                }:
                    return {
                        "ok": False,
                        "provider": "local",
                        "model": model,
                        "latency_ms": None,
                        "message": "Endpoint inválido",
                        "error": "El endpoint del LLM local debe apuntar a localhost/loopback.",
                    }
                local_client = LocalOpenAICompatibleClient(
                    endpoint=endpoint,
                    model_name=model,
                    api_key=request.api_key,
                )
                await local_client.generate("Respond with OK only.")
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return {
                    "ok": True,
                    "provider": "local",
                    "model": model,
                    "latency_ms": duration_ms,
                    "message": f"Conexión exitosa con Ollama ({model}) en {endpoint} ({duration_ms}ms)",
                    "error": None,
                }
            except Exception as exc:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return {
                    "ok": False,
                    "provider": "local",
                    "model": model,
                    "latency_ms": duration_ms,
                    "message": "Fallo de conexión con Ollama",
                    "error": f"No se pudo conectar a Ollama en {endpoint}: {exc}",
                }

        if provider == "gemini":
            api_key = request.api_key or os.getenv("GEMINI_API_KEY")
            if not api_key:
                return {
                    "ok": False,
                    "provider": "gemini",
                    "model": model,
                    "latency_ms": None,
                    "message": "Falta API Key de Gemini",
                    "error": "GEMINI_API_KEY no fue provista ni configurada en el entorno.",
                }
            try:
                gemini_client = GeminiLLMClient(api_key=api_key, model_name=model)
                await gemini_client.generate("Respond with OK only.")
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return {
                    "ok": True,
                    "provider": "gemini",
                    "model": model,
                    "latency_ms": duration_ms,
                    "message": f"Conexión exitosa con Gemini ({model}) ({duration_ms}ms)",
                    "error": None,
                }
            except Exception as exc:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return {
                    "ok": False,
                    "provider": "gemini",
                    "model": model,
                    "latency_ms": duration_ms,
                    "message": "Fallo de conexión con Gemini",
                    "error": str(exc),
                }

        if provider == "openai":
            endpoint = endpoint or os.getenv("OPENAI_API_BASE") or "https://genailab.tcs.in/v1"
            api_key = request.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return {
                    "ok": False,
                    "provider": "openai",
                    "model": model,
                    "latency_ms": None,
                    "message": "Falta API Key corporativa",
                    "error": "OPENAI_API_KEY no fue provista ni configurada en el entorno.",
                }
            try:
                parsed = urlparse(endpoint)
                if parsed.scheme not in {"http", "https"}:
                    return {
                        "ok": False,
                        "provider": "openai",
                        "model": model,
                        "latency_ms": None,
                        "message": "Endpoint inválido",
                        "error": "El endpoint OpenAI-compatible debe usar http o https.",
                    }
                openai_client = OpenAICompatibleClient(
                    endpoint=endpoint,
                    model_name=model,
                    api_key=api_key,
                )
                await openai_client.generate("Respond with OK only.")
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return {
                    "ok": True,
                    "provider": "openai",
                    "model": model,
                    "latency_ms": duration_ms,
                    "message": f"Conexión exitosa con OpenAI-compatible ({model}) en {endpoint} ({duration_ms}ms)",
                    "error": None,
                }
            except Exception as exc:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                error_text = str(exc)

                if "Invalid model name passed in model=" in error_text:
                    models_url = f"/v1/llm/models?provider=openai&endpoint={quote(endpoint, safe=':/?=&')}"
                    return {
                        "ok": False,
                        "provider": "openai",
                        "model": model,
                        "latency_ms": duration_ms,
                        "message": "Modelo no disponible para la API key corporativa",
                        "error": (
                            f"El modelo '{model}' no está habilitado para esta API key en {endpoint}. "
                            f"Consulta {models_url} para ver los modelos disponibles para esta key. "
                            f"Detalle: {error_text}"
                        ),
                    }

                return {
                    "ok": False,
                    "provider": "openai",
                    "model": model,
                    "latency_ms": duration_ms,
                    "message": "Fallo de conexión con endpoint OpenAI-compatible",
                    "error": f"No se pudo conectar al endpoint OpenAI-compatible en {endpoint}: {error_text}",
                }

        if request.api_key:
            return {
                "ok": True,
                "provider": provider,
                "model": model,
                "latency_ms": 10,
                "message": f"Credencial configurada para {provider.upper()} ({model})",
                "error": None,
            }
        return {
            "ok": False,
            "provider": provider,
            "model": model,
            "latency_ms": None,
            "message": f"Falta API Key para {provider.upper()}",
            "error": f"Por favor ingrese su API Key para {provider.upper()}.",
        }

    application.post(
        "/v1/llm/verify",
        dependencies=[Depends(_require_read_access)],
        name="verify_llm",
    )(verify_llm_endpoint)

    def _resolve_llm_config(request: BlueprintRequest) -> LLMConfiguration | None:
        llm_metadata = request.blueprint.get("llm") if isinstance(request.blueprint, dict) else None
        if not isinstance(llm_metadata, dict) and not request.llm_api_key:
            return None
        meta = llm_metadata if isinstance(llm_metadata, dict) else {}
        provider_value = str(meta.get("provider") or os.getenv("LLM_PROVIDER") or "gemini").lower()
        if provider_value not in {"gemini", "local", "openai"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported LLM provider: {provider_value}",
            )
        settings = resolve_llm_settings(
            provider=provider_value,
            model=meta.get("model"),
            endpoint=meta.get("endpoint"),
            api_key=request.llm_api_key or meta.get("apiKey") or meta.get("api_key"),
        )
        try:
            return LLMConfiguration(**settings)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    def _record(trace_id: str, name: str, status_val: str, attempts: int, outcome: Any, state: Any, **extra: Any) -> None:
        application.state.runs[trace_id] = {
            "trace_id": trace_id,
            "blueprint_name": name,
            "status": status_val,
            "repair_attempts": attempts,
            "outcome": outcome,
            "state": state,
            **extra,
        }

    async def _execute_run(
        operation: str,
        request: BlueprintRequest,
        trace_id: str,
        bp_name: str,
        workspace_dir: str,
        run_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """Run the graph to completion and record the terminal state; shared by sync and async modes."""

        async def on_progress(stage: str, live: OrchestrationState) -> None:
            _record(
                trace_id, bp_name, "RUNNING", live.attempts, None, _serialize_state(live), stage=stage
            )

        graph = application.state.graph
        sig = inspect.signature(graph.run)
        accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        kwargs = dict(run_kwargs)
        if isinstance(graph, OrchestratorGraph) or "progress" in sig.parameters:
            kwargs["progress"] = on_progress
        if operation == "verify" and (isinstance(graph, OrchestratorGraph) or "max_repair_attempts" in sig.parameters):
            kwargs["max_repair_attempts"] = 0
        for key in list(kwargs):
            if key not in sig.parameters and not accepts_kwargs:
                kwargs.pop(key)

        try:
            state = await graph.run(workspace_dir, request.blueprint, **kwargs)
        except Exception as exc:
            err_record = {
                "trace_id": trace_id,
                "blueprint_name": bp_name,
                "status": "ERROR",
                "repair_attempts": 0,
                "outcome": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            }
            application.state.runs[trace_id] = {**err_record, "state": err_record}
            try:
                _state_store().save_state(trace_id, err_record)
            except Exception:  # noqa: BLE001
                pass
            await _persist_run_status(trace_id, bp_name, "ERROR", 0)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Orchestration failed (trace_id={trace_id}): {type(exc).__name__}: {exc}",
                headers={"X-Trace-Id": trace_id},
            ) from exc

        serialized = _serialize_state(state)
        final_trace_id = serialized.get("trace_id") or trace_id
        if final_trace_id != trace_id:
            application.state.runs.pop(trace_id, None)
            repo = getattr(application.state, "repository", None)
            if repo is not None:
                try:
                    await repo.delete_run(trace_id)
                except Exception:  # noqa: BLE001
                    pass
        raw_outcome = serialized.get("outcome")
        normalized_status = (
            "SUCCESS" if raw_outcome == "SUCCESS" else "NO_FIX" if raw_outcome == "NO_FIX" else "ERROR"
        )
        attempts = int(serialized.get("attempts", 0))
        try:
            _state_store().save_state(final_trace_id, serialized)
        except Exception:  # noqa: BLE001
            pass
        _record(final_trace_id, bp_name, normalized_status, attempts, raw_outcome, serialized, stage="done")
        await _persist_run_status(final_trace_id, bp_name, normalized_status, attempts)
        return serialized

    def _create_blueprint_handler(operation: str):
        async def run_blueprint(
            request: BlueprintRequest,
            mode: Literal["sync", "async"] = Query(default="sync"),
        ) -> Any:
            explicit_trace_id = (
                request.trace_id
                or str(request.blueprint.get("trace_id") or "").strip()
                or None
            )
            tentative_trace_id = explicit_trace_id or str(uuid4())
            is_real_graph = isinstance(application.state.graph, OrchestratorGraph)
            run_kwargs: dict[str, Any] = {}
            if explicit_trace_id or is_real_graph:
                run_kwargs["trace_id"] = tentative_trace_id
            llm_config = _resolve_llm_config(request)
            if llm_config is not None:
                run_kwargs["llm_config"] = llm_config

            bp_name = str(
                (
                    request.blueprint.get("name") or request.blueprint.get("serviceName")
                    if isinstance(request.blueprint, dict)
                    else None
                )
                or "blueprint"
            )
            normalized = normalize_blueprint(request.blueprint)
            val_result = validate_blueprint(normalized)
            if operation == "validate" or (not val_result.valid and is_real_graph):
                # validate never generates code; an invalid blueprint stops every operation here
                val_state = OrchestrationState(
                    workspace_dir=request.workspace_dir,
                    blueprint=normalized,
                    trace_id=tentative_trace_id,
                    validation=val_result,
                    outcome=None if val_result.valid else "ERROR",
                    stage="validate",
                )
                serialized_val = _serialize_state(val_state)
                status_val = "VALID" if val_result.valid else "ERROR"
                _record(tentative_trace_id, bp_name, status_val, 0, serialized_val["outcome"], serialized_val)
                await _persist_run_status(tentative_trace_id, bp_name, status_val, 0)
                return serialized_val

            if is_real_graph or "AGENTIA_WORKSPACE_ROOT" in os.environ:
                workspace_path = resolve_managed_workspace(
                    request.workspace_dir,
                    bp_name,
                    tentative_trace_id,
                )
                workspace_path.mkdir(parents=True, exist_ok=True)
                marker = workspace_path / ".agentia-workspace"
                if marker.is_file():
                    for stale_subdir in ("src", "target"):
                        stale_path = workspace_path / stale_subdir
                        if stale_path.exists():
                            shutil.rmtree(stale_path, ignore_errors=True)
                marker.write_text(tentative_trace_id, encoding="utf-8")
                target_workspace_str = str(workspace_path)
            else:
                target_workspace_str = request.workspace_dir

            # Persist RUNNING status before graph dispatch
            _record(tentative_trace_id, bp_name, "RUNNING", 0, None, None, stage="queued")
            await _persist_run_status(tentative_trace_id, bp_name, "RUNNING", 0)

            if mode == "async":
                # Long runs (Maven + LLM repairs) outlive proxy timeouts: answer now, poll the status route
                async def _background() -> None:
                    try:
                        await _execute_run(
                            operation, request, tentative_trace_id, bp_name, target_workspace_str, run_kwargs
                        )
                    except HTTPException:
                        pass

                task = asyncio.create_task(_background())
                application.state.tasks.add(task)
                task.add_done_callback(application.state.tasks.discard)
                return JSONResponse(
                    status_code=status.HTTP_202_ACCEPTED,
                    content={
                        "trace_id": tentative_trace_id,
                        "status": "RUNNING",
                        "outcome": None,
                        "attempts": 0,
                        "workspace_dir": target_workspace_str,
                        "status_url": f"/v1/blueprint/status/{tentative_trace_id}",
                    },
                )

            return await _execute_run(
                operation, request, tentative_trace_id, bp_name, target_workspace_str, run_kwargs
            )

        return run_blueprint

    for operation in ("validate", "verify", "repair", "run"):
        application.post(
            f"/v1/blueprint/{operation}",
            dependencies=[Depends(_require_api_key)],
            name=f"blueprint_{operation}",
        )(_create_blueprint_handler(operation))

    async def get_run_status(trace_id: str, req: Request) -> dict[str, Any]:
        is_blueprint_status = "/blueprint/" in req.url.path
        record = application.state.runs.get(trace_id)
        if record is not None:
            if not is_blueprint_status:
                return {
                    "trace_id": record["trace_id"],
                    "blueprint_name": record["blueprint_name"],
                    "status": record["status"],
                    "repair_attempts": record["repair_attempts"],
                }
            return dict(record)
        run: Any = None
        if hasattr(application.state, "repository") and application.state.repository:
            try:
                run = await application.state.repository.get_run(trace_id)
            except Exception:  # noqa: BLE001
                run = None
        if run is not None:
            base_dict = asdict(run) if isinstance(run, ExecutionRun) else dict(run)
            if is_blueprint_status and "state" not in base_dict:
                try:
                    disk_state = _state_store().load_state(trace_id)
                    if disk_state:
                        base_dict["state"] = disk_state
                except Exception:  # noqa: BLE001
                    pass
            return base_dict
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    async def list_runs_endpoint() -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        if hasattr(application.state, "repository") and application.state.repository:
            try:
                db_runs = await application.state.repository.list_runs()
                runs = [
                    asdict(r) if isinstance(r, ExecutionRun) else dict(r)
                    for r in db_runs
                ]
            except Exception:  # noqa: BLE001
                runs = []
        if not runs and getattr(application.state, "runs", None):
            runs = list(application.state.runs.values())
        return runs

    application.get(
        "/v1/runs",
        dependencies=[Depends(_require_read_access)],
        name="list_runs",
    )(list_runs_endpoint)

    for status_path in (
        "/v1/runs/{trace_id}",
        "/v1/blueprint/status/{trace_id}",
        "/v1/blueprint/run/{trace_id}",
    ):
        application.get(
            status_path,
            dependencies=[Depends(_require_read_access)],
            name=f"get_run_{status_path.replace('/', '_').strip('_')}",
        )(get_run_status)

    return application


app = create_app()