import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useStatusPolling } from '../hooks/useStatusPolling';
import * as blueprintService from '../services/blueprintService';

describe('useStatusPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('polls repeatedly while status is RUNNING and stops on SUCCESS', async () => {
    const mockGetRunStatus = vi.spyOn(blueprintService, 'getRunStatus');
    
    mockGetRunStatus
      .mockResolvedValueOnce({
        trace_id: 'trace-1',
        blueprint_name: 'test-bp',
        status: 'RUNNING',
        repair_attempts: 0,
      })
      .mockResolvedValueOnce({
        trace_id: 'trace-1',
        blueprint_name: 'test-bp',
        status: 'SUCCESS',
        repair_attempts: 1,
      });

    const onComplete = vi.fn();

    const { result } = renderHook(() =>
      useStatusPolling({
        traceId: 'trace-1',
        apiKey: 'key',
        baseUrl: 'http://localhost:8000',
        enabled: true,
        intervalMs: 1000,
        onComplete,
      })
    );

    expect(result.current.isPolling).toBe(true);

    // Initial immediate poll
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockGetRunStatus).toHaveBeenCalledTimes(1);
    expect(result.current.currentStatus?.status).toBe('RUNNING');
    expect(result.current.isPolling).toBe(true);

    // Advance timer for second poll
    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
    });

    expect(mockGetRunStatus).toHaveBeenCalledTimes(2);
    expect(result.current.currentStatus?.status).toBe('SUCCESS');
    expect(result.current.isPolling).toBe(false);
    expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({ status: 'SUCCESS' }));
  });

  it('stops polling when traceId is null or enabled is false', async () => {
    const mockGetRunStatus = vi.spyOn(blueprintService, 'getRunStatus');

    const { result } = renderHook(() =>
      useStatusPolling({
        traceId: null,
        apiKey: 'key',
        baseUrl: 'http://localhost:8000',
        enabled: false,
      })
    );

    expect(result.current.isPolling).toBe(false);
    expect(mockGetRunStatus).not.toHaveBeenCalled();
  });
});

