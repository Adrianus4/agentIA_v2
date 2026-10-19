import type {
  BlueprintRunRequest,
  OrchestrationStateResponse,
  RunStatusResponse,
  QuarkusConfig,
  PresetTemplate,
} from '../types/blueprintGraph';
import type {
  DatabaseEngine,
  MessagingSystem,
  RequirementsSize,
  ConsistencyModel,
} from '../types/studio';

// An explicitly empty VITE_API_BASE_URL means "same origin" (the UI is served behind a /v1 proxy)
const ENV_API_BASE_URL =
  typeof import.meta !== 'undefined' ? (import.meta.env?.VITE_API_BASE_URL as string | undefined) : undefined;
export const DEFAULT_API_BASE_URL = ENV_API_BASE_URL !== undefined ? ENV_API_BASE_URL : 'http://localhost:8000';

const RUN_POLL_INTERVAL_MS = 2000;
const RUN_POLL_TIMEOUT_MS = 60 * 60 * 1000;

export const AVAILABLE_QUARKUS_EXTENSIONS = [
  { id: 'quarkus-rest', name: 'RESTEasy Reactive (quarkus-rest)', description: 'Non-blocking REST endpoints' },
  { id: 'quarkus-rest-jackson', name: 'Jackson Serialization', description: 'JSON serializer / deserializer' },
  { id: 'quarkus-hibernate-orm', name: 'Hibernate ORM / Panache', description: 'Jakarta Persistence with Panache' },
  { id: 'quarkus-hibernate-validator', name: 'Hibernate Validator', description: 'Bean Validation constraints (@NotNull, @Positive)' },
  { id: 'quarkus-smallrye-openapi', name: 'SmallRye OpenAPI / Swagger', description: 'OpenAPI 3.1 & Swagger UI' },
  { id: 'quarkus-smallrye-health', name: 'SmallRye Health', description: 'Liveness / readiness probes' },
  { id: 'quarkus-messaging-kafka', name: 'Reactive Messaging Kafka', description: 'Event streaming connector' },
];

export const PRESET_TEMPLATES: PresetTemplate[] = [
  {
    id: 'customer-billing',
    name: 'Customer Billing Service',
    description: 'Enterprise billing microservice with JPA persistence and bounded self-repair verification.',
    config: {
      framework: 'quarkus',
      serviceName: 'customer-billing-service',
      packageName: 'com.tcs.billing',
      basePort: 8080,
      javaVersion: '21',
      buildTool: 'maven',
      database: 'H2',
      architecture: 'layered',
      executionMode: 'HERMETIC_DOCKER',
      maxRepairIterations: 3,
      extensions: [
        'quarkus-rest',
        'quarkus-rest-jackson',
        'quarkus-hibernate-orm',
        'quarkus-hibernate-validator',
        'quarkus-smallrye-openapi',
      ],
      naturalLanguagePrompt:
        'Microservicio para procesar pagos y emitir facturas electrónicas. Debe registrar órdenes con monto strictly positive y estado PENDING, permitiendo confirmación de pago y rollback transaccional ante fallos.',
    },
    domainModels: [
      {
        name: 'Invoice',
        tableName: 'invoices',
        attributes: [
          { name: 'id', type: 'UUID', primaryKey: true },
          { name: 'customerId', type: 'String', nullable: false },
          { name: 'amount', type: 'BigDecimal', nullable: false },
          { name: 'status', type: 'String', nullable: false },
          { name: 'createdAt', type: 'Instant', nullable: false },
        ],
      },
      {
        name: 'PaymentRecord',
        tableName: 'payment_records',
        attributes: [
          { name: 'id', type: 'UUID', primaryKey: true },
          { name: 'invoiceId', type: 'UUID', nullable: false },
          { name: 'paymentMethod', type: 'String', nullable: false },
          { name: 'processedAt', type: 'Instant', nullable: false },
        ],
      },
    ],
    userStories: [
      {
        id: 'US-01',
        title: 'Generate and record invoice',
        acceptanceCriteria: ['Invoice amount is strictly positive', 'Initial status defaults to PENDING'],
      },
      {
        id: 'US-02',
        title: 'Process payment with transaction isolation',
        acceptanceCriteria: ['Associated invoice transitions to PAID', 'Atomic transaction rollback on failure'],
      },
    ],
  },
  {
    id: 'order-management',
    name: 'Order Management Service',
    description: 'Enterprise order fulfillment with reactive REST, audit log and validation rules.',
    config: {
      framework: 'quarkus',
      serviceName: 'order-management-service',
      packageName: 'com.tcs.orders',
      basePort: 8081,
      javaVersion: '21',
      buildTool: 'maven',
      database: 'H2',
      architecture: 'hexagonal',
      executionMode: 'HERMETIC_DOCKER',
      maxRepairIterations: 3,
      extensions: [
        'quarkus-rest',
        'quarkus-rest-jackson',
        'quarkus-hibernate-orm',
        'quarkus-hibernate-validator',
        'quarkus-smallrye-openapi',
        'quarkus-smallrye-health',
      ],
      naturalLanguagePrompt:
        'Gestionar pedidos de clientes corporativos con cálculo dinámico de impuestos, control de stock y trazabilidad de envíos.',
    },
    domainModels: [
      {
        name: 'CustomerOrder',
        tableName: 'customer_orders',
        attributes: [
          { name: 'id', type: 'UUID', primaryKey: true },
          { name: 'orderNumber', type: 'String', nullable: false },
          { name: 'totalAmount', type: 'BigDecimal', nullable: false },
          { name: 'orderStatus', type: 'String', nullable: false },
        ],
      },
    ],
    userStories: [
      {
        id: 'US-01',
        title: 'Create and validate customer order',
        acceptanceCriteria: ['Order number must be unique', 'Total amount must exceed zero'],
      },
    ],
  },
];

