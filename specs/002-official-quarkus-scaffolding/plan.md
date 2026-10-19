# Implementation Plan: Official Quarkus Scaffolding

**Branch**: `002-official-quarkus-scaffolding` | **Date**: 2026-10-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Add an optional official-tool scaffolding stage to AgentIA v2. A profile-owned
catalog derives validated extensions from a blueprint, builds a fixed argv command,
executes it in an isolated networked scaffolder role, records manifest evidence, and
passes the result to the existing offline verifier before LLM generation. Existing
requests without scaffold configuration continue on the current path.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.12; TypeScript 5.7

**Primary Dependencies**: Pydantic, FastAPI, aiosqlite, pytest, Docker SDK/CLI boundary,
React, Vite

**Storage**: Profile YAML and generated workspace files; run metadata in SQLite

**Testing**: pytest, mypy, Ruff, Vitest, TypeScript build

**Target Platform**: Linux/macOS development; Linux container execution

**Project Type**: Web application with FastAPI orchestration service and React dashboard

**Performance Goals**: Deterministic extension derivation is in-process; scaffold and
verification are bounded by explicit process timeouts.

**Constraints**: No shell command strings; no LLM-controlled argv; network only in the
scaffolder role; verifier remains offline; output stays under the workspace root;
repair remains capped at three attempts.

**Scale/Scope**: Initial Quarkus/Maven profile and curated extension catalog; additive
backward-compatible contracts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Pass:

- Specs and acceptance scenarios exist before implementation.
- Typed Pydantic contracts will be added before runtime code.
- Extension derivation is deterministic and profile-driven.
- Process execution is bounded and represented as argv.
- Offline verification and patch safety remain unchanged.
- No secret is introduced into scaffold requests, manifests, logs, or responses.

No gate violations identified.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

app/
├── core/llm/
├── orchestrator/
└── main.py
agents/
├── profiles/
├── scaffolder/
└── verifier/
contracts/
tests/
├── agents/
├── orchestrator/
└── contract/
```

**Structure Decision**: The existing single-repository web application structure is retained. New scaffold
contracts live in `contracts/models.py`; pure derivation belongs with orchestration
logic; process execution belongs under `agents/scaffolder/`; profile data remains the
source of framework-specific values; tests mirror contract, agent, and orchestrator
boundaries.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | The feature fits the existing application and agent boundaries. |
