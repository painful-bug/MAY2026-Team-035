import React from 'react';

export default function SettingsCard({ icon: Icon, title, description, children }) {
  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
          <Icon className="h-5 w-5" />
        </span>
        <div>
          <h2 className="text-base font-extrabold text-slate-800">{title}</h2>
          <p className="mt-1 text-xs font-semibold leading-relaxed text-slate-400">
            {description}
          </p>
        </div>
      </div>
      <div className="mt-5 space-y-5">{children}</div>
    </section>
  );
}
