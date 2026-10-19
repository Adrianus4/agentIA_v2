"""Construcción de paquete de evidencia acotado y oráculo determinista de referencias (A03, AC-08, AC-13, AC-14)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from contracts.models import QAHypothesis, QARunResult
from qa_agent.evidence import redact_structure, summarize_diagnostic_text


def build_evidence_packet(
    run_result: QARunResult,
    max_chars: int = 32000,
    extra_secrets: list[str] | None = None,
) -> dict[str, Any]:
    """Construye un paquete de evidencia reducido y redactado por lista permitida estricta."""
    failed_cases: list[dict[str, Any]] = []
    for c in run_result.cases:
        if c.status in ("FAILED", "ERROR"):
            clean_msg = summarize_diagnostic_text(c.message or "", extra_secrets=extra_secrets)
            failed_cases.append(
                {
                    "name": c.name,
                    "classname": c.classname,
                    "status": c.status,
                    "duration_seconds": c.duration_seconds,
                    "message": clean_msg,
                    "suite_id": c.suite_id,
                }
            )

    suite_summaries: list[dict[str, Any]] = []
    for s in run_result.suites:
        suite_summaries.append(
            {
                "suite_id": s.suite_id,
                "status": s.status,
                "engine": s.engine,
                "counts": s.counts.model_dump(),
                "reasons": s.reasons,
            }
        )

    missing_caps: list[str] = [
        cap.name for cap in run_result.capabilities if not cap.available
    ]

    packet: dict[str, Any] = {
        "trace_id": run_result.trace_id,
        "status": run_result.status,
        "exit_code": run_result.exit_code,
        "duration_seconds": run_result.duration_seconds,
        "counts": run_result.counts.model_dump(),
        "failed_cases": failed_cases,
        "suites": suite_summaries,
        "missing_capabilities": missing_caps,
    }

    # Redacción profunda recursiva de cualquier secreto potencial
    redacted_packet = redact_structure(packet, extra_secrets=extra_secrets)

    raw_json = json.dumps(redacted_packet, ensure_ascii=False)
    if len(raw_json) > max_chars:
        # 1. Truncar diagnósticos de casos si excede el presupuesto
        for fc in redacted_packet.get("failed_cases", []):
            if "message" in fc and len(fc["message"]) > 100:
                fc["message"] = fc["message"][:100] + "... [TRUNCATED]"
        raw_json = json.dumps(redacted_packet, ensure_ascii=False)

    # 2. Si aún excede el presupuesto, podar la lista de casos fallidos hasta cumplir estrictamente max_chars
    if len(raw_json) > max_chars and redacted_packet.get("failed_cases"):
        cases_list = redacted_packet["failed_cases"]
        total_cases = len(cases_list)
        low = 0
        high = total_cases
        best_slice = []
        omitted = total_cases

        while low <= high:
            mid = (low + high) // 2
            candidate_cases = cases_list[:mid]
            candidate_packet = dict(redacted_packet)
            candidate_packet["failed_cases"] = candidate_cases
            if mid < total_cases:
                candidate_packet["omitted_failed_cases"] = total_cases - mid
            cand_json = json.dumps(candidate_packet, ensure_ascii=False)
            if len(cand_json) <= max_chars:
                best_slice = candidate_cases
                omitted = total_cases - mid
                low = mid + 1
            else:
                high = mid - 1

        redacted_packet["failed_cases"] = best_slice
        if omitted > 0:
            redacted_packet["omitted_failed_cases"] = omitted

    return redacted_packet


def validate_hypothesis_references(
    hypothesis: QAHypothesis,
    packet: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Valida que todas las referencias en una hipótesis existan en el paquete de evidencia."""
    valid_tokens: set[str] = set()

    # Recolectar nombres de casos y suites
    for fc in packet.get("failed_cases", []):
        if fc.get("name"):
            valid_tokens.add(fc["name"])
        if fc.get("classname"):
            valid_tokens.add(fc["classname"])
        if fc.get("suite_id"):
            valid_tokens.add(fc["suite_id"])

    for s in packet.get("suites", []):
        if s.get("suite_id"):
            valid_tokens.add(s["suite_id"])

    for c in packet.get("cases", []):
        if c.get("name"):
            valid_tokens.add(c["name"])
        if c.get("classname"):
            valid_tokens.add(c["classname"])
        if c.get("suite_id"):
            valid_tokens.add(c["suite_id"])

    valid_tokens.update({"result.json", "junit.xml", "pytest.log", "report.html"})
    valid_tokens.discard("")

    invalid_refs: list[str] = []
    for ref in hypothesis.referenced_evidence:
        clean_ref = ref.strip()
        # Coincidencia exacta obligatoria (sin substrings ni prefijos inventados)
        if clean_ref not in valid_tokens:
            invalid_refs.append(clean_ref)

    return len(invalid_refs) == 0, invalid_refs
