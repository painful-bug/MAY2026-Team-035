import React from 'react';
import { ADMIN_BOOKING_TYPES } from '../../constants/bookingFormOptions.js';
import { formatTimelineTimeRange } from '../../utils/amenityTimeline.js';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';
import AmenityStatusToggle from '../AmenityStatusToggle.jsx';
import FormSection from '../booking/FormSection.jsx';

function PrefilledValue({ label, value }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3.5 py-3">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-xs font-bold text-slate-700">{value}</p>
    </div>
  );
}

export default function BookingDetails({
  amenity,
  slot,
  values,
  errors,
  isEditing,
  onChange,
}) {
  return (
    <FormSection
      title="Booking details"
      description={
        isEditing
          ? 'Update the date, time, and booking configuration.'
          : 'The selected amenity and time are locked for this override.'
      }
    >
      {isEditing ? (
        <div className="space-y-4">
          <PrefilledValue label="Amenity" value={amenity.name} />
          <div className="grid gap-4 sm:grid-cols-3">
            <AmenityFormField label="Date" required error={errors.date}>
              <input
                type="date"
                value={values.date}
                onChange={(event) => onChange('date', event.target.value)}
                aria-invalid={Boolean(errors.date)}
                className={`${amenityInputClasses} ${
                  errors.date
                    ? 'border-rose-300 focus:border-rose-500'
                    : ''
                }`}
              />
            </AmenityFormField>
            <AmenityFormField
              label="Start Time"
              required
              error={errors.startTime}
            >
              <input
                type="time"
                step="900"
                min={amenity.openingTime}
                max={amenity.closingTime}
                value={values.startTime}
                onChange={(event) =>
                  onChange('startTime', event.target.value)
                }
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
                min={amenity.openingTime}
                max={amenity.closingTime}
                value={values.endTime}
                onChange={(event) =>
                  onChange('endTime', event.target.value)
                }
                aria-invalid={Boolean(errors.endTime)}
                className={`${amenityInputClasses} ${
                  errors.endTime
                    ? 'border-rose-300 focus:border-rose-500'
                    : ''
                }`}
              />
            </AmenityFormField>
          </div>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-3">
          <PrefilledValue label="Amenity" value={amenity.name} />
          <PrefilledValue label="Date" value={slot.date} />
          <PrefilledValue
            label="Time"
            value={formatTimelineTimeRange(slot.startTime, slot.endTime)}
          />
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <AmenityFormField
          label="Booking Type"
          required
          error={errors.bookingType}
        >
          <select
            value={values.bookingType}
            onChange={(event) => onChange('bookingType', event.target.value)}
            aria-invalid={Boolean(errors.bookingType)}
            className={`${amenityInputClasses} ${
              errors.bookingType
                ? 'border-rose-300 focus:border-rose-500'
                : ''
            }`}
          >
            <option value="">Select booking type</option>
            {ADMIN_BOOKING_TYPES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </AmenityFormField>

        <AmenityFormField label="Guest Count" error={errors.guestCount}>
          <input
            type="number"
            min="0"
            value={values.guestCount}
            onChange={(event) => onChange('guestCount', event.target.value)}
            aria-invalid={Boolean(errors.guestCount)}
            className={`${amenityInputClasses} ${
              errors.guestCount
                ? 'border-rose-300 focus:border-rose-500'
                : ''
            }`}
          />
        </AmenityFormField>
      </div>

      {amenity.allowPrivateBooking && (
        <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">
              Private Booking
            </p>
            <p className="mt-0.5 text-xs font-semibold text-slate-400">
              Reserve the amenity exclusively for this booking.
            </p>
          </div>
          <AmenityStatusToggle
            checked={values.isPrivateBooking}
            onChange={(isPrivateBooking) =>
              onChange('isPrivateBooking', isPrivateBooking)
            }
            ariaLabel="Set private booking"
          />
        </div>
      )}
    </FormSection>
  );
}
