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

export const LEDGER_ACTION = Object.freeze({
  VIEW: 'view',
  REFUND: 'refund',
  DAMAGE: 'damage',
  FORCE_CANCEL: 'force_cancel',
});

export const FORCE_CANCEL_REASONS = [
  { value: 'emergency-maintenance', label: 'Emergency Maintenance' },
  { value: 'policy-violation', label: 'Policy Violation' },
  { value: 'resident-request', label: 'Resident Request' },
  { value: 'management-decision', label: 'Management Decision' },
  { value: 'other', label: 'Other' },
];