export const DEFAULT_BLUEPRINT_TEMPLATE = {
  name: 'CustomerBillingService',
  serviceName: 'customer-billing-service',
  description: 'Enterprise billing microservice with JPA persistence and bounded self-repair verification.',
  framework: 'quarkus',
  databaseEngine: 'POSTGRESQL',
  executionMode: 'HERMETIC_DOCKER',
  domainModels: PRESET_TEMPLATES[0].domainModels,
  userStories: PRESET_TEMPLATES[0].userStories,
};

export function buildBlueprintFromConfig(
  config: QuarkusConfig,
  domainModels?: any[],
  userStories?: any[]
): Record<string, any> {
  const pascalName = config.serviceName
    .split(/[-_]/)
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join('');

  return {
    name: pascalName || config.serviceName,
    serviceName: config.serviceName,
    packageName: config.packageName,
    basePort: config.basePort,
    framework: config.framework,
    version: '3.15.1',
    javaVersion: Number(config.javaVersion) || 21,
    buildTool: config.buildTool,
    databaseEngine: config.database,
    executionMode: config.executionMode,
    maxRepairIterations: config.maxRepairIterations,
    architecture: config.architecture,
    extensions: config.extensions,
    naturalLanguagePrompt: config.naturalLanguagePrompt,
    domainModels: domainModels || [],
    userStories: userStories || [],
  };
}

export function getDefaultBlueprint(): Record<string, any> {
  return buildBlueprintFromConfig(
    PRESET_TEMPLATES[0].config,
    PRESET_TEMPLATES[0].domainModels,
    PRESET_TEMPLATES[0].userStories
  );
}

async function readApiError(response: Response): Promise<string> {
  let errorDetail = response.statusText;
  try {
    const errorJson = await response.json();
    errorDetail = errorJson.detail || errorDetail;
  } catch {
    try {
      const text = await response.text();
      if (text) errorDetail = text;
    } catch {
      // use statusText
    }
  }
  return errorDetail;
}

/**
 * Dispatches a run in async mode (202 + polling) so long Maven/LLM repair loops survive proxy
 * timeouts, then resolves with the final orchestration state. Falls back to the synchronous
 * response when the backend answers 200 directly.
 */
