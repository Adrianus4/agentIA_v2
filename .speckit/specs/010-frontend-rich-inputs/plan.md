# Implementation Plan: 010-frontend-rich-inputs

## Phase 1: Asset Integration & Header Enhancement
- Copy TCS logos into `frontend/public/` and `frontend/src/assets/`.
- Enhance `Header.tsx` to render the TCS logo `<img src="/tcs-logo-light.png" alt="Tata Consultancy Services" />` with responsive layout and proper styling.

## Phase 2: Rich Form Model & Presets
- Define TypeScript types for Quarkus configurations, natural language business rules, and microservice presets in `frontend/src/types/blueprintGraph.ts`.
- Provide default preset templates for standard enterprise services (Order Service, Payment Service).

## Phase 3: Component Implementation & Dual-Mode UI
- Implement `QuarkusConfigSection.tsx` or incorporate into `BlueprintRunTrigger.tsx` with tabs:
  - Tab 1: "Formulario Inteligente (Requisitos NL & Quarkus)"
  - Tab 2: "Editor JSON Blueprint"
- Connect real-time two-way synchronization: updating form fields immediately builds a valid JSON blueprint conforming to orchestrator expectations.

## Phase 4: Test Suite Verification
- Update `Header.test.tsx` (or `App.test.tsx`) to assert the TCS logo renders.
- Update `BlueprintRunTrigger.test.tsx` to assert that natural language inputs and Quarkus settings correctly update and submit the payload.
- Run `npm test` and ensure all tests pass.

