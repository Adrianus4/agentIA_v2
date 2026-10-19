import inspect
from typing import Any
from unittest.mock import MagicMock

from app.core.llm.client import LLMResponse
from contracts.models import FileContent, FrameworkProfile, GenerationRequest


def _sample_profile() -> FrameworkProfile:
    return FrameworkProfile(
        id="quarkus-3",
        framework="quarkus",
        framework_version="3",
        profile_revision=1,
        java_version="17",
        build_tool="maven",
        enabled=True,
        instruction_set_revision="v1",
        concepts={
            "transactional": {
                "annotations": ["@SampleTransactional"],
                "imports": ["com.sample.tx.SampleTransactional"],
            },
            "rest_endpoint": {
                "annotations": ["@SamplePath", "@SampleGet", "@SamplePost"],
                "imports": ["com.sample.ws.SamplePath", "com.sample.ws.SampleGet"],
            },
        },
        config={},
        test_style={},
        verify_commands={},
        forbidden_imports=["org.forbidden.*"],
        allowed_exceptions=[],
        pitfalls=[],
        templates={},
    )


class SyncMockLLMClient:
    def __init__(self, responses: list[str | LLMResponse] | str | LLMResponse) -> None:
        if isinstance(responses, list):
            self.responses = list(responses)
        else:
            self.responses = [responses]
        self.calls: list[str] = []

    def generate(self, prompt: str, **kwargs: Any) -> str | LLMResponse:
        self.calls.append(prompt)
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


class AsyncMockLLMClient:
    def __init__(self, responses: list[str | LLMResponse] | str | LLMResponse) -> None:
        if isinstance(responses, list):
            self.responses = list(responses)
        else:
            self.responses = [responses]
        self.calls: list[str] = []

    async def generate(self, prompt: str, **kwargs: Any) -> str | LLMResponse:
        self.calls.append(prompt)
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


def test_generate_single_entity_produces_repository_and_resource():
    from agents.generator.resource import ResourceGenerator

    profile = _sample_profile()
    repo_code = (
        "package org.acme.domain.repository;\n\n"
        "public class CustomerRepository {\n"
        "}\n"
    )
    resource_code = (
        "package org.acme.domain.resource;\n\n"
        "public class CustomerResource {\n"
        "}\n"
    )
    llm_client = SyncMockLLMClient(responses=[repo_code, resource_code])

    request = GenerationRequest(
        blueprint={
            "serviceName": "CustomerService",
            "packageName": "org.acme.domain",
            "entities": [
                {
                    "name": "Customer",
                    "fields": [{"name": "id", "type": "Long"}],
                }
            ],
            "userStories": [
                {"title": "Manage customers", "description": "CRUD operations"}
            ],
        }
    )

    generator = ResourceGenerator()
    results = generator.generate(request, profile, llm_client)

    assert isinstance(results, list)
    assert len(results) == 2

    repo_file = results[0]
    resource_file = results[1]

    assert isinstance(repo_file, FileContent)
    assert isinstance(resource_file, FileContent)

    assert repo_file.path == "src/main/java/org/acme/domain/repository/CustomerRepository.java"
    assert repo_file.content == repo_code.strip()

    assert resource_file.path == "src/main/java/org/acme/domain/resource/CustomerResource.java"
    assert resource_file.content == resource_code.strip()

    assert len(llm_client.calls) == 2


def test_generate_path_resolution_without_package():
    from agents.generator.resource import ResourceGenerator

    profile = _sample_profile()
    llm_client = SyncMockLLMClient(responses=["public class ItemRepository {}", "public class ItemResource {}"])

    request = GenerationRequest(
        blueprint={
            "entities": [{"name": "Item"}],
        }
    )

    generator = ResourceGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 2
    assert results[0].path == "src/main/java/repository/ItemRepository.java"
    assert results[1].path == "src/main/java/resource/ItemResource.java"


def test_generate_unwraps_markdown_fences():
    from agents.generator.resource import ResourceGenerator

    profile = _sample_profile()
    raw_repo = "public class OrderRepository {}"
    raw_resource = "public class OrderResource {}"

    llm_client = SyncMockLLMClient(
        responses=[
            f"```java\n{raw_repo}\n```",
            f"```\n{raw_resource}\n```",
        ]
    )

    request = GenerationRequest(
        blueprint={
            "packageName": "com.orders",
            "entities": [{"name": "Order"}],
        }
    )

    generator = ResourceGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 2
    assert "```" not in (results[0].content or "")
    assert results[0].content == raw_repo
    assert "```" not in (results[1].content or "")
    assert results[1].content == raw_resource