export async function submitBlueprint(
  request: BlueprintRunRequest,
  apiKey: string = '',
  baseUrl: string = DEFAULT_API_BASE_URL,
  llmApiKey: string = '',
  onProgress?: (status: RunStatusResponse) => void
): Promise<OrchestrationStateResponse> {
  const cleanBase = baseUrl.replace(/\/+$/, '');
  const url = `${cleanBase}/v1/blueprint/run?mode=async`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (apiKey) {
    headers['x-api-key'] = apiKey;
  }
  const body = llmApiKey
    ? { ...request, llm_api_key: llmApiKey }
    : request;

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`API Error (${response.status}): ${await readApiError(response)}`);
  }

  const accepted = await response.json();
  if (response.status !== 202) {
    return accepted;
  }

  const traceId: string = accepted.trace_id;
  const deadline = Date.now() + RUN_POLL_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, RUN_POLL_INTERVAL_MS));
    let status: RunStatusResponse;
    try {
      status = await getRunStatus(traceId, apiKey, baseUrl);
    } catch {
      continue; // transient network/proxy glitch: keep polling
    }
    onProgress?.(status);
    if (status.status !== 'RUNNING') {
      const finalState = (status.state || {}) as OrchestrationStateResponse & { error?: string };
      if (status.status === 'ERROR' && finalState.error && !finalState.validation) {
        throw new Error(`Orchestration failed (trace_id=${traceId}): ${finalState.error}`);
      }
      return { ...finalState, trace_id: finalState.trace_id || traceId };
    }
  }
  throw new Error(`Run ${traceId} did not finish within ${RUN_POLL_TIMEOUT_MS / 60000} minutes`);
}

export async function getRunStatus(
  traceId: string,
  apiKey: string = '',
  baseUrl: string = DEFAULT_API_BASE_URL
): Promise<RunStatusResponse> {
  const cleanBase = baseUrl.replace(/\/+$/, '');
  const url = `${cleanBase}/v1/blueprint/status/${encodeURIComponent(traceId)}`;

  const headers: Record<string, string> = {};
  if (apiKey) {
    headers['x-api-key'] = apiKey;
  }

  const response = await fetch(url, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorDetail;
    } catch {
      // fallback
    }
    throw new Error(`Status Query Error (${response.status}): ${errorDetail}`);
  }

  return response.json();
}

export interface SpecDraftRequestPayload {
  directive: string;
  service_name?: string;
  package_name?: string;
  refinement_instructions?: string;
  current_context?: Record<string, any>;
  llm_config?: {
    provider: string;
    model: string;
    api_key?: string;
    endpoint?: string;
  };
}

export interface SpecDraftFieldSpec {
  name: string;
  type: string;
  nullable?: boolean;
  constraints?: string[];
}

export interface SpecDraftDomainModel {
  name: string;
  table_name: string;
  fields: SpecDraftFieldSpec[];
}

export interface SpecDraftUserStory {
  title: string;
  given: string;
  when: string;
  then: string;
  acceptance_criteria?: string[];
}

export interface SpecDraftTechnicalMatrix {
  database: DatabaseEngine;
  messaging: MessagingSystem;
  scope: RequirementsSize;
  qps: number;
  transactional_model: ConsistencyModel;
}

export interface SpecDraftResponsePayload {
  service_name: string;
  package_name: string;
  business_objective: string;
  technical_matrix: SpecDraftTechnicalMatrix;
  user_stories: SpecDraftUserStory[];
  domain_models: SpecDraftDomainModel[];
  _source?: 'backend_llm' | 'heuristic_fallback';
  _error?: string;
}

