# Data Model: Unified Orchestrator and LLM Configuration

## OrchestrationState

- `workspace_dir`: target workspace path
- `blueprint`: normalized blueprint, including `entities` derived from frontend `domainModels`
- `trace_id`: unique run identifier
- `attempts`: completed repair attempts, bounded to three
- `validation`: typed validation result
- `verification`: latest typed verification result
- `repair`: latest typed repair result
- `generated_files`: materialized `FileContent` values
- `outcome`: terminal run outcome

## LLMConfiguration

- `provider`: supported provider identifier
- `model`: selected model name
- `endpoint`: optional provider endpoint
- `api_key`: transient credential; never serialized into run state or logs

Validation rules: provider and model are required; provider-specific credentials are required before submission when the selected provider needs them.

## GeneratedFile

- `path`: workspace-relative path
- `content`: generated text
- `digest`: optional content digest

Validation rules: path must resolve beneath the requested workspace; content must be present before writing.

## VerificationAttempt

- `success`: whether verification passed
- `timed_out`: whether the runner timed out
- `issues`: structured diagnostics
- `raw_output`: bounded diagnostic output
- `wall_time_seconds`: measured duration

State transitions: `VALIDATING -> LOADING_PROFILE -> GENERATING -> VERIFYING -> REPAIRING -> VERIFYING`, or `ERROR`, `SUCCESS`, or `NO_FIX`.
