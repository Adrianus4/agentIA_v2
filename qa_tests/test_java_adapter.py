from __future__ import annotations

import json
import os
from pathlib import Path

from qa_agent import (
    EXIT_EXECUTION_ERROR,
    EXIT_INCOMPLETE,
    EXIT_PRODUCT_FAIL,
    EXIT_SUCCESS,
)
from qa_agent.adapters.java import run_java_suite
from qa_agent.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_j01_missing_java_cache_returns_incomplete_4_without_network(
    tmp_path: Path,
) -> None:
    """
    J01 / AC-11:
    Si la caché offline de Quarkus (`java-cache`) no está preparada o está vacía,
    `run_java_suite` devuelve `INCOMPLETE` (código 4) sin intentar descargas de red.
    """
    empty_cache = tmp_path / "empty-m2-cache"
    empty_cache.mkdir(parents=True, exist_ok=True)

    suite_res, artifacts, _, stdout, _ = run_java_suite(
        repo_root=REPO_ROOT,
        trace_id="qa-20261019T050000Z-j01empty",
        java_cache_dir=empty_cache,
    )
    assert suite_res["status"] == "INCOMPLETE"
    assert suite_res["exit_code"] == EXIT_INCOMPLETE
    assert artifacts == {}
    assert "incompleto" in " ".join(suite_res["reasons"]).lower()
    assert "caché offline quarkus" in stdout.lower()


