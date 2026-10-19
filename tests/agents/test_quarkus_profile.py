from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from contracts.models import FrameworkProfile

PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "profiles" / "quarkus-3.yaml"


def test_quarkus_profile_file_exists():
    """Verify that profiles/quarkus-3.yaml exists on disk."""
    assert PROFILE_PATH.exists(), f"Profile file does not exist at {PROFILE_PATH}"


def test_quarkus_profile_schema_valid():
    """Verify that profiles/quarkus-3.yaml parses directly into FrameworkProfile."""
    assert PROFILE_PATH.exists(), f"Profile file does not exist at {PROFILE_PATH}"
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    profile = FrameworkProfile.model_validate(data)
    assert isinstance(profile, FrameworkProfile)
    assert profile.id == "quarkus-3"
    assert profile.framework == "quarkus"
    assert profile.framework_version == "3"
    assert profile.enabled is True
    assert profile.build_tool == "maven"


def test_quarkus_profile_mock_in_test_concept():
    """Verify concepts.mock_in_test has exact required annotations and imports."""
    assert PROFILE_PATH.exists(), f"Profile file does not exist at {PROFILE_PATH}"
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    profile = FrameworkProfile.model_validate(data)
    assert "mock_in_test" in profile.concepts, "concepts must define mock_in_test"
    mock_concept = profile.concepts["mock_in_test"]
    assert mock_concept.get("annotations") == ["@InjectMock"]
    assert mock_concept.get("imports") == ["io.quarkus.test.junit.mockito.InjectMock"]


def test_quarkus_profile_forbidden_imports_and_pitfalls():
    """Verify forbidden imports and pitfalls isolate Quarkus from Spring."""
    assert PROFILE_PATH.exists(), f"Profile file does not exist at {PROFILE_PATH}"
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    profile = FrameworkProfile.model_validate(data)
    assert any("org.springframework." in imp for imp in profile.forbidden_imports)
    assert len(profile.pitfalls) > 0
    assert len(profile.verify_commands) > 0


def test_profile_strict_contract_rejection():
    """Verify that tampering or missing keys fails FrameworkProfile validation."""
    with pytest.raises(ValidationError):
        # Missing required fields should raise ValidationError
        FrameworkProfile.model_validate({"framework": "quarkus"})


def test_quarkus_315_profile_valid():
    """Verify profiles/quarkus-3.15.yaml is valid, targeting Quarkus 3.15 and Java 21 with Kafka."""
    p_path = PROFILE_PATH.parent / "quarkus-3.15.yaml"
    assert p_path.exists()
    with open(p_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    profile = FrameworkProfile.model_validate(data)
    assert profile.framework == "quarkus"
    assert profile.framework_version == "3.15"
    assert profile.java_version == "21"
    assert "kafka" in profile.scaffold.extension_map
    assert "io.quarkus:quarkus-smallrye-reactive-messaging-kafka" in profile.scaffold.allowed_extensions
