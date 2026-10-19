from __future__ import annotations

import posixpath
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from agents.generator.common import sanitize_java_imports


class PatchApplicationError(RuntimeError):
    """Raised when a Unified Diff or SEARCH/REPLACE patch cannot be safely and atomically applied."""


@dataclass(frozen=True)
class _PatchFile:
    source: str
    target: str
    source_path: Path | None
    target_path: Path | None


_HEADER = re.compile(r"^(---|\+\+\+) (.+?)(?:\t.*)?$")
_JAVA_CLASS_DECL = re.compile(
    r"\b(?:public\s+|protected\s+|private\s+|abstract\s+|final\s+)*(?:class|interface|record|enum)\s+([a-zA-Z0-9_]+)\b"
)


def apply_patch(
    workspace_dir: str,
    patch_content: str,
    allowed_paths: list[str] | None = None,
) -> None:
    workspace_path = Path(workspace_dir).expanduser()
    workspace_path.mkdir(parents=True, exist_ok=True)
    workspace = workspace_path.resolve(strict=True)
    if not workspace.is_dir():
        raise PatchApplicationError(f"workspace is not a directory: {workspace_dir}")
    if not patch_content.strip():
        raise PatchApplicationError("patch content is empty")

    allowed_resolved: set[Path] | None = None
    if allowed_paths is not None:
        allowed_resolved = set()
        for p in allowed_paths:
            norm = posixpath.normpath(p.replace("\\", "/")).lstrip("/").removeprefix("./")
            cand = (workspace / norm).resolve(strict=False)
            if _is_within(workspace, cand):
                allowed_resolved.add(cand)

    if "<<<<<<< SEARCH" in patch_content and ">>>>>>> REPLACE" in patch_content:
        _apply_search_replace_blocks(workspace, patch_content, allowed_resolved)
        return

    files = _parse_and_validate_headers(workspace, patch_content, allowed_resolved)
    if not files:
        file_blocks = _extract_whole_file_blocks(workspace, patch_content, allowed_resolved)
        if file_blocks:
            _apply_whole_file_blocks(workspace, file_blocks, allowed_resolved)
            return
        raise PatchApplicationError("patch contains no Unified Diff file headers")

    with tempfile.TemporaryDirectory(prefix="patch-stage-") as temporary:
        staged = Path(temporary) / "workspace"
        shutil.copytree(workspace, staged, symlinks=True)
        normalized_patch = _normalize_headers(workspace, patch_content, files)
        sanitized_patch = _sanitize_and_recount_patch(normalized_patch)

        applied = False
        detail = ""

        patch_bin = shutil.which("patch")
        if patch_bin:
            try:
                process = subprocess.run(
                    [patch_bin, "--batch", "--forward", "--fuzz=3", "-p0"],
                    cwd=staged,
                    input=sanitized_patch,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if process.returncode == 0:
                    applied = True
                else:
                    detail = (process.stderr or process.stdout).strip()
            except OSError as exc:
                detail = str(exc)

        if not applied and shutil.which("git"):
            try:
                process = subprocess.run(
                    ["git", "apply", "--whitespace=nowarn", "--recount", "-p0"],
                    cwd=staged,
                    input=sanitized_patch,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if process.returncode == 0:
                    applied = True
                else:
                    git_err = (process.stderr or process.stdout).strip()
                    detail = f"{detail} | git apply: {git_err}" if detail else git_err
            except OSError as exc:
                detail = f"{detail} | git: {exc}" if detail else str(exc)

        if not applied:
            try:
                _apply_hunks_fallback(workspace, staged, files, sanitized_patch)
                applied = True
            except Exception as exc:  # noqa: BLE001
                py_err = str(exc)
                detail = f"{detail} | python fallback: {py_err}" if detail else py_err

        if not applied:
            raise PatchApplicationError(f"Unified Diff was not applied: {detail}")

        _commit_staged_changes(workspace, staged, files)


def _parse_and_validate_headers(
    workspace: Path,
    content: str,
    allowed_resolved: set[Path] | None = None,
) -> list[_PatchFile]:
    headers: list[str] = []
    for line in content.splitlines():
        match = _HEADER.match(line)
        if match:
            headers.append(match.group(2).strip())
    if len(headers) % 2:
        raise PatchApplicationError("patch contains an incomplete file header pair")

    files: list[_PatchFile] = []
    for index in range(0, len(headers), 2):
        source, target = headers[index], headers[index + 1]
        source_path = _safe_patch_path(workspace, source, allow_dev_null=True)
        target_path = _safe_patch_path(workspace, target, allow_dev_null=True)
        if source_path is None and target_path is None:
            raise PatchApplicationError("patch cannot delete and create /dev/null")
        if allowed_resolved is not None:
            for p in (source_path, target_path):
                if p is not None and p not in allowed_resolved:
                    raise PatchApplicationError(f"patch target is outside allowed_paths: {p.relative_to(workspace)}")
        files.append(_PatchFile(source, target, source_path, target_path))
    return files


def _safe_patch_path(workspace: Path, raw_path: str, *, allow_dev_null: bool) -> Path | None:
    path = raw_path.strip('"')
    if path == "/dev/null" and allow_dev_null:
        return None
    path = path.removeprefix("a/").removeprefix("b/")
    path = path.replace("\\", "/")
    candidate = Path(path)
    if candidate.is_absolute():
        resolved = candidate.resolve(strict=False)
        if not _is_within(workspace, resolved):
            raise PatchApplicationError(f"patch path escapes workspace: {raw_path}")
        return resolved
    if any(part == ".." for part in candidate.parts):
        raise PatchApplicationError(f"patch path contains traversal: {raw_path}")
    resolved = (workspace / candidate).resolve(strict=False)
    if not _is_within(workspace, resolved):
        raise PatchApplicationError(f"patch path escapes workspace: {raw_path}")
    return resolved


def _normalize_headers(
    workspace: Path, content: str, files: list[_PatchFile]
) -> str:
    iterator = iter(files)
    output: list[str] = []
    current: _PatchFile | None = None
    for line in content.splitlines(keepends=True):
        match = _HEADER.match(line.rstrip("\r\n"))
        if match:
            if match.group(1) == "---":
                current = next(iterator)
                path = _relative_header(workspace, current.source, current.source_path)
            else:
                if current is None:
                    raise PatchApplicationError("patch contains an unexpected target header")
                path = _relative_header(workspace, current.target, current.target_path)
            newline = "\n" if line.endswith("\n") else ""
            output.append(f"{match.group(1)} {path}{newline}")
        else:
            output.append(line)
    return "".join(output)


def _relative_header(workspace: Path, raw_path: str, path: Path | None) -> str:
    del raw_path
    if path is None:
        return "/dev/null"
    return str(path.relative_to(workspace))


def _commit_staged_changes(workspace: Path, staged: Path, files: list[_PatchFile]) -> None:
    targets: list[tuple[Path, Path | None]] = []
    for file in files:
        if file.target_path is None and file.source_path is not None:
            targets.append((file.source_path, None))
        elif file.target_path is not None:
            staged_target = (staged / file.target_path.relative_to(workspace)).resolve(strict=False)
            if not _is_within(staged.resolve(strict=False), staged_target):
                raise PatchApplicationError(f"staged path escapes staging area: {file.target}")
            targets.append((file.target_path, staged_target))

    backups: dict[Path, bytes | None] = {}
    try:
        for destination, staged_target in targets:
            resolved_destination = destination.resolve(strict=False)
            if not _is_within(workspace, resolved_destination):
                raise PatchApplicationError(f"commit path escapes workspace: {destination}")
            if destination.is_symlink():
                raise PatchApplicationError(f"refusing to overwrite symlink: {destination}")
            if destination not in backups:
                backups[destination] = destination.read_bytes() if destination.exists() else None
            if staged_target is None:
                if destination.exists():
                    destination.unlink()
            else:
                if not staged_target.exists():
                    raise PatchApplicationError(f"staged target was not created: {file.target}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                content = staged_target.read_text(encoding="utf-8", errors="replace")
                if destination.suffix == ".java":
                    content = sanitize_java_imports(content)
                destination.write_text(content, encoding="utf-8")
    except Exception as exc:
        for destination, previous in backups.items():
            try:
                if previous is None:
                    if destination.exists():
                        destination.unlink()
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(previous)
            except OSError:
                pass
        if isinstance(exc, PatchApplicationError):
            raise
        raise PatchApplicationError(f"Failed to commit patched files: {exc}") from exc


def _commit_text_map_atomically(workspace: Path, staged_contents: dict[Path, str]) -> None:
    """Write a mapping of resolved target paths to new text atomically with byte-level rollback on failure."""
    backups: dict[Path, bytes | None] = {}
    try:
        for target_path, updated_text in staged_contents.items():
            resolved = target_path.resolve(strict=False)
            if not _is_within(workspace, resolved):
                raise PatchApplicationError(f"commit path escapes workspace: {target_path}")
            if target_path.is_symlink():
                raise PatchApplicationError(f"refusing to overwrite symlink: {target_path}")
            if target_path not in backups:
                backups[target_path] = target_path.read_bytes() if target_path.exists() else None
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(updated_text, encoding="utf-8")
    except Exception as exc:
        for destination, previous in backups.items():
            try:
                if previous is None:
                    if destination.exists():
                        destination.unlink()
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(previous)
            except OSError:
                pass
        if isinstance(exc, PatchApplicationError):
            raise
        raise PatchApplicationError(f"Failed to commit patched files: {exc}") from exc


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _sanitize_and_recount_patch(patch_content: str) -> str:
    """
    Sanitizes LLM-generated Unified Diffs by fixing missing space prefixes on context lines
    and recalculating hunk line counts (@@ -old_start,old_count +new_start,new_count @@).
    """
    lines = patch_content.splitlines()
    result: list[str] = []
    i = 0
    hunk_header_re = re.compile(r"^@@\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@(.*)$")

    while i < len(lines):
        line = lines[i]
        m = hunk_header_re.match(line)
        if not m:
            result.append(line)
            i += 1
            continue

        old_start = int(m.group(1))
        new_start = int(m.group(3))
        trailing = m.group(5) or ""
        i += 1

        hunk_body: list[str] = []
        old_count = 0
        new_count = 0

        while i < len(lines):
            curr = lines[i]
            if (
                curr.startswith("--- ")
                or curr.startswith("+++ ")
                or curr.startswith("diff ")
                or curr.startswith("Index: ")
                or hunk_header_re.match(curr)
            ):
                break

            if curr.startswith("+"):
                hunk_body.append(curr)
                new_count += 1
            elif curr.startswith("-"):
                hunk_body.append(curr)
                old_count += 1
            elif curr.startswith("\\"):
                hunk_body.append(curr)
            elif curr.startswith(" "):
                hunk_body.append(curr)
                old_count += 1
                new_count += 1
            else:
                hunk_body.append(" " + curr)
                old_count += 1
                new_count += 1
            i += 1

        result.append(f"@@ -{old_start},{old_count} +{new_start},{new_count} @@{trailing}")
        result.extend(hunk_body)

    return "\n".join(result) + "\n"


def _apply_hunks_fallback(
    workspace: Path,
    staged: Path,
    files: list[_PatchFile],
    sanitized_patch: str,
) -> None:
    """
    Pure-Python hunk applicator that locates context lines in the target file even when
    LLM line numbers in @@ -L,C +L,C @@ are inaccurate.
    """
    del workspace, files
    hunk_header_re = re.compile(r"^@@\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@")
    lines = sanitized_patch.splitlines()

    current_target: Path | None = None
    file_hunks: list[tuple[Path, list[str]]] = []
    active_hunk: list[str] | None = None

    for line in lines:
        if line.startswith("--- "):
            continue
        if line.startswith("+++ "):
            if active_hunk is not None and current_target is not None:
                file_hunks.append((current_target, active_hunk))
                active_hunk = None
            rel = line[4:].strip()
            current_target = None if rel == "/dev/null" else (staged / rel)
            continue
        if hunk_header_re.match(line):
            if active_hunk is not None and current_target is not None:
                file_hunks.append((current_target, active_hunk))
            active_hunk = []
            continue
        if active_hunk is not None:
            active_hunk.append(line)

    if active_hunk is not None and current_target is not None:
        file_hunks.append((current_target, active_hunk))

    if not file_hunks:
        raise PatchApplicationError("No hunks found for fallback application")

    for staged_file, hunk_lines in file_hunks:
        if not staged_file.exists():
            new_lines = [line_item[1:] for line_item in hunk_lines if line_item.startswith(("+", " "))]
            staged_file.parent.mkdir(parents=True, exist_ok=True)
            staged_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            continue

        content = staged_file.read_text(encoding="utf-8")
        old_lines = []
        new_lines = []
        for hl in hunk_lines:
            if hl.startswith("\\ No newline"):
                continue
            if hl.startswith("-"):
                old_lines.append(hl[1:])
            elif hl.startswith("+"):
                new_lines.append(hl[1:])
            elif hl.startswith(" "):
                old_lines.append(hl[1:])
                new_lines.append(hl[1:])

        if not old_lines and new_lines:
            content = content.rstrip("\n") + "\n" + "\n".join(new_lines) + "\n"
        else:
            old_str = "\n".join(old_lines)
            new_str = "\n".join(new_lines)

            if old_str in content:
                content = content.replace(old_str, new_str, 1)
            else:
                old_trimmed = old_str.strip()
                new_trimmed = new_str.strip()
                if old_trimmed and old_trimmed in content:
                    content = content.replace(old_trimmed, new_trimmed, 1)
                else:
                    content_lines = content.splitlines()
                    found_idx = -1
                    target_sub = [line_item.strip() for line_item in old_lines if line_item.strip()]
                    if target_sub:
                        for c_idx in range(len(content_lines) - len(target_sub) + 1):
                            candidate = [content_lines[c_idx + k].strip() for k in range(len(target_sub))]
                            if candidate == target_sub:
                                found_idx = c_idx
                                break
                    if found_idx != -1:
                        content_lines[found_idx : found_idx + len(target_sub)] = [
                            line_item for line_item in new_lines if line_item.strip() or len(new_lines) == 1
                        ]
                        content = "\n".join(content_lines) + "\n"
                    else:
                        raise PatchApplicationError(f"Could not locate hunk context in {staged_file.name}")

        staged_file.write_text(content, encoding="utf-8")


def _apply_search_replace_blocks(
    workspace: Path,
    content: str,
    allowed_resolved: set[Path] | None = None,
) -> None:
    """
    Applies <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE blocks atomically.
    """
    block_pattern = re.compile(
        r"(?:(?:###?\s*(?:Modified\s*|File:\s*|Target:\s*|Path:\s*)|File:\s*|`?)([\w/.-]+\.java)`?\s*)?"
        r"<<<<<<<\s*SEARCH\r?\n(.*?)\r?\n=======\r?\n(.*?)\r?\n>>>>>>>\s*REPLACE",
        re.DOTALL,
    )
    matches = list(block_pattern.finditer(content))
    if not matches:
        raise PatchApplicationError("No valid SEARCH/REPLACE blocks found")

    staged_contents: dict[Path, str] = {}
    last_resolved_file: Path | None = None

    for match in matches:
        file_hint, search_text, replace_text = match.group(1), match.group(2), match.group(3)
        target_file: Path | None = None

        if file_hint:
            target_path = _safe_patch_path(workspace, file_hint.strip(), allow_dev_null=False)
            if target_path is None or not target_path.is_file():
                raise PatchApplicationError(f"Explicit SEARCH/REPLACE target file does not exist: {file_hint}")
            target_file = target_path
            last_resolved_file = target_file
        elif last_resolved_file is not None:
            current_text = staged_contents.get(
                last_resolved_file,
                last_resolved_file.read_text(encoding="utf-8", errors="replace"),
            )
            if search_text in current_text or search_text.strip() in current_text:
                target_file = last_resolved_file

        if target_file is None:
            candidate_pool = (
                sorted(allowed_resolved)
                if allowed_resolved is not None
                else sorted(workspace.rglob("*.java"))
            )
            matching_files: list[Path] = []
            for candidate in candidate_pool:
                if candidate.is_file():
                    c_text = staged_contents.get(
                        candidate,
                        candidate.read_text(encoding="utf-8", errors="replace"),
                    )
                    if search_text in c_text or (search_text.strip() and search_text.strip() in c_text):
                        matching_files.append(candidate)
            if len(matching_files) == 1:
                target_file = matching_files[0]
                last_resolved_file = target_file

        if target_file is None:
            raise PatchApplicationError("Could not identify target file for SEARCH/REPLACE block")

        resolved_target = target_file.resolve(strict=False)
        if not _is_within(workspace, resolved_target):
            raise PatchApplicationError(f"SEARCH/REPLACE target escapes workspace: {target_file}")
        if allowed_resolved is not None and resolved_target not in allowed_resolved:
            raise PatchApplicationError(
                f"SEARCH/REPLACE target is outside allowed_paths: {resolved_target.relative_to(workspace)}"
            )

        original = staged_contents.get(resolved_target, resolved_target.read_text(encoding="utf-8"))
        if search_text in original:
            new_code = original.replace(search_text, replace_text, 1)
        elif search_text.strip() and search_text.strip() in original:
            new_code = original.replace(search_text.strip(), replace_text.strip(), 1)
        else:
            orig_lines = original.splitlines()
            search_lines = [line_item.strip() for line_item in search_text.splitlines() if line_item.strip()]
            found = -1
            if search_lines:
                for i in range(len(orig_lines) - len(search_lines) + 1):
                    if [orig_lines[i + k].strip() for k in range(len(search_lines))] == search_lines:
                        found = i
                        break
            if found != -1:
                replace_lines = replace_text.splitlines()
                orig_lines[found : found + len(search_lines)] = replace_lines
                new_code = "\n".join(orig_lines) + "\n"
            else:
                raise PatchApplicationError(f"Could not locate SEARCH block in {resolved_target.name}")

        if resolved_target.suffix == ".java":
            new_code = sanitize_java_imports(new_code)
        staged_contents[resolved_target] = new_code

    _commit_text_map_atomically(workspace, staged_contents)


def _extract_whole_file_blocks(
    workspace: Path,
    content: str,
    allowed_resolved: set[Path] | None = None,
) -> list[tuple[Path, str]]:
    results: list[tuple[Path, str]] = []

    header_block_pattern = re.compile(
        r"(?:###?\s*(?:Modified\s*|File:\s*|Target:\s*|Path:\s*)|File:\s*|`)([\w/.-]+\.(?:java|xml|properties|yaml|yml|json|txt))`?"
        r"[^\n`]*\r?\n+```(?:[a-zA-Z0-9_+-]+)?\r?\n(.*?)\r?\n```",
        re.DOTALL,
    )
    for match in header_block_pattern.finditer(content):
        file_hint = match.group(1).strip()
        code = match.group(2)
        target_path = _safe_patch_path(workspace, file_hint, allow_dev_null=False)
        if target_path and target_path.is_file():
            resolved = target_path.resolve(strict=False)
            if allowed_resolved is not None and resolved not in allowed_resolved:
                raise PatchApplicationError(f"whole-file patch target outside allowed_paths: {file_hint}")
            results.append((resolved, code))

    if results:
        return results

    code_block_pattern = re.compile(r"```(?:java)?\r?\n(.*?)\r?\n```", re.DOTALL)
    blocks = code_block_pattern.findall(content)
    if not blocks and ("package " in content or _JAVA_CLASS_DECL.search(content)):
        blocks = [content]

    for block in blocks:
        code = block.strip()
        class_match = _JAVA_CLASS_DECL.search(code)
        if not class_match:
            continue
        class_name = class_match.group(1)
        pkg_match = re.search(r"package\s+([a-zA-Z0-9_.]+);", code)

        candidates = [p for p in workspace.rglob(f"{class_name}.java") if p.is_file()]
        target_file: Path | None = None
        if pkg_match:
            pkg_path_part = pkg_match.group(1).replace(".", "/")
            matching_pkg = [p for p in candidates if pkg_path_part in str(p.as_posix())]
            if len(matching_pkg) == 1:
                target_file = matching_pkg[0]
        if target_file is None and len(candidates) == 1:
            target_file = candidates[0]

        if target_file:
            resolved = target_file.resolve(strict=False)
            if _is_within(workspace, resolved):
                if allowed_resolved is not None and resolved not in allowed_resolved:
                    raise PatchApplicationError(f"whole-file patch target outside allowed_paths: {resolved}")
                results.append((resolved, code))

    return results


def _apply_whole_file_blocks(
    workspace: Path,
    blocks: list[tuple[Path, str]],
    allowed_resolved: set[Path] | None = None,
) -> None:
    staged: dict[Path, str] = {}
    for target_file, code in blocks:
        resolved = target_file.resolve(strict=False)
        if not _is_within(workspace, resolved):
            raise PatchApplicationError(f"patch path escapes workspace: {target_file}")
        if allowed_resolved is not None and resolved not in allowed_resolved:
            raise PatchApplicationError(f"whole-file patch target outside allowed_paths: {resolved}")
        clean_code = code.strip() + "\n"
        if resolved.suffix == ".java":
            clean_code = sanitize_java_imports(clean_code)
        staged[resolved] = clean_code

    _commit_text_map_atomically(workspace, staged)
