# AgentIA v2: Agent Implementation & Repair Loop Audit

Date: 2026-10-12

Scope: `app/orchestrator/`, `agents/generator/`, `agents/verifier/`,
`agents/repair/`, `agents/scaffolder/`, `contracts/`, `profiles/`, and their regression suites.

## Executive assessment

AgentIA v2 now uses a consolidated, unified state-machine architecture for orchestration:

1. `OrchestratorGraph` in `app/orchestrator/graph.py` is the single canonical
   asynchronous execution engine. It governs state transitions, bounded retries
   (`MAX_ATTEMPTS = 3`), contract enforcement via typed nodes, and patch applications.
2. `PipelineGraph` in `app/orchestrator/pipeline.py` is a thin, synchronous
   compatibility facade. It delegates its entire execution cycle to
   `OrchestratorGraph`, eliminating duplicate retry loops and state drift while
   preserving backward-compatible synchronous calling conventions.
3. Hermetic verification defaults strictly to `LocalDockerRunner` (`--network none`,
   read-only `.m2` cache, workspace mounts). An explicit, non-fallback
   `LocalSubprocessRunner` provides host-mode execution for controlled environments.
4. Framework profiles now include full production configurations for Quarkus 3.15
   and Java 21, including SmallRye Kafka and Panache data layers.
5. Verification diagnostics deduplicate identical compiler and Surefire errors,
   ensuring deterministic repair prompts.
6. Generation helper functions (`unwrap_markdown`, `resolve_generation`) are centralized
   in `agents/generator/common.py` with backward-compatible private aliases across all generators.
7. Background execution state in `app/main.py` truthfully persists `RUNNING` before graph
   dispatch and deterministically records terminal outcomes (`SUCCESS`, `NO_FIX`, `ERROR`).

The test suite confirms 163 backend tests passed, mypy (41 source files) clean,
Ruff 100% clean, and frontend (40 tests + Vite build) 100% clean.

---

## 1. Current agent architecture and topology

### Component boundaries

| Component | Boundary | Execution model | Primary responsibility |
|---|---|---|---|
| `OrchestratorGraph` | `app/orchestrator/graph.py` | In-process async loop | Canonical engine: validates, generates, verifies, repairs, applies patches |
| `PipelineGraph` | `app/orchestrator/pipeline.py` | In-process sync facade | Adapts legacy synchronous calls by delegating directly to `OrchestratorGraph` |
| `GenerationPipeline` | `app/orchestrator/generation.py` | In-process callable | Sequentially invokes entity, resource, and test generators |
| `apply_patch` | `app/orchestrator/patching.py` | Filesystem transaction + subprocess | Safely stages and commits unified diffs with snapshot rollback |
| `EntityGenerator` | `agents/generator/entity.py` | In-process LLM adapter | Produces Panache entity `FileContent` objects |
| `ResourceGenerator` | `agents/generator/resource.py` | In-process LLM adapter | Produces repository and REST resource `FileContent` objects |
| `TestGenerator` | `agents/generator/test_writer.py` | In-process LLM adapter | Produces repository/resource unit & integration tests |
| `LocalDockerRunner` | `agents/verifier/runner.py` | Hermetic Docker container | Runs Maven inside an offline, non-networked container |
| `LocalSubprocessRunner` | `agents/verifier/runner.py` | Host subprocess (explicit only) | Runs Maven directly on host without silent fallback |
| `ScopedRepairService` | `agents/repair/service.py` | In-process LLM adapter + guards | Produces bounded, guard-checked unified diffs |
| `ExecutionRunRepository` | `app/orchestrator/db/repository.py` | SQLite async store | Persists execution run status (`RUNNING`, `SUCCESS`, `NO_FIX`, `ERROR`) |

The system uses in-process modular orchestration with subprocess execution boundaries for
Docker/host runners and patch operations.

### State and contracts

- `OrchestrationState`: workspace, blueprint, trace ID, attempt count, validation,
  verification, repair, generated files, outcome, and `profile: FrameworkProfile | None`.
- `PipelineState`: Compatibility dataclass populated from `OrchestrationState` after
  graph completion, preventing drift while preserving external field access.
- Typed Pydantic contracts in `contracts/models.py` strictly decouple agent phases:
  `GenerationRequest`, `FileContent`, `RunnerRequest`, `VerificationResult`,
  `DiagnosticIssue`, `RepairRequest`, `RepairResult`, `UniformErrorBody`.
- Invariant: `PATCHED` is exclusively a `RepairResult.outcome`. Terminal execution outcomes
  are strictly `RunOutcome` (`SUCCESS`, `NO_FIX`, `ERROR`).

---

## 2. Code generation pipeline audit

### Sequential flow

