from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

import httpx

from qa_agent import (
    EXIT_EXECUTION_ERROR,
    EXIT_FAILED,
    EXIT_INCOMPLETE,
    EXIT_INTERRUPTED,
    EXIT_PASSED,
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
from qa_agent.result_normalization import validate_and_parse_junit_xml
from qa_agent.service_harness import PlatformServiceHarness

JAVA_ENGINE = "maven+surefire"

FIXTURE_MAP: dict[str, str] = {
    "crud-h2": "crud_h2",
    "catalog-h2": "catalog_h2",
    "solution-h2": "solution_h2",
}


def _collect_surefire_reports(
    surefire_dir: Path,
    suite_id: str,
    min_mtime: float,
    extra_secrets: list[str] | None,
    artifact_prefix: str,
    artifacts: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, int], list[str], bool]:
    """
    Lee y valida todos los archivos `TEST-*.xml` de un directorio `surefire-reports` usando F01 y frescura `min_mtime`.
    Devuelve: (cases, aggregated_counts, reasons, has_report_error).
    """
    counts = {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0}
    cases: list[dict[str, Any]] = []
    reasons: list[str] = []

    if not surefire_dir.is_dir():
        return (
            [],
            counts,
            [f"No existe el directorio Surefire esperado para '{artifact_prefix}': {surefire_dir}"],
            True,
        )

    xml_files = sorted(surefire_dir.glob("TEST-*.xml"))
    if not xml_files:
        return (
            [],
            counts,
            [f"No se encontraron reportes Surefire `TEST-*.xml` para '{artifact_prefix}' en {surefire_dir}"],
            True,
        )

    has_error = False
    for xml_file in xml_files:
        raw_xml_text = xml_file.read_text(encoding="utf-8", errors="replace") if xml_file.is_file() else ""
        per_file_rc = 1 if ("<failure" in raw_xml_text or "<error" in raw_xml_text) else 0
        norm = validate_and_parse_junit_xml(
            xml_path=xml_file,
            suite_id=suite_id,
            engine=JAVA_ENGINE,
            process_exit_code=per_file_rc,
            dialect="surefire",
            min_mtime=min_mtime,
            extra_secrets=extra_secrets,
        )
        if norm.get("sanitized_xml"):
            artifacts[f"{artifact_prefix}/{xml_file.name}"] = str(norm["sanitized_xml"])
        for k in counts:
            counts[k] += norm["counts"].get(k, 0)
        for c in norm["cases"]:
            c_name = str(c.get("name", ""))
            c["case_id"] = f"{artifact_prefix}::{c_name}"
            c["name"] = f"{artifact_prefix}::{c_name}"
            cases.append(c)
        if norm["status"] == "ERROR":
            has_error = True
            reasons.extend(norm["reasons"])
        elif norm["status"] in ("FAILED", "INCOMPLETE"):
            reasons.extend(norm["reasons"])

    return cases, counts, reasons, has_error


