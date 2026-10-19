# Feature Specification: PF_01_Quarkus_Profile

**Feature Identifier**: `PF_01_Quarkus_Profile`  
**Feature Branch**: `streamA/profiles-dm1`  
**Target Artifact**: `profiles/quarkus-3.yaml`  
**Contract Authority**: `contracts/models.py` (`FrameworkProfile`)  
**Status**: Pending Review  
**Date**: 2026-10-11  

---

## 1. Executive Summary & Purpose

In accordance with **Constitution Rule 8** (*"Framework knowledge lives in profiles: Agents are framework-agnostic. No Quarkus or Spring literals may appear in agent Python code; they must be resolved dynamically from profiles/*.yaml"*), the `PF_01_Quarkus_Profile` specification establishes the single source of truth for the Quarkus 3 Java runtime environment within AgentIA v2.

This profile specifies the runtime configurations, build tools, dependency injection and mocking mechanisms, architectural conventions, forbidden packages, known pitfalls, and verification commands required by downstream agents (DM-1 Blueprint Validator, DM-2 Sandbox Verifier, DM-3 Scoped Repair).

---

## 2. Contract & Schema Alignment (`contracts/models.py`)

The YAML profile must map **strictly and without omission** to the immutable `FrameworkProfile` model defined in `contracts/models.py`:

```python
class FrameworkProfile(BaseModel):
    id: str
    framework: str
    framework_version: str
    profile_revision: int
    java_version: str
    build_tool: str
    enabled: bool
    baseline_evidence: Optional[str] = None
    instruction_set_revision: str
    concepts: Dict[str, Dict]
    config: Dict
    test_style: Dict
    verify_commands: Dict
    forbidden_imports: List[str]
    allowed_exceptions: List[str]
    pitfalls: List[str]
    templates: Dict[str, str]
```

### Exact Field Mapping Specifications

| Field Name | Type | Mandatory / Optional | Target Value for `quarkus-3.yaml` | Rationale / Constraint |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `str` | Mandatory | `"quarkus-3"` | Unique profile identifier formatted as `{framework}-{version}`. |
| `framework` | `str` | Mandatory | `"quarkus"` | Framework family name (lowercase). |
| `framework_version` | `str` | Mandatory | `"3"` | Major version indicator string. |
| `profile_revision` | `int` | Mandatory | `1` | Schema revision counter for cache busting and updates. |
| `java_version` | `str` | Mandatory | `"17"` | LTS Java baseline for Quarkus 3.x. |
| `build_tool` | `str` | Mandatory | `"maven"` | Standard build system for hermetic execution in DM-2. |
| `enabled` | `bool` | Mandatory | `true` | Must be active and selectable by `get_profile`. |
| `baseline_evidence` | `Optional[str]` | Optional | `null` (or `"evidence/quarkus-3.json"`) | Audit trail reference for baseline validation. |
| `instruction_set_revision` | `str` | Mandatory | `"v1"` | Version tag for agent prompt instructions. |
| `concepts` | `Dict[str, Dict]` | Mandatory | *See Concepts Specification below* | Framework concepts (mocking, injection, rest endpoints). |
| `config` | `Dict` | Mandatory | *See Config Specification below* | Default configuration paths and key conventions. |
| `test_style` | `Dict` | Mandatory | *See Test Style Specification below* | Annotations and conventions for test classes. |
| `verify_commands` | `Dict` | Mandatory | *See Verify Commands below* | Deterministic commands for compilation and testing. |
| `forbidden_imports` | `List[str]` | Mandatory | *See Forbidden Imports below* | Packages disallowed in Quarkus 3 code generation. |
| `allowed_exceptions` | `List[str]` | Mandatory | *See Allowed Exceptions below* | Permitted exceptions during test failure triage. |
| `pitfalls` | `List[str]` | Mandatory | *See Pitfalls Specification below* | Common hallucination traps to avoid during repair. |
| `templates` | `Dict[str, str]` | Mandatory | *See Templates Specification below* | Named template identifiers or inline scaffolding. |

---

## 3. Detailed Data Specifications

### 3.1 Concepts Specification (`concepts`)
The `concepts` dictionary maps framework concepts to concrete annotation and import declarations. Crucially, the specification mandates:

