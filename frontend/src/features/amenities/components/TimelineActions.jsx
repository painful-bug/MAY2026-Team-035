import React from 'react';
import { CalendarPlus, CalendarX2, ShieldAlert } from 'lucide-react';

// Three verbs, and there used to be a fourth.
//
// Selecting a booking opened an Edit Booking modal that wrote to a browser-side
// array. **The API has no update operation for a booking** — `0016` ships
// create, block, approve, reject, cancel, force-cancel and nothing that moves an
// existing one — so once the timeline reads from the server, Save Changes is a
// button with nowhere to send anything. It is gone rather than disabled, and
// Cancel Booking, which does have an endpoint, is offered in its place. See the
// wiring report; reinstating an edit needs a `PATCH` that does not exist yet.
export default function TimelineActions({
  canCreateBooking,
  canCancelBooking,
  onCreateBooking,
  onBlockTime,
  onCancelBooking,
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
      {canCancelBooking && (
        <button
          type="button"
          onClick={onCancelBooking}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-rose-200 px-4 py-2.5 text-xs font-bold text-rose-700 transition-colors hover:bg-rose-50"
        >
          <CalendarX2 className="h-4 w-4" />
          Cancel Selected Booking
        </button>
      )}
      <button
        type="button"
        disabled={!canCreateBooking}
        onClick={onCreateBooking}
        className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
      >
        <CalendarPlus className="h-4 w-4" />
        Create Booking (Admin Override)
      </button>
      <button
        type="button"
        onClick={onBlockTime}
        className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600 transition-colors hover:border-rose-100 hover:bg-rose-50 hover:text-rose-700"
      >
        <ShieldAlert className="h-4 w-4" />
        Block Out Time / Maintenance
      </button>
    </div>
  );
}
