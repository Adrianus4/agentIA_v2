# Feature Specification: GEN_02_Resource_Repository_Modeler

**Feature Identifier**: `GEN_02_Resource_Repository_Modeler`  
**Feature Branch**: `streamE/gen2-resource-modeler`  
**Target Artifacts**:  
- `agents/generator/prompt.py` (`build_repository_prompt`, `build_resource_prompt`)  
- `agents/generator/resource.py` (`ResourceGenerator`)  
- `agents/generator/__init__.py`  
- `tests/agents/generator/test_prompt.py`  
- `tests/agents/generator/test_resource.py`  
**Contract Authority**: `contracts.models` (`GenerationRequest`, `FileContent`, `FrameworkProfile`)  
**Status**: Pending Review  
**Date**: 2026-10-12  

---

## 1. Executive Summary & Purpose

The **Gen-2 Resource & Repository Modeler microservice** is the second stage of the Generation Graph in AgentIA v2. Its purpose is to ingest a validated architectural blueprint (`request.blueprint`) alongside an active framework profile (`FrameworkProfile`), and synthesize the Data Access layer (Repositories/DAOs) and REST Controllers (Resources) for all defined entities.

In accordance with the **AgentIA v2 Constitution**:
1. **Rule 1 (Specs before code)**: Specification must be defined and reviewed prior to test and code authoring.
2. **Rule 2 (Tests first)**: Every requirement and acceptance criterion is verified against failing automated unit tests (TDD Red phase) before implementation.
3. **Rule 3 (Contracts first)**: All inputs, outputs, and intermediate structures communicate strictly via typed Pydantic models in `contracts/models.py` (`GenerationRequest`, `FileContent`, `FrameworkProfile`).
4. **Rule 4 (Deterministic over generative)**: Destination file paths, package directory structures (`.../repository/{Entity}Repository.java`, `.../resource/{Entity}Resource.java`), and prompt injection logic are computed deterministically. The LLM is used solely to generate framework-compliant Java source code based on entity schemas and user stories.
5. **Rule 6 (Validate every LLM output)**: LLM completions are sanitized (markdown code fences stripped) and encapsulated into typed `FileContent` models.
6. **Rule 8 (Framework knowledge lives in profiles)**: Agents must be completely framework-agnostic. No Quarkus or Spring literals (such as `@Path`, `@GET`, `@POST`, `@Transactional`, `@ApplicationScoped`, `jakarta.ws.rs.*`, `jakarta.transaction.*`, `org.springframework.*`) may appear in agent Python code; they must be resolved dynamically from `profile.concepts` and `profile.forbidden_imports`.
7. **Rule 11 (Observability everywhere)**: Requests support an optional `trace_id` propagating through the generation lifecycle.
8. **Rule 13 (Simplest thing that works)**: Minimal viable interface conforming strictly to the requested signatures.

---

## 2. API Contracts & Function Signatures

### 2.1 Existing Contracts (`contracts/models.py`)

No modifications to `contracts/models.py` are required. The service uses existing models imported exclusively from `contracts.models`:
- `GenerationRequest`:
  ```python
  class GenerationRequest(BaseModel):
      blueprint: dict[str, Any]
      trace_id: str | None = None
  ```
- `FileContent`:
  ```python
  class FileContent(BaseModel):
      path: str
      content: str | None = None
      digest: str | None = None
  ```
- `FrameworkProfile`:
  Contains `framework`, `framework_version`, `java_version`, `build_tool`, `concepts`, `forbidden_imports`, `pitfalls`, etc.

### 2.2 Prompt Builders (`agents/generator/prompt.py`)

