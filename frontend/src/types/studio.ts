import type { LogEntry, OrchestrationStateResponse } from './blueprintGraph';


export type SessionStatus =
  | 'CREATED'
  | 'QUEUED'
  | 'RUNNING'
  | 'COMPLETED'
  | 'SUCCESS'
  | 'FAILED'
  | 'BLOCKED'
  | 'NO_FIX';

export type DatabaseEngine = 'POSTGRESQL' | 'MYSQL' | 'H2' | 'NONE';
export type MessagingSystem = 'KAFKA' | 'RABBITMQ' | 'NONE';
export type RequirementsSize = 'LOW' | 'MEDIUM' | 'HIGH' | 'ENTERPRISE';
export type ExpectedQps = '100' | '1000' | '5000+';
export type ConsistencyModel = 'ACID' | 'EVENTUAL';
export type BuildTool = 'MAVEN' | 'GRADLE';
export type ArchitecturePattern = 'hexagonal' | 'layered' | 'hexagonal-ddd' | 'event-driven';

export interface QuarkusParameters {
  database: DatabaseEngine;
  messaging: MessagingSystem;
  requirementsSize: RequirementsSize;
  expectedQps: ExpectedQps;
  dataConsistency: ConsistencyModel;
  buildTool: BuildTool;
  workspaceDir: string;
  architecture?: ArchitecturePattern;
}

export interface BddScenario {
  title: string;
  given: string;
  when: string;
  then: string;
}

export interface BddStory {
  id: string;
  title: string;
  role: string;
  feature: string;
  benefit: string;
  scenarios: BddScenario[];
  detected_entities: string[];
}

export interface EntityField {
  name: string;
  type: string;
  primaryKey?: boolean;
  nullable?: boolean;
  relationship?: string;
  validationRules?: string[];
}

export interface DomainEntity {
  name: string;
  tableName: string;
  description?: string;
  fields: EntityField[];
}

export interface RestContract {
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  description: string;
  requestRecord?: string;
  responseRecord?: string;
  statusCode: number;
}

export interface ArchitectureLayer {
  name: string;
  description: string;
  components: {
    name: string;
    package: string;
    responsibilities: string[];
  }[];
}

export interface SastFinding {
  id: string;
  rule_id: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  category: string;
  file: string;
  line: number;
  message: string;
  remediation?: string;
}

export interface MicroserviceSession {
  id: string;
  sessionId?: string;
  name: string;
  specName?: string;
  description: string;
  status: SessionStatus;
  currentStage: number;
  currentLifecyclePhase?: string;
  completionPercentage?: number;
  parameters: QuarkusParameters;
  traceId: string | null;
  repairAttempts: number;
  repairIterations?: number;
  stories: BddStory[];
  entities: DomainEntity[];
  contracts: RestContract[];
  blueprint: Record<string, any>;
  executionState: OrchestrationStateResponse | null;
  logs: LogEntry[];
  createdAt: string;
  updatedAt: string;
}

export interface TabItem {
  id: number;
  label: string;
  icon: string;
  description: string;
}
