import React, { useEffect, useState } from 'react';
import { ReceiptText } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { amenitiesApi } from '../amenitiesApi.js';
import AddChargeModal from '../components/Ledger/AddChargeModal.jsx';
import DamageDeductionModal from '../components/Ledger/DamageDeductionModal.jsx';
import FinancialSummary from '../components/Ledger/FinancialSummary.jsx';
import ForceCancelDialog from '../components/Ledger/ForceCancelDialog.jsx';
import LedgerFilters from '../components/Ledger/LedgerFilters.jsx';
import LedgerTable from '../components/Ledger/LedgerTable.jsx';
import RecordPaymentModal from '../components/Ledger/RecordPaymentModal.jsx';
import RefundModal from '../components/Ledger/RefundModal.jsx';
import TransactionDetailsPanel from '../components/Ledger/TransactionDetailsPanel.jsx';
import {
  EMPTY_LEDGER_SUMMARY,
  LEDGER_ACTION,
} from '../constants/ledgerStatuses.js';

// The ledger tab, over `GET /amenities/{id}/ledger` and its five writes.
//
// **Nothing on this screen computes money any more.** `remainingRefund`,
// `totalAmount`, `outstandingDeposit`, `paymentStatus` and `availableActions`
// were all derived in the browser by `amenityLedgerModel.js`; every one of them
// now arrives from Postgres, computed from the charges and the append-only
// event stream. That file is gone, and with it the possibility of a figure on
// this page disagreeing with the figure the write endpoint enforces against.
//
// The eight summary cards are their own read rather than a reduce over the
// table, for the same reason: `GET .../ledger/summary` aggregates every
// transaction for the amenity, so the totals do not change when the table
// pages. A client-side reduce would have described the current page and called
// it "Total Revenue".
//
// Filtering and search go to the server (`paymentStatus`, `q`) instead of
// filtering an array that is only ever one page deep.

const PAGE_SIZE = 50;

