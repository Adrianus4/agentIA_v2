# Feature Specification: DM_01_Blueprint_Validator

**Feature Identifier**: `DM_01_Blueprint_Validator`  
**Feature Branch**: `streamA/profiles-dm1`  
**Target Artifact**: `agents/blueprint/validate.py`  
**Contract Authority**: `contracts/models.py` (`UniformErrorBody`, `Diagnostic`, `ErrorCode`)  
**Status**: Pending Review  
**Date**: 2026-10-11  

---

## 1. Executive Summary & Purpose

The **Blueprint Validator** (DM-1) is the entry barrier for code generation and scaffolding within AgentIA v2. Before any file generation, scaffolding, or LLM-driven synthesis is initiated, the raw architectural blueprint provided by user input or prior planning phases must be validated deterministically.

In accordance with **Constitution Rule 3** (*"Contracts first: All agent components communicate strictly via typed Pydantic models in contracts/models.py"*) and **Rule 4** (*"Deterministic over generative"*), the Blueprint Validator performs fast, static checks to ensure all required top-level metadata exists and no duplicate entity models are defined.

---

## 2. API Contract & Function Signature

The validator must be implemented in `agents/blueprint/validate.py` with the following signature:

```python
from typing import Any, Dict
from contracts.models import Diagnostic, UniformErrorBody

def validate_blueprint(payload: Dict[str, Any]) -> UniformErrorBody:
    """
    Validate a raw blueprint dictionary against structural integrity rules.

    Args:
        payload: Dict containing blueprint definition.

    Returns:
        UniformErrorBody: Pydantic model containing:
            - valid: True if all checks pass, False if any violation found.
            - diagnostics: List[Diagnostic] detailing all errors detected.
    """
```

### Schema Alignment with `contracts/models.py`

```python
ErrorCode = Literal[
    "MISSING_FIELD", "INVALID_TYPE", "DUPLICATE_ENTITY_NAME",
    "MISSING_PRIMARY_KEY", "UNMAPPED_FOREIGN_KEY",
    "UNKNOWN_FRAMEWORK", "UNKNOWN_FRAMEWORK_VERSION",
    "UNKNOWN_PROFILE_REVISION", "PROFILE_DISABLED",
    "DUPLICATE_SOURCE_OF_TRUTH", "INVALID_JSON"
]

class Diagnostic(BaseModel):
    error_code: ErrorCode
    path: str
    message: str

class UniformErrorBody(BaseModel):
    valid: bool = False
    diagnostics: List[Diagnostic]
```

---

## 3. Validation Rules & Diagnostics Specification

The validator must execute multi-rule evaluation and accumulate all detected errors rather than aborting at the first failure:

### Rule 1: Required Top-Level Keys (`MISSING_FIELD`)
- **Required Keys**: `serviceName`, `packageName`, `entities`, `userStories`
- If any required key is absent, `None`, or an empty string where a string is expected:
  - `error_code`: `"MISSING_FIELD"`
  - `path`: The missing field name (e.g. `"serviceName"`, `"packageName"`, `"entities"`, `"userStories"`)
  - `message`: `"Required field '<field_name>' is missing or empty"`

### Rule 2: Field Type Integrity (`INVALID_TYPE`)
- `serviceName`: MUST be a string.
- `packageName`: MUST be a string.
- `entities`: MUST be a list.
- `userStories`: MUST be a list.
- If a provided key does not match its expected type:
  - `error_code`: `"INVALID_TYPE"`
  - `path`: The field name
  - `message`: `"Field '<field_name>' must be of type <expected_type>"`

### Rule 3: Entity Uniqueness (`DUPLICATE_ENTITY_NAME`)
- When `entities` is a list, each entity is represented as an object with a `"name"` property (or as a string name).
- If multiple entities share the same name (case-insensitive comparison):
  - `error_code`: `"DUPLICATE_ENTITY_NAME"`
  - `path`: `"entities[<index>].name"` or `"entities.<entity_name>"`
  - `message`: `"Duplicate entity name '<entity_name>' found at index <index>"`

---

## 4. User Scenarios & Acceptance Testing

### User Story 1 - Valid Blueprint Acceptance (Priority: P1)
**User Journey**: When a well-formed blueprint payload containing all required keys and unique entities is submitted, the validator confirms validity without errors.  
**Why this priority**: Happy path for blueprint ingestion into code generators.  
**Independent Test**:
- Call `validate_blueprint(valid_payload)`
- Assert `result.valid is True`
- Assert `len(result.diagnostics) == 0`

**Acceptance Scenarios**:
1. **Given** a blueprint containing valid `serviceName`, `packageName`, `entities` (with unique names), and `userStories`, **When** `validate_blueprint` is called, **Then** it returns `UniformErrorBody(valid=True, diagnostics=[])`.

---

