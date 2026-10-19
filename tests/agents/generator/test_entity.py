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
            "orm_entity": {
                "annotations": ["@SampleEntity", "@SampleTable"],
                "imports": ["com.sample.SampleEntity", "com.sample.SampleTable"],
            }
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
    def __init__(self, response: str | LLMResponse) -> None:
        self.response = response
        self.calls: list[str] = []

    def generate(self, prompt: str, **kwargs: Any) -> str | LLMResponse:
        self.calls.append(prompt)
        return self.response


class AsyncMockLLMClient:
    def __init__(self, response: str | LLMResponse) -> None:
        self.response = response
        self.calls: list[str] = []

    async def generate(self, prompt: str, **kwargs: Any) -> str | LLMResponse:
        self.calls.append(prompt)
        return self.response


def test_generate_single_entity_raw_java_code():
    from agents.generator.entity import EntityGenerator

    profile = _sample_profile()
    java_code = (
        "package org.acme.domain;\n\n"
        "public class Customer {\n"
        "    private Long id;\n"
        "}\n"
    )
    llm_client = SyncMockLLMClient(response=java_code)

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
        }
    )

    generator = EntityGenerator()
    results = generator.generate(request, profile, llm_client)

    assert isinstance(results, list)
    assert len(results) == 1
    file_content = results[0]
    assert isinstance(file_content, FileContent)
    assert file_content.path == "src/main/java/org/acme/domain/Customer.java"
    assert file_content.content == java_code.strip()
    assert len(llm_client.calls) == 1


def test_generate_unwraps_markdown_fenced_code():
    from agents.generator.entity import EntityGenerator

    profile = _sample_profile()
    raw_java = (
        "package org.acme.domain;\n\n"
        "public class Order {\n"
        "    private Long id;\n"
        "}"
    )
    markdown_wrapped = f"```java\n{raw_java}\n```"
    llm_client = SyncMockLLMClient(response=markdown_wrapped)

    request = GenerationRequest(
        blueprint={
            "packageName": "org.acme.domain",
            "entities": [{"name": "Order"}],
        }
    )

    generator = EntityGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 1
    assert "```" not in (results[0].content or "")
    assert results[0].content == raw_java
    assert results[0].path == "src/main/java/org/acme/domain/Order.java"


def test_generate_unwraps_generic_markdown_fences():
    from agents.generator.entity import EntityGenerator

    profile = _sample_profile()
    raw_java = "public class Item {}"
    markdown_wrapped = f"```\n{raw_java}\n```"
    llm_client = SyncMockLLMClient(response=markdown_wrapped)

    request = GenerationRequest(
        blueprint={
            "packageName": "com.example",
            "entities": [{"name": "Item"}],
        }
    )

    generator = EntityGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 1
    assert results[0].content == raw_java


def test_generate_multiple_entities():
    from agents.generator.entity import EntityGenerator

    profile = _sample_profile()
    generator = EntityGenerator()

    llm_client = MagicMock()
    llm_client.generate.side_effect = [
        "public class Order {}",
        "public class Customer {}",
        "```java\npublic class Product {}\n```",
    ]

    request = GenerationRequest(
        blueprint={
            "packageName": "org.acme.shop",
            "entities": [
                {"name": "Order"},
                {"name": "Customer"},
                {"name": "Product"},
            ],
        }
    )

    results = generator.generate(request, profile, llm_client)

    assert len(results) == 3
    assert results[0].path == "src/main/java/org/acme/shop/Order.java"
    assert results[0].content == "public class Order {}"
    assert results[1].path == "src/main/java/org/acme/shop/Customer.java"
    assert results[1].content == "public class Customer {}"
    assert results[2].path == "src/main/java/org/acme/shop/Product.java"
    assert results[2].content == "public class Product {}"


def test_generate_handles_llm_response_model():
    from agents.generator.entity import EntityGenerator

    profile = _sample_profile()
    response_model = LLMResponse(content="public class User {}", prompt_tokens=10, completion_tokens=20)
    llm_client = SyncMockLLMClient(response=response_model)

    request = GenerationRequest(
        blueprint={
            "packageName": "com.app",
            "entities": [{"name": "User"}],
        }
    )

    generator = EntityGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 1
    assert results[0].content == "public class User {}"


def test_generate_handles_async_llm_client():
    from agents.generator.entity import EntityGenerator

    profile = _sample_profile()
    llm_client = AsyncMockLLMClient(response="public class AsyncEntity {}")

    request = GenerationRequest(
        blueprint={
            "packageName": "com.async",
            "entities": [{"name": "AsyncEntity"}],
        }
    )

    generator = EntityGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 1
    assert results[0].content == "public class AsyncEntity {}"
    assert results[0].path == "src/main/java/com/async/AsyncEntity.java"


def test_generate_empty_entities():
    from agents.generator.entity import EntityGenerator

    profile = _sample_profile()
    llm_client = SyncMockLLMClient(response="")

    request = GenerationRequest(
        blueprint={"packageName": "com.empty", "entities": []}
    )

    generator = EntityGenerator()
    results = generator.generate(request, profile, llm_client)
    assert results == []


def test_generate_no_hardcoded_framework_literals():
    """Verify Constitution Rule 8: zero framework literals in entity.py source code."""
    import agents.generator.entity as entity_module

    source = inspect.getsource(entity_module)

    forbidden_literals = [
        "@Entity",
        "@Table",
        "@Id",
        "@GeneratedValue",
        "jakarta.persistence",
        "javax.persistence",
        "org.springframework",
    ]

    for literal in forbidden_literals:
        assert (
            literal not in source
        ), f"Constitution violation: '{literal}' is hardcoded in agents/generator/entity.py"


def test_generate_entity_uses_deterministic_template():
    from agents.generator.entity import EntityGenerator
    from agents.profiles.loader import get_profile

    profile = get_profile("quarkus", "3")
    llm_client = SyncMockLLMClient(response="WILL NOT BE CALLED")

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

    generator = EntityGenerator()
    results = generator.generate(request, profile, llm_client)

    assert len(results) == 1
    content = results[0].content or ""
    assert "public class ContratoEscrow" in content
    assert "private BigDecimal montoTotal;" in content
    assert "public BigDecimal getMontoTotal()" in content
    assert "public void setMontoTotal(BigDecimal montoTotal)" in content
    # The LLM was not invoked because the deterministic template rendered cleanly
    assert len(llm_client.calls) == 0
