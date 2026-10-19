import pytest
from pydantic import ValidationError

from contracts.models import ScaffoldConfig, ScaffoldRequest


def test_scaffold_config_rejects_unknown_placeholder() -> None:
    with pytest.raises(ValidationError):
        ScaffoldConfig(
            tool="fake",
            tool_version="1",
            command_template=["tool", "{unknown}"],
            allowed_extensions=[],
        )


def test_scaffold_request_rejects_traversal_and_uppercase_package() -> None:
    with pytest.raises(ValidationError):
        ScaffoldRequest(
            group_id="com.example",
            artifact_id="../escape",
            package_name="Com.Example",
            java_version="17",
            workspace_path="/tmp/workspace",
        )
