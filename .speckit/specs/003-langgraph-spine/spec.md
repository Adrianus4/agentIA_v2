# Feature Specification: LangGraph Spine

**Feature Branch**: `003-langgraph-spine`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Define the core orchestrator state machine in app/orchestrator/graph.py: Blueprint Validate -> Verify -> (if fail) Repair -> Apply Patch -> Verify, with a maximum of 3 repair attempts, NO_FIX after three failures, and mocked Track 2 nodes returning contracts.models Pydantic schemas."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate and verify a blueprint (Priority: P1)

As an orchestrator caller, I want a blueprint checked and then verified before any repair is attempted, so that valid workspaces complete without unnecessary modifications.

**Why this priority**: Validation and verification are the safety gates for every orchestration run.

**Independent Test**: Run the spine with a dummy validation node that returns a valid contract response and a dummy verifier that succeeds, then verify that the run completes without repair or patch application.

**Acceptance Scenarios**:

1. **Given** a blueprint accepted by the validation node, **When** verification succeeds, **Then** the workflow finishes successfully without invoking repair or patch application.
2. **Given** a blueprint rejected by validation, **When** the workflow evaluates the validation result, **Then** it returns an explicit validation failure and does not invoke verification or patch application.
3. **Given** validation and verification node results, **When** the workflow stores them, **Then** each result is an instance of the corresponding `contracts.models` schema.

### User Story 2 - Repair a failed verification (Priority: P1)

As an orchestrator caller, I want a failed verification to produce a bounded repair attempt and apply the returned patch before verifying again, so that correctable failures can converge without manual intervention.

**Why this priority**: The repair loop is the primary value of the orchestrator spine after a verification failure.

**Independent Test**: Run the spine with dummy nodes that fail the first verification, return a contract-valid repair result with a safe patch, apply it, and then return a successful verification.

**Acceptance Scenarios**:

1. **Given** verification fails and the attempt counter is below the limit, **When** the workflow routes the failure, **Then** it invokes repair with the current verification issues.
2. **Given** repair returns a contract-valid patch, **When** the workflow reaches Apply Patch, **Then** the patch is applied and the attempt counter increases exactly once.
3. **Given** a patch is applied, **When** the workflow continues, **Then** it returns to Verify rather than restarting blueprint validation.
4. **Given** verification succeeds after a repair, **When** the workflow completes, **Then** it returns a successful patched outcome with the final verification result.

### User Story 3 - Stop after three failed attempts (Priority: P1)

As a workspace owner, I want the repair cycle to stop after three unsuccessful verification attempts, so that an automated agent cannot loop indefinitely or make unbounded changes.

**Why this priority**: The three-attempt cap is a safety and resource boundary mandated by the project constitution.

**Independent Test**: Configure dummy verification and repair nodes to fail every attempt, execute the workflow, and verify that exactly three attempts are recorded before the workflow transitions to `NO_FIX`.

**Acceptance Scenarios**:

1. **Given** verification fails on attempt one or two, **When** the attempt counter is below three, **Then** the workflow may perform another repair cycle.
2. **Given** verification fails on the third attempt, **When** the workflow evaluates the counter, **Then** it transitions to `NO_FIX` and does not invoke repair or apply another patch.
3. **Given** a repair node returns a non-patchable or rejected result, **When** the workflow handles it, **Then** it records the failure explicitly and terminates with an outcome consistent with the contract rather than looping indefinitely.

### User Story 4 - Exercise the spine before Track 2 integration (Priority: P2)

As an orchestrator developer, I want temporary Track 2 node implementations that return the existing typed contracts, so that the spine can be tested before real agent microservices are connected.

**Why this priority**: The orchestration control flow must be testable independently of unavailable downstream services.

**Independent Test**: Inject dummy Validate, Verify, and Repair functions, execute the graph, and verify that their outputs parse as `UniformErrorBody`, `VerificationResult`, and `RepairResult` from `contracts.models`.

**Acceptance Scenarios**:

1. **Given** a dummy Validate node, **When** the spine invokes it, **Then** it returns a `UniformErrorBody` instance.
2. **Given** a dummy Verify node, **When** the spine invokes it, **Then** it returns a `VerificationResult` instance.
3. **Given** a dummy Repair node, **When** the spine invokes it, **Then** it returns a `RepairResult` instance.
4. **Given** a dummy node returns an unparseable or wrong-shaped value, **When** the spine handles the result, **Then** it raises or records an explicit contract error instead of treating the result as valid.

## Edge Cases

