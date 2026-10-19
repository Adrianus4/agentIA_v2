# Implementation Plan: Unified Orchestrator and LLM Configuration

**Branch**: `001-orchestrator-llm-pipeline` | **Date**: 2026-10-12 | **Spec**: [spec.md](./spec.md)

## Summary

Unify blueprint validation, profile resolution, code generation, verification, and bounded repair behind one orchestration state machine. Add a visible LLM configuration panel to the existing run form, pass only non-secret model metadata through the request, and ensure test processes terminate after completion.

## Technical Context

**Language/Version**: Python 3.11+; TypeScript/React frontend

**Primary Dependencies**: FastAPI, Pydantic, pytest/pytest-asyncio, Vite, React, Vitest

**Storage**: SQLite run records; generated source files in the requested workspace

**Testing**: pytest, ruff, mypy, Vitest, TypeScript build

**Target Platform**: Linux/macOS lab environment and browser

**Project Type**: Web application with FastAPI backend and React frontend

**Performance Goals**: Passing test suites exit within 60 seconds after the final test result; orchestration remains bounded to three verification attempts

**Constraints**: No secret persistence or logging; generated paths stay inside the workspace; verifier uses the existing hermetic policy; no unbounded retries

**Scale/Scope**: One orchestration run per request; current UI run form and backend endpoints remain backward compatible

## Constitution Check

Passes: specs before code; tests for each acceptance path; typed Pydantic boundaries; bounded repair loop; profile-driven framework behavior; safe patch/file guards; trace IDs and secret hygiene. The request-scoped LLM configuration is metadata only in persisted state; credentials remain transient.

## Project Structure

```text
app/
├── core/llm/
├── orchestrator/
└── main.py
agents/
├── blueprint/
├── generator/
├── profiles/
├── repair/
└── verifier/
contracts/
frontend/src/
├── components/orchestration/
├── services/
└── types/
tests/
├── orchestrator/
└── test_main.py
```

**Structure Decision**: Preserve the existing backend/frontend split. The unified pipeline belongs in `app/orchestrator/`; request contracts remain in `contracts/`; the model selector belongs beside the existing blueprint controls; focused integration tests belong in `tests/orchestrator/`.

## Phase 0 Research Decisions

1. Extend the existing orchestration graph rather than create a parallel state machine, preserving endpoint and status compatibility.
2. Keep LLM credentials request-scoped and model metadata explicit; never store credentials in browser storage, run records, logs, or responses.
3. Treat the observed post-summary hang as teardown/resource cleanup; validate with an explicit timeout and isolate telemetry/plugin behavior.
4. Preserve the constitution-mandated three-attempt repair budget.

## Phase 1 Design Gates

- Validation must precede generation.
- Generation must precede verification.
- Generated paths must remain inside the requested workspace.
- Every node boundary must use typed contracts.
- Repair must stop at three verification attempts.
- Test commands must return a deterministic process exit code.
- Existing `/v1/blueprint/run` and `/v1/blueprint/status/{trace_id}` contracts remain compatible.
