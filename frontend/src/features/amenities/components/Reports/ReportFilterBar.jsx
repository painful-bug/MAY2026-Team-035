import React from 'react';
import { RotateCcw } from 'lucide-react';
import { bookingStatusLabel } from '../../constants/bookingStatuses.js';
import { REPORT_ALL_FILTER } from '../../constants/amenityReports.js';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';
import DateRangePicker from './DateRangePicker.jsx';

function FilterSelect({ label, value, options, onChange }) {
  return (
    <AmenityFormField label={label}>
      {/* `AmenityFormField`'s caption is a bare `<label>` with nothing tying it
          to the control, so the select had no accessible name at all — it read
          as "combo box" to a screen reader. */}
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={amenityInputClasses}
      >
        <option value={REPORT_ALL_FILTER}>All</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </AmenityFormField>
  );
}

export default function ReportFilterBar({
  filters,
  options,
  onChange,
  onReset,
}) {
  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-extrabold text-slate-800">
            Report Filters
          </h2>
          <p className="mt-1 text-[11px] font-semibold text-slate-400">
            Filters update the summary and recent activity.
          </p>
        </div>
        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-bold text-slate-500 transition-colors hover:bg-slate-50"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset
        </button>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="xl:col-span-2">
          <DateRangePicker
            startDate={filters.startDate}
            endDate={filters.endDate}
            onChange={onChange}
          />
        </div>
        <FilterSelect
          label="Amenity"
          value={filters.amenityId}
          options={options.amenities}
          onChange={(value) => onChange('amenityId', value)}
        />
        <FilterSelect
          label="Booking Status"
          value={filters.bookingStatus}
          options={options.bookingStatuses.map((status) => ({
            value: status,
            label: bookingStatusLabel(status),
          }))}
          onChange={(value) => onChange('bookingStatus', value)}
        />
      </div>
    </section>
  );
}
