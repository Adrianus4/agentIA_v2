# Feature Specification: Containerized Orchestrator

**Feature Branch**: `005-containerization`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Provide container infrastructure for the FastAPI orchestrator with environment placeholders, a uv-based production Dockerfile, Compose service configuration, and an executable container entrypoint."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build and run the orchestrator image (Priority: P1)

As an operator, I want to build and start the FastAPI orchestrator in a production-oriented container, so that the service runs consistently without relying on host Python tooling.

**Why this priority**: A reproducible image is the deployment boundary for Track 1.

**Independent Test**: Build the image, start the service, and verify that the application listens on port 8000.

**Acceptance Scenarios**:

1. **Given** the repository source and container configuration, **When** the image is built, **Then** dependency installation completes through `uv`.
2. **Given** a built image, **When** the container starts, **Then** the entrypoint launches the FastAPI application on port 8000.
3. **Given** the running service, **When** port 8000 is accessed through the published port, **Then** the service is reachable.

### User Story 2 - Configure secrets through the environment (Priority: P1)

As an operator, I want the model and API credentials supplied at runtime, so that secrets are not embedded in the image or committed to the repository.

**Why this priority**: Runtime environment configuration is required by the application’s authentication and LLM clients.

**Independent Test**: Inspect the example environment file and Compose configuration, then start with supplied values and verify that the container receives them.

**Acceptance Scenarios**:

1. **Given** `.env.example`, **When** an operator copies it to `.env`, **Then** placeholders exist for `GEMINI_API_KEY`, `LLM_MODEL`, and `ORCHESTRATOR_API_KEY`.
2. **Given** values in `.env`, **When** Compose starts the orchestrator, **Then** those values are passed into the service environment.
3. **Given** the image build context, **When** image contents are inspected, **Then** placeholder or real credentials are not baked into the image.

### User Story 3 - Start the service through one documented command (Priority: P2)

As an operator, I want a dedicated executable entrypoint, so that local Compose and production container execution use the same startup behavior.

**Why this priority**: One startup path reduces configuration drift between environments.

**Independent Test**: Execute the entrypoint in a container-compatible environment and verify it invokes the ASGI server with the expected application and port.

**Acceptance Scenarios**:

1. **Given** the container working directory and installed dependencies, **When `scripts/start.sh` runs, **Then** it starts the application from `app.main`.
2. **Given** an environment override for host or port, **When the entrypoint runs, **Then** the configured values are honored without changing the image.

## Edge Cases

- A required runtime environment variable is missing; the application must retain its explicit configuration failure behavior.
- A `.env` file is absent; Compose must still parse and report missing values clearly rather than silently embedding secrets.
- The host port 8000 is already occupied; startup should fail with the platform’s normal bind error.
- The container receives termination signals; the entrypoint must not hide the server process behind an unnecessary shell process.
- Dependency installation or image build fails; no partially valid production image should be treated as successful.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST provide `.env.example` with placeholders for `GEMINI_API_KEY`, `LLM_MODEL`, and `ORCHESTRATOR_API_KEY`.
- **FR-002**: The repository MUST provide a production-ready `Dockerfile` for the FastAPI orchestrator.
- **FR-003**: The Dockerfile MUST install runtime dependencies using `uv`.
- **FR-004**: The Dockerfile MUST expose port 8000 and start the orchestrator through the dedicated entrypoint.
- **FR-005**: The Dockerfile SHOULD run the service as a non-root user and use a minimal Python runtime base.
- **FR-006**: The repository MUST provide `docker-compose.yml` with an `orchestrator` service.
- **FR-007**: Compose MUST publish host port 8000 to container port 8000.
- **FR-008**: Compose MUST pass `GEMINI_API_KEY`, `LLM_MODEL`, and `ORCHESTRATOR_API_KEY` from runtime environment configuration.
- **FR-009**: The repository MUST provide an executable `scripts/start.sh` entrypoint.
- **FR-010**: The entrypoint MUST launch `app.main:app` on `0.0.0.0:8000` and replace itself with the server process.
- **FR-011**: Container configuration MUST NOT contain real credentials.
- **FR-012**: The configuration MUST be syntactically valid for Dockerfile, shell, and Compose consumers.

### Key Entities *(include if feature involves data)*

- **Orchestrator Image**: The immutable runtime artifact containing application code and installed dependencies.
- **Orchestrator Service**: The Compose service exposing the FastAPI application on port 8000.
- **Runtime Environment**: The externally supplied values for model selection and API credentials.
- **Container Entrypoint**: The executable startup script that launches the ASGI application.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of required container files exist at the specified paths.
- **SC-002**: 100% of required environment variable names appear in the example and Compose configuration without real secret values.
- **SC-003**: The Dockerfile installs dependencies through `uv`, exposes port 8000, and invokes the entrypoint.
- **SC-004**: Compose configuration parses successfully and defines the required port mapping and environment forwarding.
- **SC-005**: The entrypoint passes shell syntax validation and has executable permissions.

## Assumptions

- The service object is `app.main:app`.
- Runtime dependencies are installed directly because the repository currently has no package manifest.
- Compose reads operator-provided values from a local `.env` file or exported environment variables.
- Production deployment may add an external reverse proxy and TLS termination; those are outside this deliverable.

