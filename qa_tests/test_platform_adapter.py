from __future__ import annotations

import json
import os
from pathlib import Path

from qa_agent import EXIT_PRODUCT_FAIL, EXIT_SUCCESS
from qa_agent.cli import main


def test_p06_platform_adapter_runs_real_http_and_detects_sqlite_generated_defect(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """
    P06 (AC-04..AC-08, RF-303/304/305):
    1. Al ejecutar los escenarios positivos (`-k "not solution_generated_sqlite_persistence"`),
       la suite `platform` devuelve código 0 (`PASSED`), persiste `platform/junit.xml`, `platform/platform.log`
       y `platform/boundary_profile.json` con `http=real`, `llm=double`, `compiler=double`, `java_verified=false`.
    2. Al ejecutar el escenario `test_p03_solution_generated_sqlite_persistence_across_restart`,
       la suite `platform` detecta el defecto real de persistencia SQLite (`GENERATED` -> `RUNNING` tras reinicio)
       y devuelve código 1 (`FAILED`) con el diagnóstico exacto redactado en `result.json`.
    """
    out_positive = tmp_path / "qa-out-positive"
    monkeypatch.setenv("QA_PLATFORM_PYTEST_K", "not solution_generated_sqlite_persistence")
    rc_pos = main(
        [
            "run",
            "--suite",
            "platform",
            "--output-dir",
            str(out_positive),
        ]
    )
    assert rc_pos == EXIT_SUCCESS
    pos_traces = list(out_positive.iterdir())
    assert len(pos_traces) == 1
    pos_res = json.loads((pos_traces[0] / "result.json").read_text(encoding="utf-8"))
    assert pos_res["status"] == "PASSED"
    assert pos_res["selected_suites"] == ["platform"]
    suite_entry = pos_res["suites"][0]
    assert suite_entry["suite_id"] == "platform"
    assert suite_entry["engine"] == "pytest+http-harness"
    assert suite_entry["counts"]["passed"] == 6
    assert suite_entry["counts"]["failed"] == 0
    assert (pos_traces[0] / "platform" / "junit.xml").is_file()
    assert (pos_traces[0] / "platform" / "platform.log").is_file()
    boundary_profile = json.loads(
        (pos_traces[0] / "platform" / "boundary_profile.json").read_text(encoding="utf-8")
    )
    assert boundary_profile == {
        "http": "real",
        "llm": "double",
        "compiler": "double",
        "java_verified": False,
    }

    # Ejecutar el control del defecto real de persistencia GENERATED en SQLite (AC-08)
    out_defect = tmp_path / "qa-out-defect"
    monkeypatch.setenv("QA_PLATFORM_PYTEST_K", "solution_generated_sqlite_persistence")
    rc_def = main(
        [
            "run",
            "--suite",
            "platform",
            "--output-dir",
            str(out_defect),
        ]
    )
    assert rc_def == EXIT_PRODUCT_FAIL
    def_traces = list(out_defect.iterdir())
    assert len(def_traces) == 1
    def_res = json.loads((def_traces[0] / "result.json").read_text(encoding="utf-8"))
    assert def_res["status"] == "FAILED"
    assert def_res["exit_code"] == 1
    def_suite = def_res["suites"][0]
    assert def_suite["counts"]["failed"] == 1
    failed_case = def_suite["cases"][0]
    assert failed_case["status"] == "FAILED"
    assert "GENERATED" in (failed_case.get("message") or "")
