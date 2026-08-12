import React, { useState } from 'react';
import { PAYMENT_CHARGE_TYPES } from '../../constants/ledgerStatuses.js';
import { formatLedgerCurrency } from '../../utils/amenityLedger.js';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';
import ConfirmationDialog from '../booking/ConfirmationDialog.jsx';

// Money the community RECEIVED, recorded against one existing charge.
//
// **This is not the resident's payment simulator.** `POST /invoices/{id}/pay`
// and `POST /amenity-bookings/{id}/pay` are a resident putting money through a
// gateway, and they answer `200` with a `PaymentOutcome` that may say `failed`.
// This endpoint records a payment that already happened somewhere else — at the
// desk, by transfer, in cash — so it has no outcome to branch on, no
// `idempotencyKey`, and no decline. What it has instead is `paymentReference`,
// which makes it idempotent: a replayed gateway callback returns the event
// already recorded rather than crediting twice.
//
// Overpayment is a `409`, not a clamp, and that is the API's decision rather
// than this form's: clamping accepts money and then loses it. The two hints
// below are shown so the number is right before it is sent, not so the client
// can enforce anything.

function Detail({ label, value }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3.5 py-3">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-xs font-bold text-slate-700">{value}</p>
    </div>
  );
}

export default function RecordPaymentModal({
  transaction,
  isSubmitting,
  submissionError,
  onClose,
  onRecord,
}) {
  const [chargeType, setChargeType] = useState('booking');
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState('');
  const [paymentReference, setPaymentReference] = useState('');
  const [notes, setNotes] = useState('');
  const [errors, setErrors] = useState({});

  const chargesOutstanding = Math.max(
    Number(transaction.totalAmount || 0) - Number(transaction.amountPaid || 0),
    0
  );
  const depositOutstanding = Number(transaction.outstandingDeposit || 0);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const numericAmount = Number(amount);
    const validationErrors = {};

    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      validationErrors.amount = 'Enter the amount received.';
    }

    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    const result = await onRecord(transaction.id, {
      amount: numericAmount,
      chargeType,
      method: method.trim() || null,
      paymentReference: paymentReference.trim() || null,
      notes: notes.trim() || null,
    });

    if (result) {
      onClose();
    }
  };

  return (
    <ConfirmationDialog
      title="Record Payment Received"
      description="Record money already collected against one of this booking's charges."
      confirmLabel="Record Payment"
      confirmingLabel="Recording Payment..."
      isSubmitting={isSubmitting}
      submissionError={submissionError}
      onClose={onClose}
      onConfirm={handleSubmit}
      tone="primary"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Detail
          label="Charges Outstanding"
          value={formatLedgerCurrency(chargesOutstanding)}
        />
        <Detail
          label="Deposit Outstanding"
          value={formatLedgerCurrency(depositOutstanding)}
        />
      </div>

      <AmenityFormField label="Settles" required>
        <select
          value={chargeType}
          onChange={(event) => setChargeType(event.target.value)}
          className={amenityInputClasses}
        >
          {PAYMENT_CHARGE_TYPES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </AmenityFormField>

      <AmenityFormField label="Amount Received" required error={errors.amount}>
        <input
          type="number"
          min="0"
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

      <div className="grid gap-4 sm:grid-cols-2">
        <AmenityFormField label="Method (Optional)">
          <input
            type="text"
            value={method}
            onChange={(event) => setMethod(event.target.value)}
            placeholder="UPI, Cash, Bank transfer"
            className={amenityInputClasses}
          />
        </AmenityFormField>
        {/* The idempotency key of this endpoint. Two records carrying the same
            reference against the same charge are one payment, which is what
            stops a replayed callback crediting twice. */}
        <AmenityFormField label="Payment Reference (Optional)">
          <input
            type="text"
            value={paymentReference}
            onChange={(event) => setPaymentReference(event.target.value)}
            placeholder="PAY-GYM-1006"
            className={amenityInputClasses}
          />
        </AmenityFormField>
      </div>

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
