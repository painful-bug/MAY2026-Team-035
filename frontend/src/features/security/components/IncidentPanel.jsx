import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Plus } from 'lucide-react';
import { securityApi } from '../securityApi';
import {
  Empty,
  ErrorText,
  GateModal,
  Loading,
  Pill,
} from './Primitives';
import {
  INCIDENT_CATEGORIES,
  INCIDENT_STATUSES,
  INCIDENT_STATUS_STYLES,
  SEVERITIES,
  SEVERITY_STYLES,
  inputClass,
  labelClass,
  shortDateTime,
} from './vocabulary';

// Incidents are the one part of the gate three different people touch: the
// guard who files one, the security manager who triages it, and the admin the
// notification deep-links here (`0040` sends `high` and `critical` to
// `/admin/security/incidents`). One panel, two modes, because the list and the
// status controls are identical and only the report form is not.
//
// Every gate role may PATCH an incident — that is `0040`'s rule, not a
// simplification here. A guard acknowledging what they walked past is the
// normal case, and requiring a manager for it would mean the record lags the
// event by a shift.

export default function IncidentPanel({ mode = 'report', from, to }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState('');
  const [severity, setSeverity] = useState('');
  const [reporting, setReporting] = useState(false);

  const filters = { from, to, status: status || undefined, severity: severity || undefined };
  const incidents = useQuery({
    queryKey: ['security', 'incidents', filters],
    queryFn: () => securityApi.incidents(filters),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['security', 'incidents'] });

  const record = useMutation({
    mutationFn: (payload) => securityApi.recordIncident(payload),
    onSuccess: () => {
      setReporting(false);
      invalidate();
    },
  });

  const update = useMutation({
    mutationFn: ({ incidentId, payload }) => securityApi.updateIncident(incidentId, payload),
    onSuccess: invalidate,
  });

  const rows = incidents.data || [];

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          className={`${inputClass} w-auto`}
        >
          <option value="">Any status</option>
          {INCIDENT_STATUSES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <select
          value={severity}
          onChange={(event) => setSeverity(event.target.value)}
          className={`${inputClass} w-auto`}
        >
          <option value="">Any severity</option>
          {SEVERITIES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        {mode === 'report' ? (
          <button
            type="button"
            onClick={() => setReporting(true)}
            className="ml-auto inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100"
          >
            <Plus className="h-4 w-4" />
            Report an incident
          </button>
        ) : null}
      </div>

      <ErrorText error={incidents.error} />
      <ErrorText error={update.error} />

      {incidents.isPending ? <Loading /> : null}

      {!incidents.isPending && !incidents.error && rows.length === 0 ? (
        <Empty>No incidents in this range. That is the good outcome.</Empty>
      ) : null}

      <div className="space-y-3">
        {rows.map((incident) => (
          <article
            key={incident.id}
            className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Pill className={SEVERITY_STYLES[incident.severity]}>
                    {incident.severity}
                  </Pill>
                  <Pill className={INCIDENT_STATUS_STYLES[incident.status]}>
                    {incident.status}
                  </Pill>
                  <span className="text-[11px] font-bold text-slate-400">
                    {incident.category}
                  </span>
                </div>
                <p className="mt-2 text-sm font-bold text-slate-900">{incident.summary}</p>
                {incident.details ? (
                  <p className="mt-1 text-xs font-semibold text-slate-500">{incident.details}</p>
                ) : null}
                <p className="mt-2 text-[11px] font-semibold text-slate-400">
                  {shortDateTime(incident.occurredAt)}
                  {incident.locationText ? ` · ${incident.locationText}` : ''}
                  {incident.postName ? ` · ${incident.postName}` : ''}
                  {incident.reportedByName ? ` · ${incident.reportedByName}` : ''}
                </p>
              </div>

              <div className="flex shrink-0 gap-2">
                {incident.status === 'open' ? (
                  <button
                    type="button"
                    disabled={update.isPending}
                    onClick={() =>
                      update.mutate({
                        incidentId: incident.id,
                        payload: { status: 'acknowledged' },
                      })
                    }
                    className="rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                  >
                    Acknowledge
                  </button>
                ) : null}
                {incident.status !== 'resolved' ? (
                  <button
                    type="button"
                    disabled={update.isPending}
                    onClick={() =>
                      update.mutate({
                        incidentId: incident.id,
                        payload: { status: 'resolved' },
                      })
                    }
                    className="rounded-xl bg-emerald-600 px-3 py-2 text-[11px] font-bold text-white hover:bg-emerald-700 disabled:opacity-60"
                  >
                    Resolve
                  </button>
                ) : (
                  <span className="self-center text-[11px] font-semibold text-slate-400">
                    Resolved {shortDateTime(incident.resolvedAt)}
                  </span>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>

      {reporting ? (
        <ReportForm
          onClose={() => setReporting(false)}
          onSubmit={(payload) => record.mutate(payload)}
          pending={record.isPending}
          error={record.error}
        />
      ) : null}
    </section>
  );
}

function ReportForm({ onClose, onSubmit, pending, error }) {
  const [form, setForm] = useState({
    summary: '',
    category: INCIDENT_CATEGORIES[0],
    severity: 'medium',
    details: '',
    locationText: '',
  });
  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <GateModal
      title="Report an incident"
      description="High and critical severities notify the community's admins and managers immediately."
      onClose={onClose}
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit({
            summary: form.summary.trim(),
            category: form.category,
            severity: form.severity,
            details: form.details.trim() || undefined,
            locationText: form.locationText.trim() || undefined,
          });
        }}
      >
        <div>
          <label className={labelClass} htmlFor="incident-summary">
            What happened
          </label>
          <input
            id="incident-summary"
            required
            maxLength={300}
            value={form.summary}
            onChange={set('summary')}
            placeholder="Alarm sounding on the third floor"
            className={`${inputClass} mt-1`}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={labelClass} htmlFor="incident-category">
              Category
            </label>
            <select
              id="incident-category"
              value={form.category}
              onChange={set('category')}
              className={`${inputClass} mt-1`}
            >
              {INCIDENT_CATEGORIES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass} htmlFor="incident-severity">
              Severity
            </label>
            <select
              id="incident-severity"
              value={form.severity}
              onChange={set('severity')}
              className={`${inputClass} mt-1`}
            >
              {SEVERITIES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className={labelClass} htmlFor="incident-location">
            Where
          </label>
          <input
            id="incident-location"
            maxLength={200}
            value={form.locationText}
            onChange={set('locationText')}
            placeholder="Block B, third floor"
            className={`${inputClass} mt-1`}
          />
        </div>

        <div>
          <label className={labelClass} htmlFor="incident-details">
            Details
          </label>
          <textarea
            id="incident-details"
            rows={4}
            maxLength={4000}
            value={form.details}
            onChange={set('details')}
            className={`${inputClass} mt-1`}
          />
        </div>

        {form.severity === 'high' || form.severity === 'critical' ? (
          <p className="flex items-start gap-2 rounded-xl border border-amber-100 bg-amber-50 p-3 text-[11px] font-semibold text-amber-800">
            <AlertTriangle className="mt-px h-4 w-4 shrink-0" />
            This notifies every admin and manager in the community as soon as you file it.
          </p>
        ) : null}

        <ErrorText error={error} />

        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={pending}
            className="flex-1 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
          >
            {pending ? 'Filing…' : 'File incident'}
          </button>
        </div>
      </form>
    </GateModal>
  );
}
