"""Compatibility re-export: the generation pipeline lives with the generator agent."""

from agents.generator.pipeline import (
    GenerationPipeline,
    _extension_to_dependency_xml,
    _resolve_bom_version,
)

__all__ = ["GenerationPipeline", "_extension_to_dependency_xml", "_resolve_bom_version"]
