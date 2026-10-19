"""Normalización y validación estricta de reportes por dialecto (pytest, Surefire, Vitest, Playwright) (C04, RF-311)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from qa_agent import (
    EXIT_EXECUTION_ERROR,
    EXIT_FAILED,
    EXIT_INCOMPLETE,
    EXIT_PASSED,
)
from qa_agent.evidence import redact_text, sanitize_junit_tree, summarize_diagnostic_text


def _parse_int_attr(elem: ET.Element, attr: str, default: int | None = None) -> int | None:
    raw = elem.attrib.get(attr)
    if raw is None:
        return default
    try:
        val = int(raw)
    except ValueError:
        return None
    return val if val >= 0 else None


def validate_and_parse_junit_xml(
    xml_path: Path,
    suite_id: str,
    engine: str,
    process_exit_code: int,
    min_mtime: float | None = None,
    fixture_id: str | None = None,
    app_trace_id: str | None = None,
    extra_secrets: list[str] | None = None,
    strict_all_attrs: bool = True,
    dialect: str | None = None,
) -> dict[str, Any]:
    """
    Valida un archivo JUnit XML (pytest, Surefire, Vitest o Playwright) comprobando:
    - Existencia y tamaño no vacío
    - Frescura respecto a `min_mtime` (rechaza reportes antiguos/obsoletos)
    - Bien formado sintáctico y presencia de `<testsuite>`
    - Consistencia interna F01 entre atributos de `<testsuite>` y nodos `<testcase>`
    - Concordancia con `process_exit_code`
    """
    if dialect in ("vitest", "playwright"):
        strict_all_attrs = False
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

    if not xml_path.is_file() or xml_path.stat().st_size == 0:
        reasons.append(f"El artefacto XML de '{suite_id}' no existe o está vacío: {xml_path.name}")
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": None,
        }

    if min_mtime is not None:
        actual_mtime = xml_path.stat().st_mtime
        if actual_mtime + 0.05 < min_mtime:
            reasons.append(
                f"El reporte XML '{xml_path.name}' de '{suite_id}' es antiguo u obsoleto "
                f"(mtime={actual_mtime:.3f} < inicio={min_mtime:.3f}); se exige evidencia fresca."
            )
            return {
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "counts": counts,
                "cases": cases,
                "reasons": reasons,
                "sanitized_xml": None,
            }

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        reasons.append(f"El artefacto XML '{xml_path.name}' de '{suite_id}' está corrupto o mal formado: {exc}")
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": None,
        }

    suites = (
        list(root.findall("testsuite"))
        if root.tag == "testsuites"
        else ([root] if root.tag == "testsuite" else [])
    )
    if not suites:
        reasons.append(f"El XML '{xml_path.name}' de '{suite_id}' no contiene elementos <testsuite> válidos.")
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": None,
        }

    xml_tests = 0
    xml_failures = 0
    xml_errors = 0
    xml_skipped = 0
    xml_attrs_valid = True

    for s in suites:
        t_val = _parse_int_attr(s, "tests", default=None)
        f_val = _parse_int_attr(s, "failures", default=None)
        e_val = _parse_int_attr(s, "errors", default=None if strict_all_attrs else 0)
        sk_val = _parse_int_attr(s, "skipped", default=None if strict_all_attrs else 0)
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
                skip_type = skipped_el.attrib.get("type", "").lower()
                raw_msg = (skipped_el.attrib.get("message", "") + "\n" + (skipped_el.text or "")).strip()
                msg = summarize_diagnostic_text(raw_msg, extra_secrets=extra_secrets) if raw_msg else None
                if "xfail" in skip_type:
                    c_status = "XFAIL"
                    counts["xfail"] += 1
                else:
                    c_status = "SKIPPED"
                    counts["skipped"] += 1
            else:
                c_status = "PASSED"
                counts["passed"] += 1

            cases.append(
                {
                    "classname": cname,
                    "name": tname,
                    "status": c_status,
                    "duration_seconds": round(tdur, 4),
                    "message": msg,
                    "suite_id": suite_id,
                    "fixture_id": fixture_id,
                    "app_trace_id": app_trace_id,
                    "engine": engine,
                }
            )

    counts["collected"] = len(cases)
    sanitized_xml_str = sanitize_junit_tree(root, extra_secrets=extra_secrets)

    xml_internally_consistent = (
        xml_attrs_valid
        and xml_tests == len(cases)
        and xml_failures == counts["failed"]
        and xml_errors == counts["errors"]
        and xml_skipped == (counts["skipped"] + counts["xfail"])
        and len(cases) == (
            counts["passed"] + counts["failed"] + counts["errors"] + counts["skipped"] + counts["xfail"]
        )
    )
    if not xml_internally_consistent:
        reasons.append(
            f"Inconsistencia interna en XML '{xml_path.name}' de '{suite_id}': atributos de <testsuite> "
            f"(tests={xml_tests}, failures={xml_failures}, errors={xml_errors}, skipped={xml_skipped}, "
            f"attrs_valid={xml_attrs_valid}) no coinciden con los <testcase> reales "
            f"(total={len(cases)}, passed={counts['passed']}, failed={counts['failed']}, "
            f"errors={counts['errors']}, skipped={counts['skipped']}, xfail={counts['xfail']})."
        )
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": sanitized_xml_str,
        }

    has_xml_problems = (counts["failed"] + counts["errors"]) > 0
    if process_exit_code == 0 and has_xml_problems:
        reasons.append(
            f"Contradicción en '{suite_id}': el proceso devolvió código 0 pero el XML reporta "
            f"fallos={counts['failed']}, errores={counts['errors']}."
        )
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": sanitized_xml_str,
        }

    if process_exit_code == 1 and not has_xml_problems:
        reasons.append(
            f"Contradicción en '{suite_id}': el proceso devolvió código 1 pero el XML reporta 0 fallos y 0 errores."
        )
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": sanitized_xml_str,
        }

    if process_exit_code not in (0, 1, 5):
        reasons.append(
            f"El motor '{engine}' de '{suite_id}' finalizó con código de error o colección ({process_exit_code})."
        )
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": sanitized_xml_str,
        }

    if counts["errors"] > 0 and process_exit_code != 1:
        reasons.append(f"Se detectaron {counts['errors']} errores de ejecución/colección en '{suite_id}'.")
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": sanitized_xml_str,
        }

    if counts["collected"] == 0 or process_exit_code == 5:
        reasons.append(f"Selección vacía en '{suite_id}': se recolectaron 0 casos de prueba.")
        return {
            "status": "INCOMPLETE",
            "exit_code": EXIT_INCOMPLETE,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": sanitized_xml_str,
        }

    if counts["failed"] > 0 or counts["errors"] > 0:
        reasons.append(
            f"La suite '{suite_id}' presentó {counts['failed']} fallos y {counts['errors']} errores."
        )
        if counts["skipped"] > 0 or counts["xfail"] > 0:
            reasons.append(
                f"Además se registraron {counts['skipped']} pruebas omitidas y {counts['xfail']} xfail."
            )
        return {
            "status": "FAILED",
            "exit_code": EXIT_FAILED,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": sanitized_xml_str,
        }

    if counts["skipped"] > 0 or counts["xfail"] > 0:
        reasons.append(
            f"Ejecución incompleta en '{suite_id}': se registraron {counts['skipped']} pruebas omitidas "
            f"y {counts['xfail']} xfail sin cobertura completa."
        )
        return {
            "status": "INCOMPLETE",
            "exit_code": EXIT_INCOMPLETE,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
            "sanitized_xml": sanitized_xml_str,
        }

    return {
        "status": "PASSED",
        "exit_code": EXIT_PASSED,
        "counts": counts,
        "cases": cases,
        "reasons": reasons,
        "sanitized_xml": sanitized_xml_str,
    }


def validate_and_parse_json_report(
    json_path: Path,
    dialect: str,
    suite_id: str,
    engine: str,
    process_exit_code: int,
    min_mtime: float | None = None,
    fixture_id: str | None = None,
    app_trace_id: str | None = None,
    extra_secrets: list[str] | None = None,
) -> dict[str, Any]:
    """
    Valida y normaliza un reporte JSON estructurado de Vitest (`dialect='vitest'`) o Playwright (`dialect='playwright'`).
    """
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

    if not json_path.is_file() or json_path.stat().st_size == 0:
        reasons.append(f"El reporte JSON de '{suite_id}' no existe o está vacío: {json_path.name}")
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
        }

    if min_mtime is not None:
        actual_mtime = json_path.stat().st_mtime
        if actual_mtime + 0.05 < min_mtime:
            reasons.append(
                f"El reporte JSON '{json_path.name}' de '{suite_id}' es antiguo u obsoleto "
                f"(mtime={actual_mtime:.3f} < inicio={min_mtime:.3f}); se exige evidencia fresca."
            )
            return {
                "status": "ERROR",
                "exit_code": EXIT_EXECUTION_ERROR,
                "counts": counts,
                "cases": cases,
                "reasons": reasons,
            }

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        reasons.append(f"El reporte JSON '{json_path.name}' de '{suite_id}' está corrupto: {exc}")
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
        }

    if not isinstance(payload, dict):
        reasons.append(f"El reporte JSON '{json_path.name}' no contiene un objeto raíz válido.")
        return {
            "status": "ERROR",
            "exit_code": EXIT_EXECUTION_ERROR,
            "counts": counts,
            "cases": cases,
            "reasons": reasons,
        }

    sanitized_json_str = redact_text(json.dumps(payload, indent=2), extra_secrets=extra_secrets) + "\n"
    if dialect == "vitest":
        res = _parse_vitest_json(
            payload=payload,
            suite_id=suite_id,
            engine=engine,
            process_exit_code=process_exit_code,
            fixture_id=fixture_id,
            app_trace_id=app_trace_id,
            extra_secrets=extra_secrets,
        )
        res["sanitized_json"] = sanitized_json_str
        return res
    if dialect == "playwright":
        res = _parse_playwright_json(
            payload=payload,
            suite_id=suite_id,
            engine=engine,
            process_exit_code=process_exit_code,
            fixture_id=fixture_id,
            app_trace_id=app_trace_id,
            extra_secrets=extra_secrets,
        )
        res["sanitized_json"] = sanitized_json_str
        return res

    reasons.append(f"Dialecto JSON desconocido: {dialect!r}")
    return {
        "status": "ERROR",
        "exit_code": EXIT_EXECUTION_ERROR,
        "counts": counts,
        "cases": cases,
        "reasons": reasons,
    }


def _parse_vitest_json(
    payload: dict[str, Any],
    suite_id: str,
    engine: str,
    process_exit_code: int,
    fixture_id: str | None,
    app_trace_id: str | None,
    extra_secrets: list[str] | None,
) -> dict[str, Any]:
    counts = {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0}
    cases: list[dict[str, Any]] = []
    reasons: list[str] = []

    test_results = payload.get("testResults")
    if not isinstance(test_results, list):
        reasons.append("El reporte JSON de Vitest no incluye la lista 'testResults'.")
        return {"status": "ERROR", "exit_code": EXIT_EXECUTION_ERROR, "counts": counts, "cases": cases, "reasons": reasons}

    suite_level_failures = 0
    for tr in test_results:
        if not isinstance(tr, dict):
            continue
        file_name = str(tr.get("name", "vitest"))
        assertions = tr.get("assertionResults")
        if not isinstance(assertions, list):
            continue
        if tr.get("status") == "failed" and len(assertions) == 0:
            suite_level_failures += 1
            raw_msg = str(tr.get("message", "Error al cargar o compilar archivo de prueba Vitest"))
            counts["errors"] += 1
            cases.append(
                {
                    "classname": file_name,
                    "name": Path(file_name).name,
                    "status": "ERROR",
                    "duration_seconds": 0.0,
                    "message": summarize_diagnostic_text(raw_msg, extra_secrets=extra_secrets),
                    "suite_id": suite_id,
                    "fixture_id": fixture_id,
                    "app_trace_id": app_trace_id,
                    "engine": engine,
                }
            )
            continue

        for ar in assertions:
            if not isinstance(ar, dict):
                continue
            ancestors = ar.get("ancestorTitles") or ar.get("AncestorTitles") or []
            classname = " > ".join(str(a) for a in ancestors) if ancestors else Path(file_name).name
            title = str(ar.get("title") or ar.get("fullName") or "unnamed")
            raw_status = str(ar.get("status", "")).lower()
            dur_ms = float(ar.get("duration") or 0.0)
            dur_s = max(0.0, round(dur_ms / 1000.0, 4))
            fail_msgs = ar.get("failureMessages") or []
            raw_msg = "\n".join(str(m) for m in fail_msgs if m).strip()
            msg = summarize_diagnostic_text(raw_msg, extra_secrets=extra_secrets) if raw_msg else None

            if raw_status == "passed":
                c_status = "PASSED"
                counts["passed"] += 1
            elif raw_status in ("failed", "fail"):
                c_status = "FAILED"
                counts["failed"] += 1
            elif raw_status in ("pending", "skipped", "todo", "disabled"):
                c_status = "SKIPPED"
                counts["skipped"] += 1
            else:
                c_status = "ERROR"
                counts["errors"] += 1

            cases.append(
                {
                    "classname": classname,
                    "name": title,
                    "status": c_status,
                    "duration_seconds": dur_s,
                    "message": msg,
                    "suite_id": suite_id,
                    "fixture_id": fixture_id,
                    "app_trace_id": app_trace_id,
                    "engine": engine,
                }
            )

    counts["collected"] = len(cases)
    num_total = payload.get("numTotalTests")
    num_passed = payload.get("numPassedTests")
    num_failed = payload.get("numFailedTests")
    num_pending = (payload.get("numPendingTests") or 0) + (payload.get("numTodoTests") or 0)

    if (
        not isinstance(num_total, int)
        or not isinstance(num_passed, int)
        or not isinstance(num_failed, int)
        or (suite_level_failures == 0 and (
            num_total != counts["collected"]
            or num_passed != counts["passed"]
            or num_failed != counts["failed"]
            or num_pending != counts["skipped"]
        ))
    ):
        reasons.append(
            f"Inconsistencia interna en reporte JSON de Vitest: totales declarados "
            f"(total={num_total}, passed={num_passed}, failed={num_failed}, pending={num_pending}) "
            f"no coinciden con assertionResults reales ({counts})."
        )
        return {"status": "ERROR", "exit_code": EXIT_EXECUTION_ERROR, "counts": counts, "cases": cases, "reasons": reasons}

    has_problems = (counts["failed"] + counts["errors"]) > 0
    if (process_exit_code == 0 and has_problems) or (process_exit_code != 0 and not has_problems and counts["collected"] > 0):
        reasons.append(
            f"Contradicción entre código de proceso Vitest ({process_exit_code}) y conteos del reporte JSON ({counts})."
        )
        return {"status": "ERROR", "exit_code": EXIT_EXECUTION_ERROR, "counts": counts, "cases": cases, "reasons": reasons}

    if counts["errors"] > 0:
        reasons.append(f"Se produjeron {counts['errors']} errores de colección o ejecución en Vitest.")
        return {"status": "ERROR", "exit_code": EXIT_EXECUTION_ERROR, "counts": counts, "cases": cases, "reasons": reasons}

    if counts["collected"] == 0:
        reasons.append("Vitest recolectó 0 casos de prueba.")
        return {"status": "INCOMPLETE", "exit_code": EXIT_INCOMPLETE, "counts": counts, "cases": cases, "reasons": reasons}

    if counts["failed"] > 0:
        reasons.append(f"Vitest reportó {counts['failed']} casos fallidos.")
        return {"status": "FAILED", "exit_code": EXIT_FAILED, "counts": counts, "cases": cases, "reasons": reasons}

    if counts["skipped"] > 0:
        reasons.append(f"Vitest reportó {counts['skipped']} casos omitidos/pendientes.")
        return {"status": "INCOMPLETE", "exit_code": EXIT_INCOMPLETE, "counts": counts, "cases": cases, "reasons": reasons}

    return {"status": "PASSED", "exit_code": EXIT_PASSED, "counts": counts, "cases": cases, "reasons": reasons}


def _walk_playwright_suites(
    suite_list: list[dict[str, Any]],
    parent_titles: list[str],
    out_specs: list[tuple[str, dict[str, Any]]],
) -> None:
    for s in suite_list:
        if not isinstance(s, dict):
            continue
        title = str(s.get("title", "")).strip()
        next_titles = [*parent_titles, title] if title else list(parent_titles)
        for spec in s.get("specs") or []:
            if isinstance(spec, dict):
                out_specs.append((" > ".join(next_titles), spec))
        child_suites = s.get("suites") or []
        if isinstance(child_suites, list):
            _walk_playwright_suites(child_suites, next_titles, out_specs)


def _parse_playwright_json(
    payload: dict[str, Any],
    suite_id: str,
    engine: str,
    process_exit_code: int,
    fixture_id: str | None,
    app_trace_id: str | None,
    extra_secrets: list[str] | None,
) -> dict[str, Any]:
    counts = {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfail": 0}
    cases: list[dict[str, Any]] = []
    reasons: list[str] = []

    raw_suites = payload.get("suites")
    if not isinstance(raw_suites, list):
        reasons.append("El reporte JSON de Playwright no contiene la lista 'suites'.")
        return {"status": "ERROR", "exit_code": EXIT_EXECUTION_ERROR, "counts": counts, "cases": cases, "reasons": reasons}

    specs: list[tuple[str, dict[str, Any]]] = []
    _walk_playwright_suites(raw_suites, [], specs)

    for classname, spec in specs:
        spec_title = str(spec.get("title", "unnamed"))
        for t_obj in spec.get("tests") or []:
            if not isinstance(t_obj, dict):
                continue
            results = t_obj.get("results") or []
            t_status = str(t_obj.get("status", "")).lower()
            dur_ms = sum(float(r.get("duration") or 0.0) for r in results if isinstance(r, dict))
            dur_s = max(0.0, round(dur_ms / 1000.0, 4))

            err_messages: list[str] = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                for err_obj in r.get("errors") or []:
                    if isinstance(err_obj, dict) and err_obj.get("message"):
                        err_messages.append(str(err_obj["message"]))
                if not err_messages and isinstance(r.get("error"), dict) and r["error"].get("message"):
                    err_messages.append(str(r["error"]["message"]))

            raw_msg = "\n".join(err_messages).strip()
            msg = summarize_diagnostic_text(raw_msg, extra_secrets=extra_secrets) if raw_msg else None

            # Regla del plan: cero retries / un caso inestable (flaky) no se presenta como aprobado
            if t_status == "flaky" or len(results) > 1:
                c_status = "FAILED"
                counts["failed"] += 1
                msg = (msg or "") + "\n[QA] Caso inestable (flaky o con reintentos) rechazado por política de cierre."
            elif t_status == "expected":
                c_status = "PASSED"
                counts["passed"] += 1
            elif t_status == "skipped":
                c_status = "SKIPPED"
                counts["skipped"] += 1
            else:
                # 'unexpected' o timeout de caso en navegador -> FAILED (plan.md línea 131)
                c_status = "FAILED"
                counts["failed"] += 1

            cases.append(
                {
                    "classname": classname or "playwright",
                    "name": spec_title,
                    "status": c_status,
                    "duration_seconds": dur_s,
                    "message": msg.strip() if msg else None,
                    "suite_id": suite_id,
                    "fixture_id": fixture_id,
                    "app_trace_id": app_trace_id,
                    "engine": engine,
                }
            )

    counts["collected"] = len(cases)
    stats = payload.get("stats")
    if isinstance(stats, dict):
        st_expected = int(stats.get("expected", 0))
        st_unexpected = int(stats.get("unexpected", 0))
        st_flaky = int(stats.get("flaky", 0))
        st_skipped = int(stats.get("skipped", 0))
        if (st_expected + st_unexpected + st_flaky + st_skipped) != counts["collected"]:
            reasons.append(
                f"Inconsistencia interna en reporte JSON de Playwright: stats={stats} "
                f"no coincide con casos recolectados ({counts['collected']})."
            )
            return {"status": "ERROR", "exit_code": EXIT_EXECUTION_ERROR, "counts": counts, "cases": cases, "reasons": reasons}

    top_errors = payload.get("errors") or []
    if top_errors and counts["collected"] == 0:
        reasons.append("Playwright reportó errores globales de arranque o configuración sin ejecutar casos.")
        return {"status": "ERROR", "exit_code": EXIT_EXECUTION_ERROR, "counts": counts, "cases": cases, "reasons": reasons}

    has_problems = (counts["failed"] + counts["errors"]) > 0
    if (process_exit_code == 0 and has_problems) or (process_exit_code != 0 and not has_problems and counts["collected"] > 0):
        reasons.append(
            f"Contradicción entre código de proceso Playwright ({process_exit_code}) y conteos ({counts})."
        )
        return {"status": "ERROR", "exit_code": EXIT_EXECUTION_ERROR, "counts": counts, "cases": cases, "reasons": reasons}

    if counts["collected"] == 0:
        reasons.append("Playwright recolectó 0 casos de prueba.")
        return {"status": "INCOMPLETE", "exit_code": EXIT_INCOMPLETE, "counts": counts, "cases": cases, "reasons": reasons}

    if counts["failed"] > 0:
        reasons.append(f"Playwright reportó {counts['failed']} casos fallidos.")
        return {"status": "FAILED", "exit_code": EXIT_FAILED, "counts": counts, "cases": cases, "reasons": reasons}

    if counts["skipped"] > 0:
        reasons.append(f"Playwright reportó {counts['skipped']} casos omitidos.")
        return {"status": "INCOMPLETE", "exit_code": EXIT_INCOMPLETE, "counts": counts, "cases": cases, "reasons": reasons}

    return {"status": "PASSED", "exit_code": EXIT_PASSED, "counts": counts, "cases": cases, "reasons": reasons}
