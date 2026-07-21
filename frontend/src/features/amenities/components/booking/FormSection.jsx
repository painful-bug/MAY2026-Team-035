import React from 'react';

export default function FormSection({ title, description, children }) {
  return (
    <section className="space-y-4 rounded-2xl border border-slate-100 p-4">
      <div>
        <h3 className="text-sm font-extrabold text-slate-800">{title}</h3>
        {description && (
          <p className="mt-0.5 text-[11px] font-medium text-slate-400">
            {description}
          </p>
        )}
      </div>
      {children}
    </section>
  );
}