```yaml
concepts:
  mock_in_test:
    annotations:
      - "@InjectMock"
    imports:
      - "io.quarkus.test.junit.mockito.InjectMock"
  dependency_injection:
    annotations:
      - "@Inject"
      - "@ApplicationScoped"
    imports:
      - "jakarta.inject.Inject"
      - "jakarta.enterprise.context.ApplicationScoped"
  rest_endpoint:
    annotations:
      - "@Path"
      - "@GET"
      - "@POST"
      - "@PUT"
      - "@DELETE"
      - "@Produces"
      - "@Consumes"
    imports:
      - "jakarta.ws.rs.Path"
      - "jakarta.ws.rs.GET"
      - "jakarta.ws.rs.POST"
      - "jakarta.ws.rs.PUT"
      - "jakarta.ws.rs.DELETE"
      - "jakarta.ws.rs.Produces"
      - "jakarta.ws.rs.Consumes"
      - "jakarta.ws.rs.core.MediaType"
      - "jakarta.ws.rs.core.Response"
  orm_entity:
    annotations:
      - "@Entity"
      - "@Table"
      - "@Id"
      - "@GeneratedValue"
    imports:
      - "jakarta.persistence.Entity"
      - "jakarta.persistence.Table"
      - "jakarta.persistence.Id"
      - "jakarta.persistence.GeneratedValue"
  transactional:
    annotations:
      - "@Transactional"
    imports:
      - "jakarta.transaction.Transactional"
```

### 3.2 Configuration Specification (`config`)
```yaml
config:
  file_path: "src/main/resources/application.properties"
  format: "properties"
  default_port: 8080
  properties:
    quarkus.http.port: 8080
    quarkus.log.level: "INFO"
```

### 3.3 Test Style Specification (`test_style`)
```yaml
test_style:
  class_annotations:
    - "@QuarkusTest"
  imports:
    - "io.quarkus.test.junit.QuarkusTest"
    - "org.junit.jupiter.api.Test"
    - "org.junit.jupiter.api.Assertions.*"
  assertion_library: "junit-jupiter"
```

### 3.4 Verify Commands (`verify_commands`)
Hermetic execution commands compatible with DM-2 offline runner:
```yaml
verify_commands:
  compile: "mvn clean compile -DskipTests"
  test: "mvn test"
  package: "mvn package -DskipTests"
```

### 3.5 Forbidden Imports (`forbidden_imports`)
To prevent cross-framework hallucination (e.g., Spring Boot leakage, JUnit 4, or deprecated `javax.*` packages):
```yaml
forbidden_imports:
  - "org.springframework."
  - "org.junit.Test"
  - "org.junit.Assert"
  - "javax.inject."
  - "javax.ws.rs."
  - "javax.persistence."
  - "javax.transaction."
```

### 3.6 Allowed Exceptions (`allowed_exceptions`)
```yaml
allowed_exceptions:
  - "jakarta.ws.rs.WebApplicationException"
  - "jakarta.ws.rs.NotFoundException"
  - "jakarta.ws.rs.BadRequestException"
  - "java.lang.IllegalArgumentException"
  - "java.lang.IllegalStateException"
```

### 3.7 Pitfalls (`pitfalls`)
```yaml
pitfalls:
  - "Never use @MockBean or @Autowired from Spring; use @InjectMock and @Inject."
  - "Quarkus 3 uses Jakarta EE 10 (jakarta.* namespace), never use javax.* packages."
  - "Field injection in Quarkus tests requires package-private or public fields, not private."
  - "Panache active record methods must not conflict with repository pattern usage."
```

### 3.8 Templates (`templates`)
```yaml
templates:
  resource: "templates/quarkus/Resource.java.jinja"
  entity: "templates/quarkus/Entity.java.jinja"
  repository: "templates/quarkus/Repository.java.jinja"
  test: "templates/quarkus/ResourceTest.java.jinja"
```

---

## 4. User Scenarios & Acceptance Testing

### User Story 1 - Pydantic Deserialization & Strict Typing (Priority: P1)
**User Journey**: When the framework loader reads `profiles/quarkus-3.yaml`, it deserializes the document directly into `contracts.models.FrameworkProfile` without data transformation or schema errors.  
**Why this priority**: Foundational contract validity. If the YAML cannot parse into the Pydantic model, all downstream components fail immediately.  
**Independent Test**:
- Read `profiles/quarkus-3.yaml` using PyYAML.
- Initialize `FrameworkProfile(**raw_yaml_dict)`.
- Assert instance creation succeeds, and all required attributes match expected types.

**Acceptance Scenarios**:
1. **Given** `profiles/quarkus-3.yaml` on disk, **When** loaded and passed to `FrameworkProfile.model_validate(data)`, **Then** validation succeeds with 0 validation errors.
2. **Given** the validated model, **When** inspecting `profile.framework`, `profile.framework_version`, and `profile.enabled`, **Then** the values are `"quarkus"`, `"3"`, and `True` respectively.

