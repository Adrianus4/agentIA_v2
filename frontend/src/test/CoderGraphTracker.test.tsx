import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  CoderGraphTracker,
  CODER_GRAPH_NODES,
} from '../components/orchestration/CoderGraphTracker';

describe('CoderGraphTracker', () => {
  it('renders all 5 Coder Graph nodes in pre-flight planned state', () => {
    render(
      <CoderGraphTracker
        architecture="hexagonal"
        isGenerating={false}
        isCompleted={false}
        serviceName="payment-service"
        entitiesCount={2}
        endpointsCount={3}
        storiesCount={2}
      />
    );

    expect(
      screen.getByRole('region', { name: /Grafo de Síntesis del Coder/i })
    ).toBeInTheDocument();

    expect(screen.getByText(/LISTO PARA SÍNTESIS/i)).toBeInTheDocument();
    expect(screen.getByText(/🏛️ Hexagonal \(Puertos & Adaptadores\)/i)).toBeInTheDocument();
    expect(screen.getByText(/2 Entidades/i)).toBeInTheDocument();
    expect(screen.getByText(/3 Endpoints/i)).toBeInTheDocument();

    CODER_GRAPH_NODES.forEach((node) => {
      expect(screen.getByText(node.title)).toBeInTheDocument();
      expect(screen.getByText(node.subLabel)).toBeInTheDocument();
    });
  });

  it('renders generating active state with pulse animation indicator', () => {
    render(
      <CoderGraphTracker
        architecture="layered"
        isGenerating={true}
        isCompleted={false}
        serviceName="billing-service"
      />
    );

    expect(screen.getByText(/SINTETIZANDO CÓDIGO/i)).toBeInTheDocument();
    expect(screen.getByText(/GENERANDO\.\.\./i)).toBeInTheDocument();
    expect(screen.getByText(/🏛️ Layered \(4 Capas Clásicas\)/i)).toBeInTheDocument();
  });

  it('renders completed state with check badges when generation finishes', () => {
    render(
      <CoderGraphTracker
        architecture="hexagonal-ddd"
        isGenerating={false}
        isCompleted={true}
        serviceName="order-service"
      />
    );

    expect(screen.getByText(/SÍNTESIS COMPLETADA/i)).toBeInTheDocument();
    expect(screen.getAllByText(/LISTO/i).length).toBe(CODER_GRAPH_NODES.length);
    expect(screen.getByText(/🏛️ Hexagonal \+ DDD/i)).toBeInTheDocument();
  });

  it('toggles collapsible component catalog mapping details drawer', () => {
    render(
      <CoderGraphTracker
        architecture="layered"
        isGenerating={false}
        isCompleted={false}
        serviceName="wallet-service"
        activeEntityName="Wallet"
      />
    );

    const toggleBtn = screen.getByRole('button', { name: /Ver Componentes/i });
    expect(toggleBtn).toBeInTheDocument();

    // Drawer starts closed
    expect(screen.queryByText(/WalletResource\.java/i)).not.toBeInTheDocument();

    // Open drawer
    fireEvent.click(toggleBtn);
    expect(screen.getByText(/WalletResource\.java/i)).toBeInTheDocument();
    expect(screen.getByText(/WalletService\.java/i)).toBeInTheDocument();
    expect(screen.getByText(/WalletRepository\.java/i)).toBeInTheDocument();
    expect(screen.getByText(/Wallet\.java/i)).toBeInTheDocument();

    // Close drawer
    fireEvent.click(screen.getByRole('button', { name: /Ocultar Componentes/i }));
    expect(screen.queryByText(/WalletResource\.java/i)).not.toBeInTheDocument();
  });
});
