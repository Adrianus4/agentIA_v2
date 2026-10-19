"""Adaptador determinista para pytest con interpretación combinada de código de proceso y JUnit XML (E06, F01)."""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from qa_agent import (
    EXIT_EXECUTION_ERROR,
    EXIT_FAILED,
    EXIT_INCOMPLETE,
    EXIT_INTERRUPTED,
    EXIT_PASSED,
)
from qa_agent.evidence import sanitize_junit_tree, summarize_diagnostic_text
from qa_agent.execution import IsolatedWorkspace, run_bounded_subprocess


def build_pytest_argv(workspace: IsolatedWorkspace) -> list[str]:
    """Construye el argv registrado para ejecutar pytest sobre tests/."""
    return [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        f"--basetemp={workspace.pytest_basetemp}",
        f"--junitxml={workspace.raw_xml_path}",
        "-o",
        f"cache_dir={workspace.pytest_cache}",
    ]


def _apply_simulated_xml_anomaly(xml_path: Path) -> None:
    anomaly = os.environ.get("QA_SIMULATE_XML_ANOMALY", "").strip().lower()
    if not anomaly:
        return
    if anomaly == "missing":
        if xml_path.exists():
            xml_path.unlink()
    elif anomaly == "corrupt":
        xml_path.write_text("<testsuites><testsuite tests='1'><unclosed>", encoding="utf-8")
    elif anomaly == "disagree":
        xml_path.write_text(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<testsuites><testsuite name="pytest" errors="0" failures="1" skipped="0" tests="1" time="0.01">'
            '<testcase classname="tests.test_fake" name="test_disagree" time="0.01">'
            '<failure message="forced failure">forced</failure></testcase></testsuite></testsuites>',
            encoding="utf-8",
        )


def _parse_non_negative_int_attr(elem: ET.Element, attr_name: str) -> int | None:
    raw = elem.attrib.get(attr_name, "0")
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return None
    return val if val >= 0 else None


