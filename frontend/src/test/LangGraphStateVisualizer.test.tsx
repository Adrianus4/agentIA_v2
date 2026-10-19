import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LangGraphStateVisualizer } from '../components/orchestration/LangGraphStateVisualizer';
import type { LangGraphNodeState } from '../types/blueprintGraph';

describe('LangGraphStateVisualizer', () => {
  const initialNodes: Record<string, LangGraphNodeState> = {
    validate: { id: 'validate', label: 'Validate', description: 'Schema & BDD stories validation', status: 'IDLE' },
    verify: { id: 'verify', label: 'Verify', description: 'Hermetic Docker sandbox test', status: 'IDLE' },
    repair: { id: 'repair', label: 'Repair', description: 'AST diagnostics & surgical patch', status: 'IDLE' },
    terminal: { id: 'terminal', label: 'Outcome', description: 'Final release or NO_FIX', status: 'IDLE' },
  };

  it('renders all 4 LangGraph nodes', () => {
    render(<LangGraphStateVisualizer nodes={initialNodes} currentIteration={0} outcome={null} />);
    
    expect(screen.getByTestId('node-card-validate')).toBeInTheDocument();
    expect(screen.getByTestId('node-card-verify')).toBeInTheDocument();
    expect(screen.getByTestId('node-card-repair')).toBeInTheDocument();
    expect(screen.getByTestId('node-card-terminal')).toBeInTheDocument();
  });

  it('renders active status and repair iteration counter', () => {
    const runningNodes: Record<string, LangGraphNodeState> = {
      ...initialNodes,
      validate: { ...initialNodes.validate, status: 'PASSED' },
      verify: { ...initialNodes.verify, status: 'ACTIVE' },
      repair: { ...initialNodes.repair, status: 'REPAIRING' },
    };

    render(<LangGraphStateVisualizer nodes={runningNodes} currentIteration={2} outcome={null} />);

    expect(screen.getByText(/2 \/ 3/i)).toBeInTheDocument();
  });

  it('renders NO_FIX outcome correctly on terminal node', () => {
    const failedNodes: Record<string, LangGraphNodeState> = {
      ...initialNodes,
      validate: { ...initialNodes.validate, status: 'PASSED' },
      verify: { ...initialNodes.verify, status: 'PASSED' },
      repair: { ...initialNodes.repair, status: 'NO_FIX' },
      terminal: { ...initialNodes.terminal, status: 'NO_FIX' },
    };

    render(<LangGraphStateVisualizer nodes={failedNodes} currentIteration={3} outcome="NO_FIX" />);

    expect(screen.getAllByText('NO_FIX').length).toBeGreaterThan(0);
  });
});
