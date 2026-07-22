import React from 'react';
import { getBookingTypeLabel } from '../../constants/bookingFormOptions.js';
import {
  formatLedgerCurrency,
  formatLedgerDate,
} from '../../utils/amenityLedger.js';
import BookingStatusBadge from '../booking/BookingStatusBadge.jsx';
import LedgerActionsMenu from './LedgerActionsMenu.jsx';
import PaymentStatusBadge from './PaymentStatusBadge.jsx';

export default function LedgerRow({ transaction, onSelect, onAction }) {
  const handleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelect(transaction);
    }
  };

  return (
    <tr
      tabIndex={0}
      onClick={() => onSelect(transaction)}
      onKeyDown={handleKeyDown}
      className="cursor-pointer border-b border-slate-50 transition-colors last:border-b-0 hover:bg-slate-50/70 focus:bg-slate-50 focus:outline-none"
    >
      <td className="whitespace-nowrap px-4 py-4 text-xs font-extrabold text-indigo-600 sm:px-5">
        {transaction.bookingId}
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-bold text-slate-700 sm:px-5">
        {transaction.residentName}
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-semibold text-slate-500 sm:px-5">
        {transaction.residentFlat || '—'}
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-semibold text-slate-600 sm:px-5">
        {formatLedgerDate(transaction.bookingDate)}
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-semibold text-slate-500 sm:px-5">
        {getBookingTypeLabel(transaction.bookingType)}
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-extrabold text-slate-700 sm:px-5">
        {formatLedgerCurrency(transaction.totalAmount)}
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-semibold text-slate-600 sm:px-5">
        {formatLedgerCurrency(transaction.depositAmount)}
      </td>
      <td className="whitespace-nowrap px-4 py-4 sm:px-5">
        <PaymentStatusBadge status={transaction.paymentStatus} />
      </td>
      <td className="whitespace-nowrap px-4 py-4 sm:px-5">
        <BookingStatusBadge status={transaction.bookingStatus} />
      </td>
      <td className="px-4 py-4 sm:px-5">
        <LedgerActionsMenu transaction={transaction} onAction={onAction} />
      </td>
    </tr>
  );
}
