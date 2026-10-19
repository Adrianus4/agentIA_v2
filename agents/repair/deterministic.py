"""
Deterministic repairs tried before the LLM.

A compiler "cannot find symbol" for a type whose fully qualified name is known (from the framework
profile's type_imports, or from a sibling source file in the request) is fixed by adding the import.
No framework literal lives here: every FQCN comes from the profile or from the project's own files.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from contracts.models import FrameworkProfile, RepairRequest

_SYMBOL_RE = re.compile(r"symbol:\s+(?:class|variable|interface)\s+([A-Z][A-Za-z0-9_]*)")
_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.*]+)\s*;", re.MULTILINE)


def _known_types(profile: FrameworkProfile, request: RepairRequest) -> dict[str, str]:
    known = dict(profile.type_imports or {})
    for dep in request.dependencies:
        if not dep.content or not dep.path.endswith(".java"):
            continue
        package = _PACKAGE_RE.search(dep.content)
        if package:
            known.setdefault(PurePosixPath(dep.path).stem, f"{package.group(1)}.{PurePosixPath(dep.path).stem}")
    return known


def missing_import_patch(profile: FrameworkProfile, request: RepairRequest) -> str | None:
    """Return a SEARCH/REPLACE patch adding imports for unresolved known types, or None."""
    source = request.failing_file.content or ""
    if not source or not request.failing_file.path.endswith(".java"):
        return None
    known = _known_types(profile, request)
    present = set(_IMPORT_RE.findall(source))
    own_package = _PACKAGE_RE.search(source)

    to_add: list[str] = []
    for issue in request.issues:
        if "cannot find symbol" not in issue.message:
            continue
        for symbol in _SYMBOL_RE.findall(issue.message):
            fqcn = known.get(symbol)
            if not fqcn:
                continue
            wildcard = fqcn.rsplit(".", 1)[0] + ".*"
            same_package = own_package is not None and fqcn.rsplit(".", 1)[0] == own_package.group(1)
            if fqcn in present or wildcard in present or same_package or fqcn in to_add:
                continue
            to_add.append(fqcn)
    if not to_add:
        return None

    import_block = "\n".join(f"import {fqcn};" for fqcn in sorted(to_add))
    if own_package is None:
        return None
    anchor = own_package.group(0).strip()
    return (
        f"File: {request.failing_file.path}\n"
        "<<<<<<< SEARCH\n"
        f"{anchor}\n"
        "=======\n"
        f"{anchor}\n\n{import_block}\n"
        ">>>>>>> REPLACE\n"
    )
