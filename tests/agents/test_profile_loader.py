import pytest
import yaml
from pydantic import ValidationError

from agents.profiles.loader import get_profile
from contracts.models import (
    FrameworkProfile,
    ProfileDisabled,
    UnknownFramework,
)


def test_get_profile_happy_path():
    """Verify get_profile returns valid FrameworkProfile for Quarkus 3."""
    profile = get_profile("quarkus", "3")
    assert isinstance(profile, FrameworkProfile)
    assert profile.id == "quarkus-3"
    assert profile.framework == "quarkus"
    assert profile.framework_version == "3"
    assert profile.enabled is True
    assert profile.concepts["mock_in_test"]["annotations"] == ["@InjectMock"]


def test_get_profile_case_insensitive():
    """Verify get_profile handles case normalization."""
    profile = get_profile("QUARKUS", "3")
    assert profile.framework == "quarkus"
    assert profile.framework_version == "3"


def test_get_profile_unknown_framework():
    """Verify UnknownFramework is raised for nonexistent framework."""
    with pytest.raises(UnknownFramework):
        get_profile("nonexistent_framework", "1")


def test_get_profile_unknown_version():
    """Verify UnknownFramework is raised for nonexistent version."""
    with pytest.raises(UnknownFramework):
        get_profile("quarkus", "999")


def test_get_profile_disabled(tmp_path):
    """Verify ProfileDisabled is raised when profile has enabled: false."""
    disabled_yaml = {
        "id": "disabled-fw-1",
        "framework": "disabled-fw",
        "framework_version": "1",
        "profile_revision": 1,
        "java_version": "17",
        "build_tool": "maven",
        "enabled": False,
        "instruction_set_revision": "v1",
        "concepts": {},
        "config": {},
        "test_style": {},
        "verify_commands": {},
        "forbidden_imports": [],
        "allowed_exceptions": [],
        "pitfalls": [],
        "templates": {},
    }
    profile_file = tmp_path / "disabled-fw-1.yaml"
    profile_file.write_text(yaml.dump(disabled_yaml), encoding="utf-8")

    with pytest.raises(ProfileDisabled):
        get_profile("disabled-fw", "1", profiles_dir=tmp_path)


def test_get_profile_invalid_schema(tmp_path):
    """Verify ValidationError is raised when profile YAML schema is broken."""
    invalid_yaml = {
        "framework": "broken-fw",
        "framework_version": "1",
        # missing id, build_tool, etc.
    }
    profile_file = tmp_path / "broken-fw-1.yaml"
    profile_file.write_text(yaml.dump(invalid_yaml), encoding="utf-8")

    with pytest.raises(ValidationError):
        get_profile("broken-fw", "1", profiles_dir=tmp_path)
