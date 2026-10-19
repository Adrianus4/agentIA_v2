"""
Gen-1 & Gen-2 Modeler Prompt Builders.

Constructs LLM prompts that dynamically inject framework ORM conventions,
transactional requirements, REST endpoint conventions, required imports, and forbidden imports
directly from the FrameworkProfile.
Zero framework-specific literals are hardcoded in Python code.
"""

from __future__ import annotations

from typing import Any

from contracts.models import FrameworkProfile


def _format_concept(concept_data: Any) -> list[str]:
    """Dynamically format any framework concept dictionary without hardcoding any tokens."""
    lines: list[str] = []
    if isinstance(concept_data, dict):
        annotations = concept_data.get("annotations", [])
        if isinstance(annotations, list) and annotations:
            lines.append(f"- Required Annotations: {', '.join(str(a) for a in annotations)}")

        imports = concept_data.get("imports", [])
        if isinstance(imports, list) and imports:
            lines.append(f"- Required Imports: {', '.join(str(i) for i in imports)}")

        for key, value in concept_data.items():
            if key not in ("annotations", "imports"):
                label = key.replace("_", " ").title()
                if isinstance(value, list):
                    lines.append(f"- {label}: {', '.join(str(v) for v in value)}")
                else:
                    lines.append(f"- {label}: {value}")
    elif concept_data:
        lines.append(f"- Specification: {concept_data}")
    return lines


def _format_orm_concept(orm_concept: Any) -> list[str]:
    """Backward compatibility alias for formatting ORM concepts."""
    return _format_concept(orm_concept)


def _format_entity_section(entity_def: dict[str, Any]) -> str:
    """Format target entity specification section with explicit Java camelCase guidance."""
    entity_name = str(entity_def.get("name", "Entity"))
    table_name = entity_def.get("tableName")
    fields = entity_def.get("fields", [])

    entity_lines = [
        "## Target Entity Specification",
        f"Entity Name: {entity_name}",
    ]
    if table_name:
        entity_lines.append(f"Table Name: {table_name}")

    if isinstance(fields, list) and fields:
        entity_lines.append(
            "Fields (IMPORTANT: Define Java fields in camelCase e.g. articuloId, pujaMaxima, tiempoCierre with standard getX/setX getters and setters):"
        )
        for field in fields:
            if isinstance(field, dict):
                f_name = field.get("name", "")
                f_type = field.get("type", "")
                # Convert snake_case name to camelCase for Java fields
                parts = f_name.split("_")
                java_field_name = parts[0] + "".join(p.capitalize() for p in parts[1:]) if len(parts) > 1 else f_name
                details = [f"Java Field Name: {java_field_name} (original: {f_name})", f"Type: {f_type}"]
                for k, v in field.items():
                    if k not in ("name", "type"):
                        details.append(f"{k}: {v}")
                entity_lines.append(f"  - {', '.join(details)}")
            else:
                entity_lines.append(f"  - {field}")

    return "\n".join(entity_lines)


