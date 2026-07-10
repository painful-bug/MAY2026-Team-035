import React from 'react';

export default function SectionCard({ icon: Icon, title, description, children }) {
  return (
    <section className="rounded-2xl border border-slate-100 bg-slate-50/60 p-5 sm:p-6">
      <div className="mb-5 flex items-start gap-3">
        {Icon && (
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
            <Icon className="h-4.5 w-4.5" />
          </div>
        )}
        <div className="space-y-1">
          <h2 className="text-sm font-extrabold text-slate-800">{title}</h2>
          {description && (
            <p className="text-xs font-medium leading-relaxed text-slate-500">
              {description}
            </p>
          )}
        </div>
      </div>
      {children}
    </section>
  );
}
