import React from 'react';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';
import FormSection from '../booking/FormSection.jsx';

export default function ChargeOverride({ value, error, onChange }) {
  return (
    <FormSection
      title="Charge override"
      description="Leave blank to use default pricing when it becomes available."
    >
      <AmenityFormField label="Override Amount" error={error}>
        <input
          type="number"
          min="0"
          step="0.01"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Optional amount"
          aria-invalid={Boolean(error)}
          className={`${amenityInputClasses} ${
            error ? 'border-rose-300 focus:border-rose-500' : ''
          }`}
        />
      </AmenityFormField>
    </FormSection>
  );
}
