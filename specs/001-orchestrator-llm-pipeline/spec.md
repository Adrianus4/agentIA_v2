# Feature Specification: Unified Orchestrator and LLM Configuration

**Feature Branch**: `001-orchestrator-llm-pipeline`
**Created**: 2026-10-12
**Status**: Draft
**Input**: User description: "Complete the final end-to-end orchestrator generation and verification loop, stop tests from hanging after passing, and add a UI window to select and configure the LLM."

## User Scenarios & Testing

### User Story 1 - Generate and verify a service (Priority: P1)

As a developer, I want one run to validate a blueprint, generate the service source and tests, verify it, and repair bounded failures so that I receive a working project or an explicit failure outcome.

**Why this priority**: This is the core product workflow and unifies the completed generation and verification components.

**Independent Test**: Submit a valid blueprint with a deterministic fake model and simulated verifier; confirm generated files are materialized, verification occurs, and the run returns success.

**Acceptance Scenarios**:

1. **Given** a valid blueprint and a passing verifier, **When** a run is started, **Then** validation, profile resolution, generation, and verification complete in order and the result is `SUCCESS`.
2. **Given** a failed first verification and a safe repair patch, **When** the run retries, **Then** the patch is applied and the second verification returns `PATCHED`.
3. **Given** repeated verification failures, **When** the repair budget is exhausted, **Then** the run stops after three verification attempts and returns `NO_FIX` without another repair attempt.

### User Story 2 - Configure the language model (Priority: P1)

As a developer, I want to choose the model provider and model name in the run form so that each orchestration run uses the intended model configuration.

**Why this priority**: Model choice directly affects generated output and must be visible before dispatch.

**Independent Test**: Open the run form, choose a provider and model, enter credentials without exposing them in normal text, submit a blueprint, and confirm the request contains the selected non-secret configuration.

**Acceptance Scenarios**:

1. **Given** the run form is open, **When** the developer selects a provider and model, **Then** the selected values are shown and included in the request.
2. **Given** a provider requires a credential, **When** the developer enters it, **Then** it is masked in the UI and is never persisted to browser storage or displayed in status output.
3. **Given** an unsupported or incomplete configuration, **When** the developer submits, **Then** the UI blocks submission with an actionable message.

### User Story 3 - Trust test completion (Priority: P1)

As a developer, I want the test command to exit after reporting its result so that automation and CI can reliably determine whether the suite completed.

**Why this priority**: A passing suite that remains alive is operationally indistinguishable from a hung build.

**Independent Test**: Run the documented test command under a bounded timeout and confirm it exits successfully after the summary.

**Acceptance Scenarios**:

1. **Given** all tests pass, **When** the suite finishes, **Then** the process exits with code zero within the documented completion window.
2. **Given** a test fails or times out, **When** the suite ends, **Then** the process exits nonzero and identifies the failing stage.

## Edge Cases

- The selected model credentials are missing, invalid, or unavailable.
- The generated file list contains a path outside the target workspace.
- A blueprint is invalid and must not trigger generation or verification.
- A verifier times out or returns malformed output.
- The repair service returns an unsafe, empty, or malformed patch.
- A test runner leaves a background resource open after the last test.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST execute validation, profile resolution, generation, materialization, verification, and bounded repair as one traceable workflow.
- **FR-002**: The system MUST stop before generation when blueprint validation is invalid.
- **FR-003**: The system MUST materialize generated files only within the requested workspace.
- **FR-004**: The system MUST cap verification attempts at three and return `NO_FIX` when the cap is reached.
- **FR-005**: The system MUST expose provider and model selection in the run UI.
- **FR-006**: The system MUST validate required model configuration before submission.
- **FR-007**: The system MUST prevent model credentials from appearing in persisted UI state, logs, or run status responses.
- **FR-008**: The test command MUST terminate with an exit code after the suite completes, including cleanup of resources opened by tests or plugins.
- **FR-009**: The system MUST preserve the existing blueprint submission and status polling behavior.
- **FR-010**: The system MUST emit a trace identifier for each orchestration run and retain the selected model name without retaining secret values.

### Key Entities

- **Orchestration Run**: A traceable execution with a blueprint, selected model metadata, generated files, verification result, repair attempts, and terminal outcome.
- **LLM Configuration**: Provider, model name, endpoint when applicable, and transient credential used only for the active run.
- **Generated File**: A workspace-relative path and generated source content.
- **Verification Attempt**: A bounded execution result containing success, diagnostics, timeout state, and output metadata.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A valid happy-path run completes all workflow stages in one trace and reports success.
- **SC-002**: A repairable failure reaches a passing verification in no more than three attempts.
- **SC-003**: An unrecoverable run performs no more than three verification attempts and returns a terminal failure outcome.
- **SC-004**: 100% of UI submissions with missing required model configuration are rejected before a backend run starts.
- **SC-005**: Model credentials are absent from stored run records and status responses in 100% of tested submissions.
- **SC-006**: The full automated test command exits with code zero within 60 seconds after the final test result for a passing suite.

## Assumptions

- The first production provider remains the existing Gemini-compatible client; the UI is designed so additional providers can be added without changing the run flow.
- Model credentials are supplied through the active form or server environment and are not persisted by the frontend.
- The existing API key protects the orchestration endpoint.
- Generated projects use the profile-selected verification command, with Maven clean test as the initial default for the supported Java workflow.
- Existing frontend blueprint fields and endpoint paths remain backward compatible.
