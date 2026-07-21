export const BOOKING_STATUS = Object.freeze({
  PENDING: 'pending',
  APPROVED: 'approved',
  CONFIRMED: 'confirmed',
  CANCELLED: 'cancelled',
  REJECTED: 'rejected',
  BLOCKED: 'blocked',
  COMPLETED: 'completed',
});

export const BOOKING_STATUS_LABELS = Object.freeze({
  [BOOKING_STATUS.PENDING]: 'Pending Approval',
  [BOOKING_STATUS.APPROVED]: 'Approved',
  [BOOKING_STATUS.CONFIRMED]: 'Confirmed',
  [BOOKING_STATUS.CANCELLED]: 'Cancelled',
  [BOOKING_STATUS.REJECTED]: 'Rejected',
  [BOOKING_STATUS.BLOCKED]: 'Blocked',
  [BOOKING_STATUS.COMPLETED]: 'Completed',
});

export const isCancelledBooking = (booking) =>
  booking.status === BOOKING_STATUS.CANCELLED;

export const APPROVAL_FILTERS = [
  { value: BOOKING_STATUS.PENDING, label: 'Pending' },
  { value: BOOKING_STATUS.APPROVED, label: 'Approved' },
  { value: BOOKING_STATUS.REJECTED, label: 'Rejected' },
  { value: BOOKING_STATUS.CANCELLED, label: 'Cancelled' },
];
