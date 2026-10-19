"""Registro y despacho de adaptadores por suite (C03)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from qa_agent import (
    EXIT_EXECUTION_ERROR,
    EXIT_INCOMPLETE,
    EXIT_INTERRUPTED,
)
from qa_agent.catalog import KNOWN_SUITES
from qa_agent.config import ResolvedQAConfig, normalize_suite_id
from qa_agent.execution import (
    IsolatedWorkspace,
    cleanup_isolated_workspace,
    prepare_isolated_workspace,
)
from qa_agent.pytest_adapter import parse_and_evaluate_pytest_run


def _empty_counts() -> dict[str, int]:
    return {
        "collected": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfail": 0,
    }


def dispatch_suite_execution(
    suite_id: str,
    repo_root: Path,
    trace_id: str,
    cfg: ResolvedQAConfig,
    eligibility: dict[str, bool],
    suite_reasons: dict[str, list[str]],
    extra_secrets: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, str], str | None, str, str]:
    """
    Despacha la ejecución de una suite canónica registrada.
    Devuelve: (suite_result_dict, artifacts_dict, sanitized_python_xml, raw_stdout, raw_stderr).
    """
    canonical_id = normalize_suite_id(suite_id)
    meta = KNOWN_SUITES[canonical_id]
    engine = str(meta.get("engine", "pytest"))
    timeout_seconds = cfg.get_suite_timeout(canonical_id)

    if not meta.get("implemented", True):
        reason = meta.get(
            "reason",
            f"La suite '{canonical_id}' está registrada pero NO IMPLEMENTADA en este incremento.",
        )
        return (
            {
                "suite_id": canonical_id,
                "implemented": False,
                "status": "NOT_IMPLEMENTED",
                "exit_code": EXIT_INCOMPLETE,
                "engine": engine,
                "process_exit_code": None,
                "pytest_exit_code": None,
                "timed_out": False,
                "interrupted": False,
                "output_truncated": False,
                "duration_seconds": 0.0,
                "counts": _empty_counts(),
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

    is_eligible = eligibility.get(canonical_id, False)
    s_reasons = list(suite_reasons.get(canonical_id, []))
    if not is_eligible:
        if not s_reasons:
            s_reasons = [f"Requisitos de entorno no satisfechos para la suite '{canonical_id}'."]
        return (
            {
                "suite_id": canonical_id,
                "implemented": True,
                "status": "INCOMPLETE",
                "exit_code": EXIT_INCOMPLETE,
                "engine": engine,
                "process_exit_code": None,
                "pytest_exit_code": None,
                "timed_out": False,
                "interrupted": False,
                "output_truncated": False,
                "duration_seconds": 0.0,
                "counts": _empty_counts(),
                "cases": [],
                "steps": [],
                "reasons": s_reasons,
                "evidence_files": {},
            },
            {},
            None,
            "\n".join(s_reasons),
            "",
        )

    suite_t0 = time.perf_counter()
    try:
        if canonical_id == "python":
            workspace: IsolatedWorkspace | None = None
            try:
                workspace = prepare_isolated_workspace(repo_root=repo_root, trace_id=trace_id)
                py_res, sanitized_xml, out_str, err_str = parse_and_evaluate_pytest_run(
                    workspace=workspace,
                    timeout_seconds=timeout_seconds,
                    extra_secrets=extra_secrets,
                )
                return py_res, {}, sanitized_xml, out_str, err_str
            finally:
                if workspace is not None:
                    cleanup_isolated_workspace(workspace=workspace, user_repo_root=repo_root)

        if canonical_id == "platform":
            from qa_agent.adapters.platform import run_platform_suite

            return run_platform_suite(
                repo_root=repo_root,
                trace_id=trace_id,
                timeout_seconds=timeout_seconds,
                extra_secrets=extra_secrets,
            )

        if canonical_id == "java":
            from qa_agent.adapters.java import run_java_suite

            return run_java_suite(
                repo_root=repo_root,
                trace_id=trace_id,
                timeout_seconds=timeout_seconds,
                java_cache_dir=cfg.java_cache_path,
                extra_secrets=extra_secrets,
            )

        if canonical_id == "frontend":
            from qa_agent.adapters.frontend import run_frontend_suite

            return run_frontend_suite(
                repo_root=repo_root,
                trace_id=trace_id,
                timeout_seconds=timeout_seconds,
                extra_secrets=extra_secrets,
            )

        if canonical_id == "playwright":
            from qa_agent.adapters.playwright import run_playwright_suite

            return run_playwright_suite(
                repo_root=repo_root,
                trace_id=trace_id,
                timeout_seconds=timeout_seconds,
                java_cache_dir=cfg.java_cache_path,
                browser_cache_dir=cfg.browser_cache_path,
                extra_secrets=extra_secrets,
            )

        if canonical_id == "llm":
            from qa_agent.adapters.llm import run_llm_suite

            return run_llm_suite(
                repo_root=repo_root,
                trace_id=trace_id,
                timeout_seconds=timeout_seconds,
                llm_mode=getattr(cfg, "llm_mode", "simulated"),
                llm_provider=getattr(cfg, "llm_provider", "gemini"),
                llm_model=getattr(cfg, "llm_model", None),
                verify_generated_java=getattr(cfg, "verify_generated_java", False),
                java_cache_dir=cfg.java_cache_path,
                extra_secrets=extra_secrets,
            )

        raise ValueError(f"No existe adaptador registrado para la suite '{canonical_id}'.")

    except KeyboardInterrupt:
        suite_dur = round(time.perf_counter() - suite_t0, 4)
        int_reason = f"Ejecución de la suite '{canonical_id}' interrumpida por el usuario."
        return (
            {
                "suite_id": canonical_id,
                "implemented": True,
                "status": "INTERRUPTED",
                "exit_code": EXIT_INTERRUPTED,
                "engine": engine,
                "process_exit_code": None,
                "pytest_exit_code": None,
                "timed_out": False,
                "interrupted": True,
                "output_truncated": False,
                "duration_seconds": suite_dur,
                "counts": _empty_counts(),
                "cases": [],
                "steps": [],
                "reasons": [int_reason],
                "evidence_files": {},
            },
            {},
            None,
            "",
            int_reason,
        )
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        suite_dur = round(time.perf_counter() - suite_t0, 4)
        err_reason = f"Error al preparar o ejecutar el entorno aislado de la suite '{canonical_id}': {exc}"
        return (
            {
                "suite_id": canonical_id,
                "implemented": True,
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "engine": engine,
                "process_exit_code": None,
                "pytest_exit_code": None,
                "timed_out": False,
                "interrupted": False,
                "output_truncated": False,
                "duration_seconds": suite_dur,
                "counts": _empty_counts(),
                "cases": [],
                "steps": [],
                "reasons": [err_reason],
                "evidence_files": {},
            },
            {},
            None,
            "",
            err_reason,
        )
