import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import EmployeeDetail from './EmployeeDetail';

// Pins the stacking-context escape for the approve-leave sheet. Rendered in
// place under /admin, it sat inside AdminLayout's
// `<main class="animate-fade-in">` — a fill-forwards opacity animation keeps
// <main> a stacking context forever, so the overlay's z-[999] was trapped
// below the sticky header's z-40. The portal to document.body is what makes
// the overlay immune.

const mocks = vi.hoisted(() => ({ staffMember: vi.fn() }));

vi.mock('../../features/hiring/hiringApi', () => ({
  hiringApi: {
    staffMember: mocks.staffMember,
    staffSchedule: vi.fn().mockResolvedValue([]),
    department: vi.fn().mockResolvedValue({ staff: [] }),
    coverage: vi.fn().mockResolvedValue([]),
    reassign: vi.fn(),
    decideDeparture: vi.fn(),
    openDeparture: vi.fn(),
  },
}));

vi.mock('../../features/hiring/usePortalScope', () => ({
  usePortalScope: () => ({ base: '/admin', departmentId: 'dept-1' }),
}));

vi.mock('../../store/authStore', () => ({
  useAuthStore: (selector) =>
    selector({
      sessionContext: { membership: { community_id: 'community-1' } },
    }),
}));

beforeEach(() => {
  mocks.staffMember.mockReset().mockResolvedValue({
    id: 'staff-1',
    name: 'Anil Kumar',
    rank: 'member',
    role: 'Technician',
    status: 'active',
    phone: '+91 90000 00000',
    openCommitmentCount: 0,
    activeAssignmentCount: 0,
    serviceProviderId: null,
    membershipId: null,
    departure: {
      id: 'dep-1',
      status: 'pending',
      requestedEffectiveAt: '2026-08-20T00:00:00Z',
      conflictCount: 0,
      reason: null,
    },
  });
});

const renderPage = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={['/admin/departments/dept-1/staff/staff-1']}>
        <Routes>
          <Route
            path="/admin/departments/:departmentId/staff/:staffId"
            element={<EmployeeDetail />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );

describe('approve-leave sheet portal contract', () => {
  it('portals the dialog to document.body with a full-cover overlay', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: /approve…/i }));

    const dialog = screen.getByRole('dialog', { name: 'Approve the leave' });
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

  it('keeps the escape close behavior', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: /approve…/i }));
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
