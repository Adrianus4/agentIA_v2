"""Interfaz de línea de comandos (CLI) en español para el ejecutor QA local multimotor (E02, E03, E04, E07, F03, C03, C04)."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NoReturn

from qa_agent import (
    EXIT_CONFIG_ERROR,
    EXIT_EXECUTION_ERROR,
    EXIT_FAILED,
    EXIT_INCOMPLETE,
    EXIT_INTERRUPTED,
    EXIT_PASSED,
    SCHEMA_VERSION,
)
from qa_agent.capabilities import build_doctor_report, evaluate_suite_eligibilities
from qa_agent.catalog import build_list_report, get_known_suite_ids
from qa_agent.config import QAConfigError, load_and_merge_config, resolve_repo_root
from qa_agent.evidence import (
    build_bounded_log,
    collect_sensitive_env_values,
    format_terminal_summary,
    persist_run_evidence,
    redact_text,
    safe_write_text,
    to_extended_path,
)
from qa_agent.execution import generate_trace_id
from qa_agent.suite_registry import dispatch_suite_execution

UNIMPLEMENTED_AI_FLAGS = (
    "--ai-analysis",
    "--llm-provider",
    "--ai-provider",
    "--ai-model",
    "--llm-model",
)


class QAArgumentParser(argparse.ArgumentParser):
    """ArgumentParser que garantiza código de salida 2 y mensajes en español ante errores de argumentos."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        sys.stderr.write(f"Error de argumentos (código {EXIT_CONFIG_ERROR}): {message}\n")
        raise SystemExit(EXIT_CONFIG_ERROR)


