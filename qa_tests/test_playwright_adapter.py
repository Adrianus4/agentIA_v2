from __future__ import annotations

import json
from pathlib import Path

from qa_agent import (
    EXIT_INCOMPLETE,
    EXIT_SUCCESS,
)
from qa_agent.adapters.playwright import run_playwright_suite
from qa_agent.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_u01_missing_browser_cache_returns_incomplete_4_without_network(
    tmp_path: Path,
) -> None:
    """
    U01 / AC-11 / RF-309:
    Si la caché offline de navegadores Playwright (`browser-cache`) no existe o está vacía,
    `run_playwright_suite` devuelve `INCOMPLETE` (código 4) sin intentar descargas por red.
    """
    empty_browser_cache = tmp_path / "empty-browser-cache"
    empty_browser_cache.mkdir(parents=True, exist_ok=True)

    suite_res, artifacts, _, stdout, _ = run_playwright_suite(
        repo_root=REPO_ROOT,
        trace_id="qa-20261019T060000Z-u01empty",
        browser_cache_dir=empty_browser_cache,
    )
    assert suite_res["status"] == "INCOMPLETE"
    assert suite_res["exit_code"] == EXIT_INCOMPLETE
    assert artifacts == {}
    assert "incompleto" in " ".join(suite_res["reasons"]).lower() or "no se encontró" in " ".join(suite_res["reasons"]).lower()


def test_u04_u05_u06_real_playwright_suite_walkthrough_and_negative_controls(
    tmp_path: Path,
) -> None:
    """
    U04–U07 (AC-14, AC-15, AC-16, AC-17, RF-310, RF-312):
    Ejecución completa de la suite `playwright` con Chromium real contra backend y frontend loopback:
    1. Contexto limpio y rechazo de sesiones demo (AC-14).
    2. Generación real aprobada y descarga de ZIP con pom.xml y fuentes Java (AC-15).
    3. Controles negativos de autenticación 401 y caída de backend visibles (AC-16).
    4. Reportes estructurados JUnit XML y JSON con 1 worker y 0 retries (AC-17).
    """
    out_dir = tmp_path / "qa-pw-pos"
    rc = main(
        [
            "run",
            "--suite",
            "playwright",
            "--output-dir",
            str(out_dir),
        ]
    )
    assert rc == EXIT_SUCCESS

    runs = list(out_dir.glob("qa-*"))
    assert len(runs) == 1
    res = json.loads((runs[0] / "result.json").read_text(encoding="utf-8"))
    assert res["status"] == "PASSED"
    assert res["exit_code"] == EXIT_SUCCESS

    pw_suite = next(s for s in res["suites"] if s["suite_id"] == "playwright")
    assert pw_suite["status"] == "PASSED"
    assert pw_suite["engine"] == "playwright+chromium"
    assert pw_suite["counts"]["collected"] >= 3
    assert pw_suite["counts"]["passed"] >= 3
    assert pw_suite["counts"]["failed"] == 0
    assert pw_suite["counts"]["errors"] == 0

    # Verificar presencia de artefactos normalizados
    pw_dir = runs[0] / "playwright"
    assert (pw_dir / "playwright.log").is_file()
    assert (pw_dir / "playwright.junit.xml").is_file()
    assert (pw_dir / "playwright.report.json").is_file()


def test_r01_marker_only_java_cache_returns_incomplete_without_compiler_double(
    tmp_path: Path,
) -> None:
    """
    R01 / RF-305 / RF-306 / RF-310:
    Si la caché Java contiene únicamente `.prepared.json` sin los artefactos `io/quarkus`,
    la suite `playwright` no debe degradarse a `mode=platform` (compilador doble) sino
    bloquearse y devolver INCOMPLETE (código 4).
    """
    marker_only_cache = tmp_path / "marker-only-java-cache"
    marker_only_cache.mkdir(parents=True, exist_ok=True)
    (marker_only_cache / ".prepared.json").write_text('{"prepared": true}', encoding="utf-8")

    suite_res, artifacts, _, stdout, _ = run_playwright_suite(
        repo_root=REPO_ROOT,
        trace_id="qa-20261019T064113Z-r01marker",
        java_cache_dir=marker_only_cache,
    )
    assert suite_res["status"] == "INCOMPLETE"
    assert suite_res["exit_code"] == EXIT_INCOMPLETE
    assert "platform" in " ".join(suite_res["reasons"]).lower() or "quarkus" in " ".join(suite_res["reasons"]).lower()


