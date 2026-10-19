import React, { useState } from 'react';
import {
  FileText,
  Sliders,
  Plus,
  Trash2,
  CheckCircle2,
  ArrowRight,
  Tag,
} from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { Card } from '../components/common/Card';

import type {
  DatabaseEngine,
  MessagingSystem,
  RequirementsSize,
  ExpectedQps,
  ConsistencyModel,
  BddStory,
} from '../types/studio';

export const RequirementsView: React.FC = () => {
  const { activeSession, updateActiveSession, setActiveTab } = useStudio();

  if (!activeSession) {
    return (
      <div className="text-center py-12 text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
        <FileText className="w-12 h-12 mx-auto mb-3 text-slate-500" />
        <h3 className="text-base font-bold text-white">No hay un microservicio seleccionado</h3>
        <p className="text-xs text-slate-400 mt-1">
          Seleccione un microservicio en la barra lateral o cree uno nuevo en la pestaña Resumen.
        </p>
      </div>
    );
  }

  const [promptText, setPromptText] = useState(activeSession.description);
  const [db, setDb] = useState<DatabaseEngine>(activeSession.parameters.database);
  const [messaging, setMessaging] = useState<MessagingSystem>(activeSession.parameters.messaging);
  const [size, setSize] = useState<RequirementsSize>(activeSession.parameters.requirementsSize);
  const [qps, setQps] = useState<ExpectedQps>(activeSession.parameters.expectedQps);
  const [consistency, setConsistency] = useState<ConsistencyModel>(activeSession.parameters.dataConsistency);
  const [isSaved, setIsSaved] = useState(false);

  const handleSaveParameters = () => {
    updateActiveSession({
      description: promptText,
      parameters: {
        ...activeSession.parameters,
        database: db,
        messaging,
        requirementsSize: size,
        expectedQps: qps,
        dataConsistency: consistency,
      },
    });
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
  };

  const handleAddStory = () => {
    const nextIdx = activeSession.stories.length + 1;
    const newStory: BddStory = {
      id: `US-${String(nextIdx).padStart(3, '0')}`,
      title: `Nueva Operación de Negocio ${nextIdx}`,
      role: 'Usuario del Microservicio',
      feature: 'Ejecutar transacción de negocio',
      benefit: 'Garantizar cumplimiento de regla corporativa',
      scenarios: [
        {
          title: 'Transacción exitosa',
          given: 'El servicio está operativo con dependencias listas',
          when: 'Se envía petición válida',
          then: 'Se procesa con éxito y retorna código HTTP 200',
        },
      ],
      detected_entities: [activeSession.name.split('-')[0] || 'Resource'],
    };
    updateActiveSession({
      stories: [...activeSession.stories, newStory],
    });
  };

  const handleDeleteStory = (storyId: string) => {
    updateActiveSession({
      stories: activeSession.stories.filter((s) => s.id !== storyId),
    });
  };

  return (
    <div className="space-y-6">
      {/* Top Parameter Extraction Card */}
      <Card
        title={
          <div className="flex items-center gap-2">
            <Sliders className="w-5 h-5 text-blue-400" />
            <span>Fase 1: Requisitos & Matriz de Parámetros Quarkus</span>
          </div>
        }
        subtitle="Parámetros técnicos de infraestructura y descripción funcional requeridos por el grafo de orquestación"
        action={
          <div className="flex items-center gap-2">
            {isSaved && (
              <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Guardado
              </span>
            )}
            <button
              type="button"
              onClick={handleSaveParameters}
              className="py-1.5 px-3 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-xs transition-all"
            >
              Guardar Cambios
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          {/* Parameter Selectors */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-950/70 border border-slate-800">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Base de Datos (DB)
              </label>
              <select
                value={db}
                onChange={(e) => setDb(e.target.value as DatabaseEngine)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white text-xs font-medium focus:ring-1 focus:ring-blue-500"
              >
                <option value="POSTGRESQL">PostgreSQL 16</option>
                <option value="MYSQL">MySQL 8.0</option>
                <option value="H2">H2 In-Memory</option>
                <option value="NONE">Sin Base de Datos</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Broker Mensajería
              </label>
              <select
                value={messaging}
                onChange={(e) => setMessaging(e.target.value as MessagingSystem)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white text-xs font-medium focus:ring-1 focus:ring-blue-500"
              >
                <option value="KAFKA">Apache Kafka (SmallRye)</option>
                <option value="RABBITMQ">RabbitMQ</option>
                <option value="NONE">Sin Mensajería</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Volumen Requisitos
              </label>
              <select
                value={size}
                onChange={(e) => setSize(e.target.value as RequirementsSize)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white text-xs font-medium focus:ring-1 focus:ring-blue-500"
              >
                <option value="LOW">Bajo (1-2 entidades)</option>
                <option value="MEDIUM">Medio (3-5 entidades)</option>
                <option value="HIGH">Alto (6-10 entidades)</option>
                <option value="ENTERPRISE">Enterprise (&gt;10)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Consistencia / QPS
              </label>
              <select
                value={`${consistency}-${qps}`}
                onChange={(e) => {
                  const [c, q] = e.target.value.split('-') as [ConsistencyModel, ExpectedQps];
                  setConsistency(c);
                  setQps(q);
                }}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white text-xs font-medium focus:ring-1 focus:ring-blue-500"
              >
                <option value="ACID-100">ACID · 100 QPS</option>
                <option value="ACID-1000">ACID · 1,000 QPS</option>
                <option value="EVENTUAL-5000+">Eventual (Saga) · 5,000+ QPS</option>
              </select>
            </div>
          </div>

          {/* Business Prompt */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Requisitos en Lenguaje Natural / Prompt de Negocio
            </label>
            <textarea
              rows={3}
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs leading-relaxed focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>
      </Card>

      {/* BDD Stories Card */}
      <Card
        title={
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-400" />
              <span>Historias de Usuario BDD (Given / When / Then)</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-950 text-blue-300 border border-blue-800">
                {activeSession.stories.length} historias
              </span>
            </div>
            <button
              type="button"
              onClick={handleAddStory}
              className="flex items-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
            >
              <Plus className="w-3.5 h-3.5 text-blue-400" />
              <span>Agregar Historia</span>
            </button>
          </div>
        }
        subtitle="Historias desglosadas por el agente de análisis de requerimientos para guiar la síntesis de código y pruebas"
      >
        <div className="space-y-4">
          {activeSession.stories.map((story) => (
            <div
              key={story.id}
              className="p-4 rounded-xl border border-slate-800 bg-slate-950/60 space-y-3"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-blue-400 px-2 py-0.5 rounded bg-blue-950 border border-blue-900">
                    {story.id}
                  </span>
                  <h4 className="text-xs font-bold text-white">{story.title}</h4>
                </div>
                <button
                  type="button"
                  onClick={() => handleDeleteStory(story.id)}
                  title="Eliminar historia"
                  className="p-1 text-slate-500 hover:text-rose-400"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* BDD Sentence */}
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-slate-300">
                <span className="text-blue-400 font-semibold">Como </span>
                <span>{story.role}, </span>
                <span className="text-blue-400 font-semibold">quiero </span>
                <span>{story.feature}, </span>
                <span className="text-blue-400 font-semibold">para </span>
                <span>{story.benefit}.</span>
              </div>

              {/* Scenarios */}
              <div className="space-y-2">
                {story.scenarios.map((sc, scIdx) => (
                  <div
                    key={scIdx}
                    className="p-2.5 rounded-lg bg-slate-900/50 border border-slate-800/80 text-[11px] space-y-1 font-mono"
                  >
                    <div className="font-bold text-slate-200 font-sans">{sc.title}</div>
                    <div className="text-slate-400">
                      <span className="text-emerald-400 font-bold">DADO QUE </span>
                      {sc.given}
                    </div>
                    <div className="text-slate-400">
                      <span className="text-blue-400 font-bold">CUANDO </span>
                      {sc.when}
                    </div>
                    <div className="text-slate-400">
                      <span className="text-violet-400 font-bold">ENTONCES </span>
                      {sc.then}
                    </div>
                  </div>
                ))}
              </div>

              {/* Entities detected */}
              {story.detected_entities && story.detected_entities.length > 0 && (
                <div className="flex items-center gap-1.5 pt-1 text-[11px] text-slate-400">
                  <Tag className="w-3 h-3 text-slate-500" />
                  <span>Entidades asociadas:</span>
                  <div className="flex flex-wrap gap-1">
                    {story.detected_entities.map((ent) => (
                      <span
                        key={ent}
                        className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-blue-300 border border-slate-700"
                      >
                        {ent}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Next Step Nav */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={() => setActiveTab(2)}
          className="flex items-center gap-2 py-2.5 px-5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md transition-all"
        >
          <span>Continuar a Fase 2: Arquitectura</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
