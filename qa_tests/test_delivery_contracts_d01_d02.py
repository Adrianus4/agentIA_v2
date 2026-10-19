"""Pruebas de contratos de entrega, reporte, análisis IA y política de códigos de salida (D01, D02)."""

from __future__ import annotations

import json
import pytest
from pydantic import ValidationError

from contracts.models import (
    QAArtifact,
    QAReportManifest,
    QAHypothesis,
    QAAnalysisConfig,
    QAAnalysisResult,
    QALLMTestConfig,
    QAProviderRequest,
    QAProviderResponse,
    QADeliveryResult,
    QAConfigModel,
    compute_delivery_exit_code,
)


def test_d01_qa_artifact_contract():
    """Valida el contrato de QAArtifact: rutas relativas seguras, SHA-256 de 64 caracteres, y rechazo de traversal."""
    artifact = QAArtifact(
        id="report_html",
        path="report/report.html",
        type="html",
        size_bytes=1024,
        sha256="a" * 64,
        provenance="qa_agent.reporting",
    )
    assert artifact.id == "report_html"
    assert artifact.path == "report/report.html"
    assert artifact.size_bytes == 1024
    assert artifact.sha256 == "a" * 64

    # Rechazo de path traversal o rutas absolutas
    for bad_path in ("../report.html", "/etc/passwd", "C:\\abs\\report.html", "sub/../../evil.txt"):
        with pytest.raises(ValidationError):
            QAArtifact(
                id="bad",
                path=bad_path,
                type="html",
                size_bytes=10,
                sha256="a" * 64,
            )

    # Rechazo de hash inválido
    with pytest.raises(ValidationError):
        QAArtifact(
            id="bad_hash",
            path="report/report.html",
            type="html",
            size_bytes=10,
            sha256="not-a-valid-sha256",
        )

    # Rechazo de tamaño negativo
    with pytest.raises(ValidationError):
        QAArtifact(
            id="neg_size",
            path="report/report.html",
            type="html",
            size_bytes=-1,
            sha256="a" * 64,
        )


def test_d01_qa_report_manifest_contract():
    """Valida el contrato de QAReportManifest: identidad de run, SHA del resultado y lista de artefactos."""
    manifest = QAReportManifest(
        schema_version="1.0",
        generated_utc="2026-10-19T03:00:00Z",
        test_run_trace="qa-trace-12345",
        test_result_sha256="b" * 64,
        status="SUCCESS",
        artifacts=[
            QAArtifact(
                id="result_json",
                path="result.json",
                type="json",
                size_bytes=2048,
                sha256="b" * 64,
                provenance="qa_agent.run",
            ),
            QAArtifact(
                id="report_html",
                path="report/report.html",
                type="html",
                size_bytes=8192,
                sha256="c" * 64,
                provenance="qa_agent.report",
            ),
        ],
        warnings=["Test suite python took longer than expected"],
    )
    raw = json.loads(manifest.model_dump_json())
    restored = QAReportManifest.model_validate(raw)
    assert restored.test_run_trace == "qa-trace-12345"
    assert len(restored.artifacts) == 2
    assert restored.status == "SUCCESS"

    # Rechazo de estado inválido
    with pytest.raises(ValidationError):
        QAReportManifest(
            test_run_trace="trace",
            test_result_sha256="b" * 64,
            status="INVALID_STATUS",  # type: ignore[arg-type]
        )


def test_d01_qa_analysis_config_and_secret_rejection():
    """Valida QAAnalysisConfig y garantiza que claves o credenciales no puedan serializarse ni configurarse."""
    default_cfg = QAAnalysisConfig()
    assert default_cfg.provider == "gemini"
    assert default_cfg.model == "gemini-2.5-flash"
    assert default_cfg.mode == "disabled"
    assert default_cfg.max_evidence_chars == 32000
    assert default_cfg.max_tokens == 1500
    assert default_cfg.timeout_seconds == 60.0
    assert default_cfg.deadline_seconds == 120.0
    assert default_cfg.max_requests == 3

    # Rechazo de proveedores no soportados
    with pytest.raises(ValidationError):
        QAAnalysisConfig(provider="anthropic_unsupported")  # type: ignore[arg-type]

    # Rechazo de claves o patrones de secretos en strings de configuración
    for bad_string in (
        "sk-proj-1234567890abcdefghijklmnop",
        "AIzaSyD-abc1234567890",
        "api_key=secret123",
        "Bearer super-secret-token",
    ):
        with pytest.raises(ValidationError):
            QAAnalysisConfig(model=bad_string)


