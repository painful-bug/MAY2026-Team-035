import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsPage from './Settings';

const mocks = vi.hoisted(() => ({ api: vi.fn(), showToast: vi.fn() }));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));

// The map is a lazy chunk of real Leaflet, which wants a laid-out element jsdom
// never provides. Stubbed so this file keeps testing the settings screen;
// `LocationPicker.test.jsx` covers the picker itself.
vi.mock('../../components/common/LocationMap', () => ({
  default: () => <div data-testid="map" />,
}));
vi.mock('../../store/useApp', () => ({ useApp: () => ({ showToast: mocks.showToast }) }));

const LOADED = {
  community: { latitude: 22.572645, longitude: 88.363892, locationLabel: 'Salt Lake, Kolkata' },
  preferences: { requireVisitorPreapproval: true },
  billing: { autoBillingEnabled: false, lateFeeEnabled: false },
};

// The billing card now reads `GET /billing-settings` through react-query, the
// endpoint's own writable shape rather than the read-only copy `/settings`
// echoes -- both go through the same mocked `api`, distinguished by path.
const BILLING_SETTINGS = {
  communityId: 'c1',
  currency: 'INR',
  invoiceNumberPrefix: 'INV',
  defaultMaintenanceAmount: null,
  maintenanceDueDay: 15,
  defaultTaxPercent: 0,
  autoBillingEnabled: false,
  autoBillingDay: 1,
  lateFeeEnabled: false,
  lateFeeAmount: null,
  lateFeeGraceDays: 10,
  lateFeePeriod: 'weekly',
  updatedAt: '2026-07-29T18:00:00+00:00',
};

beforeEach(() => {
  mocks.api.mockReset().mockImplementation((path) => {
    if (path === '/billing-settings') return Promise.resolve(BILLING_SETTINGS);
    return Promise.resolve(LOADED);
  });
  mocks.showToast.mockReset();
});

function renderWithProviders(ui) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

async function renderLoaded() {
  renderWithProviders(<SettingsPage />);
  await waitFor(() => expect(screen.getByLabelText('Latitude')).toHaveValue(22.572645));
  await waitFor(() => expect(screen.queryByText(/loading billing settings/i)).not.toBeInTheDocument());
  mocks.api.mockClear();
}

describe('admin settings coordinates', () => {
  it('refuses an out-of-range latitude before any request is sent', async () => {
    // This page saves from a button, not a form submit, so the `min`/`max` on
    // the coordinate inputs never run. Until the check moved into JS, 999
    // reached the API and returned a bare 422 naming no field.
    const user = userEvent.setup();
    await renderLoaded();

    await user.clear(screen.getByLabelText('Latitude'));
    await user.type(screen.getByLabelText('Latitude'), '999');
    await user.click(screen.getByRole('button', { name: /save/i }));

    expect(mocks.api).not.toHaveBeenCalled();
    expect(mocks.showToast).toHaveBeenCalledWith(
      'Latitude must be between -90 and 90, and longitude between -180 and 180',
      'error',
    );
  });

  it('refuses an out-of-range longitude too', async () => {
    const user = userEvent.setup();
    await renderLoaded();

    await user.clear(screen.getByLabelText('Longitude'));
    await user.type(screen.getByLabelText('Longitude'), '181');
    await user.click(screen.getByRole('button', { name: /save/i }));

    expect(mocks.api).not.toHaveBeenCalled();
  });

  it('still refuses an empty coordinate, and with its own message', async () => {
    const user = userEvent.setup();
    await renderLoaded();

    await user.clear(screen.getByLabelText('Latitude'));
    await user.click(screen.getByRole('button', { name: /save/i }));

    expect(mocks.api).not.toHaveBeenCalled();
    expect(mocks.showToast).toHaveBeenCalledWith('Community coordinates are required', 'error');
  });

  it('sends coordinates in range as numbers', async () => {
    const user = userEvent.setup();
    await renderLoaded();

    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith('/settings', expect.anything()));
    const [, options] = mocks.api.mock.calls.find(([path]) => path === '/settings');
    expect(JSON.parse(options.body)).toMatchObject({ latitude: 22.572645, longitude: 88.363892 });
  });

  it('round-trips the community location label', async () => {
    const user = userEvent.setup();
    await renderLoaded();

    const label = screen.getByLabelText(/Location label/);
    expect(label).toHaveValue('Salt Lake, Kolkata');
    await user.clear(label);
    await user.type(label, 'Sector V, Kolkata');
    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith('/settings', expect.anything()));
    const [, options] = mocks.api.mock.calls.find(([path]) => path === '/settings');
    expect(JSON.parse(options.body)).toMatchObject({ locationLabel: 'Sector V, Kolkata' });
  });
});
