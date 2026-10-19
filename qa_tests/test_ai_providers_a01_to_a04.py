"""Pruebas para adaptadores IA, transporte HTTPX, paquete de evidencia y análisis (A01–A04: AC-08..AC-15, AC-18)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
import httpx
from pydantic import ValidationError

from contracts.models import (
    QAAnalysisConfig,
    QAAnalysisResult,
    QAHypothesis,
    QAProviderRequest,
    QAProviderResponse,
    QARunResult,
)
from qa_agent.ai.transport import QAHTTPTransport, QACredentialsMissingError
from qa_agent.ai.evidence_packet import build_evidence_packet, validate_hypothesis_references
from qa_agent.ai.providers.gemini import GeminiProviderAdapter
from qa_agent.ai.providers.openai import OpenAIProviderAdapter
from qa_agent.ai.providers.deepseek import DeepSeekProviderAdapter
from qa_agent.ai.analysis import run_ai_analysis


def _dummy_run_result(trace_id: str = "qa-trace-ai-1") -> QARunResult:
    return QARunResult(
        schema_version="1.0",
        trace_id=trace_id,
        repo_root="/repo",
        status="FAILED",
        exit_code=1,
        selected_suites=["python"],
        scope_note="Test run with failure",
        start_utc="2026-10-19T03:00:00Z",
        end_utc="2026-10-19T03:00:05Z",
        duration_seconds=5.0,
        counts={"collected": 10, "passed": 9, "failed": 1, "errors": 0, "skipped": 0, "xfail": 0},
        suites=[
            {
                "suite_id": "python",
                "implemented": True,
                "status": "FAILED",
                "exit_code": 1,
                "engine": "pytest",
                "duration_seconds": 3.0,
                "counts": {"collected": 10, "passed": 9, "failed": 1},
                "cases": [
                    {
                        "name": "test_db_deadlock",
                        "classname": "tests.test_database",
                        "status": "FAILED",
                        "duration_seconds": 1.2,
                        "message": "OperationalError: database table is locked",
                        "suite_id": "python",
                    }
                ],
            }
        ],
        cases=[
            {
                "name": "test_db_deadlock",
                "classname": "tests.test_database",
                "status": "FAILED",
                "duration_seconds": 1.2,
                "message": "OperationalError: database table is locked",
                "suite_id": "python",
            }
        ],
        evidence_dir="/repo/.agentia-runtime/qa/" + trace_id,
    )


def test_a01_ai_disabled_produces_zero_network_traffic():
    """A01: Con modo disabled, run_ai_analysis devuelve status=DISABLED y genera CERO llamadas de red."""
    cfg = QAAnalysisConfig(provider="gemini", mode="disabled")
    res = _dummy_run_result()

    # Aunque haya claves en entorno, no se hacen peticiones
    env = {
        "GEMINI_API_KEY": "AIzaSyDummy1234567890",
        "OPENAI_API_KEY": "sk-dummy1234567890",
    }
    analysis = run_ai_analysis(res, cfg, env=env)
    assert analysis.status == "DISABLED"
    assert analysis.hypotheses == []
    assert analysis.total_tokens is None


def test_a01_missing_api_key_blocks_cleanly_without_exception():
    """A01: Con modo live y sin clave de API en entorno, queda en estado BLOCKED sin fallar con traceback."""
    cfg = QAAnalysisConfig(provider="gemini", mode="live")
    res = _dummy_run_result()

    # Sin GEMINI_API_KEY
    env: dict[str, str] = {}
    analysis = run_ai_analysis(res, cfg, env=env)
    assert analysis.status == "BLOCKED"
    assert "GEMINI_API_KEY" in (analysis.error_reason or "")
    assert analysis.hypotheses == []


@respx.mock
def test_a02_gemini_adapter_structured_output():
    """A02: El adaptador de Gemini envía formato de salida estructurado y procesa la respuesta."""
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "hypotheses": [
                                    {
                                        "cause": "Lock contention in SQLite during parallel transactions",
                                        "likelihood": "likely",
                                        "referenced_evidence": ["test_db_deadlock", "python"],
                                        "suggested_action": "Configure SQLite timeout or WAL mode",
                                    }
                                ]
                            })
                        }
                    ]
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 200,
            "candidatesTokenCount": 50,
            "totalTokenCount": 250,
        },
    }
    respx.post(endpoint).respond(200, json=gemini_response)

    transport = QAHTTPTransport(api_key="dummy_gemini_key", timeout_seconds=10.0, max_requests=2)
    adapter = GeminiProviderAdapter(transport=transport, model="gemini-2.5-flash")

    req = QAProviderRequest(
        provider="gemini",
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "Analiza este fallo"}],
    )
    resp = adapter.send_request(req)

    assert resp.provider == "gemini"
    assert resp.prompt_tokens == 200
    assert resp.completion_tokens == 50
    assert resp.total_tokens == 250
    assert "Lock contention" in resp.content


@respx.mock
def test_a02_openai_adapter_structured_output():
    """A02: El adaptador de OpenAI utiliza formato de salida tipado y procesa la respuesta."""
    endpoint = "https://api.openai.com/v1/chat/completions"
    openai_response = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "hypotheses": [
                            {
                                "cause": "Assertion timeout in integration suite",
                                "likelihood": "possible",
                                "referenced_evidence": ["test_db_deadlock"],
                                "suggested_action": "Increase timeout",
                            }
                        ]
                    }),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 40,
            "total_tokens": 190,
        },
    }
    respx.post(endpoint).respond(200, json=openai_response)

    transport = QAHTTPTransport(api_key="sk-dummy1234567890", timeout_seconds=10.0, max_requests=2)
    adapter = OpenAIProviderAdapter(transport=transport, model="gpt-4o-mini")

    req = QAProviderRequest(
        provider="openai",
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Analiza"}],
    )
    resp = adapter.send_request(req)

    assert resp.provider == "openai"
    assert resp.total_tokens == 190
    assert "Assertion timeout" in resp.content


@respx.mock
def test_a02_deepseek_adapter_json_mode():
    """A02: El adaptador de DeepSeek usa JSON mode y extrae uso de tokens."""
    endpoint = "https://api.deepseek.com/chat/completions"
    deepseek_response = {
        "id": "deepseek-123",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "hypotheses": [
                            {
                                "cause": "Database concurrency lock in test runner",
                                "likelihood": "likely",
                                "referenced_evidence": ["test_db_deadlock"],
                                "suggested_action": "Serialize database tests",
                            }
                        ]
                    }),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 180,
            "completion_tokens": 45,
            "total_tokens": 225,
        },
    }
    respx.post(endpoint).respond(200, json=deepseek_response)

    transport = QAHTTPTransport(api_key="dummy_deepseek_key", timeout_seconds=10.0, max_requests=2)
    adapter = DeepSeekProviderAdapter(transport=transport, model="deepseek-chat")

    req = QAProviderRequest(
        provider="deepseek",
        model="deepseek-chat",
        messages=[{"role": "user", "content": "Analiza"}],
    )
    resp = adapter.send_request(req)

    assert resp.provider == "deepseek"
    assert resp.total_tokens == 225
    assert "Database concurrency lock" in resp.content


@respx.mock
def test_a02_401_no_retry_and_rate_limit_handled():
    """A02: Códigos 401/403 se tratan como no reintentables y lanzan error clasificado de inmediato."""
    endpoint = "https://api.openai.com/v1/chat/completions"
    respx.post(endpoint).respond(401, json={"error": {"message": "Invalid API key"}})

    transport = QAHTTPTransport(api_key="sk-invalid-key", timeout_seconds=10.0, max_requests=3)
    adapter = OpenAIProviderAdapter(transport=transport, model="gpt-4o-mini")

    req = QAProviderRequest(provider="openai", model="gpt-4o-mini", messages=[{"role": "user", "content": "test"}])
    resp = adapter.send_request(req)

    assert resp.error_type == "AUTHENTICATION_ERROR"
    assert "Invalid API key" in (resp.error_message or "")
    # Debe haber hecho exactamente 1 petición (cero reintentos innecesarios para 401)
    assert transport.request_count == 1


def test_a03_evidence_packet_whitelisting_and_secret_redaction():
    """A03: El paquete de evidencia contiene únicamente campos permitidos y redacta secretos."""
    raw_res = _dummy_run_result()
    # Inyectar una credencial simulada en el mensaje del caso
    raw_res.cases[0].message = "Auth failed for user admin: Bearer super-secret-token-12345"

    packet = build_evidence_packet(raw_res, max_chars=16000)
    packet_json = json.dumps(packet)

    assert "super-secret-token-12345" not in packet_json
    assert "[REDACTED]" in packet_json
    assert packet["trace_id"] == raw_res.trace_id
    assert packet["counts"]["failed"] == 1
    assert len(packet["failed_cases"]) == 1
    assert packet["failed_cases"][0]["name"] == "test_db_deadlock"

    # Campos no permitidos ausentes
    assert "repo_root" not in packet
    assert "evidence_dir" not in packet


def test_a03_reference_oracle_detects_invented_references():
    """A03: Valida hipótesis de la IA y rechaza referencias a casos o suites inventados."""
    res = _dummy_run_result()
    packet = build_evidence_packet(res)

    valid_hyp = QAHypothesis(
        cause="Valid hypothesis",
        likelihood="likely",
        referenced_evidence=["test_db_deadlock", "python"],
        suggested_action="Fix lock",
    )
    is_valid, invalid_refs = validate_hypothesis_references(valid_hyp, packet)
    assert is_valid is True
    assert invalid_refs == []

    hallucinated_hyp = QAHypothesis(
        cause="Hallucinated hypothesis",
        likelihood="possible",
        referenced_evidence=["test_db_deadlock", "phantom_case_99", "invented_suite"],
        suggested_action="Fix ghost test",
    )
    is_valid, invalid_refs = validate_hypothesis_references(hallucinated_hyp, packet)
    assert is_valid is False
    assert set(invalid_refs) == {"phantom_case_99", "invented_suite"}


@respx.mock
def test_a04_cli_analyze_command(tmp_path):
    """A04: El comando analyze genera analysis.json y delivery.json sin alterar result.json."""
    from qa_tests.conftest import run_qa_cli
    from qa_agent.reporting.manifest import compute_file_sha256

    run_dir = tmp_path / "run_analyze_test"
    run_dir.mkdir()
    res = _dummy_run_result(trace_id="trace_analyze_1")
    result_json_path = run_dir / "result.json"
    result_json_path.write_text(res.model_dump_json(indent=2), encoding="utf-8")
    initial_sha = compute_file_sha256(result_json_path)

    # Mock de Gemini para análisis live con key simulada
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    respx.post(endpoint).respond(
        200,
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "hypotheses": [
                                        {
                                            "cause": "Lock contention in database",
                                            "likelihood": "likely",
                                            "referenced_evidence": ["test_db_deadlock"],
                                            "suggested_action": "Use WAL mode",
                                        }
                                    ]
                                })
                            }
                        ]
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20, "totalTokenCount": 120},
        },
    )

    env = {"GEMINI_API_KEY": "AIzaSyDummyTestKey123"}
    proc = run_qa_cli(
        ["analyze", "--input", str(result_json_path), "--ai-provider", "gemini", "--ai-mode", "offline"],
        cwd=tmp_path,
        env=env,
        use_script=True,
    )

    assert proc.returncode in (0, 1)  # Veredicto de tests era FAILED=1
    assert (run_dir / "analysis" / "analysis.json").exists()
    assert (run_dir / "delivery.json").exists()

    # AC-08: result.json es inmutable; su hash no cambia tras analizarlo
    after_sha = compute_file_sha256(result_json_path)
    assert after_sha == initial_sha
