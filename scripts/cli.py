from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.orchestrator.db.repository import RunRepository

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_DATABASE = "orchestrator.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentia")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="submit a blueprint")
    run_parser.add_argument("path", type=Path)
    run_parser.add_argument("--base-url", default=os.getenv("ORCHESTRATOR_URL", DEFAULT_BASE_URL))
    run_parser.add_argument("--api-key", default=os.getenv("ORCHESTRATOR_API_KEY", ""))
    run_parser.add_argument("--database", type=Path, default=Path(DEFAULT_DATABASE))

    status_parser = subparsers.add_parser("status", help="show a persisted run")
    status_parser.add_argument("trace_id")
    status_parser.add_argument("--database", type=Path, default=Path(DEFAULT_DATABASE))
    return parser


def _load_blueprint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"blueprint file not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read blueprint: {path}") from exc
    if not isinstance(value, dict):
        raise TypeError("blueprint JSON root must be an object")
    return value


async def _run(args: argparse.Namespace) -> int:
    blueprint = _load_blueprint(args.path)
    trace_id = str(blueprint.get("trace_id") or uuid4())
    blueprint_name = str(blueprint.get("name") or args.path.name)
    async with RunRepository(args.database) as repository:
        await repository.create_run(trace_id, blueprint_name)
        try:
            async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), timeout=30.0) as client:
                response = await client.post(
                    "/v1/blueprint/run",
                    json={
                        "workspace_dir": str(args.path.parent),
                        "blueprint": blueprint,
                        "trace_id": trace_id,
                    },
                    headers={"x-api-key": args.api_key},
                )
                response.raise_for_status()
                result = response.json()
            returned_trace_id = result.get("trace_id")
            if not returned_trace_id:
                raise ValueError("orchestrator response did not include trace_id")
            outcome = str(result.get("outcome") or "ERROR")
            attempts = int(result.get("attempts", 0))
            if returned_trace_id != trace_id:
                await repository.update_run(trace_id, status="ERROR")
                raise ValueError("orchestrator returned a different trace_id")
            normalized_outcome = "SUCCESS" if outcome == "PATCHED" else outcome
            await repository.update_run(
                trace_id,
                status=normalized_outcome if normalized_outcome in {"SUCCESS", "NO_FIX", "ERROR"} else "ERROR",
                repair_attempts=attempts,
            )
            print(f"{trace_id} {outcome}")
            return 0
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            await repository.update_run(trace_id, status="ERROR")
            print(f"error: {exc}", file=sys.stderr)
            return 1


async def _status(args: argparse.Namespace) -> int:
    async with RunRepository(args.database) as repository:
        run = await repository.get_run(args.trace_id)
    if run is None:
        print(f"error: run not found: {args.trace_id}", file=sys.stderr)
        return 1
    print(f"{run.trace_id} {run.blueprint_name} {run.status} attempts={run.repair_attempts}")
    return 0


async def _main(args: argparse.Namespace) -> int:
    return await _run(args) if args.command == "run" else await _status(args)


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(_main(build_parser().parse_args(argv)))
    except (OSError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
