import React from 'react';

export default function SegmentedToggle({
  label,
  options,
  value,
  onChange,
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
        {label}
      </legend>
      <div className="grid grid-cols-2 rounded-xl border border-slate-200 bg-slate-50 p-1">
        {options.map((option) => {
          const isSelected = option.value === value;

          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isSelected}
              onClick={() => onChange(option.value)}
              className={`rounded-lg px-3 py-2.5 text-xs font-bold transition-all sm:text-sm ${
                isSelected
                  ? 'bg-white text-indigo-700 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
