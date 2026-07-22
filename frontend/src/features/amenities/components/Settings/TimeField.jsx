import React from 'react';
import AmenityFormField, { amenityInputClasses } from '../AmenityFormField.jsx';

export default function TimeField({ label, value, error, onChange }) {
  return (
    <AmenityFormField label={label} required error={error}>
      <input
        type="time"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={Boolean(error)}
        className={`${amenityInputClasses} ${
          error ? 'border-rose-300 focus:border-rose-500' : ''
        }`}
      />
    </AmenityFormField>
  );
}