```python
from typing import Any
from contracts.models import FrameworkProfile

def build_repository_prompt(profile: FrameworkProfile, entity_def: dict[str, Any]) -> str:
    """
    Construct an LLM prompt that dynamically injects framework transactional and persistence conventions
    from profile.concepts["transactional"] and profile.forbidden_imports.
    Instructs the LLM to output ONLY raw Java code for the repository/DAO class.
    Zero framework-specific literals may be hardcoded in Python code.
    """

def build_resource_prompt(profile: FrameworkProfile, entity_def: dict[str, Any], user_stories: list[dict[str, Any]] | list[Any]) -> str:
    """
    Construct an LLM prompt that dynamically injects framework REST endpoint conventions
    from profile.concepts["rest_endpoint"] (and dependency injection / transactional concepts if present),
    forbidden imports from profile.forbidden_imports, and target user stories.
    Instructs the LLM to output ONLY raw Java code for the resource/controller class.
    Zero framework-specific literals may be hardcoded in Python code.
    """
```

### 2.3 Resource Generator Service (`agents/generator/resource.py`)

```python
from typing import Any
from contracts.models import FileContent, FrameworkProfile, GenerationRequest

class ResourceGenerator:
    """
    Coordinates prompt construction, LLM generation, code sanitization (markdown unwrapping),
    and typed FileContent wrapping for both Repository and Resource classes.
    """
    def generate(
        self,
        request: GenerationRequest,
        profile: FrameworkProfile,
        llm_client: Any,
    ) -> list[FileContent]:
        """
        Iterates through request.blueprint["entities"], generates a Repository class and
        a Resource class for each entity via llm_client, resolves dynamic destination paths,
        unwraps markdown fences, and returns a list of FileContent models.
        """
```

---

## 3. Detailed Specifications & Behavioral Rules

### 3.1 Repository Prompt Builder (`build_repository_prompt`)
- **Dynamic Concept Injection**:
  - Must extract `profile.concepts.get("transactional", {})` and format its required annotations and imports.
  - If additional persistence or repository concepts exist in `profile.concepts`, format them dynamically.
- **Forbidden Imports Injection**:
  - Injects `profile.forbidden_imports` to prohibit illegal framework namespaces.
- **Pitfalls Injection**:
  - Injects `profile.pitfalls` to steer the LLM away from framework anti-patterns.
- **Entity Schema Context**:
  - Injects entity name, table name, and field definitions from `entity_def`.
- **Output Directives**:
  - Instructs the LLM:
    - "Output ONLY the raw Java code for the repository/DAO class."
    - "Do NOT enclose code in markdown code blocks (do NOT use ``` or ```java)."
    - "Do NOT output conversational text, preambles, or explanations."
    - "The output must start directly with the package declaration or imports and end with the closing brace."
- **Strict Agnosticism (Constitution Rule 8)**:
  - Zero hardcoded framework tokens in Python code (`@Transactional`, `@ApplicationScoped`, `@Repository`, `jakarta.*`, `org.springframework.*`, etc.).

### 3.2 Resource Prompt Builder (`build_resource_prompt`)
- **Dynamic Concept Injection**:
  - Must extract `profile.concepts.get("rest_endpoint", {})` and format annotations (e.g. `@Path`, `@GET`, `@POST`, `@PUT`, `@DELETE`, `@Produces`, `@Consumes`) and required imports.
  - If `profile.concepts.get("dependency_injection", {})` exists, dynamically format it so the controller can inject the repository.
  - If `profile.concepts.get("transactional", {})` exists, dynamically format it if write operations require transactions.
- **User Stories Context**:
  - Injects user stories from `user_stories` (which may be a list of dictionaries or list of strings/descriptions).
  - Translates stories into business endpoint requirements for the entity.
- **Entity Schema Context**:
  - Injects entity name and fields from `entity_def`.
- **Forbidden Imports & Pitfalls**:
  - Injects `profile.forbidden_imports` and `profile.pitfalls`.
- **Output Directives**:
  - Instructs the LLM:
    - "Output ONLY the raw Java code for the REST resource/controller class."
    - "Do NOT enclose code in markdown code blocks (do NOT use ``` or ```java)."
    - "Do NOT output conversational text, preambles, or explanations."
    - "The output must start directly with the package declaration or imports and end with the closing brace."