1. Blueprint normalization (`normalize_blueprint`) maps incoming keys (`service_name`,
   `domainModels`, `attributes`, `table_name`) into canonical entities and fields.
2. Generator invocation (`EntityGenerator` -> `ResourceGenerator` -> `TestGenerator`).
   Markdown code blocks are cleaned via `unwrap_markdown` in `agents/generator/common.py`.
3. Materialization (`_write_generated_files`): Enforces path resolution within workspace,
   blocking symlink escapes and directory traversal.

---

## 3. Verification and hermetic runner

### Execution modes

- **Default hermetic mode**: `LocalDockerRunner` executes `maven:3.9-eclipse-temurin-21`
  with `--network none` and read-only local `.m2` cache. If Docker is missing, it returns
  exit code 127 without silently falling back to the host.
- **Local subprocess mode**: `LocalSubprocessRunner` is explicitly instantiated when
  requested. It enforces workspace path containment, timeout budgets, captures stdout/stderr
  up to 100,000 characters, parses diagnostics, and tags `image="host"`.
- **Diagnostic deduplication**: `parse_maven_output` in `agents/verifier/parser.py` deduplicates
  repeated compiler/Surefire diagnostics based on `(file_path, line_number, column_number, error_type, message)`.

---

## 4. AST repair agent and fixing-loop mechanics

- **Canonical Retry Bound**: Single implementation in `OrchestratorGraph`. Verified at exactly
  `MAX_ATTEMPTS = 3` (3 verification executions, 2 repair passes on persistent failure).
- **Source Context**: `load_repair_file` loads the diagnostic target file bounded to
  `MAX_REPAIR_FILE_CHARS = 50_000`, preserving the initial failure line.
- **Transactional Patching**: `apply_patch` stages unified diffs in a temporary directory,
  verifies patch application, and commits atomically with snapshot rollback.
- **Patch Failure Handling**: Any patch application failure returns a structured `NO_FIX`
  with failed guard `PATCH_APPLICATION`.

---

## 5. Actionable gap resolution status

### High priority

| Gap | Status | Evidence |
|---|---|---|
| Single canonical orchestrator | **RESOLVED** | `PipelineGraph` in `app/orchestrator/pipeline.py` delegates directly to `OrchestratorGraph`. Verified in `tests/orchestrator/test_e2e_pipeline.py`. |
| Local verification mode | **RESOLVED** | Implemented `LocalSubprocessRunner` (inheriting from `BaseVerifierRunner`). Verified in `tests/agents/verifier/test_runner.py`. |
| Quarkus 3.15 profile | **RESOLVED** | Added `profiles/quarkus-3.15.yaml` with Java 21, Panache, and SmallRye Kafka. Verified in `tests/agents/test_quarkus_profile.py`. |
| Truthful background status | **RESOLVED** | `app/main.py` records `RUNNING` prior to graph dispatch and transitions to `ERROR` on failures. Verified in `tests/test_main.py`. |

### Medium priority

| Gap | Status | Evidence |
|---|---|---|
| Diagnostic deduplication | **RESOLVED** | `parse_maven_output` filters duplicates across compiler and Surefire XML. Verified in `tests/agents/verifier/test_parser.py`. |
| Empty-manifest scaffolder handling | **RESOLVED** | Scaffolder returns `EMPTY_MANIFEST` when tool exits 0 but produces no files. Verified in `tests/agents/scaffolder/test_runner.py`. |
| Deduplicate generator helpers | **RESOLVED** | Extracted `unwrap_markdown` and `resolve_generation` into `agents/generator/common.py`. Verified in 35 generator tests. |
| Single canonical outcome | **RESOLVED** | `PATCHED` restricted to repair; terminal outcomes are `SUCCESS`, `NO_FIX`, `ERROR`. |

### Lower priority & deferred items

| Gap | Status | Resolution / Notes |
|---|---|---|
| LangGraph compiled graph migration | **DEFERRED** | Current in-process state machine is optimal and avoids unnecessary network overhead. LangGraph dependencies maintained for future multi-agent clustering. |
| AST-level Java parser in repair | **DEFERRED** | Diff-based repair with deterministic AST guard validations currently passes all verification tests with lower latency. |

---

## 6. Verification checklist

### Backend validation

```bash
uv run --extra dev pytest
# Result: 163 passed in 0.99s

uv run --extra dev mypy app/ contracts/ agents/
# Result: Success: no issues found in 41 source files

uv run --extra dev ruff check .
# Result: All checks passed!

git diff --check
# Result: Clean (0 whitespace/newline issues)
```

### Frontend validation

```bash
cd frontend && npm test -- --run && npm run build
# Result: 40 tests passed across 12 test files; Vite build successful (dist/ created).
```
