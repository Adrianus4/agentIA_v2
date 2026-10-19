import React, { useState } from 'react';
import { clsx } from 'clsx';
import {
  Boxes,
  Database,
  Cpu,
  Globe,
  ShieldCheck,
  CheckCircle2,
  Clock,
  ArrowRight,
  Sparkles,
  Layers,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import type { ArchitecturePattern } from '../../types/studio';

export type CoderStepId = 'entities' | 'services' | 'resources' | 'tests' | 'preflight';
export type CoderStepStatus = 'IDLE' | 'READY' | 'ACTIVE' | 'PASSED' | 'ERROR';

export interface CoderStepDefinition {
  id: CoderStepId;
  stepNumber: number;
  title: string;
  subLabel: string;
  defaultDesc: string;
  activeDesc: string;
  passedDesc: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const CODER_GRAPH_NODES: CoderStepDefinition[] = [
  {
    id: 'entities',
    stepNumber: 1,
    title: 'Modelos Panache JPA',
    subLabel: 'entity_generator',
    defaultDesc: 'Generación de entidades Jakarta @Entity y PanacheRepository',
    activeDesc: 'Sintetizando modelos Panache, campos y anotaciones JPA...',
    passedDesc: 'Entidades Panache generadas con Bean Validation (@NotNull, @Positive)',
    icon: Database,
  },
  {
    id: 'services',
    stepNumber: 2,
    title: 'Servicios CDI & Reglas BDD',
    subLabel: 'service_generator',
    defaultDesc: 'Lógica transaccional @ApplicationScoped y reglas de negocio',
    activeDesc: 'Sintetizando casos de uso transaccionales y validación BDD...',
    passedDesc: 'Servicios transaccionales CDI orquestados con el dominio',
    icon: Cpu,
  },
  {
    id: 'resources',
    stepNumber: 3,
    title: 'Recursos Quarkus REST',
    subLabel: 'resource_generator',
    defaultDesc: 'Endpoints @Path RESTEasy Reactive y Records DTO inmutables',
    activeDesc: 'Sintetizando controladores REST y contratos DTO...',
    passedDesc: 'Controladores HTTP no bloqueantes y serializadores Jackson',
    icon: Globe,
  },
  {
    id: 'tests',
    stepNumber: 4,
    title: 'Suites de Pruebas RestAssured',
    subLabel: 'test_generator',
    defaultDesc: 'Pruebas de integración @QuarkusTest y validación BDD',
    activeDesc: 'Sintetizando suites @QuarkusTest y aserciones Given/When/Then...',
    passedDesc: 'Suites de pruebas herméticas con rollback y validación de endpoints',
    icon: ShieldCheck,
  },
  {
    id: 'preflight',
    stepNumber: 5,
    title: 'Pre-Flight AST & Ensamblaje',
    subLabel: 'ast_preflight',
    defaultDesc: 'Validación sintáctica Java 21 previa a compilación Maven',
    activeDesc: 'Comprobando árbol de paquetes, imports y compilabilidad AST...',
    passedDesc: 'Código ensamblado y libre de ciclos para el verify hermético',
    icon: Sparkles,
  },
];

export interface CoderGraphTrackerProps {
  architecture?: ArchitecturePattern;
  isGenerating?: boolean;
  isCompleted?: boolean;
  serviceName?: string;
  entitiesCount?: number;
  endpointsCount?: number;
  storiesCount?: number;
  activeEntityName?: string;
  className?: string;
}

export const CoderGraphTracker: React.FC<CoderGraphTrackerProps> = ({
  architecture = 'hexagonal',
  isGenerating = false,
  isCompleted = false,
  serviceName = 'microservice',
  entitiesCount = 1,
  endpointsCount = 2,
  storiesCount = 1,
  activeEntityName = 'Order',
  className,
}) => {
  const [showCatalogDetails, setShowCatalogDetails] = useState(false);

  // Determine current node status
  const getNodeStatus = (stepIndex: number): CoderStepStatus => {
    if (isCompleted) return 'PASSED';
    if (isGenerating) {
      // While actively generating, pulse intermediate steps or pass initial ones
      if (stepIndex <= 2) return 'PASSED';
      if (stepIndex === 3) return 'ACTIVE';
      return 'READY';
    }
    // Pre-flight ready state
    return 'READY';
  };

  const getArchLabel = (arch: ArchitecturePattern): string => {
    switch (arch) {
      case 'layered':
        return 'Layered (4 Capas Clásicas)';
      case 'hexagonal-ddd':
        return 'Hexagonal + DDD';
      case 'event-driven':
        return 'Event-Driven (Reactivo)';
      case 'hexagonal':
      default:
        return 'Hexagonal (Puertos & Adaptadores)';
    }
  };

  return (
    <div
      role="region"
      aria-label="Grafo de Síntesis del Coder (Upstream)"
      className={clsx(
        'w-full bg-slate-900/90 rounded-2xl border border-slate-800 p-4 shadow-xl backdrop-blur-md space-y-4',
        className
      )}
    >
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Boxes className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                Grafo de Síntesis Coder & Topología de Código (Upstream B)
              </h3>
              {isGenerating ? (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30 animate-pulse">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
                  SINTETIZANDO CÓDIGO
                </span>
              ) : isCompleted ? (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <CheckCircle2 className="w-3 h-3" />
                  SÍNTESIS COMPLETADA
                </span>
              ) : (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                  <Clock className="w-3 h-3 text-slate-400" />
                  LISTO PARA SÍNTESIS
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Etapas de generación de agentes Coder previas a la verificación hermética Maven
            </p>
          </div>
        </div>

        {/* Badges / Metrics */}
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
          <span className="px-2.5 py-1 rounded-md bg-slate-950 border border-slate-800 text-indigo-300">
            🏛️ {getArchLabel(architecture)}
          </span>
          <span className="px-2.5 py-1 rounded-md bg-slate-950 border border-slate-800 text-slate-300">
            📦 {entitiesCount} {entitiesCount === 1 ? 'Entidad' : 'Entidades'}
          </span>
          <span className="px-2.5 py-1 rounded-md bg-slate-950 border border-slate-800 text-emerald-300">
            🌐 {endpointsCount} Endpoints
          </span>
          <span className="px-2.5 py-1 rounded-md bg-slate-950 border border-slate-800 text-amber-300">
            📝 {storiesCount} BDD
          </span>
          <button
            type="button"
            onClick={() => setShowCatalogDetails(!showCatalogDetails)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 transition-colors cursor-pointer"
          >
            <Layers className="w-3 h-3 text-blue-400" />
            <span>{showCatalogDetails ? 'Ocultar Componentes' : 'Ver Componentes'}</span>
            {showCatalogDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>
      </div>

      {/* 5-Step Horizontal Flow Nodes */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {CODER_GRAPH_NODES.map((node, index) => {
          const status = getNodeStatus(node.stepNumber);
          const isPassed = status === 'PASSED';
          const isActive = status === 'ACTIVE';
          const isReady = status === 'READY';
          const IconComponent = node.icon;

          return (
            <div
              key={node.id}
              className={clsx(
                'relative flex flex-col p-3 rounded-xl border transition-all duration-300',
                isActive && 'bg-blue-950/40 border-blue-500 shadow-lg shadow-blue-500/10 ring-1 ring-blue-500',
                isPassed && 'bg-emerald-950/20 border-emerald-500/40',
                isReady && 'bg-slate-950/60 border-slate-800 hover:border-slate-700',
                status === 'IDLE' && 'bg-slate-950/40 border-slate-800/60 opacity-60'
              )}
            >
              {/* Top row: step number + icon + status indicator */}
              <div className="flex items-center justify-between gap-1.5 mb-2">
                <div className="flex items-center gap-1.5">
                  <span
                    className={clsx(
                      'w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold font-mono',
                      isActive && 'bg-blue-500 text-white animate-pulse',
                      isPassed && 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40',
                      isReady && 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30',
                      status === 'IDLE' && 'bg-slate-800 text-slate-500'
                    )}
                  >
                    {node.stepNumber}
                  </span>
                  <div
                    className={clsx(
                      'p-1 rounded-md',
                      isActive && 'bg-blue-500/20 text-blue-400',
                      isPassed && 'bg-emerald-500/20 text-emerald-400',
                      isReady && 'bg-slate-800 text-slate-300',
                      status === 'IDLE' && 'text-slate-600'
                    )}
                  >
                    <IconComponent className="w-3.5 h-3.5" />
                  </div>
                </div>

                {/* Status badge pill */}
                {isPassed ? (
                  <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400">
                    <CheckCircle2 className="w-3 h-3" /> LISTO
                  </span>
                ) : isActive ? (
                  <span className="flex items-center gap-1 text-[10px] font-bold text-blue-400 animate-pulse">
                    GENERANDO...
                  </span>
                ) : isReady ? (
                  <span className="text-[10px] font-mono text-indigo-300 bg-indigo-950/60 px-1.5 py-0.5 rounded border border-indigo-800/50">
                    PLANIFICADO
                  </span>
                ) : (
                  <span className="text-[10px] text-slate-600 font-mono">EN ESPERA</span>
                )}
              </div>

              {/* Title & Generator Sublabel */}
              <h4 className="text-xs font-bold text-slate-200 line-clamp-1">{node.title}</h4>
              <span className="text-[10px] font-mono text-indigo-400/80 mb-1.5">{node.subLabel}</span>

              {/* Description */}
              <p className="text-[11px] leading-relaxed text-slate-400 flex-1">
                {isPassed ? node.passedDesc : isActive ? node.activeDesc : node.defaultDesc}
              </p>

              {/* Arrow Connector for larger screens */}
              {index < CODER_GRAPH_NODES.length - 1 && (
                <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-slate-600">
                  <ArrowRight className="w-3 h-3" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Collapsible Component Catalog Mapping Details */}
      {showCatalogDetails && (
        <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-3 text-xs animate-in fade-in duration-200">
          <div className="flex items-center justify-between">
            <span className="font-bold text-slate-300 uppercase tracking-wider text-[11px]">
              Topología y Componentes Proyectados para Generación ({getArchLabel(architecture)}):
            </span>
            <span className="font-mono text-[10px] text-slate-500">Quarkus 3.15.1 • Java 21</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-[11px]">
            {/* Layer 1 */}
            <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800/80 space-y-1">
              <span className="text-emerald-400 font-bold block">
                {architecture === 'layered' ? '1. Capa Controlador' : '1. Inbound Adapters'}
              </span>
              <p className="text-slate-400 text-[10px]">
                <code>{activeEntityName}Resource.java</code>
              </p>
              <div className="text-[10px] font-mono text-slate-500">
                @Path(&quot;/api/{serviceName.replace(/-service$/, '')}&quot;)
              </div>
            </div>

            {/* Layer 2 */}
            <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800/80 space-y-1">
              <span className="text-indigo-400 font-bold block">
                {architecture === 'layered' ? '2. Capa Servicio' : '2. Casos de Uso / Service'}
              </span>
              <p className="text-slate-400 text-[10px]">
                <code>{activeEntityName}Service.java</code>
              </p>
              <div className="text-[10px] font-mono text-slate-500">
                @ApplicationScoped • @Transactional
              </div>
            </div>

            {/* Layer 3 */}
            <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800/80 space-y-1">
              <span className="text-blue-400 font-bold block">
                {architecture === 'layered' ? '3. Capa Repositorio' : '3. Outbound Adapters'}
              </span>
              <p className="text-slate-400 text-[10px]">
                <code>{activeEntityName}Repository.java</code>
              </p>
              <div className="text-[10px] font-mono text-slate-500">
                PanacheRepositoryBase&lt;{activeEntityName}, Long&gt;
              </div>
            </div>

            {/* Layer 4 */}
            <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800/80 space-y-1">
              <span className="text-amber-400 font-bold block">
                {architecture === 'layered' ? '4. Capa Modelo' : '4. Dominio / Entidades'}
              </span>
              <p className="text-slate-400 text-[10px]">
                <code>{activeEntityName}.java</code>
              </p>
              <div className="text-[10px] font-mono text-slate-500">
                @Entity • PanacheEntityBase
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
