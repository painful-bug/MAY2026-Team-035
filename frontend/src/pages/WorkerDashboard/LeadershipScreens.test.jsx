import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';

// The four worker screens built around a `service_providers` row, rendered for
// somebody who has none.
//
// WorkerLayout stopped putting department leadership in front of the
// marketplace registration form on 2026-08-21, which means these four are
// reachable by a caller they were never written for: a manager or supervisor an
// administrator created by email holds a membership and a roster row and no
// provider row, so `GET /service-providers/me`, `/worker/communities` and both
// availability reads all 404 at them.
//
// Settings is the reason this file exists rather than a hand check. Its guard
// was `profile.isPending || !form`, and on a 404 `form` never gets set — so the
// screen held "Loading settings…" with no error and no way out. That failure
// mode is invisible to a test that only asserts the happy path, and it comes
// back the moment somebody re-enables the query unconditionally.

const mocks = vi.hoisted(() => ({
  snapshot: vi.fn(),
  profile: vi.fn(),
  skills: vi.fn(),
  availabilityRules: vi.fn(),
  unavailability: vi.fn(),
  myCommunities: vi.fn(),
  myApplications: vi.fn(),
  searchCommunities: vi.fn(),
  setAvailable: vi.fn(),
  updateProfile: vi.fn(),
  setSkills: vi.fn(),
  requestDeparture: vi.fn(),
  cancelDeparture: vi.fn(),
}));

vi.mock('../../features/worker/workerApi', () => ({ workerApi: mocks }));
vi.mock('../../lib/telemetry/serviceSignupTelemetry', () => ({
  recordServiceSignupEvent: vi.fn(),
}));
vi.mock('../../lib/push/pushClient', () => ({
  pushSupported: () => false,
  pushEnabled: () => Promise.resolve(false),
  enablePush: () => Promise.resolve({ ok: true }),
  disablePush: () => Promise.resolve({ ok: true }),
}));
vi.mock('../../store/authStore', () => ({
  useAuthStore: (selector) => selector({
    sessionContext: { identity: { full_name: 'Meera Nair', email: 'meera@example.com' } },
    refreshSession: vi.fn(),
  }),
}));

const ENGAGEMENT = {
  staffAssignmentId: 'staff-1',
  communityId: 'community-1',
  communityName: 'Green Meadows',
  departmentId: 'department-1',
  departmentName: 'Plumbing',
  rank: 'supervisor',
  jobTitle: 'Supervisor',
  status: 'active',
};

const notFound = () => Promise.reject(Object.assign(new Error('You have not registered as a service provider.'), { code: 'service_provider_not_found', status: 404 }));

beforeEach(() => {
  for (const fn of Object.values(mocks)) fn.mockReset();
  mocks.snapshot.mockResolvedValue({ provider: null, communities: [ENGAGEMENT] });
  mocks.profile.mockImplementation(notFound);
  mocks.myCommunities.mockImplementation(notFound);
  mocks.myApplications.mockImplementation(notFound);
  mocks.availabilityRules.mockImplementation(notFound);
  mocks.unavailability.mockImplementation(notFound);
  mocks.skills.mockResolvedValue([]);
  mocks.searchCommunities.mockResolvedValue([]);
});

async function renderScreen(Component, path = '/worker') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Component />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it('Profile', async () => {
  const { default: C } = await import('./Profile');
  await renderScreen(C);
  expect(await screen.findByText('No marketplace profile')).toBeVisible();
  expect(screen.getByText(/Plumbing · Green Meadows/)).toBeVisible();
  expect(mocks.profile).not.toHaveBeenCalled();
});

it('Settings', async () => {
  const { default: C } = await import('./Settings');
  await renderScreen(C);
  expect(await screen.findByText('Nothing else to set here')).toBeVisible();
  expect(screen.getByText('Meera Nair')).toBeVisible();
  expect(screen.queryByText('Loading settings…')).not.toBeInTheDocument();
  expect(mocks.profile).not.toHaveBeenCalled();
});

it('Availability', async () => {
  const { default: C } = await import('./Availability');
  await renderScreen(C);
  expect(await screen.findByText("Your hours are your department's")).toBeVisible();
  expect(mocks.availabilityRules).not.toHaveBeenCalled();
});

it('Communities', async () => {
  const { default: C } = await import('./Communities');
  await renderScreen(C, '/worker/communities');
  expect(await screen.findByText('Green Meadows')).toBeVisible();
  expect(screen.queryByText(/No society employs you yet/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Ask to leave/)).not.toBeInTheDocument();
  expect(mocks.myCommunities).not.toHaveBeenCalled();
});
