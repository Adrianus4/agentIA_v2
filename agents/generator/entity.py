"""
Gen-1 Entity Modeler Service.

Orchestrates framework-compliant ORM entity class generation from blueprint definitions.
Zero framework-specific literals are hardcoded in Python code.
"""

from __future__ import annotations

from typing import Any

from agents.generator.common import (
    ensure_entity_validation_imports,
    ensure_package_declaration,
    resolve_generation,
    unwrap_markdown,
)
from agents.generator.prompt import build_entity_prompt
from agents.generator.template_engine import (
    prepare_template_context,
    render_template_if_available,
)
from contracts.models import FileContent, FrameworkProfile, GenerationRequest

_unwrap_markdown = unwrap_markdown
_resolve_generation = resolve_generation



class EntityGenerator:
    """
    Coordinates prompt construction, LLM generation, code sanitization,
    and typed FileContent wrapping for domain entities.
    """

    def generate(
        self,
        request: GenerationRequest,
        profile: FrameworkProfile,
        llm_client: Any,
    ) -> list[FileContent]:
        """
        Iterates through request.blueprint["entities"], generates ORM entity code via llm_client,
        constructs dynamic destination paths using request.blueprint["packageName"],
        and returns a list of FileContent models.
        """
        entities = request.blueprint.get("entities", [])
        if not isinstance(entities, list) or not entities:
            return []

        package_name = str(request.blueprint.get("packageName", "")).strip().strip(".")
        package_path = package_name.replace(".", "/") if package_name else ""

        results: list[FileContent] = []

        for entity_def in entities:
            if not isinstance(entity_def, dict):
                continue

            entity_name = str(entity_def.get("name", "Entity")).strip()
            if package_path:
                file_path = f"src/main/java/{package_path}/{entity_name}.java"
            else:
                file_path = f"src/main/java/{entity_name}.java"

            # Priority: Deterministic Template rendering if defined in profile
            entity_template = profile.templates.get("entity") if profile.templates else None
            context = prepare_template_context(entity_def, package_name)
            rendered = render_template_if_available(entity_template, context)

            if rendered:
                clean_code = rendered.strip() + "\n"
            else:
                prompt = build_entity_prompt(profile, entity_def, package_name=package_name)
                raw_response = _resolve_generation(llm_client, prompt)
                clean_code = _unwrap_markdown(raw_response, target_class_name=entity_name)
                clean_code = ensure_package_declaration(clean_code, package_name)
                clean_code = ensure_entity_validation_imports(clean_code)

            results.append(FileContent(path=file_path, content=clean_code))

        return results
