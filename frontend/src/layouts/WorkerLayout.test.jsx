import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WorkerLayout from './WorkerLayout';

const mocks = vi.hoisted(() => ({
  snapshot: vi.fn(),
  skills: vi.fn(),
  setAvailable: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
}));

vi.mock('../features/worker/workerApi', () => ({
  workerApi: {
    snapshot: mocks.snapshot,
    skills: mocks.skills,
    setAvailable: mocks.setAvailable,
  },
}));

vi.mock('../store/authStore', () => ({
  useAuthStore: (selector) => selector({
    sessionContext: { identity: { full_name: 'Ravi Kumar', email: 'ravi@example.com' } },
    logout: mocks.logout,
    refreshSession: mocks.refreshSession,
  }),
}));

// The bell polls GET /notifications on an interval; none of that matters to
// the gate under test.
vi.mock('../components/notifications/NotificationBell', () => ({
  default: () => null,
}));

const completeProvider = {
  id: 'provider-1',
  displayName: 'Ravi Kumar',
  latitude: 22.572645,
  longitude: 88.363892,
  skillIds: ['skill-plumbing'],
  isAvailable: true,
};

beforeEach(() => {
  mocks.snapshot.mockReset();
  mocks.skills.mockReset().mockResolvedValue([
    { id: 'skill-plumbing', name: 'Plumbing', category: 'maintenance' },
  ]);
  mocks.setAvailable.mockReset();
  mocks.logout.mockReset();
  mocks.refreshSession.mockReset().mockResolvedValue({ portal: 'worker' });
});

