import { genId } from '../../../lib/ids.js';
import { BOOKING_STATUS } from '../constants/bookingStatuses.js';
import {
  LEDGER_ACTION,
  PAYMENT_STATUS,
} from '../constants/ledgerStatuses.js';
import {
  calculateLedgerSummary,
  normalizeLedgerTransaction,
} from '../utils/amenityLedgerModel.js';
import { forceCancelAmenityBooking } from './amenityBookingsService.js';

// Ledger actions are rendered from the server-backed booking data. Financial
// records without a database row must never be invented in browser storage.
let transactionCache = [];

const getAllTransactions = () => transactionCache.map((transaction) => ({ ...transaction }));

const getLedgerResult = (amenityId) => {
  const transactions = getAllTransactions()
    .filter((transaction) => transaction.amenityId === amenityId)
    .map(normalizeLedgerTransaction)
    .sort((firstTransaction, secondTransaction) =>
      secondTransaction.bookingDate.localeCompare(
        firstTransaction.bookingDate
      )
    );

  return {
    transactions,
    summary: calculateLedgerSummary(transactions),
  };
};

const getTransactionOrThrow = (transactionId) => {
  const transactions = getAllTransactions();
  const transaction = transactions.find((record) => record.id === transactionId);

  if (!transaction) {
    throw new Error('Financial transaction could not be found.');
  }

  return { transactions, transaction };
};

const saveTransaction = (transactions, updatedTransaction) => {
  transactionCache = transactions.map((transaction) =>
    transaction.id === updatedTransaction.id ? updatedTransaction : transaction
  );
  const ledger = getLedgerResult(updatedTransaction.amenityId);

  return {
    transaction: ledger.transactions.find(
      (transaction) => transaction.id === updatedTransaction.id
    ),
    ledger,
  };
};

export const getAmenityLedger = async (amenityId) =>
  getLedgerResult(amenityId);

export const getAllAmenityLedgerTransactions = async () =>
  getAllTransactions()
    .map(normalizeLedgerTransaction)
    .sort((firstTransaction, secondTransaction) =>
      secondTransaction.bookingDate.localeCompare(
        firstTransaction.bookingDate
      )
    );

export const processDepositRefund = async (transactionId, refundData) => {
  const { transactions, transaction } = getTransactionOrThrow(transactionId);
  const normalized = normalizeLedgerTransaction(transaction);

  if (!normalized.availableActions.includes(LEDGER_ACTION.REFUND)) {
    throw new Error('This deposit is no longer eligible for a refund.');
  }

  if (!refundData.processedBy) {
    throw new Error('The processing administrator could not be identified.');
  }

  const timestamp = new Date().toISOString();
  const refundAmount = normalized.remainingRefund;
  const refundEntry = {
    id: genId('refund'),
    amount: refundAmount,
    reason: refundData.reason?.trim() || null,
    processedBy: refundData.processedBy,
    createdAt: timestamp,
  };
  const updatedTransaction = {
    ...transaction,
    refundAmount: normalized.refundAmount + refundAmount,
    refundDate: timestamp,
    refundReason: refundEntry.reason,
    refundProcessedBy: refundData.processedBy,
    remainingRefund: 0,
    paymentStatus: PAYMENT_STATUS.REFUNDED,
    refundHistory: [...normalized.refundHistory, refundEntry],
    auditTrail: [
      ...normalized.auditTrail,
      {
        id: genId('audit'),
        type: 'refunded',
        label: 'Refunded',
        timestamp,
        actor: refundData.processedBy,
        amount: refundAmount,
      },
    ],
    updatedAt: timestamp,
  };

  return saveTransaction(transactions, updatedTransaction);
};

export const deductDamageCharges = async (transactionId, damageData) => {
  const { transactions, transaction } = getTransactionOrThrow(transactionId);
  const normalized = normalizeLedgerTransaction(transaction);
  const damageAmount = Number(damageData.amount);

  if (!normalized.availableActions.includes(LEDGER_ACTION.DAMAGE)) {
    throw new Error('This deposit is no longer eligible for damage deductions.');
  }

  if (!Number.isFinite(damageAmount) || damageAmount <= 0) {
    throw new Error('Enter a valid damage amount.');
  }

  if (damageAmount > normalized.remainingRefund) {
    throw new Error('Damage deduction cannot exceed the refundable amount.');
  }

  if (!damageData.reason?.trim() || !damageData.processedBy) {
    throw new Error('A damage reason and administrator are required.');
  }

  const timestamp = new Date().toISOString();
  const remainingRefund = normalized.remainingRefund - damageAmount;
  const damageEntry = {
    id: genId('damage'),
    amount: damageAmount,
    reason: damageData.reason.trim(),
    notes: damageData.notes?.trim() || null,
    processedBy: damageData.processedBy,
    createdAt: timestamp,
  };
  const updatedTransaction = {
    ...transaction,
    damageAmount: normalized.damageAmount + damageAmount,
    damageReason: damageEntry.reason,
    remainingRefund,
    paymentStatus:
      remainingRefund > 0
        ? PAYMENT_STATUS.REFUND_PENDING
        : PAYMENT_STATUS.PAID,
    damageHistory: [...normalized.damageHistory, damageEntry],
    auditTrail: [
      ...normalized.auditTrail,
      {
        id: genId('audit'),
        type: 'damage',
        label: 'Damage deduction recorded',
        timestamp,
        actor: damageData.processedBy,
        amount: damageAmount,
      },
    ],
    internalNotes:
      damageEntry.notes ?? transaction.internalNotes ?? null,
    updatedAt: timestamp,
  };

  return saveTransaction(transactions, updatedTransaction);
};

export const forceCancelLedgerBooking = async (
  transactionId,
  cancellationData
) => {
  const { transactions, transaction } = getTransactionOrThrow(transactionId);
  const normalized = normalizeLedgerTransaction(transaction);

  if (!normalized.availableActions.includes(LEDGER_ACTION.FORCE_CANCEL)) {
    throw new Error('This booking is no longer eligible for force cancellation.');
  }

  if (!cancellationData.reason || !cancellationData.cancelledBy) {
    throw new Error('A cancellation reason and administrator are required.');
  }

  const booking = await forceCancelAmenityBooking(transaction.bookingId, {
    reason: cancellationData.reason,
    cancelledBy: cancellationData.cancelledBy,
  });
  const timestamp = booking.forceCancelledAt;
  const cancellationEntry = {
    id: genId('cancellation'),
    reason: cancellationData.reason,
    cancelledBy: cancellationData.cancelledBy,
    createdAt: timestamp,
  };
  const updatedTransaction = {
    ...transaction,
    bookingStatus: BOOKING_STATUS.CANCELLED,
    paymentStatus: PAYMENT_STATUS.REFUND_PENDING,
    remainingRefund: normalized.remainingRefund,
    forceCancelled: true,
    forceCancelReason: cancellationData.reason,
    forceCancelReasonCode: cancellationData.reasonCode,
    forceCancelledBy: cancellationData.cancelledBy,
    forceCancelledAt: timestamp,
    cancellationHistory: [
      ...normalized.cancellationHistory,
      cancellationEntry,
    ],
    auditTrail: [
      ...normalized.auditTrail,
      {
        id: genId('audit'),
        type: 'cancelled',
        label: 'Cancelled',
        timestamp,
        actor: cancellationData.cancelledBy,
        details: cancellationData.reason,
      },
    ],
    updatedAt: timestamp,
  };
  const result = saveTransaction(transactions, updatedTransaction);

  return { ...result, booking };
};
