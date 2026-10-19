import React, { useState } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  Zap,
} from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { Card } from '../components/common/Card';
import type { SastFinding } from '../types/studio';

export const SecurityQualityView: React.FC = () => {
  const { activeSession } = useStudio();

  if (!activeSession) {
    return (
      <div className="text-center py-12 text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
        <ShieldCheck className="w-12 h-12 mx-auto mb-3 text-slate-500" />
        <h3 className="text-base font-bold text-white">No hay un microservicio seleccionado</h3>
      </div>
    );
  }

  const [findings] = useState<SastFinding[]>([

    {
      id: 'FIND-001',
      rule_id: 'SEC-SQLI-01',
      severity: 'LOW',
      category: 'Inyección SQL',
      file: 'PanacheEntityBase.java',
      line: 42,
      message: 'Uso de parámetros nombrados parametrizados verificado.',
      remediation: 'Utilizar siempre métodos tipados find("name", name) de Panache.',
    },
    {
      id: 'FIND-002',
      rule_id: 'SEC-JWT-02',
      severity: 'LOW',
      category: 'Autenticación',
      file: 'SecurityFilter.java',
      line: 18,
      message: 'Cabeceras Authorization validadas contra políticas de seguridad.',
      remediation: 'Mantener validación de firma asimétrica RS256.',
    },
  ]);

  const [remediatedIds, setRemediatedIds] = useState<Set<string>>(new Set());

  const handleRemediate = (id: string) => {
    setRemediatedIds((prev) => new Set(prev).add(id));
  };

  return (
    <div className="space-y-6">
      <Card
        title={
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <span>Etapa 4: Calidad de Código & Auditoría de Seguridad SAST</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              POLÍTICA SIMULADA / QUALITY GATE DEMO
            </span>
          </div>
        }
        subtitle="Simulación de Quality Gate corporativo (SpotBugs & OWASP). Las verificaciones herméticas y aserciones de compilación reales se ejecutan en el Monitor Live."

      >
        <div className="space-y-6">
          {/* Top Metric Indicators */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Quality Score</span>
              <div className="text-2xl font-black text-emerald-400">98 / 100</div>
              <span className="text-[10px] text-emerald-500 font-semibold">Quality Gate Aprobado</span>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Secretos Hardcodeados</span>
              <div className="text-2xl font-black text-white">0</div>
              <span className="text-[10px] text-slate-400">Principio VI garantizado</span>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">CVEs Críticos</span>
              <div className="text-2xl font-black text-white">0</div>
              <span className="text-[10px] text-slate-400">Dependencias Quarkus 3.x al día</span>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Cobertura de Tests</span>
              <div className="text-2xl font-black text-blue-400">88.5%</div>
              <span className="text-[10px] text-slate-400">QuarkusTest & Mockito</span>
            </div>
          </div>

          {/* SAST Findings Table */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <span className="text-xs font-bold text-slate-200 block">
              Hallazgos de Auditoría Estática (SpotBugs & OWASP)
            </span>

            <div className="space-y-2">
              {findings.map((f) => {
                const isRemediated = remediatedIds.has(f.id);
                return (
                  <div
                    key={f.id}
                    className="p-3 rounded-lg bg-slate-900 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-950 text-blue-300 border border-blue-900">
                          {f.rule_id}
                        </span>
                        <span className="font-bold text-white">{f.category}</span>
                        <span className="text-[11px] font-mono text-slate-400">({f.file}:{f.line})</span>
                      </div>
                      <p className="text-[11px] text-slate-300">{f.message}</p>
                    </div>

                    <div>
                      {isRemediated ? (
                        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-emerald-950 text-emerald-300 border border-emerald-800 text-[11px] font-bold">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Remediado
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleRemediate(f.id)}
                          className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-[11px] font-semibold transition-colors"
                        >
                          <Zap className="w-3 h-3 text-amber-400" />
                          <span>1-Click Remediation</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};
