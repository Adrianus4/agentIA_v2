---
description: "Task list for unified orchestrator and LLM configuration"
---

# Tasks: Unified Orchestrator and LLM Configuration

**Input**: Design documents from `/specs/001-orchestrator-llm-pipeline/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

## Phase 1: Setup

- [ ] T001 Confirm the feature workspace and existing test commands in `specs/001-orchestrator-llm-pipeline/quickstart.md`
- [ ] T002 [P] Record the selected provider/model metadata contract in `specs/001-orchestrator-llm-pipeline/contracts/api.md`

## Phase 2: Foundational

- [ ] T003 Add typed LLM configuration fields and secret-safe serialization rules in `contracts/models.py`
- [ ] T004 Add explicit test teardown configuration and a bounded pytest invocation in `pyproject.toml` and `tests/conftest.py`
- [ ] T005 [P] Add frontend LLM configuration types and provider/model defaults in `frontend/src/types/blueprintGraph.ts` and `frontend/src/services/blueprintService.ts`

## Phase 3: User Story 1 - Unified generation, verification, and repair

**Goal**: Execute validation, profile loading, generation, materialization, verification, and bounded repair as one traceable workflow.

**Independent Test**: `timeout 60s uv run pytest -q -p no:langsmith tests/orchestrator/test_e2e_pipeline.py`

- [ ] T006 [P] [US1] Add happy-path, repair-loop, and budget-exhaustion integration tests in `tests/orchestrator/test_e2e_pipeline.py`
- [ ] T007 [US1] Implement profile resolution and sequential generator orchestration in `app/orchestrator/pipeline.py`
- [ ] T008 [US1] Integrate `LocalDockerRunner.run` with the profile verification command and typed `VerificationResult` in `app/orchestrator/pipeline.py`
- [ ] T009 [US1] Integrate `ScopedRepairService.repair`, guarded `apply_patch`, and the three-attempt loop in `app/orchestrator/pipeline.py`
- [ ] T010 [US1] Wire the unified pipeline into `app/main.py` while preserving existing endpoint and status response contracts
- [ ] T011 [US1] Add path traversal, invalid validation, malformed node result, and timeout coverage in `tests/orchestrator/test_e2e_pipeline.py`

## Phase 4: User Story 2 - LLM configuration window

**Goal**: Let the developer select and configure the model used for a run without exposing credentials.

**Independent Test**: `cd frontend && npm test -- --run src/test/BlueprintRunTrigger.test.tsx && npm run build`

- [ ] T012 [P] [US2] Add provider, model, endpoint, and masked credential controls to `frontend/src/components/orchestration/BlueprintRunTrigger.tsx`
- [ ] T013 [US2] Include non-secret provider/model metadata in the submitted blueprint and keep credentials transient in `frontend/src/services/blueprintService.ts`
- [ ] T014 [P] [US2] Add UI tests for provider selection, model selection, validation, and secret masking in `frontend/src/test/BlueprintRunTrigger.test.tsx`
- [ ] T015 [US2] Add backend request tests proving model metadata is accepted and credentials are absent from serialized state in `tests/test_main.py`

## Phase 5: User Story 3 - Deterministic test completion

**Goal**: Ensure a passing test command exits rather than remaining blocked after the summary.

**Independent Test**: `timeout 60s uv run pytest -q -p no:langsmith; test $? -eq 0`

- [ ] T016 [US3] Identify and close the resource or plugin teardown handle that keeps pytest blocked after the final result in `tests/conftest.py` or the owning application module
- [ ] T017 [US3] Add a subprocess regression test or documented bounded command proving the full suite exits with code zero in `tests/test_runner_exit.py`
- [ ] T018 [US3] Update `start.sh`, `start.bat`, and `specs/001-orchestrator-llm-pipeline/quickstart.md` with the reliable test command and timeout behavior

## Phase 6: Polish and Cross-Cutting Concerns

- [ ] T019 Run `uv run ruff check .` and fix only feature-related findings in touched files
- [ ] T020 Run `uv run mypy app/` and fix only feature-related type errors
- [ ] T021 Run backend and frontend tests/builds from the quickstart and inspect `git diff --check`
- [ ] T022 Review logs and serialized responses for credentials, then record the final verification evidence in `specs/001-orchestrator-llm-pipeline/quickstart.md`
- [ ] T023 Stage intended files and create the requested commit with message `feat(orchestrator): wire generation graph to verification micro-tdd loop`

## Dependencies and Execution Order

- Setup: T001-T002
- Foundational: T003-T005 after setup
- US1: T006-T011 after foundational tasks
- US2: T012-T015 after T003 and T005; independent of US1 after shared contracts
- US3: T016-T018 after foundational tasks; independent of US2
- Polish: T019-T023 after all stories

## Parallel Opportunities

- T005 can run in parallel with T002-T004.
- T006 and T012 can begin in parallel after their respective prerequisites.
- T014 can be prepared alongside T012, then executed after the UI change.
- T016 can be investigated in parallel with US1 implementation.

## Implementation Strategy

1. Deliver US1 first as the MVP: unified pipeline with deterministic integration tests.
2. Add US2 without changing existing endpoints or persisting secrets.
3. Fix and regression-test process teardown.
4. Run the complete quality gate and commit only intended files.
