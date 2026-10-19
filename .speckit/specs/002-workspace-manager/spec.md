# Feature Specification: Workspace Manager

**Feature Branch**: `002-workspace-manager`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Define apply_patch(workspace_dir: str, patch_content: str) -> None in app/orchestrator/patching.py. It must reject absolute paths outside workspace_dir and relative traversal such as ../, and support standard Unified Diff patch application."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Apply an approved workspace patch (Priority: P1)

As an orchestrator, I want to apply a standard Unified Diff to the selected workspace, so that an approved repair can update source files while preserving normal patch semantics.

**Why this priority**: Applying a repair patch is the core workspace-management capability and is required for the orchestrator repair loop.

**Independent Test**: Create a temporary workspace with a target file, apply a valid Unified Diff, and verify that the target file contains the expected change while unrelated files remain unchanged.

**Acceptance Scenarios**:

1. **Given** a workspace and a valid Unified Diff targeting a file inside it, **When** the patch is applied, **Then** the function completes without returning a value and the targeted file contains the patched content.
2. **Given** a valid patch that creates a new file inside the workspace, **When** the patch is applied, **Then** the new file is created at the requested relative path.
3. **Given** a valid patch that deletes a file inside the workspace, **When** the patch is applied, **Then** the requested file is removed and no file outside the workspace is changed.

### User Story 2 - Reject unsafe patch targets (Priority: P1)

As a workspace owner, I want unsafe patch paths rejected before any file is changed, so that a repair agent cannot escape the workspace or overwrite unrelated files.

**Why this priority**: Path traversal prevention is a non-negotiable security boundary for agent-generated patches.

**Independent Test**: Submit patches containing each forbidden path form and verify that each is rejected before the filesystem changes, including checks for unchanged sentinel files.

**Acceptance Scenarios**:

1. **Given** a patch whose target path contains a relative traversal component such as `../outside.txt`, **When** the patch is submitted, **Then** the function rejects it before applying any hunk.
2. **Given** a patch whose target path is an absolute path outside `workspace_dir`, **When** the patch is submitted, **Then** the function rejects it before applying any hunk.
3. **Given** a patch whose target path uses traversal that is disguised by redundant segments, such as `nested/../../outside.txt`, **When** the patch is submitted, **Then** the function rejects it before applying any hunk.
4. **Given** a patch containing one safe file and one unsafe file, **When** the patch is submitted, **Then** the entire patch is rejected atomically and the safe file is unchanged.
5. **Given** a path that resolves inside the workspace only after following a symlink or equivalent indirection, **When** the patch is submitted, **Then** the function rejects the path unless the resolved target remains within the workspace boundary.

### User Story 3 - Report invalid patch input clearly (Priority: P2)

As an orchestrator operator, I want malformed or unappliable patches to fail explicitly, so that repair failures can be diagnosed without silent partial success.

**Why this priority**: Explicit failures allow the bounded repair loop to classify and handle patch errors safely.

**Independent Test**: Submit malformed Unified Diffs and patches with context mismatches, then verify that an explicit exception is raised and the workspace remains unchanged.

**Acceptance Scenarios**:

1. **Given** malformed patch text, **When** the function is called, **Then** it raises an explicit patch-validation error and changes no files.
2. **Given** a syntactically valid patch whose context does not match the current file, **When** the function is called, **Then** it raises an explicit application error and does not leave a partial patch behind.
3. **Given** an empty patch, **When** the function is called, **Then** it rejects the request explicitly without changing the workspace.

## Edge Cases

- The workspace directory does not exist, is not a directory, or cannot be accessed.
- A patch names the workspace root itself, a directory, or a path containing a null byte.
- A patch uses `a/` and `b/` Unified Diff prefixes, `/dev/null`, quoted paths, spaces, or Unicode characters.
- A patch uses mixed separators or repeated separators and attempts to evade traversal checks.
- A patch contains multiple files where a later hunk fails after an earlier hunk would otherwise succeed.
- A symlink inside the workspace points outside the workspace.
- The patch text is valid but attempts to modify a file not permitted by the workspace boundary.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose `apply_patch(workspace_dir: str, patch_content: str) -> None` at the workspace-manager boundary.
- **FR-002**: The system MUST support standard Unified Diff patches for file creation, modification, and deletion.
- **FR-003**: The system MUST validate every patch target before applying any hunk or filesystem mutation.
- **FR-004**: The system MUST reject any relative patch target containing a parent-directory traversal component (`..`) after path normalization.
- **FR-005**: The system MUST reject any absolute patch target whose canonical path is outside the canonical `workspace_dir`.
- **FR-006**: The system MUST reject traversal attempts that become unsafe after normalization, including redundant segments, mixed separators, and equivalent path forms.
- **FR-007**: The system MUST reject a patch if any target resolves through a symlink or other indirection to a location outside the canonical workspace boundary.
- **FR-008**: The system MUST reject the complete patch before mutation when any one target is unsafe; safe targets in the same patch MUST remain unchanged.
- **FR-009**: The system MUST apply accepted patches atomically from the caller’s perspective: if validation or application fails, it MUST NOT leave partial file changes.
- **FR-010**: The system MUST raise an explicit, actionable error for a missing or invalid workspace, empty or malformed patch, unsafe path, and hunk/context mismatch.
- **FR-011**: The system MUST preserve Unified Diff semantics for `a/` and `b/` prefixes and `/dev/null` creation/deletion markers where those forms refer to paths inside the workspace.
- **FR-012**: The system MUST return `None` after a successful application and MUST NOT return a success-shaped result when the patch was not fully applied.
- **FR-013**: The system MUST NOT modify files outside the requested workspace, including files named by absolute paths outside it or by relative traversal.

### Key Entities *(include if feature involves data)*

- **Workspace Boundary**: The canonical directory within which all patch targets must remain.
- **Unified Diff**: The patch document containing file paths, hunks, context, additions, and deletions.
- **Patch Target**: A source or destination path extracted from a Unified Diff and checked against the workspace boundary.
- **Patch Application Error**: An explicit failure category identifying invalid input, unsafe path, unavailable workspace, or failed hunk application.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of valid in-workspace Unified Diff tests for file creation, modification, and deletion complete successfully.
- **SC-002**: 100% of test cases containing `../`, normalized parent traversal, or absolute paths outside the workspace are rejected before any file mutation.
- **SC-003**: 100% of mixed safe/unsafe multi-file patches leave every workspace file byte-for-byte unchanged after rejection.
- **SC-004**: 100% of malformed or context-mismatched patch tests produce an explicit failure and leave no partial changes.
- **SC-005**: 0 files outside the canonical workspace boundary are modified by successful or rejected patch attempts.

## Assumptions

- The caller supplies a local filesystem workspace that the process is permitted to read and write.
- Standard Unified Diff path syntax is the supported patch format; unrelated patch formats are out of scope.
- The workspace boundary is established by canonical path resolution before target validation.
- Atomicity means the function either applies the complete patch or restores the pre-call workspace state for all affected files.
- File permissions, ownership changes, and metadata-only patch operations are outside the initial feature scope unless required by standard Unified Diff application.

