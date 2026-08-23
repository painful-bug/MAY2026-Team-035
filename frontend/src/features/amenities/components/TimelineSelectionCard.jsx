import React from 'react';
import { MousePointer2 } from 'lucide-react';
import { bookingStatusLabel } from '../constants/bookingStatuses.js';
import { BOOKING_TIMELINE_STATE } from '../constants/bookingTimelineStates.js';
import { formatTimelineTimeRange } from '../utils/amenityTimeline.js';

const humanizeValue = (value) => {
  if (!value) {
    return '—';
  }

  return value
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

function SelectionDetail({ label, value }) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="text-xs font-bold text-slate-700">{value || '—'}</p>
    </div>
  );
}

export default function TimelineSelectionCard({
  amenityName,
  selectedSlot,
  selectedBooking,
  selectedState,
  onClear,
}) {
  const hasSelection = Boolean(selectedSlot || selectedBooking);

  return (
    <aside className="rounded-2xl border border-slate-100 bg-slate-50 p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-indigo-600">
            <MousePointer2 className="h-4 w-4" />
          </span>
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-600">
              Timeline selection
            </p>
            <h3 className="text-sm font-extrabold text-slate-800">
              {hasSelection ? 'Selected details' : 'Nothing selected'}
            </h3>
          </div>
        </div>
        {hasSelection && (
          <button
            type="button"
            onClick={onClear}
            className="text-xs font-bold text-slate-400 transition-colors hover:text-slate-700"
          >
            Clear
          </button>
        )}
      </div>

      {!hasSelection ? (
        <p className="text-xs font-semibold text-slate-400">
          Select an available slot, booking, or blocked interval to view its details.
        </p>
      ) : selectedState === BOOKING_TIMELINE_STATE.AVAILABLE ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <SelectionDetail label="Time" value={selectedSlot.label} />
          <SelectionDetail label="Amenity" value={amenityName} />
          <SelectionDetail label="Availability" value="Available" />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <SelectionDetail
            label="Resident"
            value={selectedBooking.residentName}
          />
          <SelectionDetail
            label="Booking Title"
            value={selectedBooking.bookingTitle}
          />
          <SelectionDetail
            label="Time"
            value={formatTimelineTimeRange(
              selectedBooking.startTime,
              selectedBooking.endTime
            )}
          />
          <SelectionDetail
            label="Booking Type"
            value={humanizeValue(selectedBooking.bookingType)}
          />
          <SelectionDetail
            label="Status"
            value={bookingStatusLabel(selectedBooking.status) || '—'}
          />
        </div>
      )}
    </aside>
  );
}
