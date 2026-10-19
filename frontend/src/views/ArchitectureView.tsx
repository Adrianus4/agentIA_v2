import React, { useState } from 'react';
import {
  Layers,
  ArrowRight,
  Boxes,
  Globe,
  Database,
  Radio,
} from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { Card } from '../components/common/Card';


export const ArchitectureView: React.FC = () => {
  const { activeSession, setActiveTab } = useStudio();

  if (!activeSession) {
    return (
      <div className="text-center py-12 text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
        <Layers className="w-12 h-12 mx-auto mb-3 text-slate-500" />
        <h3 className="text-base font-bold text-white">No hay un microservicio seleccionado</h3>
      </div>
    );
  }

  const [activeTabMode, setActiveTabMode] = useState<'diagram' | 'contracts'>('diagram');

  return (
    <div className="space-y-6">
      {/* Top Architecture Card */}
      <Card
        title={
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-400" />
            <span>Fase 2: Arquitectura Hexagonal y Puertos & Adaptadores</span>
          </div>
        }
        subtitle="Estructura modular limpia: desacoplamiento entre el núcleo de dominio y la infraestructura Quarkus 3.x"
        action={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTabMode('diagram')}
              className={`py-1.5 px-3 rounded-lg text-xs font-semibold transition-all ${
                activeTabMode === 'diagram'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Diagrama de Capas
            </button>
            <button
              type="button"
              onClick={() => setActiveTabMode('contracts')}
              className={`py-1.5 px-3 rounded-lg text-xs font-semibold transition-all ${
                activeTabMode === 'contracts'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Contratos REST ({activeSession.contracts.length})
            </button>
          </div>
        }
      >
        {activeTabMode === 'diagram' ? (
          <div className="space-y-5">
            {/* Visual 4-Tier Hexagonal Flow */}
            <div className="p-5 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
                {/* Layer 1: Inbound Adapters */}
                <div className="p-3.5 rounded-xl bg-slate-900 border border-blue-900/60 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-blue-300">
                    <Globe className="w-4 h-4 text-blue-400" />
                    <span>Inbound Adapters</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    RESTEasy Reactive Endpoints y Filtros JWT
                  </p>
                  <div className="space-y-1 font-mono text-[10px] text-slate-300 pt-1">
                    <div className="p-1.5 rounded bg-slate-950 border border-slate-800 truncate">
                      {activeSession.name.split('-')[0]}Resource.java
                    </div>
                  </div>
                </div>

                {/* Layer 2: Application / Services */}
                <div className="p-3.5 rounded-xl bg-slate-900 border border-indigo-900/60 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-indigo-300">
                    <Boxes className="w-4 h-4 text-indigo-400" />
                    <span>Application Core</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Casos de uso y reglas de orquestación transaccional
                  </p>
                  <div className="space-y-1 font-mono text-[10px] text-slate-300 pt-1">
                    <div className="p-1.5 rounded bg-slate-950 border border-slate-800 truncate">
                      {activeSession.name.split('-')[0]}Service.java
                    </div>
                  </div>
                </div>

                {/* Layer 3: Domain Entities */}
                <div className="p-3.5 rounded-xl bg-slate-900 border border-emerald-900/60 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-emerald-300">
                    <Database className="w-4 h-4 text-emerald-400" />
                    <span>Domain / Panache</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Entidades JPA reactivas PanacheEntityBase
                  </p>
                  <div className="space-y-1 font-mono text-[10px] text-slate-300 pt-1">
                    {activeSession.entities.map((e) => (
                      <div key={e.name} className="p-1.5 rounded bg-slate-950 border border-slate-800 truncate">
                        {e.name}.java
                      </div>
                    ))}
                  </div>
                </div>

                {/* Layer 4: Outbound Infrastructure */}
                <div className="p-3.5 rounded-xl bg-slate-900 border border-amber-900/60 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-amber-300">
                    <Radio className="w-4 h-4 text-amber-400" />
                    <span>Outbound Infra</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    {activeSession.parameters.database} + {activeSession.parameters.messaging}
                  </p>
                  <div className="space-y-1 font-mono text-[10px] text-slate-300 pt-1">
                    <div className="p-1.5 rounded bg-slate-950 border border-slate-800 truncate">
                      {activeSession.name.split('-')[0]}Repository.java
                    </div>
                  </div>
                </div>
              </div>

              {/* Hexagonal Ports Description */}
              <div className="p-3 rounded-xl bg-blue-950/30 border border-blue-900/40 text-xs text-blue-200">
                <strong>Arquitectura Verificada:</strong> El microservicio aísla la lógica de negocio en el núcleo y expone puertos primarios para el API Gateway y puertos secundarios para persistencia en {activeSession.parameters.database} y mensajería en {activeSession.parameters.messaging}.
              </div>
            </div>
          </div>
        ) : (
          /* Contracts Table */
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] font-semibold">
                  <th className="py-2.5 px-3">Método</th>
                  <th className="py-2.5 px-3">Endpoint</th>
                  <th className="py-2.5 px-3">Descripción</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {activeSession.contracts.map((c, idx) => (
                  <tr key={idx} className="hover:bg-slate-900/40">
                    <td className="py-2.5 px-3">
                      <span
                        className={`font-mono font-bold px-2 py-0.5 rounded text-[10px] ${
                          c.method === 'POST'
                            ? 'bg-blue-950 text-blue-300 border border-blue-800'
                            : c.method === 'GET'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : 'bg-amber-950 text-amber-300 border border-amber-800'
                        }`}
                      >
                        {c.method}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono font-semibold text-slate-200">
                      {c.endpoint}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">{c.description}</td>
                    <td className="py-2.5 px-3 font-mono text-emerald-400 font-bold">
                      {c.statusCode}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Next Step Nav */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={() => setActiveTab(3)}
          className="flex items-center gap-2 py-2.5 px-5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md transition-all"
        >
          <span>Continuar a Fase 3: Modelos & SQL</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
