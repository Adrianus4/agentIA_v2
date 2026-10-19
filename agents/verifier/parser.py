"""
Surefire & Maven Output Parser.

Extracts compilation errors from Maven stdout and test failures/errors from
Surefire XML reports, mapping them to DiagnosticIssue contract models.
"""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contracts.models import DiagnosticIssue

# Matches lines like:
# [ERROR] /workspace/src/main/java/org/acme/GreetingResource.java:[14,25] cannot find symbol
# [ERROR] /workspace/src/main/java/org/acme/GreetingResource.java:[14] ';' expected
# [ERROR] /workspace/src/main/java/org/acme/GreetingResource.java:14:25: error: cannot find symbol
# [ERROR] /C:/work/src/main/java/org/acme/GreetingResource.java:[14,25] cannot find symbol  (Maven on Windows)
COMPILATION_ERROR_REGEX = re.compile(
    r"^\[ERROR\]\s+(?P<file>(?:/?[a-zA-Z]:[^\s:]+|/[^\s:]+|[a-zA-Z0-9_\-./\\]+\.(?:java|kt|scala)))(?::\[(?P<line1>\d+)(?:,(?P<col1>\d+))?\]|:(?P<line2>\d+)(?::(?P<col2>\d+))?)(?:\s*:\s*(?:error:\s*)?)?\s*(?P<msg>.*)$"
)

# Matches continuation lines for compiler errors like:
# [ERROR]   symbol:   class NonExistentService
# [ERROR]   location: package org.acme
CONTINUATION_REGEX = re.compile(r"^\[ERROR\]\s{2,}(?P<extra>\S.*)$")

# Stack frame regex: at org.acme.GreetingResourceTest.testHello(GreetingResourceTest.java:24)
STACK_FRAME_REGEX = re.compile(
    r"at\s+(?P<cls>[a-zA-Z0-9_$.]+)\.[a-zA-Z0-9_$<>]*\((?P<source>[^:()]+):(?P<line>\d+)\)"
)

# Framework prefixes to avoid when picking a stack frame line number
FRAMEWORK_PREFIXES = (
    "org.junit.",
    "org.opentest4j.",
    "java.",
    "jdk.",
    "org.apache.maven.",
    "org.mockito.",
)


def _normalize_path(file_path: str, workspace_root: str | None = None) -> str:
    """
    Normalizes an absolute or container path to a workspace-relative path.
    """
    normalized = file_path.replace("\\", "/")
    # Maven on Windows prints drive paths as /C:/...; drop the leading slash
    if re.match(r"^/[a-zA-Z]:/", normalized):
        normalized = normalized[1:]

    # Strip /workspace/ prefix commonly used in container volume mounts
    if normalized.startswith("/workspace/"):
        return normalized[len("/workspace/") :]
    if normalized == "/workspace":
        return ""

    if workspace_root:
        abs_root = os.path.abspath(workspace_root).replace("\\", "/")
        abs_file = os.path.abspath(normalized).replace("\\", "/")
        if abs_file.startswith(abs_root + "/"):
            return abs_file[len(abs_root) + 1 :]
        if abs_file == abs_root:
            return ""

    # Check for presence of /src/ in the path
    src_idx = normalized.find("/src/")
    if src_idx != -1:
        return normalized[src_idx + 1 :]

    if normalized.startswith("src/"):
        return normalized

    # Strip leading slash if still absolute
    return normalized.lstrip("/")


def _parse_compilation_errors(
    raw_stdout: str, workspace_root: str | None = None
) -> list[DiagnosticIssue]:
    """
    Parses compilation errors from Maven raw stdout.
    """
    issues: list[DiagnosticIssue] = []
    seen: set[tuple[str, int | None, int | None, str, str]] = set()

    current_file: str | None = None
    current_line: int | None = None
    current_col: int | None = None
    current_msg_parts: list[str] = []

    def flush_current() -> None:
        nonlocal current_file, current_line, current_col, current_msg_parts
        if current_file is not None:
            full_msg = "\n".join(current_msg_parts).strip()
            rel_path = _normalize_path(current_file, workspace_root)
            key = (rel_path, current_line, current_col, "COMPILE_ERROR", full_msg)
            if key not in seen:
                seen.add(key)
                issues.append(
                    DiagnosticIssue(
                        file_path=rel_path,
                        line_number=current_line,
                        column_number=current_col,
                        error_type="COMPILE_ERROR",
                        message=full_msg,
                    )
                )
            current_file = None
            current_line = None
            current_col = None
            current_msg_parts = []

    for line in raw_stdout.splitlines():
        match = COMPILATION_ERROR_REGEX.match(line)
        if match:
            flush_current()
            current_file = match.group("file")
            line_str = match.group("line1") or match.group("line2")
            col_str = match.group("col1") or match.group("col2")
            current_line = int(line_str) if line_str else None
            current_col = int(col_str) if col_str else None
            msg_str = match.group("msg").strip()
            current_msg_parts = [msg_str] if msg_str else []
            continue

        continuation = CONTINUATION_REGEX.match(line)
        if continuation and current_file is not None:
            current_msg_parts.append(continuation.group("extra").strip())
            continue

        # If line does not match continuation and begins with [INFO] or [ERROR] without match
        if line.startswith(("[INFO]", "[ERROR]")):
            flush_current()

    flush_current()
    return issues


