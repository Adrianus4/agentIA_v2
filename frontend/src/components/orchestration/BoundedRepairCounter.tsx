import React from 'react';
import { clsx } from 'clsx';
import { RotateCcw, ShieldAlert, CheckCircle2, Zap } from 'lucide-react';

interface BoundedRepairCounterProps {
  currentIteration: number;
  maxIterations?: number;
  outcome?: string | null;
  className?: string;
}

export const BoundedRepairCounter: React.FC<BoundedRepairCounterProps> = ({
  currentIteration,
  maxIterations = 3,
  outcome,
  className,
}) => {
  const isExhausted = currentIteration >= maxIterations && outcome === 'NO_FIX';
  const isRepaired  = outcome === 'PATCHED' || outcome === 'SUCCESS';
  const isActive    = currentIteration > 0 && !isRepaired && !isExhausted;

  // Fraction for the circular arc
  const radius      = 16;
  const circumference = 2 * Math.PI * radius;
  const fraction    = Math.min(currentIteration / maxIterations, 1);
  const dashOffset  = circumference * (1 - fraction);

  const arcColor =
    isExhausted ? 'stroke-rose-500'   :
    isRepaired  ? 'stroke-emerald-500' :
    isActive    ? 'stroke-amber-400'   :
    'stroke-slate-700';

  const labelColor =
    isExhausted ? 'text-rose-400'    :
    isRepaired  ? 'text-emerald-400'  :
    isActive    ? 'text-amber-300'    :
    'text-slate-400';

  return (
    <div
      className={clsx(
        'rounded-xl border p-3 flex items-center gap-3 transition-all',
        isExhausted ? 'border-rose-800/80 bg-rose-950/30'
          : isRepaired ? 'border-emerald-800/70 bg-emerald-950/20'
          : isActive   ? 'border-amber-800/70 bg-amber-950/20'
          : 'border-slate-800 bg-slate-900/60',
        className
      )}
    >
      {/* Circular progress */}
      <div className="relative shrink-0 w-10 h-10">
        <svg className="w-10 h-10 -rotate-90" viewBox="0 0 40 40">
          {/* Track */}
          <circle cx="20" cy="20" r={radius} fill="none" stroke="currentColor"
            strokeWidth="3" className="text-slate-800" />
          {/* Progress arc */}
          <circle
            cx="20" cy="20" r={radius}
            fill="none"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            className={clsx('transition-all duration-500', arcColor)}
          />
        </svg>
        {/* Centre icon */}
        <div className="absolute inset-0 flex items-center justify-center">
          {isExhausted  ? <ShieldAlert  className="w-4 h-4 text-rose-400" />
          : isRepaired  ? <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          : isActive    ? <RotateCcw    className="w-4 h-4 text-amber-400 animate-spin" />
          : <Zap className="w-4 h-4 text-slate-500" />}
        </div>
      </div>

      {/* Text block */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-slate-300">Bounded Auto-Repair</span>
          <span className={clsx('font-mono font-bold text-xs', labelColor)}>
            {currentIteration} / {maxIterations}
          </span>
        </div>

        {/* Segmented bars */}
        <div className="grid gap-1 mt-1.5" style={{ gridTemplateColumns: `repeat(${maxIterations}, 1fr)` }}>
          {Array.from({ length: maxIterations }).map((_, i) => {
            const filled = currentIteration > i;
            return (
              <div
                key={i}
                className={clsx(
                  'h-1.5 rounded-full transition-all duration-300',
                  filled
                    ? isExhausted ? 'bg-rose-500'
                      : isRepaired ? 'bg-emerald-500'
                      : 'bg-amber-400'
                    : 'bg-slate-800'
                )}
                title={`Attempt ${i + 1} of ${maxIterations}`}
              />
            );
          })}
        </div>

        <div className="flex items-center justify-between text-[10px] mt-1 text-slate-500">
          <span>Principio V (Bounded Loop)</span>
          {isExhausted ? (
            <span className="text-rose-400 font-semibold flex items-center gap-0.5">
              <ShieldAlert className="w-3 h-3" /> NO_FIX
            </span>
          ) : isRepaired ? (
            <span className="text-emerald-400 font-semibold flex items-center gap-0.5">
              <CheckCircle2 className="w-3 h-3" /> OK
            </span>
          ) : (
            <span>Máx {maxIterations} intentos</span>
          )}
        </div>
      </div>
    </div>
  );
};