function renderLayout(initialPath = '/worker') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      {
        path: '/worker',
        element: <WorkerLayout />,
        children: [
          { index: true, element: <p>Dashboard home</p> },
          { path: 'settings', element: <p>Settings page</p> },
        ],
      },
    ],
    { initialEntries: [initialPath] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

describe('WorkerLayout registration gate', () => {
  it('shows the registration screen with no portal chrome when the professional has never registered', async () => {
    mocks.snapshot.mockResolvedValue({ provider: null, communities: [] });
    renderLayout();

    expect(
      await screen.findByRole('heading', { name: 'Register as a service partner' }),
    ).toBeVisible();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /dashboard/i })).not.toBeInTheDocument();
    expect(screen.queryByText('Dashboard home')).not.toBeInTheDocument();
  });

  it('treats an incomplete provider row as unregistered and prefills the form from it', async () => {
    mocks.snapshot.mockResolvedValue({
      provider: { id: 'provider-1', displayName: 'Asha Devi', latitude: null, longitude: null, skillIds: [] },
      communities: [],
    });
    renderLayout();

    expect(
      await screen.findByRole('heading', { name: 'Register as a service partner' }),
    ).toBeVisible();
    expect(screen.getByLabelText('Your name')).toHaveValue('Asha Devi');
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('renders the portal chrome and the routed page for a registered professional', async () => {
    mocks.snapshot.mockResolvedValue({
      provider: completeProvider,
      communities: [],
      pendingOffers: [],
      today: [],
    });
    renderLayout();

    expect(await screen.findByRole('navigation')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Settings' })).toBeVisible();
    expect(screen.getByText('Dashboard home')).toBeVisible();
    expect(
      screen.queryByRole('heading', { name: 'Register as a service partner' }),
    ).not.toBeInTheDocument();
  });

  it('redirects an unregistered professional from a deep link back to /worker', async () => {
    mocks.snapshot.mockResolvedValue({ provider: null, communities: [] });
    const router = renderLayout('/worker/settings');

    expect(
      await screen.findByRole('heading', { name: 'Register as a service partner' }),
    ).toBeVisible();
    expect(router.state.location.pathname).toBe('/worker');
    expect(screen.queryByText('Settings page')).not.toBeInTheDocument();
  });

  it('lets an invited supervisor with no provider row into the portal', async () => {
    // The live defect. `claim_staff_invitations` mints a membership and a
    // roster row and no `service_providers` row, so a supervisor is
    // "unregistered" by the old test — and was shown a marketplace form asking
    // for coordinates and trades so that a society could find them, which is
    // not how they were hired.
    mocks.snapshot.mockResolvedValue({
      provider: null,
      communities: [
        {
          staffAssignmentId: 'staff-1',
          communityId: 'community-1',
          communityName: 'Green Meadows',
          departmentId: 'department-1',
          departmentName: 'Plumbing',
          rank: 'supervisor',
          status: 'active',
        },
      ],
      pendingOffers: [],
      today: [],
    });
    renderLayout();

    expect(await screen.findByRole('navigation')).toBeVisible();
    expect(screen.getByText('Dashboard home')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Complaints' })).toBeVisible();
    expect(
      screen.queryByRole('heading', { name: 'Register as a service partner' }),
    ).not.toBeInTheDocument();
  });

  it('keeps the gate for a technician-rank engagement with an incomplete profile', async () => {
    // `member` is reached only by marketplace hiring, and a technician is
    // matched by distance and trade — so the coordinates and skills the form
    // asks for are the whole reason they can be dispatched. Holding a roster
    // row does not excuse them from it.
    mocks.snapshot.mockResolvedValue({
      provider: { id: 'provider-1', displayName: 'Ravi Kumar', latitude: null, longitude: null, skillIds: [] },
      communities: [
        {
          staffAssignmentId: 'staff-2',
          communityId: 'community-1',
          communityName: 'Green Meadows',
          departmentId: 'department-1',
          departmentName: 'Plumbing',
          rank: 'member',
          status: 'active',
        },
      ],
    });
    renderLayout();

    expect(
      await screen.findByRole('heading', { name: 'Register as a service partner' }),
    ).toBeVisible();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('ignores an ended leadership engagement when deciding the gate', async () => {
    // `status` is on the roster row for a reason: a supervisor whose posting
    // ended is no longer staff, and letting an inactive row open the portal
    // would make removal from a department mean nothing here.
    mocks.snapshot.mockResolvedValue({
      provider: null,
      communities: [
        {
          staffAssignmentId: 'staff-3',
          communityId: 'community-1',
          communityName: 'Green Meadows',
          departmentId: 'department-1',
          departmentName: 'Plumbing',
          rank: 'supervisor',
          status: 'inactive',
        },
      ],
    });
    renderLayout();

    expect(
      await screen.findByRole('heading', { name: 'Register as a service partner' }),
    ).toBeVisible();
  });

  it('holds a neutral loading screen while the snapshot is in flight', () => {
    mocks.snapshot.mockReturnValue(new Promise(() => {}));
    renderLayout();

    expect(screen.getByText('Preparing your workspace…')).toBeVisible();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'Register as a service partner' }),
    ).not.toBeInTheDocument();
  });

  // The nav entry for the dispatch queue (product ruling, 2026-08-21).
  //
  // It is the first item in this sidebar that is hidden rather than
  // self-explaining, and the reason is that the layout can now afford to hide
  // it: the gate above already asks `holdsLeadershipEngagement` of this same
  // snapshot, so rank is in hand where it was not when Complaints was added.
  // The page behind it refuses a technician either way — `WorkOrders.test.jsx`
  // pins that — so what these two tests protect is the promise that a rank
  // check exists here at all, in both directions.
  it('shows the work-order queue in the nav for an active supervisor', async () => {
    mocks.snapshot.mockResolvedValue({
      provider: completeProvider,
      communities: [
        {
          staffAssignmentId: 'staff-1',
          communityId: 'community-1',
          departmentId: 'department-1',
          departmentName: 'Plumbing',
          rank: 'supervisor',
          status: 'active',
        },
      ],
      pendingOffers: [],
      today: [],
    });
    renderLayout();

    const link = await screen.findByRole('link', { name: 'Work orders' });
    expect(link).toBeVisible();
    expect(link).toHaveAttribute('href', '/worker/work-orders');
  });

  it('hides it from a technician and from a marketplace professional', async () => {
    mocks.snapshot.mockResolvedValue({
      provider: completeProvider,
      communities: [
        {
          staffAssignmentId: 'staff-2',
          communityId: 'community-1',
          departmentId: 'department-1',
          departmentName: 'Plumbing',
          rank: 'member',
          status: 'active',
        },
      ],
      pendingOffers: [],
      today: [],
    });
    renderLayout();

    await screen.findByRole('navigation');
    expect(screen.queryByRole('link', { name: 'Work orders' })).not.toBeInTheDocument();
    // The rest of the sidebar is untouched: this is one hidden entry, not a
    // second navigation for technicians.
    expect(screen.getByRole('link', { name: 'Complaints' })).toBeVisible();
  });

  it('hides it once the supervisor posting has ended', async () => {
    mocks.snapshot.mockResolvedValue({
      provider: completeProvider,
      communities: [
        {
          staffAssignmentId: 'staff-3',
          communityId: 'community-1',
          departmentId: 'department-1',
          departmentName: 'Plumbing',
          rank: 'supervisor',
          status: 'ended',
        },
      ],
      pendingOffers: [],
      today: [],
    });
    renderLayout();

    await screen.findByRole('navigation');
    expect(screen.queryByRole('link', { name: 'Work orders' })).not.toBeInTheDocument();
  });

  it('offers a retry when the snapshot fails, and recovers into the portal', async () => {
    const user = userEvent.setup();
    // The recovery value is persistent, not `Once`: once the gate passes,
    // AvailabilityToggle mounts as a second observer of the same (stale) query
    // and immediately refetches.
    mocks.snapshot
      .mockRejectedValueOnce(new Error('Snapshot unavailable'))
      .mockResolvedValue({
        provider: completeProvider,
        communities: [],
        pendingOffers: [],
        today: [],
      });
    renderLayout();

    expect(await screen.findByText('Snapshot unavailable')).toBeVisible();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.getByRole('navigation')).toBeVisible());
    expect(mocks.snapshot.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
