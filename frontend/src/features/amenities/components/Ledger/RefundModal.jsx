import React, { useState } from 'react';
import { formatLedgerCurrency } from '../../utils/amenityLedger.js';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';
import ConfirmationDialog from '../booking/ConfirmationDialog.jsx';

function RefundDetail({ label, value }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3.5 py-3">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-xs font-bold text-slate-700">{value || '—'}</p>
    </div>
  );
}

export default function RefundModal({
  transaction,
  isSubmitting,
  submissionError,
  onClose,
  onProcess,
}) {
  const [reason, setReason] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    const result = await onProcess(transaction.id, { reason });

    if (result) {
      onClose();
    }
  };

  return (
    <ConfirmationDialog
      title="Refund Security Deposit"
      description="Process the full refundable deposit balance."
      confirmLabel="Process Refund"
      confirmingLabel="Processing Refund..."
      isSubmitting={isSubmitting}
      submissionError={submissionError}
      onClose={onClose}
      onConfirm={handleSubmit}
      tone="primary"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <RefundDetail label="Resident" value={transaction.residentName} />
        <RefundDetail label="Flat" value={transaction.residentFlat} />
        <RefundDetail label="Booking" value={transaction.bookingId} />
        <RefundDetail
          label="Deposit Amount"
          value={formatLedgerCurrency(transaction.depositAmount)}
        />
        <RefundDetail
          label="Refundable Amount"
          value={formatLedgerCurrency(transaction.remainingRefund)}
        />
        <RefundDetail
          label="Already Refunded"
          value={formatLedgerCurrency(transaction.refundAmount)}
        />
      </div>

      <AmenityFormField label="Reason (Optional)">
        <textarea
          rows={3}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Add an internal refund reason."
          className={`${amenityInputClasses} resize-none`}
        />
      </AmenityFormField>
    </ConfirmationDialog>
  );
}
