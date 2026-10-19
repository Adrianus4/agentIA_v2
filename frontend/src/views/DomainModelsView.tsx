import React, { useState } from 'react';
import {
  Database,
  Table,
  Key,
  ArrowRight,
  Copy,
  Check,
} from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { Card } from '../components/common/Card';


export const DomainModelsView: React.FC = () => {
  const { activeSession, setActiveTab } = useStudio();

  if (!activeSession) {
    return (
      <div className="text-center py-12 text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
        <Database className="w-12 h-12 mx-auto mb-3 text-slate-500" />
        <h3 className="text-base font-bold text-white">No hay un microservicio seleccionado</h3>
      </div>
    );
  }

  const [activeTabMode, setActiveTabMode] = useState<'entities' | 'sql'>('entities');
  const [selectedEntityIdx, setSelectedEntityIdx] = useState(0);
  const [copied, setCopied] = useState(false);

  const selectedEntity = activeSession.entities[selectedEntityIdx] || activeSession.entities[0];

  const generateSchemaSql = () => {
    const db = activeSession.parameters.database;
    const lines: string[] = [
      `-- ========================================================`,
      `-- AgentIA v2 Generated DDL Schema for Quarkus 3.x`,
      `-- Database Engine: ${db}`,
      `-- Microservice: ${activeSession.name}`,
      `-- ========================================================`,
      ``,
    ];

    activeSession.entities.forEach((entity) => {
      lines.push(`CREATE TABLE IF NOT EXISTS ${entity.tableName} (`);
      const fieldDefs = entity.fields.map((f) => {
        let sqlType = 'VARCHAR(255)';
        if (f.primaryKey) sqlType = db === 'POSTGRESQL' ? 'BIGSERIAL PRIMARY KEY' : 'BIGINT PRIMARY KEY AUTO_INCREMENT';
        else if (f.type === 'Long') sqlType = 'BIGINT';
        else if (f.type === 'Integer') sqlType = 'INTEGER';
        else if (f.type === 'BigDecimal') sqlType = 'NUMERIC(12, 2)';
        else if (f.type === 'Instant') sqlType = 'TIMESTAMP WITH TIME ZONE';
        else if (f.type === 'Boolean') sqlType = 'BOOLEAN';

        const nullableStr = f.nullable === false ? ' NOT NULL' : '';
        return `    ${f.name.replace(/([A-Z])/g, '_$1').toLowerCase()} ${sqlType}${nullableStr}`;
      });
      lines.push(fieldDefs.join(',\n'));
      lines.push(`);\n`);
    });

    return lines.join('\n');
  };

  const schemaSql = generateSchemaSql();

  const handleCopySql = () => {
    navigator.clipboard.writeText(schemaSql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Top Models Card */}
      <Card
        title={
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-blue-400" />
            <span>Fase 3: Modelos de Dominio Panache JPA & DDL SQL</span>
          </div>
        }
        subtitle="Entidades reactivas de Quarkus con mapeo relacional a Hibernate Panache y scripts de migración"
        action={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTabMode('entities')}
              className={`py-1.5 px-3 rounded-lg text-xs font-semibold transition-all ${
                activeTabMode === 'entities'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Entidades JPA ({activeSession.entities.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTabMode('sql')}
              className={`py-1.5 px-3 rounded-lg text-xs font-semibold transition-all ${
                activeTabMode === 'sql'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Esquema schema.sql
            </button>
          </div>
        }
      >
        {activeTabMode === 'entities' ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Entity List */}
            <div className="space-y-2">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                Entidades Panache
              </span>
              {activeSession.entities.map((ent, idx) => (
                <button
                  key={ent.name}
                  type="button"
                  onClick={() => setSelectedEntityIdx(idx)}
                  className={`w-full text-left p-3 rounded-xl border text-xs transition-all flex items-center justify-between ${
                    idx === selectedEntityIdx
                      ? 'bg-blue-950/60 border-blue-600 text-blue-200 shadow-xs font-bold'
                      : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Table className="w-4 h-4 text-blue-400" />
                    <span>{ent.name}</span>
                  </div>
                  <span className="font-mono text-[10px] text-slate-500">{ent.tableName}</span>
                </button>
              ))}
            </div>

            {/* Field Details */}
            {selectedEntity && (
              <div className="md:col-span-2 p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div>
                    <h4 className="text-sm font-bold text-white flex items-center gap-2">
                      <span>{selectedEntity.name}</span>
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-900 text-slate-400 font-mono">
                        tabla: {selectedEntity.tableName}
                      </span>
                    </h4>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      {selectedEntity.description || 'Entidad persistente administrada por Panache'}
                    </p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] font-semibold">
                        <th className="py-2 px-3">Campo</th>
                        <th className="py-2 px-3">Tipo Java</th>
                        <th className="py-2 px-3">Clave</th>
                        <th className="py-2 px-3">Validaciones</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                      {selectedEntity.fields.map((f, fIdx) => (
                        <tr key={fIdx} className="hover:bg-slate-900/50">
                          <td className="py-2.5 px-3 text-slate-200 font-semibold">{f.name}</td>
                          <td className="py-2.5 px-3 text-blue-300">{f.type}</td>
                          <td className="py-2.5 px-3">
                            {f.primaryKey ? (
                              <span className="inline-flex items-center gap-1 text-[10px] text-amber-400 font-bold">
                                <Key className="w-3 h-3" /> PK
                              </span>
                            ) : (
                              <span className="text-slate-500">-</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-[10px] text-emerald-400">
                            {f.validationRules && f.validationRules.length > 0 ? (
                              f.validationRules.join(', ')
                            ) : (
                              <span className="text-slate-500">Ninguna</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* SQL Tab */
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-mono">
                schema.sql ({activeSession.parameters.database})
              </span>
              <button
                type="button"
                onClick={handleCopySql}
                className="flex items-center gap-1.5 py-1 px-2.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:text-white transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copiado' : 'Copiar DDL'}</span>
              </button>
            </div>
            <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-emerald-300 font-mono text-xs overflow-x-auto leading-relaxed">
              {schemaSql}
            </pre>
          </div>
        )}
      </Card>

      {/* Next Step Nav */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={() => setActiveTab(4)}
          className="flex items-center gap-2 py-2.5 px-5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md transition-all"
        >
          <span>Continuar a Fase 4: Blueprints & SpecKit</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
