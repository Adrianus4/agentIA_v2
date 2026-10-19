from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from qa_agent import (
    EXIT_EXECUTION_ERROR,
    EXIT_INCOMPLETE,
    EXIT_INTERRUPTED,
    EXIT_PRODUCT_FAIL,
)
from qa_agent.capabilities import resolve_toolchain_binary
from qa_agent.evidence import build_bounded_log
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

FRONTEND_ENGINE = "vitest+tsc+vite"


def materialize_directory_copy(
    src_dir: Path,
    dst_dir: Path,
    timeout_seconds: float = 180.0,
) -> tuple[float, int]:
    """
    Materializa una copia de dependencias (`node_modules` o caché Maven) en el scratch sin modificar el origen,
    sin requerir privilegios de symlink/junction, y registrando duración y bytes copiados (RF-312, C05).
    """
    t0 = time.perf_counter()
    if os.environ.get("QA_SIMULATE_DEPS_COPY_FAILURE") == "1":
        raise OSError("Fallo simulado al materializar dependencias en el directorio scratch.")

    if not src_dir.is_dir():
        raise FileNotFoundError(f"El directorio de dependencias de origen no existe: {src_dir}")

    dst_dir.parent.mkdir(parents=True, exist_ok=True)
    eff_timeout = max(5, int(timeout_seconds))
    if os.name == "nt" and shutil.which("robocopy"):
        proc = subprocess.run(
            [
                "robocopy",
                str(src_dir),
                str(dst_dir),
                "/E",
                "/NFL",
                "/NDL",
                "/NJH",
                "/NJS",
                "/NC",
                "/NS",
                "/NP",
                "/MT:16",
                "/R:1",
                "/W:1",
            ],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=eff_timeout,
        )
        # En robocopy, códigos 0..7 indican éxito / archivos copiados; >= 8 indica error.
        if proc.returncode >= 8:
            raise OSError(
                f"Error de robocopy (exit={proc.returncode}) al copiar {src_dir} -> {dst_dir}: {proc.stderr or proc.stdout}"
            )
    else:
        shutil.copytree(src_dir, dst_dir, symlinks=True, dirs_exist_ok=True)

    if not dst_dir.is_dir():
        raise OSError(f"El directorio destino no fue creado tras la copia: {dst_dir}")

    total_bytes = 0
    for f in dst_dir.rglob("*"):
        if f.is_file() and not f.is_symlink():
            try:
                total_bytes += f.stat().st_size
            except OSError:
                pass
    duration = round(time.perf_counter() - t0, 4)
    return duration, total_bytes


