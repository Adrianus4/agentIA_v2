import React, { useRef, useEffect } from 'react';
import { clsx } from 'clsx';
import { Terminal as TerminalIcon, Copy, Trash2 } from 'lucide-react';
import type { LogEntry } from '../../types/blueprintGraph';

interface RealtimeTerminalProps {
  logs: LogEntry[];
  traceId?: string | null;
  onClearLogs?: () => void;
  className?: string;
}

export const RealtimeTerminal: React.FC<RealtimeTerminalProps> = ({
  logs,
  traceId,
  onClearLogs,
  className,
}) => {
  const terminalBodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (terminalBodyRef.current) {
      terminalBodyRef.current.scrollTop = terminalBodyRef.current.scrollHeight;
    }
  }, [logs]);

  const copyLogsToClipboard = () => {
    const text = logs
      .map((l) => `[${l.timestamp}] [${l.level}] ${l.message}`)
      .join('\n');
    navigator.clipboard.writeText(text);
  };

  const getLevelStyle = (level: LogEntry['level']) => {
    switch (level) {
      case 'ERROR':
        return 'text-rose-400 bg-rose-950/60 border-rose-800/60';
      case 'WARN':
        return 'text-amber-400 bg-amber-950/60 border-amber-800/60';
      case 'SYSTEM':
        return 'text-blue-400 bg-blue-950/60 border-blue-800/60';
      case 'SUCCESS':
        return 'text-emerald-400 bg-emerald-950/60 border-emerald-800/60';
      case 'INFO':
      default:
        return 'text-slate-400 bg-slate-800/60 border-slate-700/60';
    }
  };

  return (
    <div
      className={clsx(
        'rounded-xl border border-slate-800 bg-slate-950 overflow-hidden shadow-2xl font-mono text-xs flex flex-col',
        className
      )}
    >
      {/* Mac Title Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-2">
          {/* Mac Window Controls */}
          <div className="flex items-center gap-1.5 mr-2">
            <span className="w-3 h-3 rounded-full bg-rose-500 inline-block opacity-80" />
            <span className="w-3 h-3 rounded-full bg-amber-500 inline-block opacity-80" />
            <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block opacity-80" />
          </div>
          <div className="flex items-center gap-1.5 text-slate-300 font-semibold">
            <TerminalIcon className="w-3.5 h-3.5 text-blue-400" />
            <span>AgentIA Execution Console</span>
          </div>
          {traceId && (
            <span className="ml-2 px-2 py-0.5 rounded text-[10px] bg-slate-800 text-blue-300 border border-slate-700 truncate max-w-[200px]" title={traceId}>
              {traceId}
            </span>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 text-slate-400">
          <button
            onClick={copyLogsToClipboard}
            className="hover:text-white p-1 rounded hover:bg-slate-800 transition-colors"
            title="Copy logs"
          >
            <Copy className="w-3.5 h-3.5" />
          </button>
          {onClearLogs && (
            <button
              onClick={onClearLogs}
              className="hover:text-rose-400 p-1 rounded hover:bg-slate-800 transition-colors"
              title="Clear terminal"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Terminal Body */}
      <div
        ref={terminalBodyRef}
        className="p-4 h-80 overflow-y-auto space-y-1.5 text-slate-200 select-text"
      >
        {logs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-center gap-2">
            <TerminalIcon className="w-8 h-8 opacity-40" />
            <p>Waiting for orchestrator execution logs...</p>
            <p className="text-[11px] text-slate-600">
              Submit a blueprint above to trigger the LangGraph state machine.
            </p>
          </div>
        ) : (
          logs.map((log) => (
            <div key={log.id} className="flex items-start gap-2.5 leading-relaxed hover:bg-slate-900/40 px-1 rounded">
              <span className="text-slate-600 select-none text-[11px] font-mono shrink-0">
                {log.timestamp}
              </span>
              <span
                className={clsx(
                  'px-1.5 py-0.2 rounded text-[10px] uppercase font-bold border shrink-0',
                  getLevelStyle(log.level)
                )}
              >
                {log.level}
              </span>
              <span className="text-slate-300 break-all">{log.message}</span>
            </div>
          ))
        )}
      </div>

      {/* Terminal Status Footer */}
      <div className="px-4 py-1.5 bg-slate-900/80 border-t border-slate-800 text-[11px] text-slate-500 flex items-center justify-between">
        <span>Log lines: {logs.length}</span>
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping inline-block" />
          Stream Active
        </span>
      </div>
    </div>
  );
};
