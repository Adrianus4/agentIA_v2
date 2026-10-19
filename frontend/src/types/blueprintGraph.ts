export type LangGraphNodeId = 'validate' | 'generate' | 'verify' | 'repair' | 'terminal';

export type NodeExecutionStatus =
  | 'IDLE'
  | 'ACTIVE'
  | 'PASSED'
  | 'REPAIRING'
  | 'SUCCESS'
  | 'NO_FIX'
  | 'ERROR'
  | 'SKIPPED';

export interface LangGraphNodeState {
  id: LangGraphNodeId;
  label: string;
  description: string;
  status: NodeExecutionStatus;
  currentIteration?: number;
  maxIterations?: number;
  details?: string | null;
}

export interface BlueprintRunRequest {
  workspace_dir: string;
  blueprint: Record<string, any>;
  trace_id?: string;
}

export interface LlmConfig {
  provider: 'gemini' | 'local' | 'openai';
  model: string;
  endpoint?: string;
  apiKey?: string;
}

export interface LlmSettings {
  provider: LlmConfig['provider'];
  model: string;
  endpoint: string;
  apiKey: string;
}

export interface ValidationDiagnostic {
  error_code: string;
  path: string;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  diagnostics: ValidationDiagnostic[];
}

export interface VerificationResult {
  success: boolean;
  wall_time_seconds?: number;
  exit_code?: number | null;
  timed_out?: boolean;
  issues?: Array<{
    file_path: string;
    line_number?: number | null;
    column_number?: number | null;
    error_type: string;
    message: string;
  }>;
  raw_output?: string;
  raw_output_truncated?: boolean;
  runner_name?: string;
  image?: string;
}

export interface RepairResult {
  outcome: string;
  classification?: string;
  hypothesis?: string;
  patches?: string[];
  files_touched?: string[];
  guard_report?: {
    passed: boolean;
    failed_guards?: string[];
  };
  attempts_used?: number;
  trace_id?: string;
}

export interface GeneratedFile {
  path: string;
  content: string;
  digest?: string | null;
}

export interface OrchestrationStateResponse {
  workspace_dir: string;
  blueprint: Record<string, any>;
  trace_id: string;
  attempts: number;
  validation?: ValidationResult | null;
  verification?: VerificationResult | null;
  repair?: RepairResult | null;
  generated_files?: GeneratedFile[];
  outcome?: string | null;
  state?: {
    generated_files?: GeneratedFile[];
    [key: string]: any;
  };
}

export interface RunStatusResponse {
  trace_id: string;
  blueprint_name: string;
  status: 'RUNNING' | 'SUCCESS' | 'NO_FIX' | 'ERROR' | 'VALID';
  repair_attempts: number;
  outcome?: string;
  stage?: string;
  state?: OrchestrationStateResponse;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'SYSTEM' | 'SUCCESS';
  message: string;
}

export interface KpiMetrics {
  currentPhase: string;
  sandboxStatus: 'PENDING' | 'PASSED' | 'FAILED' | 'SKIPPED_BY_CHOICE' | 'INTERRUPTED' | 'RUNNING';
  repairIteration: number;
  maxRepairs: number;
}

export interface QuarkusConfig {
  framework: 'quarkus' | 'springboot';
  serviceName: string;
  packageName: string;
  basePort: number;
  javaVersion: '21' | '17';
  buildTool: 'maven' | 'gradle';
  database: 'POSTGRESQL' | 'MYSQL' | 'H2';
  architecture: 'layered' | 'hexagonal' | 'hexagonal-ddd';
  executionMode: 'SOURCE_ONLY' | 'HERMETIC_DOCKER';
  maxRepairIterations: number;
  extensions: string[];
  naturalLanguagePrompt: string;
}

export interface PresetTemplate {
  id: string;
  name: string;
  description: string;
  config: QuarkusConfig;
  domainModels?: Array<{
    name: string;
    tableName: string;
    attributes: Array<{ name: string; type: string; primaryKey?: boolean; nullable?: boolean }>;
  }>;
  userStories?: Array<{
    id: string;
    title: string;
    acceptanceCriteria: string[];
  }>;
}