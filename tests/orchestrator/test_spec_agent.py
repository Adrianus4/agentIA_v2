from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.llm.client import FakeLLMClient
from app.main import create_app
from app.orchestrator.spec_agent import SpecDraftingAgent
from contracts.models import SpecDraftRequest, SpecDraftResponse


def banking_response() -> str:
    return json.dumps(
        {
            "service_name": "payments",
            "package_name": "com.example.payments",
            "business_objective": "Process secure account-to-account payments.",
            "technical_matrix": {
                "database": "POSTGRESQL",
                "messaging": "KAFKA",
                "scope": "HIGH",
                "qps": 250,
                "transactional_model": "ACID",
            },
            "user_stories": [
                {
                    "title": "Submit a payment",
                    "given": "a valid payment instruction exists",
                    "when": "the customer submits the payment",
                    "then": "the payment is authorized and recorded",
                    "acceptance_criteria": ["Reject insufficient funds"],
                }
            ],
            "domain_models": [
                {
                    "name": "Payment",
                    "table_name": "payments",
                    "fields": [
                        {
                            "name": "amount",
                            "type": "BigDecimal",
                            "nullable": False,
                            "constraints": ["@NotNull", "@Positive"],
                        }
                    ],
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_drafts_banking_payment_directive() -> None:
    agent = SpecDraftingAgent(FakeLLMClient(banking_response()))
    response = await agent.draft(
        SpecDraftRequest(directive="Build a banking payment service with async processing")
    )

    assert response.service_name == "payments"
    assert response.technical_matrix.messaging == "KAFKA"
    assert response.user_stories[0].then.startswith("the payment")
    assert response.domain_models[0].fields[0].constraints == ["@NotNull", "@Positive"]


@pytest.mark.asyncio
async def test_invalid_first_response_is_retried_then_falls_back() -> None:
    class TwoInvalidResponses:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, prompt: str):
            del prompt
            self.calls += 1
            return type("Response", (), {"content": "not json"})()

    client = TwoInvalidResponses()
    response = await SpecDraftingAgent(client).draft(
        SpecDraftRequest(
            directive="Track customer payments",
            service_name="payments",
            package_name="com.example.payments",
        )
    )

    assert client.calls == 2
    assert response.service_name == "payments"
    assert len(response.domain_models) >= 1
    assert response.domain_models[0].name in ("PaymentTransfer", "DailyLimitAccumulator", "Payment")
    assert response.user_stories


def test_spec_draft_route_returns_validated_response(monkeypatch) -> None:
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")

    class StubAgent:
        async def draft(self, request):
            return SpecDraftingAgent(FakeLLMClient(banking_response()))._fallback(request)

    client = TestClient(create_app(spec_agent=StubAgent()))
    response = client.post(
        "/v1/spec/draft",
        headers={"x-api-key": "secret"},
        json={"directive": "Process banking payments"},
    )

    assert response.status_code == 200
    assert response.json()["service_name"] == "payment-transfers-service"
    assert len(response.json()["domain_models"]) >= 1


@pytest.mark.asyncio
async def test_wallet_directive_fallback_infers_kafka_and_wallet_models() -> None:
    class InvalidClient:
        async def generate(self, prompt: str):
            del prompt
            return type("Response", (), {"content": "not json"})()

    agent = SpecDraftingAgent(InvalidClient())
    response = await agent.draft(
        SpecDraftRequest(
            directive="Servicio de billetera móvil con transferencias inmediatas en PEN y tópico Kafka wallet-transfers"
        )
    )
    assert response.service_name == "customer-wallet-service"
    assert response.package_name == "com.tcs.wallet"
    assert response.technical_matrix.messaging == "KAFKA"
    assert len(response.domain_models) >= 2
    entity_names = [dm.name for dm in response.domain_models]
    assert "DigitalWallet" in entity_names
    assert "WalletLedgerEntry" in entity_names
    assert len(response.user_stories) >= 2


def test_spec_draft_response_to_generation_blueprint() -> None:
    agent_resp = SpecDraftResponse.model_validate(json.loads(banking_response()))
    blueprint = agent_resp.to_blueprint()

    assert blueprint["serviceName"] == "payments"
    assert blueprint["packageName"] == "com.example.payments"
    assert len(blueprint["entities"]) == 1

    entity = blueprint["entities"][0]
    assert entity["name"] == "Payment"
    assert entity["tableName"] == "payments"
    assert len(entity["fields"]) == 1
    assert entity["fields"][0]["name"] == "amount"
    assert entity["fields"][0]["type"] == "BigDecimal"
    assert entity["fields"][0]["nullable"] is False
    assert entity["fields"][0]["constraints"] == ["@NotNull", "@Positive"]

    assert len(blueprint["userStories"]) == 1
    assert blueprint["userStories"][0]["acceptanceCriteria"] == ["Reject insufficient funds"]


def test_frontend_domain_models_attributes_normalization() -> None:
    from app.orchestrator.graph import normalize_blueprint

    frontend_bp = {
        "serviceName": "OrderService",
        "packageName": "com.example.orders",
        "domainModels": [
            {
                "name": "Order",
                "tableName": "orders",
                "attributes": [
                    {"name": "id", "type": "Long", "primaryKey": True},
                    {"name": "description", "type": "String", "nullable": True},
                ],
            }
        ],
        "userStories": [
            {
                "id": "US-1",
                "title": "Create order",
                "acceptanceCriteria": ["Valid items only"],
            }
        ],
    }

    normalized = normalize_blueprint(frontend_bp)
    assert len(normalized["entities"]) == 1
    entity = normalized["entities"][0]
    assert entity["name"] == "Order"
    assert entity["tableName"] == "orders"
    assert len(entity["fields"]) == 2
    assert entity["fields"][0]["name"] == "id"
    assert entity["fields"][1]["type"] == "String"
    assert normalized["userStories"][0]["acceptanceCriteria"] == ["Valid items only"]


def test_snake_case_specification_response_normalization() -> None:
    from app.orchestrator.graph import normalize_blueprint

    snake_bp = {
        "service_name": "payment-gateway",
        "package_name": "com.corp.payment",
        "domain_models": [
            {
                "name": "Transaction",
                "table_name": "tx_log",
                "fields": [
                    {"name": "txId", "type": "String", "constraints": ["@NotBlank"]},
                ],
            }
        ],
        "user_stories": [
            {
                "title": "Process transaction",
                "given": "card is present",
                "when": "swipe happens",
                "then": "charge card",
                "acceptance_criteria": ["Auth within 200ms"],
            }
        ],
    }

    normalized = normalize_blueprint(snake_bp)
    assert normalized["serviceName"] == "payment-gateway"
    assert normalized["packageName"] == "com.corp.payment"
    assert len(normalized["entities"]) == 1
    ent = normalized["entities"][0]
    assert ent["name"] == "Transaction"
    assert ent["tableName"] == "tx_log"
    assert ent["fields"][0]["constraints"] == ["@NotBlank"]
    assert normalized["userStories"][0]["acceptanceCriteria"] == ["Auth within 200ms"]


def test_legacy_blueprint_input_preserved() -> None:
    from app.orchestrator.graph import normalize_blueprint

    legacy = {
        "serviceName": "legacy-service",
        "packageName": "com.legacy",
        "entities": [{"name": "Item", "tableName": "items", "fields": [{"name": "sku", "type": "String"}]}],
        "userStories": ["Story 1"],
    }

    normalized = normalize_blueprint(legacy)
    assert normalized["serviceName"] == "legacy-service"
    assert normalized["packageName"] == "com.legacy"
    assert normalized["entities"][0]["name"] == "Item"
    assert normalized["entities"][0]["fields"][0]["name"] == "sku"
    assert normalized["userStories"] == ["Story 1"]


def test_banking_spec_flows_through_all_generators() -> None:
    from agents.generator.entity import EntityGenerator
    from agents.generator.resource import ResourceGenerator
    from agents.generator.test_writer import TestGenerator
    from contracts.models import FrameworkProfile, GenerationRequest

    profile = FrameworkProfile(
        id="quarkus-3",
        framework="quarkus",
        framework_version="3",
        profile_revision=1,
        java_version="17",
        build_tool="maven",
        enabled=True,
        instruction_set_revision="v1",
        concepts={},
        config={},
        test_style={},
        verify_commands={},
        forbidden_imports=[],
        allowed_exceptions=[],
        pitfalls=[],
        templates={},
    )

    agent_resp = SpecDraftResponse.model_validate(json.loads(banking_response()))
    blueprint = agent_resp.to_blueprint()

    req = GenerationRequest(blueprint=blueprint)
    llm = FakeLLMClient("public class GeneratedCode {}")

    # 1. Entity generation receives populated fields rather than empty entities
    entity_gen = EntityGenerator()
    entity_files = entity_gen.generate(req, profile, llm)
    assert len(entity_files) == 1
    assert entity_files[0].path == "src/main/java/com/example/payments/Payment.java"

    # 2. Resource generation
    res_gen = ResourceGenerator()
    res_files = res_gen.generate(req, profile, llm)
    assert len(res_files) == 2  # Repository + Resource

    # 3. Test generation
    test_gen = TestGenerator()
    test_files = test_gen.generate(req, profile, llm)
    assert len(test_files) == 2  # ResourceTest + RepositoryTest


def test_normalizes_imperfect_llm_output() -> None:
    raw = json.dumps({
        "service_name": "ProductCatalogService",
        "package_name": "com.example.productcatalog",
        "business_objective": "Manage product catalog",
        "technical_matrix": {
            "stack": ["Quarkus", "Java"],
            "recommendations": {"kafka": True}
        },
        "user_stories": [
            {
                "given": "El usuario necesita acceder a productos",
                "when": "El usuario consulta GET /products",
                "then": "El servicio devuelve productos"
            }
        ],
        "domain_models": [
            {
                "name": "Product",
                "fields": [
                    {"name": "id", "type": "Long", "constraints": "@NotNull"},
                    {"name": "name", "type": "String", "constraints": "@NotBlank"},
                    {"name": "price", "type": "BigDecimal", "constraints": "@Positive"}
                ]
            }
        ]
    })
    req = SpecDraftRequest(directive="Catalogo de productos")
    parsed = SpecDraftingAgent._parse(raw, req)
    assert parsed.service_name == "productcatalogservice"
    assert parsed.technical_matrix.messaging == "KAFKA"
    assert parsed.user_stories[0].title.startswith("Historia 1")
    assert parsed.domain_models[0].table_name == "products"
    assert parsed.domain_models[0].fields[0].constraints == ["@NotNull"]
    assert parsed.domain_models[0].fields[2].constraints == ["@Positive"]

