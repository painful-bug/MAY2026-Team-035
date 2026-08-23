import {
  BOOKING_MODE,
  BOOKING_MODE_OPTIONS,
} from '../constants/bookingModes.js';

export const validateAmenityForm = (values) => {
  const errors = {};

  if (!values.name.trim()) {
    errors.name = 'Amenity name is required.';
  }

  if (!values.description.trim()) {
    errors.description = 'Description is required.';
  }

  if (!values.openingTime) {
    errors.openingTime = 'Opening time is required.';
  }

  if (!values.closingTime) {
    errors.closingTime = 'Closing time is required.';
  } else if (values.openingTime && values.closingTime <= values.openingTime) {
    // The hours are persisted now, and both the write model and the
    // `amenities_hours_check` constraint behind it refuse closing <= opening.
    // Saying so here beats a 422 that arrives after the form is filled in.
    // `HH:MM` strings compare correctly as strings.
    errors.closingTime = 'Closing time must be later than opening time.';
  }

  const validBookingModes = BOOKING_MODE_OPTIONS.map((option) => option.value);
  const supportsSharedCapacity =
    values.bookingMode === BOOKING_MODE.SHARED ||
    values.bookingMode === BOOKING_MODE.HYBRID;

  if (!validBookingModes.includes(values.bookingMode)) {
    errors.bookingMode = 'Booking mode is required.';
  }

  if (supportsSharedCapacity) {
    const capacity = Number(values.capacity);

    if (values.capacity === '' || !Number.isFinite(capacity)) {
      errors.capacity = 'Enter a valid capacity.';
    } else if (capacity <= 0) {
      errors.capacity = 'Capacity must be greater than zero.';
    }
  }

  if (values.cleaningBuffer !== '') {
    const cleaningBuffer = Number(values.cleaningBuffer);

    if (!Number.isFinite(cleaningBuffer)) {
      errors.cleaningBuffer = 'Enter a valid cleaning buffer.';
    } else if (cleaningBuffer < 0) {
      errors.cleaningBuffer = 'Cleaning buffer cannot be negative.';
    }
  }

  if (values.maxBookingsPerResident !== '') {
    const maximumBookings = Number(values.maxBookingsPerResident);

    if (!Number.isFinite(maximumBookings)) {
      errors.maxBookingsPerResident = 'Enter a valid booking limit.';
    } else if (maximumBookings < 0) {
      errors.maxBookingsPerResident = 'Maximum bookings cannot be negative.';
    }
  }

  return errors;
};
