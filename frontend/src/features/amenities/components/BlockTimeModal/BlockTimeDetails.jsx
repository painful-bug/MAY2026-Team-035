import React from 'react';
import { MAINTENANCE_DEPARTMENTS } from '../../constants/bookingFormOptions.js';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';
import FormSection from '../booking/FormSection.jsx';

function ContextValue({ label, value }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3.5 py-3">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-xs font-bold text-slate-700">{value}</p>
    </div>
  );
}

export default function BlockTimeDetails({
  amenity,
  date,
  values,
  errors,
  onChange,
}) {
  return (
    <div className="space-y-5">
      <FormSection
        title="Block details"
        description="Record why this amenity should be unavailable."
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <ContextValue label="Amenity" value={amenity.name} />
          <ContextValue label="Date" value={date} />
        </div>

        <AmenityFormField label="Reason" required error={errors.reason}>
          <textarea
            rows={3}
            value={values.reason}
            onChange={(event) => onChange('reason', event.target.value)}
            placeholder="Why should this time be blocked?"
            aria-invalid={Boolean(errors.reason)}
            className={`${amenityInputClasses} resize-none ${
              errors.reason ? 'border-rose-300 focus:border-rose-500' : ''
            }`}
          />
        </AmenityFormField>

        <AmenityFormField
          label="Department"
          required
          error={errors.department}
        >
          <select
            value={values.department}
            onChange={(event) => onChange('department', event.target.value)}
            aria-invalid={Boolean(errors.department)}
            className={`${amenityInputClasses} ${
              errors.department
                ? 'border-rose-300 focus:border-rose-500'
                : ''
            }`}
          >
            <option value="">Select department</option>
            {MAINTENANCE_DEPARTMENTS.map((department) => (
              <option key={department} value={department}>
                {department}
              </option>
            ))}
          </select>
        </AmenityFormField>
      </FormSection>

      <FormSection
        title="Time slot"
        description="Adjust the selected time before creating the blocked interval."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <AmenityFormField
            label="Start Time"
            required
            error={errors.startTime}
          >
            <input
              type="time"
              step="900"
              value={values.startTime}
              min={amenity.openingTime}
              max={amenity.closingTime}
              onChange={(event) => onChange('startTime', event.target.value)}
              aria-invalid={Boolean(errors.startTime)}
              className={`${amenityInputClasses} ${
                errors.startTime
                  ? 'border-rose-300 focus:border-rose-500'
                  : ''
              }`}
            />
          </AmenityFormField>
          <AmenityFormField
            label="End Time"
            required
            error={errors.endTime}
          >
            <input
              type="time"
              step="900"
              value={values.endTime}
              min={amenity.openingTime}
              max={amenity.closingTime}
              onChange={(event) => onChange('endTime', event.target.value)}
              aria-invalid={Boolean(errors.endTime)}
              className={`${amenityInputClasses} ${
                errors.endTime
                  ? 'border-rose-300 focus:border-rose-500'
                  : ''
              }`}
            />
          </AmenityFormField>
        </div>
      </FormSection>

      <FormSection title="Notes" description="Optional internal context.">
        <textarea
          rows={3}
          value={values.notes}
          onChange={(event) => onChange('notes', event.target.value)}
          placeholder="Add notes for the admin or maintenance team."
          className={`${amenityInputClasses} resize-none`}
        />
      </FormSection>
    </div>
  );
}
