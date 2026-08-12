import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import GetStartedPage from './GetStartedPage';
import { destinationAfterAuth, SERVICE_PROVIDER_INTENT } from '../../routes/authRoutes';

// A signed-in identity with no membership and no portal: the state that reaches
// this page. It is also, exactly, the state an email-confirmed service
// professional lands in -- their `intent` never survives the Supabase email
// template, so nothing here can tell the two apart. Hence the door.
const CONTEXT = { identity: { full_name: 'Ravi Kumar', email: 'ravi@example.test' }, onboarding_eligible: true };

vi.mock('../../store/authStore', () => ({
  useAuthStore: (selector) => selector({ sessionContext: CONTEXT, isAuthReady: true }),
}));

vi.mock('../../store/onboardingStore', () => ({
  useOnboardingStore: (selector) => selector({ setAdminProfile: vi.fn() }),
}));

describe('GetStartedPage service-professional door', () => {
  it('offers a way out to the professional portal', () => {
    render(<MemoryRouter><GetStartedPage /></MemoryRouter>);

    const link = screen.getByRole('link', { name: 'Register as a service professional' });
    expect(link.parentElement).toHaveTextContent('Here to work rather than to live here?');
  });

  it('lands on the same continuation point the OAuth path uses for this context', () => {
    // Parity is the acceptance criterion, so it is asserted against
    // `destinationAfterAuth` itself rather than against a copied literal: a
    // change to where a professional continues has to move both or neither.
    render(<MemoryRouter><GetStartedPage /></MemoryRouter>);

    const link = screen.getByRole('link', { name: 'Register as a service professional' });
    expect(link).toHaveAttribute('href', destinationAfterAuth(CONTEXT, SERVICE_PROVIDER_INTENT));
    expect(link).toHaveAttribute('href', '/worker');
  });

  it('does not offer it as a third tab', () => {
    // Create and Join are two views of one decision; this is a way off the
    // page. A tab would put it in the same grammar as the other two and imply
    // a founder flow it is not part of.
    render(<MemoryRouter><GetStartedPage /></MemoryRouter>);

    expect(screen.getAllByRole('tab')).toHaveLength(2);
  });
});
