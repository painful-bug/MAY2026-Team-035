import React from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { AMENITY_CATEGORIES } from '../../constants/amenityCategories.js';
import { BOOKING_MODE_OPTIONS } from '../../constants/bookingModes.js';
import AmenityFormField, { amenityInputClasses } from '../AmenityFormField.jsx';
import NumberField from './NumberField.jsx';
import SettingsCard from './SettingsCard.jsx';
import SettingsSection from './SettingsSection.jsx';
import TimeField from './TimeField.jsx';

export default function GeneralSettingsCard({ values, errors, onChange }) {
  return (
    <SettingsCard
      icon={SlidersHorizontal}
      title="General Settings"
      description="Manage the amenity identity, booking mode, and daily operating schedule."
    >
      <SettingsSection title="Amenity details">
        <div className="grid gap-4 sm:grid-cols-2">
          <AmenityFormField label="Amenity Name" required error={errors.name}>
            <input
              value={values.name}
              onChange={(event) => onChange('name', event.target.value)}
              className={`${amenityInputClasses} ${
                errors.name ? 'border-rose-300 focus:border-rose-500' : ''
              }`}
            />
          </AmenityFormField>
          <AmenityFormField label="Category">
            <select
              value={values.category}
              onChange={(event) => onChange('category', event.target.value)}
              className={amenityInputClasses}
            >
              {AMENITY_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </AmenityFormField>
          <AmenityFormField label="Location">
            <input
              value={values.location}
              onChange={(event) => onChange('location', event.target.value)}
              placeholder="e.g. Clubhouse, Ground Floor"
              className={amenityInputClasses}
            />
          </AmenityFormField>
          <NumberField
            label="Maximum Capacity"
            required
            min={1}
            value={values.capacity}
            error={errors.capacity}
            onChange={(value) => onChange('capacity', value)}
          />
          <div className="sm:col-span-2">
            <AmenityFormField label="Description">
              <textarea
                rows={3}
                value={values.description}
                onChange={(event) =>
                  onChange('description', event.target.value)
                }
                className={`${amenityInputClasses} resize-none`}
              />
            </AmenityFormField>
          </div>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Operating hours"
        description="Changes here are reflected in the booking timeline."
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <AmenityFormField label="Booking Mode">
            <select
              value={values.bookingMode}
              onChange={(event) =>
                onChange('bookingMode', event.target.value)
              }
              className={amenityInputClasses}
            >
              {BOOKING_MODE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.value}
                </option>
              ))}
            </select>
          </AmenityFormField>
          <TimeField
            label="Opening Time"
            value={values.openingTime}
            error={errors.openingTime}
            onChange={(value) => onChange('openingTime', value)}
          />
          <TimeField
            label="Closing Time"
            value={values.closingTime}
            error={errors.closingTime}
            onChange={(value) => onChange('closingTime', value)}
          />
          <NumberField
            label="Booking Slot Duration (min)"
            required
            min={1}
            value={values.slotDurationMinutes}
            error={errors.slotDurationMinutes}
            onChange={(value) => onChange('slotDurationMinutes', value)}
          />
          <NumberField
            label="Cleaning Buffer (min)"
            value={values.cleaningBufferMinutes}
            error={errors.cleaningBufferMinutes}
            onChange={(value) => onChange('cleaningBufferMinutes', value)}
          />
          <NumberField
            label="Maximum Active Bookings Per Resident"
            value={values.maxActiveBookingsPerResident}
            error={errors.maxActiveBookingsPerResident}
            placeholder="Unlimited"
            onChange={(value) =>
              onChange('maxActiveBookingsPerResident', value)
            }
          />
        </div>
      </SettingsSection>
    </SettingsCard>
  );
}
