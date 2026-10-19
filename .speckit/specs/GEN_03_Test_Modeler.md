# Feature Specification: GEN_03_Test_Modeler

**Feature Identifier**: `GEN_03_Test_Modeler`  
**Feature Branch**: `streamF/gen3-test-modeler`  
**Target Artifacts**:  
- `agents/generator/prompt.py` (`build_test_prompt`)  
- `agents/generator/test_writer.py` (`TestGenerator`)  
- `agents/generator/__init__.py`  
- `tests/agents/generator/test_prompt.py`  
- `tests/agents/generator/test_test_writer.py`  
**Contract Authority**: `contracts.models` (`GenerationRequest`, `FileContent`, `FrameworkProfile`)  
**Status**: Pending Review  
**Date**: 2026-10-12  

---

## 1. Executive Summary & Purpose

The **Gen-3 Test Writer microservice** is the third stage of the Generation Graph in AgentIA v2. Its purpose is to ingest a validated architectural blueprint (`request.blueprint`) alongside an active framework profile (`FrameworkProfile`), and synthesize compile-ready automated test classes (Unit and Integration tests) for the previously modeled Resources and Repositories across all defined entities.

In accordance with the **AgentIA v2 Constitution**:
1. **Rule 1 (Specs before code)**: Specification must be defined and reviewed prior to test and code authoring.
2. **Rule 2 (Tests first)**: Every requirement and acceptance criterion is verified against failing automated unit tests (TDD Red phase) before implementation.
3. **Rule 3 (Contracts first)**: All inputs, outputs, and intermediate structures communicate strictly via typed Pydantic models in `contracts/models.py` (`GenerationRequest`, `FileContent`, `FrameworkProfile`).
4. **Rule 4 (Deterministic over generative)**: Destination test file paths, package directory structures (`src/test/java/{package}/resource/{Name}ResourceTest.java`, `src/test/java/{package}/repository/{Name}RepositoryTest.java`), and prompt injection logic are computed deterministically. The LLM is used solely to generate framework-compliant Java unit/integration test source code based on target class signatures, mock requirements, and user stories.
5. **Rule 6 (Validate every LLM output)**: LLM completions are sanitized (markdown code fences stripped) and encapsulated into typed `FileContent` models.
6. **Rule 8 (Framework knowledge lives in profiles)**: Agents must be completely framework-agnostic. No Quarkus or Spring literals (such as `@QuarkusTest`, `@InjectMock`, `@SpringBootTest`, `@MockBean`, `io.quarkus.test.*`, `org.springframework.boot.test.*`) may appear in agent Python code; they must be resolved dynamically from `profile.test_style` and `profile.concepts["mock_in_test"]`.
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
  Contains `framework`, `framework_version`, `java_version`, `build_tool`, `concepts` (including `mock_in_test`), `test_style` (including `class_annotations`, `imports`, `assertion_library`), `forbidden_imports`, `pitfalls`, etc.

### 2.2 Test Prompt Builder (`agents/generator/prompt.py`)

```python
from typing import Any
from contracts.models import FrameworkProfile

def build_test_prompt(
    profile: FrameworkProfile,
    target_class_name: str,
    class_type: str,
    user_stories: list[dict[str, Any]] | list[Any],
) -> str:
    """
    Construct an LLM prompt that dynamically injects framework testing conventions
    from profile.test_style (class annotations, imports, assertion library) and
    profile.concepts["mock_in_test"] (mock annotations, imports), forbidden imports,
    pitfalls, target class details, and user stories.
    Instructs the LLM to output ONLY raw Java code for the unit/integration test class.
    Zero framework-specific literals may be hardcoded in Python code.
    """
```

### 2.3 Test Generator Service (`agents/generator/test_writer.py`)

```python
from typing import Any
from contracts.models import FileContent, FrameworkProfile, GenerationRequest

class TestGenerator:
    """
    Coordinates prompt construction, LLM generation, code sanitization (markdown unwrapping),
    and typed FileContent wrapping for both Resource and Repository automated test classes.
    """
    def generate(
        self,
        request: GenerationRequest,
        profile: FrameworkProfile,
        llm_client: Any,
    ) -> list[FileContent]:
        """
        Iterates through request.blueprint["entities"], generates a Resource test class and
        a Repository test class for each entity via llm_client, resolves dynamic destination paths
        under src/test/java/..., unwraps markdown fences, and returns a list of FileContent models.
        """
```

---

## 3. Detailed Specifications & Behavioral Rules

### 3.1 Test Prompt Builder (`build_test_prompt`)
- **Dynamic Test Style Injection**:
  - Must extract `profile.test_style` dictionary:
    - `class_annotations`: class-level test annotations (e.g., `@QuarkusTest` or `@SpringBootTest`).
    - `imports`: test framework imports (e.g., `io.quarkus.test.junit.QuarkusTest`, `org.junit.jupiter.api.Test`, assertions).
    - `assertion_library`: library style (e.g., `junit-jupiter`, `assertj`).
  - Formats these into a dedicated `## Framework Testing Conventions` section.
