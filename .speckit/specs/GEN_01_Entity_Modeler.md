# Feature Specification: GEN_01_Entity_Modeler

**Feature Identifier**: `GEN_01_Entity_Modeler`  
**Feature Branch**: `streamD/gen1-entity-modeler`  
**Target Artifacts**:  
- `contracts/models.py` (`GenerationRequest`)  
- `agents/generator/__init__.py`  
- `agents/generator/prompt.py`  
- `agents/generator/entity.py`  
- `tests/agents/generator/__init__.py`  
- `tests/agents/generator/test_prompt.py`  
- `tests/agents/generator/test_entity.py`  
**Contract Authority**: `contracts/models.py` (`GenerationRequest`, `FileContent`, `FrameworkProfile`)  
**Status**: Pending Review  
**Date**: 2026-10-11  

---

## 1. Executive Summary & Purpose

The **Gen-1 Entity Modeler microservice** is the initial code generation component of the Generation Graph in AgentIA v2. Its purpose is to ingest a validated architectural blueprint (`blueprint["entities"]` and `blueprint["packageName"]`) alongside a framework profile (`FrameworkProfile`), and synthesize framework-compliant ORM entity class files (`List[FileContent]`).

In accordance with the **AgentIA v2 Constitution**:
1. **Rule 1 (Specs before code)**: Specification must be defined and reviewed prior to test and code authoring.
2. **Rule 2 (Tests first)**: Every requirement and acceptance criterion is verified against failing automated unit tests before implementation.
3. **Rule 3 (Contracts first)**: All inputs, outputs, and intermediate structures communicate strictly via typed Pydantic models in `contracts/models.py` (`GenerationRequest`, `FileContent`, `FrameworkProfile`).
4. **Rule 4 (Deterministic over generative)**: File paths, package directories, and prompt injection logic are computed deterministically. The LLM is used solely to generate framework-compliant Java source definitions from entity schemas.
5. **Rule 6 (Validate every LLM output)**: Output from the LLM is sanitized (markdown code fences stripped) and wrapped into a typed `FileContent` model.
6. **Rule 8 (Framework knowledge lives in profiles)**: Agents must be completely framework-agnostic. No Quarkus, Spring, or JPA literals (such as `@Entity`, `@Table`, `@Id`, `jakarta.persistence.*`, `org.springframework.*`) may be hardcoded in Python agent code; they must be resolved dynamically from `profile.concepts["orm_entity"]` and `profile.forbidden_imports`.
7. **Rule 11 (Observability everywhere)**: Requests support an optional `trace_id` propagating through the generation lifecycle.
8. **Rule 13 (Simplest thing that works)**: Minimal viable interface conforming strictly to the requested signatures.

---

## 2. API Contracts & Function Signatures

### 2.1 Contract Extension (`contracts/models.py`)

Under `# --- DM-4 / GEN-1: Generation Graph Contract ---`:

```python
class GenerationRequest(BaseModel):
    blueprint: dict[str, Any]
    trace_id: str | None = None
```

Existing contracts utilized:
- `FileContent(path: str, content: str | None = None, digest: str | None = None)`
- `FrameworkProfile` (fields: `framework`, `framework_version`, `java_version`, `concepts`, `forbidden_imports`, etc.)

### 2.2 Entity Generation Prompt Builder (`agents/generator/prompt.py`)

```python
def build_entity_prompt(profile: FrameworkProfile, entity_def: dict[str, Any]) -> str:
    """
    Construct an LLM prompt that dynamically injects framework conventions from
    profile.concepts["orm_entity"] (annotations, required imports) and profile.forbidden_imports.
    
    Instructs the LLM to output ONLY raw Java code for the entity (no markdown code blocks,
    no conversational text) based on the entity_def schema.
    
    Zero framework-specific literals may be hardcoded in Python code.
    """
```

### 2.3 Entity Generator Service (`agents/generator/entity.py`)

