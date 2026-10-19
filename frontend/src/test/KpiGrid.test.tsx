import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KpiGrid } from '../components/layout/KpiGrid';

describe('KpiGrid', () => {
  it('renders all 4 executive KPI cards', () => {
    render(
      <KpiGrid
        currentPhase="VERIFICATION"
        sandboxStatus="RUNNING"
        repairIteration={1}
        maxRepairs={3}
      />
    );

    expect(screen.getByText('Fase Actual')).toBeInTheDocument();
    expect(screen.getByText('VERIFICATION')).toBeInTheDocument();
    expect(screen.getByText('Estado del Sandbox')).toBeInTheDocument();
    expect(screen.getByText('RUNNING')).toBeInTheDocument();
    expect(screen.getByText('Iteración Auto-Reparación')).toBeInTheDocument();
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.getByText('Límite Constitucional')).toBeInTheDocument();
    expect(screen.getByText('Máx 3 (Principio V)')).toBeInTheDocument();
  });

  it('renders honest diagnostic for SKIPPED_BY_CHOICE', () => {
    render(
      <KpiGrid
        currentPhase="TERMINAL"
        sandboxStatus="SKIPPED_BY_CHOICE"
        repairIteration={0}
        maxRepairs={3}
      />
    );

    expect(screen.getByText('SKIPPED_BY_CHOICE')).toBeInTheDocument();
  });
});
