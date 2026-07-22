import React from 'react';
import AmenityStatusToggle from '../AmenityStatusToggle.jsx';

export default function ToggleField({ label, description, checked, onChange }) {
  return (
    <div className="flex min-h-20 items-center justify-between gap-4 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
      <div>
        <p className="text-xs font-extrabold text-slate-700">{label}</p>
        <p className="mt-1 text-[11px] font-medium leading-relaxed text-slate-400">
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
