import React from 'react';
import { amenityInputClasses } from '../AmenityFormField.jsx';
import FormSection from '../booking/FormSection.jsx';

export default function InternalNotes({ value, onChange }) {
  return (
    <FormSection
      title="Internal notes"
      description="Visible to administrators only."
    >
      <textarea
        rows={3}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Add context for the admin team."
        className={`${amenityInputClasses} resize-none`}
      />
    </FormSection>
  );
}
