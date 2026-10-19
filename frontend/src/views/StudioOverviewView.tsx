import React, { useState } from 'react';
import {
  Rocket,
  Play,
  Layers,
  Database,
  Sliders,
  ArrowRight,
  Activity,
  FileCode,
  ShieldCheck,
  Server,
  Terminal,
  Cpu,
  Zap,
  Wrench,
  Flag,
} from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { Card } from '../components/common/Card';
import { KpiGrid } from '../components/layout/KpiGrid';
import type { DatabaseEngine, MessagingSystem, RequirementsSize, ExpectedQps, ConsistencyModel } from '../types/studio';

/** Mini pipeline step for the hero diagram */
const PipelineStep: React.FC<{
  step: number;
  label: string;
  sublabel: string;
  icon: React.ComponentType<{ className?: string }>;
  color: 'blue' | 'violet' | 'emerald' | 'amber' | 'slate';
  isLast?: boolean;
}> = ({ step, label, sublabel, icon: Icon, color, isLast = false }) => {
  const palette = {
    blue:    { bg: 'bg-blue-950/50',    ring: 'ring-blue-500/40',    badge: 'bg-blue-500',    text: 'text-blue-300',    arrow: 'text-blue-500/40' },
    violet:  { bg: 'bg-violet-950/50',  ring: 'ring-violet-500/40',  badge: 'bg-violet-500',  text: 'text-violet-300',  arrow: 'text-violet-500/40' },
    emerald: { bg: 'bg-emerald-950/50', ring: 'ring-emerald-500/40', badge: 'bg-emerald-500', text: 'text-emerald-300', arrow: 'text-emerald-500/40' },
    amber:   { bg: 'bg-amber-950/50',   ring: 'ring-amber-500/40',   badge: 'bg-amber-500',   text: 'text-amber-300',   arrow: 'text-amber-500/40' },
    slate:   { bg: 'bg-slate-800/60',   ring: 'ring-slate-600/40',   badge: 'bg-slate-600',   text: 'text-slate-300',   arrow: 'text-slate-600/40' },
  } as const;
  const c = palette[color];
  return (
    <div className="flex items-center gap-1 flex-1 min-w-[90px]">
      <div className={`flex-1 flex flex-col items-center gap-1.5 px-2 py-3 rounded-xl ring-1 ${c.bg} ${c.ring}`}>
        <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black text-white ${c.badge}`}>
          {step}
        </span>
        <div className={`p-1.5 rounded-lg bg-white/5 ${c.text}`}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="text-center">
          <p className={`text-[10px] font-bold ${c.text} leading-tight`}>{label}</p>
          <p className="text-[9px] text-slate-500 mt-0.5 font-mono leading-tight">{sublabel}</p>
        </div>
      </div>
      {!isLast && (
        <ArrowRight className={`w-3.5 h-3.5 shrink-0 ${c.arrow}`} />
      )}
    </div>
  );
};


export const StudioOverviewView: React.FC = () => {
  const {
    activeSessionId,
    activeSession,
    setActiveTab,
    createSession,
    executeLangGraph,
    isExecuting,
  } = useStudio();

  // Quick Start Form state
  const [serviceName, setServiceName] = useState('');
  const [database, setDatabase] = useState<DatabaseEngine>('POSTGRESQL');
  const [messaging, setMessaging] = useState<MessagingSystem>('KAFKA');
  const [requirementsSize, setRequirementsSize] = useState<RequirementsSize>('MEDIUM');
  const [expectedQps, setExpectedQps] = useState<ExpectedQps>('1000');
  const [dataConsistency, setDataConsistency] = useState<ConsistencyModel>('ACID');
  const [prompt, setPrompt] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleQuickStart = async (autoRun: boolean) => {
    if (!serviceName.trim() || !prompt.trim()) {
      setErrorMsg('Por favor complete el nombre del microservicio y la descripción de requisitos.');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      await createSession({
        name: serviceName.trim(),
        description: prompt.trim(),
        parameters: {
          database,
          messaging,
          requirementsSize,
          expectedQps,
          dataConsistency,
          buildTool: 'MAVEN',
          workspaceDir: `/tmp/agentia-workspace/${serviceName.trim()}`,
        },
        autoRun,
      });
    } catch (err: any) {
      setErrorMsg(err.message || 'Error al inicializar el microservicio.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* If No Active Session: Show Quick Start Initializer */}
      {!activeSessionId || !activeSession ? (
        <div className="bg-gradient-to-r from-blue-950 via-slate-900 to-slate-950 rounded-2xl p-6 sm:p-8 text-white border border-blue-900/60 shadow-xl relative overflow-hidden">
          <div className="max-w-3xl space-y-5 relative z-10">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-400/30">
                <Rocket className="w-3.5 h-3.5" />
                <span>⚡ Nuevo Microservicio (Inicio Rápido 1-Click)</span>
              </span>
            </div>

            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Generación Autónoma de Microservicio Quarkus 3.x
            </h2>

            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Configure los parámetros de arquitectura y requisitos de negocio para iniciar el ciclo de desarrollo asistido o ejecutar la síntesis autónoma con LangGraph.
            </p>

            {/* ── Pipeline Hero Diagram ── */}
            <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3 backdrop-blur-sm">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2.5 px-1">
                Pipeline de generación autónoma
              </p>
              <div className="flex items-stretch gap-1 overflow-x-auto pb-0.5">
                <PipelineStep step={1} label="Validate"  sublabel="blueprint / BDD"  icon={ShieldCheck} color="blue"    />
                <PipelineStep step={2} label="Generate"  sublabel="Jinja2 → .java"   icon={Cpu}         color="violet"  />
                <PipelineStep step={3} label="Verify"    sublabel="mvn test (JDK 21)" icon={Zap}         color="emerald" />
                <PipelineStep step={4} label="Repair"    sublabel="AST patch + LLM"  icon={Wrench}      color="amber"   />
                <PipelineStep step={5} label="Outcome"   sublabel="SUCCESS / NO_FIX"  icon={Flag}        color="slate"   isLast />
              </div>
              <p className="text-[9px] text-slate-600 font-mono mt-2 px-1">
                El reparador itera máx. 3 veces (Principio V) antes de una parada constitucional NO_FIX.
              </p>
            </div>

            {errorMsg && (
              <div className="p-3.5 rounded-xl bg-rose-950/60 border border-rose-800 text-xs text-rose-200">
                {errorMsg}
              </div>
            )}


            <div className="space-y-4 pt-1">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Nombre del Microservicio
                  </label>
                  <input
                    type="text"
                    value={serviceName}
                    onChange={(e) => setServiceName(e.target.value)}
                    placeholder="ej. order-fulfillment-service"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Motor de Base de Datos
                  </label>
                  <select
                    value={database}
                    onChange={(e) => setDatabase(e.target.value as DatabaseEngine)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  >
                    <option value="POSTGRESQL">PostgreSQL 16 (Producción Panache JPA)</option>
                    <option value="MYSQL">MySQL 8.0</option>
                    <option value="H2">H2 In-Memory (Test hermético)</option>
                    <option value="NONE">Sin Base de Datos Relacional</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Broker de Mensajería / Eventos
                  </label>
                  <select
                    value={messaging}
                    onChange={(e) => setMessaging(e.target.value as MessagingSystem)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  >
                    <option value="KAFKA">Apache Kafka (SmallRye Reactive)</option>
                    <option value="RABBITMQ">RabbitMQ AMQP</option>
                    <option value="NONE">Sin Mensajería</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Volumen de Requisitos
                  </label>
                  <select
                    value={requirementsSize}
                    onChange={(e) => setRequirementsSize(e.target.value as RequirementsSize)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  >
                    <option value="LOW">Bajo (1 - 2 entidades)</option>
                    <option value="MEDIUM">Medio (3 - 5 entidades)</option>
                    <option value="HIGH">Alto (6 - 10 entidades)</option>
                    <option value="ENTERPRISE">Enterprise (&gt;10 entidades)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Rendimiento Esperado (QPS)
                  </label>
                  <select
                    value={expectedQps}
                    onChange={(e) => setExpectedQps(e.target.value as ExpectedQps)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  >
                    <option value="100">Estándar (~100 QPS)</option>
                    <option value="1000">Alto Rendimiento (~1,000 QPS)</option>
                    <option value="5000+">Ultra Crítico (&gt;5,000 QPS)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Modelo de Consistencia
                  </label>
                  <select
                    value={dataConsistency}
                    onChange={(e) => setDataConsistency(e.target.value as ConsistencyModel)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  >
                    <option value="ACID">Fuerte (ACID Transaccional)</option>
                    <option value="EVENTUAL">Eventual (Saga / Event-Driven)</option>
                  </select>
                </div>
              </div>


              {/* Natural Language Prompt */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Descripción de Requisitos / Prompt de Negocio
                </label>
                <textarea
                  rows={3}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describa el objetivo de negocio, entidades principales, validaciones y reglas requeridas..."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs leading-relaxed focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>

              {/* Action Buttons */}
              <div className="pt-2">
                <p className="text-[11px] text-blue-300/80 mb-3 flex items-center gap-1.5">
                  <span>ℹ️</span>
                  <span>
                    <strong>Modo Asistido:</strong> Le guía fase por fase (Requisitos ➔ Arquitectura ➔ Modelos ➔ Monitor) con observabilidad completa de cada agente.
                  </span>
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => handleQuickStart(false)}
                    disabled={isSubmitting || !serviceName.trim() || !prompt.trim()}
                    className="flex items-center justify-center gap-2 py-3 px-5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <span>👣 Iniciar Modo Asistido (Fase por Fase)</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleQuickStart(true)}
                    disabled={isSubmitting || !serviceName.trim() || !prompt.trim()}
                    className="flex items-center justify-center gap-2 py-3 px-5 rounded-xl text-xs font-bold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <Play className="w-3.5 h-3.5 fill-current text-emerald-400" />
                    <span>⚡ Crear y Ejecutar Pipeline LangGraph</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Active Microservice Overview */
        <div className="space-y-6">
          {/* Executive Header Banner */}
          <div className="bg-gradient-to-r from-blue-950 via-slate-900 to-slate-950 rounded-2xl p-6 text-white border border-blue-900/60 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
                  Microservicio Activo
                </span>
                <h2 className="text-2xl font-black tracking-tight text-white mt-0.5">
                  ⚡ {activeSession.name || activeSession.specName}
                </h2>
                <p className="text-xs text-slate-400 mt-1 max-w-2xl">
                  {activeSession.description}
                </p>
              </div>

              <div className="flex items-center gap-2 self-start sm:self-center">
                <button
                  type="button"
                  onClick={() => executeLangGraph()}
                  disabled={isExecuting}
                  className="flex items-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md transition-all disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>{isExecuting ? 'Ejecutando...' : 'Re-ejecutar LangGraph'}</span>
                </button>
              </div>
            </div>

            {/* Architecture Metadata Badges */}
            <div className="flex flex-wrap items-center gap-2.5 pt-4 mt-4 border-t border-slate-800/80 text-xs">
              <span className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 font-mono text-[11px]">
                DB: {activeSession.parameters.database}
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 font-mono text-[11px]">
                Messaging: {activeSession.parameters.messaging}
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 font-mono text-[11px]">
                QPS: ~{activeSession.parameters.expectedQps}
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 font-mono text-[11px]">
                Consistency: {activeSession.parameters.dataConsistency}
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 font-mono text-[11px]">
                Build: {activeSession.parameters.buildTool}
              </span>
            </div>
          </div>

          {/* 4-KPI Grid */}
          <KpiGrid
            currentPhase={activeSession.status === 'RUNNING' ? 'SANDBOX_BUILD' : 'TERMINAL'}
            sandboxStatus={
              activeSession.status === 'SUCCESS' || activeSession.status === 'COMPLETED'
                ? 'PASSED'
                : activeSession.status === 'RUNNING'
                ? 'RUNNING'
                : 'FAILED'
            }
            repairIteration={activeSession.repairAttempts}
            maxRepairs={3}
          />

          {/* Observability Roadmap / Stage Navigator */}
          <Card
            title="Navegación Asistida por Etapas del Ciclo de Vida"
            subtitle="Inspeccione en profundidad los artefactos generados por cada agente en el grafo"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {[
                { tab: 1, title: '1. Requisitos & BDD', desc: 'Parámetros Quarkus, historias Given/When/Then y entidades detectadas', icon: Sliders },
                { tab: 2, title: '2. Arquitectura', desc: 'Diagrama hexagonal 4 capas, puertos, adaptadores y contratos REST', icon: Layers },
                { tab: 3, title: '3. Modelos & SQL', desc: 'Entidades Panache JPA, campos, claves y scripts DDL schema.sql', icon: Database },
                { tab: 4, title: '4. Blueprints', desc: 'Esquema SpecKit formal, validación JSON y configuración de generación', icon: FileCode },
                { tab: 5, title: '5. Monitor Live', desc: 'Visualizador de 4 nodos LangGraph, bounded loops y streaming console', icon: Activity },
                { tab: 6, title: '6. Código & Fix', desc: 'Explorador de archivos Java, pom.xml y parches quirúrgicos AST', icon: Terminal },
                { tab: 7, title: '7. Calidad SAST', desc: 'Auditoría estática, vulnerabilidades SpotBugs y 1-Click Remediation', icon: ShieldCheck },
                { tab: 8, title: '8. DevOps & Demo', desc: 'Manifiestos docker-compose y consola interactiva de prueba REST', icon: Server },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.tab}
                    type="button"
                    onClick={() => setActiveTab(item.tab)}
                    className="p-3.5 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-800/80 hover:border-slate-700 text-left transition-all group flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2 font-bold text-xs text-white group-hover:text-blue-300">
                        <Icon className="w-4 h-4 text-blue-400" />
                        <span>{item.title}</span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                        {item.desc}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 text-[10px] font-semibold text-blue-400 mt-2.5">
                      <span>Ver detalles</span>
                      <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                    </div>
                  </button>
                );
              })}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
