import React, { useState } from 'react';
import {
  Server,
  Send,
} from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { Card } from '../components/common/Card';


export const DevOpsDeploymentView: React.FC = () => {
  const { activeSession } = useStudio();

  if (!activeSession) {
    return (
      <div className="text-center py-12 text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
        <Server className="w-12 h-12 mx-auto mb-3 text-slate-500" />
        <h3 className="text-base font-bold text-white">No hay un microservicio seleccionado</h3>
      </div>
    );
  }

  const [activeTabMode, setActiveTabMode] = useState<'manifests' | 'console'>('console');
  const [targetHost, setTargetHost] = useState('http://localhost:8080');
  const [method, setMethod] = useState<'GET' | 'POST'>('GET');
  const [endpoint, setEndpoint] = useState(`/api/${activeSession.name.replace(/-service$/, '')}`);
  const [bodyText, setBodyText] = useState('{\n  "name": "Prueba Transaccional",\n  "status": "ACTIVE"\n}');
  const [responseOutput, setResponseOutput] = useState<string | null>(null);
  const [responseStatus, setResponseStatus] = useState<number | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isLiveSuccess, setIsLiveSuccess] = useState<boolean | null>(null);

  const handleSendRequest = async () => {
    setIsSending(true);
    setResponseOutput(null);
    setResponseStatus(null);
    setLatency(null);
    setIsLiveSuccess(null);

    const start = performance.now();

    try {
      const fullUrl = `${targetHost.replace(/\/+$/, '')}${endpoint.startsWith('/') ? endpoint : '/' + endpoint}`;
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);

      const res = await fetch(fullUrl, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: method === 'POST' ? bodyText : undefined,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const dur = Math.round(performance.now() - start);
      setLatency(dur);
      setResponseStatus(res.status);
      setIsLiveSuccess(true);

      const text = await res.text();
      try {
        const json = JSON.parse(text);
        setResponseOutput(JSON.stringify(json, null, 2));
      } catch {
        setResponseOutput(text || `HTTP ${res.status} ${res.statusText}`);
      }
    } catch (err: any) {
      const dur = Math.round(performance.now() - start);
      setLatency(dur);
      setIsLiveSuccess(false);
      setResponseStatus(503);
      const wsDir = activeSession.parameters.workspaceDir || `/tmp/agentia-workspace/${activeSession.name}`;
      setResponseOutput(
        JSON.stringify(
          {
            error: 'No se pudo conectar al runtime en vivo de Quarkus',
            target: `${targetHost}${endpoint}`,
            detail: String(err?.message || err),
            instructions: [
              `Para iniciar el microservicio real en ${targetHost}:`,
              `1. Abre una terminal en la máquina donde reside el workspace.`,
              `2. Ejecuta: cd ${wsDir} && mvn quarkus:dev`,
              `3. Una vez iniciado Quarkus en el puerto 8080 (Listening on: http://localhost:8080), vuelve a presionar 'Enviar Request a Runtime'.`,
            ],
          },
          null,
          2
        )
      );
    } finally {
      setIsSending(false);
    }
  };

  const composeYaml = `version: '3.8'

services:
  ${activeSession.name}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ${activeSession.name}
    ports:
      - "8080:8080"
    environment:
      - QUARKUS_DATASOURCE_JDBC_URL=jdbc:${activeSession.parameters.database.toLowerCase()}://db:5432/${activeSession.name.replace(/-/g, '_')}
      - QUARKUS_DATASOURCE_USERNAME=quarkus
      - QUARKUS_DATASOURCE_PASSWORD=quarkus
    depends_on:
      - db

  db:
    image: postgres:16-alpine
    container_name: ${activeSession.name}-db
    environment:
      POSTGRES_DB: ${activeSession.name.replace(/-/g, '_')}
      POSTGRES_USER: quarkus
      POSTGRES_PASSWORD: quarkus
    ports:
      - "5432:5432"
`;

  return (
    <div className="space-y-6">
      <Card
        title={
          <div className="flex items-center gap-2">
            <Server className="w-5 h-5 text-blue-400" />
            <span>Fase 8: DevOps, Despliegue en Contenedores & Consola de Demostración</span>
          </div>
        }
        subtitle="Manifiestos de despliegue Docker/Compose y consola de pruebas REST interactiva"
        action={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTabMode('console')}
              className={`py-1.5 px-3 rounded-lg text-xs font-semibold transition-all ${
                activeTabMode === 'console'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Consola REST Interactiva
            </button>
            <button
              type="button"
              onClick={() => setActiveTabMode('manifests')}
              className={`py-1.5 px-3 rounded-lg text-xs font-semibold transition-all ${
                activeTabMode === 'manifests'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              docker-compose.yml
            </button>
          </div>
        }
      >
        {activeTabMode === 'console' ? (
          <div className="space-y-5">
            {/* Live Runtime Connection Banner */}
            <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
              <div className="space-y-0.5">
                <span className="font-bold text-white flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  Pruebas Reales de API en Vivo (Quarkus JVM Runtime)
                </span>
                <span className="text-slate-400 text-[11px]">
                  Realiza peticiones HTTP directas contra el microservicio compilado y levantado en {targetHost}.
                </span>
              </div>
              <div className="px-3 py-1 rounded-md text-[11px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700">
                ● MODO EN VIVO (SIN MOCKS)
              </div>
            </div>

            {/* Target Server Host & Guidance */}
            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2.5">
              <div className="flex flex-col sm:flex-row items-center gap-2">
                <label className="text-[11px] font-semibold text-slate-300 shrink-0">
                  Host del Servidor Quarkus:
                </label>
                <input
                  type="text"
                  value={targetHost}
                  onChange={(e) => setTargetHost(e.target.value)}
                  placeholder="http://localhost:8080 o http://192.168.1.135:8080"
                  className="flex-1 w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-white text-xs font-mono focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <p className="text-[10px] text-slate-400">
                💡 Para que este endpoint responda en vivo, inicia el servidor en el workspace:{' '}
                <code className="text-emerald-400 font-mono">
                  cd {activeSession.parameters.workspaceDir || `/tmp/agentia-workspace/${activeSession.name}`} &amp;&amp; mvn quarkus:dev
                </code>
              </p>
            </div>

            {/* Request input bar */}
            <div className="flex flex-col sm:flex-row items-center gap-2">
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value as 'GET' | 'POST')}
                className="w-full sm:w-28 px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs font-mono font-bold focus:ring-1 focus:ring-blue-500"
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
              </select>

              <input
                type="text"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                className="w-full flex-1 px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs font-mono focus:ring-1 focus:ring-blue-500"
              />

              <button
                type="button"
                onClick={handleSendRequest}
                disabled={isSending}
                className="w-full sm:w-auto flex items-center justify-center gap-2 py-2 px-5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md transition-all cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
                <span>{isSending ? 'Conectando...' : 'Enviar Request a Runtime'}</span>
              </button>
            </div>

            {method === 'POST' && (
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Cuerpo de la Solicitud (JSON Payload)
                </label>
                <textarea
                  rows={4}
                  value={bodyText}
                  onChange={(e) => setBodyText(e.target.value)}
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-emerald-300 font-mono text-xs leading-relaxed focus:ring-1 focus:ring-blue-500"
                />
              </div>
            )}

            {/* Response Viewer */}
            {responseOutput && (
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs pb-2 border-b border-slate-800 font-mono">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400">Origen:</span>
                    {isLiveSuccess === true ? (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700">
                        ● RUNTIME EN VIVO (Quarkus JVM)
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-700">
                        ✕ FALLO DE CONEXIÓN A RUNTIME
                      </span>
                    )}
                    <span className="text-slate-400 ml-2">HTTP:</span>
                    <span
                      className={`font-bold ${
                        (responseStatus || 0) < 400 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {responseStatus} {(responseStatus || 0) < 400 ? 'OK' : 'ERROR'}
                    </span>
                  </div>
                  {latency !== null && (
                    <div className="text-slate-400">
                      Latencia: <span className="text-blue-300 font-bold">{latency} ms</span>
                    </div>
                  )}
                </div>
                <pre className="text-xs font-mono text-slate-200 overflow-x-auto p-2 leading-relaxed">
                  {responseOutput}
                </pre>
              </div>
            )}
          </div>
        ) : (
          /* Manifests */
          <div className="space-y-3">
            <span className="text-xs font-mono text-slate-400 block">docker-compose.yml</span>
            <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-blue-300 font-mono text-xs overflow-x-auto leading-relaxed">
              {composeYaml}
            </pre>
          </div>
        )}
      </Card>
    </div>
  );
};
