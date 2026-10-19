import React from 'react';
import { Key, ShieldCheck, Sparkles } from 'lucide-react';
import type { LlmSettings } from '../../types/blueprintGraph';
import { Card } from '../common/Card';

interface LlmConfigurationPanelProps {
  settings: LlmSettings;
  onChange: (patch: Partial<LlmSettings>) => void;
}

const CORPORATE_OPENAI_BASE = 'https://genailab.tcs.in/v1';

const RECOMMENDED_BY_PROVIDER: Record<LlmSettings['provider'], string[]> = {
  openai: ['azure/genailab-maas-gpt-4o-mini', 'genailab-maas-gpt-4o', 'genailab-maas-gpt-5.1', 'genailab-maas-gpt-5.2-codex', 'genailab-maas-gpt-5.3-codex', 'genailab-maas-gpt-5.4'],
  gemini: ['gemini-flash-latest', 'gemini-pro-latest'],
  local: ['qwen2.5-coder:3b', 'qwen2.5-coder:7b'],
};

export const LlmConfigurationPanel: React.FC<LlmConfigurationPanelProps> = ({
  settings,
  onChange,
}) => (
  <Card
    title={
      <div className="flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-violet-400" />
        <span>Configuración del motor LLM</span>
      </div>
    }
    subtitle="Selección heredada de AgentIA v1, conectada al pipeline de generación de AgentIA v2"
  >
    <div className="space-y-5">
      <div className="flex items-start gap-3 rounded-xl border border-blue-800/70 bg-blue-950/30 p-4 text-xs text-blue-100">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
        <p>
          La clave se mantiene en memoria y solo se envía de forma transitoria durante
          una ejecución. No se incluye en el estado de la ejecución ni en los logs.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <label className="text-xs text-slate-300">
          Proveedor
          <select
            aria-label="LLM provider"
            value={settings.provider}
            onChange={(event) => {
              const nextProvider = event.target.value as LlmSettings['provider'];
              onChange({
                provider: nextProvider,
                model:
                  RECOMMENDED_BY_PROVIDER[nextProvider]?.[0] ??
                  (nextProvider === 'openai'
                    ? 'azure/genailab-maas-gpt-4o-mini'
                    : nextProvider === 'local'
                    ? 'qwen2.5-coder:3b'
                    : 'gemini-flash-latest'),
                endpoint:
                  nextProvider === 'openai'
                    ? CORPORATE_OPENAI_BASE
                    : nextProvider === 'local'
                    ? 'http://127.0.0.1:11434'
                    : '',
              });
            }}
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          >
            <option value="openai">TCS OpenAI-Compatible</option>
            <option value="gemini">Google Gemini</option>
            <option value="local">Local (Ollama / llama.cpp)</option>
          </select>
          <span className="mt-1 block text-[11px] text-slate-500">
            OpenAI usa el endpoint corporativo <code className="font-mono text-blue-300">{CORPORATE_OPENAI_BASE}</code>.
            La disponibilidad de modelos depende de tu API key.
          </span>
        </label>

        <label className="text-xs text-slate-300">
          Modelo
          <input
            aria-label="LLM model"
            value={settings.model}
            onChange={(event) => onChange({ model: event.target.value })}
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm"
            placeholder={
              settings.provider === 'local'
                ? 'qwen2.5-coder:3b'
                : settings.provider === 'openai'
                ? 'azure/genailab-maas-gpt-4o-mini'
                : 'gemini-flash-latest'
            }
          />
        </label>

        <div className="text-xs text-slate-300 md:col-span-2">
          <span className="mb-2 block">Modelos recomendados</span>
          <div className="flex flex-wrap gap-2">
            {RECOMMENDED_BY_PROVIDER[settings.provider].map((candidate) => (
              <button
                key={candidate}
                type="button"
                onClick={() => onChange({ model: candidate })}
                className={`rounded-lg border px-2.5 py-1 font-mono text-[11px] transition ${
                  settings.model === candidate
                    ? 'border-violet-500 bg-violet-950/40 text-violet-200'
                    : 'border-slate-700 bg-slate-950 text-slate-400 hover:text-slate-200'
                }`}
              >
                {candidate}
              </button>
            ))}
          </div>
          {settings.provider === 'openai' ? (
            <span className="mt-2 block text-[11px] text-amber-400">
              Si un modelo devuelve 400 Invalid model name, usa `azure/genailab-maas-gpt-4o-mini` o consulta `/v1/models` con tu key.
            </span>
          ) : null}
        </div>

        <label className="text-xs text-slate-300 md:col-span-2">
          API key efímera {settings.provider === 'local' ? '(opcional para local)' : '(opcional si el backend ya la tiene)'}
          <div className="relative mt-1">
            <Key className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              aria-label="LLM API key"
              type="password"
              value={settings.apiKey}
              onChange={(event) => onChange({ apiKey: event.target.value })}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2 pl-10 pr-3 font-mono text-sm"
              placeholder={
                settings.provider === 'local'
                  ? 'Opcional; no necesaria para Ollama local'
                  : settings.provider === 'openai'
                  ? 'Corporate API key de GenAILab'
                  : 'API key del proveedor'
              }
            />
          </div>
        </label>

        <label className="text-xs text-slate-300 md:col-span-2">
          {settings.provider === 'openai'
            ? 'API Base OpenAI-Compatible'
            : settings.provider === 'local'
            ? 'Endpoint local'
            : 'Endpoint override'}
          <input
            aria-label="LLM endpoint"
            value={settings.endpoint}
            onChange={(event) => onChange({ endpoint: event.target.value })}
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm"
            placeholder={
              settings.provider === 'local'
                ? 'http://127.0.0.1:11434'
                : settings.provider === 'openai'
                ? CORPORATE_OPENAI_BASE
                : 'Opcional; usa el endpoint predeterminado del proveedor'
            }
          />
          <span className="mt-1 block text-[11px] text-slate-500">
            {settings.provider === 'openai'
              ? 'Recomendado: usar la base corporativa https://genailab.tcs.in/v1.'
              : settings.provider === 'local'
              ? 'Debe apuntar a localhost para Ollama o llama.cpp.'
              : 'Puede dejarse vacío para usar la configuración predeterminada del backend.'}
          </span>
        </label>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3 text-xs text-slate-400">
        Selección activa: <span className="font-mono text-violet-300">{settings.provider}</span>
        {' / '}
        <span className="font-mono text-slate-200">{settings.model || 'sin modelo'}</span>
        {settings.endpoint ? (
          <>
            {' / '}
            <span className="font-mono text-slate-400">{settings.endpoint}</span>
          </>
        ) : null}
      </div>
    </div>
  </Card>
);

