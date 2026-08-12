import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import LandingPage from './LandingPage';

vi.mock('../../lib/telemetry/serviceSignupTelemetry', () => ({
  recordServiceSignupEvent: vi.fn().mockResolvedValue(undefined),
}));

describe('LandingPage professional CTA', () => {
  it('renders the exact copy and link directly after the hero Get Started action', () => {
    render(<MemoryRouter><LandingPage /></MemoryRouter>);
    const link = screen.getByRole('link', { name: 'Sign up here' });
    expect(link).toHaveAttribute('href', '/register?intent=service-provider');
    expect(link.parentElement).toHaveTextContent('Signing up as a service professional? Sign up here');
    expect(link.parentElement.previousElementSibling).toHaveTextContent('Get Started');
  });
});
