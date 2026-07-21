import React from 'react';
import { BadgeIndianRupee } from 'lucide-react';
import { CURRENCY_OPTIONS } from '../../constants/amenitySettings.js';
import AmenityFormField, { amenityInputClasses } from '../AmenityFormField.jsx';
import NumberField from './NumberField.jsx';
import SettingsCard from './SettingsCard.jsx';

export default function PaymentSettingsCard({ values, errors, onChange }) {
  return (
    <SettingsCard
      icon={BadgeIndianRupee}
      title="Payment Settings"
      description="Store pricing and deposit rules without connecting a payment gateway."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <NumberField
          label="Booking Fee"
          step="0.01"
          value={values.bookingFee}
          error={errors.bookingFee}
          onChange={(value) => onChange('bookingFee', value)}
        />
        <NumberField
          label="Security Deposit"
          step="0.01"
          value={values.securityDeposit}
          error={errors.securityDeposit}
          onChange={(value) => onChange('securityDeposit', value)}
        />
        <NumberField
          label="Late Cancellation Charge"
          step="0.01"
          value={values.lateCancellationCharge}
          error={errors.lateCancellationCharge}
          onChange={(value) => onChange('lateCancellationCharge', value)}
        />
        <NumberField
          label="Damage Deposit"
          step="0.01"
          value={values.damageDeposit}
          error={errors.damageDeposit}
          onChange={(value) => onChange('damageDeposit', value)}
        />
        <AmenityFormField label="Currency">
          <select
            value={values.currency}
            onChange={(event) => onChange('currency', event.target.value)}
            className={amenityInputClasses}
          >
            {CURRENCY_OPTIONS.map((currency) => (
              <option key={currency.value} value={currency.value}>
                {currency.label}
              </option>
            ))}
          </select>
        </AmenityFormField>
        <div className="sm:col-span-2 lg:col-span-3">
          <AmenityFormField label="Refund Policy">
            <textarea
              rows={3}
              value={values.refundPolicy}
              onChange={(event) =>
                onChange('refundPolicy', event.target.value)
              }
              placeholder="Describe refund eligibility and timelines."
              className={`${amenityInputClasses} resize-none`}
            />
          </AmenityFormField>
        </div>
      </div>
    </SettingsCard>
  );
}
