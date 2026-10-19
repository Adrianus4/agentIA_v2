# Feature Specification: PF_01_Profile_Loader

**Feature Identifier**: `PF_01_Profile_Loader`  
**Feature Branch**: `streamA/profiles-dm1`  
**Target Artifact**: `agents/profiles/loader.py`  
**Contract Authority**: `contracts/models.py` (`FrameworkProfile`, `UnknownFramework`, `ProfileDisabled`, `UnknownFrameworkVersion`)  
**Status**: Pending Review  
**Date**: 2026-10-11  

---

## 1. Executive Summary & Purpose

The **Profile Loader** microservice is the single programmatic interface used by AgentIA v2 agents to access framework runtime rules, compilation directives, testing styles, and forbidden imports.

In accordance with **Constitution Rule 8** (*"Framework knowledge lives in profiles: Agents are framework-agnostic. No Quarkus or Spring literals may appear in agent Python code; they must be resolved dynamically from profiles/*.yaml"*), the loader dynamically discovers, parses, validates, and serves `FrameworkProfile` objects from YAML files stored in the `profiles/` directory.

The loader ensures that invalid, disabled, or unconfigured frameworks are halted deterministically before reaching LLM generation or sandbox compilation stages.

---

## 2. API Contract & Function Signature

The loader must be implemented in `agents/profiles/loader.py` and expose the primary interface:

```python
from pathlib import Path
from typing import Optional, Union
from contracts.models import FrameworkProfile, UnknownFramework, ProfileDisabled, UnknownFrameworkVersion

def get_profile(
    framework: str,
    framework_version: str,
    profiles_dir: Optional[Union[str, Path]] = None
) -> FrameworkProfile:
    """
    Resolve, load, and validate a FrameworkProfile from disk.

    Args:
        framework: The framework identifier (e.g., 'quarkus', 'spring-boot').
        framework_version: The major version string (e.g., '3', '3.2').
        profiles_dir: Optional path override for the profiles directory.
                     Defaults to the project root 'profiles/' directory.

    Returns:
        FrameworkProfile: Validated Pydantic model instance from contracts/models.py.

    Raises:
        UnknownFramework: If no profile YAML matches the framework name or version.
        ProfileDisabled: If the matched profile YAML has `enabled: false`.
        pydantic.ValidationError: If the profile YAML schema violates FrameworkProfile contract.
    """
```

### Exception Semantics from `contracts/models.py`

| Condition | Raised Exception | Exception Superclass |
| :--- | :--- | :--- |
| Framework not recognized (no matching YAML) | `UnknownFramework` | `FrameworkProfileErrors` |
| Framework recognized but version not found | `UnknownFramework` (or `UnknownFrameworkVersion`) | `FrameworkProfileErrors` |
| Framework found but `enabled == False` | `ProfileDisabled` | `FrameworkProfileErrors` |
| Corrupted or schema-nonconforming YAML | `pydantic.ValidationError` | `ValueError` |

---

## 3. Profile Discovery & Resolution Logic

1. **Resolution Path**:
   - By default, search in `<PROJECT_ROOT>/profiles/`.
   - File naming convention: `<profiles_dir>/{framework}-{framework_version}.yaml` (e.g., `profiles/quarkus-3.yaml`).
   - If a direct filename match is not found, scan all `*.yaml` and `*.yml` files in `profiles_dir`, reading their `framework` and `framework_version` metadata.
2. **Case Normalization**:
   - Inputs `framework` and `framework_version` should be trimmed and lowercased for lookup comparison.
3. **Status Check**:
   - Upon successful deserialization into `FrameworkProfile`, check `profile.enabled`.
   - If `profile.enabled is False`, raise `ProfileDisabled(f"Profile '{profile.id}' is disabled")`.
4. **Caching Strategy (Deterministic & Fast)**:
   - Use an in-memory dictionary cache to avoid redundant filesystem reads for identical `(framework, framework_version, profiles_dir)` queries.
   - Cache invalidation / reload support for testing if necessary.

---

## 4. User Scenarios & Acceptance Testing

### User Story 1 - Successful Profile Retrieval (Priority: P1)
**User Journey**: An agent component requests the Quarkus 3 profile via `get_profile("quarkus", "3")` and receives a verified `FrameworkProfile` instance.  
**Why this priority**: Core happy path for all downstream pipeline microservices.  
**Independent Test**:
- Call `get_profile("quarkus", "3")`.
- Assert return value is instance of `contracts.models.FrameworkProfile`.
- Assert `profile.framework == "quarkus"`, `profile.framework_version == "3"`, and `profile.enabled is True`.

**Acceptance Scenarios**:
1. **Given** `profiles/quarkus-3.yaml` exists and is enabled, **When** `get_profile("quarkus", "3")` is invoked, **Then** a valid `FrameworkProfile` is returned.
2. **Given** case variation `get_profile("QUARKUS", "3")`, **When** invoked, **Then** it resolves `profiles/quarkus-3.yaml` identically.

