# Research: Unified Orchestrator and LLM Configuration

## Decision: Extend the existing orchestration graph with explicit pipeline stages

**Rationale**: `OrchestratorGraph` already owns validation, generation injection, verification, repair, and safe file writing. Extending that seam avoids duplicating retry and contract logic while preserving existing endpoint behavior.

**Alternatives considered**: A second independent state machine would duplicate state and make existing tests less meaningful; replacing the current graph would risk breaking the frontend status contract.

## Decision: Keep LLM credentials request-scoped and model metadata explicit

**Rationale**: The current client reads credentials from environment variables and the constitution forbids secrets in source or logs. The UI can collect a transient credential while sending provider/model metadata in the blueprint; the backend remains responsible for credential resolution.

**Alternatives considered**: Persisting credentials in local storage or run records was rejected because it violates secret hygiene. Supporting multiple provider SDKs in this change was rejected because only the Gemini-compatible client exists today.

## Decision: Diagnose test hangs as teardown/resource leaks

**Rationale**: The observed process reports all tests passed, then remains blocked on a futex. This indicates post-test cleanup rather than a test assertion failure. The validation command will use an explicit timeout and the implementation will close owned async resources and disable unwanted telemetry/plugin background work in the test environment.

**Alternatives considered**: Treating the run as successful solely because the summary appeared was rejected; CI needs an exit code.

## Decision: Preserve the existing three-attempt repair budget

**Rationale**: The project constitution requires a maximum of three attempts, and the existing graph already implements that bound.

**Alternatives considered**: An unlimited retry count was rejected as unsafe and contrary to the constitution.
