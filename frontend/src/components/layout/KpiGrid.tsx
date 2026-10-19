import React from 'react';
import { clsx } from 'clsx';
import { Activity, Box, RotateCcw, ShieldCheck, CheckCircle2, AlertTriangle, Clock, RefreshCw } from 'lucide-react';
import { StatusPill } from '../common/StatusPill';

interface KpiGridProps {
  currentPhase: string;
  sandboxStatus: 'PENDING' | 'PASSED' | 'FAILED' | 'SKIPPED_BY_CHOICE' | 'INTERRUPTED' | 'RUNNING';
  repairIteration: number;
  maxRepairs?: number;
  className?: string;
}

export const KpiGrid: React.FC<KpiGridProps> = ({
  currentPhase,
  sandboxStatus,
  repairIteration,
  maxRepairs = 3,
  className,
}) => {
  const getSandboxPillVariant = () => {
    switch (sandboxStatus) {
      case 'PASSED':
        return 'success';
      case 'RUNNING':
        return 'active';
      case 'FAILED':
      case 'INTERRUPTED':
        return 'danger';
      case 'SKIPPED_BY_CHOICE':
        return 'warning';
      case 'PENDING':
      default:
        return 'neutral';
    }
  };

  const getSandboxIcon = () => {
    switch (sandboxStatus) {
      case 'PASSED':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'RUNNING':
        return <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />;
      case 'FAILED':
      case 'INTERRUPTED':
        return <AlertTriangle className="w-4 h-4 text-rose-400" />;
      case 'SKIPPED_BY_CHOICE':
        return <AlertTriangle className="w-4 h-4 text-amber-400" />;
      case 'PENDING':
      default:
        return <Clock className="w-4 h-4 text-slate-500" />;
    }
  };

  return (
    <div className={clsx('grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4', className)}>
      {/* 1. Fase Actual */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-4 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
          <span className="font-semibold uppercase tracking-wider">Fase Actual</span>
          <Activity className="w-4 h-4 text-blue-400" />
        </div>
        <div>
          <div className="text-lg font-bold font-mono text-white truncate" title={currentPhase}>
            {currentPhase}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">LangGraph Active Node</div>
        </div>
      </div>

      {/* 2. Estado del Sandbox */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-4 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
          <span className="font-semibold uppercase tracking-wider">Estado del Sandbox</span>
          <Box className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <div className="flex items-center gap-2 mt-0.5">
            {getSandboxIcon()}
            <StatusPill
              label={sandboxStatus}
              variant={getSandboxPillVariant()}
              className="text-[11px]"
            />
          </div>
          <div className="text-[11px] text-slate-500 mt-1.5">
            {sandboxStatus === 'SKIPPED_BY_CHOICE'
              ? 'Ejecución omitida por elección'
              : 'Verificación hermética'}
          </div>
        </div>
      </div>

      {/* 3. Iteración Auto-Reparación */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-4 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
          <span className="font-semibold uppercase tracking-wider">Iteración Auto-Reparación</span>
          <RotateCcw className="w-4 h-4 text-amber-400" />
        </div>
        <div>
          <div className="text-lg font-bold font-mono text-white">
            {repairIteration} / {maxRepairs}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            {repairIteration === 0
              ? 'Sin reparaciones requeridas'
              : `Intento de parche ${repairIteration}`}
          </div>
        </div>
      </div>

      {/* 4. Límite Constitucional */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-4 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
          <span className="font-semibold uppercase tracking-wider">Límite Constitucional</span>
          <ShieldCheck className="w-4 h-4 text-blue-400" />
        </div>
        <div>
          <div className="text-base font-bold text-white flex items-center gap-1.5">
            <span>Máx {maxRepairs} (Principio V)</span>
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Garantía de parada finita
          </div>
        </div>
      </div>
    </div>
  );
};

