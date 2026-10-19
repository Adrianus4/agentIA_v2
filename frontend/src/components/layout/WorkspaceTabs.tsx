import React from 'react';
import {
  Activity,
  FileInput,
  Layers,
  LayoutDashboard,
  Settings2,
} from 'lucide-react';

export type WorkspaceTab = 'overview' | 'blueprints' | 'llm' | 'monitor';

interface WorkspaceTabsProps {
  activeTab: WorkspaceTab;
  onChange: (tab: WorkspaceTab) => void;
}

const tabs = [
  { key: 'blueprints', label: 'Blueprints', icon: FileInput },
  { key: 'overview', label: 'Resumen', icon: LayoutDashboard },
  { key: 'llm', label: 'Motor LLM', icon: Settings2 },
  { key: 'monitor', label: 'Monitor Live', icon: Activity },
] as const;

export const WorkspaceTabs: React.FC<WorkspaceTabsProps> = ({ activeTab, onChange }) => (
  <nav
    aria-label="Workspace navigation"
    className="flex gap-2 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/70 p-2"
  >
    {tabs.map(({ key, label, icon: Icon }) => (
      <button
        key={key}
        type="button"
        aria-current={activeTab === key ? 'page' : undefined}
        onClick={() => onChange(key)}
        className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition ${
          activeTab === key
            ? 'bg-blue-600 text-white shadow'
            : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
        }`}
      >
        <Icon className="h-4 w-4" />
        {label}
      </button>
    ))}
    <span className="ml-auto hidden items-center gap-1 px-2 text-[10px] text-slate-600 lg:flex">
      <Layers className="h-3 w-3" />
      legacy workflow
    </span>
  </nav>
);
