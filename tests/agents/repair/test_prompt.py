"""
Unit tests for DM-3 Repair Prompt Builder (prompt.py).
Enforces dynamic profile injection and zero hardcoded framework literals.
"""

import re
from pathlib import Path

import pytest

from agents.repair.prompt import build_repair_prompt
from contracts.models import (
    DiagnosticIssue,
    FileContent,
    FrameworkProfile,
    RepairRequest,
    TestBaseline,
)


@pytest.fixture
def sample_profile() -> FrameworkProfile:
    return FrameworkProfile(
        id="sample-fw-1",
        framework="custom-framework",
        framework_version="3.2.1",
        profile_revision=1,
        java_version="21",
        build_tool="maven",
        enabled=True,
        instruction_set_revision="rev-99",
        concepts={
            "mock_in_test": {
                "annotations": ["@CustomInjectMock"],
                "imports": ["com.custom.test.CustomInjectMock"],
            },
            "rest_endpoint": {
                "annotations": ["@CustomEndpoint", "@CustomGet"],
                "imports": ["com.custom.ws.CustomEndpoint", "com.custom.ws.CustomGet"],
            },
        },
        config={
            "file_path": "src/main/resources/custom.properties",
            "properties": {"server.port": 8080},
        },
        test_style={
            "class_annotations": ["@CustomFrameworkTest"],
            "assertion_library": "custom-assert",
        },
        verify_commands={
            "compile": "mvn compile",
            "test": "mvn test",
        },
        forbidden_imports=["com.legacy.", "org.prohibited."],
        allowed_exceptions=["com.custom.NotFoundException"],
        pitfalls=[
            "Never use legacy annotations; use modern conventions.",
            "Always annotate mock beans using the custom mock annotation.",
        ],
        templates={},
    )


@pytest.fixture
def sample_request() -> RepairRequest:
    return RepairRequest(
        framework="custom-framework",
        framework_version="3.2.1",
        profile_revision=1,
        failing_file=FileContent(
            path="src/main/java/com/custom/ExampleService.java",
            content=(
                "package com.custom;\n"
                "public class ExampleService {\n"
                "    public String compute() {\n"
                "        return legacy();\n"
                "    }\n"
                "}\n"
            ),
        ),
        issues=[
            DiagnosticIssue(
                file_path="src/main/java/com/custom/ExampleService.java",
                line_number=4,
                column_number=16,
                error_type="COMPILE_ERROR",
                message="cannot find symbol: method legacy()",
            )
        ],
        dependencies=[
            FileContent(
                path="src/main/java/com/custom/Helper.java",
                content="package com.custom;\npublic class Helper {}\n",
            )
        ],
        allowed_paths=["src/main/java/com/custom/ExampleService.java"],
        attempt_budget=3,
        test_baseline=TestBaseline(
            test_count=1,
            assertion_count=2,
            disabled_count=0,
        ),
    )


def test_build_repair_prompt_dynamic_injection(
    sample_profile: FrameworkProfile, sample_request: RepairRequest
):
    """Prompt must inject conventions, issues, and failing content dynamically from objects."""
    prompt = build_repair_prompt(sample_profile, sample_request)

    # Dynamic framework metadata
    assert sample_profile.framework in prompt
    assert sample_profile.framework_version in prompt
    assert sample_profile.java_version in prompt

    # Dynamic concepts
    assert "@CustomInjectMock" in prompt
    assert "com.custom.test.CustomInjectMock" in prompt
    assert "@CustomEndpoint" in prompt

    # Dynamic forbidden imports & pitfalls
    assert "com.legacy." in prompt
    assert "Always annotate mock beans using the custom mock annotation." in prompt

    # Diagnostics
    assert "cannot find symbol: method legacy()" in prompt
    assert "COMPILE_ERROR" in prompt
    assert "src/main/java/com/custom/ExampleService.java" in prompt

    # Failing file content
    assert "public String compute()" in prompt

    # Dependencies
    assert "src/main/java/com/custom/Helper.java" in prompt

    # Allowed paths
    assert "src/main/java/com/custom/ExampleService.java" in prompt


