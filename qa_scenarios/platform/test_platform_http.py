from __future__ import annotations

import concurrent.futures
import contextlib
import json
import socket
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from qa_agent.service_harness import PlatformServiceHarness

REPO_ROOT = Path(__file__).resolve().parents[2]
CRUD_FIXTURE_PATH = REPO_ROOT / "qa_scenarios" / "fixtures" / "crud_h2" / "fixture.json"
SOLUTION_FIXTURE_PATH = REPO_ROOT / "qa_scenarios" / "fixtures" / "solution_h2" / "fixture.json"


def _load_crud_blueprint() -> dict[str, Any]:
    data = json.loads(CRUD_FIXTURE_PATH.read_text(encoding="utf-8"))
    return dict(data["blueprint"])


def _load_solution_request() -> dict[str, Any]:
    data = json.loads(SOLUTION_FIXTURE_PATH.read_text(encoding="utf-8"))
    return dict(data["solutionRequest"])


@pytest.fixture(scope="module")
def shared_harness(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """Harness compartido para los escenarios que no requieren topología rota ni reinicio destructivo."""
    root = tmp_path_factory.mktemp("platform_shared_harness")
    harness = PlatformServiceHarness(
        repo_root=REPO_ROOT,
        harness_root=root,
        mode="platform",
    )
    harness.start(startup_timeout_seconds=25.0)
    try:
        yield harness
    finally:
        harness.stop()


def test_p01_harness_startup_failure_rollback_and_occupied_port_handling(tmp_path: Path) -> None:
    """
    P01 (AC-04):
    - Si un puerto deseado está ocupado por un socket externo, el harness reasigna un puerto libre
      sin matar el proceso ocupante (o falla limpiamente si se fuerza `fail_on_occupied_forced_port=True`).
    - Si uno de los 5 servicios falla al arrancar, el harness retira todos los procesos propios ya iniciados.
    """
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as occupant:
        occupant.bind(("127.0.0.1", 0))
        occupant.listen(1)
        occupied_port = int(occupant.getsockname()[1])

        failing_harness = PlatformServiceHarness(
            repo_root=REPO_ROOT,
            harness_root=tmp_path / "fail_harness",
            mode="platform",
            forced_ports={"validator": occupied_port},
            fail_on_occupied_forced_port=False,
            extra_env={"QA_FORCE_STARTUP_FAIL_ROLE": "orchestrator"},
        )
        with pytest.raises(RuntimeError, match="terminó prematuramente"):
            failing_harness.start(startup_timeout_seconds=15.0)

        assert failing_harness.ports["validator"] != occupied_port
        assert len(failing_harness.processes) == 0
        assert occupant.fileno() != -1


def test_p02_authentication_gateway_and_validation_contracts(
    shared_harness: PlatformServiceHarness,
    tmp_path: Path,
) -> None:
    """
    P02 (AC-05):
    - Valida clave válida (200), clave inválida (401) y ausencia de clave en cabecera (401).
    - Valida ausencia de configuración ORCHESTRATOR_API_KEY en una instancia (503).
    - Valida rechazo del gateway de agentes (`x-api-key` inválida en servicio downstream -> 401).
    - Distingue JSON/esquema inválido (422) de blueprint semánticamente inválido (200 con outcome=ERROR / valid=False).
    """
    shared_harness.set_control({})
    orch_url = shared_harness.orchestrator_url
    val_url = shared_harness.service_url("validator")
    valid_headers = {"x-api-key": shared_harness.orchestrator_api_key}

    with httpx.Client(timeout=15.0) as client:
        # 1. Clave inválida -> 401
        resp_bad_key = client.get(f"{orch_url}/v1/runs", headers={"x-api-key": "wrong-key"})
        assert resp_bad_key.status_code == 401

        # 2. Sin cabecera -> 401
        resp_no_key = client.get(f"{orch_url}/v1/runs")
        assert resp_no_key.status_code == 401

        # 3. Clave válida -> 200
        resp_ok = client.get(f"{orch_url}/v1/runs", headers=valid_headers)
        assert resp_ok.status_code == 200

        # 4. Gateway de agentes rechaza clave inválida -> 401
        resp_gw_bad = client.post(
            f"{val_url}/v1/validate",
            headers={"x-api-key": "invalid-gateway-key"},
            json={"trace_id": "gw-1", "blueprint": _load_crud_blueprint(), "workflow_state": {}},
        )
        assert resp_gw_bad.status_code == 401

        # 5. Esquema inválido en /v1/blueprint/run -> HTTP 422
        resp_schema_422 = client.post(
            f"{orch_url}/v1/blueprint/run",
            headers=valid_headers,
            json={"not_a_blueprint": 123},
        )
        assert resp_schema_422.status_code == 422

        # 6. Blueprint semánticamente inválido (nombres de entidad duplicados DUPLICATE_ENTITY_NAME)
        # El validador devuelve HTTP 200 con validation.valid=False y el orquestador devuelve HTTP 200 con outcome="ERROR"
        semantically_invalid_bp = {
            "serviceName": "dup-entity-service",
            "packageName": "com.agentia.qa.dup",
            "entities": [
                {"name": "DuplicateOrder", "fields": [{"name": "id", "type": "Long"}]},
                {"name": "DuplicateOrder", "fields": [{"name": "id", "type": "Long"}]},
            ],
            "userStories": [],
        }
        resp_val = client.post(
            f"{val_url}/v1/validate",
            headers={"x-api-key": shared_harness.gateway_api_key},
            json={"trace_id": "sem-1", "blueprint": semantically_invalid_bp, "workflow_state": {}},
        )
        assert resp_val.status_code == 200
        val_payload = resp_val.json()
        assert val_payload["validation"]["valid"] is False
        assert len(val_payload["validation"]["diagnostics"]) >= 1

        resp_orch_sem = client.post(
            f"{orch_url}/v1/blueprint/run",
            headers=valid_headers,
            json={
                "workspace_dir": "sem-invalid-service",
                "blueprint": semantically_invalid_bp,
                "trace_id": "trace-sem-invalid-001",
            },
        )
        assert resp_orch_sem.status_code == 200
        orch_sem_body = resp_orch_sem.json()
        assert orch_sem_body["outcome"] == "ERROR"
        assert orch_sem_body["validation"]["valid"] is False

    # 7. Ausencia de configuración ORCHESTRATOR_API_KEY -> 503
    shared_harness.restart_orchestrator(role_extra_env={"ORCHESTRATOR_API_KEY": ""})
    try:
        with httpx.Client(timeout=10.0) as client:
            resp_unconfigured = client.get(f"{orch_url}/v1/runs", headers=valid_headers)
            assert resp_unconfigured.status_code == 503
    finally:
        shared_harness.restart_orchestrator()


def test_p03_async_execution_running_barrier_and_orchestrator_restart_persistence(
    shared_harness: PlatformServiceHarness,
    tmp_path: Path,
) -> None:
    """
    P03 (AC-06, AC-08):
    - `POST /v1/blueprint/run?mode=async` devuelve HTTP 202 y `trace_id`.
    - Usando un archivo de sincronización en la frontera del verificador, se observa determinísticamente `RUNNING`.
    - Al liberar la sincronización, alcanza `SUCCESS` y coincide entre `/v1/blueprint/status/{trace_id}`, `/v1/runs` y `/v1/runs/{trace_id}`.
    - Consulta de `trace_id` inexistente devuelve 404.
    - Tras reiniciar el proceso del orquestador, la ejecución previa se recupera desde SQLite y estado en disco.
    """
    hold_file = tmp_path / "verifier_hold.lock"
    hold_file.write_text("hold", encoding="utf-8")
    shared_harness.set_control({"hold_signal_file": str(hold_file), "hold_max_seconds": 10.0})

    orch_url = shared_harness.orchestrator_url
    headers = {"x-api-key": shared_harness.orchestrator_api_key}
    bp = _load_crud_blueprint()
    trace_id = "trace-async-p03-001"

    with httpx.Client(timeout=20.0) as client:
        resp_404 = client.get(f"{orch_url}/v1/blueprint/status/non-existent-trace-999", headers=headers)
        assert resp_404.status_code == 404

        resp_202 = client.post(
            f"{orch_url}/v1/blueprint/run?mode=async",
            headers=headers,
            json={
                "workspace_dir": "invoice-service",
                "blueprint": bp,
                "trace_id": trace_id,
            },
        )
        assert resp_202.status_code == 202
        body_202 = resp_202.json()
        assert body_202["trace_id"] == trace_id
        assert body_202["status"] == "RUNNING"

        status_running = client.get(f"{orch_url}/v1/blueprint/status/{trace_id}", headers=headers)
        assert status_running.status_code == 200
        assert status_running.json()["status"] == "RUNNING"

        hold_file.unlink(missing_ok=True)
        terminal_body: dict[str, Any] = {}
        deadline = time.time() + 15.0
        while time.time() < deadline:
            r = client.get(f"{orch_url}/v1/blueprint/status/{trace_id}", headers=headers)
            assert r.status_code == 200
            terminal_body = r.json()
            if terminal_body["status"] != "RUNNING":
                break
            time.sleep(0.08)

        assert terminal_body.get("status") == "SUCCESS"
        assert terminal_body.get("trace_id") == trace_id
        state_obj = terminal_body.get("state") or {}
        gen_files = state_obj.get("generated_files") or terminal_body.get("generated_files") or []
        assert len(gen_files) >= 5

        runs_payload = client.get(f"{orch_url}/v1/runs", headers=headers).json()
        runs_list = runs_payload if isinstance(runs_payload, list) else runs_payload.get("runs", [])
        matching = [item for item in runs_list if item["trace_id"] == trace_id]
        assert len(matching) == 1
        assert matching[0]["status"] == "SUCCESS"

        run_detail = client.get(f"{orch_url}/v1/runs/{trace_id}", headers=headers).json()
        assert run_detail["status"] == "SUCCESS"
        assert run_detail["trace_id"] == trace_id

    shared_harness.set_control({})
    shared_harness.restart_orchestrator()

    with httpx.Client(timeout=15.0) as client:
        after_status = client.get(f"{orch_url}/v1/blueprint/status/{trace_id}", headers=headers)
        assert after_status.status_code == 200
        assert after_status.json()["status"] == "SUCCESS"

        after_detail = client.get(f"{orch_url}/v1/runs/{trace_id}", headers=headers)
        assert after_detail.status_code == 200
        assert after_detail.json()["status"] == "SUCCESS"


def test_p03_solution_generated_sqlite_persistence_across_restart(
    shared_harness: PlatformServiceHarness,
) -> None:
    """
    P03 / AC-08:
    - Cuando `/v1/solution/run` se ejecuta sin verificación Maven (`SOLUTION_VERIFY_ENABLED=0`),
      produce estado `GENERATED`.
    - Al reiniciar el orquestador, la consulta de `/v1/runs/{trace_id}` debe conservar `status == 'GENERATED'`
      sin degradarse a `RUNNING` por errores silenciados en SQLite.
    """
    orch_url = shared_harness.orchestrator_url
    headers = {"x-api-key": shared_harness.orchestrator_api_key}
    shared_harness.restart_orchestrator(role_extra_env={"SOLUTION_VERIFY_ENABLED": "0"})
    try:
        sol_req = _load_solution_request()
        sol_trace = "trace-sol-generated-p03"
        sol_req["trace_id"] = sol_trace

        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{orch_url}/v1/solution/run", headers=headers, json=sol_req)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "GENERATED"
            assert data["outcome"] == "GENERATED"
            assert len(data["services"]) == 2

        shared_harness.restart_orchestrator(role_extra_env={"SOLUTION_VERIFY_ENABLED": "0"})
        with httpx.Client(timeout=15.0) as client:
            persisted = client.get(f"{orch_url}/v1/runs/{sol_trace}", headers=headers)
            assert persisted.status_code == 200
            persisted_body = persisted.json()
            assert persisted_body["status"] == "GENERATED", (
                f"Defecto real de persistencia en producto (AC-08): `/v1/solution/run` devolvió 'GENERATED', "
                f"pero tras reiniciar el orquestador `/v1/runs/{sol_trace}` reporta status={persisted_body['status']!r} "
                f"porque `app/orchestrator/db/repository.py` rechaza 'GENERATED' en su CHECK constraint."
            )
    finally:
        shared_harness.restart_orchestrator()


def test_p04_graph_step_order_and_surgical_repair_outcomes(
    shared_harness: PlatformServiceHarness,
) -> None:
    """
    P04 (AC-07, RF-305):
    - Verifica el orden de pasos HTTP: validator -> generator -> verifier -> repair -> verifier.
    - Caso 1: Parche válido aplicado por `ScopedRepairService` corrige el archivo y alcanza `SUCCESS`.
    - Caso 2: Parche rechazado por guards G1-G8 (intenta añadir importación prohibida) termina en `NO_FIX`.
    - Caso 3: Agotamiento del límite `MAX_REPAIR_ATTEMPTS=3` termina en `NO_FIX`.
    - Cero conexiones externas y cero llamadas LLM no declaradas.
    """
    orch_url = shared_harness.orchestrator_url
    headers = {"x-api-key": shared_harness.orchestrator_api_key}
    bp = _load_crud_blueprint()
    target_rel = "src/main/java/com/agentia/qa/invoice/resource/InvoiceResource.java"

    shared_harness.clear_telemetry()
    shared_harness.set_control({})
    with httpx.Client(timeout=20.0) as client:
        baseline_resp = client.post(
            f"{orch_url}/v1/blueprint/run",
            headers=headers,
            json={
                "workspace_dir": "invoice-service",
                "blueprint": bp,
                "trace_id": "trace-p04-baseline",
            },
        )
        assert baseline_resp.status_code == 200
        baseline_body = baseline_resp.json()
        gen_list = baseline_body.get("generated_files") or []
        gen_files = {f["path"]: f["content"] for f in gen_list}
        orig_resource_code = gen_files[target_rel]

    patched_resource_code = orig_resource_code.replace(
        "public class InvoiceResource {",
        "public class InvoiceResource {\n    // QA_REPAIRED_MARKER",
        1,
    )
    shared_harness.clear_telemetry()
    shared_harness.set_control(
        {
            "verifier_require_file_substring": {target_rel: "// QA_REPAIRED_MARKER"},
            "verifier_issue_line": 20,
            "repair_llm_responses": [patched_resource_code],
        }
    )
    with httpx.Client(timeout=25.0) as client:
        rep_ok = client.post(
            f"{orch_url}/v1/blueprint/run",
            headers=headers,
            json={
                "workspace_dir": "invoice-service",
                "blueprint": bp,
                "trace_id": "trace-p04-repair-applied",
            },
        )
        assert rep_ok.status_code == 200
        rep_ok_body = rep_ok.json()
        assert rep_ok_body["outcome"] == "SUCCESS"
        assert rep_ok_body["attempts"] == 1

    events = shared_harness.read_telemetry()
    http_services = [
        e["service"]
        for e in events
        if e.get("event") == "http_request" and e.get("service") != "orchestrator"
    ]
    assert http_services == ["validator", "generator", "verifier", "repair", "verifier"]
    assert not [
        e for e in events if e.get("event") in ("blocked_external_connection", "unexpected_llm_call")
    ]

    forbidden_patch = (
        "import org.springframework.beans.factory.annotation.Autowired;\n" + orig_resource_code
    )
    shared_harness.clear_telemetry()
    shared_harness.set_control(
        {
            "verifier_require_file_substring": {target_rel: "// NEVER_PRESENT_MARKER"},
            "verifier_issue_line": 20,
            "repair_llm_responses": [forbidden_patch, orig_resource_code, orig_resource_code],
        }
    )
    with httpx.Client(timeout=25.0) as client:
        rep_guard_fail = client.post(
            f"{orch_url}/v1/blueprint/run",
            headers=headers,
            json={
                "workspace_dir": "invoice-service",
                "blueprint": bp,
                "trace_id": "trace-p04-guard-rejected",
            },
        )
        assert rep_guard_fail.status_code == 200
        guard_body = rep_guard_fail.json()
        assert guard_body["outcome"] == "NO_FIX"
        assert guard_body["attempts"] <= 3

    p1 = orig_resource_code.replace(
        "public class InvoiceResource {", "public class InvoiceResource {\n    // ATTEMPT_1", 1
    )
    p2 = orig_resource_code.replace(
        "public class InvoiceResource {", "public class InvoiceResource {\n    // ATTEMPT_2", 1
    )
    p3 = orig_resource_code.replace(
        "public class InvoiceResource {", "public class InvoiceResource {\n    // ATTEMPT_3", 1
    )
    shared_harness.clear_telemetry()
    shared_harness.set_control(
        {
            "verifier_require_file_substring": {target_rel: "// MARKER_THAT_NEVER_APPEARS"},
            "verifier_issue_line": 20,
            "repair_llm_responses": [p1, p2, p3],
        }
    )
    with httpx.Client(timeout=25.0) as client:
        rep_exhausted = client.post(
            f"{orch_url}/v1/blueprint/run",
            headers=headers,
            json={
                "workspace_dir": "invoice-service",
                "blueprint": bp,
                "trace_id": "trace-p04-budget-exhausted",
            },
        )
        assert rep_exhausted.status_code == 200
        exhausted_body = rep_exhausted.json()
        assert exhausted_body["outcome"] == "NO_FIX"
        assert exhausted_body["attempts"] == 3


def test_p04_downstream_service_5xx_malformed_json_timeout_and_crash(
    shared_harness: PlatformServiceHarness,
) -> None:
    """
    P04 (AC-07):
    - Provoca en servicios downstream respuesta 5xx (`http_503`), JSON mal formado (`malformed_json`),
      timeout (`timeout`) y caída abrupta (`crash`).
    - Comprueba que el orquestador captura el fallo sin colgarse, devuelve 502 en modo síncrono
      y persiste estado terminal `ERROR` en `/v1/runs/{trace_id}`.
    """
    orch_url = shared_harness.orchestrator_url
    headers = {"x-api-key": shared_harness.orchestrator_api_key}
    bp = _load_crud_blueprint()

    try:
        shared_harness.set_control({"service_faults": {"generator": "http_503"}})
        with httpx.Client(timeout=15.0) as client:
            r_503 = client.post(
                f"{orch_url}/v1/blueprint/run",
                headers=headers,
                json={
                    "workspace_dir": "invoice-service",
                    "blueprint": bp,
                    "trace_id": "trace-p04-gen-503",
                },
            )
            assert r_503.status_code == 502
            st_503 = client.get(f"{orch_url}/v1/runs/trace-p04-gen-503", headers=headers)
            assert st_503.status_code == 200
            assert st_503.json()["status"] == "ERROR"

        shared_harness.set_control({"service_faults": {"verifier": "malformed_json"}})
        with httpx.Client(timeout=15.0) as client:
            r_bad_json = client.post(
                f"{orch_url}/v1/blueprint/run",
                headers=headers,
                json={
                    "workspace_dir": "invoice-service",
                    "blueprint": bp,
                    "trace_id": "trace-p04-ver-badjson",
                },
            )
            assert r_bad_json.status_code == 502
            st_bad_json = client.get(f"{orch_url}/v1/runs/trace-p04-ver-badjson", headers=headers)
            assert st_bad_json.status_code == 200
            assert st_bad_json.json()["status"] == "ERROR"

        shared_harness.restart_orchestrator(role_extra_env={"AGENT_CLIENT_TIMEOUT_SECONDS": "0.5"})
        shared_harness.set_control(
            {"service_faults": {"validator": {"type": "timeout", "sleep_seconds": 1.2}}}
        )
        with httpx.Client(timeout=15.0) as client:
            r_timeout = client.post(
                f"{orch_url}/v1/blueprint/run",
                headers=headers,
                json={
                    "workspace_dir": "invoice-service",
                    "blueprint": bp,
                    "trace_id": "trace-p04-val-timeout",
                },
            )
            assert r_timeout.status_code == 502
            st_timeout = client.get(f"{orch_url}/v1/runs/trace-p04-val-timeout", headers=headers)
            assert st_timeout.status_code == 200
            assert st_timeout.json()["status"] == "ERROR"

        shared_harness.set_control({"service_faults": {"generator": "crash"}})
        with httpx.Client(timeout=15.0) as client:
            r_crash = client.post(
                f"{orch_url}/v1/blueprint/run",
                headers=headers,
                json={
                    "workspace_dir": "invoice-service",
                    "blueprint": bp,
                    "trace_id": "trace-p04-gen-crash",
                },
            )
            assert r_crash.status_code == 502
            st_crash = client.get(f"{orch_url}/v1/runs/trace-p04-gen-crash", headers=headers)
            assert st_crash.status_code == 200
            assert st_crash.json()["status"] == "ERROR"
    finally:
        shared_harness.set_control({})
        shared_harness.restart_service("generator")
        shared_harness.restart_orchestrator()


def test_p05_concurrent_runs_and_dual_independent_harnesses(
    shared_harness: PlatformServiceHarness,
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """
    P05 (AC-04, AC-17):
    - Dos ejecuciones simultáneas sobre el mismo harness mantienen `trace_id` y workspaces separados.
    - Dos instancias de `PlatformServiceHarness` ejecutándose en paralelo usan puertos, bases SQLite
      y directorios de trabajo distintos, preservan archivos centinela y no dejan procesos residuales al cerrar.
    """
    shared_harness.set_control({})
    orch_url = shared_harness.orchestrator_url
    headers = {"x-api-key": shared_harness.orchestrator_api_key}
    bp = _load_crud_blueprint()

    def _run_job(trace_id: str, url: str, api_key: str) -> dict[str, Any]:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(
                f"{url}/v1/blueprint/run",
                headers={"x-api-key": api_key},
                json={
                    "workspace_dir": f"invoice-{trace_id}",
                    "blueprint": bp,
                    "trace_id": trace_id,
                },
            )
            assert resp.status_code == 200, f"Status {resp.status_code} para {trace_id}: {resp.text}"
            return resp.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(
            _run_job, "trace-concurrent-a", orch_url, shared_harness.orchestrator_api_key
        )
        f2 = pool.submit(
            _run_job, "trace-concurrent-b", orch_url, shared_harness.orchestrator_api_key
        )
        res_a = f1.result(timeout=25)
        res_b = f2.result(timeout=25)

    assert res_a["outcome"] == "SUCCESS"
    assert res_b["outcome"] == "SUCCESS"
    assert res_a["trace_id"] == "trace-concurrent-a"
    assert res_b["trace_id"] == "trace-concurrent-b"

    sentinel_file = tmp_path / "user_sentinel.txt"
    sentinel_file.write_text("DO_NOT_MODIFY_SENTINEL", encoding="utf-8")

    second_harness = PlatformServiceHarness(
        repo_root=REPO_ROOT,
        harness_root=tmp_path_factory.mktemp("ph2"),
        mode="platform",
        orchestrator_api_key="qa-second-harness-key",
        excluded_ports=set(shared_harness.ports.values()),
    )
    second_harness.start(startup_timeout_seconds=25.0)
    try:
        assert set(shared_harness.ports.values()).isdisjoint(set(second_harness.ports.values()))
        assert shared_harness.sqlite_path != second_harness.sqlite_path

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(
                _run_job,
                "trace-dual-harness-1",
                shared_harness.orchestrator_url,
                shared_harness.orchestrator_api_key,
            )
            fb = pool.submit(
                _run_job,
                "trace-dual-harness-2",
                second_harness.orchestrator_url,
                second_harness.orchestrator_api_key,
            )
            ra = fa.result(timeout=25)
            rb = fb.result(timeout=25)

        assert ra["outcome"] == "SUCCESS"
        assert rb["outcome"] == "SUCCESS"

        with httpx.Client(timeout=10.0) as client:
            r_check = client.get(
                f"{shared_harness.orchestrator_url}/v1/runs/trace-dual-harness-2",
                headers=headers,
            )
            assert r_check.status_code == 404
    finally:
        second_harness.stop()

    assert len(second_harness.processes) == 0
    assert sentinel_file.read_text(encoding="utf-8") == "DO_NOT_MODIFY_SENTINEL"
