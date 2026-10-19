# Contract: Official Quarkus Scaffolding

## Profile contract

Profiles may include an optional `scaffold` object containing:

```json
{
  "tool": "quarkus-maven-plugin",
  "tool_version": "pinned-version",
  "command_template": ["mvn", "...", "{extensions}"],
  "base_extensions": [],
  "allowed_extensions": [],
  "extension_map": {}
}
```

The command template is an argv list. `{extensions}` expands to a validated
comma-separated value or the tool-specific validated argument representation.

## Python contracts

The implementation adds typed models to `contracts.models`:

- `ScaffoldConfig`
- `ScaffoldRequest`
- `ManifestEvidence`
- `ScaffoldResult`

And a protocol:

```text
Scaffolder.scaffold(request, profile) -> ScaffoldResult
```

## Validation errors

Unsupported extension requests use `UNSUPPORTED_EXTENSION`. Invalid scaffold
configuration, unsafe identifiers, and unsafe paths use existing diagnostic behavior
or a new explicit error code if the existing enum cannot represent the condition.

## Orchestration boundary

The optional scaffold stage executes after blueprint validation and extension
derivation, before LLM generation. If scaffolding or offline scaffold verification
fails, no generated business files are materialized.
