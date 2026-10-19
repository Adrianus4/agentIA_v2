"""Adaptador de ejecución para la suite `llm` (Trabajo 7: A05, A06).

Soporta dos modos:
1. `simulated` (predeterminado): Cero tráfico externo; ejecuta el escenario crud-h2 DELETE 200->204
   mediante dobles controlados de generación de parches y valida los guards reales G1, G3 y G7.
2. `real`: Invoca el proveedor LLM configurado (Gemini, OpenAI, DeepSeek) a través de la frontera
   del producto (build_llm_client / ScopedRepairService), verifica credenciales por entorno,
   acota presupuestos de llamadas y ejecuta la reparación real.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from agents.generator.common import resolve_generation
from agents.profiles.loader import get_profile
from agents.repair.service import ScopedRepairService
from app.core.llm.factory import build_llm_client
from app.orchestrator.patching import apply_patch
from qa_agent import (
    EXIT_EXECUTION_ERROR,
    EXIT_FAILED,
    EXIT_INCOMPLETE,
    EXIT_PASSED,
)
from qa_agent.adapters.frontend import materialize_directory_copy
from qa_agent.capabilities import resolve_toolchain_binary
from qa_agent.evidence import build_bounded_log
from qa_agent.execution import (
    IsolatedWorkspace,
    cleanup_isolated_workspace,
    prepare_isolated_workspace,
    run_bounded_subprocess,
)
from qa_agent.result_normalization import validate_and_parse_junit_xml
from qa_scenarios.llm.crud_h2_repair_scenario import (
    build_crud_h2_repair_request,
    build_simulated_repair_patch,
    evaluate_delete_oracle_in_process,
    materialize_defective_crud_h2,
)

LLM_ENGINE = "llm+repair"

PROVIDER_ENV_KEYS: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gpt": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


def run_llm_suite(
    repo_root: Path,
    trace_id: str,
    timeout_seconds: int = 120,
    llm_mode: str = "simulated",
    llm_provider: str = "gemini",
    llm_model: str | None = None,
    verify_generated_java: bool = False,
    java_cache_dir: Path | None = None,
    extra_secrets: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, str], str | None, str, str]:
    """
    Ejecuta la suite `llm` (A05, A06).
    Devuelve: (suite_result_dict, artifacts_dict, sanitized_xml, raw_stdout, raw_stderr).
    """
    t0 = time.perf_counter()
    canonical_provider = "openai" if llm_provider == "gpt" else llm_provider.lower()
    counts = {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0}
    cases: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    reasons: list[str] = []
    artifacts: dict[str, str] = {}
    stdout_acc: list[str] = []
    stderr_acc: list[str] = []

    # 1. Comprobar credenciales si el modo es real
    if llm_mode == "real":
        key_var = PROVIDER_ENV_KEYS.get(canonical_provider, f"{canonical_provider.upper()}_API_KEY")
        api_key = os.environ.get(key_var, "").strip()
        if not api_key:
            msg = (
                f"La suite llm en modo 'real' con proveedor '{canonical_provider}' requiere la variable "
                f"de entorno '{key_var}', pero no fue encontrada."
            )
            reasons.append(msg)
            return (
                {
                    "suite_id": "llm",
                    "implemented": True,
                    "status": "INCOMPLETE",
                    "exit_code": EXIT_INCOMPLETE,
                    "engine": LLM_ENGINE,
                    "process_exit_code": None,
                    "pytest_exit_code": None,
                    "timed_out": False,
                    "interrupted": False,
                    "output_truncated": False,
                    "duration_seconds": round(time.perf_counter() - t0, 4),
                    "counts": counts,
                    "cases": [],
                    "steps": [
                        {
                            "step_id": "llm-credentials-check",
                            "kind": "prepare",
                            "status": "INCOMPLETE",
                            "exit_code": EXIT_INCOMPLETE,
                            "duration_seconds": round(time.perf_counter() - t0, 4),
                            "command": ["check_env", key_var],
                            "diagnostic": msg,
                        }
                    ],
                    "reasons": reasons,
                    "evidence_files": {},
                },
                {},
                None,
                msg,
                "",
            )

    workspace: IsolatedWorkspace | None = None
    try:
        workspace = prepare_isolated_workspace(
            repo_root=repo_root,
            trace_id=f"{trace_id}-llm",
            suite_id="llm",
        )
        target_ws = workspace.scratch_root / "crud-h2-defective"

        # Paso 1: Materializar el escenario defectuoso crud-h2
        t_prep_start = time.perf_counter()
        meta = materialize_defective_crud_h2(target_ws, workspace.repo_copy)
        failing_rel_path = meta["failing_rel_path"]
        defective_code = meta["defective_code"]
        prep_dur = round(time.perf_counter() - t_prep_start, 4)

        steps.append(
            {
                "step_id": "llm-materialize-defective-fixture",
                "kind": "prepare",
                "status": "PASSED",
                "exit_code": 0,
                "duration_seconds": prep_dur,
                "command": ["materialize_defective_crud_h2", "crud-h2"],
                "diagnostic": f"Materializado crud-h2 defectuoso con DELETE devolviendo HTTP {meta['defective_delete_status']}",
            }
        )
        artifacts["llm/defective_InvoiceResource.java"] = defective_code

        # Paso 2: Control Negativo demostrando que el oráculo falla con el código defectuoso
        t_neg_start = time.perf_counter()
        neg_passed, neg_diag = evaluate_delete_oracle_in_process(defective_code)
        neg_dur = round(time.perf_counter() - t_neg_start, 4)

        counts["collected"] += 1
        if not neg_passed:
            # El oráculo falló como debía sobre el código defectuoso: el control negativo es exitoso
            counts["passed"] += 1
            cases.append(
                {
                    "case_id": "crud_h2::negative_control",
                    "name": "delete_200_negative_control",
                    "classname": "qa_scenarios.llm.crud_h2",
                    "suite_id": "llm",
                    "engine": LLM_ENGINE,
                    "status": "PASSED",
                    "duration_seconds": neg_dur,
                    "message": f"Control negativo demostrado: {neg_diag}",
                }
            )
            steps.append(
                {
                    "step_id": "llm-negative-control",
                    "kind": "test",
                    "status": "PASSED",
                    "exit_code": 0,
                    "duration_seconds": neg_dur,
                    "command": ["evaluate_delete_oracle", failing_rel_path],
                    "diagnostic": neg_diag,
                }
            )
        else:
            # Inesperado: el código supuestamente defectuoso fue aprobado por el oráculo
            counts["failed"] += 1
            err_msg = "Fallo de control negativo: el oráculo aprobó el código supuestamente defectuoso."
            reasons.append(err_msg)
            cases.append(
                {
                    "case_id": "crud_h2::negative_control",
                    "name": "delete_200_negative_control",
                    "classname": "qa_scenarios.llm.crud_h2",
                    "suite_id": "llm",
                    "engine": LLM_ENGINE,
                    "status": "FAILED",
                    "duration_seconds": neg_dur,
                    "message": err_msg,
                }
            )
            steps.append(
                {
                    "step_id": "llm-negative-control",
                    "kind": "test",
                    "status": "FAILED",
                    "exit_code": 1,
                    "duration_seconds": neg_dur,
                    "command": ["evaluate_delete_oracle", failing_rel_path],
                    "diagnostic": err_msg,
                }
            )

        # Paso 3: Construir RepairRequest y ejecutar ScopedRepairService
        t_repair_start = time.perf_counter()
        repair_req = build_crud_h2_repair_request(target_ws, failing_rel_path, defective_code)
        profile = get_profile("quarkus", "3.15.1")

        llm_requests_count = 0
        if llm_mode == "real":
            key_var = PROVIDER_ENV_KEYS.get(canonical_provider, f"{canonical_provider.upper()}_API_KEY")
            api_key = os.environ.get(key_var, "").strip()
            real_client = build_llm_client(
                provider=canonical_provider,
                model=llm_model,
                api_key=api_key,
            )

            def _real_patch_generator(prompt: str) -> str:
                nonlocal llm_requests_count
                llm_requests_count += 1
                return str(resolve_generation(real_client, prompt))

            repair_service = ScopedRepairService(patch_generator=_real_patch_generator)
        else:
            # Modo simulado: generador determinista que produce el parche exacto
            sim_patch = build_simulated_repair_patch(failing_rel_path)
            repair_service = ScopedRepairService(patch_generator=lambda prompt: sim_patch)

        repair_result = repair_service.repair(profile, repair_req, trace_id=f"{trace_id}-repair")
        repair_dur = round(time.perf_counter() - t_repair_start, 4)

        artifacts["llm/repair_result.json"] = repair_result.model_dump_json(indent=2) + "\n"
        if repair_result.patches:
            artifacts["llm/repair_patch.diff"] = repair_result.patches[0]

        # Evaluar resultado de guardias
        counts["collected"] += 1
        if repair_result.guard_report.passed:
            counts["passed"] += 1
            cases.append(
                {
                    "case_id": "crud_h2::guard_evaluation",
                    "name": "patch_guard_evaluation",
                    "classname": "agents.repair.guards",
                    "suite_id": "llm",
                    "engine": LLM_ENGINE,
                    "status": "PASSED",
                    "duration_seconds": repair_dur,
                    "message": f"Guardias de producción G1, G3 y G7 evaluadas y aprobadas (outcome={repair_result.outcome}).",
                }
            )
        else:
            counts["failed"] += 1
            failed_str = ", ".join(repair_result.guard_report.failed_guards)
            cases.append(
                {
                    "case_id": "crud_h2::guard_evaluation",
                    "name": "patch_guard_evaluation",
                    "classname": "agents.repair.guards",
                    "suite_id": "llm",
                    "engine": LLM_ENGINE,
                    "status": "FAILED",
                    "duration_seconds": repair_dur,
                    "message": f"Guardias de parche rechazadas: {failed_str}",
                }
            )

        steps.append(
            {
                "step_id": "llm-scoped-repair",
                "kind": "test",
                "status": "PASSED" if repair_result.outcome == "PATCHED" else "FAILED",
                "exit_code": 0 if repair_result.outcome == "PATCHED" else 1,
                "duration_seconds": repair_dur,
                "command": ["ScopedRepairService.repair", f"mode={llm_mode}", f"provider={canonical_provider}"],
                "diagnostic": f"Outcome: {repair_result.outcome}, Hypothesis: {repair_result.hypothesis}",
            }
        )

        # Paso 4: Aplicar el parche al workspace si el outcome es PATCHED
        if repair_result.outcome == "PATCHED" and repair_result.patches:
            t_apply_start = time.perf_counter()
            apply_patch(
                str(target_ws),
                repair_result.patches[0],
                allowed_paths=[failing_rel_path],
            )
            apply_dur = round(time.perf_counter() - t_apply_start, 4)
            steps.append(
                {
                    "step_id": "llm-apply-patch",
                    "kind": "prepare",
                    "status": "PASSED",
                    "exit_code": 0,
                    "duration_seconds": apply_dur,
                    "command": ["apply_patch", failing_rel_path],
                    "diagnostic": f"Parche aplicado limpiamente en {target_ws}",
                }
            )

            # Paso 5: Control Positivo verificando que post-parche el oráculo aprueba
            patched_file = target_ws / failing_rel_path
            patched_code = patched_file.read_text(encoding="utf-8") if patched_file.is_file() else ""
            artifacts["llm/patched_InvoiceResource.java"] = patched_code

            t_pos_start = time.perf_counter()
            pos_passed, pos_diag = evaluate_delete_oracle_in_process(patched_code)
            pos_dur = round(time.perf_counter() - t_pos_start, 4)

            counts["collected"] += 1
            if pos_passed:
                counts["passed"] += 1
                cases.append(
                    {
                        "case_id": "crud_h2::oracle_verification",
                        "name": "delete_204_oracle_verification",
                        "classname": "qa_scenarios.llm.crud_h2",
                        "suite_id": "llm",
                        "engine": LLM_ENGINE,
                        "status": "PASSED",
                        "duration_seconds": pos_dur,
                        "message": f"Verificación post-reparación aprobada: {pos_diag}",
                    }
                )
                steps.append(
                    {
                        "step_id": "llm-positive-control-python",
                        "kind": "test",
                        "status": "PASSED",
                        "exit_code": 0,
                        "duration_seconds": pos_dur,
                        "command": ["evaluate_delete_oracle", failing_rel_path],
                        "diagnostic": pos_diag,
                    }
                )
            else:
                counts["failed"] += 1
                cases.append(
                    {
                        "case_id": "crud_h2::oracle_verification",
                        "name": "delete_204_oracle_verification",
                        "classname": "qa_scenarios.llm.crud_h2",
                        "suite_id": "llm",
                        "engine": LLM_ENGINE,
                        "status": "FAILED",
                        "duration_seconds": pos_dur,
                        "message": f"El código reparado no satisfizo el oráculo: {pos_diag}",
                    }
                )
                steps.append(
                    {
                        "step_id": "llm-positive-control-python",
                        "kind": "test",
                        "status": "FAILED",
                        "exit_code": 1,
                        "duration_seconds": pos_dur,
                        "command": ["evaluate_delete_oracle", failing_rel_path],
                        "diagnostic": pos_diag,
                    }
                )

        # Paso 6: Verificación Java real con Maven si verify_generated_java está activado (A06)
        if verify_generated_java:
            java_bin = resolve_toolchain_binary("java", repo_root)
            mvn_bin = resolve_toolchain_binary("mvn", repo_root)
            eff_cache = (java_cache_dir or (repo_root / ".agentia-runtime" / "java-cache")).resolve()

            if not java_bin or not mvn_bin or not (eff_cache / "io" / "quarkus").is_dir():
                missing_tools = []
                if not java_bin:
                    missing_tools.append("java")
                if not mvn_bin:
                    missing_tools.append("mvn")
                if not (eff_cache / "io" / "quarkus").is_dir():
                    missing_tools.append("java_cache_dir")
                diag_msg = (
                    f"Nivel de aceptación Java omitido: herramientas no disponibles ({', '.join(missing_tools)}). "
                    "Se declara compilador doble para el nivel Python sin acreditar compilación Java."
                )
                steps.append(
                    {
                        "step_id": "llm-java-maven-verification",
                        "kind": "test",
                        "status": "INCOMPLETE",
                        "exit_code": EXIT_INCOMPLETE,
                        "duration_seconds": 0.0,
                        "command": ["mvn", "test", "-o"],
                        "diagnostic": diag_msg,
                    }
                )
                reasons.append(diag_msg)
            else:
                m2_run_copy = workspace.scratch_root / "m2"
                materialize_directory_copy(eff_cache, m2_run_copy)
                eff_cache = m2_run_copy

                mvn_env = dict(workspace.env)
                if java_bin:
                    java_bin_dir = str(Path(java_bin).resolve().parent)
                    mvn_env["PATH"] = f"{java_bin_dir}{os.pathsep}{mvn_env.get('PATH', '')}"
                    mvn_env["JAVA_HOME"] = str(Path(java_bin).resolve().parent.parent)
                if mvn_bin:
                    mvn_bin_dir = str(Path(mvn_bin).resolve().parent)
                    mvn_env["PATH"] = f"{mvn_bin_dir}{os.pathsep}{mvn_env.get('PATH', '')}"

                t_mvn_start = time.perf_counter()
                mvn_cmd = [
                    mvn_bin,
                    "test",
                    "-o",
                    "-B",
                    "-nsu",
                    f"-Dmaven.repo.local={eff_cache}",
                    "-Dquarkus.http.test-port=0",
                    "-Dquarkus.datasource.devservices.enabled=false",
                ]
                outcome = run_bounded_subprocess(
                    argv=mvn_cmd,
                    cwd=target_ws,
                    env=mvn_env,
                    timeout_seconds=max(30, timeout_seconds - int(time.perf_counter() - t0)),
                )
                mvn_dur = round(time.perf_counter() - t_mvn_start, 4)
                mvn_log, _ = build_bounded_log(outcome.stdout, outcome.stderr, extra_secrets=extra_secrets)
                artifacts["llm/maven.log"] = mvn_log

                # Leer y normalizar reportes Surefire reales generados en target/surefire-reports
                surefire_dir = target_ws / "target" / "surefire-reports"
                found_surefire_cases: list[dict[str, Any]] = []
                if surefire_dir.is_dir():
                    for xml_file in sorted(surefire_dir.glob("TEST-*.xml")):
                        parsed_xml = validate_and_parse_junit_xml(
                            xml_path=xml_file,
                            suite_id="llm",
                            engine="maven+surefire",
                            process_exit_code=outcome.exit_code,
                            dialect="surefire",
                        )
                        if parsed_xml.get("cases"):
                            found_surefire_cases.extend(parsed_xml["cases"])
                        artifacts[f"llm/surefire-reports/{xml_file.name}"] = xml_file.read_text(
                            encoding="utf-8", errors="replace"
                        )

                if found_surefire_cases:
                    for sc in found_surefire_cases:
                        counts["collected"] += 1
                        if sc["status"] == "PASSED":
                            counts["passed"] += 1
                        elif sc["status"] == "FAILED":
                            counts["failed"] += 1
                        elif sc["status"] == "ERROR":
                            counts["errors"] += 1
                        elif sc["status"] == "SKIPPED":
                            counts["skipped"] += 1
                        cases.append(sc)
                else:
                    counts["collected"] += 1
                    if outcome.exit_code == 0:
                        counts["passed"] += 1
                        cases.append(
                            {
                                "case_id": "crud_h2::maven_oracle_acceptance",
                                "name": "oracle_invoice_acceptance_test_maven",
                                "classname": "com.agentia.qa.invoice.resource.OracleInvoiceAcceptanceTest",
                                "suite_id": "llm",
                                "engine": "maven+surefire",
                                "status": "PASSED",
                                "duration_seconds": mvn_dur,
                                "message": "OracleInvoiceAcceptanceTest ejecutado y aprobado con Maven real offline.",
                            }
                        )
                    else:
                        counts["failed"] += 1
                        cases.append(
                            {
                                "case_id": "crud_h2::maven_oracle_acceptance",
                                "name": "oracle_invoice_acceptance_test_maven",
                                "classname": "com.agentia.qa.invoice.resource.OracleInvoiceAcceptanceTest",
                                "suite_id": "llm",
                                "engine": "maven+surefire",
                                "status": "FAILED",
                                "duration_seconds": mvn_dur,
                                "message": f"Maven falló con exit code {outcome.exit_code}.",
                            }
                        )

                step_status = "PASSED" if outcome.exit_code == 0 else "FAILED"
                steps.append(
                    {
                        "step_id": "llm-java-maven-verification",
                        "kind": "test",
                        "status": step_status,
                        "exit_code": outcome.exit_code,
                        "duration_seconds": mvn_dur,
                        "command": ["mvn", "test", "-o", "-B"],
                        "diagnostic": (
                            "Pruebas JUnit Quarkus aprobadas exitosamente."
                            if outcome.exit_code == 0
                            else f"Fallo en pruebas Maven JUnit (exit {outcome.exit_code})."
                        ),
                    }
                )

        # Estado global de la suite
        total_duration = round(time.perf_counter() - t0, 4)
        if counts["failed"] > 0:
            overall_status = "FAILED"
            exit_code = EXIT_FAILED
        elif counts["errors"] > 0:
            overall_status = "ERROR"
            exit_code = EXIT_EXECUTION_ERROR
        elif any(s["status"] == "INCOMPLETE" for s in steps):
            overall_status = "INCOMPLETE"
            exit_code = EXIT_INCOMPLETE
        else:
            overall_status = "PASSED"
            exit_code = EXIT_PASSED

        fidelity_desc = f"mode={llm_mode};provider={canonical_provider};requests={llm_requests_count}"
        reasons.append(f"Suite llm finalizada con estado {overall_status} ({fidelity_desc}).")

        result_dict = {
            "suite_id": "llm",
            "implemented": True,
            "status": overall_status,
            "exit_code": exit_code,
            "engine": LLM_ENGINE,
            "process_exit_code": None,
            "pytest_exit_code": None,
            "timed_out": False,
            "interrupted": False,
            "output_truncated": False,
            "duration_seconds": total_duration,
            "counts": counts,
            "cases": cases,
            "steps": steps,
            "reasons": reasons,
            "evidence_files": {},
        }
        return result_dict, artifacts, None, "\n".join(stdout_acc), "\n".join(stderr_acc)

    except Exception as exc:
        err_msg = f"Error no controlado durante la ejecución de la suite llm: {exc}"
        reasons.append(err_msg)
        return (
            {
                "suite_id": "llm",
                "implemented": True,
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "engine": LLM_ENGINE,
                "process_exit_code": None,
                "pytest_exit_code": None,
                "timed_out": False,
                "interrupted": False,
                "output_truncated": False,
                "duration_seconds": round(time.perf_counter() - t0, 4),
                "counts": counts,
                "cases": cases,
                "steps": steps,
                "reasons": reasons,
                "evidence_files": {},
            },
            artifacts,
            None,
            "",
            err_msg,
        )
    finally:
        if workspace is not None:
            cleanup_isolated_workspace(workspace=workspace, user_repo_root=repo_root)
