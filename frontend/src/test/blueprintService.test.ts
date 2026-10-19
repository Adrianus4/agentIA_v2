import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { submitBlueprint, getRunStatus, getDefaultBlueprint } from '../services/blueprintService';
import type { BlueprintRunRequest } from '../types/blueprintGraph';

describe('blueprintService', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('provides a valid default blueprint template', () => {
    const bp = getDefaultBlueprint();
    expect(bp).toBeDefined();
    expect(bp.name).toBe('CustomerBillingService');
    expect(bp.serviceName).toBe('customer-billing-service');
    expect(bp.domainModels).toBeInstanceOf(Array);
  });

  it('submits a blueprint run request with x-api-key header', async () => {
    const mockResponse = {
      trace_id: 'test-trace-123',
      workspace_dir: '/tmp/workspace',
      blueprint: { name: 'CustomerBillingService' },
      attempts: 0,
      validation: { valid: true, diagnostics: [] },
      verification: { success: true, wall_time_seconds: 1.2 },
      outcome: 'PATCHED',
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const request: BlueprintRunRequest = {
      workspace_dir: '/tmp/workspace',
      blueprint: { name: 'CustomerBillingService' },
    };

    const result = await submitBlueprint(request, 'test-secret-key', 'http://localhost:8000');

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/v1/blueprint/run?mode=async', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': 'test-secret-key',
      },
      body: JSON.stringify(request),
    });
    expect(result.trace_id).toBe('test-trace-123');
    expect(result.outcome).toBe('PATCHED');
  });

  it('polls the status route after a 202 until the run reaches a terminal state', async () => {
    vi.useFakeTimers();
    const finalState = {
      trace_id: 'trace-async',
      attempts: 1,
      outcome: 'SUCCESS',
      validation: { valid: true, diagnostics: [] },
      verification: { success: true, wall_time_seconds: 3.4 },
    };
    (global.fetch as any)
      .mockResolvedValueOnce({ ok: true, status: 202, json: async () => ({ trace_id: 'trace-async', status: 'RUNNING' }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ trace_id: 'trace-async', status: 'RUNNING', stage: 'verify', repair_attempts: 0 }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ trace_id: 'trace-async', status: 'SUCCESS', repair_attempts: 1, state: finalState }) });

    const stages: string[] = [];
    const pending = submitBlueprint(
      { workspace_dir: '/tmp/ws', blueprint: { name: 'Demo' } },
      'k',
      'http://localhost:8000',
      '',
      (status) => stages.push(status.stage || status.status)
    );
    await vi.advanceTimersByTimeAsync(5000);
    const result = await pending;
    vi.useRealTimers();

    expect(global.fetch).toHaveBeenCalledTimes(3);
    expect((global.fetch as any).mock.calls[1][0]).toBe('http://localhost:8000/v1/blueprint/status/trace-async');
    expect(stages).toEqual(['verify', 'SUCCESS']);
    expect(result.outcome).toBe('SUCCESS');
    expect(result.attempts).toBe(1);
  });

  it('throws an informative error when submission fails', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      text: async () => JSON.stringify({ detail: 'Invalid API key' }),
    });

    const request: BlueprintRunRequest = {
      workspace_dir: '/tmp/workspace',
      blueprint: {},
    };

    await expect(
      submitBlueprint(request, 'bad-key', 'http://localhost:8000')
    ).rejects.toThrow('API Error (401)');
  });

  it('queries run status by trace ID with x-api-key header', async () => {
    const mockStatus = {
      trace_id: 'test-trace-123',
      blueprint_name: 'CustomerBillingService',
      status: 'SUCCESS',
      repair_attempts: 1,
      outcome: 'PATCHED',
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockStatus,
    });

    const result = await getRunStatus('test-trace-123', 'test-secret-key', 'http://localhost:8000');

    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/v1/blueprint/status/test-trace-123', {
      method: 'GET',
      headers: {
        'x-api-key': 'test-secret-key',
      },
    });
    expect(result.status).toBe('SUCCESS');
    expect(result.repair_attempts).toBe(1);
  });

  it('generates heuristic draft for payment directive with Kafka messaging and Panache models', async () => {
    const { draftSpec, generateHeuristicDraft } = await import('../services/blueprintService');
    const draft = generateHeuristicDraft('Crear un servicio de pagos en soles con Kafka y limites diarios');

    expect(draft.service_name).toBe('payment-transfers-service');
    expect(draft.technical_matrix.database).toBe('POSTGRESQL');
    expect(draft.technical_matrix.messaging).toBe('KAFKA');
    expect(draft.user_stories.length).toBeGreaterThan(0);
    expect(draft.domain_models.length).toBeGreaterThan(0);
    expect(draft.domain_models[0].name).toBe('PaymentTransfer');
    expect(draft.domain_models[0].fields.some((f) => f.name === 'amount')).toBe(true);

    // draftSpec falls back gracefully when backend fetch fails
    (global.fetch as any).mockRejectedValueOnce(new Error('Connection refused'));
    const fetchedDraft = await draftSpec({
      directive: 'Crear un servicio de pagos en soles con Kafka y limites diarios',
    });
    expect(fetchedDraft.service_name).toBe('payment-transfers-service');
  });

  it('calls POST /v1/spec/draft when backend responds successfully', async () => {
    const { draftSpec } = await import('../services/blueprintService');
    const mockDraftResponse = {
      service_name: 'custom-pmo-service',
      package_name: 'com.tcs.custom',
      business_objective: 'Procesamiento de directivas PMO',
      technical_matrix: {
        database: 'POSTGRESQL',
        messaging: 'KAFKA',
        scope: 'HIGH',
        qps: 5000,
        transactional_model: 'ACID',
      },
      user_stories: [
        {
          title: 'Directiva ejecutada',
          given: 'Servicio listo',
          when: 'Se envía directiva',
          then: 'Se procesa exitosamente',
        },
      ],
      domain_models: [
        {
          name: 'PmoDirective',
          table_name: 'pmo_directives',
          fields: [{ name: 'id', type: 'UUID', nullable: false, constraints: ['@NotNull'] }],
        },
      ],
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockDraftResponse,
    });

    const result = await draftSpec(
      {
        directive: 'PMO Directive Test',
        service_name: 'custom-pmo-service',
      },
      'secret-key',
      'http://localhost:8000'
    );

    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/v1/spec/draft', expect.objectContaining({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': 'secret-key',
      },
    }));
    expect(result.service_name).toBe('custom-pmo-service');
    expect(result.domain_models[0].name).toBe('PmoDirective');
  });
});

