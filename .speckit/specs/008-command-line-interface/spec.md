# Feature Specification: Orchestrator Command-Line Interface

**Feature Branch**: `008-command-line-interface`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Build a CLI that submits a blueprint to the orchestrator and reports a persisted run status by trace ID."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit a blueprint (Priority: P1)

As an operator, I want to run the CLI with a blueprint path, so that the blueprint is submitted to the orchestrator without manually constructing an HTTP request.

**Independent Test**: Mock the orchestrator response and assert the CLI sends the blueprint and records the returned trace ID.

**Acceptance Scenarios**:

1. Given a readable JSON blueprint file, when `run <path>` is executed, then the CLI submits it to the configured endpoint and prints the trace ID and outcome.
2. Given an unreadable or malformed blueprint file, when `run` is executed, then the CLI exits nonzero with a concise error.
3. Given an orchestrator HTTP failure, when `run` is executed, then the CLI exits nonzero without claiming success.

### User Story 2 - Inspect run status (Priority: P1)

As an operator, I want to query a trace ID, so that I can inspect the latest locally persisted status.

**Independent Test**: Seed a repository and assert `status <trace-id>` prints the stored status and attempts.

**Acceptance Scenarios**:

1. Given a known trace ID, when `status` is executed, then the CLI prints its blueprint name, status, and repair attempts.
2. Given an unknown trace ID, when `status` is executed, then the CLI exits nonzero and reports that the run was not found.

## Edge Cases

- The blueprint path is missing or is not a regular file.
- The blueprint JSON root is not an object.
- The API key is omitted.
- The response omits a trace ID.
- The local database does not yet exist.
- HTTP and database failures must be explicit and must not produce success-shaped output.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The CLI MUST provide `run <path-to-blueprint>` and `status <trace-id>` commands.
- **FR-002**: `run` MUST read a JSON object from the supplied path and submit it to the orchestrator run endpoint.
- **FR-003**: `run` MUST support configurable base URL, API key, and local database path.
- **FR-004**: `run` MUST persist a `RUNNING` record before submission and update it with the returned outcome and repair attempts.
- **FR-005**: `run` MUST print the resulting trace ID and outcome on success and return a nonzero exit code on failure.
- **FR-006**: `status` MUST read the requested trace ID from SQLite and print status and repair attempts.
- **FR-007**: `status` MUST return a nonzero exit code for an unknown trace ID or database failure.
- **FR-008**: CLI behavior MUST be testable with mocked HTTP and repository boundaries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Valid mocked submissions print a trace ID and outcome and return exit code zero.
- **SC-002**: Invalid input and failed HTTP requests return nonzero exit codes without false success output.
- **SC-003**: Known status queries print the persisted status and attempt count.
- **SC-004**: All CLI tests run without network access or a live orchestrator.

## Assumptions

- Blueprint files are JSON objects.
- The orchestrator endpoint is `/v1/blueprint/run`.
- The orchestrator response contains `trace_id`, `outcome`, and optionally `attempts`.
- The CLI stores local history in `orchestrator.db` unless overridden.