export function generateHeuristicDraft(
  directive: string,
  serviceName?: string,
  packageName?: string
): SpecDraftResponsePayload {
  const lower = directive.toLowerCase();

  // Pattern 1: Payments / Transfers in Soles
  if (lower.includes('pago') || lower.includes('transfer') || lower.includes('payment') || lower.includes('soles')) {
    const sName = serviceName || 'payment-transfers-service';
    const pName = packageName || 'com.tcs.payments';
    return {
      service_name: sName,
      package_name: pName,
      business_objective: directive.trim(),
      technical_matrix: {
        database: 'POSTGRESQL',
        messaging: lower.includes('kafka') ? 'KAFKA' : 'NONE',
        scope: 'MEDIUM',
        qps: 1000,
        transactional_model: 'ACID',
      },
      user_stories: [
        {
          title: 'Procesar transferencia con validación de límite diario en soles',
          given: 'El cliente posee saldo disponible y no excede el límite operativo diario de PEN 5,000',
          when: 'Se envía solicitud POST a /api/transfers con cuenta origen, destino y monto en PEN',
          then: 'Se debita la cuenta origen, se acredita el destino y se emite evento de confirmación Kafka',
          acceptance_criteria: [
            'Monto de transferencia strictly positive (> 0)',
            'Bloqueo transaccional ACID para evitar doble gasto',
            'Publicación de evento transfer.completed a Kafka',
          ],
        },
        {
          title: 'Rollback atómico ante fondos insuficientes o límite diario superado',
          given: 'El saldo es insuficiente o la transferencia supera el límite diario',
          when: 'Se intenta procesar la transacción en /api/transfers',
          then: 'Se rechaza con HTTP 422 Unprocessable Entity y se ejecuta rollback atómico',
          acceptance_criteria: [
            'Cero mutación de saldo ante error',
            'Registro de auditoría con motivo de rechazo',
          ],
        },
      ],
      domain_models: [
        {
          name: 'PaymentTransfer',
          table_name: 'payment_transfers',
          fields: [
            { name: 'id', type: 'UUID', nullable: false, constraints: ['@NotNull'] },
            { name: 'originAccount', type: 'String', nullable: false, constraints: ['@NotBlank'] },
            { name: 'destinationAccount', type: 'String', nullable: false, constraints: ['@NotBlank'] },
            { name: 'amount', type: 'BigDecimal', nullable: false, constraints: ['@NotNull', '@Positive'] },
            { name: 'currency', type: 'String', nullable: false, constraints: ['@NotBlank'] },
            { name: 'status', type: 'String', nullable: false, constraints: ['@NotBlank'] },
            { name: 'createdAt', type: 'Instant', nullable: false, constraints: ['@NotNull'] },
          ],
        },
        {
          name: 'DailyLimitAccumulator',
          table_name: 'daily_limit_accumulators',
          fields: [
            { name: 'id', type: 'UUID', nullable: false, constraints: ['@NotNull'] },
            { name: 'customerId', type: 'String', nullable: false, constraints: ['@NotBlank'] },
            { name: 'totalAmountPen', type: 'BigDecimal', nullable: false, constraints: ['@NotNull'] },
            { name: 'maxDailyLimit', type: 'BigDecimal', nullable: false, constraints: ['@Positive'] },
            { name: 'lastUpdated', type: 'Instant', nullable: false, constraints: ['@NotNull'] },
          ],
        },
      ],
    };
  }

  // Pattern 2: Customer Wallet
  if (lower.includes('wallet') || lower.includes('billetera')) {
    const sName = serviceName || 'customer-wallet-service';
    const pName = packageName || 'com.tcs.wallet';
    return {
      service_name: sName,
      package_name: pName,
      business_objective: directive.trim(),
      technical_matrix: {
        database: 'POSTGRESQL',
        messaging: 'KAFKA',
        scope: 'MEDIUM',
        qps: 1000,
        transactional_model: 'ACID',
      },
      user_stories: [
        {
          title: 'Recarga y balance de billetera digital',
          given: 'Una billetera activa asociada a un documento de identidad',
          when: 'Se efectúa una recarga en /api/wallets/{id}/topup',
          then: 'Se incrementa el saldo en Panache JPA y se confirma con HTTP 200',
          acceptance_criteria: ['Monto mayor a cero', 'Actualización de timestamp'],
        },
        {
          title: 'Transferencia P2P entre billeteras',
          given: 'Dos billeteras activas con saldo disponible',
          when: 'Se ejecuta una transferencia entre pares',
          then: 'Se actualizan ambos saldos en una transacción atómica ACID',
          acceptance_criteria: ['Transacción atómica', 'Notificación en Kafka topic wallet.p2p'],
        },
      ],
      domain_models: [
        {
          name: 'DigitalWallet',
          table_name: 'digital_wallets',
          fields: [
            { name: 'id', type: 'UUID', nullable: false, constraints: ['@NotNull'] },
            { name: 'ownerDocument', type: 'String', nullable: false, constraints: ['@NotBlank'] },
            { name: 'balance', type: 'BigDecimal', nullable: false, constraints: ['@PositiveOrZero'] },
            { name: 'currency', type: 'String', nullable: false, constraints: ['@NotBlank'] },
            { name: 'status', type: 'String', nullable: false, constraints: ['@NotBlank'] },
          ],
        },
        {
          name: 'WalletLedgerEntry',
          table_name: 'wallet_ledger_entries',
          fields: [
            { name: 'id', type: 'UUID', nullable: false, constraints: ['@NotNull'] },
            { name: 'walletId', type: 'UUID', nullable: false, constraints: ['@NotNull'] },
            { name: 'entryType', type: 'String', nullable: false, constraints: ['@NotBlank'] },
            { name: 'amount', type: 'BigDecimal', nullable: false, constraints: ['@Positive'] },
            { name: 'timestamp', type: 'Instant', nullable: false, constraints: ['@NotNull'] },
          ],
        },
        {
          name: 'DailyLimitAccumulator',
          table_name: 'daily_limit_accumulators',
          fields: [
            { name: 'id', type: 'UUID', nullable: false, constraints: ['@NotNull'] },
            { name: 'walletId', type: 'UUID', nullable: false, constraints: ['@NotNull'] },
            { name: 'totalAmountPen', type: 'BigDecimal', nullable: false, constraints: ['@NotNull'] },
            { name: 'maxDailyLimit', type: 'BigDecimal', nullable: false, constraints: ['@Positive'] },
            { name: 'lastUpdated', type: 'Instant', nullable: false, constraints: ['@NotNull'] },
          ],
        },
      ],
    };
  }

  // Default / Order Service
  const safeName = (serviceName || lower.match(/[a-z0-9]+/g)?.slice(0, 3).join('-') || 'order-service')
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, '-');
  const sName = safeName.endsWith('-service') ? safeName : `${safeName}-service`;
  const pName = packageName || `com.tcs.${safeName.replace(/-service$/, '').replace(/-/g, '')}`;

  return {
    service_name: sName,
    package_name: pName,
    business_objective: directive.trim() || 'Servicio de procesamiento reactivo y persistencia empresarial.',
    technical_matrix: {
      database: 'POSTGRESQL',
      messaging: lower.includes('kafka') ? 'KAFKA' : 'NONE',
      scope: 'MEDIUM',
      qps: 1000,
      transactional_model: 'ACID',
    },
    user_stories: [
      {
        title: `Procesamiento principal de ${sName}`,
        given: 'Entorno Quarkus inicializado con persistencia Panache activa',
        when: 'Se envía una petición válida según las directivas del negocio',
        then: 'Se procesa la regla de negocio y se persiste con código HTTP 201 Created',
        acceptance_criteria: ['Validación estricta de parámetros', 'Registro en log estructurado'],
      },
      {
        title: 'Consulta y trazabilidad por identificador único',
        given: 'El recurso fue persistido previamente en base de datos',
        when: 'Se consulta mediante GET por su identificador único',
        then: 'Se retorna el estado actual con código HTTP 200 OK',
        acceptance_criteria: ['Respuesta JSON serializada con Jackson'],
      },
    ],
    domain_models: [
      {
        name: sName
          .split('-')
          .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
          .join('')
          .replace(/Service$/, '') || 'CustomerOrder',
        table_name: `${sName.replace(/-service$/, '').replace(/-/g, '_')}_records`,
        fields: [
          { name: 'id', type: 'Long', nullable: false, constraints: ['@NotNull'] },
          { name: 'orderNumber', type: 'String', nullable: false, constraints: ['@NotBlank'] },
          { name: 'totalAmount', type: 'BigDecimal', nullable: false, constraints: ['@Positive'] },
          { name: 'status', type: 'String', nullable: false, constraints: ['@NotBlank'] },
          { name: 'createdAt', type: 'Instant', nullable: false, constraints: ['@NotNull'] },
        ],
      },
    ],
  };
}

