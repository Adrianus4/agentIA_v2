"""
Unit tests for DM-3 Scoped Repair Service (service.py).
"""

import pytest

from agents.repair.service import ScopedRepairService
from contracts.models import (
    DiagnosticIssue,
    FileContent,
    FrameworkProfile,
    RepairRequest,
    RepairResult,
    TestBaseline,
)


@pytest.fixture
def profile() -> FrameworkProfile:
    return FrameworkProfile(
        id="test-profile",
        framework="framework-y",
        framework_version="2.0",
        profile_revision=1,
        java_version="17",
        build_tool="maven",
        enabled=True,
        instruction_set_revision="v1",
        concepts={},
        config={},
        test_style={},
        verify_commands={"compile": "mvn compile"},
        forbidden_imports=[],
        allowed_exceptions=[],
        pitfalls=[],
        templates={},
    )


@pytest.fixture
def repair_request() -> RepairRequest:
    return RepairRequest(
        framework="framework-y",
        framework_version="2.0",
        profile_revision=1,
        failing_file=FileContent(
            path="src/main/java/Service.java",
            content="public class Service {}",
        ),
        issues=[
            DiagnosticIssue(
                file_path="src/main/java/Service.java",
                line_number=1,
                column_number=1,
                error_type="COMPILE_ERROR",
                message="syntax error",
            )
        ],
        allowed_paths=["src/main/java/Service.java"],
        attempt_budget=3,
        test_baseline=TestBaseline(
            test_count=1,
            assertion_count=1,
            disabled_count=0,
        ),
    )


def test_service_successful_repair(profile: FrameworkProfile, repair_request: RepairRequest):
    """When patch generator produces valid patch on allowed file, outcome is PATCHED."""
    valid_patch = (
        "--- a/src/main/java/Service.java\n"
        "+++ b/src/main/java/Service.java\n"
        "@@ -1,1 +1,2 @@\n"
        " public class Service {\n"
        "+    void fix() {}\n"
        " }\n"
    )

    def mock_generator(prompt: str) -> str:
        assert len(prompt) > 0
        return valid_patch

    service = ScopedRepairService(patch_generator=mock_generator)
    result = service.repair(profile, repair_request, trace_id="trace-test-123")

    assert isinstance(result, RepairResult)
    assert result.outcome == "PATCHED"
    assert result.classification == "COMPILE_ERROR"
    assert result.guard_report.passed is True
    assert result.guard_report.failed_guards == []
    assert result.files_touched == ["src/main/java/Service.java"]
    assert result.attempts_used == 1
    assert result.trace_id == "trace-test-123"
    assert result.patches == [valid_patch]


def test_service_rejected_by_guard(profile: FrameworkProfile, repair_request: RepairRequest):
    """When patch generator returns malicious patch touching pom.xml, outcome is REJECTED_BY_GUARD."""
    malicious_patch = (
        "--- a/pom.xml\n"
        "+++ b/pom.xml\n"
        "@@ -1,1 +1,2 @@\n"
        "+<evil/>\n"
    )

    def malicious_generator(prompt: str) -> str:
        return malicious_patch

    service = ScopedRepairService(patch_generator=malicious_generator)
    result = service.repair(profile, repair_request, trace_id="trace-guard-violation")

    assert result.outcome == "REJECTED_BY_GUARD"
    assert result.guard_report.passed is False
    assert "G1" in result.guard_report.failed_guards
    assert "G7" in result.guard_report.failed_guards
    assert result.trace_id == "trace-guard-violation"


def test_service_no_fix_on_empty_patch(profile: FrameworkProfile, repair_request: RepairRequest):
    """When patch generator yields empty/no patch, outcome is NO_FIX."""
    def empty_generator(prompt: str) -> str:
        return ""

    service = ScopedRepairService(patch_generator=empty_generator)
    result = service.repair(profile, repair_request, trace_id="trace-empty")

    assert result.outcome == "NO_FIX"
    assert result.attempts_used == 3


def test_service_without_configured_generator(
    profile: FrameworkProfile, repair_request: RepairRequest
):
    """When no patch generator is provided, outcome is NO_FIX."""
    service = ScopedRepairService(patch_generator=None)
    result = service.repair(profile, repair_request, trace_id="trace-no-gen")
    assert result.outcome == "NO_FIX"
    assert result.attempts_used == repair_request.attempt_budget
    assert result.trace_id == "trace-no-gen"


def test_service_with_empty_issues_list(profile: FrameworkProfile):
    """Service gracefully defaults classification when issues list is empty."""
    req = RepairRequest(
        framework="framework-y",
        framework_version="2.0",
        failing_file=FileContent(path="src/Main.java", content=""),
        issues=[],
        allowed_paths=["src/Main.java"],
        attempt_budget=2,
        test_baseline=TestBaseline(
            test_count=0,
            assertion_count=0,
            disabled_count=0,
        ),
    )
    service = ScopedRepairService(patch_generator=lambda p: "")
    result = service.repair(profile, req)
    assert result.outcome == "NO_FIX"
    assert result.classification == "COMPILE_ERROR"

