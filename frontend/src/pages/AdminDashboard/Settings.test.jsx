import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsPage from './Settings';

const mocks = vi.hoisted(() => ({ api: vi.fn(), showToast: vi.fn() }));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));
vi.mock('../../store/useApp', () => ({ useApp: () => ({ showToast: mocks.showToast }) }));

const LOADED = {
  community: { latitude: 22.572645, longitude: 88.363892 },
  preferences: { requireVisitorPreapproval: true },
  billing: { autoBillingEnabled: false, lateFeeEnabled: false },
};

beforeEach(() => {
  mocks.api.mockReset().mockResolvedValue(LOADED);
  mocks.showToast.mockReset();
});

async function renderLoaded() {
  render(<SettingsPage />);
  await waitFor(() => expect(screen.getByLabelText('Latitude')).toHaveValue(22.572645));
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
});
