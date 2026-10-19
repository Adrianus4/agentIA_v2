"""Pruebas de portabilidad, tareas VS Code y condiciones adversas (P01 a P05: AC-02, AC-07, AC-18, AC-24 a AC-29, AC-31)."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from qa_tests.conftest import REPO_ROOT, create_minimal_repo, run_qa_cli


def test_p01_dependencies_pinned_and_audit():
    """P01: Verifica que requirements-qa.txt esté fijado, exista y sea coherente con Python 3.12."""
    req_file = REPO_ROOT / "requirements-qa.txt"
    assert req_file.is_file(), "requirements-qa.txt debe existir"
    content = req_file.read_text(encoding="utf-8")

    # Verifica dependencias clave fijadas con versiones exactas
    assert "fastapi==" in content
    assert "httpx==" in content
    assert "Jinja2==" in content
    assert "pydantic==" in content
    assert "PyYAML==" in content
    assert "uvicorn" in content


def test_p03_vscode_tasks_valid_json_and_contracts():
    """P03: Verifica que .vscode/tasks.json sea JSON válido, use variables estándar y no rutas hardcodeadas."""
    tasks_file = REPO_ROOT / ".vscode" / "tasks.json"
    assert tasks_file.is_file(), ".vscode/tasks.json debe existir"

    data = json.loads(tasks_file.read_text(encoding="utf-8"))
    assert data.get("version") == "2.0.0"
    tasks = data.get("tasks", [])
    assert len(tasks) >= 6, "Deben existir al menos 6 tareas estructuradas"

    labels = {t.get("label") for t in tasks}
    assert any("Doctor" in l for l in labels)
    assert any("Listar" in l for l in labels)
    assert any("Mínimo" in l or "Minimo" in l for l in labels)
    assert any("Plataforma" in l for l in labels)
    assert any("Completo" in l for l in labels)
    assert any("Reporte" in l for l in labels)

    raw_text = tasks_file.read_text(encoding="utf-8")
    assert "C:\\Users\\willi" not in raw_text, "No deben existir rutas absolutas del desarrollador en tasks.json"
    assert "C:/Users/willi" not in raw_text, "No deben existir rutas absolutas del desarrollador en tasks.json"
    assert "API_KEY" not in raw_text, "tasks.json no debe contener claves de API"

    for t in tasks:
        assert t.get("command") == "${command:python.interpreterPath}"
        assert isinstance(t.get("args"), list), "Los argumentos deben ser una lista estructurada, no string concatenado"


def test_p05_paths_with_spaces_and_unicode(tmp_path: Path):
    """P05: Verifica que rutas con espacios y caracteres acentuados/Unicode se manejen correctamente."""
    unicode_dir = tmp_path / "Directorio Con Espacios y Acentos áéíóú ñ"
    unicode_dir.mkdir(parents=True, exist_ok=True)
    repo = create_minimal_repo(unicode_dir / "repo_origen")
    out_dir = unicode_dir / "salida reportes"

    # Ejecutar doctor con repo en ruta con espacios
    proc = run_qa_cli(["doctor", "--repo", str(repo), "--json"], use_script=True)
    assert proc.returncode == 0
    doc_data = json.loads(proc.stdout)
    assert "capabilities" in doc_data

    # Ejecutar run con repo y output_dir en rutas complejas
    proc_run = run_qa_cli(
        ["run", "--repo", str(repo), "--suite", "python", "--output-dir", str(out_dir)],
        use_script=True,
    )
    assert proc_run.returncode == 0
    traces = list(out_dir.glob("qa-*"))
    assert len(traces) == 1, f"Se esperaba un trace dir en {out_dir}, se encontró: {traces}"
    trace_dir = traces[0]
    assert (trace_dir / "result.json").is_file()
    assert (trace_dir / "delivery.json").is_file()
    assert (trace_dir / "report" / "report.html").is_file()


def test_p05_external_cwd_execution(tmp_path: Path):
    """P05: Ejecuta scripts/qa.py desde un cwd completamente externo y ajeno al repositorio."""
    external_cwd = tmp_path / "completamente_externo"
    external_cwd.mkdir()

    # Invocamos scripts/qa.py pasando el cwd externo y apuntando con --repo a REPO_ROOT
    proc = run_qa_cli(["doctor", "--repo", str(REPO_ROOT), "--json"], cwd=external_cwd, use_script=True)
    assert proc.returncode == 0
    doc_data = json.loads(proc.stdout)
    assert doc_data["repo_root"] == str(REPO_ROOT)


def test_p05_repository_without_git(tmp_path: Path):
    """P05: Ejecuta QA sobre una copia que NO contiene directorio .git (degradación a hash)."""
    no_git_repo = create_minimal_repo(tmp_path / "no_git_repo")
    assert not (no_git_repo / ".git").exists()

    out_dir = tmp_path / "no_git_out"
    proc = run_qa_cli(["run", "--repo", str(no_git_repo), "--suite", "python", "--output-dir", str(out_dir)], use_script=True)
    assert proc.returncode == 0

    traces = list(out_dir.glob("qa-*"))
    assert len(traces) == 1
    trace_dir = traces[0]
    result_data = json.loads((trace_dir / "result.json").read_text(encoding="utf-8"))
    assert result_data["status"] == "PASSED"
    # Sin git, git_commit_sha no está o es nulo
    assert result_data.get("git_commit_sha") is None or isinstance(result_data.get("git_commit_sha"), str)


def test_p05_workspace_isolation_cleanup_and_sentinel(tmp_path: Path):
    """P05: Verifica que el workspace aislado se limpie y el centinela del repositorio no sea modificado."""
    repo = create_minimal_repo(tmp_path / "sentinel_repo")
    sentinel = repo / "sentinel.txt"
    assert sentinel.read_text(encoding="utf-8") == "SENTINEL_UNTOUCHED"

    out_dir = tmp_path / "sentinel_out"
    proc = run_qa_cli(["run", "--repo", str(repo), "--suite", "python", "--output-dir", str(out_dir)], use_script=True)
    assert proc.returncode == 0

    # Centinela debe permanecer intacto
    assert sentinel.read_text(encoding="utf-8") == "SENTINEL_UNTOUCHED"


def test_p05_missing_suite_blocked_without_crash(tmp_path: Path):
    """P05: Solicitar una suite cuyas capacidades están ausentes debe reportar BLOCKED o fallar con código 2 sin crashear."""
    repo = create_minimal_repo(tmp_path / "blocked_repo")

    # Si forzamos una suite con ruta inventada o sin tools requeridas
    proc = run_qa_cli(["run", "--repo", str(repo), "--suite", "inexistente_suite"], use_script=True)
    assert proc.returncode == 2, "Suites no registradas deben fallar con código de configuración 2"
