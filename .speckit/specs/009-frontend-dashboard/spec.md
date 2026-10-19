# Feature Specification: AgentIA v2 Frontend Dashboard MVP

**Feature Branch**: `009-frontend-dashboard`

**Created**: 2026-10-11

**Status**: Ready for Implementation

**Input**: User description: "Build the new visual dashboard for AgentIA v2 to track the Orchestrator LangGraph state machine with JSON blueprint submission to POST /v1/blueprint/run, trace_id status-polling, and real-time visual pipeline loop (Validate -> Verify -> Repair -> Success/NO_FIX) matching legacy styling."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit Blueprint and Trigger Orchestration (Priority: P1)

As a software architect or developer, I want to input and submit a JSON blueprint along with workspace configuration to the orchestrator API, so that I can initiate autonomous code synthesis, verification, and repair.

**Why this priority**: Initiating the blueprint execution is the fundamental entry point of the entire AgentIA v2 platform.

**Independent Test**: Mount the BlueprintRunTrigger component, enter valid blueprint JSON with workspace parameters, submit to POST `/v1/blueprint/run`, and verify that the API request is issued with the correct payload and headers, returning an initial run state with a `trace_id`.

**Acceptance Scenarios**:

1. **Given** valid JSON in the blueprint input area and valid workspace parameters, **When** the user clicks "Run Orchestrator", **Then** the application submits a POST request to `http://localhost:8000/v1/blueprint/run` carrying `workspace_dir`, `blueprint`, and `x-api-key` header.
2. **Given** an invalid or syntactically malformed JSON blueprint, **When** the user attempts to submit, **Then** the UI halts submission, highlights the syntax error, and prevents invalid API calls.
3. **Given** a successful submission response containing a `trace_id`, **When** the response is received, **Then** the UI captures the `trace_id`, transitions the visual state to active, and begins monitoring.

---

### User Story 2 - Visualize LangGraph State Machine Loop (Priority: P1)

As an operator, I want to visually track the execution of the 4 LangGraph nodes (`Validate` -> `Verify` -> `Repair` -> `Success` / `NO_FIX`) with real-time status indicators and KPI metrics, so that I have immediate situational awareness of the orchestration lifecycle.

**Why this priority**: Visualizing the state transitions and bounded repair cycles satisfies AgentIA Constitution Principle V (Honest Diagnostics & Bounded Loops).

**Independent Test**: Provide mock or live execution states transitioning from Validate -> Verify -> Repair (iteration 1..3) -> Success/NO_FIX, and verify that the visual node cards, connecting indicators, repair attempt counter, and 4-column KPI cards render the corresponding active, passed, repairing, or failed states.

**Acceptance Scenarios**:

1. **Given** a run in progress, **When** the orchestrator enters the `Validate` node, **Then** the Validate card displays active spinning indicator (`RefreshCw`), transitioning to emerald checkmark (`CheckCircle2`) upon structural validation success.
2. **Given** verification failures during the `Verify` node, **When** the orchestrator transitions to `Repair`, **Then** the Repair node activates with amber treatment (`RotateCcw`), and the bounded repair gauge increments (e.g., `Attempt 1 of 3`).
3. **Given** a successful fix verification, **When** the graph reaches completion, **Then** the terminal node displays `SUCCESS` with an emerald summary card.
4. **Given** repair iterations reach the constitutional limit (3 attempts) without passing, **When** the graph halts, **Then** the terminal node displays `NO_FIX` with high-visibility rose diagnostic banner adhering to honest reporting rules.

---

### User Story 3 - Poll Execution Status by Trace ID (Priority: P2)

As a dashboard user, I want the UI to poll the execution status using the returned `trace_id`, so that I can track asynchronous or long-running orchestrator jobs to completion without lost state.

**Why this priority**: Orchestration runs involving compilation and sandboxed testing take time; reliable status polling ensures resilience against transient network lags.

**Independent Test**: Trigger a run that returns `trace_id: "trace-xyz"`, simulate polling requests to `GET /v1/blueprint/status/trace-xyz` returning `RUNNING` followed by `SUCCESS`, and verify that the dashboard updates at each interval until a terminal state is reached.

**Acceptance Scenarios**:

1. **Given** an active `trace_id`, **When** polling begins, **Then** the client queries `http://localhost:8000/v1/blueprint/status/{trace_id}` at configurable intervals (e.g. 1000ms).
2. **Given** the poll response returns updated attempt counts or node status, **When** the payload is parsed, **Then** the state visualizer immediately reflects the new state.
3. **Given** the poll response indicates a terminal status (`SUCCESS`, `NO_FIX`, or `ERROR`), **When** detected, **Then** polling terminates and final metrics are frozen.

---

### User Story 4 - Honest Diagnostic Terminal and 4-Column KPI Grid (Priority: P2)

As a quality assurance engineer, I want to inspect raw execution logs in a Mac-style terminal console and see honest verification metrics, so that I can diagnose issues without disguised failures or fake pass states.

**Why this priority**: Complies strictly with Constitution Principle 5 (Measurable claims only) and Principle 11 (Observability everywhere).

**Independent Test**: Load a test run with Surefire compiler logs and test failure traces, verify the terminal displays color-coded logs, and confirm the 4 KPI cards (Current Phase, Sandbox Status, Repair Iteration, Constitutional Limit) reflect actual data.

**Acceptance Scenarios**:

