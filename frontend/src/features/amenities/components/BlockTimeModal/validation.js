const timeToMinutes = (time) => {
  const [hours, minutes] = time.split(':').map(Number);
  return hours * 60 + minutes;
};

const minutesToTime = (minutes) => {
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${String(hours).padStart(2, '0')}:${String(remainingMinutes).padStart(2, '0')}`;
};

export const getInitialBlockTime = (amenity, selectedSlot) => {
  if (selectedSlot) {
    return {
      startTime: selectedSlot.startTime,
      endTime: selectedSlot.endTime,
    };
  }

  const openingMinutes = timeToMinutes(amenity.openingTime);
  const closingMinutes = timeToMinutes(amenity.closingTime);

  return {
    startTime: amenity.openingTime,
    endTime: minutesToTime(Math.min(openingMinutes + 60, closingMinutes)),
  };
};

export const validateBlockedSlot = (values) => {
  const errors = {};

  if (!values.reason.trim()) {
    errors.reason = 'Enter a reason for blocking this time.';
  }

  if (!values.department) {
    errors.department = 'Select a department.';
  }

  if (!values.startTime) {
    errors.startTime = 'Start time is required.';
  }

  if (!values.endTime) {
    errors.endTime = 'End time is required.';
  } else if (
    values.startTime &&
    timeToMinutes(values.endTime) <= timeToMinutes(values.startTime)
  ) {
    errors.endTime = 'End time must be later than start time.';
  }

  return errors;
};
