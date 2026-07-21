const toMinutes = (timeValue) => {
  const [hours, minutes] = timeValue.split(':').map(Number);
  return hours * 60 + minutes;
};

const validateNonNegative = (errors, values, field, label) => {
  const number = Number(values[field]);

  if (values[field] === '' || !Number.isFinite(number) || number < 0) {
    errors[field] = `${label} cannot be negative.`;
  }
};

const validatePositive = (errors, values, field, label) => {
  const number = Number(values[field]);

  if (values[field] === '' || !Number.isFinite(number) || number <= 0) {
    errors[field] = `${label} must be greater than zero.`;
  }
};

export const validateAmenitySettings = (values) => {
  const errors = {};

  if (!values.name.trim()) {
    errors.name = 'Amenity name is required.';
  }

  if (!values.openingTime) {
    errors.openingTime = 'Opening time is required.';
  }

  if (!values.closingTime) {
    errors.closingTime = 'Closing time is required.';
  }

  if (
    values.openingTime &&
    values.closingTime &&
    toMinutes(values.openingTime) >= toMinutes(values.closingTime)
  ) {
    errors.closingTime = 'Closing time must be after opening time.';
  }

  validatePositive(errors, values, 'capacity', 'Maximum capacity');
  validatePositive(
    errors,
    values,
    'slotDurationMinutes',
    'Booking slot duration'
  );
  validateNonNegative(
    errors,
    values,
    'cleaningBufferMinutes',
    'Cleaning buffer'
  );
  validateNonNegative(errors, values, 'bookingFee', 'Booking fee');
  validateNonNegative(errors, values, 'securityDeposit', 'Security deposit');
  validateNonNegative(
    errors,
    values,
    'lateCancellationCharge',
    'Late cancellation charge'
  );
  validateNonNegative(errors, values, 'damageDeposit', 'Damage deposit');
  validatePositive(
    errors,
    values,
    'minimumBookingDurationMinutes',
    'Minimum booking duration'
  );
  validatePositive(
    errors,
    values,
    'maximumBookingDurationMinutes',
    'Maximum booking duration'
  );
  validateNonNegative(
    errors,
    values,
    'advanceBookingWindowDays',
    'Advance booking window'
  );
  validatePositive(
    errors,
    values,
    'defaultMaintenanceDurationMinutes',
    'Default maintenance duration'
  );

  if (
    !errors.minimumBookingDurationMinutes &&
    !errors.maximumBookingDurationMinutes &&
    Number(values.minimumBookingDurationMinutes) >
      Number(values.maximumBookingDurationMinutes)
  ) {
    errors.maximumBookingDurationMinutes =
      'Maximum duration must be at least the minimum duration.';
  }

  if (values.maxActiveBookingsPerResident !== '') {
    validateNonNegative(
      errors,
      values,
      'maxActiveBookingsPerResident',
      'Maximum active bookings'
    );
  }

  return errors;
};
