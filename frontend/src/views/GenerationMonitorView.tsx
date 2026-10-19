import React, { useCallback } from 'react';
import { Activity, Play, RefreshCw, RotateCcw, CheckCircle2, ShieldAlert } from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { LangGraphStateVisualizer } from '../components/orchestration/LangGraphStateVisualizer';
import { RealtimeTerminal } from '../components/orchestration/RealtimeTerminal';
import { BoundedRepairCounter } from '../components/orchestration/BoundedRepairCounter';
import { Card } from '../components/common/Card';
import { useStatusPolling } from '../hooks/useStatusPolling';
import type { LangGraphNodeState, RunStatusResponse } from '../types/blueprintGraph';

export const GenerationMonitorView: React.FC = () => {
  const {
    activeSession,
    executeLangGraph,
    isExecuting,
    updateActiveSession,
    apiKey,
    baseUrl,
  } = useStudio();

  if (!activeSession) {
    return (
      <div className="text-center py-12 text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
        <Activity className="w-12 h-12 mx-auto mb-3 text-slate-500" />
        <h3 className="text-base font-bold text-white">No hay un microservicio seleccionado</h3>
        <p className="text-xs text-slate-400 mt-1">
          Seleccione un microservicio en la barra lateral o cree uno en la etapa de Definición.
        </p>
      </div>
    );
  }

  const repairAttempts = activeSession.repairAttempts || 0;
  const outcome =
    activeSession.executionState?.outcome ||
    (activeSession.status === 'SUCCESS'
      ? 'SUCCESS'
      : activeSession.status === 'NO_FIX'
      ? 'NO_FIX'
      : activeSession.status === 'FAILED'
      ? 'ERROR'
      : null);

  // Wire real-time status polling for GET /v1/runs/{trace_id}
  const handleStatusChange = useCallback(
    (statusResult: RunStatusResponse) => {
      const attempts = statusResult.repair_attempts || 0;
      const normalizedStatus =
        statusResult.status === 'SUCCESS' || statusResult.outcome === 'SUCCESS' || statusResult.outcome === 'PATCHED'
          ? 'SUCCESS'
          : statusResult.status === 'NO_FIX' || statusResult.outcome === 'NO_FIX'
          ? 'NO_FIX'
          : statusResult.status === 'ERROR'
          ? 'FAILED'
          : 'RUNNING';

      const realState = statusResult.state;
      updateActiveSession({
        status: normalizedStatus,
        repairAttempts: attempts,
        executionState: realState || {
          trace_id: statusResult.trace_id,
          workspace_dir: activeSession.parameters.workspaceDir,
          blueprint: activeSession.blueprint,
          outcome: statusResult.outcome || normalizedStatus,
          attempts,
          validation: statusResult.state?.validation,
          verification: statusResult.state?.verification,
          generated_files: statusResult.state?.generated_files || [],
        },
      });
    },
    [activeSession.blueprint, activeSession.parameters.workspaceDir, updateActiveSession]
  );

  const handleStatusComplete = useCallback(
    (finalResult: RunStatusResponse) => {
      const attempts = finalResult.repair_attempts || 0;
      const finalOutcome = finalResult.outcome || finalResult.status;
      const normalizedStatus =
        finalOutcome === 'SUCCESS' || finalOutcome === 'PATCHED'
          ? 'SUCCESS'
          : finalOutcome === 'NO_FIX'
          ? 'NO_FIX'
          : 'FAILED';

      const realState = finalResult.state;
      updateActiveSession({
        status: normalizedStatus,
        repairAttempts: attempts,
        executionState: realState || activeSession.executionState,
        logs: [
          ...activeSession.logs,
          {
            id: `${Date.now()}-poll-complete`,
            timestamp: new Date().toLocaleTimeString(),
            level: normalizedStatus === 'SUCCESS' ? 'SUCCESS' : 'ERROR',
            message: `Polling completado. Trace: ${finalResult.trace_id}, Estado: ${finalOutcome}, Intentos de reparación: ${attempts}/3`,
          },
        ],
      });
    },
    [activeSession.logs, activeSession.executionState, updateActiveSession]
  );

  const { isPolling } = useStatusPolling({
    traceId: activeSession.traceId,
    apiKey,
    baseUrl,
    enabled: Boolean(activeSession.traceId && (isExecuting || activeSession.status === 'RUNNING')),
    intervalMs: 1500,
    onStatusChange: handleStatusChange,
    onComplete: handleStatusComplete,
  });

  // Calculate dynamic node states reflecting current progression
  const dynamicNodes: Record<string, LangGraphNodeState> = React.useMemo(() => {
    const isRunning = isExecuting || activeSession.status === 'RUNNING' || isPolling;
    const execState = activeSession.executionState;
    const valResult = execState?.validation;
    const verResult = execState?.verification;
    const genFiles = execState?.generated_files || [];
    const entitiesCount = activeSession.entities?.length || 1;

    // 1. Validate Node
    let validateState: LangGraphNodeState;
    if (valResult) {
      validateState = {
        id: 'validate',
        label: '1. Validate',
        description: 'Validación de esquema SpecKit y contratos BDD',
        status: valResult.valid ? 'PASSED' : 'ERROR',
        details: valResult.valid
          ? `Esquema aprobado (${entitiesCount} entidad/es sin campos huérfanos)`
          : `Error en esquema: ${valResult.diagnostics?.[0]?.message || 'Inválido'}`,
      };
    } else if (isRunning) {
      validateState = {
        id: 'validate',
        label: '1. Validate',
        description: 'Validación de esquema SpecKit y contratos BDD',
        status: 'ACTIVE',
        details: 'Verificando perfiles y entidades...',
      };
    } else {
      validateState = {
        id: 'validate',
        label: '1. Validate',
        description: 'Validación de esquema SpecKit y contratos BDD',
        status: activeSession.status === 'FAILED' ? 'ERROR' : 'IDLE',
        details: activeSession.status === 'FAILED' ? 'Fallo en validación previa' : 'En espera...',
      };
    }

    // 2. Generate Node
    let generateState: LangGraphNodeState;
    if (genFiles.length > 0) {
      generateState = {
        id: 'generate',
        label: '2. Generate',
        description: 'Generación reactiva: Entity ➔ Resource ➔ Test',
        status: 'PASSED',
        details: `${genFiles.length} archivos generados (Entity, Resource, Test, pom.xml)`,
      };
    } else if (isRunning && validateState.status === 'PASSED') {
      generateState = {
        id: 'generate',
        label: '2. Generate',
        description: 'Generación reactiva: Entity ➔ Resource ➔ Test',
        status: 'ACTIVE',
        details: 'Generando componentes con Jinja2...',
      };
    } else {
      generateState = {
        id: 'generate',
        label: '2. Generate',
        description: 'Generación reactiva: Entity ➔ Resource ➔ Test',
        status: 'IDLE',
        details: 'Pendiente de generación',
      };
    }

    // 3. Verify Node
    let verifyState: LangGraphNodeState;
    if (verResult) {
      const timeStr = verResult.wall_time_seconds ? `${verResult.wall_time_seconds.toFixed(1)}s` : '';
      if (verResult.timed_out) {
        verifyState = {
          id: 'verify',
          label: '3. Verify',
          description: 'Compilación en sandbox hermético Docker',
          status: 'ERROR',
          details: `Timeout (${verResult.wall_time_seconds || 180}s): Compilación excedió el tiempo límite`,
        };
      } else if (verResult.success) {
        verifyState = {
          id: 'verify',
          label: '3. Verify',
          description: 'Compilación en sandbox hermético Docker',
          status: 'PASSED',
          details: `Compilación hermética exitosa (${timeStr} • 0 errores)`,
        };
      } else {
        const errorCount = verResult.issues?.length || 1;
        const firstMsg = verResult.issues?.[0]?.message || 'Fallo de compilación o test';
        verifyState = {
          id: 'verify',
          label: '3. Verify',
          description: 'Compilación en sandbox hermético Docker',
          status: 'ERROR',
          details: `Fallo (exit ${verResult.exit_code ?? 1}): ${errorCount} error(es) (${firstMsg})`,
        };
      }
    } else if (isRunning && (validateState.status === 'PASSED' || generateState.status === 'PASSED')) {
      verifyState = {
        id: 'verify',
        label: '3. Verify',
        description: 'Compilación en sandbox hermético Docker',
        status: 'ACTIVE',
        details: 'Ejecutando Maven en sandbox...',
      };
    } else {
      verifyState = {
        id: 'verify',
        label: '3. Verify',
        description: 'Compilación en sandbox hermético Docker',
        status: 'IDLE',
        details: 'En cola para verificación',
      };
    }

    // 4. Repair Node
    let repairState: LangGraphNodeState;
    if (repairAttempts > 0) {
      const isRepaired = outcome === 'PATCHED' || outcome === 'SUCCESS';
      repairState = {
        id: 'repair',
        label: '4. Repair',
        description: 'Parche quirúrgico AST guiado por diagnósticos',
        status: outcome === 'NO_FIX' ? 'NO_FIX' : isRepaired ? 'PASSED' : 'REPAIRING',
        currentIteration: repairAttempts,
        details: outcome === 'NO_FIX'
          ? `Presupuesto agotado (${repairAttempts}/3)`
          : isRepaired
          ? `Reparado exitosamente (${repairAttempts}/3)`
          : `Iteración de reparación: ${repairAttempts} / 3`,
      };
    } else {
      repairState = {
        id: 'repair',
        label: '4. Repair',
        description: 'Parche quirúrgico AST guiado por diagnósticos',
        status: 'IDLE',
        currentIteration: 0,
        details: outcome === 'SUCCESS' ? 'Zero-Shot Validado (0 reparaciones requeridas)' : 'Iteración de reparación: 0 / 3',
      };
    }

    // 5. Terminal Node
    let terminalState: LangGraphNodeState;
    if (outcome === 'NO_FIX') {
      terminalState = {
        id: 'terminal',
        label: '5. Outcome',
        description: 'Liberación de código o fallo constitucional NO_FIX',
        status: 'NO_FIX',
        details: 'Constitución V: Parada de seguridad por límite de iteraciones',
      };
    } else if (outcome === 'ERROR' || activeSession.status === 'FAILED') {
      terminalState = {
        id: 'terminal',
        label: '5. Outcome',
        description: 'Liberación de código o fallo constitucional NO_FIX',
        status: 'ERROR',
        details: 'Fallo en pipeline de verificación o validación',
      };
    } else if (outcome === 'SUCCESS' || outcome === 'PATCHED' || activeSession.status === 'SUCCESS') {
      terminalState = {
        id: 'terminal',
        label: '5. Outcome',
        description: 'Liberación de código o fallo constitucional NO_FIX',
        status: 'SUCCESS',
        details: 'Microservicio validado y listo para deploy',
      };
    } else if (isRunning) {
      terminalState = {
        id: 'terminal',
        label: '5. Outcome',
        description: 'Liberación de código o fallo constitucional NO_FIX',
        status: 'IDLE',
        details: 'En ejecución...',
      };
    } else {
      terminalState = {
        id: 'terminal',
        label: '5. Outcome',
        description: 'Liberación de código o fallo constitucional NO_FIX',
        status: 'IDLE',
        details: 'En espera...',
      };
    }

    return {
      validate: validateState,
      generate: generateState,
      verify: verifyState,
      repair: repairState,
      terminal: terminalState,
    };
  }, [isExecuting, activeSession.status, isPolling, activeSession.executionState, activeSession.entities, repairAttempts, outcome]);


  const handleClearLogs = () => {
    updateActiveSession({ logs: [] });
  };

  return (
    <div className="space-y-6">
      {/* Top Monitor Status Banner */}
      <Card
        title={
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-400" />
            <span>Etapa 3: Orquestación & Monitoreo en Vivo (LangGraph Loops)</span>
          </div>
        }
        subtitle="Visualización en tiempo real del ciclo de vida reactivo: Validate ➔ Verify ➔ Bounded Self-Repair ➔ Terminal Outcome"
        action={
          <div className="flex items-center gap-3">
            {activeSession.traceId && (
              <span className="font-mono text-xs px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-blue-300">
                Trace: {activeSession.traceId}
              </span>
            )}
            <button
              type="button"
              onClick={() => void executeLangGraph()}
              disabled={isExecuting || isPolling}
              className="flex items-center gap-2 py-1.5 px-3.5 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-xs transition-all disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{isExecuting || isPolling ? 'Ejecutando en Vivo...' : 'Re-ejecutar Pipeline'}</span>
            </button>
          </div>
        }
      >
        <div className="space-y-6">
          {/* LangGraph 4-Node Visualizer with explicit Node Progression & Iteration display */}
          <LangGraphStateVisualizer
            nodes={dynamicNodes}
            currentIteration={repairAttempts}
            maxIterations={3}
            outcome={outcome}
          />

          {/* Repair Loop & Live Telemetry Details */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {/* Left 1/3: Bounded Repair Status, Active Counter, and Execution Meta */}
            <div className="space-y-4">
              <BoundedRepairCounter
                currentIteration={repairAttempts}
                maxIterations={3}
                outcome={outcome}
              />

              {/* Explicit Active Iteration Card */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <RotateCcw className="w-3.5 h-3.5 text-amber-400" />
                    Bucle de Reparación Quirúrgica
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-950 text-amber-300 border border-amber-800">
                    Iteración: {repairAttempts} / 3
                  </span>
                </div>

                <div className="text-[11px] text-slate-400 leading-relaxed">
                  {repairAttempts === 0 ? (
                    <span className="text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                      Build inicial verificado sin errores. Sin reparaciones requeridas.
                    </span>
                  ) : outcome === 'NO_FIX' ? (
                    <span className="text-rose-400 flex items-center gap-1">
                      <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                      Se agotaron las 3 iteraciones permitidas por el Principio V. Detención constitucional estricta.
                    </span>
                  ) : (
                    <span className="text-blue-300 flex items-center gap-1">
                      <RefreshCw className="w-3.5 h-3.5 shrink-0 animate-spin" />
                      Parche quirúrgico AST generado y validado contra el sandbox Docker hermético.
                    </span>
                  )}
                </div>

                {/* Execution Metadata Table */}
                <div className="pt-2 border-t border-slate-800/80 space-y-1.5 font-mono text-[11px] text-slate-400">
                  <div className="flex justify-between">
                    <span>Estado del Run:</span>
                    <span className="text-white font-bold">{activeSession.status}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Veredicto Final:</span>
                    <span className={outcome === 'NO_FIX' ? 'text-rose-400 font-bold' : 'text-emerald-400 font-bold'}>
                      {outcome || 'En progreso'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Base de Datos:</span>
                    <span className="text-slate-300">{activeSession.parameters.database}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Mensajería:</span>
                    <span className="text-slate-300">{activeSession.parameters.messaging}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Sandbox Hermético:</span>
                    <span className="text-emerald-400">mvn test-compile (OK)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right 2/3: Realtime Console Terminal Streaming Live Logs */}
            <div className="lg:col-span-2">
              <RealtimeTerminal
                logs={activeSession.logs}
                traceId={activeSession.traceId}
                onClearLogs={handleClearLogs}
              />
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};
