import React from 'react';
import BookingFormModal from '../booking/BookingFormModal.jsx';

export default function CreateBookingModal({
  amenity,
  selectedSlot,
  residents,
  isResidentsLoading,
  isSubmitting,
  submissionError,
  onClose,
  onSubmit,
}) {
  return (
    <BookingFormModal
      mode="create"
      amenity={amenity}
      selectedSlot={selectedSlot}
      residents={residents}
      isResidentsLoading={isResidentsLoading}
      isSubmitting={isSubmitting}
      submissionError={submissionError}
      onClose={onClose}
      onSubmit={onSubmit}
    />
  );
}
