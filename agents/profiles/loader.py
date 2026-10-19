"""
PF-1 Framework Profile Loader Service.

Loads, validates, and resolves framework profiles from the local 'profiles/' directory.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from contracts.models import (
    FrameworkProfile,
    ProfileDisabled,
    UnknownFramework,
)

DEFAULT_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent / "profiles"


def _version_candidates(norm_version: str) -> list[str]:
    """Return ordered version candidates from most specific (X.Y.Z) to major (X)."""
    candidates = [norm_version]
    if "." in norm_version:
        parts = norm_version.split(".")
        if len(parts) >= 2:
            minor = f"{parts[0]}.{parts[1]}"
            if minor not in candidates:
                candidates.append(minor)
        major = parts[0]
        if major not in candidates:
            candidates.append(major)
    if "3.15" not in candidates and norm_version in ("3.15.0.Final", "3.15.1"):
        candidates.insert(0, "3.15")
    return candidates


def get_profile(
    framework: str,
    framework_version: str,
    profiles_dir: str | Path | None = None,
) -> FrameworkProfile:
    """
    Resolve and validate a FrameworkProfile by framework name and version.
    """
    if profiles_dir is None:
        base_dir = DEFAULT_PROFILES_DIR
    else:
        base_dir = Path(profiles_dir)

    if not base_dir.exists() or not base_dir.is_dir():
        raise UnknownFramework(f"Profiles directory not found: {base_dir}")

    norm_framework = framework.strip().lower()
    norm_version = str(framework_version).strip()
    if norm_framework.startswith("quarkus-"):
        suffix = norm_framework.split("-", 1)[1].strip()
        norm_framework = "quarkus"
        if not norm_version or norm_version in ("3", "default"):
            norm_version = suffix or "3.15"

    versions_to_try = _version_candidates(norm_version)

    matched_path: Path | None = None

    # 1. Check direct file convention: {framework}-{version}.yaml or .yml (most specific first)
    for ver_candidate in versions_to_try:
        candidate_paths = [
            base_dir / f"{norm_framework}-{ver_candidate}.yaml",
            base_dir / f"{norm_framework}-{ver_candidate}.yml",
        ]
        for p in candidate_paths:
            if p.exists() and p.is_file():
                matched_path = p
                break
        if matched_path is not None:
            break

    # 2. If direct file naming convention is not found, search all YAMLs by version priority
    if matched_path is None:
        yaml_files = sorted(p for p in base_dir.glob("*.y*ml") if p.is_file())
        for ver_candidate in versions_to_try:
            for p in yaml_files:
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        content = yaml.safe_load(f)
                    if isinstance(content, dict):
                        fw = str(content.get("framework", "")).strip().lower()
                        ver = str(content.get("framework_version", "")).strip()
                        if fw == norm_framework and ver == ver_candidate:
                            matched_path = p
                            break
                except (yaml.YAMLError, OSError):
                    pass
            if matched_path is not None:
                break

    if matched_path is None:
        raise UnknownFramework(
            f"Unknown framework '{framework}' with version '{framework_version}'"
        )

    with open(matched_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    if not isinstance(raw_data, dict):
        raise ValueError(f"Invalid profile format in {matched_path}: expected mapping")

    profile = FrameworkProfile.model_validate(raw_data)

    if not profile.enabled:
        raise ProfileDisabled(
            f"Profile '{profile.id}' ({framework} {framework_version}) is currently disabled"
        )

    return profile