def parse_and_evaluate_pytest_run(
    workspace: IsolatedWorkspace,
    timeout_seconds: int,
    extra_secrets: list[str] | None = None,
) -> tuple[dict[str, Any], str | None, str, str]:
    """Ejecuta pytest en el workspace aislado y evalúa XML + código de salida real."""
    argv = build_pytest_argv(workspace)
    outcome = run_bounded_subprocess(
        argv=argv,
        cwd=workspace.repo_copy,
        env=workspace.env,
        timeout_seconds=timeout_seconds,
    )

    _apply_simulated_xml_anomaly(workspace.raw_xml_path)

    counts = {
        "collected": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfail": 0,
    }
    cases: list[dict[str, Any]] = []
    reasons: list[str] = []
    sanitized_xml_str: str | None = None

    if outcome.interrupted:
        reasons.append("Ejecución interrumpida por el usuario (código 130).")
        return (
            {
                "suite_id": "python",
                "implemented": True,
                "status": "INTERRUPTED",
                "exit_code": EXIT_INTERRUPTED,
                "engine": "pytest",
                "process_exit_code": outcome.exit_code,
                "pytest_exit_code": outcome.exit_code,
                "timed_out": False,
                "interrupted": True,
                "output_truncated": outcome.output_truncated,
                "duration_seconds": outcome.duration_seconds,
                "counts": counts,
                "cases": cases,
                "steps": [],
                "reasons": reasons,
                "evidence_files": {},
            },
            None,
            outcome.stdout,
            outcome.stderr,
        )

    if outcome.timed_out:
        reasons.append(f"La suite python excedió el tiempo máximo de {timeout_seconds} segundos.")
        return (
            {
                "suite_id": "python",
                "implemented": True,
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "engine": "pytest",
                "process_exit_code": outcome.exit_code,
                "pytest_exit_code": outcome.exit_code,
                "timed_out": True,
                "interrupted": False,
                "output_truncated": outcome.output_truncated,
                "duration_seconds": outcome.duration_seconds,
                "counts": counts,
                "cases": cases,
                "steps": [],
                "reasons": reasons,
                "evidence_files": {},
            },
            None,
            outcome.stdout,
            outcome.stderr,
        )

    if not workspace.raw_xml_path.is_file():
        reasons.append("No se generó el artefacto XML de evidencia (python.junit.xml ausente).")
        return (
            {
                "suite_id": "python",
                "implemented": True,
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "engine": "pytest",
                "process_exit_code": outcome.exit_code,
                "pytest_exit_code": outcome.exit_code,
                "timed_out": False,
                "interrupted": False,
                "output_truncated": outcome.output_truncated,
                "duration_seconds": outcome.duration_seconds,
                "counts": counts,
                "cases": cases,
                "steps": [],
                "reasons": reasons,
                "evidence_files": {},
            },
            None,
            outcome.stdout,
            outcome.stderr,
        )

    try:
        tree = ET.parse(workspace.raw_xml_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        reasons.append(f"El artefacto XML de pytest está corrupto o mal formado: {exc}")
        return (
            {
                "suite_id": "python",
                "implemented": True,
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "engine": "pytest",
                "process_exit_code": outcome.exit_code,
                "pytest_exit_code": outcome.exit_code,
                "timed_out": False,
                "interrupted": False,
                "output_truncated": outcome.output_truncated,
                "duration_seconds": outcome.duration_seconds,
                "counts": counts,
                "cases": cases,
                "steps": [],
                "reasons": reasons,
                "evidence_files": {},
            },
            None,
            outcome.stdout,
            outcome.stderr,
        )

    suites = list(root.findall("testsuite")) if root.tag == "testsuites" else ([root] if root.tag == "testsuite" else [])
    if not suites:
        reasons.append("El XML generado no contiene elementos <testsuite> válidos.")
        return (
            {
                "suite_id": "python",
                "implemented": True,
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "engine": "pytest",
                "process_exit_code": outcome.exit_code,
                "pytest_exit_code": outcome.exit_code,
                "timed_out": False,
                "interrupted": False,
                "output_truncated": outcome.output_truncated,
                "duration_seconds": outcome.duration_seconds,
                "counts": counts,
                "cases": cases,
                "steps": [],
                "reasons": reasons,
                "evidence_files": {},
            },
            None,
            outcome.stdout,
            outcome.stderr,
        )

    xml_tests = 0
    xml_failures = 0
    xml_errors = 0
    xml_skipped = 0
    xml_attrs_valid = True

    for s in suites:
        t_val = _parse_non_negative_int_attr(s, "tests")
        f_val = _parse_non_negative_int_attr(s, "failures")
        e_val = _parse_non_negative_int_attr(s, "errors")
        sk_val = _parse_non_negative_int_attr(s, "skipped")
        if None in (t_val, f_val, e_val, sk_val):
            xml_attrs_valid = False
            break
        xml_tests += t_val  # type: ignore[operator]
        xml_failures += f_val  # type: ignore[operator]
        xml_errors += e_val  # type: ignore[operator]
        xml_skipped += sk_val  # type: ignore[operator]

    for s in suites:
        for tc in s.findall("testcase"):
            cname = tc.attrib.get("classname", "")
            tname = tc.attrib.get("name", "unknown")
            try:
                tdur = float(tc.attrib.get("time", "0") or 0.0)
                if tdur < 0.0:
                    xml_attrs_valid = False
                    tdur = 0.0
            except ValueError:
                xml_attrs_valid = False
                tdur = 0.0

            failure_el = tc.find("failure")
            error_el = tc.find("error")
            skipped_el = tc.find("skipped")
            msg: str | None = None

            if error_el is not None:
                c_status = "ERROR"
                raw_msg = (error_el.attrib.get("message", "") + "\n" + (error_el.text or "")).strip()
                msg = summarize_diagnostic_text(raw_msg, extra_secrets=extra_secrets)
                counts["errors"] += 1
            elif failure_el is not None:
                c_status = "FAILED"
                raw_msg = (failure_el.attrib.get("message", "") + "\n" + (failure_el.text or "")).strip()
                msg = summarize_diagnostic_text(raw_msg, extra_secrets=extra_secrets)
                counts["failed"] += 1
            elif skipped_el is not None:
                skip_type = (skipped_el.attrib.get("type", "") or "").lower()
                raw_msg = (skipped_el.attrib.get("message", "") or (skipped_el.text or "")).strip()
                msg = summarize_diagnostic_text(raw_msg, extra_secrets=extra_secrets) if raw_msg else None
                if "xfail" in skip_type:
                    c_status = "XFAIL"
                    counts["xfail"] += 1
                else:
                    c_status = "SKIPPED"
                    counts["skipped"] += 1
            else:
                c_status = "PASSED"
                msg = None
                counts["passed"] += 1

            cases.append(
                {
                    "classname": cname,
                    "name": tname,
                    "status": c_status,
                    "duration_seconds": round(tdur, 4),
                    "message": msg,
                    "suite_id": "python",
                    "engine": "pytest",
                }
            )

    sanitized_xml_str = sanitize_junit_tree(root, extra_secrets=extra_secrets)

    # Validar consistencia interna estricta del XML (F01 / CA-10)
    total_case_outcomes = (
        counts["passed"] + counts["failed"] + counts["errors"] + counts["skipped"] + counts["xfail"]
    )
    xml_consistent = (
        xml_attrs_valid
        and xml_tests == len(cases)
        and xml_tests == total_case_outcomes
        and xml_failures == counts["failed"]
        and xml_errors == counts["errors"]
        and xml_skipped == (counts["skipped"] + counts["xfail"])
    )
    counts["collected"] = len(cases) if xml_consistent else max(0, xml_tests)

    if not xml_consistent:
        reasons.append(
            "El XML JUnit es internamente inconsistente: los atributos de testsuite "
            f"(tests={xml_tests}, failures={xml_failures}, errors={xml_errors}, skipped={xml_skipped}) "
            f"no coinciden con los elementos testcase observados (casos={len(cases)}, "
            f"passed={counts['passed']}, failed={counts['failed']}, errors={counts['errors']}, "
            f"skipped={counts['skipped'] + counts['xfail']})."
        )
        status = "ERROR"
        exit_code = EXIT_EXECUTION_ERROR
    # 1. Ausencia de casos recolectados (pytest exit code 5 o 0 casos en XML)
    elif outcome.exit_code == 5 or (counts["collected"] == 0 and counts["errors"] == 0 and outcome.exit_code in (0, 5)):
        reasons.append("No se recolectaron casos de prueba en la suite python (0 casos).")
        status = "INCOMPLETE"
        exit_code = EXIT_INCOMPLETE
    # 2. Verificar consistencia entre código del proceso y conteos del XML (CA-10)
    elif outcome.exit_code == 0 and (counts["failed"] > 0 or counts["errors"] > 0):
        reasons.append(
            f"Desacuerdo entre proceso pytest (código 0) y XML (fallos={counts['failed']}, errores={counts['errors']})."
        )
        status = "ERROR"
        exit_code = EXIT_EXECUTION_ERROR
    elif outcome.exit_code != 0 and counts["failed"] == 0 and counts["errors"] == 0:
        reasons.append(
            f"El proceso pytest terminó con código {outcome.exit_code} pero el XML no reportó fallos ni errores."
        )
        status = "ERROR"
        exit_code = EXIT_EXECUTION_ERROR
    # 3. Prioridad: ERROR (3) > FAILED (1) > INCOMPLETE (4) > PASSED (0)
    elif counts["errors"] > 0 or outcome.exit_code in (2, 3, 4):
        reasons.append(f"Se detectaron {counts['errors']} errores de colección o ejecución en pytest.")
        status = "ERROR"
        exit_code = EXIT_EXECUTION_ERROR
    elif counts["failed"] > 0:
        reasons.append(f"Se detectaron {counts['failed']} pruebas con aserciones fallidas.")
        if counts["skipped"] > 0 or counts["xfail"] > 0:
            reasons.append(
                f"Además se registraron {counts['skipped']} pruebas omitidas y {counts['xfail']} xfail."
            )
        status = "FAILED"
        exit_code = EXIT_FAILED
    elif counts["skipped"] > 0 or counts["xfail"] > 0:
        reasons.append(
            f"Ejecución incompleta: {counts['skipped']} pruebas omitidas y {counts['xfail']} xfail pendientes."
        )
        status = "INCOMPLETE"
        exit_code = EXIT_INCOMPLETE
    elif counts["passed"] > 0 and outcome.exit_code == 0:
        status = "PASSED"
        exit_code = EXIT_PASSED
    else:
        reasons.append("Resultado no concluyente de pytest.")
        status = "ERROR"
        exit_code = EXIT_EXECUTION_ERROR

    if outcome.output_truncated:
        reasons.append("La salida estándar/error del proceso excedió el límite y fue truncada.")

    return (
        {
            "suite_id": "python",
            "implemented": True,
            "status": status,
            "exit_code": exit_code,
            "engine": "pytest",
            "process_exit_code": outcome.exit_code,
            "pytest_exit_code": outcome.exit_code,
            "timed_out": False,
            "interrupted": False,
            "output_truncated": outcome.output_truncated,
            "duration_seconds": outcome.duration_seconds,
            "counts": counts,
            "cases": cases,
            "steps": [],
            "reasons": reasons,
            "evidence_files": {},
        },
        sanitized_xml_str,
        outcome.stdout,
        outcome.stderr,
    )
