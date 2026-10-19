"""
DM-3 Scoped Repair Patch Guards.

Enforces deterministic guards on generated patches:
- Guard G1: Fail if the patch touches any file not explicitly listed in request.allowed_paths,
            or if a full-file / SEARCH-REPLACE patch targets an unallowed dependency or lacks a valid target.
- Guard G3: Fail if the patch deletes or weakens assertions or disables tests.
- Guard G7: Fail if it modifies pom.xml unless pom.xml is in request.allowed_paths.
"""

from __future__ import annotations

import posixpath
import re
import shlex
from pathlib import Path

from contracts.models import FileContent, GuardReport, RepairRequest


def _clean_path(raw: str, allowed_set: set[str] | None = None) -> str | None:
    """
    Cleans, strips quotes/timestamps, and normalizes a candidate path from a diff.
    """
    if not raw:
        return None

    p = raw.strip()

    if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
        p = p[1:-1]

    if "\t" in p:
        p = p.split("\t", 1)[0].strip()

    ts_match = re.search(r"\s+\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?.*$", p)
    if ts_match:
        p = p[: ts_match.start()].strip()

    p = p.strip().strip("'\"")

    if p in ("/dev/null", "dev/null"):
        return None

    p = p.replace("\\", "/")
    norm = posixpath.normpath(p)

    norm = norm.lstrip("/")
    while norm.startswith("./"):
        norm = norm[2:]

    if not norm or norm == ".":
        return None

    if allowed_set is not None and norm in allowed_set:
        return norm

    if norm.startswith(("a/", "b/")):
        stripped = norm[2:]
        if allowed_set is not None and (stripped in allowed_set or norm not in allowed_set):
            return stripped
        return stripped

    if allowed_set is not None:
        matching_allowed = [
            a for a in allowed_set
            if a == norm or a.endswith("/" + norm) or norm.endswith("/" + a)
        ]
        if len(matching_allowed) == 1:
            return matching_allowed[0]

    return norm


_FILE_EXTENSIONS = {
    "java", "kt", "kts", "scala", "groovy", "gradle", "xml", "properties", "yaml", "yml",
    "json", "sql", "txt", "md", "html", "js", "ts", "css", "sh", "cmd", "bat", "conf", "env",
}


def _looks_like_file_path(token: str) -> bool:
    """Distinguish file paths from dotted identifiers such as org.example.common.Page."""
    if "/" in token or "\\" in token:
        return True
    return token.rsplit(".", 1)[-1].lower() in _FILE_EXTENSIONS


