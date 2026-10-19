import { useState, useEffect, useCallback, useRef } from 'react';
import type { RunStatusResponse } from '../types/blueprintGraph';
import { getRunStatus } from '../services/blueprintService';

export interface UseStatusPollingOptions {
  traceId: string | null;
  apiKey?: string;
  baseUrl?: string;
  enabled?: boolean;
  intervalMs?: number;
  onStatusChange?: (status: RunStatusResponse) => void;
  onComplete?: (finalStatus: RunStatusResponse) => void;
  onError?: (error: Error) => void;
}

export function useStatusPolling({
  traceId,
  apiKey = '',
  baseUrl = 'http://localhost:8000',
  enabled = true,
  intervalMs = 1000,
  onStatusChange,
  onComplete,
  onError,
}: UseStatusPollingOptions) {
  const [isPolling, setIsPolling] = useState(false);
  const [currentStatus, setCurrentStatus] = useState<RunStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeRef = useRef(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const onStatusChangeRef = useRef(onStatusChange);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
    onCompleteRef.current = onComplete;
    onErrorRef.current = onError;
  });

  const stopPolling = useCallback(() => {
    activeRef.current = false;
    setIsPolling(false);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const poll = useCallback(async () => {
    if (!traceId || !activeRef.current) return;

    try {
      const result = await getRunStatus(traceId, apiKey, baseUrl);
      if (!activeRef.current) return;

      setCurrentStatus(result);
      setError(null);
      onStatusChangeRef.current?.(result);

      if (result.status === 'SUCCESS' || result.status === 'NO_FIX' || result.status === 'ERROR') {
        stopPolling();
        onCompleteRef.current?.(result);
      } else {
        timerRef.current = setTimeout(poll, intervalMs);
      }
    } catch (err: any) {
      if (!activeRef.current) return;
      const errorObj = err instanceof Error ? err : new Error(String(err));
      setError(errorObj.message);
      onErrorRef.current?.(errorObj);
      // For temporary network glitches, continue polling with backoff
      timerRef.current = setTimeout(poll, intervalMs * 1.5);
    }
  }, [traceId, apiKey, baseUrl, intervalMs, stopPolling]);

  useEffect(() => {
    if (enabled && traceId) {
      activeRef.current = true;
      setIsPolling(true);
      setError(null);
      poll();
    } else {
      stopPolling();
    }

    return () => {
      stopPolling();
    };
  }, [enabled, traceId, poll, stopPolling]);

  return {
    isPolling,
    currentStatus,
    error,
    stopPolling,
    pollOnce: poll,
  };
}

