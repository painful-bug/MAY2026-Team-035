import React from 'react';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';

export default function ReasonSelector({
  label,
  options,
  value,
  otherValue,
  error,
  otherError,
  onChange,
  onOtherChange,
}) {
  return (
    <div className="space-y-4">
      <AmenityFormField label={label} required error={error}>
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={Boolean(error)}
          className={`${amenityInputClasses} ${
            error ? 'border-rose-300 focus:border-rose-500' : ''
          }`}
        >
          <option value="">Select a reason</option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </AmenityFormField>

      {value === 'other' && (
        <AmenityFormField
          label="Other Reason"
          required
          error={otherError}
        >
          <textarea
            rows={3}
            value={otherValue}
            onChange={(event) => onOtherChange(event.target.value)}
            placeholder="Enter the reason."
            aria-invalid={Boolean(otherError)}
            className={`${amenityInputClasses} resize-none ${
              otherError
                ? 'border-rose-300 focus:border-rose-500'
                : ''
            }`}
          />
        </AmenityFormField>
      )}
    </div>
  );
}
