import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RealtimeTerminal } from '../components/orchestration/RealtimeTerminal';
import type { LogEntry } from '../types/blueprintGraph';

describe('RealtimeTerminal', () => {
  const sampleLogs: LogEntry[] = [
    { id: '1', timestamp: '23:15:00', level: 'SYSTEM', message: 'Orchestrator graph initialized' },
    { id: '2', timestamp: '23:15:01', level: 'INFO', message: 'Validation completed successfully' },
    { id: '3', timestamp: '23:15:02', level: 'WARN', message: 'Surefire warning: deprecated API' },
    { id: '4', timestamp: '23:15:03', level: 'ERROR', message: 'Test failed: expected 200 got 500' },
  ];

  it('renders Mac terminal title bar and colored logs', () => {
    render(<RealtimeTerminal logs={sampleLogs} traceId="trace-test-123" />);

    expect(screen.getByText('trace-test-123')).toBeInTheDocument();
    expect(screen.getByText('Orchestrator graph initialized')).toBeInTheDocument();
    expect(screen.getByText('Validation completed successfully')).toBeInTheDocument();
    expect(screen.getByText('Surefire warning: deprecated API')).toBeInTheDocument();
    expect(screen.getByText('Test failed: expected 200 got 500')).toBeInTheDocument();
  });

  it('renders placeholder when logs are empty', () => {
    render(<RealtimeTerminal logs={[]} traceId="trace-empty" />);
    expect(screen.getByText(/waiting for orchestrator execution/i)).toBeInTheDocument();
  });
});
