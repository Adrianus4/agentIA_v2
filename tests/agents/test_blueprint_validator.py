from agents.blueprint.validate import validate_blueprint
from contracts.models import UniformErrorBody


def test_validate_blueprint_valid():
    """Verify that a well-formed blueprint payload is valid with 0 diagnostics."""
    payload = {
        "serviceName": "OrderService",
        "packageName": "com.example.orders",
        "entities": [
            {"name": "Order"},
            {"name": "Customer"},
        ],
        "userStories": [
            "As a customer I want to create an order",
            "As a manager I want to view orders",
        ],
    }
    result = validate_blueprint(payload)
    assert isinstance(result, UniformErrorBody)
    assert result.valid is True
    assert len(result.diagnostics) == 0


def test_validate_blueprint_missing_fields():
    """Verify that missing required keys produce MISSING_FIELD diagnostics."""
    payload = {
        "serviceName": "OrderService",
    }
    result = validate_blueprint(payload)
    assert result.valid is False
    error_codes = [d.error_code for d in result.diagnostics]
    paths = [d.path for d in result.diagnostics]
    assert "MISSING_FIELD" in error_codes
    assert "packageName" in paths
    assert "entities" in paths
    assert "userStories" in paths


def test_validate_blueprint_empty_payload():
    """Verify empty dictionary produces diagnostics for all 4 required fields."""
    result = validate_blueprint({})
    assert result.valid is False
    assert len(result.diagnostics) == 4
    paths = {d.path for d in result.diagnostics}
    assert paths == {"serviceName", "packageName", "entities", "userStories"}


def test_validate_blueprint_invalid_types():
    """Verify that non-string or non-list values produce INVALID_TYPE diagnostics."""
    payload = {
        "serviceName": 12345,  # should be string
        "packageName": "com.example",
        "entities": "not-a-list",  # should be list
        "userStories": {"story": "invalid"},  # should be list
    }
    result = validate_blueprint(payload)
    assert result.valid is False
    invalid_type_paths = [
        d.path for d in result.diagnostics if d.error_code == "INVALID_TYPE"
    ]
    assert "serviceName" in invalid_type_paths
    assert "entities" in invalid_type_paths
    assert "userStories" in invalid_type_paths


def test_validate_blueprint_duplicate_entity_names():
    """Verify duplicate entity names produce DUPLICATE_ENTITY_NAME diagnostics."""
    payload = {
        "serviceName": "CatalogService",
        "packageName": "com.example.catalog",
        "entities": [
            {"name": "Product"},
            {"name": "product"},  # Case-insensitive duplicate
        ],
        "userStories": ["Manage products"],
    }
    result = validate_blueprint(payload)
    assert result.valid is False
    duplicate_errors = [
        d for d in result.diagnostics if d.error_code == "DUPLICATE_ENTITY_NAME"
    ]
    assert len(duplicate_errors) == 1
    assert "product" in duplicate_errors[0].message.lower()


def test_validate_blueprint_multiple_accumulated_errors():
    """Verify validator collects multiple distinct errors simultaneously."""
    payload = {
        # missing serviceName
        "packageName": 999,  # invalid type
        "entities": [
            {"name": "Item"},
            {"name": "Item"},  # duplicate
        ],
        # missing userStories
    }
    result = validate_blueprint(payload)
    assert result.valid is False
    error_codes = {d.error_code for d in result.diagnostics}
    assert "MISSING_FIELD" in error_codes
    assert "INVALID_TYPE" in error_codes
    assert "DUPLICATE_ENTITY_NAME" in error_codes
