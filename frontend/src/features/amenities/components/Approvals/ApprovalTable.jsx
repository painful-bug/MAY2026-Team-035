import React from 'react';
import ApprovalRow from './ApprovalRow.jsx';

const TABLE_COLUMNS = [
  'Resident',
  'Apartment / Flat Number',
  'Booking Date',
  'Time Slot',
  'Booking Type',
  'Requested On',
  'Current Status',
  'Actions',
];

// One row per REQUEST, not per day — `GET /amenities/{id}/approvals` groups the
// series and sends its first day plus `dayCount` and `dates`. Which is why the
// busy row is keyed by `approvingSeriesId`: one decision covers every day of
// the request, so there is no per-day id to spin.
export default function ApprovalTable({
  bookings,
  approvingSeriesId,
  onApprove,
  onReject,
  emptyMessage,
}) {
  if (bookings.length === 0) {
    return (
      <div className="px-6 py-14 text-center">
        <p className="text-sm font-extrabold text-slate-700">
          {emptyMessage}
        </p>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          Booking requests matching this view will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto overscroll-x-contain">
      <table className="w-full min-w-[1120px] border-collapse text-left">
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
          {bookings.map((booking) => (
            <ApprovalRow
              key={booking.bookingSeriesId ?? booking.id}
              booking={booking}
              isApproving={approvingSeriesId === booking.bookingSeriesId}
              onApprove={onApprove}
              onReject={onReject}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
