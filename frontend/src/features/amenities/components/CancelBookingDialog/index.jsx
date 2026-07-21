import React, { useState } from 'react';
import { BOOKING_CANCELLATION_REASONS } from '../../constants/bookingFormOptions.js';
import { formatTimelineTimeRange } from '../../utils/amenityTimeline.js';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';
import ConfirmationDialog from '../booking/ConfirmationDialog.jsx';

function BookingDetail({ label, value }) {
  return (
    <div className="space-y-1 rounded-xl bg-slate-50 px-3.5 py-3">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="text-xs font-bold text-slate-700">{value || '—'}</p>
    </div>
  );
}

export default function CancelBookingDialog({
  booking,
  isSubmitting,
  submissionError,
  onClose,
  onConfirm,
}) {
  const [reason, setReason] = useState('');
  const [details, setDetails] = useState('');
  const [errors, setErrors] = useState({});

  const handleConfirm = async (event) => {
    event.preventDefault();
    const validationErrors = {};

    if (!reason) {
      validationErrors.reason = 'Select a cancellation reason.';
    }

    if (reason === 'other' && !details.trim()) {
      validationErrors.details = 'Add the cancellation reason.';
    }

    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    await onConfirm(booking.id, { reason, details });
  };

  return (
    <ConfirmationDialog
      title="Cancel Booking"
      description="The booking will remain in history with a cancelled status."
      confirmLabel="Confirm Cancellation"
      confirmingLabel="Cancelling Booking..."
      isSubmitting={isSubmitting}
      submissionError={submissionError}
      onClose={onClose}
      onConfirm={handleConfirm}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <BookingDetail label="Resident" value={booking.residentName} />
        <BookingDetail label="Booking" value={booking.bookingTitle} />
        <BookingDetail label="Date" value={booking.date} />
        <BookingDetail
          label="Time"
          value={formatTimelineTimeRange(
            booking.startTime,
            booking.endTime
          )}
        />
      </div>

      <AmenityFormField
        label="Reason for Cancellation"
        required
        error={errors.reason}
      >
        <select
          value={reason}
          onChange={(event) => {
            setReason(event.target.value);
            setErrors((currentErrors) => ({
              ...currentErrors,
              reason: undefined,
            }));
          }}
          aria-invalid={Boolean(errors.reason)}
          className={`${amenityInputClasses} ${
            errors.reason ? 'border-rose-300 focus:border-rose-500' : ''
          }`}
        >
          <option value="">Select a reason</option>
          {BOOKING_CANCELLATION_REASONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </AmenityFormField>

      {reason === 'other' && (
        <AmenityFormField
          label="Cancellation Details"
          required
          error={errors.details}
        >
          <textarea
            rows={3}
            value={details}
            onChange={(event) => {
              setDetails(event.target.value);
              setErrors((currentErrors) => ({
                ...currentErrors,
                details: undefined,
              }));
            }}
            placeholder="Explain why this booking is being cancelled."
            aria-invalid={Boolean(errors.details)}
            className={`${amenityInputClasses} resize-none ${
              errors.details
                ? 'border-rose-300 focus:border-rose-500'
                : ''
            }`}
          />
        </AmenityFormField>
      )}
    </ConfirmationDialog>
  );
}
