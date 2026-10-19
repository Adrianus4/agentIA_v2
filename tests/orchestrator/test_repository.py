import pytest

from app.orchestrator.db.repository import (
    RunNotFoundError,
    RunRepository,
    RunRepositoryError,
)


@pytest.mark.asyncio
async def test_repository_crud_and_state_updates(tmp_path):
    async with RunRepository(tmp_path / "runs.db") as repository:
        created = await repository.create_run("trace-1", "blueprint.json")
        assert created.status == "RUNNING"
        assert created.repair_attempts == 0

        updated = await repository.update_run("trace-1", status="SUCCESS", repair_attempts=2)
        assert updated.status == "SUCCESS"
        assert updated.repair_attempts == 2
        assert await repository.get_run("trace-1") == updated
        assert await repository.list_runs() == [updated]

        await repository.delete_run("trace-1")
        assert await repository.get_run("trace-1") is None


@pytest.mark.asyncio
async def test_repository_rejects_invalid_and_missing_operations(tmp_path):
    async with RunRepository(tmp_path / "runs.db") as repository:
        with pytest.raises(ValueError):
            await repository.create_run("", "blueprint.json")
        with pytest.raises(ValueError):
            await repository.create_run("trace-1", "blueprint.json", repair_attempts=-1)
        with pytest.raises(ValueError):
            await repository.create_run("trace-1", "blueprint.json", status="BOGUS")
        await repository.create_run("trace-1", "blueprint.json")
        with pytest.raises(RunRepositoryError):
            await repository.create_run("trace-1", "other.json")
        with pytest.raises(RunNotFoundError):
            await repository.update_run("missing", status="ERROR")
        with pytest.raises(RunNotFoundError):
            await repository.delete_run("missing")


@pytest.mark.asyncio
async def test_repository_persists_across_connections(tmp_path):
    database = tmp_path / "runs.db"
    async with RunRepository(database) as repository:
        await repository.create_run("trace-1", "blueprint.json")
        await repository.update_run("trace-1", status="NO_FIX", repair_attempts=3)
    async with RunRepository(database) as reopened:
        run = await reopened.get_run("trace-1")
        assert run is not None
        assert (run.status, run.repair_attempts) == ("NO_FIX", 3)
