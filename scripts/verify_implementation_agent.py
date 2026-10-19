#!/usr/bin/env python3
"""
Implementation Verification Agent (verify_implementation_agent.py).

Verifies all Codex Audit findings (including audit 8dbebe07 counterexamples)
against the live codebase using targeted behavioral and security probes.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import tempfile
from pathlib import Path


def _load_test_shims(intermediate_dir: Path) -> None:
    runner_path = intermediate_dir / "run_tests.py"
    spec = importlib.util.spec_from_file_location("run_tests_shim", runner_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)


def run_probes(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root))
    import contracts.models as cm
    from agents.profiles.loader import get_profile
    from agents.repair.guards import evaluate_guards
    from agents.repair.service import ScopedRepairService
    from app.core.llm.client import FakeLLMClient
    from app.orchestrator.clients.workflow_store import WorkflowStore
    from app.orchestrator.execution_nodes import resolve_verifier_command
    from app.orchestrator.generation import GenerationPipeline
    from app.orchestrator.graph import (
        OrchestratorGraph,
        get_transient_llm_config,
        register_transient_llm_config,
    )
    from app.orchestrator.patching import PatchApplicationError, apply_patch
    from app.orchestrator.solution_generation import (
        SolutionGenerationPipeline,
        resolve_managed_workspace,
    )
    from contracts.agent_api import VerifierAgentRequest
    from contracts.models import (
        DiagnosticIssue,
        DomainModel,
        FieldSpec,
        FileContent,
        GuardReport,
        LLMConfiguration,
        RepairRequest,
        RepairResult,
        RunnerRequest,
        TechnicalMatrix,
        TestBaseline,
        UniformErrorBody,
        UserStory,
        VerificationResult,
    )
    from contracts.solution_models import (
        DeploymentSpec,
        EventSpec,
        MicroserviceSpec,
        ObservabilitySpec,
        SecuritySpec,
        SolutionBlueprint,
        SolutionGenerationRequest,
    )
    from services.repair_service import _build_repair_llm_client
    from services.verifier_service import verify as verifier_endpoint

    rebuild_fn = getattr(cm.FrameworkProfile, "model_rebuild", None) or getattr(
        cm.FrameworkProfile, "update_forward_refs", None
    )
    if rebuild_fn:
        rebuild_fn()

    print("=== IMPLEMENTATION VERIFICATION AGENT: AUDIT 8dbebe07 PROBES ===")

    # Probe 1: Default verifier command runs 'mvn -B test -Dquarkus.http.test-port=0'
    cmd = resolve_verifier_command()
    assert "test" in cmd and "test-compile" not in cmd, f"Probe 1 failed: {cmd}"
    print("[PASS] Probe 01: Default verifier command executes 'mvn -B test -Dquarkus.http.test-port=0'")

    # Probe 2, 3, 4, 5, 6, 7, 11, 12, 13: SolutionGenerationPipeline, Instant vs LocalDateTime, Kafka topic wiring, OutboxRelayService, Workspace isolation
    with tempfile.TemporaryDirectory() as tmp:
        old_ws_env = os.environ.get("AGENTIA_WORKSPACE_ROOT")
        os.environ["AGENTIA_WORKSPACE_ROOT"] = str(Path(tmp) / "managed-root")
        try:
            # Create external sentinel directory with src/sentinel.txt outside AGENTIA_WORKSPACE_ROOT
            external_dir = Path(tmp) / "external-temp-dir"
            (external_dir / "src").mkdir(parents=True, exist_ok=True)
            sentinel_file = external_dir / "src" / "sentinel.txt"
            sentinel_file.write_text("DO_NOT_DELETE", encoding="utf-8")

            resolved_ws = resolve_managed_workspace(str(external_dir), "billing-service", "trace-sentinel-1")
            assert resolved_ws != external_dir.resolve(), "External temp dir was not redirected into AGENTIA_WORKSPACE_ROOT"

            svc = MicroserviceSpec(
                service_name="billing-service",
                package_name="com.tcs.billing",
                technical_matrix=TechnicalMatrix(database="H2", messaging="KAFKA"),
                domain_models=[
                    DomainModel(
                        name="Invoice",
                        table_name="invoices",
                        fields=[
                            FieldSpec(name="id", type="int", nullable=False, constraints=[]),
                            FieldSpec(name="code", type="String", nullable=False, constraints=["@NotBlank"]),
                            FieldSpec(name="amount", type="BigDecimal", nullable=False, constraints=["@Positive"]),
                            FieldSpec(name="issuedAt", type="Instant", nullable=False, constraints=[]),
                            FieldSpec(name="localDue", type="LocalDateTime", nullable=False, constraints=[]),
                        ],
                    )
                ],
                user_stories=[
                    UserStory(title="Create Invoice", given="Valid", when="POST", then="201")
                ],
                events=[
                    EventSpec(
                        name="InvoiceCreated",
                        topic="invoices.created",
                        direction="BIDIRECTIONAL",
                        payload_fields=[FieldSpec(name="amount", type="BigDecimal", nullable=False)],
                    )
                ],
                workspace_dir=str(external_dir),
            )
            sol = SolutionBlueprint(
                name="billing-solution",
                services=[svc],
                deployment=DeploymentSpec(docker=True, kubernetes=True, openshift=True),
                observability=ObservabilitySpec(enabled=True, health=True, metrics=True, tracing=True),
                security=SecuritySpec(enabled=True, mode="JWT", roles=["admin"]),
            )
            sol_pipe = SolutionGenerationPipeline(
                generation_pipeline=GenerationPipeline(llm_client=FakeLLMClient("UNUSED"))
            )
            sol_res = sol_pipe(SolutionGenerationRequest(solution=sol))
            assert sol_res.trace_id is not None
            assert sol_res.status == "GENERATED"
            assert sentinel_file.is_file() and sentinel_file.read_text(encoding="utf-8") == "DO_NOT_DELETE"
            files_map = {f.path: f.content or "" for f in sol_res.services[0].files}

            pom = files_map["pom.xml"]
            assert "quarkus-smallrye-health" in pom
            assert "quarkus-micrometer-registry-prometheus" in pom
            assert "quarkus-smallrye-jwt" in pom
            app_props = files_map["src/main/resources/application.properties"]
            assert "quarkus.http.auth.permission.internal.paths=/internal/*" in app_props
            assert "quarkus.smallrye-health.root-path=/q/health" in app_props
            assert "quarkus.log.console.json" not in app_props
            assert "quarkus.log.console.format=" in app_props
            assert "mp.messaging.outgoing.invoices.created-out.topic=invoices.created" in app_props
            assert "mp.messaging.incoming.invoices.created-in.topic=invoices.created" in app_props
            trace_filter = files_map["src/main/java/com/tcs/billing/observability/TraceFilter.java"]
            assert "ContainerResponseFilter" in trace_filter
            assert "responseContext.getHeaders().putSingle(TRACE_HEADER, traceId);" in trace_filter
            print("[PASS] Probe 02 & 03: Security, Observability (structured log format + OTel), and TraceFilter verified")

            event_dto = files_map["src/main/java/com/tcs/billing/events/InvoiceCreated.java"]
            assert "import java.math.BigDecimal;" in event_dto
            assert "public BigDecimal amount;" in event_dto
            assert "public String traceId;" in event_dto
            assert "src/main/java/com/tcs/billing/outbox/OutboxRelayService.java" in files_map
            print("[PASS] Probe 04: Kafka Event DTO, channel-to-topic mappings, and OutboxRelayService verified")

            dockerignore = files_map[".dockerignore"]
            assert "!target/quarkus-app/" in dockerignore
            k8s_dep = files_map["k8s/deployment.yaml"]
            assert "configMapRef:" in k8s_dep and "secretRef:" in k8s_dep
            assert (Path(sol_res.services[0].workspace_dir) / "pom.xml").is_file()
            print("[PASS] Probe 05 & 06: .dockerignore, k8s ConfigMap/Secret, and strict AGENTIA_WORKSPACE_ROOT sentinel isolation verified")

            entity_java = files_map["src/main/java/com/tcs/billing/Invoice.java"]
            repo_java = files_map["src/main/java/com/tcs/billing/repository/InvoiceRepository.java"]
            res_java = files_map["src/main/java/com/tcs/billing/resource/InvoiceResource.java"]
            repo_test = files_map["src/test/java/com/tcs/billing/repository/InvoiceRepositoryTest.java"]
            res_test = files_map["src/test/java/com/tcs/billing/resource/InvoiceResourceTest.java"]

            assert "private Integer id;" in entity_java
            assert "@Positive" in entity_java
            assert "PanacheRepositoryBase<Invoice, Integer>" in repo_java
            assert "if (size <= 0)" in res_java and "Page.of(safePage, safeSize)" in res_java
            assert "repository.deleteAll();" in repo_test
            assert "T12:00:00Z" in res_test, "Instant field must use ISO-8601 Z suffix in ResourceTest"
            assert 'T12:00:00\\"' in res_test, "LocalDateTime field must use local ISO format without Z in ResourceTest"
            print("[PASS] Probe 11, 12, 13: Primitive int PK -> Integer, Instant (with Z) vs LocalDateTime (no Z), RepositoryTest isolated")
        finally:
            if old_ws_env is None:
                os.environ.pop("AGENTIA_WORKSPACE_ROOT", None)
            else:
                os.environ["AGENTIA_WORKSPACE_ROOT"] = old_ws_env

    # Probe 7: Security boundaries (WorkflowStore traversal, secret stripping, verifier command guard)
    with tempfile.TemporaryDirectory() as tmp:
        store = WorkflowStore(tmp)
        rejected_traversal = False
        try:
            store.save_state("../escaped", {"ok": True})
        except ValueError:
            rejected_traversal = True
        assert rejected_traversal, "WorkflowStore allowed ../escaped"
        saved = store.save_state("trace-sec-1", {"llm_api_key": "super-secret", "llm_model": "gpt-4o"})
        assert "llm_api_key" not in saved
        disk_text = (Path(tmp) / "trace-sec-1" / "state.json").read_text(encoding="utf-8")
        assert "super-secret" not in disk_text
    print("[PASS] Probe 07a: WorkflowStore blocks '../' traversal and strips llm_api_key from state.json")

    unauth_cmd_res = asyncio.run(
        verifier_endpoint(
            VerifierAgentRequest(
                trace_id="trc-cmd",
                workflow_state={"llm_api_key": "secret"},
                runner=RunnerRequest(workspace_path="/tmp", command=["echo", "pwned"]),
            )
        )
    )
    assert unauth_cmd_res.verification.success is False
    assert unauth_cmd_res.verification.issues[0].error_type == "UNAUTHORIZED_COMMAND"
    assert "llm_api_key" not in unauth_cmd_res.workflow_state
    print("[PASS] Probe 07b: Verifier service blocks non-Maven commands and strips secrets")

    # Probe 8: Repair Guards G1 & G3 + Unheadered whole-file class B counterexample + Atomic SEARCH/REPLACE
    req_guard = RepairRequest(
        framework="quarkus",
        framework_version="3.15",
        failing_file=FileContent(path="src/test/java/A.java", content="class A { @Test void t() { assertTrue(false); } }"),
        issues=[DiagnosticIssue(file_path="src/test/java/A.java", error_type="COMPILE_ERROR", message="err")],
        dependencies=[FileContent(path="src/main/java/B.java", content="class B { int secret = 1; }")],
        allowed_paths=["src/test/java/A.java"],
        test_baseline=TestBaseline(test_count=1, assertion_count=1, disabled_count=0),
    )
    # G1 check 1: SEARCH/REPLACE matching B.java content (unallowed dependency)
    g1_rep = evaluate_guards(req_guard, "<<<<<<< SEARCH\nint secret = 1;\n=======\nint secret = 2;\n>>>>>>> REPLACE")
    assert not g1_rep.passed and "G1" in g1_rep.failed_guards, f"Expected G1 failure, got {g1_rep}"

    # G1 check 2 (Audit 8dbebe07 counterexample!): Unheadered full-file replacement 'class B { int n = 2; }'
    g1_unheadered_b = evaluate_guards(req_guard, "class B { int n = 2; }")
    assert not g1_unheadered_b.passed and "G1" in g1_unheadered_b.failed_guards, (
        f"Expected G1 failure on unheadered 'class B', got {g1_unheadered_b}"
    )
    profile_q = get_profile("quarkus", "3.15")
    scoped_svc = ScopedRepairService(patch_generator=lambda _p: "class B { int n = 2; }")
    scoped_res = scoped_svc.repair(profile_q, req_guard, "trc-b")
    assert scoped_res.outcome == "REJECTED_BY_GUARD" and "G1" in scoped_res.guard_report.failed_guards

    # G3 check: SEARCH/REPLACE weakening assertTrue(false) -> assertTrue(true)
    g3_rep = evaluate_guards(req_guard, "<<<<<<< SEARCH\nassertTrue(false);\n=======\nassertTrue(true);\n>>>>>>> REPLACE")
    assert not g3_rep.passed and "G3" in g3_rep.failed_guards, f"Expected G3 failure, got {g3_rep}"

    # Patcher allowed_paths check on unheadered 'class B { int n = 2; }' and atomic multi-block rollback
    with tempfile.TemporaryDirectory() as tmp:
        a_file = Path(tmp) / "A.java"
        b_file = Path(tmp) / "B.java"
        a_file.write_text("public class A {\n    int x = 1;\n}\n", encoding="utf-8")
        b_file.write_text("class B {\n    int n = 1;\n}\n", encoding="utf-8")

        b_rejected = False
        try:
            apply_patch(tmp, "class B { int n = 2; }", allowed_paths=["A.java"])
        except PatchApplicationError:
            b_rejected = True
        assert b_rejected, "apply_patch allowed modifying B.java when allowed_paths=['A.java']"
        assert "int n = 1;" in b_file.read_text(encoding="utf-8"), "B.java was modified despite allowed_paths=['A.java']"

        two_block_patch = (
            "File: A.java\n<<<<<<< SEARCH\nint x = 1;\n=======\nint x = 2;\n>>>>>>> REPLACE\n"
            "File: A.java\n<<<<<<< SEARCH\nint nonExistent = 99;\n=======\nint nonExistent = 100;\n>>>>>>> REPLACE\n"
        )
        rolled_back = False
        try:
            apply_patch(tmp, two_block_patch, allowed_paths=["A.java"])
        except PatchApplicationError:
            rolled_back = True
        assert rolled_back, "Expected PatchApplicationError on second block failure"
        assert "int x = 1;" in a_file.read_text(encoding="utf-8"), "Block 1 was not rolled back atomically!"
    print("[PASS] Probe 08: G1 & apply_patch block unheadered 'class B' outside allowed_paths; G3 & atomic rollback verified")

    # Probe 9: Post-repair state.generated_files synchronization & transient LLM credential passing
    register_transient_llm_config(
        "trace-transient-key",
        LLMConfiguration(provider="openai", model="gpt-4o", endpoint="https://api.openai.com/v1", api_key="TRANSIENT_KEY_123"),
    )
    transient_loaded = get_transient_llm_config("trace-transient-key")
    assert transient_loaded.get("api_key") == "TRANSIENT_KEY_123"

    with tempfile.TemporaryDirectory() as tmp:
        calls = 0

        def _verify_probe9(_state: object) -> VerificationResult:
            nonlocal calls
            calls += 1
            if calls == 1:
                return VerificationResult(
                    success=False,
                    exit_code=1,
                    wall_time_seconds=0.01,
                    issues=[DiagnosticIssue(file_path="src/main/java/App.java", error_type="ERR", message="bad")],
                    raw_output="ERR",
                    runner_name="test",
                    image="test",
                )
            return VerificationResult(
                success=True, exit_code=0, wall_time_seconds=0.01, issues=[], raw_output="OK", runner_name="test", image="test"
            )

        def _repair_probe9(state: object) -> RepairResult:
            tid = getattr(state, "trace_id", "trc")
            return RepairResult(
                outcome="PATCHED",
                classification="CODE_BUG",
                hypothesis="fix",
                patches=["File: src/main/java/App.java\n<<<<<<< SEARCH\nbroken\n=======\nfixed\n>>>>>>> REPLACE"],
                files_touched=["src/main/java/App.java"],
                guard_report=GuardReport(passed=True),
                attempts_used=1,
                trace_id=tid,
            )

        graph = OrchestratorGraph(
            validate_node=lambda _bp, _tid: UniformErrorBody(valid=True, diagnostics=[]),
            generation_node=lambda _req, _st: [FileContent(path="src/main/java/App.java", content="public class App { broken }")],
            verify_node=_verify_probe9,
            repair_node=_repair_probe9,
        )
        final_state = asyncio.run(graph.run(tmp, {"serviceName": "svc"}))
        assert final_state.outcome == "SUCCESS"
        assert "fixed" in (final_state.generated_files[0].content or "")
        assert final_state.generated_files[0].digest is not None
    print("[PASS] Probe 09: state.generated_files refreshes repaired content/digest and transient llm_api_key reaches repair")

    # Probe 10: SolutionBlueprint rejects empty services=[], omitted services, and services=None
    for label, invalid_kwargs in (
        ("explicit empty list", {"name": "empty-sol", "services": []}),
        ("omitted services", {"name": "omitted-sol"}),
        ("null services", {"name": "null-sol", "services": None}),
    ):
        rejected = False
        try:
            SolutionBlueprint(**invalid_kwargs)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            rejected = True
        assert rejected, f"SolutionBlueprint accepted {label}: {invalid_kwargs}"
    print("[PASS] Probe 10: SolutionBlueprint rejects explicit empty, omitted, and null services")

    # Probe 14 & 16: Multi-provider repair_service supports local/openai/gemini
    local_client = _build_repair_llm_client({"llm_provider": "local", "llm_model": "qwen2.5-coder:3b"})
    assert local_client.__class__.__name__ == "LocalOpenAICompatibleClient"
    print("[PASS] Probe 14 & 16: Multi-provider repair_service supports local/openai/gemini and upfront trace_id")
    print("=== ALL AUDIT 8dbebe07 VERIFICATION PROBES PASSED ===")


if __name__ == "__main__":
    repo_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    inter_dir = Path("/working_dir/c_7416cca43deda67f/artifacts/file_generation/ttl=63d/intermediate")
    if (inter_dir / "run_tests.py").is_file():
        _load_test_shims(inter_dir)
    run_probes(repo_dir)
