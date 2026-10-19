import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Header } from '../components/layout/Header';

describe('Header Enterprise Branding', () => {
  it('renders official TCS logo image with accessible alt text', () => {
    render(<Header />);

    const logo = screen.getByAltText('Tata Consultancy Services');
    expect(logo).toBeInTheDocument();
    expect(logo).toHaveAttribute('src', '/tcs-logo-light.png');
  });

  it('renders Enterprise Studio title and state machine subtitle', () => {
    render(<Header traceId="trace-test-123" isRunning={true} />);

    expect(screen.getByText(/Enterprise Studio/i)).toBeInTheDocument();
    expect(screen.getByText(/Microservice Architecture & LangGraph State Machine/i)).toBeInTheDocument();
    expect(screen.getByText('trace-test-123')).toBeInTheDocument();
  });
});

