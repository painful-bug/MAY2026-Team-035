import { useState } from 'react';
import ExportButton from '../../features/security/components/ExportButton';
import IncidentPanel from '../../features/security/components/IncidentPanel';
import { PageHeading } from '../../features/security/components/Primitives';
import { inputClass, labelClass } from '../../features/security/components/vocabulary';

export default function Incidents() {
  const [range, setRange] = useState({ from: '', to: '' });
  const from = range.from ? new Date(`${range.from}T00:00:00`).toISOString() : undefined;
  const to = range.to ? new Date(`${range.to}T23:59:59`).toISOString() : undefined;

  return (
    <div className="space-y-6">
      <PageHeading
        title="Incidents"
        description="Anything that happened at or around the gate. High and critical reach the committee immediately."
      />

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className={labelClass} htmlFor="incidents-from">
            From
          </label>
          <input
            id="incidents-from"
            type="date"
            value={range.from}
            onChange={(event) => setRange((current) => ({ ...current, from: event.target.value }))}
            className={`${inputClass} mt-1`}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="incidents-to">
            To
          </label>
          <input
            id="incidents-to"
            type="date"
            value={range.to}
            onChange={(event) => setRange((current) => ({ ...current, to: event.target.value }))}
            className={`${inputClass} mt-1`}
          />
        </div>
        <ExportButton dataset="incidents" from={from} to={to} />
      </div>

      <IncidentPanel mode="report" from={from} to={to} />
    </div>
  );
}
