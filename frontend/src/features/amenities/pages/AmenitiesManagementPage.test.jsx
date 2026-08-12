import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AmenitiesManagementPage from './AmenitiesManagementPage.jsx';
import { useAmenitiesStore } from '../store/useAmenitiesStore.js';

// The amenities catalogue is read out of `GET /dashboard/snapshot`, which was
// 500ing on every call when this page was walked in live testing — the
// "Something went wrong. Please try again." on screen was the backend's own
// 500 envelope, not a wiring defect here. These tests pin the recovery
// contract: the failure lands in the error state, and "Try again" issues a
// genuinely fresh snapshot read, so the page heals the moment the backend
// does.

const mocks = vi.hoisted(() => ({ getDashboardSnapshot: vi.fn() }));

vi.mock('../../../lib/dashboard/dashboardApi.js', () => ({
  getDashboardSnapshot: mocks.getDashboardSnapshot,
}));

const AMENITY = {
  id: 'a1',
  name: 'Clubhouse',
  description: 'Community hall',
  category: 'Recreation',
  status: 'Active',
  isActive: true,
  capacity: 40,
  hourlyRate: 0,
  pendingRequests: 0,
  outstandingDues: 0,
};

beforeEach(() => {
  mocks.getDashboardSnapshot.mockReset();
  // The store is module-level zustand state; put it back to its initial shape
  // so one test's failure cannot leak into the next.
  useAmenitiesStore.setState({
    amenities: [],
    isLoading: false,
    isAdding: false,
    error: null,
    addError: null,
    selectedAmenity: null,
    detailAmenityId: null,
    isDetailLoading: false,
    detailError: null,
  });
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <AmenitiesManagementPage />
    </MemoryRouter>
  );

describe('amenities management snapshot failure', () => {
  it('surfaces the backend error and recovers through Try again', async () => {
    const user = userEvent.setup();
    // First load: the snapshot 500, as translated by the api client.
    mocks.getDashboardSnapshot.mockRejectedValueOnce(
      new Error('Something went wrong. Please try again.')
    );

    renderPage();

    expect(
      await screen.findByText('Something went wrong. Please try again.')
    ).toBeInTheDocument();

    // The backend is fixed; Try again must refetch rather than replay a cache.
    mocks.getDashboardSnapshot.mockResolvedValueOnce({ amenities: [AMENITY] });
    await user.click(screen.getByRole('button', { name: 'Try again' }));

    expect(await screen.findByText('Clubhouse')).toBeInTheDocument();
    expect(
      screen.queryByText('Something went wrong. Please try again.')
    ).not.toBeInTheDocument();
    expect(mocks.getDashboardSnapshot).toHaveBeenCalledTimes(2);
  });

  it('treats a snapshot without an amenities key as an empty catalogue', async () => {
    mocks.getDashboardSnapshot.mockResolvedValueOnce({});

    renderPage();

    expect(
      await screen.findByText('No amenities match your search.')
    ).toBeInTheDocument();
  });
});
