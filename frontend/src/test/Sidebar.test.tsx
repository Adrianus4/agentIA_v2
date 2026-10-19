import { describe, it, expect } from 'vitest';

import { render, screen, fireEvent } from '@testing-library/react';
import { Sidebar } from '../components/layout/Sidebar';
import { StudioProvider } from '../context/StudioContext';
import { LlmProvider } from '../context/LlmContext';

describe('Sidebar Component', () => {
  it('renders TCS branding, new service button, and session list', () => {
    render(
      <LlmProvider>
        <StudioProvider>
          <Sidebar />
        </StudioProvider>
      </LlmProvider>
    );

    expect(screen.getByAltText('TCS Logo')).toBeInTheDocument();
    expect(screen.getByText('+ Nuevo Microservicio')).toBeInTheDocument();
    expect(screen.getByText('order-fulfillment-service')).toBeInTheDocument();
    expect(screen.getByText('customer-identity-service')).toBeInTheDocument();
  });

  it('filters sessions by search input', () => {
    render(
      <LlmProvider>
        <StudioProvider>
          <Sidebar />
        </StudioProvider>
      </LlmProvider>
    );

    const input = screen.getByPlaceholderText('Filtrar microservicios...');
    fireEvent.change(input, { target: { value: 'customer' } });

    expect(screen.getByText('customer-identity-service')).toBeInTheDocument();
    expect(screen.queryByText('order-fulfillment-service')).not.toBeInTheDocument();
  });

  it('handles clicking + Nuevo Microservicio to clear active selection', () => {
    render(
      <LlmProvider>
        <StudioProvider>
          <Sidebar />
        </StudioProvider>
      </LlmProvider>
    );

    const newBtn = screen.getByText('+ Nuevo Microservicio');
    fireEvent.click(newBtn);

    // Button gains active state class
    expect(newBtn.closest('button')).toHaveClass('bg-blue-600');
  });
});
