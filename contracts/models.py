import os
import re
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --- Shared Status Enums ---
RepairOutcome = Literal["PATCHED", "REJECTED_BY_GUARD", "NO_FIX", "ERROR"]
RunOutcome = Literal["SUCCESS", "NO_FIX", "ERROR"]
Outcome = RepairOutcome
FailureClass = Literal["COMPILE_ERROR", "CODE_BUG", "TEST_BUG", "SPEC_AMBIGUITY", "UNKNOWN"]
ErrorCode = Literal[
    "MISSING_FIELD", "INVALID_TYPE", "DUPLICATE_ENTITY_NAME",
    "MISSING_PRIMARY_KEY", "UNMAPPED_FOREIGN_KEY",
    "UNKNOWN_FRAMEWORK", "UNKNOWN_FRAMEWORK_VERSION",
    "UNKNOWN_PROFILE_REVISION", "PROFILE_DISABLED",
    "DUPLICATE_SOURCE_OF_TRUTH", "INVALID_JSON",
    "UNSUPPORTED_EXTENSION", "INVALID_SCAFFOLD_CONFIG",
    "UNSAFE_PATH", "INVALID_IDENTIFIER", "SCAFFOLD_FAILED",
]


def _validate_llm_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > 12000:
        raise ValueError(f"{field_name} exceeds the 12000 character limit")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in normalized):
        raise ValueError(f"{field_name} contains unsupported control characters")
    secret_patterns = (
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*\S+",
    )
    if any(re.search(pattern, normalized) for pattern in secret_patterns):
        raise ValueError(f"{field_name} appears to contain a secret")
    return normalized

# --- PF-1: Framework Profiles ---
class FrameworkProfileErrors(Exception): pass
class UnknownFramework(FrameworkProfileErrors): pass
class UnknownFrameworkVersion(FrameworkProfileErrors): pass
class UnknownProfileRevision(FrameworkProfileErrors): pass
class ProfileDisabled(FrameworkProfileErrors): pass

class FrameworkProfile(BaseModel):
    id: str
    framework: str
    framework_version: str
    profile_revision: int
    java_version: str
    build_tool: str
    enabled: bool
    baseline_evidence: str | None = None
    instruction_set_revision: str
    concepts: dict[str, dict]
    config: dict
    test_style: dict
    verify_commands: dict
    forbidden_imports: list[str]
    allowed_exceptions: list[str]
    pitfalls: list[str]
    templates: dict[str, str]
    canonical_examples: dict[str, str] = {}
    type_imports: dict[str, str] = {}
    scaffold: "ScaffoldConfig | None" = None


class ScaffoldConfig(BaseModel):
    tool: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    command_template: list[str] = Field(min_length=1)
    base_extensions: list[str] = []
    allowed_extensions: list[str] = []
    extension_map: dict[str, list[str]] = {}

    @model_validator(mode="after")
    def validate_configuration(self) -> "ScaffoldConfig":
        allowed = set(self.allowed_extensions)
        extensions = list(self.base_extensions)
        for mapped in self.extension_map.values():
            extensions.extend(mapped)
        if any(extension not in allowed for extension in extensions):
            raise ValueError("base and mapped extensions must be in allowed_extensions")
        placeholders = {
            placeholder
            for token in self.command_template
            for placeholder in _PLACEHOLDER_RE.findall(token)
        }
        if not placeholders.issubset(_ALLOWED_SCAFFOLD_PLACEHOLDERS):
            raise ValueError("command_template contains an unsupported placeholder")
        return self


_PLACEHOLDER_RE = __import__("re").compile(r"\{([a-z_]+)\}")
_ALLOWED_SCAFFOLD_PLACEHOLDERS = {
    "group_id", "artifact_id", "package_name", "java_version", "extensions",
    "tool_version",
}


class ScaffoldRequest(BaseModel):
    group_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    package_name: str = Field(min_length=1)
    java_version: str = Field(min_length=1)
    extensions: list[str] = []
    workspace_path: str = Field(min_length=1)
    timeout_seconds: int = Field(default=300, ge=1, le=1800)

    @field_validator("group_id", "artifact_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9._-]*", value):
            raise ValueError("identifier must start lowercase and contain only safe characters")
        return value

    @field_validator("package_name")
    @classmethod
    def validate_package(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)*", value):
            raise ValueError("package_name must be a lowercase dotted Java package")
        return value