# Anchored to the start of a line so prose such as "the class has been ..." is not read as code
_JAVA_TYPE_DECL_RE = re.compile(
    r"^\s*(?:public\s+|protected\s+|private\s+|abstract\s+|final\s+|static\s+)*(?:class|interface|record|enum)\s+([A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)


def extract_touched_files(
    patch_text: str,
    allowed_paths: list[str] | None = None,
    dependencies: list[FileContent] | None = None,
) -> list[str]:
    """
    Parses a unified diff, SEARCH/REPLACE, or full-file replacement string to extract all touched file paths.
    """
    allowed_set: set[str] | None = None
    if allowed_paths is not None:
        allowed_set = {
            posixpath.normpath(p.replace("\\", "/")).lstrip("/").removeprefix("./")
            for p in allowed_paths
        }

    dep_paths: list[str] = []
    if dependencies:
        for dep in dependencies:
            dep_paths.append(
                posixpath.normpath(dep.path.replace("\\", "/")).lstrip("/").removeprefix("./")
            )

    touched: set[str] = set()

    for line in patch_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue

        if line_clean.startswith("diff --git"):
            try:
                parts = shlex.split(line_clean[10:].strip())
                if len(parts) >= 2:
                    p1 = _clean_path(parts[0], allowed_set)
                    p2 = _clean_path(parts[1], allowed_set)
                    if p1:
                        touched.add(p1)
                    if p2:
                        touched.add(p2)
                    continue
            except ValueError:
                pass
            m_git = re.match(r"^diff\s+--git\s+(\S+)\s+(\S+)", line_clean)
            if m_git:
                p1 = _clean_path(m_git.group(1), allowed_set)
                p2 = _clean_path(m_git.group(2), allowed_set)
                if p1:
                    touched.add(p1)
                if p2:
                    touched.add(p2)
            continue

        if line_clean.startswith("--- "):
            raw = line_clean[4:].strip()
            p = _clean_path(raw, allowed_set)
            if p:
                touched.add(p)
            continue

        if line_clean.startswith("+++ "):
            raw = line_clean[4:].strip()
            p = _clean_path(raw, allowed_set)
            if p:
                touched.add(p)
            continue

        if line_clean.startswith("Index: "):
            raw = line_clean[7:].strip()
            p = _clean_path(raw, allowed_set)
            if p:
                touched.add(p)
            continue

        m_rc = re.match(r"^(?:rename|copy)\s+(?:from|to)\s+(.+)$", line_clean)
        if m_rc:
            p = _clean_path(m_rc.group(1).strip(), allowed_set)
            if p:
                touched.add(p)
            continue

        m_bin = re.match(r"^Binary\s+files\s+(.+)\s+and\s+(.+)\s+differ", line_clean)
        if m_bin:
            p1 = _clean_path(m_bin.group(1).strip(), allowed_set)
            p2 = _clean_path(m_bin.group(2).strip(), allowed_set)
            if p1:
                touched.add(p1)
            if p2:
                touched.add(p2)
            continue

        m_file = re.search(
            r"(?:###?\s*(?:Modified|File:?)\s*|File:\s*|Target:\s*|Path:\s*|`)([a-zA-Z0-9_/.-]+\.[a-zA-Z0-9]+)`?",
            line_clean,
        )
        if m_file and _looks_like_file_path(m_file.group(1).strip()):
            p = _clean_path(m_file.group(1).strip(), allowed_set)
            if p:
                touched.add(p)
            continue

    if not touched and patch_text.strip() and "<<<<<<< SEARCH" not in patch_text:
        for class_match in _JAVA_TYPE_DECL_RE.finditer(patch_text):
            class_name = class_match.group(1)
            target_filename = f"{class_name}.java"
            matched = False
            if allowed_set:
                for candidate in allowed_set:
                    if candidate.endswith(f"/{target_filename}") or candidate == target_filename:
                        touched.add(candidate)
                        matched = True
                        break
            if not matched:
                for dep_p in dep_paths:
                    if dep_p.endswith(f"/{target_filename}") or dep_p == target_filename:
                        touched.add(dep_p)
                        matched = True
                        break
            if not matched:
                touched.add(target_filename)

    return sorted(touched)


_ASSERTION_TOKENS = ("@Test", "assert", "assertThat", "statusCode")
_TRIVIAL_TRUE_RE = re.compile(
    r"\b(?:assertTrue\s*\(\s*true\s*\)|assertFalse\s*\(\s*false\s*\)|assertEquals\s*\(\s*(true|1|\"[^\"]*\")\s*,\s*\1\s*\))"
)
_DISABLED_TEST_RE = re.compile(r"@(?:Disabled|Ignore)\b")


def _violates_test_integrity(patch_text: str) -> bool:
    """Detect deleted assertions, added @Disabled/@Ignore, or trivialized assertions in diffs and SEARCH/REPLACE."""
    for line in patch_text.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            minus_text = line[1:].strip()
            if any(tok in minus_text for tok in _ASSERTION_TOKENS):
                return True
        elif line.startswith("+") and not line.startswith("+++"):
            plus_text = line[1:].strip()
            if _DISABLED_TEST_RE.search(plus_text) or _TRIVIAL_TRUE_RE.search(plus_text):
                return True

    sr_pattern = re.compile(
        r"<<<<<<<\s*SEARCH\r?\n(.*?)\r?\n=======\r?\n(.*?)\r?\n>>>>>>>\s*REPLACE",
        re.DOTALL,
    )
    for match in sr_pattern.finditer(patch_text):
        search_block, replace_block = match.group(1), match.group(2)
        if _DISABLED_TEST_RE.search(replace_block) and not _DISABLED_TEST_RE.search(search_block):
            return True
        if _TRIVIAL_TRUE_RE.search(replace_block) and not _TRIVIAL_TRUE_RE.search(search_block):
            return True
        for tok in _ASSERTION_TOKENS:
            if search_block.count(tok) > replace_block.count(tok):
                return True

    return False


def evaluate_guards(request: RepairRequest, patch_text: str) -> GuardReport:
    """
    Evaluates patch safety against deterministic guards:
    - Guard G1: Fail if any touched file is not explicitly in request.allowed_paths,
                if a full-file replacement targets an unallowed class, or if SEARCH/REPLACE blocks
                match content in unallowed dependency files.
    - Guard G3: Fail if the patch deletes or weakens assertions in test files.
    - Guard G7: Fail if pom.xml is modified unless pom.xml is in request.allowed_paths.
    """
    allowed_set = {
        posixpath.normpath(p.replace("\\", "/")).lstrip("/").removeprefix("./")
        for p in request.allowed_paths
    }

    touched_files = extract_touched_files(
        patch_text,
        request.allowed_paths,
        dependencies=request.dependencies,
    )

    failed_guards: list[str] = []

    for path in touched_files:
        if path not in allowed_set:
            failed_guards.append("G1")
            break

    if "G1" not in failed_guards and "<<<<<<< SEARCH" in patch_text:
        sr_pattern = re.compile(
            r"<<<<<<<\s*SEARCH\r?\n(.*?)\r?\n=======\r?\n(.*?)\r?\n>>>>>>>\s*REPLACE",
            re.DOTALL,
        )
        failing_content = request.failing_file.content or ""
        matches = list(sr_pattern.finditer(patch_text))
        if not matches:
            failed_guards.append("G1")
        for match in matches:
            search_str = match.group(1).strip()
            if search_str and failing_content and search_str not in failing_content:
                for dep in request.dependencies:
                    dep_norm = posixpath.normpath(dep.path.replace("\\", "/")).lstrip("/").removeprefix("./")
                    if dep_norm not in allowed_set and dep.content and search_str in dep.content:
                        failed_guards.append("G1")
                        break
            if "G1" in failed_guards:
                break

    # If no touched files were identified and it is not a valid SEARCH/REPLACE block for failing_file, reject under G1
    if "G1" not in failed_guards and patch_text.strip() and not touched_files and allowed_set:
        if "<<<<<<< SEARCH" in patch_text:
            failing_norm = (
                posixpath.normpath(request.failing_file.path.replace("\\", "/"))
                .lstrip("/")
                .removeprefix("./")
            )
            if failing_norm not in allowed_set:
                failed_guards.append("G1")
        else:
            failed_guards.append("G1")

    # Guard G3: Test Integrity Guard
    has_test_file = any("test" in path.lower() for path in touched_files) or (
        "test" in request.failing_file.path.lower()
    )
    if (has_test_file or _TRIVIAL_TRUE_RE.search(patch_text)) and _violates_test_integrity(patch_text):
        failed_guards.append("G3")

    # Guard G7: Fail if it modifies pom.xml unless pom.xml is in request.allowed_paths
    for path in touched_files:
        if (path == "pom.xml" or path.endswith("/pom.xml") or Path(path).name == "pom.xml") and path not in allowed_set:
            failed_guards.append("G7")
            break

    passed = len(failed_guards) == 0
    return GuardReport(passed=passed, failed_guards=failed_guards)
