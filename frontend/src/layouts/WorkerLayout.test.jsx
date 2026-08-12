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

  it('holds a neutral loading screen while the snapshot is in flight', () => {
    mocks.snapshot.mockReturnValue(new Promise(() => {}));
    renderLayout();

    expect(screen.getByText('Preparing your workspace…')).toBeVisible();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'Register as a service partner' }),
    ).not.toBeInTheDocument();
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
