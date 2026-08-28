import { getDashboardSnapshot } from '../../../lib/dashboard/dashboardApi.js';
import { BOOKING_STATUS } from '../constants/bookingStatuses.js';
import { BOOKING_TIMELINE_STATE } from '../constants/bookingTimelineStates.js';
import {
  createHourlySlots,
  createTimelineBlocks,
} from '../utils/amenityTimeline.js';
import { api } from '../../../lib/api/client.js';

// What is left of the demo booking service: the resident booking form, and
// nothing else.
//
// **Seventeen exports used to live here.** The admin half of them — the day
// timeline, the approvals queue, create-on-behalf, edit, cancel, block and
// force-cancel — moved to `features/amenities/amenitiesApi.js` and are read
// through react-query by the screens that need them. The demo halves that
// invented bookings in a module-level array went with them, along with
// `getResidentAmenityBookings`, which filtered `GET /dashboard/snapshot` by a
// resident id: that endpoint is ADMIN/MANAGER-guarded, so the resident's own
// bookings table `403`d every time it loaded. It reads
// `GET /amenity-bookings/mine` now.
//
// The three below serve `pages/ResidentDashboard/Amenities.jsx`. Two of them
// are already real API calls. The third is not, and says so.

const cloneBooking = (booking) => ({
  ...booking,
  guests: Array.isArray(booking.guests)
    ? booking.guests.map((guest) => ({ ...guest }))
    : booking.guests,
});

const timeToMinutes = (time) => {
  const [hours, minutes] = time.split(':').map(Number);
  return hours * 60 + minutes;
};

const intervalsOverlap = (firstStart, firstEnd, secondStart, secondEnd) =>
  firstStart < secondEnd && firstEnd > secondStart;

const isAvailabilityBlockingBooking = (booking) =>
  ![BOOKING_STATUS.REJECTED, BOOKING_STATUS.CANCELLED].includes(booking.status);

const assertValidTimeRange = (startTime, endTime) => {
  if (
    !startTime ||
    !endTime ||
    timeToMinutes(endTime) <= timeToMinutes(startTime)
  ) {
    throw new Error('End time must be later than start time.');
  }
};

// The slot picker's hint, and it is a HINT — never an answer the UI may
// present as verified.
//
// It greys out slots the resident probably cannot have, working that out from
// `GET /dashboard/snapshot`, which is ADMIN/MANAGER-guarded and therefore
// `403`s for the very person looking at the booking form. There is no resident
// read that would answer it either: §10 of docs/API.md is explicit that **no
// availability check happens in the API**, because a read describing which
// slots are free describes a moment that has already passed. Availability is
// decided on write, under an advisory lock, and a `409` is the real answer.
//
// So the failure is no longer allowed to be fatal (issue #48 D5). A snapshot
// the caller may not read leaves the conflict cache empty and the check
// UNVERIFIED: the opening-hours window — which is local arithmetic and needs
// no server — is still applied, everything else resolves optimistically, and
// `checkBookingSlotAvailability` reports `verified: false` so the screen can
// say so rather than claim a check it did not perform. What it must never do
// again is reject: a rejected promise here left "Checking availability..." on
// screen for good.
let bookingCache = [];

const refreshBookings = async () => {
  try {
    bookingCache = ((await getDashboardSnapshot()).bookings ?? []).map(
      cloneBooking
    );
    return true;
  } catch {
    bookingCache = [];
    return false;
  }
};

const getAllBookings = () => bookingCache.map(cloneBooking);

/**
 * One snapshot fetch for a whole grid of slot-date questions.
 *
 * `checkBookingSlotAvailability` below re-fetches the ENTIRE dashboard
 * snapshot per slot-date pair, which is up to slots x dates full snapshot
 * requests when a screen asks about all of them at once. A screen that needs
 * the grid calls this ONCE per amenity/date-range change and then answers
 * every pair locally with `evaluateBookingSlot`, passing `bookings` in.
 *
 * Never rejects: a refused snapshot (the resident cannot read it) resolves
 * `{ bookings: [], verified: false }`, the same optimistic contract as the
 * per-pair call.
 */
export const fetchBookingConflicts = async () => {
  const verified = await refreshBookings();
  return { bookings: getAllBookings(), verified };
};

