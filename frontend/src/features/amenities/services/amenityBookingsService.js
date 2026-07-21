import { amenityBookingsMock } from '../../../data/amenityBookings.js';
import { initialPayments } from '../../../data/payments.js';
import { initialUsers } from '../../../data/users.js';
import { genId } from '../../../lib/ids.js';
import {
  BOOKING_STATUS,
  isCancelledBooking,
} from '../constants/bookingStatuses.js';
import { BOOKING_TIMELINE_STATE } from '../constants/bookingTimelineStates.js';
import {
  loadAmenityBookings,
  saveAmenityBookings,
} from '../persistence/amenityBookingsPersistence.js';
import {
  createHourlySlots,
  createTimelineBlocks,
} from '../utils/amenityTimeline.js';

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

const getAllBookings = () => loadAmenityBookings(amenityBookingsMock);

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

const getOutstandingDues = (residentId) =>
  initialPayments
    .filter(
      (payment) =>
        payment.userId === residentId && payment.status === 'Unpaid'
    )
    .reduce((total, payment) => total + Number(payment.amount || 0), 0);

const createApprovalRecord = (booking) => {
  const resident = initialUsers.find(
    (user) => user.id === booking.residentId
  );

  return {
    ...cloneBooking(booking),
    residentFlat: resident?.flat ?? booking.residentFlat ?? null,
    outstandingDues: getOutstandingDues(booking.residentId),
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
  getAllBookings()
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
  getAllBookings()
    .map(cloneBooking)
    .sort((firstBooking, secondBooking) =>
      secondBooking.date.localeCompare(firstBooking.date)
    );

export const getBookableResidents = async () =>
  initialUsers
    .filter(
      (user) => user.role === 'Resident' && user.status === 'Active'
    )
    .map((resident) => ({ ...resident }));

export const getAmenityApprovalRequests = async (amenityId) =>
  getAllBookings()
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
  const bookings = getAllBookings();
  const booking = bookings.find((record) => record.id === bookingId);

  if (
    !booking ||
    booking.requiresApproval !== true ||
    booking.source !== 'resident' ||
    booking.status !== BOOKING_STATUS.PENDING
  ) {
    throw new Error('This booking request is no longer pending approval.');
  }

  const timestamp = new Date().toISOString();
  const approvedBooking = {
    ...booking,
    status: BOOKING_STATUS.APPROVED,
    approvedAt: timestamp,
    updatedAt: timestamp,
  };

  saveAmenityBookings(
    bookings.map((record) =>
      record.id === bookingId ? approvedBooking : record
    )
  );
  return createApprovalRecord(approvedBooking);
};

export const rejectAmenityBookingRequest = async (
  bookingId,
  rejectionData
) => {
  const bookings = getAllBookings();
  const booking = bookings.find((record) => record.id === bookingId);

  if (!booking || booking.requiresApproval !== true) {
    throw new Error('Booking request could not be found.');
  }

  if (booking.status === BOOKING_STATUS.APPROVED) {
    throw new Error('This booking request has already been approved.');
  }

  if (booking.status === BOOKING_STATUS.REJECTED) {
    throw new Error('This booking request has already been rejected.');
  }

  if (booking.status !== BOOKING_STATUS.PENDING) {
    throw new Error('This booking request is no longer pending approval.');
  }

  if (!rejectionData.reason) {
    throw new Error('Select a rejection reason.');
  }

  if (
    rejectionData.reason === 'other' &&
    !rejectionData.otherReason?.trim()
  ) {
    throw new Error('Add the rejection reason.');
  }

  if (!rejectionData.rejectedBy) {
    throw new Error('The rejecting administrator could not be identified.');
  }

  const timestamp = new Date().toISOString();
  const rejectedBooking = {
    ...booking,
    status: BOOKING_STATUS.REJECTED,
    rejectionReason:
      rejectionData.reason === 'other'
        ? rejectionData.otherReason.trim()
        : rejectionData.reason,
    rejectionReasonCode: rejectionData.reason,
    rejectedBy: rejectionData.rejectedBy,
    rejectedAt: timestamp,
    notifyResident: Boolean(rejectionData.notifyResident),
    updatedAt: timestamp,
  };

  saveAmenityBookings(
    bookings.map((record) =>
      record.id === bookingId ? rejectedBooking : record
    )
  );
  return createApprovalRecord(rejectedBooking);
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
}) => {
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

export const createAmenityBlockedSlot = async (blockedSlotData) => {
  await assertSlotAvailable(blockedSlotData);

  const timestamp = new Date().toISOString();
  const blockedSlot = {
    id: genId('blocked'),
    amenityId: blockedSlotData.amenityId,
    residentId: null,
    residentName: null,
    bookingTitle: blockedSlotData.reason.trim(),
    date: blockedSlotData.date,
    startTime: blockedSlotData.startTime,
    endTime: blockedSlotData.endTime,
    state: BOOKING_TIMELINE_STATE.BLOCKED,
    bookingType: 'maintenance-reservation',
    status: BOOKING_STATUS.BLOCKED,
    reason: blockedSlotData.reason.trim(),
    department: blockedSlotData.department,
    notes: blockedSlotData.notes?.trim() || null,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
  const bookings = getAllBookings();

  saveAmenityBookings([...bookings, blockedSlot]);
  return cloneBooking(blockedSlot);
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
  const bookings = getAllBookings();
  const existingBooking = bookings.find((booking) => booking.id === bookingId);

  if (!existingBooking) {
    throw new Error('The linked booking could not be found.');
  }

  if (
    ![BOOKING_STATUS.APPROVED, BOOKING_STATUS.CONFIRMED].includes(
      existingBooking.status
    )
  ) {
    throw new Error('This booking is no longer eligible for force cancellation.');
  }

  if (!cancellationData.reason || !cancellationData.cancelledBy) {
    throw new Error('A cancellation reason and administrator are required.');
  }

  const timestamp = new Date().toISOString();
  const cancelledBooking = {
    ...existingBooking,
    status: BOOKING_STATUS.CANCELLED,
    forceCancelled: true,
    forceCancelReason: cancellationData.reason,
    forceCancelledBy: cancellationData.cancelledBy,
    forceCancelledAt: timestamp,
    cancellationReason: cancellationData.reason,
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

export const sortAmenityBookings = (bookings) =>
  sortBookings(bookings).map(cloneBooking);
