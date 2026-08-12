import { useState } from 'react';
import ExportButton from '../../features/security/components/ExportButton';
import IncidentPanel from '../../features/security/components/IncidentPanel';
import { PageHeading } from '../../features/security/components/Primitives';
import { inputClass, labelClass } from '../../features/security/components/vocabulary';

export default function ManagerIncidents() {
  const [range, setRange] = useState({ from: '', to: '' });
  const from = range.from ? new Date(`${range.from}T00:00:00`).toISOString() : undefined;
  const to = range.to ? new Date(`${range.to}T23:59:59`).toISOString() : undefined;

  return (
    <div className="space-y-6">
      <PageHeading
        title="Incident triage"
        description="Everything the gate has filed. Acknowledge what is being handled, resolve what is done."
      />

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className={labelClass} htmlFor="triage-from">
            From
          </label>
          <input
            id="triage-from"
            type="date"
            value={range.from}
            onChange={(event) => setRange((current) => ({ ...current, from: event.target.value }))}
            className={`${inputClass} mt-1`}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="triage-to">
            To
          </label>
          <input
            id="triage-to"
            type="date"
            value={range.to}
            onChange={(event) => setRange((current) => ({ ...current, to: event.target.value }))}
            className={`${inputClass} mt-1`}
          />
        </div>
        <ExportButton dataset="incidents" from={from} to={to} />
      </div>

      <IncidentPanel mode="triage" from={from} to={to} />
    </div>
  );
}
