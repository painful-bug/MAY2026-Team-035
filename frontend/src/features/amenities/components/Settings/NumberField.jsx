import React from 'react';
import AmenityFormField, { amenityInputClasses } from '../AmenityFormField.jsx';

export default function NumberField({
  label,
  value,
  error,
  onChange,
  min = 0,
  step = 1,
  placeholder,
  required = false,
}) {
  return (
    <AmenityFormField label={label} required={required} error={error}>
      <input
        type="number"
        min={min}
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
        className={`${amenityInputClasses} ${
          error ? 'border-rose-300 focus:border-rose-500' : ''
        }`}
      />
    </AmenityFormField>
  );
}