def _build_parser() -> QAArgumentParser:
    parser = QAArgumentParser(
        prog="qa_agent",
        description=(
            "Ejecutor local de aseguramiento de calidad (QA) para AgentIA. "
            "Ofrece diagnóstico de entorno (doctor), catálogo de suites (list) "
            "y ejecución aislada de suites por capacidades (run)."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", title="comandos disponibles")

    # doctor
    doc_parser = subparsers.add_parser(
        "doctor",
        help="Inspecciona Python, paquetes, toolchains y cachés por suite sin instalar ni descargar nada.",
        description="Inspecciona el entorno local y determina qué suites son elegibles para ejecutarse.",
    )
    doc_parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Ruta al repositorio objetivo (admite rutas con espacios).",
    )
    doc_parser.add_argument(
        "--java-cache-dir",
        type=str,
        default=None,
        help="Ruta opcional al directorio de caché Maven offline de Quarkus.",
    )
    doc_parser.add_argument(
        "--browser-cache-dir",
        type=str,
        default=None,
        help="Ruta opcional al directorio de navegadores Playwright preparados.",
    )
    doc_parser.add_argument(
        "--json",
        action="store_true",
        help="Emite el diagnóstico en formato JSON estructurado.",
    )

    # list
    list_parser = subparsers.add_parser(
        "list",
        help="Lista las suites registradas y su estado de elegibilidad en la máquina actual.",
        description="Muestra el catálogo de suites registradas y su estado (EXECUTABLE, BLOCKED, NOT_IMPLEMENTED).",
    )
    list_parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Ruta al repositorio objetivo (admite rutas con espacios).",
    )
    list_parser.add_argument(
        "--java-cache-dir",
        type=str,
        default=None,
        help="Ruta opcional al directorio de caché Maven offline de Quarkus.",
    )
    list_parser.add_argument(
        "--browser-cache-dir",
        type=str,
        default=None,
        help="Ruta opcional al directorio de navegadores Playwright preparados.",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Emite el catálogo en formato JSON estructurado.",
    )

    # run
    run_parser = subparsers.add_parser(
        "run",
        help="Ejecuta las suites seleccionadas en entornos aislados y guarda evidencia redactada por suite.",
        description="Valida la configuración, prepara aislamiento temporal, ejecuta las suites elegidas y persiste evidencia.",
    )
    run_parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Ruta al repositorio objetivo (admite rutas con espacios).",
    )
    run_parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Ruta al archivo JSON de configuración (precedencia: CLI > JSON > valores por defecto).",
    )
    run_parser.add_argument(
        "--suite",
        action="append",
        dest="suites",
        default=None,
        help="Suite a ejecutar (predeterminada: python). Puede repetirse o separarse por comas.",
    )
    run_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="Tiempo máximo global por defecto en segundos (predeterminado: 300).",
    )
    run_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directorio base donde guardar la evidencia (predeterminado: .agentia-runtime/qa).",
    )
    run_parser.add_argument(
        "--java-cache-dir",
        type=str,
        default=None,
        help="Ruta opcional al directorio de caché Maven offline de Quarkus.",
    )
    run_parser.add_argument(
        "--browser-cache-dir",
        type=str,
        default=None,
        help="Ruta opcional al directorio de navegadores Playwright preparados.",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime el resultado final también en formato JSON por salida estándar.",
    )
    run_parser.add_argument(
        "--ai-analysis",
        action="store_true",
        help="Activa el análisis IA opcional al finalizar la ejecución de las suites.",
    )
    run_parser.add_argument(
        "--ai-provider",
        type=str,
        choices=["gemini", "openai", "deepseek", "gpt"],
        default="gemini",
        help="Proveedor de IA para el análisis (gemini, openai, deepseek; default: gemini).",
    )
    run_parser.add_argument(
        "--ai-model",
        type=str,
        default=None,
        help="Modelo específico para el análisis IA.",
    )
    run_parser.add_argument(
        "--ai-mode",
        type=str,
        choices=["disabled", "offline", "live"],
        default="live",
        help="Modo de ejecución del análisis IA (offline o live; default: live).",
    )
    run_parser.add_argument(
        "--llm-mode",
        type=str,
        choices=["simulated", "real"],
        default="simulated",
        help="Modo de ejecución de la suite llm (simulated o real; default: simulated).",
    )
    run_parser.add_argument(
        "--llm-provider",
        type=str,
        choices=["gemini", "openai", "deepseek", "gpt"],
        default="gemini",
        help="Proveedor LLM para la suite llm.",
    )
    run_parser.add_argument(
        "--llm-model",
        type=str,
        default=None,
        help="Modelo específico para la suite llm.",
    )
    run_parser.add_argument(
        "--verify-generated-java",
        action="store_true",
        help="En la suite llm, ejecuta también verificación completa Maven/Surefire del código Java parchado.",
    )

    # report (Trabajo 6: R02)
    report_parser = subparsers.add_parser(
        "report",
        help="Reconstruye el informe HTML y manifiesto desde un archivo result.json existente sin ejecutar tests.",
        description="Genera el informe HTML consolidado y valida el manifiesto de artefactos de un run previo.",
    )
    report_parser.add_argument(
        "--input",
        type=str,
        required=False,
        default=None,
        help="Ruta al archivo result.json del run a reportar (si se omite, auto-detecta la última ejecución).",
    )
    report_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directorio destino opcional para el informe HTML (por defecto, la subcarpeta 'report' del run).",
    )
    report_parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime el manifiesto de reporte generado en JSON.",
    )

    # analyze (Trabajo 7: A04)
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Ejecuta análisis de resultados determinista o live por API sobre un archivo result.json existente.",
        description="Analiza un run existente, infiere hipótesis y persiste analysis.json y delivery.json sin alterar result.json.",
    )
    analyze_parser.add_argument(
        "--input",
        type=str,
        required=False,
        default=None,
        help="Ruta al archivo result.json a analizar (si se omite, auto-detecta la última ejecución).",
    )
    analyze_parser.add_argument(
        "--ai-provider",
        type=str,
        choices=["gemini", "openai", "deepseek", "gpt"],
        default="gemini",
        help="Proveedor de IA para el análisis.",
    )
    analyze_parser.add_argument(
        "--ai-model",
        type=str,
        default=None,
        help="Modelo específico a utilizar.",
    )
    analyze_parser.add_argument(
        "--ai-mode",
        type=str,
        choices=["offline", "live"],
        default="live",
        help="Modo de análisis (offline o live; default: live).",
    )
    analyze_parser.add_argument(
        "--json",
        action="store_true",
        help="Emite el análisis generado en formato JSON estructurado.",
    )

    return parser


def _check_unimplemented_ai_flags(argv: list[str]) -> None:
    # En Trabajo 7 las opciones de IA e integración están completamente implementadas
    pass


