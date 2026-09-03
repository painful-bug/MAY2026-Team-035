import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Settings from './Settings';

// Worker settings used to show "where you are based" as a read-only pair of
// numbers with an Update button that only ever asked the browser for a GPS fix.
// A denied permission left a serviceman with no way at all to correct the one
// field that decides whether community search returns anything — which is the
// defect the picker replaced it for, so it is worth a test of its own.

const mocks = vi.hoisted(() => ({
  snapshot: vi.fn(),
  profile: vi.fn(),
  skills: vi.fn(),
  updateProfile: vi.fn(),
  setSkills: vi.fn(),
  myCommunities: vi.fn(),
  geoSearch: vi.fn(),
  geoReverse: vi.fn(),
}));

vi.mock('../../features/worker/workerApi', () => ({ workerApi: mocks }));
vi.mock('../../features/geo/geoApi', () => ({
  geoApi: { search: mocks.geoSearch, reverse: mocks.geoReverse },
}));
vi.mock('../../components/common/LocationMap', () => ({
  default: () => <div data-testid="map" />,
}));
vi.mock('../../lib/push/pushClient', () => ({
  pushSupported: () => false,
  pushEnabled: () => Promise.resolve(false),
  enablePush: () => Promise.resolve({ ok: true }),
  disablePush: () => Promise.resolve({ ok: true }),
}));
vi.mock('../../store/authStore', () => ({
  useAuthStore: (selector) => selector({
    sessionContext: { identity: { full_name: 'Ravi Kumar', email: 'ravi@example.com' } },
    refreshSession: vi.fn(),
  }),
}));

const PROFILE = {
  id: 'provider-1',
  displayName: 'Ravi Kumar',
  headline: 'Plumber, 12 years',
  bio: '',
  phone: '+919876543210',
  serviceRadiusKm: 15,
  latitude: 12.9716,
  longitude: 77.5946,
  locationLabel: 'Indiranagar, Bengaluru',
  skillIds: ['skill-plumbing'],
};

beforeEach(() => {
  for (const fn of Object.values(mocks)) fn.mockReset();
  mocks.snapshot.mockResolvedValue({ provider: PROFILE, communities: [] });
  mocks.profile.mockResolvedValue(PROFILE);
  mocks.skills.mockResolvedValue([
    { id: 'skill-plumbing', name: 'Plumbing', category: 'maintenance' },
  ]);
  mocks.updateProfile.mockResolvedValue(PROFILE);
  mocks.setSkills.mockResolvedValue({ skillCount: 1 });
  mocks.myCommunities.mockResolvedValue([]);
  mocks.geoSearch.mockResolvedValue([]);
  mocks.geoReverse.mockResolvedValue({ label: 'Whitefield, Bengaluru' });
});

function renderSettings() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/worker/settings']}>
        <Settings />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('worker settings location', () => {
  it('loads the stored pin and label into the picker', async () => {
    renderSettings();

    await waitFor(() => expect(screen.getByLabelText(/Location label/)).toHaveValue('Indiranagar, Bengaluru'));
    expect(screen.getByLabelText('Latitude')).toHaveValue(12.9716);
  });

  it('saves a new pin and label picked from address search', async () => {
    const user = userEvent.setup();
    mocks.geoSearch.mockResolvedValue([{
      label: 'Whitefield, Bengaluru',
      description: 'Whitefield, Bengaluru, Karnataka, India',
      latitude: 12.9698,
      longitude: 77.7500,
    }]);
    renderSettings();

    await screen.findByLabelText('Search for your address');
    await user.type(screen.getByLabelText('Search for your address'), 'whitefield');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    await user.click(await screen.findByRole('button', { name: /Whitefield, Bengaluru/ }));
    await user.click(screen.getByRole('button', { name: /Save changes/i }));

    await waitFor(() => expect(mocks.updateProfile).toHaveBeenCalledWith(expect.objectContaining({
      latitude: 12.9698,
      longitude: 77.75,
      locationLabel: 'Whitefield, Bengaluru',
    })));
  });
});

// C-iii: the save used to await updateProfile then setSkills, so a skills
// refusal (the RPC's "Choose at least one skill.") landed after the profile
// half had already committed — one red "Could not save" banner over a save
// that had, in fact, half-succeeded. setSkills now runs first.
describe('worker settings save ordering', () => {
  it('does not call updateProfile, and reports the real reason, when setSkills is refused', async () => {
    const user = userEvent.setup();
    mocks.setSkills.mockRejectedValue(new Error('Choose at least one skill.'));
    renderSettings();

    await screen.findByLabelText(/Location label/);
    await user.click(screen.getByRole('button', { name: /Save changes/i }));

    expect(await screen.findByText('Choose at least one skill.')).toBeVisible();
    expect(mocks.updateProfile).not.toHaveBeenCalled();
  });

  it('disables submit once every trade is deselected', async () => {
    const user = userEvent.setup();
    renderSettings();

    await screen.findByLabelText(/Location label/);
    await user.click(screen.getByRole('button', { name: 'Plumbing' }));

    expect(screen.getByRole('button', { name: /Save changes/i })).toBeDisabled();
  });
});
