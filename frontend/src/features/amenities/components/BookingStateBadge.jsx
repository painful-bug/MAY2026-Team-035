import React from 'react';
import { BOOKING_TIMELINE_STATE_META } from '../constants/bookingTimelineStates.js';

export default function BookingStateBadge({ state }) {
  const stateMeta = BOOKING_TIMELINE_STATE_META[state];

  if (!stateMeta) {
    return null;
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-extrabold ${stateMeta.badgeClasses}`}
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 rounded-full bg-current"
      />
      {stateMeta.label}
    </span>
  );
}
