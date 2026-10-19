import React, { useState, useEffect } from 'react';
import {
  FileText,
  Save,
  Plus,
  Trash2,
  Sparkles,
  Loader2,
  BrainCircuit,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Table,
  X,
  Bot,
  BotMessageSquare,
} from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { useLlm } from '../context/LlmContext';
import { Card } from '../components/common/Card';
import { RequirementsGraphTracker } from '../components/orchestration/RequirementsGraphTracker';
import {
  PRESET_TEMPLATES,
  AVAILABLE_QUARKUS_EXTENSIONS,
  draftSpec,
} from '../services/blueprintService';
import type {
  DatabaseEngine,
  MessagingSystem,
  RequirementsSize,
  ExpectedQps,
  ConsistencyModel,
  BddStory,
  DomainEntity,
  EntityField,
} from '../types/studio';

const COPILOT_PRESET_CHIPS = [
  {
    id: 'payment',
    label: 'Payment Service',
    description: 'Transferencias CCE / Soles PEN & Kafka',
    directive:
      'Crear un servicio de procesamiento de pagos y transferencias en soles peruanos con límites diarios, validación de saldo y notificación Kafka...',
    serviceName: 'payment-transfers-service',
    packageName: 'com.tcs.payments',
  },
  {
    id: 'order',
    label: 'Order Service',
    description: 'Facturación SUNAT, IGV 18% & PostgreSQL',
    directive:
      'Gestionar órdenes de cobro corporativo y facturación electrónica SUNAT en soles peruanos, retenciones de IGV (18%), validación de RUC en línea y persistencia transaccional ACID en PostgreSQL.',
    serviceName: 'order-fulfillment-service',
    packageName: 'com.tcs.orders',
  },
  {
    id: 'wallet',
    label: 'Customer Wallet',
    description: 'Billetera Móvil P2P (Yape/Plin) & Saldo Móvil',
    directive:
      'Billetera digital móvil para transferencias P2P inmediatas en soles peruanos por número de celular, recargas con tarjeta, verificación de saldo en tiempo real y registro contable ACID.',
    serviceName: 'customer-wallet-service',
    packageName: 'com.tcs.wallet',
  },
];