```python
from typing import List
from contracts.models import FileContent, FrameworkProfile, GenerationRequest
from app.core.llm.client import LLMClient

class EntityGenerator:
    """
    Orchestrates entity class generation by iterating through blueprint entities,
    invoking prompt generation, querying the LLMClient, sanitizing code output,
    and packaging results into typed FileContent models.
    """
    def generate(
        self,
        request: GenerationRequest,
        profile: FrameworkProfile,
        llm_client: LLMClient,
    ) -> List[FileContent]:
        """
        Iterates through request.blueprint["entities"], generates ORM entity code via llm_client,
        constructs dynamic destination paths using request.blueprint["packageName"],
        and returns a list of FileContent models.
        """
```

---

## 3. Detailed Specifications & Behavioral Rules

### 3.1 Prompt Builder Specifications (`agents/generator/prompt.py`)
- **Rule 1 (Dynamic Concept Injection)**:
  - Must extract `profile.concepts.get("orm_entity", {})`.
  - Annotations from `orm_entity.get("annotations", [])` must be listed as mandatory class/field annotations (e.g. `@Entity`, `@Table`, `@Id`, `@GeneratedValue`).
  - Required imports from `orm_entity.get("imports", [])` must be listed as mandatory import statements.
- **Rule 2 (Forbidden Imports Injection)**:
  - Must extract `profile.forbidden_imports` and list them as prohibited imports (e.g., prohibited framework or legacy namespaces).
- **Rule 3 (Entity Schema Injection)**:
  - Injects target entity metadata from `entity_def`:
    - Entity class name (e.g., `entity_def["name"]`).
    - Table name if provided, or instruction to derive snake_case / default table name.
    - Fields list (field names, types, constraints such as primary key, nullable, etc.).
- **Rule 4 (Strict Output Formatting Directives)**:
  - Instructs LLM: "Output ONLY the raw Java code for the entity. Do NOT use markdown code blocks (no ``` or ```java). Do NOT output conversational prose, commentary, or explanation."
- **Rule 5 (Framework Agnosticism - Constitution Rule 8)**:
  - Zero framework literals (`@Entity`, `@Table`, `@Id`, `jakarta.persistence`, `org.springframework`, etc.) in `agents/generator/prompt.py`. Everything is injected dynamically from `profile`.

### 3.2 Dynamic Path Resolution (`agents/generator/entity.py`)
- Given `request.blueprint["packageName"]` (e.g. `"org.acme.domain"` or `"com.example.orders"`):
  - Convert dots to directory slashes: `"org.acme.domain"` $\rightarrow$ `"org/acme/domain"`.
  - Destination file path: `f"src/main/java/{package_path}/{entity_name}.java"`.
  - Example: `packageName="org.acme.domain"`, entity `name="Customer"` $\rightarrow$ `src/main/java/org/acme/domain/Customer.java`.
  - If `packageName` is empty, path defaults to `src/main/java/{entity_name}.java`.

### 3.3 LLM Client Interoperability & Code Cleansing
- **LLM Client Execution**:
  - `llm_client.generate(prompt)` may return an `LLMResponse` object (with `.content`) or a string.
  - The client call may be synchronous or an awaitable coroutine; `EntityGenerator.generate` must handle both execution models cleanly.
- **Code Cleansing (Constitution Rule 6)**:
  - If the LLM generates markdown fences (e.g. ```` ```java ... ``` ```` or ```` ``` ... ``` ````), `EntityGenerator` must strip the enclosing markdown backticks and language tag, trimming surrounding whitespace to ensure `FileContent.content` contains pure Java source code.

### 3.4 Empty & Edge Case Blueprints
- If `request.blueprint.get("entities")` is missing or empty, `generate()` returns an empty list `[]`.
- If an entity definition has minimal fields (e.g. `{"name": "Item"}` without explicit fields list), prompt handles it gracefully.

---

## 4. User Scenarios & Acceptance Testing

### User Story 1 - Single Entity Generation (Priority: P1)
**User Journey**: When a validated blueprint containing a single entity (`Customer`) and package name (`org.acme.domain`) is provided with a Quarkus profile, the service invokes the LLM client and returns a single `FileContent` with the correct path and raw Java content.  
**Why this priority**: Core MVP functionality for Gen-1.  
**Independent Test**:
- Supply `GenerationRequest(blueprint={"packageName": "org.acme.domain", "entities": [{"name": "Customer", "fields": [{"name": "id", "type": "Long", "id": True}]}]})`.
- Provide mock `llm_client` returning `"package org.acme.domain;\npublic class Customer {}"`.
- Verify `result` has length 1.
- Verify `result[0].path == "src/main/java/org/acme/domain/Customer.java"`.
- Verify `result[0].content` matches expected Java code.

