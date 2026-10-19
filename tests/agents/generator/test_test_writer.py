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
            "mock_in_test": {
                "annotations": ["@SampleInjectMock"],
                "imports": ["com.sample.mock.SampleInjectMock"],
            },
        },
        config={},
        test_style={
            "class_annotations": ["@SampleQuarkusTest"],
            "imports": ["com.sample.test.SampleQuarkusTest", "org.junit.jupiter.api.Test"],
            "assertion_library": "junit-jupiter",
        },
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


def test_generate_single_entity_produces_resource_and_repository_tests():
    from agents.generator.test_writer import TestGenerator

    profile = _sample_profile()
    resource_test_code = (
        "package org.acme.domain.resource;\n\n"
        "public class CustomerResourceTest {\n"
        "}\n"
    )
    repo_test_code = (
        "package org.acme.domain.repository;\n\n"
        "public class CustomerRepositoryTest {\n"
        "}\n"
    )
    llm_client = SyncMockLLMClient(responses=[resource_test_code, repo_test_code])

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

    generator = TestGenerator()
    results = generator.generate(request, profile, llm_client)

    assert isinstance(results, list)
    assert len(results) == 2

    resource_test_file = results[0]
    repo_test_file = results[1]

    assert isinstance(resource_test_file, FileContent)
    assert isinstance(repo_test_file, FileContent)

    assert resource_test_file.path == "src/test/java/org/acme/domain/resource/CustomerResourceTest.java"
    assert resource_test_file.content == resource_test_code.strip()

    assert repo_test_file.path == "src/test/java/org/acme/domain/repository/CustomerRepositoryTest.java"
    assert repo_test_file.content == repo_test_code.strip()

    assert len(llm_client.calls) == 2


def test_generate_path_resolution_without_package():
    from agents.generator.test_writer import TestGenerator

    profile = _sample_profile()
    llm_client = SyncMockLLMClient(
        responses=["public class ItemResourceTest {}", "public class ItemRepositoryTest {}"]
    )

    request = GenerationRequest(
        blueprint={
            "entities": [{"name": "Item"}],
        }
    )

    generator = TestGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 2
    assert results[0].path == "src/test/java/resource/ItemResourceTest.java"
    assert results[1].path == "src/test/java/repository/ItemRepositoryTest.java"


def test_generate_unwraps_markdown_fences():
    from agents.generator.test_writer import TestGenerator

    profile = _sample_profile()
    raw_resource_test = "public class OrderResourceTest {}"
    raw_repo_test = "public class OrderRepositoryTest {}"

    llm_client = SyncMockLLMClient(
        responses=[
            f"```java\n{raw_resource_test}\n```",
            f"```\n{raw_repo_test}\n```",
        ]
    )

    request = GenerationRequest(
        blueprint={
            "packageName": "com.orders",
            "entities": [{"name": "Order"}],
        }
    )

    generator = TestGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 2
    assert "```" not in (results[0].content or "")
    assert results[0].content == raw_resource_test
    assert "```" not in (results[1].content or "")
    assert results[1].content == raw_repo_test


