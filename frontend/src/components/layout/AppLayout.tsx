import React from 'react';
import { Terminal } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { SettingsDrawer } from './SettingsDrawer';
import { ResponsiveTabGrid } from './ResponsiveTabGrid';
import { ExecutionDrawer } from './ExecutionDrawer';
import { WorkspaceRouter } from '../../views/WorkspaceRouter';
import { useStudio } from '../../context/StudioContext';

export const AppLayout: React.FC = () => {
  const { isTelemetryDrawerOpen, toggleTelemetryDrawer } = useStudio();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans">
      {/* Left Persistent Sidebar */}
      <Sidebar />

      {/* Main Studio Viewport */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Top Header */}
        <Header />

        {/* 5-Stage Lifecycle Navigation Bar (Fixed directly beneath Header) */}
        <div className="bg-slate-950 border-b border-slate-800/80 px-4 sm:px-6 py-2.5 shrink-0 z-20">
          <div className="max-w-7xl mx-auto">
            <ResponsiveTabGrid />
          </div>
        </div>

        {/* Scrollable Center Canvas */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Active Stage View Canvas */}
            <WorkspaceRouter />
          </div>
        </main>

        {/* Global Footer */}
        <footer className="border-t border-slate-900 bg-slate-950 py-2.5 px-6 flex items-center justify-between text-xs text-slate-500 font-mono shrink-0">
          <span>AgentIA v2 • Spec-Driven Development (SDD) • Quarkus 3.x Multi-Stage Observable Studio</span>
          <button
            type="button"
            onClick={toggleTelemetryDrawer}
            className="flex items-center gap-1.5 text-slate-400 hover:text-blue-400 transition-colors cursor-pointer text-xs"
          >
            <Terminal className="w-3.5 h-3.5 text-blue-400" />
            <span>Terminal / Estado de Ejecución {isTelemetryDrawerOpen ? '(Abierto)' : '(Oculto)'}</span>
          </button>
        </footer>
      </div>

      {/* Collapsible Telemetry & Execution State Drawer */}
      <ExecutionDrawer />

      {/* Pop-up Window / Slide-over Drawer for LLM Engine Selector */}
      <SettingsDrawer />
    </div>
  );
};