### User Story 2 - Missing Required Keys Detection (Priority: P1)
**User Journey**: When a blueprint payload is missing one or more required keys, the validator flags each missing key with `MISSING_FIELD`.  
**Why this priority**: Guard against generating code from incomplete architecture blueprints.  
**Independent Test**:
- Call `validate_blueprint({"serviceName": "OrderService"})` (missing `packageName`, `entities`, `userStories`).
- Assert `result.valid is False`.
- Assert diagnostics contains `MISSING_FIELD` for `"packageName"`, `"entities"`, and `"userStories"`.

**Acceptance Scenarios**:
1. **Given** a payload missing `serviceName`, **When** validated, **Then** `result.valid is False` and `diagnostics` has an entry with `error_code == "MISSING_FIELD"` and `path == "serviceName"`.
2. **Given** an empty dictionary `{}`, **When** validated, **Then** all 4 required keys are reported in `diagnostics`.

---

### User Story 3 - Duplicate Entity Name Rejection (Priority: P1)
**User Journey**: When a blueprint declares two or more entities with identical names (e.g., two `Customer` entities), the validator catches the duplication.  
**Why this priority**: Prevents conflicting Java class generation and JPA entity collision.  
**Independent Test**:
- Provide payload with `entities: [{"name": "Customer"}, {"name": "customer"}]`.
- Assert `result.valid is False`.
- Assert diagnostics contains `error_code == "DUPLICATE_ENTITY_NAME"`.

**Acceptance Scenarios**:
1. **Given** `entities` list with duplicate names, **When** validated, **Then** `result.valid is False` and `diagnostics` contains `"DUPLICATE_ENTITY_NAME"`.

---

### User Story 4 - Multi-Error Accumulation (Priority: P2)
**User Journey**: When a blueprint contains both missing keys and invalid types or duplicate entities, the validator returns all issues simultaneously.  
**Why this priority**: Avoids frustrating "fix-one-error-at-a-time" feedback cycles for upstream agents.  
**Acceptance Scenarios**:
1. **Given** a payload missing `userStories` and containing duplicate entities, **When** validated, **Then** `diagnostics` contains both the `MISSING_FIELD` diagnostic and the `DUPLICATE_ENTITY_NAME` diagnostic.

---

## 5. Blast Radius & Contract Impact Analysis

- **Affected Files**:
  - `agents/blueprint/validate.py` (new implementation)
  - `agents/blueprint/__init__.py` (module initialization)
  - `tests/agents/test_blueprint_validator.py` (unit tests covering all rules)
- **Zero Impact on Existing Code**:
  - `contracts/models.py` remains strictly unchanged.
  - `agents/profiles/` remains strictly unchanged.
  - `profiles/quarkus-3.yaml` remains strictly unchanged.

---

## 6. Functional Requirements

- **FR-001**: System MUST define `validate_blueprint(payload: dict) -> UniformErrorBody` in `agents/blueprint/validate.py`.
- **FR-002**: Function MUST return an instance of `UniformErrorBody` as defined in `contracts/models.py`.
- **FR-003**: Function MUST validate presence of `serviceName`, `packageName`, `entities`, and `userStories`.
- **FR-004**: Function MUST record `MISSING_FIELD` diagnostics for any absent or empty required keys.
- **FR-005**: Function MUST record `DUPLICATE_ENTITY_NAME` diagnostics for duplicate entities in `entities`.
- **FR-006**: Function MUST record `INVALID_TYPE` diagnostics if fields do not match expected types.
- **FR-007**: Function MUST return `valid: True` and empty diagnostics if and only if zero violations are found.

---

## 7. Success Criteria

- **SC-001**: Clean valid blueprint yields `UniformErrorBody(valid=True, diagnostics=[])`.
- **SC-002**: Missing keys, wrong types, and duplicate entities yield `UniformErrorBody(valid=False, diagnostics=[...])` with exact `ErrorCode` matches.
- **SC-003**: 100% test pass rate in `tests/agents/test_blueprint_validator.py`.
- **SC-004**: Zero `mypy` or `ruff` warnings across `agents/blueprint/`.

---

## 8. Verification Strategy (Trust but Verify)

1. **Step 1 (Red Phase / TDD)**:
   Write unit test suite in `tests/agents/test_blueprint_validator.py`:
   - Valid blueprint payload $\rightarrow$ `valid: True`, `diagnostics: []`
   - Missing required keys (`serviceName`, `packageName`, `entities`, `userStories`) $\rightarrow$ `valid: False`, `MISSING_FIELD`
   - Invalid types (e.g. `serviceName: 123`, `entities: "not-a-list"`) $\rightarrow$ `valid: False`, `INVALID_TYPE`
   - Duplicate entity names (exact and case-insensitive) $\rightarrow$ `valid: False`, `DUPLICATE_ENTITY_NAME`
   - Multiple errors combined $\rightarrow$ all accumulated
   Run `pytest tests/agents/test_blueprint_validator.py` $\rightarrow$ Capture failing trace (module not found).
2. **Step 2 (Green Phase / Minimal Implementation)**:
   Implement `agents/blueprint/validate.py`.
3. **Step 3 (Post-Implementation Verification)**:
   Run `pytest`, `mypy`, and `ruff` $\rightarrow$ Capture 100% passing trace.

