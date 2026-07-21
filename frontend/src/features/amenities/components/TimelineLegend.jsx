import React from 'react';
import {
  BOOKING_TIMELINE_LEGEND_STATES,
} from '../constants/bookingTimelineStates.js';
import BookingStateBadge from './BookingStateBadge.jsx';

export default function TimelineLegend() {
  return (
    <div className="flex flex-wrap gap-2" aria-label="Timeline legend">
      {BOOKING_TIMELINE_LEGEND_STATES.map((state) => {
        return <BookingStateBadge key={state} state={state} />;
      })}
    </div>
  );
}
