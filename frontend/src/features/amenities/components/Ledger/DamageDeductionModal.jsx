import React, { useState } from 'react';
import { formatLedgerCurrency } from '../../utils/amenityLedger.js';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';
import ConfirmationDialog from '../booking/ConfirmationDialog.jsx';

export default function DamageDeductionModal({
  transaction,
  isSubmitting,
  submissionError,
  onClose,
  onDeduct,
}) {
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [notes, setNotes] = useState('');
  const [errors, setErrors] = useState({});

  const handleSubmit = async (event) => {
    event.preventDefault();
    const numericAmount = Number(amount);
    const validationErrors = {};

    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      validationErrors.amount = 'Enter a valid damage amount.';
    } else if (numericAmount > transaction.remainingRefund) {
      validationErrors.amount =
        'Damage deduction cannot exceed the refundable amount.';
    }

    if (!reason.trim()) {
      validationErrors.reason = 'Enter the damage reason.';
    }

    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    const result = await onDeduct(transaction.id, {
      amount: numericAmount,
      reason,
      notes,
    });

    if (result) {
      onClose();
    }
  };

  return (
    <ConfirmationDialog
      title="Deduct Damage Charges"
      description="Record charges against the refundable security deposit."
      confirmLabel="Deduct Charges"
      confirmingLabel="Saving Deduction..."
      isSubmitting={isSubmitting}
      submissionError={submissionError}
      onClose={onClose}
      onConfirm={handleSubmit}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-slate-50 px-3.5 py-3">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            Deposit Amount
          </p>
          <p className="mt-1 text-xs font-bold text-slate-700">
            {formatLedgerCurrency(transaction.depositAmount)}
          </p>
        </div>
        <div className="rounded-xl bg-slate-50 px-3.5 py-3">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            Current Refundable Amount
          </p>
          <p className="mt-1 text-xs font-bold text-slate-700">
            {formatLedgerCurrency(transaction.remainingRefund)}
          </p>
        </div>
      </div>

      <AmenityFormField label="Damage Amount" required error={errors.amount}>
        <input
          type="number"
          min="0"
          max={transaction.remainingRefund}
          step="0.01"
          value={amount}
          onChange={(event) => {
            setAmount(event.target.value);
            setErrors((current) => ({ ...current, amount: undefined }));
          }}
          aria-invalid={Boolean(errors.amount)}
          className={`${amenityInputClasses} ${
            errors.amount ? 'border-rose-300 focus:border-rose-500' : ''
          }`}
        />
      </AmenityFormField>

      <AmenityFormField label="Reason" required error={errors.reason}>
        <textarea
          rows={2}
          value={reason}
          onChange={(event) => {
            setReason(event.target.value);
            setErrors((current) => ({ ...current, reason: undefined }));
          }}
          placeholder="Describe the damage."
          aria-invalid={Boolean(errors.reason)}
          className={`${amenityInputClasses} resize-none ${
            errors.reason ? 'border-rose-300 focus:border-rose-500' : ''
          }`}
        />
      </AmenityFormField>

      <AmenityFormField label="Internal Notes (Optional)">
        <textarea
          rows={2}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Add internal context."
          className={`${amenityInputClasses} resize-none`}
        />
      </AmenityFormField>
    </ConfirmationDialog>
  );
}
