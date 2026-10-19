import json
import logging
from pathlib import Path

from agents.generator.template_engine import (
    prepare_template_context,
    render_template_if_available,
)
from app.core.llm.client import FakeLLMClient
from app.orchestrator.generation import GenerationPipeline
from app.orchestrator.pipeline import PipelineGraph
from contracts.models import (
    DiagnosticIssue,
    GenerationRequest,
    GuardReport,
    RepairResult,
    VerificationResult,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_BLUEPRINT_PATH = REPO_ROOT / "blueprints" / "demo_quarkus.json"

BLUEPRINT = {
    "serviceName": "billing",
    "packageName": "com.example",
    "framework": "quarkus",
    "version": "3",
    "entities": [{"name": "Invoice"}],
    "userStories": [],
}


class SequenceRunner:
    def __init__(self, results: list[VerificationResult]) -> None:
        self.results = iter(results)
        self.commands: list[list[str]] = []

    def run(self, request):
        self.commands.append(request.command)
        return next(self.results)


def result(success: bool) -> VerificationResult:
    return VerificationResult(
        success=success,
        exit_code=0 if success else 1,
        wall_time_seconds=0.01,
        issues=[] if success else [
            DiagnosticIssue(
                file_path="src/main/java/com/example/Invoice.java",
                error_type="COMPILE_ERROR",
                message="failed",
            )
        ],
        raw_output="BUILD SUCCESS" if success else "BUILD FAILURE",
        runner_name="fake",
        image="fake",
    )


def repair_result(trace_id: str) -> RepairResult:
    return RepairResult(
        outcome="PATCHED",
        classification="CODE_BUG",
        hypothesis="test patch",
        patches=["--- src/main.java\n+++ src/main.java\n@@ -1 +1 @@\n-old\n+new\n"],
        files_touched=["src/main.java"],
        guard_report=GuardReport(passed=True, failed_guards=[]),
        attempts_used=1,
        trace_id=trace_id,
    )


def test_happy_path_generates_and_verifies(tmp_path: Path) -> None:
    runner = SequenceRunner([result(True)])
    graph = PipelineGraph(FakeLLMClient("class Generated {}"), runner=runner)

    state = graph.run(str(tmp_path), BLUEPRINT, "trace-happy")

    assert state.outcome == "SUCCESS"
    assert state.generated_files
    assert (tmp_path / "src/main/java/com/example/Invoice.java").exists()
    assert runner.commands == [["mvn", "clean", "test"]]


def test_repair_loop_patches_and_passes_on_second_attempt(tmp_path: Path) -> None:
    runner = SequenceRunner([result(False), result(True)])
    patched: list[str] = []

    class Repair:
        def repair(self, profile, request, trace_id):
            return repair_result(trace_id)

    graph = PipelineGraph(
        FakeLLMClient("old"),
        runner=runner,
        repair_service=Repair(),
        patcher=lambda workspace, patch: patched.append(patch),
    )

    state = graph.run(str(tmp_path), BLUEPRINT, "trace-repair")

    assert state.outcome == "SUCCESS"
    assert state.attempts == 1
    assert patched


def test_budget_exhaustion_returns_no_fix(tmp_path: Path) -> None:
    runner = SequenceRunner([result(False)] * 4)

    class NoRepair:
        def repair(self, profile, request, trace_id):
            return repair_result(trace_id)

    state = PipelineGraph(
        FakeLLMClient("generated"),
        runner=runner,
        repair_service=NoRepair(),
        patcher=lambda workspace, patch: None,
    ).run(str(tmp_path), BLUEPRINT, "trace-budget")

    assert state.outcome == "NO_FIX"
    assert state.attempts == 3


def test_demo_quarkus_blueprint_end_to_end_smoke(tmp_path: Path) -> None:
    """Audit Item 10: Run blueprints/demo_quarkus.json end-to-end with zero LLM calls and zero repairs."""
    blueprint = json.loads(DEMO_BLUEPRINT_PATH.read_text(encoding="utf-8"))
    llm_client = FakeLLMClient("SHOULD_NOT_BE_CALLED")
    runner = SequenceRunner([result(True)])

    pipeline = GenerationPipeline(llm_client=llm_client)
    files = pipeline(GenerationRequest(blueprint=blueprint, trace_id="smoke-demo"))
    file_map = {f.path: f.content or "" for f in files}

    expected_paths = {
        "pom.xml",
        "src/main/resources/application.properties",
        "src/main/java/com/example/catalog/User.java",
        "src/main/java/com/example/catalog/Product.java",
        "src/main/java/com/example/catalog/repository/UserRepository.java",
        "src/main/java/com/example/catalog/repository/ProductRepository.java",
        "src/main/java/com/example/catalog/resource/UserResource.java",
        "src/main/java/com/example/catalog/resource/ProductResource.java",
        "src/test/java/com/example/catalog/resource/UserResourceTest.java",
        "src/test/java/com/example/catalog/resource/ProductResourceTest.java",
        "src/test/java/com/example/catalog/repository/UserRepositoryTest.java",
        "src/test/java/com/example/catalog/repository/ProductRepositoryTest.java",
    }
    assert expected_paths.issubset(set(file_map.keys()))

    # Audit Item 1: application.properties separates %dev, %test, %prod and includes JDBC URL, username, password
    app_props = file_map["src/main/resources/application.properties"]
    assert "%dev.quarkus.hibernate-orm.database.generation=drop-and-create" in app_props
    assert "%test.quarkus.hibernate-orm.database.generation=drop-and-create" in app_props
    assert "%prod.quarkus.hibernate-orm.database.generation=${DB_SCHEMA_GENERATION:validate}" in app_props
    assert "%prod.quarkus.datasource.jdbc.url=" in app_props
    assert "%prod.quarkus.datasource.username=" in app_props
    assert "%prod.quarkus.datasource.password=" in app_props

    # Audit Item 2: pom.xml derived from quarkus-3.15 profile and extension_map (no Kafka when not requested)
    pom_xml = file_map["pom.xml"]
    assert "<maven.compiler.release>21</maven.compiler.release>" in pom_xml
    assert "<quarkus.platform.version>3.15.1</quarkus.platform.version>" in pom_xml
    assert "<artifactId>quarkus-hibernate-orm-panache</artifactId>" in pom_xml
    assert "<artifactId>quarkus-hibernate-validator</artifactId>" in pom_xml
    assert "<artifactId>quarkus-jdbc-postgresql</artifactId>" in pom_xml
    assert "quarkus-smallrye-reactive-messaging-kafka" not in pom_xml

    # Audit Items 3, 7, 8: Resource has @Valid @NotNull, nulls ID on POST, and supports pagination
    user_resource = file_map["src/main/java/com/example/catalog/resource/UserResource.java"]
    assert "@Valid @NotNull User entity" in user_resource
    assert "@Valid @NotNull User updated" in user_resource
    assert "entity.setId(null);" in user_resource
    assert '@QueryParam("page")' in user_resource
    assert "Page.of(" in user_resource

    # Audit Item 6: ResourceTest tests full POST -> GET -> PUT -> DELETE lifecycle with valid JSON payload
    product_test = file_map["src/test/java/com/example/catalog/resource/ProductResourceTest.java"]
    assert "testCreateGetUpdateAndDeleteLifecycle" in product_test
    assert '.when().post("/api/product")' in product_test
    assert '.when().put("/api/product/" + createdId)' in product_test
    assert '.when().delete("/api/product/" + createdId)' in product_test
    assert ".statusCode(201)" in product_test
    assert ".statusCode(204)" in product_test

    # Execute through PipelineGraph / OrchestratorGraph and verify 0 repair attempts
    graph = PipelineGraph(llm_client, runner=runner)
    state = graph.run(str(tmp_path), blueprint, "smoke-trace-001")
    assert state.outcome == "SUCCESS"
    assert state.attempts == 0


def test_custom_primary_keys_uuid_and_string_compile_cleanly() -> None:
    """Audit Item 4: Verify UUID and custom String primary keys declared via entity primaryKey do not add extra id."""
    uuid_entity = {
        "name": "SessionToken",
        "tableName": "session_tokens",
        "primaryKey": "tokenId",
        "fields": [
            {"name": "tokenId", "type": "UUID", "nullable": False},
            {"name": "userAgent", "type": "String", "nullable": False},
        ],
    }
    ctx_uuid = prepare_template_context(uuid_entity, "com.example.auth")
    assert ctx_uuid["id_name"] == "tokenId"
    assert ctx_uuid["id_pascal_name"] == "TokenId"
    assert ctx_uuid["id_type"] == "UUID"
    assert ctx_uuid["id_generated"] is True
    assert len(ctx_uuid["fields"]) == 2

    entity_java = render_template_if_available("templates/quarkus/Entity.java.jinja", ctx_uuid) or ""
    repo_java = render_template_if_available("templates/quarkus/Repository.java.jinja", ctx_uuid) or ""
    res_java = render_template_if_available("templates/quarkus/Resource.java.jinja", ctx_uuid) or ""
    res_test_java = render_template_if_available("templates/quarkus/ResourceTest.java.jinja", ctx_uuid) or ""
    repo_test_java = render_template_if_available("templates/quarkus/RepositoryTest.java.jinja", ctx_uuid) or ""

    assert "@GeneratedValue(strategy = GenerationType.UUID)" in entity_java
    assert "PanacheRepositoryBase<SessionToken, UUID>" in repo_java
    assert "@PathParam(\"id\") UUID id" in res_java
    assert "entity.setTokenId(null);" in res_java
    assert "00000000-0000-0000-0000-000000000000" in res_test_java
    assert "UUID id = entity.getTokenId();" in repo_test_java

    string_entity = {
        "name": "Country",
        "tableName": "countries",
        "primaryKey": "isoCode",
        "fields": [
            {"name": "isoCode", "type": "String", "nullable": False},
            {"name": "name", "type": "String", "nullable": False},
        ],
    }
    ctx_str = prepare_template_context(string_entity, "com.example.geo")
    assert ctx_str["id_name"] == "isoCode"
    assert ctx_str["id_type"] == "String"
    assert ctx_str["id_generated"] is False
    assert len(ctx_str["fields"]) == 2

    res_str_java = render_template_if_available("templates/quarkus/Resource.java.jinja", ctx_str) or ""
    repo_str_test = render_template_if_available("templates/quarkus/RepositoryTest.java.jinja", ctx_str) or ""
    assert "setIsoCode(null)" not in res_str_java
    assert 'entity.setIsoCode("Sample");' in repo_str_test
    assert "String id = entity.getIsoCode();" in repo_str_test


def test_template_failure_logs_warning(caplog) -> None:
    """Audit Item 5: Verify render_template_if_available logs a warning when template rendering fails."""
    with caplog.at_level(logging.WARNING):
        res = render_template_if_available("templates/quarkus/NonExistentTemplate.java.jinja", {})
    assert res is None
    assert "Error rendering template" in caplog.text


def test_dockerfile_copies_all_required_runtime_directories() -> None:
    """Audit Item 9: Verify Dockerfile copies app, services, contracts, agents, profiles, and templates."""
    dockerfile_text = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    for required_copy in (
        "COPY app ./app",
        "COPY services ./services",
        "COPY contracts ./contracts",
        "COPY agents ./agents",
        "COPY profiles ./profiles",
        "COPY templates ./templates",
    ):
        assert required_copy in dockerfile_text, f"Missing '{required_copy}' in Dockerfile"


def test_codex_audit_primitive_pk_and_pagination_and_isolation() -> None:
    """Codex Findings 11, 12, 13: Primitive int PK normalizes to Integer, tests isolate state, and page 0 is bounded."""
    int_pk_entity = {
        "name": "Ticket",
        "tableName": "tickets",
        "primaryKey": "id",
        "fields": [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "code", "type": "String", "nullable": False, "unique": True},
        ],
    }
    ctx = prepare_template_context(int_pk_entity, "com.example.support")
    assert ctx["id_type"] == "Integer"
    assert ctx["id_generated"] is True

    entity_java = render_template_if_available("templates/quarkus/Entity.java.jinja", ctx) or ""
    repo_java = render_template_if_available("templates/quarkus/Repository.java.jinja", ctx) or ""
    res_java = render_template_if_available("templates/quarkus/Resource.java.jinja", ctx) or ""
    repo_test_java = render_template_if_available("templates/quarkus/RepositoryTest.java.jinja", ctx) or ""
    res_test_java = render_template_if_available("templates/quarkus/ResourceTest.java.jinja", ctx) or ""

    assert "private Integer id;" in entity_java
    assert "PanacheRepositoryBase<Ticket, Integer>" in repo_java
    assert "if (size <= 0)" in res_java and "Page.of(safePage, safeSize)" in res_java
    assert "repository.deleteAll();" in repo_test_java
    assert '"Sample_2"' in repo_test_java
    assert '.body("code", equalTo("sample_code_4"))' in res_test_java


