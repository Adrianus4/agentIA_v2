import React from 'react';
import { clsx } from 'clsx';
import {
  CheckCircle2,
  RefreshCw,
  RotateCcw,
  AlertCircle,
  ShieldAlert,
  Clock,
  ArrowRight,
  GitBranch,
} from 'lucide-react';
import type { LangGraphNodeState } from '../../types/blueprintGraph';

interface LiveGraphMonitorProps {
  nodes: Record<string, LangGraphNodeState>;
  currentIteration?: number;
  maxIterations?: number;
  outcome?: string | null;
  className?: string;
}

interface NodeDefinition {
  key: string;
  stepNumber: number;
  title: string;
  defaultDescription: string;
  subLabel: string;
}

const ORCHESTRATOR_NODES: NodeDefinition[] = [
  {
    key: 'validate',
    stepNumber: 1,
    title: 'Validación de Esquema',
    defaultDescription: 'Validación de esquema SpecKit y contratos BDD',
    subLabel: 'validate',
  },
  {
    key: 'generate',
    stepNumber: 2,
    title: 'Generación de Componentes',
    defaultDescription: 'Generación reactiva: Entity ➔ Resource ➔ Test',
    subLabel: 'generate',
  },
  {
    key: 'verify',
    stepNumber: 3,
    title: 'Verificación Maven Hermética',
    defaultDescription: 'Sandbox hermético Docker (mvn test-compile)',
    subLabel: 'verify',
  },
  {
    key: 'repair',
    stepNumber: 4,
    title: 'Reparación Quirúrgica AST',
    defaultDescription: 'Parche quirúrgico AST guiado por diagnósticos',
    subLabel: 'repair',
  },
  {
    key: 'terminal',
    stepNumber: 5,
    title: 'Veredicto Final',
    defaultDescription: 'Liberación de código o fallo constitucional NO_FIX',
    subLabel: 'terminal',
  },
];

