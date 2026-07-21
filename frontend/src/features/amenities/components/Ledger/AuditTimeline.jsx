import React from 'react';

const formatAuditDate = (timestamp) =>
  new Date(timestamp).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });

export default function AuditTimeline({ entries }) {
  if (entries.length === 0) {
    return (
      <p className="rounded-xl bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-400">
        No audit events recorded.
      </p>
    );
  }

  return (
    <ol className="space-y-3">
      {entries.map((entry) => (
        <li key={entry.id} className="flex gap-3">
          <div className="flex flex-col items-center">
            <span className="mt-1 h-2.5 w-2.5 rounded-full bg-indigo-500" />
            <span className="mt-1 h-full w-px bg-slate-100 last:hidden" />
          </div>
          <div className="min-w-0 flex-1 pb-2">
            <p className="text-xs font-extrabold text-slate-700">
              {entry.label}
            </p>
            <p className="mt-0.5 text-[10px] font-semibold text-slate-400">
              {formatAuditDate(entry.timestamp)}
              {entry.actor ? ` · ${entry.actor}` : ''}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