class ManifestEvidence(BaseModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)


class ScaffoldResult(BaseModel):
    success: bool
    tool: str
    tool_version: str
    extensions: list[str] = []
    manifest: list[ManifestEvidence] = []
    wall_time_seconds: float = Field(ge=0)
    exit_code: int | None = None
    raw_output: str = ""
    raw_output_truncated: bool = False
    error_code: str | None = None

# --- DM-1: Blueprint Validation Contract ---
class Diagnostic(BaseModel):
    error_code: ErrorCode
    path: str
    message: str

class UniformErrorBody(BaseModel):
    valid: bool = False
    diagnostics: list[Diagnostic]

# --- DM-2: Sandbox Verifier Contract ---
class RunnerRequest(BaseModel):
    workspace_path: str
    command: list[str]
    timeout_seconds: int = 30
    network_policy: Literal["none"] = "none"

class DiagnosticIssue(BaseModel):
    file_path: str
    line_number: int | None = None
    column_number: int | None = None
    error_type: str
    message: str

class VerificationResult(BaseModel):
    success: bool
    exit_code: int | None = None
    timed_out: bool = False
    wall_time_seconds: float
    issues: list[DiagnosticIssue] = []
    raw_output: str
    raw_output_truncated: bool = False
    runner_name: str
    image: str

# --- DM-3: Scoped Repair Contract ---
class FileContent(BaseModel):
    path: str
    content: str | None = None
    digest: str | None = None

class TestBaseline(BaseModel):
    __test__ = False
    test_count: int
    assertion_count: int
    disabled_count: int

class RepairRequest(BaseModel):
    framework: str
    framework_version: str
    profile_revision: int | None = None
    failing_file: FileContent
    issues: list[DiagnosticIssue]
    dependencies: list[FileContent] = []
    allowed_paths: list[str]
    attempt_budget: int = Field(default=3, le=3)
    test_baseline: TestBaseline
    blueprint_entities: list[dict[str, Any]] = []

class GuardReport(BaseModel):
    passed: bool
    failed_guards: list[str] = []

class RepairResult(BaseModel):
    outcome: RepairOutcome
    classification: FailureClass
    hypothesis: str
    patches: list[str]
    files_touched: list[str]
    guard_report: GuardReport
    attempts_used: int
    tokens: int | None = None
    trace_id: str

# --- DM-5: Run Log Record ---
class RunLogRecord(BaseModel):
    timestamp: str
    trace_id: str
    run_id: str
    service: str
    endpoint: str
    framework: str | None = None
    framework_version: str | None = None
    profile_revision: int | None = None
    http_status: int
    duration_ms: float
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    outcome: str
    error_code: str | None = None
    guard_report: GuardReport | None = None

# --- DM-4 / GEN-1: Generation Graph Contract ---
class LLMConfiguration(BaseModel):
    provider: Literal["gemini", "local", "openai", "deepseek"] = "gemini"
    model: str = Field(min_length=1, max_length=200)
    endpoint: str | None = None
    api_key: str | None = Field(default=None, repr=False, max_length=500)

    @model_validator(mode="after")
    def validate_provider_settings(self) -> "LLMConfiguration":
        if self.provider == "local":
            if not self.endpoint:
                raise ValueError("local LLM requires an endpoint")
            parsed = urlparse(self.endpoint)
            allowed_hosts = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"} | {
                h.strip() for h in os.getenv("LOCAL_LLM_ALLOWED_HOSTS", "").split(",") if h.strip()
            }
            if parsed.scheme not in {"http", "https"} or parsed.hostname not in allowed_hosts:
                raise ValueError("local LLM endpoint must target localhost")

        if self.provider in ("openai", "deepseek") and self.endpoint:
            parsed = urlparse(self.endpoint)
            if parsed.scheme not in {"http", "https"}:
                raise ValueError(f"{self.provider} endpoint must use http or https")

        return self