**Acceptance Scenarios**:
1. **Given** a valid `GenerationRequest` with one entity, **When** `generate()` is called, **Then** returns `[FileContent(path="src/main/java/org/acme/domain/Customer.java", content=...)]`.

---

### User Story 2 - Multi-Entity Batch Generation (Priority: P1)
**User Journey**: When a blueprint contains multiple entities (`Order`, `Customer`, `Product`), the service generates a distinct prompt and `FileContent` for each entity in the blueprint.  
**Why this priority**: Production blueprints define multiple domain entities.  
**Independent Test**:
- Supply blueprint with 3 entities.
- Verify `llm_client.generate` is called 3 times with entity-specific prompts.
- Verify 3 `FileContent` instances are returned with paths `src/main/java/org/acme/domain/Order.java`, `src/main/java/org/acme/domain/Customer.java`, and `src/main/java/org/acme/domain/Product.java`.

**Acceptance Scenarios**:
1. **Given** a blueprint with $N$ entities, **When** `generate()` is called, **Then** exactly $N$ `FileContent` objects are returned corresponding to each entity.

---

### User Story 3 - Dynamic Profile Conventions Injection (Priority: P1)
**User Journey**: When `build_entity_prompt` is invoked, it dynamically pulls annotations and imports from `profile.concepts["orm_entity"]` and forbidden packages from `profile.forbidden_imports` without hardcoding any framework literals in Python source code.  
**Why this priority**: Enforces Constitution Rule 8 (Framework knowledge lives in profiles).  
**Independent Test**:
- Pass a test profile with unique arbitrary concepts (e.g. annotations `["@CustomEntity"]`, imports `["com.custom.Entity"]`, forbidden `["com.bad.*"]`).
- Assert that prompt contains `@CustomEntity`, `com.custom.Entity`, and `com.bad.*`.
- Perform static code inspection on `agents/generator/prompt.py` to confirm no framework literals (e.g. `@Entity`, `@Table`, `jakarta.persistence`, `org.springframework`) appear in the source code.

**Acceptance Scenarios**:
1. **Given** a `FrameworkProfile` with custom ORM concepts and forbidden imports, **When** `build_entity_prompt` is called, **Then** the prompt contains all specified annotations, imports, and prohibitions.

---

### User Story 4 - Markdown Fence Stripping (Priority: P2)
**User Journey**: If the LLM generates Java code enclosed within markdown code fences (` ```java ... ``` `), the service strips the fences and returns pure Java code.  
**Why this priority**: LLMs frequently emit markdown fences despite negative constraints; stripping ensures the generated files compile without syntax errors.  
**Independent Test**:
- Mock `llm_client.generate` returning ```` ```java\npackage org.acme;\npublic class Item {}\n``` ````.
- Assert `result[0].content` equals `"package org.acme;\npublic class Item {}"`.

**Acceptance Scenarios**:
1. **Given** LLM output wrapped in markdown code blocks, **When** wrapped in `FileContent`, **Then** markdown delimiters are stripped and the content is clean raw Java.

---

### User Story 5 - Edge Cases and Resiliency (Priority: P3)
**User Journey**: Handles empty entity lists, missing package names, and sync/async LLM clients safely.  
**Acceptance Scenarios**:
1. **Given** `blueprint["entities"]` is empty or missing, **When** `generate()` is called, **Then** returns `[]`.
2. **Given** `blueprint["packageName"]` is absent, **When** path is calculated, **Then** it generates `src/main/java/{EntityName}.java` without malformed slashes.
3. **Given** an asynchronous `llm_client.generate()`, **When** `generate()` executes, **Then** the coroutine is awaited and resolves correctly.

---

## 5. Blast Radius & Contract Impact Analysis

- **Contracts**:
  - `contracts/models.py`: Add `GenerationRequest(blueprint: dict[str, Any], trace_id: str | None = None)`.
  - Zero breaking changes to existing contracts (`FileContent`, `FrameworkProfile`, `RepairRequest`, etc.).
