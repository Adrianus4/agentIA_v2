import React from 'react';
import {
  FileText,
  Layers,
  Code,
  ShieldCheck,
  Server,
} from 'lucide-react';
import { useStudio } from '../../context/StudioContext';

export interface TabItem {
  id: number;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const WORKSPACE_TABS: TabItem[] = [
  { id: 0, label: '1. Especificación', icon: FileText },
  { id: 1, label: '2. Arquitectura & Modelos', icon: Layers },
  { id: 2, label: '3. Código & Pruebas', icon: Code },
  { id: 3, label: '4. Verificación & Calidad', icon: ShieldCheck },
  { id: 4, label: '5. DevOps & Despliegue', icon: Server },
];

interface ResponsiveTabGridProps {
  activeTab?: number;
  onTabChange?: (tab: number) => void;
}

export const ResponsiveTabGrid: React.FC<ResponsiveTabGridProps> = ({
  activeTab: propActiveTab,
  onTabChange,
}) => {
  const { activeTab: contextActiveTab, setActiveTab: setContextActiveTab } = useStudio();

  const activeTab = propActiveTab !== undefined ? propActiveTab : contextActiveTab;
  const setActiveTab = onTabChange || setContextActiveTab;

  return (
    <nav
      aria-label="Navegación de etapas del ciclo de vida"
      className="w-full bg-slate-900/80 p-2 rounded-2xl border border-slate-800 shadow-md backdrop-blur-md"
    >
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
        {WORKSPACE_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-xs font-semibold transition-all ${
                isActive
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20 font-bold border border-blue-400/40 ring-1 ring-blue-400/30'
                  : 'bg-slate-950/70 text-slate-300 hover:text-white hover:bg-slate-800/80 border border-slate-850'
              }`}
            >
              <Icon
                className={`w-4 h-4 shrink-0 ${
                  isActive ? 'text-white' : 'text-slate-400'
                }`}
              />
              <span className="truncate">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
