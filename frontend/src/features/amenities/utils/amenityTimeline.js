import { BOOKING_TIMELINE_STATE } from '../constants/bookingTimelineStates.js';

const MINUTES_PER_HOUR = 60;
const TIMELINE_INCREMENT_MINUTES = 15;

const timeToMinutes = (time) => {
  const [hours, minutes] = time.split(':').map(Number);
  return hours * MINUTES_PER_HOUR + minutes;
};

const minutesToTime = (minutes) => {
  const hours = Math.floor(minutes / MINUTES_PER_HOUR);
  const remainingMinutes = minutes % MINUTES_PER_HOUR;
  return `${String(hours).padStart(2, '0')}:${String(remainingMinutes).padStart(2, '0')}`;
};

const formatHour = (minutes) => {
  const hours = Math.floor(minutes / MINUTES_PER_HOUR) % 24;
  return {
    hour: hours % 12 || 12,
    period: hours >= 12 ? 'PM' : 'AM',
  };
};

const formatSlotLabel = (startMinutes, endMinutes) => {
  const start = formatHour(startMinutes);
  const end = formatHour(endMinutes);

  if (start.period === end.period) {
    return `${start.hour}–${end.hour} ${end.period}`;
  }

  return `${start.hour} ${start.period}–${end.hour} ${end.period}`;
};

export const formatTimelineTimeRange = (startTime, endTime) =>
  formatSlotLabel(timeToMinutes(startTime), timeToMinutes(endTime));

export const createHourlySlots = (openingTime, closingTime) => {
  if (!openingTime || !closingTime) {
    return [];
  }

  const openingMinutes = timeToMinutes(openingTime);
  const closingMinutes = timeToMinutes(closingTime);
  const slots = [];

  for (
    let startMinutes = openingMinutes;
    startMinutes < closingMinutes;
    startMinutes += MINUTES_PER_HOUR
  ) {
    const endMinutes = Math.min(
      startMinutes + MINUTES_PER_HOUR,
      closingMinutes
    );

    slots.push({
      id: `${startMinutes}-${endMinutes}`,
      startMinutes,
      endMinutes,
      startTime: minutesToTime(startMinutes),
      endTime: minutesToTime(endMinutes),
      label: formatSlotLabel(startMinutes, endMinutes),
      startSlot: Math.floor(
        (startMinutes - openingMinutes) / TIMELINE_INCREMENT_MINUTES
      ),
      endSlot: Math.ceil(
        (endMinutes - openingMinutes) / TIMELINE_INCREMENT_MINUTES
      ),
    });
  }

  return slots;
};

const createCleaningBuffers = (
  bookings,
  cleaningBuffer,
  closingMinutes
) => {
  const bufferMinutes = Number(cleaningBuffer) || 0;

  if (bufferMinutes <= 0) {
    return [];
  }

  return bookings.flatMap((booking) => {
    if (booking.state !== BOOKING_TIMELINE_STATE.BOOKED) {
      return [];
    }

    const bufferStart = timeToMinutes(booking.endTime);
    const desiredBufferEnd = Math.min(
      bufferStart + bufferMinutes,
      closingMinutes
    );
    const firstCollision = bookings
      .filter((candidate) => candidate.id !== booking.id)
      .map((candidate) => ({
        start: timeToMinutes(candidate.startTime),
        end: timeToMinutes(candidate.endTime),
      }))
      .filter(
        (candidate) =>
          candidate.start < desiredBufferEnd && candidate.end > bufferStart
      )
      .sort((first, second) => first.start - second.start)[0];
    const bufferEnd = firstCollision
      ? Math.min(desiredBufferEnd, Math.max(bufferStart, firstCollision.start))
      : desiredBufferEnd;

    if (bufferEnd <= bufferStart) {
      return [];
    }

    return [
      {
        id: `buffer-${booking.id}`,
        amenityId: booking.amenityId,
        bookingTitle: 'Cleaning Buffer',
        startTime: booking.endTime,
        endTime: minutesToTime(bufferEnd),
        state: BOOKING_TIMELINE_STATE.CLEANING_BUFFER,
        bufferMinutes: bufferEnd - bufferStart,
      },
    ];
  });
};

export const createTimelineBlocks = (
  bookings,
  slots,
  cleaningBuffer = 0
) => {
  if (slots.length === 0) {
    return [];
  }

  const openingMinutes = slots[0].startMinutes;
  const closingMinutes = slots[slots.length - 1].endMinutes;
  const scheduleItems = [
    ...bookings,
    ...createCleaningBuffers(bookings, cleaningBuffer, closingMinutes),
  ];

  return scheduleItems.flatMap((item) => {
    const itemStart = Math.max(
      timeToMinutes(item.startTime),
      openingMinutes
    );
    const itemEnd = Math.min(timeToMinutes(item.endTime), closingMinutes);

    if (itemEnd <= itemStart) {
      return [];
    }

    const startColumnOffset = Math.floor(
      (itemStart - openingMinutes) / TIMELINE_INCREMENT_MINUTES
    );
    const endColumnOffset = Math.ceil(
      (itemEnd - openingMinutes) / TIMELINE_INCREMENT_MINUTES
    );
    return [
      {
        ...item,
        startSlot: startColumnOffset,
        endSlot: endColumnOffset,
      },
    ];
  });
};

export const getTimelineSlotCount = (slots) =>
  slots.reduce(
    (slotCount, slot) => Math.max(slotCount, slot.endSlot),
    0
  );

export const getTimelineGridColumn = ({ startSlot, endSlot }) =>
  `${startSlot + 1} / ${endSlot + 1}`;
