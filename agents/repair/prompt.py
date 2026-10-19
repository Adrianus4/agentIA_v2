"""
DM-3 Scoped Repair Prompt Builder.

Constructs dynamic LLM prompts by extracting framework conventions, concepts,
forbidden imports, and pitfalls directly from the FrameworkProfile contract.
Zero framework-specific literals are hardcoded in Python code.
"""

from __future__ import annotations

from typing import Any

from contracts.models import FrameworkProfile, RepairRequest


def _format_concept(name: str, definition: Any) -> str:
    """Format a single framework concept dynamically."""
    title = name.replace("_", " ").title()
    lines = [f"### Convention: {title}"]

    if isinstance(definition, dict):
        annotations = definition.get("annotations", [])
        if annotations and isinstance(annotations, list):
            lines.append(f"- Annotations: {', '.join(str(a) for a in annotations)}")

        imports = definition.get("imports", [])
        if imports and isinstance(imports, list):
            lines.append(f"- Required Imports: {', '.join(str(i) for i in imports)}")

        for key, value in definition.items():
            if key not in ("annotations", "imports"):
                label = key.replace("_", " ").title()
                if isinstance(value, list):
                    lines.append(f"- {label}: {', '.join(str(v) for v in value)}")
                else:
                    lines.append(f"- {label}: {value}")
    else:
        lines.append(f"- Specification: {definition}")

    return "\n".join(lines)


DEFAULT_MAX_PROMPT_CHARS = 30_000
DEFAULT_MAX_FAILING_FILE_CHARS = 12_000
DEFAULT_MAX_DEPENDENCY_CHARS = 3_000
WINDOW_HALF_LINES = 35


def _extract_source_window(
    content: str,
    diagnostic_line: int | None,
    max_chars: int = DEFAULT_MAX_FAILING_FILE_CHARS,
) -> str:
    """
    Deterministic windowing for failing file.
    If content fits in max_chars, return completely.
    Otherwise, extract a line-centered window around diagnostic_line.
    """
    if len(content) <= max_chars:
        return content

    lines = content.splitlines(keepends=True)
    total_lines = len(lines)
    if not lines:
        return ""

    target_line = diagnostic_line if diagnostic_line is not None and 1 <= diagnostic_line <= total_lines else 1
    target_idx = target_line - 1

    start_idx = max(0, target_idx - WINDOW_HALF_LINES)
    end_idx = min(total_lines, target_idx + WINDOW_HALF_LINES + 1)

    window = lines[start_idx:end_idx]
    result_parts: list[str] = []
    if start_idx > 0:
        result_parts.append("// ... preceding source omitted ...\n")
    result_parts.extend(window)
    if end_idx < total_lines:
        result_parts.append("// ... following source omitted ...\n")

    excerpt = "".join(result_parts)
    if len(excerpt) > max_chars:
        # Extra safety truncation preserving diagnostic area
        return excerpt[:max_chars] + "\n// ... following source omitted ..."
    return excerpt


