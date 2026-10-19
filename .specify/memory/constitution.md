# AgentIA v2 Constitution

## I. Core Engineering Principles
1. **Specs before code:** No code is written without a concrete contract or spec.
2. **Tests first:** Every acceptance criterion requires an automated test seen failing before implementation.
3. **Contracts first:** All agent components communicate strictly via typed Pydantic models in `contracts/models.py`.
4. **Deterministic over generative:** Use static parsing, templates, and compiler outputs over LLM generation wherever possible.
5. **Measurable claims only:** Every verification step must yield a concrete, parseable metric or exit code. Never invent or assume values.

## II. Agent Safety & Boundaries
6. **Validate every LLM output:** All LLM completions must parse through a Pydantic model with a maximum of 2 retries.
7. **Bounded loops:** The repair cycle is capped at 3 attempts. If compilation fails after attempt 3, return `NO_FIX`.
8. **Framework knowledge lives in profiles:** Agents are framework-agnostic. No Quarkus or Spring literals (e.g., `@InjectMock`, `@MockBean`, `@Path`) may appear in agent Python code; they must be resolved dynamically from `profiles/*.yaml`.
9. **Patch safety is non-negotiable:** Patches must pass deterministic guards (G1: allowed file paths only; G7: no `pom.xml` modifications without explicit permission). There is no bypass toggle.

## III. Execution & Environment
10. **Hermetic verification:** The compiler runner must run offline (`--network none`) using a read-only Maven cache (`:ro`) and an isolated, temporary copy of the target workspace.
11. **Observability everywhere:** A unique `trace_id` must propagate through every request, response, and log entry. Never log file contents, full source diffs, or secrets.
12. **Secrets stay out of source:** API keys must come from environment variables (`.env`), never committed or logged.
13. **Simplest thing that works:** Implement the minimal viable interface defined in the contracts.
