import React from 'react';
import { CalendarDays } from 'lucide-react';
import AmenityFormField, { amenityInputClasses } from '../AmenityFormField.jsx';
import DaySelector from './DaySelector.jsx';
import NumberField from './NumberField.jsx';
import SettingsCard from './SettingsCard.jsx';
import SettingsSection from './SettingsSection.jsx';
import ToggleField from './ToggleField.jsx';

export default function AvailabilitySettingsCard({
  values,
  errors,
  onChange,
  onToggleDay,
}) {
  return (
    <SettingsCard
      icon={CalendarDays}
      title="Availability Settings"
      description="Define recurring closures and the booking window for this amenity."
    >
      <SettingsSection title="Availability calendar">
        <div className="space-y-4">
          <DaySelector
            label="Closed Days"
            selectedDays={values.closedDays}
            onToggle={(day) => onToggleDay('closedDays', day)}
          />
          <DaySelector
            label="Maintenance Days"
            selectedDays={values.maintenanceDays}
            onToggle={(day) => onToggleDay('maintenanceDays', day)}
          />
          <AmenityFormField label="Holiday Overrides">
            <textarea
              rows={3}
              value={values.holidayOverrides}
              onChange={(event) =>
                onChange('holidayOverrides', event.target.value)
              }
              placeholder={'Enter dates separated by commas or new lines\ne.g. 2026-08-15'}
              className={`${amenityInputClasses} resize-none`}
            />
          </AmenityFormField>
          <ToggleField
            label="Temporary Closure"
            description="Temporarily prevent new bookings for this amenity."
            checked={values.temporaryClosure}
            onChange={(checked) => onChange('temporaryClosure', checked)}
          />
        </div>
      </SettingsSection>

      <SettingsSection title="Booking duration and notice">
        <div className="grid gap-4 sm:grid-cols-3">
          <NumberField
            label="Minimum Booking Duration (min)"
            required
            min={1}
            value={values.minimumBookingDurationMinutes}
            error={errors.minimumBookingDurationMinutes}
            onChange={(value) =>
              onChange('minimumBookingDurationMinutes', value)
            }
          />
          <NumberField
            label="Maximum Booking Duration (min)"
            required
            min={1}
            value={values.maximumBookingDurationMinutes}
            error={errors.maximumBookingDurationMinutes}
            onChange={(value) =>
              onChange('maximumBookingDurationMinutes', value)
            }
          />
          <NumberField
            label="Advance Booking Window (days)"
            value={values.advanceBookingWindowDays}
            error={errors.advanceBookingWindowDays}
            onChange={(value) => onChange('advanceBookingWindowDays', value)}
          />
        </div>
      </SettingsSection>
    </SettingsCard>
  );
}
