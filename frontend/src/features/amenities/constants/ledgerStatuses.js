export const PAYMENT_STATUS = Object.freeze({
  PAID: 'paid',
  PENDING: 'pending',
  PARTIALLY_PAID: 'partially_paid',
  REFUND_PENDING: 'refund_pending',
  REFUNDED: 'refunded',
  CANCELLED: 'cancelled',
});

export const PAYMENT_STATUS_LABELS = Object.freeze({
  [PAYMENT_STATUS.PAID]: 'Paid',
  [PAYMENT_STATUS.PENDING]: 'Pending',
  [PAYMENT_STATUS.PARTIALLY_PAID]: 'Partially Paid',
  [PAYMENT_STATUS.REFUND_PENDING]: 'Refund Pending',
  [PAYMENT_STATUS.REFUNDED]: 'Refunded',
  [PAYMENT_STATUS.CANCELLED]: 'Cancelled',
});

export const LEDGER_FILTERS = [
  { value: 'all', label: 'All' },
  { value: PAYMENT_STATUS.PAID, label: 'Paid' },
  { value: PAYMENT_STATUS.PENDING, label: 'Pending' },
  { value: PAYMENT_STATUS.REFUND_PENDING, label: 'Refund Pending' },
  { value: PAYMENT_STATUS.CANCELLED, label: 'Cancelled' },
];

export const EMPTY_LEDGER_SUMMARY = Object.freeze({
  totalBookings: 0,
  totalRevenue: 0,
  pendingDeposits: 0,
  refundPending: 0,
  refundCompleted: 0,
  damageDeductions: 0,
  outstandingRefunds: 0,
  completedTransactions: 0,
});

// The first four are the API's own vocabulary: `LedgerTransaction.availableActions`
// is a server-computed list drawn from exactly these, using the same rules the
// write endpoints enforce.
//
// The last two are not in that list, and their absence is deliberate rather
// than an omission. Adding a charge has no precondition at all — the endpoint
// answers `404` and nothing else — and recording a payment is refused only when
// there is no outstanding charge of the named kind, which the row's own figures
// already say. Neither needed a server flag, so neither got one; the client
// decides whether to offer them from the transaction it is holding. See
// `getLedgerMenuActions`.
export const LEDGER_ACTION = Object.freeze({
  VIEW: 'view',
  REFUND: 'refund',
  DAMAGE: 'damage',
  FORCE_CANCEL: 'force_cancel',
  PAYMENT: 'payment',
  CHARGE: 'charge',
});

/** `chargeType` for `POST /amenity-bookings/{id}/payments` — what the money settles. */
export const PAYMENT_CHARGE_TYPES = [
  { value: 'booking', label: 'Booking Fee' },
  { value: 'deposit', label: 'Security Deposit' },
  { value: 'additional', label: 'Additional Charges' },
  { value: 'late_cancellation', label: 'Late Cancellation Fee' },
];

/** `chargeType` for `POST /amenity-bookings/{id}/charges` — what is being billed. */
export const ADDABLE_CHARGE_TYPES = [
  { value: 'additional', label: 'Additional Charge' },
  { value: 'late_cancellation', label: 'Late Cancellation Fee' },
];

export const FORCE_CANCEL_REASONS = [
  { value: 'emergency-maintenance', label: 'Emergency Maintenance' },
  { value: 'policy-violation', label: 'Policy Violation' },
  { value: 'resident-request', label: 'Resident Request' },
  { value: 'management-decision', label: 'Management Decision' },
  { value: 'other', label: 'Other' },
];
