import React, { useState } from 'react';
import {
  PlusCircle,
  RefreshCw,
  Box,
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  ChevronRight,
  Search,
  Trash2,
  Layers,
} from 'lucide-react';
import { useStudio } from '../../context/StudioContext';

export const Sidebar: React.FC = () => {
  const {
    sessions,
    activeSessionId,
    selectSession,
    startNewService,
    refreshSessions,
    deleteSession,
  } = useStudio();

  const [searchQuery, setSearchQuery] = useState('');
  const isCreatingNew = !activeSessionId;

  const filteredSessions = sessions.filter((s) =>
    (s.name || s.specName || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
      case 'SUCCESS':
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />;
      case 'RUNNING':
        return <RefreshCw className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" />;
      case 'QUEUED':
        return <Clock className="w-3.5 h-3.5 text-amber-400 shrink-0" />;
      case 'NO_FIX':
      case 'BLOCKED':
        return <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />;
      case 'FAILED':
      case 'ERROR':
        return <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />;
      default:
        return <Box className="w-3.5 h-3.5 text-slate-500 shrink-0" />;
    }
  };

  return (
    <aside
      aria-label="Barra lateral de microservicios"
      className="w-64 sm:w-72 bg-slate-950 border-r border-slate-800 flex flex-col shrink-0 z-20 h-screen sticky top-0 text-slate-100"
    >
      {/* Brand Header with TCS Logo */}
      <div className="h-16 px-4 border-b border-slate-800 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <img
            src="/tcs-logo-light.png"
            alt="TCS Logo"
            className="h-7 w-auto object-contain select-none"
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />
          <div className="truncate">
            <span className="text-xs font-black tracking-tight text-white block">
              AgentIA <span className="text-blue-400 font-mono">v2</span>
            </span>
            <span className="text-[10px] text-slate-400 block truncate">
              Quarkus Studio
            </span>
          </div>
        </div>
      </div>

      {/* Action: New Microservice CTA */}
      <div className="p-3 border-b border-slate-800/80">
        <button
          onClick={startNewService}
          className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold text-white transition-all focus:outline-none ${
            isCreatingNew
              ? 'bg-blue-600 ring-2 ring-blue-400 shadow-lg font-bold'
              : 'bg-blue-600/90 hover:bg-blue-600 active:bg-blue-700 shadow-sm'
          }`}
        >
          <PlusCircle className="w-4 h-4" />
          <span>+ Nuevo Microservicio</span>
        </button>
      </div>

      {/* Search Filter */}
      <div className="px-3 pt-3 pb-1">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filtrar microservicios..."
            className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none placeholder:text-slate-500"
          />
        </div>
      </div>

      {/* Sessions List Header */}
      <div className="px-4 py-2.5 flex items-center justify-between text-xs">
        <span className="text-[11px] font-semibold tracking-wider uppercase text-slate-400">
          Microservicios ({sessions.length})
        </span>
        <button
          onClick={() => void refreshSessions()}
          className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          title="Actualizar listado de sesiones"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Sessions Items Scroll Area */}
      <div className="flex-1 overflow-y-auto px-2 space-y-1 py-1">
        {filteredSessions.length === 0 ? (
          <div className="text-center py-8 px-4 text-xs text-slate-500">
            {searchQuery
              ? 'No se encontraron resultados.'
              : 'No hay microservicios registrados. Inicie uno con el botón superior.'}
          </div>
        ) : (
          filteredSessions.map((sess) => {
            const isSelected = sess.id === activeSessionId || sess.sessionId === activeSessionId;
            return (
              <div
                key={sess.id}
                className={`group relative rounded-xl transition-all border ${
                  isSelected
                    ? 'bg-blue-950/40 border-blue-800 shadow-sm'
                    : 'bg-transparent border-transparent hover:bg-slate-900 hover:border-slate-800'
                }`}
              >
                <button
                  type="button"
                  onClick={() => selectSession(sess.id)}
                  className="w-full text-left p-2.5 text-xs flex items-center justify-between pr-8"
                >
                  <div className="flex items-center gap-2.5 truncate min-w-0">
                    {getStatusBadge(sess.status)}
                    <div className="truncate">
                      <div
                        className={`font-semibold truncate text-xs ${
                          isSelected ? 'text-blue-300' : 'text-slate-200 group-hover:text-white'
                        }`}
                      >
                        {sess.name || sess.specName || 'app-service'}
                      </div>
                      <div className="text-[10px] text-slate-500 flex items-center gap-1.5 mt-0.5">
                        <span className="font-mono">{sess.parameters?.database || 'DB'}</span>
                        <span>·</span>
                        <span>{sess.currentLifecyclePhase || 'FASE ' + sess.currentStage}</span>
                        <span>·</span>
                        <span>{sess.completionPercentage || 0}%</span>
                      </div>
                    </div>
                  </div>

                  <ChevronRight
                    className={`w-3.5 h-3.5 shrink-0 transition-transform ${
                      isSelected ? 'text-blue-400 translate-x-0.5' : 'text-slate-600'
                    }`}
                  />
                </button>

                {/* Quick Delete action button */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSession(sess.id);
                  }}
                  title="Eliminar microservicio"
                  className="absolute right-2 top-3 opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 transition-opacity"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            );
          })
        )}
      </div>

      {/* Footer Info */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/90 text-[11px] text-slate-500">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Layers className="w-3 h-3 text-blue-400" />
            <span>AgentIA v2 Studio</span>
          </div>
          <span className="font-mono text-emerald-400 font-semibold">TCS Global</span>
        </div>
      </div>
    </aside>
  );
};
