import { create } from 'zustand';
import { useAppStore } from '../../../store/appStore.js';
import { useAuthStore } from '../../../store/authStore.js';
import { EMPTY_LEDGER_SUMMARY } from '../constants/ledgerStatuses.js';
import {
  deductDamageCharges,
  forceCancelLedgerBooking,
  getAmenityLedger,
  processDepositRefund,
} from '../services/amenityLedgerService.js';
import { useAmenityBookingsStore } from './useAmenityBookingsStore.js';

const getErrorMessage = (error) =>
  error instanceof Error
    ? error.message
    : 'Unable to update the financial transaction.';

const getCurrentAdminId = () =>
  useAuthStore.getState().currentUser?.id ?? 'admin';

export const useAmenityLedgerStore = create((set) => ({
  transactions: [],
  summary: { ...EMPTY_LEDGER_SUMMARY },
  ledgerAmenityId: null,
  isLoading: false,
  isSubmitting: false,
  error: null,
  actionError: null,
  selectedTransaction: null,

  fetchLedger: async (amenityId) => {
    set({
      transactions: [],
      summary: { ...EMPTY_LEDGER_SUMMARY },
      ledgerAmenityId: amenityId,
      isLoading: true,
      error: null,
      actionError: null,
      selectedTransaction: null,
    });

    try {
      const ledger = await getAmenityLedger(amenityId);
      set((state) =>
        state.ledgerAmenityId === amenityId
          ? {
              transactions: ledger.transactions,
              summary: ledger.summary,
              isLoading: false,
            }
          : state
      );
      return ledger;
    } catch (error) {
      set((state) =>
        state.ledgerAmenityId === amenityId
          ? {
              transactions: [],
              summary: { ...EMPTY_LEDGER_SUMMARY },
              isLoading: false,
              error: getErrorMessage(error),
            }
          : state
      );
      return null;
    }
  },

  selectTransaction: (transaction) =>
    set({ selectedTransaction: transaction, actionError: null }),

  clearSelectedTransaction: () => set({ selectedTransaction: null }),

  clearActionError: () => set({ actionError: null }),

  processRefund: async (transactionId, refundData) => {
    set({ isSubmitting: true, actionError: null });

    try {
      const result = await processDepositRefund(transactionId, {
        ...refundData,
        processedBy: getCurrentAdminId(),
      });
      set((state) => ({
        transactions: result.ledger.transactions,
        summary: result.ledger.summary,
        selectedTransaction:
          state.selectedTransaction?.id === result.transaction.id
            ? result.transaction
            : state.selectedTransaction,
        isSubmitting: false,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast('Security deposit refunded', 'success');
      appStore.addActivity(
        `Admin refunded the deposit for ${result.transaction.bookingId}`,
        'general'
      );
      return result.transaction;
    } catch (error) {
      set({ isSubmitting: false, actionError: getErrorMessage(error) });
      return null;
    }
  },

  deductDamage: async (transactionId, damageData) => {
    set({ isSubmitting: true, actionError: null });

    try {
      const result = await deductDamageCharges(transactionId, {
        ...damageData,
        processedBy: getCurrentAdminId(),
      });
      set((state) => ({
        transactions: result.ledger.transactions,
        summary: result.ledger.summary,
        selectedTransaction:
          state.selectedTransaction?.id === result.transaction.id
            ? result.transaction
            : state.selectedTransaction,
        isSubmitting: false,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast('Damage charges deducted', 'success');
      appStore.addActivity(
        `Admin recorded damage charges for ${result.transaction.bookingId}`,
        'general'
      );
      return result.transaction;
    } catch (error) {
      set({ isSubmitting: false, actionError: getErrorMessage(error) });
      return null;
    }
  },

  forceCancel: async (transactionId, cancellationData) => {
    set({ isSubmitting: true, actionError: null });

    try {
      const result = await forceCancelLedgerBooking(transactionId, {
        ...cancellationData,
        cancelledBy: getCurrentAdminId(),
      });
      useAmenityBookingsStore
        .getState()
        .syncForceCancelledBooking(result.booking);
      set((state) => ({
        transactions: result.ledger.transactions,
        summary: result.ledger.summary,
        selectedTransaction:
          state.selectedTransaction?.id === result.transaction.id
            ? result.transaction
            : state.selectedTransaction,
        isSubmitting: false,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast('Booking force cancelled', 'success');
      appStore.addActivity(
        `Admin force cancelled ${result.transaction.bookingId}`,
        'general'
      );
      return result.transaction;
    } catch (error) {
      set({ isSubmitting: false, actionError: getErrorMessage(error) });
      return null;
    }
  },
}));