def _compute_source_provenance(repo_root: Path) -> dict[str, Any]:
    """Calcula procedencia determinista con revisión Git o huellas SHA-256 de archivos fuente clave (S12)."""
    git_rev = None
    git_bin = shutil.which("git")
    if git_bin and (repo_root / ".git").exists():
        try:
            res = subprocess.run(
                [git_bin, "rev-parse", "HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                git_rev = res.stdout.strip()
        except Exception:
            pass

    source_hashes: dict[str, str] = {}
    candidate_patterns = [
        "app/**/*.py",
        "agents/**/*.py",
        "contracts/**/*.py",
        "services/**/*.py",
        "templates/quarkus/pom.xml",
        "profiles/quarkus.yaml",
        "frontend/package.json",
        "frontend/src/**/*.tsx",
        "frontend/src/**/*.ts",
    ]
    for pat in candidate_patterns:
        for f in repo_root.glob(pat):
            if f.is_file() and not f.name.startswith("."):
                rel_path = f.relative_to(repo_root).as_posix()
                try:
                    source_hashes[rel_path] = hashlib.sha256(f.read_bytes()).hexdigest()
                except Exception:
                    pass

    return {
        "git_revision": git_rev,
        "source_hashes": source_hashes,
        "fidelity": {"mode": "git" if git_rev else "hash_fallback"},
        "tool_versions": {
            "python": sys.version.split()[0],
        },
    }


def _find_latest_run_result(repo_root: Path) -> Path | None:
    """Busca automáticamente la ejecución QA más reciente cuando se omite --input (S11)."""
    candidate_roots = [
        repo_root / ".agentia-runtime" / "qa",
        repo_root / ".agentia-runtime",
        repo_root / "reports",
        Path.cwd() / ".agentia-runtime" / "qa",
        Path.cwd(),
    ]
    all_runs: list[Path] = []
    for root in candidate_roots:
        if root.is_dir():
            for result_file in root.glob("**/result.json"):
                if result_file.is_file():
                    all_runs.append(result_file)
    if not all_runs:
        return None
    all_runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return all_runs[0]


def _handle_doctor(args: argparse.Namespace) -> int:
    t0 = time.perf_counter()
    repo_root = resolve_repo_root(args.repo)
    cfg = load_and_merge_config(
        repo_root=repo_root,
        known_suites=get_known_suite_ids(),
        cli_java_cache_dir=getattr(args, "java_cache_dir", None),
        cli_browser_cache_dir=getattr(args, "browser_cache_dir", None),
    )
    trace_id = generate_trace_id()
    dur = time.perf_counter() - t0
    report = build_doctor_report(
        repo_root=repo_root,
        trace_id=trace_id,
        duration_seconds=dur,
        java_cache_dir=cfg.java_cache_path,
        browser_cache_dir=cfg.browser_cache_path,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"=== Diagnóstico Local QA ({report['trace_id']}) ===")
        print(f"Repositorio            : {report['repo_root']}")
        print(f"Suite Python elegible  : {'SÍ' if report['python_suite_eligible'] else 'NO'}")
        print(f"Estado general         : {report['status']} (código {report['exit_code']})")
        elig = report.get("suite_eligibility", {})
        if elig:
            print("\nElegibilidad por suite:")
            for s_name, s_ok in elig.items():
                print(f"  - {s_name}: {'ELEGIBLE' if s_ok else 'BLOQUEADA'}")
        print("\nCapacidades obligatorias (Python):")
        for cap in report["capabilities"]:
            if cap["required"]:
                estado = "DISPONIBLE" if cap["available"] else "AUSENTE"
                ver = f" ({cap['version']})" if cap.get("version") else ""
                print(f"  - {cap['name']}{ver}: {estado}")
                if cap.get("reason"):
                    print(f"      Motivo: {cap['reason']}")
        print("\nHerramientas opcionales / por suite:")
        for cap in report["capabilities"]:
            if not cap["required"]:
                estado = "DISPONIBLE" if cap["available"] else "AUSENTE (opcional)"
                print(f"  - {cap['name']}: {estado}")
    return int(report["exit_code"])


def _handle_list(args: argparse.Namespace) -> int:
    t0 = time.perf_counter()
    repo_root = resolve_repo_root(args.repo)
    cfg = load_and_merge_config(
        repo_root=repo_root,
        known_suites=get_known_suite_ids(),
        cli_java_cache_dir=getattr(args, "java_cache_dir", None),
        cli_browser_cache_dir=getattr(args, "browser_cache_dir", None),
    )
    trace_id = generate_trace_id()
    dur = time.perf_counter() - t0
    report = build_list_report(
        repo_root=repo_root,
        trace_id=trace_id,
        duration_seconds=dur,
        java_cache_dir=cfg.java_cache_path,
        browser_cache_dir=cfg.browser_cache_path,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"=== Catálogo de Suites QA ({report['trace_id']}) ===")
        print(f"Repositorio: {report['repo_root']}\n")
        for s in report["suites"]:
            impl_label = "IMPLEMENTADA" if s["implemented"] else "NO IMPLEMENTADA"
            alias_note = f" (alias: {', '.join(s['aliases'])})" if s.get("aliases") else ""
            print(f"- {s['suite_id']}{alias_note} [{impl_label} | motor={s.get('engine')} | estado={s['status']}]")
            print(f"    Descripción : {s['description']}")
            print(f"    Rutas       : {', '.join(s['target_paths'])}")
            if s.get("reason"):
                print(f"    Nota        : {s['reason']}")
    return 0


def _combine_suite_outcomes(
    suite_results: list[dict[str, Any]],
) -> tuple[str, int]:
    """Combina estados según prioridad: INTERRUPTED (130) > ERROR (3) > FAILED (1) > INCOMPLETE (4) > PASSED (0)."""
    if not suite_results:
        return "INCOMPLETE", EXIT_INCOMPLETE

    statuses = {s["status"] for s in suite_results}
    if "INTERRUPTED" in statuses:
        return "INTERRUPTED", EXIT_INTERRUPTED
    if "ERROR" in statuses:
        return "ERROR", EXIT_EXECUTION_ERROR
    if "FAILED" in statuses:
        return "FAILED", EXIT_FAILED
    if "INCOMPLETE" in statuses or "NOT_IMPLEMENTED" in statuses:
        return "INCOMPLETE", EXIT_INCOMPLETE

    total_passed = sum(int(s.get("counts", {}).get("passed", 0)) for s in suite_results)
    if total_passed > 0 and all(s["status"] == "PASSED" for s in suite_results):
        return "PASSED", EXIT_PASSED
    return "INCOMPLETE", EXIT_INCOMPLETE


def _build_scope_note(selected_suites: list[str], suite_results: list[dict[str, Any]]) -> str:
    joined = ", ".join(selected_suites)
    executed_real_java = any(
        (
            s.get("suite_id") == "java"
            or (
                s.get("suite_id") == "playwright"
                and any("compiler=maven-real" in r for r in s.get("reasons", []))
            )
        )
        and s.get("status") in ("PASSED", "FAILED")
        for s in suite_results
    )
    executed_real_browser = any(
        s.get("suite_id") == "playwright" and s.get("status") in ("PASSED", "FAILED")
        for s in suite_results
    )
    missing_scopes: list[str] = []
    if not executed_real_java:
        missing_scopes.append("compilación Java/Maven real")
    if not executed_real_browser:
        missing_scopes.append("navegador Chromium real")
    if missing_scopes:
        return (
            f"Alcance parcial ejecutado: {joined}. "
            f"Esta ejecución valida únicamente las suites seleccionadas y no equivale a validar "
            f"{', '.join(missing_scopes)} ni la plataforma completa."
        )
    return f"Alcance ejecutado: {joined} (incluye verificación real de procesos HTTP, Maven/Quarkus y navegador)."


def _handle_run(args: argparse.Namespace) -> int:
    repo_root = resolve_repo_root(args.repo)
    cfg = load_and_merge_config(
        repo_root=repo_root,
        known_suites=get_known_suite_ids(),
        config_file=args.config,
        cli_suites=args.suites,
        cli_timeout_seconds=args.timeout_seconds,
        cli_output_dir=args.output_dir,
        cli_java_cache_dir=getattr(args, "java_cache_dir", None),
        cli_browser_cache_dir=getattr(args, "browser_cache_dir", None),
        cli_llm_mode=getattr(args, "llm_mode", None),
        cli_llm_provider=getattr(args, "llm_provider", None),
        cli_llm_model=getattr(args, "llm_model", None),
        cli_verify_java=getattr(args, "verify_generated_java", None),
    )

    if getattr(args, "llm_mode", "simulated") == "real" and "llm" not in cfg.suites:
        raise QAConfigError("El modo real de LLM (--llm-mode real) requiere seleccionar la suite 'llm'.")

    trace_id = generate_trace_id()
    start_utc = datetime.datetime.now(datetime.UTC).isoformat()
    t0 = time.perf_counter()

    extra_secrets = collect_sensitive_env_values()
    capabilities, eligibility, suite_reasons = evaluate_suite_eligibilities(
        repo_root=repo_root,
        java_cache_dir=cfg.java_cache_path,
        browser_cache_dir=cfg.browser_cache_path,
    )

    suite_results: list[dict[str, Any]] = []
    all_cases: list[dict[str, Any]] = []
    agg_counts = {
        "collected": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfail": 0,
    }
    overall_reasons: list[str] = []
    sanitized_xml: str | None = None
    suite_artifacts: dict[str, dict[str, str]] = {}
    raw_stdout_acc: list[str] = []
    raw_stderr_acc: list[str] = []
    evidence_dir = cfg.output_path / trace_id

    try:
        for suite_id in cfg.suites:
            s_res, s_arts, s_py_xml, out_str, err_str = dispatch_suite_execution(
                suite_id=suite_id,
                repo_root=repo_root,
                trace_id=trace_id,
                cfg=cfg,
                eligibility=eligibility,
                suite_reasons=suite_reasons,
                extra_secrets=extra_secrets,
            )
            if s_py_xml is not None:
                sanitized_xml = s_py_xml
            if s_arts:
                suite_artifacts[suite_id] = s_arts
            if out_str:
                raw_stdout_acc.append(out_str)
            if err_str:
                raw_stderr_acc.append(err_str)

            suite_results.append(s_res)
            all_cases.extend(s_res.get("cases", []))
            for k in agg_counts:
                agg_counts[k] += int(s_res.get("counts", {}).get(k, 0))
            overall_reasons.extend(s_res.get("reasons", []))

            if s_res.get("status") == "INTERRUPTED":
                break

        end_utc = datetime.datetime.now(datetime.UTC).isoformat()
        total_dur = round(time.perf_counter() - t0, 4)
        overall_status, overall_exit_code = _combine_suite_outcomes(suite_results)

        bounded_log, log_truncated = build_bounded_log(
            raw_stdout="\n".join(raw_stdout_acc),
            raw_stderr="\n".join(raw_stderr_acc),
            extra_secrets=extra_secrets,
        )
        if log_truncated:
            for s in suite_results:
                if s["suite_id"] == "python":
                    s["output_truncated"] = True

        scope_note = _build_scope_note(cfg.suites, suite_results)

        run_result: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "trace_id": trace_id,
            "repo_root": str(repo_root),
            "status": overall_status,
            "exit_code": overall_exit_code,
            "selected_suites": cfg.suites,
            "scope_note": scope_note,
            "start_utc": start_utc,
            "end_utc": end_utc,
            "duration_seconds": total_dur,
            "capabilities": capabilities,
            "suites": suite_results,
            "cases": all_cases,
            "counts": agg_counts,
            "reasons": overall_reasons,
            "provenance": _compute_source_provenance(repo_root),
            "evidence_dir": str(evidence_dir),
            "evidence_files": {},
        }

        persist_run_evidence(
            evidence_dir=evidence_dir,
            run_result=run_result,
            sanitized_xml=sanitized_xml,
            bounded_log=bounded_log,
            extra_secrets=extra_secrets,
            suite_artifacts=suite_artifacts,
        )

        # Análisis IA opcional (Trabajo 7: A04)
        analysis_res = None
        analysis_status = "DISABLED"
        if getattr(args, "ai_analysis", False):
            try:
                from contracts.models import QAAnalysisConfig, QARunResult
                from qa_agent.ai.analysis import run_ai_analysis

                raw_prov = getattr(args, "ai_provider", "gemini")
                prov = "openai" if raw_prov == "gpt" else raw_prov
                default_models = {"gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini", "deepseek": "deepseek-chat"}
                model = getattr(args, "ai_model", None) or default_models.get(prov, "gemini-2.5-flash")
                ai_mode = getattr(args, "ai_mode", "live")
                ai_cfg = QAAnalysisConfig(provider=prov, model=model, mode=ai_mode)
                analysis_res = run_ai_analysis(QARunResult.model_validate(run_result), ai_cfg, run_dir=evidence_dir)
                analysis_status = analysis_res.status
            except Exception:
                analysis_status = "ERROR"

        # Generar manifiesto de reporte y renderizar informe HTML (Trabajo 6: R02 / Trabajo 7: A04)
        delivery_code = overall_exit_code
        try:
            from contracts.models import QADeliveryResult, compute_delivery_exit_code
            from qa_agent.reporting.manifest import generate_report_manifest, write_delivery_result
            from qa_agent.reporting.render import render_html_report

            report_html_path = evidence_dir / "report" / "report.html"
            pre_manifest = generate_report_manifest(evidence_dir, trace_id=trace_id, write_to_disk=False)
            render_html_report(result=run_result, manifest=pre_manifest, analysis=analysis_res, output_path=report_html_path)
            manifest = generate_report_manifest(evidence_dir, trace_id=trace_id, write_to_disk=True)

            delivery_code = compute_delivery_exit_code(
                test_exit_code=overall_exit_code,
                report_status="SUCCESS",
                analysis_status=analysis_status,
            )
            delivery_status = "SUCCESS" if delivery_code == 0 else ("FAILED" if delivery_code == 1 else "ERROR")

            delivery_res = QADeliveryResult(
                schema_version=SCHEMA_VERSION,
                trace_id=trace_id,
                test_status=overall_status,
                test_exit_code=overall_exit_code,
                analysis_status=analysis_status,
                report_status="SUCCESS",
                delivery_status=delivery_status,
                delivery_exit_code=delivery_code,
                test_result_path="result.json",
                report_html_path="report/report.html",
                report_manifest_path="report/report_manifest.json",
                analysis_path="analysis/analysis.json" if analysis_res is not None else None,
            )
            write_delivery_result(evidence_dir, delivery_res)
        except Exception:
            delivery_code = 3 if overall_exit_code == 0 else overall_exit_code

        if args.json:
            print(redact_text(json.dumps(run_result, indent=2, ensure_ascii=False), extra_secrets=extra_secrets))
        else:
            print(format_terminal_summary(run_result, extra_secrets=extra_secrets))

        return delivery_code

    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        # Fallback de persistencia de emergencia (R08)
        try:
            emergency_dir = to_extended_path(evidence_dir)
            emergency_dir.mkdir(parents=True, exist_ok=True)
            emergency_result: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "trace_id": trace_id,
                "repo_root": str(repo_root),
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "selected_suites": getattr(cfg, "suites", []),
                "scope_note": "Ejecución interrumpida por excepción no controlada.",
                "start_utc": start_utc,
                "end_utc": datetime.datetime.now(datetime.UTC).isoformat(),
                "duration_seconds": round(time.perf_counter() - t0, 4),
                "capabilities": capabilities,
                "suites": suite_results,
                "cases": all_cases,
                "counts": agg_counts,
                "reasons": overall_reasons + [f"Fallo crítico no controlado en QA runner: {exc}"],
                "evidence_dir": str(evidence_dir),
                "evidence_files": {},
            }
            safe_write_text(
                emergency_dir / "result.json",
                redact_text(json.dumps(emergency_result, indent=2, ensure_ascii=False), extra_secrets=extra_secrets),
            )
        except Exception:
            pass
        raise


