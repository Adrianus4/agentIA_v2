from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contracts.models import FrameworkProfile, ScaffoldConfig


def _has_validation_constraints(entities: Any) -> bool:
    if not isinstance(entities, list):
        return False
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        fields = ent.get("fields") or ent.get("attributes") or []
        if not isinstance(fields, list):
            continue
        for fld in fields:
            if not isinstance(fld, dict):
                continue
            if fld.get("nullable") is False or fld.get("validationRules") or fld.get("constraints"):
                return True
    return False


def derive_extensions(
    blueprint: Mapping[str, Any], profile: FrameworkProfile | ScaffoldConfig
) -> list[str]:
    config = profile.scaffold if isinstance(profile, FrameworkProfile) else profile
    if config is None:
        raise ValueError("profile does not define scaffold configuration")

    features: set[str] = set()
    entities = blueprint.get("entities") or blueprint.get("domainModels") or []
    if entities:
        features.add("persistence")
        if "validation" in config.extension_map or _has_validation_constraints(entities):
            features.add("validation")

    params = blueprint.get("parameters")
    params_map = params if isinstance(params, Mapping) else {}

    raw_db = (
        blueprint.get("database")
        or blueprint.get("databaseType")
        or blueprint.get("databaseEngine")
        or params_map.get("database")
        or params_map.get("databaseEngine")
    )
    if raw_db:
        db_norm = str(raw_db).strip().lower()
        if db_norm != "none":
            if "postgres" in db_norm:
                features.add("postgresql")
            elif "mysql" in db_norm:
                features.add("mysql")
            elif "h2" in db_norm:
                features.add("h2")
            else:
                features.add(db_norm)
    elif entities and "postgresql" in config.extension_map:
        features.add("postgresql")

    raw_messaging = blueprint.get("messaging") or params_map.get("messaging")
    events = blueprint.get("events")
    if (raw_messaging and "kafka" in str(raw_messaging).lower()) or (
        isinstance(events, list) and len(events) > 0
    ):
        if "kafka" in config.extension_map:
            features.add("kafka")

    # Observability extensions (health, metrics, tracing)
    obs = blueprint.get("observability")
    if isinstance(obs, Mapping) and obs.get("enabled", True):
        if obs.get("health", True) and "health" in config.extension_map:
            features.add("health")
        if obs.get("metrics") and "metrics" in config.extension_map:
            features.add("metrics")
        if obs.get("tracing") and "otel" in config.extension_map:
            features.add("otel")

    # Security extensions (JWT / OIDC)
    sec = blueprint.get("security")
    if isinstance(sec, Mapping) and sec.get("enabled", True):
        sec_mode = str(sec.get("mode", "NONE")).upper()
        if sec_mode == "JWT" and "security_jwt" in config.extension_map:
            features.add("security_jwt")
        elif sec_mode == "OIDC" and "security_oidc" in config.extension_map:
            features.add("security_oidc")

    if blueprint.get("validation") or blueprint.get("validations"):
        features.add("validation")
    if blueprint.get("rest", True):
        features.add("rest")

    selected: set[str] = set(config.base_extensions)
    for feature in sorted(features):
        if feature not in config.extension_map:
            raise ValueError(f"unsupported extension feature: {feature}")
        selected.update(config.extension_map.get(feature, []))
    unsupported = sorted(selected.difference(config.allowed_extensions))
    if unsupported:
        raise ValueError(f"unsupported extensions: {', '.join(unsupported)}")
    return sorted(selected)
