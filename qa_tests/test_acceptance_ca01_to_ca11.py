import concurrent.futures
import json
import os
import time
from pathlib import Path

import pytest

from contracts.models import (
    QACaseResult,
    QAConfigModel,
    QACounts,
    QADoctorReport,
    QAListReport,
    QARunResult,
    QASuiteExecutionResult,
)
from qa_tests.conftest import REPO_ROOT, create_minimal_repo, run_qa_cli


def test_e01_contracts_models_validation():
    """E01: Verify QA Pydantic contracts in contracts/models.py enforce schema and extra=forbid."""
    cfg = QAConfigModel(suites=["python"], timeout_seconds=120, output_dir=".agentia-runtime/qa")
    assert cfg.schema_version == "1.0"
    assert cfg.suites == ["python"]

    with pytest.raises(ValueError):
        QAConfigModel(suites=[])

    with pytest.raises(ValueError):
        QAConfigModel(timeout_seconds=0)

    with pytest.raises(ValueError):
        QAConfigModel(output_dir="../escape")

    with pytest.raises(ValueError):
        QAConfigModel(unknown_field="not_allowed")  # type: ignore[call-arg]

    counts = QACounts(collected=2, passed=2, failed=0, errors=0, skipped=0, xfail=0)
    case = QACaseResult(classname="tests.test_a", name="test_ok", status="PASSED", duration_seconds=0.01)
    suite_res = QASuiteExecutionResult(
        suite_id="python",
        implemented=True,
        status="PASSED",
        exit_code=0,
        pytest_exit_code=0,
        duration_seconds=0.5,
        counts=counts,
        cases=[case],
    )
    run_res = QARunResult(
        trace_id="qa-test-trace",
        repo_root=str(REPO_ROOT),
        status="PASSED",
        exit_code=0,
        selected_suites=["python"],
        scope_note="Alcance parcial: solo suite python",
        start_utc="2026-10-18T00:00:00Z",
        end_utc="2026-10-18T00:00:01Z",
        duration_seconds=0.5,
        suites=[suite_res],
        cases=[case],
        counts=counts,
        evidence_dir=".agentia-runtime/qa/qa-test-trace",
    )
    assert run_res.status == "PASSED"


def test_ca01_doctor_and_run_without_optional_tools(tmp_path: Path):
    """CA-01: Con Python compatible y sin Node, Java, Maven ni Docker, doctor identifica ausencias y python sigue siendo ejecutable."""
    repo = create_minimal_repo(tmp_path / "repo_ca01")
    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PATH"] = str(empty_bin)

    doc_proc = run_qa_cli(["doctor", "--repo", str(repo), "--json"], env=env)
    assert doc_proc.returncode == 0, f"doctor failed: {doc_proc.stdout}\n{doc_proc.stderr}"
    doc_data = json.loads(doc_proc.stdout)
    report = QADoctorReport.model_validate(doc_data)
    assert report.python_suite_eligible is True
    assert report.status == "PASSED"

    optional_by_name = {c.name: c for c in report.capabilities if not c.required}
    for tool_name in ("node", "npm", "java", "mvn", "docker"):
        assert tool_name in optional_by_name
        assert optional_by_name[tool_name].available is False

    run_proc = run_qa_cli(["run", "--repo", str(repo), "--suite", "python"], env=env)
    assert run_proc.returncode == 0, f"run failed: {run_proc.stdout}\n{run_proc.stderr}"


def test_ca02_missing_required_dependency_explains_and_returns_incomplete(tmp_path: Path):
    """CA-02: Sin pytest o dependencia requerida, doctor explica el requisito y run devuelve ejecución incompleta (4) sin instalar."""
    repo = create_minimal_repo(tmp_path / "repo_ca02")
    env = os.environ.copy()
    env["QA_SIMULATE_MISSING_PACKAGES"] = "pytest,respx"

    doc_proc = run_qa_cli(["doctor", "--repo", str(repo), "--json"], env=env)
    assert doc_proc.returncode == 4
    doc_report = QADoctorReport.model_validate(json.loads(doc_proc.stdout))
    assert doc_report.python_suite_eligible is False
    assert doc_report.status == "INCOMPLETE"
    assert any("pytest" in r or "respx" in r for r in doc_report.reasons)

    run_proc = run_qa_cli(["run", "--repo", str(repo), "--suite", "python"], env=env)
    assert run_proc.returncode == 4
    assert "INCOMPLETE" in run_proc.stdout or "incompleta" in run_proc.stdout.lower()