- **Strict Agnosticism (Constitution Rule 8)**:
  - Zero hardcoded framework tokens in Python code (`@Path`, `@RestController`, `@GetMapping`, `jakarta.ws.rs.*`, etc.).

### 3.3 Dynamic Path Resolution (`ResourceGenerator`)
- Base package path is derived from `request.blueprint.get("packageName", "")`:
  - `package_path = package_name.replace(".", "/")`
- For each entity in `request.blueprint.get("entities", [])`:
  - **Repository path**:
    - With package: `src/main/java/{package_path}/repository/{Name}Repository.java`
    - Without package: `src/main/java/repository/{Name}Repository.java`
  - **Resource path**:
    - With package: `src/main/java/{package_path}/resource/{Name}Resource.java`
    - Without package: `src/main/java/resource/{Name}Resource.java`
- For $N$ entities, the service generates $2N$ files ($N$ Repositories and $N$ Resources).

### 3.4 LLM Interoperability & Markdown Fence Stripping
- **Client Execution**:
  - Invokes `llm_client.generate(prompt)`.
  - Supports both synchronous and asynchronous client implementations.
  - Supports both `LLMResponse` objects (extracting `.content`) and raw strings.
- **Markdown Cleansing**:
  - Strips leading ```` ``` ```` or ```` ```java ```` tags and trailing ```` ``` ```` tags.
  - Trims surrounding whitespace.

### 3.5 Edge Cases
- If `request.blueprint.get("entities")` is missing or empty, `generate()` returns `[]`.
- If `request.blueprint.get("userStories")` is missing or empty, `build_resource_prompt` handles it gracefully without errors.
- Entities missing `fields` or `tableName` are handled gracefully.

---

## 4. User Scenarios & Acceptance Testing

### User Story 1 - Single Entity Repository & Resource Generation (Priority: P1)
**User Journey**: When a validated blueprint containing a single entity (`Order`), package (`org.acme.domain`), and user stories is provided with a framework profile, the generator produces two files: `OrderRepository.java` and `OrderResource.java`.  
**Independent Test**:
- Supply blueprint with `packageName="org.acme.domain"`, entity `Order`, and 1 user story.
- Mock `llm_client.generate` returning valid raw Java classes for Repository and Resource.
- Verify result contains 2 `FileContent` instances:
  - `src/main/java/org/acme/domain/repository/OrderRepository.java`
  - `src/main/java/org/acme/domain/resource/OrderResource.java`

**Acceptance Scenarios**:
1. **Given** a blueprint with 1 entity and package name, **When** `ResourceGenerator.generate` runs, **Then** it returns 2 `FileContent` items with the exact repository and resource paths and stripped code.

---

### User Story 2 - Multiple Entities Batch Generation (Priority: P1)
**User Journey**: When a blueprint contains $N$ entities (`Customer`, `Order`, `Invoice`), the generator produces $2N$ files ($N$ repositories and $N$ resources).  
**Independent Test**:
- Supply blueprint with 3 entities.
- Verify `llm_client.generate` is called 6 times.
- Verify result contains 6 `FileContent` instances with appropriate repository and resource paths.

**Acceptance Scenarios**:
1. **Given** a blueprint with $N$ entities, **When** `ResourceGenerator.generate` runs, **Then** $2N$ `FileContent` objects are returned in deterministic order.

---

### User Story 3 - Dynamic Profile Concept Injection for Repositories (Priority: P1)
**User Journey**: When `build_repository_prompt` is invoked, it injects annotations and imports from `profile.concepts["transactional"]` without hardcoding any framework tokens.  
**Independent Test**:
- Supply custom profile with `transactional` annotations `["@CustomTx"]` and imports `["com.custom.Tx"]`.
- Verify the generated prompt contains `@CustomTx` and `com.custom.Tx`.
- Inspect `agents/generator/prompt.py` to ensure no framework literals (`@Transactional`, `@ApplicationScoped`, etc.) are hardcoded.

**Acceptance Scenarios**:
1. **Given** a profile with custom transactional concepts, **When** `build_repository_prompt` is called, **Then** the prompt contains the injected annotations and imports.

---

### User Story 4 - Dynamic Profile Concept Injection for Resources with User Stories (Priority: P1)
**User Journey**: When `build_resource_prompt` is invoked, it injects annotations and imports from `profile.concepts["rest_endpoint"]`, dependency injection concepts, and user stories without hardcoding any framework tokens.  
**Independent Test**:
- Supply custom profile with `rest_endpoint` annotations `["@CustomRest", "@CustomGet"]` and imports `["com.custom.Rest"]`.
- Supply user stories `[{"title": "Create Order", "description": "Customer creates order"}]` and `["View order history"]`.
- Verify the generated prompt contains `@CustomRest`, `com.custom.Rest`, and the story details.
- Inspect `agents/generator/prompt.py` to ensure no framework literals (`@Path`, `@GET`, `@PostMapping`, etc.) are hardcoded.

**Acceptance Scenarios**:
1. **Given** a profile with REST concepts and a list of user stories, **When** `build_resource_prompt` is called, **Then** the prompt reflects all REST annotations, imports, and story requirements.

---

### User Story 5 - Markdown Code Fence Stripping (Priority: P2)
**User Journey**: When the LLM outputs Java source wrapped in markdown fences, `ResourceGenerator` unwraps the fences so the `FileContent` contains pure compilable Java.  
**Independent Test**:
- Mock `llm_client.generate` returning ```` ```java\npackage org.acme.repository;\npublic class OrderRepository {}\n``` ````.
- Assert `content` does not contain backticks.

**Acceptance Scenarios**:
1. **Given** LLM output wrapped in markdown code fences, **When** processed by `ResourceGenerator`, **Then** the resulting `FileContent.content` contains raw Java with all markdown fences stripped.

---

### User Story 6 - Edge Cases & Robustness (Priority: P3)
**User Journey**: System handles missing entities, missing package names, missing user stories, and async clients cleanly.  
**Acceptance Scenarios**:
1. **Given** `blueprint["entities"]` is empty or missing, **When** `generate()` is called, **Then** it returns `[]`.
2. **Given** `blueprint["packageName"]` is missing or empty, **When** `generate()` is called, **Then** paths resolve to `src/main/java/repository/{Name}Repository.java` and `src/main/java/resource/{Name}Resource.java`.
3. **Given** `blueprint["userStories"]` is missing or empty, **When** generating resources, **Then** prompt handles empty stories gracefully.
4. **Given** an asynchronous `llm_client.generate`, **When** `generate()` executes, **Then** coroutine is awaited and resolves correctly.

---

## 5. Blast Radius & Contract Impact Analysis

- **Contracts (`contracts/models.py`)**:
  - Zero changes required. `GenerationRequest`, `FileContent`, and `FrameworkProfile` already satisfy all requirements.
- **Modified Generator Modules**:
  - `agents/generator/prompt.py`: Adds `build_repository_prompt` and `build_resource_prompt`. Existing `build_entity_prompt` is untouched.
  - `agents/generator/__init__.py`: Exports `ResourceGenerator`, `build_repository_prompt`, `build_resource_prompt`.
- **New Generator Module**:
  - `agents/generator/resource.py`: Implements `ResourceGenerator`.
- **Test Modules**:
  - `tests/agents/generator/test_prompt.py`: Extended with test cases for repository and resource prompt builders.
  - `tests/agents/generator/test_resource.py`: New unit test suite for `ResourceGenerator`.
- **Zero Impact on Other Modules**:
  - `agents/blueprint/`, `agents/repair/`, `agents/verifier/`, and `app/orchestrator/` remain unaffected.

---

## 6. Functional Requirements

- **FR-001**: `agents/generator/prompt.py` MUST export `build_repository_prompt(profile: FrameworkProfile, entity_def: dict[str, Any]) -> str`.
- **FR-002**: `build_repository_prompt` MUST dynamically inject transactional annotations and imports from `profile.concepts.get("transactional", {})`.
- **FR-003**: `build_repository_prompt` MUST dynamically inject forbidden imports from `profile.forbidden_imports` and pitfalls from `profile.pitfalls`.
- **FR-004**: `build_repository_prompt` MUST instruct the LLM to output ONLY raw Java code without markdown fences or conversational text.
- **FR-005**: `agents/generator/prompt.py` MUST export `build_resource_prompt(profile: FrameworkProfile, entity_def: dict[str, Any], user_stories: list[dict[str, Any]] | list[Any]) -> str`.
- **FR-006**: `build_resource_prompt` MUST dynamically inject REST endpoint annotations and imports from `profile.concepts.get("rest_endpoint", {})`.
- **FR-007**: `build_resource_prompt` MUST inject user stories into the prompt context.
- **FR-008**: `build_resource_prompt` MUST instruct the LLM to output ONLY raw Java code without markdown fences or conversational text.
- **FR-009**: Neither `build_repository_prompt` nor `build_resource_prompt` may contain hardcoded framework tokens (Constitution Rule 8).
- **FR-010**: `agents/generator/resource.py` MUST define `ResourceGenerator` with method `def generate(self, request: GenerationRequest, profile: FrameworkProfile, llm_client: Any) -> list[FileContent]`.
- **FR-011**: `ResourceGenerator.generate` MUST iterate through `request.blueprint["entities"]` and generate both a Repository and a Resource class for each entity.
- **FR-012**: Repository path MUST be dynamically resolved as `src/main/java/{package_path}/repository/{Name}Repository.java` (or `src/main/java/repository/{Name}Repository.java` if package is empty).
- **FR-013**: Resource path MUST be dynamically resolved as `src/main/java/{package_path}/resource/{Name}Resource.java` (or `src/main/java/resource/{Name}Resource.java` if package is empty).
- **FR-014**: `ResourceGenerator` MUST strip markdown fences from LLM responses before creating `FileContent`.
- **FR-015**: `ResourceGenerator` MUST handle both synchronous and asynchronous `llm_client.generate` methods.

---

## 7. Success Criteria

- **SC-001**: 100% test pass rate in `tests/agents/generator/test_prompt.py` and `tests/agents/generator/test_resource.py`.
- **SC-002**: Existing test suite (88 tests) passes with zero regressions.
- **SC-003**: Zero hardcoded framework tokens in `agents/generator/prompt.py` and `agents/generator/resource.py` (verified via static AST or token inspection test).
- **SC-004**: Zero `mypy` type check errors on new and modified modules.
- **SC-005**: Zero `ruff` lint violations on new and modified modules.

---

## 8. Verification Strategy (Trust but Verify)

1. **Step 1 (Red Phase / TDD)**:
   - Add unit tests in `tests/agents/generator/test_prompt.py` for `build_repository_prompt` and `build_resource_prompt`.
   - Add unit tests in `tests/agents/generator/test_resource.py` for `ResourceGenerator` (single entity, multiple entities, path resolution, markdown unwrapping, empty entities, async client).
   - Add AST / token check verifying no framework literals exist in prompt builder or generator.
   - Run `/home/gjanampa/.venv/bin/pytest tests/agents/generator/` to observe failing tests.
2. **Step 2 (Green Phase / Implementation)**:
   - Implement `build_repository_prompt` and `build_resource_prompt` in `agents/generator/prompt.py`.
   - Implement `ResourceGenerator` in `agents/generator/resource.py`.
   - Update `agents/generator/__init__.py`.
   - Run `/home/gjanampa/.venv/bin/pytest tests/agents/generator/` to verify all tests pass.
3. **Step 3 (Refactor & Quality Checks)**:
   - Run complete test suite: `/home/gjanampa/.venv/bin/pytest`.
   - Run type checking: `/home/gjanampa/.venv/bin/mypy agents/generator tests/agents/generator`.
   - Run linter: `/home/gjanampa/.venv/bin/ruff check agents/generator tests/agents/generator`.