def test_generate_multiple_entities_batch():
    from agents.generator.resource import ResourceGenerator

    profile = _sample_profile()
    generator = ResourceGenerator()

    llm_client = MagicMock()
    llm_client.generate.side_effect = [
        "public class OrderRepository {}",
        "public class OrderResource {}",
        "public class CustomerRepository {}",
        "public class CustomerResource {}",
        "public class ProductRepository {}",
        "public class ProductResource {}",
    ]

    request = GenerationRequest(
        blueprint={
            "packageName": "org.acme.shop",
            "entities": [
                {"name": "Order"},
                {"name": "Customer"},
                {"name": "Product"},
            ],
            "userStories": ["Buy products", "View cart"],
        }
    )

    results = generator.generate(request, profile, llm_client)

    assert len(results) == 6
    assert results[0].path == "src/main/java/org/acme/shop/repository/OrderRepository.java"
    assert results[1].path == "src/main/java/org/acme/shop/resource/OrderResource.java"
    assert results[2].path == "src/main/java/org/acme/shop/repository/CustomerRepository.java"
    assert results[3].path == "src/main/java/org/acme/shop/resource/CustomerResource.java"
    assert results[4].path == "src/main/java/org/acme/shop/repository/ProductRepository.java"
    assert results[5].path == "src/main/java/org/acme/shop/resource/ProductResource.java"
    assert llm_client.generate.call_count == 6


def test_generate_handles_llm_response_model():
    from agents.generator.resource import ResourceGenerator

    profile = _sample_profile()
    repo_resp = LLMResponse(content="public class UserRepo {}", prompt_tokens=10, completion_tokens=20)
    res_resp = LLMResponse(content="public class UserResource {}", prompt_tokens=15, completion_tokens=25)
    llm_client = SyncMockLLMClient(responses=[repo_resp, res_resp])

    request = GenerationRequest(
        blueprint={
            "packageName": "com.app",
            "entities": [{"name": "User"}],
        }
    )

    generator = ResourceGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 2
    assert results[0].content == "public class UserRepo {}"
    assert results[1].content == "public class UserResource {}"


def test_generate_handles_async_llm_client():
    from agents.generator.resource import ResourceGenerator

    profile = _sample_profile()
    llm_client = AsyncMockLLMClient(
        responses=[
            "public class AsyncRepository {}",
            "public class AsyncResource {}",
        ]
    )

    request = GenerationRequest(
        blueprint={
            "packageName": "com.async",
            "entities": [{"name": "AsyncEntity"}],
        }
    )

    generator = ResourceGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 2
    assert results[0].content == "public class AsyncRepository {}"
    assert results[0].path == "src/main/java/com/async/repository/AsyncEntityRepository.java"
    assert results[1].content == "public class AsyncResource {}"
    assert results[1].path == "src/main/java/com/async/resource/AsyncEntityResource.java"


def test_generate_empty_entities():
    from agents.generator.resource import ResourceGenerator

    profile = _sample_profile()
    llm_client = SyncMockLLMClient(responses="")

    request = GenerationRequest(
        blueprint={"packageName": "com.empty", "entities": []}
    )

    generator = ResourceGenerator()
    results = generator.generate(request, profile, llm_client)
    assert results == []


def test_generate_no_hardcoded_framework_literals():
    """Verify Constitution Rule 8: zero framework literals in resource.py source code."""
    import agents.generator.resource as resource_module

    source = inspect.getsource(resource_module)

    forbidden_literals = [
        "@Path",
        "@GET",
        "@POST",
        "@PUT",
        "@DELETE",
        "@Transactional",
        "@Repository",
        "@RestController",
        "@GetMapping",
        "@PostMapping",
        "jakarta.ws.rs",
        "javax.ws.rs",
        "jakarta.transaction",
        "javax.transaction",
        "org.springframework",
        "PanacheRepository",
    ]

    for literal in forbidden_literals:
        assert (
            literal not in source
        ), f"Constitution violation: '{literal}' is hardcoded in agents/generator/resource.py"


def test_generate_resource_and_repo_uses_deterministic_template():
    from agents.generator.resource import ResourceGenerator
    from agents.profiles.loader import get_profile

    profile = get_profile("quarkus", "3")
    llm_client = SyncMockLLMClient(responses=[])

    request = GenerationRequest(
        blueprint={
            "packageName": "com.example.escrow",
            "entities": [
                {
                    "name": "ContratoEscrow",
                    "tableName": "contratos_escrow",
                    "fields": [
                        {"name": "id", "type": "Long", "primaryKey": True},
                        {"name": "monto_total", "type": "BigDecimal", "nullable": False},
                        {"name": "estado", "type": "String", "nullable": False},
                    ],
                }
            ],
        }
    )

    generator = ResourceGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 2
    repo_file = results[0]
    resource_file = results[1]

    assert repo_file.path == "src/main/java/com/example/escrow/repository/ContratoEscrowRepository.java"
    assert "public class ContratoEscrowRepository" in (repo_file.content or "")
    assert "PanacheRepository<ContratoEscrow>" in (repo_file.content or "")

    assert resource_file.path == "src/main/java/com/example/escrow/resource/ContratoEscrowResource.java"
    assert "public class ContratoEscrowResource" in (resource_file.content or "")
    assert "repository.findByIdOptional(id)" in (resource_file.content or "")
    assert "existing.setMontoTotal(updated.getMontoTotal());" in (resource_file.content or "")
    # LLM was not called
    assert len(llm_client.calls) == 0