---

### User Story 2 - Quarkus 3 Mocking Concept Integrity (Priority: P1)
**User Journey**: When an agent requests the testing concepts for mocking, it accesses `concepts.mock_in_test` and retrieves the exact annotations and imports required for Quarkus JUnit tests without having hardcoded strings in Python.  
**Why this priority**: Mandated specifically by the user prompt and Constitution Rule 8.  
**Independent Test**:
- Inspect `profile.concepts["mock_in_test"]`.
- Check `"@InjectMock" in profile.concepts["mock_in_test"]["annotations"]`.
- Check `"io.quarkus.test.junit.mockito.InjectMock" in profile.concepts["mock_in_test"]["imports"]`.

**Acceptance Scenarios**:
1. **Given** the loaded `FrameworkProfile`, **When** accessing `profile.concepts["mock_in_test"]["annotations"]`, **Then** it contains exactly `["@InjectMock"]`.
2. **Given** the loaded `FrameworkProfile`, **When** accessing `profile.concepts["mock_in_test"]["imports"]`, **Then** it contains exactly `["io.quarkus.test.junit.mockito.InjectMock"]`.

---

### User Story 3 - Negative & Edge Case Validation (Priority: P2)
**User Journey**: Ensure that malformed, corrupted, or incomplete profile structures are immediately rejected by Pydantic before reaching runtime agents.  
**Why this priority**: Guard against regressions or schema drift.  
**Acceptance Scenarios**:
1. **Given** a profile missing mandatory keys (e.g. `pitfalls` or `test_style`), **When** validated against `FrameworkProfile`, **Then** Pydantic raises `ValidationError`.
2. **Given** a profile with wrong types (e.g. `profile_revision: "one"` instead of `int`), **When** validated, **Then** Pydantic raises `ValidationError`.

---

## 5. Blast Radius & Contract Impact Analysis

- **Affected Files**:
  - `profiles/quarkus-3.yaml` (new file)
  - `tests/agents/test_quarkus_profile.py` (new test file for verification)
- **Zero Impact on Existing Code**:
  - `contracts/models.py` remains completely untouched (immutable source of truth).
- **Downstream Consumers**:
  - `agents/profiles/loader.py` (`PF_01_Profile_Loader`) will consume this YAML directly via `get_profile("quarkus", "3")`.
  - `agents/blueprint/validate.py` (`DM_01_Blueprint_Validator`) relies on consistent profile models.

---

## 6. Functional Requirements

- **FR-001**: System MUST provide `profiles/quarkus-3.yaml` adhering strictly to `FrameworkProfile` model schema.
- **FR-002**: `profiles/quarkus-3.yaml` MUST specify `framework: "quarkus"`, `framework_version: "3"`, and `enabled: true`.
- **FR-003**: `profiles/quarkus-3.yaml` MUST define `concepts.mock_in_test` with `annotations: ["@InjectMock"]` and `imports: ["io.quarkus.test.junit.mockito.InjectMock"]`.
- **FR-004**: `profiles/quarkus-3.yaml` MUST specify `forbidden_imports` to isolate Quarkus from Spring and legacy libraries.
- **FR-005**: All dictionary keys and list values in `profiles/quarkus-3.yaml` MUST strictly conform to Pydantic types declared in `contracts/models.py`.

---

## 7. Success Criteria

- **SC-001**: Parsing `profiles/quarkus-3.yaml` via `pydantic.TypeAdapter(FrameworkProfile).validate_python(...)` passes cleanly with 0 errors.
- **SC-002**: Verification test suite executes via `pytest` and achieves 100% pass rate.
- **SC-003**: Static analysis via `ruff check` and `mypy` verifies full type safety against `contracts/models.py`.

---

## 8. Verification Strategy (Trust but Verify)

1. **Step 1 (Pre-implementation Test)**:
   Create `tests/agents/test_quarkus_profile.py` verifying:
   - File existence of `profiles/quarkus-3.yaml`.
   - Pydantic validation against `FrameworkProfile`.
   - Verification of `mock_in_test` annotations and imports.
   - Verification of all required contract fields.
   Run `pytest` to record the expected initial failure (file does not exist yet).
2. **Step 2 (Implementation)**:
   Create `profiles/quarkus-3.yaml` with the exact structure.
3. **Step 3 (Post-implementation Verification)**:
   Run `pytest tests/agents/test_quarkus_profile.py`, `ruff`, and `mypy` to record clean passing execution.

