from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from qa_agent import (
    EXIT_EXECUTION_ERROR,
    EXIT_INTERRUPTED,
)
from qa_agent.evidence import build_bounded_log
from qa_agent.execution import (
    IsolatedWorkspace,
    cleanup_isolated_workspace,
    prepare_isolated_workspace,
    run_bounded_subprocess,
)
from qa_agent.result_normalization import validate_and_parse_junit_xml

PLATFORM_ENGINE = "pytest+http-harness"
PLATFORM_BOUNDARY_PROFILE = {
    "http": "real",
    "llm": "double",
    "compiler": "double",
    "java_verified": False,
}


def run_platform_suite(
    repo_root: Path,
    trace_id: str,
    timeout_seconds: int = 180,
    extra_secrets: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, str], str | None, str, str]:
    """
    Ejecuta la suite `platform` (Trabajo 3) sobre sockets loopback reales (`127.0.0.1`)
    y 5 procesos FastAPI, con fronteras controladas `http=real`, `llm=double`, `compiler=double`.
    """
    workspace: IsolatedWorkspace | None = None
    try:
        workspace = prepare_isolated_workspace(
            repo_root=repo_root,
            trace_id=f"{trace_id}-platform",
            suite_id="platform",
        )
        scenarios_dir = workspace.repo_copy / "qa_scenarios" / "platform"
        raw_xml_path = workspace.scratch_root / "raw-platform.junit.xml"

        argv = [
            sys.executable,
            "-m",
            "pytest",
            str(scenarios_dir),
            "-o",
            f"cache_dir={workspace.pytest_cache}",
            f"--basetemp={workspace.pytest_basetemp}",
            f"--junitxml={raw_xml_path}",
            "--tb=short",
            "-q",
        ]
        k_filter = os.environ.get("QA_PLATFORM_PYTEST_K", "").strip()
        if k_filter:
            argv.extend(["-k", k_filter])

        env = dict(workspace.env)
        existing_py = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{workspace.repo_copy}{os.pathsep}{existing_py}"
            if existing_py
            else str(workspace.repo_copy)
        )

        min_mtime = time.time() - 1.0
        outcome = run_bounded_subprocess(
            argv=argv,
            cwd=workspace.repo_copy,
            env=env,
            timeout_seconds=timeout_seconds,
        )

        if outcome.interrupted:
            reason = "Ejecución de la suite 'platform' interrumpida por el usuario."
            return (
                {
                    "suite_id": "platform",
                    "implemented": True,
                    "status": "INTERRUPTED",
                    "exit_code": EXIT_INTERRUPTED,
                    "engine": PLATFORM_ENGINE,
                    "process_exit_code": None,
                    "pytest_exit_code": None,
                    "timed_out": False,
                    "interrupted": True,
                    "output_truncated": outcome.output_truncated,
                    "duration_seconds": outcome.duration_seconds,
                    "counts": {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0},
                    "cases": [],
                    "steps": [],
                    "reasons": [reason],
                    "evidence_files": {},
                },
                {},
                None,
                outcome.stdout,
                outcome.stderr,
            )

        if outcome.timed_out:
            reason = f"La suite 'platform' excedió el presupuesto de tiempo ({timeout_seconds}s)."
            bounded_log, _ = build_bounded_log(outcome.stdout, outcome.stderr, extra_secrets=extra_secrets)
            return (
                {
                    "suite_id": "platform",
                    "implemented": True,
                    "status": "ERROR",
                    "exit_code": EXIT_EXECUTION_ERROR,
                    "engine": PLATFORM_ENGINE,
                    "process_exit_code": None,
                    "pytest_exit_code": None,
                    "timed_out": True,
                    "interrupted": False,
                    "output_truncated": outcome.output_truncated,
                    "duration_seconds": outcome.duration_seconds,
                    "counts": {"collected": 0, "passed": 0, "failed": 0, "errors": 1, "skipped": 0, "xfail": 0},
                    "cases": [],
                    "steps": [
                        {
                            "step_id": "platform-pytest-http",
                            "kind": "test",
                            "status": "ERROR",
                            "exit_code": None,
                            "duration_seconds": outcome.duration_seconds,
                            "command": argv,
                            "diagnostic": reason,
                        }
                    ],
                    "reasons": [reason],
                    "evidence_files": {},
                },
                {"platform.log": bounded_log},
                None,
                outcome.stdout,
                outcome.stderr,
            )

        norm = validate_and_parse_junit_xml(
            xml_path=raw_xml_path,
            suite_id="platform",
            engine=PLATFORM_ENGINE,
            process_exit_code=outcome.exit_code,
            min_mtime=min_mtime,
            extra_secrets=extra_secrets,
        )

        bounded_log, log_trunc = build_bounded_log(outcome.stdout, outcome.stderr, extra_secrets=extra_secrets)
        reasons = list(norm["reasons"])
        reasons.append(
            "Fronteras de ejecución platform: http=real, llm=double, compiler=double (sin compilación Java real en esta suite)."
        )

        step_status = "PASSED" if norm["status"] == "PASSED" else ("FAILED" if norm["status"] == "FAILED" else "ERROR")
        steps = [
            {
                "step_id": "platform-pytest-http",
                "kind": "test",
                "status": step_status,
                "exit_code": outcome.exit_code,
                "duration_seconds": outcome.duration_seconds,
                "command": ["python", "-m", "pytest", "qa_scenarios/platform"],
                "diagnostic": "; ".join(norm["reasons"]) if norm["reasons"] else None,
            }
        ]

        artifacts: dict[str, str] = {
            "platform.log": bounded_log,
            "boundary_profile.json": json.dumps(PLATFORM_BOUNDARY_PROFILE, indent=2) + "\n",
        }
        if norm.get("sanitized_xml"):
            artifacts["junit.xml"] = str(norm["sanitized_xml"])

        suite_result = {
            "suite_id": "platform",
            "implemented": True,
            "status": norm["status"],
            "exit_code": norm["exit_code"],
            "engine": PLATFORM_ENGINE,
            "process_exit_code": outcome.exit_code,
            "pytest_exit_code": outcome.exit_code,
            "timed_out": False,
            "interrupted": False,
            "output_truncated": outcome.output_truncated or log_trunc,
            "duration_seconds": outcome.duration_seconds,
            "counts": norm["counts"],
            "cases": norm["cases"],
            "steps": steps,
            "reasons": reasons,
            "evidence_files": {},
        }
        return suite_result, artifacts, None, outcome.stdout, outcome.stderr
    finally:
        if workspace is not None:
            cleanup_isolated_workspace(workspace=workspace, user_repo_root=repo_root)
