import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  RequirementsGraphTracker,
  REQUIREMENTS_NODES,
} from '../components/orchestration/RequirementsGraphTracker';

describe('RequirementsGraphTracker', () => {
  it('renders all 5 requirements graph nodes in IDLE state', () => {
    render(
      <RequirementsGraphTracker
        isDrafting={false}
        isCompleted={false}
        storiesCount={0}
        entitiesCount={0}
      />
    );

    expect(screen.getByRole('region', { name: /Grafo de Requisitos & Especificación/i })).toBeInTheDocument();
    expect(screen.getByText('LISTO PARA ANALIZAR')).toBeInTheDocument();

    // Verify all 5 steps are present
    REQUIREMENTS_NODES.forEach((node) => {
      expect(screen.getByTestId(`requirements-node-${node.id}`)).toBeInTheDocument();
      expect(screen.getByText(node.title)).toBeInTheDocument();
      expect(screen.getByText(`Paso ${node.stepNumber}`)).toBeInTheDocument();
    });
  });

  it('renders in DRAFTING active state with pulsing status badge', () => {
    render(
      <RequirementsGraphTracker
        isDrafting={true}
        isCompleted={false}
        elapsedTime={1.2}
        storiesCount={0}
        entitiesCount={0}
      />
    );

    expect(screen.getByText('INFERIENDO REQUISITOS...')).toBeInTheDocument();
    expect(screen.getByText('1.2s')).toBeInTheDocument();
  });

  it('renders in COMPLETED state with checkmarks and summary telemetry bar', () => {
    render(
      <RequirementsGraphTracker
        isDrafting={false}
        isCompleted={true}
        elapsedTime={2.4}
        serviceName="payment-service"
        database="POSTGRESQL"
        messaging="KAFKA"
        storiesCount={3}
        entitiesCount={2}
      />
    );

    expect(screen.getByText('ESPECIFICACIÓN COMPILADA')).toBeInTheDocument();
    expect(screen.getByText('2.4s')).toBeInTheDocument();

    // Summary pills
    expect(screen.getByText('payment-service')).toBeInTheDocument();
    expect(screen.getByText('POSTGRESQL')).toBeInTheDocument();
    expect(screen.getByText('KAFKA')).toBeInTheDocument();
    expect(screen.getByText('3 Historias BDD')).toBeInTheDocument();
    expect(screen.getByText('2 Entidades Panache')).toBeInTheDocument();
    expect(screen.getByText('Listo para revisar y avanzar a Arquitectura ➜')).toBeInTheDocument();
  });

  it('renders in ERROR state with error badge', () => {
    render(
      <RequirementsGraphTracker
        isDrafting={false}
        isCompleted={false}
        error="Fallo al conectar con Gemini LLM"
      />
    );

    expect(screen.getByText('ERROR DE SÍNTESIS')).toBeInTheDocument();
  });

  it('renders in stepped execution mode with activeAgentLog and completed steps', () => {
    render(
      <RequirementsGraphTracker
        isDrafting={true}
        isCompleted={false}
        currentStepIndex={2}
        completedSteps={[1, 2]}
        activeAgentLog="[bdd_synthesizer] Sintetizando escenarios Given/When/Then..."
        storiesCount={2}
        entitiesCount={2}
      />
    );

    expect(screen.getByText('[bdd_synthesizer] Sintetizando escenarios Given/When/Then...')).toBeInTheDocument();
    expect(screen.getByText('Agente Activo')).toBeInTheDocument();

    const node1 = screen.getByTestId('requirements-node-parse');
    const node3 = screen.getByTestId('requirements-node-bdd');
    expect(node1).toBeInTheDocument();
    expect(node3).toBeInTheDocument();
  });

  it('triggers onStepClick when node card is clicked', () => {
    let clickedStep: number | null = null;
    render(
      <RequirementsGraphTracker
        isDrafting={false}
        isCompleted={false}
        onStepClick={(step) => {
          clickedStep = step;
        }}
      />
    );

    const node3 = screen.getByTestId('requirements-node-bdd');
    node3.click();
    expect(clickedStep).toBe(3);
  });
});