def test_j05_verifier_dry_run_is_rejected_as_execution_error_3(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """
    J05 / RF-306 / RF-308:
    `VERIFIER_DRY_RUN=1` es rechazado explícitamente por la suite `java` con `ERROR` (código 3).
    """
    monkeypatch.setenv("VERIFIER_DRY_RUN", "1")
    suite_res, _, _, _, stderr = run_java_suite(
        repo_root=REPO_ROOT,
        trace_id="qa-20261019T050000Z-j05dry",
        java_cache_dir=tmp_path / "unused-cache",
    )
    assert suite_res["status"] == "ERROR"
    assert suite_res["exit_code"] == EXIT_EXECUTION_ERROR
    assert "VERIFIER_DRY_RUN" in stderr


def test_j03_j04_j06_real_java_suite_positive_and_negative_controls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """
    J03, J04, J06 (AC-09, AC-10, AC-12, RF-306, RF-307, RF-308):
    1. Ejecución positiva sobre `crud-h2`, `catalog-h2` y `solution-h2` con Maven offline (`-o -B`)
       y H2 en memoria (sin Docker ni red externa):
       - Devuelve código 0 (`PASSED`).
       - Recoge reportes Surefire del verificador y de los oráculos independientes `@QuarkusTest`.
       - Verifica que `/v1/solution/run` alcance estado `SUCCESS` y cada microservicio quede en `VERIFIED`
         (distinto de `GENERATED`).
    2. Controles negativos (`crud-h2-negative-compile` y `crud-h2-negative-assertion`):
       - Devuelven código 1 (`FAILED`, fallo de producto, no código 3 de infraestructura).
       - Registran el caso fallido de compilación y el caso fallido de aserción Surefire en `result.json`.
    """
    out_pos = tmp_path / "qa-java-pos"
    monkeypatch.setenv("QA_JAVA_FIXTURES", "crud-h2,catalog-h2,solution-h2")
    rc_pos = main(
        [
            "run",
            "--suite",
            "java",
            "--output-dir",
            str(out_pos),
        ]
    )
    assert rc_pos == EXIT_SUCCESS

    pos_runs = list(out_pos.glob("qa-*"))
    assert len(pos_runs) == 1
    pos_res = json.loads((pos_runs[0] / "result.json").read_text(encoding="utf-8"))
    assert pos_res["status"] == "PASSED"
    assert pos_res["exit_code"] == EXIT_SUCCESS

    java_suite = next(s for s in pos_res["suites"] if s["suite_id"] == "java")
    assert java_suite["status"] == "PASSED"
    assert java_suite["engine"] == "maven+surefire"
    assert java_suite["counts"]["collected"] >= 16
    assert java_suite["counts"]["failed"] == 0
    assert java_suite["counts"]["errors"] == 0

    sol_summary_path = pos_runs[0] / "java" / "solution-h2" / "solution_result_summary.json"
    assert sol_summary_path.is_file()
    sol_summary = json.loads(sol_summary_path.read_text(encoding="utf-8"))
    assert sol_summary["status"] == "SUCCESS"
    for svc in sol_summary["services"]:
        assert svc["status"] == "VERIFIED"

    crud_manifest_path = pos_runs[0] / "java" / "crud-h2" / "generated_manifest.json"
    assert crud_manifest_path.is_file()
    crud_manifest = json.loads(crud_manifest_path.read_text(encoding="utf-8"))
    assert crud_manifest["api_outcome"] == "SUCCESS"
    assert crud_manifest["verification_success"] is True
    assert len(crud_manifest["files"]) >= 5

    # Ejecutar controles negativos (compilación rota y aserción rota)
    out_neg = tmp_path / "qa-java-neg"
    monkeypatch.setenv("QA_JAVA_FIXTURES", "crud-h2-negative-compile,crud-h2-negative-assertion")
    rc_neg = main(
        [
            "run",
            "--suite",
            "java",
            "--output-dir",
            str(out_neg),
        ]
    )
    assert rc_neg == EXIT_PRODUCT_FAIL

    neg_runs = list(out_neg.glob("qa-*"))
    assert len(neg_runs) == 1
    neg_res = json.loads((neg_runs[0] / "result.json").read_text(encoding="utf-8"))
    assert neg_res["status"] == "FAILED"
    assert neg_res["exit_code"] == EXIT_PRODUCT_FAIL

    neg_suite = next(s for s in neg_res["suites"] if s["suite_id"] == "java")
    assert neg_suite["status"] == "FAILED"
    assert neg_suite["counts"]["failed"] >= 2
    case_names = [c["name"] for c in neg_suite["cases"] if c["status"] == "FAILED"]
    assert "maven_compilation" in case_names


def test_r05_partial_java_cache_returns_incomplete_4_not_error_3(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """
    R05 / RF-313 / AC-11:
    Cuando la caché Maven offline existe (contiene io/quarkus) pero está incompleta
    y Maven falla en modo offline al faltar artefactos/plugins, el adaptador java
    debe devolver INCOMPLETE (código 4), NO ERROR (código 3).
    """
    from qa_agent.adapters import java as java_module

    # Crear una carpeta con io/quarkus para superar la verificación inicial de elegibilidad
    partial_cache = tmp_path / "partial-quarkus-cache"
    (partial_cache / "io" / "quarkus").mkdir(parents=True, exist_ok=True)

    # Simular que Maven falla en offline indicando que falta un artefacto
    monkeypatch.setattr(
        java_module,
        "run_bounded_subprocess",
        lambda **kwargs: type("Outcome", (), {
            "stdout": "[ERROR] Cannot access central in offline mode\n[ERROR] Missing: io.quarkus:quarkus-core:jar:3.15.0",
            "stderr": "The following artifacts could not be resolved",
            "exit_code": 1,
            "duration_seconds": 1.2,
            "timed_out": False,
            "interrupted": False,
            "output_truncated": False,
        })(),
    )

    suite_res, _, _, _, _ = java_module.run_java_suite(
        repo_root=REPO_ROOT,
        trace_id="qa-20261019T064300Z-r05partial",
        java_cache_dir=partial_cache,
    )
    assert suite_res["status"] == "INCOMPLETE"
    assert suite_res["exit_code"] == 4
    assert any("incompleta" in r.lower() for r in suite_res["reasons"])


def test_r08_long_windows_paths_persistence(
    tmp_path: Path,
) -> None:
    """
    R08 / RF-312 / RF-315 / AC-17:
    Comprueba que la persistencia de evidencia maneje nombres de ruta largos (> 260 caracteres en Windows)
    mediante to_extended_path y safe_write_text sin generar FileNotFoundError ni OSError.
    """
    from qa_agent.evidence import persist_run_evidence, to_extended_path

    # Crear una jerarquía de carpetas profunda que supere 260 caracteres
    deep_base = tmp_path / ("a" * 80) / ("b" * 80)
    deep_evidence = deep_base / "evidence-run-trace"
    long_surefire_name = "TEST-com.agentia.qa.orders.repository.OrderRecordRepositoryLongNameAcceptanceTest.xml"

    # Verificar que to_extended_path agrega \\?\ en Windows para rutas absolutas
    ext_path = to_extended_path(deep_evidence / long_surefire_name)
    if os.name == "nt":
        assert str(ext_path).startswith("\\\\?\\")

    # Persistir evidencia con un artefacto de ruta muy larga
    fake_run = {
        "schema_version": "1.0",
        "trace_id": "qa-r08-trace",
        "repo_root": str(REPO_ROOT),
        "status": "PASSED",
        "exit_code": 0,
        "selected_suites": ["java"],
        "scope_note": "Fronteras: java=real",
        "start_utc": "2026-10-19T06:43:00Z",
        "end_utc": "2026-10-19T06:43:05Z",
        "duration_seconds": 5.0,
        "suites": [
            {
                "suite_id": "java",
                "implemented": True,
                "status": "PASSED",
                "exit_code": 0,
                "duration_seconds": 5.0,
                "counts": {"passed": 1, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0, "collected": 1},
                "cases": [],
                "steps": [],
                "reasons": [],
                "evidence_files": {},
            }
        ],
        "evidence_files": {},
    }
    suite_artifacts = {
        "java": {
            f"solution-h2/order-service/verifier/{long_surefire_name}": "<testsuite name='ok'/>",
        }
    }

    persist_run_evidence(
        evidence_dir=deep_evidence,
        run_result=fake_run,
        sanitized_xml=None,
        bounded_log="log content",
        suite_artifacts=suite_artifacts,
    )

    written_file = deep_evidence / "java" / "solution-h2" / "order-service" / "verifier" / long_surefire_name
    assert to_extended_path(written_file).is_file()
    assert (to_extended_path(deep_evidence / "result.json")).is_file()