def _truncate_dependency_excerpt(
    content: str,
    max_chars: int = DEFAULT_MAX_DEPENDENCY_CHARS,
) -> str:
    """Bounding excerpt for dependency source."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n// ... following source omitted ..."


def build_repair_prompt(
    profile: FrameworkProfile,
    request: RepairRequest,
    *,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> str:
    """
    Constructs an LLM repair prompt dynamically from FrameworkProfile and RepairRequest.
    Enforces deterministic source context limits and total character budgeting.
    """
    sections: list[str] = []

    # 1. Mission and Target Environment
    sections.append(
        f"You are an expert autonomous code repair agent.\n"
        f"Target Framework: {profile.framework} (Version: {profile.framework_version})\n"
        f"Language / Runtime: Java {profile.java_version}\n"
        f"Build Tool: {profile.build_tool}\n"
        f"Profile Revision: {profile.profile_revision}"
    )

    # 2. Framework Conventions & Concepts
    if profile.concepts:
        concept_blocks = [
            _format_concept(key, val) for key, val in profile.concepts.items()
        ]
        sections.append(
            "## Framework Conventions & Syntactic Rules\n"
            "You MUST strictly adhere to the following framework conventions:\n\n"
            + "\n\n".join(concept_blocks)
        )

    # 3. Test Style Conventions
    if profile.test_style:
        test_style_lines = []
        for key, value in profile.test_style.items():
            label = key.replace("_", " ").title()
            if isinstance(value, list):
                test_style_lines.append(f"- {label}: {', '.join(str(v) for v in value)}")
            else:
                test_style_lines.append(f"- {label}: {value}")
        if test_style_lines:
            sections.append(
                "## Testing Conventions\n" + "\n".join(test_style_lines)
            )

    # 4. Forbidden Imports
    if profile.forbidden_imports:
        forbidden = "\n".join(f"- {item}" for item in profile.forbidden_imports)
        sections.append(
            f"## Forbidden Imports\n"
            f"DO NOT import or use any of the following prohibited packages/classes:\n"
            f"{forbidden}"
        )

    # 5. Common Pitfalls
    if profile.pitfalls:
        pitfalls = "\n".join(f"- {item}" for item in profile.pitfalls)
        sections.append(
            f"## Common Pitfalls & Anti-Patterns to Avoid\n"
            f"{pitfalls}"
        )

    # 6. Allowed Exceptions
    if profile.allowed_exceptions:
        exceptions = "\n".join(f"- {item}" for item in profile.allowed_exceptions)
        sections.append(
            f"## Permitted Exceptions\n"
            f"{exceptions}"
        )

    # 7. Diagnostic Issues
    issue_lines: list[str] = []
    first_diagnostic_line: int | None = None
    for idx, issue in enumerate(request.issues, start=1):
        if first_diagnostic_line is None and issue.line_number is not None:
            first_diagnostic_line = issue.line_number
        loc = []
        if issue.line_number is not None:
            loc.append(f"line {issue.line_number}")
        if issue.column_number is not None:
            loc.append(f"column {issue.column_number}")
        loc_str = f" ({', '.join(loc)})" if loc else ""
        issue_lines.append(
            f"{idx}. [{issue.error_type}] in {issue.file_path}{loc_str}:\n"
            f"   Message: {issue.message}"
        )

    issues_text = "\n".join(issue_lines) if issue_lines else "None reported."
    sections.append(
        f"## Diagnostic Issues to Fix\n"
        f"The build or test suite failed with the following diagnostic errors:\n"
        f"{issues_text}"
    )

    # 8. Failing File (with deterministic windowing)
    raw_failing_content = request.failing_file.content or ""
    windowed_failing = _extract_source_window(
        raw_failing_content,
        first_diagnostic_line,
        max_chars=DEFAULT_MAX_FAILING_FILE_CHARS,
    )
    sections.append(
        f"## Target Failing File\n"
        f"File Path: {request.failing_file.path}\n"
        f"Source Content:\n"
        f"```java\n"
        f"{windowed_failing}\n"
        f"```"
    )

    # 8.1 Target Entity Schema & Field Constraints (Prevent Cross-Entity Hallucinations)
    if request.blueprint_entities:
        target_path = request.failing_file.path
        matched_entity: dict[str, Any] | None = None
        for ent in request.blueprint_entities:
            if isinstance(ent, dict):
                ent_name = str(ent.get("name", "")).strip()
                if ent_name and ent_name in target_path:
                    matched_entity = ent
                    break

        if matched_entity:
            ent_name = matched_entity.get("name", "")
            fields = matched_entity.get("fields", [])
            field_details: list[str] = []
            for f in fields:
                if isinstance(f, dict):
                    f_name = f.get("name", "")
                    f_type = f.get("type", "")
                    parts = f_name.split("_")
                    camel = parts[0] + "".join(p.capitalize() for p in parts[1:]) if len(parts) > 1 else f_name
                    field_details.append(f"- {camel} (type: {f_type}, setter: set{camel[0].upper() + camel[1:]}, getter: get{camel[0].upper() + camel[1:]})")
            schema_block = [
                f"## Target Entity Schema for {ent_name}",
                f"CRITICAL CONSTRAINT: When modifying code or tests for {ent_name}, use ONLY the exact fields declared for {ent_name}:",
                "\n".join(field_details) if field_details else "No custom fields.",
                "STRICT ISOLATION RULE: Do NOT copy methods, getters, or setters from other entities in the dependencies! Each entity has its own distinct schema.",
            ]
            sections.append("\n".join(schema_block))

    # 9. Dependencies Context (bounded excerpts)
    if request.dependencies:
        dep_blocks = []
        for dep in request.dependencies:
            content = dep.content or ""
            bounded_content = _truncate_dependency_excerpt(content)
            dep_blocks.append(
                f"### Dependency: {dep.path}\n```java\n{bounded_content}\n```"
            )
        sections.append(
            "## Related Dependencies Context\n" + "\n\n".join(dep_blocks)
        )

    # 10. Allowed Paths & Output Instructions
    allowed_list = "\n".join(f"- {p}" for p in request.allowed_paths)
    sections.append(
        f"## Modification Scope & Strict Constraints\n"
        f"You are authorized to modify ONLY the following files:\n"
        f"{allowed_list}\n\n"
        f"STRICT SAFETY RULES:\n"
        f"1. Never touch any file not listed in the authorized modification scope.\n"
        f"2. Provide your fix using SEARCH/REPLACE blocks (preferred):\n"
        f"   File: path/to/File.java\n"
        f"   <<<<<<< SEARCH\n"
        f"   exact lines from current file to replace\n"
        f"   =======\n"
        f"   replacement lines\n"
        f"   >>>>>>> REPLACE\n"
        f"   Alternatively, provide the full updated file using a file block:\n"
        f"   File: path/to/File.java\n"
        f"   ```java\n"
        f"   <complete updated file content>\n"
        f"   ```\n"
        f"3. Make minimal, surgical modifications to resolve all diagnostics without collateral changes."
    )

    full_prompt = "\n\n".join(sections)
    if len(full_prompt) <= max_prompt_chars:
        return full_prompt

    # If full_prompt exceeds max_prompt_chars, enforce the overall budget while preserving
    # critical headers, target path, diagnostics, and output instructions.
    omission_note = "\n// ... [Context truncated to stay within character budget] ...\n"
    target_failing_chars = max(1000, max_prompt_chars - len(full_prompt) + len(windowed_failing) - len(omission_note))
    shrunk_failing = windowed_failing[:target_failing_chars] + omission_note

    # Reassemble with truncated failing content and dropped dependencies if still over budget
    sections[7] = (
        f"## Target Failing File\n"
        f"File Path: {request.failing_file.path}\n"
        f"Source Content:\n"
        f"```java\n"
        f"{shrunk_failing}\n"
        f"```"
    )
    if len("\n\n".join(sections)) > max_prompt_chars and len(sections) > 8:
        # Drop dependencies section if needed
        del sections[8]

    shrunk_prompt = "\n\n".join(sections)
    if len(shrunk_prompt) > max_prompt_chars:
        return shrunk_prompt[:max_prompt_chars]
    return shrunk_prompt