def test_generate_multiple_entities_batch():
    from agents.generator.test_writer import TestGenerator

    profile = _sample_profile()
    generator = TestGenerator()

    llm_client = MagicMock()
    llm_client.generate.side_effect = [
        "public class OrderResourceTest {}",
        "public class OrderRepositoryTest {}",
        "public class CustomerResourceTest {}",
        "public class CustomerRepositoryTest {}",
        "public class ProductResourceTest {}",
        "public class ProductRepositoryTest {}",
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
    assert results[0].path == "src/test/java/org/acme/shop/resource/OrderResourceTest.java"
    assert results[1].path == "src/test/java/org/acme/shop/repository/OrderRepositoryTest.java"
    assert results[2].path == "src/test/java/org/acme/shop/resource/CustomerResourceTest.java"
    assert results[3].path == "src/test/java/org/acme/shop/repository/CustomerRepositoryTest.java"
    assert results[4].path == "src/test/java/org/acme/shop/resource/ProductResourceTest.java"
    assert results[5].path == "src/test/java/org/acme/shop/repository/ProductRepositoryTest.java"
    assert llm_client.generate.call_count == 6


def test_generate_handles_llm_response_model():
    from agents.generator.test_writer import TestGenerator

    profile = _sample_profile()
    res_resp = LLMResponse(content="public class UserResourceTest {}", prompt_tokens=15, completion_tokens=25)
    repo_resp = LLMResponse(content="public class UserRepoTest {}", prompt_tokens=10, completion_tokens=20)
    llm_client = SyncMockLLMClient(responses=[res_resp, repo_resp])

    request = GenerationRequest(
        blueprint={
            "packageName": "com.app",
            "entities": [{"name": "User"}],
        }
    )

    generator = TestGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 2
    assert results[0].content == "public class UserResourceTest {}"
    assert results[1].content == "public class UserRepoTest {}"


def test_generate_handles_async_llm_client():
    from agents.generator.test_writer import TestGenerator

    profile = _sample_profile()
    llm_client = AsyncMockLLMClient(
        responses=[
            "public class AsyncResourceTest {}",
            "public class AsyncRepositoryTest {}",
        ]
    )

    request = GenerationRequest(
        blueprint={
            "packageName": "com.async",
            "entities": [{"name": "AsyncEntity"}],
        }
    )

    generator = TestGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 2
    assert results[0].content == "public class AsyncResourceTest {}"
    assert results[0].path == "src/test/java/com/async/resource/AsyncEntityResourceTest.java"
    assert results[1].content == "public class AsyncRepositoryTest {}"
    assert results[1].path == "src/test/java/com/async/repository/AsyncEntityRepositoryTest.java"


def test_generate_empty_entities():
    from agents.generator.test_writer import TestGenerator

    profile = _sample_profile()
    llm_client = SyncMockLLMClient(responses="")

    request = GenerationRequest(
        blueprint={"packageName": "com.empty", "entities": []}
    )

    generator = TestGenerator()
    results = generator.generate(request, profile, llm_client)
    assert results == []


def test_generate_no_hardcoded_framework_literals():
    """Verify Constitution Rule 8: zero framework literals in test_writer.py source code."""
    import agents.generator.test_writer as test_writer_module

    source = inspect.getsource(test_writer_module)

    forbidden_literals = [
        "@QuarkusTest",
        "@SpringBootTest",
        "@InjectMock",
        "@MockBean",
        "@Test",
        "io.quarkus.test",
        "org.springframework.boot.test",
        "org.junit",
        "@Path",
        "@GET",
        "@Transactional",
    ]

    for literal in forbidden_literals:
        assert (
            literal not in source
        ), f"Constitution violation: '{literal}' is hardcoded in agents/generator/test_writer.py"


def test_fix_entity_imports_sanitizes_static_assertions_and_entity():
    from agents.generator.common import fix_entity_imports

    raw_test_code = (
        "package com.example.repository;\n\n"
        "import io.quarkus.test.junit.QuarkusTest;\n"
        "import org.junit.jupiter.api.Test;\n"
        "import org.junit.jupiter.api.Assertions.*;\n\n"
        "@QuarkusTest\n"
        "public class TransaccionRepositoryTest {\n"
        "    public void testMethod() {\n"
        "        Transaccion t = new Transaccion();\n"
        "        assertTrue(true);\n"
        "    }\n"
        "}\n"
    )

    cleaned = fix_entity_imports(raw_test_code, "com.example", "Transaccion")
    assert "import static org.junit.jupiter.api.Assertions.*;" in cleaned
    assert "import com.example.Transaccion;" in cleaned


def test_generate_tests_uses_deterministic_templates():
    from agents.generator.test_writer import TestGenerator
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

    generator = TestGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 2
    res_test = results[0]
    repo_test = results[1]

    assert res_test.path == "src/test/java/com/example/escrow/resource/ContratoEscrowResourceTest.java"
    assert "public class ContratoEscrowResourceTest" in (res_test.content or "")
    assert ".get(\"/api/contratoescrow\")" in (res_test.content or "")

    assert repo_test.path == "src/test/java/com/example/escrow/repository/ContratoEscrowRepositoryTest.java"
    assert "public class ContratoEscrowRepositoryTest" in (repo_test.content or "")
    assert "repository.findByIdOptional(entity.getId()).isPresent()" in (repo_test.content or "")
    assert "repository.deleteById(id)" in (repo_test.content or "")
    # LLM was not called
    assert len(llm_client.calls) == 0
