"""
DM-3 Scoped Repair Service.

Coordinates prompt construction, patch generation via LLM or generator,
and strict patch guard evaluation, returning a typed RepairResult.
"""

from __future__ import annotations

import posixpath
from collections.abc import Callable
from typing import cast

from agents.repair.deterministic import missing_import_patch
from agents.repair.guards import evaluate_guards, extract_touched_files
from agents.repair.prompt import build_repair_prompt
from contracts.models import (
    FailureClass,
    FrameworkProfile,
    GuardReport,
    RepairRequest,
    RepairResult,
)


class ScopedRepairService:
    """
    Coordinates prompt construction, patch generation, and deterministic guard evaluation.
    """

    def __init__(
        self,
        patch_generator: Callable[[str], str] | None = None,
    ) -> None:
        self.patch_generator = patch_generator

    def repair(
        self,
        profile: FrameworkProfile,
        request: RepairRequest,
        trace_id: str = "trace-default",
    ) -> RepairResult:
        """
        Executes a bounded repair attempt.
        """
        first_err_type = (
            request.issues[0].error_type if request.issues else "COMPILE_ERROR"
        )
        valid_classes = {
            "COMPILE_ERROR",
            "CODE_BUG",
            "TEST_BUG",
            "SPEC_AMBIGUITY",
            "UNKNOWN",
        }
        classification: FailureClass = cast(
            FailureClass,
            first_err_type if first_err_type in valid_classes else "COMPILE_ERROR",
        )

        # Cheap, exact fixes first: a missing import of a known type needs no LLM call
        deterministic_patch = missing_import_patch(profile, request)
        if deterministic_patch:
            det_report = evaluate_guards(request, deterministic_patch)
            if det_report.passed:
                return RepairResult(
                    outcome="PATCHED",
                    classification="COMPILE_ERROR",
                    hypothesis=f"Deterministic import fix for {request.failing_file.path}",
                    patches=[deterministic_patch],
                    files_touched=[
                        posixpath.normpath(request.failing_file.path.replace("\\", "/"))
                        .lstrip("/")
                        .removeprefix("./")
                    ],
                    guard_report=det_report,
                    attempts_used=1,
                    trace_id=trace_id,
                )

        prompt = build_repair_prompt(profile, request)

        if not self.patch_generator:
            return RepairResult(
                outcome="NO_FIX",
                classification=classification,
                hypothesis="No patch generator configured.",
                patches=[],
                files_touched=[],
                guard_report=GuardReport(passed=True, failed_guards=[]),
                attempts_used=request.attempt_budget,
                trace_id=trace_id,
            )

        patch_text = self.patch_generator(prompt)

        if not patch_text or not patch_text.strip():
            return RepairResult(
                outcome="NO_FIX",
                classification=classification,
                hypothesis="Patch generator produced empty patch.",
                patches=[],
                files_touched=[],
                guard_report=GuardReport(passed=True, failed_guards=[]),
                attempts_used=request.attempt_budget,
                trace_id=trace_id,
            )

        guard_report = evaluate_guards(request, patch_text)
        touched = extract_touched_files(
            patch_text,
            request.allowed_paths,
            dependencies=request.dependencies,
        )

        if not guard_report.passed:
            return RepairResult(
                outcome="REJECTED_BY_GUARD",
                classification="CODE_BUG",
                hypothesis=f"Patch rejected by guards: {', '.join(guard_report.failed_guards)}",
                patches=[patch_text],
                files_touched=touched,
                guard_report=guard_report,
                attempts_used=1,
                trace_id=trace_id,
            )

        if not touched:
            failing_norm = (
                posixpath.normpath(request.failing_file.path.replace("\\", "/"))
                .lstrip("/")
                .removeprefix("./")
            )
            touched = [failing_norm]

        return RepairResult(
            outcome="PATCHED",
            classification=classification,
            hypothesis=f"Surgical patch applied cleanly to {request.failing_file.path}",
            patches=[patch_text],
            files_touched=touched,
            guard_report=guard_report,
            attempts_used=1,
            trace_id=trace_id,
        )