class LLMVerifyRequest(BaseModel):
    provider: Literal["gemini", "local", "mock", "groq", "openai", "deepseek"] = "local"
    model: str = Field(default="qwen2.5-coder:3b", min_length=1, max_length=200)
    endpoint: str | None = None
    api_key: str | None = Field(default=None, repr=False, max_length=500)


class GenerationRequest(BaseModel):
    blueprint: dict[str, Any]
    trace_id: str | None = None
    llm: LLMConfiguration | None = None


class SpecDraftRequest(BaseModel):
    directive: str = Field(min_length=1, max_length=12000)
    service_name: str | None = Field(default=None, min_length=1)
    package_name: str | None = Field(default=None, min_length=1)
    refinement_instructions: str | None = Field(default=None, max_length=5000)
    current_context: dict[str, Any] | None = None
    llm_config: LLMConfiguration | None = None

    @field_validator("directive")
    @classmethod
    def validate_directive(cls, value: str) -> str:
        return _validate_llm_text(value, "directive")


class FieldSpec(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    nullable: bool = True
    constraints: list[str] = []


class DomainModel(BaseModel):
    name: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    fields: list[FieldSpec] = []


class UserStory(BaseModel):
    title: str = Field(min_length=1)
    given: str = Field(min_length=1)
    when: str = Field(min_length=1)
    then: str = Field(min_length=1)
    acceptance_criteria: list[str] = []


class TechnicalMatrix(BaseModel):
    database: Literal["POSTGRESQL", "MYSQL", "H2", "NONE"] = "NONE"
    messaging: Literal["KAFKA", "RABBITMQ", "NONE"] = "NONE"
    scope: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    qps: int = Field(default=0, ge=0)
    transactional_model: Literal["ACID", "EVENTUAL"] = "ACID"


class SpecDraftResponse(BaseModel):
    service_name: str = Field(min_length=1)
    package_name: str = Field(min_length=1)
    business_objective: str = Field(min_length=1)
    technical_matrix: TechnicalMatrix
    user_stories: list[UserStory] = []
    domain_models: list[DomainModel] = []

    def to_blueprint(self) -> dict[str, Any]:
        """Convert specification response to generation blueprint dictionary."""
        from app.orchestrator.graph import normalize_blueprint

        return normalize_blueprint(self)


# --- QA-1: Local QA Runner Contracts (Increment 003) ---
QASchemaVersion = Literal["1.0"]
QAExitCode = Literal[0, 1, 2, 3, 4, 130]
QAOverallStatus = Literal["PASSED", "FAILED", "ERROR", "INCOMPLETE", "INTERRUPTED"]
QACaseStatus = Literal["PASSED", "FAILED", "ERROR", "SKIPPED", "XFAIL"]
QASuiteCatalogStatus = Literal["EXECUTABLE", "BLOCKED", "NOT_IMPLEMENTED"]


def _validate_safe_path_str(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized or "\x00" in normalized:
        raise ValueError(f"{field_name} must be a valid non-empty path")
    if any(tok in normalized for tok in (";", "&&", "||", "|", "`", "$(")):
        raise ValueError(f"{field_name} must not contain shell command fragments")
    parts = re.split(r"[\\/]+", normalized)
    if ".." in parts:
        raise ValueError(f"{field_name} must not contain parent path traversal ('..')")
    return normalized


_SECRET_PATTERNS = (
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----",
    r"\bsk-[A-Za-z0-9\-_]{10,}\b",
    r"\bAIza[0-9A-Za-z\-_]{12,}\b",
    r"(?i)\bBearer\s+[^\s\"',;)]+",
    r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|credential)\s*[:=]\s*\S+",
)


def _assert_no_secrets(value: str, field_name: str) -> str:
    if not value:
        return value
    for pattern in _SECRET_PATTERNS:
        if re.search(pattern, value):
            raise ValueError(f"{field_name} appears to contain a secret, token, or private key")
    return value


def _validate_safe_relative_path_str(value: str, field_name: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized or "\x00" in normalized:
        raise ValueError(f"{field_name} must be a valid non-empty path")
    if normalized.startswith("/") or ":" in normalized:
        raise ValueError(f"{field_name} must be a relative path, not an absolute path")
    if any(tok in normalized for tok in (";", "&&", "||", "|", "`", "$(")):
        raise ValueError(f"{field_name} must not contain shell command fragments")
    parts = normalized.split("/")
    if ".." in parts:
        raise ValueError(f"{field_name} must not contain parent path traversal ('..')")
    return normalized


# --- QA Delivery, Manifest and AI Contracts (Trabajos 5-9) ---

class QAArtifact(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    type: str = Field(default="other", min_length=1)
    size_bytes: int = Field(default=0, ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: str | dict[str, Any] | None = None

    @field_validator("path")
    @classmethod
    def validate_artifact_path(cls, value: str) -> str:
        return _validate_safe_relative_path_str(value, "path")


class QAReportManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "1.0"
    generated_utc: str = Field(min_length=1)
    test_run_trace: str = Field(min_length=1)
    test_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["SUCCESS", "PARTIAL", "FAILED", "ERROR"] = "SUCCESS"
    artifacts: list[QAArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class QAHypothesis(BaseModel):
    model_config = ConfigDict(extra="allow")

    cause: str = Field(min_length=1)
    likelihood: Literal["likely", "possible", "unlikely"] = "possible"
    referenced_evidence: list[str] = Field(default_factory=list)
    suggested_action: str = ""


class QAAnalysisConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["gemini", "openai", "deepseek"] = "gemini"
    model: str = "gemini-2.5-flash"
    mode: Literal["disabled", "offline", "live"] = "disabled"
    max_evidence_chars: int = Field(default=32000, ge=1000, le=128000)
    max_tokens: int = Field(default=1500, ge=100, le=8000)
    timeout_seconds: float = Field(default=60.0, ge=1.0, le=300.0)
    deadline_seconds: float = Field(default=120.0, ge=1.0, le=600.0)
    max_requests: int = Field(default=3, ge=1, le=10)

    @field_validator("model")
    @classmethod
    def validate_model_no_secret(cls, value: str) -> str:
        return _assert_no_secrets(value, "model")


class QAAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "1.0"
    trace_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    status: Literal["SUCCESS", "BLOCKED", "ERROR", "DISABLED"]
    error_reason: str | None = None
    hypotheses: list[QAHypothesis] = Field(default_factory=list)
    referenced_items: list[str] = Field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_estimate_usd: float | None = None
    duration_seconds: float = Field(default=0.0, ge=0.0)
    warnings: list[str] = Field(default_factory=list)


class QALLMTestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["simulated", "real"] = "simulated"
    provider: Literal["gemini", "openai", "deepseek"] = "gemini"
    model: str = "gemini-2.5-flash"
    verify_generated_java: bool = False
    max_requests: int = Field(default=6, ge=1, le=20)
    timeout_seconds: float = Field(default=60.0, ge=1.0, le=300.0)

    @field_validator("model")
    @classmethod
    def validate_model_no_secret(cls, value: str) -> str:
        return _assert_no_secrets(value, "model")


class QAProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["gemini", "openai", "deepseek"]
    model: str = Field(min_length=1)
    messages: list[dict[str, str]] = Field(default_factory=list)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1500, ge=1, le=8000)
    system_instruction: str | None = None

    @field_validator("model")
    @classmethod
    def validate_model_no_secret(cls, value: str) -> str:
        return _assert_no_secrets(value, "model")

    @field_validator("messages")
    @classmethod
    def validate_messages_no_secrets(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        for msg in value:
            content = msg.get("content", "")
            _assert_no_secrets(content, "message.content")
        return value


class QAProviderResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: Literal["gemini", "openai", "deepseek"]
    model: str = Field(min_length=1)
    content: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    duration_seconds: float = Field(default=0.0, ge=0.0)
    raw_finish_reason: str | None = None
    error_type: str | None = None
    error_message: str | None = None


class QADeliveryResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "1.0"
    trace_id: str = Field(min_length=1)
    test_status: QAOverallStatus
    test_exit_code: int
    analysis_status: Literal["SUCCESS", "BLOCKED", "ERROR", "DISABLED", "NOT_REQUESTED"] = "NOT_REQUESTED"
    report_status: Literal["SUCCESS", "FAILED", "ERROR", "SKIPPED"] = "SUCCESS"
    delivery_status: Literal["SUCCESS", "FAILED", "ERROR", "INCOMPLETE", "INTERRUPTED"]
    delivery_exit_code: int
    test_result_path: str | None = None
    report_html_path: str | None = None
    report_manifest_path: str | None = None
    analysis_path: str | None = None
    warnings: list[str] = Field(default_factory=list)


def compute_delivery_exit_code(
    test_exit_code: int,
    report_status: str,
    analysis_status: str,
    *,
    config_valid: bool = True,
    interrupted: bool = False,
) -> int:
    """Calcula el código de salida operacional según la política oficial de entrega (plan.md).

    | Situación | Salida de la CLI |
    | Tests aprobados; HTML entregado; IA desactivada o completada | 0. |
    | Tests fallidos; informe generado, con o sin análisis | 1; fallo de tests visible. |
    | Configuración inválida | 2, sin ejecutar la capacidad inválida. |
    | Error de ejecución/evidencia/HTML | 3; conservar por separado la salida de tests. |
    | Tests incompletos o análisis solicitado que queda bloqueado/fallido con base aprobada | 4; base conservada, entrega parcial declarada. |
    | Interrupción del usuario | 130. |
    """
    if interrupted or test_exit_code == 130:
        return 130
    if not config_valid:
        return 2
    if report_status in ("ERROR", "FAILED"):
        return 3
    if test_exit_code == 1:
        return 1
    if test_exit_code == 3:
        return 3
    if test_exit_code == 4:
        return 4
    if test_exit_code == 0:
        if analysis_status in ("BLOCKED", "ERROR"):
            return 4
        return 0
    return test_exit_code


class QAConfigModel(BaseModel):
    model_config = {"extra": "forbid"}

    schema_version: QASchemaVersion = "1.0"
    suites: list[str] = Field(default_factory=lambda: ["python"])
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    output_dir: str = Field(default=".agentia-runtime/qa", min_length=1)
    suite_timeouts: dict[str, int] = Field(default_factory=dict)
    java_cache_dir: str | None = None
    browser_cache_dir: str | None = None
    analysis: QAAnalysisConfig | None = None
    llm_test: QALLMTestConfig | None = None
    report_enabled: bool = True

    @field_validator("suites")
    @classmethod
    def validate_suites(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list) or not value:
            raise ValueError("suites must be a non-empty list of suite identifiers")
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("suite identifier must be a non-empty string")
            cleaned.append(item.strip())
        return cleaned

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, value: str) -> str:
        return _validate_safe_path_str(value, "output_dir")

    @field_validator("suite_timeouts", mode="before")
    @classmethod
    def validate_suite_timeouts(cls, value: Any) -> dict[str, int]:
        if not isinstance(value, dict):
            raise ValueError("suite_timeouts must be a mapping of suite_id to timeout seconds")
        cleaned: dict[str, int] = {}
        for k, v in value.items():
            if not isinstance(k, str) or not k.strip():
                raise ValueError("suite_timeouts keys must be non-empty strings")
            if isinstance(v, bool) or not isinstance(v, int) or v < 1 or v > 7200:
                raise ValueError("suite_timeouts values must be integers between 1 and 7200")
            cleaned[k.strip().lower()] = v
        return cleaned

    @field_validator("java_cache_dir", "browser_cache_dir")
    @classmethod
    def validate_optional_cache_dirs(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("cache_dir must be a string path")
        return _validate_safe_path_str(value, "cache_dir")


class QACapabilityStatus(BaseModel):
    name: str = Field(min_length=1)
    category: Literal["python_runtime", "python_package", "optional_tool", "suite_requirement", "cache"]
    required: bool
    available: bool
    version: str | None = None
    path: str | None = None
    reason: str | None = None


class QASuiteCatalogEntry(BaseModel):
    suite_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    implemented: bool
    status: QASuiteCatalogStatus
    engine: str | None = None
    aliases: list[str] = Field(default_factory=list)
    target_paths: list[str] = []
    required_capabilities: list[str] = []
    optional_capabilities: list[str] = []
    reason: str | None = None


class QACaseResult(BaseModel):
    classname: str = ""
    name: str = Field(min_length=1)
    status: QACaseStatus
    duration_seconds: float = Field(default=0.0, ge=0.0)
    message: str | None = None
    suite_id: str | None = None
    fixture_id: str | None = None
    app_trace_id: str | None = None
    engine: str | None = None


class QACounts(BaseModel):
    collected: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    xfail: int = Field(default=0, ge=0)


class QASuiteStepResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    step_id: str = Field(min_length=1)
    description: str = ""
    kind: str = "test"
    command: list[str] | str | None = None
    diagnostic: str | None = None
    status: Literal["PASSED", "FAILED", "ERROR", "INCOMPLETE", "SKIPPED"]
    exit_code: int | None = None
    duration_seconds: float = Field(default=0.0, ge=0.0)
    message: str | None = None
    evidence_files: dict[str, str] = Field(default_factory=dict)


class QASourceProvenance(BaseModel):
    git_revision: str | None = None
    source_hashes: dict[str, str] = Field(default_factory=dict)
    fidelity: dict[str, str] = Field(default_factory=dict)
    tool_versions: dict[str, str] = Field(default_factory=dict)


class QASuiteExecutionResult(BaseModel):
    suite_id: str = Field(min_length=1)
    implemented: bool
    status: Literal["PASSED", "FAILED", "ERROR", "INCOMPLETE", "INTERRUPTED", "NOT_IMPLEMENTED"]
    exit_code: int
    engine: str = "pytest"
    process_exit_code: int | None = None
    pytest_exit_code: int | None = None
    timed_out: bool = False
    interrupted: bool = False
    output_truncated: bool = False
    duration_seconds: float = Field(default=0.0, ge=0.0)
    counts: QACounts = Field(default_factory=QACounts)
    cases: list[QACaseResult] = []
    steps: list[QASuiteStepResult] = []
    provenance: QASourceProvenance | None = None
    reasons: list[str] = []
    evidence_dir: str | None = None
    evidence_files: dict[str, str] = {}


class QADoctorReport(BaseModel):
    schema_version: QASchemaVersion = "1.0"
    trace_id: str = Field(min_length=1)
    repo_root: str = Field(min_length=1)
    status: Literal["PASSED", "INCOMPLETE", "ERROR"]
    exit_code: int
    python_suite_eligible: bool
    suite_eligibility: dict[str, bool] = Field(default_factory=dict)
    capabilities: list[QACapabilityStatus] = []
    selected_suites: list[str] = Field(default_factory=lambda: ["python"])
    cases: list[QACaseResult] = []
    counts: QACounts = Field(default_factory=QACounts)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    reasons: list[str] = []
    evidence_files: dict[str, str] = {}


class QAListReport(BaseModel):
    schema_version: QASchemaVersion = "1.0"
    trace_id: str = Field(min_length=1)
    repo_root: str = Field(min_length=1)
    status: Literal["PASSED", "INCOMPLETE", "ERROR"] = "PASSED"
    exit_code: int = 0
    capabilities: list[QACapabilityStatus] = []
    selected_suites: list[str] = []
    suites: list[QASuiteCatalogEntry] = []
    cases: list[QACaseResult] = []
    counts: QACounts = Field(default_factory=QACounts)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    reasons: list[str] = []
    evidence_files: dict[str, str] = {}


class QARunResult(BaseModel):
    schema_version: QASchemaVersion = "1.0"
    trace_id: str = Field(min_length=1)
    repo_root: str = Field(min_length=1)
    status: QAOverallStatus
    exit_code: int
    selected_suites: list[str] = []
    scope_note: str = Field(min_length=1)
    start_utc: str = Field(min_length=1)
    end_utc: str = Field(min_length=1)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    capabilities: list[QACapabilityStatus] = []
    suites: list[QASuiteExecutionResult] = []
    cases: list[QACaseResult] = []
    counts: QACounts = Field(default_factory=QACounts)
    provenance: QASourceProvenance | None = None
    reasons: list[str] = []
    evidence_dir: str = Field(min_length=1)
    evidence_files: dict[str, str] = {}


def validate_run_result_consistency(res: QARunResult) -> list[str]:
    """Valida invariantes deterministas de identidad, conteos, veredictos y códigos entre run y suites (AC-03, AC-06, S06)."""
    errors: list[str] = []

    # 1. Invariantes de veredicto PASSED
    if res.status == "PASSED":
        if res.exit_code != 0:
            errors.append(f"Inconsistencia: estado global PASSED pero exit_code={res.exit_code} (se exige 0).")
        if res.counts.failed > 0:
            errors.append(f"Inconsistencia: estado global PASSED pero counts.failed={res.counts.failed}.")
        if res.counts.errors > 0:
            errors.append(f"Inconsistencia: estado global PASSED pero counts.errors={res.counts.errors}.")
        for c in res.cases:
            if c.status in ("FAILED", "ERROR"):
                errors.append(f"Inconsistencia: estado global PASSED pero caso '{c.name}' tiene status={c.status}.")
        for s in res.suites:
            if s.status in ("FAILED", "ERROR"):
                errors.append(f"Inconsistencia: estado global PASSED pero suite '{s.suite_id}' tiene status={s.status}.")
            if s.exit_code != 0:
                errors.append(f"Inconsistencia: estado global PASSED pero suite '{s.suite_id}' tiene exit_code={s.exit_code}.")
            if s.counts.failed > 0 or s.counts.errors > 0:
                errors.append(f"Inconsistencia: estado global PASSED pero suite '{s.suite_id}' tiene fallos/errores registrados.")
            for sc in s.cases:
                if sc.status in ("FAILED", "ERROR"):
                    errors.append(f"Inconsistencia: estado global PASSED pero caso '{sc.name}' en suite '{s.suite_id}' tiene status={sc.status}.")

    # 2. Invariantes de veredicto FAILED / ERROR
    elif res.status in ("FAILED", "ERROR"):
        has_failure_evidence = (
            res.exit_code != 0
            or res.counts.failed > 0
            or res.counts.errors > 0
            or any(c.status in ("FAILED", "ERROR") for c in res.cases)
            or any(s.status in ("FAILED", "ERROR") or s.exit_code != 0 or s.counts.failed > 0 for s in res.suites)
        )
        if not has_failure_evidence:
            errors.append(f"Inconsistencia: estado global {res.status} pero no existe ningún caso fallido, suite fallida ni exit_code distinto de 0.")

    # 3. Correspondencia de conteos
    if res.counts.collected > 0 and len(res.cases) > res.counts.collected:
        errors.append(f"Inconsistencia de conteo: len(cases)={len(res.cases)} supera counts.collected={res.counts.collected}.")

    failed_cases_count = sum(1 for c in res.cases if c.status in ("FAILED", "ERROR"))
    if failed_cases_count > 0 and (res.counts.failed == 0 and res.counts.errors == 0):
        errors.append(
            f"Inconsistencia de conteo: se registran {failed_cases_count} casos fallidos/error pero counts.failed={res.counts.failed} y counts.errors={res.counts.errors}."
        )

    for s in res.suites:
        if s.counts.collected > 0 and len(s.cases) > s.counts.collected:
            errors.append(f"Inconsistencia de conteo en suite '{s.suite_id}': len(cases)={len(s.cases)} supera counts.collected={s.counts.collected}.")
        s_failed = sum(1 for c in s.cases if c.status in ("FAILED", "ERROR"))
        if s_failed > 0 and (s.counts.failed == 0 and s.counts.errors == 0):
            errors.append(
                f"Inconsistencia de conteo en suite '{s.suite_id}': se registran {s_failed} casos fallidos pero s.counts.failed={s.counts.failed}."
            )

    return errors