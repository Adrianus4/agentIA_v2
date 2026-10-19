# Feature Specification: Official Quarkus Scaffolding

**Feature Branch**: `002-official-quarkus-scaffolding`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: Review and implement the SC-1 proposal against the current AgentIA v2 state using Spec-Kit tools.

## User Scenarios & Testing

### User Story 1 - Generate a Valid Project Scaffold (Priority: P1)

As an AgentIA user, I want a project scaffold produced by the official framework tooling so that generated business code starts from a valid, reproducible project structure.

**Why this priority**: A valid scaffold is the foundation for all subsequent generation and verification.

**Independent Test**: Submit a valid blueprint with a supported framework profile and confirm that the scaffold completes, records its manifest, and remains inside the requested workspace.

**Acceptance Scenarios**:

1. **Given** a valid blueprint and an enabled profile scaffold catalog, **When** scaffolding runs, **Then** it returns success with the selected tool, pinned version, extensions, and a non-empty manifest.
2. **Given** a scaffold request with an invalid artifact identifier or path traversal, **When** the request is validated, **Then** no process starts and a typed validation error is returned.

### User Story 2 - Derive Extensions from Requirements (Priority: P1)

As an AgentIA user, I want the selected framework extensions to reflect the requirements graph so that the generated project includes only supported capabilities.

**Why this priority**: Extension selection determines whether the scaffold can compile and whether the generated project matches the blueprint.

**Independent Test**: Provide blueprints with different entities, database types, validation rules, and optional capabilities, then compare the deterministic extension lists.

**Acceptance Scenarios**:

1. **Given** a blueprint with entities and a supported database, **When** extensions are derived, **Then** persistence, REST/JSON, and the matching database driver are included once in deterministic order.
2. **Given** a blueprint requesting an extension outside the profile catalog, **When** the blueprint is validated, **Then** the request is rejected with an unsupported-extension diagnostic naming the offending field.

### User Story 3 - Verify Offline Compatibility Before Generation (Priority: P1)

As an AgentIA operator, I want the scaffold verified in the hermetic environment before LLM generation continues so that missing dependencies fail early and predictably.

**Why this priority**: The verifier must remain offline and reproducible, while scaffolding is the only networked preparation step.

**Independent Test**: Run scaffold verification against a warmed catalog combination and confirm the offline compile command succeeds; run an unavailable combination and confirm a typed failure.

**Acceptance Scenarios**:

1. **Given** a successful scaffold, **When** the offline pre-generation verification runs, **Then** it uses the verifier boundary and reports a parseable exit result.
2. **Given** a scaffold whose dependencies are not available in the offline cache, **When** verification runs, **Then** generation stops with the failure evidence and does not claim success.

### User Story 4 - Preserve Existing Generation and Repair Behavior (Priority: P2)

As an AgentIA maintainer, I want official scaffolding to be additive and optional so that existing profile loading, generation, verification, repair, and API behavior remain compatible.

**Why this priority**: Existing tracks and callers must not regress while the new scaffold capability is introduced.

**Independent Test**: Run existing graph, pipeline, API, and frontend suites with scaffolding disabled and confirm unchanged behavior.

**Acceptance Scenarios**:

1. **Given** a request without scaffold configuration, **When** orchestration runs, **Then** the existing generation path remains available.
2. **Given** a profile without scaffold configuration, **When** orchestration runs, **Then** it returns a clear capability error rather than constructing an unsafe default command.

## Edge Cases

- Empty extension catalogs must reject any derived non-base extension.
- Duplicate extensions must be de-duplicated before command construction.
- Invalid placeholders in a command template must fail profile validation.
- Absolute paths, `..` segments, shell metacharacters, whitespace, and uppercase package names must be rejected where the contract forbids them.
- A scaffolder process that exits successfully without a manifest must be treated as failure.
- Scaffold output outside the workspace root must be rejected.
- Raw tool output must be capped and must not contain API keys or full source contents.
- A networked scaffolder must never be reused as the offline verifier.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose typed scaffold configuration, request, result, and protocol contracts.
- **FR-002**: System MUST derive extensions deterministically from blueprint features and profile data.
- **FR-003**: System MUST validate every derived and user-selected extension against the profile allowlist.
- **FR-004**: System MUST construct scaffolder commands as validated argument arrays, never shell command strings.
- **FR-005**: System MUST reject unsafe identifiers and paths before starting a process.
- **FR-006**: System MUST restrict scaffold output to the configured workspace root.
- **FR-007**: System MUST record tool name, pinned version, selected extensions, manifest metadata, timing, exit code, and capped output.
- **FR-008**: System MUST verify scaffold output through the existing offline verifier before LLM generation.
- **FR-009**: System MUST keep the networked scaffolder and offline verifier as separate execution roles.
- **FR-010**: System MUST preserve the current generation and repair path when scaffolding is not configured.
- **FR-011**: System MUST add validation diagnostics for unsupported extensions and invalid scaffold configuration.
- **FR-012**: System MUST provide automated tests for deterministic derivation, input rejection, workspace containment, manifest requirements, offline verification, and backward compatibility.

### Key Entities

- **ScaffoldConfig**: Profile-owned tool, version, command template, base extensions, allowed extensions, and feature-to-extension mappings.
- **ScaffoldRequest**: Validated project identity, Java version, extension list, and workspace path.
- **ScaffoldResult**: Typed execution result and manifest evidence.
- **ExtensionMap**: Generic blueprint feature to profile extension mapping.
- **ManifestEvidence**: Path, digest, and size for scaffold output.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of accepted scaffold commands are represented as argument arrays with no shell interpolation.
- **SC-002**: 100% of scaffold output manifests contain at least one file and every listed file is inside the requested workspace.
- **SC-003**: Deterministic derivation produces identical ordered extension lists for identical blueprint/profile inputs across repeated runs.
- **SC-004**: Existing backend and frontend regression suites remain green with scaffolding disabled.
- **SC-005**: Every invalid identifier, unsupported extension, invalid placeholder, and unsafe output path is rejected before process execution.
- **SC-006**: Offline verification produces a parseable success or failure result for every catalog combination covered by the profile.

## Assumptions

- The initial implementation targets the existing Quarkus profile and Maven execution path.
- The profile catalog is curated and pre-warmed; dynamic arbitrary extension installation is out of scope.
- The official tooling command and flags must be verified against the installed Maven/Quarkus tooling before enabling live scaffolding.
- Existing users may continue using the current generation path when no scaffold configuration is present.
- Network access is permitted only to the isolated scaffolder role; verification remains offline.