export async function draftSpec(
  request: SpecDraftRequestPayload,
  apiKey: string = '',
  baseUrl: string = DEFAULT_API_BASE_URL,
  llmApiKey: string = ''
): Promise<SpecDraftResponsePayload> {
  const cleanBase = baseUrl.replace(/\/+$/, '');
  const url = `${cleanBase}/v1/spec/draft`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (apiKey) {
    headers['x-api-key'] = apiKey;
  }
  if (llmApiKey) {
    headers['x-llm-api-key'] = llmApiKey;
  }

  let backendData: SpecDraftResponsePayload | null = null;
  let failureReason: string | null = null;
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(request),
    });

    if (response.ok) {
      const data = await response.json();
      if (data && data.service_name && data.technical_matrix) {
        backendData = data as SpecDraftResponsePayload;
      }
    } else {
      let errDetail = `HTTP ${response.status}`;
      try {
        const errJson = await response.json();
        if (errJson?.detail) errDetail += `: ${errJson.detail}`;
      } catch {}
      failureReason = `El backend en ${cleanBase} respondió con error: ${errDetail}`;
    }
  } catch (err: any) {
    failureReason = `No se pudo conectar al backend en ${cleanBase} (${err.message || 'Error de red'}). ¿Está corriendo ./run_backend.sh?`;
  }

  const heuristic = generateHeuristicDraft(request.directive, request.service_name, request.package_name);

  if (!backendData) {
    return {
      ...heuristic,
      _source: 'heuristic_fallback',
      _error: failureReason || 'Backend no disponible',
    };
  }

  // Augment backend data if it fell back to generic placeholders or empty models
  const isGenericName =
    !backendData.service_name ||
    backendData.service_name === 'generated-service' ||
    backendData.service_name === 'service';
  const hasEmptyModels = !backendData.domain_models || backendData.domain_models.length === 0;
  const isGenericStory =
    !backendData.user_stories ||
    backendData.user_stories.length === 0 ||
    (backendData.user_stories.length === 1 &&
      backendData.user_stories[0].title === 'Capture the requested business outcome');

  const resolvedServiceName = isGenericName ? heuristic.service_name : backendData.service_name;
  const resolvedPackageName =
    !backendData.package_name || backendData.package_name.includes('example.generated')
      ? heuristic.package_name
      : backendData.package_name;
  const resolvedDomainModels = hasEmptyModels ? heuristic.domain_models : backendData.domain_models;
  const resolvedUserStories = isGenericStory ? heuristic.user_stories : backendData.user_stories;

  // Messaging inference: if directive explicitly demands Kafka and backend returned NONE
  let resolvedMatrix = { ...backendData.technical_matrix };
  const lowerDirective = request.directive.toLowerCase();
  if (
    (lowerDirective.includes('kafka') || lowerDirective.includes('topic') || lowerDirective.includes('stream')) &&
    resolvedMatrix.messaging === 'NONE'
  ) {
    resolvedMatrix.messaging = 'KAFKA';
  }

  return {
    service_name: resolvedServiceName,
    package_name: resolvedPackageName,
    business_objective: backendData.business_objective || heuristic.business_objective,
    technical_matrix: resolvedMatrix,
    user_stories: resolvedUserStories,
    domain_models: resolvedDomainModels,
    _source: 'backend_llm',
  };
}

