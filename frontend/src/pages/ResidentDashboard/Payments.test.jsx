import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Payments from './Payments';

// Pins the stacking-context escape for the pay modal. Rendered in place, it
// sat inside ResidentLayout's `<main class="animate-fade-in">` — a
// fill-forwards opacity animation keeps <main> a stacking context forever,
// so the overlay's z-[999] was trapped below the sticky header's z-40. The
// portal to document.body is what makes the overlay immune.

const mocks = vi.hoisted(() => ({
  invoices: vi.fn(),
  amenityBookings: vi.fn(),
}));

vi.mock('../../features/resident/residentApi', () => ({
  residentApi: {
    invoices: mocks.invoices,
    amenityBookings: mocks.amenityBookings,
    payInvoice: vi.fn(),
    payAmenityBooking: vi.fn(),
  },
}));

beforeEach(() => {
  mocks.invoices.mockReset().mockResolvedValue({
    items: [
      {
        id: 'inv-1',
        title: 'March maintenance',
        status: 'Unpaid',
        isPayable: true,
        outstandingAmount: 1200,
        invoiceNumber: 'INV-001',
        dueOn: '2026-08-31',
      },
    ],
  });
  mocks.amenityBookings.mockReset().mockResolvedValue({ items: [] });
});

const renderPage = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Payments />
    </QueryClientProvider>
  );

describe('pay modal portal contract', () => {
  it('portals the dialog to document.body with a full-cover overlay', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Pay Bill' }));

    const dialog = screen.getByRole('dialog', { name: 'Society payment gateway' });
    expect(dialog.parentElement).toBe(document.body);
    expect(dialog.className).toContain('fixed inset-0');
    expect(dialog.className).toContain('z-[999]');
    // The panel scrolls internally on a short viewport instead of clipping.
    // `dvh`, not `vh`: the guard that landed on this panel independently
    // measures the dynamic viewport, so a mobile browser's collapsing URL bar
    // cannot push the panel's bottom out of reach. Kept as-is by the port.
    const panel = dialog.firstElementChild;
    expect(panel.className).toContain('overflow-y-auto');
    expect(panel.className).toContain('max-h-[calc(100dvh-2rem)]');
  });

  it('keeps the Close behavior', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Pay Bill' }));
    await user.click(screen.getByRole('button', { name: 'Close' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
