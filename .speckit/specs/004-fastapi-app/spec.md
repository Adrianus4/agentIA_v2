# Feature Specification: FastAPI Orchestrator App

**Feature Branch**: `004-fastapi-app`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Define app/main.py with x-api-key authentication using a constant-time comparison and route blueprint stub endpoints to the LangGraph orchestrator."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Authenticate orchestrator requests (Priority: P1)

As an API consumer, I want protected orchestrator endpoints to require the configured API key, so that unauthenticated callers cannot start or inspect orchestration work.

**Why this priority**: Authentication is the security boundary for every exposed orchestration route.

**Independent Test**: Call a protected endpoint with a missing, incorrect, and correct `x-api-key` header and verify the respective unauthorized or successful outcomes.

**Acceptance Scenarios**:

1. **Given** a request without `x-api-key`, **When** it reaches a protected endpoint, **Then** the request is rejected with an authentication error.
2. **Given** a request with an incorrect key, **When** it reaches a protected endpoint, **Then** the request is rejected with the same authentication error without disclosing the expected key.
3. **Given** a request with the configured key, **When** it reaches a protected endpoint, **Then** the request proceeds to the orchestrator.

### User Story 2 - Start blueprint orchestration through the API (Priority: P1)

As an API consumer, I want blueprint endpoints to invoke the orchestrator spine, so that validation and repair behavior is available through a stable HTTP interface.

**Why this priority**: The API is the integration boundary for callers of the orchestrator.

**Independent Test**: Inject a deterministic graph implementation, call each supported blueprint route with valid authentication, and verify that the graph receives the request and its result is returned.

**Acceptance Scenarios**:

1. **Given** an authenticated blueprint request, **When** `/v1/blueprint/validate` is called, **Then** the application invokes the LangGraph spine and returns its structured state result.
2. **Given** an authenticated blueprint request, **When** a verify, repair, or run stub endpoint is called, **Then** it routes through the same orchestrator boundary rather than returning an unconnected placeholder.
3. **Given** the orchestrator returns a structured outcome, **When** the API serializes it, **Then** the response contains the outcome, attempt count, trace identifier, and contract-backed results where present.

### User Story 3 - Report request failures safely (Priority: P2)

As an operator, I want API failures to be explicit and safe, so that callers can correct invalid requests without learning credentials or internal source content.

**Why this priority**: Clear failure behavior is necessary for reliable automation and safe operations.

**Independent Test**: Exercise invalid JSON, graph exceptions, and missing configuration, then verify explicit HTTP errors without secret or patch-content leakage.

**Acceptance Scenarios**:

1. **Given** the orchestrator raises a controlled error, **When** an authenticated request is processed, **Then** the API returns an explicit non-success response.
2. **Given** the API-key configuration is absent, **When** a protected endpoint is called, **Then** the API reports unavailable authentication configuration rather than accepting requests.
3. **Given** a request or downstream error contains sensitive values, **When** the API creates its response, **Then** it does not include the API key, full patch content, or source files.

## Edge Cases

- API key environment configuration is missing or blank.
- API key header is missing, empty, or has surrounding whitespace.
- Header uses a near-match key of the same length or a different length.
- Request body is missing, malformed, or omits the workspace path.
- Graph result contains optional nested contract results or a `NO_FIX` outcome.
- Graph invocation raises a patching, contract, or unexpected exception.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a FastAPI application from `app/main.py`.
- **FR-002**: The system MUST protect every `/v1/blueprint/*` endpoint with an `x-api-key` header.
- **FR-003**: The system MUST compare the supplied API key using a constant-time comparison operation.
- **FR-004**: The system MUST load the expected API key from an environment variable and MUST reject requests when the configuration is missing or blank.
- **FR-005**: The system MUST return an authentication error for missing or invalid API keys without revealing the expected value.
- **FR-006**: The system MUST expose stubs for blueprint validation and related orchestration operations, including `/v1/blueprint/validate`, `/v1/blueprint/verify`, `/v1/blueprint/repair`, and `/v1/blueprint/run`.
- **FR-007**: Each blueprint stub endpoint MUST route authenticated requests to the LangGraph orchestration boundary.
- **FR-008**: The API MUST serialize graph state and contract-backed results into JSON without exposing provider-specific objects.
- **FR-009**: The API MUST preserve the graph trace identifier and return it in successful responses.
- **FR-010**: The API MUST return explicit non-success responses for malformed input, unavailable authentication configuration, graph contract failures, and downstream patch errors.
- **FR-011**: Error responses MUST NOT expose API keys, complete patch content, or full source files.
- **FR-012**: The application MUST allow the graph boundary to be replaced by a deterministic test double without changing authentication behavior.

### Key Entities *(include if feature involves data)*

- **Authenticated Blueprint Request**: A request carrying a workspace and blueprint payload after API-key verification.
- **Graph Result**: The serialized orchestration state returned by the LangGraph spine.
- **API Error Response**: A safe HTTP error containing a client-actionable status and message without secrets.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of protected endpoint requests without a valid API key are rejected.
- **SC-002**: 100% of authenticated blueprint endpoint requests invoke the graph boundary exactly once.
- **SC-003**: 100% of authentication checks use constant-time key comparison and expose no expected-key value in responses.
- **SC-004**: 100% of graph outcomes, including `NO_FIX`, preserve the trace identifier and attempt count in the API response.
- **SC-005**: 0 tested error responses expose API keys, full source files, or complete patch content.

## Assumptions

- The expected API key is supplied by an environment variable named `ORCHESTRATOR_API_KEY`.
- Blueprint request bodies contain a workspace directory and an optional JSON blueprint object.
- The LangGraph spine is the single orchestration boundary for all blueprint stub routes in this initial API.
- Authentication failures use a generic message for both missing and incorrect credentials.
- API versioning remains under `/v1` and response models may evolve in later deliverables.

