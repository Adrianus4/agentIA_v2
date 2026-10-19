import React, { useState, useEffect, useCallback } from 'react';
import { clsx } from 'clsx';
import {
  Play,
  RotateCw,
  FileCode,
  Search,
  Key,
  Folder,
  CheckCircle,
  AlertTriangle,
  Sparkles,
  Layers,
} from 'lucide-react';
import type {
  BlueprintRunRequest,
  LlmSettings,
  QuarkusConfig,
  PresetTemplate,
} from '../../types/blueprintGraph';
import {
  getDefaultBlueprint,
  DEFAULT_API_BASE_URL,
  PRESET_TEMPLATES,
  AVAILABLE_QUARKUS_EXTENSIONS,
  buildBlueprintFromConfig,
} from '../../services/blueprintService';
import { Card } from '../common/Card';

interface BlueprintRunTriggerProps {
  onSubmit: (request: BlueprintRunRequest, apiKey: string, baseUrl: string, llmApiKey: string) => void;
  onQueryTrace: (traceId: string, apiKey: string, baseUrl: string) => void;
  isSubmitting?: boolean;
  initialApiKey?: string;
  initialBaseUrl?: string;
  llmSettings?: LlmSettings;
  onLlmSettingsChange?: (patch: Partial<LlmSettings>) => void;
  className?: string;
}

const CORPORATE_OPENAI_BASE = 'https://genailab.tcs.in/v1';

const DEFAULT_LLM_SETTINGS: LlmSettings = {
  provider: 'openai',
  model: 'azure/genailab-maas-gpt-4o-mini',
  endpoint: CORPORATE_OPENAI_BASE,
  apiKey: '',
};

