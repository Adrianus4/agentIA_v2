import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ResponsiveTabGrid } from '../components/layout/ResponsiveTabGrid';
import { StudioProvider } from '../context/StudioContext';
import { LlmProvider } from '../context/LlmContext';

describe('ResponsiveTabGrid Component', () => {
  it('renders all 5 distinct engineering lifecycle stages', () => {
    render(
      <LlmProvider>
        <StudioProvider>
          <ResponsiveTabGrid />
        </StudioProvider>
      </LlmProvider>
    );

    expect(screen.getByText('1. Especificación')).toBeInTheDocument();
    expect(screen.getByText('2. Arquitectura & Modelos')).toBeInTheDocument();
    expect(screen.getByText('3. Código & Pruebas')).toBeInTheDocument();
    expect(screen.getByText('4. Verificación & Calidad')).toBeInTheDocument();
    expect(screen.getByText('5. DevOps & Despliegue')).toBeInTheDocument();
  });

  it('triggers onTabChange callback when tab is clicked', () => {
    const handleTabChange = vi.fn();
    render(
      <LlmProvider>
        <StudioProvider>
          <ResponsiveTabGrid activeTab={0} onTabChange={handleTabChange} />
        </StudioProvider>
      </LlmProvider>
    );

    const tab2 = screen.getByText('3. Código & Pruebas');
    fireEvent.click(tab2);

    expect(handleTabChange).toHaveBeenCalledWith(2);
  });
});
