"""Coordinador de análisis IA y oráculo determinista (A03, A04, AC-08..AC-15, AC-18)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from contracts.models import (
    QAAnalysisConfig,
    QAAnalysisResult,
    QAHypothesis,
    QAProviderRequest,
    QARunResult,
)
from qa_agent.ai.evidence_packet import build_evidence_packet, validate_hypothesis_references
from qa_agent.ai.providers.deepseek import DeepSeekProviderAdapter
from qa_agent.ai.providers.gemini import GeminiProviderAdapter
from qa_agent.ai.providers.openai import OpenAIProviderAdapter
from qa_agent.ai.transport import QAHTTPTransport
from qa_agent.evidence import collect_sensitive_env_values, redact_text
from qa_agent.reporting.manifest import atomic_write_text

PROVIDER_ENV_VARS: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


def _get_provider_adapter(
    provider: str,
    model: str,
    transport: QAHTTPTransport,
):
    if provider == "gemini":
        return GeminiProviderAdapter(transport=transport, model=model)
    if provider == "openai":
        return OpenAIProviderAdapter(transport=transport, model=model)
    if provider == "deepseek":
        return DeepSeekProviderAdapter(transport=transport, model=model)
    raise ValueError(f"Proveedor no soportado: {provider}")


def run_ai_analysis(
    run_result: QARunResult,
    config: QAAnalysisConfig,
    env: dict[str, str] | None = None,
    run_dir: Path | None = None,
) -> QAAnalysisResult:
    """Ejecuta análisis de resultados determinista o live por API según la configuración."""
    t0 = time.perf_counter()
    effective_env = env if env is not None else dict(os.environ)

    # 1. Modo disabled -> Cero tráfico, salida inmediata
    if config.mode == "disabled":
        res = QAAnalysisResult(
            schema_version="1.0",
            trace_id=run_result.trace_id,
            provider=config.provider,
            model=config.model,
            status="DISABLED",
            duration_seconds=round(time.perf_counter() - t0, 4),
        )
        return res

    packet = build_evidence_packet(run_result, max_chars=config.max_evidence_chars)

    # 2. Modo offline (simulado / fixture determinista)
    if config.mode == "offline":
        hypotheses: list[QAHypothesis] = []
        for fc in packet.get("failed_cases", []):
            hypotheses.append(
                QAHypothesis(
                    cause=f"Fallo detectado en caso de prueba: {fc.get('message', 'Sin mensaje')}",
                    likelihood="likely",
                    referenced_evidence=[fc.get("name", ""), fc.get("suite_id", "")],
                    suggested_action="Verificar la implementación o el entorno de la suite.",
                )
            )

        res = QAAnalysisResult(
            schema_version="1.0",
            trace_id=run_result.trace_id,
            provider=config.provider,
            model=config.model,
            status="SUCCESS",
            hypotheses=hypotheses,
            referenced_items=[fc.get("name", "") for fc in packet.get("failed_cases", [])],
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            duration_seconds=round(time.perf_counter() - t0, 4),
        )
        _persist_analysis(run_dir, res)
        return res

    # 3. Modo live -> Validar clave de API del proveedor
    key_var_name = PROVIDER_ENV_VARS.get(config.provider, f"{config.provider.upper()}_API_KEY")
    api_key = effective_env.get(key_var_name, "").strip()

    extra_secrets: list[str] = collect_sensitive_env_values(effective_env)
    if api_key:
        extra_secrets.append(api_key)

    if not api_key:
        res = QAAnalysisResult(
            schema_version="1.0",
            trace_id=run_result.trace_id,
            provider=config.provider,
            model=config.model,
            status="BLOCKED",
            error_reason=f"Credencial ausente en entorno: variable {key_var_name} no configurada.",
            duration_seconds=round(time.perf_counter() - t0, 4),
        )
        _persist_analysis(run_dir, res, extra_secrets=extra_secrets)
        return res

    # 4. Enviar solicitud live mediante transporte y adaptador HTTPX
    transport = QAHTTPTransport(
        api_key=api_key,
        timeout_seconds=config.timeout_seconds,
        deadline_seconds=config.deadline_seconds,
        max_requests=config.max_requests,
    )
    adapter = _get_provider_adapter(config.provider, config.model, transport)

    system_instruction = (
        "Eres un analista determinista de pruebas de software. "
        "Analiza el paquete de evidencia provisto y genera exclusivamente un objeto JSON "
        "con una lista de hipótesis (`hypotheses`). Cada hipótesis debe contener: "
        "`cause` (cadena), `likelihood` ('likely', 'possible' o 'unlikely'), "
        "`referenced_evidence` (lista de nombres de casos o suites existentes en el paquete), "
        "y `suggested_action` (cadena). "
        "No inventes nombres de casos ni suites."
    )
    user_message = (
        f"A continuación se adjunta el paquete de evidencia del run {run_result.trace_id}:\n"
        f"{json.dumps(packet, ensure_ascii=False, indent=2)}"
    )

    req = QAProviderRequest(
        provider=config.provider,
        model=config.model,
        messages=[{"role": "user", "content": user_message}],
        system_instruction=system_instruction,
        max_tokens=config.max_tokens,
    )

    resp = adapter.send_request(req)

    if resp.error_type:
        clean_err = redact_text(resp.error_message or "", extra_secrets=extra_secrets)
        res = QAAnalysisResult(
            schema_version="1.0",
            trace_id=run_result.trace_id,
            provider=config.provider,
            model=config.model,
            status="ERROR",
            error_reason=f"{resp.error_type}: {clean_err}",
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            total_tokens=resp.total_tokens,
            duration_seconds=round(time.perf_counter() - t0, 4),
        )
        _persist_analysis(run_dir, res, extra_secrets=extra_secrets)
        return res

    # Rechazar truncamiento por límite de tokens
    if resp.raw_finish_reason in ("length", "MAX_TOKENS", "max_tokens", "truncated"):
        err_msg = f"Respuesta IA truncada por límite de tokens (finish_reason={resp.raw_finish_reason})"
        res = QAAnalysisResult(
            schema_version="1.0",
            trace_id=run_result.trace_id,
            provider=config.provider,
            model=config.model,
            status="ERROR",
            error_reason=err_msg,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            total_tokens=resp.total_tokens,
            duration_seconds=round(time.perf_counter() - t0, 4),
            warnings=[err_msg],
        )
        _persist_analysis(run_dir, res, extra_secrets=extra_secrets)
        return res

    # 5. Parsear y validar hipótesis mediante el oráculo de referencias
    warnings: list[str] = []
    try:
        raw_parsed = json.loads(resp.content)
    except Exception as exc:
        err_msg = f"Error procesando contenido JSON de respuesta IA: {exc}"
        res = QAAnalysisResult(
            schema_version="1.0",
            trace_id=run_result.trace_id,
            provider=config.provider,
            model=config.model,
            status="ERROR",
            error_reason=err_msg,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            total_tokens=resp.total_tokens,
            duration_seconds=round(time.perf_counter() - t0, 4),
            warnings=[err_msg],
        )
        _persist_analysis(run_dir, res, extra_secrets=extra_secrets)
        return res

    if not isinstance(raw_parsed, dict) or not raw_parsed.get("hypotheses"):
        err_msg = "Respuesta IA no contiene hipótesis de diagnóstico requeridas (esquema incompleto o vacío)."
        res = QAAnalysisResult(
            schema_version="1.0",
            trace_id=run_result.trace_id,
            provider=config.provider,
            model=config.model,
            status="ERROR",
            error_reason=err_msg,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            total_tokens=resp.total_tokens,
            duration_seconds=round(time.perf_counter() - t0, 4),
            warnings=[err_msg],
        )
        _persist_analysis(run_dir, res, extra_secrets=extra_secrets)
        return res

    raw_list = raw_parsed.get("hypotheses", [])
    validated_hypotheses: list[QAHypothesis] = []
    referenced_items: list[str] = []
    has_reference_error = False

    for item in raw_list:
        try:
            hyp = QAHypothesis.model_validate(item)
            hyp.cause = redact_text(hyp.cause, extra_secrets=extra_secrets)
            hyp.suggested_action = redact_text(hyp.suggested_action, extra_secrets=extra_secrets)
            hyp.referenced_evidence = [
                redact_text(r, extra_secrets=extra_secrets) for r in hyp.referenced_evidence
            ]
            is_valid, invalid_refs = validate_hypothesis_references(hyp, packet)
            if not is_valid:
                has_reference_error = True
                warnings.append(
                    f"Hipótesis descartó referencias inventadas por la IA: {invalid_refs}"
                )
                hyp.referenced_evidence = [
                    r for r in hyp.referenced_evidence if r not in invalid_refs
                ]
            if hyp.referenced_evidence:
                validated_hypotheses.append(hyp)
                referenced_items.extend(hyp.referenced_evidence)
        except Exception as exc:
            has_reference_error = True
            warnings.append(f"Error validando hipótesis contra esquema: {exc}")

    if has_reference_error or not validated_hypotheses or not referenced_items:
        err_msg = "Análisis IA rechazado: contiene referencias inventadas o no verificables en la evidencia."
        res = QAAnalysisResult(
            schema_version="1.0",
            trace_id=run_result.trace_id,
            provider=config.provider,
            model=config.model,
            status="ERROR",
            error_reason=err_msg,
            hypotheses=validated_hypotheses if not has_reference_error else [],
            referenced_items=sorted(set(referenced_items)) if not has_reference_error else [],
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            total_tokens=resp.total_tokens,
            duration_seconds=round(time.perf_counter() - t0, 4),
            warnings=warnings,
        )
        _persist_analysis(run_dir, res, extra_secrets=extra_secrets)
        return res

    res = QAAnalysisResult(
        schema_version="1.0",
        trace_id=run_result.trace_id,
        provider=config.provider,
        model=config.model,
        status="SUCCESS",
        hypotheses=validated_hypotheses,
        referenced_items=sorted(set(referenced_items)),
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
        total_tokens=resp.total_tokens,
        duration_seconds=round(time.perf_counter() - t0, 4),
        warnings=warnings,
    )

    _persist_analysis(run_dir, res, extra_secrets=extra_secrets)
    return res


def _persist_analysis(
    run_dir: Path | None,
    res: QAAnalysisResult,
    extra_secrets: list[str] | None = None,
) -> None:
    if run_dir is not None:
        target = Path(run_dir).resolve() / "analysis" / "analysis.json"
        raw_json = res.model_dump_json(indent=2)
        redacted_json = redact_text(raw_json, extra_secrets=extra_secrets)
        atomic_write_text(target, redacted_json)
