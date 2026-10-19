# Feature Specification: LLM Clients

**Feature Branch**: `001-llm-clients`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Define the LLMClient Protocol, FakeLLMClient (offline), and GeminiLLMClient (API key from env) in app/core/llm/, returning usage-aware asynchronous responses."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the orchestrator offline (Priority: P1)

As a developer running the orchestrator locally or in automated tests, I want a deterministic language-model client that does not require network access or credentials, so that I can exercise orchestration behavior repeatably while retaining usage metadata.

**Why this priority**: Offline execution is required for reliable development and test automation and prevents tests from depending on an external provider.

**Independent Test**: Instantiate the offline client with a predefined response, asynchronously submit a prompt, and verify that a usage-aware response is returned without requiring an API key or network access.

**Acceptance Scenarios**:

1. **Given** an offline client configured with a predefined response, **When** the orchestrator submits a prompt, **Then** the client returns that response deterministically.
2. **Given** an offline client with no predefined response, **When** the orchestrator submits a prompt, **Then** the client returns a documented safe default or explicit error rather than attempting a network call.
3. **Given** repeated submissions of the same prompt to an unchanged offline client, **When** each submission completes, **Then** the returned result is identical.

### User Story 2 - Use one interchangeable client contract (Priority: P1)

As an orchestrator developer, I want all language-model providers to conform to one client contract, so that the orchestration loop can switch between offline and hosted providers without provider-specific branching.

**Why this priority**: A stable contract is the boundary between the orchestrator and model providers and prevents provider details from leaking into workflow logic.

**Independent Test**: Type-check or otherwise validate both client implementations against the same asynchronous client contract and invoke them through that contract.

**Acceptance Scenarios**:

1. **Given** a client implementation, **When** it is supplied to an orchestrator component expecting the common contract, **Then** the component can submit a prompt using the contract without knowing the provider.
2. **Given** a client response, **When** the response is returned to the orchestrator, **Then** it has content plus optional prompt and completion token counts and does not expose provider-specific response objects.

### User Story 3 - Call Gemini with environment-managed credentials (Priority: P2)

As an operator running the hosted configuration, I want the Gemini client to obtain its credential from an environment variable, so that the API key is not embedded in source code or passed through application logic.

**Why this priority**: Hosted model access is needed for production-like behavior, while environment-managed credentials are a core security boundary.

**Independent Test**: Configure the required environment variable with a test credential, construct the hosted client, and verify that a model request is made through the provider boundary; remove the variable and verify that construction or invocation fails explicitly.

**Acceptance Scenarios**:

1. **Given** the required API-key environment variable is set, **When** the hosted client is initialized and invoked, **Then** it uses that credential through the provider SDK and returns the agreed textual result.
2. **Given** the required API-key environment variable is absent, **When** the hosted client is initialized or invoked, **Then** it fails explicitly with an actionable configuration error.
3. **Given** a hosted request fails at the provider boundary, **When** the client reports the failure, **Then** the error does not include the API key or other secret values.

## Edge Cases

- The required credential environment variable is missing, empty, or whitespace-only.
- The provider returns an empty response or a response that cannot be converted to the agreed textual result.
- The provider request times out or returns an authentication, rate-limit, or service error.
- A caller passes an empty prompt or a prompt containing sensitive content; the client must not log the prompt or credentials by default.
- The offline client is used in a process where network access is unavailable; it must remain fully usable without network access.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose an asynchronous language-model client contract with `generate(prompt: str, **kwargs)` returning an `LLMResponse`.
- **FR-002**: The system MUST provide an offline client that conforms to the common client contract and never requires network access or a provider credential.
- **FR-003**: The offline client MUST support deterministic, caller-configurable responses for automated tests.
- **FR-004**: The offline client MUST define explicit behavior for requests made without a configured response and MUST NOT silently call a hosted provider.
- **FR-005**: The system MUST provide a Gemini-backed client that conforms to the common client contract.
- **FR-006**: The Gemini-backed client MUST read its API key from an environment variable and MUST NOT require the key to be hard-coded or logged.
- **FR-007**: The Gemini-backed client MUST fail explicitly when its required environment variable is missing or blank.
- **FR-008**: Both clients MUST return an `LLMResponse` containing `content: str`, `prompt_tokens: Optional[int]`, and `completion_tokens: Optional[int]`.
- **FR-009**: Both clients MUST surface provider or configuration failures explicitly and MUST NOT convert failures into successful-looking results.
- **FR-010**: Client errors and diagnostics MUST NOT expose API keys or other credential values.
- **FR-011**: The client boundary MUST allow the orchestrator to depend on the common contract rather than on a specific provider implementation.
- **FR-012**: The Gemini-backed client MUST read its API key from `GEMINI_API_KEY` and its model name from `LLM_MODEL`.

### Key Entities *(include if feature involves data)*

- **LLM Client Contract**: The provider-independent capability used by the orchestrator to submit prompts and receive textual results.
- **Offline Client Configuration**: The deterministic response and related options used to run without network access or credentials.
- **Hosted Client Configuration**: The provider selection and environment-managed credential required to call Gemini.
- **LLMResponse**: The provider-independent response containing textual content and optional prompt/completion token counts for run logging.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of automated offline-client tests complete without network access, external credentials, or provider service availability.
- **SC-002**: 100% of supported client implementations pass the same contract-conformance test suite.
- **SC-003**: 100% of hosted-client initialization attempts without a valid credential fail explicitly and do not issue a provider request.
- **SC-004**: 0 test or application log records expose the configured API key during successful requests or handled failures.
- **SC-005**: At least 95% of repeated offline-client calls with identical configuration and prompt return the same result across a test run.

## Assumptions

- The orchestrator consumes a textual result; structured agent-to-agent payloads remain governed by the existing Pydantic contracts.
- The Gemini provider SDK and model selection details will be chosen during planning to match the repository’s supported dependency and configuration conventions.
- The Gemini client uses `GEMINI_API_KEY` for credentials and `LLM_MODEL` for model selection.
- Credential rotation and secret storage infrastructure are outside this feature; this feature only prevents credentials from being embedded in source or logs.
- Provider retry policy, timeout values, and rate-limit handling will follow existing application conventions or be defined during planning without changing the client contract.
