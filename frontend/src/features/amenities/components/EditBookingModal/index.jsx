import React from 'react';
import BookingFormModal from '../booking/BookingFormModal.jsx';

export default function EditBookingModal({ booking, onSubmit, ...props }) {
  return (
    <BookingFormModal
      {...props}
      mode="edit"
      booking={booking}
      onSubmit={(bookingData) => onSubmit(booking.id, bookingData)}
    />
  );
}
