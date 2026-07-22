export const BOOKING_TIMELINE_STATE = Object.freeze({
  AVAILABLE: 'available',
  BOOKED: 'booked',
  CLEANING_BUFFER: 'buffer',
  BLOCKED: 'blocked',
});

export const BOOKING_TIMELINE_STATE_META = Object.freeze({
  [BOOKING_TIMELINE_STATE.AVAILABLE]: {
    label: 'Available',
    badgeClasses: 'border-emerald-100 bg-emerald-50 text-emerald-700',
    blockClasses: 'border-emerald-100 bg-emerald-50/70 text-emerald-700',
  },
  [BOOKING_TIMELINE_STATE.BOOKED]: {
    label: 'Booked',
    badgeClasses: 'border-indigo-100 bg-indigo-50 text-indigo-700',
    blockClasses: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  },
  [BOOKING_TIMELINE_STATE.CLEANING_BUFFER]: {
    label: 'Cleaning Buffer',
    badgeClasses: 'border-amber-100 bg-amber-50 text-amber-700',
    blockClasses: 'border-amber-200 bg-amber-50 text-amber-700',
  },
  [BOOKING_TIMELINE_STATE.BLOCKED]: {
    label: 'Blocked',
    badgeClasses: 'border-rose-100 bg-rose-50 text-rose-700',
    blockClasses: 'border-rose-200 bg-rose-50 text-rose-700',
  },
});

export const BOOKING_TIMELINE_LEGEND_STATES = [
  BOOKING_TIMELINE_STATE.AVAILABLE,
  BOOKING_TIMELINE_STATE.BOOKED,
  BOOKING_TIMELINE_STATE.CLEANING_BUFFER,
  BOOKING_TIMELINE_STATE.BLOCKED,
];