def _write_generated_files_to_dir(target_dir: Path, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for f in files:
        rel_path = str(f.get("path", "")).strip()
        content = f.get("content")
        if not rel_path or content is None:
            continue
        dest = (target_dir / rel_path).resolve()
        try:
            dest.relative_to(target_dir.resolve())
        except ValueError:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = str(content)
        dest.write_text(text, encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        manifest.append({"path": rel_path, "sha256": digest, "size_bytes": len(text.encode("utf-8"))})
    return manifest


def _ensure_devservices_disabled(project_dir: Path) -> None:
    """Garantiza que H2 en memoria y la desactivación de Dev Services estén presentes en application.properties."""
    props_path = project_dir / "src" / "main" / "resources" / "application.properties"
    props_path.parent.mkdir(parents=True, exist_ok=True)
    existing = props_path.read_text(encoding="utf-8", errors="replace") if props_path.is_file() else ""
    extra_lines: list[str] = []
    if "%test.quarkus.datasource.devservices.enabled" not in existing:
        extra_lines.append("%test.quarkus.datasource.devservices.enabled=false")
    if "%test.quarkus.kafka.devservices.enabled" not in existing:
        extra_lines.append("%test.quarkus.kafka.devservices.enabled=false")
    if extra_lines:
        props_path.write_text(existing.rstrip() + "\n" + "\n".join(extra_lines) + "\n", encoding="utf-8")


def run_java_suite(
    repo_root: Path,
    trace_id: str,
    timeout_seconds: int = 1200,
    java_cache_dir: Path | None = None,
    extra_secrets: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, str], str | None, str, str]:
    """
    Ejecuta la suite `java` (Trabajo 4, J01–J06):
    - Rechaza explícitamente `VERIFIER_DRY_RUN=1` como evidencia real.
    - Comprueba disponibilidad de JDK 21, Maven 3.9+ y caché offline Quarkus (`java_cache_dir`).
    - Materializa una copia por ejecución de la caché Maven sin tocar `~/.m2` ni el directorio de origen.
    - Ejecuta las rutas reales `/v1/blueprint/run` (`crud-h2`, `catalog-h2`) y `/v1/solution/run` (`solution-h2`),
      recoge reportes Surefire del verificador y ejecuta una segunda pasada con los oráculos independientes.
    - Soporta controles negativos de compilación (`crud-h2-negative-compile`) y aserción (`crud-h2-negative-assertion`).
    """
    if os.environ.get("VERIFIER_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}:
        reason = (
            "VERIFIER_DRY_RUN está activo; la suite 'java' rechaza ejecuciones dry_run como evidencia de verificación real (RF-306/308)."
        )
        return (
            {
                "suite_id": "java",
                "implemented": True,
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "engine": JAVA_ENGINE,
                "process_exit_code": None,
                "pytest_exit_code": None,
                "timed_out": False,
                "interrupted": False,
                "output_truncated": False,
                "duration_seconds": 0.0,
                "counts": {"collected": 0, "passed": 0, "failed": 0, "errors": 1, "skipped": 0, "xfail": 0},
                "cases": [],
                "steps": [],
                "reasons": [reason],
                "evidence_files": {},
            },
            {},
            None,
            "",
            reason,
        )

    java_bin = resolve_toolchain_binary("java", repo_root)
    mvn_bin = resolve_toolchain_binary("mvn", repo_root)
    eff_cache_dir = (java_cache_dir or (repo_root / ".agentia-runtime" / "java-cache")).resolve()

    if not java_bin or not mvn_bin or not (eff_cache_dir / "io" / "quarkus").is_dir():
        missing_parts: list[str] = []
        if not java_bin:
            missing_parts.append("JDK 21 (java)")
        if not mvn_bin:
            missing_parts.append("Maven 3.9+ (mvn)")
        if not (eff_cache_dir / "io" / "quarkus").is_dir():
            missing_parts.append(f"caché offline Quarkus en {eff_cache_dir}")
        reason = f"Entorno Java incompleto ({', '.join(missing_parts)}). Ejecute la preparación previa documentada."
        return (
            {
                "suite_id": "java",
                "implemented": True,
                "status": "INCOMPLETE",
                "exit_code": EXIT_INCOMPLETE,
                "engine": JAVA_ENGINE,
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
    harness: PlatformServiceHarness | None = None
    suite_t0 = time.perf_counter()

    try:
        workspace = prepare_isolated_workspace(
            repo_root=repo_root,
            trace_id=f"{trace_id}-java",
            suite_id="java",
        )
        m2_run_copy = workspace.scratch_root / "m2"
        prep_timeout = max(5.0, (suite_t0 + float(timeout_seconds)) - time.perf_counter())
        prep_dur, prep_bytes = materialize_directory_copy(eff_cache_dir, m2_run_copy, timeout_seconds=prep_timeout)

        steps: list[dict[str, Any]] = [
            {
                "step_id": "java-prepare-offline-cache",
                "kind": "prepare",
                "status": "PASSED",
                "exit_code": 0,
                "duration_seconds": prep_dur,
                "command": ["materialize_directory_copy", str(eff_cache_dir)],
                "diagnostic": f"Copiados {prep_bytes} bytes de caché Maven en {prep_dur:.3f}s",
            }
        ]

        java_home = str(Path(java_bin).resolve().parent.parent)
        java_bin_dir = str(Path(java_bin).resolve().parent)
        mvn_bin_dir = str(Path(mvn_bin).resolve().parent)
        base_path = workspace.env.get("PATH", "")
        combined_path = f"{java_bin_dir}{os.pathsep}{mvn_bin_dir}{os.pathsep}{base_path}"

        verifier_cmd_str = (
            f"mvn test -o -B -nsu -Dmaven.repo.local={m2_run_copy} "
            "-Dquarkus.http.test-port=0 -Dquarkus.http.port=0 "
            "-Dquarkus.datasource.devservices.enabled=false -Dquarkus.kafka.devservices.enabled=false"
        )

        java_env = dict(workspace.env)
        java_env["JAVA_HOME"] = java_home
        java_env["PATH"] = combined_path
        java_env["VERIFIER_RUNNER"] = "host"
        java_env["VERIFIER_DRY_RUN"] = "0"
        java_env["VERIFIER_KEEP_WORKSPACE"] = "1"
        java_env["VERIFIER_COMMAND"] = verifier_cmd_str
        java_env["SOLUTION_VERIFY_ENABLED"] = "1"

        raw_fixtures = os.environ.get("QA_JAVA_FIXTURES", "").strip()
        if raw_fixtures:
            selected_fixtures = [f.strip() for f in raw_fixtures.split(",") if f.strip()]
        else:
            selected_fixtures = ["crud-h2", "catalog-h2", "solution-h2"]
            if os.environ.get("QA_JAVA_INCLUDE_NEGATIVE_CONTROLS") == "1":
                selected_fixtures.extend(["crud-h2-negative-compile", "crud-h2-negative-assertion"])

        harness = PlatformServiceHarness(
            repo_root=workspace.repo_copy,
            harness_root=workspace.scratch_root / "jh",
            mode="java",
            extra_env=java_env,
        )
        harness.start(startup_timeout_seconds=25.0)

        all_cases: list[dict[str, Any]] = []
        total_counts = {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0}
        reasons: list[str] = []
        artifacts: dict[str, str] = {}
        all_stdout: list[str] = []
        all_stderr: list[str] = []
        has_execution_error = False
        has_product_failure = False
        has_incomplete = False

        fixtures_root = workspace.repo_copy / "qa_scenarios" / "fixtures"
        orch_url = harness.orchestrator_url
        headers = {"x-api-key": harness.orchestrator_api_key}

        def _run_maven_oracle_or_control(
            project_dir: Path,
            step_id: str,
            artifact_prefix: str,
            expect_compile_failure: bool = False,
        ) -> None:
            nonlocal has_execution_error, has_product_failure, has_incomplete
            _ensure_devservices_disabled(project_dir)
            surefire_dir = project_dir / "target" / "surefire-reports"
            if surefire_dir.exists():
                shutil.rmtree(surefire_dir, ignore_errors=True)

            rem = int(timeout_seconds - (time.perf_counter() - suite_t0))
            if rem <= 0:
                has_execution_error = True
                t_reason = f"Presupuesto de tiempo global agotado antes de ejecutar Maven en '{step_id}'."
                reasons.append(t_reason)
                steps.append(
                    {
                        "step_id": step_id,
                        "kind": "test",
                        "status": "ERROR",
                        "exit_code": None,
                        "duration_seconds": 0.0,
                        "command": ["mvn", "test", "-o", "-B"],
                        "diagnostic": t_reason,
                    }
                )
                return

            mvn_argv = [
                mvn_bin,
                "test",
                "-o",
                "-B",
                "-nsu",
                f"-Dmaven.repo.local={m2_run_copy}",
                "-Dquarkus.http.test-port=0",
                "-Dquarkus.http.port=0",
                "-Dquarkus.datasource.devservices.enabled=false",
                "-Dquarkus.kafka.devservices.enabled=false",
            ]
            step_min_mtime = time.time() - 1.0
            outcome = run_bounded_subprocess(
                argv=mvn_argv,
                cwd=project_dir,
                env=java_env,
                timeout_seconds=rem,
            )
            all_stdout.append(outcome.stdout)
            all_stderr.append(outcome.stderr)
            mvn_log, _ = build_bounded_log(outcome.stdout, outcome.stderr, extra_secrets=extra_secrets)
            artifacts[f"{artifact_prefix}/maven.log"] = mvn_log

            if outcome.timed_out:
                has_execution_error = True
                t_reason = f"Timeout de Maven ({rem}s) en '{step_id}'."
                reasons.append(t_reason)
                steps.append(
                    {
                        "step_id": step_id,
                        "kind": "test",
                        "status": "ERROR",
                        "exit_code": None,
                        "duration_seconds": outcome.duration_seconds,
                        "command": ["mvn", "test", "-o", "-B"],
                        "diagnostic": t_reason,
                    }
                )
                return

            # Si falló la compilación y no se generaron reportes Surefire, comprobar si es falta de caché o código roto
            if outcome.exit_code != 0 and not surefire_dir.is_dir():
                diag = summarize_diagnostic_text(outcome.stdout + "\n" + outcome.stderr, extra_secrets=extra_secrets)
                combined_lower = f"{outcome.stdout.lower()}\n{outcome.stderr.lower()}"
                if (
                    "missing:" in combined_lower
                    or ("offline mode" in combined_lower and ("cannot access" in combined_lower or "was not found" in combined_lower or "offline" in combined_lower))
                    or "non-resolvable parent pom" in combined_lower
                    or "could not resolve dependencies" in combined_lower
                    or ("plugin" in combined_lower and "could not be resolved" in combined_lower)
                    or "the following artifacts could not be resolved" in combined_lower
                ):
                    # Si falta un artefacto o plugin en la caché offline -> INCOMPLETE (código 4), NO ERROR (R05)
                    incomplete_msg = f"Caché Maven offline incompleta durante '{step_id}': {diag[:300]}"
                    reasons.append(incomplete_msg)
                    steps.append(
                        {
                            "step_id": step_id,
                            "kind": "build" if expect_compile_failure else "test",
                            "status": "INCOMPLETE",
                            "exit_code": outcome.exit_code,
                            "duration_seconds": outcome.duration_seconds,
                            "command": ["mvn", "test", "-o", "-B"],
                            "diagnostic": incomplete_msg,
                        }
                    )
                    has_incomplete = True
                    return

                has_product_failure = True
                total_counts["collected"] += 1
                total_counts["failed"] += 1
                all_cases.append(
                    {
                        "case_id": f"{artifact_prefix}::compilation",
                        "name": "maven_compilation",
                        "classname": artifact_prefix,
                        "suite_id": "java",
                        "engine": JAVA_ENGINE,
                        "status": "FAILED",
                        "duration_seconds": outcome.duration_seconds,
                        "message": diag[:600] or f"Fallo de compilación Maven (exit={outcome.exit_code})",
                    }
                )
                steps.append(
                    {
                        "step_id": step_id,
                        "kind": "build" if expect_compile_failure else "test",
                        "status": "FAILED",
                        "exit_code": outcome.exit_code,
                        "duration_seconds": outcome.duration_seconds,
                        "command": ["mvn", "test", "-o", "-B"],
                        "diagnostic": diag[:500],
                    }
                )
                reasons.append(f"Fallo de compilación en '{artifact_prefix}' (exit={outcome.exit_code}).")
                return

            c_list, c_counts, c_reasons, c_err = _collect_surefire_reports(
                surefire_dir=surefire_dir,
                suite_id="java",
                min_mtime=step_min_mtime,
                extra_secrets=extra_secrets,
                artifact_prefix=artifact_prefix,
                artifacts=artifacts,
            )
            for k in total_counts:
                total_counts[k] += c_counts[k]
            all_cases.extend(c_list)
            reasons.extend(c_reasons)

            if c_err:
                has_execution_error = True
                s_status = "ERROR"
            elif outcome.exit_code != 0 or c_counts["failed"] > 0 or c_counts["errors"] > 0:
                has_product_failure = True
                s_status = "FAILED"
            else:
                s_status = "PASSED"

            steps.append(
                {
                    "step_id": step_id,
                    "kind": "test",
                    "status": s_status,
                    "exit_code": outcome.exit_code,
                    "duration_seconds": outcome.duration_seconds,
                    "command": ["mvn", "test", "-o", "-B"],
                    "diagnostic": "; ".join(c_reasons) if c_reasons else None,
                }
            )

        suite_deadline = suite_t0 + float(timeout_seconds)
        with httpx.Client(timeout=float(timeout_seconds)) as client:
            for fix_id in selected_fixtures:
                remaining_time = suite_deadline - time.perf_counter()
                if remaining_time <= 0:
                    timed_out = True
                    reasons.append(f"Suite Java superó el deadline dominante de {timeout_seconds}s.")
                    break

                if fix_id in ("crud-h2", "catalog-h2"):
                    fix_dir = fixtures_root / FIXTURE_MAP[fix_id]
                    fix_data = json.loads((fix_dir / "fixture.json").read_text(encoding="utf-8"))
                    bp = fix_data["blueprint"]
                    expectations = fix_data["expectations"]
                    run_trace = f"java-{fix_id}-{trace_id[-6:]}"
                    fix_t0 = time.time() - 1.0

                    resp = client.post(
                        f"{orch_url}/v1/blueprint/run",
                        headers=headers,
                        json={
                            "workspace_dir": f"{fix_id}-ws",
                            "blueprint": bp,
                            "trace_id": run_trace,
                        },
                        timeout=max(1.0, remaining_time),
                    )
                    if resp.status_code != 200:
                        has_product_failure = True
                        reasons.append(f"API `/v1/blueprint/run` falló para '{fix_id}' con HTTP {resp.status_code}.")
                        continue

                    body = resp.json()
                    gen_files = body.get("generated_files") or []
                    ver_obj = body.get("verification") or {}
                    outcome_str = body.get("outcome")

                    # Guardar manifiesto de archivos generados y sus huellas SHA-256
                    oracle_ws = workspace.scratch_root / "oracle-workspaces" / fix_id
                    gen_manifest = _write_generated_files_to_dir(oracle_ws, gen_files)
                    artifacts[f"{fix_id}/generated_manifest.json"] = (
                        json.dumps(
                            {
                                "fixture_id": fix_id,
                                "trace_id": run_trace,
                                "api_outcome": outcome_str,
                                "verification_success": ver_obj.get("success"),
                                "files": gen_manifest,
                            },
                            indent=2,
                        )
                        + "\n"
                    )

                    # Recoger reportes Surefire producidos por el servicio verifier correlacionados por run_trace[:12]
                    candidate_roots = [
                        harness.verifier_scratch_dir / "agentia-verify",
                        workspace.scratch_root / "tmp" / "verifier-scratch" / "agentia-verify",
                        Path(java_env.get("VERIFIER_SCRATCH_DIR", "")) / "agentia-verify" if java_env.get("VERIFIER_SCRATCH_DIR") else None,
                        Path(os.environ.get("VERIFIER_SCRATCH_DIR", "")) / "agentia-verify" if os.environ.get("VERIFIER_SCRATCH_DIR") else None,
                    ]
                    matched_ver_dirs: list[Path] = []
                    for vr in candidate_roots:
                        if vr is not None and vr.is_dir():
                            matched = sorted(vr.glob(f"{run_trace[:12]}-*"))
                            if matched:
                                matched_ver_dirs = matched
                                break
                    if not matched_ver_dirs:
                        has_execution_error = True
                        reasons.append(
                            f"No se encontró el workspace del verificador para '{fix_id}' (trace_id={run_trace})."
                        )
                    else:
                        ver_ws = matched_ver_dirs[-1]
                        try:
                            sf_dir = ver_ws / "target" / "surefire-reports"
                            raw_out = str(ver_obj.get("raw_output") or "")
                            combined_diag = raw_out.lower()
                            is_cache_missing = (
                                "missing:" in combined_diag
                                or ("offline mode" in combined_diag and ("cannot access" in combined_diag or "was not found" in combined_diag or "offline" in combined_diag))
                                or "could not resolve dependencies" in combined_diag
                                or ("plugin" in combined_diag and "could not be resolved" in combined_diag)
                                or "the following artifacts could not be resolved" in combined_diag
                            )

                            if is_cache_missing:
                                has_incomplete = True
                                reasons.append(f"Caché Maven offline incompleta durante verificación de '{fix_id}'.")
                                steps.append(
                                    {
                                        "step_id": f"java-{fix_id}-verifier",
                                        "kind": "test",
                                        "status": "INCOMPLETE",
                                        "exit_code": ver_obj.get("exit_code", 1),
                                        "duration_seconds": float(ver_obj.get("wall_time_seconds") or 0.0),
                                        "command": ["POST", "/v1/blueprint/run", fix_id],
                                        "diagnostic": f"Caché offline incompleta: {raw_out[:300]}",
                                    }
                                )
                            elif not sf_dir.is_dir() and (ver_obj.get("exit_code") not in (0, None) or outcome_str != "SUCCESS"):
                                has_product_failure = True
                                total_counts["collected"] += 1
                                total_counts["failed"] += 1
                                all_cases.append(
                                    {
                                        "case_id": f"{fix_id}::verifier_compilation",
                                        "name": f"{fix_id}::verifier_compilation",
                                        "classname": fix_id,
                                        "suite_id": "java",
                                        "engine": JAVA_ENGINE,
                                        "status": "FAILED",
                                        "duration_seconds": float(ver_obj.get("wall_time_seconds") or 0.0),
                                        "message": raw_out[:600] or "Fallo de compilación en verificador",
                                    }
                                )
                                steps.append(
                                    {
                                        "step_id": f"java-{fix_id}-verifier",
                                        "kind": "test",
                                        "status": "FAILED",
                                        "exit_code": ver_obj.get("exit_code", 1),
                                        "duration_seconds": float(ver_obj.get("wall_time_seconds") or 0.0),
                                        "command": ["POST", "/v1/blueprint/run", fix_id],
                                        "diagnostic": raw_out[:500],
                                    }
                                )
                            else:
                                v_cases, v_counts, v_reasons, v_err = _collect_surefire_reports(
                                    surefire_dir=sf_dir,
                                    suite_id="java",
                                    min_mtime=fix_t0,
                                    extra_secrets=extra_secrets,
                                    artifact_prefix=f"{fix_id}/verifier",
                                    artifacts=artifacts,
                                )
                                for k in total_counts:
                                    total_counts[k] += v_counts[k]
                                all_cases.extend(v_cases)
                                reasons.extend(v_reasons)
                                if v_err:
                                    has_execution_error = True
                                elif outcome_str != "SUCCESS" or not ver_obj.get("success") or v_counts["failed"] > 0:
                                    has_product_failure = True
                                steps.append(
                                    {
                                        "step_id": f"java-{fix_id}-verifier",
                                        "kind": "test",
                                        "status": "PASSED" if (not v_err and outcome_str == "SUCCESS") else ("ERROR" if v_err else "FAILED"),
                                        "exit_code": ver_obj.get("exit_code", 0),
                                        "duration_seconds": float(ver_obj.get("wall_time_seconds") or 0.0),
                                        "command": ["POST", "/v1/blueprint/run", fix_id],
                                        "diagnostic": None if outcome_str == "SUCCESS" else f"outcome={outcome_str}",
                                    }
                                )
                        finally:
                            shutil.rmtree(ver_ws, ignore_errors=True)

                    # Segunda ejecución con el oráculo Java independiente sobre copia identificada
                    oracle_rel = expectations["oracleTestRelativePath"]
                    oracle_src = fix_dir / Path(oracle_rel).name
                    oracle_dst = oracle_ws / oracle_rel
                    oracle_dst.parent.mkdir(parents=True, exist_ok=True)
                    oracle_content = oracle_src.read_text(encoding="utf-8")
                    oracle_dst.write_text(oracle_content, encoding="utf-8")
                    artifacts[f"{fix_id}/oracle_provenance.json"] = (
                        json.dumps(
                            {
                                "fixture_id": fix_id,
                                "added_oracle_test": oracle_rel,
                                "oracle_sha256": hashlib.sha256(oracle_content.encode("utf-8")).hexdigest(),
                            },
                            indent=2,
                        )
                        + "\n"
                    )
                    _run_maven_oracle_or_control(
                        project_dir=oracle_ws,
                        step_id=f"java-{fix_id}-oracle",
                        artifact_prefix=f"{fix_id}/oracle",
                    )

                elif fix_id == "solution-h2":
                    fix_dir = fixtures_root / "solution_h2"
                    fix_data = json.loads((fix_dir / "fixture.json").read_text(encoding="utf-8"))
                    sol_req = dict(fix_data["solutionRequest"])
                    sol_expectations = fix_data["expectations"]["services"]
                    run_trace = f"java-sol-{trace_id[-6:]}"
                    sol_req["trace_id"] = run_trace
                    fix_t0 = time.time() - 1.0

                    resp = client.post(
                        f"{orch_url}/v1/solution/run",
                        headers=headers,
                        json=sol_req,
                        timeout=max(1.0, remaining_time),
                    )
                    if resp.status_code != 200:
                        has_product_failure = True
                        reasons.append(f"API `/v1/solution/run` falló con HTTP {resp.status_code}.")
                        continue

                    sol_body = resp.json()
                    sol_status = sol_body.get("status")
                    artifacts["solution-h2/solution_result_summary.json"] = (
                        json.dumps(
                            {
                                "trace_id": run_trace,
                                "status": sol_status,
                                "outcome": sol_body.get("outcome"),
                                "services": [
                                    {"service_name": s.get("service_name"), "status": s.get("status")}
                                    for s in (sol_body.get("services") or [])
                                ],
                            },
                            indent=2,
                        )
                        + "\n"
                    )
                    if sol_status != "SUCCESS":
                        has_product_failure = True
                        reasons.append(
                            f"La solución 'solution-h2' terminó con status={sol_status!r} (se esperaba 'SUCCESS' verificado con Maven)."
                        )

                    for svc_obj in sol_body.get("services") or []:
                        svc_name = str(svc_obj.get("service_name"))
                        svc_status = str(svc_obj.get("status"))
                        svc_ws = Path(str(svc_obj.get("workspace_dir")))
                        if svc_status != "VERIFIED":
                            has_product_failure = True
                            reasons.append(
                                f"El servicio '{svc_name}' de solution-h2 quedó en estado {svc_status!r} (se esperaba 'VERIFIED', no solo 'GENERATED')."
                            )
                        sf_reports_dir = svc_ws / "target" / "surefire-reports"
                        if sf_reports_dir.is_dir():
                            v_cases, v_counts, v_reasons, v_err = _collect_surefire_reports(
                                surefire_dir=sf_reports_dir,
                                suite_id="java",
                                min_mtime=fix_t0,
                                extra_secrets=extra_secrets,
                                artifact_prefix=f"solution-h2/{svc_name}/verifier",
                                artifacts=artifacts,
                            )
                            for k in total_counts:
                                total_counts[k] += v_counts[k]
                            all_cases.extend(v_cases)
                            reasons.extend(v_reasons)
                            if v_err and not has_incomplete:
                                has_execution_error = True
                        elif svc_status == "VERIFIED" and not has_incomplete:
                            has_product_failure = True
                            reasons.append(
                                f"El servicio '{svc_name}' reportó VERIFIED pero falta el directorio Surefire: {sf_reports_dir}"
                            )

                        # Ejecutar oráculo independiente para cada microservicio de la solución
                        svc_exp = sol_expectations.get(svc_name, {})
                        oracle_Copy = workspace.scratch_root / "oracle-workspaces" / "solution-h2" / svc_name
                        _write_generated_files_to_dir(oracle_Copy, svc_obj.get("files") or [])
                        oracle_rel = svc_exp.get("oracleTestRelativePath")
                        oracle_file = svc_exp.get("oracleTestFile")
                        if oracle_rel and oracle_file:
                            o_src = fix_dir / oracle_file
                            o_dst = oracle_Copy / oracle_rel
                            o_dst.parent.mkdir(parents=True, exist_ok=True)
                            o_dst.write_text(o_src.read_text(encoding="utf-8"), encoding="utf-8")
                        _run_maven_oracle_or_control(
                            project_dir=oracle_Copy,
                            step_id=f"java-solution-{svc_name}-oracle",
                            artifact_prefix=f"solution-h2/{svc_name}/oracle",
                        )

                elif fix_id in ("crud-h2-negative-compile", "crud-h2-negative-assertion"):
                    # Preparar copia base de crud-h2 sin mutar el repo del usuario
                    fix_dir = fixtures_root / "crud_h2"
                    fix_data = json.loads((fix_dir / "fixture.json").read_text(encoding="utf-8"))
                    bp = fix_data["blueprint"]
                    expectations = fix_data["expectations"]
                    neg_ws = workspace.scratch_root / "negative-controls" / fix_id
                    # Generar árbol de archivos mediante el generador real
                    from agents.generator.pipeline import GenerationPipeline
                    from contracts.models import GenerationRequest

                    gen_files_models = GenerationPipeline()(GenerationRequest(blueprint=bp, trace_id=f"neg-{fix_id}"))
                    _write_generated_files_to_dir(
                        neg_ws,
                        [{"path": f.path, "content": f.content} for f in gen_files_models],
                    )
                    oracle_rel = expectations["oracleTestRelativePath"]
                    oracle_src = fix_dir / Path(oracle_rel).name
                    oracle_dst = neg_ws / oracle_rel
                    oracle_dst.parent.mkdir(parents=True, exist_ok=True)
                    oracle_dst.write_text(oracle_src.read_text(encoding="utf-8"), encoding="utf-8")

                    mut_target = neg_ws / expectations["mutationTargetRelativePath"]
                    orig_java = mut_target.read_text(encoding="utf-8")
                    if fix_id == "crud-h2-negative-compile":
                        mutated_java = orig_java.replace(
                            "public class InvoiceResource {",
                            'public class InvoiceResource {\n    private final int brokenType = "COMPILE_ERROR_CONTROL";',
                            1,
                        )
                        mut_target.write_text(mutated_java, encoding="utf-8")
                        _run_maven_oracle_or_control(
                            project_dir=neg_ws,
                            step_id="java-crud-h2-negative-compile",
                            artifact_prefix="crud-h2-negative-compile",
                            expect_compile_failure=True,
                        )
                    else:
                        # Mutar DELETE para devolver 200 OK en vez de 204 NO_CONTENT y provocar fallo de aserción en Surefire
                        mutated_java = orig_java.replace(
                            "Response.Status.NO_CONTENT",
                            "Response.Status.OK",
                        )
                        mut_target.write_text(mutated_java, encoding="utf-8")
                        _run_maven_oracle_or_control(
                            project_dir=neg_ws,
                            step_id="java-crud-h2-negative-assertion",
                            artifact_prefix="crud-h2-negative-assertion",
                            expect_compile_failure=False,
                        )

        reasons.append(
            "Fronteras de ejecución java: http=real, compiler=real (Maven -o -B offline con H2 en memoria y Dev Services desactivados; sin aislamiento de red de contenedor Docker)."
        )

        if has_incomplete:
            final_status = "INCOMPLETE"
            final_exit = EXIT_INCOMPLETE
        elif has_execution_error:
            final_status = "ERROR"
            final_exit = EXIT_EXECUTION_ERROR
        elif total_counts["collected"] == 0 or total_counts["skipped"] > 0:
            final_status = "INCOMPLETE"
            final_exit = EXIT_INCOMPLETE
        elif has_product_failure or total_counts["failed"] > 0 or total_counts["errors"] > 0:
            final_status = "FAILED"
            final_exit = EXIT_FAILED
        else:
            final_status = "PASSED"
            final_exit = EXIT_PASSED

        suite_result = {
            "suite_id": "java",
            "implemented": True,
            "status": final_status,
            "exit_code": final_exit,
            "engine": JAVA_ENGINE,
            "process_exit_code": 0 if final_exit == EXIT_PASSED else 1,
            "pytest_exit_code": None,
            "timed_out": False,
            "interrupted": False,
            "output_truncated": False,
            "duration_seconds": round(time.perf_counter() - suite_t0, 4),
            "counts": total_counts,
            "cases": all_cases,
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
    except KeyboardInterrupt:
        return (
            {
                "suite_id": "java",
                "implemented": True,
                "status": "INTERRUPTED",
                "exit_code": EXIT_INTERRUPTED,
                "engine": JAVA_ENGINE,
                "process_exit_code": None,
                "pytest_exit_code": None,
                "timed_out": False,
                "interrupted": True,
                "output_truncated": False,
                "duration_seconds": round(time.perf_counter() - suite_t0, 4),
                "counts": {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0},
                "cases": [],
                "steps": [],
                "reasons": ["Ejecución de la suite 'java' interrumpida por el usuario."],
                "evidence_files": {},
            },
            {},
            None,
            "",
            "Interrumpido",
        )
    finally:
        if harness is not None:
            harness.stop()
        if workspace is not None:
            cleanup_isolated_workspace(workspace=workspace, user_repo_root=repo_root)
