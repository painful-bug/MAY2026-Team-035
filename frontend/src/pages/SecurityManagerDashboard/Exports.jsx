import { useState } from 'react';
import ExportButton from '../../features/security/components/ExportButton';
import { PageHeading } from '../../features/security/components/Primitives';
import {
  EXPORT_DATASETS,
  inputClass,
  labelClass,
} from '../../features/security/components/vocabulary';

// `US-3.6` — "retention, six months, one year, or longer".
//
// There is no retention *policy* to configure here and that is not an omission:
// nothing this project writes is ever aged out, so the story's requirement is
// answered by an unbounded date range rather than by a setting. Leaving both
// dates empty exports everything the server will return (5000 rows).

export default function Exports() {
  const [range, setRange] = useState({ from: '', to: '' });
  const from = range.from ? new Date(`${range.from}T00:00:00`).toISOString() : undefined;
  const to = range.to ? new Date(`${range.to}T23:59:59`).toISOString() : undefined;

  return (
    <div className="space-y-6">
      <PageHeading
        title="Exports"
        description="Any register as a spreadsheet, over any period. Oldest row first."
      />

      <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className={labelClass} htmlFor="exports-from">
              From
            </label>
            <input
              id="exports-from"
              type="date"
              value={range.from}
              onChange={(event) =>
                setRange((current) => ({ ...current, from: event.target.value }))
              }
              className={`${inputClass} mt-1`}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="exports-to">
              To
            </label>
            <input
              id="exports-to"
              type="date"
              value={range.to}
              onChange={(event) => setRange((current) => ({ ...current, to: event.target.value }))}
              className={`${inputClass} mt-1`}
            />
          </div>
          <p className="text-[11px] font-semibold text-slate-400">
            Leave both empty for everything on record.
          </p>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {EXPORT_DATASETS.map(([dataset, label]) => (
            <div
              key={dataset}
              className="rounded-2xl border border-slate-100 bg-slate-50 p-4"
            >
              <p className="text-xs font-bold text-slate-800">{label}</p>
              <div className="mt-3">
                <ExportButton dataset={dataset} from={from} to={to} label="Download" />
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
