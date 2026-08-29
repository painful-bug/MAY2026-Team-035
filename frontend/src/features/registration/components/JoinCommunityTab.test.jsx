import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import JoinCommunityTab from './JoinCommunityTab';

// The join form now captures the applicant's residence as FREE TEXT (privacy
// invariant: non-members never see the unit inventory). The fields branch on
// the selected community's type — tower + flat for apartments, a single villa
// number otherwise — and gate submission until they are filled.

const mocks = vi.hoisted(() => ({
  registrationApi: {
    myAccessRequests: vi.fn(),
    createAccessRequest: vi.fn(),
  },
  search: { data: { items: [] }, isFetching: false, error: null },
}));

vi.mock('../registrationApi', () => ({ registrationApi: mocks.registrationApi }));
vi.mock('../hooks/useCommunitySearch', () => ({ useCommunitySearch: () => mocks.search }));

const APARTMENT = { id: 'com-1', name: 'Green Heights', city: 'Pune', state: 'MH', community_type: 'apartment' };
const VILLA = { id: 'com-2', name: 'Palm Meadows', city: 'Goa', state: 'GA', community_type: 'layout_villa' };

beforeEach(() => {
  mocks.registrationApi.myAccessRequests.mockReset().mockResolvedValue({ items: [] });
  mocks.registrationApi.createAccessRequest.mockReset().mockResolvedValue({ id: 'ar-1', status: 'pending' });
  mocks.search = { data: { items: [APARTMENT, VILLA] }, isFetching: false, error: null };
});

function renderTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <JoinCommunityTab />
    </QueryClientProvider>
  );
}

async function selectCommunity(user, name) {
  await user.click(screen.getByRole('option', { name: new RegExp(name) }));
}

describe('join community residence capture', () => {
  it('asks an apartment applicant for tower and flat, and posts both trimmed', async () => {
    const user = userEvent.setup();
    renderTab();
    await selectCommunity(user, 'Green Heights');

    const submit = screen.getByRole('button', { name: /request to join green heights/i });
    // Residence fields are required before the request can go out.
    expect(submit).toBeDisabled();

    await user.type(screen.getByPlaceholderText('C'), '  C  ');
    expect(submit).toBeDisabled();
    await user.type(screen.getByPlaceholderText('505'), ' 505 ');
    expect(submit).toBeEnabled();

    await user.click(submit);
    await waitFor(() => expect(mocks.registrationApi.createAccessRequest).toHaveBeenCalledTimes(1));
    // mutationFn receives a react-query context object as a second argument —
    // only the payload matters here.
    expect(mocks.registrationApi.createAccessRequest.mock.calls[0][0]).toEqual({
      community_id: 'com-1',
      requested_relationship: 'tenant',
      phone: null,
      requested_building_text: 'C',
      requested_unit_text: '505',
    });
  });

  it('asks a villa applicant only for a villa number and omits requested_building_text', async () => {
    const user = userEvent.setup();
    renderTab();
    await selectCommunity(user, 'Palm Meadows');

    expect(screen.getByPlaceholderText('Villa-17')).toBeInTheDocument();
    expect(screen.queryByText('Tower / Block')).not.toBeInTheDocument();

    const submit = screen.getByRole('button', { name: /request to join palm meadows/i });
    expect(submit).toBeDisabled();
    await user.type(screen.getByPlaceholderText('Villa-17'), 'Villa-17');
    await user.click(submit);

    await waitFor(() => expect(mocks.registrationApi.createAccessRequest).toHaveBeenCalledTimes(1));
    const payload = mocks.registrationApi.createAccessRequest.mock.calls[0][0];
    expect(payload).toMatchObject({ community_id: 'com-2', requested_unit_text: 'Villa-17' });
    expect(payload).not.toHaveProperty('requested_building_text');
  });

  it('resets the residence claim when the applicant picks a different community', async () => {
    const user = userEvent.setup();
    renderTab();
    await selectCommunity(user, 'Green Heights');
    await user.type(screen.getByPlaceholderText('C'), 'C');
    await user.type(screen.getByPlaceholderText('505'), '505');

    // A different community means a different address scheme — nothing carries.
    await selectCommunity(user, 'Palm Meadows');
    expect(screen.getByPlaceholderText('Villa-17')).toHaveValue('');
    expect(screen.getByRole('button', { name: /request to join palm meadows/i })).toBeDisabled();
  });
});
