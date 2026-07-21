import React from 'react';
import { WEEK_DAYS } from '../../constants/amenitySettings.js';

export default function DaySelector({ label, selectedDays, onToggle }) {
  return (
    <div className="space-y-2">
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <div className="flex flex-wrap gap-2">
        {WEEK_DAYS.map((day) => {
          const isSelected = selectedDays.includes(day);
          return (
            <button
              key={day}
              type="button"
              aria-pressed={isSelected}
              onClick={() => onToggle(day)}
              className={`rounded-xl border px-3 py-2 text-[11px] font-bold transition-colors ${
                isSelected
                  ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                  : 'border-slate-200 bg-slate-50 text-slate-500 hover:bg-white'
              }`}
            >
              {day.slice(0, 3)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
