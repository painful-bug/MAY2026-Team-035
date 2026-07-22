import React from 'react';

export const amenityInputClasses =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm font-medium text-slate-700 placeholder:text-slate-400 transition-all focus:border-indigo-500 focus:bg-white focus:outline-none';

export default function AmenityFormField({
  label,
  required = false,
  error,
  children,
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
        {label}
        {required && <span className="ml-0.5 text-rose-600">*</span>}
      </label>
      {children}
      {error && (
        <p role="alert" className="text-[10px] font-semibold text-rose-600">
          {error}
        </p>
      )}
    </div>
  );
}
