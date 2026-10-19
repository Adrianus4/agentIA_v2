# Feature Specification: Execution Run Persistence

**Feature Branch**: `007-database-layer`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Implement an asynchronous SQLite repository that persists execution runs with trace ID, blueprint name, status, and repair attempts, including CRUD and state updates."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record an execution run (Priority: P1)

As the orchestrator, I want to create a run record when execution begins, so that operators can identify and track work in progress.

**Independent Test**: Create a run and retrieve it by its trace ID; all identifying fields match.

**Acceptance Scenarios**:

1. Given a new trace ID and blueprint name, when a run is created, then it is stored with status `RUNNING` and zero repair attempts by default.
2. Given an existing trace ID, when a duplicate run is created, then the repository reports an explicit conflict rather than silently overwriting the record.

### User Story 2 - Update execution state (Priority: P1)

As the orchestrator, I want to update status and repair attempts, so that the persisted record reflects the current execution outcome.

**Independent Test**: Update a running record to `SUCCESS` and verify the status and attempt count after retrieval.

**Acceptance Scenarios**:

1. Given a running record, when its status and repair attempts are updated, then subsequent reads return the new values.
2. Given a missing trace ID, when an update is requested, then the repository reports that the run does not exist.

### User Story 3 - Enumerate and remove records (Priority: P2)

As an operator, I want to list and delete stored runs, so that local execution history can be inspected and maintained.

**Independent Test**: Create multiple records, list them, delete one, and verify only the remaining record is returned.

**Acceptance Scenarios**:

1. Given multiple records, when runs are listed, then each stored run is returned with its fields.
2. Given an existing record, when it is deleted, then retrieval returns no record.

## Edge Cases

- Empty trace IDs and blueprint names are rejected.
- Repair attempts cannot be negative.
- Status values are restricted to known execution states such as `RUNNING`, `SUCCESS`, and `NO_FIX`.
- The repository creates its schema before the first operation.
- Concurrent callers share a consistent schema and commit each mutation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST expose asynchronous create, retrieve, list, update, and delete operations for execution runs.
- **FR-002**: Each run MUST persist `trace_id`, `blueprint_name`, `status`, and `repair_attempts`.
- **FR-003**: New runs MUST default to `RUNNING` and zero repair attempts.
- **FR-004**: Trace IDs MUST be unique and duplicate creation MUST raise an explicit repository error.
- **FR-005**: Updates MUST reject missing records, invalid statuses, and negative repair attempts.
- **FR-006**: Every mutation MUST be committed before the operation returns.
- **FR-007**: The repository MUST use an asynchronous SQLite access path and support temporary database files for tests.
- **FR-008**: Repository reads MUST return typed run records or `None`, not raw database tuples.

## Key Entities

- **ExecutionRun**: A typed record containing trace ID, blueprint name, status, and repair attempt count.
- **RunRepository**: The asynchronous persistence boundary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All CRUD and state-update tests pass for both empty and populated repositories.
- **SC-002**: 100% of duplicate, missing-record, invalid-status, and negative-attempt cases produce explicit errors.
- **SC-003**: A committed update is visible from a newly opened repository connection.
- **SC-004**: No public repository method returns an untyped database row.

## Assumptions

- The database is local SQLite and does not provide distributed coordination.
- Status is represented as a small controlled string set: `RUNNING`, `SUCCESS`, `NO_FIX`, and `ERROR`.
- A trace ID is the primary lookup key for the CLI and orchestrator integration.
