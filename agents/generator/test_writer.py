"""
Gen-3 Test Writer Modeler Service.

Orchestrates framework-compliant automated unit and integration test class generation
for previously modeled Resource and Repository classes.
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
from agents.generator.prompt import build_test_prompt
from agents.generator.template_engine import (
    prepare_template_context,
    render_template_if_available,
)
from contracts.models import FileContent, FrameworkProfile, GenerationRequest

_unwrap_markdown = unwrap_markdown
_resolve_generation = resolve_generation


class TestGenerator:
    """
    Coordinates prompt construction, LLM generation, code sanitization,
    and typed FileContent wrapping for resource and repository automated test classes.
    """

    def generate(
        self,
        request: GenerationRequest,
        profile: FrameworkProfile,
        llm_client: Any,
    ) -> list[FileContent]:
        """
        Iterates through request.blueprint["entities"], generates a Resource test class
        and a Repository test class for each entity via llm_client, resolves dynamic destination paths
        under src/test/java/..., unwraps markdown fences, and returns a list of FileContent models.
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

            # 1. Generate Resource Test
            resource_class_name = f"{entity_name}Resource"
            if package_path:
                resource_test_path = (
                    f"src/test/java/{package_path}/resource/{resource_class_name}Test.java"
                )
            else:
                resource_test_path = (
                    f"src/test/java/resource/{resource_class_name}Test.java"
                )

            resource_test_template = profile.templates.get("test") if profile.templates else None
            resource_test_rendered = render_template_if_available(resource_test_template, context)
            if resource_test_rendered:
                resource_clean = resource_test_rendered.strip() + "\n"
            else:
                resource_test_prompt = build_test_prompt(
                    profile=profile,
                    target_class_name=resource_class_name,
                    class_type="resource",
                    user_stories=user_stories,
                    package_name=package_name,
                    entity_def=entity_def,
                )
                resource_raw = _resolve_generation(llm_client, resource_test_prompt)
                resource_clean = _unwrap_markdown(resource_raw, target_class_name=f"{resource_class_name}Test")
                resource_clean = ensure_package_declaration(
                    resource_clean, f"{package_name}.resource" if package_name else "resource"
                )
                resource_clean = fix_entity_imports(resource_clean, package_name, entity_name)
            results.append(FileContent(path=resource_test_path, content=resource_clean))

            # 2. Generate Repository Test
            repo_class_name = f"{entity_name}Repository"
            if package_path:
                repo_test_path = (
                    f"src/test/java/{package_path}/repository/{repo_class_name}Test.java"
                )
            else:
                repo_test_path = (
                    f"src/test/java/repository/{repo_class_name}Test.java"
                )

            repo_test_template = profile.templates.get("repository_test") if profile.templates else None
            repo_test_rendered = render_template_if_available(repo_test_template, context)
            if repo_test_rendered:
                repo_clean = repo_test_rendered.strip() + "\n"
            else:
                repo_test_prompt = build_test_prompt(
                    profile=profile,
                    target_class_name=repo_class_name,
                    class_type="repository",
                    user_stories=user_stories,
                    package_name=package_name,
                    entity_def=entity_def,
                )
                repo_raw = _resolve_generation(llm_client, repo_test_prompt)
                repo_clean = _unwrap_markdown(repo_raw, target_class_name=f"{repo_class_name}Test")
                repo_clean = ensure_package_declaration(
                    repo_clean, f"{package_name}.repository" if package_name else "repository"
                )
                repo_clean = fix_entity_imports(repo_clean, package_name, entity_name)
            results.append(FileContent(path=repo_test_path, content=repo_clean))

        return results
