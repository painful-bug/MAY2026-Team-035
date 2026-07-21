import React, { useEffect, useMemo, useState } from 'react';
import { ReceiptText } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';
import DamageDeductionModal from '../components/Ledger/DamageDeductionModal.jsx';
import FinancialSummary from '../components/Ledger/FinancialSummary.jsx';
import ForceCancelDialog from '../components/Ledger/ForceCancelDialog.jsx';
import LedgerFilters from '../components/Ledger/LedgerFilters.jsx';
import LedgerTable from '../components/Ledger/LedgerTable.jsx';
import RefundModal from '../components/Ledger/RefundModal.jsx';
import TransactionDetailsPanel from '../components/Ledger/TransactionDetailsPanel.jsx';
import { LEDGER_ACTION } from '../constants/ledgerStatuses.js';
import { useAmenityLedgerStore } from '../store/useAmenityLedgerStore.js';

export default function AmenityLedgerPage() {
  const { amenity } = useOutletContext();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [activeAction, setActiveAction] = useState(null);
  const transactions = useAmenityLedgerStore(
    (state) => state.transactions
  );
  const summary = useAmenityLedgerStore((state) => state.summary);
  const ledgerAmenityId = useAmenityLedgerStore(
    (state) => state.ledgerAmenityId
  );
  const isLoading = useAmenityLedgerStore((state) => state.isLoading);
  const error = useAmenityLedgerStore((state) => state.error);
  const actionError = useAmenityLedgerStore((state) => state.actionError);
  const isSubmitting = useAmenityLedgerStore(
    (state) => state.isSubmitting
  );
  const selectedTransaction = useAmenityLedgerStore(
    (state) => state.selectedTransaction
  );
  const fetchLedger = useAmenityLedgerStore((state) => state.fetchLedger);
  const selectTransaction = useAmenityLedgerStore(
    (state) => state.selectTransaction
  );
  const clearSelectedTransaction = useAmenityLedgerStore(
    (state) => state.clearSelectedTransaction
  );
  const clearActionError = useAmenityLedgerStore(
    (state) => state.clearActionError
  );
  const processRefund = useAmenityLedgerStore(
    (state) => state.processRefund
  );
  const deductDamage = useAmenityLedgerStore(
    (state) => state.deductDamage
  );
  const forceCancel = useAmenityLedgerStore((state) => state.forceCancel);

  useEffect(() => {
    fetchLedger(amenity.id);
  }, [amenity.id, fetchLedger]);

  const counts = useMemo(
    () =>
      transactions.reduce(
        (statusCounts, transaction) => {
          statusCounts.all += 1;
          statusCounts[transaction.paymentStatus] =
            (statusCounts[transaction.paymentStatus] ?? 0) + 1;
          return statusCounts;
        },
        { all: 0 }
      ),
    [transactions]
  );

  const filteredTransactions = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();

    return transactions.filter((transaction) => {
      if (
        activeFilter !== 'all' &&
        transaction.paymentStatus !== activeFilter
      ) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      return [
        transaction.residentName,
        transaction.residentFlat,
        transaction.bookingId,
      ].some((value) => value?.toLowerCase().includes(normalizedQuery));
    });
  }, [activeFilter, searchQuery, transactions]);

  const isLedgerLoading = ledgerAmenityId !== amenity.id || isLoading;

  const handleTransactionAction = (action, transaction) => {
    if (action === LEDGER_ACTION.VIEW) {
      selectTransaction(transaction);
      return;
    }

    clearActionError();
    setActiveAction({ action, transaction });
  };

  const closeAction = () => {
    if (isSubmitting) {
      return;
    }

    clearActionError();
    setActiveAction(null);
  };

  return (
    <>
      <div className="space-y-5">
        <FinancialSummary summary={summary} />

        <section className="overflow-hidden rounded-2xl border border-slate-100 bg-white">
          <div className="flex items-start gap-3 p-5 sm:p-6">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
              <ReceiptText className="h-5 w-5" />
            </span>
            <div>
              <p className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-600">
                Financial history
              </p>
              <h2 className="mt-0.5 text-base font-extrabold text-slate-800">
                Booking transactions
              </h2>
              <p className="mt-1 text-xs font-semibold text-slate-400">
                Financial records for {amenity.name}.
              </p>
            </div>
          </div>

          <LedgerFilters
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            activeFilter={activeFilter}
            onFilterChange={setActiveFilter}
            counts={counts}
          />

          {error && (
            <div
              role="alert"
              className="mx-4 mt-4 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-700 sm:mx-5"
            >
              {error}
            </div>
          )}

          {isLedgerLoading ? (
            <div className="px-6 py-14 text-center text-xs font-semibold text-slate-400">
              Loading financial transactions...
            </div>
          ) : (
            <LedgerTable
              transactions={filteredTransactions}
              onSelect={selectTransaction}
              onAction={handleTransactionAction}
            />
          )}
        </section>
      </div>

      {selectedTransaction && (
        <TransactionDetailsPanel
          transaction={selectedTransaction}
          amenityName={amenity.name}
          onClose={clearSelectedTransaction}
        />
      )}

      {activeAction?.action === LEDGER_ACTION.REFUND && (
        <RefundModal
          transaction={activeAction.transaction}
          isSubmitting={isSubmitting}
          submissionError={actionError}
          onClose={closeAction}
          onProcess={processRefund}
        />
      )}

      {activeAction?.action === LEDGER_ACTION.DAMAGE && (
        <DamageDeductionModal
          transaction={activeAction.transaction}
          isSubmitting={isSubmitting}
          submissionError={actionError}
          onClose={closeAction}
          onDeduct={deductDamage}
        />
      )}

      {activeAction?.action === LEDGER_ACTION.FORCE_CANCEL && (
        <ForceCancelDialog
          transaction={activeAction.transaction}
          isSubmitting={isSubmitting}
          submissionError={actionError}
          onClose={closeAction}
          onForceCancel={forceCancel}
        />
      )}
    </>
  );
}
