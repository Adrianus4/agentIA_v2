# Feature Specification: DM_03_Scoped_Repair

**Feature Identifier**: `DM_03_Scoped_Repair`  
**Feature Branch**: `streamC/dm3-repair`  
**Target Artifacts**:  
- `agents/repair/__init__.py`  
- `agents/repair/guards.py`  
- `agents/repair/prompt.py`  
- `agents/repair/service.py`  
- `tests/agents/repair/test_guards.py`  
- `tests/agents/repair/test_prompt.py`  
- `tests/agents/repair/test_service.py`  
**Contract Authority**: `contracts/models.py` (`RepairRequest`, `RepairResult`, `GuardReport`, `FrameworkProfile`)  
**Status**: Ready for Implementation  
**Date**: 2026-10-11  

---

## 1. Executive Summary & Purpose

The **DM-3 Scoped Repair microservice ("The Surgeon")** is the targeted code generation and repair component of the AgentIA v2 pipeline. It synthesizes minimal, correct source code patches to address compilation errors and test failures diagnosed by DM-2.

In strict adherence to:
- **Constitution Rule 1 & 2** (*Specs before code, Tests first*).
- **Constitution Rule 3** (*Contracts first: Typed Pydantic models in `contracts/models.py`*).
- **Constitution Rule 6** (*Validate every LLM output*).
- **Constitution Rule 7** (*Bounded loops: Repair cycle capped at 3 attempts*).
- **Constitution Rule 8** (*Framework knowledge lives in profiles: Agents are framework-agnostic. No framework literals like `@InjectMock` or framework names in Python source code*).
- **Constitution Rule 9** (*Patch safety is non-negotiable: Patches must pass deterministic guards G1 and G7*).
- **Constitution Rule 11** (*Observability everywhere: propagate `trace_id`*).

---

## 2. API Contracts & Signatures

### 2.1 Patch Guards (`agents/repair/guards.py`)

```python
from typing import List, Set
from contracts.models import GuardReport, RepairRequest

def extract_touched_files(patch_text: str) -> List[str]:
    """
    Parses a unified diff string to extract all touched file paths,
    normalizing relative paths, git prefixes (a/, b/), and ignoring /dev/null.
    """
    ...

def evaluate_guards(request: RepairRequest, patch_text: str) -> GuardReport:
    """
    Evaluates patch safety against deterministic guards:
    - Guard G1: Fail if any touched file is not explicitly in request.allowed_paths.
    - Guard G7: Fail if pom.xml is modified unless pom.xml is in request.allowed_paths.

    Returns:
        GuardReport: passed status and list of failed guard IDs ("G1", "G7").
    """
    ...
```

### 2.2 Repair Prompt Builder (`agents/repair/prompt.py`)

```python
from contracts.models import FrameworkProfile, RepairRequest

def build_repair_prompt(profile: FrameworkProfile, request: RepairRequest) -> str:
    """
    Constructs an LLM prompt string that dynamically injects framework conventions
    from profile.concepts, profile.forbidden_imports, profile.pitfalls, and profile.test_style,
    along with failing_file content, diagnostics issues, and allowed paths.
    Zero framework-specific literals may be hardcoded in Python.
    """
    ...
```

### 2.3 Scoped Repair Service (`agents/repair/service.py`)

```python
from typing import Callable, Optional
from contracts.models import FrameworkProfile, RepairRequest, RepairResult

class ScopedRepairService:
    """
    Coordinates prompt construction, patch generation via LLM or generator,
    and strict patch guard evaluation, returning a typed RepairResult.
    """
    def __init__(
        self,
        patch_generator: Optional[Callable[[str], str]] = None,
    ) -> None:
        ...

    def repair(
        self,
        profile: FrameworkProfile,
        request: RepairRequest,
        trace_id: str = "trace-default",
    ) -> RepairResult:
        ...
```

---

## 3. Requirements & Acceptance Criteria