def _format_user_stories(user_stories: list[dict[str, Any]] | list[Any]) -> str:
    """Format user stories section for REST resource prompts including BDD scenarios and criteria."""
    lines = ["## User Stories & Business Requirements"]
    if not user_stories:
        lines.append("No explicit user stories provided. Implement standard REST CRUD operations.")
        return "\n".join(lines)

    for item in user_stories:
        if isinstance(item, dict):
            title = item.get("title", "")
            desc = item.get("description", "")
            if title and desc:
                lines.append(f"### {title}\nDescription: {desc}")
            elif title:
                lines.append(f"### {title}")
            elif desc:
                lines.append(f"- {desc}")
            else:
                pairs = [f"{k}: {v}" for k, v in item.items() if k not in ("scenarios", "bddScenarios", "acceptanceCriteria", "acceptance_criteria")]
                if pairs:
                    lines.append(f"- {', '.join(pairs)}")

            # Include BDD scenarios
            scenarios = item.get("scenarios") or item.get("bddScenarios")
            if isinstance(scenarios, list) and scenarios:
                lines.append("  BDD Scenarios:")
                for sc in scenarios:
                    if isinstance(sc, dict):
                        sc_title = sc.get("title") or sc.get("name") or "Scenario"
                        lines.append(f"    - Scenario: {sc_title}")
                        for step in ("given", "when", "then"):
                            val = sc.get(step)
                            if val:
                                lines.append(f"        {step.upper()}: {val}")
                    else:
                        lines.append(f"    - {sc}")

            # Include Acceptance Criteria
            criteria = item.get("acceptanceCriteria") or item.get("acceptance_criteria")
            if isinstance(criteria, list) and criteria:
                lines.append("  Acceptance Criteria:")
                for crit in criteria:
                    lines.append(f"    - {crit}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)



def build_entity_prompt(
    profile: FrameworkProfile,
    entity_def: dict[str, Any],
    package_name: str | None = None,
) -> str:
    """
    Constructs an LLM prompt that injects framework ORM entity conventions
    and forbidden imports, requesting raw Java source code for the entity.
    """
    sections: list[str] = []

    # 1. Target Environment
    sections.append(
        "You are an expert autonomous software engineer specializing in backend domain modeling.\n"
        f"Target Framework: {profile.framework} (Version: {profile.framework_version})\n"
        f"Language / Runtime: Java {profile.java_version}\n"
        f"Build Tool: {profile.build_tool}"
    )

    # 1.1 Target Package
    if package_name:
        sections.append(
            "## Target Package Declaration\n"
            f"You MUST declare this EXACT package at the very top of the file:\n"
            f"package {package_name};"
        )

    # 2. Dynamic ORM Entity Conventions
    orm_concept = profile.concepts.get("orm_entity", {})
    orm_lines = _format_concept(orm_concept)
    if orm_lines:
        sections.append(
            "## Framework ORM Entity Conventions\n"
            "You MUST strictly adhere to the following framework conventions:\n"
            + "\n".join(orm_lines)
        )

    # 3. Forbidden Imports
    if profile.forbidden_imports:
        forbidden_list = "\n".join(f"- {item}" for item in profile.forbidden_imports)
        sections.append(
            "## Forbidden Imports\n"
            "DO NOT import or use any of the following prohibited packages or classes:\n"
            f"{forbidden_list}"
        )

    # 4. Pitfalls
    if profile.pitfalls:
        pitfalls_list = "\n".join(f"- {item}" for item in profile.pitfalls)
        sections.append(
            "## Framework Pitfalls & Anti-Patterns to Avoid\n"
            f"{pitfalls_list}"
        )

    # 5. Entity Definition
    sections.append(_format_entity_section(entity_def))

    # 5.1 Declarative Type & Validation Imports (Skill Standard)
    if getattr(profile, "type_imports", None):
        needed_imports = []
        fields = entity_def.get("fields", [])
        for fld in fields:
            if isinstance(fld, dict):
                f_type = fld.get("type", "")
                if f_type in profile.type_imports:
                    needed_imports.append(f"import {profile.type_imports[f_type]};")
                rules = fld.get("validationRules", [])
                for r in rules:
                    rule_clean = r.lstrip("@").split("(")[0]
                    if rule_clean in profile.type_imports:
                        needed_imports.append(f"import {profile.type_imports[rule_clean]};")
        if needed_imports:
            unique_imports = sorted(set(needed_imports))
            sections.append(
                "## Required Type & Validation Imports\n"
                "You MUST include these imports for the types and validation rules used:\n"
                + "\n".join(unique_imports)
            )

    # 6. Output Instructions (Strict Raw Java, Zero Markdown)
    sections.append(
        "## Output Instructions\n"
        "Output ONLY the raw Java code for the entity.\n"
        "Do NOT enclose code in markdown code blocks (do NOT use ``` or ```java).\n"
        "Do NOT output conversational text, preambles, or markdown formatting.\n"
        "The output must start directly with the package declaration or imports and end with the closing brace."
    )

    return "\n\n".join(sections)


def build_repository_prompt(
    profile: FrameworkProfile,
    entity_def: dict[str, Any],
    package_name: str | None = None,
) -> str:
    """
    Constructs an LLM prompt that injects framework transactional conventions,
    forbidden imports, and entity metadata, requesting raw Java source code for the repository/DAO class.
    """
    sections: list[str] = []

    # 1. Target Environment
    sections.append(
        "You are an expert autonomous software engineer specializing in backend data access.\n"
        f"Target Framework: {profile.framework} (Version: {profile.framework_version})\n"
        f"Language / Runtime: Java {profile.java_version}\n"
        f"Build Tool: {profile.build_tool}"
    )

    # 1.1 Target Package
    entity_name = str(entity_def.get("name", "Entity")).strip()
    repo_pkg = f"{package_name}.repository" if package_name else "repository"
    entity_import = f"import {package_name}.{entity_name};" if package_name else f"import {entity_name};"
    sections.append(
        "## Target Package Declaration\n"
        f"You MUST declare this EXACT package at the very top of the file:\n"
        f"package {repo_pkg};\n\n"
        f"You MUST import the entity class:\n"
        f"{entity_import}"
    )

    # 2. Dynamic Transactional & Persistence Conventions
    tx_concept = profile.concepts.get("transactional", {})
    tx_lines = _format_concept(tx_concept)
    if tx_lines:
        sections.append(
            "## Framework Transactional Conventions\n"
            "You MUST strictly adhere to the following framework conventions:\n"
            + "\n".join(tx_lines)
        )

    # 3. Forbidden Imports
    if profile.forbidden_imports:
        forbidden_list = "\n".join(f"- {item}" for item in profile.forbidden_imports)
        sections.append(
            "## Forbidden Imports\n"
            "DO NOT import or use any of the following prohibited packages or classes:\n"
            f"{forbidden_list}"
        )

    # 4. Pitfalls
    if profile.pitfalls:
        pitfalls_list = "\n".join(f"- {item}" for item in profile.pitfalls)
        sections.append(
            "## Framework Pitfalls & Anti-Patterns to Avoid\n"
            f"{pitfalls_list}"
        )

    # 4.1 Canonical Reference (Clean Repository)
    if getattr(profile, "canonical_examples", None) and "repository_clean" in profile.canonical_examples:
        example_repo = profile.canonical_examples["repository_clean"].replace("Entity", entity_name)
        sections.append(
            "## Canonical Framework Implementation Reference\n"
            "Keep the repository class clean and minimal. Built-in methods are already provided:\n"
            f"```java\n{example_repo}\n```"
        )

    # 5. Entity Definition
    sections.append(_format_entity_section(entity_def))

    # 6. Output Instructions (Strict Raw Java, Zero Markdown)
    sections.append(
        "## Output Instructions\n"
        "Output ONLY the raw Java code for the repository/DAO class.\n"
        "Do NOT enclose code in markdown code blocks (do NOT use ``` or ```java).\n"
        "Do NOT output conversational text, preambles, or markdown formatting.\n"
        "The output must start directly with the package declaration or imports and end with the closing brace."
    )

    return "\n\n".join(sections)


def build_resource_prompt(
    profile: FrameworkProfile,
    entity_def: dict[str, Any],
    user_stories: list[dict[str, Any]] | list[Any],
    package_name: str | None = None,
) -> str:
    """
    Constructs an LLM prompt that injects framework REST endpoint conventions,
    forbidden imports, entity metadata, and user stories, requesting raw Java source code
    for the REST resource/controller class.
    """
    sections: list[str] = []

    # 1. Target Environment
    sections.append(
        "You are an expert autonomous software engineer specializing in backend REST API design.\n"
        f"Target Framework: {profile.framework} (Version: {profile.framework_version})\n"
        f"Language / Runtime: Java {profile.java_version}\n"
        f"Build Tool: {profile.build_tool}"
    )

    # 1.1 Target Package
    entity_name = str(entity_def.get("name", "Entity")).strip()
    res_pkg = f"{package_name}.resource" if package_name else "resource"
    repo_pkg = f"{package_name}.repository.{entity_name}Repository" if package_name else f"repository.{entity_name}Repository"
    entity_import = f"import {package_name}.{entity_name};" if package_name else f"import {entity_name};"
    sections.append(
        "## Target Package Declaration\n"
        f"You MUST declare this EXACT package at the very top of the file:\n"
        f"package {res_pkg};\n\n"
        f"You MUST import the entity and repository:\n"
        f"{entity_import}\n"
        f"import {repo_pkg};"
    )

    # 2. Dynamic REST Endpoint Conventions
    rest_concept = profile.concepts.get("rest_endpoint", {})
    rest_lines = _format_concept(rest_concept)
    if rest_lines:
        sections.append(
            "## Framework REST Endpoint Conventions\n"
            "You MUST strictly adhere to the following framework conventions:\n"
            + "\n".join(rest_lines)
        )

    # Optional Dependency Injection Conventions
    di_concept = profile.concepts.get("dependency_injection", {})
    di_lines = _format_concept(di_concept)
    if di_lines:
        sections.append(
            "## Framework Dependency Injection Conventions\n"
            "You MUST strictly adhere to the following framework conventions:\n"
            + "\n".join(di_lines)
        )

    # Optional Transactional Conventions
    tx_concept = profile.concepts.get("transactional", {})
    tx_lines = _format_concept(tx_concept)
    if tx_lines:
        sections.append(
            "## Framework Transactional Conventions\n"
            "You MUST strictly adhere to the following framework conventions for mutating/transactional operations:\n"
            + "\n".join(tx_lines)
        )

    # 3. Forbidden Imports
    if profile.forbidden_imports:
        forbidden_list = "\n".join(f"- {item}" for item in profile.forbidden_imports)
        sections.append(
            "## Forbidden Imports\n"
            "DO NOT import or use any of the following prohibited packages or classes:\n"
            f"{forbidden_list}"
        )

    # 4. Pitfalls
    if profile.pitfalls:
        pitfalls_list = "\n".join(f"- {item}" for item in profile.pitfalls)
        sections.append(
            "## Framework Pitfalls & Anti-Patterns to Avoid\n"
            f"{pitfalls_list}"
        )

    # 4.1 Canonical Reference Examples (Skill / Playbook Standard)
    if getattr(profile, "canonical_examples", None):
        ex_code = profile.canonical_examples.get("rest_resource_crud") or profile.canonical_examples.get("rest_resource_get")
        if ex_code:
            formatted_example = ex_code.replace("Entity", entity_name)
            sections.append(
                "## Canonical Framework Implementation Reference\n"
                "Follow these exact idiomatic patterns when querying, updating, or deleting entities:\n"
                f"```java\n{formatted_example}\n```"
            )

    # 5. Entity Definition
    sections.append(_format_entity_section(entity_def))

    # 6. User Stories & Business Requirements
    sections.append(_format_user_stories(user_stories))

    # 7. Output Instructions (Strict Raw Java, Zero Markdown)
    sections.append(
        "## Output Instructions\n"
        "Output ONLY the raw Java code for the REST resource/controller class.\n"
        "Do NOT enclose code in markdown code blocks (do NOT use ``` or ```java).\n"
        "Do NOT output conversational text, preambles, or markdown formatting.\n"
        "The output must start directly with the package declaration or imports and end with the closing brace."
    )

    return "\n\n".join(sections)


def build_test_prompt(
    profile: FrameworkProfile,
    target_class_name: str,
    class_type: str,
    user_stories: list[dict[str, Any]] | list[Any],
    package_name: str | None = None,
    entity_def: dict[str, Any] | None = None,
) -> str:
    """
    Constructs an LLM prompt that injects framework testing conventions (from profile.test_style),
    mocking conventions (from profile.concepts["mock_in_test"]), forbidden imports, pitfalls,
    target class details, entity schema definitions, and user stories, requesting raw Java source code
    for the automated test class.
    Zero framework-specific literals are hardcoded in Python code.
    """
    sections: list[str] = []

    # 1. Target Environment
    sections.append(
        "You are an expert autonomous software engineer specializing in automated testing and test-driven development.\n"
        f"Target Framework: {profile.framework} (Version: {profile.framework_version})\n"
        f"Language / Runtime: Java {profile.java_version}\n"
        f"Build Tool: {profile.build_tool}"
    )

    # 1.1 Target Package
    if package_name:
        pkg_suffix = "resource" if class_type == "resource" else "repository"
        ent_name = target_class_name.replace("Resource", "").replace("Repository", "")
        sections.append(
            "## Target Package Declaration\n"
            f"You MUST declare this EXACT package at the very top of the file:\n"
            f"package {package_name}.{pkg_suffix};\n\n"
            f"You MUST import the entity class:\n"
            f"import {package_name}.{ent_name};"
        )

    # 2. Dynamic Testing Conventions (test_style)
    test_lines: list[str] = []
    if isinstance(profile.test_style, dict):
        class_annos = profile.test_style.get("class_annotations", [])
        if isinstance(class_annos, list) and class_annos:
            test_lines.append(f"- Test Class Annotations: {', '.join(str(a) for a in class_annos)}")

        test_imports = profile.test_style.get("imports", [])
        if isinstance(test_imports, list) and test_imports:
            test_lines.append(f"- Test Imports: {', '.join(str(i) for i in test_imports)}")

        assertion_lib = profile.test_style.get("assertion_library")
        if assertion_lib:
            test_lines.append(f"- Assertion Library: {assertion_lib}")

        for k, v in profile.test_style.items():
            if k not in ("class_annotations", "imports", "assertion_library"):
                label = k.replace("_", " ").title()
                if isinstance(v, list):
                    test_lines.append(f"- {label}: {', '.join(str(x) for x in v)}")
                else:
                    test_lines.append(f"- {label}: {v}")

    if test_lines:
        sections.append(
            "## Framework Testing Conventions\n"
            "You MUST strictly adhere to the following framework testing conventions:\n"
            + "\n".join(test_lines)
        )

    # 3. Dynamic Mocking Conventions (mock_in_test)
    mock_concept = profile.concepts.get("mock_in_test", {})
    mock_lines = _format_concept(mock_concept)
    if mock_lines:
        sections.append(
            "## Mocking Conventions\n"
            "You MUST strictly adhere to the following framework mocking conventions:\n"
            + "\n".join(mock_lines)
        )

    # 4. Forbidden Imports
    if profile.forbidden_imports:
        forbidden_list = "\n".join(f"- {item}" for item in profile.forbidden_imports)
        sections.append(
            "## Forbidden Imports\n"
            "DO NOT import or use any of the following prohibited packages or classes:\n"
            f"{forbidden_list}"
        )

    # 5. Pitfalls
    if profile.pitfalls:
        pitfalls_list = "\n".join(f"- {item}" for item in profile.pitfalls)
        sections.append(
            "## Framework Pitfalls & Anti-Patterns to Avoid\n"
            f"{pitfalls_list}"
        )

    # 5.1 Canonical Reference Example
    if getattr(profile, "canonical_examples", None):
        ex_code = None
        if class_type == "resource":
            ex_code = profile.canonical_examples.get("resource_test_rest_assured")
        elif class_type == "repository":
            ex_code = profile.canonical_examples.get("repository_test")
        if ex_code:
            ent_name = target_class_name.replace("Resource", "").replace("Repository", "")
            formatted_example = ex_code.replace("Entity", ent_name)
            sections.append(
                "## Canonical Framework Implementation Reference\n"
                f"Follow this idiomatic testing pattern for {class_type} tests:\n"
                f"```java\n{formatted_example}\n```"
            )

    # 6. Target Test Specification
    sections.append(
        "## Target Class Under Test\n"
        f"Target Class Name: {target_class_name}\n"
        f"Target Class Type: {class_type}"
    )

    # 6.1 Entity Definition & Field Integrity
    if entity_def:
        sections.append(_format_entity_section(entity_def))
        integrity_lines = [
            "## Entity Field Integrity & Method Constraints",
            "CRITICAL: When instantiating or asserting the Entity, use ONLY the exact field names and getter/setter methods",
            "defined in the Entity Definition above. Do NOT invent getters, setters, or attributes that are not declared.",
        ]
        # Inject exact types instructions (e.g. Timestamp vs Date)
        if getattr(profile, "type_imports", None):
            type_lines: list[str] = []
            fields = entity_def.get("fields", [])
            for fld in fields:
                if isinstance(fld, dict):
                    f_type = fld.get("type", "")
                    if f_type in profile.type_imports:
                        imp = profile.type_imports[f_type]
                        if f_type == "Timestamp":
                            type_lines.append(
                                f"- Timestamp: use `{imp}` (e.g. `new {imp}(System.currentTimeMillis())`). Do NOT use `java.util.Date`."
                            )
                        else:
                            type_lines.append(f"- {f_type}: use `{imp}`.")
            if type_lines:
                integrity_lines.append(
                    "You MUST use the exact Java types matching the entity schema:\n"
                    + "\n".join(sorted(set(type_lines)))
                )
        sections.append("\n".join(integrity_lines))

    # 7. User Stories & Acceptance Criteria
    sections.append(_format_user_stories(user_stories))

    # 8. Output Instructions (Strict Raw Java, Zero Markdown)
    sections.append(
        "## Output Instructions\n"
        "Output ONLY the raw Java code for the automated test class.\n"
        "Do NOT enclose code in markdown code blocks (do NOT use ``` or ```java).\n"
        "Do NOT output conversational text, preambles, or markdown formatting.\n"
        "The output must start directly with the package declaration or imports and end with the closing brace."
    )

    return "\n\n".join(sections)