def test_zero_hardcoded_framework_literals_in_source():
    """
    CRITICAL RULE (Constitution Rule 8 & Deliverable 2):
    NO framework strings (e.g., 'Spring', 'Quarkus', '@InjectMock', '@Path', '@MockBean')
    may be hardcoded in Python agents/repair/ code. Everything must come from FrameworkProfile.
    """
    forbidden_literals = [
        "quarkus",
        "spring",
        "@injectmock",
        "@mockbean",
        "@path",
        "@inject",
        "micronaut",
    ]

    target_files = [
        Path("agents/repair/prompt.py"),
        Path("agents/repair/guards.py"),
    ]

    for file_path in target_files:
        assert file_path.exists(), f"File {file_path} must exist"
        content = file_path.read_text(encoding="utf-8").lower()
        for literal in forbidden_literals:
            # Check for literal outside comments/docs or anywhere in source
            matches = re.findall(rf"\b{re.escape(literal)}\b", content)
            assert not matches, (
                f"Violation of Constitution Rule 8: '{literal}' found in {file_path}"
            )


def test_build_repair_prompt_minimal_fields():
    """Prompt must build cleanly even with minimal/empty optional profile and request fields."""
    minimal_profile = FrameworkProfile(
        id="min-1",
        framework="framework-z",
        framework_version="1.0",
        profile_revision=1,
        java_version="17",
        build_tool="maven",
        enabled=True,
        instruction_set_revision="rev-1",
        concepts={},
        config={},
        test_style={},
        verify_commands={"compile": "mvn compile"},
        forbidden_imports=[],
        allowed_exceptions=[],
        pitfalls=[],
        templates={},
    )
    minimal_request = RepairRequest(
        framework="framework-z",
        framework_version="1.0",
        failing_file=FileContent(path="src/Main.java", content=None),
        issues=[
            DiagnosticIssue(
                file_path="src/Main.java",
                line_number=None,
                column_number=None,
                error_type="UNKNOWN",
                message="generic failure",
            )
        ],
        allowed_paths=["src/Main.java"],
        attempt_budget=1,
        test_baseline=TestBaseline(
            test_count=0,
            assertion_count=0,
            disabled_count=0,
        ),
    )

    prompt = build_repair_prompt(minimal_profile, minimal_request)
    assert "framework-z" in prompt
    assert "src/Main.java" in prompt
    assert "generic failure" in prompt


def test_repair_prompt_small_file_remains_complete(sample_profile: FrameworkProfile) -> None:
    small_content = "public class Small {\n    void run() {\n        int x = 1;\n    }\n}\n"
    request = RepairRequest(
        framework="custom-framework",
        framework_version="3.2.1",
        failing_file=FileContent(path="src/Small.java", content=small_content),
        issues=[
            DiagnosticIssue(
                file_path="src/Small.java",
                line_number=3,
                error_type="COMPILE_ERROR",
                message="syntax error",
            )
        ],
        allowed_paths=["src/Small.java"],
        test_baseline=TestBaseline(test_count=1, assertion_count=1, disabled_count=0),
    )
    prompt = build_repair_prompt(sample_profile, request)
    assert small_content in prompt
    assert "// ... preceding source omitted ..." not in prompt
    assert "// ... following source omitted ..." not in prompt


def test_repair_prompt_large_file_is_windowed(sample_profile: FrameworkProfile) -> None:
    lines = [f"    // line {i} padding content for testing windowing\n" for i in range(1, 500)]
    lines[250] = "    int targetError = broken(); // diagnostic line\n"
    large_content = "public class Large {\n" + "".join(lines) + "}\n"

    request = RepairRequest(
        framework="custom-framework",
        framework_version="3.2.1",
        failing_file=FileContent(path="src/Large.java", content=large_content),
        issues=[
            DiagnosticIssue(
                file_path="src/Large.java",
                line_number=252,
                error_type="COMPILE_ERROR",
                message="cannot find symbol broken()",
            )
        ],
        allowed_paths=["src/Large.java"],
        test_baseline=TestBaseline(test_count=1, assertion_count=1, disabled_count=0),
    )
    prompt = build_repair_prompt(sample_profile, request)
    assert "int targetError = broken(); // diagnostic line" in prompt
    assert "// ... preceding source omitted ..." in prompt
    assert "// ... following source omitted ..." in prompt
    # Initial lines far from diagnostic are omitted
    assert "// line 10 padding content" not in prompt


