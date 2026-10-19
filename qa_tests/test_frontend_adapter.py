from __future__ import annotations

import json
import subprocess
from pathlib import Path

from qa_agent import (
    EXIT_EXECUTION_ERROR,
    EXIT_INCOMPLETE,
    EXIT_PRODUCT_FAIL,
    EXIT_SUCCESS,
)
from qa_agent.adapters.frontend import run_frontend_suite
from qa_agent.cli import main
from qa_agent.execution import SubprocessOutcome

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_u01_missing_node_modules_returns_incomplete_4_without_network(
    tmp_path: Path,
) -> None:
    """
    U01 / RF-309 / RF-313:
    Si `frontend/node_modules` no está preparado en el repositorio objetivo,
    `run_frontend_suite` devuelve `INCOMPLETE` (código 4) sin ejecutar `npm install`.
    """
    fake_repo = tmp_path / "repo-no-node-modules"
    (fake_repo / "frontend").mkdir(parents=True, exist_ok=True)
    suite_res, artifacts, _, _, _ = run_frontend_suite(
        repo_root=fake_repo,
        trace_id="qa-20261019T050000Z-u01nomod",
    )
    assert suite_res["status"] == "INCOMPLETE"
    assert suite_res["exit_code"] == EXIT_INCOMPLETE
    assert artifacts == {}


