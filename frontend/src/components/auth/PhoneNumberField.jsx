import React from 'react';
import { Phone } from 'lucide-react';

export default function PhoneNumberField({ value, onChange, disabled = false }) {
  return (
    <div className="space-y-1">
      <label
        htmlFor="admin-phone"
        className="text-[11px] font-bold text-slate-500 uppercase tracking-wider"
      >
        Mobile Number
      </label>
      <div className="flex rounded-xl border border-slate-200 bg-slate-50 focus-within:border-indigo-500 focus-within:bg-white transition-all overflow-hidden">
        <span className="flex items-center gap-2 border-r border-slate-200 px-3.5 text-sm font-semibold text-slate-500">
          <Phone className="w-4 h-4 text-slate-400" />
          +91
        </span>
        <input
          id="admin-phone"
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          value={value}
          onChange={onChange}
          disabled={disabled}
          placeholder="98765 43210"
          className="min-w-0 flex-1 bg-transparent px-4 py-3 text-sm focus:outline-none text-slate-700 placeholder:text-slate-400 font-medium disabled:cursor-not-allowed"
        />
      </div>
    </div>
  );
}
