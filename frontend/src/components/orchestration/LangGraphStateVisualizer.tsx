import React from 'react';
import { clsx } from 'clsx';
import { ArrowRight, CornerDownLeft, GitBranch, RefreshCw } from 'lucide-react';
import type { LangGraphNodeState } from '../../types/blueprintGraph';
import { NodeCard } from './NodeCard';
import { BoundedRepairCounter } from './BoundedRepairCounter';
import { Card } from '../common/Card';

interface LangGraphStateVisualizerProps {
  nodes: Record<string, LangGraphNodeState>;
  currentIteration: number;
  maxIterations?: number;
  outcome?: string | null;
  className?: string;
}

/** Thin animated connector between node cards */
const Connector: React.FC<{ isActive?: boolean; isLoop?: boolean }> = ({
  isActive = false,
  isLoop = false,
}) => (
  <div className="hidden md:flex items-center justify-center shrink-0 w-6 z-10">
    <div className={clsx('relative flex items-center')}>
      {/* Line */}
      <div
        className={clsx(
          'h-0.5 w-6 rounded-full transition-all duration-500',
          isLoop
            ? 'bg-amber-500/60'
            : isActive
            ? 'bg-blue-500/80'
            : 'bg-slate-700'
        )}
      />
      {/* Arrow head */}
      <ArrowRight
        className={clsx(
          'absolute -right-2 w-3.5 h-3.5 transition-colors duration-300',
          isLoop
            ? 'text-amber-400'
            : isActive
            ? 'text-blue-400'
            : 'text-slate-600'
        )}
      />
    </div>
  </div>
);

export const LangGraphStateVisualizer: React.FC<LangGraphStateVisualizerProps> = ({
  nodes,
  currentIteration,
  maxIterations = 3,
  outcome,
  className,
}) => {
  const hasGenerate = Boolean(nodes.generate);

  const validateNode = nodes.validate || {
    id: 'validate',
    label: '1. Validate',
    description: 'Schema & BDD stories validation',
    status: 'IDLE',
  };

  const generateNode = nodes.generate;

  const verifyNode = nodes.verify || {
    id: 'verify',
    label: hasGenerate ? '3. Verify' : '2. Verify',
    description: 'Hermetic Docker sandbox test',
    status: 'IDLE',
  };

  const repairNode = nodes.repair || {
    id: 'repair',
    label: hasGenerate ? '4. Repair' : '3. Repair',
    description: 'AST diagnostics & surgical patch',
    status: 'IDLE',
  };

  const terminalNode = nodes.terminal || {
    id: 'terminal',
    label: hasGenerate ? '5. Outcome' : '4. Outcome',
    description: 'Final release or NO_FIX',
    status: 'IDLE',
  };

  // Determine which connectors should glow
  const validatePassed  = validateNode.status === 'PASSED' || validateNode.status === 'SUCCESS';
  const generatePassed  = generateNode?.status === 'PASSED' || generateNode?.status === 'SUCCESS';
  const verifyPassed    = verifyNode.status  === 'PASSED' || verifyNode.status === 'SUCCESS';
  const repairActive    = repairNode.status  === 'REPAIRING' || repairNode.status === 'ACTIVE';
  const repairLoop      = currentIteration > 0;

  return (
    <Card
      title={
        <div className="flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-blue-400" />
          <span>LangGraph State Machine Pipeline</span>
        </div>
      }
      subtitle={
        hasGenerate
          ? 'Ciclo de ejecución en tiempo real: Validate ➔ Generate ➔ Verify ➔ Bounded Repair ➔ Outcome'
          : 'Ciclo de ejecución en tiempo real: Validate ➔ Verify ➔ Bounded Repair ➔ Outcome'
      }
      headerRight={
        <BoundedRepairCounter
          currentIteration={currentIteration}
          maxIterations={maxIterations}
          outcome={outcome}
          className="min-w-[200px]"
        />
      }
      className={clsx('relative overflow-hidden', className)}
    >
      {/* ── Node Flow: cards + connectors in a flex row ── */}
      <div className="flex flex-col md:flex-row items-stretch gap-2 md:gap-0 mt-2 overflow-x-auto pb-1">

        {/* Node 1: Validate */}
        <NodeCard node={validateNode} stepNumber={1} className="flex-1 min-w-[140px]" />

        <Connector isActive={validatePassed} />

        {/* Node 2: Generate (optional) */}
        {hasGenerate && generateNode && (
          <>
            <NodeCard node={generateNode} stepNumber={2} className="flex-1 min-w-[140px]" />
            <Connector isActive={generatePassed} />
          </>
        )}

        {/* Node: Verify */}
        <NodeCard node={verifyNode} stepNumber={hasGenerate ? 3 : 2} className="flex-1 min-w-[140px]" />

        {/* Repair loop connector */}
        <div className="hidden md:flex flex-col items-center justify-center shrink-0 w-6">
          <div
            className={clsx(
              'h-0.5 w-6 rounded-full transition-all duration-500',
              repairLoop ? 'bg-amber-500/70' : 'bg-slate-700'
            )}
          />
          {repairLoop && (
            <RefreshCw className="w-3 h-3 text-amber-400 mt-0.5 animate-spin" />
          )}
          {!repairLoop && (
            <ArrowRight className="w-3.5 h-3.5 text-slate-600 -mt-1" />
          )}
        </div>

        {/* Node: Repair */}
        <NodeCard node={repairNode} stepNumber={hasGenerate ? 4 : 3} className="flex-1 min-w-[140px]" />

        <Connector isActive={!repairActive && (verifyPassed || outcome === 'SUCCESS' || outcome === 'NO_FIX')} />

        {/* Node: Terminal */}
        <NodeCard node={terminalNode} stepNumber={hasGenerate ? 5 : 4} className="flex-1 min-w-[140px]" />
      </div>

      {/* ── Repair loop arc annotation (visible on md+) ── */}
      {repairLoop && (
        <div className="hidden md:flex items-center gap-2 mt-3 px-4 py-2 rounded-xl bg-amber-950/30 border border-amber-800/50 text-[11px] text-amber-300 font-mono">
          <RefreshCw className="w-3.5 h-3.5 shrink-0 animate-spin" />
          <span>
            Bucle de reparación activo — intento {currentIteration} / {maxIterations}
            {outcome === 'NO_FIX' && ' — ⛔ NO_FIX: presupuesto agotado'}
          </span>
        </div>
      )}

      {/* ── Legend ── */}
      <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-blue-400">
            <ArrowRight className="w-3.5 h-3.5" /> Transición directa
          </span>
          <span className="flex items-center gap-1.5 text-amber-400">
            <RefreshCw className="w-3.5 h-3.5" /> Bucle Verify ↔ Repair (máx {maxIterations})
          </span>
          <span className="flex items-center gap-1.5 text-rose-400">
            <CornerDownLeft className="w-3.5 h-3.5" /> Parada constitucional NO_FIX
          </span>
        </div>
        <div className="font-mono text-[11px] text-slate-500">
          Orchestrator Spine v2 • LangGraph State Graph
        </div>
      </div>
    </Card>
  );
};
