import React from 'react';
import {
  BOOKING_TIMELINE_STATE,
  BOOKING_TIMELINE_STATE_META,
} from '../constants/bookingTimelineStates.js';
import { getTimelineGridColumn } from '../utils/amenityTimeline.js';

const getBookingTitle = (booking, stateMeta) =>
  booking.bookingTitle || booking.residentName || stateMeta.label;

const getBookingCaption = (booking, stateMeta) => {
  if (booking.state === BOOKING_TIMELINE_STATE.CLEANING_BUFFER) {
    return `${booking.bufferMinutes} min`;
  }

  if (booking.state === BOOKING_TIMELINE_STATE.BLOCKED) {
    return stateMeta.label;
  }

  return booking.residentName || stateMeta.label;
};

export default function BookingBlock({ booking, isSelected, onSelect }) {
  const stateMeta = BOOKING_TIMELINE_STATE_META[booking.state];

  if (!stateMeta) {
    return null;
  }

  const blockStyle = {
    gridColumn: getTimelineGridColumn(booking),
    gridRow: 2,
  };
  const blockClasses = `z-10 my-1 flex min-w-0 flex-col justify-center overflow-hidden rounded-lg border px-2.5 py-2 text-left outline-none ${stateMeta.blockClasses} ${
    isSelected ? 'ring-2 ring-inset ring-indigo-500' : ''
  }`;
  const content = (
    <>
      <p className="truncate text-xs font-extrabold">
        {getBookingTitle(booking, stateMeta)}
      </p>
      <p className="mt-0.5 truncate text-[10px] font-bold opacity-75">
        {getBookingCaption(booking, stateMeta)}
      </p>
    </>
  );

  if (booking.state === BOOKING_TIMELINE_STATE.CLEANING_BUFFER) {
    return (
      <div style={blockStyle} className={blockClasses}>
        {content}
      </div>
    );
  }

  return (
    <button
      type="button"
      aria-pressed={isSelected}
      aria-label={`Select ${getBookingTitle(booking, stateMeta)}`}
      onClick={() => onSelect(booking)}
      style={blockStyle}
      className={`${blockClasses} focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-500`}
    >
      {content}
    </button>
  );
}
