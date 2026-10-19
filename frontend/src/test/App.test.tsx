import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from '../App';

describe('App Multi-Stage Studio Integration', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn();
    localStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('renders complete studio layout with Sidebar, Header, and 5 Engineering Lifecycle Tabs', () => {
    render(<App />);

    // Brand and Header
    expect(screen.getAllByText(/AgentIA/i).length).toBeGreaterThan(0);
    expect(screen.getByText('Enterprise Studio')).toBeInTheDocument();
    expect(screen.getByText(/Microservice Architecture & LangGraph State Machine/i)).toBeInTheDocument();

    // Sidebar
    expect(screen.getByText('+ Nuevo Microservicio')).toBeInTheDocument();
    expect(screen.getByText('Microservicios (2)')).toBeInTheDocument();
    expect(screen.getAllByText('order-fulfillment-service').length).toBeGreaterThan(0);

    // 5 Engineering Lifecycle Tabs
    expect(screen.getAllByText(/1\. Especificación/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/2\. Arquitectura & Modelos/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/3\. Código & Pruebas/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/4\. Verificación & Calidad/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/5\. DevOps & Despliegue/i).length).toBeGreaterThan(0);

    // Initial Tab: Specification & Definition form + Requirements Graph Tracker
    expect(screen.getByRole('region', { name: /Grafo de Requisitos & Especificación/i })).toBeInTheDocument();
    expect(screen.getByText(/Definición Integral del Microservicio/i)).toBeInTheDocument();
    expect(screen.getByText(/Matriz de Parámetros Técnicos Quarkus/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Historias de Usuario BDD/i).length).toBeGreaterThan(0);

    // Telemetry Terminal Toggle in Footer
    expect(screen.getByText(/Terminal \/ Estado de Ejecución/i)).toBeInTheDocument();
  });

  it('navigates across lifecycle tabs including Arquitectura & Modelos and Código & Pruebas', () => {
    render(<App />);

    // Navigate to Arquitectura & Modelos
    const archTab = screen.getAllByText(/2\. Arquitectura & Modelos/i)[0];
    fireEvent.click(archTab);

    expect(screen.getByText(/Arquitectura Hexagonal & Modelos de Dominio/i)).toBeInTheDocument();
    expect(screen.getByText(/1\. Core Dominio/i)).toBeInTheDocument();
    expect(screen.getByText(/Inbound Adapters/i)).toBeInTheDocument();

    // Navigate to Código & Pruebas
    const codeTab = screen.getAllByText(/3\. Código & Pruebas/i)[0];
    fireEvent.click(codeTab);

    expect(screen.getByText(/Etapa 3: Explorador de Código & Pruebas Quarkus/i)).toBeInTheDocument();
  });

  it('submits a run from stepped intake and automatically opens the live graph monitor telemetry drawer', async () => {
    const mockResponse = {
      trace_id: 'trace-test-789',
      workspace_dir: '/tmp/agentia-workspace',
      blueprint: { name: 'OrderFulfillmentService' },
      attempts: 1,
      validation: { valid: true, diagnostics: [] },
      verification: {
        success: true,
        wall_time_seconds: 1.12,
        runner_name: 'hermetic-sandbox',
        image: 'maven-jdk21:latest',
        raw_output: 'Tests run: 8, Failures: 0, Errors: 0, Skipped: 0',
      },
      outcome: 'PATCHED',
    };

    (global.fetch as any).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('/v1/blueprint/run')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockResponse,
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => [],
      });
    });

    render(<App />);

    // Step 1: On Tab 0 (Especificación), click Continuar a Arquitectura & Modelos
    const continueBtn = screen.getAllByRole('button', { name: /Continuar a Arquitectura & Modelos/i })[0];
    fireEvent.click(continueBtn);

    // Verify Tab 2 (Arquitectura & Modelos) is active
    expect(screen.getByText(/Arquitectura Hexagonal & Modelos de Dominio/i)).toBeInTheDocument();

    // Step 2: On Tab 2, click Aprobar y Generar Microservicio
    const generateBtns = screen.getAllByRole('button', { name: /Aprobar y Generar Microservicio/i });
    fireEvent.click(generateBtns[0]);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    // Step 3: Automatically opens the Execution Drawer with Live Graph Monitor
    await waitFor(() => {
      expect(screen.getByRole('region', { name: /Panel de Telemetría y Ejecución/i })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: /Monitor de Grafo en Vivo/i })).toBeInTheDocument();
      expect(screen.getByText(/Ruta de Ejecución del Grafo LangGraph/i)).toBeInTheDocument();
      expect(screen.getByTestId('live-graph-node-validate')).toBeInTheDocument();
      expect(screen.getByTestId('live-graph-node-generate')).toBeInTheDocument();
      expect(screen.getByTestId('live-graph-node-verify')).toBeInTheDocument();
      expect(screen.getByTestId('live-graph-node-repair')).toBeInTheDocument();
      expect(screen.getByTestId('live-graph-node-terminal')).toBeInTheDocument();
    });
  });

  it('runs Guided Specification flow: fills directive from chip, structures spec, and populates Panache models on Tab 2', async () => {
    render(<App />);

    // Check presence of Directive elements on Tab 0
    expect(screen.getByText(/Directiva de Negocio o Comando del PMO/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Estructurar Especificación/i })).toBeInTheDocument();

    // Click Payment Service chip
    const paymentChip = screen.getByText('Payment Service');
    fireEvent.click(paymentChip);

    // Directive textarea is populated
    const directiveInput = screen.getByPlaceholderText(/Crear un servicio de procesamiento de pagos/i);
    expect((directiveInput as HTMLTextAreaElement).value).toContain('pagos y transferencias en soles');

    // Click Estructurar Especificación
    const analyzeBtn = screen.getByRole('button', { name: /Estructurar Especificación/i });
    fireEvent.click(analyzeBtn);

    // Continue to Tab 2: Arquitectura & Modelos
    await waitFor(() => {
      expect(screen.getByText(/Especificación estructurada con éxito/i)).toBeInTheDocument();
    });

    const continueBtn = screen.getAllByRole('button', { name: /Continuar a Arquitectura & Modelos/i })[0];
    fireEvent.click(continueBtn);

    // Verify Panache Entity Modeler on Tab 2 displays populated PaymentTransfer entity
    await waitFor(() => {
      expect(screen.getAllByText(/Modelador de Entidades Panache JPA/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/PaymentTransfer/i).length).toBeGreaterThan(0);
    });
  });

  it('switches microservice session when clicked in the sidebar', () => {
    render(<App />);

    const customerServiceBtn = screen.getByText('customer-identity-service');
    fireEvent.click(customerServiceBtn);

    // Form reflects the newly selected service
    expect(screen.getByDisplayValue('customer-identity-service')).toBeInTheDocument();
  });

  it('opens LLM Settings pop-up drawer when clicking the LLM engine badge in the header', () => {
    render(<App />);

    const llmBadge = screen.getByTitle(/Abrir ventana emergente de Configuración del Motor LLM/i);
    fireEvent.click(llmBadge);

    expect(screen.getByRole('dialog', { name: /Configuración del Motor LLM/i })).toBeInTheDocument();
    expect(screen.getByText(/Memoria Efímera en Sesión/i)).toBeInTheDocument();

    const closeBtn = screen.getByRole('button', { name: /Cerrar modal/i });
    fireEvent.click(closeBtn);

    expect(screen.queryByRole('dialog', { name: /Configuración del Motor LLM/i })).not.toBeInTheDocument();
  });
});
