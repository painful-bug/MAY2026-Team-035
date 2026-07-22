import React from 'react';
import {
  BOOKING_MODE,
  BOOKING_MODE_OPTIONS,
} from '../constants/bookingModes.js';
import AmenityFormField, {
  amenityInputClasses,
} from './AmenityFormField.jsx';
import AmenityStatusToggle from './AmenityStatusToggle.jsx';

function ConfigurationToggle({ label, description, checked, onChange }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl bg-white px-4 py-3">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          {label}
        </p>
        <p className="mt-0.5 text-[11px] font-medium text-slate-400">
          {description}
        </p>
      </div>
      <AmenityStatusToggle
        checked={checked}
        onChange={onChange}
        ariaLabel={label}
      />
    </div>
  );
}

export default function BookingConfigurationSection({
  values,
  errors,
  onFieldChange,
  onBookingModeChange,
}) {
  const supportsSharedCapacity =
    values.bookingMode === BOOKING_MODE.SHARED ||
    values.bookingMode === BOOKING_MODE.HYBRID;
  const isHybrid = values.bookingMode === BOOKING_MODE.HYBRID;
  const selectedMode = BOOKING_MODE_OPTIONS.find(
    (option) => option.value === values.bookingMode
  );

  return (
    <section className="space-y-4 rounded-2xl bg-slate-50 p-5">
      <div>
        <h3 className="text-sm font-extrabold text-slate-800">
          Booking Configuration
        </h3>
        <p className="mt-1 text-[11px] font-medium leading-relaxed text-slate-400">
          Define how this amenity can be reserved. This stores configuration only.
        </p>
      </div>

      <AmenityFormField
        label="Booking Mode"
        required
        error={errors.bookingMode}
      >
        <select
          value={values.bookingMode}
          onChange={(event) => onBookingModeChange(event.target.value)}
          aria-invalid={Boolean(errors.bookingMode)}
          className={`${amenityInputClasses} bg-white ${
            errors.bookingMode ? 'border-rose-300 focus:border-rose-500' : ''
          }`}
        >
          <option value="" disabled>
            Select booking mode
          </option>
          {BOOKING_MODE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.value}
            </option>
          ))}
        </select>
        {selectedMode && (
          <p className="text-[11px] font-medium leading-relaxed text-slate-400">
            {selectedMode.description}
          </p>
        )}
      </AmenityFormField>

      <div
        className={`grid grid-cols-1 gap-4 ${
          supportsSharedCapacity ? 'sm:grid-cols-3' : 'sm:grid-cols-2'
        }`}
      >
        {supportsSharedCapacity && (
          <AmenityFormField
            label="Capacity"
            required
            error={errors.capacity}
          >
            <input
              type="number"
              min="1"
              value={values.capacity}
              onChange={(event) =>
                onFieldChange('capacity', event.target.value)
              }
              placeholder="e.g. 30"
              aria-invalid={Boolean(errors.capacity)}
              className={`${amenityInputClasses} bg-white ${
                errors.capacity ? 'border-rose-300 focus:border-rose-500' : ''
              }`}
            />
          </AmenityFormField>
        )}

        <AmenityFormField
          label="Cleaning Buffer (minutes)"
          error={errors.cleaningBuffer}
        >
          <input
            type="number"
            min="0"
            value={values.cleaningBuffer}
            onChange={(event) =>
              onFieldChange('cleaningBuffer', event.target.value)
            }
            placeholder="e.g. 30"
            aria-invalid={Boolean(errors.cleaningBuffer)}
            className={`${amenityInputClasses} bg-white ${
              errors.cleaningBuffer
                ? 'border-rose-300 focus:border-rose-500'
                : ''
            }`}
          />
        </AmenityFormField>

        <AmenityFormField
          label="Max bookings per resident"
          error={errors.maxBookingsPerResident}
        >
          <input
            type="number"
            min="0"
            value={values.maxBookingsPerResident}
            onChange={(event) =>
              onFieldChange('maxBookingsPerResident', event.target.value)
            }
            placeholder="Unlimited"
            aria-invalid={Boolean(errors.maxBookingsPerResident)}
            className={`${amenityInputClasses} bg-white ${
              errors.maxBookingsPerResident
                ? 'border-rose-300 focus:border-rose-500'
                : ''
            }`}
          />
        </AmenityFormField>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {isHybrid && (
          <ConfigurationToggle
            label="Allow Private Booking"
            description={
              values.allowPrivateBooking
                ? 'Private reservations are allowed'
                : 'Shared reservations only'
            }
            checked={values.allowPrivateBooking}
            onChange={(allowPrivateBooking) =>
              onFieldChange('allowPrivateBooking', allowPrivateBooking)
            }
          />
        )}
        <div className={isHybrid ? '' : 'sm:col-span-2'}>
          <ConfigurationToggle
            label="Require Admin Approval"
            description={
              values.requireApproval
                ? 'Bookings will require approval'
                : 'Bookings can proceed without approval'
            }
            checked={values.requireApproval}
            onChange={(requireApproval) =>
              onFieldChange('requireApproval', requireApproval)
            }
          />
        </div>
      </div>
    </section>
  );
}
