# Feature Specification: Microservice HTTP Adapters

**Feature Branch**: `006-microservice-adapters`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Create an asynchronous AgentClient using httpx to call verifier and repair microservices, with 30-second timeouts, up to two retries for HTTP 5xx responses, and strict mapping into contracts.models schemas."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verify through the microservice boundary (Priority: P1)

As the orchestrator, I want to submit a blueprint payload to the verifier microservice and receive a typed verification result, so that the LangGraph spine can use the remote verifier without provider-specific response handling.

**Why this priority**: Verification is the first external agent call required by the approved orchestration loop.

**Independent Test**: Mock the verifier endpoint with valid JSON and assert that the asynchronous client returns a `VerificationResult`.

**Acceptance Scenarios**:

1. **Given** a valid verifier response, **When** `verify_blueprint` is called, **Then** it returns a `VerificationResult` instance with the response fields preserved.
2. **Given** malformed or schema-incompatible verifier JSON, **When** `verify_blueprint` is called, **Then** it raises an explicit adapter/schema error.
3. **Given** a verifier response with an HTTP client or server error, **When** the call completes, **Then** it raises an explicit adapter error rather than returning a success-shaped value.

### User Story 2 - Request repairs through the microservice boundary (Priority: P1)

As the orchestrator, I want to submit a repair payload to the repair microservice and receive a typed repair result, so that the LangGraph spine can safely decide whether to apply returned patches.

**Why this priority**: Repair is the second external agent call required to progress a failed verification.

**Independent Test**: Mock the repair endpoint with valid JSON and assert that the asynchronous client returns a `RepairResult`.

**Acceptance Scenarios**:

1. **Given** a valid repair response, **When** `repair_code` is called, **Then** it returns a `RepairResult` instance with guard and attempt metadata preserved.
2. **Given** malformed or schema-incompatible repair JSON, **When** `repair_code` is called, **Then** it raises an explicit adapter/schema error.
3. **Given** an HTTP error from the repair service, **When** the call completes, **Then** it raises an explicit adapter error without fabricating patches.

### User Story 3 - Retry transient service failures safely (Priority: P1)

As an operator, I want transient verifier and repair service failures retried a bounded number of times, so that temporary 5xx responses do not immediately fail an otherwise recoverable orchestration run.

**Why this priority**: External services can transiently fail, but unbounded retries would violate the orchestrator’s bounded execution model.

**Independent Test**: Mock two 5xx responses followed by a valid response and assert exactly three requests; mock three 5xx responses and assert an explicit final failure.

**Acceptance Scenarios**:

1. **Given** a 5xx response on the first request, **When** the adapter retries, **Then** it makes another request.
2. **Given** two consecutive 5xx responses followed by success, **When** the adapter completes, **Then** it returns the typed success after exactly three requests.
3. **Given** three consecutive 5xx responses, **When** the adapter completes, **Then** it raises an explicit HTTP error after exactly three requests.
4. **Given** a timeout, **When** the adapter completes, **Then** it raises an explicit timeout error and does not retry indefinitely.

## Edge Cases

- A response has a non-JSON body or missing required schema fields.
- A response returns 4xx; it must not be retried as a transient 5xx.
- A request times out at the 30-second client timeout.
- The configured service URL has or lacks a trailing slash.
- A caller passes a non-dictionary payload.
- A service returns extra JSON fields; schema parsing must retain the contract boundary and not expose raw provider objects.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose an asynchronous `AgentClient` in `app/orchestrator/clients/agent_client.py`.
- **FR-002**: `AgentClient.verify_blueprint(payload: dict)` MUST POST the payload to the configured verifier endpoint and return `VerificationResult`.
- **FR-003**: `AgentClient.repair_code(payload: dict)` MUST POST the payload to the configured repair endpoint and return `RepairResult`.
- **FR-004**: The client MUST use a 30-second request timeout by default.
- **FR-005**: The client MUST retry HTTP 5xx responses no more than two times after the initial request, for a maximum of three total requests.
- **FR-006**: The client MUST NOT retry HTTP 4xx responses.
- **FR-007**: The client MUST map verifier JSON strictly through `VerificationResult` validation and repair JSON strictly through `RepairResult` validation.
- **FR-008**: The client MUST raise explicit typed errors for timeout, transport, HTTP status, invalid JSON, and schema validation failures.
- **FR-009**: The client MUST never return raw JSON dictionaries or provider-specific response objects from its public methods.
- **FR-010**: The client MUST support deterministic HTTP mocking through an injectable transport or client for automated tests.
- **FR-011**: The client MUST close internally-owned HTTP resources and MUST NOT close caller-owned injected clients.
- **FR-012**: The adapter MUST not log request payloads, response bodies, credentials, or complete patch content by default.

### Key Entities *(include if feature involves data)*

- **AgentClient**: The asynchronous HTTP boundary for verifier and repair microservices.
- **VerificationResult**: The typed verifier response contract from `contracts.models`.
- **RepairResult**: The typed repair response contract from `contracts.models`.
- **Adapter Error**: An explicit failure category for timeout, transport, HTTP, JSON, or schema failures.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of valid mocked verifier and repair responses produce the corresponding Pydantic schema type.
- **SC-002**: 100% of sequences with two transient 5xx responses followed by success make exactly three requests and succeed.
- **SC-003**: 100% of sequences with three transient 5xx responses terminate after exactly three requests.
- **SC-004**: 100% of malformed or schema-invalid response tests raise explicit adapter errors.
- **SC-005**: 0 tests return raw response dictionaries from public adapter methods.

## Assumptions

- Verifier and repair endpoint paths are configurable and default to `/verify` and `/repair`.
- The caller supplies a base service URL appropriate for the deployed microservice.
- Retries are immediate and bounded; backoff policy is outside this deliverable.
- Authentication headers, tracing headers, and service discovery can be added through client configuration without changing the typed method results.