def _handle_report(args: argparse.Namespace) -> int:
    """Reconstruye el informe HTML y manifiesto desde un archivo result.json sin ejecutar subprocesos."""
    input_str = getattr(args, "input", None)
    if not input_str:
        repo_root = resolve_repo_root(getattr(args, "repo", None))
        found = _find_latest_run_result(repo_root)
        if not found:
            sys.stderr.write("Debe especificar la ruta a result.json con --input o tener un run previo en .agentia-runtime/qa/.\n")
            return EXIT_CONFIG_ERROR
        input_path = found
    else:
        input_path = Path(input_str).expanduser().resolve()

    if not input_path.is_file():
        sys.stderr.write(f"No se encontró el archivo de resultado: {input_path}\n")
        return EXIT_CONFIG_ERROR

    try:
        from contracts.models import QARunResult, validate_run_result_consistency
        raw_result = json.loads(input_path.read_text(encoding="utf-8"))
        typed_result = QARunResult.model_validate(raw_result)
        consistency_errors = validate_run_result_consistency(typed_result)
        if consistency_errors:
            sys.stderr.write("Resultado de pruebas inconsistente o contradictorio:\n" + "\n".join(consistency_errors) + "\n")
            return EXIT_EXECUTION_ERROR
    except Exception as exc:
        sys.stderr.write(f"Error al leer result.json: {exc}\n")
        return EXIT_EXECUTION_ERROR

    run_dir = input_path.parent
    output_dir = Path(args.output_dir).resolve() if getattr(args, "output_dir", None) else run_dir / "report"
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis_file = run_dir / "analysis" / "analysis.json"
    analysis_data = None
    analysis_status = "DISABLED"
    if analysis_file.is_file():
        try:
            from contracts.models import QAAnalysisResult
            analysis_data = QAAnalysisResult.model_validate(json.loads(analysis_file.read_text(encoding="utf-8")))
            analysis_status = analysis_data.status
        except Exception:
            analysis_status = "ERROR"

    from contracts.models import QADeliveryResult, compute_delivery_exit_code
    from qa_agent.reporting.manifest import atomic_write_text, generate_report_manifest, write_delivery_result
    from qa_agent.reporting.render import render_html_report

    try:
        report_html_path = output_dir / "report.html"
        pre_manifest = generate_report_manifest(run_dir, trace_id=typed_result.trace_id, write_to_disk=False)
        render_html_report(
            result=typed_result,
            manifest=pre_manifest,
            analysis=analysis_data,
            output_path=report_html_path,
        )
        manifest = generate_report_manifest(run_dir, trace_id=typed_result.trace_id, write_to_disk=True)
        if output_dir != run_dir / "report":
            atomic_write_text(output_dir / "report_manifest.json", manifest.model_dump_json(indent=2))

        delivery_code = compute_delivery_exit_code(
            test_exit_code=typed_result.exit_code,
            report_status="SUCCESS",
            analysis_status=analysis_status,
        )
        delivery_status = "SUCCESS" if delivery_code == 0 else ("FAILED" if delivery_code == 1 else "ERROR")

        rel_result_path = "result.json"
        try:
            if input_path.is_relative_to(run_dir):
                rel_result_path = str(input_path.relative_to(run_dir)).replace("\\", "/")
        except Exception:
            pass

        delivery_res = QADeliveryResult(
            schema_version=SCHEMA_VERSION,
            trace_id=typed_result.trace_id,
            test_status=typed_result.status,
            test_exit_code=typed_result.exit_code,
            analysis_status=analysis_status,
            report_status="SUCCESS",
            delivery_status=delivery_status,
            delivery_exit_code=delivery_code,
            test_result_path=rel_result_path,
            report_html_path="report/report.html",
            report_manifest_path="report/report_manifest.json",
            analysis_path="analysis/analysis.json" if analysis_file.is_file() else None,
        )
        write_delivery_result(run_dir, delivery_res)

        if getattr(args, "json", False):
            print(manifest.model_dump_json(indent=2))
        else:
            print("=== Informe QA Consolidado Generado ===")
            print(f"Traza                  : {typed_result.trace_id}")
            print(f"Estado de pruebas      : {typed_result.status} (código {typed_result.exit_code})")
            print(f"Estado de entrega      : {delivery_status} (código {delivery_code})")
            print(f"Informe HTML           : {report_html_path}")
            print(f"Manifiesto             : {run_dir / 'report' / 'report_manifest.json'}")

        return delivery_code
    except Exception as exc:
        sys.stderr.write(f"Error generando informe o manifiesto: {exc}\n")
        return EXIT_EXECUTION_ERROR


