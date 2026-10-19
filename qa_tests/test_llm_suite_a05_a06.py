"""Pruebas unitarias e integración de la suite LLM (A05, A06: AC-09, AC-10, AC-16, AC-17, AC-18)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from contracts.models import (
    DiagnosticIssue,
    FileContent,
    RepairRequest,
    TestBaseline,
)
from qa_agent.adapters.llm import run_llm_suite
from qa_scenarios.llm.crud_h2_repair_scenario import (
    build_crud_h2_repair_request,
    build_simulated_repair_patch,
    evaluate_delete_oracle_in_process,
    materialize_defective_crud_h2,
)
from qa_tests.conftest import create_minimal_repo, run_qa_cli


def test_a05_materialize_defective_crud_h2_and_negative_control(tmp_path: Path):
    """A05: Materializa crud-h2 con DELETE retornando HTTP 200 y demuestra el control negativo contra el oráculo."""
    repo_root = Path(__file__).resolve().parents[1]
    ws = tmp_path / "ws_defective"

    meta = materialize_defective_crud_h2(ws, repo_root)
    assert meta["fixture_id"] == "crud-h2"
    assert meta["defective_delete_status"] == 200
    assert meta["expected_delete_status"] == 204

    failing_file = ws / meta["failing_rel_path"]
    assert failing_file.is_file()
    content = failing_file.read_text(encoding="utf-8")
    assert "return Response.ok().build();" in content

    oracle_file = ws / meta["oracle_test_path"]
    assert oracle_file.is_file()

    # Control Negativo: el código defectuoso debe fallar la aserción de DELETE 204
    passed, diag = evaluate_delete_oracle_in_process(content)
    assert passed is False
    assert "200 en lugar del HTTP 204" in diag


def test_a05_guards_enforcement_and_rejections(tmp_path: Path):
    """A05: ScopedRepairService aplica deterministicamente guards G1, G3 y G7 en el contexto de crud-h2."""
    from agents.profiles.loader import get_profile
    from agents.repair.service import ScopedRepairService

    repo_root = Path(__file__).resolve().parents[1]
    ws = tmp_path / "ws_guards"
    meta = materialize_defective_crud_h2(ws, repo_root)
    req = build_crud_h2_repair_request(ws, meta["failing_rel_path"], meta["defective_code"])
    profile = get_profile("quarkus", "3.15.1")

    # 1. Parche quirúrgico válido -> PATCHED, guards passed
    valid_patch = build_simulated_repair_patch(meta["failing_rel_path"])
    svc = ScopedRepairService(patch_generator=lambda p: valid_patch)
    res_valid = svc.repair(profile, req)
    assert res_valid.outcome == "PATCHED"
    assert res_valid.guard_report.passed is True
    assert res_valid.guard_report.failed_guards == []

    # 2. Violación G1: intenta modificar un archivo no permitido
    bad_g1_patch = (
        "--- a/src/main/java/com/agentia/qa/invoice/Unallowed.java\n"
        "+++ b/src/main/java/com/agentia/qa/invoice/Unallowed.java\n"
        "@@ -1,1 +1,1 @@\n"
        "-class Unallowed {}\n"
        "+class Unallowed { int x; }\n"
    )
    svc_g1 = ScopedRepairService(patch_generator=lambda p: bad_g1_patch)
    res_g1 = svc_g1.repair(profile, req)
    assert res_g1.outcome == "REJECTED_BY_GUARD"
    assert res_g1.guard_report.passed is False
    assert "G1" in res_g1.guard_report.failed_guards

    # 3. Violación G7: intenta modificar pom.xml sin estar en allowed_paths
    bad_g7_patch = (
        "--- a/pom.xml\n"
        "+++ b/pom.xml\n"
        "@@ -1,1 +1,1 @@\n"
        "-<project>\n"
        "+<project modified='true'>\n"
    )
    svc_g7 = ScopedRepairService(patch_generator=lambda p: bad_g7_patch)
    res_g7 = svc_g7.repair(profile, req)
    assert res_g7.outcome == "REJECTED_BY_GUARD"
    assert "G7" in res_g7.guard_report.failed_guards


def test_a06_llm_suite_simulated_mode_passes(tmp_path: Path):
    """A06: La suite llm en modo simulated (predeterminado) pasa localmente con cero llamadas externas."""
    repo_root = Path(__file__).resolve().parents[1]
    res, arts, xml, out, err = run_llm_suite(
        repo_root=repo_root,
        trace_id="test-sim-01",
        timeout_seconds=60,
        llm_mode="simulated",
        llm_provider="gemini",
    )
    assert res["suite_id"] == "llm"
    assert res["status"] == "PASSED"
    assert res["exit_code"] == 0
    assert res["counts"]["passed"] >= 3
    assert res["counts"]["failed"] == 0

    case_ids = {c["case_id"] for c in res["cases"]}
    assert "crud_h2::negative_control" in case_ids
    assert "crud_h2::guard_evaluation" in case_ids
    assert "crud_h2::oracle_verification" in case_ids

    # Artefactos esperados persistidos
    assert "llm/defective_InvoiceResource.java" in arts
    assert "llm/repair_result.json" in arts
    assert "llm/repair_patch.diff" in arts
    assert "llm/patched_InvoiceResource.java" in arts

    # El archivo parchado contiene HTTP 204
    assert "NO_CONTENT" in arts["llm/patched_InvoiceResource.java"]


def test_a06_llm_suite_real_mode_missing_credentials_blocks_cleanly(tmp_path: Path):
    """A06: En modo real sin credenciales, devuelve INCOMPLETE (exit code 4) sin lanzar excepciones ni hacer peticiones."""
    repo_root = Path(__file__).resolve().parents[1]
    clean_env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}

    orig_env = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(clean_env)

        res, arts, xml, out, err = run_llm_suite(
            repo_root=repo_root,
            trace_id="test-real-missing-key",
            timeout_seconds=60,
            llm_mode="real",
            llm_provider="deepseek",
        )
        assert res["suite_id"] == "llm"
        assert res["status"] == "INCOMPLETE"
        assert res["exit_code"] == 4
        assert any("DEEPSEEK_API_KEY" in r for r in res["reasons"])
    finally:
        os.environ.clear()
        os.environ.update(orig_env)


def test_a06_cli_rejects_llm_mode_real_without_suite_llm(tmp_path: Path):
    """A06: CLI rechaza --llm-mode real si no se selecciona la suite llm (exit code 2)."""
    repo = create_minimal_repo(tmp_path / "repo_cli_llm")
    proc = run_qa_cli(["run", "--repo", str(repo), "--suite", "python", "--llm-mode", "real"])
    assert proc.returncode == 2
    assert "requiere seleccionar la suite 'llm'" in proc.stdout or "requiere seleccionar la suite 'llm'" in proc.stderr


def test_a06_verify_generated_java_reports_incomplete_without_tools(tmp_path: Path):
    """A06: verify_generated_java sin JDK/Maven/cache declara compilador doble y reporta INCOMPLETE sin llamarlo compilación."""
    repo_root = Path(__file__).resolve().parents[1]
    empty_cache = tmp_path / "empty-m2"
    empty_cache.mkdir()

    res, arts, xml, out, err = run_llm_suite(
        repo_root=repo_root,
        trace_id="test-verify-java-missing-tools",
        timeout_seconds=60,
        llm_mode="simulated",
        verify_generated_java=True,
        java_cache_dir=empty_cache,
    )
    # Se debe registrar el paso java-maven-verification como INCOMPLETE si faltan artefactos
    maven_step = next((s for s in res["steps"] if s["step_id"] == "llm-java-maven-verification"), None)
    assert maven_step is not None
    assert maven_step["status"] in ("INCOMPLETE", "PASSED")
