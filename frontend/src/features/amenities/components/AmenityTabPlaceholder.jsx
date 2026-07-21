import React from 'react';

export default function AmenityTabPlaceholder({ title, message }) {
  return (
    <section className="flex min-h-64 items-center justify-center rounded-2xl border border-slate-100 bg-white p-6 text-center">
      <div className="max-w-md space-y-2">
        <p className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-600">
          {title}
        </p>
        <p className="text-sm font-semibold text-slate-400">{message}</p>
      </div>
    </section>
  );
}