def test_d01_qa_analysis_result_contract():
    """Valida QAAnalysisResult y sus hipótesis asociadas con referencias verificables."""
    hypothesis = QAHypothesis(
        cause="Database connection timeout in repository integration test",
        likelihood="likely",
        referenced_evidence=["tests/test_repo.py", "python/junit.xml#test_db_timeout"],
        suggested_action="Verify connection pool configuration in application.properties",
    )
    assert hypothesis.likelihood == "likely"
    assert len(hypothesis.referenced_evidence) == 2

    res = QAAnalysisResult(
        schema_version="1.0",
        trace_id="qa-trace-9999",
        provider="gemini",
        model="gemini-2.5-flash",
        status="SUCCESS",
        hypotheses=[hypothesis],
        referenced_items=["python/junit.xml", "result.json"],
        prompt_tokens=450,
        completion_tokens=120,
        total_tokens=570,
        cost_estimate_usd=0.00015,
        duration_seconds=2.45,
    )
    dumped = json.loads(res.model_dump_json())
    restored = QAAnalysisResult.model_validate(dumped)
    assert restored.trace_id == "qa-trace-9999"
    assert len(restored.hypotheses) == 1
    assert restored.hypotheses[0].likelihood == "likely"
    assert restored.total_tokens == 570


def test_d01_qa_llm_test_config_contract():
    """Valida QALLMTestConfig para pruebas funcionales con LLM."""
    cfg = QALLMTestConfig(
        mode="simulated",
        provider="openai",
        model="gpt-4o-mini",
        verify_generated_java=True,
        max_requests=5,
        timeout_seconds=45.0,
    )
    assert cfg.mode == "simulated"
    assert cfg.provider == "openai"
    assert cfg.verify_generated_java is True

    # Rechazo de secretos
    with pytest.raises(ValidationError):
        QALLMTestConfig(model="sk-test-token-value-here")


def test_d01_qa_provider_wire_contract():
    """Valida QAProviderRequest y QAProviderResponse asegurando transporte tipado y aislamiento de secretos."""
    req = QAProviderRequest(
        provider="gemini",
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "Analiza la falla del test X"}],
        temperature=0.0,
        max_tokens=1000,
        system_instruction="Eres un auditor de pruebas determinista.",
    )
    assert req.provider == "gemini"
    assert req.temperature == 0.0

    # Rechazo de secretos en contenido de mensaje
    with pytest.raises(ValidationError):
        QAProviderRequest(
            provider="gemini",
            model="gemini-2.5-flash",
            messages=[{"role": "user", "content": "Here is the key sk-1234567890abcdef"}],
        )

    resp = QAProviderResponse(
        provider="gemini",
        model="gemini-2.5-flash",
        content='{"hypotheses": []}',
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120,
        duration_seconds=1.2,
        raw_finish_reason="STOP",
    )
    assert resp.content == '{"hypotheses": []}'
    assert resp.total_tokens == 120


def test_d01_qa_delivery_result_contract():
    """Valida QADeliveryResult relacionando el resultado base de pruebas, informe y análisis."""
    delivery = QADeliveryResult(
        schema_version="1.0",
        trace_id="qa-trace-5555",
        test_status="PASSED",
        test_exit_code=0,
        analysis_status="SUCCESS",
        report_status="SUCCESS",
        delivery_status="SUCCESS",
        delivery_exit_code=0,
        test_result_path="result.json",
        report_html_path="report/report.html",
        report_manifest_path="report/report_manifest.json",
        analysis_path="analysis/analysis.json",
        warnings=[],
    )
    dumped = json.loads(delivery.model_dump_json())
    restored = QADeliveryResult.model_validate(dumped)
    assert restored.delivery_exit_code == 0
    assert restored.test_status == "PASSED"
    assert restored.report_html_path == "report/report.html"