---

### User Story 2 - Unknown Framework Handling (Priority: P1)
**User Journey**: When a request queries an unsupported or nonexistent framework (e.g. `django` or `nonexistent`), the system raises `UnknownFramework` immediately.  
**Why this priority**: Guard against pipeline crashes or undefined behaviors when unsupported stacks are requested.  
**Independent Test**:
- Call `get_profile("django", "5")`.
- Assert `UnknownFramework` exception is raised.

**Acceptance Scenarios**:
1. **Given** no profile exists for framework `"django"`, **When** `get_profile("django", "5")` is invoked, **Then** `UnknownFramework` is raised.
2. **Given** framework `"quarkus"` exists for version `"3"`, **When** `get_profile("quarkus", "99")` is invoked, **Then** `UnknownFramework` (or `UnknownFrameworkVersion`) is raised.

---

### User Story 3 - Disabled Profile Handling (Priority: P1)
**User Journey**: When a framework profile exists but has been administratively disabled (`enabled: false`), the system prevents its usage by raising `ProfileDisabled`.  
**Why this priority**: Allows deprecating or quarantining framework versions without deleting profile definitions.  
**Independent Test**:
- Point `profiles_dir` to a temporary directory with a profile having `enabled: false`.
- Call `get_profile("disabled-fw", "1")`.
- Assert `ProfileDisabled` exception is raised.

**Acceptance Scenarios**:
1. **Given** a profile with `enabled: false`, **When** `get_profile(...)` is called for that profile, **Then** `ProfileDisabled` is raised.

---

### User Story 4 - Strict Contract Validation on Corrupt Profiles (Priority: P2)
**User Journey**: If a profile YAML is syntactically invalid or misses mandatory contract fields, the loader refuses to return a broken object.  
**Why this priority**: Zero tolerance for schema drift (`contracts/models.py` as immutable single source of truth).  
**Acceptance Scenarios**:
1. **Given** a YAML file missing mandatory fields (e.g. `verify_commands`), **When** loaded, **Then** `pydantic.ValidationError` is raised.

---

## 5. Blast Radius & Contract Impact Analysis

- **Affected Files**:
  - `agents/profiles/loader.py` (new implementation)
  - `agents/profiles/__init__.py` (module initialization)
  - `tests/agents/test_profile_loader.py` (unit tests covering all acceptance criteria)
- **Zero Impact on Existing Code**:
  - `contracts/models.py` remains strictly unchanged.
  - `profiles/quarkus-3.yaml` remains strictly unchanged.
- **Dependencies**:
  - `pyyaml` (already in pyproject.toml)
  - `pydantic` (already in pyproject.toml)

---

## 6. Functional Requirements

- **FR-001**: System MUST define `get_profile(framework: str, framework_version: str, profiles_dir: Optional[Path] = None) -> FrameworkProfile` in `agents/profiles/loader.py`.
- **FR-002**: Function MUST return an instance of `FrameworkProfile` strictly matching `contracts/models.py`.
- **FR-003**: Function MUST raise `UnknownFramework` when the requested framework or version cannot be resolved.
- **FR-004**: Function MUST raise `ProfileDisabled` when the resolved profile has `enabled: false`.
- **FR-005**: Function MUST support optional `profiles_dir` parameter for dependency injection and test isolation.

---

## 7. Success Criteria

- **SC-001**: `get_profile("quarkus", "3")` resolves `profiles/quarkus-3.yaml` and returns valid `FrameworkProfile`.
- **SC-002**: 100% of negative test cases (`UnknownFramework`, `ProfileDisabled`, `ValidationError`) pass in `tests/agents/test_profile_loader.py`.
- **SC-003**: `mypy` and `ruff check` complete with 0 errors across `agents/profiles/` and `tests/agents/`.

---

## 8. Verification Strategy (Trust but Verify)

1. **Step 1 (Red Phase / TDD)**:
   Write unit test suite in `tests/agents/test_profile_loader.py`:
   - Valid resolution: `get_profile("quarkus", "3")`
   - Unknown framework: `get_profile("unknown", "1")` -> raises `UnknownFramework`
   - Unknown version: `get_profile("quarkus", "99")` -> raises `UnknownFramework` or `UnknownFrameworkVersion`
   - Disabled profile: temporary profile with `enabled: false` -> raises `ProfileDisabled`
   - Corrupt profile: invalid schema -> raises `ValidationError`
   Run `pytest tests/agents/test_profile_loader.py` in terminal $\rightarrow$ Capture failing trace (module not found).
2. **Step 2 (Green Phase / Minimal Implementation)**:
   Implement `agents/profiles/loader.py` with minimal, clean logic.
3. **Step 3 (Refactor & Tool Verification)**:
   Run `pytest tests/agents/test_profile_loader.py`, `mypy agents/profiles/`, and `ruff check agents/profiles/` $\rightarrow$ Capture 100% passing trace.