def test_codex_audit_post_repair_refreshes_generated_files(tmp_path: Path) -> None:
    """Codex Finding 9: Repaired workspace files are reloaded into state.generated_files with SHA-256 digests."""
    runner = SequenceRunner([result(False), result(True)])

    class SurgicalRepair:
        def repair(self, profile, request, trace_id):
            return RepairResult(
                outcome="PATCHED",
                classification="CODE_BUG",
                hypothesis="fix Invoice class",
                patches=[
                    "File: src/main/java/com/example/Invoice.java\n"
                    "<<<<<<< SEARCH\n"
                    "public class Invoice {\n"
                    "=======\n"
                    "// Repaired by agent\npublic class Invoice {\n"
                    ">>>>>>> REPLACE\n"
                ],
                files_touched=["src/main/java/com/example/Invoice.java"],
                guard_report=GuardReport(passed=True, failed_guards=[]),
                attempts_used=1,
                trace_id=trace_id,
            )

    graph = PipelineGraph(
        FakeLLMClient("class Generated {}"),
        runner=runner,
        repair_service=SurgicalRepair(),
    )
    state = graph.run(str(tmp_path), BLUEPRINT, "trace-refresh")
    assert state.outcome == "SUCCESS"
    invoice_fc = next(f for f in (state.generated_files or []) if f.path.endswith("Invoice.java"))
    assert "// Repaired by agent" in (invoice_fc.content or "")
    assert invoice_fc.digest is not None
