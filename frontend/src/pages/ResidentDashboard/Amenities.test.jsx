import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Amenities from './Amenities';

// The "pool" defect (2026-08-12): an amenity whose hours were never set. The
// hosted row holds NULL opening/closing and `GET /amenities/available`
// faithfully reports "00:00"/"00:00" — which used to render as opening
// "12:00 am", closing "12:00 am", an empty disabled time-slot dropdown and a
// dead submit button, with no word of explanation. The dialog now names the
// problem, shows "Not set" instead of midnight, and disables the submit
// deliberately.

const mocks = vi.hoisted(() => ({
  availableAmenities: vi.fn(),
  amenityBookings: vi.fn(),
  showToast: vi.fn(),
  addActivity: vi.fn(),
}));

vi.mock('../../features/resident/residentApi.js', () => ({
  residentApi: {
    availableAmenities: mocks.availableAmenities,
    amenityBookings: mocks.amenityBookings,
  },
}));

vi.mock('../../features/amenities/services/amenityBookingsService.js', () => ({
  cancelResidentAmenityBookingDays: vi.fn(),
  createResidentAmenityBookingSeries: vi.fn(),
  validateBookingSlot: vi.fn().mockResolvedValue(true),
}));

vi.mock('../../store/appStore.js', () => ({
  useAppStore: (selector) =>
    selector({
      searchQuery: '',
      showToast: mocks.showToast,
      addActivity: mocks.addActivity,
    }),
}));

vi.mock('../../store/authStore.js', () => ({
  useAuthStore: (selector) =>
    selector({ currentUser: { id: 'p1', name: 'Asha Rao' } }),
}));

// One bookable amenity, exactly as the wire reports the NULL-hours pool row.
const bookableAmenity = (overrides = {}) => ({
  id: 'pool-1',
  name: 'pool',
  description: 'Community pool',
  category: 'Recreation',
  location: 'Block A',
  image: '',
  capacity: 20,
  openingTime: '00:00',
  closingTime: '00:00',
  slotDurationMinutes: 60,
  bookingMode: 'Shared',
  maxActiveBookingsPerResident: null,
  requiresApproval: false,
  allowPrivateBooking: false,
  allowRecurringBooking: false,
  allowGuestBooking: true,
  allowSameDayBooking: true,
  bookingFee: 0,
  securityDeposit: 0,
  refundPolicy: '',
  currencyCode: 'INR',
  closedDays: [],
  minimumBookingDurationMinutes: null,
  maximumBookingDurationMinutes: null,
  advanceBookingWindowDays: null,
  ...overrides,
});

beforeEach(() => {
  mocks.availableAmenities
    .mockReset()
    .mockResolvedValue({ items: [bookableAmenity()] });
  mocks.amenityBookings.mockReset().mockResolvedValue({ items: [] });
});

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <Amenities />
    </QueryClientProvider>
  );
};

const openDialog = async (user) => {
  await user.click(await screen.findByRole('button', { name: /pool/i }));
  return screen.findByRole('dialog');
};

describe('resident booking dialog with no bookable hours', () => {
  it('says the hours are not set instead of showing midnight and an empty dropdown', async () => {
    const user = userEvent.setup();
    renderPage();
    const dialog = await openDialog(user);

    // "Not set" for both clocks — never "12:00 am".
    expect(within(dialog).getAllByText('Not set')).toHaveLength(2);
    expect(within(dialog).queryByText(/12:00 am/i)).not.toBeInTheDocument();

    // The inline explanation, and a deliberately disabled submit.
    expect(
      within(dialog).getByText(/no bookable hours set yet/i)
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole('button', { name: /book 1 day/i })
    ).toBeDisabled();

    // The dropdown explains its own emptiness.
    expect(
      within(dialog).getByRole('option', { name: 'No time slots available' })
    ).toBeInTheDocument();
  });

  it('keeps normal hours untouched: real clocks, no warning, slots offered', async () => {
    mocks.availableAmenities.mockResolvedValue({
      items: [bookableAmenity({ openingTime: '06:00', closingTime: '22:00' })],
    });
    const user = userEvent.setup();
    renderPage();
    const dialog = await openDialog(user);

    expect(within(dialog).getByText('6:00 am')).toBeInTheDocument();
    expect(within(dialog).getByText('10:00 pm')).toBeInTheDocument();
    expect(within(dialog).queryByText('Not set')).not.toBeInTheDocument();
    expect(
      within(dialog).queryByText(/no bookable hours set yet/i)
    ).not.toBeInTheDocument();
    expect(
      await within(dialog).findByRole('option', {
        name: /6:00 am - 7:00 am/i,
      })
    ).toBeInTheDocument();
  });
});
