from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from qa_agent import (
    EXIT_EXECUTION_ERROR,
    EXIT_INCOMPLETE,
    EXIT_INTERRUPTED,
    EXIT_PASSED,
    EXIT_PRODUCT_FAIL,
)
from qa_agent.adapters.frontend import materialize_directory_copy
from qa_agent.capabilities import resolve_toolchain_binary
from qa_agent.evidence import build_bounded_log, summarize_diagnostic_text
from qa_agent.execution import (
    IsolatedWorkspace,
    cleanup_isolated_workspace,
    prepare_isolated_workspace,
    run_bounded_subprocess,
)
from qa_agent.result_normalization import (
    validate_and_parse_json_report,
    validate_and_parse_junit_xml,
)
from qa_agent.service_harness import (
    ManagedDaemonProcess,
    PlatformServiceHarness,
    allocate_loopback_ports,
    wait_for_http_health,
)

PLAYWRIGHT_ENGINE = "playwright+chromium"


def run_playwright_suite(
    repo_root: Path,
    trace_id: str,
    timeout_seconds: int = 600,
    java_cache_dir: Path | None = None,
    browser_cache_dir: Path | None = None,
    extra_secrets: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, str], str | None, str, str]:
    """
    Ejecuta la suite `playwright` (Trabajo 5, U04–U07):
    - Comprueba disponibilidad de Node.js, Chromium en caché offline (`browser-cache`) y runner Playwright.
    - Rechaza descargas por red de navegadores en caliente (AC-11, RF-309).
    - Despliega un sandbox aislado con el backend multi-servicio y el servidor frontend en loopback.
    - Ejecuta Chromium sin sesiones de demostración (`AC-14`), validando generación real y descarga de ZIP (`AC-15`).
    - Valida controles negativos: autenticación inválida 401 y caída de backend visibles (`AC-16`).
    - Recolecta reportes JUnit XML y JSON normalizados con 1 worker y 0 retries (`RF-310/312`).
    """
    suite_t0 = time.perf_counter()
    steps: list[dict[str, Any]] = []
    artifacts: dict[str, str] = {}
    reasons: list[str] = []

    # 1. Comprobación estricta de binarios y dependencias (U01 / AC-11)
    node_bin = resolve_toolchain_binary("node", repo_root)
    src_node_modules = repo_root / "frontend" / "node_modules"
    pw_cli_rel = Path("node_modules") / "@playwright" / "test" / "cli.js"

    eff_browser_cache = browser_cache_dir or (repo_root / ".agentia-runtime" / "browser-cache")

    if not node_bin:
        reason = "Falta el binario 'node' en PATH o toolchains para ejecutar la suite 'playwright'."
        return _make_incomplete_result(reason), {}, None, reason, ""

    if not (src_node_modules / "@playwright" / "test" / "cli.js").is_file():
        reason = "Falta el paquete '@playwright/test' en 'frontend/node_modules'; no se permiten descargas de paquetes durante la ejecución."
        return _make_incomplete_result(reason), {}, None, reason, ""

    if not eff_browser_cache.is_dir():
        reason = f"No existe el directorio de caché de navegadores Playwright: {eff_browser_cache}."
        return _make_incomplete_result(reason), {}, None, reason, ""

    has_chromium = any(
        p.is_dir() and p.name.startswith("chromium-") for p in eff_browser_cache.iterdir()
    ) if eff_browser_cache.is_dir() else False

    if not has_chromium:
        reason = (
            f"No se encontró el navegador Chromium en la caché offline {eff_browser_cache}. "
            "La suite 'playwright' no descarga navegadores en tiempo de ejecución (RF-309, AC-11)."
        )
        return _make_incomplete_result(reason), {}, None, reason, ""

    workspace: IsolatedWorkspace | None = None
    harness: PlatformServiceHarness | None = None
    fe_proc: ManagedDaemonProcess | None = None

    try:
        # 2. Preparar workspace aislado (U04)
        workspace = prepare_isolated_workspace(
            repo_root=repo_root,
            trace_id=f"{trace_id}-pw",
            suite_id="playwright",
        )
        fe_dir = workspace.repo_copy / "frontend"
        dst_node_modules = fe_dir / "node_modules"

        prep_dur, prep_bytes = materialize_directory_copy(src_node_modules, dst_node_modules)
        steps.append(
            {
                "step_id": "playwright-prepare-frontend-deps",
                "kind": "prepare",
                "status": "PASSED",
                "exit_code": 0,
                "duration_seconds": prep_dur,
                "command": ["materialize_directory_copy", "frontend/node_modules"],
                "diagnostic": f"Copiados {prep_bytes} bytes en {prep_dur:.3f}s",
            }
        )

        # 3. Lanzar backend multi-proceso (modo java obligatorio con Maven real; prohibido fallback a platform según R01)
        eff_java_cache = java_cache_dir or (repo_root / ".agentia-runtime" / "java-cache")
        has_quarkus_cache = (
            eff_java_cache.is_dir()
            and (
                (eff_java_cache / "repository" / "io" / "quarkus").is_dir()
                or (eff_java_cache / "io" / "quarkus").is_dir()
            )
        )
        java_bin = resolve_toolchain_binary("java", repo_root, workspace.env.get("PATH"))
        mvn_bin = resolve_toolchain_binary("mvn", repo_root, workspace.env.get("PATH"))

        if not has_quarkus_cache or not java_bin or not mvn_bin:
            missing_items = []
            if not has_quarkus_cache:
                missing_items.append(f"caché offline Quarkus en '{eff_java_cache}'")
            if not java_bin:
                missing_items.append("binario 'java' (JDK 21)")
            if not mvn_bin:
                missing_items.append("binario 'mvn' (Maven 3.9+)")
            req_reason = (
                f"Playwright E2E requiere backend verificado real con compilador Maven. "
                f"Faltan requisitos: {', '.join(missing_items)}. Fallback a 'platform' prohibido (R01)."
            )
            return (
                _make_incomplete_result(req_reason),
                artifacts,
                None,
                req_reason,
                "",
            )

        backend_mode = "java"
        java_bin_dir = str(Path(java_bin).resolve().parent)
        mvn_bin_dir = str(Path(mvn_bin).resolve().parent)
        base_p = workspace.env.get("PATH", "")
        extra_backend_env = dict(workspace.env)
        extra_backend_env["JAVA_HOME"] = str(Path(java_bin_dir).parent)
        extra_backend_env["PATH"] = f"{java_bin_dir}{os.pathsep}{mvn_bin_dir}{os.pathsep}{base_p}"
        m2_copy = workspace.scratch_root / "m2"
        m2_timeout = max(5.0, timeout_seconds - (time.perf_counter() - suite_t0))
        materialize_directory_copy(eff_java_cache, m2_copy, timeout_seconds=m2_timeout)
        extra_backend_env["VERIFIER_COMMAND"] = (
            f"mvn test -o -B -nsu -Dmaven.repo.local={m2_copy} "
            "-Dquarkus.http.test-port=0 -Dquarkus.http.port=0 "
            "-Dquarkus.datasource.devservices.enabled=false -Dquarkus.kafka.devservices.enabled=false"
        )

        harness_t0 = time.perf_counter()
        harness = PlatformServiceHarness(
            repo_root=workspace.repo_copy,
            harness_root=workspace.scratch_root / "pwh",
            mode=backend_mode,
            extra_env=extra_backend_env,
        )
        harness.start(startup_timeout_seconds=25.0)
        harness_dur = round(time.perf_counter() - harness_t0, 4)
        steps.append(
            {
                "step_id": "playwright-launch-backend",
                "kind": "prepare",
                "status": "PASSED",
                "exit_code": 0,
                "duration_seconds": harness_dur,
                "command": ["start_service_harness", f"mode={backend_mode}", "compiler=maven-real"],
                "diagnostic": f"Servicios HTTP loopback iniciados con Maven real (orquestador={harness.orchestrator_url})",
            }
        )

        # 4. Lanzar frontend en puerto efímero con proxy apuntando al backend del harness
        fe_port = allocate_loopback_ports(1)[0]
        vite_js = dst_node_modules / "vite" / "bin" / "vite.js"
        fe_env = dict(workspace.env)
        fe_env["BACKEND_URL"] = harness.orchestrator_url
        fe_env["VITE_BACKEND_URL"] = harness.orchestrator_url
        fe_env["PORT"] = str(fe_port)

        fe_argv = [
            node_bin,
            str(vite_js),
            "--port",
            str(fe_port),
            "--host",
            "127.0.0.1",
            "--strictPort",
        ]
        fe_t0 = time.perf_counter()
        fe_proc = ManagedDaemonProcess(
            name=f"qa-fe-vite-{fe_port}",
            argv=fe_argv,
            cwd=fe_dir,
            env=fe_env,
        )
        fe_proc.start()
        wait_for_http_health(
            url=f"http://127.0.0.1:{fe_port}/",
            proc=fe_proc,
            timeout_seconds=20.0,
        )
        fe_dur = round(time.perf_counter() - fe_t0, 4)
        steps.append(
            {
                "step_id": "playwright-launch-frontend",
                "kind": "prepare",
                "status": "PASSED",
                "exit_code": 0,
                "duration_seconds": fe_dur,
                "command": ["vite", f"--port={fe_port}"],
                "diagnostic": f"Frontend Vite disponible en http://127.0.0.1:{fe_port}/",
            }
        )

        # 5. Ejecutar Playwright en modo hermético (1 worker, 0 retries, Chromium offline)
        raw_junit = workspace.scratch_root / "playwright.junit.xml"
        raw_json = workspace.scratch_root / "playwright.report.json"
        test_results_dir = workspace.scratch_root / "playwright-results"
        test_results_dir.mkdir(parents=True, exist_ok=True)

        pw_env = dict(workspace.env)
        pw_env["PLAYWRIGHT_BROWSERS_PATH"] = str(eff_browser_cache.resolve())
        pw_env["PLAYWRIGHT_BASE_URL"] = f"http://127.0.0.1:{fe_port}"
        pw_env["BACKEND_URL"] = harness.orchestrator_url
        pw_env["ORCHESTRATOR_API_KEY"] = harness.orchestrator_api_key
        pw_env["PLAYWRIGHT_JUNIT_OUTPUT_NAME"] = str(raw_junit)
        pw_env["PLAYWRIGHT_JSON_OUTPUT_NAME"] = str(raw_json)
        pw_env["PLAYWRIGHT_OUTPUT_DIR"] = str(test_results_dir)
        pw_env["CI"] = "1"

        pw_cli_path = dst_node_modules / "@playwright" / "test" / "cli.js"
        pw_argv = [
            node_bin,
            str(pw_cli_path),
            "test",
            "--config=playwright.config.ts",
            "--workers=1",
            "--retries=0",
        ]

        rem_timeout = int(timeout_seconds - (time.perf_counter() - suite_t0))
        if rem_timeout <= 0:
            steps.append(
                {
                    "step_id": "playwright-test",
                    "kind": "test",
                    "status": "ERROR",
                    "exit_code": None,
                    "duration_seconds": 0.0,
                    "command": ["playwright", "test", "--workers=1", "--retries=0"],
                    "diagnostic": "Presupuesto de tiempo global agotado antes de ejecutar Playwright",
                }
            )
            return (
                {
                    "suite_id": "playwright",
                    "implemented": True,
                    "status": "ERROR",
                    "exit_code": EXIT_EXECUTION_ERROR,
                    "engine": PLAYWRIGHT_ENGINE,
                    "process_exit_code": None,
                    "pytest_exit_code": None,
                    "timed_out": True,
                    "interrupted": False,
                    "output_truncated": False,
                    "duration_seconds": round(time.perf_counter() - suite_t0, 4),
                    "counts": {"collected": 0, "passed": 0, "failed": 0, "errors": 1, "skipped": 0, "xfail": 0},
                    "cases": [],
                    "steps": steps,
                    "reasons": ["Presupuesto de tiempo global agotado antes de iniciar Playwright."],
                    "evidence_files": {},
                },
                artifacts,
                None,
                "",
                "Timeout global agotado.",
            )

        pw_min_mtime = time.time() - 1.0

        pw_outcome = run_bounded_subprocess(
            argv=pw_argv,
            cwd=fe_dir,
            env=pw_env,
            timeout_seconds=rem_timeout,
        )

        pw_log, pw_trunc = build_bounded_log(
            pw_outcome.stdout, pw_outcome.stderr, extra_secrets=extra_secrets
        )
        artifacts["playwright.log"] = pw_log

        # R09: Recolectar adjuntos de fallo (screenshots, traces, etc.) antes de cleanup del workspace
        if test_results_dir.is_dir():
            for att_file in test_results_dir.rglob("*"):
                if att_file.is_file():
                    rel_name = att_file.relative_to(test_results_dir).as_posix()
                    art_key = f"playwright-results/{rel_name}"
                    try:
                        if att_file.suffix.lower() in (".txt", ".log", ".json", ".xml", ".html", ".md"):
                            artifacts[art_key] = att_file.read_text(encoding="utf-8", errors="replace")
                        else:
                            artifacts[art_key] = att_file.read_bytes()
                    except Exception:
                        pass

        # 6. Parseo y normalización de resultados (JUnit XML + JSON)
        xml_norm = validate_and_parse_junit_xml(
            xml_path=raw_junit,
            suite_id="playwright",
            engine=PLAYWRIGHT_ENGINE,
            process_exit_code=pw_outcome.exit_code or 0,
            dialect="playwright",
            min_mtime=pw_min_mtime,
            extra_secrets=extra_secrets,
            strict_all_attrs=False,
        )
        if xml_norm.get("sanitized_xml"):
            artifacts["playwright.junit.xml"] = str(xml_norm["sanitized_xml"])

        json_norm = validate_and_parse_json_report(
            json_path=raw_json,
            dialect="playwright",
            suite_id="playwright",
            engine=PLAYWRIGHT_ENGINE,
            process_exit_code=pw_outcome.exit_code or 0,
            min_mtime=pw_min_mtime,
            extra_secrets=extra_secrets,
        )
        if json_norm.get("sanitized_json"):
            artifacts["playwright.report.json"] = str(json_norm["sanitized_json"])

        step_diag = summarize_diagnostic_text(
            f"{pw_outcome.stdout}\n{pw_outcome.stderr}",
            xml_norm.get("reasons", []) + json_norm.get("reasons", []),
        )

        steps.append(
            {
                "step_id": "playwright-test",
                "kind": "test",
                "status": "PASSED" if pw_outcome.exit_code == 0 else "FAILED",
                "exit_code": pw_outcome.exit_code,
                "duration_seconds": pw_outcome.duration_seconds,
                "command": ["playwright", "test", "--workers=1", "--retries=0"],
                "diagnostic": step_diag,
            }
        )

        # 7. Determinar veredicto de la suite
        has_exec_err = False
        has_prod_fail = False
        has_incomplete = False

        if pw_outcome.timed_out:
            has_exec_err = True
            reasons.append(f"Timeout de Playwright superado ({rem_timeout}s).")
        elif pw_outcome.interrupted:
            return (
                _make_interrupted_result(round(time.perf_counter() - suite_t0, 4)),
                artifacts,
                None,
                pw_outcome.stdout,
                pw_outcome.stderr,
            )

        if xml_norm.get("status") == "ERROR":
            has_exec_err = True
            reasons.extend(xml_norm.get("reasons", []))
        elif xml_norm.get("status") == "FAILED":
            has_prod_fail = True
            reasons.extend(xml_norm.get("reasons", []))
        elif xml_norm.get("status") == "INCOMPLETE":
            has_incomplete = True
            reasons.extend(xml_norm.get("reasons", []))

        if json_norm.get("status") == "ERROR":
            has_exec_err = True
            reasons.extend(json_norm.get("reasons", []))
        elif json_norm.get("status") == "INCOMPLETE":
            has_incomplete = True
            reasons.extend(json_norm.get("reasons", []))

        # R02: Si se recolectaron 0 casos o hubo skipped > 0, clasificar como INCOMPLETE
        counts = xml_norm.get("counts", {})
        if counts.get("collected", 0) == 0:
            has_incomplete = True
            reasons.append("La suite 'playwright' no recolectó ningún caso de prueba (collected=0).")
        if counts.get("skipped", 0) > 0:
            has_incomplete = True
            reasons.append(f"La suite 'playwright' tiene casos omitidos (skipped={counts['skipped']}).")

        # R02: Verificar concordancia estricta F01 entre reportes en todas las categorías
        if xml_norm.get("counts") and json_norm.get("counts"):
            xc = xml_norm["counts"]
            jc = json_norm["counts"]
            mismatches = []
            for k in ("collected", "passed", "failed", "errors", "skipped", "xfail"):
                if xc.get(k, 0) != jc.get(k, 0):
                    mismatches.append(f"{k} (XML={xc.get(k, 0)} vs JSON={jc.get(k, 0)})")
            if mismatches:
                mismatch_msg = (
                    f"Discrepancia F01 entre JUnit XML y JSON report de Playwright: {', '.join(mismatches)}."
                )
                has_exec_err = True
                reasons.append(mismatch_msg)

        reasons.append(
            "Fronteras de ejecución playwright: http=real, compiler=maven-real, browser=chromium-real."
        )

        if has_exec_err:
            final_status = "ERROR"
            final_rc = EXIT_EXECUTION_ERROR
        elif has_incomplete:
            final_status = "INCOMPLETE"
            final_rc = EXIT_INCOMPLETE
        elif has_prod_fail or (pw_outcome.exit_code not in (0, None)):
            final_status = "FAILED"
            final_rc = EXIT_PRODUCT_FAIL
        else:
            final_status = "PASSED"
            final_rc = EXIT_PASSED

        suite_result = {
            "suite_id": "playwright",
            "implemented": True,
            "status": final_status,
            "exit_code": final_rc,
            "engine": PLAYWRIGHT_ENGINE,
            "process_exit_code": pw_outcome.exit_code,
            "pytest_exit_code": None,
            "timed_out": pw_outcome.timed_out,
            "interrupted": pw_outcome.interrupted,
            "output_truncated": pw_outcome.output_truncated or pw_trunc,
            "duration_seconds": round(time.perf_counter() - suite_t0, 4),
            "counts": xml_norm["counts"],
            "cases": xml_norm["cases"],
            "steps": steps,
            "reasons": reasons,
            "evidence_files": {},
        }
        return (
            suite_result,
            artifacts,
            None,
            pw_outcome.stdout,
            pw_outcome.stderr,
        )

    except KeyboardInterrupt:
        dur = round(time.perf_counter() - suite_t0, 4)
        return _make_interrupted_result(dur), artifacts, None, "", "Interrumpido por el usuario."
    except Exception as exc:
        dur = round(time.perf_counter() - suite_t0, 4)
        err_reason = f"Error no controlado al ejecutar la suite 'playwright': {type(exc).__name__}: {exc}"
        return (
            {
                "suite_id": "playwright",
                "implemented": True,
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "engine": PLAYWRIGHT_ENGINE,
                "process_exit_code": None,
                "pytest_exit_code": None,
                "timed_out": False,
                "interrupted": False,
                "output_truncated": False,
                "duration_seconds": dur,
                "counts": {"collected": 0, "passed": 0, "failed": 0, "errors": 1, "skipped": 0, "xfail": 0},
                "cases": [],
                "steps": steps,
                "reasons": [err_reason],
                "evidence_files": {},
            },
            artifacts,
            None,
            "",
            err_reason,
        )
    finally:
        if fe_proc is not None:
            fe_proc.stop()
        if harness is not None:
            harness.stop()
        if workspace is not None:
            cleanup_isolated_workspace(workspace=workspace, user_repo_root=repo_root)


def _make_incomplete_result(reason: str) -> dict[str, Any]:
    return {
        "suite_id": "playwright",
        "implemented": True,
        "status": "INCOMPLETE",
        "exit_code": EXIT_INCOMPLETE,
        "engine": PLAYWRIGHT_ENGINE,
        "process_exit_code": None,
        "pytest_exit_code": None,
        "timed_out": False,
        "interrupted": False,
        "output_truncated": False,
        "duration_seconds": 0.0,
        "counts": {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0},
        "cases": [],
        "steps": [],
        "reasons": [reason],
        "evidence_files": {},
    }


def _make_interrupted_result(dur: float) -> dict[str, Any]:
    return {
        "suite_id": "playwright",
        "implemented": True,
        "status": "INTERRUPTED",
        "exit_code": EXIT_INTERRUPTED,
        "engine": PLAYWRIGHT_ENGINE,
        "process_exit_code": None,
        "pytest_exit_code": None,
        "timed_out": False,
        "interrupted": True,
        "output_truncated": False,
        "duration_seconds": dur,
        "counts": {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0},
        "cases": [],
        "steps": [],
        "reasons": ["Ejecución de la suite 'playwright' interrumpida."],
        "evidence_files": {},
    }
