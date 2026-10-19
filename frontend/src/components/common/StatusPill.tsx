import React from 'react';
import { clsx } from 'clsx';

export type StatusPillVariant = 'primary' | 'success' | 'warning' | 'danger' | 'neutral' | 'active';

interface StatusPillProps {
  label: string;
  variant?: StatusPillVariant;
  icon?: React.ReactNode;
  className?: string;
}

export const StatusPill: React.FC<StatusPillProps> = ({
  label,
  variant = 'neutral',
  icon,
  className,
}) => {
  const variantStyles = {
    primary: 'bg-blue-950/60 border-blue-500/50 text-blue-300',
    active: 'bg-blue-900/40 border-blue-400 text-blue-300 animate-pulse',
    success: 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300',
    warning: 'bg-amber-950/60 border-amber-500/50 text-amber-300',
    danger: 'bg-rose-950/60 border-rose-500/50 text-rose-300',
    neutral: 'bg-slate-800/80 border-slate-700 text-slate-300',
  }[variant];

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border tracking-wide uppercase font-mono shadow-sm',
        variantStyles,
        className
      )}
    >
      {icon}
      <span>{label}</span>
    </span>
  );
};

