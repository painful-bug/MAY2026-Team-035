import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Visitors from './Visitors';

// Pins the stacking-context escape for the QR pass modal. Rendered in place,
// it sat inside ResidentLayout's `<main class="animate-fade-in">` — a
// fill-forwards opacity animation keeps <main> a stacking context forever,
// so the overlay's z-[999] was trapped below the sticky header's z-40. The
// portal to document.body is what makes the overlay immune.

const mocks = vi.hoisted(() => ({
  visitorPasses: vi.fn(),
  createVisitorPass: vi.fn(),
  showToast: vi.fn(),
}));

vi.mock('../../features/resident/residentApi', () => ({
  residentApi: {
    visitorPasses: mocks.visitorPasses,
    createVisitorPass: mocks.createVisitorPass,
    approveVisitorPass: vi.fn(),
    rejectVisitorPass: vi.fn(),
    cancelVisitorPass: vi.fn(),
  },
}));

vi.mock('../../store/appStore', () => ({
  useAppStore: (selector) => selector({ showToast: mocks.showToast }),
}));

// The QR encoder draws onto a canvas jsdom does not have.
vi.mock('qrcode', () => ({
  default: { toDataURL: vi.fn().mockResolvedValue('data:image/png;base64,qr') },
}));

beforeEach(() => {
  mocks.visitorPasses.mockReset().mockResolvedValue({ items: [] });
  mocks.createVisitorPass.mockReset().mockResolvedValue({
    id: 'pass-1',
    guestCount: 1,
    purpose: 'Guest',
    validFrom: '2026-08-12T16:00:00Z',
    securityCode: '482913',
    passToken: 'token-1',
  });
});

const renderPage = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <Visitors />
      </MemoryRouter>
    </QueryClientProvider>
  );

describe('visitor QR modal portal contract', () => {
  it('portals the dialog to document.body after generating a pass', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      await screen.findByRole('button', { name: /generate qr code/i })
    );

    const dialog = await screen.findByRole('dialog', {
      name: 'Visitor QR pass',
    });
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

  it('keeps the close-button behavior', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      await screen.findByRole('button', { name: /generate qr code/i })
    );
    await screen.findByRole('dialog', { name: 'Visitor QR pass' });
    await user.click(screen.getByRole('button', { name: 'Close QR pass' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