const RECOMMENDED_MODELS: Record<LlmSettings['provider'], string[]> = {
  openai: ['azure/genailab-maas-gpt-4o-mini', 'genailab-maas-gpt-4o', 'genailab-maas-gpt-5.1', 'genailab-maas-gpt-5.2-codex', 'genailab-maas-gpt-5.3-codex', 'genailab-maas-gpt-5.4'],
  gemini: ['gemini-flash-latest', 'gemini-pro-latest'],
  local: ['qwen2.5-coder:3b', 'qwen2.5-coder:7b'],
};
export const BlueprintRunTrigger: React.FC<BlueprintRunTriggerProps> = ({
  onSubmit,
  onQueryTrace,
  isSubmitting = false,
  initialApiKey = 'secret',
  initialBaseUrl = DEFAULT_API_BASE_URL,
  llmSettings = DEFAULT_LLM_SETTINGS,
  onLlmSettingsChange = () => undefined,
  className,
}) => {
  const [activeTab, setActiveTab] = useState<'form' | 'json'>('form');
  const [workspaceDir, setWorkspaceDir] = useState('/tmp/agentia-workspace');
  const [apiKey, setApiKey] = useState(initialApiKey);
  const [baseUrl, setBaseUrl] = useState(initialBaseUrl);

  const [config, setConfig] = useState<QuarkusConfig>(() => ({
    ...PRESET_TEMPLATES[0].config,
  }));
  const [domainModels, setDomainModels] = useState<any[]>(
    () => PRESET_TEMPLATES[0].domainModels || []
  );
  const [userStories, setUserStories] = useState<any[]>(
    () => PRESET_TEMPLATES[0].userStories || []
  );

  const [blueprintJson, setBlueprintJson] = useState(() =>
    JSON.stringify(getDefaultBlueprint(), null, 2)
  );
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [queryTraceInput, setQueryTraceInput] = useState('');

  useEffect(() => {
    try {
      const parsed = JSON.parse(blueprintJson);
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        setJsonError('Blueprint root must be a JSON object');
      } else {
        setJsonError(null);
      }
    } catch (err: any) {
      setJsonError(err.message || 'Invalid JSON syntax');
    }
  }, [blueprintJson]);

  const syncConfigToJson = useCallback(
    (newConfig: QuarkusConfig, models = domainModels, stories = userStories) => {
      const built = buildBlueprintFromConfig(newConfig, models, stories);
      setBlueprintJson(JSON.stringify(built, null, 2));
    },
    [domainModels, userStories]
  );

  const handleConfigChange = (patch: Partial<QuarkusConfig>) => {
    setConfig((prev) => {
      const updated = { ...prev, ...patch };
      syncConfigToJson(updated);
      return updated;
    });
  };

  const handleToggleExtension = (extId: string) => {
    const exists = config.extensions.includes(extId);
    const updated = exists
      ? config.extensions.filter((id) => id !== extId)
      : [...config.extensions, extId];
    handleConfigChange({ extensions: updated });
  };

  const handleApplyPreset = (preset: PresetTemplate) => {
    setConfig({ ...preset.config });
    setDomainModels(preset.domainModels || []);
    setUserStories(preset.userStories || []);
    syncConfigToJson(preset.config, preset.domainModels, preset.userStories);
    setJsonError(null);
  };

  const handleLoadPreset = () => {
    handleApplyPreset(PRESET_TEMPLATES[0]);
  };

  const handleFormatJson = () => {
    try {
      const parsed = JSON.parse(blueprintJson);
      setBlueprintJson(JSON.stringify(parsed, null, 2));
      setJsonError(null);
    } catch {
      // ignore
    }
  };

  const triggerSubmit = () => {
    if (jsonError || !workspaceDir.trim() || !llmSettings.model.trim() || isSubmitting) return;

    try {
      const parsed = JSON.parse(blueprintJson);
      onSubmit(
        {
          workspace_dir: workspaceDir.trim(),
          blueprint: {
            ...parsed,
            llm: {
              provider: llmSettings.provider,
              model: llmSettings.model.trim(),
              ...(llmSettings.endpoint.trim() ? { endpoint: llmSettings.endpoint.trim() } : {}),
            },
          },
        },
        apiKey.trim(),
        baseUrl.trim(),
        llmSettings.apiKey.trim()
      );
    } catch {
      setJsonError('Unable to parse JSON');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    triggerSubmit();
  };

  const handleQueryTraceSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryTraceInput.trim()) return;
    onQueryTrace(queryTraceInput.trim(), apiKey.trim(), baseUrl.trim());
  };

  return (
    <Card
      title={
        <div className="flex items-center gap-2">
          <FileCode className="w-5 h-5 text-blue-400" />
          <span>Blueprint Submission & Run Controls</span>
        </div>
      }
      subtitle="Configure target workspace, natural language requirements, Quarkus architecture, and dispatch to POST /v1/blueprint/run"
      className={className}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="rounded-xl border border-violet-800/70 bg-violet-950/20 p-3.5 space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
            <Sparkles className="w-4 h-4 text-violet-400" />
            <span>LLM Generation Configuration</span>
            <span className="text-[11px] font-normal text-slate-500">Credentials are used only for this run</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <label className="text-[11px] text-slate-400">
              Provider
              <select
                aria-label="LLM provider"
                value={llmSettings.provider}
                onChange={(e) => {
                  const nextProvider = e.target.value as LlmSettings['provider'];
                  onLlmSettingsChange({
                    provider: nextProvider,
                    model:
                      RECOMMENDED_MODELS[nextProvider]?.[0] ??
                      (nextProvider === 'openai'
                        ? 'azure/genailab-maas-gpt-4o-mini'
                        : nextProvider === 'local'
                        ? 'qwen2.5-coder:3b'
                        : 'gemini-flash-latest'),
                    endpoint:
                      nextProvider === 'openai'
                        ? CORPORATE_OPENAI_BASE
                        : nextProvider === 'local'
                        ? 'http://127.0.0.1:8080'
                        : '',
                  });
                }}
                className="mt-1 w-full p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 text-xs"
              >
                <option value="openai">TCS OpenAI-Compatible</option>
                <option value="gemini">Google Gemini</option>
                <option value="local">Local (Ollama / llama.cpp)</option>
              </select>
            </label>

            <label className="text-[11px] text-slate-400">
              Model
              <input
                aria-label="LLM model"
                value={llmSettings.model}
                onChange={(e) => onLlmSettingsChange({ model: e.target.value })}
                placeholder={
                  llmSettings.provider === 'openai'
                    ? 'azure/genailab-maas-gpt-4o-mini'
                    : llmSettings.provider === 'local'
                    ? 'qwen2.5-coder:3b'
                    : 'gemini-flash-latest'
                }
                required
                className="mt-1 w-full px-2 py-1.5 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-100 font-mono"
              />
            </label>

            <label className="text-[11px] text-slate-400">
              API key
              <input
                aria-label="LLM API key"
                type="password"
                value={llmSettings.apiKey}
                onChange={(e) => onLlmSettingsChange({ apiKey: e.target.value })}
                placeholder={
                  llmSettings.provider === 'openai'
                    ? 'Corporate API key'
                    : 'Optional if configured on server'
                }
                className="mt-1 w-full px-2 py-1.5 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-100 font-mono"
              />
            </label>
          </div>

          <label className="block text-[11px] text-slate-400">
            {llmSettings.provider === 'openai' ? 'API Base corporativa' : 'Endpoint override (optional)'}
            <input
              aria-label="LLM endpoint"
              value={llmSettings.endpoint}
              onChange={(e) => onLlmSettingsChange({ endpoint: e.target.value })}
              placeholder={
                llmSettings.provider === 'openai'
                  ? CORPORATE_OPENAI_BASE
                  : 'Leave empty for the provider default'
              }
              className="mt-1 w-full px-2 py-1.5 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-100 font-mono"
            />
          </label>

          <div className="flex flex-wrap gap-2">
            {RECOMMENDED_MODELS[llmSettings.provider].map((candidate) => (
              <button
                key={candidate}
                type="button"
                onClick={() => onLlmSettingsChange({ model: candidate })}
                className={clsx(
                  'rounded-md border px-2 py-1 text-[10px] font-mono transition-colors',
                  llmSettings.model === candidate
                    ? 'border-violet-500 bg-violet-950/50 text-violet-200'
                    : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200'
                )}
              >
                {candidate}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label
              htmlFor="workspace-dir-input"
              className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5"
            >
              <Folder className="w-3.5 h-3.5 text-blue-400" />
              Workspace Directory
            </label>
            <input
              id="workspace-dir-input"
              type="text"
              value={workspaceDir}
              onChange={(e) => setWorkspaceDir(e.target.value)}
              placeholder="/tmp/agentia-workspace"
              required
              className="w-full px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>

          <div>
            <label
              htmlFor="api-key-input"
              className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5"
            >
              <Key className="w-3.5 h-3.5 text-amber-400" />
              Orchestrator API Key
            </label>
            <input
              id="api-key-input"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="x-api-key"
              className="w-full px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>

          <div>
            <label
              htmlFor="backend-url-input"
              className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5"
            >
              <RotateCw className="w-3.5 h-3.5 text-emerald-400" />
              Backend URL
            </label>
            <input
              id="backend-url-input"
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://localhost:8000"
              required
              className="w-full px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-y border-slate-800/80 py-2.5">
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            <button
              type="button"
              onClick={() => setActiveTab('form')}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold transition-all',
                activeTab === 'form'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              )}
            >
              <Sparkles className="w-3.5 h-3.5" />
              Formulario Asistido (NL & Quarkus)
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('json')}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold transition-all',
                activeTab === 'json'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              )}
            >
              <FileCode className="w-3.5 h-3.5" />
              Editor JSON Blueprint
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium text-slate-500">Plantillas:</span>
            {PRESET_TEMPLATES.map((tmpl) => (
              <button
                key={tmpl.id}
                type="button"
                onClick={() => handleApplyPreset(tmpl)}
                className={clsx(
                  'px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors border',
                  config.serviceName === tmpl.config.serviceName
                    ? 'bg-blue-950/60 text-blue-300 border-blue-700/60 font-semibold'
                    : 'bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-800'
                )}
              >
                {tmpl.name}
              </button>
            ))}
          </div>
        </div>

        {activeTab === 'form' && (
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <label
                  htmlFor="nl-prompt-input"
                  className="text-xs font-semibold text-slate-300 flex items-center gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                  Requisitos de Negocio / Natural Language Prompt
                </label>
                <span className="text-[11px] text-slate-500 font-mono">
                  Sintetiza especificaciÃ³n BDD & JPA
                </span>
              </div>
              <textarea
                id="nl-prompt-input"
                rows={3}
                value={config.naturalLanguagePrompt}
                onChange={(e) =>
                  handleConfigChange({ naturalLanguagePrompt: e.target.value })
                }
                placeholder="Ej. Microservicio para procesar pagos y emitir facturas con validaciÃ³n de montos positivos..."
                className="w-full p-2.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label
                  htmlFor="service-name-input"
                  className="block text-xs font-semibold text-slate-300 mb-1"
                >
                  Nombre del Microservicio
                </label>
                <input
                  id="service-name-input"
                  type="text"
                  value={config.serviceName}
                  onChange={(e) => handleConfigChange({ serviceName: e.target.value })}
                  placeholder="order-service"
                  className="w-full px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-100 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label
                  htmlFor="package-name-input"
                  className="block text-xs font-semibold text-slate-300 mb-1"
                >
                  Paquete Java
                </label>
                <input
                  id="package-name-input"
                  type="text"
                  value={config.packageName}
                  onChange={(e) => handleConfigChange({ packageName: e.target.value })}
                  placeholder="com.tcs.orders"
                  className="w-full px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-100 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label
                  htmlFor="base-port-input"
                  className="block text-xs font-semibold text-slate-300 mb-1"
                >
                  Puerto Base HTTP
                </label>
                <input
                  id="base-port-input"
                  type="number"
                  value={config.basePort}
                  onChange={(e) =>
                    handleConfigChange({ basePort: Number(e.target.value) || 8080 })
                  }
                  className="w-full px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-100 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
                <Layers className="w-4 h-4 text-blue-400" />
                <span>ConfiguraciÃ³n de Quarkus, Base de Datos y Arquitectura</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2.5 text-xs">
                <div>
                  <label htmlFor="framework-select" className="block text-[11px] text-slate-400 mb-1">Framework</label>
                  <select
                    id="framework-select"
                    value={config.framework}
                    onChange={(e) =>
                      handleConfigChange({ framework: e.target.value as any })
                    }
                    className="w-full p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-blue-500"
                  >
                    <option value="quarkus">Quarkus 3.x</option>
                    <option value="springboot">Spring Boot 3.x</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="java-version-select" className="block text-[11px] text-slate-400 mb-1">Java Version</label>
                  <select
                    id="java-version-select"
                    value={config.javaVersion}
                    onChange={(e) =>
                      handleConfigChange({ javaVersion: e.target.value as any })
                    }
                    className="w-full p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-blue-500"
                  >
                    <option value="21">Java 21 LTS</option>
                    <option value="17">Java 17 LTS</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="build-tool-select" className="block text-[11px] text-slate-400 mb-1">Build Tool</label>
                  <select
                    id="build-tool-select"
                    value={config.buildTool}
                    onChange={(e) =>
                      handleConfigChange({ buildTool: e.target.value as any })
                    }
                    className="w-full p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-blue-500"
                  >
                    <option value="maven">Apache Maven</option>
                    <option value="gradle">Gradle</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="database-select" className="block text-[11px] text-slate-400 mb-1">Base de Datos</label>
                  <select
                    id="database-select"
                    value={config.database}
                    onChange={(e) =>
                      handleConfigChange({ database: e.target.value as any })
                    }
                    className="w-full p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-blue-500"
                  >
                    <option value="POSTGRESQL">PostgreSQL</option>
                    <option value="MYSQL">MySQL</option>
                    <option value="H2">H2 (En memoria)</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="architecture-select" className="block text-[11px] text-slate-400 mb-1">Arquitectura</label>
                  <select
                    id="architecture-select"
                    value={config.architecture}
                    onChange={(e) =>
                      handleConfigChange({ architecture: e.target.value as any })
                    }
                    className="w-full p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-blue-500"
                  >
                    <option value="layered">Layered (4 Capas)</option>
                    <option value="hexagonal">Hexagonal</option>
                    <option value="hexagonal-ddd">Hexagonal + DDD</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="execution-mode-select" className="block text-[11px] text-slate-400 mb-1">EjecuciÃ³n</label>
                  <select
                    id="execution-mode-select"
                    value={config.executionMode}
                    onChange={(e) =>
                      handleConfigChange({ executionMode: e.target.value as any })
                    }
                    className="w-full p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-blue-500"
                  >
                    <option value="HERMETIC_DOCKER">Docker Sandbox</option>
                    <option value="SOURCE_ONLY">Solo Fuentes</option>
                  </select>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800/60">
                <span className="block text-[11px] font-semibold text-slate-400 mb-2">
                  Extensiones de Quarkus Seleccionadas:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                  {AVAILABLE_QUARKUS_EXTENSIONS.map((ext) => {
                    const isChecked = config.extensions.includes(ext.id);
                    return (
                      <label
                        key={ext.id}
                        className={clsx(
                          'flex items-start gap-2 p-2 rounded-lg border text-xs cursor-pointer select-none transition-colors',
                          isChecked
                            ? 'bg-blue-950/40 border-blue-800/80 text-blue-200'
                            : 'bg-slate-900/50 border-slate-800/80 text-slate-400 hover:border-slate-700'
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleToggleExtension(ext.id)}
                          className="mt-0.5 rounded border-slate-700 bg-slate-900 text-blue-600 focus:ring-0 focus:ring-offset-0"
                        />
                        <div>
                          <div className="font-medium text-[11px] text-slate-200">
                            {ext.name}
                          </div>
                          <div className="text-[10px] text-slate-500 leading-tight">
                            {ext.description}
                          </div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className={activeTab === 'json' ? 'space-y-3' : 'hidden'}>
          <div className="flex items-center justify-between mb-1.5">
            <label
              htmlFor="blueprint-json-input"
              className="text-xs font-semibold text-slate-300 flex items-center gap-2"
            >
              <span>Blueprint JSON Specification</span>
              {jsonError ? (
                <span className="text-[11px] text-rose-400 font-mono flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" /> Invalid JSON: {jsonError}
                </span>
              ) : (
                <span className="text-[11px] text-emerald-400 font-mono flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" /> Valid JSON
                </span>
              )}
            </label>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleFormatJson}
                disabled={!!jsonError}
                className="text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors disabled:opacity-40"
              >
                Format
              </button>
              <button
                type="button"
                onClick={handleLoadPreset}
                className="text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
              >
                Reset Preset
              </button>
            </div>
          </div>

          <textarea
            id="blueprint-json-input"
            value={blueprintJson}
            onChange={(e) => setBlueprintJson(e.target.value)}
            rows={12}
            className={clsx(
              'w-full p-3 text-xs bg-slate-950 font-mono rounded-lg border focus:outline-none transition-colors select-text',
              jsonError
                ? 'border-rose-700 text-rose-200'
                : 'border-slate-800 text-slate-200 focus:border-blue-500'
            )}
            spellCheck={false}
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
          <div className="flex items-center gap-2 flex-1 max-w-sm">
            <input
              type="text"
              value={queryTraceInput}
              onChange={(e) => setQueryTraceInput(e.target.value)}
              placeholder="Query by Trace ID..."
              className="flex-1 px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 font-mono"
            />
            <button
              type="button"
              onClick={handleQueryTraceSubmit}
              disabled={!queryTraceInput.trim() || isSubmitting}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors disabled:opacity-50"
            >
              <Search className="w-3.5 h-3.5" />
              Lookup
            </button>
          </div>

          <button
            type="submit"
            onClick={(e) => {
              e.preventDefault();
              triggerSubmit();
            }}
            disabled={!!jsonError || !workspaceDir.trim() || isSubmitting}
            className={clsx(
              'inline-flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-bold transition-all shadow-md',
              isSubmitting
                ? 'bg-blue-800 text-blue-200 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-900/40 active:translate-y-0.5'
            )}
          >
            {isSubmitting ? (
              <>
                <RotateCw className="w-4 h-4 animate-spin" />
                Dispatching Run...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                Run Orchestrator
              </>
            )}
          </button>
        </div>
      </form>
    </Card>
  );
};

