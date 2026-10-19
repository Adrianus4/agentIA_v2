"""
Template Engine Renderer for Deterministic CRUD Generation.
Renders Jinja2 templates declared in FrameworkProfile for entities, repositories, resources, and tests.
Zero hardcoded framework literals in Python code (Constitution Principle V).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)


_JINJA_ENV: Environment | None = None

_PRIMITIVE_TO_WRAPPER = {
    "int": "Integer",
    "long": "Long",
    "double": "Double",
    "float": "Float",
    "boolean": "Boolean",
    "short": "Short",
    "byte": "Byte",
    "char": "Character",
}


def get_jinja_env(templates_root: str | Path | None = None) -> Environment:
    global _JINJA_ENV
    if _JINJA_ENV is None or templates_root is not None:
        root = Path(templates_root) if templates_root else Path(__file__).resolve().parents[2]
        _JINJA_ENV = Environment(
            loader=FileSystemLoader(str(root)),
            autoescape=select_autoescape(disabled_extensions=("jinja", "java")),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _JINJA_ENV


def _to_camel_case(snake_str: str) -> str:
    parts = snake_str.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:]) if len(parts) > 1 else snake_str


def _to_pascal_case(name: str) -> str:
    camel = _to_camel_case(name)
    return camel[0].upper() + camel[1:] if camel else ""


def _normalize_java_type(raw_type: str) -> str:
    cleaned = raw_type.strip()
    return _PRIMITIVE_TO_WRAPPER.get(cleaned, cleaned)


def _derive_sample_value(java_type: str, variant: int = 1) -> str:
    norm_type = _normalize_java_type(java_type)
    if variant == 1:
        mapping = {
            "Long": "1L",
            "Integer": "1",
            "Short": "(short) 1",
            "Byte": "(byte) 1",
            "String": '"Sample"',
            "BigDecimal": 'new BigDecimal("100.00")',
            "Boolean": "true",
            "Double": "10.5",
            "Float": "10.5f",
            "LocalDate": "LocalDate.now()",
            "LocalDateTime": "LocalDateTime.now()",
            "Instant": "Instant.now()",
            "Timestamp": "new Timestamp(System.currentTimeMillis())",
            "UUID": "UUID.randomUUID()",
        }
    else:
        mapping = {
            "Long": f"{variant}L",
            "Integer": str(variant),
            "Short": f"(short) {variant}",
            "Byte": f"(byte) {variant}",
            "String": f'"Sample_{variant}"',
            "BigDecimal": f'new BigDecimal("{variant}00.00")',
            "Boolean": "false" if variant % 2 == 0 else "true",
            "Double": f"{variant}0.5",
            "Float": f"{variant}0.5f",
            "LocalDate": "LocalDate.now()",
            "LocalDateTime": "LocalDateTime.now()",
            "Instant": "Instant.now()",
            "Timestamp": "new Timestamp(System.currentTimeMillis())",
            "UUID": "UUID.randomUUID()",
        }
    return mapping.get(norm_type, "null")


def _derive_json_value(java_type: str, field_name: str, variant: int = 1) -> Any:
    norm_type = _normalize_java_type(java_type)
    suffix = str(variant)
    lower_name = field_name.lower()
    if norm_type in ("Long", "Integer", "Short", "Byte"):
        return variant
    if norm_type in ("Double", "Float", "BigDecimal"):
        return float(f"{variant}00.00")
    if norm_type == "Boolean":
        return variant % 2 == 1
    if norm_type == "LocalDate":
        return f"2026-10-1{min(variant + 3, 9)}"
    if norm_type == "LocalDateTime":
        return f"2026-10-1{min(variant + 3, 9)}T12:00:00"
    if norm_type in ("Instant", "Timestamp", "OffsetDateTime", "ZonedDateTime"):
        return f"2026-10-1{min(variant + 3, 9)}T12:00:00Z"
    if norm_type == "UUID":
        digit = str(min(variant, 9))
        return f"{digit * 8}-{digit * 4}-{digit * 4}-{digit * 4}-{digit * 12}"
    if "email" in lower_name:
        return f"user{suffix}@example.com"
    return f"sample_{field_name}_{suffix}"


def _java_escaped_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload)
    return raw.replace("\\", "\\\\").replace('"', '\\"')


def prepare_template_context(
    entity_def: dict[str, Any],
    package_name: str,
) -> dict[str, Any]:
    """Extract and format entity fields for Jinja2 template rendering."""
    entity_name = str(entity_def.get("name", "Entity")).strip()
    table_name = str(entity_def.get("tableName", entity_def.get("table_name", entity_name.lower())))
    raw_fields = entity_def.get("fields", [])

    raw_entity_pk = entity_def.get("primaryKey", entity_def.get("primary_key"))
    entity_pk_name: str | None = None
    entity_pk_type: str = "Long"
    if isinstance(raw_entity_pk, str) and raw_entity_pk.strip():
        entity_pk_name = raw_entity_pk.strip()
    elif isinstance(raw_entity_pk, dict):
        if raw_entity_pk.get("name"):
            entity_pk_name = str(raw_entity_pk["name"]).strip()
        if raw_entity_pk.get("type"):
            entity_pk_type = _normalize_java_type(str(raw_entity_pk["type"]))

    any_explicit_field_pk = False
    if isinstance(raw_fields, list):
        for f in raw_fields:
            if isinstance(f, dict) and bool(f.get("primaryKey", f.get("primary_key", False))):
                any_explicit_field_pk = True
                break

    fields: list[dict[str, Any]] = []
    has_primary_key = False

    if isinstance(raw_fields, list):
        for f in raw_fields:
            if not isinstance(f, dict):
                continue
            f_name = str(f.get("name", ""))
            raw_f_type = str(f.get("type", "String"))
            explicit_pk = bool(f.get("primaryKey", f.get("primary_key", False)))
            if explicit_pk:
                is_pk = True
            elif entity_pk_name is not None:
                is_pk = f_name.lower() == entity_pk_name.lower()
            elif not any_explicit_field_pk:
                is_pk = f_name.lower() == "id"
            else:
                is_pk = False

            # Normalize primitive types to boxed wrapper types so JPA/Panache generics and null checks compile
            f_type = _normalize_java_type(raw_f_type)
            if is_pk:
                has_primary_key = True
            is_nullable = bool(f.get("nullable", True))
            is_unique = bool(f.get("unique", False))
            camel = _to_camel_case(f_name)
            pascal = _to_pascal_case(f_name)

            raw_constraints = f.get("validationRules") or f.get("constraints") or []
            constraints = [str(c).strip() for c in raw_constraints if str(c).strip()] if isinstance(raw_constraints, list) else []

            fields.append({
                "raw_name": f_name,
                "column_name": f_name,
                "java_name": camel,
                "pascal_name": pascal,
                "java_type": f_type,
                "primary_key": is_pk,
                "nullable": is_nullable,
                "unique": is_unique,
                "constraints": constraints,
                "sample_value": _derive_sample_value(f_type, variant=1),
                "updated_sample_value": _derive_sample_value(f_type, variant=2),
            })

    if not has_primary_key:
        pk_raw_name = entity_pk_name or "id"
        pk_camel = _to_camel_case(pk_raw_name)
        pk_pascal = _to_pascal_case(pk_raw_name)
        norm_pk_type = _normalize_java_type(entity_pk_type)
        fields.insert(0, {
            "raw_name": pk_raw_name,
            "column_name": pk_raw_name,
            "java_name": pk_camel,
            "pascal_name": pk_pascal,
            "java_type": norm_pk_type,
            "primary_key": True,
            "nullable": False,
            "unique": True,
            "constraints": [],
            "sample_value": _derive_sample_value(norm_pk_type, variant=1),
            "updated_sample_value": _derive_sample_value(norm_pk_type, variant=2),
        })

    resource_path = f"/api/{entity_name.lower()}"

    pk_field = next((f for f in fields if f.get("primary_key")), None)
    id_type = _normalize_java_type(str(pk_field.get("java_type", "Long"))) if pk_field else "Long"
    id_name = str(pk_field.get("java_name", "id")) if pk_field else "id"
    id_pascal_name = str(pk_field.get("pascal_name", "Id")) if pk_field else "Id"
    id_sample_value = str(pk_field.get("sample_value", "1L")) if pk_field else "1L"

    id_generated = id_type in ("Long", "Integer", "Short", "Byte", "UUID")
    if id_type == "UUID":
        not_found_id_literal = "00000000-0000-0000-0000-000000000000"
    elif id_type in ("Long", "Integer", "Short", "Byte"):
        not_found_id_literal = "999999"
    else:
        not_found_id_literal = "non-existent-id"

    # Use variants 3 and 4 for REST ResourceTest payloads so they never collide with RepositoryTest variants 1 and 2
    create_payload: dict[str, Any] = {}
    update_payload: dict[str, Any] = {}
    first_editable_string_field: str | None = None
    first_editable_updated_value: str | None = None

    for f in fields:
        j_name = f["java_name"]
        j_type = f["java_type"]
        if f["primary_key"]:
            if not id_generated:
                create_payload[j_name] = _derive_json_value(j_type, j_name, variant=3)
                update_payload[j_name] = _derive_json_value(j_type, j_name, variant=3)
        else:
            create_payload[j_name] = _derive_json_value(j_type, j_name, variant=3)
            upd_val = _derive_json_value(j_type, j_name, variant=4)
            update_payload[j_name] = upd_val
            if first_editable_string_field is None and j_type == "String":
                first_editable_string_field = j_name
                first_editable_updated_value = str(upd_val)

    return {
        "package_name": package_name,
        "entity_name": entity_name,
        "table_name": table_name,
        "resource_path": resource_path,
        "fields": fields,
        "id_type": id_type,
        "id_name": id_name,
        "id_pascal_name": id_pascal_name,
        "id_sample_value": id_sample_value,
        "id_generated": id_generated,
        "not_found_id_literal": not_found_id_literal,
        "sample_json_payload": _java_escaped_json(create_payload),
        "updated_json_payload": _java_escaped_json(update_payload),
        "first_editable_string_field": first_editable_string_field,
        "first_editable_updated_value": first_editable_updated_value,
    }


def render_template_if_available(
    template_path: str | None,
    context: dict[str, Any],
) -> str | None:
    """Render a template path if it exists on the filesystem, otherwise return None."""
    if not template_path:
        return None
    try:
        env = get_jinja_env()
        tmpl = env.get_template(template_path)
        return tmpl.render(**context)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Error rendering template {template_path}: {e}")
        return None
