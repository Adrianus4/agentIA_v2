import { describe, it, expect, vi, beforeEach } from 'vitest';

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SettingsDrawer } from '../components/layout/SettingsDrawer';
import { LlmProvider } from '../context/LlmContext';

describe('SettingsDrawer Pop-up Modal', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          ok: true,
          latency_ms: 35,
          message: 'Conexión verificada con backend y modelo',
        }),
      })
    );
  });
  it('renders modal dialog when open with TCS security banner and providers', () => {
    render(
      <LlmProvider>
        <SettingsDrawer isOpen={true} />
      </LlmProvider>
    );

    expect(screen.getByRole('dialog', { name: /Configuración del Motor LLM/i })).toBeInTheDocument();
    expect(screen.getByText(/Seguridad Empresarial TCS/i)).toBeInTheDocument();
    expect(screen.getByText(/Proveedor de Inteligencia Artificial/i)).toBeInTheDocument();
  });

  it('allows changing provider and testing connection latency', async () => {
    render(
      <LlmProvider>
        <SettingsDrawer isOpen={true} />
      </LlmProvider>
    );

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'groq' } });

    expect(screen.getByDisplayValue(/qwen-2.5-coder-32b/i)).toBeInTheDocument();

    const verifyBtn = screen.getByRole('button', { name: /Probar Conexión/i });
    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(screen.getByText(/Conectado/i)).toBeInTheDocument();
    });
  });

  it('allows selecting Local Ollama provider with Fedora RX 570 recommendations', async () => {
    render(
      <LlmProvider>
        <SettingsDrawer isOpen={true} />
      </LlmProvider>
    );

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'local' } });

    expect(screen.getByDisplayValue(/qwen2.5-coder:3b/i)).toBeInTheDocument();
    expect(screen.getByText(/RX 570 \/ 8GB/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/http:\/\/127.0.0.1:11434/i)).toBeInTheDocument();
    expect(screen.getAllByText(/TCS Gateway/i).length).toBeGreaterThan(0);
  });

  it('does not render when isOpen is false', () => {
    render(
      <LlmProvider>
        <SettingsDrawer isOpen={false} />
      </LlmProvider>
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
