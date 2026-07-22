import React from 'react';
import BookingBlock from './BookingBlock.jsx';
import TimelineSlot from './TimelineSlot.jsx';
import { BOOKING_TIMELINE_STATE } from '../constants/bookingTimelineStates.js';
import {
  createHourlySlots,
  createTimelineBlocks,
  getTimelineGridColumn,
  getTimelineSlotCount,
} from '../utils/amenityTimeline.js';

const TIMELINE_SLOT_WIDTH = 40;

export default function BookingTimeline({
  bookings,
  openingTime,
  closingTime,
  cleaningBuffer,
  amenityId,
  selectedDate,
  selectedSlot,
  selectedBooking,
  onSelectSlot,
  onSelectBooking,
}) {
  const slots = createHourlySlots(openingTime, closingTime);
  const timelineBlocks = createTimelineBlocks(
    bookings,
    slots,
    cleaningBuffer
  );
  const slotCount = getTimelineSlotCount(slots);
  const gridStyle = {
    gridTemplateColumns: `repeat(${slotCount}, minmax(${TIMELINE_SLOT_WIDTH}px, 1fr))`,
    gridTemplateRows: '2.5rem 7rem',
    minWidth: `${slotCount * TIMELINE_SLOT_WIDTH}px`,
  };

  if (slots.length === 0) {
    return (
      <p className="rounded-xl bg-slate-50 px-4 py-8 text-center text-xs font-semibold text-slate-400">
        Operating hours are unavailable.
      </p>
    );
  }

  return (
    <div className="scroll-smooth overflow-x-auto overscroll-x-contain rounded-xl border border-slate-100">
      <div className="grid touch-pan-x bg-white" style={gridStyle}>
        {slots.map((slot) => (
          <div
            key={slot.id}
            style={{
              gridColumn: getTimelineGridColumn(slot),
              gridRow: 1,
            }}
            className="flex items-center justify-center border-r border-b border-slate-100 bg-slate-50 px-3 text-center text-[10px] font-extrabold uppercase tracking-wider text-slate-500"
          >
            {slot.label}
          </div>
        ))}
        {slots.map((slot) => (
          <TimelineSlot
            key={slot.id}
            slot={{
              ...slot,
              id: `${amenityId}-${selectedDate}-${slot.id}`,
              amenityId,
              date: selectedDate,
              state: BOOKING_TIMELINE_STATE.AVAILABLE,
            }}
            isSelected={
              selectedSlot?.id === `${amenityId}-${selectedDate}-${slot.id}`
            }
            onSelect={onSelectSlot}
          />
        ))}
        {timelineBlocks.map((booking) => (
          <BookingBlock
            key={booking.id}
            booking={booking}
            isSelected={selectedBooking?.id === booking.id}
            onSelect={onSelectBooking}
          />
        ))}
      </div>
    </div>
  );
}
