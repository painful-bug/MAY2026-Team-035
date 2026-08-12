import React, { useState } from 'react';
import { ADDABLE_CHARGE_TYPES } from '../../constants/ledgerStatuses.js';
import { formatLedgerCurrency } from '../../utils/amenityLedger.js';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';
import ConfirmationDialog from '../booking/ConfirmationDialog.jsx';

// Money the resident now OWES that nobody had billed yet.
//
// The opposite direction from the payment form beside it, and a different thing
// again from a damage deduction: damage comes OUT of a deposit already held and
// reduces what is refundable, while this RAISES what is owed and is settled
// separately. Billing damage here instead would leave the deposit untouched and
// the resident invoiced for it twice over.
//
// **A second charge of the same kind adds to the first.** The ledger carries one
// `additionalCharges` figure, and housekeeping on Monday plus a broken chair on
// Tuesday is two things — so this form never overwrites, and the total below is
// what the amount will be added to.

export default function AddChargeModal({
  transaction,
  isSubmitting,
  submissionError,
  onClose,
  onAdd,
}) {
  const [chargeType, setChargeType] = useState('additional');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [errors, setErrors] = useState({});

  const handleSubmit = async (event) => {
    event.preventDefault();
    const numericAmount = Number(amount);
    const validationErrors = {};

    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      validationErrors.amount = 'Enter the amount to bill.';
    }

    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    const result = await onAdd(transaction.id, {
      amount: numericAmount,
      chargeType,
      description: description.trim() || null,
    });

    if (result) {
      onClose();
    }
  };

  return (
    <ConfirmationDialog
      title="Add Charge"
      description="Bill something after the fact against this booking."
      confirmLabel="Add Charge"
      confirmingLabel="Adding Charge..."
      isSubmitting={isSubmitting}
      submissionError={submissionError}
      onClose={onClose}
      onConfirm={handleSubmit}
      tone="primary"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-slate-50 px-3.5 py-3">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            Additional Charges So Far
          </p>
          <p className="mt-1 text-xs font-bold text-slate-700">
            {formatLedgerCurrency(transaction.additionalCharges)}
          </p>
        </div>
        <div className="rounded-xl bg-slate-50 px-3.5 py-3">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            Total Billed
          </p>
          <p className="mt-1 text-xs font-bold text-slate-700">
            {formatLedgerCurrency(transaction.totalAmount)}
          </p>
        </div>
      </div>

      <AmenityFormField label="Charge Type" required>
        <select
          value={chargeType}
          onChange={(event) => setChargeType(event.target.value)}
          className={amenityInputClasses}
        >
          {ADDABLE_CHARGE_TYPES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </AmenityFormField>

      <AmenityFormField label="Amount" required error={errors.amount}>
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

      <AmenityFormField label="Description (Optional)">
        <textarea
          rows={2}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Additional housekeeping after the event."
          className={`${amenityInputClasses} resize-none`}
        />
      </AmenityFormField>
    </ConfirmationDialog>
  );
}
