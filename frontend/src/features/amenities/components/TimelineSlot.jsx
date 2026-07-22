import React from 'react';
import {
  BOOKING_TIMELINE_STATE,
  BOOKING_TIMELINE_STATE_META,
} from '../constants/bookingTimelineStates.js';
import { getTimelineGridColumn } from '../utils/amenityTimeline.js';

export default function TimelineSlot({
  slot,
  isSelected,
  onSelect,
}) {
  const availableState =
    BOOKING_TIMELINE_STATE_META[BOOKING_TIMELINE_STATE.AVAILABLE];

  return (
    <button
      type="button"
      aria-pressed={isSelected}
      aria-label={`Select available slot ${slot.label}`}
      onClick={() => onSelect(slot)}
      style={{
        gridColumn: getTimelineGridColumn(slot),
        gridRow: 2,
      }}
      className={`flex min-w-0 items-end justify-center border-r p-3 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-500 ${availableState.blockClasses} ${
        isSelected ? 'ring-2 ring-inset ring-indigo-500' : ''
      }`}
    >
      <span className="text-[10px] font-bold">{availableState.label}</span>
    </button>
  );
}
