import React, { useState } from 'react';
import { BOOKING_REJECTION_REASONS } from '../../constants/bookingFormOptions.js';
import { formatTimelineTimeRange } from '../../utils/amenityTimeline.js';
import ConfirmationDialog from '../booking/ConfirmationDialog.jsx';
import ReasonSelector from '../booking/ReasonSelector.jsx';
import ApprovalStatusBadge from './ApprovalStatusBadge.jsx';

const formatCurrency = (amount) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount);

const formatBookingDate = (date) =>
  new Date(`${date}T00:00:00`).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

function BookingDetail({ label, value, children }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3.5 py-3">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      {children ?? (
        <p className="mt-1 text-xs font-bold text-slate-700">
          {value || '—'}
        </p>
      )}
    </div>
  );
}

export default function RejectBookingDialog({
  booking,
  amenityName,
  isSubmitting,
  submissionError,
  onClose,
  onReject,
}) {
  const [reason, setReason] = useState('');
  const [otherReason, setOtherReason] = useState('');
  const [notifyResident, setNotifyResident] = useState(true);
  const [errors, setErrors] = useState({});

  const handleReasonChange = (value) => {
    setReason(value);
    setErrors((currentErrors) => ({
      ...currentErrors,
      reason: undefined,
    }));
  };

  const handleConfirm = async (event) => {
    event.preventDefault();
    const validationErrors = {};

    if (!reason) {
      validationErrors.reason = 'Select a rejection reason.';
    }

    if (reason === 'other' && !otherReason.trim()) {
      validationErrors.otherReason = 'Enter the rejection reason.';
    }

    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    // The series id, not the row's: rejecting decides the whole request and
    // releases every day of it. `POST /amenity-bookings/{seriesId}/reject`.
    const rejectedBooking = await onReject(booking.bookingSeriesId, {
      reason,
      otherReason,
      notifyResident,
    });

    if (rejectedBooking) {
      onClose();
    }
  };

  return (
    <ConfirmationDialog
      title="Reject Booking Request"
      description="Confirm the rejection details for this resident request."
      confirmLabel="Reject Booking"
      confirmingLabel="Rejecting Booking..."
      isSubmitting={isSubmitting}
      submissionError={submissionError}
      onClose={onClose}
      onConfirm={handleConfirm}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <BookingDetail label="Resident Name" value={booking.residentName} />
        <BookingDetail label="Flat Number" value={booking.residentFlat} />
        <BookingDetail label="Booking Title" value={booking.bookingTitle} />
        <BookingDetail label="Amenity" value={amenityName} />
        <BookingDetail label="Date" value={formatBookingDate(booking.date)} />
        <BookingDetail
          label="Time Slot"
          value={formatTimelineTimeRange(
            booking.startTime,
            booking.endTime
          )}
        />
        <BookingDetail label="Booking Status">
          <span className="mt-1 inline-flex">
            <ApprovalStatusBadge status={booking.status} />
          </span>
        </BookingDetail>
        <BookingDetail label="Account Status">
          {booking.outstandingDues > 0 ? (
            <span className="mt-1 inline-flex rounded-full border border-amber-100 bg-amber-50 px-2.5 py-1 text-[10px] font-extrabold text-amber-700">
              Outstanding Dues {formatCurrency(booking.outstandingDues)}
            </span>
          ) : (
            <p className="mt-1 text-xs font-bold text-slate-600">
              No outstanding dues
            </p>
          )}
        </BookingDetail>
      </div>

      <ReasonSelector
        label="Reason for Rejection"
        options={BOOKING_REJECTION_REASONS}
        value={reason}
        otherValue={otherReason}
        error={errors.reason}
        otherError={errors.otherReason}
        onChange={handleReasonChange}
        onOtherChange={(value) => {
          setOtherReason(value);
          setErrors((currentErrors) => ({
            ...currentErrors,
            otherReason: undefined,
          }));
        }}
      />

      <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
        <input
          type="checkbox"
          checked={notifyResident}
          onChange={(event) => setNotifyResident(event.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-slate-300 accent-indigo-600"
        />
        <span>
          <span className="block text-xs font-bold text-slate-700">
            Notify resident with this reason
          </span>
          <span className="mt-0.5 block text-[10px] font-semibold text-slate-400">
            The preference will be stored; no notification is sent yet.
          </span>
        </span>
      </label>
    </ConfirmationDialog>
  );
}
