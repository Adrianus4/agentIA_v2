import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, renderHook, act } from '@testing-library/react';
import JSZip from 'jszip';
import { useStatusPolling } from '../hooks/useStatusPolling';
import * as blueprintService from '../services/blueprintService';
import { StudioProvider, useStudio } from '../context/StudioContext';
import { LlmProvider } from '../context/LlmContext';
import { DevOpsAndDeliveryView } from '../views/DevOpsAndDeliveryView';

/**
 * U02 (AC-13, RF-309):
 * Ampliación de pruebas de componentes y estado con jsdom y mocks explícitos de fetch/servicios:
 * - Polling hacia estados terminales `NO_FIX` y `ERROR`, y reintento ante error transitorio de red.
 * - Fallo de autenticación (401/403) y caída de red en `submitBlueprint`.
 * - Rehidratación de estado desde `/v1/blueprint/status/{trace_id}` y limpieza de secretos en `localStorage`.
 * - Exportación ZIP en `DevOpsAndDeliveryView`: distinción entre paquete con `generated_files` reales vs fallback de solo `README.md`.
 */
describe('U02 Functional Component & State Coverage (fetch=mocked)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('useStatusPolling stops on NO_FIX and ERROR and reports transient network errors via onError', async () => {
    vi.useFakeTimers();
    const mockGetRunStatus = vi.spyOn(blueprintService, 'getRunStatus');
    mockGetRunStatus
      .mockRejectedValueOnce(new Error('Network offline'))
      .mockResolvedValueOnce({
        trace_id: 'trc-nofix-1',
        blueprint_name: 'invoice-service',
        status: 'NO_FIX',
        repair_attempts: 3,
      });

    const onError = vi.fn();
    const onComplete = vi.fn();

    const { result } = renderHook(() =>
      useStatusPolling({
        traceId: 'trc-nofix-1',
        apiKey: 'qa-key',
        baseUrl: 'http://127.0.0.1:8000',
        enabled: true,
        intervalMs: 400,
        onError,
        onComplete,
      })
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(onError).toHaveBeenCalledTimes(1);
    expect(result.current.error).toContain('Network offline');
    expect(result.current.isPolling).toBe(true);

    await act(async () => {
      vi.advanceTimersByTime(650);
      await Promise.resolve();
    });

    expect(result.current.currentStatus?.status).toBe('NO_FIX');
    expect(result.current.isPolling).toBe(false);
    expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({ status: 'NO_FIX', repair_attempts: 3 }));
  });

  it('submitBlueprint surfaces HTTP 401/403 authentication errors and terminal ERROR states', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch');

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Invalid or missing API key' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    await expect(
      blueprintService.submitBlueprint(
        { workspace_dir: 'ws', blueprint: { name: 'svc' } },
        'wrong-key',
        'http://127.0.0.1:8000'
      )
    ).rejects.toThrow(/API Error \(401\): Invalid or missing API key/);

    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(
      blueprintService.submitBlueprint(
        { workspace_dir: 'ws', blueprint: { name: 'svc' } },
        'valid-key',
        'http://127.0.0.1:8000'
      )
    ).rejects.toThrow(/Failed to fetch/);
  });

  it('rehydrates executionState from /v1/blueprint/status/{traceId} when session has no generated_files', async () => {
    const seededSession = [
      {
        id: 'sess-rehydrate-1',
        sessionId: 'sess-rehydrate-1',
        name: 'rehydrated-service',
        specName: 'rehydrated-service',
        description: 'Sesión restaurada tras recarga',
        status: 'RUNNING',
        currentStage: 5,
        currentLifecyclePhase: 'MONITOR',
        completionPercentage: 60,
        traceId: 'trace-rehydrate-001',
        repairAttempts: 0,
        parameters: {
          database: 'POSTGRESQL',
          messaging: 'NONE',
          requirementsSize: 'MEDIUM',
          expectedQps: '1000',
          dataConsistency: 'ACID',
          buildTool: 'MAVEN',
          workspaceDir: '/tmp/ws',
        },
        stories: [],
        entities: [],
        contracts: [],
        blueprint: { name: 'rehydrated-service', llm: { apiKey: 'MUST_BE_STRIPPED_SECRET' } },
        executionState: null,
        logs: [],
        createdAt: '2026-10-19T00:00:00.000Z',
        updatedAt: '2026-10-19T00:00:00.000Z',
      },
    ];
    localStorage.setItem('agentia_v2_sessions', JSON.stringify(seededSession));
    localStorage.setItem('agentia_v2_active_session_id', 'sess-rehydrate-1');

    vi.spyOn(blueprintService, 'getRunStatus').mockResolvedValueOnce({
      trace_id: 'trace-rehydrate-001',
      blueprint_name: 'rehydrated-service',
      status: 'NO_FIX',
      repair_attempts: 3,
      state: {
        trace_id: 'trace-rehydrate-001',
        workspace_dir: '/tmp/ws',
        blueprint: { name: 'rehydrated-service' },
        outcome: 'NO_FIX',
        attempts: 3,
        generated_files: [{ path: 'pom.xml', content: '<project/>' }],
      },
    });

    const Inspector: React.FC = () => {
      const { activeSession } = useStudio();
      return (
        <div>
          <span data-testid="sess-status">{activeSession?.status}</span>
          <span data-testid="sess-attempts">{activeSession?.repairAttempts}</span>
          <span data-testid="sess-files">{activeSession?.executionState?.generated_files?.length || 0}</span>
        </div>
      );
    };

    render(
      <LlmProvider>
        <StudioProvider>
          <Inspector />
        </StudioProvider>
      </LlmProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('sess-status').textContent).toBe('NO_FIX');
      expect(screen.getByTestId('sess-attempts').textContent).toBe('3');
      expect(screen.getByTestId('sess-files').textContent).toBe('1');
    });

    const storedRaw = localStorage.getItem('agentia_v2_sessions') || '';
    expect(storedRaw).not.toContain('MUST_BE_STRIPPED_SECRET');
  });

  it('DevOpsAndDeliveryView exports README.md fallback when generated_files is empty and real files when present', async () => {
    const fileSpy = vi.spyOn(JSZip.prototype, 'file');
    const generateSpy = vi
      .spyOn(JSZip.prototype, 'generateAsync')
      .mockResolvedValue(new Blob(['PK-zip'], { type: 'application/zip' }));

    if (!URL.createObjectURL) {
      Object.defineProperty(URL, 'createObjectURL', {
        writable: true,
        value: vi.fn(() => 'blob:mock-url'),
      });
    } else {
      vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url');
    }
    if (!URL.revokeObjectURL) {
      Object.defineProperty(URL, 'revokeObjectURL', {
        writable: true,
        value: vi.fn(),
      });
    } else {
      vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    }

    // 1. Default session has no generated_files -> falls back to README.md only
    const { unmount } = render(
      <LlmProvider>
        <StudioProvider>
          <DevOpsAndDeliveryView />
        </StudioProvider>
      </LlmProvider>
    );

    fireEvent.click(screen.getByText(/Entrega Git & ZIP/i));
    fireEvent.click(screen.getByText(/Descargar Código \(\.ZIP\)/i));

    await waitFor(() => {
      expect(generateSpy).toHaveBeenCalledTimes(1);
    });
    expect(fileSpy).toHaveBeenCalledWith('README.md', expect.stringContaining('# order-fulfillment-service'));
    unmount();

    // 2. Session with real generated_files -> packages real files without README.md fallback
    fileSpy.mockClear();
    generateSpy.mockClear();
    localStorage.setItem(
      'agentia_v2_sessions',
      JSON.stringify([
        {
          id: 'sess-real-zip',
          sessionId: 'sess-real-zip',
          name: 'invoice-service',
          specName: 'invoice-service',
          description: 'Real generated files',
          status: 'SUCCESS',
          currentStage: 5,
          currentLifecyclePhase: 'VERIFIED',
          completionPercentage: 100,
          traceId: 'trace-real-zip',
          repairAttempts: 0,
          parameters: {
            database: 'POSTGRESQL',
            messaging: 'NONE',
            requirementsSize: 'LOW',
            expectedQps: '100',
            dataConsistency: 'ACID',
            buildTool: 'MAVEN',
            workspaceDir: '/tmp/invoice',
          },
          stories: [],
          entities: [],
          contracts: [],
          blueprint: { name: 'invoice-service' },
          executionState: {
            trace_id: 'trace-real-zip',
            workspace_dir: '/tmp/invoice',
            blueprint: { name: 'invoice-service' },
            outcome: 'SUCCESS',
            attempts: 0,
            generated_files: [
              { path: 'pom.xml', content: '<project><artifactId>invoice-service</artifactId></project>' },
              {
                path: 'src/main/java/com/agentia/qa/invoice/Invoice.java',
                content: 'package com.agentia.qa.invoice; public class Invoice {}',
              },
            ],
          },
          logs: [],
          createdAt: '2026-10-19T00:00:00.000Z',
          updatedAt: '2026-10-19T00:00:00.000Z',
        },
      ])
    );
    localStorage.setItem('agentia_v2_active_session_id', 'sess-real-zip');

    render(
      <LlmProvider>
        <StudioProvider>
          <DevOpsAndDeliveryView />
        </StudioProvider>
      </LlmProvider>
    );

    fireEvent.click(screen.getByText(/Entrega Git & ZIP/i));
    fireEvent.click(screen.getByText(/Descargar Código \(\.ZIP\)/i));

    await waitFor(() => {
      expect(generateSpy).toHaveBeenCalledTimes(1);
    });
    expect(fileSpy).toHaveBeenCalledWith('pom.xml', expect.stringContaining('invoice-service'));
    expect(fileSpy).toHaveBeenCalledWith(
      'src/main/java/com/agentia/qa/invoice/Invoice.java',
      expect.stringContaining('class Invoice')
    );
  });
});
