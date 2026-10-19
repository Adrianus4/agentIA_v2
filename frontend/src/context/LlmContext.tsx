import React, { createContext, useContext, useState, useCallback } from 'react';
import { DEFAULT_API_BASE_URL } from '../services/blueprintService';

export type LlmProviderType = 'gemini' | 'groq' | 'openai' | 'deepseek' | 'local' | 'mock';

export interface ModelOption {
  id: string;
  label: string;
  badge?: string;
}

const CORPORATE_OPENAI_BASE = 'https://genailab.tcs.in/v1';
const CORPORATE_OPENAI_MODEL_NOTE = 'Disponibilidad según tu API key';
const CORPORATE_OPENAI_DEFAULT_MODEL = 'azure/genailab-maas-gpt-4o-mini';

export const RECOMMENDED_MODELS: Record<LlmProviderType, ModelOption[]> = {
  local: [
    { id: 'qwen2.5-coder:3b', label: 'Qwen 2.5 Coder 3B', badge: 'RX 570 / 8GB' },
    { id: 'qwen2.5-coder:7b', label: 'Qwen 2.5 Coder 7B', badge: 'Alta Precisión' },
    { id: 'deepseek-coder:1.3b', label: 'DeepSeek Coder 1.3B', badge: 'Ultra Rápido' },
  ],
  gemini: [
    { id: 'gemini-flash-latest', label: 'Gemini Flash (latest)', badge: 'Recomendado' },
    { id: 'gemini-pro-latest', label: 'Gemini Pro (latest)', badge: 'Alta Precisión' },
    { id: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash', badge: 'Rápido' },
  ],
  groq: [
    { id: 'qwen-2.5-coder-32b', label: 'Qwen 2.5 Coder 32B', badge: 'Código' },
    { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B', badge: 'Orquestador' },
  ],
  openai: [
    { id: 'azure/genailab-maas-gpt-4o-mini', label: 'GPT-4o Mini', badge: 'Corporativo recomendado' },
    { id: 'genailab-maas-gpt-4o', label: 'GPT-4o', badge: CORPORATE_OPENAI_MODEL_NOTE },
    { id: 'genailab-maas-gpt-5.1', label: 'GPT-5.1', badge: CORPORATE_OPENAI_MODEL_NOTE },
    { id: 'genailab-maas-gpt-5.2-codex', label: 'GPT-5.2 Codex', badge: CORPORATE_OPENAI_MODEL_NOTE },
    { id: 'genailab-maas-gpt-5.3-codex', label: 'GPT-5.3 Codex', badge: CORPORATE_OPENAI_MODEL_NOTE },
    { id: 'genailab-maas-gpt-5.4', label: 'GPT-5.4', badge: CORPORATE_OPENAI_MODEL_NOTE },
  ],
  deepseek: [
    { id: 'deepseek-coder-v2', label: 'DeepSeek Coder V2', badge: 'Especializado' },
    { id: 'deepseek-chat', label: 'DeepSeek Chat V3', badge: 'General' },
  ],
  mock: [
    { id: 'mock-deterministic', label: 'Mock Engine Offline', badge: 'Sin Costo' },
  ],
};

interface LlmContextType {
  provider: LlmProviderType;
  apiKey: string;
  model: string;
  endpoint: string;
  isSettingsOpen: boolean;
  isVerified: boolean;
  latencyMs: number | null;
  statusMessage: string;
  isVerifying: boolean;
  setIsSettingsOpen: (open: boolean) => void;
  setProvider: (p: LlmProviderType) => void;
  setApiKey: (key: string) => void;
  setModel: (m: string) => void;
  setEndpoint: (ep: string) => void;
  verifyConnection: (
    key?: string,
    prov?: LlmProviderType,
    mod?: string,
    ep?: string,
    targetBaseUrl?: string,
    targetApiKey?: string
  ) => Promise<boolean>;
}

const LLM_SETTINGS_STORAGE_KEY = 'agentia_v2_llm_settings';

const LlmContext = createContext<LlmContextType | undefined>(undefined);

export const LlmProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [provider, setProviderState] = useState<LlmProviderType>(() => {
    try {
      const saved = localStorage.getItem(LLM_SETTINGS_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.provider) return parsed.provider;
      }
    } catch {
      // Ignore
    }
    return 'openai';
  });

  const [apiKey, setApiKey] = useState<string>('');

  const [model, setModel] = useState<string>(() => {
    try {
      const saved = localStorage.getItem(LLM_SETTINGS_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.model) return parsed.model;
      }
    } catch {
      // Ignore
    }
    return CORPORATE_OPENAI_DEFAULT_MODEL;
  });

  const [endpoint, setEndpoint] = useState<string>(() => {
    try {
      const saved = localStorage.getItem(LLM_SETTINGS_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.endpoint !== undefined) return parsed.endpoint;
      }
    } catch {
      // Ignore
    }
    return CORPORATE_OPENAI_BASE;
  });

  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isVerified, setIsVerified] = useState<boolean>(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>(
    'Conexión no verificada. Haz clic en "Probar Conexión" para validar el backend y el LLM.'
  );
  const [isVerifying, setIsVerifying] = useState<boolean>(false);

  React.useEffect(() => {
    try {
      // Security policy: never persist plaintext apiKey in browser localStorage
      localStorage.setItem(
        LLM_SETTINGS_STORAGE_KEY,
        JSON.stringify({ provider, model, endpoint })
      );
    } catch {
      // Ignore
    }
  }, [provider, model, endpoint]);

  const setProvider = useCallback((newProvider: LlmProviderType) => {
    setProviderState(newProvider);
    const defaults = RECOMMENDED_MODELS[newProvider];
    if (defaults && defaults.length > 0) {
      setModel(defaults[0].id);
    }

    if (newProvider === 'local') {
      setEndpoint('http://127.0.0.1:8080');
      return;
    }

    if (newProvider === 'openai') {
      setEndpoint(CORPORATE_OPENAI_BASE);
      setModel(CORPORATE_OPENAI_DEFAULT_MODEL);
      return;
    }

    if (newProvider === 'gemini' || newProvider === 'groq' || newProvider === 'deepseek' || newProvider === 'mock') {
      setEndpoint('');
    }
  }, []);

  const verifyConnection = useCallback(
    async (
      overrideKey?: string,
      overrideProvider?: LlmProviderType,
      overrideModel?: string,
      overrideEndpoint?: string,
      targetBaseUrl?: string,
      targetApiKey?: string
    ): Promise<boolean> => {
      const activeProv = overrideProvider || provider;
      const activeModel = overrideModel || model;
      const activeEp =
        overrideEndpoint !== undefined
          ? overrideEndpoint
          : activeProv === 'openai'
          ? endpoint || CORPORATE_OPENAI_BASE
          : endpoint;
      const activeKey = overrideKey !== undefined ? overrideKey : apiKey;

      const effectiveBaseUrl = (
        targetBaseUrl ||
        (() => {
          try {
            return localStorage.getItem('agentia_v2_backend_url') || DEFAULT_API_BASE_URL;
          } catch {
            return DEFAULT_API_BASE_URL;
          }
        })()
      ).replace(/\/+$/, '');

      const effectiveApiKey =
        targetApiKey !== undefined
          ? targetApiKey
          : (() => {
              try {
                return localStorage.getItem('agentia_v2_api_key') || 'secret';
              } catch {
                return 'secret';
              }
            })();

      setIsVerifying(true);
      setStatusMessage(`Probando conectividad en ${effectiveBaseUrl} con ${activeProv}...`);

      const startTime = performance.now();
      try {
        if (activeProv === 'mock') {
          await new Promise((resolve) => setTimeout(resolve, 80));
          const duration = Math.round(performance.now() - startTime);
          setLatencyMs(duration);
          setIsVerified(true);
          setStatusMessage(`Motor offline listo (modo simulado) en ${duration}ms`);
          return true;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 6000);

        const verifyRes = await fetch(`${effectiveBaseUrl}/v1/llm/verify`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-api-key': effectiveApiKey || 'secret',
          },
          body: JSON.stringify({
            provider: activeProv,
            model: activeModel,
            endpoint: activeEp || undefined,
            api_key: activeKey || undefined,
          }),
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        const duration = Math.round(performance.now() - startTime);
        setLatencyMs(duration);

        if (verifyRes.ok) {
          const data = await verifyRes.json();
          if (data.ok) {
            setIsVerified(true);
            setLatencyMs(data.latency_ms ?? duration);
            setStatusMessage(`✅ ${data.message}`);
            return true;
          } else {
            setIsVerified(false);
            setStatusMessage(`âŒ ${data.error || data.message || 'Error del proveedor LLM'}`);
            return false;
          }
        } else if (verifyRes.status === 401) {
          setIsVerified(false);
          setStatusMessage(`âŒ Error de autenticación (401): API Key del backend inválida en ${effectiveBaseUrl}`);
          return false;
        } else {
          setIsVerified(false);
          setStatusMessage(`âŒ Error HTTP ${verifyRes.status} al verificar conectividad`);
          return false;
        }
      } catch (error: any) {
        setIsVerified(false);
        setStatusMessage(`âŒ ${error?.message || 'No se pudo verificar la conexión'}`);
        return false;
      } finally {
        setIsVerifying(false);
      }
    },
    [provider, apiKey, model, endpoint]
  );

  return (
    <LlmContext.Provider
      value={{
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
      }}
    >
      {children}
    </LlmContext.Provider>
  );
};

export const useLlm = (): LlmContextType => {
  const context = useContext(LlmContext);
  if (!context) {
    return {
      provider: 'openai',
      apiKey: '',
      model: 'azure/genailab-maas-gpt-4o-mini',
      endpoint: CORPORATE_OPENAI_BASE,
      isSettingsOpen: false,
      isVerified: false,
      latencyMs: null,
      statusMessage: 'Conexión no verificada.',
      isVerifying: false,
      setIsSettingsOpen: () => {},
      setProvider: () => {},
      setApiKey: () => {},
      setModel: () => {},
      setEndpoint: () => {},
      verifyConnection: async () => false,
    };
  }
  return context;
};


