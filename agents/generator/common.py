"""
Shared utility functions for generation services.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import re
from typing import Any


def unwrap_markdown(code: str, target_class_name: str | None = None) -> str:
    """Strip opening and closing markdown code blocks if present, and trim trailing content."""
    cleaned = code.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        else:
            cleaned = ""
    # Strip any trailing markdown closing fence
    if "```" in cleaned:
        cleaned = cleaned.split("```")[0].strip()
    cleaned = cleaned.strip()

    # If the LLM concatenated multiple top-level files (e.g. adding a Test class or second file inside the source):
    # 1. Truncate before any secondary package declaration (which is invalid in a single .java file)
    second_pkg = re.search(r"\n\s*package\s+[\w.]+;", cleaned)
    if second_pkg:
        cleaned = cleaned[: second_pkg.start()].strip()

    # 2. If more than one "public class" is defined, truncate before the second public class
    public_classes = list(re.finditer(r"\n\s*public\s+class\s+\w+", cleaned))
    if len(public_classes) > 1:
        cleaned = cleaned[: public_classes[1].start()].strip()

    return cleaned


async def _await_result(awaitable: Any) -> Any:
    return await awaitable


def _run_coroutine(awaitable: Any) -> Any:
    return asyncio.run(_await_result(awaitable))


def resolve_generation(llm_client: Any, prompt: str) -> str:
    """Invoke LLM client handling both synchronous and asynchronous implementations."""
    result = llm_client.generate(prompt)
    if inspect.isawaitable(result):
        loop: asyncio.AbstractEventLoop | None = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(_run_coroutine, result).result()
        else:
            result = _run_coroutine(result)

    if hasattr(result, "content"):
        return str(result.content)
    return str(result)


def ensure_package_declaration(code: str, expected_package: str) -> str:
    """Ensure that if the generated Java source declares a package, it matches expected_package."""
    if not expected_package or not code:
        return code
    lines = code.splitlines()
    for idx, line in enumerate(lines):
        trimmed = line.strip()
        if trimmed.startswith("package ") and trimmed.endswith(";"):
            lines[idx] = f"package {expected_package};"
            trailing = "\n" if code.endswith("\n") else ""
            return "\n".join(lines) + trailing
    return code


def fix_entity_imports(code: str, package_name: str, entity_name: str) -> str:
    """Ensure imports for entity and repository point to the actual target package,
    and sanitize static imports for test assertions and mocking."""
    if not code:
        return code
    cleaned = code
    if package_name and entity_name:
        # Normalize existing entity and repository imports
        cleaned = re.sub(
            rf"import\s+[a-zA-Z0-9_.]+\.{entity_name}\s*;",
            f"import {package_name}.{entity_name};",
            cleaned,
        )
        cleaned = re.sub(
            rf"import\s+[a-zA-Z0-9_.]+\.{entity_name}Repository\s*;",
            f"import {package_name}.repository.{entity_name}Repository;",
            cleaned,
        )

        # If entity is referenced but not imported, and this file is in a subpackage:
        if f"import {package_name}.{entity_name};" not in cleaned and re.search(rf"\b{entity_name}\b", cleaned):
            pkg_match = re.search(r"package\s+([a-zA-Z0-9_.]+);", cleaned)
            if pkg_match and pkg_match.group(1) != package_name:
                lines = cleaned.splitlines()
                insert_idx = -1
                for idx, line in enumerate(lines):
                    trimmed = line.strip()
                    if trimmed.startswith(("package ", "import ")):
                        insert_idx = idx
                if insert_idx != -1:
                    lines.insert(insert_idx + 1, f"import {package_name}.{entity_name};")
                    cleaned = "\n".join(lines) + ("\n" if cleaned.endswith("\n") else "")


    # Sanitize JUnit 5 static assertions
    cleaned = re.sub(
        r"import\s+org\.junit\.jupiter\.api\.Assertions\.\*;",
        "import static org.junit.jupiter.api.Assertions.*;",
        cleaned,
    )
    # Sanitize Mockito static imports
    cleaned = re.sub(
        r"import\s+org\.mockito\.Mockito\.\*;",
        "import static org.mockito.Mockito.*;",
        cleaned,
    )
    if "when(" in cleaned and "import static org.mockito.Mockito" not in cleaned:
        lines = cleaned.splitlines()
        insert_idx = -1
        for idx, line in enumerate(lines):
            trimmed = line.strip()
            if trimmed.startswith(("package ", "import ")):
                insert_idx = idx
        if insert_idx != -1:
            lines.insert(insert_idx + 1, "import static org.mockito.Mockito.*;")
            cleaned = "\n".join(lines) + ("\n" if cleaned.endswith("\n") else "")

    # Sanitize Quarkus @InjectMock import
    if "@InjectMock" in cleaned and "import io.quarkus.test.junit.mockito.InjectMock" not in cleaned:
        lines = cleaned.splitlines()
        insert_idx = -1
        for idx, line in enumerate(lines):
            trimmed = line.strip()
            if trimmed.startswith(("package ", "import ")):
                insert_idx = idx
        if insert_idx != -1:
            lines.insert(insert_idx + 1, "import io.quarkus.test.junit.mockito.InjectMock;")
            cleaned = "\n".join(lines) + ("\n" if cleaned.endswith("\n") else "")

    # Sanitize Java standard collections (List, ArrayList, Arrays, Optional, Map, Set)
    if re.search(r"\b(List|ArrayList|Arrays|Optional|Map|HashMap|Set|HashSet)\b", cleaned) and "import java.util." not in cleaned:
        lines = cleaned.splitlines()
        insert_idx = -1
        for idx, line in enumerate(lines):
            trimmed = line.strip()
            if trimmed.startswith(("package ", "import ")):
                insert_idx = idx
        if insert_idx != -1:
            lines.insert(insert_idx + 1, "import java.util.*;")
            cleaned = "\n".join(lines) + ("\n" if cleaned.endswith("\n") else "")

    # Sanitize BigDecimal
    if re.search(r"\bBigDecimal\b", cleaned) and "import java.math.BigDecimal" not in cleaned:
        lines = cleaned.splitlines()
        insert_idx = -1
        for idx, line in enumerate(lines):
            trimmed = line.strip()
            if trimmed.startswith(("package ", "import ")):
                insert_idx = idx
        if insert_idx != -1:
            lines.insert(insert_idx + 1, "import java.math.BigDecimal;")
            cleaned = "\n".join(lines) + ("\n" if cleaned.endswith("\n") else "")

    # Sanitize Timestamp
    if re.search(r"\bTimestamp\b", cleaned) and "import java.sql.Timestamp" not in cleaned:
        lines = cleaned.splitlines()
        insert_idx = -1
        for idx, line in enumerate(lines):
            trimmed = line.strip()
            if trimmed.startswith(("package ", "import ")):
                insert_idx = idx
        if insert_idx != -1:
            lines.insert(insert_idx + 1, "import java.sql.Timestamp;")
            cleaned = "\n".join(lines) + ("\n" if cleaned.endswith("\n") else "")

    # Sanitize Hamcrest matchers in REST tests
    if (
        re.search(r"\b(is|equalTo|notNullValue|nullValue|hasSize|containsString|anyOf|allOf)\(", cleaned)
        and "import static org.hamcrest.CoreMatchers.*" not in cleaned
    ):
        # Replace single member imports with wildcard or insert wildcard
        if "import static org.hamcrest.CoreMatchers." in cleaned:
            cleaned = re.sub(
                r"import\s+static\s+org\.hamcrest\.CoreMatchers\.[a-zA-Z0-9_]+;",
                "import static org.hamcrest.CoreMatchers.*;",
                cleaned,
            )
        else:
            lines = cleaned.splitlines()
            insert_idx = -1
            for idx, line in enumerate(lines):
                trimmed = line.strip()
                if trimmed.startswith(("package ", "import ")):
                    insert_idx = idx
            if insert_idx != -1:
                lines.insert(insert_idx + 1, "import static org.hamcrest.CoreMatchers.*;")
                cleaned = "\n".join(lines) + ("\n" if cleaned.endswith("\n") else "")


    # Sanitize Panache repository.findById(...) when LLM mistakenly assumes it returns Optional:
    # 1. repository.findById(id).get() -> repository.findByIdOptional(id).get()
    # 2. repository.findById(id).orElse(...) -> repository.findByIdOptional(id).orElse(...)
    # 3. repository.findById(id).orElseThrow(...) -> repository.findByIdOptional(id).orElseThrow(...)
    # 4. repository.findById(id).isPresent() -> repository.findByIdOptional(id).isPresent()
    cleaned = re.sub(
        r"(\b\w*[rR]epository\s*\.\s*)findById\s*\(([^)]+)\)\s*\.\s*(get|orElse|orElseThrow|isPresent)\b",
        r"\1findByIdOptional(\2).\3",
        cleaned,
    )

    return cleaned


def sanitize_java_imports(code: str, package_name: str = "", entity_name: str = "") -> str:
    """Convenience alias for general Java code sanitization."""
    return fix_entity_imports(code, package_name, entity_name)


def ensure_entity_validation_imports(code: str) -> str:
    """Ensure jakarta.validation.constraints.NotNull is imported if @NotNull is used in code."""
    if "@NotNull" not in code:
        return code
    if "import jakarta.validation.constraints.NotNull;" in code:
        return code

    lines = code.splitlines()
    insert_idx = -1
    for idx, line in enumerate(lines):
        trimmed = line.strip()
        if trimmed.startswith(("package ", "import ")):
            insert_idx = idx

    if insert_idx != -1:
        lines.insert(insert_idx + 1, "import jakarta.validation.constraints.NotNull;")
        trailing = "\n" if code.endswith("\n") else ""
        return "\n".join(lines) + trailing

    return "import jakarta.validation.constraints.NotNull;\n" + code