def _handle_analyze(args: argparse.Namespace) -> int:
    """Ejecuta análisis sobre un result.json existente e integra los resultados en el paquete de evidencias."""
    input_str = getattr(args, "input", None)
    if not input_str:
        repo_root = resolve_repo_root(getattr(args, "repo", None))
        found = _find_latest_run_result(repo_root)
        if not found:
            sys.stderr.write("Debe especificar la ruta a result.json con --input o tener un run previo en .agentia-runtime/qa/.\n")
            return EXIT_CONFIG_ERROR
        input_path = found
    else:
        input_path = Path(input_str).expanduser().resolve()

    if not input_path.is_file():
        sys.stderr.write(f"No se encontró el archivo de resultado: {input_path}\n")
        return EXIT_CONFIG_ERROR

    try:
        from contracts.models import QARunResult, validate_run_result_consistency
        raw_result = json.loads(input_path.read_text(encoding="utf-8"))
        typed_result = QARunResult.model_validate(raw_result)
        consistency_errors = validate_run_result_consistency(typed_result)
        if consistency_errors:
            sys.stderr.write("Resultado de pruebas inconsistente o contradictorio:\n" + "\n".join(consistency_errors) + "\n")
            return EXIT_EXECUTION_ERROR
    except Exception as exc:
        sys.stderr.write(f"Error al leer result.json: {exc}\n")
        return EXIT_EXECUTION_ERROR

    run_dir = input_path.parent

    raw_prov = getattr(args, "ai_provider", "gemini")
    prov = "openai" if raw_prov == "gpt" else raw_prov
    default_models = {"gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini", "deepseek": "deepseek-chat"}
    model = getattr(args, "ai_model", None) or default_models.get(prov, "gemini-2.5-flash")
    ai_mode = getattr(args, "ai_mode", "live")

    from contracts.models import QAAnalysisConfig, QADeliveryResult, compute_delivery_exit_code
    from qa_agent.ai.analysis import run_ai_analysis
    from qa_agent.reporting.manifest import generate_report_manifest, write_delivery_result
    from qa_agent.reporting.render import render_html_report

    try:
        ai_cfg = QAAnalysisConfig(provider=prov, model=model, mode=ai_mode)
        analysis_res = run_ai_analysis(typed_result, ai_cfg, run_dir=run_dir)

        report_html_path = run_dir / "report" / "report.html"
        pre_manifest = generate_report_manifest(run_dir, trace_id=typed_result.trace_id, write_to_disk=False)
        render_html_report(result=typed_result, manifest=pre_manifest, analysis=analysis_res, output_path=report_html_path)
        manifest = generate_report_manifest(run_dir, trace_id=typed_result.trace_id, write_to_disk=True)

        delivery_code = compute_delivery_exit_code(
            test_exit_code=typed_result.exit_code,
            report_status="SUCCESS",
            analysis_status=analysis_res.status,
        )
        delivery_status = "SUCCESS" if delivery_code == 0 else ("FAILED" if delivery_code == 1 else "ERROR")

        rel_result_path = "result.json"
        try:
            if input_path.is_relative_to(run_dir):
                rel_result_path = str(input_path.relative_to(run_dir)).replace("\\", "/")
        except Exception:
            pass

        delivery_res = QADeliveryResult(
            schema_version=SCHEMA_VERSION,
            trace_id=typed_result.trace_id,
            test_status=typed_result.status,
            test_exit_code=typed_result.exit_code,
            analysis_status=analysis_res.status,
            report_status="SUCCESS",
            delivery_status=delivery_status,
            delivery_exit_code=delivery_code,
            test_result_path=rel_result_path,
            report_html_path="report/report.html",
            report_manifest_path="report/report_manifest.json",
            analysis_path="analysis/analysis.json",
        )
        write_delivery_result(run_dir, delivery_res)

        if getattr(args, "json", False):
            print(analysis_res.model_dump_json(indent=2))
        else:
            print("=== Análisis IA de Resultados QA ===")
            print(f"Traza                  : {typed_result.trace_id}")
            print(f"Proveedor / Modelo     : {analysis_res.provider} / {analysis_res.model}")
            print(f"Estado del análisis    : {analysis_res.status}")
            if analysis_res.error_reason:
                print(f"Detalle / Bloqueo      : {analysis_res.error_reason}")
            if analysis_res.hypotheses:
                print(f"Hipótesis identificadas: {len(analysis_res.hypotheses)}")
                for idx, h in enumerate(analysis_res.hypotheses, 1):
                    print(f"  {idx}. [{h.likelihood.upper()}] {h.cause}")
                    if h.suggested_action:
                        print(f"     Acción sugerida: {h.suggested_action}")
            print(f"Archivo generado       : {run_dir / 'analysis' / 'analysis.json'}")

        return delivery_code
    except Exception as exc:
        sys.stderr.write(f"Error ejecutando análisis IA: {exc}\n")
        return EXIT_EXECUTION_ERROR


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()

    if not effective_argv:
        parser.print_help(sys.stdout)
        return EXIT_CONFIG_ERROR

    try:
        _check_unimplemented_ai_flags(effective_argv)
        args = parser.parse_args(effective_argv)
        if args.subcommand == "doctor":
            return _handle_doctor(args)
        if args.subcommand == "list":
            return _handle_list(args)
        if args.subcommand == "run":
            return _handle_run(args)
        if args.subcommand == "report":
            return _handle_report(args)
        if args.subcommand == "analyze":
            return _handle_analyze(args)
        parser.print_help(sys.stdout)
        return EXIT_CONFIG_ERROR
    except QAConfigError as exc:
        sys.stderr.write(f"Error de configuración (código {EXIT_CONFIG_ERROR}): {exc}\n")
        return EXIT_CONFIG_ERROR
    except KeyboardInterrupt:
        sys.stderr.write(f"Ejecución interrumpida por el usuario (código {EXIT_INTERRUPTED}).\n")
        return EXIT_INTERRUPTED
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EXIT_CONFIG_ERROR
        return code
    except (OSError, RuntimeError, ValueError) as exc:
        sys.stderr.write(f"Error interno de ejecución QA (código {EXIT_EXECUTION_ERROR}): {exc}\n")
        return EXIT_EXECUTION_ERROR