- **New Agents Module**:
  - `agents/generator/__init__.py`
  - `agents/generator/prompt.py`
  - `agents/generator/entity.py`
- **New Unit Test Suite**:
  - `tests/agents/generator/__init__.py`
  - `tests/agents/generator/test_prompt.py`
  - `tests/agents/generator/test_entity.py`
- **Zero Impact on Existing Modules**:
  - `agents/blueprint/` untouched.
  - `agents/profiles/` untouched.
  - `agents/repair/` untouched.
  - `agents/verifier/` untouched.
  - `app/orchestrator/` untouched.

---

## 6. Functional Requirements

- **FR-001**: System MUST define `GenerationRequest` in `contracts/models.py` with `blueprint: dict[str, Any]` and optional `trace_id: str | None`.
- **FR-002**: `agents/generator/prompt.py` MUST export `build_entity_prompt(profile: FrameworkProfile, entity_def: dict) -> str`.
- **FR-003**: `build_entity_prompt` MUST dynamically inject ORM entity annotations and imports from `profile.concepts.get("orm_entity", {})`.
- **FR-004**: `build_entity_prompt` MUST dynamically inject forbidden imports from `profile.forbidden_imports`.
- **FR-005**: `build_entity_prompt` MUST explicitly instruct the LLM to output ONLY raw Java code without markdown fences.
- **FR-006**: `agents/generator/prompt.py` MUST NOT hardcode any framework-specific annotations, classes, or package names (Constitution Rule 8).
- **FR-007**: `agents/generator/entity.py` MUST export `EntityGenerator` class with `def generate(self, request: GenerationRequest, profile: FrameworkProfile, llm_client: LLMClient) -> List[FileContent]`.
- **FR-008**: `EntityGenerator.generate` MUST iterate over `request.blueprint["entities"]` and generate a `FileContent` for each entity.
- **FR-009**: Destination path MUST be calculated dynamically as `src/main/java/{package_path}/{entity_name}.java` where `package_path` is derived from `request.blueprint["packageName"]`.
- **FR-010**: `EntityGenerator` MUST sanitize LLM output by stripping markdown fences (```java ... ```) if present.
- **FR-011**: `EntityGenerator` MUST support both `LLMResponse` objects and raw strings returned by `llm_client.generate`.
- **FR-012**: `EntityGenerator` MUST support both synchronous and asynchronous `llm_client.generate` calls.

---

## 7. Success Criteria

- **SC-001**: 100% test pass rate across `tests/agents/generator/`.
- **SC-002**: Existing test suite (76 tests) continues to pass with 0 regressions.
- **SC-003**: Zero framework literals hardcoded in `agents/generator/prompt.py` (verified via AST or static token check in unit tests).
- **SC-004**: Zero `mypy` type check errors on new modules.
- **SC-005**: Zero `ruff` lint/format violations on new modules.

---

## 8. Verification Strategy (Trust but Verify)

1. **Step 1 (Red Phase / TDD)**:
   - Add `GenerationRequest` contract to `contracts/models.py`.
   - Write comprehensive unit tests in `tests/agents/generator/test_prompt.py` (testing dynamic injection of profile concepts, forbidden imports, instructions, and static check for no hardcoded literals).
   - Write comprehensive unit tests in `tests/agents/generator/test_entity.py` (testing single entity, multi-entity, path construction, markdown stripping, sync/async client handling).
   - Execute `uv run --extra dev pytest tests/agents/generator/` to observe initial failure (Red Phase).
2. **Step 2 (Green Phase / Implementation)**:
   - Implement `agents/generator/prompt.py`.
   - Implement `agents/generator/entity.py`.
   - Implement `agents/generator/__init__.py`.
   - Execute `uv run --extra dev pytest tests/agents/generator/` to verify all tests pass.
3. **Step 3 (Refactor & Compliance Verification)**:
   - Run full test suite: `uv run --extra dev pytest`.
   - Run type checking: `uv run --extra dev mypy agents/generator tests/agents/generator`.
   - Run linter: `uv run --extra dev ruff check agents/generator tests/agents/generator`.