def test_r02_playwright_preserves_incomplete_on_skipped_or_zero_cases(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """
    R02 / RF-302 / RF-311 / AC-18:
    Comprueba que el adaptador Playwright preserve el veredicto INCOMPLETE (código 4)
    cuando se recolectan 0 casos o existen casos omitidos (skipped > 0).
    """
    from qa_agent.adapters import playwright as pw_module

    # Simular ejecución donde el XML tiene un aprobado y un omitido
    fake_xml = {
        "status": "INCOMPLETE",
        "exit_code": 4,
        "counts": {"collected": 2, "passed": 1, "failed": 0, "errors": 0, "skipped": 1, "xfail": 0},
        "cases": [],
        "reasons": ["Casos omitidos detectados"],
        "sanitized_xml": "<testsuites/>",
    }
    fake_json = {
        "status": "INCOMPLETE",
        "counts": {"collected": 2, "passed": 1, "failed": 0, "errors": 0, "skipped": 1, "xfail": 0},
        "sanitized_json": "{}",
    }

    class MockHarness:
        def __init__(self, *args, **kwargs):
            self.orchestrator_url = "http://127.0.0.1:8000"
            self.orchestrator_api_key = "secret"
        def start(self, **kwargs): pass
        def stop(self): pass

    class MockProc:
        def start(self): pass
        def stop(self): pass

    monkeypatch.setattr(pw_module, "PlatformServiceHarness", MockHarness)
    monkeypatch.setattr(pw_module, "ManagedDaemonProcess", lambda **kwargs: MockProc())
    monkeypatch.setattr(pw_module, "wait_for_http_health", lambda **kwargs: True)
    monkeypatch.setattr(pw_module, "materialize_directory_copy", lambda *a, **k: (0.01, 10))

    monkeypatch.setattr(pw_module, "validate_and_parse_junit_xml", lambda **kwargs: fake_xml)
    monkeypatch.setattr(pw_module, "validate_and_parse_json_report", lambda **kwargs: fake_json)
    monkeypatch.setattr(
        pw_module,
        "run_bounded_subprocess",
        lambda **kwargs: type("Outcome", (), {
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "duration_seconds": 1.0,
            "timed_out": False,
            "interrupted": False,
            "output_truncated": False,
        })(),
    )

    suite_res, _, _, _, _ = pw_module.run_playwright_suite(
        repo_root=REPO_ROOT,
        trace_id="qa-20261019T070000Z-r02skip",
    )
    assert suite_res["status"] == "INCOMPLETE"
    assert suite_res["exit_code"] == 4


def test_r02_playwright_flags_error_on_xml_json_category_mismatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """
    R02 / F01:
    Comprueba que una discrepancia en cualquier categoría entre XML y JSON
    (ej. XML: 2 pasados, JSON: 1 pasado y 1 omitido) active ERROR (código 3).
    """
    from qa_agent.adapters import playwright as pw_module

    fake_xml = {
        "status": "PASSED",
        "exit_code": 0,
        "counts": {"collected": 2, "passed": 2, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0},
        "cases": [],
        "reasons": [],
        "sanitized_xml": "<testsuites/>",
    }
    fake_json = {
        "status": "PASSED",
        "counts": {"collected": 2, "passed": 1, "failed": 0, "errors": 0, "skipped": 1, "xfail": 0},
        "sanitized_json": "{}",
        "reasons": [],
    }

    class MockHarness:
        def __init__(self, *args, **kwargs):
            self.orchestrator_url = "http://127.0.0.1:8000"
            self.orchestrator_api_key = "secret"
        def start(self, **kwargs): pass
        def stop(self): pass

    class MockProc:
        def start(self): pass
        def stop(self): pass

    monkeypatch.setattr(pw_module, "PlatformServiceHarness", MockHarness)
    monkeypatch.setattr(pw_module, "ManagedDaemonProcess", lambda **kwargs: MockProc())
    monkeypatch.setattr(pw_module, "wait_for_http_health", lambda **kwargs: True)
    monkeypatch.setattr(pw_module, "materialize_directory_copy", lambda *a, **k: (0.01, 10))

    monkeypatch.setattr(pw_module, "validate_and_parse_junit_xml", lambda **kwargs: fake_xml)
    monkeypatch.setattr(pw_module, "validate_and_parse_json_report", lambda **kwargs: fake_json)
    monkeypatch.setattr(
        pw_module,
        "run_bounded_subprocess",
        lambda **kwargs: type("Outcome", (), {
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "duration_seconds": 1.0,
            "timed_out": False,
            "interrupted": False,
            "output_truncated": False,
        })(),
    )

    suite_res, _, _, _, _ = pw_module.run_playwright_suite(
        repo_root=REPO_ROOT,
        trace_id="qa-20261019T070000Z-r02mismatch",
    )
    assert suite_res["status"] == "ERROR"
    assert suite_res["exit_code"] == 3
    assert any("Discrepancia F01" in r for r in suite_res["reasons"])

