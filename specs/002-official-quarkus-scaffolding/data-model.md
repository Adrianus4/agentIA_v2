# Data Model: Official Quarkus Scaffolding

## ScaffoldConfig

Profile-owned configuration:

- `tool`: supported tool identifier.
- `tool_version`: pinned version string.
- `command_template`: argv list with an allowlisted placeholder vocabulary.
- `base_extensions`: extensions always included.
- `allowed_extensions`: curated catalog accepted by the profile.
- `extension_map`: generic requirement feature to extension identifiers.

Validation:

- Every base and mapped extension appears in `allowed_extensions`.
- Extension identifiers match the contract pattern.
- Every placeholder is allowlisted.

## ScaffoldRequest

Execution input:

- `group_id`
- `artifact_id`
- `package_name`
- `java_version`
- `extensions`
- `workspace_path`

Validation rejects shell metacharacters, path traversal, absolute output paths,
whitespace where forbidden, and uppercase package names.

## ScaffoldResult

Execution evidence:

- `success`
- `tool`
- `tool_version`
- `extensions`
- `manifest`
- `wall_time_seconds`
- `exit_code`
- capped `raw_output`
- `error_code`

`success` is valid only when the process exits zero and the manifest is non-empty.

## ManifestEvidence

- `path`: relative path under the requested workspace.
- `sha256`: digest of the manifest or generated file evidence.
- `size`: byte size.

## Derived extension state

The pure derivation function consumes `(blueprint, profile.scaffold)` and returns a
deterministically ordered list. It does not mutate the blueprint or profile and does
not start a process.

## State transitions

```text
VALIDATED
  -> EXTENSIONS_DERIVED
  -> SCAFFOLDED
  -> OFFLINE_VERIFIED
  -> GENERATED
  -> VERIFIED
  -> REPAIRED (zero or more, max three)
  -> SUCCESS | NO_FIX | ERROR
```
