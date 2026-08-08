import { getDashboardSnapshot } from '../../../lib/dashboard/dashboardApi.js';
import { genId } from '../../../lib/ids.js';
import {
  BOOKING_STATUS,
  isCancelledBooking,
} from '../constants/bookingStatuses.js';
import { BOOKING_TIMELINE_STATE } from '../constants/bookingTimelineStates.js';
import {
  createHourlySlots,
  createTimelineBlocks,
} from '../utils/amenityTimeline.js';
import { getAmenityById } from './amenitiesService.js';
import { api } from '../../../lib/api/client.js';

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

let bookingCache = [];

const refreshBookings = async () => {
  bookingCache = (await getDashboardSnapshot()).bookings.map(cloneBooking);
  return bookingCache;
};

const getAllBookings = () => bookingCache.map(cloneBooking);
const saveAmenityBookings = (bookings) => {
  bookingCache = bookings.map(cloneBooking);
  return getAllBookings();
};

const sortBookings = (bookings) =>
  [...bookings].sort((firstBooking, secondBooking) =>
    firstBooking.startTime.localeCompare(secondBooking.startTime)
  );

const APPROVAL_STATUSES = new Set([
  BOOKING_STATUS.PENDING,
  BOOKING_STATUS.APPROVED,
  BOOKING_STATUS.REJECTED,
  BOOKING_STATUS.CANCELLED,
]);

const isTimelineVisibleBooking = (booking) =>
  ![
    BOOKING_STATUS.PENDING,
    BOOKING_STATUS.REJECTED,
    BOOKING_STATUS.CANCELLED,
  ].includes(booking.status);

const isAvailabilityBlockingBooking = (booking) =>
  ![BOOKING_STATUS.REJECTED, BOOKING_STATUS.CANCELLED].includes(
    booking.status
  );

const getOutstandingDues = () => 0;

const createApprovalRecord = (booking) => {
  return {
    ...cloneBooking(booking),
    residentFlat: booking.residentFlat ?? null,
    outstandingDues: getOutstandingDues(),
  };
};

const assertValidTimeRange = (startTime, endTime) => {
  if (
    !startTime ||
    !endTime ||
    timeToMinutes(endTime) <= timeToMinutes(startTime)
  ) {
    throw new Error('End time must be later than start time.');
  }
};

const assertValidBookingDetails = (bookingData) => {
  if (!bookingData.residentId || !bookingData.residentName) {
    throw new Error('Select a resident.');
  }

  if (!bookingData.bookingType) {
    throw new Error('Select a booking type.');
  }

  if (!bookingData.date) {
    throw new Error('Select a booking date.');
  }

  if (Number(bookingData.guestCount) < 0) {
    throw new Error('Guest count cannot be negative.');
  }

  assertValidTimeRange(bookingData.startTime, bookingData.endTime);
};

export const getAmenityBookings = async (amenityId, date) =>
  (await refreshBookings())
    .filter(
      (booking) =>
        booking.amenityId === amenityId &&
        booking.date === date &&
        isTimelineVisibleBooking(booking)
    )
    .sort((firstBooking, secondBooking) =>
      firstBooking.startTime.localeCompare(secondBooking.startTime)
    )
    .map(cloneBooking);

export const getAllAmenityBookings = async () =>
  (await refreshBookings())
    .map(cloneBooking)
    .sort((firstBooking, secondBooking) =>
      secondBooking.date.localeCompare(firstBooking.date)
    );

export const getResidentAmenityBookings = async (residentId) =>
  (await refreshBookings())
    .filter((booking) => booking.residentId === residentId)
    .map(cloneBooking)
    .sort((firstBooking, secondBooking) => {
      const dateComparison = firstBooking.date.localeCompare(
        secondBooking.date
      );

      return dateComparison !== 0
        ? dateComparison
        : firstBooking.startTime.localeCompare(secondBooking.startTime);
    });

export const getBookableResidents = async () =>
  (await getDashboardSnapshot()).users
    .filter(
      (user) => user.role === 'Resident' && user.status === 'Active'
    )
    .map((resident) => ({ ...resident }));

export const getAmenityApprovalRequests = async (amenityId) =>
  (await refreshBookings())
    .filter(
      (booking) =>
        booking.amenityId === amenityId &&
        booking.requiresApproval === true &&
        booking.source === 'resident' &&
        APPROVAL_STATUSES.has(booking.status)
    )
    .sort((firstBooking, secondBooking) =>
      secondBooking.createdAt.localeCompare(firstBooking.createdAt)
    )
    .map(createApprovalRecord);