- **Dynamic Mock Injection**:
  - Must extract `profile.concepts.get("mock_in_test", {})`:
    - `annotations`: mocking annotations (e.g., `@InjectMock` or `@MockBean`).
    - `imports`: mocking library imports (e.g., `io.quarkus.test.junit.mockito.InjectMock`).
  - Formats these into a dedicated `## Mocking Conventions` section.
- **Forbidden Imports Injection**:
  - Injects `profile.forbidden_imports` to prohibit illegal framework namespaces (e.g., legacy JUnit 4 `org.junit.Test`, Spring in Quarkus).
- **Pitfalls Injection**:
  - Injects `profile.pitfalls` to steer the LLM away from framework testing anti-patterns (e.g., package-private field visibility in Quarkus tests).
- **Target Class & Class Type Context**:
  - Injects `target_class_name` (e.g., `OrderResource`, `OrderRepository`).
  - Injects `class_type` (e.g., `resource` or `repository`).
  - Provides guidance on testing objectives:
    - For `resource`: Test HTTP endpoints, status codes, request/response serialization, and mock repository dependencies.
    - For `repository`: Test data persistence, query operations, and transactions.
- **User Stories Context**:
  - Injects formatted `user_stories` to drive behavior-driven test scenarios matching acceptance criteria.
- **Output Directives (Zero Markdown, Raw Java)**:
  - Instructs the LLM:
    - "Output ONLY the raw Java code for the test class."
    - "Do NOT enclose code in markdown code blocks (do NOT use ``` or ```java)."
    - "Do NOT output conversational text, preambles, or markdown formatting."
    - "The output must start directly with the package declaration or imports and end with the closing brace."
- **Strict Agnosticism (Constitution Rule 8)**:
  - Zero hardcoded framework tokens in Python code (`@QuarkusTest`, `@InjectMock`, `@SpringBootTest`, `@MockBean`, `io.quarkus.*`, `org.springframework.*`, etc.).

### 3.2 Dynamic Destination Path Resolution (`TestGenerator`)
- Base package path is derived from `request.blueprint.get("packageName", "")`:
  - `package_path = package_name.replace(".", "/")`
- For each entity in `request.blueprint.get("entities", [])`:
  - Target Entity Name: `{entity_name}` (e.g., `Order`)
  - **Resource Test path**:
    - With package: `src/test/java/{package_path}/resource/{entity_name}ResourceTest.java`
    - Without package: `src/test/java/resource/{entity_name}ResourceTest.java`
  - **Repository Test path**:
    - With package: `src/test/java/{package_path}/repository/{entity_name}RepositoryTest.java`
    - Without package: `src/test/java/repository/{entity_name}RepositoryTest.java`
- For $N$ entities, the service generates $2N$ test files ($N$ Resource tests and $N$ Repository tests).

### 3.3 LLM Interoperability & Markdown Fence Stripping
- **Client Execution**:
  - Invokes `llm_client.generate(prompt)`.
  - Supports both synchronous and asynchronous client implementations.
  - Supports both `LLMResponse` objects (extracting `.content`) and raw strings.