export default function AmenityLedgerPage() {
  const { amenity } = useOutletContext();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [activeAction, setActiveAction] = useState(null);
  const [selectedTransaction, setSelectedTransaction] = useState(null);

  // The search is the server's `q`, so it is debounced: a request per keystroke
  // against a query that joins charges and financial events is a lot of work to
  // throw away on the next letter.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const ledger = useQuery({
    queryKey: [
      'amenities',
      amenity.id,
      'ledger',
      { paymentStatus: activeFilter, q: debouncedSearch },
    ],
    queryFn: () =>
      amenitiesApi.ledger(amenity.id, {
        paymentStatus: activeFilter,
        q: debouncedSearch || undefined,
        pageSize: PAGE_SIZE,
      }),
    placeholderData: (previous) => previous,
  });

  const summary = useQuery({
    queryKey: ['amenities', amenity.id, 'ledger', 'summary'],
    queryFn: () => amenitiesApi.ledgerSummary(amenity.id),
  });

  const transactions = ledger.data?.items || [];

  // Every write returns the recomputed transaction, so the panel behind the
  // modal is refreshed from the response rather than from what the form sent.
  const invalidate = (updated) => {
    queryClient.invalidateQueries({ queryKey: ['amenities', amenity.id] });
    setSelectedTransaction((current) =>
      current && updated && current.id === updated.id ? updated : current
    );
  };

  const refund = useMutation({
    mutationFn: ({ transactionId, payload }) =>
      amenitiesApi.refundDeposit(transactionId, payload),
    onSuccess: invalidate,
  });
  const damage = useMutation({
    mutationFn: ({ transactionId, payload }) =>
      amenitiesApi.deductDamage(transactionId, payload),
    onSuccess: invalidate,
  });
  const payment = useMutation({
    mutationFn: ({ transactionId, payload }) =>
      amenitiesApi.recordPayment(transactionId, payload),
    onSuccess: invalidate,
  });
  const charge = useMutation({
    mutationFn: ({ transactionId, payload }) =>
      amenitiesApi.addCharge(transactionId, payload),
    onSuccess: invalidate,
  });
  const forceCancel = useMutation({
    mutationFn: ({ transactionId, payload }) =>
      amenitiesApi.forceCancel(transactionId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['amenities', amenity.id] });
      setSelectedTransaction(null);
    },
  });

  // The modals close on a truthy result and stay open on a falsy one, which is
  // how they already reported failure. `mutateAsync` throws, so the rejection
  // is turned back into `null` here and the message is read off the mutation.
  const submit = (mutation) => async (transactionId, payload) => {
    try {
      return await mutation.mutateAsync({ transactionId, payload });
    } catch {
      return null;
    }
  };

  const closeAction = () => {
    if (
      refund.isPending ||
      damage.isPending ||
      payment.isPending ||
      charge.isPending ||
      forceCancel.isPending
    ) {
      return;
    }

    setActiveAction(null);
  };

  const handleTransactionAction = (action, transaction) => {
    if (action === LEDGER_ACTION.VIEW) {
      setSelectedTransaction(transaction);
      return;
    }

    [refund, damage, payment, charge, forceCancel].forEach((mutation) =>
      mutation.reset()
    );
    setActiveAction({ action, transaction });
  };

  // A row the table has just replaced is a row whose modal is describing the
  // previous version of it. Re-reading it from the refreshed page keeps the
  // "Refundable Amount" in the dialog the same number the endpoint will use.
  const actionTransaction = activeAction
    ? transactions.find((row) => row.id === activeAction.transaction.id) ||
      activeAction.transaction
    : null;

  useEffect(() => {
    setActiveAction(null);
    setSelectedTransaction(null);
  }, [amenity.id]);

  return (
    <>
      <div className="space-y-5">
        <FinancialSummary summary={summary.data || EMPTY_LEDGER_SUMMARY} />

        {summary.error && (
          <p
            role="status"
            className="rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-xs font-semibold text-amber-700"
          >
            The summary totals could not be loaded ({summary.error.message}). The
            transactions below are unaffected.
          </p>
        )}

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
            counts={{ [activeFilter]: ledger.data?.total }}
          />

          {ledger.isPending ? (
            <div className="px-6 py-14 text-center text-xs font-semibold text-slate-400">
              Loading financial transactions...
            </div>
          ) : ledger.error ? (
            <div className="px-6 py-14 text-center">
              <p role="alert" className="text-xs font-bold text-rose-700">
                {ledger.error.message}
              </p>
              <button
                type="button"
                onClick={() => ledger.refetch()}
                className="mt-3 rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
              >
                Try again
              </button>
            </div>
          ) : (
            <>
              <LedgerTable
                transactions={transactions}
                onSelect={setSelectedTransaction}
                onAction={handleTransactionAction}
                emptyMessage={
                  searchQuery.trim() || activeFilter !== 'all'
                    ? 'No transactions match this view.'
                    : 'No financial transactions available.'
                }
              />
              {ledger.data?.hasMore && (
                <p className="border-t border-slate-50 px-6 py-3 text-[11px] font-semibold text-slate-400">
                  Showing the first {PAGE_SIZE} of {ledger.data.total}{' '}
                  transactions. Narrow the search or the status filter to reach
                  the rest — the summary cards above already count all of them.
                </p>
              )}
            </>
          )}
        </section>
      </div>

      {selectedTransaction && (
        <TransactionDetailsPanel
          transaction={selectedTransaction}
          amenityName={amenity.name}
          onClose={() => setSelectedTransaction(null)}
        />
      )}

      {activeAction?.action === LEDGER_ACTION.REFUND && (
        <RefundModal
          transaction={actionTransaction}
          isSubmitting={refund.isPending}
          submissionError={refund.error?.message}
          onClose={closeAction}
          onProcess={submit(refund)}
        />
      )}

      {activeAction?.action === LEDGER_ACTION.DAMAGE && (
        <DamageDeductionModal
          transaction={actionTransaction}
          isSubmitting={damage.isPending}
          submissionError={damage.error?.message}
          onClose={closeAction}
          onDeduct={submit(damage)}
        />
      )}

      {activeAction?.action === LEDGER_ACTION.PAYMENT && (
        <RecordPaymentModal
          transaction={actionTransaction}
          isSubmitting={payment.isPending}
          submissionError={payment.error?.message}
          onClose={closeAction}
          onRecord={submit(payment)}
        />
      )}

      {activeAction?.action === LEDGER_ACTION.CHARGE && (
        <AddChargeModal
          transaction={actionTransaction}
          isSubmitting={charge.isPending}
          submissionError={charge.error?.message}
          onClose={closeAction}
          onAdd={submit(charge)}
        />
      )}

      {activeAction?.action === LEDGER_ACTION.FORCE_CANCEL && (
        <ForceCancelDialog
          transaction={actionTransaction}
          isSubmitting={forceCancel.isPending}
          submissionError={forceCancel.error?.message}
          onClose={closeAction}
          onForceCancel={submit(forceCancel)}
        />
      )}
    </>
  );
}
