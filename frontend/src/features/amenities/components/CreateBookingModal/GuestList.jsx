import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { amenityInputClasses } from '../AmenityFormField.jsx';
import FormSection from '../booking/FormSection.jsx';

export default function GuestList({ guests, onAdd, onChange, onRemove }) {
  return (
    <FormSection
      title="Guest list"
      description="Optional contact details for guests included in this booking."
    >
      {guests.length === 0 ? (
        <p className="rounded-xl bg-slate-50 px-4 py-4 text-center text-xs font-semibold text-slate-400">
          No guest details added.
        </p>
      ) : (
        <div className="space-y-3">
          {guests.map((guest, index) => (
            <div
              key={guest.id}
              className="grid gap-3 rounded-xl bg-slate-50 p-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
            >
              <label className="space-y-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Guest Name
                </span>
                <input
                  type="text"
                  value={guest.name}
                  onChange={(event) =>
                    onChange(index, 'name', event.target.value)
                  }
                  className={`${amenityInputClasses} bg-white`}
                />
              </label>
              <label className="space-y-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Contact Number
                </span>
                <input
                  type="tel"
                  value={guest.contactNumber}
                  onChange={(event) =>
                    onChange(index, 'contactNumber', event.target.value)
                  }
                  className={`${amenityInputClasses} bg-white`}
                />
              </label>
              <button
                type="button"
                onClick={() => onRemove(index)}
                aria-label={`Remove guest ${index + 1}`}
                className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={onAdd}
        className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50"
      >
        <Plus className="h-4 w-4" />
        Add Guest
      </button>
    </FormSection>
  );
}