def _extract_frame_info(
    stack_trace: str, classname: str
) -> tuple[int | None, str | None]:
    """
    Extracts the failing line number and source file from the stack trace.
    Prefers frames belonging to the test class, then non-framework frames.
    """
    frames = list(STACK_FRAME_REGEX.finditer(stack_trace))
    if not frames:
        return None, None

    # 1. First look for frame matching classname exactly or suffix
    for frame in frames:
        frame_cls = frame.group("cls")
        if frame_cls == classname or classname.endswith(frame_cls):
            return int(frame.group("line")), frame.group("source")

    # 2. Look for first non-framework frame
    for frame in frames:
        frame_cls = frame.group("cls")
        if not any(frame_cls.startswith(prefix) for prefix in FRAMEWORK_PREFIXES):
            return int(frame.group("line")), frame.group("source")

    # 3. Fallback to first frame with a line
    first = frames[0]
    return int(first.group("line")), first.group("source")


def _resolve_test_file_path(
    classname: str, workspace_root: str | None = None
) -> str:
    """
    Resolves the workspace-relative path for a Java test class name.
    """
    class_rel = classname.replace(".", "/") + ".java"
    test_path = f"src/test/java/{class_rel}"
    main_path = f"src/main/java/{class_rel}"

    if workspace_root:
        if os.path.isfile(os.path.join(workspace_root, test_path)):
            return test_path
        if os.path.isfile(os.path.join(workspace_root, main_path)):
            return main_path

    return test_path


def _parse_surefire_reports(
    surefire_dir: str, workspace_root: str | None = None
) -> list[DiagnosticIssue]:
    """
    Parses Surefire XML reports from the specified directory.
    """
    issues: list[DiagnosticIssue] = []
    dir_path = Path(surefire_dir)
    if not dir_path.is_dir():
        return issues

    xml_files = sorted(dir_path.glob("**/TEST-*.xml"))
    if not xml_files:
        xml_files = sorted(dir_path.glob("TEST-*.xml"))

    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
        except (ET.ParseError, OSError):
            continue

        # Find testcase elements
        testcases = root.findall(".//testcase") if root.tag != "testcase" else [root]
        for tc in testcases:
            classname = tc.get("classname", "")
            test_name = tc.get("name", "")

            for child in tc:
                if child.tag in ("failure", "error"):
                    error_type = child.get("type") or (
                        "TEST_FAILURE" if child.tag == "failure" else "TEST_ERROR"
                    )
                    attr_msg = child.get("message") or ""
                    stack_trace = (child.text or "").strip()

                    if attr_msg and stack_trace:
                        if attr_msg in stack_trace:
                            message = stack_trace
                        else:
                            message = f"{attr_msg}\n{stack_trace}"
                    elif attr_msg:
                        message = attr_msg
                    elif stack_trace:
                        message = stack_trace
                    else:
                        message = f"Test {test_name} failed"

                    line_number, _ = _extract_frame_info(stack_trace, classname)
                    file_path = _resolve_test_file_path(classname, workspace_root)

                    issues.append(
                        DiagnosticIssue(
                            file_path=_normalize_path(file_path, workspace_root),
                            line_number=line_number,
                            column_number=None,
                            error_type=error_type,
                            message=message,
                        )
                    )

    return issues


def parse_maven_output(
    raw_stdout: str,
    surefire_dir: str | None = None,
    workspace_root: str | None = None,
) -> list[DiagnosticIssue]:
    """
    Parses compilation errors from Maven raw stdout and test failure/error reports
    from Surefire XML files, mapping them to DiagnosticIssue models.

    Args:
        raw_stdout: Captured stdout and stderr from Maven build execution.
        surefire_dir: Path to directory containing Surefire XML reports.
        workspace_root: Optional root path of workspace to normalize file paths.

    Returns:
        List[DiagnosticIssue]: Extracted diagnostic issues with workspace-relative file paths.
    """
    issues: list[DiagnosticIssue] = []

    # 1. Parse compilation errors from raw stdout
    compilation_issues = _parse_compilation_errors(
        raw_stdout, workspace_root=workspace_root
    )
    issues.extend(compilation_issues)

    # 2. Parse Surefire XML reports if directory provided
    if surefire_dir:
        surefire_issues = _parse_surefire_reports(
            surefire_dir, workspace_root=workspace_root
        )
        issues.extend(surefire_issues)

    # Deterministic deduplication by location and headline. Maven prints each compiler error twice
    # (once in the COMPILATION ERROR block, once with its symbol/location details), so the copy
    # with the longest message wins and keeps the first-seen position.
    deduped_issues: list[DiagnosticIssue] = []
    index_by_identity: dict[tuple[str, int | None, int | None, str, str], int] = {}
    for issue in issues:
        message = issue.message.strip()
        identity = (
            issue.file_path,
            issue.line_number,
            issue.column_number,
            issue.error_type,
            message.splitlines()[0] if message else "",
        )
        existing = index_by_identity.get(identity)
        if existing is None:
            index_by_identity[identity] = len(deduped_issues)
            deduped_issues.append(issue)
        elif len(message) > len(deduped_issues[existing].message.strip()):
            deduped_issues[existing] = issue

    return deduped_issues
