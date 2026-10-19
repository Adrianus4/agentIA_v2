import json
from pathlib import Path

from app.orchestrator.solution_generation import SolutionGenerationPipeline
from contracts.models import (
    DomainModel,
    FieldSpec,
    FileContent,
    LLMConfiguration,
    TechnicalMatrix,
    UserStory,
)
from contracts.solution_models import (
    ApiEndpointSpec,
    DeploymentSpec,
    EventSpec,
    MicroserviceSpec,
    ObservabilitySpec,
    SecuritySpec,
    SolutionBlueprint,
    SolutionGenerationRequest,
)


def _service(name: str, package_name: str, messaging: str = "NONE") -> MicroserviceSpec:
    return MicroserviceSpec(
        service_name=name,
        package_name=package_name,
        technical_matrix=TechnicalMatrix(database="POSTGRESQL", messaging=messaging, scope="MEDIUM", qps=100, transactional_model="ACID"),
        user_stories=[
            UserStory(
                title=f"Manage {name}",
                given="A valid request",
                when="The endpoint is called",
                then="The resource is processed",
                acceptance_criteria=["Trace ID propagated"],
            )
        ],
        domain_models=[
            DomainModel(
                name="Order",
                table_name="orders",
                fields=[
                    FieldSpec(name="id", type="Long", nullable=False, constraints=[]),
                    FieldSpec(name="status", type="String", nullable=False, constraints=["@NotBlank"]),
                ],
            )
        ],
        api_endpoints=[ApiEndpointSpec(name="listOrders", method="GET", path="/api/orders")],
        events=[EventSpec(name="OrderCreated", topic="orders.created", direction="BIDIRECTIONAL")],
        workspace_dir=str(Path("/tmp") / name),
    )


class FakeGenerationPipeline:
    def __call__(self, request):
        service_name = request.blueprint["serviceName"]
        package_name = request.blueprint["packageName"]
        return [
            FileContent(
                path="pom.xml",
                content=f"<artifactId>{service_name}</artifactId>",
            ),
            FileContent(
                path=f"src/main/java/{package_name.replace('.', '/')}/App.java",
                content="public class App {}",
            ),
        ]


def test_solution_generation_pipeline_builds_multi_service_solution_from_catalog_shape():
    solution = SolutionBlueprint(
        name="commerce-platform",
        services=[
            _service("order-service", "com.tcs.order", messaging="KAFKA"),
            _service("inventory-service", "com.tcs.inventory", messaging="NONE"),
        ],
        deployment=DeploymentSpec(docker=True, kubernetes=True, openshift=True, namespace="agentia"),
        observability=ObservabilitySpec(enabled=True, metrics=True, tracing=True, structured_logging=True),
        security=SecuritySpec(enabled=True, mode="JWT", service_to_service_auth=True, roles=["user", "admin"]),
    )
    request = SolutionGenerationRequest(
        solution=solution,
        trace_id="trace-123",
        llm=LLMConfiguration(provider="gemini", model="gemini-2.5-flash", api_key="test-key"),
    )

    pipeline = SolutionGenerationPipeline(generation_pipeline=FakeGenerationPipeline())
    result = pipeline(request)

    assert result.solution_name == "commerce-platform"
    assert len(result.services) == 2
    assert any(item.path == "solution-manifest.json" for item in result.manifest)

    order_files = {file.path for file in result.services[0].files}
    assert "pom.xml" in order_files
    assert "Dockerfile" in order_files
    assert "k8s/deployment.yaml" in order_files
    assert "openshift/route.yaml" in order_files
    assert any(path.endswith("OrderCreated.java") for path in order_files)
    assert any(path.endswith("OrderCreatedProducer.java") for path in order_files)
    assert any(path.endswith("OrderCreatedConsumer.java") for path in order_files)
    assert any(path.endswith("OutboxEvent.java") for path in order_files)
    assert any(path.endswith("OutboxRelayService.java") for path in order_files)
    assert "src/main/resources/observability.properties" in order_files
    assert "src/main/resources/security.properties" in order_files
    assert "src/main/resources/messaging.properties" in order_files

    inventory_files = {file.path for file in result.services[1].files}
    assert "Dockerfile" in inventory_files
    assert "k8s/service.yaml" in inventory_files


def test_microservices_catalog_examples_convert_into_solution_generation_request():
    catalog_path = Path(__file__).resolve().parents[2] / "examples" / "microservices_catalog.json"
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    examples = payload["examples"][:3]

    services = []
    for item in examples:
        stories = []
        for us in item.get("userStories", []):
            scenario = (us.get("scenarios") or [{}])[0]
            stories.append(
                UserStory(
                    title=us.get("title") or "Story",
                    given=scenario.get("given") or "Given",
                    when=scenario.get("when") or "When",
                    then=scenario.get("then") or "Then",
                    acceptance_criteria=us.get("acceptanceCriteria", []),
                )
            )
        models = []
        for entity in item.get("entities", []):
            models.append(
                DomainModel(
                    name=entity["name"],
                    table_name=entity["tableName"],
                    fields=[
                        FieldSpec(
                            name=field["name"],
                            type=field["type"],
                            nullable=field.get("nullable", True),
                            constraints=field.get("validationRules", []),
                        )
                        for field in entity.get("fields", [])
                    ],
                )
            )
        services.append(
            MicroserviceSpec(
                service_name=item["serviceName"],
                package_name=item["packageName"],
                technical_matrix=TechnicalMatrix(
                    database=item["parameters"].get("database", "NONE"),
                    messaging=item["parameters"].get("messaging", "NONE"),
                    scope="MEDIUM",
                    qps=100,
                    transactional_model="ACID",
                ),
                user_stories=stories,
                domain_models=models,
                workspace_dir=item["parameters"].get("workspaceDir"),
                events=[EventSpec(name="GeneratedEvent", topic=f"{item['serviceName']}.events")]
                if item["parameters"].get("messaging") == "KAFKA"
                else [],
            )
        )

    solution = SolutionBlueprint(name="catalog-solution", services=services)
    request = SolutionGenerationRequest(solution=solution)
    pipeline = SolutionGenerationPipeline(generation_pipeline=FakeGenerationPipeline())
    result = pipeline(request)

    assert len(result.services) == 3
