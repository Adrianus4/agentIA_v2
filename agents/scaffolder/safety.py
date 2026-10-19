from __future__ import annotations

import hashlib
import re
from pathlib import Path

from contracts.models import ManifestEvidence, ScaffoldRequest

_SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9._-]*$")
_SAFE_PACKAGE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)*$")


def validate_request(request: ScaffoldRequest) -> None:
    if not _SAFE_IDENTIFIER.fullmatch(request.group_id):
        raise ValueError("invalid group_id")
    if not _SAFE_IDENTIFIER.fullmatch(request.artifact_id):
        raise ValueError("invalid artifact_id")
    if not _SAFE_PACKAGE.fullmatch(request.package_name):
        raise ValueError("invalid package_name")
    if any(
        marker in value
        for value in (request.group_id, request.artifact_id, request.package_name)
        for marker in (";", "|", "&", "$", "`", "\n", "\r")
    ):
        raise ValueError("unsafe scaffold identifier")
    workspace = Path(request.workspace_path).expanduser().resolve(strict=False)
    if workspace.is_file():
        raise ValueError("workspace_path must be a directory")


def collect_manifest(workspace_path: str) -> list[ManifestEvidence]:
    workspace = Path(workspace_path).expanduser().resolve(strict=True)
    evidence: list[ManifestEvidence] = []
    for path in sorted(item for item in workspace.rglob("*") if item.is_file()):
        relative = path.relative_to(workspace).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        evidence.append(
            ManifestEvidence(path=relative, sha256=digest, size=path.stat().st_size)
        )
    return evidence
