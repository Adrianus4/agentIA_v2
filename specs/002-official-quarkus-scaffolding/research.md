# Research: Official Quarkus Scaffolding

## Decision: Profile-owned curated catalog

Use a profile-owned `allowed_extensions`, `base_extensions`, and `extension_map`.
Derivation is pure, deterministic, de-duplicated, and sorted.

Rationale: the verifier is offline with a pre-warmed cache. Allowing arbitrary
extensions would make cache availability nondeterministic. A curated catalog makes
unsupported requests fail at the validation boundary.

Alternatives considered:

- Dynamic online dependency resolution: deferred because it adds a second networked
  preparation workflow and cache warm-up complexity.
- Hardcoded framework mapping in Python: rejected by the constitution; framework
  knowledge belongs in profiles.

## Decision: Maven plugin is the first live tool path

Use the Quarkus Maven plugin create goal as the initial adapter because Maven is
already the project build tool and is available in the pinned verifier image.
The exact plugin coordinates and flags must be verified with the installed tool before
enabling live execution; the adapter must fail explicitly if verification is absent.

Alternatives considered:

- Quarkus CLI: requires another installation path and is deferred.
- code.quarkus.io: convenient but introduces a public service dependency.

## Decision: Separate networked scaffolder and offline verifier

The scaffolder gets bounded network access and a disposable workspace role. The
verifier remains `--network none`, uses a read-only cache, and verifies a temporary
copy. No code path may reuse the scaffolder command as a verifier command.

## Decision: Manifest evidence is mandatory

Success requires exit code zero and a non-empty manifest containing path, SHA-256,
and size. This prevents a process that exits successfully without producing a usable
project from entering generation.

## Decision: Backward-compatible opt-in

Profiles without scaffold configuration and requests without a scaffold stage continue
through the current generation path. The new contracts are optional and do not alter
existing graph state serialization.

## Verified current-state findings

- Current contracts use Pydantic models in `contracts/models.py`.
- The existing generation path is coordinated by `GenerationPipeline`.
- `LocalDockerRunner` is the existing verifier boundary.
- The current profile loader resolves framework behavior from profile data.
- The existing repair loop is capped at three attempts.
- No `agents/scaffolder/` package exists yet; it is the implementation gap.
