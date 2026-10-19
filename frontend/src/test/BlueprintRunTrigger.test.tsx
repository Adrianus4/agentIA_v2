import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BlueprintRunTrigger } from '../components/orchestration/BlueprintRunTrigger';

describe('BlueprintRunTrigger', () => {
  it('renders inputs and submit button with default values', () => {
    render(
      <BlueprintRunTrigger
        onSubmit={vi.fn()}
        onQueryTrace={vi.fn()}
        isSubmitting={false}
      />
    );

    expect(screen.getByLabelText(/workspace directory/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/orchestrator api key/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /run orchestrator/i })).toBeInTheDocument();
  });

  it('validates JSON and blocks submission if invalid JSON is entered', () => {
    const onSubmit = vi.fn();
    render(
      <BlueprintRunTrigger
        onSubmit={onSubmit}
        onQueryTrace={vi.fn()}
        isSubmitting={false}
      />
    );

    const textarea = screen.getByLabelText(/blueprint json specification/i);
    fireEvent.change(textarea, { target: { value: '{ invalid json' } });

    expect(screen.getByText(/Invalid JSON:/)).toBeInTheDocument();
    
    const runBtn = screen.getByRole('button', { name: /run orchestrator/i });
    expect(runBtn).toBeDisabled();
  });

  it('submits valid blueprint when Run Orchestrator is clicked', () => {
    const onSubmit = vi.fn();
    render(
      <BlueprintRunTrigger
        onSubmit={onSubmit}
        onQueryTrace={vi.fn()}
        isSubmitting={false}
      />
    );

    const runBtn = screen.getByRole('button', { name: /run orchestrator/i });
    expect(runBtn).not.toBeDisabled();
    fireEvent.click(runBtn);

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        workspace_dir: expect.any(String),
        blueprint: expect.any(Object),
      }),
      expect.any(String),
      expect.any(String),
      expect.any(String)
    );
  });

  it('renders rich form with Natural Language prompt and Quarkus configuration', () => {
    render(
      <BlueprintRunTrigger
        onSubmit={vi.fn()}
        onQueryTrace={vi.fn()}
        isSubmitting={false}
      />
    );

    expect(screen.getByText(/Formulario Asistido \(NL & Quarkus\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Editor JSON Blueprint/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Requisitos de Negocio \/ Natural Language Prompt/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Nombre del Microservicio/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Framework/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Base de Datos/i)).toBeInTheDocument();
  });

  it('updates natural language prompt and submits enriched blueprint', () => {
    const onSubmit = vi.fn();
    render(
      <BlueprintRunTrigger
        onSubmit={onSubmit}
        onQueryTrace={vi.fn()}
        isSubmitting={false}
      />
    );

    const promptTextarea = screen.getByLabelText(/Requisitos de Negocio \/ Natural Language Prompt/i);
    fireEvent.change(promptTextarea, {
      target: { value: 'Microservicio de auditoria con persistencia en tiempo real.' },
    });

    const runBtn = screen.getByRole('button', { name: /run orchestrator/i });
    fireEvent.click(runBtn);

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submittedPayload = onSubmit.mock.calls[0][0];
    expect(submittedPayload.blueprint.naturalLanguagePrompt).toBe(
      'Microservicio de auditoria con persistencia en tiempo real.'
    );
  });

  it('switches preset template and updates service and database config', () => {
    const onSubmit = vi.fn();
    render(
      <BlueprintRunTrigger
        onSubmit={onSubmit}
        onQueryTrace={vi.fn()}
        isSubmitting={false}
      />
    );

    const orderPresetBtn = screen.getByRole('button', { name: /Order Management Service/i });
    fireEvent.click(orderPresetBtn);

    const runBtn = screen.getByRole('button', { name: /run orchestrator/i });
    fireEvent.click(runBtn);

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submittedPayload = onSubmit.mock.calls[0][0];
    expect(submittedPayload.blueprint.serviceName).toBe('order-management-service');
    expect(submittedPayload.blueprint.architecture).toBe('hexagonal');
  });
});
