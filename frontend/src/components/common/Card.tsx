import React from 'react';
import { clsx } from 'clsx';

interface CardProps {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  headerRight?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({
  title,
  subtitle,
  headerRight,
  action,
  children,
  footer,
  className,
}) => {
  const rightContent = action || headerRight;
  return (
    <div
      className={clsx(
        'rounded-xl border border-slate-800 bg-slate-900/90 p-5 shadow-sm transition-all',
        className
      )}
    >
      {(title || rightContent) && (
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            {title && (
              <h3 className="text-sm sm:text-base font-semibold text-white tracking-tight">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
            )}
          </div>
          {rightContent && <div className="flex-shrink-0">{rightContent}</div>}
        </div>
      )}

      <div className="text-slate-200">{children}</div>
      {footer && (
        <div className="border-t border-slate-800/80 pt-3 mt-4 flex items-center justify-between text-xs text-slate-400">
          {footer}
        </div>
      )}
    </div>
  );
};