export const LiveGraphMonitor: React.FC<LiveGraphMonitorProps> = ({
  nodes,
  currentIteration = 0,
  maxIterations = 3,
  outcome,
  className,
}) => {
  return (
    <div
      role="region"
      aria-label="Monitor de Grafo en Vivo"
      className={clsx(
        'w-full bg-slate-900/90 rounded-2xl border border-slate-800 p-4 shadow-xl backdrop-blur-md space-y-4',
        className
      )}
    >
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-blue-400" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Ruta de Ejecución del Grafo LangGraph (Orchestrator Path)
          </h3>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400">
          <span className="flex items-center gap-1.5 text-blue-400">
            <ArrowRight className="w-3 h-3" /> Transición Directa
          </span>
          <span className="flex items-center gap-1.5 text-amber-400">
            <RotateCcw className="w-3 h-3" /> Auto-Reparación AST (≤ {maxIterations})
          </span>
          {currentIteration > 0 && (
            <span className="px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-800 font-bold">
              Intento {currentIteration} / {maxIterations}
            </span>
          )}
        </div>
      </div>

      {/* 5-Node Step Pipeline Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 relative">
        {ORCHESTRATOR_NODES.map((def, idx) => {
          const nodeData = nodes[def.key] || {
            id: def.key,
            label: `${def.stepNumber}. ${def.title}`,
            description: def.defaultDescription,
            status: 'IDLE',
          };

          const isRunning = nodeData.status === 'ACTIVE';
          const isRepairing = nodeData.status === 'REPAIRING';
          const isPassed = nodeData.status === 'PASSED' || nodeData.status === 'SUCCESS';
          const isFailed = nodeData.status === 'NO_FIX' || nodeData.status === 'ERROR';

          // Node status badge text & styling
          let badgeText = 'EN ESPERA';
          let badgeClass = 'bg-slate-950 text-slate-400 border-slate-800';
          let cardBorderClass = 'border-slate-800 bg-slate-950/60 opacity-80';

          if (isRunning) {
            badgeText = 'EJECUTANDO';
            badgeClass = 'bg-blue-500/20 text-blue-300 border-blue-400/40 animate-pulse font-bold';
            cardBorderClass = 'border-blue-500/80 bg-blue-950/30 shadow-lg shadow-blue-500/10 ring-1 ring-blue-500/40';
          } else if (isRepairing) {
            badgeText = `REPARANDO (${currentIteration}/${maxIterations})`;
            badgeClass = 'bg-amber-500/20 text-amber-300 border-amber-400/40 animate-pulse font-bold';
            cardBorderClass = 'border-amber-500/80 bg-amber-950/30 shadow-lg shadow-amber-500/10 ring-1 ring-amber-500/40';
          } else if (isPassed) {
            badgeText = def.key === 'terminal' ? 'EXITOSO' : 'COMPLETADO';
            badgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-400/40 font-bold';
            cardBorderClass = 'border-emerald-500/60 bg-emerald-950/20 shadow-md';
          } else if (isFailed) {
            badgeText = def.key === 'repair' ? `AGOTADO (${currentIteration}/${maxIterations})` : outcome || 'FALLIDO';
            badgeClass = 'bg-rose-500/20 text-rose-300 border-rose-400/40 font-bold';
            cardBorderClass = 'border-rose-500/80 bg-rose-950/30 shadow-lg shadow-rose-500/10 ring-1 ring-rose-500/40';
          }

          return (
            <div
              key={def.key}
              data-testid={`live-graph-node-${def.key}`}
              className={clsx(
                'relative rounded-xl border p-3.5 flex flex-col justify-between min-h-[160px] transition-all duration-300',
                cardBorderClass
              )}
            >
              {/* Connector Arrow on Desktop */}
              {idx < ORCHESTRATOR_NODES.length - 1 && (
                <div className="hidden lg:block absolute -right-2.5 top-1/2 -translate-y-1/2 z-10 text-slate-700 pointer-events-none">
                  <ArrowRight className="w-3.5 h-3.5" />
                </div>
              )}

              {/* Node Top: Step number + Title + Icon */}
              <div>
                <div className="flex items-start justify-between gap-1.5 mb-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={clsx(
                        'flex items-center justify-center w-5 h-5 rounded-full text-[11px] font-mono font-bold border shrink-0',
                        isPassed
                          ? 'bg-emerald-950 text-emerald-400 border-emerald-700'
                          : isRunning || isRepairing
                          ? 'bg-blue-950 text-blue-400 border-blue-700 animate-pulse'
                          : 'bg-slate-900 text-slate-400 border-slate-750'
                      )}
                    >
                      {def.stepNumber}
                    </span>
                    <span className="font-mono text-[10px] text-slate-400 uppercase font-semibold">
                      [{def.subLabel}]
                    </span>
                  </div>

                  {/* Status Node Feedback Icon */}
                  <div className="shrink-0">
                    {isRunning && <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />}
                    {isRepairing && <RotateCcw className="w-4 h-4 text-amber-400 animate-spin" />}
                    {isPassed && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                    {isFailed && (
                      def.key === 'terminal' || def.key === 'repair' ? (
                        <ShieldAlert className="w-4 h-4 text-rose-400" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-rose-400" />
                      )
                    )}
                    {!isRunning && !isRepairing && !isPassed && !isFailed && (
                      <Clock className="w-4 h-4 text-slate-600" />
                    )}
                  </div>
                </div>

                <h4 className="text-xs font-bold text-white tracking-tight mb-1">
                  [{def.title}]
                </h4>

                <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                  {nodeData.description || def.defaultDescription}
                </p>
              </div>

              {/* Node Bottom: Status Badge + Live Details */}
              <div className="pt-2 border-t border-slate-800/80 flex flex-col gap-1 text-[10px]">
                <div className="flex items-center justify-between">
                  <span className={clsx('px-2 py-0.5 rounded text-[10px] border', badgeClass)}>
                    {badgeText}
                  </span>
                </div>

                {nodeData.details && (
                  <span
                    className="font-mono text-[10px] text-slate-300 truncate"
                    title={nodeData.details}
                  >
                    {nodeData.details}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
