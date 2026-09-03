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
  fetchBookingConflicts: vi.fn(),
  showToast: vi.fn(),
  addActivity: vi.fn(),
}));

vi.mock('../../features/resident/residentApi.js', () => ({
  residentApi: {
    availableAmenities: mocks.availableAmenities,
    amenityBookings: mocks.amenityBookings,
  },
}));

vi.mock(
  '../../features/amenities/services/amenityBookingsService.js',
  async (importOriginal) => ({
    // The real `evaluateBookingSlot` stays: it is pure arithmetic over the
    // bookings handed to it, and the page's slot filtering is what is under
    // test. Only the network half is mocked.
    ...(await importOriginal()),
    cancelResidentAmenityBookingDays: vi.fn(),
    createResidentAmenityBookingSeries: vi.fn(),
    // `{ bookings, verified }`: the conflict read is the ADMIN-guarded
    // snapshot, so "we could not check" is one of its normal answers
    // (issue #48 D5).
    fetchBookingConflicts: mocks.fetchBookingConflicts,
  })
);

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
  mocks.fetchBookingConflicts
    .mockReset()
    .mockResolvedValue({ bookings: [], verified: true });
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
    // The check succeeded, so nothing hedges about it.
    expect(
      within(dialog).queryByText(/could not check which slots/i)
    ).not.toBeInTheDocument();
  });
});

// Issue #48 D5, at the screen. The slot hint reads `GET /dashboard/snapshot`,
// which 403s the resident looking at this very form. That rejection used to
// escape the effect, so `isCheckingSlots` never cleared: the dropdown read
// "Checking availability..." for as long as the page stayed open and the
// submit button stayed disabled behind it.
describe('resident booking dialog when availability cannot be checked', () => {
  const hoursAmenity = () =>
    bookableAmenity({ openingTime: '06:00', closingTime: '22:00' });

  it('offers the slots and says the check did not happen, rather than hanging', async () => {
    mocks.availableAmenities.mockResolvedValue({ items: [hoursAmenity()] });
    mocks.fetchBookingConflicts.mockResolvedValue({
      bookings: [],
      verified: false,
    });
    const user = userEvent.setup();
    renderPage();
    const dialog = await openDialog(user);

    expect(
      await within(dialog).findByText(/could not check which slots are already taken/i)
    ).toBeInTheDocument();
    expect(
      within(dialog).queryByRole('option', {
        name: 'Checking availability...',
      })
    ).not.toBeInTheDocument();
    expect(
      within(dialog).getByRole('option', { name: /6:00 am - 7:00 am/i })
    ).toBeEnabled();
    expect(
      within(dialog).getByRole('button', { name: /book 1 day/i })
    ).toBeEnabled();
  });

  it('recovers the same way when the hint throws outright', async () => {
    mocks.availableAmenities.mockResolvedValue({ items: [hoursAmenity()] });
    mocks.fetchBookingConflicts.mockRejectedValue(
      new Error('Network request failed.')
    );
    const user = userEvent.setup();
    renderPage();
    const dialog = await openDialog(user);

    expect(
      await within(dialog).findByText(/could not check which slots are already taken/i)
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole('button', { name: /book 1 day/i })
    ).toBeEnabled();
  });
});

// Pins the stacking-context escape for the booking modal. Rendered in place,
// it sat inside ResidentLayout's `<main class="animate-fade-in">` — a
// fill-forwards opacity animation keeps <main> a stacking context forever, so
// the overlay's z-[999] was trapped below the sticky header's z-40. The portal
// to document.body is what makes the overlay immune. (The manage-booking-days
// modal takes the same portal; it needs a live booking group to open, so the
// booking form stands in for the contract here.)
describe('resident booking modal portal contract', () => {
  it('portals the dialog to document.body, top-anchored with internal scroll', async () => {
    const user = userEvent.setup();
    renderPage();
    const dialog = await openDialog(user);

    const overlay = dialog.parentElement;
    expect(overlay.parentElement).toBe(document.body);
    expect(overlay.className).toContain('fixed inset-0');
    expect(overlay.className).toContain('z-[999]');
    // Top-anchored: a panel taller than the viewport clips at the bottom into
    // its own scrollbar, never at the title.
    expect(overlay.className).toContain('items-start');
    expect(dialog.className).toContain('overflow-y-auto');
    expect(dialog.className).toContain('max-h-[calc(100vh-4rem)]');
  });

  it('keeps the close-button behavior', async () => {
    const user = userEvent.setup();
    renderPage();
    await openDialog(user);

    await user.click(
      screen.getByRole('button', { name: 'Close booking form' })
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
