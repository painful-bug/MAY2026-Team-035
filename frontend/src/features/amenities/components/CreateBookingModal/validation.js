const timeToMinutes = (time) => {
  const [hours, minutes] = time.split(':').map(Number);
  return hours * 60 + minutes;
};

export const validateBooking = (values) => {
  const errors = {};

  if (!values.residentId) {
    errors.residentId = 'Select a resident.';
  }

  if (!values.bookingType) {
    errors.bookingType = 'Select a booking type.';
  }

  if (!values.date) {
    errors.date = 'Select a booking date.';
  }

  if (!values.startTime) {
    errors.startTime = 'Select a start time.';
  }

  if (!values.endTime) {
    errors.endTime = 'Select an end time.';
  } else if (
    values.startTime &&
    timeToMinutes(values.endTime) <= timeToMinutes(values.startTime)
  ) {
    errors.endTime = 'End time must be later than start time.';
  }

  if (Number(values.guestCount) < 0) {
    errors.guestCount = 'Guest count cannot be negative.';
  }

  if (
    values.chargeOverride !== '' &&
    Number(values.chargeOverride) < 0
  ) {
    errors.chargeOverride = 'Charge override cannot be negative.';
  }

  return errors;
};

export const validateCreateBooking = validateBooking;
