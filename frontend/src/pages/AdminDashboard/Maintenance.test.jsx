import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Maintenance from './Maintenance';

// Pins the stacking-context escape for this page's shared Modal wrapper (the
// issue-invoice and record-payment sheets). Rendered in place, it sat inside
// AdminLayout's `<main class="animate-fade-in">` — a fill-forwards opacity
// animation keeps <main> a stacking context forever, so the overlay's
// z-[999] was trapped below the sticky header's z-40. The portal to
// document.body is what makes the overlay immune.

const mocks = vi.hoisted(() => ({ state: {} }));

// `useApp` is selector-based now: every call site passes a one-key selector,
// so the mock has to apply it (a bare object would hand the component the
// whole state where it expects one field).
vi.mock('../../store/useApp', () => ({
  useApp: (selector) => (selector ? selector(mocks.state) : mocks.state),
}));
vi.mock('../../features/money/moneyApi', () => ({
  moneyApi: { createInvoice: vi.fn(), recordPayment: vi.fn() },
}));
vi.mock('../../lib/dashboard/dashboardApi', () => ({
  getDashboardSnapshot: vi.fn(),
}));

beforeEach(() => {
  mocks.state = {
    payments: [],
    users: [],
    hydrateDashboard: vi.fn(),
    showToast: vi.fn(),
  };
});

const renderPage = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Maintenance />
    </QueryClientProvider>
  );

describe('maintenance Modal portal contract', () => {
  it('portals the issue-invoice dialog to document.body', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: /issue invoice/i }));

    const dialog = screen.getByRole('dialog', { name: 'Issue an invoice' });
    expect(dialog.parentElement).toBe(document.body);
    expect(dialog.className).toContain('fixed inset-0');
    expect(dialog.className).toContain('z-[999]');
    // The panel scrolls internally on a short viewport instead of clipping.
    const panel = dialog.firstElementChild;
    expect(panel.className).toContain('overflow-y-auto');
    expect(panel.className).toContain('max-h-[calc(100vh-2rem)]');
  });
});
