import asyncio
import json

import httpx
import respx

from app.orchestrator.db.repository import RunRepository
from scripts.cli import main


def test_cli_run_submits_blueprint_and_persists_result(tmp_path, capsys):
    blueprint = tmp_path / "blueprint.json"
    blueprint.write_text(json.dumps({"name": "demo", "framework": "spring", "trace_id": "trace-1"}), encoding="utf-8")
    database = tmp_path / "runs.db"

    with respx.mock(base_url="http://orchestrator.test") as router:
        route = router.post("/v1/blueprint/run").mock(
            return_value=httpx.Response(
                200,
                json={"trace_id": "trace-1", "outcome": "SUCCESS", "attempts": 1},
            )
        )
        assert main(
            ["run", str(blueprint), "--base-url", "http://orchestrator.test", "--api-key", "secret", "--database", str(database)]
        ) == 0
        assert route.called
        assert route.calls[0].request.headers["x-api-key"] == "secret"

    output = capsys.readouterr().out
    trace_id = output.split()[0]
    assert output.endswith(" SUCCESS\n")
    async def read_run():
        async with RunRepository(database) as repository:
            return await repository.get_run(trace_id)
    run = asyncio.run(read_run())
    assert run is not None
    assert (run.status, run.repair_attempts) == ("SUCCESS", 1)


def test_cli_status_reads_repository(tmp_path, capsys):
    database = tmp_path / "runs.db"
    async def seed() -> None:
        async with RunRepository(database) as repository:
            await repository.create_run("trace-1", "demo.json", status="NO_FIX", repair_attempts=3)
    asyncio.run(seed())
    assert main(["status", "trace-1", "--database", str(database)]) == 0
    assert "trace-1 demo.json NO_FIX attempts=3" in capsys.readouterr().out


def test_cli_rejects_invalid_blueprint(tmp_path, capsys):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")
    assert main(["run", str(invalid), "--database", str(tmp_path / "runs.db")]) == 1
    assert "object" in capsys.readouterr().err


def test_cli_status_returns_nonzero_for_unknown_trace(tmp_path, capsys):
    assert main(["status", "missing", "--database", str(tmp_path / "runs.db")]) == 1
    assert "run not found" in capsys.readouterr().err