- Validation returns invalid diagnostics with no repairable verification stage.
- Verification fails before any repair attempt and returns multiple issues.
- Repair returns no patches, multiple patches, or an outcome that rejects the patch.
- Patch application raises an error after repair returns a result.
- Verification succeeds on the first attempt, on the first repaired attempt, or on the third attempt.
- Verification fails three times; no fourth verification, repair, or patch application is performed.
- A node raises an exception or returns an object that is not the expected Pydantic schema.
- A workflow is invoked with an initial attempt counter at or above the maximum; it must reject invalid state rather than bypassing the cap.
- Every run and node result requires a trace identifier without exposing source content or secrets in logs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose the orchestrator state machine in `app/orchestrator/graph.py`.
- **FR-002**: The workflow MUST execute nodes in this order for a normal run: Blueprint Validate, Verify, and, only after a failed Verify, Repair, Apply Patch, and Verify again.
- **FR-003**: The workflow MUST stop after a successful validation and verification without invoking Repair or Apply Patch.
- **FR-004**: The workflow MUST maintain an explicit repair-attempt counter in state and initialize it deterministically for each run.
- **FR-005**: The workflow MUST permit no more than three failed verification attempts in one run.
- **FR-006**: When verification fails for the third time, the workflow MUST transition to a `NO_FIX` outcome and terminate without invoking a fourth repair, patch, or verification step.
- **FR-007**: The workflow MUST increment the repair-attempt counter exactly once for each repair cycle and expose the final count in its result state.
- **FR-008**: The workflow MUST route a failed verification with an available attempt to Repair, then route a successful contract-valid repair result to Apply Patch, then route back to Verify.
- **FR-009**: The workflow MUST not restart Blueprint Validate after a patch is applied.
- **FR-010**: Track 2 Validate, Verify, and Repair nodes MUST initially be injectable dummy functions that return `UniformErrorBody`, `VerificationResult`, and `RepairResult` instances from `contracts.models`.
- **FR-011**: The workflow MUST validate node outputs against the expected Pydantic schemas before using their fields for routing or state updates.
- **FR-012**: The workflow MUST surface node exceptions, invalid contract outputs, rejected repairs, and patch-application errors explicitly.
- **FR-013**: The workflow MUST represent final outcomes using the existing outcome vocabulary, including `NO_FIX` for the exhausted repair budget.
- **FR-014**: The workflow state MUST retain the current trace identifier and propagate it to node inputs and final results or logs.
- **FR-015**: The workflow MUST not log full source files, complete patch content, credentials, or other secrets while reporting node or routing failures.
- **FR-016**: The workflow MUST reject or normalize invalid initial state so that callers cannot bypass the three-attempt limit by supplying an elevated counter.

### Key Entities *(include if feature involves data)*

- **Orchestration State**: The bounded workflow state containing the workspace and blueprint inputs, attempt counter, trace identifier, validation result, verification result, repair result, patch status, and final outcome.
- **Validate Result**: A `UniformErrorBody` contract result determining whether the blueprint can proceed to verification.
- **Verify Result**: A `VerificationResult` contract result indicating success, diagnostics, and execution metadata.
- **Repair Result**: A `RepairResult` contract result describing the proposed outcome, patches, touched files, guards, and attempts used.
- **Workflow Outcome**: The final status, including successful completion, rejection, error, or `NO_FIX`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of successful first-pass runs invoke Validate and Verify exactly once and invoke Repair and Apply Patch zero times.
- **SC-002**: 100% of repairable failures route through Repair and Apply Patch before returning to Verify.
- **SC-003**: 100% of permanently failing runs terminate after exactly three failed verification attempts with `NO_FIX`, with zero fourth attempts.
- **SC-004**: 100% of dummy Track 2 node outputs used by the spine validate as the specified `contracts.models` Pydantic schemas.
- **SC-005**: 100% of invalid node outputs, patch failures, and node exceptions produce explicit non-success handling rather than silent continuation.
- **SC-006**: 0 workflow runs exceed three repair attempts, regardless of initial state or downstream node behavior.

## Assumptions

- The existing `contracts.models` schemas are the source of truth for inter-agent payloads and will not be duplicated in the orchestrator.
- The Apply Patch step delegates filesystem safety to the approved Workspace Manager boundary.
- Track 2 dummy nodes are temporary testable seams and will later be replaced by adapters for real microservices without changing routing semantics.
- A failed verification means `VerificationResult.success` is false; a successful verification means it is true.
- The first Verify occurs after successful Blueprint Validate and counts toward the three failed verification-attempt limit.
- The workflow receives a trace identifier or creates one at its entry point when absent.
- The graph library and exact node function signatures are implementation choices for the planning phase, provided the state and routing behavior remain observable and testable.

