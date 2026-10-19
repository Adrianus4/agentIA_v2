"""Pruebas de aceptación para el informe HTML consolidado (R01–R04: AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-31)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from contracts.models import (
    QACaseResult,
    QACounts,
    QARunResult,
    QASourceProvenance,
    QASuiteExecutionResult,
    QASuiteStepResult,
)
from qa_agent.reporting.render import render_html_report
from qa_agent.reporting.manifest import generate_report_manifest, validate_package_integrity


def _create_sample_run_result(
    trace_id: str = "qa-trace-demo",
    status: str = "PASSED",
    exit_code: int = 0,
    with_failures: bool = False,
    xss_payload: str | None = None,
) -> QARunResult:
    case_name = xss_payload or "test_service_health_check"
    failed_case_msg = xss_payload or "AssertionError: expected 200 got 500"

    cases = [
        QACaseResult(
            classname="tests.test_health",
            name=case_name,
            status="PASSED" if not with_failures else "FAILED",
            duration_seconds=0.25,
            message=None if not with_failures else failed_case_msg,
            suite_id="python",
        ),
        QACaseResult(
            classname="tests.test_logic",
            name="test_order_processing",
            status="PASSED",
            duration_seconds=0.85,
            suite_id="python",
        ),
    ]

    steps = [
        QASuiteStepResult(
            step_id="build_step_tsc",
            description="TypeScript compilation",
            kind="build",
            status="PASSED",
            duration_seconds=1.5,
        )
    ]

    suites = [
        QASuiteExecutionResult(
            suite_id="python",
            implemented=True,
            status="PASSED" if not with_failures else "FAILED",
            exit_code=0 if not with_failures else 1,
            engine="pytest",
            duration_seconds=2.5,
            counts=QACounts(
                collected=2,
                passed=2 if not with_failures else 1,
                failed=0 if not with_failures else 1,
            ),
            cases=cases,
            steps=steps,
            provenance=QASourceProvenance(
                git_revision="abc1234",
                tool_versions={"python": "3.12.10", "pytest": "9.1.1"},
            ),
            evidence_files={"junit.xml": "python/junit.xml", "pytest.log": "python/pytest.log"},
        )
    ]

    actual_status = status if status != "PASSED" else ("FAILED" if with_failures else "PASSED")
    actual_exit = exit_code if exit_code != 0 else (1 if with_failures else 0)

    return QARunResult(
        schema_version="1.0",
        trace_id=trace_id,
        repo_root="/repo",
        status=actual_status,  # type: ignore[arg-type]
        exit_code=actual_exit,
        selected_suites=["python"],
        scope_note="Verification test suite",
        start_utc="2026-10-19T03:00:00Z",
        end_utc="2026-10-19T03:00:05Z",
        duration_seconds=5.0,
        suites=suites,
        cases=cases,
        counts=QACounts(
            collected=2,
            passed=2 if not with_failures else 1,
            failed=0 if not with_failures else 1,
        ),
        provenance=QASourceProvenance(
            git_revision="abc1234",
            tool_versions={"python": "3.12.10"},
        ),
        evidence_dir="/repo/.agentia-runtime/qa/" + trace_id,
    )


def test_r01_html_render_contains_all_sections_and_metrics(tmp_path):
    """R01: El informe HTML incluye estado global, totales, suites, casos, pasos, procedencia y enlaces relativos."""
    res = _create_sample_run_result(with_failures=True, status="FAILED", exit_code=1)
    run_dir = tmp_path / "run_html"
    run_dir.mkdir()
    (run_dir / "result.json").write_text(res.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "python").mkdir()
    (run_dir / "python" / "junit.xml").write_text("<xml/>", encoding="utf-8")
    (run_dir / "python" / "pytest.log").write_text("pytest log here", encoding="utf-8")

    manifest = generate_report_manifest(run_dir, trace_id=res.trace_id)
    html_output = run_dir / "report" / "report.html"

    rendered = render_html_report(result=res, manifest=manifest, output_path=html_output)

    assert html_output.exists()
    assert "<!DOCTYPE html>" in rendered
    assert res.trace_id in rendered
    assert "FAILED" in rendered
    assert "test_service_health_check" in rendered
    assert "AssertionError: expected 200 got 500" in rendered
    assert "build_step_tsc" in rendered
    assert "TypeScript compilation" in rendered
    assert "pytest" in rendered
    assert "3.12.10" in rendered

    # R01: Los pasos de build NO deben sumarse como casos de prueba
    # El conteo total de casos debe seguir siendo exactamente 2 (1 passed, 1 failed)
    assert '<div class="metric-number">2</div>' in rendered
    assert "Casos Recolectados" in rendered


def test_r01_no_build_steps_counted_as_test_cases():
    """R01: Los pasos de preparación/build no alteran las métricas deterministas de casos de prueba."""
    res = _create_sample_run_result()
    # Hay 1 paso de build en res.suites[0].steps
    assert len(res.suites[0].steps) == 1
    # Pero el conteo de casos es 2
    assert res.counts.collected == 2
    assert res.counts.passed == 2
    rendered = render_html_report(result=res)
    # Verificar que el número en metric-number es 2
    assert '<div class="metric-number">2</div>' in rendered


def test_r02_reconstruct_report_from_result_json_without_subprocesses(tmp_path):
    """R02: El comando report reconstruye HTML exclusivamente desde result.json y evidencia validada."""
    from qa_tests.conftest import run_qa_cli

    run_dir = tmp_path / "run_cli_report"
    run_dir.mkdir()
    res = _create_sample_run_result(trace_id="trace_cli_rep")
    (run_dir / "result.json").write_text(res.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "python").mkdir()
    (run_dir / "python" / "junit.xml").write_text("<xml/>", encoding="utf-8")

    # Invocar CLI qa report --input <run_dir>/result.json
    proc = run_qa_cli(
        ["report", "--input", str(run_dir / "result.json")],
        cwd=tmp_path,
        use_script=True,
    )
    assert proc.returncode == 0, f"Error invocando qa_agent report: {proc.stderr}"

    report_html = run_dir / "report" / "report.html"
    report_manifest = run_dir / "report" / "report_manifest.json"
    delivery_json = run_dir / "delivery.json"

    assert report_html.exists()
    assert report_manifest.exists()
    assert delivery_json.exists()

    delivery_data = json.loads(delivery_json.read_text(encoding="utf-8"))
    assert delivery_data["test_exit_code"] == 0
    assert delivery_data["delivery_exit_code"] == 0
    assert delivery_data["delivery_status"] == "SUCCESS"


def test_r02_cli_report_preserves_test_failure_exit_code(tmp_path):
    """R02: Reportar sobre un run con pruebas fallidas preserva el código 1 (un último comando no transforma rojo en verde)."""
    from qa_tests.conftest import run_qa_cli

    run_dir = tmp_path / "run_failed_report"
    run_dir.mkdir()
    res = _create_sample_run_result(trace_id="trace_failed_rep", status="FAILED", exit_code=1, with_failures=True)
    (run_dir / "result.json").write_text(res.model_dump_json(indent=2), encoding="utf-8")

    proc = run_qa_cli(
        ["report", "--input", str(run_dir / "result.json")],
        cwd=tmp_path,
        use_script=True,
    )
    # Debe retornar 1 según la política de salida de entrega
    assert proc.returncode == 1

    # Y los archivos deben haberse generado
    assert (run_dir / "report" / "report.html").exists()
    assert (run_dir / "delivery.json").exists()
    delivery_data = json.loads((run_dir / "delivery.json").read_text(encoding="utf-8"))
    assert delivery_data["test_exit_code"] == 1
    assert delivery_data["delivery_exit_code"] == 1
    assert delivery_data["delivery_status"] == "FAILED"


def test_r03_xss_sanitization_and_isolated_links(tmp_path):
    """R03: Inyección de HTML/JS activo en casos o logs es tratada como datos; enlaces peligrosos bloqueados."""
    xss_payload = '<script>alert("XSS")</script><img src=x onerror=alert(1)>'
    res = _create_sample_run_result(with_failures=True, xss_payload=xss_payload)

    rendered = render_html_report(result=res)

    # El script no debe aparecer como etiqueta HTML ejecutable
    assert "<script>alert" not in rendered
    assert "&lt;script&gt;alert" in rendered
    assert "<img src=x" not in rendered
    assert "&lt;img src=x" in rendered

    # Verificación de que no hay enlaces externos ni scripts remotos
    assert not re.search(r'<script\s+src=["\']https?://', rendered, re.IGNORECASE)
    assert not re.search(r'<link\s+[^>]*href=["\']https?://', rendered, re.IGNORECASE)
    assert not re.search(r'href=["\']javascript:', rendered, re.IGNORECASE)
    assert not re.search(r'href=["\']data:', rendered, re.IGNORECASE)


def test_r04_report_package_is_fully_relocatable_and_reopenable(tmp_path):
    """R04: El paquete de reporte se puede mover y abrir en el navegador localmente sin enlaces rotos."""
    run_dir = tmp_path / "original_run"
    run_dir.mkdir()
    res = _create_sample_run_result(trace_id="reloc_run", with_failures=True)
    (run_dir / "result.json").write_text(res.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "python").mkdir()
    (run_dir / "python" / "junit.xml").write_text("<testsuite></testsuite>", encoding="utf-8")
    (run_dir / "python" / "pytest.log").write_text("pytest log data", encoding="utf-8")

    manifest = generate_report_manifest(run_dir, trace_id=res.trace_id)
    report_html = run_dir / "report" / "report.html"
    render_html_report(result=res, manifest=manifest, output_path=report_html)

    # Mover paquete a otra ubicación
    moved_dir = tmp_path / "moved_package"
    shutil.move(str(run_dir), str(moved_dir))

    # Verificar integridad tras mover
    is_valid, errors = validate_package_integrity(moved_dir)
    assert is_valid is True
    assert errors == []

    # Verificar que los enlaces dentro de report.html son relativos locales
    content = (moved_dir / "report" / "report.html").read_text(encoding="utf-8")
    for match in re.finditer(r'href=["\']([^"#\':]+)["\']', content):
        rel_link = match.group(1)
        # El enlace debe resolver a un archivo real relativo a report.html
        target_file = (moved_dir / "report" / rel_link).resolve()
        assert target_file.exists(), f"El enlace relativo '{rel_link}' no existe en {target_file}"
