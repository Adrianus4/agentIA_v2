import React, { useState, useEffect } from 'react';
import { clsx } from 'clsx';
import { ShieldCheck, Activity, Cpu, Server, CheckCircle2, AlertCircle, Terminal } from 'lucide-react';
import { StatusPill } from '../common/StatusPill';
import { useLlm } from '../../context/LlmContext';
import { useStudio } from '../../context/StudioContext';

interface HeaderProps {
  traceId?: string | null;
  isRunning?: boolean;
  onOpenSettings?: () => void;
  className?: string;
}

export const Header: React.FC<HeaderProps> = ({
  traceId: propTraceId,
  isRunning: propIsRunning,
  onOpenSettings,
  className,
}) => {
  const { provider, model, isVerified, setIsSettingsOpen } = useLlm();
  const { activeSession, isExecuting, baseUrl, apiKey, isTelemetryDrawerOpen, toggleTelemetryDrawer } = useStudio();

  const traceId = propTraceId !== undefined ? propTraceId : activeSession?.traceId;
  const isRunning = propIsRunning !== undefined ? propIsRunning : isExecuting;

  const [backendHealth, setBackendHealth] = useState<'UP' | 'DOWN' | 'CHECKING'>('CHECKING');

  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      try {
        const res = await fetch(`${baseUrl}/v1/runs`, {
          headers: { 'x-api-key': apiKey },
        });
        if (isMounted) {
          setBackendHealth(res.ok || res.status === 401 ? 'UP' : 'DOWN');
        }
      } catch {
        if (isMounted) setBackendHealth('DOWN');
      }
    };

    void checkHealth();
    const timer = setInterval(() => void checkHealth(), 15000);
    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, [baseUrl, apiKey]);

  const handleOpenSettings = () => {
    if (onOpenSettings) {
      onOpenSettings();
    } else {
      setIsSettingsOpen(true);
    }
  };

  return (
    <header
      className={clsx(
        'border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-30 px-4 sm:px-6 py-3 shadow-md text-slate-100',
        className
      )}
    >
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        {/* Brand Hero with TCS Logo */}
        <div className="flex items-center gap-3">
          <img
            src="/tcs-logo-light.png"
            alt="Tata Consultancy Services"
            className="h-8 sm:h-9 w-auto object-contain select-none"
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />
          <span className="h-6 w-px bg-slate-800 hidden sm:block" />
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base sm:text-lg font-extrabold tracking-tight text-white">
                AgentIA <span className="text-blue-400 font-mono text-sm">v2</span>
              </h1>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-950/80 text-blue-300 border border-blue-800/80 uppercase font-mono">
                Enterprise Studio
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Microservice Architecture & LangGraph State Machine
            </p>
          </div>
        </div>

        {/* Status Indicators & Interactive LLM Modal Trigger */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Active Trace Pill */}
          {traceId ? (
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[11px]">
              <span className="text-slate-500">Trace:</span>
              <span className="text-blue-300 font-bold truncate max-w-[160px]" title={traceId}>
                {traceId}
              </span>
              {isRunning && (
                <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping inline-block ml-1" />
              )}
            </div>
          ) : (
            <div className="px-3 py-1 rounded-lg bg-slate-950/60 border border-slate-800/80 text-slate-500 text-[11px] font-mono">
              Ready for run
            </div>
          )}

          {/* FastAPI Health Indicator */}
          <div
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300"
            title={`FastAPI Orchestrator: ${backendHealth}`}
          >
            <Server className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">FastAPI</span>
            {backendHealth === 'UP' ? (
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
            ) : backendHealth === 'DOWN' ? (
              <span className="w-2 h-2 rounded-full bg-rose-500" />
            ) : (
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            )}
          </div>

          {/* Constitutional Gate Badge */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300 text-[11px]">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Principio V (Bounded Loops)</span>
          </div>

          {/* Telemetry Terminal Toggle */}
          <button
            type="button"
            onClick={toggleTelemetryDrawer}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer border ${
              isTelemetryDrawerOpen
                ? 'bg-blue-600/20 text-blue-300 border-blue-500/50 hover:bg-blue-600/30'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200 hover:border-slate-700'
            }`}
            title="Terminal / Estado de Ejecución"
          >
            <Terminal className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Terminal / Telemetría</span>
          </button>

          {/* LLM Engine Badge / Button to Open Settings Drawer */}
          <button
            type="button"
            onClick={handleOpenSettings}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
              isVerified
                ? 'bg-blue-950/80 text-blue-300 border border-blue-800 hover:border-blue-600 hover:bg-blue-900/60 shadow-xs'
                : 'bg-amber-950/80 text-amber-300 border border-amber-800 hover:border-amber-600 shadow-xs'
            }`}
            title="Abrir ventana emergente de Configuración del Motor LLM"
          >
            <Cpu className="w-3.5 h-3.5" />
            <span className="font-semibold uppercase text-[11px] font-mono">{provider}</span>
            <span className="text-[10px] text-slate-400 hidden xl:inline">({model})</span>
            {isVerified ? (
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            ) : (
              <AlertCircle className="w-3 h-3 text-amber-400" />
            )}
          </button>

          {/* Engine Status Pill */}
          <StatusPill
            label={isRunning ? 'EXECUTION IN PROGRESS' : 'IDLE / READY'}
            variant={isRunning ? 'active' : 'neutral'}
            icon={<Activity className="w-3.5 h-3.5" />}
            className="text-[10px]"
          />
        </div>
      </div>
    </header>
  );
};
