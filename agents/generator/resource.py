"""
Gen-2 Resource & Repository Modeler Service.

Orchestrates framework-compliant Repository/DAO and REST Resource/Controller class generation
from blueprint definitions and user stories.
Zero framework-specific literals are hardcoded in Python code.
"""

from __future__ import annotations

from typing import Any

from agents.generator.common import (
    ensure_package_declaration,
    fix_entity_imports,
    resolve_generation,
    unwrap_markdown,
)
from agents.generator.prompt import build_repository_prompt, build_resource_prompt
from agents.generator.template_engine import (
    prepare_template_context,
    render_template_if_available,
)
from contracts.models import FileContent, FrameworkProfile, GenerationRequest

_unwrap_markdown = unwrap_markdown
_resolve_generation = resolve_generation


class ResourceGenerator:
    """
    Coordinates prompt construction, LLM generation, code sanitization,
    and typed FileContent wrapping for repository and REST resource classes.
    """

    def generate(
        self,
        request: GenerationRequest,
        profile: FrameworkProfile,
        llm_client: Any,
    ) -> list[FileContent]:
        """
        Iterates through request.blueprint["entities"], generates both a Repository class
        and a Resource class for each entity via llm_client, resolves dynamic destination paths,
        unwraps markdown fences, and returns a list of FileContent models.
        """
        entities = request.blueprint.get("entities", [])
        if not isinstance(entities, list) or not entities:
            return []

        package_name = str(request.blueprint.get("packageName", "")).strip().strip(".")
        package_path = package_name.replace(".", "/") if package_name else ""
        user_stories = request.blueprint.get("userStories", [])
        if not isinstance(user_stories, list):
            user_stories = []

        results: list[FileContent] = []

        for entity_def in entities:
            if not isinstance(entity_def, dict):
                continue

            entity_name = str(entity_def.get("name", "Entity")).strip()

            context = prepare_template_context(entity_def, package_name)

            # 1. Generate Repository
            if package_path:
                repo_path = f"src/main/java/{package_path}/repository/{entity_name}Repository.java"
            else:
                repo_path = f"src/main/java/repository/{entity_name}Repository.java"

            repo_template = profile.templates.get("repository") if profile.templates else None
            repo_rendered = render_template_if_available(repo_template, context)
            if repo_rendered:
                repo_clean = repo_rendered.strip() + "\n"
            else:
                repo_prompt = build_repository_prompt(profile, entity_def, package_name=package_name)
                repo_raw = _resolve_generation(llm_client, repo_prompt)
                repo_clean = _unwrap_markdown(repo_raw, target_class_name=f"{entity_name}Repository")
                repo_clean = ensure_package_declaration(
                    repo_clean, f"{package_name}.repository" if package_name else "repository"
                )
                repo_clean = fix_entity_imports(repo_clean, package_name, entity_name)
            results.append(FileContent(path=repo_path, content=repo_clean))

            # 2. Generate Resource
            if package_path:
                resource_path = f"src/main/java/{package_path}/resource/{entity_name}Resource.java"
            else:
                resource_path = f"src/main/java/resource/{entity_name}Resource.java"

            resource_template = profile.templates.get("resource") if profile.templates else None
            resource_rendered = render_template_if_available(resource_template, context)
            if resource_rendered:
                resource_clean = resource_rendered.strip() + "\n"
            else:
                resource_prompt = build_resource_prompt(
                    profile, entity_def, user_stories, package_name=package_name
                )
                resource_raw = _resolve_generation(llm_client, resource_prompt)
                resource_clean = _unwrap_markdown(resource_raw, target_class_name=f"{entity_name}Resource")
                resource_clean = ensure_package_declaration(
                    resource_clean, f"{package_name}.resource" if package_name else "resource"
                )
                resource_clean = fix_entity_imports(resource_clean, package_name, entity_name)
            results.append(FileContent(path=resource_path, content=resource_clean))

        return results