def test_ca03_external_cwd_absolute_launcher_and_repo_with_spaces(tmp_path: Path):
    """CA-03: Desde otro directorio, ruta absoluta a scripts/qa.py y repo con espacios permiten listar y ejecutar."""
    repo_with_spaces = create_minimal_repo(tmp_path / "carpeta con espacios" / "mi proyecto agentia")
    external_cwd = tmp_path / "directorio externo de ejecucion"
    external_cwd.mkdir(parents=True, exist_ok=True)

    help_proc = run_qa_cli(["--help"], cwd=external_cwd, use_script=True)
    assert help_proc.returncode == 0
    assert "doctor" in help_proc.stdout and "list" in help_proc.stdout and "run" in help_proc.stdout

    list_proc = run_qa_cli(
        ["list", "--repo", str(repo_with_spaces), "--json"],
        cwd=external_cwd,
        use_script=True,
    )
    assert list_proc.returncode == 0, list_proc.stderr
    list_report = QAListReport.model_validate(json.loads(list_proc.stdout))
    suite_map = {s.suite_id: s for s in list_report.suites}
    assert suite_map["python"].implemented is True
    assert suite_map["python"].status == "EXECUTABLE"
    assert any(
        s.status in ("BLOCKED", "NOT_IMPLEMENTED") for s in list_report.suites if s.suite_id != "python"
    )

    run_proc = run_qa_cli(
        ["run", "--repo", str(repo_with_spaces), "--suite", "python"],
        cwd=external_cwd,
        use_script=True,
    )
    assert run_proc.returncode == 0, f"{run_proc.stdout}\n{run_proc.stderr}"


