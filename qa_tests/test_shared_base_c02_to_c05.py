"""Pruebas de aceptación para la base compartida multimotor (C02–C05: AC-01, AC-02, AC-03, AC-12 parcial, AC-18)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.models import (
    QACaseResult,
    QAConfigModel,
    QADoctorReport,
    QAListReport,
    QARunResult,
    QASourceProvenance,
    QASuiteExecutionResult,
    QASuiteStepResult,
)
from qa_tests.conftest import create_minimal_repo, run_qa_cli


def test_c02_additive_contracts_and_backward_compatibility():
    """C02: QAConfigModel y modelos de resultado aceptan campos aditivos multimotor y mantienen compatibilidad 1.0."""
    legacy = QAConfigModel(schema_version="1.0", suites=["python"], timeout_seconds=300, output_dir=".agentia-runtime/qa")
    assert legacy.suite_timeouts == {}
    assert legacy.java_cache_dir is None
    assert legacy.browser_cache_dir is None

    extended = QAConfigModel(
        schema_version="1.0",
        suites=["python", "platform", "java", "frontend", "playwright"],
        timeout_seconds=300,
        output_dir=".agentia-runtime/qa",
        suite_timeouts={"platform": 180, "java": 1200, "frontend": 300, "playwright": 1500},
        java_cache_dir=".agentia-runtime/java-cache",
        browser_cache_dir=".agentia-runtime/browser-cache",
    )
    assert extended.suite_timeouts["java"] == 1200

    for bad_path in ("../outside", "cache; rm -rf /", "cache && calc.exe", "cache | more"):
        with pytest.raises(ValidationError):
            QAConfigModel(java_cache_dir=bad_path)
        with pytest.raises(ValidationError):
            QAConfigModel(browser_cache_dir=bad_path)

    with pytest.raises(ValidationError):
        QAConfigModel(suite_timeouts={"java": 0})
    with pytest.raises(ValidationError):
        QAConfigModel(suite_timeouts={"java": True})  # type: ignore[dict-item]

    step = QASuiteStepResult(
        step_id="tsc_check",
        description="TypeScript build check",
        status="PASSED",
        exit_code=0,
        duration_seconds=1.2,
    )
    prov = QASourceProvenance(
        git_revision="d7a14ff",
        source_hashes={"pyproject.toml": "abc"},
        fidelity={"http": "real", "llm": "double", "compiler": "double"},
        tool_versions={"python": "3.12.10"},
    )
    case = QACaseResult(
        classname="qa_scenarios.platform.test_auth",
        name="test_valid_api_key",
        status="PASSED",
        duration_seconds=0.15,
        suite_id="platform",
        fixture_id="crud-h2",
        app_trace_id="trace-123",
        engine="pytest+httpx",
    )
    suite_res = QASuiteExecutionResult(
        suite_id="platform",
        implemented=True,
        status="PASSED",
        exit_code=0,
        engine="pytest+httpx",
        process_exit_code=0,
        pytest_exit_code=0,
        steps=[step],
        provenance=prov,
        cases=[case],
    )
    assert suite_res.engine == "pytest+httpx"
    assert suite_res.steps[0].step_id == "tsc_check"
    assert suite_res.cases[0].app_trace_id == "trace-123"


def test_ac01_without_java_node_browser_python_and_platform_remain_eligible_others_incomplete(tmp_path: Path):
    """AC-01: Sin Java, Maven, Node ni navegador, python y platform son elegibles; java/frontend/playwright devuelven INCOMPLETE (4)."""
    repo = create_minimal_repo(tmp_path / "repo_ac01")
    env = os.environ.copy()
    env["PATH"] = ""
    env["QA_FORCE_NO_LOCAL_TOOLCHAINS"] = "1"

    doc_proc = run_qa_cli(["doctor", "--repo", str(repo), "--json"], env=env)
    assert doc_proc.returncode == 0, f"doctor failed: {doc_proc.stdout}\n{doc_proc.stderr}"
    doc_data = QADoctorReport.model_validate(json.loads(doc_proc.stdout))
    assert doc_data.python_suite_eligible is True
    assert doc_data.suite_eligibility.get("python") is True
    assert doc_data.suite_eligibility.get("platform") is True
    assert doc_data.suite_eligibility.get("java") is False
    assert doc_data.suite_eligibility.get("frontend") is False
    assert doc_data.suite_eligibility.get("playwright") is False

    list_proc = run_qa_cli(["list", "--repo", str(repo), "--json"], env=env)
    assert list_proc.returncode == 0
    list_data = QAListReport.model_validate(json.loads(list_proc.stdout))
    by_id = {s.suite_id: s for s in list_data.suites}
    assert set(by_id.keys()) == {"python", "platform", "java", "frontend", "playwright", "llm"}
    assert by_id["python"].implemented is True and by_id["python"].status == "EXECUTABLE"
    assert by_id["platform"].implemented is True and by_id["platform"].status == "EXECUTABLE"
    assert by_id["llm"].implemented is True and by_id["llm"].status == "EXECUTABLE"
    for blocked_id in ("java", "frontend", "playwright"):
        assert by_id[blocked_id].implemented is True
        assert by_id[blocked_id].status == "BLOCKED"
        assert by_id[blocked_id].reason

    for blocked_id in ("java", "frontend", "playwright"):
        run_proc = run_qa_cli(["run", "--repo", str(repo), "--suite", blocked_id, "--json"], env=env)
        assert run_proc.returncode == 4, f"Expected 4 for blocked {blocked_id}, got {run_proc.returncode}"
        run_data = QARunResult.model_validate(json.loads(run_proc.stdout))
        assert run_data.status == "INCOMPLETE"
        assert run_data.suites[0].suite_id == blocked_id
        assert run_data.suites[0].status == "INCOMPLETE"
        assert len(run_data.suites[0].reasons) > 0


def test_ac02_aliases_normalized_deduplicated_and_multi_suite_evidence_not_overwritten(tmp_path: Path):
    """AC-02: Alias react/frontend y browser/playwright se normalizan y deduplican; ninguna evidencia se sobrescribe."""
    repo = create_minimal_repo(tmp_path / "repo_ac02")
    env = os.environ.copy()
    env["PATH"] = ""
    env["QA_FORCE_NO_LOCAL_TOOLCHAINS"] = "1"

    proc = run_qa_cli(
        [
            "run",
            "--repo",
            str(repo),
            "--suite",
            "python,react,frontend,browser,playwright,python",
            "--json",
        ],
        env=env,
    )
    assert proc.returncode == 4
    result = QARunResult.model_validate(json.loads(proc.stdout))
    assert result.selected_suites == ["python", "frontend", "playwright"]
    assert [s.suite_id for s in result.suites] == ["python", "frontend", "playwright"]
    # Python ran once (2 cases in create_minimal_repo), not twice (4 cases)
    assert result.suites[0].counts.passed == 2
    assert result.counts.passed == 2

    ev_dir = Path(result.evidence_dir)
    assert (ev_dir / "result.json").is_file()
    # Evidencia histórica Python conservada y también separada por suite
    assert (ev_dir / "python.junit.xml").is_file()
    assert (ev_dir / "python" / "junit.xml").is_file()
    assert (ev_dir / "frontend" / "suite_result.json").is_file()
    assert (ev_dir / "playwright" / "suite_result.json").is_file()


def test_ac03_and_ac18_legacy_config_multi_engine_results_and_blocked_suite_prevents_exit_0(tmp_path: Path):
    """AC-03 / AC-18: Config anterior y nueva funcionan; una suite bloqueada junto con una aprobada impide salida 0."""
    repo = create_minimal_repo(tmp_path / "repo_ac03")
    legacy_cfg = tmp_path / "legacy.json"
    legacy_cfg.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "suites": ["python"],
                "timeout_seconds": 120,
                "output_dir": ".agentia-runtime/qa-legacy",
            }
        ),
        encoding="utf-8",
    )
    p_leg = run_qa_cli(["run", "--repo", str(repo), "--config", str(legacy_cfg), "--json"])
    assert p_leg.returncode == 0
    r_leg = QARunResult.model_validate(json.loads(p_leg.stdout))
    assert r_leg.status == "PASSED"
    assert r_leg.suites[0].engine == "pytest"
    assert r_leg.suites[0].process_exit_code == 0

    ext_cfg = tmp_path / "extended.json"
    ext_cfg.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "suites": ["python", "java"],
                "timeout_seconds": 120,
                "suite_timeouts": {"python": 90, "java": 600},
                "java_cache_dir": ".agentia-runtime/java-cache",
                "browser_cache_dir": ".agentia-runtime/browser-cache",
                "output_dir": ".agentia-runtime/qa-ext",
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = ""
    env["QA_FORCE_NO_LOCAL_TOOLCHAINS"] = "1"
    p_ext = run_qa_cli(["run", "--repo", str(repo), "--config", str(ext_cfg), "--json"], env=env)
    assert p_ext.returncode == 4
    r_ext = QARunResult.model_validate(json.loads(p_ext.stdout))
    assert r_ext.status == "INCOMPLETE"
    assert r_ext.suites[0].suite_id == "python" and r_ext.suites[0].status == "PASSED"
    assert r_ext.suites[1].suite_id == "java" and r_ext.suites[1].status == "INCOMPLETE"


def test_c04_multi_dialect_report_normalizer_rejects_missing_stale_corrupt_or_contradictory_reports(tmp_path: Path):
    """C04 (RF-311 / AC-12): Normalizador multimotor valida reportes JUnit/JSON de pytest, Surefire, Vitest y Playwright."""
    from qa_agent.result_normalization import validate_and_parse_junit_xml, validate_and_parse_json_report

    missing_xml = tmp_path / "nonexistent.xml"
    res_missing = validate_and_parse_junit_xml(
        xml_path=missing_xml,
        suite_id="java",
        engine="maven+surefire",
        process_exit_code=0,
        min_mtime=time.time(),
    )
    assert res_missing["status"] == "ERROR"
    assert res_missing["exit_code"] == 3

    stale_xml = tmp_path / "stale.xml"
    stale_xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?><testsuite name="s" tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="c" name="t1" time="0.1"/></testsuite>',
        encoding="utf-8",
    )
    old_time = time.time() - 120.0
    os.utime(stale_xml, (old_time, old_time))
    res_stale = validate_and_parse_junit_xml(
        xml_path=stale_xml,
        suite_id="java",
        engine="maven+surefire",
        process_exit_code=0,
        min_mtime=time.time() - 10.0,
    )
    assert res_stale["status"] == "ERROR"
    assert res_stale["exit_code"] == 3
    assert any("antiguo" in r.lower() or "obsoleto" in r.lower() or "fresco" in r.lower() for r in res_stale["reasons"])

    contradictory_json = tmp_path / "vitest_bad.json"
    contradictory_json.write_text(
        json.dumps(
            {
                "numTotalTests": 3,
                "numPassedTests": 3,
                "numFailedTests": 0,
                "numPendingTests": 0,
                "testResults": [
                    {
                        "name": "App.test.tsx",
                        "assertionResults": [
                            {"AncestorTitles": ["App"], "title": "renders", "status": "passed", "duration": 12}
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    res_bad_json = validate_and_parse_json_report(
        json_path=contradictory_json,
        dialect="vitest",
        suite_id="frontend",
        engine="vitest+tsc+vite",
        process_exit_code=0,
        min_mtime=time.time() - 10.0,
    )
    assert res_bad_json["status"] == "ERROR"
    assert res_bad_json["exit_code"] == 3


def test_c05_suite_snapshots_windows_batch_guard_and_daemon_cleanup(tmp_path: Path) -> None:
    """
    C05 (RF-312, RF-314):
    - Snapshots por suite incluyen solo los recursos necesarios y siempre excluyen `qa_tests/`.
    - `build_windows_safe_argv` rechaza metacaracteres de batch (`&`, `|`, `>`, `%`, `!`, saltos de línea) en wrappers `.cmd`/`.bat`,
      pero permite rutas con espacios seguros.
    - `ManagedDaemonProcess` drena salida masiva acotadamente y termina descendientes al cerrarse.
    """
    import sys as _sys

    from qa_agent.execution import (
        build_windows_safe_argv,
        cleanup_isolated_workspace,
        prepare_isolated_workspace,
    )
    from qa_agent.service_harness import ManagedDaemonProcess, allocate_loopback_ports

    repo = create_minimal_repo(tmp_path / "repo")
    (repo / "qa_scenarios" / "platform").mkdir(parents=True, exist_ok=True)
    (repo / "qa_scenarios" / "platform" / "test_sample.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (repo / "qa_tests").mkdir(parents=True, exist_ok=True)
    (repo / "qa_tests" / "secret_self_test.py").write_text("assert True\n", encoding="utf-8")

    ws_py = prepare_isolated_workspace(repo, "qa-c05-py", suite_id="python")
    try:
        assert not (ws_py.repo_copy / "qa_scenarios").exists()
        assert not (ws_py.repo_copy / "qa_tests").exists()
    finally:
        cleanup_isolated_workspace(ws_py, user_repo_root=repo)

    ws_plat = prepare_isolated_workspace(repo, "qa-c05-plat", suite_id="platform")
    try:
        assert (ws_plat.repo_copy / "qa_scenarios" / "platform" / "test_sample.py").is_file()
        assert not (ws_plat.repo_copy / "qa_tests").exists()
    finally:
        cleanup_isolated_workspace(ws_plat, user_repo_root=repo)

    # Rutas con espacios en wrappers .cmd son válidas si no contienen metacaracteres de cmd.exe
    safe_cmd = build_windows_safe_argv(["C:\\Program Files\\Maven\\bin\\mvn.cmd", "-Dmaven.repo.local=C:\\Path With Spaces\\m2", "test"])
    assert len(safe_cmd) >= 3

    for unsafe_arg in ["test&calc", "test|whoami", "foo>bar", "%PATH%", "!var!", "line1\nline2"]:
        try:
            build_windows_safe_argv(["mvn.cmd", unsafe_arg])
            raise AssertionError(f"Se esperaba ValueError para argumento inseguro: {unsafe_arg!r}")
        except ValueError:
            pass

    ports = allocate_loopback_ports(3)
    assert len(set(ports)) == 3

    child_pid_file = tmp_path / "daemon_child.pid"
    daemon_code = (
        "import subprocess, sys, time\n"
        "from pathlib import Path\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"Path({str(child_pid_file)!r}).write_text(str(child.pid), encoding='utf-8')\n"
        "for _ in range(100):\n"
        "    sys.stdout.write('X' * 300 + '\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(30)\n"
    )
    daemon = ManagedDaemonProcess(
        name="test-daemon",
        argv=[_sys.executable, "-c", daemon_code],
        cwd=tmp_path,
        env=os.environ.copy(),
        max_capture_chars=2048,
    )
    daemon.start()
    try:
        deadline = time.time() + 5.0
        while not child_pid_file.is_file() and time.time() < deadline:
            time.sleep(0.05)
        assert child_pid_file.is_file()
        assert daemon.is_running()
    finally:
        daemon.stop()

    assert not daemon.is_running()
    assert len(daemon.stdout_text()) <= 2048


def test_c06_versioned_fixtures_and_outbound_network_guard(tmp_path: Path) -> None:
    """
    C06 (RF-305, RF-307):
    - Las fixtures versionadas (`crud-h2`, `catalog-h2`, `solution-h2`) existen con blueprints y oráculos separados.
    - El network guard bloquea conexiones salientes no loopback y registra telemetría.
    """
    import sys as _sys

    from qa_agent.execution import run_bounded_subprocess

    repo_root = Path(__file__).resolve().parents[1]
    for fixture_dir, oracle_file in [
        ("crud_h2", "OracleInvoiceAcceptanceTest.java"),
        ("catalog_h2", "OracleCatalogAcceptanceTest.java"),
        ("solution_h2", "OracleOrderServiceAcceptanceTest.java"),
    ]:
        f_json = repo_root / "qa_scenarios" / "fixtures" / fixture_dir / "fixture.json"
        o_java = repo_root / "qa_scenarios" / "fixtures" / fixture_dir / oracle_file
        assert f_json.is_file(), f"Falta fixture {f_json}"
        assert o_java.is_file(), f"Falta oráculo {o_java}"
        parsed = json.loads(f_json.read_text(encoding="utf-8"))
        assert "fixtureId" in parsed and "version" in parsed

    telemetry_file = tmp_path / "guard_telemetry.jsonl"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    env["QA_SCENARIO_TELEMETRY_FILE"] = str(telemetry_file)
    env["OPENAI_API_KEY"] = "sk-should-be-stripped-by-guard"

    probe_code = (
        "import os, socket\n"
        "from qa_scenarios.support.network_guard import install_loopback_only_socket_guard\n"
        "install_loopback_only_socket_guard()\n"
        "assert 'OPENAI_API_KEY' not in os.environ\n"
        "try:\n"
        "    socket.create_connection(('8.8.8.8', 53), timeout=1.0)\n"
        "except RuntimeError as exc:\n"
        "    print('GUARD_BLOCKED_OK:' + str(exc))\n"
    )
    outcome = run_bounded_subprocess(
        argv=[_sys.executable, "-c", probe_code],
        cwd=tmp_path,
        env=env,
        timeout_seconds=10,
    )
    assert outcome.exit_code == 0
    assert "GUARD_BLOCKED_OK" in outcome.stdout
    assert telemetry_file.is_file()
    assert "blocked_external_connection" in telemetry_file.read_text(encoding="utf-8")


def test_r07_pydantic_round_trip_preserves_step_command_and_diagnostic():
    """
    R07: Comprueba que la validación y serialización de Pydantic en QASuiteStepResult
    y QARunResult no descartan 'kind', 'command' ni 'diagnostic' (C02/C04/V03).
    """
    step_data = {
        "step_id": "step-playwright-launch",
        "kind": "prepare",
        "status": "PASSED",
        "exit_code": 0,
        "duration_seconds": 2.45,
        "command": ["start_service_harness", "mode=java", "compiler=maven-real"],
        "diagnostic": "Servicios HTTP loopback iniciados con Maven real",
    }
    step_model = QASuiteStepResult.model_validate(step_data)
    dumped = step_model.model_dump()
    assert dumped["kind"] == "prepare"
    assert dumped["command"] == ["start_service_harness", "mode=java", "compiler=maven-real"]
    assert dumped["diagnostic"] == "Servicios HTTP loopback iniciados con Maven real"

    # Validar también dentro de un QASuiteExecutionResult
    suite_data = {
        "suite_id": "playwright",
        "implemented": True,
        "status": "PASSED",
        "exit_code": 0,
        "engine": "playwright+chromium",
        "steps": [step_data],
        "cases": [],
    }
    suite_model = QASuiteExecutionResult.model_validate(suite_data)
    suite_dumped = suite_model.model_dump()
    assert suite_dumped["steps"][0]["kind"] == "prepare"
    assert suite_dumped["steps"][0]["command"] == ["start_service_harness", "mode=java", "compiler=maven-real"]
    assert suite_dumped["steps"][0]["diagnostic"] == "Servicios HTTP loopback iniciados con Maven real"