def run_frontend_suite(
    repo_root: Path,
    trace_id: str,
    timeout_seconds: int = 300,
    extra_secrets: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, str], str | None, str, str]:
    """
    Ejecuta la suite `frontend` (Trabajo 5, U03):
    1. Materializa `frontend/node_modules` en el workspace aislado.
    2. Ejecuta Vitest mediante Node (sin npm.cmd ni npx) generando JUnit XML y JSON.
    3. Valida ambos reportes y verifica que sus conteos coincidan (F01).
    4. Ejecuta `tsc -b` y `vite build` como pasos separados (`QASuiteStepResult`) sin inflar `counts.collected`.
    """
    node_bin = resolve_toolchain_binary("node", repo_root)
    src_node_modules = repo_root / "frontend" / "node_modules"
    vitest_rel = Path("node_modules") / "vitest" / "vitest.mjs"
    tsc_rel = Path("node_modules") / "typescript" / "bin" / "tsc"
    vite_rel = Path("node_modules") / "vite" / "bin" / "vite.js"

    missing_bins: list[str] = []
    if not node_bin:
        missing_bins.append("binario 'node'")
    if not (src_node_modules / "vitest" / "vitest.mjs").is_file():
        missing_bins.append("'frontend/node_modules/vitest/vitest.mjs'")
    if not (src_node_modules / "typescript" / "bin" / "tsc").is_file():
        missing_bins.append("'frontend/node_modules/typescript/bin/tsc'")
    if not (src_node_modules / "vite" / "bin" / "vite.js").is_file():
        missing_bins.append("'frontend/node_modules/vite/bin/vite.js'")

    if missing_bins:
        reason = f"Faltan dependencias o binarios CLI para la suite 'frontend': {', '.join(missing_bins)}."
        return (
            {
                "suite_id": "frontend",
                "implemented": True,
                "status": "INCOMPLETE",
                "exit_code": EXIT_INCOMPLETE,
                "engine": FRONTEND_ENGINE,
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
            },
            {},
            None,
            reason,
            "",
        )

    workspace: IsolatedWorkspace | None = None
    suite_t0 = time.perf_counter()
    try:
        workspace = prepare_isolated_workspace(
            repo_root=repo_root,
            trace_id=f"{trace_id}-frontend",
            suite_id="frontend",
        )
        fe_dir = workspace.repo_copy / "frontend"
        dst_node_modules = fe_dir / "node_modules"

        prep_dur, prep_bytes = materialize_directory_copy(src_node_modules, dst_node_modules)
        steps: list[dict[str, Any]] = [
            {
                "step_id": "frontend-prepare-node-modules",
                "kind": "prepare",
                "status": "PASSED",
                "exit_code": 0,
                "duration_seconds": prep_dur,
                "command": ["materialize_directory_copy", "frontend/node_modules"],
                "diagnostic": f"Copiados {prep_bytes} bytes en {prep_dur:.3f}s",
            }
        ]

        raw_junit = workspace.scratch_root / "vitest.junit.xml"
        raw_json = workspace.scratch_root / "vitest.report.json"

        vitest_argv = [
            node_bin,
            str(fe_dir / vitest_rel),
            "run",
            "--reporter=default",
            "--reporter=junit",
            "--reporter=json",
            f"--outputFile.junit={raw_junit}",
            f"--outputFile.json={raw_json}",
        ]
        min_mtime = time.time() - 1.0
        remaining_budget = max(5, int(timeout_seconds - (time.perf_counter() - suite_t0)))
        vt_outcome = run_bounded_subprocess(
            argv=vitest_argv,
            cwd=fe_dir,
            env=dict(workspace.env),
            timeout_seconds=remaining_budget,
        )

        if vt_outcome.interrupted:
            return (
                {
                    "suite_id": "frontend",
                    "implemented": True,
                    "status": "INTERRUPTED",
                    "exit_code": EXIT_INTERRUPTED,
                    "engine": FRONTEND_ENGINE,
                    "process_exit_code": None,
                    "pytest_exit_code": None,
                    "timed_out": False,
                    "interrupted": True,
                    "output_truncated": vt_outcome.output_truncated,
                    "duration_seconds": round(time.perf_counter() - suite_t0, 4),
                    "counts": {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0},
                    "cases": [],
                    "steps": steps,
                    "reasons": ["Ejecución de Vitest interrumpida por el usuario."],
                    "evidence_files": {},
                },
                {},
                None,
                vt_outcome.stdout,
                vt_outcome.stderr,
            )

        if vt_outcome.timed_out:
            reason = f"El paso Vitest de la suite 'frontend' excedió el presupuesto ({remaining_budget}s)."
            vt_log, _ = build_bounded_log(vt_outcome.stdout, vt_outcome.stderr, extra_secrets=extra_secrets)
            steps.append(
                {
                    "step_id": "frontend-vitest",
                    "kind": "test",
                    "status": "ERROR",
                    "exit_code": None,
                    "duration_seconds": vt_outcome.duration_seconds,
                    "command": ["node", "node_modules/vitest/vitest.mjs", "run"],
                    "diagnostic": reason,
                }
            )
            return (
                {
                    "suite_id": "frontend",
                    "implemented": True,
                    "status": "ERROR",
                    "exit_code": EXIT_EXECUTION_ERROR,
                    "engine": FRONTEND_ENGINE,
                    "process_exit_code": None,
                    "pytest_exit_code": None,
                    "timed_out": True,
                    "interrupted": False,
                    "output_truncated": vt_outcome.output_truncated,
                    "duration_seconds": round(time.perf_counter() - suite_t0, 4),
                    "counts": {"collected": 0, "passed": 0, "failed": 0, "errors": 1, "skipped": 0, "xfail": 0},
                    "cases": [],
                    "steps": steps,
                    "reasons": [reason],
                    "evidence_files": {},
                },
                {"vitest.log": vt_log},
                None,
                vt_outcome.stdout,
                vt_outcome.stderr,
            )

        xml_norm = validate_and_parse_junit_xml(
            xml_path=raw_junit,
            suite_id="frontend",
            engine=FRONTEND_ENGINE,
            process_exit_code=vt_outcome.exit_code,
            dialect="vitest",
            min_mtime=min_mtime,
            extra_secrets=extra_secrets,
        )
        json_norm = validate_and_parse_json_report(
            json_path=raw_json,
            dialect="vitest",
            suite_id="frontend",
            engine=FRONTEND_ENGINE,
            process_exit_code=vt_outcome.exit_code,
            min_mtime=min_mtime,
            extra_secrets=extra_secrets,
        )

        vt_log, vt_trunc = build_bounded_log(vt_outcome.stdout, vt_outcome.stderr, extra_secrets=extra_secrets)
        artifacts: dict[str, str] = {"vitest.log": vt_log}
        if xml_norm.get("sanitized_xml"):
            artifacts["junit.xml"] = str(xml_norm["sanitized_xml"])
        if json_norm.get("sanitized_json"):
            artifacts["vitest-report.json"] = str(json_norm["sanitized_json"])

        if xml_norm["status"] == "ERROR" or json_norm["status"] == "ERROR":
            err_reasons = list(dict.fromkeys(xml_norm["reasons"] + json_norm["reasons"]))
            steps.append(
                {
                    "step_id": "frontend-vitest",
                    "kind": "test",
                    "status": "ERROR",
                    "exit_code": vt_outcome.exit_code,
                    "duration_seconds": vt_outcome.duration_seconds,
                    "command": ["node", "node_modules/vitest/vitest.mjs", "run"],
                    "diagnostic": "; ".join(err_reasons),
                }
            )
            return (
                {
                    "suite_id": "frontend",
                    "implemented": True,
                    "status": "ERROR",
                    "exit_code": EXIT_EXECUTION_ERROR,
                    "engine": FRONTEND_ENGINE,
                    "process_exit_code": vt_outcome.exit_code,
                    "pytest_exit_code": None,
                    "timed_out": False,
                    "interrupted": False,
                    "output_truncated": vt_outcome.output_truncated or vt_trunc,
                    "duration_seconds": round(time.perf_counter() - suite_t0, 4),
                    "counts": xml_norm["counts"],
                    "cases": xml_norm["cases"],
                    "steps": steps,
                    "reasons": err_reasons,
                    "evidence_files": {},
                },
                artifacts,
                None,
                vt_outcome.stdout,
                vt_outcome.stderr,
            )

        # Comprobar paridad entre JUnit XML y JSON de Vitest (F01)
        if xml_norm["counts"]["collected"] != json_norm["counts"]["collected"] or (
            xml_norm["counts"]["failed"] + xml_norm["counts"]["errors"]
            != json_norm["counts"]["failed"] + json_norm["counts"]["errors"]
        ):
            mismatch_reason = (
                f"Contradicción entre reportes JUnit XML ({xml_norm['counts']}) y JSON ({json_norm['counts']}) de Vitest (F01)."
            )
            steps.append(
                {
                    "step_id": "frontend-vitest",
                    "kind": "test",
                    "status": "ERROR",
                    "exit_code": vt_outcome.exit_code,
                    "duration_seconds": vt_outcome.duration_seconds,
                    "command": ["node", "node_modules/vitest/vitest.mjs", "run"],
                    "diagnostic": mismatch_reason,
                }
            )
            return (
                {
                    "suite_id": "frontend",
                    "implemented": True,
                    "status": "ERROR",
                    "exit_code": EXIT_EXECUTION_ERROR,
                    "engine": FRONTEND_ENGINE,
                    "process_exit_code": vt_outcome.exit_code,
                    "pytest_exit_code": None,
                    "timed_out": False,
                    "interrupted": False,
                    "output_truncated": vt_outcome.output_truncated or vt_trunc,
                    "duration_seconds": round(time.perf_counter() - suite_t0, 4),
                    "counts": xml_norm["counts"],
                    "cases": xml_norm["cases"],
                    "steps": steps,
                    "reasons": [mismatch_reason],
                    "evidence_files": {},
                },
                artifacts,
                None,
                vt_outcome.stdout,
                vt_outcome.stderr,
            )

        vt_step_status = (
            "PASSED"
            if xml_norm["status"] == "PASSED"
            else ("FAILED" if xml_norm["status"] == "FAILED" else "INCOMPLETE")
        )
        steps.append(
            {
                "step_id": "frontend-vitest",
                "kind": "test",
                "status": vt_step_status,
                "exit_code": vt_outcome.exit_code,
                "duration_seconds": vt_outcome.duration_seconds,
                "command": ["node", "node_modules/vitest/vitest.mjs", "run"],
                "diagnostic": "; ".join(xml_norm["reasons"]) if xml_norm["reasons"] else None,
            }
        )

        reasons = list(xml_norm["reasons"])
        overall_status = xml_norm["status"]
        overall_exit = xml_norm["exit_code"]
        all_stdout = [vt_outcome.stdout]
        all_stderr = [vt_outcome.stderr]

        # Paso 2: TypeScript typecheck (`tsc -b`)
        tsc_script = fe_dir / tsc_rel
        if not tsc_script.is_file():
            steps.append(
                {
                    "step_id": "frontend-typecheck-tsc",
                    "kind": "typecheck",
                    "status": "INCOMPLETE",
                    "exit_code": EXIT_INCOMPLETE,
                    "duration_seconds": 0.0,
                    "command": ["node", str(tsc_rel), "-b"],
                    "diagnostic": f"Binario no encontrado en workspace: {tsc_script}",
                }
            )
            overall_status = "INCOMPLETE"
            overall_exit = EXIT_INCOMPLETE
            reasons.append(f"No se encontró el ejecutable '{tsc_rel}' en el espacio de trabajo frontend.")
        else:
            rem_tsc = int(timeout_seconds - (time.perf_counter() - suite_t0))
            if rem_tsc <= 0:
                steps.append(
                    {
                        "step_id": "frontend-typecheck-tsc",
                        "kind": "typecheck",
                        "status": "ERROR",
                        "exit_code": None,
                        "duration_seconds": 0.0,
                        "command": ["node", str(tsc_rel), "-b"],
                        "diagnostic": "Presupuesto de tiempo global agotado antes de tsc -b",
                    }
                )
                overall_status = "ERROR"
                overall_exit = EXIT_EXECUTION_ERROR
                reasons.append("Presupuesto de tiempo global agotado antes de ejecutar `tsc -b`.")
            else:
                tsc_outcome = run_bounded_subprocess(
                    argv=[node_bin, str(tsc_script), "-b"],
                    cwd=fe_dir,
                    env=dict(workspace.env),
                    timeout_seconds=rem_tsc,
                )
                tsc_log, _ = build_bounded_log(tsc_outcome.stdout, tsc_outcome.stderr, extra_secrets=extra_secrets)
                artifacts["tsc.log"] = tsc_log
                all_stdout.append(tsc_outcome.stdout)
                all_stderr.append(tsc_outcome.stderr)
                if tsc_outcome.timed_out:
                    steps.append(
                        {
                            "step_id": "frontend-typecheck-tsc",
                            "kind": "typecheck",
                            "status": "ERROR",
                            "exit_code": None,
                            "duration_seconds": tsc_outcome.duration_seconds,
                            "command": ["node", "node_modules/typescript/bin/tsc", "-b"],
                            "diagnostic": "Timeout en tsc -b",
                        }
                    )
                    overall_status = "ERROR"
                    overall_exit = EXIT_EXECUTION_ERROR
                    reasons.append("El chequeo TypeScript (`tsc -b`) excedió el tiempo límite.")
                elif tsc_outcome.exit_code != 0:
                    steps.append(
                        {
                            "step_id": "frontend-typecheck-tsc",
                            "kind": "typecheck",
                            "status": "FAILED",
                            "exit_code": tsc_outcome.exit_code,
                            "duration_seconds": tsc_outcome.duration_seconds,
                            "command": ["node", "node_modules/typescript/bin/tsc", "-b"],
                            "diagnostic": tsc_log[:500] or f"tsc -b falló con código {tsc_outcome.exit_code}",
                        }
                    )
                    if overall_status not in ("ERROR", "INCOMPLETE"):
                        overall_status = "FAILED"
                        overall_exit = EXIT_PRODUCT_FAIL
                    reasons.append(f"El chequeo TypeScript (`tsc -b`) falló con código {tsc_outcome.exit_code}.")
                else:
                    steps.append(
                        {
                            "step_id": "frontend-typecheck-tsc",
                            "kind": "typecheck",
                            "status": "PASSED",
                            "exit_code": 0,
                            "duration_seconds": tsc_outcome.duration_seconds,
                            "command": ["node", "node_modules/typescript/bin/tsc", "-b"],
                            "diagnostic": None,
                        }
                    )

        # Paso 3: Vite build (`vite build`)
        vite_script = fe_dir / vite_rel
        if not vite_script.is_file():
            steps.append(
                {
                    "step_id": "frontend-build-vite",
                    "kind": "build",
                    "status": "INCOMPLETE",
                    "exit_code": EXIT_INCOMPLETE,
                    "duration_seconds": 0.0,
                    "command": ["node", str(vite_rel), "build"],
                    "diagnostic": f"Binario no encontrado en workspace: {vite_script}",
                }
            )
            overall_status = "INCOMPLETE"
            overall_exit = EXIT_INCOMPLETE
            reasons.append(f"No se encontró el ejecutable '{vite_rel}' en el espacio de trabajo frontend.")
        else:
            rem_vite = int(timeout_seconds - (time.perf_counter() - suite_t0))
            if rem_vite <= 0:
                steps.append(
                    {
                        "step_id": "frontend-build-vite",
                        "kind": "build",
                        "status": "ERROR",
                        "exit_code": None,
                        "duration_seconds": 0.0,
                        "command": ["node", str(vite_rel), "build"],
                        "diagnostic": "Presupuesto de tiempo global agotado antes de vite build",
                    }
                )
                overall_status = "ERROR"
                overall_exit = EXIT_EXECUTION_ERROR
                reasons.append("Presupuesto de tiempo global agotado antes de ejecutar `vite build`.")
            else:
                vite_outcome = run_bounded_subprocess(
                    argv=[node_bin, str(vite_script), "build"],
                    cwd=fe_dir,
                    env=dict(workspace.env),
                    timeout_seconds=rem_vite,
                )
                vite_log, _ = build_bounded_log(vite_outcome.stdout, vite_outcome.stderr, extra_secrets=extra_secrets)
                artifacts["vite-build.log"] = vite_log
                all_stdout.append(vite_outcome.stdout)
                all_stderr.append(vite_outcome.stderr)
                if vite_outcome.timed_out:
                    steps.append(
                        {
                            "step_id": "frontend-build-vite",
                            "kind": "build",
                            "status": "ERROR",
                            "exit_code": None,
                            "duration_seconds": vite_outcome.duration_seconds,
                            "command": ["node", "node_modules/vite/bin/vite.js", "build"],
                            "diagnostic": "Timeout en vite build",
                        }
                    )
                    overall_status = "ERROR"
                    overall_exit = EXIT_EXECUTION_ERROR
                    reasons.append("El empaquetado de producción (`vite build`) excedió el tiempo límite.")
                elif vite_outcome.exit_code != 0:
                    steps.append(
                        {
                            "step_id": "frontend-build-vite",
                            "kind": "build",
                            "status": "FAILED",
                            "exit_code": vite_outcome.exit_code,
                            "duration_seconds": vite_outcome.duration_seconds,
                            "command": ["node", "node_modules/vite/bin/vite.js", "build"],
                            "diagnostic": vite_log[:500] or f"vite build falló con código {vite_outcome.exit_code}",
                        }
                    )
                    if overall_status not in ("ERROR", "INCOMPLETE"):
                        overall_status = "FAILED"
                        overall_exit = EXIT_PRODUCT_FAIL
                    reasons.append(f"El empaquetado de producción (`vite build`) falló con código {vite_outcome.exit_code}.")
                else:
                    steps.append(
                        {
                            "step_id": "frontend-build-vite",
                            "kind": "build",
                            "status": "PASSED",
                            "exit_code": 0,
                            "duration_seconds": vite_outcome.duration_seconds,
                            "command": ["node", "node_modules/vite/bin/vite.js", "build"],
                            "diagnostic": None,
                        }
                    )

        reasons.append("Pruebas de componentes ejecutadas con mocks declarados de fetch (fetch=mock).")

        suite_result = {
            "suite_id": "frontend",
            "implemented": True,
            "status": overall_status,
            "exit_code": overall_exit,
            "engine": FRONTEND_ENGINE,
            "process_exit_code": vt_outcome.exit_code,
            "pytest_exit_code": None,
            "timed_out": False,
            "interrupted": False,
            "output_truncated": vt_outcome.output_truncated or vt_trunc,
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
            "\n".join(s for s in all_stdout if s),
            "\n".join(s for s in all_stderr if s),
        )
    finally:
        if workspace is not None:
            cleanup_isolated_workspace(workspace=workspace, user_repo_root=repo_root)