def test_d01_compute_delivery_exit_code_matrix():
    """Verifica exhaustivamente la política de códigos de salida según la tabla del plan (AC-02, AC-08, AC-31)."""
    # 1. Tests aprobados, HTML entregado, IA desactivada o completada -> 0
    assert compute_delivery_exit_code(test_exit_code=0, report_status="SUCCESS", analysis_status="DISABLED") == 0
    assert compute_delivery_exit_code(test_exit_code=0, report_status="SUCCESS", analysis_status="NOT_REQUESTED") == 0
    assert compute_delivery_exit_code(test_exit_code=0, report_status="SUCCESS", analysis_status="SUCCESS") == 0

    # 2. Tests fallidos, informe generado, con o sin análisis -> 1 (fallo de tests visible)
    assert compute_delivery_exit_code(test_exit_code=1, report_status="SUCCESS", analysis_status="DISABLED") == 1
    assert compute_delivery_exit_code(test_exit_code=1, report_status="SUCCESS", analysis_status="SUCCESS") == 1
    assert compute_delivery_exit_code(test_exit_code=1, report_status="SUCCESS", analysis_status="BLOCKED") == 1
    assert compute_delivery_exit_code(test_exit_code=1, report_status="SUCCESS", analysis_status="ERROR") == 1

    # 3. Configuración inválida -> 2
    assert compute_delivery_exit_code(test_exit_code=0, report_status="SUCCESS", analysis_status="SUCCESS", config_valid=False) == 2

    # 4. Error de ejecución / evidencia / HTML -> 3 (conservando prioridad sobre fallo de tests)
    assert compute_delivery_exit_code(test_exit_code=0, report_status="ERROR", analysis_status="SUCCESS") == 3
    assert compute_delivery_exit_code(test_exit_code=1, report_status="ERROR", analysis_status="SUCCESS") == 3
    assert compute_delivery_exit_code(test_exit_code=3, report_status="SUCCESS", analysis_status="SUCCESS") == 3

    # 5. Tests incompletos o análisis solicitado que queda bloqueado/fallido con base aprobada -> 4
    assert compute_delivery_exit_code(test_exit_code=4, report_status="SUCCESS", analysis_status="DISABLED") == 4
    assert compute_delivery_exit_code(test_exit_code=0, report_status="SUCCESS", analysis_status="BLOCKED") == 4
    assert compute_delivery_exit_code(test_exit_code=0, report_status="SUCCESS", analysis_status="ERROR") == 4

    # 6. Interrupción del usuario -> 130
    assert compute_delivery_exit_code(test_exit_code=130, report_status="SUCCESS", analysis_status="SUCCESS") == 130
    assert compute_delivery_exit_code(test_exit_code=0, report_status="SUCCESS", analysis_status="SUCCESS", interrupted=True) == 130


def test_d01_qa_config_model_additive_compatibility():
    """Verifica que QAConfigModel preserve compatibilidad 1.0 con campos aditivos de entrega/análisis."""
    # Configuración histórica sin campos nuevos
    legacy = QAConfigModel(
        schema_version="1.0",
        suites=["python"],
        timeout_seconds=300,
        output_dir=".agentia-runtime/qa",
    )
    assert legacy.analysis is None
    assert legacy.llm_test is None
    assert legacy.report_enabled is True

    # Configuración extendida con campos aditivos
    extended = QAConfigModel(
        schema_version="1.0",
        suites=["python", "java"],
        timeout_seconds=300,
        output_dir=".agentia-runtime/qa",
        analysis=QAAnalysisConfig(provider="gemini", mode="disabled"),
        llm_test=QALLMTestConfig(mode="simulated"),
        report_enabled=True,
    )
    assert extended.analysis is not None
    assert extended.analysis.provider == "gemini"
    assert extended.llm_test is not None
    assert extended.llm_test.mode == "simulated"


def test_d02_atomic_write_text_and_bytes(tmp_path):
    """D02: Escritura atómica sin dejar temporales residuales ante éxito."""
    from qa_agent.reporting.manifest import atomic_write_bytes, atomic_write_text

    target_txt = tmp_path / "sub" / "evidence.txt"
    atomic_write_text(target_txt, "Hello deterministic evidence\n")
    assert target_txt.exists()
    assert target_txt.read_text(encoding="utf-8") == "Hello deterministic evidence\n"

    target_bin = tmp_path / "sub" / "data.bin"
    atomic_write_bytes(target_bin, b"\x00\x01\x02\xfe\xff")
    assert target_bin.exists()
    assert target_bin.read_bytes() == b"\x00\x01\x02\xfe\xff"

    # Verificar que no quedan archivos temporales .tmp en el directorio
    tmp_files = list((tmp_path / "sub").glob("*.tmp*"))
    assert tmp_files == []


