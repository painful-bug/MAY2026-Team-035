// The resident booking dialog's slot arithmetic, extracted verbatim from
// `pages/ResidentDashboard/Amenities.jsx` so the empty-hours behaviour has a
// unit-testable home.
//
// THE CASE THIS FILE EXISTS FOR: an amenity whose hours were never set. The
// hosted `amenities` rows can hold NULL opening/closing times, and the
// resident endpoint (`GET /amenities/available`) faithfully reports those as
// "00:00"/"00:00". Fed to `createBookingSlots`, opening == closing means the
// loop never runs — an empty slot list, which the dialog used to render as a
// silently disabled dropdown. `hasBookableHours` names that case so the
// dialog can say what is actually wrong instead.

export const timeToMinutes = (time) => {
  const [hours, minutes] = time.split(':').map(Number);
  return hours * 60 + minutes;
};

export const minutesToTime = (minutes) =>
  `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(
    minutes % 60
  ).padStart(2, '0')}`;

export const formatTime = (time) =>
  new Intl.DateTimeFormat('en-IN', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC',
  }).format(new Date(`2000-01-01T${time}:00.000Z`));

/**
 * Whether the amenity has a real booking window: both clock strings present
 * and closing strictly after opening. `"00:00"/"00:00"` — the wire's spelling
 * of NULL hours — fails this, as does anything the backend's own
 * closing-after-opening validation would refuse.
 */
export const hasBookableHours = (amenity) => {
  const opening = amenity?.openingTime;
  const closing = amenity?.closingTime;
  if (!opening || !closing) return false;
  const openingMinutes = timeToMinutes(opening);
  const closingMinutes = timeToMinutes(closing);
  return (
    Number.isFinite(openingMinutes) &&
    Number.isFinite(closingMinutes) &&
    closingMinutes > openingMinutes
  );
};

export const createBookingSlots = (amenity) => {
  if (!amenity?.openingTime || !amenity?.closingTime) {
    return [];
  }

  const minimumDuration =
    amenity.availabilitySettings.minimumBookingDurationMinutes;
  const maximumDuration =
    amenity.availabilitySettings.maximumBookingDurationMinutes;
  const configuredDuration = amenity.bookingSlotDuration || 60;
  const duration = Math.min(
    Math.max(configuredDuration, minimumDuration),
    maximumDuration
  );
  const openingMinutes = timeToMinutes(amenity.openingTime);
  const closingMinutes = timeToMinutes(amenity.closingTime);
  const slots = [];

  for (
    let startMinutes = openingMinutes;
    startMinutes + duration <= closingMinutes;
    startMinutes += configuredDuration
  ) {
    const startTime = minutesToTime(startMinutes);
    const endTime = minutesToTime(startMinutes + duration);
    slots.push({
      value: `${startTime}-${endTime}`,
      startTime,
      endTime,
      label: `${formatTime(startTime)} - ${formatTime(endTime)}`,
    });
  }

  return slots;
};
