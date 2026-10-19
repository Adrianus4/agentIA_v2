# Tasks: AgentIA v2 Frontend Dashboard MVP

**Input**: Design documents from `.speckit/specs/009-frontend-dashboard/` (spec.md, plan.md)
**Prerequisites**: spec.md (required), plan.md (required)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: US1 (Blueprint Submit), US2 (State Machine Visualizer), US3 (Trace Polling), US4 (Terminal & KPIs)

---

## Phase 1: Setup & Scaffolding

- [x] T001 Initialize `frontend/` directory with `package.json`, Vite 6, React 18, TypeScript 5, Tailwind CSS 3.4, and Lucide React.
- [x] T002 Configure `vite.config.ts` with React plugin, test configuration, and dev proxy for `/v1` to `http://localhost:8000`.
- [x] T003 Configure `tailwind.config.js` with TCS Brand Blue (`#0076CE`), Navy (`#0A192F`), and Slate palette.
- [x] T004 Setup Vitest environment and test setup in `src/test/setup.ts`.

---

## Phase 2: Contracts, Types & Backend Alignment

- [x] T005 Create TypeScript interface contracts in `frontend/src/types/blueprintGraph.ts` matching `contracts/models.py`.
- [x] T006 Ensure FastAPI `app/main.py` has CORS middleware and status endpoints (`/v1/blueprint/status/{trace_id}`).

---

## Phase 3: Core Services & Hooks (TDD: Test -> Code)

- [x] T007 [P] [US1] Write test and implement `blueprintService.ts` for blueprint submission (`POST /v1/blueprint/run`) and trace queries (`GET /v1/blueprint/status/{trace_id}`).
- [x] T008 [P] [US3] Write test and implement `useStatusPolling.ts` for automated status polling using `trace_id`.

---

## Phase 4: UI Components (TDD: Test -> Code)

- [x] T009 [US1] Write test and implement `BlueprintRunTrigger.tsx` with JSON editor, syntax validation, preset selector, and run button.
- [x] T010 [US2] Write test and implement `NodeCard.tsx` and `LangGraphStateVisualizer.tsx` displaying the 4 nodes (`Validate` -> `Verify` -> `Repair` -> `Success`/`NO_FIX`) with legacy styling and Lucide icons.
- [x] T011 [US4] Write test and implement `KpiGrid.tsx` (Current Phase, Sandbox Status, Repair Iteration, Constitutional Limit).
- [x] T012 [US4] Write test and implement `RealtimeTerminal.tsx` with Mac window controls and monospaced log streaming.
- [x] T013 Implement header, app layout, and main page in `App.tsx`.

---

## Phase 5: Verification & Polish

- [x] T014 Run full frontend test suite (`npm test`).
- [x] T015 Run production build (`npm run build`) and type check.
- [x] T016 Verify backend test suite (`uv run --extra dev pytest tests/test_main.py`).