def test_repair_prompt_dependencies_are_truncated(sample_profile: FrameworkProfile) -> None:
    huge_dep = "public class Dep {\n" + ("    // dep line filler\n" * 400) + "}\n"
    request = RepairRequest(
        framework="custom-framework",
        framework_version="3.2.1",
        failing_file=FileContent(path="src/Main.java", content="class Main {}"),
        issues=[
            DiagnosticIssue(
                file_path="src/Main.java",
                line_number=1,
                error_type="COMPILE_ERROR",
                message="err",
            )
        ],
        dependencies=[
            FileContent(path="src/Dep.java", content=huge_dep),
        ],
        allowed_paths=["src/Main.java"],
        test_baseline=TestBaseline(test_count=1, assertion_count=1, disabled_count=0),
    )
    prompt = build_repair_prompt(sample_profile, request)
    assert "Dependency: src/Dep.java" in prompt
    assert "// ... following source omitted ..." in prompt
    assert len(huge_dep) > 3500


def test_repair_prompt_character_budget_enforced(sample_profile: FrameworkProfile) -> None:
    huge_failing = "class Huge {\n" + ("    String s = 'long string filler content';\n" * 500) + "}\n"
    request = RepairRequest(
        framework="custom-framework",
        framework_version="3.2.1",
        failing_file=FileContent(path="src/Huge.java", content=huge_failing),
        issues=[
            DiagnosticIssue(
                file_path="src/Huge.java",
                line_number=100,
                error_type="COMPILE_ERROR",
                message="type error",
            )
        ],
        allowed_paths=["src/Huge.java"],
        test_baseline=TestBaseline(test_count=1, assertion_count=1, disabled_count=0),
    )

    budget = 4000
    prompt = build_repair_prompt(sample_profile, request, max_prompt_chars=budget)
    assert len(prompt) <= budget
    assert "Target Failing File" in prompt
    assert "File Path: src/Huge.java" in prompt
    assert "Modification Scope & Strict Constraints" in prompt


def test_repair_prompt_sections_remain_present(sample_profile: FrameworkProfile, sample_request: RepairRequest) -> None:
    prompt = build_repair_prompt(sample_profile, sample_request)
    assert "## Framework Conventions & Syntactic Rules" in prompt
    assert "## Testing Conventions" in prompt
    assert "## Forbidden Imports" in prompt
    assert "## Common Pitfalls & Anti-Patterns to Avoid" in prompt
    assert "## Diagnostic Issues to Fix" in prompt
    assert "## Target Failing File" in prompt
    assert "## Modification Scope & Strict Constraints" in prompt


def test_repair_prompt_injects_entity_schema_and_isolation_rule(sample_profile: FrameworkProfile) -> None:
    request = RepairRequest(
        framework="custom-framework",
        framework_version="3.2.1",
        failing_file=FileContent(
            path="src/test/java/com/example/repository/ContratoEscrowRepositoryTest.java",
            content="class ContratoEscrowRepositoryTest {}",
        ),
        issues=[
            DiagnosticIssue(
                file_path="src/test/java/com/example/repository/ContratoEscrowRepositoryTest.java",
                line_number=20,
                error_type="COMPILE_ERROR",
                message="cannot find symbol: method setParte(String)",
            )
        ],
        allowed_paths=["src/test/java/com/example/repository/ContratoEscrowRepositoryTest.java"],
        test_baseline=TestBaseline(test_count=1, assertion_count=1, disabled_count=0),
        blueprint_entities=[
            {
                "name": "ContratoEscrow",
                "fields": [
                    {"name": "id", "type": "Long"},
                    {"name": "monto_total", "type": "BigDecimal"},
                ],
            },
            {
                "name": "AprobacionHitos",
                "fields": [
                    {"name": "parte", "type": "String"},
                ],
            },
        ],
    )
    prompt = build_repair_prompt(sample_profile, request)
    assert "## Target Entity Schema for ContratoEscrow" in prompt
    assert "montoTotal" in prompt
    assert "STRICT ISOLATION RULE" in prompt
    assert "Do NOT copy methods, getters, or setters from other entities" in prompt

