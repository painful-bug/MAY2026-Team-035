import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Complaints from './Complaints';

// Pins the stacking-context escape for the raise-complaint modal. Rendered
// in place, it sat inside ResidentLayout's `<main class="animate-fade-in">`
// — a fill-forwards opacity animation keeps <main> a stacking context
// forever, so the overlay's z-[999] was trapped below the sticky header's
// z-40. The portal to document.body is what makes the overlay immune. (The
// detail drawer takes the same portal; it needs a live complaint to open,
// so the form modal stands in for the contract here.)

const mocks = vi.hoisted(() => ({
  complaints: vi.fn(),
  directoryContacts: vi.fn(),
}));

vi.mock('../../features/resident/residentApi', () => ({
  residentApi: {
    complaints: mocks.complaints,
    directoryContacts: mocks.directoryContacts,
    createComplaint: vi.fn(),
    markComplaintsRead: vi.fn().mockResolvedValue({}),
  },
}));

// Live updates subscribe to an event stream; a unit render has no stream.
vi.mock('../../features/resident/residentEvents', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useResidentLiveUpdates: () => {} };
});

beforeEach(() => {
  mocks.complaints
    .mockReset()
    .mockResolvedValue({ items: [], total: 0, hasMore: false });
  mocks.directoryContacts.mockReset().mockResolvedValue([]);
});

const renderPage = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Complaints />
    </QueryClientProvider>
  );

describe('raise-complaint modal portal contract', () => {
  it('portals the dialog to document.body, top-anchored with internal scroll', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: /raise complaint/i }));

    const dialog = screen.getByRole('dialog', { name: 'Raise a complaint' });
    expect(dialog.parentElement).toBe(document.body);
    expect(dialog.className).toContain('fixed inset-0');
    expect(dialog.className).toContain('z-[999]');
    // Top-anchored: a panel taller than the viewport clips at the bottom
    // into its own scrollbar, never at the title.
    expect(dialog.className).toContain('items-start');
    const panel = dialog.firstElementChild;
    expect(panel.className).toContain('overflow-y-auto');
    expect(panel.className).toContain('max-h-[calc(100vh-4rem)]');
  });

  it('keeps the close-button behavior', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: /raise complaint/i }));
    await user.click(
      screen.getByRole('button', { name: 'Close complaint form' })
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
