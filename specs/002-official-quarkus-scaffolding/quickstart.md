# Quickstart: Official Quarkus Scaffolding

## Prerequisites

- Python dependencies: `uv sync --extra dev`
- Frontend dependencies: `cd frontend && npm install`
- A verified Quarkus/Maven tool command for the selected profile
- A disposable workspace under the configured workspace root

## Contract tests

```bash
uv run --extra dev pytest tests/contract/test_scaffolding_contracts.py
```

Expected: unsafe identifiers, invalid placeholders, unsupported extensions, and
invalid paths are rejected before process execution.

## Derivation tests

```bash
uv run --extra dev pytest tests/agents/scaffolder/test_extensions.py
```

Expected: identical inputs produce identical ordered extension lists, database
selection chooses the matching driver, and duplicates are removed.

## Adapter tests

```bash
uv run --extra dev pytest tests/agents/scaffolder/test_runner.py
```

Expected: command execution uses argv, output is capped, manifest evidence is
required, and output containment is enforced.

## Regression suite

```bash
uv run --extra dev pytest
cd frontend && npm test -- --run && npm run build
```

Scaffolding disabled must preserve the current v2 behavior.

## Live-tool verification gate

Before enabling the live adapter, run the selected Maven/Quarkus command with its
`--help` or equivalent installed-tool inspection and record the verified command,
produced file list, catalog combinations, and offline cache results in
`docs/spikes.md`.

## Implementation validation evidence

- Focused scaffolding tests: 8 passed.
- Full backend suite: 140 passed.
- `mypy app/`: passed.
- Changed-file Ruff checks: passed.
- Frontend Vitest suite: 24 passed.
- Frontend production build: passed.
- Live Maven verification: blocked because Maven is not installed in the current
  environment; see `docs/spikes.md`.
