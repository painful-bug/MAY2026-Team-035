// The booking lifecycle's vocabulary, as it crosses the wire.
//
// Every `status` the API sends is a LOWERCASE MACHINE VALUE — one of
// `pending | approved | rejected | cancelled | completed | no_show` — and the
// display wording is the frontend's job (issue #48, contract §C). The API used
// to send a Title-case display string from the reporting view beside the
// stored one, so two spellings of the same status crossed the wire and the
// screens picked whichever they happened to read; that is over.
//
// `confirmed` and `blocked` are kept as READ-ONLY spellings: no endpoint emits
// them any more, but the reports filter's fixed option list and older cached
// rows still can, and a badge must not go blank when it meets one.
export const BOOKING_STATUS = Object.freeze({
  PENDING: 'pending',
  APPROVED: 'approved',
  CONFIRMED: 'confirmed',
  CANCELLED: 'cancelled',
  REJECTED: 'rejected',
  BLOCKED: 'blocked',
  COMPLETED: 'completed',
  NO_SHOW: 'no_show',
});

export const BOOKING_STATUS_LABELS = Object.freeze({
  [BOOKING_STATUS.PENDING]: 'Pending Approval',
  [BOOKING_STATUS.APPROVED]: 'Approved',
  [BOOKING_STATUS.CONFIRMED]: 'Confirmed',
  [BOOKING_STATUS.CANCELLED]: 'Cancelled',
  [BOOKING_STATUS.REJECTED]: 'Rejected',
  [BOOKING_STATUS.BLOCKED]: 'Blocked',
  [BOOKING_STATUS.COMPLETED]: 'Completed',
  [BOOKING_STATUS.NO_SHOW]: 'No Show',
});

/**
 * The machine value for a status however it is spelled — `no_show`, `No Show`
 * and `NO-SHOW` are the same status, and only the first is what the rest of
 * this frontend compares against.
 */
export const normalizeBookingStatus = (status) =>
  String(status ?? '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');

/**
 * The one place display casing is decided. Unknown statuses are humanised
 * rather than dropped, so a status this build has never heard of reads as
 * "Some Status" instead of a raw enum or a blank cell.
 */
export const bookingStatusLabel = (status) => {
  const normalized = normalizeBookingStatus(status);

  if (!normalized) {
    return '';
  }

  return (
    BOOKING_STATUS_LABELS[normalized] ??
    normalized
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  );
};

export const isCancelledBooking = (booking) =>
  normalizeBookingStatus(booking.status) === BOOKING_STATUS.CANCELLED;

export const APPROVAL_FILTERS = [
  { value: BOOKING_STATUS.PENDING, label: 'Pending' },
  { value: BOOKING_STATUS.APPROVED, label: 'Approved' },
  { value: BOOKING_STATUS.REJECTED, label: 'Rejected' },
  { value: BOOKING_STATUS.CANCELLED, label: 'Cancelled' },
];
