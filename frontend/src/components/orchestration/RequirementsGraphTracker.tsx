import React, { useState, useEffect } from 'react';
import { clsx } from 'clsx';
import {
  BrainCircuit,
  Sliders,
  FileText,
  Database,
  CheckCircle2,
  Clock,
  ArrowRight,
  Sparkles,
  AlertCircle,
  Check,
} from 'lucide-react';

export type RequirementsStepId = 'parse' | 'matrix' | 'bdd' | 'models' | 'contract';
export type RequirementsStepStatus = 'IDLE' | 'ACTIVE' | 'PASSED' | 'ERROR';

export interface RequirementsStepDefinition {
  id: RequirementsStepId;
  stepNumber: number;
  title: string;
  subLabel: string;
  defaultDesc: string;
  activeDesc: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const REQUIREMENTS_NODES: RequirementsStepDefinition[] = [
  {
    id: 'parse',
    stepNumber: 1,
    title: 'Análisis Directiva PMO',
    subLabel: 'directive_parser',
    defaultDesc: 'Extracción de objetivos y delimitación de alcance',
    activeDesc: 'Analizando directiva y delimitando alcance de negocio...',
    icon: BrainCircuit,
  },
  {
    id: 'matrix',
    stepNumber: 2,
    title: 'Matriz Técnica Quarkus',
    subLabel: 'technical_matrix',
    defaultDesc: 'Inferencia de DB, Kafka, QPS y consistencia ACID',
    activeDesc: 'Infiriendo base de datos, mensajería y concurrencia...',
    icon: Sliders,
  },
  {
    id: 'bdd',
    stepNumber: 3,
    title: 'Historias de Usuario BDD',
    subLabel: 'bdd_synthesizer',
    defaultDesc: 'Síntesis de escenarios Given/When/Then y reglas',
    activeDesc: 'Sintetizando escenarios BDD y criterios de aceptación...',
    icon: FileText,
  },
  {
    id: 'models',
    stepNumber: 4,
    title: 'Modelado Panache JPA',
    subLabel: 'domain_modeler',
    defaultDesc: 'Entidades, claves primarias y Bean Validation',
    activeDesc: 'Infiriendo entidades Panache, campos y validaciones...',
    icon: Database,
  },
  {
    id: 'contract',
    stepNumber: 5,
    title: 'Compilación SpecKit',
    subLabel: 'speckit_contract',
    defaultDesc: 'Ensamble de contrato canónico para LangGraph',
    activeDesc: 'Validando contrato canónico para ejecución hermética...',
    icon: Sparkles,
  },
];

export interface RequirementsGraphTrackerProps {
  isDrafting: boolean;
  isCompleted: boolean;
  error?: string | null;
  elapsedTime?: number;
  serviceName?: string;
  database?: string;
  messaging?: string;
  storiesCount?: number;
  entitiesCount?: number;
  className?: string;
  currentStepIndex?: number;
  completedSteps?: number[];
  onStepClick?: (stepNumber: number) => void;
  activeAgentLog?: string | null;
  stepDetails?: Partial<Record<RequirementsStepId, string>>;
}

export const RequirementsGraphTracker: React.FC<RequirementsGraphTrackerProps> = ({
  isDrafting,
  isCompleted,
  error,
  elapsedTime = 0,
  serviceName,
  database,
  messaging,
  storiesCount = 0,
  entitiesCount = 0,
  className,
  currentStepIndex,
  completedSteps,
  onStepClick,
  activeAgentLog,
  stepDetails,
}) => {
  // Stepped active simulation during drafting when external currentStepIndex is not controlled
  const [internalStepIndex, setInternalStepIndex] = useState<number>(0);

  useEffect(() => {
    if (currentStepIndex !== undefined) {
      setInternalStepIndex(currentStepIndex);
      return;
    }

    if (!isDrafting) {
      if (isCompleted) {
        setInternalStepIndex(5);
      } else {
        setInternalStepIndex(0);
      }
      return;
    }

    // Step progression animation during in-flight drafting
    setInternalStepIndex(0);
    const interval = setInterval(() => {
      setInternalStepIndex((prev) => (prev < 4 ? prev + 1 : prev));
    }, 450);

    return () => clearInterval(interval);
  }, [isDrafting, isCompleted, currentStepIndex]);

  const activeIdx = currentStepIndex !== undefined ? currentStepIndex : internalStepIndex;

  const getNodeStatus = (index: number): RequirementsStepStatus => {
    const stepNum = index + 1;
    if (completedSteps && completedSteps.includes(stepNum)) {
      return 'PASSED';
    }
    if (error && index === activeIdx) return 'ERROR';
    if (isCompleted) return 'PASSED';
    if (isDrafting) {
      if (index === activeIdx) return 'ACTIVE';
      if (index < activeIdx) return 'PASSED';
      return 'IDLE';
    }
    return 'IDLE';
  };

  const getCompletedDetail = (nodeId: RequirementsStepId): string => {
    if (stepDetails && stepDetails[nodeId]) {
      return stepDetails[nodeId]!;
    }
    switch (nodeId) {
      case 'parse':
        return serviceName && serviceName !== 'generated-service'
          ? `Objetivo: ${serviceName}`
          : 'Directiva analizada con éxito';
      case 'matrix':
        return `${database || 'POSTGRESQL'} • ${messaging || 'KAFKA'}`;
      case 'bdd':
        return `${storiesCount > 0 ? storiesCount : 2} Historias BDD generadas`;
      case 'models':
        return `${entitiesCount > 0 ? entitiesCount : 2} Entidades Panache JPA`;
      case 'contract':
        return 'Contrato SpecKit v1 Compilado';
      default:
        return 'Completado';
    }
  };

  return (
    <div
      role="region"
      aria-label="Grafo de Requisitos & Especificación"
      className={clsx(
        'rounded-2xl border bg-slate-950/90 backdrop-blur-md p-4 sm:p-5 transition-all shadow-lg',
        isDrafting
          ? 'border-indigo-600/60 shadow-indigo-500/10'
          : isCompleted
          ? 'border-emerald-600/50 shadow-emerald-500/10'
          : error
          ? 'border-rose-700/60 shadow-rose-500/10'
          : 'border-slate-800',
        className
      )}
    >
      {/* Top Header Strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          <div
            className={clsx(
              'w-8 h-8 rounded-xl flex items-center justify-center border',
              isDrafting
                ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-400'
                : isCompleted
                ? 'bg-emerald-600/20 border-emerald-500/50 text-emerald-400'
                : 'bg-slate-900 border-slate-700 text-slate-400'
            )}
          >
            <BrainCircuit className={clsx('w-4 h-4', isDrafting && 'animate-pulse')} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs sm:text-sm font-bold text-white tracking-tight">
                Grafo de Requisitos & Especificación Upstream
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                SpecDrafting Pipeline
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Observabilidad en tiempo real del pipeline de inferencia y extracción de requerimientos
            </p>
          </div>
        </div>

        {/* Status Badge & Metrics */}
        <div className="flex items-center gap-2 text-xs shrink-0 font-mono">
          {isDrafting && (
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-950/80 border border-indigo-700/80 text-indigo-300 text-[11px] font-bold animate-pulse">
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping" />
              <span>INFERIENDO REQUISITOS...</span>
            </div>
          )}

          {isCompleted && (
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-950/80 border border-emerald-700/80 text-emerald-300 text-[11px] font-bold">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>ESPECIFICACIÓN COMPILADA</span>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-950/80 border border-rose-700/80 text-rose-300 text-[11px] font-bold">
              <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
              <span>ERROR DE SÍNTESIS</span>
            </div>
          )}

          {!isDrafting && !isCompleted && !error && (
            <div className="px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-slate-400 text-[11px]">
              LISTO PARA ANALIZAR
            </div>
          )}

          {elapsedTime > 0 && (
            <div className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 text-[11px]">
              <Clock className="w-3 h-3 text-slate-500" />
              <span>{elapsedTime.toFixed(1)}s</span>
            </div>
          )}
        </div>
      </div>

      {/* Live Procedural Agent Activity Log */}
      {activeAgentLog && (
        <div className="mt-3 px-3.5 py-2 rounded-xl bg-slate-900/90 border border-indigo-700/60 flex items-center justify-between gap-3 text-xs font-mono text-indigo-300 shadow-sm animate-fadeIn">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping shrink-0" />
            <span className="truncate">{activeAgentLog}</span>
          </div>
          <span className="text-[10px] text-indigo-400/80 bg-indigo-950/80 border border-indigo-800/80 px-2 py-0.5 rounded-full shrink-0 uppercase tracking-wider font-semibold">
            Agente Activo
          </span>
        </div>
      )}

      {/* 5-Node Interactive Stepper Flow */}
      <div className="pt-4 grid grid-cols-1 sm:grid-cols-5 gap-3">
        {REQUIREMENTS_NODES.map((node, idx) => {
          const NodeIcon = node.icon;
          const status = getNodeStatus(idx);
          const isPassed = status === 'PASSED';
          const isActive = status === 'ACTIVE';
          const isError = status === 'ERROR';

          return (
            <div
              key={node.id}
              role={onStepClick ? 'button' : undefined}
              tabIndex={onStepClick ? 0 : undefined}
              onClick={() => onStepClick?.(node.stepNumber)}
              onKeyDown={(e) => {
                if (onStepClick && (e.key === 'Enter' || e.key === ' ')) {
                  onStepClick(node.stepNumber);
                }
              }}
              data-testid={`requirements-node-${node.id}`}
              className={clsx(
                'relative flex flex-col p-3 rounded-xl border transition-all text-left group',
                onStepClick && 'cursor-pointer hover:scale-[1.02] focus:outline-hidden focus:ring-1 focus:ring-indigo-400',
                isActive
                  ? 'bg-gradient-to-b from-indigo-950/70 to-slate-900 border-indigo-500 shadow-md shadow-indigo-500/20 ring-1 ring-indigo-500/50'
                  : isPassed
                  ? 'bg-slate-900/90 border-emerald-800/60 hover:border-emerald-700'
                  : isError
                  ? 'bg-rose-950/40 border-rose-800'
                  : 'bg-slate-900/40 border-slate-800/80 opacity-75'
              )}
            >
              {/* Connector line for large screens */}
              {idx < REQUIREMENTS_NODES.length - 1 && (
                <div className="hidden sm:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 pointer-events-none">
                  <ArrowRight
                    className={clsx(
                      'w-3.5 h-3.5',
                      isPassed ? 'text-emerald-500' : 'text-slate-700'
                    )}
                  />
                </div>
              )}

              {/* Node Top Row: Step Badge + Status Icon */}
              <div className="flex items-center justify-between gap-1 mb-2">
                <span
                  className={clsx(
                    'text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border',
                    isActive
                      ? 'bg-indigo-900/60 text-indigo-300 border-indigo-700'
                      : isPassed
                      ? 'bg-emerald-950/80 text-emerald-400 border-emerald-800'
                      : isError
                      ? 'bg-rose-950 text-rose-400 border-rose-800'
                      : 'bg-slate-950 text-slate-500 border-slate-800'
                  )}
                >
                  Paso {node.stepNumber}
                </span>

                <div className="shrink-0 flex items-center gap-1.5">
                  <span className="text-[9px] font-mono text-slate-500 hidden sm:inline">
                    {node.subLabel}
                  </span>
                  {isPassed && <Check className="w-4 h-4 text-emerald-400" />}
                  {isActive && (
                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-ping inline-block" />
                  )}
                  {isError && <AlertCircle className="w-4 h-4 text-rose-400" />}
                  {!isPassed && !isActive && !isError && (
                    <span className="w-2 h-2 rounded-full bg-slate-700 inline-block" />
                  )}
                </div>
              </div>

              {/* Icon & Title */}
              <div className="flex items-center gap-2 mb-1.5 min-w-0">
                <NodeIcon
                  className={clsx(
                    'w-3.5 h-3.5 shrink-0',
                    isActive
                      ? 'text-indigo-400'
                      : isPassed
                      ? 'text-emerald-400'
                      : isError
                      ? 'text-rose-400'
                      : 'text-slate-500'
                  )}
                />
                <span
                  className={clsx(
                    'text-xs font-bold truncate',
                    isActive ? 'text-white' : isPassed ? 'text-slate-100' : 'text-slate-300'
                  )}
                >
                  {node.title}
                </span>
              </div>

              {/* Description / Telemetry Detail */}
              <p className="text-[11px] leading-snug line-clamp-2 text-slate-400 mt-auto">
                {isPassed
                  ? getCompletedDetail(node.id)
                  : isActive
                  ? node.activeDesc
                  : node.defaultDesc}
              </p>
            </div>
          );
        })}
      </div>

      {/* Telemetry Summary Bar when completed */}
      {isCompleted && (
        <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
            <span className="text-slate-500">Resumen Inferido:</span>
            <span className="px-2 py-0.5 rounded bg-blue-950/60 border border-blue-800/60 text-blue-300">
              {serviceName || 'microservice'}
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
              {database || 'POSTGRESQL'}
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
              {messaging || 'NONE'}
            </span>
            <span className="px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/60 text-emerald-300">
              {storiesCount} Historias BDD
            </span>
            <span className="px-2 py-0.5 rounded bg-indigo-950/60 border border-indigo-800/60 text-indigo-300">
              {entitiesCount} Entidades Panache
            </span>
          </div>

          <span className="text-emerald-400 font-semibold text-[11px] flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Listo para revisar y avanzar a Arquitectura ➜</span>
          </span>
        </div>
      )}
    </div>
  );
};