def test_e03_config_precedence_and_invalid_rejection(tmp_path: Path):
    """E03: Precedencia CLI > JSON > defaults y rechazo de claves desconocidas, comandos arbitrarios y opciones de IA."""
    repo = create_minimal_repo(tmp_path / "repo_e03")
    custom_out = repo / ".agentia-runtime" / "custom-qa"
    cfg_file = tmp_path / "valid-qa.json"
    cfg_file.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "suites": ["java"],
                "timeout_seconds": 45,
                "output_dir": ".agentia-runtime/from-json",
            }
        ),
        encoding="utf-8",
    )

    # CLI overrides JSON suite ("java" -> "python"), timeout (45 -> 60) and output_dir
    proc = run_qa_cli(
        [
            "run",
            "--repo",
            str(repo),
            "--config",
            str(cfg_file),
            "--suite",
            "python",
            "--timeout-seconds",
            "60",
            "--output-dir",
            ".agentia-runtime/custom-qa",
        ]
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert custom_out.is_dir()

    # Reject unknown keys / arbitrary command in JSON (exit code 2)
    bad_cfg = tmp_path / "bad-cmd.json"
    bad_cfg.write_text(
        json.dumps({"schema_version": "1.0", "suites": ["python"], "command": "echo hacked"}),
        encoding="utf-8",
    )
    bad_proc = run_qa_cli(["run", "--repo", str(repo), "--config", str(bad_cfg)])
    assert bad_proc.returncode == 2

    # Reject unimplemented AI options in JSON or CLI (exit code 2)
    ai_cfg = tmp_path / "ai-cfg.json"
    ai_cfg.write_text(
        json.dumps({"schema_version": "1.0", "suites": ["python"], "llm_provider": "gemini"}),
        encoding="utf-8",
    )
    ai_proc = run_qa_cli(["run", "--repo", str(repo), "--config", str(ai_cfg)])
    assert ai_proc.returncode == 2

    ai_cli_proc = run_qa_cli(["run", "--repo", str(repo), "--ai-provider", "unsupported_provider"])
    assert ai_cli_proc.returncode == 2


def test_ca04_passing_controlled_suite_produces_artifacts_and_exit_0(controlled_repo: Path):
    """CA-04: Suite controlada aprobada produce casos y duración observados, artefactos válidos y salida 0."""
    proc = run_qa_cli(["run", "--repo", str(controlled_repo), "--suite", "python"])
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"

    qa_root = controlled_repo / ".agentia-runtime" / "qa"
    trace_dirs = [d for d in qa_root.iterdir() if d.is_dir()]
    assert len(trace_dirs) == 1
    ev_dir = trace_dirs[0]

    result_path = ev_dir / "result.json"
    xml_path = ev_dir / "python.junit.xml"
    log_path = ev_dir / "python.log"
    assert result_path.is_file()
    assert xml_path.is_file()
    assert log_path.is_file()

    result = QARunResult.model_validate(json.loads(result_path.read_text(encoding="utf-8")))
    assert result.exit_code == 0
    assert result.status == "PASSED"
    assert result.counts.collected == 2
    assert result.counts.passed == 2
    assert result.counts.failed == 0
    assert result.duration_seconds > 0
    assert len(result.cases) == 2
    assert "python" in result.scope_note.lower()


def test_ca05_failing_assertion_returns_exit_1_with_case_and_diagnosis(tmp_path: Path):
    """CA-05: Aserción fallida produce salida 1 y conserva el nombre del caso y un diagnóstico útil."""
    repo = create_minimal_repo(
        tmp_path / "repo_ca05",
        {
            "test_fail.py": (
                "def test_passes():\n"
                "    assert True\n\n"
                "def test_expected_calculation_failure():\n"
                "    expected_total = 42\n"
                "    actual_total = 19\n"
                "    assert actual_total == expected_total, 'Calculo de saldo inconsistente'\n"
            )
        },
    )
    proc = run_qa_cli(["run", "--repo", str(repo), "--suite", "python"])
    assert proc.returncode == 1

    qa_root = repo / ".agentia-runtime" / "qa"
    ev_dir = next(d for d in qa_root.iterdir() if d.is_dir())
    result = QARunResult.model_validate(json.loads((ev_dir / "result.json").read_text(encoding="utf-8")))
    assert result.status == "FAILED"
    assert result.exit_code == 1
    assert result.counts.passed == 1
    assert result.counts.failed == 1
    failed_cases = [c for c in result.cases if c.status == "FAILED"]
    assert len(failed_cases) == 1
    assert "test_expected_calculation_failure" in failed_cases[0].name
    assert failed_cases[0].message and "Calculo de saldo inconsistente" in failed_cases[0].message


def test_ca06_empty_selection_and_unimplemented_or_unknown_suites(tmp_path: Path):
    """CA-06: Selección vacía o no implementada nunca se informa como aprobada (4); suite desconocida es error de config (2)."""
    empty_repo = create_minimal_repo(tmp_path / "repo_empty", {"test_nothing.py": "# sin funciones test\nx = 1\n"})
    empty_proc = run_qa_cli(["run", "--repo", str(empty_repo), "--suite", "python"])
    assert empty_proc.returncode == 4

    unimpl_proc = run_qa_cli(["run", "--repo", str(empty_repo), "--suite", "java"])
    assert unimpl_proc.returncode == 4

    unknown_proc = run_qa_cli(["run", "--repo", str(empty_repo), "--suite", "cobol_suite"])
    assert unknown_proc.returncode == 2


def test_ca07_collection_error_timeout_and_interruption_cleanup(tmp_path: Path):
    """CA-07: Error de colección y timeout producen 3; interrupción produce 130; no quedan procesos hijos activos."""
    # 1. Collection error -> exit code 3
    broken_repo = create_minimal_repo(
        tmp_path / "repo_broken",
        {"test_syntax.py": "def test_broken(\n    assert True\n"},
    )
    broken_proc = run_qa_cli(["run", "--repo", str(broken_repo), "--suite", "python"])
    assert broken_proc.returncode == 3

    # 2. Timeout with spawned child process -> exit code 3 and child killed
    child_pid_file = tmp_path / "spawned_child.pid"
    slow_repo = create_minimal_repo(
        tmp_path / "repo_slow",
        {
            "test_hang.py": (
                "import subprocess, sys, time\n"
                "from pathlib import Path\n"
                "def test_spawns_and_hangs():\n"
                "    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                f"    Path({str(child_pid_file)!r}).write_text(str(p.pid), encoding='utf-8')\n"
                "    time.sleep(60)\n"
            )
        },
    )
    t_proc = run_qa_cli(["run", "--repo", str(slow_repo), "--suite", "python", "--timeout-seconds", "2"])
    assert t_proc.returncode == 3

    if child_pid_file.is_file():
        child_pid = int(child_pid_file.read_text(encoding="utf-8").strip())
        time.sleep(0.3)
        if os.name == "nt":
            import subprocess as _sp

            chk = _sp.run(
                ["tasklist", "/FI", f"PID eq {child_pid}", "/NH"],
                check=False,
                capture_output=True,
                text=True,
                shell=False,
            )
            assert str(child_pid) not in chk.stdout, f"Child process {child_pid} still alive after timeout!"
        else:
            with pytest.raises(ProcessLookupError):
                os.kill(child_pid, 0)

    # 3. Simulated user interruption -> exit code 130
    int_env = os.environ.copy()
    int_env["QA_SIMULATE_INTERRUPT"] = "1"
    int_proc = run_qa_cli(["run", "--repo", str(broken_repo), "--suite", "python"], env=int_env)
    assert int_proc.returncode == 130


def test_ca08_concurrent_runs_use_distinct_dirs_and_preserve_sentinel(tmp_path: Path):
    """CA-08: Dos ejecuciones simultáneas usan directorios e identificadores distintos y preservan centinela."""
    repo = create_minimal_repo(
        tmp_path / "repo_concurrent",
        {
            "test_concurrent.py": (
                "import time\n"
                "from pathlib import Path\n"
                "def test_writes_local_artifact():\n"
                "    Path('local_side_effect.txt').write_text('isolated', encoding='utf-8')\n"
                "    time.sleep(0.4)\n"
                "    assert Path('sentinel.txt').read_text(encoding='utf-8') == 'SENTINEL_UNTOUCHED'\n"
            )
        },
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(run_qa_cli, ["run", "--repo", str(repo), "--suite", "python"])
        f2 = pool.submit(run_qa_cli, ["run", "--repo", str(repo), "--suite", "python"])
        p1, p2 = f1.result(), f2.result()

    assert p1.returncode == 0, f"{p1.stdout}\n{p1.stderr}"
    assert p2.returncode == 0, f"{p2.stdout}\n{p2.stderr}"
    assert (repo / "sentinel.txt").read_text(encoding="utf-8") == "SENTINEL_UNTOUCHED"
    assert not (repo / "local_side_effect.txt").exists()

    qa_root = repo / ".agentia-runtime" / "qa"
    trace_dirs = [d for d in qa_root.iterdir() if d.is_dir()]
    assert len(trace_dirs) == 2
    r1 = QARunResult.model_validate(json.loads((trace_dirs[0] / "result.json").read_text(encoding="utf-8")))
    r2 = QARunResult.model_validate(json.loads((trace_dirs[1] / "result.json").read_text(encoding="utf-8")))
    assert r1.trace_id != r2.trace_id


def test_ca09_credentials_redacted_in_console_and_artifacts(tmp_path: Path):
    """CA-09: Credenciales ficticias sembradas en variables y mensajes quedan redactadas en consola y artefactos."""
    fake_gemini = "AIzaSyD9FakeSecretKeyForTestingRedaction12345"
    fake_openai = "sk-proj-FakeOpenAISecretTokenValue9876543210abcd"
    fake_custom = "super-secret-custom-token-value-xyz987"

    repo = create_minimal_repo(
        tmp_path / "repo_secrets",
        {
            "test_leak.py": (
                "def test_prints_and_fails_with_secrets():\n"
                f"    print('GEMINI_API_KEY={fake_gemini}')\n"
                f"    print('Authorization: Bearer {fake_openai}')\n"
                f"    assert False, 'Error con api_key={fake_custom} y {fake_gemini}'\n"
            )
        },
    )
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = fake_gemini
    env["OPENAI_API_KEY"] = fake_openai
    env["ORCHESTRATOR_API_KEY"] = fake_custom

    proc = run_qa_cli(["run", "--repo", str(repo), "--suite", "python"], env=env)
    assert proc.returncode == 1

    combined_console = proc.stdout + "\n" + proc.stderr
    for secret in (fake_gemini, fake_openai, fake_custom):
        assert secret not in combined_console, f"Secret {secret} leaked in console output!"

    qa_root = repo / ".agentia-runtime" / "qa"
    ev_dir = next(d for d in qa_root.iterdir() if d.is_dir())
    for fname in ("result.json", "python.junit.xml", "python.log"):
        content = (ev_dir / fname).read_text(encoding="utf-8")
        for secret in (fake_gemini, fake_openai, fake_custom):
            assert secret not in content, f"Secret {secret} leaked in {fname}!"
        assert "[REDACTED]" in content


def test_ca10_corrupt_missing_or_disagreeing_xml_returns_exit_3(tmp_path: Path):
    """CA-10: Desaparecer o corromper el XML, o desacuerdo entre XML y código del proceso, devuelve código 3."""
    repo = create_minimal_repo(tmp_path / "repo_ca10")

    # Simulate corrupt XML post-execution via controlled hook env var
    env_corrupt = os.environ.copy()
    env_corrupt["QA_SIMULATE_XML_ANOMALY"] = "corrupt"
    p_corrupt = run_qa_cli(["run", "--repo", str(repo), "--suite", "python"], env=env_corrupt)
    assert p_corrupt.returncode == 3

    # Simulate missing XML
    env_missing = os.environ.copy()
    env_missing["QA_SIMULATE_XML_ANOMALY"] = "missing"
    p_missing = run_qa_cli(["run", "--repo", str(repo), "--suite", "python"], env=env_missing)
    assert p_missing.returncode == 3

    # Simulate disagreement (process exit 0 but XML claims failure, or process exit 1 but XML claims 0 failures)
    env_disagree = os.environ.copy()
    env_disagree["QA_SIMULATE_XML_ANOMALY"] = "disagree"
    p_disagree = run_qa_cli(["run", "--repo", str(repo), "--suite", "python"], env=env_disagree)
    assert p_disagree.returncode == 3


def test_ca11_skipped_or_xfail_returns_incomplete_4_and_preserves_blocked_when_failed(tmp_path: Path):
    """CA-11: Prueba omitida o xfail mantiene resultado incompleto (4); en combinación con fallo gana FAILED (1) sin ocultar omitidas."""
    repo_skip = create_minimal_repo(
        tmp_path / "repo_skip",
        {
            "test_skip.py": (
                "import pytest\n"
                "def test_ok():\n"
                "    assert True\n\n"
                "@pytest.mark.skip(reason='pendiente de recurso externo')\n"
                "def test_skipped_case():\n"
                "    assert True\n"
            )
        },
    )
    proc_skip = run_qa_cli(["run", "--repo", str(repo_skip), "--suite", "python"])
    assert proc_skip.returncode == 4
    ev_skip = next(d for d in (repo_skip / ".agentia-runtime" / "qa").iterdir() if d.is_dir())
    res_skip = QARunResult.model_validate(json.loads((ev_skip / "result.json").read_text(encoding="utf-8")))
    assert res_skip.status == "INCOMPLETE"
    assert res_skip.counts.passed == 1
    assert res_skip.counts.skipped == 1

    # Combined FAILED + SKIPPED -> status FAILED (1) and skipped count preserved
    repo_combo = create_minimal_repo(
        tmp_path / "repo_combo",
        {
            "test_combo.py": (
                "import pytest\n"
                "def test_fail():\n"
                "    assert 1 == 2\n\n"
                "@pytest.mark.skip(reason='omitida')\n"
                "def test_skip():\n"
                "    assert True\n"
            )
        },
    )
    proc_combo = run_qa_cli(["run", "--repo", str(repo_combo), "--suite", "python"])
    assert proc_combo.returncode == 1
    ev_combo = next(d for d in (repo_combo / ".agentia-runtime" / "qa").iterdir() if d.is_dir())
    res_combo = QARunResult.model_validate(json.loads((ev_combo / "result.json").read_text(encoding="utf-8")))
    assert res_combo.status == "FAILED"
    assert res_combo.counts.failed == 1
    assert res_combo.counts.skipped == 1
    assert any(c.status == "SKIPPED" for c in res_combo.cases)


def _is_pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import subprocess as _sp

        chk = _sp.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
        )
        return str(pid) in chk.stdout
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def test_f01_internally_contradictory_xml_counts_and_skipped_returns_exit_3(tmp_path: Path):
    """F01 (CA-10 / RF-07 / RF-11): Un XML sintácticamente válido pero internamente contradictorio devuelve código 3 (ERROR)."""
    repo = create_minimal_repo(
        tmp_path / "repo_f01",
        {"test_ok.py": "def test_ok():\n    assert True\n"},
    )
    # Hook en conftest del fixture que altera tests="2" y skipped="1" manteniendo un solo testcase aprobado
    (repo / "tests" / "conftest.py").write_text(
        "import xml.etree.ElementTree as ET\n"
        "from pathlib import Path\n"
        "def pytest_unconfigure(config):\n"
        "    xmlpath = getattr(config.option, 'xmlpath', None)\n"
        "    if xmlpath and Path(xmlpath).exists():\n"
        "        tree = ET.parse(xmlpath)\n"
        "        root = tree.getroot()\n"
        "        suite = root.find('testsuite') if root.tag == 'testsuites' else root\n"
        "        if suite is not None:\n"
        "            suite.set('tests', '2')\n"
        "            suite.set('skipped', '1')\n"
        "            tree.write(xmlpath, encoding='utf-8', xml_declaration=True)\n",
        encoding="utf-8",
    )

    proc = run_qa_cli(["run", "--repo", str(repo), "--suite", "python", "--json"])
    assert proc.returncode == 3, f"Expected exit 3 for contradictory XML, got {proc.returncode}: {proc.stdout}"
    data = QARunResult.model_validate(json.loads(proc.stdout))
    assert data.status == "ERROR"
    assert data.exit_code == 3


def test_f02_exited_parent_leaves_no_orphan_descendants_on_timeout_or_interrupt(tmp_path: Path):
    """F02 (CA-07 / RF-08): Si el proceso padre termina antes que un hijo con pipes heredados, el timeout o interrupción real mata al descendiente."""
    import sys as _sys

    from qa_agent.execution import run_bounded_subprocess

    # 1. Padre crea hijo de 20 s y termina inmediatamente; el hijo retiene los pipes hasta el timeout
    child_pid_file = tmp_path / "orphan_child.pid"
    parent_code = (
        "import subprocess, sys\n"
        "from pathlib import Path\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
        f"Path({str(child_pid_file)!r}).write_text(str(child.pid), encoding='utf-8')\n"
        "sys.exit(0)\n"
    )
    outcome = run_bounded_subprocess(
        argv=[_sys.executable, "-c", parent_code],
        cwd=tmp_path,
        env=os.environ.copy(),
        timeout_seconds=1,
    )
    assert outcome.timed_out is True
    assert child_pid_file.is_file(), "El proceso padre no llegó a registrar el PID del hijo"
    orphan_pid = int(child_pid_file.read_text(encoding="utf-8").strip())
    try:
        time.sleep(0.2)
        assert not _is_pid_alive(orphan_pid), f"El proceso descendiente {orphan_pid} quedó vivo tras finalizar su padre y vencer el timeout"
    finally:
        if _is_pid_alive(orphan_pid) and os.name == "nt":
            import subprocess as _sp

            _sp.run(["taskkill", "/F", "/T", "/PID", str(orphan_pid)], check=False, capture_output=True)

    # 2. Interrupción real con procesos activos (padre + hijo vivos cuando ocurre la interrupción)
    int_child_pid_file = tmp_path / "interrupt_child.pid"
    int_parent_code = (
        "import subprocess, sys, time\n"
        "from pathlib import Path\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
        f"Path({str(int_child_pid_file)!r}).write_text(str(child.pid), encoding='utf-8')\n"
        "time.sleep(20)\n"
    )
    int_env = os.environ.copy()
    int_env["QA_INTERRUPT_AFTER_SECONDS"] = "0.5"
    int_outcome = run_bounded_subprocess(
        argv=[_sys.executable, "-c", int_parent_code],
        cwd=tmp_path,
        env=int_env,
        timeout_seconds=10,
    )
    assert int_outcome.interrupted is True
    assert int_child_pid_file.is_file(), "El proceso padre no registró el PID del hijo antes de la interrupción"
    int_child_pid = int(int_child_pid_file.read_text(encoding="utf-8").strip())
    try:
        time.sleep(0.2)
        assert not _is_pid_alive(int_child_pid), f"El proceso hijo {int_child_pid} siguió vivo tras interrupción real"
    finally:
        if _is_pid_alive(int_child_pid) and os.name == "nt":
            import subprocess as _sp

            _sp.run(["taskkill", "/F", "/T", "/PID", str(int_child_pid)], check=False, capture_output=True)


def test_f03_snapshot_copy_failure_cleans_scratch_and_persists_error_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """F03 (RF-09 / RF-10): Un fallo durante prepare_isolated_workspace limpia el scratch creado y persiste result.json con código 3."""
    import shutil as _shutil
    import tempfile as _tempfile

    from qa_agent.cli import main as qa_main
    from qa_agent.execution import prepare_isolated_workspace

    repo = create_minimal_repo(tmp_path / "repo_f03")
    external_sentinel = tmp_path / "external_sentinel.txt"
    external_sentinel.write_text("KEEP_EXTERNAL", encoding="utf-8")

    temp_root = Path(_tempfile.gettempdir())
    trace_unit = "qa-f03-unit-probe"

    def _failing_copy2(src, dst, *args, **kwargs):
        raise PermissionError("Fallo simulado de copia en snapshot")

    monkeypatch.setattr(_shutil, "copy2", _failing_copy2)

    with pytest.raises(PermissionError):
        prepare_isolated_workspace(repo_root=repo, trace_id=trace_unit)

    leftover = list(temp_root.glob(f"agentia-{trace_unit}-*"))
    assert len(leftover) == 0, f"Quedaron directorios scratch tras error de copia: {leftover}"
    assert external_sentinel.read_text(encoding="utf-8") == "KEEP_EXTERNAL"

    # Ahora verificar por CLI completa que se emite código 3 y se persiste result.json en output_dir/<trace_id>/
    before_scratches = set(temp_root.glob("agentia-qa-*"))
    exit_code = qa_main(["run", "--repo", str(repo), "--suite", "python"])
    after_scratches = set(temp_root.glob("agentia-qa-*"))
    assert exit_code == 3
    assert after_scratches - before_scratches == set(), "Quedó scratch huérfano tras fallo en CLI run"

    qa_root = repo / ".agentia-runtime" / "qa"
    assert qa_root.is_dir(), "No se creó el directorio de evidencia tras error de snapshot"
    result_files = list(qa_root.glob("*/result.json"))
    assert len(result_files) == 1, f"Se esperaba 1 result.json, se encontraron {len(result_files)}"
    err_result = QARunResult.model_validate(json.loads(result_files[0].read_text(encoding="utf-8")))
    assert err_result.status == "ERROR"
    assert err_result.exit_code == 3
    assert err_result.trace_id == result_files[0].parent.name
    assert (result_files[0].parent / "python.log").is_file()


def test_f04_bounded_stream_capture_limits_buffer_during_read(tmp_path: Path):
    """F04 (E05): La captura de salida drena stdout y stderr concurrentemente con buffers acotados durante la lectura."""
    import sys as _sys

    from qa_agent.execution import run_bounded_subprocess

    noisy_code = (
        "import sys\n"
        "for _ in range(250):\n"
        "    sys.stdout.write('A' * 400 + '\\n')\n"
        "    sys.stderr.write('B' * 200 + '\\n')\n"
        "sys.stdout.flush()\n"
        "sys.stderr.flush()\n"
    )
    outcome = run_bounded_subprocess(
        argv=[_sys.executable, "-c", noisy_code],
        cwd=tmp_path,
        env=os.environ.copy(),
        timeout_seconds=15,
        max_capture_chars=4096,
    )
    assert outcome.exit_code == 0
    assert outcome.timed_out is False
    assert outcome.output_truncated is True
    assert len(outcome.stdout) == 4096
    assert len(outcome.stderr) == 4096

