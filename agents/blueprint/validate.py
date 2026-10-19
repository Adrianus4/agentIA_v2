from typing import Any

from contracts.models import Diagnostic, UniformErrorBody

REQUIRED_FIELDS = ("serviceName", "packageName", "entities", "userStories")


def validate_blueprint(payload: dict[str, Any]) -> UniformErrorBody:
    """
    Validate a raw blueprint dictionary against structural integrity rules.

    Args:
        payload: Dict containing blueprint definition.

    Returns:
        UniformErrorBody: Pydantic model containing:
            - valid: True if all checks pass, False if any violation found.
            - diagnostics: List[Diagnostic] detailing all errors detected.
    """
    diagnostics: list[Diagnostic] = []

    # 1. Check for required fields
    for field_name in REQUIRED_FIELDS:
        if field_name not in payload or payload[field_name] is None:
            diagnostics.append(
                Diagnostic(
                    error_code="MISSING_FIELD",
                    path=field_name,
                    message=f"Required field '{field_name}' is missing or empty",
                )
            )

    # 2. Check field types for present fields
    if "serviceName" in payload and payload["serviceName"] is not None and not isinstance(payload["serviceName"], str):
        diagnostics.append(
            Diagnostic(
                error_code="INVALID_TYPE",
                path="serviceName",
                message="Field 'serviceName' must be a string",
            )
        )

    if "packageName" in payload and payload["packageName"] is not None and not isinstance(payload["packageName"], str):
        diagnostics.append(
            Diagnostic(
                error_code="INVALID_TYPE",
                path="packageName",
                message="Field 'packageName' must be a string",
            )
        )

    if "entities" in payload and payload["entities"] is not None:
        if not isinstance(payload["entities"], list):
            diagnostics.append(
                Diagnostic(
                    error_code="INVALID_TYPE",
                    path="entities",
                    message="Field 'entities' must be a list",
                )
            )
        else:
            # 3. Check for duplicate entity names
            seen_entities: set[str] = set()
            for idx, entity in enumerate(payload["entities"]):
                name: str | None = None
                if isinstance(entity, dict):
                    raw_name = entity.get("name")
                    if isinstance(raw_name, str):
                        name = raw_name
                elif isinstance(entity, str):
                    name = entity

                if name:
                    normalized = name.strip().lower()
                    if normalized in seen_entities:
                        diagnostics.append(
                            Diagnostic(
                                error_code="DUPLICATE_ENTITY_NAME",
                                path=f"entities[{idx}].name",
                                message=f"Duplicate entity name '{name}' found at index {idx}",
                            )
                        )
                    else:
                        seen_entities.add(normalized)

    if "userStories" in payload and payload["userStories"] is not None and not isinstance(payload["userStories"], list):
        diagnostics.append(
            Diagnostic(
                error_code="INVALID_TYPE",
                path="userStories",
                message="Field 'userStories' must be a list",
            )
        )

    return UniformErrorBody(
        valid=len(diagnostics) == 0,
        diagnostics=diagnostics,
    )
