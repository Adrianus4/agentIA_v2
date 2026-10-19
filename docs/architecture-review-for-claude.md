# AgentIA v2 Architecture and Implementation Review

Date: 2026-10-12

## Executive summary

AgentIA v2 is a FastAPI + React/Vite application that exposes a blueprint execution
boundary and visualizes a bounded generation/verification/repair loop. The current
backend is intentionally narrower than the legacy AgentIA v1 UI: v2's typed contract
currently supports Gemini only, while v1 exposed Gemini, Groq, OpenAI, DeepSeek, and
an offline mock selector.

The startup issue observed during review was not a backend import failure in the
current checkout. The backend reached `Application startup complete`. The actionable
problem was a port mismatch: `start.sh` advertised port 5173 while
`frontend/vite.config.ts` configured Vite for port 3000. The deployment-style
`scripts/start.sh` also depended on the caller's current directory and invoked a
bare `uvicorn`. Both scripts were corrected.

## Runtime architecture

```text
Browser
  |
  | React/Vite dashboard
  | - Workspace tabs
  | - LLM configuration
  | - Blueprint form
  | - State visualizer and polling
  v
FastAPI /v1/blueprint/run
  |
  v
OrchestratorGraph
  |
  +--> validation
  +--> optional GenerationPipeline
  |      +--> EntityGenerator
  |      +--> ResourceGenerator
  |      +--> TestGenerator
  |      +--> safe workspace materialization
  |
  +--> verification / LocalDockerRunner
  +--> bounded repair / ScopedRepairService
  +--> apply_patch
  |
  v
RunRepository (SQLite/aiosqlite) + serialized status response
```

Primary source anchors:

- [app/main.py](/home/gjanampa/Projects/AI_AGENTS/agentIA_v2/app/main.py): HTTP
  boundary, authentication, request-scoped LLM configuration, and run persistence.
- [app/orchestrator/graph.py](/home/gjanampa/Projects/AI_AGENTS/agentIA_v2/app/orchestrator/graph.py):
  existing asynchronous orchestration state and optional generation node.
- [app/orchestrator/generation.py](/home/gjanampa/Projects/AI_AGENTS/agentIA_v2/app/orchestrator/generation.py):
  sequential generation coordination.
- [app/orchestrator/pipeline.py](/home/gjanampa/Projects/AI_AGENTS/agentIA_v2/app/orchestrator/pipeline.py):
  synchronous end-to-end generation, verification, and repair pipeline used by
  integration tests.
- [contracts/models.py](/home/gjanampa/Projects/AI_AGENTS/agentIA_v2/contracts/models.py):
  Pydantic contracts and the current `LLMConfiguration` provider boundary.
- [frontend/src/App.tsx](/home/gjanampa/Projects/AI_AGENTS/agentIA_v2/frontend/src/App.tsx):
  dashboard state, status polling, workspace navigation, and submission wiring.
- [frontend/src/components/orchestration/BlueprintRunTrigger.tsx](/home/gjanampa/Projects/AI_AGENTS/agentIA_v2/frontend/src/components/orchestration/BlueprintRunTrigger.tsx):
  blueprint authoring and dispatch.
- [frontend/src/components/orchestration/LlmConfigurationPanel.tsx](/home/gjanampa/Projects/AI_AGENTS/agentIA_v2/frontend/src/components/orchestration/LlmConfigurationPanel.tsx):
  restored dedicated LLM configuration tab.

## Program implementation logic

1. The browser builds a blueprint from the assisted Quarkus form or JSON editor.
2. The UI adds non-secret LLM metadata (`provider`, `model`, and optional endpoint)
   to the blueprint. The API key is sent as a transient top-level `llm_api_key`.
3. FastAPI authenticates the request with `ORCHESTRATOR_API_KEY`.
4. If LLM metadata exists, FastAPI constructs `LLMConfiguration`. Unsupported
   providers are rejected instead of being accepted and failing later.
5. The graph validates and normalizes the blueprint. `domainModels` are normalized
   into the generator-compatible entity shape.
6. When `ORCHESTRATOR_GENERATION_ENABLED` is enabled, generation runs in the order
   entity -> resource/repository -> tests. Generated paths are restricted to the
   requested workspace.
7. Verification executes `mvn clean test` through the hermetic runner.
8. Failed verification invokes the scoped repair service. Patches are applied only
   within the allowed generated paths. The repair loop stops after three attempts.
9. The final state is persisted as `SUCCESS`, `NO_FIX`, or `ERROR`; status polling
   exposes state without exposing the LLM key.

## Legacy AgentIA v1 comparison

The legacy implementation was found in the sibling project
[`agentIA`](/home/gjanampa/Projects/AI_AGENTS/agentIA), not in the v2 git tree.
Its distribution included:

- Sidebar session list and “Nuevo Microservicio”
- Workspace tabs: Blueprints, Resumen, Requisitos, Arquitectura, Modelos & SQL,
  Código & Fix, Calidad SAST, DevOps & Demo, Entrega Git
- A separate Monitor Live surface
- A settings drawer for LLM provider, API key, model, connection state, and latency

The v2 UI previously collapsed LLM configuration into the blueprint form. This
review restores the missing distribution contract with a workspace navigation strip
and a dedicated **Motor LLM** tab. The existing dashboard and blueprint flow remain
available under the same page, so this is an additive migration rather than a
replacement of the v2 execution visualizer.

## Compatibility boundary and remaining gap

The legacy provider selector cannot be copied verbatim into v2 without backend work.
The v2 contract declares `provider: Literal["gemini"]`, and the active client is
Gemini-backed. The restored UI therefore presents Gemini as the valid provider and
labels other v1 providers as requiring backend adapters. This avoids a misleading
selector that accepts values the v2 API cannot execute.

To restore all v1 providers, Claude should review and implement:

1. A provider enum and adapter/factory in `app/core/llm/client.py`.
2. Provider-specific endpoint and credential validation.
3. A backend connection-verification endpoint.
4. Per-provider model capability metadata.
5. Tests proving that credentials never enter state persistence or logs.

## Startup corrections

- `start.sh` now defaults to `FRONTEND_PORT=3000`, matching Vite, and passes the
  configured port explicitly. Operators may still set `FRONTEND_PORT=5173`.
- `scripts/start.sh` now resolves the repository root before launching and uses
  `uv run uvicorn`, making it safe to invoke from another working directory.
- `start.bat` reports the configurable `FRONTEND_PORT` consistently.

## Verification performed

- Backend full suite: 135 tests passed and exited cleanly.
- Frontend suite: 24 tests passed.
- Frontend production build: passed.
- Mypy: passed.
- Focused Ruff checks for the pipeline and new tests: passed.
## SC-1 scaffolding boundary

Official framework scaffolding is now opt-in and profile-owned. The deterministic
extension mapper runs before the networked `SubprocessScaffolder`; commands are
constructed as argv arrays and output is collected as in-workspace manifest
evidence. The existing `LocalDockerRunner` remains a separate offline boundary
and receives `mvn -o -q test-compile` for scaffold verification before business
generation. Requests without `scaffold: true` use the existing generation and
repair loop unchanged.
