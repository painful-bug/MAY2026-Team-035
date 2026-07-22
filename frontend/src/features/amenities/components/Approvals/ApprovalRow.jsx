import React from 'react';
import { Check, X } from 'lucide-react';
import { BOOKING_STATUS } from '../../constants/bookingStatuses.js';
import { getBookingTypeLabel } from '../../constants/bookingFormOptions.js';
import { formatTimelineTimeRange } from '../../utils/amenityTimeline.js';
import ApprovalStatusBadge from './ApprovalStatusBadge.jsx';

const formatCurrency = (amount) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount);

const formatBookingDate = (date) =>
  new Date(`${date}T00:00:00`).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

const formatRequestedOn = (timestamp) =>
  new Date(timestamp).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

export default function ApprovalRow({
  booking,
  isApproving,
  onApprove,
  onReject,
}) {
  const isPending = booking.status === BOOKING_STATUS.PENDING;

  return (
    <tr className="border-b border-slate-50 last:border-b-0">
      <td className="px-4 py-4 align-top sm:px-5">
        <div className="min-w-52 space-y-1.5">
          <div>
            <p className="text-xs font-extrabold text-slate-800">
              {booking.residentName}
            </p>
            <p className="mt-0.5 text-[11px] font-semibold text-slate-400">
              {booking.bookingTitle}
            </p>
          </div>
          {booking.outstandingDues > 0 && (
            <span className="inline-flex whitespace-nowrap rounded-full border border-amber-100 bg-amber-50 px-2.5 py-1 text-[10px] font-extrabold text-amber-700">
              Outstanding Dues {formatCurrency(booking.outstandingDues)}
            </span>
          )}
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-bold text-slate-600 sm:px-5">
        {booking.residentFlat || '—'}
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-bold text-slate-600 sm:px-5">
        {formatBookingDate(booking.date)}
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-bold text-slate-600 sm:px-5">
        {formatTimelineTimeRange(booking.startTime, booking.endTime)}
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-semibold text-slate-500 sm:px-5">
        {getBookingTypeLabel(booking.bookingType)}
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-xs font-semibold text-slate-500 sm:px-5">
        {formatRequestedOn(booking.createdAt)}
      </td>
      <td className="whitespace-nowrap px-4 py-4 sm:px-5">
        <ApprovalStatusBadge status={booking.status} />
      </td>
      <td className="px-4 py-4 sm:px-5">
        {isPending ? (
          <div className="flex min-w-max gap-2">
            <button
              type="button"
              disabled={isApproving}
              onClick={() => onApprove(booking.id)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-2 text-[11px] font-bold text-white shadow-md shadow-indigo-100 transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
            >
              <Check className="h-3.5 w-3.5" />
              {isApproving ? 'Approving...' : 'Approve'}
            </button>
            <button
              type="button"
              disabled={isApproving}
              onClick={() => onReject(booking)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-bold text-slate-600 transition-colors hover:border-rose-100 hover:bg-rose-50 hover:text-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <X className="h-3.5 w-3.5" />
              Reject
            </button>
          </div>
        ) : (
          <span className="text-[11px] font-semibold text-slate-400">
            No actions
          </span>
        )}
      </td>
    </tr>
  );
}
