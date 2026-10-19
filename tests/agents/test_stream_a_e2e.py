import pytest

from agents.blueprint.validate import validate_blueprint
from agents.profiles.loader import get_profile
from contracts.models import FrameworkProfile, ProfileDisabled, UnknownFramework


def test_stream_a_e2e_valid_blueprint_to_profile_loader():
    """
    End-to-end integration test:
    1. Ingest raw valid blueprint payload
    2. Validate blueprint schema via validate_blueprint
    3. Extract framework configuration
    4. Successfully load FrameworkProfile via get_profile
    5. Verify contract satisfaction and framework concepts
    """
    payload = {
        "serviceName": "QuarkusOrderService",
        "packageName": "org.acme.orders",
        "framework": "quarkus",
        "framework_version": "3",
        "entities": [
            {"name": "Order"},
            {"name": "OrderItem"},
        ],
        "userStories": [
            "As a customer, I want to create an order.",
            "As a customer, I want to view my order history.",
        ],
    }

    # Step 1: Validate Blueprint
    validation_result = validate_blueprint(payload)
    assert validation_result.valid is True
    assert len(validation_result.diagnostics) == 0

    # Step 2: Extract framework and version
    framework = payload["framework"]
    framework_version = payload["framework_version"]

    # Step 3: Load Framework Profile
    profile = get_profile(framework, framework_version)
    assert isinstance(profile, FrameworkProfile)
    assert profile.id == "quarkus-3"
    assert profile.framework == "quarkus"
    assert profile.framework_version == "3"
    assert profile.enabled is True

    # Step 4: Verify concepts mapping
    mock_concept = profile.concepts["mock_in_test"]
    assert mock_concept["annotations"] == ["@InjectMock"]
    assert mock_concept["imports"] == ["io.quarkus.test.junit.mockito.InjectMock"]


def test_stream_a_e2e_disabled_profile_rejection():
    """Verify that disabled profiles in profiles/ are rejected by get_profile."""
    payload = {
        "serviceName": "SampleService",
        "packageName": "org.example.sample",
        "framework": "disabled-sample",
        "framework_version": "1",
        "entities": [{"name": "Sample"}],
        "userStories": ["Do something"],
    }

    # Blueprint itself passes structural validation
    validation_result = validate_blueprint(payload)
    assert validation_result.valid is True

    # Profile loader must deterministically reject disabled profile
    with pytest.raises(ProfileDisabled):
        get_profile(payload["framework"], payload["framework_version"])


def test_stream_a_e2e_unknown_framework_rejection():
    """Verify that unsupported frameworks are rejected by get_profile."""
    payload = {
        "serviceName": "UnknownService",
        "packageName": "org.example.unknown",
        "framework": "unsupported-framework",
        "framework_version": "99",
        "entities": [{"name": "Entity"}],
        "userStories": ["Do something"],
    }

    validation_result = validate_blueprint(payload)
    assert validation_result.valid is True

    with pytest.raises(UnknownFramework):
        get_profile(payload["framework"], payload["framework_version"])


def test_stream_a_e2e_invalid_blueprint_blocked():
    """Verify that malformed blueprints fail validation before profile loading."""
    invalid_payload = {
        "serviceName": "BrokenService",
        # missing packageName
        "entities": [
            {"name": "Order"},
            {"name": "Order"},  # duplicate entity
        ],
        # missing userStories
    }

    validation_result = validate_blueprint(invalid_payload)
    assert validation_result.valid is False
    assert len(validation_result.diagnostics) >= 3

    error_codes = {d.error_code for d in validation_result.diagnostics}
    assert "MISSING_FIELD" in error_codes
    assert "DUPLICATE_ENTITY_NAME" in error_codes