export const DefinitionConfigView: React.FC = () => {
  const {
    activeSessionId,
    activeSession,
    createSession,
    updateActiveSession,
    setActiveTab,
    apiKey,
    baseUrl,
  } = useStudio();

  const { provider, apiKey: llmApiKey, model, endpoint } = useLlm();

  // Business Directive State
  const [directiveText, setDirectiveText] = useState<string>(
    'Crear un servicio de procesamiento de pagos y transferencias en soles peruanos con límites diarios y notificación Kafka...'
  );
  const [isDrafting, setIsDrafting] = useState<boolean>(false);
  const [specSuccessMsg, setSpecSuccessMsg] = useState<string | null>(null);

  // Unified Form States
  const [selectedPresetId, setSelectedPresetId] = useState<string>('custom');
  const [serviceName, setServiceName] = useState<string>(
    activeSession ? activeSession.name : 'order-fulfillment-service'
  );
  const [packageName, setPackageName] = useState<string>('com.tcs.orders');
  const [description, setDescription] = useState<string>(
    activeSession
      ? activeSession.description
      : 'Microservicio para orquestación de órdenes con persistencia reactiva y validación de reglas de negocio.'
  );
  const [database, setDatabase] = useState<DatabaseEngine>(
    activeSession ? activeSession.parameters.database : 'H2'
  );
  const [messaging, setMessaging] = useState<MessagingSystem>(
    activeSession ? activeSession.parameters.messaging : 'KAFKA'
  );
  const [requirementsSize, setRequirementsSize] = useState<RequirementsSize>(
    activeSession ? activeSession.parameters.requirementsSize : 'MEDIUM'
  );
  const [expectedQps, setExpectedQps] = useState<ExpectedQps>(
    activeSession ? activeSession.parameters.expectedQps : '1000'
  );
  const [dataConsistency, setDataConsistency] = useState<ConsistencyModel>(
    activeSession ? activeSession.parameters.dataConsistency : 'ACID'
  );
  const [selectedExtensions, setSelectedExtensions] = useState<string[]>([
    'quarkus-rest',
    'quarkus-rest-jackson',
    'quarkus-hibernate-orm',
    'quarkus-hibernate-validator',
  ]);

  const [stories, setStories] = useState<BddStory[]>(
    activeSession && activeSession.stories.length > 0
      ? activeSession.stories
      : [
          {
            id: 'US-001',
            title: 'Creación de Órdenes',
            role: 'Cliente del Sistema',
            feature: 'Crear nueva orden con validaciones estrictas',
            benefit: 'Garantizar consistencia de precios y stock',
            scenarios: [
              {
                title: 'Creación exitosa con payload válido',
                given: 'El servicio está desplegado con conexión a base de datos',
                when: 'Se envía un POST a /api/orders con items y email válido',
                then: 'Se persiste la orden y se retorna HTTP 201 Created',
              },
            ],
            detected_entities: ['Order', 'OrderItem'],
          },
        ]
  );

  // Panache Entity Modeler State
  const [entities, setEntities] = useState<DomainEntity[]>(
    activeSession && activeSession.entities.length > 0
      ? activeSession.entities
      : [
          {
            name: 'Order',
            tableName: 'orders',
            description: 'Entidad raíz de orden de compra agregada',
            fields: [
              { name: 'id', type: 'Long', primaryKey: true, nullable: false, validationRules: ['@NotNull'] },
              { name: 'customerEmail', type: 'String', nullable: false, validationRules: ['@Email', '@NotNull'] },
              { name: 'totalAmount', type: 'BigDecimal', nullable: false, validationRules: ['@Positive', '@NotNull'] },
              { name: 'status', type: 'String', nullable: false, validationRules: ['@NotBlank'] },
              { name: 'createdAt', type: 'Instant', nullable: false, validationRules: ['@NotNull'] },
            ],
          },
        ]
  );
  const [selectedEntityIdx, setSelectedEntityIdx] = useState<number>(0);

  const [saveSuccess, setSaveSuccess] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [draftElapsedTime, setDraftElapsedTime] = useState<number>(0);
  const [isSpecCompleted, setIsSpecCompleted] = useState<boolean>(() =>
    Boolean(activeSession?.stories?.length || activeSession?.entities?.length)
  );
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [completedSteps, setCompletedSteps] = useState<number[]>(() =>
    activeSession?.stories?.length || activeSession?.entities?.length ? [1, 2, 3, 4, 5] : []
  );
  const [activeAgentLog, setActiveAgentLog] = useState<string | null>(null);

  // Track which steps have an active AI recommendation
  const [aiRecommendations, setAiRecommendations] = useState<Record<number, { agent: string; summary: string }>>({});

  // HITL Refinement Modal State
  const [refineModalStep, setRefineModalStep] = useState<number | null>(null);
  const [refineInstructions, setRefineInstructions] = useState<string>('');
  const [isRefiningWithLlm, setIsRefiningWithLlm] = useState<boolean>(false);

  // Scroll to and activate step
  const goToStep = (stepNum: number) => {
    setCurrentStepIndex(stepNum - 1);
    const element = document.getElementById(`step-card-${stepNum}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  // Sync when activeSession changes
  useEffect(() => {
    if (activeSession) {
      setServiceName(activeSession.name);
      setDescription(activeSession.description);
      setDatabase(activeSession.parameters.database);
      setMessaging(activeSession.parameters.messaging);
      setRequirementsSize(activeSession.parameters.requirementsSize);
      setExpectedQps(activeSession.parameters.expectedQps);
      setDataConsistency(activeSession.parameters.dataConsistency);
      if (activeSession.stories && activeSession.stories.length > 0) {
        setStories(activeSession.stories);
        setIsSpecCompleted(true);
      } else {
        setStories([]);
        setIsSpecCompleted(false);
      }
      if (activeSession.entities && activeSession.entities.length > 0) {
        setEntities(activeSession.entities);
        setIsSpecCompleted(true);
      } else {
        setEntities([]);
      }
      if (activeSession.stories?.length || activeSession.entities?.length) {
        setCompletedSteps([1, 2, 3, 4, 5]);
      } else {
        setCompletedSteps([]);
      }
    } else {
      // Clean state for fresh new microservice creation
      setServiceName('');
      setPackageName('com.example');
      setDescription('');
      setDirectiveText('');
      setStories([]);
      setEntities([]);
      setDatabase('H2');
      setMessaging('NONE');
      setRequirementsSize('MEDIUM');
      setExpectedQps('1000');
      setDataConsistency('ACID');
      setIsSpecCompleted(false);
      setCompletedSteps([]);
      setCurrentStepIndex(0);
      setActiveAgentLog(null);
      setSpecSuccessMsg(null);
      setValidationError(null);
    }
  }, [activeSessionId, activeSession]);

  // Clickable preset chip selection
  const handleSelectChip = (chip: (typeof COPILOT_PRESET_CHIPS)[0]) => {
    setDirectiveText(chip.directive);
    setServiceName(chip.serviceName);
    setPackageName(chip.packageName);
    setValidationError(null);
  };

  // Entity Model Manipulation Handlers
  const handleAddEntity = () => {
    const nextIdx = entities.length + 1;
    const newEnt: DomainEntity = {
      name: `Entity${nextIdx}`,
      tableName: `entity_${nextIdx}s`,
      description: `Entidad de persistencia Panache JPA para Entity${nextIdx}`,
      fields: [
        { name: 'id', type: 'Long', primaryKey: true, nullable: false, validationRules: ['@NotNull'] },
        { name: 'status', type: 'String', nullable: false, validationRules: ['@NotBlank'] },
        { name: 'createdAt', type: 'Instant', nullable: false, validationRules: ['@NotNull'] },
      ],
    };
    const updated = [...entities, newEnt];
    setEntities(updated);
    setSelectedEntityIdx(entities.length);
    if (activeSession) {
      updateActiveSession({ entities: updated });
    }
  };

  const handleDeleteEntity = (idx: number) => {
    if (entities.length <= 1) return;
    const updated = entities.filter((_, i) => i !== idx);
    setEntities(updated);
    setSelectedEntityIdx(Math.max(0, idx - 1));
    if (activeSession) {
      updateActiveSession({ entities: updated });
    }
  };

  const handleUpdateEntity = (idx: number, patch: Partial<DomainEntity>) => {
    const updated = [...entities];
    updated[idx] = { ...updated[idx], ...patch };
    setEntities(updated);
    if (activeSession) {
      updateActiveSession({ entities: updated });
    }
  };

  const handleAddField = (entityIdx: number) => {
    const updated = [...entities];
    const ent = { ...updated[entityIdx] };
    const nextFieldIdx = ent.fields.length + 1;
    ent.fields = [
      ...ent.fields,
      {
        name: `field${nextFieldIdx}`,
        type: 'String',
        primaryKey: false,
        nullable: true,
        validationRules: [],
      },
    ];
    updated[entityIdx] = ent;
    setEntities(updated);
    if (activeSession) {
      updateActiveSession({ entities: updated });
    }
  };

  const handleDeleteField = (entityIdx: number, fieldIdx: number) => {
    const updated = [...entities];
    const ent = { ...updated[entityIdx] };
    if (ent.fields.length <= 1) return;
    ent.fields = ent.fields.filter((_, i) => i !== fieldIdx);
    updated[entityIdx] = ent;
    setEntities(updated);
    if (activeSession) {
      updateActiveSession({ entities: updated });
    }
  };

  const handleUpdateField = (
    entityIdx: number,
    fieldIdx: number,
    patch: Partial<EntityField>
  ) => {
    const updated = [...entities];
    const ent = { ...updated[entityIdx] };
    const fields = [...ent.fields];
    fields[fieldIdx] = { ...fields[fieldIdx], ...patch };
    ent.fields = fields;
    updated[entityIdx] = ent;
    setEntities(updated);
    if (activeSession) {
      updateActiveSession({ entities: updated });
    }
  };

  const applyDraftToStep = (
    stepNum: number,
    draft: Awaited<ReturnType<typeof draftSpec>>
  ): { stories: BddStory[]; entities: DomainEntity[] } => {
    let nextStories = stories;
    let nextEntities = entities;

    if (stepNum === 1) {
      setServiceName(draft.service_name);
      setPackageName(draft.package_name);
      setDescription(draft.business_objective);
      setActiveAgentLog(
        `[directive_parser] Identificado microservicio: ${draft.service_name} (${draft.package_name})`
      );
    } else if (stepNum === 2) {
      setDatabase(draft.technical_matrix.database);
      setMessaging(draft.technical_matrix.messaging);
      setRequirementsSize(draft.technical_matrix.scope);
      const qpsNum = String(draft.technical_matrix.qps || 1000);
      const resolvedQps: ExpectedQps =
        qpsNum === '100' ? '100' : qpsNum === '5000' || qpsNum === '5000+' ? '5000+' : '1000';
      setExpectedQps(resolvedQps);
      setDataConsistency(draft.technical_matrix.transactional_model);

      if (draft.technical_matrix.messaging === 'KAFKA') {
        setSelectedExtensions((prev) =>
          prev.includes('quarkus-messaging-kafka') ? prev : [...prev, 'quarkus-messaging-kafka']
        );
      }
      setActiveAgentLog(
        `[technical_matrix] Configurado: ${draft.technical_matrix.database} + ${draft.technical_matrix.messaging} (${draft.technical_matrix.transactional_model})`
      );
    } else if (stepNum === 3) {
      if (draft.user_stories && draft.user_stories.length > 0) {
        nextStories = draft.user_stories.map((us, idx) => ({
          id: `US-${String(idx + 1).padStart(3, '0')}`,
          title: us.title,
          role: 'Usuario del Microservicio',
          feature: us.title,
          benefit: us.acceptance_criteria?.[0] || 'Cumplir con las reglas de negocio',
          scenarios: [
            {
              title: us.title,
              given: us.given,
              when: us.when,
              then: us.then,
            },
          ],
          detected_entities: [draft.domain_models?.[0]?.name || 'Resource'],
        }));
        setStories(nextStories);
        setActiveAgentLog(
          `[bdd_synthesizer] ${nextStories.length} historias BDD sintetizadas con escenarios Given/When/Then`
        );
      }
    } else if (stepNum === 4) {
      if (draft.domain_models && draft.domain_models.length > 0) {
        nextEntities = draft.domain_models.map((dm) => ({
          name: dm.name,
          tableName: dm.table_name || `${dm.name.toLowerCase()}s`,
          description: `Entidad de persistencia Panache JPA para ${dm.name}`,
          fields: dm.fields.map((f, fIdx) => ({
            name: f.name,
            type: f.type,
            primaryKey: fIdx === 0 || f.name.toLowerCase() === 'id',
            nullable: f.nullable !== false,
            validationRules: f.constraints || (f.nullable === false ? ['@NotNull'] : []),
          })),
        }));
        setEntities(nextEntities);
        setActiveAgentLog(
          `[domain_modeler] ${nextEntities.length} entidades Panache JPA modeladas con validaciones de persistencia`
        );
      }
    } else if (stepNum === 5) {
      setIsSpecCompleted(true);
      setActiveAgentLog('[speckit_contract] Contrato SpecKit v1 validado y ensamblado exitosamente.');
      setSpecSuccessMsg('✨ Contrato canónico SpecKit validado.');
    }

    return { stories: nextStories, entities: nextEntities };
  };

  // Step-by-Step Individual Step Dispatcher
  const executeStep = async (stepNum: number) => {
    if (!directiveText.trim()) {
      setValidationError('Por favor ingrese una directiva de negocio o seleccione una plantilla rápida.');
      return;
    }
    setValidationError(null);
    setIsDrafting(true);
    goToStep(stepNum);

    try {
      const draft = await draftSpec(
        {
          directive: directiveText.trim(),
          service_name: serviceName.trim() || undefined,
          package_name: packageName.trim() || undefined,
          llm_config: {
            provider,
            model,
            api_key: llmApiKey || undefined,
            endpoint: provider === 'local' ? (endpoint || 'http://127.0.0.1:8080') : (endpoint || undefined),
          },
        },
        apiKey,
        baseUrl,
        llmApiKey || undefined
      );

      applyDraftToStep(stepNum, draft);
      setCompletedSteps((prev) => Array.from(new Set([...prev, stepNum])));
      
      const agentNames: Record<number, string> = {
        1: 'directive_parser',
        2: 'technical_matrix_agent',
        3: 'bdd_synthesizer',
        4: 'panache_domain_modeler',
        5: 'speckit_contract_compiler',
      };
      const agentDescriptions: Record<number, string> = {
        1: `Identificado microservicio: ${draft.service_name} (${draft.package_name})`,
        2: `Recomendado stack: ${draft.technical_matrix.database} + ${draft.technical_matrix.messaging} (${draft.technical_matrix.transactional_model})`,
        3: `Sintetizadas ${draft.user_stories?.length || 2} historias BDD con criterios Given/When/Then`,
        4: `Modeladas ${draft.domain_models?.length || 1} entidades Panache JPA fuertemente tipadas`,
        5: `Contrato canónico SpecKit validado para generación`,
      };
      setAiRecommendations((prev) => ({
        ...prev,
        [stepNum]: {
          agent: agentNames[stepNum] || 'requirements_agent',
          summary: agentDescriptions[stepNum] || 'Recomendación generada por el agente de requisitos',
        },
      }));
    } catch (err: any) {
      setValidationError(`Error en Paso ${stepNum}: ${err.message || 'Error de comunicación'}`);
    } finally {
      setIsDrafting(false);
    }
  };

  // Stepped forward navigation: triggers LLM for the target step and smoothly advances
  const advanceAndExecuteStep = async (targetStepNum: number) => {
    await executeStep(targetStepNum);
  };

  // Reformulate specific step under the command of a Java Quarkus Expert
  const reformulateWithQuarkusExpert = async (stepNum: number) => {
    setIsDrafting(true);
    goToStep(stepNum);
    setValidationError(null);
    setActiveAgentLog(`[quarkus_expert] Re-formulando Paso ${stepNum} bajo estándares Java Quarkus DDD...`);

    try {
      const draft = await draftSpec(
        {
          directive: directiveText.trim() || 'Servicio de procesamiento reactivo empresarial',
          service_name: serviceName.trim() || undefined,
          package_name: packageName.trim() || undefined,
          llm_config: {
            provider,
            model,
            api_key: llmApiKey || undefined,
            endpoint: provider === 'local' ? (endpoint || 'http://127.0.0.1:8080') : (endpoint || undefined),
          },
        },
        apiKey,
        baseUrl,
        llmApiKey || undefined
      );

      if (stepNum === 1) {
        // Step 1: Normalize Java DDD naming and structured technical scope
        const rawName = (draft.service_name || serviceName || 'order-service')
          .toLowerCase()
          .replace(/[^a-z0-9-]/g, '-');
        const formattedServiceName = rawName.endsWith('-service') ? rawName : `${rawName}-service`;
        const domainSlug = formattedServiceName.replace(/-service$/, '').replace(/-/g, '');
        const formattedPackage = `com.tcs.${domainSlug}`;
        const expertScope = `Microservicio empresarial Quarkus 3.15 y Java 21 para ${formattedServiceName}. ` +
          `Delimita el contexto transaccional con endpoints REST asíncronos serializados con Jackson, ` +
          `persistencia reactiva mediante Panache JPA y auditoría de eventos de dominio.`;

        setServiceName(formattedServiceName);
        setPackageName(formattedPackage);
        setDescription(expertScope);
        setActiveAgentLog(`[quarkus_expert] Paso 1: Metadatos y delimitación de contexto re-formulados con estándares Java DDD (${formattedServiceName}).`);
        setCompletedSteps((prev) => Array.from(new Set([...prev, 1])));
      } else if (stepNum === 2) {
        // Step 2: Quarkus technical matrix optimization
        const lowerDirective = `${directiveText} ${description}`.toLowerCase();
        const isKafka =
          lowerDirective.includes('kafka') ||
          lowerDirective.includes('evento') ||
          lowerDirective.includes('stream') ||
          lowerDirective.includes('notif') ||
          lowerDirective.includes('p2p') ||
          lowerDirective.includes('transferencia');
        const dbEngine: DatabaseEngine = 'POSTGRESQL';
        const msgEngine: MessagingSystem = isKafka ? 'KAFKA' : 'NONE';
        const qps: ExpectedQps =
          isKafka || lowerDirective.includes('alto') || lowerDirective.includes('p2p') ? '5000+' : '1000';
        const consistency: ConsistencyModel = 'ACID';

        setDatabase(dbEngine);
        setMessaging(msgEngine);
        setRequirementsSize('MEDIUM');
        setExpectedQps(qps);
        setDataConsistency(consistency);

        const baseExtensions = [
          'quarkus-rest',
          'quarkus-rest-jackson',
          'quarkus-hibernate-orm',
          'quarkus-hibernate-validator',
          'quarkus-smallrye-openapi',
          'quarkus-smallrye-health',
        ];
        if (msgEngine === 'KAFKA') {
          baseExtensions.push('quarkus-messaging-kafka');
        }
        setSelectedExtensions(Array.from(new Set([...selectedExtensions, ...baseExtensions])));
        setActiveAgentLog(
          `[quarkus_expert] Paso 2: Matriz técnica Quarkus 3.15 optimizada (PostgreSQL + ${msgEngine === 'KAFKA' ? 'Kafka SmallRye' : 'REST'} + ${consistency}).`
        );
        setCompletedSteps((prev) => Array.from(new Set([...prev, 2])));
      } else if (stepNum === 3) {
        // Step 3: High-quality BDD stories with REST-assured verification criteria
        let synthStories: BddStory[] = [];
        if (draft.user_stories && draft.user_stories.length > 0) {
          synthStories = draft.user_stories.map((us, idx) => ({
            id: `US-${String(idx + 1).padStart(3, '0')}`,
            title: us.title,
            role: 'Cliente Autorizado',
            feature: us.title,
            benefit: us.acceptance_criteria?.[0] || 'Garantizar consistencia e integridad transaccional',
            scenarios: [
              {
                title: `${us.title} - Flujo Exitoso`,
                given: us.given || 'El microservicio Quarkus está operativo con base de datos sincronizada',
                when: us.when || 'Se recibe una solicitud HTTP POST con payload JSON válido',
                then: us.then || 'Se persiste la entidad con Panache JPA y retorna HTTP 201 Created',
              },
              {
                title: `${us.title} - Validación de Parámetros`,
                given: 'El payload contiene parámetros nulos o valores fuera de rango',
                when: 'Se envía la petición al endpoint REST',
                then: 'Se rechaza con HTTP 400 Bad Request y violaciones de Bean Validation',
              },
            ],
            detected_entities: [draft.domain_models?.[0]?.name || 'Resource'],
          }));
        } else {
          synthStories = [
            {
              id: 'US-001',
              title: `Procesamiento transaccional de ${serviceName}`,
              role: 'Cliente Autorizado',
              feature: 'Ejecutar operación de negocio con validación estricta',
              benefit: 'Asegurar consistencia de saldos y registros contables',
              scenarios: [
                {
                  title: 'Procesamiento exitoso',
                  given: 'Base de datos PostgreSQL conectada y parámetros válidos',
                  when: 'Se invoca el endpoint POST /api/v1/operations con DTO válido',
                  then: 'Se registra la transacción en Panache y retorna HTTP 201 Created',
                },
                {
                  title: 'Rechazo por validación de Bean Validation',
                  given: 'El DTO contiene un monto negativo o id nulo',
                  when: 'Se envía POST a /api/v1/operations',
                  then: 'Retorna HTTP 400 Bad Request detallando violaciones de @Positive / @NotNull',
                },
              ],
              detected_entities: [entities[0]?.name || 'Transaction'],
            },
          ];
        }
        setStories(synthStories);
        setActiveAgentLog(
          `[quarkus_expert] Paso 3: ${synthStories.length} Historias BDD re-formuladas con escenarios REST-assured y validación Bean Validation.`
        );
        setCompletedSteps((prev) => Array.from(new Set([...prev, 3])));
      } else if (stepNum === 4) {
        // Step 4: Panache JPA Entity modeling
        let synthEntities: DomainEntity[] = [];
        if (draft.domain_models && draft.domain_models.length > 0) {
          synthEntities = draft.domain_models.map((dm) => ({
            name: dm.name,
            tableName: dm.table_name || `${dm.name.toLowerCase()}s`,
            description: `Entidad de persistencia Panache JPA para ${dm.name}`,
            fields: dm.fields.map((f, fIdx) => ({
              name: f.name,
              type: f.type,
              primaryKey: fIdx === 0 || f.name.toLowerCase() === 'id',
              nullable: f.nullable !== false,
              validationRules: f.constraints || (f.nullable === false ? ['@NotNull'] : []),
            })),
          }));
        } else {
          const cleanPascal = serviceName
            .split('-')
            .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
            .join('')
            .replace(/Service$/, '') || 'BusinessEntity';
          synthEntities = [
            {
              name: cleanPascal,
              tableName: `${cleanPascal.toLowerCase()}s`,
              description: `Entidad raíz de agregación Panache JPA para ${cleanPascal}`,
              fields: [
                { name: 'id', type: 'Long', primaryKey: true, nullable: false, validationRules: ['@NotNull'] },
                { name: 'referenceNumber', type: 'String', nullable: false, validationRules: ['@NotBlank', '@Size(max=64)'] },
                { name: 'amount', type: 'BigDecimal', nullable: false, validationRules: ['@NotNull', '@Positive'] },
                { name: 'status', type: 'String', nullable: false, validationRules: ['@NotBlank'] },
                { name: 'createdAt', type: 'Instant', nullable: false, validationRules: ['@NotNull'] },
              ],
            },
          ];
        }
        setEntities(synthEntities);
        if (activeSession) {
          updateActiveSession({ entities: synthEntities });
        }
        setActiveAgentLog(
          `[quarkus_expert] Paso 4: ${synthEntities.length} Entidades Panache JPA re-modeladas con tipos Java enterprise y Bean Validation.`
        );
        setCompletedSteps((prev) => Array.from(new Set([...prev, 4])));
      } else if (stepNum === 5) {
        // Step 5: SpecKit validation and compilation
        setCompletedSteps([1, 2, 3, 4, 5]);
        setIsSpecCompleted(true);
        setActiveAgentLog('[quarkus_expert] Paso 5: Contrato SpecKit v1 validado y sincronizado con éxito.');
        setSpecSuccessMsg('✨ Contrato canónico SpecKit validado y listo para Arquitectura & Modelos.');
      }
    } catch (err: any) {
      setValidationError(`Error al re-formular Paso ${stepNum}: ${err.message || 'Error de comunicación'}`);
    } finally {
      setIsDrafting(false);
    }
  };

  // Handle HITL Refinement with LLM
  const handleRefineWithLlm = async (stepNum: number, instructions: string) => {
    if (!instructions.trim()) return;
    setIsRefiningWithLlm(true);
    setValidationError(null);
    setActiveAgentLog(`[refine_llm] Refinando Paso ${stepNum} con instrucciones del usuario: "${instructions.slice(0, 60)}..."`);

    try {
      // Assemble current context for the LLM
      const currentContext = {
        step: stepNum,
        service_name: serviceName,
        package_name: packageName,
        description,
        technical_matrix: {
          database,
          messaging,
          scope: requirementsSize,
          qps: expectedQps,
          transactional_model: dataConsistency,
        },
        user_stories: stories,
        domain_models: entities.map((e) => ({
          name: e.name,
          table_name: e.tableName,
          fields: e.fields,
        })),
      };

      const draft = await draftSpec(
        {
          directive: directiveText.trim() || 'Servicio de procesamiento reactivo empresarial',
          service_name: serviceName.trim() || undefined,
          package_name: packageName.trim() || undefined,
          refinement_instructions: instructions.trim(),
          current_context: currentContext,
          llm_config: {
            provider,
            model,
            api_key: llmApiKey || undefined,
            endpoint: provider === 'local' ? (endpoint || 'http://127.0.0.1:8080') : (endpoint || undefined),
          },
        },
        apiKey,
        baseUrl,
        llmApiKey || undefined
      );

      applyDraftToStep(stepNum, draft);
      setCompletedSteps((prev) => Array.from(new Set([...prev, stepNum])));
      setRefineModalStep(null);
      setRefineInstructions('');
      setActiveAgentLog(`[refine_llm] Paso ${stepNum} refinado y sincronizado con éxito.`);
    } catch (err: any) {
      setValidationError(`Error al refinar con el Agente: ${err.message || 'Error de comunicación'}`);
    } finally {
      setIsRefiningWithLlm(false);
    }
  };

  // Full Procedural Generation Across All 5 Requirements Nodes
  const handleAnalyzeDirective = async () => {
    if (!directiveText.trim()) {
      setValidationError('Por favor ingrese una directiva de negocio o seleccione una plantilla rápida.');
      return;
    }
    setValidationError(null);
    setIsDrafting(true);
    setIsSpecCompleted(false);
    setDraftElapsedTime(0);
    setSpecSuccessMsg(null);
    setCompletedSteps([]);

    const startTime = Date.now();
    const timerInterval = setInterval(() => {
      setDraftElapsedTime(Math.round((Date.now() - startTime) / 100) / 10);
    }, 100);

    try {
      // Step 1: directive_parser
      setCurrentStepIndex(0);
      setActiveAgentLog('[directive_parser] Analizando directiva PMO y delimitando contexto de servicio...');
      const draft = await draftSpec(
        {
          directive: directiveText.trim(),
          service_name: serviceName.trim() || undefined,
          package_name: packageName.trim() || undefined,
          llm_config: {
            provider,
            model,
            api_key: llmApiKey || undefined,
            endpoint: provider === 'local' ? (endpoint || 'http://127.0.0.1:8080') : (endpoint || undefined),
          },
        },
        apiKey,
        baseUrl,
        llmApiKey || undefined
      );

      const STEP_DELAY_MS = typeof process !== 'undefined' && process.env?.NODE_ENV === 'test' ? 0 : 50;

      if (draft._source === 'heuristic_fallback') {
        setActiveAgentLog(
          `⚠️ [Modo Offline / Fallback]: El backend en ${baseUrl} no pudo ser contactado (${draft._error || 'sin respuesta'}). Se generaron requerimientos preliminares sintéticos. Verifique la IP del backend y el LLM en el Drawer.`
        );
        setValidationError(
          `Atención: No se pudo contactar al backend en ${baseUrl}. Se cargó una plantilla heurística preliminar. Para inferencia real con el modelo ${model}, configure la IP del backend en el botón LLM del encabezado.`
        );
      } else {
        setValidationError(null);
        setActiveAgentLog(`[directive_parser] Generación inteligente con ${provider} (${model}): ${draft.service_name} (${draft.package_name})`);
      }

      // Step 1 execution
      setServiceName(draft.service_name);
      setPackageName(draft.package_name);
      setDescription(draft.business_objective);
      setCompletedSteps([1]);
      if (draft._source !== 'heuristic_fallback') {
        setActiveAgentLog(`[directive_parser] Servicio delimitado: ${draft.service_name} (${draft.package_name})`);
      }

      if (STEP_DELAY_MS > 0) await new Promise((r) => setTimeout(r, STEP_DELAY_MS));

      // Step 2: technical_matrix
      setCurrentStepIndex(1);
      setActiveAgentLog('[technical_matrix] Infiriendo base de datos, mensajería reactiva y concurrencia...');
      setDatabase(draft.technical_matrix.database);
      setMessaging(draft.technical_matrix.messaging);
      setRequirementsSize(draft.technical_matrix.scope);
      const qpsNum = String(draft.technical_matrix.qps || 1000);
      const resolvedQps: ExpectedQps =
        qpsNum === '100' ? '100' : qpsNum === '5000' || qpsNum === '5000+' ? '5000+' : '1000';
      setExpectedQps(resolvedQps);
      setDataConsistency(draft.technical_matrix.transactional_model);
      if (draft.technical_matrix.messaging === 'KAFKA') {
        setSelectedExtensions((prev) =>
          prev.includes('quarkus-messaging-kafka') ? prev : [...prev, 'quarkus-messaging-kafka']
        );
      }
      setCompletedSteps([1, 2]);
      setActiveAgentLog(
        `[technical_matrix] Configurado: ${draft.technical_matrix.database} + ${draft.technical_matrix.messaging} (${draft.technical_matrix.transactional_model})`
      );

      if (STEP_DELAY_MS > 0) await new Promise((r) => setTimeout(r, STEP_DELAY_MS));

      // Step 3: bdd_synthesizer
      setCurrentStepIndex(2);
      setActiveAgentLog('[bdd_synthesizer] Sintetizando historias de usuario BDD y escenarios Given/When/Then...');
      let mappedStories: BddStory[] = [];
      if (draft.user_stories && draft.user_stories.length > 0) {
        mappedStories = draft.user_stories.map((us, idx) => ({
          id: `US-${String(idx + 1).padStart(3, '0')}`,
          title: us.title,
          role: 'Usuario del Microservicio',
          feature: us.title,
          benefit: us.acceptance_criteria?.[0] || 'Cumplir con las reglas de negocio',
          scenarios: [
            {
              title: us.title,
              given: us.given,
              when: us.when,
              then: us.then,
            },
          ],
          detected_entities: [draft.domain_models?.[0]?.name || 'Resource'],
        }));
        setStories(mappedStories);
      }
      setCompletedSteps([1, 2, 3]);
      setActiveAgentLog(
        `[bdd_synthesizer] ${mappedStories.length} historias BDD sintetizadas con criterios de aceptación`
      );

      if (STEP_DELAY_MS > 0) await new Promise((r) => setTimeout(r, STEP_DELAY_MS));

      // Step 4: domain_modeler
      setCurrentStepIndex(3);
      setActiveAgentLog('[domain_modeler] Modelando entidades Panache JPA, campos tipados y Bean Validation...');
      let mappedEntities: DomainEntity[] = [];
      if (draft.domain_models && draft.domain_models.length > 0) {
        mappedEntities = draft.domain_models.map((dm) => ({
          name: dm.name,
          tableName: dm.table_name || `${dm.name.toLowerCase()}s`,
          description: `Entidad de persistencia Panache JPA para ${dm.name}`,
          fields: dm.fields.map((f, fIdx) => ({
            name: f.name,
            type: f.type,
            primaryKey: fIdx === 0 || f.name.toLowerCase() === 'id',
            nullable: f.nullable !== false,
            validationRules: f.constraints || (f.nullable === false ? ['@NotNull'] : []),
          })),
        }));
        setEntities(mappedEntities);
      }
      setCompletedSteps([1, 2, 3, 4]);
      setActiveAgentLog(`[domain_modeler] ${mappedEntities.length} entidades Panache JPA modeladas`);

      if (STEP_DELAY_MS > 0) await new Promise((r) => setTimeout(r, STEP_DELAY_MS));

      // Step 5: speckit_contract
      setCurrentStepIndex(4);
      setActiveAgentLog('[speckit_contract] Validando contrato canónico SpecKit y sincronizando sesión...');
      if (activeSession) {
        updateActiveSession({
          name: draft.service_name,
          description: draft.business_objective,
          parameters: {
            ...activeSession.parameters,
            database: draft.technical_matrix.database,
            messaging: draft.technical_matrix.messaging,
            requirementsSize: draft.technical_matrix.scope,
            expectedQps: resolvedQps,
            dataConsistency: draft.technical_matrix.transactional_model,
            workspaceDir:
              activeSession.parameters?.workspaceDir && activeSession.parameters.workspaceDir !== '/tmp/agentia-workspace'
                ? activeSession.parameters.workspaceDir
                : `/tmp/agentia-workspace/${draft.service_name}`,
          },
          stories: mappedStories,
          entities: mappedEntities,
        });
      } else {
        await createSession({
          name: draft.service_name,
          description: draft.business_objective,
          parameters: {
            database: draft.technical_matrix.database,
            messaging: draft.technical_matrix.messaging,
            requirementsSize: draft.technical_matrix.scope,
            expectedQps: resolvedQps,
            dataConsistency: draft.technical_matrix.transactional_model,
            buildTool: 'MAVEN',
            workspaceDir: `/tmp/agentia-workspace/${draft.service_name}`,
          },
          autoRun: false,
          stories: mappedStories,
          entities: mappedEntities,
        });
      }

      setCompletedSteps([1, 2, 3, 4, 5]);
      setIsSpecCompleted(true);
      setActiveAgentLog('[speckit_contract] Contrato canónico SpecKit v1 compilado y sincronizado exitosamente.');
      setDraftElapsedTime(Math.round((Date.now() - startTime) / 100) / 10);
      setSpecSuccessMsg(
        `✨ Especificación estructurada con éxito: ${mappedEntities.length} entidades Panache y ${mappedStories.length} historias BDD inferidas para ${draft.service_name}.`
      );
    } catch (err: any) {
      setIsSpecCompleted(false);
      setValidationError(`Error al procesar pipeline de especificación: ${err.message || 'Error de comunicación'}`);
      setActiveAgentLog(`[error] Fallo en la generación: ${err.message || 'Error'}`);
    } finally {
      clearInterval(timerInterval);
      setIsDrafting(false);
    }
  };

  // Load preset templates
  const handleApplyPreset = (presetId: string) => {
    setSelectedPresetId(presetId);
    const preset = PRESET_TEMPLATES.find((p) => p.id === presetId);
    if (preset) {
      setServiceName(preset.config.serviceName);
      setPackageName(preset.config.packageName);
      setDescription(preset.config.naturalLanguagePrompt);
      setDatabase(preset.config.database as DatabaseEngine);
      setSelectedExtensions(preset.config.extensions);
      const convertedStories: BddStory[] = (preset.userStories || []).map((us, idx) => ({
        id: us.id || `US-${idx + 1}`,
        title: us.title,
        role: 'Usuario',
        feature: us.title,
        benefit: 'Cumplir con los criterios de aceptación',
        scenarios: (us.acceptanceCriteria || []).map((crit: string, cIdx: number) => ({
          title: `Criterio ${cIdx + 1}`,
          given: 'Dado el entorno configurado',
          when: 'Cuando se ejecuta la operación',
          then: crit,
        })),
        detected_entities: [preset.domainModels?.[0]?.name || 'Entity'],
      }));
      setStories(convertedStories);

      if (preset.domainModels && preset.domainModels.length > 0) {
        const convertedEntities: DomainEntity[] = preset.domainModels.map((dm) => ({
          name: dm.name,
          tableName: dm.tableName,
          description: `Entidad de persistencia ${dm.name}`,
          fields: dm.attributes.map((a: any) => ({
            name: a.name,
            type: a.type,
            primaryKey: !!a.primaryKey,
            nullable: a.nullable !== false,
            validationRules: a.nullable === false ? ['@NotNull'] : [],
          })),
        }));
        setEntities(convertedEntities);
      }
      setIsSpecCompleted(true);
      setSpecSuccessMsg(null);
    }
  };

  const handleToggleExtension = (extId: string) => {
    setSelectedExtensions((prev) =>
      prev.includes(extId) ? prev.filter((id) => id !== extId) : [...prev, extId]
    );
  };

  // BDD Story handlers
  const handleAddStory = () => {
    const nextIdx = stories.length + 1;
    const newStory: BddStory = {
      id: `US-${String(nextIdx).padStart(3, '0')}`,
      title: `Operación de Negocio ${nextIdx}`,
      role: 'Usuario del Microservicio',
      feature: 'Ejecutar transacción de negocio',
      benefit: 'Garantizar cumplimiento de regla corporativa',
      scenarios: [
        {
          title: 'Operación válida',
          given: 'El servicio está operativo con dependencias listas',
          when: 'Se envía petición válida',
          then: 'Se procesa con éxito y retorna código HTTP 200/201',
        },
      ],
      detected_entities: [serviceName.split('-')[0] || 'Resource'],
    };
    setStories([...stories, newStory]);
  };

  const handleDeleteStory = (storyId: string) => {
    setStories(stories.filter((s) => s.id !== storyId));
  };


  // Compile full SpecKit Blueprint
  const compiledBlueprint = React.useMemo(() => {
    const cleanServiceName =
      serviceName.trim().toLowerCase().replace(/[^a-z0-9-]/g, '-') || 'microservice';
    const pascalName = cleanServiceName
      .split(/[-_]/)
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
      .join('');

    return {
      name: pascalName,
      serviceName: cleanServiceName,
      packageName: packageName.trim() || 'com.example.service',
      framework: 'quarkus',
      version: '3.15.1',
      javaVersion: 21,
      buildTool: 'MAVEN',
      database,
      databaseEngine: database,
      messagingSystem: messaging,
      requirementsSize,
      expectedQps,
      dataConsistency,
      extensions: selectedExtensions,
      naturalLanguagePrompt: description,
      userStories: stories,
      domainModels: entities.map((e) => ({
        name: e.name,
        tableName: e.tableName,
        attributes: e.fields.map((f) => ({
          name: f.name,
          type: f.type,
          primaryKey: !!f.primaryKey,
          nullable: f.nullable !== false,
          validationRules: f.validationRules || [],
        })),
      })),
      entities,
      llm: {
        provider,
        model,
        endpoint: provider === 'local' ? (endpoint || 'http://127.0.0.1:8080') : (endpoint || undefined),
        apiKey: llmApiKey || undefined,
      },
      workspaceDir: `/tmp/agentia-workspace/${cleanServiceName}`,
    };
  }, [
    serviceName,
    packageName,
    database,
    messaging,
    requirementsSize,
    expectedQps,
    dataConsistency,
    selectedExtensions,
    description,
    stories,
    entities,
    provider,
    model,
    endpoint,
    llmApiKey,
  ]);

  // Save current definition into session
  const handleSaveDefinition = () => {
    if (!serviceName.trim() || !description.trim()) {
      setValidationError('Por favor complete el nombre del servicio y el objetivo de negocio.');
      return;
    }
    setValidationError(null);

    if (activeSession) {
      updateActiveSession({
        name: serviceName.trim(),
        description: description.trim(),
        parameters: {
          ...activeSession.parameters,
          database,
          messaging,
          requirementsSize,
          expectedQps,
          dataConsistency,
        },
        stories,
        entities,
        blueprint: compiledBlueprint,
      });
    }

    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 2000);
  };

  // Primary Stepped Action: Validate, Persist Session & Navigate to Tab 2
  const handleContinueToArchitecture = async () => {
    if (!serviceName.trim() || !description.trim()) {
      setValidationError(
        'Por favor complete el nombre del microservicio y el objetivo de negocio antes de continuar.'
      );
      return;
    }
    setValidationError(null);

    const updatedParams = {
      database,
      messaging,
      requirementsSize,
      expectedQps,
      dataConsistency,
      buildTool: 'MAVEN' as const,
      workspaceDir: `/tmp/agentia-workspace/${serviceName.trim()}`,
    };

    if (!activeSession) {
      await createSession({
        name: serviceName.trim(),
        description: description.trim(),
        parameters: updatedParams,
        autoRun: false,
      });
    } else {
      updateActiveSession({
        name: serviceName.trim(),
        description: description.trim(),
        parameters: {
          ...activeSession.parameters,
          ...updatedParams,
        },
        stories,
        entities,
        blueprint: compiledBlueprint,
      });
    }

    setActiveTab(1); // Navigate to 2. Arquitectura & Modelos
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Quick Presets Header */}
      <div className="bg-gradient-to-r from-blue-950 via-slate-900 to-slate-950 rounded-2xl p-6 text-white border border-blue-900/60 shadow-xl relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-400/30">
                <FileText className="w-3.5 h-3.5" />
                <span>1. Especificación del Microservicio</span>
              </span>
              <span className="font-mono text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                Quarkus 3.15 • Java 21 • Panache JPA
              </span>
            </div>
            <h2 className="text-2xl font-extrabold tracking-tight text-white">
              Definición Integral del Microservicio
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Flujo guiado de ingeniería: redacte una directiva de negocio, estructure la especificación
              para inferir historias BDD y entidades Panache, y continúe a la etapa de Arquitectura & Modelos.
            </p>
          </div>

          {/* Primary Action Buttons */}
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={handleSaveDefinition}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-all shadow-sm"
            >
              <Save className="w-4 h-4 text-slate-400" />
              <span>{saveSuccess ? '¡Guardado!' : 'Guardar Parámetros'}</span>
            </button>

            <button
              type="button"
              onClick={() => void handleContinueToArchitecture()}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 border border-blue-400/40 shadow-lg shadow-blue-500/20 transition-all cursor-pointer"
            >
              <span>Continuar a Arquitectura & Modelos ➜</span>
            </button>
          </div>
        </div>

        {/* Preset Selector Pill Bar */}
        <div className="mt-5 pt-4 border-t border-slate-800/80 flex flex-wrap items-center gap-2.5 text-xs">
          <span className="text-slate-400 font-medium flex items-center gap-1.5 mr-1">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            Plantillas Disponibles:
          </span>
          <button
            type="button"
            onClick={() => handleApplyPreset('customer-billing')}
            className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
              selectedPresetId === 'customer-billing'
                ? 'bg-blue-600/30 border-blue-500 text-blue-200 font-bold'
                : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-800'
            }`}
          >
            Customer Billing (JPA + Bounded Repair)
          </button>
          <button
            type="button"
            onClick={() => handleApplyPreset('order-management')}
            className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
              selectedPresetId === 'order-management'
                ? 'bg-blue-600/30 border-blue-500 text-blue-200 font-bold'
                : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-800'
            }`}
          >
            Order Management (Hexagonal + Reactive)
          </button>
          <button
            type="button"
            onClick={() => setSelectedPresetId('custom')}
            className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
              selectedPresetId === 'custom'
                ? 'bg-blue-600/30 border-blue-500 text-blue-200 font-bold'
                : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-800'
            }`}
          >
            Personalizado
          </button>
        </div>
      </div>

      {/* Validation Error Alert */}
      {validationError && (
        <div className="p-4 rounded-xl bg-rose-950/70 border border-rose-800 text-xs text-rose-200 flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{validationError}</span>
        </div>
      )}

      {/* Specification Success Alert */}
      {specSuccessMsg && (
        <div className="p-4 rounded-xl bg-emerald-950/70 border border-emerald-800 text-xs text-emerald-200 flex items-center gap-2.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{specSuccessMsg}</span>
        </div>
      )}

      {/* Visual Requirements Graph Tracker (Observable Upstream SpecDrafting Pipeline) */}
      <RequirementsGraphTracker
        isDrafting={isDrafting}
        isCompleted={isSpecCompleted}
        error={validationError}
        elapsedTime={draftElapsedTime}
        serviceName={serviceName}
        database={database}
        messaging={messaging}
        storiesCount={stories.length}
        entitiesCount={entities.length}
        currentStepIndex={currentStepIndex}
        completedSteps={completedSteps}
        onStepClick={(stepNum) => void executeStep(stepNum)}
        activeAgentLog={activeAgentLog}
      />

      {/* ========================================================================= */}
      {/* SECTION 0: DIRECTIVA DE NEGOCIO & ESPECIFICACIÓN HITL                     */}
      {/* ========================================================================= */}
      <div id="step-card-0">
        <Card
          title={
            <div className="flex items-center gap-2">
              <BrainCircuit className="w-5 h-5 text-indigo-400" />
              <span>Directiva de Negocio & Requerimientos Funcionales</span>
              <span className="ml-2 px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                Entrada Principal del Negocio
              </span>
            </div>
          }
          subtitle="Único punto de entrada estratégico del PMO / Usuario. Ingrese aquí el caso de negocio o directiva funcional principal. Los 5 pasos posteriores del grafo de requerimientos se derivan, refinan y estructuran a partir de esta directiva."
        >
          <div className="space-y-4">
            {/* Business Input Clarification Banner */}
            <div className="p-3.5 rounded-xl bg-blue-950/40 border border-blue-800/60 text-xs text-blue-200 flex items-start gap-2.5">
              <Sparkles className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-white">Punto de Partida Único:</span> Redacte aquí su directiva funcional o seleccione una plantilla rápida. Puede ejecutar el flujo paso a paso utilizando los botones de cada tarjeta o presionar <strong>Estructurar Especificación</strong> para ejecutar los 5 nodos en cadena.
              </div>
            </div>

            {/* Quick Preset Chips */}
            <div className="space-y-1.5">
              <span className="text-xs font-semibold text-slate-300 block">
                Plantillas Rápidas (Click para cargar directiva):
              </span>
              <div className="flex flex-wrap gap-2">
                {COPILOT_PRESET_CHIPS.map((chip) => (
                  <button
                    key={chip.id}
                    type="button"
                    onClick={() => handleSelectChip(chip)}
                    className="px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-900/80 hover:bg-blue-950/50 hover:border-blue-500/70 text-xs text-slate-300 hover:text-white transition-all flex items-center gap-2 group cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-amber-400 group-hover:scale-110 transition-transform" />
                    <span className="font-semibold text-blue-300">{chip.label}</span>
                    <span className="text-[11px] text-slate-500 hidden sm:inline">({chip.description})</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Directive Text Area */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Directiva de Negocio o Comando del PMO
              </label>
              <textarea
                rows={3}
                value={directiveText}
                onChange={(e) => setDirectiveText(e.target.value)}
                placeholder="Crear un servicio de procesamiento de pagos y transferencias en soles peruanos con límites diarios, notificación Kafka o billetera móvil..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-white focus:outline-hidden focus:border-blue-500 leading-relaxed font-sans placeholder-slate-600"
              />
            </div>

            {/* Stepped Procedural Execution Control Bar */}
            <div className="pt-2 border-t border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="text-[11px] font-semibold text-slate-400 mr-1 flex items-center gap-1">
                  <BrainCircuit className="w-3 h-3 text-indigo-400" />
                  Paso a Paso:
                </span>
                <button
                  type="button"
                  onClick={() => void executeStep(1)}
                  disabled={isDrafting}
                  className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono transition-all cursor-pointer ${
                    completedSteps.includes(1)
                      ? 'bg-emerald-950/60 border-emerald-700/80 text-emerald-300'
                      : 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800 hover:border-slate-700'
                  }`}
                  title="Paso 1: Análisis Directiva PMO (directive_parser)"
                >
                  1. Directiva
                </button>
                <button
                  type="button"
                  onClick={() => void executeStep(2)}
                  disabled={isDrafting}
                  className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono transition-all cursor-pointer ${
                    completedSteps.includes(2)
                      ? 'bg-emerald-950/60 border-emerald-700/80 text-emerald-300'
                      : 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800 hover:border-slate-700'
                  }`}
                  title="Paso 2: Matriz Técnica Quarkus (technical_matrix)"
                >
                  2. Matriz
                </button>
                <button
                  type="button"
                  onClick={() => void executeStep(3)}
                  disabled={isDrafting}
                  className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono transition-all cursor-pointer ${
                    completedSteps.includes(3)
                      ? 'bg-emerald-950/60 border-emerald-700/80 text-emerald-300'
                      : 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800 hover:border-slate-700'
                  }`}
                  title="Paso 3: Historias de Usuario BDD (bdd_synthesizer)"
                >
                  3. BDD ({stories.length})
                </button>
                <button
                  type="button"
                  onClick={() => void executeStep(4)}
                  disabled={isDrafting}
                  className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono transition-all cursor-pointer ${
                    completedSteps.includes(4)
                      ? 'bg-emerald-950/60 border-emerald-700/80 text-emerald-300'
                      : 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800 hover:border-slate-700'
                  }`}
                  title="Paso 4: Modelado Panache JPA (domain_modeler)"
                >
                  4. Entidades ({entities.length})
                </button>
                <button
                  type="button"
                  onClick={() => void executeStep(5)}
                  disabled={isDrafting}
                  className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono transition-all cursor-pointer ${
                    completedSteps.includes(5)
                      ? 'bg-emerald-950/60 border-emerald-700/80 text-emerald-300'
                      : 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800 hover:border-slate-700'
                  }`}
                  title="Paso 5: Compilación SpecKit (speckit_contract)"
                >
                  5. Compilar
                </button>
              </div>

              {/* Primary Action Button: Procedural Pipeline Auto-Run */}
              <button
                type="button"
                onClick={() => void handleAnalyzeDirective()}
                disabled={isDrafting}
                className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-indigo-600 via-blue-600 to-indigo-700 hover:from-indigo-500 hover:to-blue-500 border border-indigo-400/40 shadow-md shadow-indigo-500/20 transition-all disabled:opacity-50 shrink-0 cursor-pointer"
              >
                {isDrafting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-blue-200" />
                    <span>Ejecutando Pipeline Procedimental...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 text-amber-300" />
                    <span>Estructurar Especificación (Pipeline Completo)</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </Card>
      </div>

      {/* ========================================================================= */}
      {/* STEP 1: METADATOS DEL MICROSERVICIO                                      */}
      {/* ========================================================================= */}
      <div id="step-card-1">
        <Card
          title={
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 border border-blue-400/30 flex items-center justify-center text-xs font-bold">
                  1
                </span>
                <span>Paso 1: Identificación & Metadatos del Microservicio</span>
                {aiRecommendations[1] && (
                  <span className="ml-2 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                    <Bot className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Recomendación del Agente ({aiRecommendations[1].agent})</span>
                  </span>
                )}
              </div>
              {completedSteps.includes(1) && (
                <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Completado
                </span>
              )}
            </div>
          }
          subtitle="Nombre del servicio, paquete Java de destino y resumen técnico delimitado por el agente directive_parser a partir de la Directiva Principal."
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Nombre del Microservicio
                </label>
                <input
                  type="text"
                  value={serviceName}
                  onChange={(e) => setServiceName(e.target.value)}
                  placeholder="ej. order-fulfillment-service"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-hidden focus:border-blue-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Paquete Base Java (Package Name)
                </label>
                <input
                  type="text"
                  value={packageName}
                  onChange={(e) => setPackageName(e.target.value)}
                  placeholder="ej. com.tcs.orders"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-hidden focus:border-blue-500 font-mono"
                />
              </div>

              <div className="md:col-span-2">
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-semibold text-slate-300">
                    Resumen de Alcance Técnico (Generado a partir de la Directiva PMO)
                  </label>
                  <span className="text-[10px] text-slate-400 font-normal">
                    Derivado por directive_parser • Editable
                  </span>
                </div>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describa el comportamiento deseado, entidades principales y reglas de negocio..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-white focus:outline-hidden focus:border-blue-500 leading-relaxed font-sans placeholder-slate-600"
                />
              </div>
            </div>

            {/* Step 1 Action Footer */}
            <div className="pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="text-xs text-slate-500">
                Paso 1 de 5 • Delimitación Bounded Context
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setRefineModalStep(1)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-indigo-300 bg-indigo-950/40 hover:bg-indigo-900/50 border border-indigo-700/60 transition-all disabled:opacity-50 cursor-pointer"
                  title="Abre el asistente para dar indicaciones específicas al Agente y refinar los metadatos"
                >
                  <BotMessageSquare className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Refinar con Agente</span>
                </button>
                <button
                  type="button"
                  onClick={() => void reformulateWithQuarkusExpert(1)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-amber-300 bg-amber-950/40 hover:bg-amber-900/50 border border-amber-700/60 transition-all disabled:opacity-50 cursor-pointer"
                  title="Aplica convenciones de nomenclatura Java DDD y sintetiza alcance técnico con Quarkus"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>⚡ Re-formular Metadatos</span>
                </button>
                <button
                  type="button"
                  onClick={() => void advanceAndExecuteStep(2)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 transition-all shadow-sm disabled:opacity-50 cursor-pointer"
                  title="Invoca al agente para inferir la matriz técnica y avanza al Paso 2"
                >
                  {isDrafting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Consultando al Agente...</span>
                    </>
                  ) : (
                    <>
                      <Bot className="w-4 h-4 text-blue-200" />
                      <span>Siguiente: 2. Matriz Técnica</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* ========================================================================= */}
      {/* STEP 2: MATRIZ TÉCNICA QUARKUS 3.X                                       */}
      {/* ========================================================================= */}
      <div id="step-card-2">
        <Card
          title={
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 border border-blue-400/30 flex items-center justify-center text-xs font-bold">
                  2
                </span>
                <span>Paso 2: Matriz de Parámetros Técnicos Quarkus</span>
                {aiRecommendations[2] && (
                  <span className="ml-2 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                    <Bot className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Recomendación del Agente ({aiRecommendations[2].agent})</span>
                  </span>
                )}
              </div>
              {completedSteps.includes(2) && (
                <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Completado
                </span>
              )}
            </div>
          }
          subtitle="Configuración de persistencia, mensajería reactiva, throughput esperado y modelo transaccional sugerido."
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              {/* Base de Datos */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <span className="text-xs font-semibold text-slate-300 block">Base de Datos</span>
                <select
                  value={database}
                  onChange={(e) => setDatabase(e.target.value as DatabaseEngine)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                >
                  <option value="POSTGRESQL">PostgreSQL (Recomendado)</option>
                  <option value="MYSQL">MySQL</option>
                  <option value="H2">H2 (In-Memory Test)</option>
                  <option value="NONE">Ninguna (Stateless)</option>
                </select>
                <span className="text-[11px] text-slate-500 block">Hibernate ORM con Panache</span>
              </div>

              {/* Mensajería */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <span className="text-xs font-semibold text-slate-300 block">Broker Mensajería</span>
                <select
                  value={messaging}
                  onChange={(e) => setMessaging(e.target.value as MessagingSystem)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                >
                  <option value="KAFKA">Apache Kafka (SmallRye)</option>
                  <option value="RABBITMQ">RabbitMQ</option>
                  <option value="NONE">Sin mensajería</option>
                </select>
                <span className="text-[11px] text-slate-500 block">Event-Driven Reactive Messaging</span>
              </div>

              {/* Tamaño / Scope */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <span className="text-xs font-semibold text-slate-300 block">Alcance de Entidades</span>
                <select
                  value={requirementsSize}
                  onChange={(e) => setRequirementsSize(e.target.value as RequirementsSize)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                >
                  <option value="LOW">Bajo (1-2 entidades)</option>
                  <option value="MEDIUM">Medio (3-5 entidades)</option>
                  <option value="HIGH">Alto (6-10 entidades)</option>
                  <option value="ENTERPRISE">Enterprise (10+)</option>
                </select>
                <span className="text-[11px] text-slate-500 block">Complejidad del dominio</span>
              </div>

              {/* QPS */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <span className="text-xs font-semibold text-slate-300 block">Throughput (QPS)</span>
                <select
                  value={expectedQps}
                  onChange={(e) => setExpectedQps(e.target.value as ExpectedQps)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                >
                  <option value="100">100 req/s</option>
                  <option value="1000">1,000 req/s</option>
                  <option value="5000+">5,000+ req/s (Reactive)</option>
                </select>
                <span className="text-[11px] text-slate-500 block">Dimensionamiento de hilos</span>
              </div>

              {/* Consistencia */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <span className="text-xs font-semibold text-slate-300 block">Consistencia</span>
                <select
                  value={dataConsistency}
                  onChange={(e) => setDataConsistency(e.target.value as ConsistencyModel)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                >
                  <option value="ACID">ACID Transaccional</option>
                  <option value="EVENTUAL">Eventual (Saga/Outbox)</option>
                </select>
                <span className="text-[11px] text-slate-500 block">Aislamiento de datos</span>
              </div>
            </div>

            {/* Extensiones Quarkus Selector */}
            <div className="pt-2 border-t border-slate-800/80">
              <label className="block text-xs font-semibold text-slate-300 mb-2">
                Extensiones Quarkus Oficiales Incluidas:
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                {AVAILABLE_QUARKUS_EXTENSIONS.map((ext) => {
                  const isChecked = selectedExtensions.includes(ext.id);
                  return (
                    <button
                      key={ext.id}
                      type="button"
                      onClick={() => handleToggleExtension(ext.id)}
                      className={`text-left p-2.5 rounded-xl border text-xs transition-all flex items-start gap-2.5 cursor-pointer ${
                        isChecked
                          ? 'bg-blue-950/40 border-blue-600/70 text-blue-200'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      <div
                        className={`w-4 h-4 rounded mt-0.5 flex items-center justify-center border text-[10px] ${
                          isChecked
                            ? 'bg-blue-600 border-blue-500 text-white font-bold'
                            : 'border-slate-700 bg-slate-900'
                        }`}
                      >
                        {isChecked && '✓'}
                      </div>
                      <div>
                        <div className="font-semibold text-slate-200">{ext.name}</div>
                        <div className="text-[11px] text-slate-500">{ext.description}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Step 2 Action Footer */}
            <div className="pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => goToStep(1)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-700 transition-all cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>⮌ Paso Anterior: 1. Metadatos</span>
              </button>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setRefineModalStep(2)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-indigo-300 bg-indigo-950/40 hover:bg-indigo-900/50 border border-indigo-700/60 transition-all disabled:opacity-50 cursor-pointer"
                  title="Abre el asistente para dar indicaciones específicas al Agente y refinar la matriz técnica"
                >
                  <BotMessageSquare className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Refinar con Agente</span>
                </button>
                <button
                  type="button"
                  onClick={() => void reformulateWithQuarkusExpert(2)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-amber-300 bg-amber-950/40 hover:bg-amber-900/50 border border-amber-700/60 transition-all disabled:opacity-50 cursor-pointer"
                  title="Alinea base de datos PostgreSQL, broker Kafka y extensiones recomendadas"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>⚡ Re-formular Matriz</span>
                </button>
                <button
                  type="button"
                  onClick={() => void advanceAndExecuteStep(3)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 transition-all shadow-sm disabled:opacity-50 cursor-pointer"
                  title="Invoca al agente bdd_synthesizer para inferir historias BDD y avanza al Paso 3"
                >
                  {isDrafting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Consultando al Agente...</span>
                    </>
                  ) : (
                    <>
                      <Bot className="w-4 h-4 text-blue-200" />
                      <span>Siguiente: 3. Historias BDD</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* ========================================================================= */}
      {/* STEP 3: HISTORIAS DE USUARIO BDD                                         */}
      {/* ========================================================================= */}
      <div id="step-card-3">
        <Card
          title={
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 border border-blue-400/30 flex items-center justify-center text-xs font-bold">
                  3
                </span>
                <span>Paso 3: Historias de Usuario BDD (Given / When / Then)</span>
                {aiRecommendations[3] && (
                  <span className="ml-2 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                    <Bot className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Recomendación del Agente ({aiRecommendations[3].agent})</span>
                  </span>
                )}
              </div>
              {completedSteps.includes(3) && (
                <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Completado
                </span>
              )}
            </div>
          }
          subtitle="Casos de uso formales sugeridos a partir de los requisitos que alimentan la generación de pruebas de integración y contratos REST."
          action={
            <button
              type="button"
              onClick={handleAddStory}
              className="flex items-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-semibold text-blue-300 bg-blue-950/60 border border-blue-800 hover:bg-blue-900/60 transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Agregar Historia</span>
            </button>
          }
        >
          <div className="space-y-4">
            <div className="space-y-3">
              {stories.map((story) => (
                <div
                  key={story.id}
                  className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs px-2 py-0.5 rounded bg-blue-950 border border-blue-800 text-blue-300 font-bold">
                        {story.id}
                      </span>
                      <input
                        type="text"
                        value={story.title}
                        onChange={(e) => {
                          const updated = stories.map((s) =>
                            s.id === story.id ? { ...s, title: e.target.value } : s
                          );
                          setStories(updated);
                        }}
                        className="bg-transparent border-b border-transparent hover:border-slate-700 focus:border-blue-500 text-xs font-bold text-white px-1 py-0.5 focus:outline-hidden"
                      />
                    </div>
                    {stories.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleDeleteStory(story.id)}
                        className="p-1 text-slate-500 hover:text-rose-400 transition-colors rounded cursor-pointer"
                        title="Eliminar historia"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs bg-slate-900/60 p-3 rounded-lg border border-slate-800/80">
                    <div>
                      <span className="text-slate-500 block text-[11px] font-semibold">Como (Rol):</span>
                      <input
                        type="text"
                        value={story.role}
                        onChange={(e) => {
                          const updated = stories.map((s) =>
                            s.id === story.id ? { ...s, role: e.target.value } : s
                          );
                          setStories(updated);
                        }}
                        className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-300 text-xs mt-1"
                      />
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px] font-semibold">Quiero (Capacidad):</span>
                      <input
                        type="text"
                        value={story.feature}
                        onChange={(e) => {
                          const updated = stories.map((s) =>
                            s.id === story.id ? { ...s, feature: e.target.value } : s
                          );
                          setStories(updated);
                        }}
                        className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-300 text-xs mt-1"
                      />
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px] font-semibold">Para (Beneficio):</span>
                      <input
                        type="text"
                        value={story.benefit}
                        onChange={(e) => {
                          const updated = stories.map((s) =>
                            s.id === story.id ? { ...s, benefit: e.target.value } : s
                          );
                          setStories(updated);
                        }}
                        className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-300 text-xs mt-1"
                      />
                    </div>
                  </div>

                  {/* Scenarios Given / When / Then */}
                  <div className="space-y-2">
                    {story.scenarios.map((sc, sIdx) => (
                      <div
                        key={sIdx}
                        className="p-3 rounded-lg bg-slate-900/40 border border-slate-800 text-xs space-y-2 font-mono text-[11px]"
                      >
                        <div className="text-slate-400 font-sans font-semibold mb-1">
                          Escenario: {sc.title}
                        </div>
                        <div className="flex flex-col sm:flex-row sm:items-center gap-1.5">
                          <span className="text-slate-500 shrink-0 w-24">Dado (Given):</span>
                          <input
                            type="text"
                            value={sc.given}
                            onChange={(e) => {
                              const updated = stories.map((s) => {
                                if (s.id !== story.id) return s;
                                const newSc = [...s.scenarios];
                                newSc[sIdx] = { ...newSc[sIdx], given: e.target.value };
                                return { ...s, scenarios: newSc };
                              });
                              setStories(updated);
                            }}
                            className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-blue-300 font-mono text-xs"
                          />
                        </div>
                        <div className="flex flex-col sm:flex-row sm:items-center gap-1.5">
                          <span className="text-slate-500 shrink-0 w-24">Cuando (When):</span>
                          <input
                            type="text"
                            value={sc.when}
                            onChange={(e) => {
                              const updated = stories.map((s) => {
                                if (s.id !== story.id) return s;
                                const newSc = [...s.scenarios];
                                newSc[sIdx] = { ...newSc[sIdx], when: e.target.value };
                                return { ...s, scenarios: newSc };
                              });
                              setStories(updated);
                            }}
                            className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-amber-300 font-mono text-xs"
                          />
                        </div>
                        <div className="flex flex-col sm:flex-row sm:items-center gap-1.5">
                          <span className="text-slate-500 shrink-0 w-24">Entonces (Then):</span>
                          <input
                            type="text"
                            value={sc.then}
                            onChange={(e) => {
                              const updated = stories.map((s) => {
                                if (s.id !== story.id) return s;
                                const newSc = [...s.scenarios];
                                newSc[sIdx] = { ...newSc[sIdx], then: e.target.value };
                                return { ...s, scenarios: newSc };
                              });
                              setStories(updated);
                            }}
                            className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-emerald-300 font-mono text-xs"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Step 3 Action Footer */}
            <div className="pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => goToStep(2)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-700 transition-all cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>⮌ Paso Anterior: 2. Matriz Técnica</span>
              </button>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setRefineModalStep(3)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-indigo-300 bg-indigo-950/40 hover:bg-indigo-900/50 border border-indigo-700/60 transition-all disabled:opacity-50 cursor-pointer"
                  title="Abre el asistente para dar indicaciones al Agente y refinar historias de usuario BDD"
                >
                  <BotMessageSquare className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Refinar con Agente</span>
                </button>
                <button
                  type="button"
                  onClick={() => void reformulateWithQuarkusExpert(3)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-amber-300 bg-amber-950/40 hover:bg-amber-900/50 border border-amber-700/60 transition-all disabled:opacity-50 cursor-pointer"
                  title="Sintetiza historias BDD con aserciones RestAssured y validaciones de Bean Validation"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>⚡ Re-sintetizar BDD</span>
                </button>
                <button
                  type="button"
                  onClick={() => void advanceAndExecuteStep(4)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 transition-all shadow-sm disabled:opacity-50 cursor-pointer"
                  title="Invoca al agente panache_domain_modeler para inferir entidades Panache JPA y avanza al Paso 4"
                >
                  {isDrafting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Consultando al Agente...</span>
                    </>
                  ) : (
                    <>
                      <Bot className="w-4 h-4 text-blue-200" />
                      <span>Siguiente: 4. Entidades Panache</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* ========================================================================= */}
      {/* STEP 4: MODELADO DE ENTIDADES PANACHE JPA                                */}
      {/* ========================================================================= */}
      <div id="step-card-4">
        <Card
          title={
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 border border-blue-400/30 flex items-center justify-center text-xs font-bold">
                  4
                </span>
                <span>Paso 4: Modelador de Entidades Panache JPA</span>
                <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 ml-2">
                  {entities.length} {entities.length === 1 ? 'entidad' : 'entidades'}
                </span>
                {aiRecommendations[4] && (
                  <span className="ml-2 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                    <Bot className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Recomendación del Agente ({aiRecommendations[4].agent})</span>
                  </span>
                )}
              </div>
              {completedSteps.includes(4) && (
                <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Completado
                </span>
              )}
            </div>
          }
          subtitle="Entidades de persistencia Quarkus Panache (Active Record / Repository) con tipos de datos fuertemente tipados (UUID, BigDecimal, Instant) y reglas de Bean Validation (@NotNull, @Positive)."
          action={
            <button
              type="button"
              onClick={handleAddEntity}
              className="flex items-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-semibold text-blue-300 bg-blue-950/60 border border-blue-800 hover:bg-blue-900/60 transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Nueva Entidad</span>
            </button>
          }
        >
          <div className="space-y-4">
            {/* Entity Selector Tabs */}
            <div className="flex flex-wrap items-center gap-2 pb-3 border-b border-slate-800">
              {entities.map((ent, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedEntityIdx(idx)}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-mono font-semibold transition-all flex items-center gap-2 cursor-pointer ${
                    selectedEntityIdx === idx
                      ? 'bg-blue-600/30 border-blue-500 text-blue-200'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  <Table className="w-3 h-3" />
                  <span>{ent.name || `Entity${idx + 1}`}</span>
                  <span className="text-[10px] text-slate-500">({ent.fields.length} campos)</span>
                </button>
              ))}
              <button
                type="button"
                onClick={handleAddEntity}
                className="px-2.5 py-1 rounded-lg border border-dashed border-slate-700 text-slate-400 hover:text-white text-xs flex items-center gap-1 cursor-pointer"
              >
                <Plus className="w-3 h-3" /> Entidad
              </button>
            </div>

            {/* Selected Entity Editor */}
            {entities[selectedEntityIdx] ? (
              <div className="space-y-3 bg-slate-900/40 p-3.5 rounded-xl border border-slate-800">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                      Nombre de la Entidad (Clase Java)
                    </label>
                    <input
                      type="text"
                      value={entities[selectedEntityIdx].name}
                      onChange={(e) =>
                        handleUpdateEntity(selectedEntityIdx, { name: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                      Tabla de Base de Datos (PostgreSQL)
                    </label>
                    <input
                      type="text"
                      value={entities[selectedEntityIdx].tableName}
                      onChange={(e) =>
                        handleUpdateEntity(selectedEntityIdx, { tableName: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-blue-300 font-mono"
                    />
                  </div>
                  <div className="flex items-end justify-between gap-2">
                    <div className="w-full">
                      <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                        Descripción del Dominio
                      </label>
                      <input
                        type="text"
                        value={entities[selectedEntityIdx].description}
                        onChange={(e) =>
                          handleUpdateEntity(selectedEntityIdx, { description: e.target.value })
                        }
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-sans"
                      />
                    </div>
                    {entities.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleDeleteEntity(selectedEntityIdx)}
                        className="p-2 text-slate-500 hover:text-rose-400 border border-slate-800 rounded-lg hover:border-rose-800/80 transition-colors cursor-pointer shrink-0"
                        title="Eliminar entidad"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Fields Table */}
                <div className="space-y-1.5 pt-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-slate-300">
                      Campos & Atributos Fuertemente Tipados:
                    </span>
                    <button
                      type="button"
                      onClick={() => handleAddField(selectedEntityIdx)}
                      className="text-[11px] text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-1 cursor-pointer"
                    >
                      <Plus className="w-3 h-3" /> Agregar Campo
                    </button>
                  </div>

                  <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-900/80 text-[10px] font-mono text-slate-400 uppercase border-b border-slate-800">
                        <tr>
                          <th className="p-2.5">Campo Java</th>
                          <th className="p-2.5">Tipo de Dato</th>
                          <th className="p-2.5 text-center">PK</th>
                          <th className="p-2.5">Reglas Bean Validation</th>
                          <th className="p-2.5 text-right">Acción</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-850">
                        {entities[selectedEntityIdx].fields.map((f, fIdx) => (
                          <tr key={fIdx} className="hover:bg-slate-900/40">
                            <td className="p-2">
                              <input
                                type="text"
                                value={f.name || ''}
                                onChange={(e) =>
                                  handleUpdateField(selectedEntityIdx, fIdx, { name: e.target.value })
                                }
                                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-white font-mono text-xs"
                              />
                            </td>
                            <td className="p-2">
                              <select
                                value={f.type || 'String'}
                                onChange={(e) =>
                                  handleUpdateField(selectedEntityIdx, fIdx, { type: e.target.value })
                                }
                                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-blue-300 font-mono text-xs"
                              >
                                <option value="Long">Long</option>
                                <option value="UUID">UUID</option>
                                <option value="String">String</option>
                                <option value="BigDecimal">BigDecimal</option>
                                <option value="Instant">Instant</option>
                                <option value="Integer">Integer</option>
                                <option value="Boolean">Boolean</option>
                                <option value="Double">Double</option>
                              </select>
                            </td>
                            <td className="p-2 text-center">
                              <input
                                type="checkbox"
                                checked={Boolean(f.primaryKey)}
                                onChange={(e) =>
                                  handleUpdateField(selectedEntityIdx, fIdx, { primaryKey: e.target.checked })
                                }
                                className="rounded border-slate-700 bg-slate-900 text-blue-600 focus:ring-0 cursor-pointer"
                              />
                            </td>
                            <td className="p-2">
                              <input
                                type="text"
                                value={(f.validationRules || []).join(', ')}
                                onChange={(e) => {
                                  const rules = e.target.value
                                    .split(',')
                                    .map((r) => r.trim())
                                    .filter(Boolean);
                                  handleUpdateField(selectedEntityIdx, fIdx, { validationRules: rules });
                                }}
                                placeholder="@NotNull, @Positive..."
                                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-emerald-300 font-mono text-xs"
                              />
                            </td>
                            <td className="p-2 text-right">
                              {entities[selectedEntityIdx].fields.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => handleDeleteField(selectedEntityIdx, fIdx)}
                                  className="text-slate-500 hover:text-rose-400 p-1 rounded transition-colors cursor-pointer"
                                  title="Eliminar campo"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-4 text-center text-xs text-slate-500 bg-slate-950 rounded-xl border border-slate-800">
                No hay entidades definidas. Haga clic en Nueva Entidad o ejecute el modelador automático.
              </div>
            )}

            {/* Step 4 Action Footer */}
            <div className="pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => goToStep(3)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-700 transition-all cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>⮌ Paso Anterior: 3. Historias BDD</span>
              </button>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setRefineModalStep(4)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-indigo-300 bg-indigo-950/40 hover:bg-indigo-900/50 border border-indigo-700/60 transition-all disabled:opacity-50 cursor-pointer"
                  title="Abre el asistente para dar indicaciones al Agente y refinar el modelo de entidades Panache JPA"
                >
                  <BotMessageSquare className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Refinar con Agente</span>
                </button>
                <button
                  type="button"
                  onClick={() => void reformulateWithQuarkusExpert(4)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-amber-300 bg-amber-950/40 hover:bg-amber-900/50 border border-amber-700/60 transition-all disabled:opacity-50 cursor-pointer"
                  title="Modelado Panache JPA con tipos BigDecimal, Instant y Bean Validation"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>⚡ Re-modelar Entidades</span>
                </button>
                <button
                  type="button"
                  onClick={() => void advanceAndExecuteStep(5)}
                  disabled={isDrafting || isRefiningWithLlm}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 transition-all shadow-sm disabled:opacity-50 cursor-pointer"
                  title="Invoca al agente speckit_contract_compiler para compilar y validar el contrato canónico y avanza al Paso 5"
                >
                  {isDrafting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Consultando al Agente...</span>
                    </>
                  ) : (
                    <>
                      <Bot className="w-4 h-4 text-blue-200" />
                      <span>Siguiente: 5. Compilar SpecKit</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* ========================================================================= */}
      {/* STEP 5: COMPILACIÓN & VALIDACIÓN DEL CONTRATO SPECKIT                    */}
      {/* ========================================================================= */}
      <div id="step-card-5">
        <Card
          title={
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 border border-blue-400/30 flex items-center justify-center text-xs font-bold">
                  5
                </span>
                <span>Paso 5: Compilación & Validación del Contrato SpecKit</span>
                {aiRecommendations[5] && (
                  <span className="ml-2 inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                    <Bot className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Recomendación del Agente ({aiRecommendations[5].agent})</span>
                  </span>
                )}
              </div>
              {completedSteps.includes(5) && (
                <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Contrato Compilado
                </span>
              )}
            </div>
          }
          subtitle="Consolidación canónica del contrato SpecKit v1 que gobierna la generación, verificación y autorreparación acotada del microservicio."
        >
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Microservicio</span>
                <span className="font-mono font-bold text-white">{serviceName || 'No especificado'}</span>
                <span className="text-[10px] text-slate-500 block">{packageName}</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Stack Tecnológico</span>
                <span className="font-mono font-bold text-white">{database} • {messaging}</span>
                <span className="text-[10px] text-slate-500 block">Quarkus 3.15 • Java 21 • Maven</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Historias BDD</span>
                <span className="font-mono font-bold text-white">{stories.length} Historias</span>
                <span className="text-[10px] text-slate-500 block">Criterios Given/When/Then</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Entidades Panache</span>
                <span className="font-mono font-bold text-white">{entities.length} Entidades JPA</span>
                <span className="text-[10px] text-slate-500 block">Bean Validation (@NotNull, @Positive)</span>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800/60 flex items-center justify-between gap-3 text-xs text-emerald-200">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>
                  Todos los nodos del grafo de requerimientos han sido completados y validados. El contrato canónico está listo para la etapa de arquitectura.
                </span>
              </div>
            </div>

            {/* Step 5 Action Footer */}
            <div className="pt-3 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => goToStep(4)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-700 transition-all cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>⮌ Paso Anterior: 4. Entidades Panache</span>
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void reformulateWithQuarkusExpert(5)}
                  disabled={isDrafting}
                  className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-semibold text-emerald-300 bg-emerald-950/60 hover:bg-emerald-900/60 border border-emerald-700 transition-all cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                  <span>⚡ Validar y Compilar SpecKit</span>
                </button>
                <button
                  type="button"
                  onClick={() => void handleContinueToArchitecture()}
                  className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-lg shadow-blue-500/20 transition-all cursor-pointer"
                >
                  <span>Continuar a Arquitectura & Modelos ➜</span>
                </button>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* ========================================================================= */}
      {/* HITL REFINEMENT MODAL (ASSISTED REFORMULATION & CONTEXT UPDATE)          */}
      {/* ========================================================================= */}
      {refineModalStep !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center">
                  <BotMessageSquare className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">
                    Refinar Paso {refineModalStep}: {
                      refineModalStep === 1
                        ? 'Metadatos & Alcance'
                        : refineModalStep === 2
                        ? 'Matriz Técnica Quarkus'
                        : refineModalStep === 3
                        ? 'Historias de Usuario BDD'
                        : refineModalStep === 4
                        ? 'Entidades Panache JPA'
                        : 'Contrato SpecKit'
                    }
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Proporcione instrucciones al Agente para ajustar o reformular este paso sin perder el contexto actual.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setRefineModalStep(null);
                  setRefineInstructions('');
                }}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Indicaciones para el Agente ({model})
                </label>
                <textarea
                  rows={4}
                  value={refineInstructions}
                  onChange={(e) => setRefineInstructions(e.target.value)}
                  placeholder={
                    refineModalStep === 1
                      ? 'ej. "Cambia el nombre a wallet-core-service y delimita el paquete como com.banco.wallet. Enfócate en transferencias interbancarias."'
                      : refineModalStep === 2
                      ? 'ej. "Cambia la base de datos a PostgreSQL con 5000 QPS e incluye Kafka SmallRye para eventos de saldo."'
                      : refineModalStep === 3
                      ? 'ej. "Agrega un escenario de validación de fondos insuficientes con HTTP 422 y uno de concurrencia."'
                      : refineModalStep === 4
                      ? 'ej. "Agrega a la entidad un campo balance de tipo BigDecimal con validación @PositiveOrZero y un campo currency String."'
                      : 'ej. "Consolida las reglas bajo el modelo transaccional ACID estricto."'
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-white focus:outline-hidden focus:border-indigo-500 leading-relaxed font-sans placeholder-slate-600"
                />
              </div>

              {/* Context Summary Preview */}
              <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 text-[11px] space-y-1">
                <span className="font-semibold text-indigo-300 block">Contexto que se enviará al Agente:</span>
                <div className="text-slate-400 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px]">
                  <span>Servicio: <strong className="text-white">{serviceName || 'N/A'}</strong></span>
                  <span>DB: <strong className="text-white">{database}</strong></span>
                  <span>Mensajería: <strong className="text-white">{messaging}</strong></span>
                  <span>Historias: <strong className="text-white">{stories.length}</strong></span>
                  <span>Entidades: <strong className="text-white">{entities.length}</strong></span>
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => {
                  setRefineModalStep(null);
                  setRefineInstructions('');
                }}
                disabled={isRefiningWithLlm}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 transition-colors cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => void handleRefineWithLlm(refineModalStep, refineInstructions)}
                disabled={isRefiningWithLlm || !refineInstructions.trim()}
                className="flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 shadow-md shadow-indigo-600/20 transition-all disabled:opacity-50 cursor-pointer"
              >
                {isRefiningWithLlm ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Refinando con el Agente...</span>
                  </>
                ) : (
                  <>
                    <Bot className="w-3.5 h-3.5 text-amber-300" />
                    <span>Aplicar Refinamiento</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
