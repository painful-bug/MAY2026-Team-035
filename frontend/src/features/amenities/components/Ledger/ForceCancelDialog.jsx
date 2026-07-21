import React, { useState } from 'react';
import { FORCE_CANCEL_REASONS } from '../../constants/ledgerStatuses.js';
import { formatLedgerDate } from '../../utils/amenityLedger.js';
import ConfirmationDialog from '../booking/ConfirmationDialog.jsx';
import ReasonSelector from '../booking/ReasonSelector.jsx';

export default function ForceCancelDialog({
  transaction,
  isSubmitting,
  submissionError,
  onClose,
  onForceCancel,
}) {
  const [reason, setReason] = useState('');
  const [otherReason, setOtherReason] = useState('');
  const [errors, setErrors] = useState({});

  const handleSubmit = async (event) => {
    event.preventDefault();
    const validationErrors = {};

    if (!reason) {
      validationErrors.reason = 'Select a cancellation reason.';
    }

    if (reason === 'other' && !otherReason.trim()) {
      validationErrors.otherReason = 'Enter the cancellation reason.';
    }

    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    const reasonLabel =
      reason === 'other'
        ? otherReason.trim()
        : FORCE_CANCEL_REASONS.find((option) => option.value === reason)?.label;
    const result = await onForceCancel(transaction.id, {
      reason: reasonLabel,
      reasonCode: reason,
    });

    if (result) {
      onClose();
    }
  };

  return (
    <ConfirmationDialog
      title="Force Cancel Booking"
      description="Cancel this future booking and move its deposit to refund review."
      confirmLabel="Force Cancel Booking"
      confirmingLabel="Cancelling Booking..."
      isSubmitting={isSubmitting}
      submissionError={submissionError}
      onClose={onClose}
      onConfirm={handleSubmit}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-slate-50 px-3.5 py-3">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            Resident
          </p>
          <p className="mt-1 text-xs font-bold text-slate-700">
            {transaction.residentName}
          </p>
        </div>
        <div className="rounded-xl bg-slate-50 px-3.5 py-3">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            Booking
          </p>
          <p className="mt-1 text-xs font-bold text-slate-700">
            {transaction.bookingId}
          </p>
        </div>
        <div className="rounded-xl bg-slate-50 px-3.5 py-3">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            Booking Date
          </p>
          <p className="mt-1 text-xs font-bold text-slate-700">
            {formatLedgerDate(transaction.bookingDate)}
          </p>
        </div>
        <div className="rounded-xl bg-slate-50 px-3.5 py-3">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            Flat
          </p>
          <p className="mt-1 text-xs font-bold text-slate-700">
            {transaction.residentFlat || '—'}
          </p>
        </div>
      </div>

      <ReasonSelector
        label="Cancellation Reason"
        options={FORCE_CANCEL_REASONS}
        value={reason}
        otherValue={otherReason}
        error={errors.reason}
        otherError={errors.otherReason}
        onChange={(value) => {
          setReason(value);
          setErrors((current) => ({ ...current, reason: undefined }));
        }}
        onOtherChange={(value) => {
          setOtherReason(value);
          setErrors((current) => ({
            ...current,
            otherReason: undefined,
          }));
        }}
      />
    </ConfirmationDialog>
  );
}
