import React from 'react';
import { CalendarPlus, ShieldAlert } from 'lucide-react';

export default function TimelineActions({
  canCreateBooking,
  onCreateBooking,
  onBlockTime,
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
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