### 3.1 Unified Diff Parsing & Normalization
- **FR-001**: System MUST extract file paths from unified diff headers:
  - `--- a/<path>` and `+++ b/<path>`
  - `diff --git a/<path> b/<path>`
  - `Index: <path>`
  - `rename to <path>` / `rename from <path>`
- **FR-002**: System MUST ignore `/dev/null` indicating added or removed files.
- **FR-003**: System MUST strip quotes, trailing timestamps, and normalize directory paths (resolving `.` and `..`).
- **FR-004**: System MUST strip git prefixes `a/` and `b/` when referencing repository files.

### 3.2 Guard Evaluation
- **FR-005 (Guard G1)**: If any touched path is not present in `request.allowed_paths` (normalized), Guard G1 MUST fail and `"G1"` MUST be included in `failed_guards`.
- **FR-006 (Guard G7)**: If `pom.xml` (or any path whose filename is `pom.xml`) is modified, Guard G7 MUST fail and `"G7"` MUST be included in `failed_guards`, unless `pom.xml` is explicitly included in `request.allowed_paths`.
- **FR-007 (Multiple Violations)**: If a patch touches an unallowed `pom.xml`, both `"G1"` and `"G7"` MUST be reported in `failed_guards`.
- **FR-008 (Pass Report)**: If all touched files are allowed and `pom.xml` rules are respected, `passed` MUST be `True` and `failed_guards` MUST be empty.

### 3.3 Dynamic Prompt Generation
- **FR-009**: The prompt MUST dynamically interpolate:
  - `profile.framework` and `profile.framework_version`
  - `profile.java_version` and `profile.build_tool`
  - `profile.concepts` annotations and imports
  - `profile.pitfalls` and `profile.forbidden_imports`
  - `request.failing_file.path` and `request.failing_file.content`
  - `request.issues` diagnostic items (file path, line number, column number, error type, message)
  - `request.allowed_paths`
- **FR-010**: No framework literals or framework names (e.g., framework brands, specific annotations) may be hardcoded in Python code.

### 3.4 Repair Service & Execution
- **FR-011**: System MUST return a `RepairResult` with:
  - `outcome="PATCHED"` when guards pass.
  - `outcome="REJECTED_BY_GUARD"` when guards fail.
  - `outcome="NO_FIX"` when budget is exhausted or no patch generated.
- **FR-012**: System MUST propagate `trace_id` through the result.

---

## 4. Test Strategy

1. **Guard Tests (`tests/agents/repair/test_guards.py`)**:
   - Single allowed file patch -> passes G1 & G7.
   - Patch touching unallowed file -> fails G1.
   - Sneaking `pom.xml` in diff when not allowed -> fails G1 & G7.
   - Patch touching `pom.xml` when `pom.xml` is in `allowed_paths` -> passes G1 & G7.
   - Adversarial diffs:
     - Multi-file patch with hidden pom.xml hunk.
     - Path traversal (`a/src/../../pom.xml`).
     - Prefixes (`b/pom.xml`, `./pom.xml`).
     - Subdirectory `pom.xml` (`module/pom.xml`).
     - Renaming file to `pom.xml`.
     - Deleting file `/dev/null`.
     - Git header only (`diff --git a/pom.xml b/pom.xml`).
     - Timestamp suffixes in unified diff (`--- a/file\t2026-10-11`).

2. **Prompt Tests (`tests/agents/repair/test_prompt.py`)**:
   - Dynamic interpolation of concepts, annotations, imports from `profile`.
   - Dynamic inclusion of diagnostics issues.
   - Dynamic inclusion of failing file path and source code.
   - Dynamic inclusion of allowed paths.
   - Static inspection asserting NO framework literals are hardcoded in `agents/repair/prompt.py`.

3. **Service Tests (`tests/agents/repair/test_service.py`)**:
   - Valid patch generation returning `outcome="PATCHED"`.
   - Malicious/invalid patch generation returning `outcome="REJECTED_BY_GUARD"`.
   - Empty patch returning `outcome="NO_FIX"`.
   - Trace ID propagation.