- **Markdown Cleansing**:
  - Strips leading ```` ``` ```` or ```` ```java ```` tags and trailing ```` ``` ```` tags.
  - Trims surrounding whitespace so the output is pure compile-ready Java.

### 3.4 Edge Cases & Robustness
- If `request.blueprint.get("entities")` is missing or empty, `generate()` returns `[]`.
- If `request.blueprint.get("userStories")` is missing or empty, `build_test_prompt` handles it gracefully without errors.
- Entities missing `name` default gracefully to `Entity`.
- Non-dict entity or user story entries are safely ignored or formatted.

---

## 4. User Scenarios & Acceptance Testing

### User Story 1 - Single Entity Resource & Repository Test Generation (Priority: P1)
**User Journey**: When a validated blueprint containing an entity (`Order`), package (`org.acme.domain`), and user stories is provided with a framework profile, the generator produces two test files: `OrderResourceTest.java` and `OrderRepositoryTest.java`.  
**Independent Test**:
- Supply blueprint with `packageName="org.acme.domain"`, entity `Order`, and 1 user story.
- Mock `llm_client.generate` returning valid raw Java test classes.
- Verify result contains 2 `FileContent` instances:
  - `src/test/java/org/acme/domain/resource/OrderResourceTest.java`
  - `src/test/java/org/acme/domain/repository/OrderRepositoryTest.java`

**Acceptance Scenarios**:
1. **Given** a blueprint with 1 entity and package name, **When** `TestGenerator.generate` runs, **Then** it returns 2 `FileContent` items with the exact test paths and stripped code.

---

### User Story 2 - Multiple Entities Batch Test Generation (Priority: P1)
**User Journey**: When a blueprint contains $N$ entities (`Customer`, `Order`, `Invoice`), the generator produces $2N$ test files ($N$ resource tests and $N$ repository tests).  
**Independent Test**:
- Supply blueprint with 3 entities.
- Verify `llm_client.generate` is called 6 times (2 calls per entity).
- Verify result contains 6 `FileContent` instances with appropriate test paths.

**Acceptance Scenarios**:
1. **Given** a blueprint with $N$ entities, **When** `TestGenerator.generate` runs, **Then** $2N$ `FileContent` objects are returned in deterministic order.

---

### User Story 3 - Dynamic Profile Injection of `test_style` and `mock_in_test` (Priority: P1)
**User Journey**: When `build_test_prompt` is invoked, it injects class annotations and imports from `profile.test_style` and mock annotations and imports from `profile.concepts["mock_in_test"]` without hardcoding any framework tokens.  
**Independent Test**:
- Supply custom profile with `test_style` having annotations `["@CustomTestAnnotation"]` and imports `["com.custom.TestRunner"]`.
- Supply custom profile with `concepts.mock_in_test` having annotations `["@CustomMockAnnotation"]` and imports `["com.custom.MockService"]`.
- Verify the generated prompt contains `@CustomTestAnnotation`, `com.custom.TestRunner`, `@CustomMockAnnotation`, and `com.custom.MockService`.
- Inspect `agents/generator/prompt.py` to ensure no framework literals (`@QuarkusTest`, `@InjectMock`, `@SpringBootTest`, etc.) are hardcoded.

**Acceptance Scenarios**:
1. **Given** a profile with custom test style and mock concepts, **When** `build_test_prompt` is called, **Then** the prompt dynamically contains the injected test annotations, mock annotations, and imports.

---

### User Story 4 - Markdown Code Fence Stripping for Tests (Priority: P2)
**User Journey**: When the LLM outputs Java test source wrapped in markdown fences, `TestGenerator` unwraps the fences so the `FileContent` contains pure compilable Java.  
**Independent Test**:
- Mock `llm_client.generate` returning ```` ```java\npackage org.acme.resource;\nclass OrderResourceTest {}\n``` ````.
- Assert `content` does not contain backticks.

**Acceptance Scenarios**:
1. **Given** LLM output wrapped in markdown code fences, **When** processed by `TestGenerator`, **Then** the resulting `FileContent.content` contains raw Java with all markdown fences stripped.

---

### User Story 5 - Framework Agnosticism & Constitution Compliance (Priority: P1)
**User Journey**: Ensure zero framework-specific literals are hardcoded in `agents/generator/prompt.py` or `agents/generator/test_writer.py`.  
**Independent Test**:
- Static scan / AST analysis of `agents/generator/prompt.py` and `agents/generator/test_writer.py` verifying no forbidden framework tokens (`QuarkusTest`, `InjectMock`, `SpringBootTest`, `MockBean`, `org.junit.Test`, etc.) appear as literals.

**Acceptance Scenarios**:
1. **Given** agent generator code, **When** inspected for hardcoded framework literals, **Then** zero occurrences are found outside of dynamic profile attribute access.

---

### User Story 6 - Edge Cases & Robustness (Priority: P3)
**User Journey**: System handles missing entities, missing package names, missing user stories, and async clients cleanly.  
**Acceptance Scenarios**:
1. **Given** `blueprint["entities"]` is empty or missing, **When** `generate()` is called, **Then** it returns `[]`.
2. **Given** `blueprint["packageName"]` is missing or empty, **When** `generate()` is called, **Then** paths resolve to `src/test/java/resource/{Name}ResourceTest.java` and `src/test/java/repository/{Name}RepositoryTest.java`.
3. **Given** `blueprint["userStories"]` is missing or empty, **When** generating tests, **Then** prompt handles empty stories gracefully.
4. **Given** an asynchronous `llm_client.generate`, **When** `generate()` executes, **Then** coroutine is awaited and resolves correctly.

---

## 5. Blast Radius & Contract Impact Analysis

- **Contracts (`contracts/models.py`)**:
  - Zero changes required. `GenerationRequest`, `FileContent`, and `FrameworkProfile` already satisfy all requirements.
- **Modified Generator Modules**:
  - `agents/generator/prompt.py`: Adds `build_test_prompt`. Existing `build_entity_prompt`, `build_repository_prompt`, and `build_resource_prompt` remain untouched.
  - `agents/generator/__init__.py`: Exports `TestGenerator` and `build_test_prompt`.
- **New Generator Module**:
  - `agents/generator/test_writer.py`: Implements `TestGenerator`.
- **Test Modules**:
  - `tests/agents/generator/test_prompt.py`: Extended with test cases for `build_test_prompt`.
  - `tests/agents/generator/test_test_writer.py`: New comprehensive unit test suite for `TestGenerator`.
- **Zero Impact on Other Modules**:
  - `agents/blueprint/`, `agents/repair/`, `agents/verifier/`, and `app/orchestrator/` remain unaffected.

---

## 6. Functional Requirements

- **FR-001**: `agents/generator/prompt.py` MUST export `build_test_prompt(profile: FrameworkProfile, target_class_name: str, class_type: str, user_stories: list[dict[str, Any]] | list[Any]) -> str`.
- **FR-002**: `build_test_prompt` MUST dynamically inject test class annotations, imports, and assertion library preferences from `profile.test_style`.
- **FR-003**: `build_test_prompt` MUST dynamically inject mock annotations and mock imports from `profile.concepts.get("mock_in_test", {})`.
- **FR-004**: `build_test_prompt` MUST dynamically inject forbidden imports from `profile.forbidden_imports` and pitfalls from `profile.pitfalls`.
- **FR-005**: `build_test_prompt` MUST inject `target_class_name`, `class_type`, and user stories into the prompt context.
- **FR-006**: `build_test_prompt` MUST instruct the LLM to output ONLY raw Java code without markdown fences or conversational text.
- **FR-007**: `build_test_prompt` MUST NOT contain hardcoded framework tokens (Constitution Rule 8).
- **FR-008**: `agents/generator/test_writer.py` MUST define `TestGenerator` with method `def generate(self, request: GenerationRequest, profile: FrameworkProfile, llm_client: Any) -> list[FileContent]`.
- **FR-009**: `TestGenerator.generate` MUST iterate through `request.blueprint["entities"]` and generate both a Resource test class and a Repository test class for each entity.
- **FR-010**: Resource test destination path MUST be dynamically resolved as `src/test/java/{package_path}/resource/{Name}ResourceTest.java` (or `src/test/java/resource/{Name}ResourceTest.java` if package is empty).
- **FR-011**: Repository test destination path MUST be dynamically resolved as `src/test/java/{package_path}/repository/{Name}RepositoryTest.java` (or `src/test/java/repository/{Name}RepositoryTest.java` if package is empty).
- **FR-012**: `TestGenerator` MUST strip markdown fences from LLM responses before creating `FileContent`.
- **FR-013**: `TestGenerator` MUST handle both synchronous and asynchronous `llm_client.generate` methods.
- **FR-014**: `TestGenerator` MUST return an empty list if `entities` is missing or empty.
- **FR-015**: `agents/generator/__init__.py` MUST expose `TestGenerator` and `build_test_prompt`.

---

## 7. Success Criteria

- **SC-001**: 100% test pass rate in `tests/agents/generator/test_prompt.py` and `tests/agents/generator/test_test_writer.py`.
- **SC-002**: Existing test suite (100 tests) passes with zero regressions.
- **SC-003**: Zero hardcoded framework tokens in `agents/generator/prompt.py` and `agents/generator/test_writer.py` (verified via static AST or token inspection test).
- **SC-004**: Zero `mypy` type check errors on new and modified modules.
- **SC-005**: Zero `ruff` lint violations on new and modified modules.

---

## 8. Verification Strategy (Trust but Verify)

1. **Step 1 (Red Phase / TDD)**:
   - Add unit tests in `tests/agents/generator/test_prompt.py` for `build_test_prompt`.
   - Add unit tests in `tests/agents/generator/test_test_writer.py` for `TestGenerator` (single entity, multiple entities, path resolution, markdown unwrapping, empty entities, async client, agnosticism check).
   - Run `/home/gjanampa/Projects/AI_AGENTS/agentIA_v2_streamF/.venv/bin/pytest tests/agents/generator/` to observe failing tests.
2. **Step 2 (Green Phase / Implementation)**:
   - Implement `build_test_prompt` in `agents/generator/prompt.py`.
   - Implement `TestGenerator` in `agents/generator/test_writer.py`.
   - Update `agents/generator/__init__.py`.
   - Run `/home/gjanampa/Projects/AI_AGENTS/agentIA_v2_streamF/.venv/bin/pytest tests/agents/generator/` to verify all generator tests pass.
3. **Step 3 (Refactor & Quality Checks)**:
   - Run complete test suite: `/home/gjanampa/Projects/AI_AGENTS/agentIA_v2_streamF/.venv/bin/pytest`.
   - Run type checking: `/home/gjanampa/Projects/AI_AGENTS/agentIA_v2_streamF/.venv/bin/mypy agents/generator tests/agents/generator`.
   - Run linter: `/home/gjanampa/Projects/AI_AGENTS/agentIA_v2_streamF/.venv/bin/ruff check agents/generator tests/agents/generator`.