// Pure, over whatever `refreshBookings` managed to cache — or over an
// explicit `bookings` array handed in by a caller that fetched once via
// `fetchBookingConflicts`. With an empty list — the caller was forbidden the
// snapshot — every conflict test below finds nothing to conflict with and the
// answer collapses to the opening-hours window, which is the optimistic half
// of the contract.
export const evaluateBookingSlot = ({
  amenityId,
  date,
  startTime,
  endTime,
  openingTime,
  closingTime,
  cleaningBuffer = 0,
  excludeBookingId = null,
  bookingMode = null,
  isPrivateBooking = false,
  guestCount = 0,
  capacity = null,
  bookings = null,
}) => {
  assertValidTimeRange(startTime, endTime);

  const proposedStart = timeToMinutes(startTime);
  const proposedEnd = timeToMinutes(endTime);
  const openingMinutes = timeToMinutes(openingTime);
  const closingMinutes = timeToMinutes(closingTime);

  if (proposedStart < openingMinutes || proposedEnd > closingMinutes) {
    return false;
  }

  const dayBookings = (bookings ?? getAllBookings()).filter(
    (booking) =>
      booking.amenityId === amenityId &&
      booking.date === date &&
      booking.id !== excludeBookingId &&
      isAvailabilityBlockingBooking(booking)
  );
  const supportsSharedCapacity =
    ['Shared', 'Hybrid'].includes(bookingMode) && !isPrivateBooking;

  if (supportsSharedCapacity) {
    const overlappingBookings = dayBookings.filter((booking) =>
      intervalsOverlap(
        proposedStart,
        proposedEnd,
        timeToMinutes(booking.startTime),
        timeToMinutes(booking.endTime)
      )
    );
    const hasExclusiveConflict = overlappingBookings.some(
      (booking) =>
        booking.state === BOOKING_TIMELINE_STATE.BLOCKED ||
        booking.isPrivateBooking ||
        booking.bookingType === 'private-event'
    );

    if (hasExclusiveConflict) {
      return false;
    }

    if (capacity != null) {
      const occupiedCapacity = overlappingBookings.reduce(
        (total, booking) => total + 1 + Number(booking.guestCount || 0),
        0
      );

      if (occupiedCapacity + 1 + Number(guestCount || 0) > Number(capacity)) {
        return false;
      }
    }

    const timelineBlocks = createTimelineBlocks(
      dayBookings,
      createHourlySlots(openingTime, closingTime),
      cleaningBuffer
    );
    return !timelineBlocks
      .filter(
        (block) =>
          block.state === BOOKING_TIMELINE_STATE.CLEANING_BUFFER ||
          block.state === BOOKING_TIMELINE_STATE.BLOCKED
      )
      .some((block) =>
        intervalsOverlap(
          proposedStart,
          proposedEnd,
          timeToMinutes(block.startTime),
          timeToMinutes(block.endTime)
        )
      );
  }

  const timelineBlocks = createTimelineBlocks(
    dayBookings,
    createHourlySlots(openingTime, closingTime),
    cleaningBuffer
  );

  return !timelineBlocks.some((block) =>
    intervalsOverlap(
      proposedStart,
      proposedEnd,
      timeToMinutes(block.startTime),
      timeToMinutes(block.endTime)
    )
  );
};

/**
 * `{ available, verified }` — whether the slot looks bookable, and whether
 * anything beyond the amenity's own opening hours was actually checked.
 *
 * `verified: false` means the conflict read was refused (the resident cannot
 * read the admin snapshot) and `available` is the optimistic answer. Screens
 * that show the difference must not describe an unverified slot as free.
 */
export const checkBookingSlotAvailability = async (params) => {
  const verified = await refreshBookings();
  return { available: evaluateBookingSlot(params), verified };
};

/**
 * The boolean half, for callers that only grey out a slot.
 *
 * It resolves for every API outcome, 403 included — the backend decides
 * availability on write and answers with a `409` there, so a failed hint is
 * never a reason to fail a form.
 */
export const validateBookingSlot = async (params) =>
  (await checkBookingSlotAvailability(params)).available;

/**
 * `POST /amenities/{id}/bookings/request` — one or more days of the same slot.
 *
 * The flat is not sent: it is read from the caller's own residency, so a
 * resident cannot book against somebody else's unit. Every day is validated
 * before any is written, so a three-day request lands whole or not at all.
 */
export const createResidentAmenityBookingSeries = async (bookingData) => {
  const dates = [...new Set(bookingData.dates ?? [bookingData.date])].sort();

  if (dates.length === 0) {
    throw new Error('Select at least one booking date.');
  }

  const payload = {
    bookingTitle: bookingData.bookingTitle,
    dates,
    startTime: bookingData.startTime,
    endTime: bookingData.endTime,
    guestCount: bookingData.guestCount ?? 0,
    guests: Array.isArray(bookingData.guests) ? bookingData.guests : [],
    isPrivateBooking: bookingData.isPrivateBooking ?? false,
    notes: bookingData.notes ?? '',
  };

  // No cache refresh afterwards. It used to call `refreshBookings()` here —
  // inside the `try` — so a resident whose booking had just been created got
  // the snapshot's `403` translated into "Failed to create booking request".
  // The screen invalidates its own react-query key instead.
  const result = await api(
    `/amenities/${bookingData.amenityId}/bookings/request`,
    { method: 'POST', body: JSON.stringify(payload) }
  );
  return result.items || [];
};

/**
 * `POST /amenity-bookings/cancel` — withdraw selected days.
 *
 * No resident id in the payload: which days you may cancel is decided from the
 * authenticated membership, so there is nothing in the body to lie about. The
 * call is all-or-nothing — one ineligible day is a `409` for the whole request
 * rather than four cancellations reported as five.
 */
export const cancelResidentAmenityBookingDays = async ({
  bookingIds,
  reason,
}) => {
  await api('/amenity-bookings/cancel', {
    method: 'POST',
    body: JSON.stringify({
      occurrenceIds: bookingIds,
      reason: reason?.trim() || null,
    }),
  });
  return bookingIds.map((id) => ({ id }));
};
