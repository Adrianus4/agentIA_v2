"""Canonical blueprint normalization shared by the validator service and the orchestrator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contracts.models import SpecDraftResponse


def normalize_blueprint(blueprint: Mapping[str, Any] | SpecDraftResponse) -> dict[str, Any]:
    """
    Shared canonical adapter normalizing specification or frontend shapes into generation input.
    """
    if isinstance(blueprint, SpecDraftResponse):
        raw: Mapping[str, Any] = blueprint.model_dump()
    else:
        raw = dict(blueprint)

    normalized: dict[str, Any] = dict(raw)

    if "service_name" in normalized and "serviceName" not in normalized:
        normalized["serviceName"] = normalized["service_name"]
    elif "name" in normalized and "serviceName" not in normalized and isinstance(normalized["name"], str):
        normalized["serviceName"] = normalized["name"]

    if "package_name" in normalized and "packageName" not in normalized:
        normalized["packageName"] = normalized["package_name"]
    elif "packageName" not in normalized and "name" in normalized and isinstance(normalized["name"], str):
        slug = "".join(c for c in normalized["name"].lower().replace("service", "") if c.isalnum()) or "app"
        normalized["packageName"] = f"com.tcs.{slug}"

    fw_val = str(normalized.get("framework", "")).strip().lower()
    if fw_val.startswith("quarkus-"):
        normalized["framework"] = "quarkus"

    raw_entities = (
        normalized.get("entities")
        or normalized.get("domainModels")
        or normalized.get("domain_models")
    )

    if isinstance(raw_entities, list):
        canonical_entities: list[dict[str, Any]] = []
        for ent in raw_entities:
            if isinstance(ent, dict):
                e = dict(ent)
                if "table_name" in e and "tableName" not in e:
                    e["tableName"] = e["table_name"]
                elif "tableName" in e and "table_name" not in e:
                    e["table_name"] = e["tableName"]

                raw_fields = e.get("fields") or e.get("attributes")
                if isinstance(raw_fields, list):
                    e["fields"] = [dict(fld) if isinstance(fld, dict) else fld for fld in raw_fields]
                canonical_entities.append(e)
            else:
                canonical_entities.append(ent)
        normalized["entities"] = canonical_entities
    elif "entities" not in normalized:
        normalized["entities"] = []

    raw_stories = normalized.get("userStories") or normalized.get("user_stories")
    if isinstance(raw_stories, list):
        canonical_stories: list[Any] = []
        for story in raw_stories:
            if isinstance(story, dict):
                s = dict(story)
                if "acceptance_criteria" in s and "acceptanceCriteria" not in s:
                    s["acceptanceCriteria"] = s["acceptance_criteria"]
                elif "acceptanceCriteria" in s and "acceptance_criteria" not in s:
                    s["acceptance_criteria"] = s["acceptanceCriteria"]
                canonical_stories.append(s)
            else:
                canonical_stories.append(story)
        normalized["userStories"] = canonical_stories
    elif "userStories" not in normalized:
        normalized["userStories"] = []

    return normalized