def test_d02_generate_report_manifest_and_sha256(tmp_path):
    """D02: Genera un manifiesto exhaustivo con rutas relativas, hashes exactos y SHA del result.json."""
    from qa_agent.reporting.manifest import generate_report_manifest, compute_file_sha256

    run_dir = tmp_path / "qa_trace_123"
    run_dir.mkdir(parents=True)

    result_json_path = run_dir / "result.json"
    dummy_result = {
        "schema_version": "1.0",
        "trace_id": "qa_trace_123",
        "repo_root": str(tmp_path),
        "status": "PASSED",
        "exit_code": 0,
        "selected_suites": ["python"],
        "scope_note": "test",
        "start_utc": "2026-10-19T03:00:00Z",
        "end_utc": "2026-10-19T03:01:00Z",
        "duration_seconds": 60.0,
        "evidence_dir": str(run_dir),
    }
    result_json_path.write_text(json.dumps(dummy_result), encoding="utf-8")
    expected_result_sha = compute_file_sha256(result_json_path)

    # Subdirectorios y artefactos
    python_dir = run_dir / "python"
    python_dir.mkdir()
    (python_dir / "junit.xml").write_text("<testsuite></testsuite>", encoding="utf-8")
    (python_dir / "pytest.log").write_text("pytest log text", encoding="utf-8")

    report_dir = run_dir / "report"
    report_dir.mkdir()
    (report_dir / "report.html").write_text("<html>Report</html>", encoding="utf-8")

    manifest = generate_report_manifest(run_dir, trace_id="qa_trace_123")

    assert manifest.schema_version == "1.0"
    assert manifest.test_run_trace == "qa_trace_123"
    assert manifest.test_result_sha256 == expected_result_sha
    assert manifest.status == "SUCCESS"

    artifact_paths = [a.path for a in manifest.artifacts]
    assert "result.json" in artifact_paths
    assert "python/junit.xml" in artifact_paths
    assert "python/pytest.log" in artifact_paths
    assert "report/report.html" in artifact_paths

    # Verificar que el archivo manifest se escribió en report/report_manifest.json
    manifest_file = run_dir / "report" / "report_manifest.json"
    assert manifest_file.exists()


def test_d02_validate_package_integrity_and_tampering_detection(tmp_path):
    """D02: Detecta alteración de result.json, archivos faltantes y cambios de contenido."""
    from qa_agent.reporting.manifest import generate_report_manifest, validate_package_integrity

    run_dir = tmp_path / "run_integrity"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text('{"status": "PASSED"}', encoding="utf-8")
    p_dir = run_dir / "python"
    p_dir.mkdir()
    (p_dir / "junit.xml").write_text("<xml/>", encoding="utf-8")
    (run_dir / "report").mkdir()
    (run_dir / "report" / "report.html").write_text("<h1>Report</h1>", encoding="utf-8")

    generate_report_manifest(run_dir, trace_id="run_integrity")

    is_valid, errors = validate_package_integrity(run_dir)
    assert is_valid is True
    assert errors == []

    # 1. Modificar result.json (tampering del veredicto determinista)
    (run_dir / "result.json").write_text('{"status": "FAILED"}', encoding="utf-8")
    is_valid, errors = validate_package_integrity(run_dir)
    assert is_valid is False
    assert any("result.json" in err and "hash mismatch" in err.lower() for err in errors)

    # Restaurar
    (run_dir / "result.json").write_text('{"status": "PASSED"}', encoding="utf-8")

    # 2. Borrar un artefacto listado
    (p_dir / "junit.xml").unlink()
    is_valid, errors = validate_package_integrity(run_dir)
    assert is_valid is False
    assert any("python/junit.xml" in err and "missing" in err.lower() for err in errors)


def test_d02_package_is_relocatable(tmp_path):
    """D02: El paquete de evidencias y manifiesto puede moverse de ruta y conservar integridad completa."""
    import shutil
    from qa_agent.reporting.manifest import generate_report_manifest, validate_package_integrity

    orig_dir = tmp_path / "orig_trace"
    orig_dir.mkdir()
    (orig_dir / "result.json").write_text('{"trace": "relocatable"}', encoding="utf-8")
    (orig_dir / "report").mkdir()
    (orig_dir / "report" / "report.html").write_text("<html>Report</html>", encoding="utf-8")

    generate_report_manifest(orig_dir, trace_id="relocatable")

    # Mover a otra ruta
    dest_dir = tmp_path / "moved_trace"
    shutil.move(str(orig_dir), str(dest_dir))

    # Validar en la nueva ruta
    is_valid, errors = validate_package_integrity(dest_dir)
    assert is_valid is True
    assert errors == []


def test_d02_copy_binary_artifact_and_traversal_guard(tmp_path):
    """D02: Copia binaria segura con cálculo de SHA y rechazo de traversal."""
    from qa_agent.reporting.manifest import copy_artifact_binary

    source = tmp_path / "sample.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    target_dir = tmp_path / "artifacts"
    artifact = copy_artifact_binary(
        source_path=source,
        target_dir=target_dir,
        relative_name="assets/screenshot.png",
        artifact_id="screenshot_1",
        provenance="playwright_e2e",
    )
    assert artifact.id == "screenshot_1"
    assert artifact.path == "assets/screenshot.png"
    assert artifact.type == "png"
    assert artifact.size_bytes == len(source.read_bytes())
    assert (target_dir / "assets" / "screenshot.png").exists()

    # Rechazo de traversal
    with pytest.raises(ValueError):
        copy_artifact_binary(
            source_path=source,
            target_dir=target_dir,
            relative_name="../outside.png",
            artifact_id="evil",
        )

