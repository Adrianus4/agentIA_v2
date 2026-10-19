# Quickstart Validation

## Backend

```bash
uv sync --extra dev
timeout 60s uv run pytest -q -p no:langsmith
uv run ruff check .
uv run mypy app/
```

Expected: pytest exits with code 0 after the summary; all lint/type checks pass.

## Frontend

```bash
cd frontend
npm test -- --run
npm run build
```

Expected: all Vitest tests pass and the production bundle builds.

## End-to-end pipeline

Run `tests/orchestrator/test_e2e_pipeline.py` with the fake LLM and simulated verifier. Confirm happy-path success, one repair followed by `PATCHED`, and bounded `NO_FIX`.

## Manual UI check

Open the run form, choose the provider/model, enter a credential, submit a blueprint, and confirm the request uses the selected model while status output contains no credential.
