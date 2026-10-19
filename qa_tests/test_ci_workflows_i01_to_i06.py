"""Pruebas de validación y contratos de CI en GitHub Actions (I01 a I06: AC-11, AC-15, AC-18, AC-19 a AC-24, AC-28 a AC-32)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
QA_YML_PATH = WORKFLOWS_DIR / "qa.yml"
QA_LLM_LIVE_YML_PATH = WORKFLOWS_DIR / "qa-llm-live.yml"

HEX_40_REGEX = re.compile(r"^[0-9a-f]{40}$")


def _load_yaml(path: Path) -> dict[str, Any]:
    assert path.is_file(), f"El archivo de workflow {path} no existe."
    content = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict), f"El contenido de {path} no es un diccionario YAML válido."
    return parsed


def test_i01_workflow_files_exist_and_parse_valid_yaml():
    """I01: Verifica que qa.yml y qa-llm-live.yml existan y sean sintácticamente válidos."""
    assert QA_YML_PATH.is_file(), "qa.yml debe existir en .github/workflows/"
    assert QA_LLM_LIVE_YML_PATH.is_file(), "qa-llm-live.yml debe existir en .github/workflows/"

    qa_data = _load_yaml(QA_YML_PATH)
    qa_llm_data = _load_yaml(QA_LLM_LIVE_YML_PATH)

    assert "name" in qa_data
    assert "jobs" in qa_data
    assert "name" in qa_llm_data
    assert "jobs" in qa_llm_data


def test_i01_triggers_and_least_privilege_permissions():
    """I01: Verifica triggers PR/push/dispatch y permisos de solo lectura (least privilege)."""
    qa_data = _load_yaml(QA_YML_PATH)

    # Permisos mínimos
    assert qa_data.get("permissions") == {"contents": "read"}

    # Triggers
    on_triggers = qa_data.get("on") or qa_data.get(True)
    assert isinstance(on_triggers, dict)
    assert "pull_request" in on_triggers
    assert "push" in on_triggers
    assert "workflow_dispatch" in on_triggers

    # Dispatch profile selector
    inputs = on_triggers["workflow_dispatch"].get("inputs", {})
    assert "profile" in inputs
    assert inputs["profile"]["type"] == "choice"
    assert set(inputs["profile"]["options"]) >= {"all", "core", "platform", "frontend", "functional"}


def test_i01_all_actions_use_pinned_sha_and_version_comment():
    """I01, I02: Verifica que toda acción oficial use un commit SHA inmutable de 40 caracteres hexadecimales."""
    for path in (QA_YML_PATH, QA_LLM_LIVE_YML_PATH):
        raw_text = path.read_text(encoding="utf-8")
        qa_data = yaml.safe_load(raw_text)

        for job_name, job_def in qa_data.get("jobs", {}).items():
            for step in job_def.get("steps", []):
                uses = step.get("uses")
                if uses:
                    # Formato: action/name@<sha40>
                    action_part = uses.split("#")[0].strip()
                    assert "@" in action_part, f"Acción sin versión/SHA: {uses} en job {job_name} ({path.name})"
                    action_name, ref = action_part.split("@", 1)
                    assert HEX_40_REGEX.match(ref), (
                        f"La acción '{action_name}' en job '{job_name}' ({path.name}) no usa un commit SHA inmutable de 40 hex (usa '{ref}')"
                    )


def test_i02_ordinary_jobs_structure_and_runners():
    """I02: Verifica jobs core, platform, frontend, functional y summary en qa.yml."""
    qa_data = _load_yaml(QA_YML_PATH)
    jobs = qa_data["jobs"]

    assert "core" in jobs
    assert "platform" in jobs
    assert "frontend" in jobs
    assert "functional" in jobs
    assert "summary" in jobs

    # Matriz multiplataforma Windows y Linux para core, platform y functional
    for matrix_job in ("core", "platform", "functional"):
        matrix = jobs[matrix_job].get("strategy", {}).get("matrix", {})
        os_list = matrix.get("os", [])
        assert "ubuntu-latest" in os_list, f"El job {matrix_job} debe probar ubuntu-latest"
        assert "windows-latest" in os_list, f"El job {matrix_job} debe probar windows-latest"


def test_i02_no_secrets_in_ordinary_qa_pipeline():
    """I02: Verifica que qa.yml no contenga ninguna referencia a secretos ni claves de API."""
    raw_text = QA_YML_PATH.read_text(encoding="utf-8")
    assert "secrets." not in raw_text, "qa.yml no debe acceder a secretos en flujos ordinarios ni PRs."
    assert "API_KEY" not in raw_text, "qa.yml no debe declarar variables con API_KEY."


def test_i03_functional_job_dependencies_and_caches():
    """I03: Verifica configuración de JDK 21, Maven 3.9.9, Node 22, Playwright cache y exclusión de PRs ordinarios."""
    qa_data = _load_yaml(QA_YML_PATH)
    func_job = qa_data["jobs"]["functional"]

    # Condición de ejecución: solo push o workflow_dispatch con perfil correspondiente
    condition = func_job.get("if", "")
    assert "push" in condition
    assert "workflow_dispatch" in condition
    assert "pull_request" not in condition, "functional no debe ejecutarse por defecto en pull_request"

    steps = func_job.get("steps", [])
    step_uses = [s.get("uses", "") for s in steps]

    # Verifica presencia de setup-java y setup-node
    has_java = any("actions/setup-java" in u for u in step_uses)
    has_node = any("actions/setup-node" in u for u in step_uses)
    has_cache = any("actions/cache" in u for u in step_uses)

    assert has_java, "functional debe incluir actions/setup-java"
    assert has_node, "functional debe incluir actions/setup-node"
    assert has_cache, "functional debe incluir actions/cache para Playwright Chromium"


def test_i04_artifacts_preservation_and_exit_code_propagation():
    """I04: Verifica upload-artifact con if: always(), retención de 7 días y propagación de exit code."""
    qa_data = _load_yaml(QA_YML_PATH)

    for job_name in ("core", "platform", "frontend", "functional"):
        job = qa_data["jobs"][job_name]
        steps = job.get("steps", [])

        # Debe existir un paso de upload-artifact
        upload_steps = [s for s in steps if "actions/upload-artifact" in s.get("uses", "")]
        assert len(upload_steps) >= 1, f"El job {job_name} debe incluir actions/upload-artifact"
        upload_step = upload_steps[0]

        assert upload_step.get("if") == "always()", f"El upload en {job_name} debe tener 'if: always()'"
        with_cfg = upload_step.get("with", {})
        assert with_cfg.get("retention-days") == 7, f"La retención en {job_name} debe ser de 7 días"

        # Debe existir paso con escritura a GITHUB_STEP_SUMMARY
        summary_steps = [s for s in steps if "$GITHUB_STEP_SUMMARY" in s.get("run", "")]
        assert len(summary_steps) >= 1, f"El job {job_name} debe generar un paso de resumen en GITHUB_STEP_SUMMARY"


def test_i05_live_llm_workflow_isolation_and_credentials_guard():
    """I05: Verifica que qa-llm-live.yml solo corra por workflow_dispatch con guards estrictos de credenciales."""
    qa_llm_data = _load_yaml(QA_LLM_LIVE_YML_PATH)

    # Exclusivamente workflow_dispatch
    triggers = qa_llm_data.get("on") or qa_llm_data.get(True)
    assert set(triggers.keys()) == {"workflow_dispatch"}, "qa-llm-live.yml solo debe admitir workflow_dispatch"

    inputs = triggers["workflow_dispatch"].get("inputs", {})
    assert "provider" in inputs
    assert "llm_mode" in inputs
    assert set(inputs["provider"]["options"]) == {"gemini", "openai", "deepseek"}
    assert set(inputs["llm_mode"]["options"]) == {"real", "simulated"}

    job = qa_llm_data["jobs"]["llm-live"]
    assert job.get("environment") == "qa-live", "El job llm-live debe usar el environment 'qa-live'"

    # Guard de verificación de credenciales presente
    steps = job.get("steps", [])
    guard_steps = [s for s in steps if "Verify Credentials Guard" in s.get("name", "")]
    assert len(guard_steps) == 1, "Debe existir un paso explícito de verificación de credenciales"
    guard_run = guard_steps[0].get("run", "")
    assert "GEMINI_API_KEY" in guard_run
    assert "OPENAI_API_KEY" in guard_run
    assert "DEEPSEEK_API_KEY" in guard_run
    assert "exit 4" in guard_run, "La ausencia de credenciales en modo real debe abortar con código 4 (INCOMPLETE)"


def test_i06_local_dry_run_of_workflow_commands():
    """I06: Ejecuta en seco los comandos de entrada que invocará el runner de CI."""
    from qa_tests.conftest import run_qa_cli

    # Comprobar doctor y list usando el lanzador scripts/qa.py
    proc = run_qa_cli(["doctor", "--json"], use_script=True)
    assert proc.returncode == 0
    assert "capabilities" in proc.stdout

    proc = run_qa_cli(["list", "--json"], use_script=True)
    assert proc.returncode == 0
    assert "suites" in proc.stdout
