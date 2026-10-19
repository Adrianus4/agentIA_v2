from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Self

import aiosqlite

VALID_STATUSES = frozenset({"RUNNING", "SUCCESS", "NO_FIX", "ERROR"})


class RunRepositoryError(Exception):
    """Base error for execution-run persistence failures."""


class RunNotFoundError(RunRepositoryError):
    """Raised when an operation references an unknown trace ID."""


@dataclass(frozen=True)
class ExecutionRun:
    trace_id: str
    blueprint_name: str
    status: str
    repair_attempts: int


class RunRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._connection: aiosqlite.Connection | None = None

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def connect(self) -> None:
        if self._connection is not None:
            return
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.database_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_runs (
                trace_id TEXT PRIMARY KEY,
                blueprint_name TEXT NOT NULL,
                status TEXT NOT NULL,
                repair_attempts INTEGER NOT NULL DEFAULT 0,
                CHECK (status IN ('RUNNING', 'SUCCESS', 'NO_FIX', 'ERROR')),
                CHECK (repair_attempts >= 0)
            )
            """
        )
        await self._connection.commit()

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def _db(self) -> aiosqlite.Connection:
        await self.connect()
        assert self._connection is not None
        return self._connection

    @staticmethod
    def _validate_fields(trace_id: str, blueprint_name: str, status: str, repair_attempts: int) -> None:
        if not trace_id.strip() or not blueprint_name.strip():
            raise ValueError("trace_id and blueprint_name must not be empty")
        if status not in VALID_STATUSES:
            raise ValueError(f"unsupported run status: {status}")
        if repair_attempts < 0:
            raise ValueError("repair_attempts must not be negative")

    @staticmethod
    def _record(row: aiosqlite.Row) -> ExecutionRun:
        return ExecutionRun(
            trace_id=row["trace_id"],
            blueprint_name=row["blueprint_name"],
            status=row["status"],
            repair_attempts=row["repair_attempts"],
        )

    async def create_run(
        self,
        trace_id: str,
        blueprint_name: str,
        *,
        status: str = "RUNNING",
        repair_attempts: int = 0,
    ) -> ExecutionRun:
        self._validate_fields(trace_id, blueprint_name, status, repair_attempts)
        db = await self._db()
        try:
            await db.execute(
                "INSERT INTO execution_runs "
                "(trace_id, blueprint_name, status, repair_attempts) VALUES (?, ?, ?, ?)",
                (trace_id, blueprint_name, status, repair_attempts),
            )
        except aiosqlite.IntegrityError as exc:
            raise RunRepositoryError(f"run already exists: {trace_id}") from exc
        await db.commit()
        return await self.get_run(trace_id)  # type: ignore[return-value]

    async def get_run(self, trace_id: str) -> ExecutionRun | None:
        db = await self._db()
        cursor = await db.execute(
            "SELECT trace_id, blueprint_name, status, repair_attempts "
            "FROM execution_runs WHERE trace_id = ?",
            (trace_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return self._record(row) if row is not None else None

    async def list_runs(self) -> list[ExecutionRun]:
        db = await self._db()
        cursor = await db.execute(
            "SELECT trace_id, blueprint_name, status, repair_attempts "
            "FROM execution_runs ORDER BY rowid"
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._record(row) for row in rows]

    async def update_run(
        self,
        trace_id: str,
        *,
        status: str | None = None,
        repair_attempts: int | None = None,
    ) -> ExecutionRun:
        current = await self.get_run(trace_id)
        if current is None:
            raise RunNotFoundError(f"run not found: {trace_id}")
        next_status = status if status is not None else current.status
        next_attempts = repair_attempts if repair_attempts is not None else current.repair_attempts
        self._validate_fields(current.trace_id, current.blueprint_name, next_status, next_attempts)
        db = await self._db()
        await db.execute(
            "UPDATE execution_runs SET status = ?, repair_attempts = ? WHERE trace_id = ?",
            (next_status, next_attempts, trace_id),
        )
        await db.commit()
        updated = await self.get_run(trace_id)
        if updated is None:
            raise RunNotFoundError(f"run not found: {trace_id}")
        return updated

    async def delete_run(self, trace_id: str) -> None:
        db = await self._db()
        cursor = await db.execute("DELETE FROM execution_runs WHERE trace_id = ?", (trace_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise RunNotFoundError(f"run not found: {trace_id}")
        await cursor.close()


ExecutionRunRepository = RunRepository
