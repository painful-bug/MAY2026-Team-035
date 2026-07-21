import React from 'react';
import LedgerRow from './LedgerRow.jsx';

const TABLE_COLUMNS = [
  'Booking ID',
  'Resident',
  'Flat',
  'Booking Date',
  'Booking Type',
  'Amount',
  'Deposit',
  'Payment Status',
  'Booking Status',
  'Actions',
];

export default function LedgerTable({
  transactions,
  onSelect,
  onAction,
  emptyMessage = 'No financial transactions available.',
}) {
  if (transactions.length === 0) {
    return (
      <div className="px-6 py-14 text-center">
        <p className="text-sm font-extrabold text-slate-700">
          {emptyMessage}
        </p>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          Booking transactions matching this view will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto overscroll-x-contain">
      <table className="w-full min-w-[1280px] border-collapse text-left">
        <thead className="bg-slate-50">
          <tr>
            {TABLE_COLUMNS.map((column) => (
              <th
                key={column}
                scope="col"
                className="whitespace-nowrap px-4 py-3 text-[10px] font-extrabold uppercase tracking-wider text-slate-400 sm:px-5"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {transactions.map((transaction) => (
            <LedgerRow
              key={transaction.id}
              transaction={transaction}
              onSelect={onSelect}
              onAction={onAction}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