export const approveAmenityBookingRequest = async (bookingId) => {
  try {
    const result = await api(`/amenity-bookings/${bookingId}/approve`, {
      method: 'POST',
      body: JSON.stringify({})
    });
    await refreshBookings();
    return result;
  } catch (err) {
    throw new Error(err.message || 'Failed to approve booking.');
  }
};

export const rejectAmenityBookingRequest = async (
  bookingId,
  rejectionData
) => {
  const payload = {
    reasonCode: rejectionData.reason,
    reason: rejectionData.otherReason?.trim() || null,
  };
  try {
    const result = await api(`/amenity-bookings/${bookingId}/reject`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    await refreshBookings();
    return result;
  } catch (err) {
    throw new Error(err.message || 'Failed to reject booking.');
  }
};

export const validateBookingSlot = async ({
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
}) => {
  await refreshBookings();
  assertValidTimeRange(startTime, endTime);

  const proposedStart = timeToMinutes(startTime);
  const proposedEnd = timeToMinutes(endTime);
  const openingMinutes = timeToMinutes(openingTime);
  const closingMinutes = timeToMinutes(closingTime);

  if (proposedStart < openingMinutes || proposedEnd > closingMinutes) {
    return false;
  }

  const dayBookings = getAllBookings().filter(
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

const assertSlotAvailable = async (bookingData) => {
  const isAvailable = await validateBookingSlot(bookingData);

  if (!isAvailable) {
    throw new Error(
      'This time slot is no longer available. Select another slot and try again.'
    );
  }
};

export const createAmenityBooking = async (bookingData) => {
  assertValidBookingDetails(bookingData);
  await assertSlotAvailable(bookingData);

  const timestamp = new Date().toISOString();
  const booking = {
    id: genId('booking'),
    amenityId: bookingData.amenityId,
    residentId: bookingData.residentId,
    residentName: bookingData.residentName,
    bookingTitle: bookingData.bookingTitle,
    date: bookingData.date,
    startTime: bookingData.startTime,
    endTime: bookingData.endTime,
    state: BOOKING_TIMELINE_STATE.BOOKED,
    bookingType: bookingData.bookingType,
    status: BOOKING_STATUS.CONFIRMED,
    source: 'admin-override',
    requiresApproval: false,
    isPrivateBooking: Boolean(bookingData.isPrivateBooking),
    guestCount: Number(bookingData.guestCount) || 0,
    guests: (bookingData.guests ?? []).map((guest) => ({ ...guest })),
    notes: bookingData.notes,
    chargeOverride:
      bookingData.chargeOverride === '' ||
      bookingData.chargeOverride == null
        ? null
        : Number(bookingData.chargeOverride),
    createdAt: timestamp,
    updatedAt: timestamp,
  };
  const bookings = getAllBookings();

  saveAmenityBookings([...bookings, booking]);
  return cloneBooking(booking);
};

const getDayName = (date) =>
  new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    timeZone: 'UTC',
  }).format(new Date(`${date}T00:00:00.000Z`));

const assertResidentBookingRules = (
  amenity,
  bookingData,
  bookings,
  additionalBookingCount = 1
) => {
  if (!amenity || !amenity.isActive) {
    throw new Error('This amenity is currently unavailable.');
  }

  const availability = amenity.availabilitySettings;
  const bookingSettings = amenity.bookingSettings;
  const selectedDay = getDayName(bookingData.date);

  if (
    availability.temporaryClosure ||
    availability.closedDays.includes(selectedDay) ||
    availability.maintenanceDays.includes(selectedDay) ||
    availability.holidayOverrides.includes(bookingData.date)
  ) {
    throw new Error('This amenity is closed on the selected date.');
  }

  const today = new Date();
  const todayIso = today.toISOString().split('T')[0];
  const selectedDate = new Date(`${bookingData.date}T00:00:00.000Z`);
  const todayDate = new Date(`${todayIso}T00:00:00.000Z`);
  const daysInAdvance = Math.round(
    (selectedDate.getTime() - todayDate.getTime()) / 86400000
  );

  if (daysInAdvance < 0) {
    throw new Error('Select today or a future date.');
  }

  if (!bookingSettings.allowSameDayBooking && daysInAdvance === 0) {
    throw new Error('Same-day bookings are not allowed for this amenity.');
  }

  if (daysInAdvance > availability.advanceBookingWindowDays) {
    throw new Error(
      `Bookings can only be made ${availability.advanceBookingWindowDays} days in advance.`
    );
  }

  const supportsPrivateBooking =
    amenity.bookingMode === 'Exclusive' ||
    (amenity.bookingMode === 'Hybrid' &&
      bookingSettings.allowPrivateBooking);

  if (bookingData.isPrivateBooking && !supportsPrivateBooking) {
    throw new Error('Private bookings are not allowed for this amenity.');
  }

  if (
    !bookingData.isPrivateBooking &&
    amenity.bookingMode === 'Exclusive'
  ) {
    throw new Error('This amenity only supports private bookings.');
  }

  if (Number(bookingData.guestCount) > 0 && !bookingSettings.allowGuestBooking) {
    throw new Error('Guest bookings are not allowed for this amenity.');
  }

  if (
    amenity.capacity != null &&
    Number(bookingData.guestCount) + 1 > amenity.capacity
  ) {
    throw new Error(
      `This amenity allows up to ${amenity.capacity} people per booking.`
    );
  }

  const duration =
    timeToMinutes(bookingData.endTime) - timeToMinutes(bookingData.startTime);

  if (duration < availability.minimumBookingDurationMinutes) {
    throw new Error(
      `Bookings must be at least ${availability.minimumBookingDurationMinutes} minutes.`
    );
  }

  if (duration > availability.maximumBookingDurationMinutes) {
    throw new Error(
      `Bookings cannot exceed ${availability.maximumBookingDurationMinutes} minutes.`
    );
  }

  const bookingLimit = bookingSettings.maxActiveBookingsPerResident;

  if (bookingLimit != null) {
    const activeBookingCount = new Set(
      bookings
        .filter(
          (booking) =>
            booking.residentId === bookingData.residentId &&
            booking.amenityId === bookingData.amenityId &&
            booking.date >= todayIso &&
            ![
              BOOKING_STATUS.CANCELLED,
              BOOKING_STATUS.REJECTED,
              BOOKING_STATUS.COMPLETED,
            ].includes(booking.status)
        )
        .map((booking) => booking.bookingGroupId ?? booking.id)
    ).size;

    if (activeBookingCount + additionalBookingCount > bookingLimit) {
      throw new Error(
        `You can have up to ${bookingLimit} active bookings for this amenity.`
      );
    }
  }
};

const createResidentBookingRecord = (
  bookingData,
  amenity,
  timestamp,
  groupData
) => {
  const requiresApproval =
    amenity.bookingSettings.requireAdminApproval &&
    !amenity.bookingSettings.enableAutoApproval;
  return {
    id: genId('booking'),
    amenityId: bookingData.amenityId,
    residentId: bookingData.residentId,
    residentName: bookingData.residentName,
    bookingTitle: bookingData.bookingTitle || 'Resident Booking',
    date: bookingData.date,
    startTime: bookingData.startTime,
    endTime: bookingData.endTime,
    state: BOOKING_TIMELINE_STATE.BOOKED,
    bookingType: bookingData.isPrivateBooking
      ? 'private-event'
      : 'resident',
    status: requiresApproval
      ? BOOKING_STATUS.PENDING
      : BOOKING_STATUS.CONFIRMED,
    source: 'resident',
    requiresApproval,
    isPrivateBooking: Boolean(bookingData.isPrivateBooking),
    guestCount: Number(bookingData.guestCount) || 0,
    guests: [],
    notes: bookingData.notes?.trim() || null,
    chargeOverride: null,
    ...groupData,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
};

export const createResidentAmenityBookingSeries = async (bookingData) => {
  const dates = [
    ...new Set(bookingData.dates ?? [bookingData.date]),
  ].sort();

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
  
  try {
    const result = await api('/amenities/bookings/request', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    await refreshBookings();
    return result.items || [];
  } catch (err) {
    throw new Error(err.message || 'Failed to create booking request.');
  }
};

export const createResidentAmenityBooking = async (bookingData) => {
  const bookings = await createResidentAmenityBookingSeries({
    ...bookingData,
    dates: [bookingData.date],
  });
  return bookings[0];
};

export const cancelResidentAmenityBookingDays = async ({
  bookingIds,
  residentId,
  reason,
}) => {
  const payload = {
    occurrenceIds: bookingIds,
    reason: reason?.trim() || null,
  };
  try {
    const result = await api('/amenity-bookings/cancel', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    await refreshBookings();
    return bookingIds.map(id => ({ id }));
  } catch (err) {
    throw new Error(err.message || 'Failed to cancel bookings.');
  }
};

export const createAmenityBlockedSlot = async (blockedSlotData) => {
  const payload = {
    date: blockedSlotData.date,
    startTime: blockedSlotData.startTime,
    endTime: blockedSlotData.endTime,
    reason: blockedSlotData.reason.trim(),
    department: blockedSlotData.department,
    notes: blockedSlotData.notes?.trim() || null,
  };
  
  try {
    const result = await api('/amenities/blocks', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    await refreshBookings();
    return result;
  } catch (err) {
    throw new Error(err.message || 'Failed to block slot.');
  }
};

export const updateAmenityBooking = async (bookingId, bookingData) => {
  assertValidBookingDetails(bookingData);

  const bookings = getAllBookings();
  const existingBooking = bookings.find((booking) => booking.id === bookingId);

  if (
    !existingBooking ||
    existingBooking.state !== BOOKING_TIMELINE_STATE.BOOKED ||
    isCancelledBooking(existingBooking)
  ) {
    throw new Error('This booking is no longer available to edit.');
  }

  await assertSlotAvailable({
    ...bookingData,
    excludeBookingId: bookingId,
  });

  const updatedBooking = {
    ...existingBooking,
    residentId: bookingData.residentId,
    residentName: bookingData.residentName,
    bookingTitle: bookingData.bookingTitle || existingBooking.bookingTitle,
    date: bookingData.date,
    startTime: bookingData.startTime,
    endTime: bookingData.endTime,
    bookingType: bookingData.bookingType,
    isPrivateBooking: Boolean(bookingData.isPrivateBooking),
    guestCount: Number(bookingData.guestCount) || 0,
    guests: (bookingData.guests ?? []).map((guest) => ({ ...guest })),
    notes: bookingData.notes,
    chargeOverride:
      bookingData.chargeOverride === '' ||
      bookingData.chargeOverride == null
        ? null
        : Number(bookingData.chargeOverride),
    updatedAt: new Date().toISOString(),
  };

  saveAmenityBookings(
    bookings.map((booking) =>
      booking.id === bookingId ? updatedBooking : booking
    )
  );
  return cloneBooking(updatedBooking);
};

export const cancelAmenityBooking = async (
  bookingId,
  cancellationData
) => {
  if (!cancellationData.reason) {
    throw new Error('Select a cancellation reason.');
  }

  if (
    cancellationData.reason === 'other' &&
    !cancellationData.details?.trim()
  ) {
    throw new Error('Add details for the cancellation reason.');
  }

  const bookings = getAllBookings();
  const existingBooking = bookings.find((booking) => booking.id === bookingId);

  if (
    !existingBooking ||
    existingBooking.state !== BOOKING_TIMELINE_STATE.BOOKED ||
    isCancelledBooking(existingBooking)
  ) {
    throw new Error('This booking is no longer available to cancel.');
  }

  const timestamp = new Date().toISOString();
  const cancelledBooking = {
    ...existingBooking,
    status: BOOKING_STATUS.CANCELLED,
    cancellationReason: cancellationData.reason,
    cancellationDetails: cancellationData.details?.trim() || null,
    cancelledAt: timestamp,
    updatedAt: timestamp,
  };

  saveAmenityBookings(
    bookings.map((booking) =>
      booking.id === bookingId ? cancelledBooking : booking
    )
  );
  return cloneBooking(cancelledBooking);
};

export const forceCancelAmenityBooking = async (
  bookingId,
  cancellationData
) => {
  const payload = {
    reasonCode: cancellationData.reason,
    reason: cancellationData.otherReason?.trim() || null,
  };
  try {
    const result = await api(`/amenity-bookings/${bookingId}/force-cancel`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    await refreshBookings();
    return result;
  } catch (err) {
    throw new Error(err.message || 'Failed to force cancel booking.');
  }
};

export const sortAmenityBookings = (bookings) =>
  sortBookings(bookings).map(cloneBooking);
