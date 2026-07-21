import React from 'react';

export default function LedgerSummaryCard({
  label,
  value,
  caption,
  icon: Icon,
  iconClasses,
}) {
  return (
    <article className="rounded-2xl border border-slate-100 bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            {label}
          </p>
          <p className="mt-2 truncate text-2xl font-extrabold tracking-tight text-slate-800">
            {value}
          </p>
          <p className="mt-1 text-[11px] font-semibold text-slate-400">
            {caption}
          </p>
        </div>
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${iconClasses}`}
        >
          <Icon className="h-4 w-4" />
        </span>
      </div>
    </article>
  );
}
