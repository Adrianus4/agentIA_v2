import React, { useState, useEffect } from 'react';
import { X, ShieldCheck, Cpu, Key, CheckCircle2, AlertCircle, RefreshCw, Server } from 'lucide-react';
import { useLlm, RECOMMENDED_MODELS, type LlmProviderType } from '../../context/LlmContext';
import { useStudio } from '../../context/StudioContext';

interface SettingsDrawerProps {
  isOpen?: boolean;
  onClose?: () => void;
}

const CORPORATE_OPENAI_BASE = 'https://genailab.tcs.in/v1';

export const SettingsDrawer: React.FC<SettingsDrawerProps> = ({
  isOpen: propIsOpen,
  onClose: propOnClose,
}) => {
  const {
    provider,
    apiKey,
    model,
    endpoint,
    isSettingsOpen,
    isVerified,
    latencyMs,
    statusMessage,
    isVerifying,
    setIsSettingsOpen,
    setProvider,
    setApiKey,
    setModel,
    setEndpoint,
    verifyConnection,
  } = useLlm();

  const {
    baseUrl,
    setBaseUrl,
    apiKey: orchestratorApiKey,
    setApiKey: setOrchestratorApiKey,
  } = useStudio();

  const isOpen = propIsOpen !== undefined ? propIsOpen : isSettingsOpen;
  const onClose = propOnClose || (() => setIsSettingsOpen(false));

  const [localKey, setLocalKey] = useState(apiKey);
  const [showKey, setShowKey] = useState(false);
  const [localBaseUrl, setLocalBaseUrl] = useState(baseUrl);
  const [localOrchestratorKey, setLocalOrchestratorKey] = useState(orchestratorApiKey);

  useEffect(() => {
    setLocalKey(apiKey);
  }, [apiKey]);

  useEffect(() => {
    setLocalBaseUrl(baseUrl);
  }, [baseUrl]);

  useEffect(() => {
    setLocalOrchestratorKey(orchestratorApiKey);
  }, [orchestratorApiKey]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextProvider = e.target.value as LlmProviderType;
    setProvider(nextProvider);
  };

  const handleSaveAndVerify = async () => {
    setApiKey(localKey);
    setBaseUrl(localBaseUrl);
    setOrchestratorApiKey(localOrchestratorKey);
    await verifyConnection(localKey, provider, model, endpoint, localBaseUrl, localOrchestratorKey);
  };

  const modelPlaceholder =
    provider === 'local'
      ? 'qwen2.5-coder:3b'
      : provider === 'openai'
      ? 'azure/genailab-maas-gpt-4o-mini'
      : provider === 'gemini'
      ? 'gemini-flash-latest'
      : 'model-id';

  const endpointLabel =
    provider === 'local'
      ? 'Endpoint de Inferencia Local / Gateway'
      : provider === 'openai'
      ? 'API Base OpenAI-Compatible Corporativa'
      : 'Endpoint Override (Opcional)';

  const endpointPlaceholder =
    provider === 'local'
      ? 'http://127.0.0.1:11434'
      : provider === 'openai'
      ? CORPORATE_OPENAI_BASE
      : 'Predeterminado del proveedor';

  return (
    <>
      <div
        data-testid="settings-drawer-backdrop"
        className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-40 transition-opacity animate-fade-in"
        onClick={onClose}
      />

      <div
        data-testid="settings-drawer"
        role="dialog"
        aria-label="Configuración del Motor LLM"
        className="fixed inset-y-0 right-0 h-screen w-full max-w-lg bg-slate-900 border-l border-slate-800 shadow-2xl z-50 flex flex-col transform transition-transform duration-300 ease-in-out text-slate-100"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-2.5">
            <Cpu className="w-5 h-5 text-blue-400" />
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                Configuración del Motor LLM
              </h2>
              <p className="text-xs text-slate-400">
                Memoria Efímera en Sesión (Constitución Principio VI)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Cerrar modal"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="p-3.5 rounded-xl bg-blue-950/40 border border-blue-900/60 flex items-start gap-3 text-xs text-blue-200">
            <ShieldCheck className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block mb-0.5">Seguridad Empresarial TCS</span>
              Las claves de API se mantienen exclusivamente en memoria de navegación y se transmiten de forma transitoria por ejecución. Nunca se guardan en disco ni en base de datos.
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold text-white">
              <Server className="w-4 h-4 text-emerald-400" />
              <span>Servidor Orquestador (Backend FastAPI)</span>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                URL del Backend Orquestador
              </label>
              <input
                type="text"
                value={localBaseUrl}
                onChange={(e) => setLocalBaseUrl(e.target.value)}
                placeholder="http://192.168.1.135:8000"
                className="w-full px-3 py-2 rounded-xl border border-slate-700 bg-slate-900 text-white text-xs font-mono focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
              <p className="text-[10px] text-slate-500 mt-1">
                Para conectar desde esta laptop a la PC con la GPU, ingrese su IP y puerto (ej. <code className="text-emerald-400">http://192.168.1.135:8000</code>).
              </p>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                API Key del Orquestador
              </label>
              <input
                type="password"
                value={localOrchestratorKey}
                onChange={(e) => setLocalOrchestratorKey(e.target.value)}
                placeholder="secret"
                className="w-full px-3 py-2 rounded-xl border border-slate-700 bg-slate-900 text-white text-xs font-mono focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-2">
              Proveedor de Inteligencia Artificial
            </label>
            <select
              value={provider}
              onChange={handleProviderChange}
              className="w-full px-3 py-2.5 rounded-xl border border-slate-700 bg-slate-950 text-white text-xs font-medium focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="openai">TCS OpenAI-Compatible ({CORPORATE_OPENAI_BASE})</option>
              <option value="local">Local (Ollama / llama.cpp - Fedora RX 570)</option>
              <option value="gemini">Google Gemini (Gemini Flash (latest) / 2.5 Pro)</option>
              <option value="groq">Groq Cloud (Qwen 2.5 Coder 32B / Llama 3.3 70B)</option>
              <option value="deepseek">DeepSeek (DeepSeek Coder V2 / Chat V3)</option>
              <option value="mock">Modo Offline (Mock Engine Determínistico - Sin Costo)</option>
            </select>
          </div>

          {provider !== 'mock' && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-semibold text-slate-300">
                  Clave de API / Token ({provider === 'local' ? 'Opcional / TCS Gateway' : provider === 'openai' ? 'Corporativa TCS' : provider.toUpperCase()})
                </label>
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="text-[11px] text-blue-400 hover:text-blue-300"
                >
                  {showKey ? 'Ocultar' : 'Mostrar'}
                </button>
              </div>
              <div className="relative">
                <Key className="absolute left-3 top-2.5 w-4 h-4 text-slate-500 pointer-events-none" />
                <input
                  type={showKey ? 'text' : 'password'}
                  value={localKey}
                  onChange={(e) => setLocalKey(e.target.value)}
                  placeholder={
                    provider === 'local'
                      ? 'No requerido para Ollama local (o token Bearer / TCS Gateway)'
                      : provider === 'gemini'
                      ? 'AIzaSy... (o vacío para usar GEMINI_API_KEY del server)'
                      : provider === 'openai'
                      ? 'Corporate API key para https://genailab.tcs.in/v1'
                      : 'API key del proveedor'
                  }
                  className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-700 bg-slate-950 text-white text-xs font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                {provider === 'local'
                  ? 'Para Ollama en la PC Fedora deje en blanco. Si utiliza TCS Gateway Guard, ingrese el token aquí.'
                  : provider === 'openai'
                  ? 'Use la API key corporativa del endpoint OpenAI-compatible de TCS. Si se deja vacío, el backend intentará usar OPENAI_API_KEY.'
                  : 'Deje en blanco para utilizar la clave configurada en el servidor backend.'}
              </p>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Modelo Designado
            </label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={modelPlaceholder}
              className="w-full px-3 py-2 rounded-xl border border-slate-700 bg-slate-950 text-white text-xs font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />

            {RECOMMENDED_MODELS[provider] && (
              <div className="flex flex-wrap gap-1.5 mt-2.5">
                {RECOMMENDED_MODELS[provider].map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setModel(opt.id)}
                    className={`text-[10px] px-2.5 py-1 rounded-lg border font-mono transition-colors ${
                      model === opt.id
                        ? 'bg-blue-950/80 border-blue-500 text-blue-300 font-bold ring-1 ring-blue-500'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                    }`}
                  >
                    {opt.label} {opt.badge && <span className="opacity-75">({opt.badge})</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              {endpointLabel}
            </label>
            <input
              type="text"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder={endpointPlaceholder}
              className="w-full px-3 py-2 rounded-xl border border-slate-700 bg-slate-950 text-white text-xs font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />

            {provider === 'openai' && (
              <div className="mt-2 space-y-1.5">
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => setEndpoint(CORPORATE_OPENAI_BASE)}
                    className={`text-[10px] px-2.5 py-1 rounded-lg border font-mono transition-colors ${
                      endpoint === CORPORATE_OPENAI_BASE
                        ? 'bg-blue-950/80 border-blue-500 text-blue-300 font-bold ring-1 ring-blue-500'
                        : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Base corporativa TCS
                  </button>
                </div>
                <p className="text-[11px] text-slate-500">
                  Recomendado: <code className="text-blue-300 font-mono">{CORPORATE_OPENAI_BASE}</code>.
                </p>
              </div>
            )}

            {provider === 'local' && (
              <div className="mt-2 space-y-1.5">
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => setEndpoint('http://127.0.0.1:8080')}
                    className={`text-[10px] px-2.5 py-1 rounded-lg border font-mono transition-colors ${
                      endpoint === 'http://127.0.0.1:8080'
                        ? 'bg-emerald-950/80 border-emerald-500 text-emerald-300 font-bold ring-1 ring-emerald-500'
                        : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    :8080 (llama-server Vulkan RX 570)
                  </button>
                  <button
                    type="button"
                    onClick={() => setEndpoint('http://127.0.0.1:11434')}
                    className={`text-[10px] px-2.5 py-1 rounded-lg border font-mono transition-colors ${
                      endpoint === 'http://127.0.0.1:11434'
                        ? 'bg-blue-950/80 border-blue-500 text-blue-300 font-bold ring-1 ring-blue-500'
                        : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    :11434 (Ollama)
                  </button>
                </div>
                <p className="text-[11px] text-slate-500">
                  Usa <code className="text-emerald-300 font-mono">http://127.0.0.1:8080</code> para tu script Vulkan (scripts/start_vulkan_llm.sh) o <code className="text-blue-300 font-mono">http://127.0.0.1:11434</code> para Ollama.
                </p>
              </div>
            )}
          </div>

          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-300">Estado de Conexión</span>
              <span
                className={`inline-flex items-center gap-1 font-semibold ${
                  isVerified ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {isVerified ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Conectado</span>
                  </>
                ) : (
                  <>
                    <AlertCircle className="w-3.5 h-3.5" />
                    <span>Pendiente / Error</span>
                  </>
                )}
              </span>
            </div>

            {latencyMs !== null && (
              <div className="flex items-center justify-between text-slate-400 text-[11px]">
                <span>Latencia de verificación:</span>
                <span className="font-mono text-emerald-400 font-semibold">{latencyMs} ms</span>
              </div>
            )}

            <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-900">
              {statusMessage}
            </div>
          </div>
        </div>

        <div className="p-5 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between gap-3 shrink-0">
          <button
            type="button"
            onClick={handleSaveAndVerify}
            disabled={isVerifying}
            className="flex items-center gap-2 py-2 px-4 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isVerifying ? 'animate-spin' : ''}`} />
            <span>{isVerifying ? 'Verificando...' : 'Probar Conexión'}</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setApiKey(localKey);
              setBaseUrl(localBaseUrl);
              setOrchestratorApiKey(localOrchestratorKey);
              onClose();
            }}
            className="py-2 px-5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md transition-all"
          >
            Guardar y Cerrar
          </button>
        </div>
      </div>
    </>
  );
};