def test_u03_contradictory_vitest_reports_zero_cases_and_build_failure_classification(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """
    U03 (AC-13, F01):
    - Reportes contradictorios entre JUnit XML y JSON de Vitest devuelven `ERROR` (código 3).
    - Cero casos recolectados (`tests=0`) devuelve `INCOMPLETE` (código 4).
    - Fallo de compilación TypeScript (`tsc -b` exit 2) con Vitest verde devuelve `FAILED` (código 1)
      en el paso `frontend-typecheck-tsc` sin inflar `counts.collected`.
    """
    fake_repo = tmp_path / "fake-fe-repo"
    vt_dir = fake_repo / "frontend" / "node_modules" / "vitest"
    tsc_dir = fake_repo / "frontend" / "node_modules" / "typescript" / "bin"
    vite_dir = fake_repo / "frontend" / "node_modules" / "vite" / "bin"
    for d in (vt_dir, tsc_dir, vite_dir, fake_repo / "frontend" / "src", fake_repo / "app", fake_repo / "tests"):
        d.mkdir(parents=True, exist_ok=True)
    (vt_dir / "vitest.mjs").write_text("// stub", encoding="utf-8")
    (tsc_dir / "tsc").write_text("// stub", encoding="utf-8")
    (vite_dir / "vite.js").write_text("// stub", encoding="utf-8")
    (fake_repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    # 1. Contradicción JUnit XML (2 passed) vs JSON (1 passed, 1 failed) -> ERROR (3)
    def _mock_contradictory_subproc(argv, cwd, env, timeout_seconds):
        cmd_str = " ".join(str(a) for a in argv)
        if "vitest.mjs" in cmd_str:
            junit_arg = next(str(a) for a in argv if str(a).startswith("--outputFile.junit="))
            json_arg = next(str(a) for a in argv if str(a).startswith("--outputFile.json="))
            junit_path = Path(junit_arg.split("=", 1)[1])
            json_path = Path(json_arg.split("=", 1)[1])
            junit_path.write_text(
                '<testsuites><testsuite name="vt" tests="2" failures="0" errors="0" skipped="0">'
                '<testcase classname="a" name="t1" time="0.01"/><testcase classname="a" name="t2" time="0.01"/>'
                "</testsuite></testsuites>",
                encoding="utf-8",
            )
            json_path.write_text(
                json.dumps(
                    {
                        "numTotalTests": 2,
                        "numPassedTests": 1,
                        "numFailedTests": 1,
                        "numPendingTests": 0,
                        "testResults": [
                            {
                                "name": "a.test.tsx",
                                "assertionResults": [
                                    {"title": "t1", "status": "passed", "duration": 10},
                                    {"title": "t2", "status": "failed", "duration": 10, "failureMessages": ["boom"]},
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
        return SubprocessOutcome(exit_code=0, timed_out=False, interrupted=False, stdout="ok", stderr="", duration_seconds=0.1, output_truncated=False)

    monkeypatch.setattr("qa_agent.adapters.frontend.run_bounded_subprocess", _mock_contradictory_subproc)
    res_mismatch, _, _, _, _ = run_frontend_suite(repo_root=fake_repo, trace_id="qa-20261019T050000Z-u03mis")
    assert res_mismatch["status"] == "ERROR"
    assert res_mismatch["exit_code"] == EXIT_EXECUTION_ERROR
    assert any("contradicción" in r.lower() for r in res_mismatch["reasons"])

    # 2. Ausencia de casos (0 tests) -> INCOMPLETE (4)
    def _mock_zero_cases_subproc(argv, cwd, env, timeout_seconds):
        cmd_str = " ".join(str(a) for a in argv)
        if "vitest.mjs" in cmd_str:
            junit_arg = next(str(a) for a in argv if str(a).startswith("--outputFile.junit="))
            json_arg = next(str(a) for a in argv if str(a).startswith("--outputFile.json="))
            Path(junit_arg.split("=", 1)[1]).write_text(
                '<testsuites><testsuite name="vt" tests="0" failures="0" errors="0" skipped="0"/></testsuites>',
                encoding="utf-8",
            )
            Path(json_arg.split("=", 1)[1]).write_text(
                json.dumps({"numTotalTests": 0, "numPassedTests": 0, "numFailedTests": 0, "numPendingTests": 0, "testResults": []}),
                encoding="utf-8",
            )
        return SubprocessOutcome(exit_code=0, timed_out=False, interrupted=False, stdout="0 tests", stderr="", duration_seconds=0.1, output_truncated=False)

    monkeypatch.setattr("qa_agent.adapters.frontend.run_bounded_subprocess", _mock_zero_cases_subproc)
    res_zero, _, _, _, _ = run_frontend_suite(repo_root=fake_repo, trace_id="qa-20261019T050000Z-u03zero")
    assert res_zero["status"] == "INCOMPLETE"
    assert res_zero["exit_code"] == EXIT_INCOMPLETE

    # 3. Vitest verde (2 passed) pero tsc -b falla (exit 2) -> FAILED (1), counts.collected se mantiene en 2
    def _mock_tsc_fail_subproc(argv, cwd, env, timeout_seconds):
        cmd_str = " ".join(str(a) for a in argv)
        if "vitest.mjs" in cmd_str:
            junit_arg = next(str(a) for a in argv if str(a).startswith("--outputFile.junit="))
            json_arg = next(str(a) for a in argv if str(a).startswith("--outputFile.json="))
            Path(junit_arg.split("=", 1)[1]).write_text(
                '<testsuites><testsuite name="vt" tests="2" failures="0" errors="0" skipped="0">'
                '<testcase classname="a" name="t1" time="0.01"/><testcase classname="a" name="t2" time="0.01"/>'
                "</testsuite></testsuites>",
                encoding="utf-8",
            )
            Path(json_arg.split("=", 1)[1]).write_text(
                json.dumps(
                    {
                        "numTotalTests": 2,
                        "numPassedTests": 2,
                        "numFailedTests": 0,
                        "numPendingTests": 0,
                        "testResults": [
                            {
                                "name": "a.test.tsx",
                                "assertionResults": [
                                    {"title": "t1", "status": "passed", "duration": 10},
                                    {"title": "t2", "status": "passed", "duration": 10},
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return SubprocessOutcome(exit_code=0, timed_out=False, interrupted=False, stdout="2 passed", stderr="", duration_seconds=0.1, output_truncated=False)
        if "tsc" in cmd_str:
            return SubprocessOutcome(exit_code=2, timed_out=False, interrupted=False, stdout="src/App.tsx(5,1): error TS2322", stderr="", duration_seconds=0.1, output_truncated=False)
        return SubprocessOutcome(exit_code=0, timed_out=False, interrupted=False, stdout="built", stderr="", duration_seconds=0.1, output_truncated=False)

    monkeypatch.setattr("qa_agent.adapters.frontend.run_bounded_subprocess", _mock_tsc_fail_subproc)
    res_tsc_fail, _, _, _, _ = run_frontend_suite(repo_root=fake_repo, trace_id="qa-20261019T050000Z-u03tsc")
    assert res_tsc_fail["status"] == "FAILED"
    assert res_tsc_fail["exit_code"] == EXIT_PRODUCT_FAIL
    assert res_tsc_fail["counts"]["collected"] == 2
    tsc_step = next(s for s in res_tsc_fail["steps"] if s["step_id"] == "frontend-typecheck-tsc")
    assert tsc_step["status"] == "FAILED"


def test_u03_real_frontend_suite_vitest_tsc_and_vite_build(
    tmp_path: Path,
) -> None:
    """
    U03 (AC-13, RF-309):
    Ejecuta `python -m qa_agent run --suite frontend` real sobre el repositorio:
    - Materializa `frontend/node_modules` en el workspace aislado.
    - Ejecuta los 14 archivos de tests Vitest (`FunctionalCoverageU02.test.tsx` + 13 existentes),
      valida JUnit XML + JSON, ejecuta `tsc -b` y ejecuta `vite build`.
    - Devuelve código 0 (`PASSED`) y persiste todos los artefactos bajo `frontend/`.
    """
    out_dir = tmp_path / "qa-frontend-out"
    rc = main(
        [
            "run",
            "--suite",
            "frontend",
            "--output-dir",
            str(out_dir),
        ]
    )
    assert rc == EXIT_SUCCESS

    runs = list(out_dir.glob("qa-*"))
    assert len(runs) == 1
    result_data = json.loads((runs[0] / "result.json").read_text(encoding="utf-8"))
    assert result_data["status"] == "PASSED"
    assert result_data["exit_code"] == EXIT_SUCCESS

    fe_suite = next(s for s in result_data["suites"] if s["suite_id"] == "frontend")
    assert fe_suite["status"] == "PASSED"
    assert fe_suite["engine"] == "vitest+tsc+vite"
    assert fe_suite["counts"]["collected"] >= 40
    assert fe_suite["counts"]["failed"] == 0
    assert fe_suite["counts"]["errors"] == 0

    step_ids = [s["step_id"] for s in fe_suite["steps"]]
    assert step_ids == [
        "frontend-prepare-node-modules",
        "frontend-vitest",
        "frontend-typecheck-tsc",
        "frontend-build-vite",
    ]
    for s in fe_suite["steps"]:
        assert s["status"] == "PASSED"

    for expected_file in ("vitest.log", "junit.xml", "vitest-report.json", "tsc.log", "vite-build.log"):
        assert (runs[0] / "frontend" / expected_file).is_file()


def test_r06_missing_tsc_or_vite_returns_incomplete_4(
    tmp_path: Path,
) -> None:
    """
    R06 / AC-13 / U03:
    Si faltan los binarios CLI `typescript/bin/tsc` o `vite/bin/vite.js`,
    la suite `frontend` no debe omitirlos silenciosamente ni aprobar con éxito falso,
    sino devolver INCOMPLETE (código 4).
    """
    fake_repo = tmp_path / "repo-missing-tsc"
    vt_dir = fake_repo / "frontend" / "node_modules" / "vitest"
    vt_dir.mkdir(parents=True, exist_ok=True)
    (vt_dir / "vitest.mjs").write_text("// stub", encoding="utf-8")
    (fake_repo / "frontend" / "package.json").write_text('{"name": "fe"}', encoding="utf-8")

    suite_res, artifacts, _, stdout, _ = run_frontend_suite(
        repo_root=fake_repo,
        trace_id="qa-20261019T064500Z-r06notsc",
    )
    assert suite_res["status"] == "INCOMPLETE"
    assert suite_res["exit_code"] == EXIT_INCOMPLETE
    assert any("typescript/bin/tsc" in r or "binarios CLI" in r for r in suite_res["reasons"])

