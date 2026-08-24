const timeToMinutes = (time) => {
  const [hours, minutes] = String(time ?? '').split(':').map(Number);
  return hours * 60 + minutes;
};

// null rather than NaN for anything that is not a clock time, so callers have
// to decide what to do about it instead of propagating NaN into a value the
// form renders.
const parseClock = (time) => {
  const match = /^(\d{1,2}):([0-5]\d)(?::[0-5]\d)?$/.exec(
    String(time ?? '').trim()
  );

  if (!match) {
    return null;
  }

  const hours = Number(match[1]);
  return hours > 23 ? null : hours * 60 + Number(match[2]);
};

const LAST_MINUTE = 23 * 60 + 59;
const DEFAULT_BLOCK_START = 9 * 60;
const DEFAULT_BLOCK_LENGTH = 60;

const minutesToTime = (minutes) => {
  const clamped = Math.min(Math.max(Math.round(minutes), 0), LAST_MINUTE);
  const hours = Math.floor(clamped / 60);
  const remainingMinutes = clamped % 60;
  return `${String(hours).padStart(2, '0')}:${String(remainingMinutes).padStart(2, '0')}`;
};

/**
 * The times the Block Time form opens with.
 *
 * An amenity whose hours were never stored arrives here with
 * `openingTime: ''` / `closingTime: ''` (the snapshot rows carry no hours and
 * `normalizeAmenityRecord` does not invent any). That used to seed
 * `startTime: ''` and `endTime: 'NaN:NaN'` — a form the admin could not submit
 * before touching it, and one whose end-time input rendered blank because
 * "NaN:NaN" is not a value `<input type="time">` accepts (issue #48 D3).
 * Both fields are now always a usable `HH:MM`: the amenity's own hours when it
 * has them, an ordinary 09:00-10:00 working hour when it does not.
 */
export const getInitialBlockTime = (amenity, selectedSlot) => {
  if (selectedSlot?.startTime && selectedSlot?.endTime) {
    return {
      startTime: selectedSlot.startTime,
      endTime: selectedSlot.endTime,
    };
  }

  const openingMinutes = parseClock(amenity?.openingTime) ?? DEFAULT_BLOCK_START;
  const closingMinutes = parseClock(amenity?.closingTime);
  const endMinutes =
    closingMinutes != null && closingMinutes > openingMinutes
      ? Math.min(openingMinutes + DEFAULT_BLOCK_LENGTH, closingMinutes)
      : openingMinutes + DEFAULT_BLOCK_LENGTH;

  return {
    startTime: minutesToTime(openingMinutes),
    endTime: minutesToTime(endMinutes),
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
