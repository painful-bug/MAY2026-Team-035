import { BOOKING_STATUS } from '../constants/bookingStatuses.js';
import {
  EMPTY_LEDGER_SUMMARY,
  LEDGER_ACTION,
  PAYMENT_STATUS,
} from '../constants/ledgerStatuses.js';

const cloneEntries = (entries) =>
  Array.isArray(entries) ? entries.map((entry) => ({ ...entry })) : [];

const getRemainingRefund = (transaction) => {
  if (transaction.remainingRefund != null) {
    return Math.max(Number(transaction.remainingRefund), 0);
  }

  return Math.max(
    Number(transaction.depositPaid || 0) -
      Number(transaction.damageAmount || 0) -
      Number(transaction.refundAmount || 0),
    0
  );
};

const getAvailableActions = (transaction) => {
  const actions = [LEDGER_ACTION.VIEW];
  const isFinanciallyClosed =
    transaction.paymentStatus === PAYMENT_STATUS.REFUNDED ||
    transaction.paymentStatus === PAYMENT_STATUS.CANCELLED;

  if (
    transaction.remainingRefund > 0 &&
    !isFinanciallyClosed &&
    [BOOKING_STATUS.COMPLETED, BOOKING_STATUS.CANCELLED].includes(
      transaction.bookingStatus
    )
  ) {
    actions.push(LEDGER_ACTION.REFUND, LEDGER_ACTION.DAMAGE);
  }

  if (
    [BOOKING_STATUS.APPROVED, BOOKING_STATUS.CONFIRMED].includes(
      transaction.bookingStatus
    ) &&
    transaction.bookingDate > new Date().toISOString().split('T')[0] &&
    !transaction.forceCancelled
  ) {
    actions.push(LEDGER_ACTION.FORCE_CANCEL);
  }

  return actions;
};

const getInitialAuditTrail = (transaction) => {
  const entries = cloneEntries(transaction.auditTrail);
  const hasApprovalState = [
    BOOKING_STATUS.APPROVED,
    BOOKING_STATUS.CONFIRMED,
    BOOKING_STATUS.COMPLETED,
    BOOKING_STATUS.CANCELLED,
  ].includes(transaction.bookingStatus);

  if (!entries.some((entry) => entry.type === 'created')) {
    entries.unshift({
      id: `audit-created-${transaction.id}`,
      type: 'created',
      label: 'Created',
      timestamp: transaction.createdAt,
      actor: null,
    });
  }

  if (
    hasApprovalState &&
    !entries.some((entry) => entry.type === 'approved')
  ) {
    entries.push({
      id: `audit-approved-${transaction.id}`,
      type: 'approved',
      label: 'Approved',
      timestamp: transaction.approvedAt ?? transaction.createdAt,
      actor: null,
    });
  }

  if (
    transaction.bookingStatus === BOOKING_STATUS.CANCELLED &&
    !entries.some((entry) => entry.type === 'cancelled')
  ) {
    entries.push({
      id: `audit-cancelled-${transaction.id}`,
      type: 'cancelled',
      label: 'Cancelled',
      timestamp:
        transaction.forceCancelledAt ??
        transaction.cancelledAt ??
        transaction.updatedAt,
      actor: transaction.forceCancelledBy ?? null,
    });
  }

  return entries.sort((first, second) =>
    first.timestamp.localeCompare(second.timestamp)
  );
};

const getInitialCancellationHistory = (transaction) => {
  const entries = cloneEntries(transaction.cancellationHistory);

  if (
    transaction.bookingStatus === BOOKING_STATUS.CANCELLED &&
    entries.length === 0
  ) {
    entries.push({
      id: `cancellation-initial-${transaction.id}`,
      reason: transaction.forceCancelReason ?? 'Booking cancelled',
      cancelledBy: transaction.forceCancelledBy ?? null,
      createdAt:
        transaction.forceCancelledAt ??
        transaction.cancelledAt ??
        transaction.updatedAt,
    });
  }

  return entries;
};

export const normalizeLedgerTransaction = (transaction) => {
  const normalized = {
    ...transaction,
    refundHistory: cloneEntries(transaction.refundHistory),
    damageHistory: cloneEntries(transaction.damageHistory),
    cancellationHistory: getInitialCancellationHistory(transaction),
    damageAmount: Number(transaction.damageAmount || 0),
    refundAmount: Number(transaction.refundAmount || 0),
    remainingRefund: getRemainingRefund(transaction),
    totalAmount:
      Number(transaction.bookingCharges || 0) +
      Number(transaction.additionalCharges || 0),
    outstandingDeposit: Math.max(
      Number(transaction.depositAmount || 0) -
        Number(transaction.depositPaid || 0),
      0
    ),
    auditTrail: getInitialAuditTrail(transaction),
  };

  return {
    ...normalized,
    availableActions: getAvailableActions(normalized),
  };
};

export const calculateLedgerSummary = (transactions) =>
  transactions.reduce(
    (summary, transaction) => ({
      totalBookings: summary.totalBookings + 1,
      totalRevenue:
        summary.totalRevenue + Number(transaction.amountPaid || 0),
      pendingDeposits:
        summary.pendingDeposits + transaction.outstandingDeposit,
      refundPending:
        summary.refundPending +
        (transaction.paymentStatus === PAYMENT_STATUS.REFUND_PENDING ? 1 : 0),
      refundCompleted:
        summary.refundCompleted + Number(transaction.refundAmount || 0),
      damageDeductions:
        summary.damageDeductions + Number(transaction.damageAmount || 0),
      outstandingRefunds:
        summary.outstandingRefunds +
        (transaction.paymentStatus === PAYMENT_STATUS.REFUND_PENDING
          ? transaction.remainingRefund
          : 0),
      completedTransactions:
        summary.completedTransactions +
        (transaction.bookingStatus === BOOKING_STATUS.COMPLETED ? 1 : 0),
    }),
    { ...EMPTY_LEDGER_SUMMARY }
  );