1. **Given** verification or build logs in the response, **When** displayed in the Mac terminal console, **Then** lines are formatted with monospaced typography (`JetBrains Mono` / `Fira Code`), dark canvas (`#020617`), and window control dots.
2. **Given** a run where verification was skipped or interrupted, **When** the KPI card renders, **Then** it displays `SKIPPED_BY_CHOICE` or `INTERRUPTED` without falsely claiming tests passed.

---

## Edge Cases

- **Malformed JSON Blueprint**: User pastes invalid JSON; editor flags error with line number and disables submit button.
- **Empty or Missing Workspace Directory**: Workspace path validation halts submission with clear error helper.
- **Missing or Invalid API Key**: Backend responds with 401 Unauthorized; UI displays non-disclosing authentication banner and prompts user for configured `x-api-key`.
- **Backend Unreachable (Network Error / 502 / 503)**: Polling gracefully handles transient network errors with exponential backoff and displays an explicit connection alert.
- **Constitutional Limit Reached (`NO_FIX`)**: Repair count hits 3/3; dashboard locks into `NO_FIX` state with clear diagnostic failure reasons and AST diff summaries.
- **Unknown Trace ID on Polling**: Polling endpoint returns 404; polling halts and reports that the trace could not be found.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single-page React 18+ application built with Vite and Tailwind CSS matching the extracted design tokens (TCS Modern Enterprise palette `#0076CE`, Slate neutrals, dark mode support).
- **FR-002**: The system MUST render a Blueprint Trigger component allowing users to view, edit, and submit JSON blueprints along with `workspace_dir` and `x-api-key`.
- **FR-003**: The system MUST pre-load a default valid AgentIA blueprint template to allow immediate testing without manual JSON creation.
- **FR-004**: The system MUST submit blueprint requests to `POST http://localhost:8000/v1/blueprint/run` with the configured `x-api-key` header.
- **FR-005**: The system MUST extract the returned `trace_id` and start an automated polling mechanism querying `GET http://localhost:8000/v1/blueprint/status/{trace_id}`.
- **FR-006**: The system MUST render a 4-stage visual pipeline representing the LangGraph state machine:
  1. `Validate`: Structural schema & story validation
  2. `Verify`: Hermetic sandbox compilation & JUnit test suite
  3. `Repair`: Bounded auto-repair loop with AST diagnostics
  4. `Terminal`: Final verdict (`SUCCESS` or `NO_FIX`)
- **FR-007**: Each pipeline node MUST render distinct icons from `lucide-react` matching the extraction matrix (`Clock`, `RefreshCw`, `CheckCircle2`, `RotateCcw`, `ShieldAlert`, `AlertCircle`).
- **FR-008**: The system MUST render a Bounded Repair Counter displaying the current attempt out of the constitutional maximum (capped at 3).
- **FR-009**: The system MUST display a 4-column KPI metric grid:
  1. Current Phase (`Fase Actual`)
  2. Sandbox Status (`Estado del Sandbox`)
  3. Repair Iteration (`Iteración Auto-Reparación`)
  4. Constitutional Limit (`Límite Constitucional`: Fixed Máx 3)
- **FR-010**: The system MUST render a Mac-style dark console terminal (`RealtimeTerminal`) with colored window controls (`rose`, `amber`, `emerald` dots) and monospaced log stream.
- **FR-011**: The system MUST enforce honest diagnostics: `NO_FIX`, `ERROR`, `SKIPPED_BY_CHOICE`, and `INTERRUPTED` statuses MUST be clearly distinguished from `PASSED`/`SUCCESS`.
- **FR-012**: The system MUST support manual trace query input, allowing operators to look up previously recorded runs by trace ID.
- **FR-013**: The system MUST provide comprehensive unit and component tests with Vitest and React Testing Library verifying state transitions, form submission, and status polling.
- **FR-014**: The system MUST pass static type checking and production build without errors.

---

### Key Entities

- **BlueprintRunRequest**: Object containing `workspace_dir`, `blueprint` dictionary, and optional `trace_id`.
- **OrchestrationState**: Core state returned by `/v1/blueprint/run` containing `trace_id`, `attempts`, `validation`, `verification`, `repair`, and `outcome`.
- **RunStatusRecord**: Polling entity containing `trace_id`, `blueprint_name`, `status` (`RUNNING`, `SUCCESS`, `NO_FIX`, `ERROR`), and `repair_attempts`.
- **LangGraphNodeState**: Frontend presentation model tracking node identifier, label, description, status (`IDLE`, `ACTIVE`, `PASSED`, `REPAIRING`, `SUCCESS`, `NO_FIX`), and diagnostics.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of user-submitted blueprints are validated locally for valid JSON before issuing network requests.
- **SC-002**: 100% of successful run submissions initiate automatic status-polling within 500ms of response receipt.
- **SC-003**: All 4 LangGraph nodes render with correct semantic tokens and `lucide-react` icons corresponding to their active, passed, or failed status.
- **SC-004**: Repair iteration counter strictly reflects values $0 \le n \le 3$, and halts with `NO_FIX` if $n = 3$ without verified pass.
- **SC-005**: 100% of automated frontend component tests pass in Vitest.
- **SC-006**: Production build (`npm run build`) completes with zero TypeScript or bundler errors.

---

## Assumptions

- The AgentIA FastAPI backend runs on `http://localhost:8000`.
- The backend authentication header is `x-api-key` and uses the value configured in `.env` (`ORCHESTRATOR_API_KEY`).
- A status polling endpoint `GET /v1/blueprint/status/{trace_id}` is exposed to query execution run progress.
- Node.js version is v24+ with npm available in the environment.

