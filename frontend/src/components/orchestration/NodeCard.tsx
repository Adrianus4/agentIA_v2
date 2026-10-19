import React from 'react';
import { clsx } from 'clsx';
import {
  Clock,
  RefreshCw,
  CheckCircle2,
  RotateCcw,
  ShieldAlert,
  AlertCircle,
  Check,
  ShieldCheck,
  Cpu,
  Zap,
  Wrench,
  Flag,
} from 'lucide-react';
import type { LangGraphNodeState, LangGraphNodeId } from '../../types/blueprintGraph';
import { StatusPill } from '../common/StatusPill';

interface NodeCardProps {
  node: LangGraphNodeState;
  stepNumber: number;
  className?: string;
}

/** Big icon per pipeline step */
const NODE_ICON_MAP: Record<LangGraphNodeId, React.ComponentType<{ className?: string }>> = {
  validate: ShieldCheck,
  generate: Cpu,
  verify: Zap,
  repair: Wrench,
  terminal: Flag,
};

/** Human-readable purpose per step */
const NODE_PURPOSE_MAP: Record<LangGraphNodeId, string> = {
  validate:  'Comprueba el esquema del blueprint y las historias BDD antes de generar.',
  generate:  'Sintetiza entidades, recursos REST y pruebas con plantillas Jinja2.',
  verify:    'Compila y ejecuta `mvn test` en un sandbox hermético (JDK 21).',
  repair:    'Analiza diagnósticos y aplica parches quirúrgicos AST guiados por el LLM.',
  terminal:  'Publica el microservicio verificado o detiene el proceso con NO_FIX.',
};

const STATUS_BG: Record<string, string> = {
  ACTIVE:    'from-blue-950/60 to-slate-900/80 border-blue-500/70 shadow-blue-950/40',
  REPAIRING: 'from-amber-950/60 to-slate-900/80 border-amber-500/70 shadow-amber-950/40',
  PASSED:    'from-emerald-950/40 to-slate-900/70 border-emerald-500/50 shadow-emerald-950/20',
  SUCCESS:   'from-emerald-950/40 to-slate-900/70 border-emerald-500/50 shadow-emerald-950/20',
  NO_FIX:    'from-rose-950/60 to-slate-900/80 border-rose-500/60 shadow-rose-950/40',
  ERROR:     'from-rose-950/60 to-slate-900/80 border-rose-500/60 shadow-rose-950/40',
  IDLE:      'from-slate-900/60 to-slate-900/40 border-slate-800 opacity-60',
  SKIPPED:   'from-slate-900/60 to-slate-900/40 border-slate-800',
};

const ICON_RING: Record<string, string> = {
  ACTIVE:    'bg-blue-500/15 ring-blue-500/40 text-blue-300',
  REPAIRING: 'bg-amber-500/15 ring-amber-500/40 text-amber-300',
  PASSED:    'bg-emerald-500/15 ring-emerald-500/30 text-emerald-300',
  SUCCESS:   'bg-emerald-500/15 ring-emerald-500/30 text-emerald-300',
  NO_FIX:    'bg-rose-500/15 ring-rose-500/40 text-rose-300',
  ERROR:     'bg-rose-500/15 ring-rose-500/40 text-rose-300',
  IDLE:      'bg-slate-800/60 ring-slate-700/30 text-slate-500',
  SKIPPED:   'bg-slate-800/60 ring-slate-700/30 text-slate-400',
};

const STEP_NUM: Record<string, string> = {
  ACTIVE:    'bg-blue-500 text-white shadow-lg shadow-blue-500/50',
  REPAIRING: 'bg-amber-500 text-white shadow-lg shadow-amber-500/50',
  PASSED:    'bg-emerald-500/80 text-white',
  SUCCESS:   'bg-emerald-500/80 text-white',
  NO_FIX:    'bg-rose-500 text-white',
  ERROR:     'bg-rose-500 text-white',
  IDLE:      'bg-slate-800 text-slate-400 border border-slate-700',
  SKIPPED:   'bg-slate-700 text-slate-400',
};

export const NodeCard: React.FC<NodeCardProps> = ({ node, stepNumber, className }) => {
  const status = node.status ?? 'IDLE';
  const bg = STATUS_BG[status] ?? STATUS_BG.IDLE;
  const iconRing = ICON_RING[status] ?? ICON_RING.IDLE;
  const numStyle = STEP_NUM[status] ?? STEP_NUM.IDLE;

  const BigIcon = NODE_ICON_MAP[node.id as LangGraphNodeId] ?? ShieldCheck;
  const purpose = NODE_PURPOSE_MAP[node.id as LangGraphNodeId] ?? node.description;

  const isActive    = status === 'ACTIVE';
  const isRepairing = status === 'REPAIRING';
  const isPassed    = status === 'PASSED' || status === 'SUCCESS';
  const isError     = status === 'ERROR' || status === 'NO_FIX';

  const StatusIcon = isActive    ? <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />
                   : isRepairing ? <RotateCcw  className="w-4 h-4 text-amber-400 animate-spin" />
                   : isPassed    ? <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                   : status === 'NO_FIX' ? <ShieldAlert  className="w-4 h-4 text-rose-400" />
                   : isError     ? <AlertCircle  className="w-4 h-4 text-rose-400" />
                   : status === 'SKIPPED' ? <Check className="w-4 h-4 text-slate-400" />
                   : <Clock className="w-4 h-4 text-slate-500" />;

  const pillVariant =
    isActive    ? 'active'   :
    isRepairing ? 'warning'  :
    isPassed    ? 'success'  :
    isError     ? 'danger'   : 'neutral';

  return (
    <div
      className={clsx(
        'relative rounded-2xl border bg-gradient-to-b p-4 transition-all duration-300 flex flex-col gap-3 shadow-lg',
        bg,
        className
      )}
      data-testid={`node-card-${node.id}`}
    >
      {/* Pulse ring overlay for ACTIVE / REPAIRING */}
      {(isActive || isRepairing) && (
        <span
          className={clsx(
            'pointer-events-none absolute inset-0 rounded-2xl ring-2 animate-pulse',
            isActive ? 'ring-blue-500/30' : 'ring-amber-500/30'
          )}
        />
      )}

      {/* ── Header: step badge + label + status icon ── */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              'flex items-center justify-center w-6 h-6 rounded-full text-[11px] font-mono font-black shrink-0',
              numStyle
            )}
          >
            {stepNumber}
          </span>
          <h4 className="text-sm font-bold text-white leading-tight tracking-tight">
            {node.label}
          </h4>
        </div>
        <div className="shrink-0 mt-0.5">{StatusIcon}</div>
      </div>

      {/* ── Big Icon + Purpose ── */}
      <div className="flex items-start gap-3">
        <div
          className={clsx(
            'shrink-0 flex items-center justify-center w-11 h-11 rounded-xl ring-1',
            iconRing
          )}
        >
          <BigIcon className="w-5 h-5" />
        </div>
        <p className="text-[11px] leading-relaxed text-slate-400 flex-1 pt-0.5">
          {purpose}
        </p>
      </div>

      {/* ── Status pill + details ── */}
      <div className="pt-2 border-t border-white/5 flex flex-wrap items-center justify-between gap-2 text-xs">
        <StatusPill
          label={status}
          variant={pillVariant}
          className="text-[10px] px-2 py-0.5"
        />
        {node.details && (
          <span
            className="text-[10px] font-mono text-slate-300 truncate max-w-[160px]"
            title={node.details}
          >
            {node.details}
          </span>
        )}
      </div>
    </div>
  );
};
