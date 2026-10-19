# Implementation Plan: AgentIA v2 Frontend Dashboard MVP

**Branch**: `009-frontend-dashboard` | **Date**: 2026-10-11 | **Spec**: [.speckit/specs/009-frontend-dashboard/spec.md](spec.md)

**Input**: Feature specification from `.speckit/specs/009-frontend-dashboard/spec.md` and legacy extraction report from `/home/gjanampa/Projects/AI_AGENTS/agentIA/docs/frontend_legacy_extraction.md`.

## Summary

Build the AgentIA v2 Frontend Visual Dashboard as a React 18+ SPA bundled with Vite, TypeScript, Tailwind CSS, and `lucide-react`. The application interfaces with the AgentIA FastAPI backend at `http://localhost:8000`:
1. Provides a Blueprint Submission interface (`BlueprintRunTrigger`) to submit JSON blueprints with workspace configurations to `POST /v1/blueprint/run`.
2. Provides an automated status-polling engine (`useStatusPolling` / `blueprintService`) querying `GET /v1/blueprint/status/{trace_id}`.
3. Renders a reactive 4-stage visual state machine (`LangGraphStateVisualizer`) tracking the loop: `Validate` -> `Verify` -> `Repair (1..3 bounded)` -> `Success` / `NO_FIX`.
4. Renders 4-column KPI cards and Mac-style real-time log terminal (`RealtimeTerminal`) with honest diagnostic indicators (`SKIPPED_BY_CHOICE`, `NO_FIX`, `PASSED`).

## Technical Context

**Language/Version**: TypeScript 5.7+ (strict mode, ES2022)  
**Framework**: React 18.3+ (`react`, `react-dom`)  
**Bundler / Tooling**: Vite 6.x (`@vitejs/plugin-react`)  
**Styling**: Tailwind CSS 3.4.x, PostCSS, Autoprefixer, `clsx`, `tailwind-merge`  
**Icon Library**: `lucide-react` (matching legacy matrix)  
**Testing**: Vitest 3.x / React Testing Library / `@testing-library/jest-dom`  
**Backend API**: FastAPI on `http://localhost:8000` (`/v1/blueprint/run`, `/v1/blueprint/status/{trace_id}`)  
**Design Tokens**: TCS Blue (`#0076CE`), Navy (`#0A192F`), Slate Neutrals, JetBrains Mono font, Dark Terminal Canvas (`#020617`)

## Constitution Check

*GATE: AgentIA v2 Constitution Principles Verified*
- **Principle 1 (Specs before code)**: Specification and checklist completed in `.speckit/specs/009-frontend-dashboard/`.
- **Principle 5 (Measurable claims only)**: Exact metrics displayed (attempt counts, pass counts, status); no fabricated passes.
- **Principle 7 (Bounded loops)**: Repair counter hard-capped at 3 attempts with `NO_FIX` boundary.
- **Principle 11 (Observability everywhere)**: `trace_id` visible in header, KPI cards, and terminal logs.
- **Principle 12 (Secrets stay out of source)**: `x-api-key` is user-provided or environment-configured; never hardcoded.

## Project Structure

```text
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── index.css
│   ├── types/
│   │   └── blueprintGraph.ts
│   ├── services/
│   │   └── blueprintService.ts
│   ├── hooks/
│   │   └── useStatusPolling.ts
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   └── KpiGrid.tsx
│   │   ├── orchestration/
│   │   │   ├── BlueprintRunTrigger.tsx
│   │   │   ├── LangGraphStateVisualizer.tsx
│   │   │   ├── NodeCard.tsx
│   │   │   ├── BoundedRepairCounter.tsx
│   │   │   └── RealtimeTerminal.tsx
│   │   └── common/
│   │       ├── StatusPill.tsx
│   │       └── Card.tsx
│   └── test/
│       ├── setup.ts
│       ├── BlueprintRunTrigger.test.tsx
│       ├── LangGraphStateVisualizer.test.tsx
│       └── blueprintService.test.ts
```

## Phase Plan

- **Phase 1**: Frontend Scaffolding (Vite, React, TypeScript, Tailwind CSS, Lucide icons, Vitest).
- **Phase 2**: Backend API adjustments (CORS middleware & status endpoints in `app/main.py` if needed).
- **Phase 3**: Type definitions & API Service (`blueprintGraph.ts`, `blueprintService.ts`, `useStatusPolling.ts`).
- **Phase 4**: Visual UI Components (`BlueprintRunTrigger`, `LangGraphStateVisualizer`, `KpiGrid`, `RealtimeTerminal`, `Header`).
- **Phase 5**: Component & Unit Testing (TDD loop with Vitest).
- **Phase 6**: End-to-End Build & Integration Verification.

