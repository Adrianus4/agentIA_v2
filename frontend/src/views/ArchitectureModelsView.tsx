import React, { useState, useEffect, useMemo } from 'react';
import {
  Layers,
  Database,
  ArrowRight,
  Boxes,
  Globe,
  Radio,
  Table,
  Copy,
  Check,
  Plus,
  Trash2,
  Play,
  Activity,
  Cpu,
  Workflow,
  Sparkles,
  Loader2,
  X,
  Bot,
  BotMessageSquare,
} from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { useLlm } from '../context/LlmContext';
import { Card } from '../components/common/Card';
import type { DomainEntity, ArchitecturePattern } from '../types/studio';
import { CoderGraphTracker } from '../components/orchestration/CoderGraphTracker';
import { draftSpec } from '../services/blueprintService';

export const ArchitectureModelsView: React.FC = () => {
  const {
    activeSession,
    updateActiveSession,
    executeLangGraph,
    isExecuting,
    setIsTelemetryDrawerOpen,
    setActiveTab,
    baseUrl,
    apiKey,
  } = useStudio();
  const { provider, model, endpoint, apiKey: llmApiKey } = useLlm();

  if (!activeSession) {
    return (
      <div className="text-center py-12 text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
        <Layers className="w-12 h-12 mx-auto mb-3 text-slate-500" />
        <h3 className="text-base font-bold text-white">No hay un microservicio seleccionado</h3>
        <p className="text-xs text-slate-500 mt-1">
          Regrese a la etapa de Especificación o seleccione un servicio en el panel lateral.
        </p>
      </div>
    );
  }

  // Interactive Sub-views & tabs
  const [archTabMode, setArchTabMode] = useState<'diagram' | 'contracts'>('diagram');
  const [modelTabMode, setModelTabMode] = useState<'entities' | 'sql'>('entities');
  const [selectedEntityIdx, setSelectedEntityIdx] = useState(0);
  const [copiedSql, setCopiedSql] = useState(false);

  // Architectural Pattern Selection (Parity with Legacy v1 & Multi-pattern support)
  const [selectedArch, setSelectedArch] = useState<ArchitecturePattern>(
    (activeSession.parameters.architecture as ArchitecturePattern) ||
    'hexagonal'
  );

  useEffect(() => {
    if (activeSession.parameters.architecture && activeSession.parameters.architecture !== selectedArch) {
      setSelectedArch(activeSession.parameters.architecture as ArchitecturePattern);
    }
  }, [activeSession.parameters.architecture]);

  const handleSelectArchitecture = (arch: ArchitecturePattern) => {
    setSelectedArch(arch);
    updateActiveSession({
      parameters: {
        ...activeSession.parameters,
        architecture: arch,
      },
    });
  };

  // Entities state synchronized with activeSession
  const [entities, setEntities] = useState<DomainEntity[]>(
    activeSession.entities && activeSession.entities.length > 0
      ? activeSession.entities
      : [
          {
            name: 'Order',
            tableName: 'orders',
            description: 'Entidad de dominio principal',
            fields: [
              { name: 'id', type: 'Long', primaryKey: true, nullable: false, validationRules: ['@NotNull'] },
              { name: 'status', type: 'String', nullable: false, validationRules: ['@NotBlank'] },
              { name: 'createdAt', type: 'Instant', nullable: false, validationRules: ['@NotNull'] },
            ],
          },
        ]
  );

  useEffect(() => {
    if (activeSession.entities && activeSession.entities.length > 0) {
      setEntities(activeSession.entities);
    }
  }, [activeSession.entities]);

  const safeEntityIdx = Math.min(selectedEntityIdx, Math.max(0, entities.length - 1));
  const currentEntity = entities[safeEntityIdx] || entities[0];

  // Entity editing handlers
  const handleUpdateEntities = (updated: DomainEntity[]) => {
    setEntities(updated);
    updateActiveSession({ entities: updated });
  };

  const handleAddEntity = () => {
    const nextIdx = entities.length + 1;
    const newEnt: DomainEntity = {
      name: `Entity${nextIdx}`,
      tableName: `entity_${nextIdx}s`,
      description: `Nueva entidad de persistencia ${nextIdx}`,
      fields: [
        { name: 'id', type: 'Long', primaryKey: true, nullable: false, validationRules: ['@NotNull'] },
        { name: 'name', type: 'String', nullable: false, validationRules: ['@NotBlank'] },
        { name: 'createdAt', type: 'Instant', nullable: false, validationRules: ['@NotNull'] },
      ],
    };
    const updated = [...entities, newEnt];
    handleUpdateEntities(updated);
    setSelectedEntityIdx(entities.length);
  };

  const handleDeleteEntity = (idx: number) => {
    if (entities.length <= 1) return;
    const updated = entities.filter((_, i) => i !== idx);
    handleUpdateEntities(updated);
    setSelectedEntityIdx(Math.max(0, idx - 1));
  };

  const handleUpdateEntityMeta = (idx: number, patch: Partial<DomainEntity>) => {
    const updated = [...entities];
    updated[idx] = { ...updated[idx], ...patch };
    handleUpdateEntities(updated);
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
        nullable: true,
        validationRules: [],
      },
    ];
    updated[entityIdx] = ent;
    handleUpdateEntities(updated);
  };

  const handleDeleteField = (entityIdx: number, fieldIdx: number) => {
    const updated = [...entities];
    const ent = { ...updated[entityIdx] };
    if (ent.fields.length <= 1) return;
    ent.fields = ent.fields.filter((_, i) => i !== fieldIdx);
    updated[entityIdx] = ent;
    handleUpdateEntities(updated);
  };

  const handleUpdateField = (
    entityIdx: number,
    fieldIdx: number,
    patch: Partial<DomainEntity['fields'][0]>
  ) => {
    const updated = [...entities];
    const ent = { ...updated[entityIdx] };
    const fields = [...ent.fields];
    fields[fieldIdx] = { ...fields[fieldIdx], ...patch };
    ent.fields = fields;
    updated[entityIdx] = ent;
    handleUpdateEntities(updated);
  };

  // Recommended architecture pattern according to the business & technical parameters
  const recommendedArch = useMemo<ArchitecturePattern>(() => {
    const directiveLower = (activeSession.description || activeSession.name || '').toLowerCase();
    const isKafka =
      activeSession.parameters.messaging === 'KAFKA' ||
      directiveLower.includes('kafka') ||
      directiveLower.includes('evento') ||
      directiveLower.includes('stream') ||
      directiveLower.includes('p2p');
    if (isKafka) return 'event-driven';
    if (
      activeSession.parameters.requirementsSize === 'HIGH' ||
      activeSession.parameters.requirementsSize === 'ENTERPRISE' ||
      directiveLower.includes('ddd') ||
      directiveLower.includes('agregado')
    ) {
      return 'hexagonal-ddd';
    }
    if (
      activeSession.parameters.requirementsSize === 'LOW' &&
      (activeSession.parameters.expectedQps === '100' || !activeSession.parameters.expectedQps)
    ) {
      return 'layered';
    }
    return 'hexagonal';
  }, [
    activeSession.parameters.messaging,
    activeSession.parameters.requirementsSize,
    activeSession.parameters.expectedQps,
    activeSession.description,
    activeSession.name,
  ]);

  // AI Recommendations per stage in Arquitectura & Modelos
  const [aiRecommendations, setAiRecommendations] = useState<{
    architecture?: { agent: string; summary: string };
    domainModels?: { agent: string; summary: string };
  }>({});

  useEffect(() => {
    const archLabels: Record<ArchitecturePattern, string> = {
      hexagonal: 'Hexagonal (Puertos & Adaptadores)',
      layered: 'Layered (4 Capas Clásicas)',
      'hexagonal-ddd': 'Hexagonal + Domain-Driven Design',
      'event-driven': 'Event-Driven Reactive Messaging',
    };
    setAiRecommendations((prev) => ({
      architecture: prev.architecture || {
        agent: 'architecture_agent',
        summary: `Patrón sugerido: ${archLabels[recommendedArch]} acorde a mensajería ${activeSession.parameters.messaging} y alcance ${activeSession.parameters.requirementsSize}`,
      },
      domainModels: prev.domainModels || {
        agent: 'panache_domain_modeler',
        summary: `Modeladas ${entities.length} entidades Panache JPA fuertemente tipadas`,
      },
    }));
  }, [
    recommendedArch,
    activeSession.parameters.messaging,
    activeSession.parameters.requirementsSize,
    entities.length,
  ]);

  // HITL Refinement Modal State
  const [refineTarget, setRefineTarget] = useState<'architecture' | 'domainModels' | null>(null);
  const [refineInstructions, setRefineInstructions] = useState('');
  const [isRefiningWithLlm, setIsRefiningWithLlm] = useState(false);
  const [refinementStatusLog, setRefinementStatusLog] = useState<string | null>(null);

  const handleRefineWithLlm = async () => {
    if (!refineTarget || !refineInstructions.trim()) return;
    setIsRefiningWithLlm(true);
    const agentName = refineTarget === 'architecture' ? 'architecture_agent' : 'panache_domain_modeler';
    setRefinementStatusLog(
      `[${agentName}] Refinando con instrucciones: "${refineInstructions.trim().slice(0, 60)}..."`
    );

    try {
      if (refineTarget === 'architecture') {
        const currentContext = {
          service_name: activeSession.name,
          current_architecture: selectedArch,
          recommended_architecture: recommendedArch,
          database: activeSession.parameters.database,
          messaging: activeSession.parameters.messaging,
          requirements_size: activeSession.parameters.requirementsSize,
          expected_qps: activeSession.parameters.expectedQps,
        };

        const draft = await draftSpec(
          {
            directive: activeSession.description || activeSession.name,
            service_name: activeSession.name,
            refinement_instructions: `Ajuste arquitectónico: ${refineInstructions.trim()}`,
            current_context: currentContext,
            llm_config: {
              provider,
              model,
              api_key: llmApiKey || undefined,
              endpoint:
                provider === 'local' ? (endpoint || 'http://127.0.0.1:8080') : (endpoint || undefined),
            },
          },
          apiKey,
          baseUrl,
          llmApiKey || undefined
        );

        const lowerInstr = refineInstructions.toLowerCase();
        let targetArch: ArchitecturePattern = selectedArch;
        if (lowerInstr.includes('layered') || lowerInstr.includes('capas') || lowerInstr.includes('clasic')) {
          targetArch = 'layered';
        } else if (
          lowerInstr.includes('ddd') ||
          lowerInstr.includes('agregado') ||
          lowerInstr.includes('hexagonal ddd') ||
          lowerInstr.includes('hexagonal-ddd')
        ) {
          targetArch = 'hexagonal-ddd';
        } else if (
          lowerInstr.includes('event') ||
          lowerInstr.includes('kafka') ||
          lowerInstr.includes('reactiv') ||
          lowerInstr.includes('stream')
        ) {
          targetArch = 'event-driven';
        } else if (lowerInstr.includes('hexagonal') || lowerInstr.includes('puertos')) {
          targetArch = 'hexagonal';
        } else if (draft.technical_matrix?.messaging === 'KAFKA') {
          targetArch = 'event-driven';
        }

        handleSelectArchitecture(targetArch);
        setAiRecommendations((prev) => ({
          ...prev,
          architecture: {
            agent: 'architecture_agent',
            summary: `Arquitectura actualizada a ${targetArch.toUpperCase()} según: "${refineInstructions.trim().slice(0, 45)}"`,
          },
        }));
        setRefinementStatusLog(`✓ Arquitectura actualizada a ${targetArch.toUpperCase()}`);
      } else if (refineTarget === 'domainModels') {
        const currentContext = {
          service_name: activeSession.name,
          database: activeSession.parameters.database,
          entities: entities.map((e) => ({
            name: e.name,
            tableName: e.tableName,
            fields: e.fields.map((f) => ({
              name: f.name,
              type: f.type,
              primaryKey: f.primaryKey,
              nullable: f.nullable,
              validationRules: f.validationRules,
            })),
          })),
        };

        const draft = await draftSpec(
          {
            directive: activeSession.description || activeSession.name,
            service_name: activeSession.name,
            refinement_instructions: `Refinamiento de entidades Panache JPA: ${refineInstructions.trim()}`,
            current_context: currentContext,
            llm_config: {
              provider,
              model,
              api_key: llmApiKey || undefined,
              endpoint:
                provider === 'local' ? (endpoint || 'http://127.0.0.1:8080') : (endpoint || undefined),
            },
          },
          apiKey,
          baseUrl,
          llmApiKey || undefined
        );

        if (draft.domain_models && draft.domain_models.length > 0) {
          const refinedEntities: DomainEntity[] = draft.domain_models.map((dm) => ({
            name: dm.name,
            tableName: dm.table_name || dm.name.toLowerCase() + 's',
            description: `Entidad Panache ${dm.name} refinada con Agente`,
            fields: dm.fields.map((f, idx) => ({
              name: f.name,
              type: (f.type as any) || 'String',
              primaryKey: idx === 0 || f.name.toLowerCase() === 'id',
              nullable: f.nullable !== false,
              validationRules: f.constraints || [],
            })),
          }));
          handleUpdateEntities(refinedEntities);
          setSelectedEntityIdx(0);
          setAiRecommendations((prev) => ({
            ...prev,
            domainModels: {
              agent: 'panache_domain_modeler',
              summary: `Modeladas ${refinedEntities.length} entidades Panache con Agente (${refinedEntities.map((e) => e.name).join(', ')})`,
            },
          }));
          setRefinementStatusLog(`✓ Entidades Panache actualizadas (${refinedEntities.length} entidades)`);
        }
      }

      setRefineTarget(null);
      setRefineInstructions('');
    } catch (err: any) {
      setRefinementStatusLog(`Error en refinamiento: ${err.message || 'Error desconocido'}`);
    } finally {
      setIsRefiningWithLlm(false);
    }
  };

  // Compile full SpecKit Blueprint for execution
  const compiledBlueprint = useMemo(() => {
    const cleanServiceName =
      activeSession.name.trim().toLowerCase().replace(/[^a-z0-9-]/g, '-') || 'microservice';
    const pascalName = cleanServiceName
      .split(/[-_]/)
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
      .join('');

    return {
      name: pascalName,
      serviceName: cleanServiceName,
      packageName: (activeSession.blueprint as any)?.packageName || 'com.tcs.service',
      framework: 'quarkus',
      version: '3.15.1',
      javaVersion: 21,
      buildTool: activeSession.parameters.buildTool || 'MAVEN',
      databaseEngine: activeSession.parameters.database,
      messagingSystem: activeSession.parameters.messaging,
      requirementsSize: activeSession.parameters.requirementsSize,
      expectedQps: activeSession.parameters.expectedQps,
      dataConsistency: activeSession.parameters.dataConsistency,
      architecture: selectedArch,
      extensions: (activeSession.blueprint as any)?.extensions || [
        'quarkus-rest',
        'quarkus-rest-jackson',
        'quarkus-hibernate-orm',
        'quarkus-hibernate-validator',
      ],
      naturalLanguagePrompt: activeSession.description,
      userStories: activeSession.stories,
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
      workspaceDir:
        activeSession.parameters.workspaceDir || `/tmp/agentia-workspace/${cleanServiceName}`,
    };
  }, [activeSession, entities, selectedArch, provider, model, endpoint, llmApiKey]);

  // Primary Execution Action: Approve & Generate Microservice via LangGraph
  const handleApproveAndGenerate = async () => {
    setIsTelemetryDrawerOpen(true);
    await executeLangGraph(activeSession.id, compiledBlueprint || undefined);
  };

  // Generate DDL SQL dynamically
  const generateSchemaSql = () => {
    const db = activeSession.parameters.database;
    const lines: string[] = [
      `-- ========================================================`,
      `-- AgentIA v2 Generated DDL Schema for Quarkus 3.x`,
      `-- Database Engine: ${db}`,
      `-- Microservice: ${activeSession.name}`,
      `-- ========================================================`,
      ``,
    ];

    entities.forEach((entity) => {
      lines.push(`CREATE TABLE IF NOT EXISTS ${entity.tableName} (`);
      const fieldDefs = entity.fields.map((f) => {
        let sqlType = 'VARCHAR(255)';
        if (f.primaryKey)
          sqlType = db === 'POSTGRESQL' ? 'BIGSERIAL PRIMARY KEY' : 'BIGINT PRIMARY KEY AUTO_INCREMENT';
        else if (f.type === 'Long') sqlType = 'BIGINT';
        else if (f.type === 'Integer') sqlType = 'INTEGER';
        else if (f.type === 'BigDecimal') sqlType = 'NUMERIC(12, 2)';
        else if (f.type === 'Instant') sqlType = 'TIMESTAMP WITH TIME ZONE';
        else if (f.type === 'Boolean') sqlType = 'BOOLEAN';

        const nullableStr = f.nullable === false ? ' NOT NULL' : '';
        return `    ${f.name.replace(/([A-Z])/g, '_$1').toLowerCase()} ${sqlType}${nullableStr}`;
      });
      lines.push(fieldDefs.join(',\n'));
      lines.push(`);\n`);
    });

    return lines.join('\n');
  };

  const handleCopySql = () => {
    navigator.clipboard.writeText(generateSchemaSql());
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  const contracts = activeSession.contracts?.length
    ? activeSession.contracts
    : [
        {
          endpoint: `/api/${activeSession.name.replace(/-service$/, '')}`,
          method: 'GET',
          description: `Listar elementos de ${activeSession.name}`,
          statusCode: 200,
        },
        {
          endpoint: `/api/${activeSession.name.replace(/-service$/, '')}`,
          method: 'POST',
          description: `Crear nuevo registro en ${activeSession.name}`,
          statusCode: 201,
        },
      ];

  return (
    <div className="space-y-6">
      {/* Top Banner: Architecture & Generation Hero */}
      <div className="bg-gradient-to-r from-blue-950 via-slate-900 to-slate-950 rounded-2xl p-6 text-white border border-blue-900/60 shadow-xl relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-400/30">
                <Layers className="w-3.5 h-3.5" />
                <span>2. Arquitectura & Modelos</span>
              </span>
              <span className="font-mono text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                {activeSession.name}
              </span>
            </div>
            <h2 className="text-2xl font-extrabold tracking-tight text-white">
              Arquitectura Hexagonal & Modelos de Dominio
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Audite las fronteras de puertos y adaptadores, configure las entidades Panache JPA con sus
              anotaciones Bean Validation y apruebe la generación del microservicio hacia el orquestador LangGraph.
            </p>
          </div>

          {/* Primary Action Buttons */}
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={() => setActiveTab(0)}
              className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-all cursor-pointer"
            >
              <span>← Volver a Especificación</span>
            </button>

            <button
              type="button"
              onClick={() => void handleApproveAndGenerate()}
              disabled={isExecuting}
              className="flex items-center gap-2.5 px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 hover:from-blue-500 hover:to-indigo-500 border border-blue-400/40 shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50 cursor-pointer"
            >
              {isExecuting ? (
                <>
                  <Activity className="w-4 h-4 animate-spin" />
                  <span>Ejecutando en LangGraph...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>Aprobar y Generar Microservicio 🚀</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* UPSTREAM CODER GRAPH STATUS TRACKER                                       */}
      {/* ========================================================================= */}
      <CoderGraphTracker
        architecture={selectedArch}
        isGenerating={isExecuting}
        isCompleted={activeSession.status === 'COMPLETED' || activeSession.status === 'SUCCESS'}
        serviceName={activeSession.name}
        entitiesCount={entities.length}
        endpointsCount={contracts.length}
        storiesCount={activeSession.stories?.length || 0}
        activeEntityName={currentEntity?.name || 'Order'}
      />

      {/* Status Log Banner */}
      {refinementStatusLog && (
        <div className="p-3.5 rounded-xl bg-indigo-950/50 border border-indigo-700/80 text-xs text-indigo-200 flex items-center justify-between gap-3 animate-in fade-in duration-200">
          <div className="flex items-center gap-2 font-mono">
            <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
            <span>{refinementStatusLog}</span>
          </div>
          <button
            type="button"
            onClick={() => setRefinementStatusLog(null)}
            className="text-indigo-400 hover:text-indigo-200 p-1 rounded cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* CARD 1: FRONTERAS HEXAGONALES & ENDPOINTS REST                             */}
      {/* ========================================================================= */}
      <Card
        title={
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-400" />
            <span>Fronteras Hexagonales & Endpoints REST</span>
            {aiRecommendations.architecture && (
              <span className="ml-2 inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                <Bot className="w-3.5 h-3.5 text-indigo-400" />
                <span>Recomendación del Agente ({aiRecommendations.architecture.agent})</span>
              </span>
            )}
          </div>
        }
        subtitle={`Topología de componentes, puertos y separación de capas • Estilo activo: ${
          selectedArch === 'layered'
            ? 'Layered (4 Capas Clásicas)'
            : selectedArch === 'hexagonal-ddd'
            ? 'Hexagonal + DDD'
            : selectedArch === 'event-driven'
            ? 'Event-Driven (Reactivo)'
            : 'Hexagonal (Puertos & Adaptadores)'
        }`}
        action={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setRefineTarget('architecture');
                setRefineInstructions('');
              }}
              disabled={isRefiningWithLlm}
              className="flex items-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-semibold text-indigo-300 bg-indigo-950/60 border border-indigo-800 hover:bg-indigo-900/60 transition-colors disabled:opacity-50 cursor-pointer"
              title="Abre el asistente para dar indicaciones al Agente y refinar el patrón arquitectónico"
            >
              <BotMessageSquare className="w-3.5 h-3.5 text-indigo-400" />
              <span>Refinar con Agente</span>
            </button>
            <button
              type="button"
              onClick={() => setArchTabMode('diagram')}
              className={`py-1.5 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                archTabMode === 'diagram'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Diagrama de Capas
            </button>
            <button
              type="button"
              onClick={() => setArchTabMode('contracts')}
              className={`py-1.5 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                archTabMode === 'contracts'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Contratos REST ({contracts.length})
            </button>
          </div>
        }
      >
        {archTabMode === 'diagram' ? (
          <div className="space-y-6">
            {/* Architectural Pattern Selector (Parity with Legacy v1 & Multi-pattern support) */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                    <Workflow className="w-4 h-4 text-blue-400" />
                    <span>Patrón Arquitectónico del Microservicio (Quarkus 3.x)</span>
                  </h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Seleccione el estilo de estructuración de paquetes, puertos y separación de responsabilidades para los agentes Coder
                  </p>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
                  Estilo Activo: {selectedArch.toUpperCase()}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                {/* Option 1: Hexagonal */}
                <button
                  type="button"
                  onClick={() => handleSelectArchitecture('hexagonal')}
                  className={`p-3 rounded-xl text-left border transition-all cursor-pointer ${
                    selectedArch === 'hexagonal'
                      ? 'bg-blue-950/50 border-blue-500 shadow-md shadow-blue-500/10 ring-1 ring-blue-500'
                      : recommendedArch === 'hexagonal'
                      ? 'bg-slate-900/80 border-indigo-500/40 hover:border-indigo-400 text-slate-300'
                      : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-white flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-blue-400" />
                      <span>Hexagonal</span>
                      {recommendedArch === 'hexagonal' && (
                        <span title="Sugerencia del Agente LLM para este caso" className="inline-flex items-center">
                          <Bot className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                        </span>
                      )}
                    </span>
                    <div className="flex items-center gap-1">
                      {recommendedArch === 'hexagonal' && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 flex items-center gap-1 font-sans font-semibold shadow-xs" title="Sugerencia del Agente LLM para este caso">
                          <Bot className="w-3 h-3 text-amber-400 shrink-0" />
                          <span>Sugerido</span>
                        </span>
                      )}
                      {selectedArch === 'hexagonal' && <Check className="w-3.5 h-3.5 text-blue-400" />}
                    </div>
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-2">
                    Puertos & Adaptadores. Desacopla el núcleo de dominio de HTTP y persistencia.
                  </p>
                </button>

                {/* Option 2: Layered (4 Capas) */}
                <button
                  type="button"
                  onClick={() => handleSelectArchitecture('layered')}
                  className={`p-3 rounded-xl text-left border transition-all cursor-pointer ${
                    selectedArch === 'layered'
                      ? 'bg-blue-950/50 border-blue-500 shadow-md shadow-blue-500/10 ring-1 ring-blue-500'
                      : recommendedArch === 'layered'
                      ? 'bg-slate-900/80 border-indigo-500/40 hover:border-indigo-400 text-slate-300'
                      : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-white flex items-center gap-1.5">
                      <Boxes className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Layered (4 Capas)</span>
                      {recommendedArch === 'layered' && (
                        <span title="Sugerencia del Agente LLM para este caso" className="inline-flex items-center">
                          <Bot className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                        </span>
                      )}
                    </span>
                    <div className="flex items-center gap-1">
                      {recommendedArch === 'layered' && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 flex items-center gap-1 font-sans font-semibold shadow-xs" title="Sugerencia del Agente LLM para este caso">
                          <Bot className="w-3 h-3 text-amber-400 shrink-0" />
                          <span>Sugerido</span>
                        </span>
                      )}
                      {selectedArch === 'layered' && <Check className="w-3.5 h-3.5 text-blue-400" />}
                    </div>
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-2">
                    Controller ➔ Service ➔ Repository ➔ Model. Clásico Quarkus empresarial.
                  </p>
                </button>

                {/* Option 3: Hexagonal + DDD */}
                <button
                  type="button"
                  onClick={() => handleSelectArchitecture('hexagonal-ddd')}
                  className={`p-3 rounded-xl text-left border transition-all cursor-pointer ${
                    selectedArch === 'hexagonal-ddd'
                      ? 'bg-blue-950/50 border-blue-500 shadow-md shadow-blue-500/10 ring-1 ring-blue-500'
                      : recommendedArch === 'hexagonal-ddd'
                      ? 'bg-slate-900/80 border-indigo-500/40 hover:border-indigo-400 text-slate-300'
                      : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-white flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                      <span>Hexagonal + DDD</span>
                      {recommendedArch === 'hexagonal-ddd' && (
                        <span title="Sugerencia del Agente LLM para este caso" className="inline-flex items-center">
                          <Bot className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                        </span>
                      )}
                    </span>
                    <div className="flex items-center gap-1">
                      {recommendedArch === 'hexagonal-ddd' && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 flex items-center gap-1 font-sans font-semibold shadow-xs" title="Sugerencia del Agente LLM para este caso">
                          <Bot className="w-3 h-3 text-amber-400 shrink-0" />
                          <span>Sugerido</span>
                        </span>
                      )}
                      {selectedArch === 'hexagonal-ddd' && <Check className="w-3.5 h-3.5 text-blue-400" />}
                    </div>
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-2">
                    Agregados ricos, Value Objects, Domain Events y separación en bounded contexts.
                  </p>
                </button>

                {/* Option 4: Event-Driven */}
                <button
                  type="button"
                  onClick={() => handleSelectArchitecture('event-driven')}
                  className={`p-3 rounded-xl text-left border transition-all cursor-pointer ${
                    selectedArch === 'event-driven'
                      ? 'bg-blue-950/50 border-blue-500 shadow-md shadow-blue-500/10 ring-1 ring-blue-500'
                      : recommendedArch === 'event-driven'
                      ? 'bg-slate-900/80 border-indigo-500/40 hover:border-indigo-400 text-slate-300'
                      : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-white flex items-center gap-1.5">
                      <Radio className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Event-Driven</span>
                      {recommendedArch === 'event-driven' && (
                        <span title="Sugerencia del Agente LLM para este caso" className="inline-flex items-center">
                          <Bot className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                        </span>
                      )}
                    </span>
                    <div className="flex items-center gap-1">
                      {recommendedArch === 'event-driven' && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 flex items-center gap-1 font-sans font-semibold shadow-xs" title="Sugerencia del Agente LLM para este caso">
                          <Bot className="w-3 h-3 text-amber-400 shrink-0" />
                          <span>Sugerido</span>
                        </span>
                      )}
                      {selectedArch === 'event-driven' && <Check className="w-3.5 h-3.5 text-blue-400" />}
                    </div>
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-2">
                    SmallRye Reactive Messaging, canales Kafka, pipelines Mutiny y estado desacoplado.
                  </p>
                </button>
              </div>
            </div>

            {/* Dynamic 4-Tier Topology Cards based on selectedArch */}
            {selectedArch === 'layered' ? (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* 1. Capa Controlador */}
                <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs uppercase tracking-wider">
                    <Globe className="w-4 h-4" />
                    <span>1. Capa Controlador (REST)</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Recursos RESTEasy Reactive (@Path) que exponen endpoints HTTP con serialización Jackson y validación Bean (@Valid).
                  </p>
                  <div className="pt-2 border-t border-emerald-900/40 text-[11px] font-mono text-emerald-300">
                    {currentEntity?.name || 'Order'}Resource.java
                  </div>
                </div>

                {/* 2. Capa Servicio */}
                <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-indigo-400 font-bold text-xs uppercase tracking-wider">
                    <Layers className="w-4 h-4" />
                    <span>2. Capa Servicio (Lógica CDI)</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Lógica de negocio @ApplicationScoped y transacciones atómicas @Transactional que validan reglas BDD.
                  </p>
                  <div className="pt-2 border-t border-indigo-900/40 text-[11px] font-mono text-indigo-300">
                    {currentEntity?.name || 'Order'}Service.java
                  </div>
                </div>

                {/* 3. Capa Repositorio */}
                <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-blue-400 font-bold text-xs uppercase tracking-wider">
                    <Database className="w-4 h-4" />
                    <span>3. Capa Repositorio (Panache)</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Acceso a datos con PanacheRepositoryBase, consultas HQL tipadas y caché Hibernate de segundo nivel.
                  </p>
                  <div className="pt-2 border-t border-blue-900/40 text-[11px] font-mono text-blue-300">
                    {currentEntity?.name || 'Order'}Repository.java
                  </div>
                </div>

                {/* 4. Capa Modelo */}
                <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase tracking-wider">
                    <Boxes className="w-4 h-4" />
                    <span>4. Capa Modelo (Entidades JPA)</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Entidades @Entity Jakarta Persistence mapeadas a {activeSession.parameters.database} con anotaciones de validación.
                  </p>
                  <div className="pt-2 border-t border-amber-900/40 text-[11px] font-mono text-amber-300">
                    {entities.map((e) => e.name).join(', ')}
                  </div>
                </div>
              </div>
            ) : selectedArch === 'hexagonal-ddd' ? (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* 1. Inbound Adapters */}
                <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs uppercase tracking-wider">
                    <Globe className="w-4 h-4" />
                    <span>1. Inbound Adapters (REST)</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Adaptadores primarios de entrada HTTP que convierten DTOs externos en comandos del dominio DDD.
                  </p>
                  <div className="pt-2 border-t border-emerald-900/40 text-[11px] font-mono text-emerald-300">
                    @Path Primary Adapters
                  </div>
                </div>

                {/* 2. Application Services */}
                <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-indigo-400 font-bold text-xs uppercase tracking-wider">
                    <Layers className="w-4 h-4" />
                    <span>2. Application Services</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Coordinadores de casos de uso y despachadores de comandos que operan sobre los agregados de dominio.
                  </p>
                  <div className="pt-2 border-t border-indigo-900/40 text-[11px] font-mono text-indigo-300">
                    Command & Query Handlers
                  </div>
                </div>

                {/* 3. Agregados & DDD Core */}
                <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-blue-400 font-bold text-xs uppercase tracking-wider">
                    <Boxes className="w-4 h-4" />
                    <span>3. Agregados & DDD Core</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Aggregate Roots puros, Value Objects y Domain Events invariantes sin dependencias externas.
                  </p>
                  <div className="pt-2 border-t border-blue-900/40 text-[11px] font-mono text-blue-300">
                    {entities.map((e) => e.name).join(', ')} (Aggregates)
                  </div>
                </div>

                {/* 4. Outbound Infrastructure */}
                <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase tracking-wider">
                    <Database className="w-4 h-4" />
                    <span>4. Outbound Infrastructure</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Implementaciones de puertos secundarios para repositorios Panache JPA y publicadores de eventos Kafka.
                  </p>
                  <div className="pt-2 border-t border-amber-900/40 text-[11px] font-mono text-amber-300">
                    Secondary Persistence Ports
                  </div>
                </div>
              </div>
            ) : selectedArch === 'event-driven' ? (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* 1. Ingress Channels */}
                <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs uppercase tracking-wider">
                    <Radio className="w-4 h-4" />
                    <span>1. Canales Ingress (Kafka)</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Conectores reactivos SmallRye @Incoming(&quot;channel&quot;) y consumidores HTTP asíncronos.
                  </p>
                  <div className="pt-2 border-t border-emerald-900/40 text-[11px] font-mono text-emerald-300">
                    SmallRye Reactive Ingress
                  </div>
                </div>

                {/* 2. Procesadores Reactivos */}
                <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-indigo-400 font-bold text-xs uppercase tracking-wider">
                    <Cpu className="w-4 h-4" />
                    <span>2. Procesadores Reactivos</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Pipelines de transformación no bloqueantes con Mutiny Uni y Multi para alta concurrencia.
                  </p>
                  <div className="pt-2 border-t border-indigo-900/40 text-[11px] font-mono text-indigo-300">
                    Mutiny Pipeline Processors
                  </div>
                </div>

                {/* 3. Estado & Entidades */}
                <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-blue-400 font-bold text-xs uppercase tracking-wider">
                    <Boxes className="w-4 h-4" />
                    <span>3. Estado & Entidades</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Persistencia reactiva Hibernate Reactive Panache con transacciones atómicas no bloqueantes.
                  </p>
                  <div className="pt-2 border-t border-blue-900/40 text-[11px] font-mono text-blue-300">
                    {entities.map((e) => e.name).join(', ')} (Reactive)
                  </div>
                </div>

                {/* 4. Canales Egress */}
                <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase tracking-wider">
                    <Radio className="w-4 h-4" />
                    <span>4. Canales Egress (Kafka)</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Publicación reactiva de eventos hacia topics de mensajería @Outgoing(&quot;channel&quot;).
                  </p>
                  <div className="pt-2 border-t border-amber-900/40 text-[11px] font-mono text-amber-300">
                    Kafka Reactive Emitters
                  </div>
                </div>
              </div>
            ) : (
              /* Default: Hexagonal (Puertos & Adaptadores) */
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* 1. Core Domain */}
                <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-blue-400 font-bold text-xs uppercase tracking-wider">
                    <Boxes className="w-4 h-4" />
                    <span>1. Core Dominio</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Entidades puras, agregados y reglas de negocio invariantes sin acoplamiento a frameworks.
                  </p>
                  <div className="pt-2 border-t border-blue-900/40 text-[11px] font-mono text-blue-300">
                    {entities.map((e) => e.name).join(', ')}
                  </div>
                </div>

                {/* 2. Application Services */}
                <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-indigo-400 font-bold text-xs uppercase tracking-wider">
                    <Layers className="w-4 h-4" />
                    <span>2. Casos de Uso</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Servicios transaccionales Panache que orquestan el flujo de datos y validan BDD.
                  </p>
                  <div className="pt-2 border-t border-indigo-900/40 text-[11px] font-mono text-indigo-300">
                    @ApplicationScoped Services
                  </div>
                </div>

                {/* 3. Inbound Ports */}
                <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs uppercase tracking-wider">
                    <Globe className="w-4 h-4" />
                    <span>3. Inbound Adapters</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Endpoints RESTEasy Reactive con serialización Jackson y validaciones Bean (@Valid).
                  </p>
                  <div className="pt-2 border-t border-emerald-900/40 text-[11px] font-mono text-emerald-300">
                    @Path Resources (REST)
                  </div>
                </div>

                {/* 4. Outbound Ports */}
                <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-900/60 space-y-2">
                  <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase tracking-wider">
                    {activeSession.parameters.messaging === 'KAFKA' ? <Radio className="w-4 h-4" /> : <Database className="w-4 h-4" />}
                    <span>4. Outbound Adapters</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Persistencia JPA Hibernate Panache y productores SmallRye Reactive Messaging.
                  </p>
                  <div className="pt-2 border-t border-amber-900/40 text-[11px] font-mono text-amber-300">
                    {activeSession.parameters.database} • {activeSession.parameters.messaging}
                  </div>
                </div>
              </div>
            )}

            {/* Visual Directional Flow Pipeline */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs space-y-2 font-mono">
              <div className="flex items-center justify-between text-slate-400 text-[11px]">
                {selectedArch === 'layered' ? (
                  <>
                    <span className="text-emerald-400">Controller (@Path / REST)</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-indigo-300">Service (@ApplicationScoped)</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-blue-300">Repository (Panache ORM)</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-amber-300">Model (@Entity)</span>
                  </>
                ) : selectedArch === 'hexagonal-ddd' ? (
                  <>
                    <span className="text-emerald-400">Inbound HTTP Adapters</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-indigo-300">Application Command Handler</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-blue-300">Aggregate Roots (DDD)</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-amber-300">Infrastructure Ports</span>
                  </>
                ) : selectedArch === 'event-driven' ? (
                  <>
                    <span className="text-emerald-400">Kafka / HTTP Ingress</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-indigo-300">Mutiny Stream Pipeline</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-blue-300">Reactive State Panache</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-amber-300">Kafka Outgoing Topic</span>
                  </>
                ) : (
                  <>
                    <span className="text-emerald-400">RESTEasy Reactive (HTTP / JSON)</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-indigo-300">Domain Use Cases & Ports</span>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-amber-300">Hibernate Panache & Kafka Channels</span>
                  </>
                )}
              </div>
            </div>
          </div>
        ) : (
          /* REST Contracts Table */
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Método</th>
                  <th className="py-2.5 px-3">Ruta</th>
                  <th className="py-2.5 px-3 font-sans">Descripción</th>
                  <th className="py-2.5 px-3">Estado HTTP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {contracts.map((c, idx) => (
                  <tr key={idx} className="hover:bg-slate-900/40 transition-colors">
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        c.method === 'GET' ? 'bg-blue-950 text-blue-300 border border-blue-800' :
                        c.method === 'POST' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' :
                        'bg-amber-950 text-amber-300 border border-amber-800'
                      }`}>
                        {c.method}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-200 font-semibold">{c.endpoint}</td>
                    <td className="py-2.5 px-3 text-slate-400 font-sans">{c.description}</td>
                    <td className="py-2.5 px-3 text-emerald-400">{c.statusCode} OK</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ========================================================================= */}
      {/* CARD 2: MODELOS PANACHE JPA & DDL SQL                                     */}
      {/* ========================================================================= */}
      <Card
        title={
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-blue-400" />
            <span>Modelos Panache JPA & DDL SQL</span>
            {aiRecommendations.domainModels && (
              <span className="ml-2 inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                <Bot className="w-3.5 h-3.5 text-indigo-400" />
                <span>Recomendación del Agente ({aiRecommendations.domainModels.agent})</span>
              </span>
            )}
          </div>
        }
        subtitle={`Entidades de persistencia activas y esquema relacional DDL para ${activeSession.parameters.database}`}
        action={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setRefineTarget('domainModels');
                setRefineInstructions('');
              }}
              disabled={isRefiningWithLlm}
              className="flex items-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-semibold text-indigo-300 bg-indigo-950/60 border border-indigo-800 hover:bg-indigo-900/60 transition-colors disabled:opacity-50 cursor-pointer"
              title="Abre el asistente para dar indicaciones al Agente y refinar las entidades y atributos Panache JPA"
            >
              <BotMessageSquare className="w-3.5 h-3.5 text-indigo-400" />
              <span>Refinar con Agente</span>
            </button>
            <button
              type="button"
              onClick={() => setModelTabMode('entities')}
              className={`py-1.5 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                modelTabMode === 'entities'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Modelador de Entidades Panache JPA ({entities.length})
            </button>
            <button
              type="button"
              onClick={() => setModelTabMode('sql')}
              className={`py-1.5 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                modelTabMode === 'sql'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Vista Previa DDL SQL
            </button>
          </div>
        }
      >
        {modelTabMode === 'entities' ? (
          <div className="space-y-4">
            {/* Entity Tab Selector & Add Entity Button */}
            <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
              <div className="flex flex-wrap items-center gap-2">
                {entities.map((ent, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setSelectedEntityIdx(idx)}
                    className={`flex items-center gap-2 py-1.5 px-3.5 rounded-xl text-xs font-mono transition-all cursor-pointer ${
                      safeEntityIdx === idx
                        ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-500/20'
                        : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                    }`}
                  >
                    <Table className="w-3.5 h-3.5" />
                    <span>{ent.name}</span>
                    <span className="text-[10px] opacity-70 font-sans">({ent.fields.length} campos)</span>
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={handleAddEntity}
                className="flex items-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-semibold text-blue-300 bg-blue-950/60 border border-blue-800 hover:bg-blue-900/60 transition-colors cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Agregar Entidad</span>
              </button>
            </div>

            {/* Current Selected Entity Modeler */}
            {currentEntity && (
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 flex-1">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                        Nombre de Entidad Java (PanacheEntityBase)
                      </label>
                      <input
                        type="text"
                        value={currentEntity.name}
                        onChange={(e) =>
                          handleUpdateEntityMeta(safeEntityIdx, { name: e.target.value })
                        }
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                        Tabla en Base de Datos ({activeSession.parameters.database})
                      </label>
                      <input
                        type="text"
                        value={currentEntity.tableName}
                        onChange={(e) =>
                          handleUpdateEntityMeta(safeEntityIdx, { tableName: e.target.value })
                        }
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono"
                      />
                    </div>
                  </div>

                  {entities.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleDeleteEntity(safeEntityIdx)}
                      className="self-end sm:self-center flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-rose-300 bg-rose-950/40 border border-rose-800 hover:bg-rose-900/50 transition-colors cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Eliminar Entidad</span>
                    </button>
                  )}
                </div>

                {/* Fields Table */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-300">
                      Campos & Anotaciones Bean Validation:
                    </span>
                    <button
                      type="button"
                      onClick={() => handleAddField(safeEntityIdx)}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-semibold text-blue-300 bg-blue-950/40 border border-blue-800 hover:bg-blue-900/50 cursor-pointer"
                    >
                      <Plus className="w-3 h-3" />
                      <span>Agregar Campo</span>
                    </button>
                  </div>

                  <div className="overflow-x-auto rounded-lg border border-slate-800">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-slate-900 text-slate-400 text-[11px] uppercase tracking-wider">
                        <tr>
                          <th className="py-2 px-3">Campo</th>
                          <th className="py-2 px-3">Tipo Java</th>
                          <th className="py-2 px-3 text-center">PK</th>
                          <th className="py-2 px-3 text-center">Nullable</th>
                          <th className="py-2 px-3">Validaciones (Anotaciones)</th>
                          <th className="py-2 px-3 text-right">Acción</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/80">
                        {currentEntity.fields.map((f, fIdx) => (
                          <tr key={fIdx} className="hover:bg-slate-900/40 transition-colors">
                            <td className="py-2 px-3">
                              <input
                                type="text"
                                value={f.name}
                                onChange={(e) =>
                                  handleUpdateField(safeEntityIdx, fIdx, { name: e.target.value })
                                }
                                className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-white text-xs w-36 font-mono"
                              />
                            </td>
                            <td className="py-2 px-3">
                              <select
                                value={f.type}
                                onChange={(e) =>
                                  handleUpdateField(safeEntityIdx, fIdx, { type: e.target.value })
                                }
                                className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-blue-300 text-xs font-mono"
                              >
                                <option value="Long">Long</option>
                                <option value="UUID">UUID</option>
                                <option value="String">String</option>
                                <option value="BigDecimal">BigDecimal</option>
                                <option value="Instant">Instant</option>
                                <option value="Integer">Integer</option>
                                <option value="Boolean">Boolean</option>
                              </select>
                            </td>
                            <td className="py-2 px-3 text-center">
                              <input
                                type="checkbox"
                                checked={!!f.primaryKey}
                                onChange={(e) =>
                                  handleUpdateField(safeEntityIdx, fIdx, {
                                    primaryKey: e.target.checked,
                                    nullable: !e.target.checked,
                                  })
                                }
                                className="rounded border-slate-700 bg-slate-900 text-blue-600 focus:ring-0"
                              />
                            </td>
                            <td className="py-2 px-3 text-center">
                              <input
                                type="checkbox"
                                checked={f.nullable !== false}
                                disabled={!!f.primaryKey}
                                onChange={(e) =>
                                  handleUpdateField(safeEntityIdx, fIdx, {
                                    nullable: e.target.checked,
                                  })
                                }
                                className="rounded border-slate-700 bg-slate-900 text-blue-600 focus:ring-0"
                              />
                            </td>
                            <td className="py-2 px-3">
                              <input
                                type="text"
                                value={(f.validationRules || []).join(', ')}
                                onChange={(e) =>
                                  handleUpdateField(safeEntityIdx, fIdx, {
                                    validationRules: e.target.value
                                      .split(',')
                                      .map((s) => s.trim())
                                      .filter(Boolean),
                                  })
                                }
                                placeholder="@NotNull, @Positive"
                                className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-emerald-300 text-xs w-full font-mono placeholder-slate-600"
                              />
                            </td>
                            <td className="py-2 px-3 text-right">
                              {currentEntity.fields.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => handleDeleteField(safeEntityIdx, fIdx)}
                                  className="p-1 text-slate-500 hover:text-rose-400 rounded cursor-pointer"
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
            )}
          </div>
        ) : (
          /* DDL SQL Preview */
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-mono">
                Esquema DDL para motor {activeSession.parameters.database}
              </span>
              <button
                type="button"
                onClick={handleCopySql}
                className="flex items-center gap-1.5 py-1 px-2.5 rounded text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium cursor-pointer"
              >
                {copiedSql ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedSql ? 'Copiado' : 'Copiar DDL'}</span>
              </button>
            </div>
            <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-blue-300 overflow-x-auto leading-relaxed max-h-96">
              {generateSchemaSql()}
            </pre>
          </div>
        )}
      </Card>

      {/* ========================================================================= */}
      {/* BOTTOM STICKY ACTION BAR: APROBAR Y GENERAR MICROSERVICIO                 */}
      {/* ========================================================================= */}
      <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4 backdrop-blur-md">
        <div className="text-xs text-slate-400">
          ¿Modelos y arquitectura verificados? Al presionar <strong>Aprobar y Generar Microservicio</strong>, el contrato
          compilado se despacha a <code className="text-blue-300 font-mono">POST /v1/blueprint/run</code> y se abrirá el
          monitor de telemetría del orquestador LangGraph.
        </div>
        <button
          type="button"
          onClick={() => void handleApproveAndGenerate()}
          disabled={isExecuting}
          className="w-full sm:w-auto flex items-center justify-center gap-2.5 px-7 py-3 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 hover:from-blue-500 hover:to-indigo-500 shadow-xl shadow-blue-500/20 transition-all disabled:opacity-50 shrink-0 cursor-pointer"
        >
          {isExecuting ? (
            <>
              <Activity className="w-4 h-4 animate-spin" />
              <span>Ejecutando en LangGraph...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              <span>Aprobar y Generar Microservicio 🚀</span>
            </>
          )}
        </button>
      </div>

      {/* ========================================================================= */}
      {/* HITL REFINEMENT MODAL (ARCHITECTURE & DOMAIN MODELS ASSISTANT)             */}
      {/* ========================================================================= */}
      {refineTarget !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-indigo-500/40 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="p-2 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-400/30">
                  <BotMessageSquare className="w-5 h-5 text-indigo-400" />
                </span>
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>Asistente de Refinamiento del Agente</span>
                    <span className="text-[11px] font-mono font-normal px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                      {refineTarget === 'architecture' ? 'architecture_agent' : 'panache_domain_modeler'}
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400">
                    {refineTarget === 'architecture'
                      ? 'Re-evalúe el patrón arquitectónico, fronteras y puertos con indicaciones en lenguaje natural'
                      : 'Modifique o expanda las entidades Panache JPA, campos y validaciones con asistencia del Agente'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setRefineTarget(null);
                  setRefineInstructions('');
                }}
                disabled={isRefiningWithLlm}
                className="text-slate-400 hover:text-white p-1 rounded-lg cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Indicaciones para el Agente (Prompt de Refinamiento)
                </label>
                <textarea
                  rows={4}
                  value={refineInstructions}
                  onChange={(e) => setRefineInstructions(e.target.value)}
                  placeholder={
                    refineTarget === 'architecture'
                      ? 'Ej: Cambia la arquitectura a hexagonal-ddd porque el microservicio gestionará agregados complejos con eventos de dominio...'
                      : 'Ej: Agrega el campo status con Bean Validation @NotNull, agrega auditoría con updatedAt tipo Instant, y añade una entidad de Historial...'
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-white focus:outline-hidden focus:border-indigo-500 placeholder-slate-600 font-sans leading-relaxed"
                  autoFocus
                />
              </div>

              {/* Context Summary Preview */}
              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-[11px] space-y-1">
                <span className="text-slate-400 font-semibold block">Contexto actual transmitido al Agente:</span>
                <pre className="font-mono text-slate-300 text-[10px] overflow-x-auto max-h-28 p-2 rounded bg-slate-900/60 border border-slate-800/80">
                  {JSON.stringify(
                    refineTarget === 'architecture'
                      ? {
                          service_name: activeSession.name,
                          current_architecture: selectedArch,
                          database: activeSession.parameters.database,
                          messaging: activeSession.parameters.messaging,
                          requirements_size: activeSession.parameters.requirementsSize,
                        }
                      : {
                          service_name: activeSession.name,
                          database: activeSession.parameters.database,
                          entities_count: entities.length,
                          entity_names: entities.map((e) => e.name),
                        },
                    null,
                    2
                  )}
                </pre>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => {
                  setRefineTarget(null);
                  setRefineInstructions('');
                }}
                disabled={isRefiningWithLlm}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-all cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => void handleRefineWithLlm()}
                disabled={isRefiningWithLlm || !refineInstructions.trim()}
                className="flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 border border-indigo-400/40 shadow-lg shadow-indigo-500/20 transition-all disabled:opacity-50 cursor-pointer"
              >
                {isRefiningWithLlm ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Refinando con el Agente...</span>
                  </>
                ) : (
                  <>
                    <Bot className="w-3.5 h-3.5 text-amber-300" />
                    <span>Re-formular con el Agente ⚡</span>
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
