# Tasks: Official Quarkus Scaffolding

**Input**: Design documents from `/specs/002-official-quarkus-scaffolding/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Required by the project constitution and feature specification.

## Phase 1: Setup

- [X] T001 Create the scaffolder package structure and test directories in `agents/scaffolder/__init__.py`, `tests/agents/scaffolder/`, and `tests/contract/`
- [X] T002 [P] Verify the installed Maven/Quarkus tool command and record supported flags and output behavior in `docs/spikes.md`

## Phase 2: Foundational Contracts and Safety

- [X] T003 Add typed `ScaffoldConfig`, `ScaffoldRequest`, `ManifestEvidence`, and `ScaffoldResult` models with the documented validation constraints in `contracts/models.py`
- [X] T004 [P] Add scaffold-specific diagnostic/error codes and typed validation responses in `contracts/errors.py`
- [X] T005 [P] Add profile schema support for optional scaffold configuration, including tool version, command template, extension catalogs, and feature mappings in `agents/profiles/`
- [X] T006 Add contract tests for invalid identifiers, unsafe paths, unsupported extensions, invalid placeholders, duplicate extensions, and successful model parsing in `tests/contract/test_scaffolding_contracts.py`
- [X] T007 Add profile fixture data for a verified Quarkus/Maven catalog without embedding framework literals in agent Python code in `tests/fixtures/` and `profiles/`

## Phase 3: User Story 1 - Generate a Valid Project Scaffold (Priority: P1)

**Goal**: Produce a valid official-tool project scaffold inside the requested workspace with auditable manifest evidence.

**Independent test**: A valid request returns a successful typed result with tool/version, selected extensions, and a non-empty in-workspace manifest; unsafe requests start no process.

- [X] T008 [P] [US1] Implement deterministic command-template validation and argv expansion in `agents/scaffolder/command.py`
- [X] T009 [P] [US1] Implement workspace containment, identifier validation, and generated-file manifest collection with SHA-256 and byte size in `agents/scaffolder/safety.py`
- [X] T010 [US1] Implement the bounded official-tool process adapter using argv arrays, timeout, capped output, and explicit exit/error handling in `agents/scaffolder/service.py`
- [X] T011 [US1] Define the `Scaffolder` protocol and compose command, safety, process, and manifest behavior in `agents/scaffolder/service.py`
- [X] T012 [US1] Add fake-process tests for argv-only execution, timeout/error reporting, output capping, manifest-required success, and output containment in `tests/agents/scaffolder/test_runner.py`
- [X] T013 [US1] Add deterministic scaffold service tests for valid project creation and rejected unsafe requests in `tests/agents/scaffolder/test_runner.py`

## Phase 4: User Story 2 - Derive Extensions from Requirements (Priority: P1)

**Goal**: Derive a deterministic, profile-owned extension list from blueprint capabilities.

**Independent test**: Repeated identical blueprint/profile inputs return identical ordered, deduplicated extensions, while unsupported capabilities identify the offending field.

- [X] T014 [P] [US2] Implement pure `derive_extensions` using profile base extensions, allowlist, and feature mapping in `agents/scaffolder/extensions.py`
- [X] T015 [US2] Add extension derivation tests for persistence, REST/JSON, database drivers, optional capabilities, sorting, deduplication, and unsupported extension diagnostics in `tests/agents/scaffolder/test_extensions.py`
- [X] T016 [US2] Add blueprint-to-scaffold mapping fixtures covering entity, database, validation, and optional capability combinations in `tests/fixtures/scaffolding/`

## Phase 5: User Story 3 - Verify Offline Compatibility Before Generation (Priority: P1)

**Goal**: Verify scaffold output through the existing hermetic verifier before LLM generation or file materialization.

**Independent test**: A warmed catalog combination produces a parseable offline success result; an unavailable combination stops generation with failure evidence.

- [X] T017 [US3] Add an offline scaffold verification request builder that invokes the existing verifier with `mvn -o -q test-compile` and never reuses the networked scaffolder command in `agents/scaffolder/verification.py`
- [X] T018 [US3] Integrate scaffold verification into the orchestration boundary after validation/scaffolding and before generation in `app/orchestrator/pipeline.py`
- [X] T019 [US3] Add pipeline tests proving failed scaffolding or offline verification does not materialize generated business files in `tests/orchestrator/test_scaffolding_pipeline.py`
- [X] T020 [US3] Add verifier fake tests for parseable success/failure results, offline flag enforcement, cache availability failures, and trace ID propagation in `tests/agents/scaffolder/test_verification.py`

## Phase 6: User Story 4 - Preserve Existing Generation and Repair Behavior (Priority: P2)

**Goal**: Keep existing generation, verification, repair, API, and frontend behavior unchanged when scaffolding is not configured.

**Independent test**: Existing pipeline/API/frontend tests pass with scaffolding disabled; profiles without scaffold configuration return a clear capability error only when scaffolding is explicitly requested.

- [X] T021 [US4] Make scaffolding opt-in in `app/orchestrator/generation.py` and preserve the current generation path when no scaffold configuration is present
- [X] T022 [US4] Add explicit capability handling for profiles without scaffold configuration in `app/orchestrator/pipeline.py`
- [X] T023 [US4] Add backward-compatibility tests through the existing regression suite and focused scaffold tests
- [X] T024 [P] [US4] Preserve transient API-key handling; no frontend contract change was required

## Phase 7: Polish and Cross-Cutting Validation

- [X] T025 [P] Add focused documentation for the scaffold role boundary, verified command, catalog policy, and offline cache requirements in `docs/architecture-review-for-claude.md` and `docs/spikes.md`
- [X] T026 Run focused scaffold tests; 5 passed
- [X] T027 Run backend quality checks; pytest and mypy pass, changed-file Ruff passes, full Ruff retains pre-existing findings
- [X] T028 Frontend request types were unchanged; existing frontend validation remains applicable
- [X] T029 Run `git diff --check` and review the final diff for safety boundaries

## Dependencies and Execution Order

### Story completion order

1. Phase 1 setup
2. Phase 2 foundational contracts and safety
3. US1 scaffold execution
4. US2 extension derivation
5. US3 offline verification integration
6. US4 compatibility
7. Polish and validation

### Dependency graph

```text
T001,T002 -> T003,T004,T005,T006,T007
T003,T004,T005,T006,T007 -> T008,T009,T010,T011,T012,T013
T005,T006,T007 -> T014,T015,T016
T011,T014 -> T017,T018,T019,T020
T018 -> T021,T022,T023,T024
T012,T015,T019,T020,T023 -> T025,T026,T027,T028,T029
```

### Parallel opportunities

- T002 can run in parallel with T001.
- T004, T005, and T007 can run in parallel after T003's contract shape is agreed.
- T008 and T009 can run in parallel; T010 depends on their safety interfaces.
- T014 and US1 adapter tests can proceed in parallel after profile contracts exist.
- T025 can proceed in parallel with focused validation once implementation is stable.

## Implementation Strategy

1. **MVP**: Complete Phases 1-3 for a safe, typed, fake-tested scaffold adapter.
2. **Capability mapping**: Complete US2 with deterministic profile-driven extension derivation.
3. **Runtime integration**: Complete US3 while preserving the verifier's offline boundary.
4. **Compatibility gate**: Complete US4 and run the existing full suites before enabling any live scaffolding profile.
5. **Release gate**: Only enable the live Quarkus profile after T002 records verified tooling flags and the offline cache combination passes.
