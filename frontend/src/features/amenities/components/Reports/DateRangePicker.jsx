import React from 'react';
import AmenityFormField, { amenityInputClasses } from '../AmenityFormField.jsx';

export default function DateRangePicker({ startDate, endDate, onChange }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <AmenityFormField label="From Date">
        <input
          type="date"
          value={startDate}
          max={endDate || undefined}
          onChange={(event) => onChange('startDate', event.target.value)}
          className={amenityInputClasses}
        />
      </AmenityFormField>
      <AmenityFormField label="To Date">
        <input
          type="date"
          value={endDate}
          min={startDate || undefined}
          onChange={(event) => onChange('endDate', event.target.value)}
          className={amenityInputClasses}
        />
      </AmenityFormField>
    </div>
  );
}
