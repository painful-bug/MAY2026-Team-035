import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PendingRegistrations from './PendingRegistrations';

// Approval now REQUIRES a resolvable unit (backend 422 approval_requires_unit
// otherwise), so Accept no longer fires the mutation directly: it opens an
// inline panel prefilled from the applicant's free-text claim, previews
// whether the composed code matches an existing unit, and only Confirm posts.

const mocks = vi.hoisted(() => ({
  registrationApi: {
    adminAccessRequests: vi.fn(),
    adminUnits: vi.fn(),
    approveAccessRequest: vi.fn(),
    rejectAccessRequest: vi.fn(),
    blacklistAccessRequest: vi.fn(),
  },
}));

vi.mock('../../features/registration/registrationApi', () => ({ registrationApi: mocks.registrationApi }));

const APARTMENT_REQUEST = {
  id: 'req-1',
  applicant_name: 'Asha Rao',
  applicant_email: 'asha@example.com',
  applicant_phone_e164: null,
  requested_relationship: 'family_member',
  requested_unit_id: null,
  requested_building_text: 'C',
  requested_unit_text: '505',
  community: { id: 'com-1', name: 'Green Heights', community_type: 'apartment' },
};

const VILLA_REQUEST = {
  id: 'req-2',
  applicant_name: 'Vikram Shetty',
  applicant_email: 'vikram@example.com',
  applicant_phone_e164: null,
  requested_relationship: 'owner',
  requested_unit_id: null,
  requested_building_text: null,
  requested_unit_text: null,
  community: { id: 'com-2', name: 'Palm Meadows', community_type: 'layout_villa' },
};

beforeEach(() => {
  mocks.registrationApi.adminAccessRequests.mockReset().mockResolvedValue({ items: [APARTMENT_REQUEST, VILLA_REQUEST] });
  mocks.registrationApi.adminUnits.mockReset().mockResolvedValue({
    items: [{ id: 'u1', unit_code: 'C-505', building_name: 'Tower C' }],
  });
  mocks.registrationApi.approveAccessRequest.mockReset().mockResolvedValue({ request_id: 'req-1', status: 'approved' });
  mocks.registrationApi.rejectAccessRequest.mockReset().mockResolvedValue({});
  mocks.registrationApi.blacklistAccessRequest.mockReset().mockResolvedValue({});
});

async function renderLoaded() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <PendingRegistrations />
    </QueryClientProvider>
  );
  await waitFor(() => expect(screen.getByText('Asha Rao')).toBeInTheDocument());
}

describe('pending registrations residence claims', () => {
  it('renders the claimed residence, and "Not stated" for pre-migration rows', async () => {
    await renderLoaded();
    expect(screen.getByText(/Tower C · Flat 505/)).toBeInTheDocument();
    expect(screen.getByText(/Not stated/)).toBeInTheDocument();
  });
});

describe('inline approval panel', () => {
  it('opens prefilled from the claim instead of approving on click, shows the match, and posts the confirmed unit', async () => {
    const user = userEvent.setup();
    await renderLoaded();

    const acceptButtons = screen.getAllByRole('button', { name: /accept/i });
    await user.click(acceptButtons[0]);

    // No direct approval any more.
    expect(mocks.registrationApi.approveAccessRequest).not.toHaveBeenCalled();

    // Prefilled from the free-text claim, labels in apartment vocabulary.
    expect(screen.getByPlaceholderText('C')).toHaveValue('C');
    expect(screen.getByPlaceholderText('505')).toHaveValue('505');

    // The composed candidate C-505 matches the seeded unit inventory.
    await waitFor(() => expect(screen.getByText('Matches existing unit C-505')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /confirm approval/i }));
    await waitFor(() => expect(mocks.registrationApi.approveAccessRequest).toHaveBeenCalledTimes(1));
    expect(mocks.registrationApi.approveAccessRequest).toHaveBeenCalledWith('req-1', {
      unit_code: '505',
      building_code: 'C',
    });
  });

  it('announces a unit that will be created when the claim matches nothing', async () => {
    const user = userEvent.setup();
    await renderLoaded();

    await user.click(screen.getAllByRole('button', { name: /accept/i })[0]);
    const flat = screen.getByPlaceholderText('505');
    await user.clear(flat);
    await user.type(flat, '506');

    await waitFor(() => expect(screen.getByText('Will create unit C-506')).toBeInTheDocument());
  });

  it('uses villa vocabulary and blocks Confirm until a unit is typed, then posts a null building_code', async () => {
    const user = userEvent.setup();
    await renderLoaded();

    await user.click(screen.getAllByRole('button', { name: /accept/i })[1]);

    // Villa community: one input, no tower field, nothing prefilled.
    const villa = screen.getByPlaceholderText('Villa-17');
    expect(villa).toHaveValue('');
    expect(screen.queryByPlaceholderText('C')).not.toBeInTheDocument();

    const confirm = screen.getByRole('button', { name: /confirm approval/i });
    expect(confirm).toBeDisabled();
    expect(screen.getByText('A unit is required to approve.')).toBeInTheDocument();

    await user.type(villa, 'Villa-9');
    await waitFor(() => expect(screen.getByText('Will create unit Villa-9')).toBeInTheDocument());
    await user.click(confirm);

    await waitFor(() => expect(mocks.registrationApi.approveAccessRequest).toHaveBeenCalledTimes(1));
    expect(mocks.registrationApi.approveAccessRequest).toHaveBeenCalledWith('req-2', {
      unit_code: 'Villa-9',
      building_code: null,
    });
  });

  it('surfaces the backend refusal through the alert line', async () => {
    mocks.registrationApi.approveAccessRequest.mockRejectedValue(new Error('Approving a resident requires a unit'));
    const user = userEvent.setup();
    await renderLoaded();

    await user.click(screen.getAllByRole('button', { name: /accept/i })[0]);
    await user.click(screen.getByRole('button', { name: /confirm approval/i }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Approving a resident requires a unit')
    );
  });
});
