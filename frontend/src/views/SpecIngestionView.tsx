import React from 'react';
import { FileInput } from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { useLlm } from '../context/LlmContext';
import { BlueprintRunTrigger } from '../components/orchestration/BlueprintRunTrigger';
import type { BlueprintRunRequest, LlmConfig, LlmSettings } from '../types/blueprintGraph';

export const SpecIngestionView: React.FC = () => {
  const {
    activeSession,
    executeLangGraph,
    setActiveTab,
    isExecuting,
    apiKey,
    baseUrl,
    updateActiveSession,
  } = useStudio();

  const {
    provider,
    model,
    endpoint,
    apiKey: llmApiKey,
    setProvider,
    setModel,
    setEndpoint,
    setApiKey,
  } = useLlm();

  if (!activeSession) {
    return (
      <div className="text-center py-12 text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
        <FileInput className="w-12 h-12 mx-auto mb-3 text-slate-500" />
        <h3 className="text-base font-bold text-white">No hay un microservicio seleccionado</h3>
      </div>
    );
  }

  const normalizedProvider: LlmConfig['provider'] =
    provider === 'gemini' || provider === 'local' || provider === 'openai'
      ? provider
      : 'openai';

  const handleBlueprintSubmit = async (request: BlueprintRunRequest) => {
    setActiveTab(5);
    await executeLangGraph(activeSession.id, request.blueprint);
  };

  const handleQueryTrace = (queriedTraceId: string) => {
    updateActiveSession({ traceId: queriedTraceId });
    setActiveTab(5);
  };

  return (
    <div className="space-y-6">
      <BlueprintRunTrigger
        onSubmit={(req) => void handleBlueprintSubmit(req)}
        onQueryTrace={handleQueryTrace}
        isSubmitting={isExecuting}
        initialApiKey={apiKey}
        initialBaseUrl={baseUrl}
        llmSettings={{
          provider: normalizedProvider,
          model,
          endpoint,
          apiKey: llmApiKey,
        }}
        onLlmSettingsChange={(patch: Partial<LlmSettings>) => {
          if (patch.provider !== undefined) setProvider(patch.provider);
          if (patch.model !== undefined) setModel(patch.model);
          if (patch.endpoint !== undefined) setEndpoint(patch.endpoint);
          if (patch.apiKey !== undefined) setApiKey(patch.apiKey);
        }}
      />
    </div>
  );
};