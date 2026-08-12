import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { AlertTriangle, Boxes, Droplets, ShieldCheck } from 'lucide-react';
import { securityApi } from '../../features/security/securityApi';
import {
  Empty,
  ErrorText,
  Loading,
  MetricCard,
  PageHeading,
  Pill,
} from '../../features/security/components/Primitives';
import {
  INCIDENT_STATUS_STYLES,
  SEVERITY_STYLES,
  SHIFT_STATUS_STYLES,
  shortDateTime,
} from '../../features/security/components/vocabulary';

// **There is no snapshot endpoint for the gate, and that was a decision** —
// `API.md` §19 says so explicitly. So this page fans out across four list reads
// and renders each independently: one failing leaves the other three on screen,
// which is the behaviour a snapshot would have taken away.

export default function Overview() {
  const { dayFrom, dayTo } = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setDate(end.getDate() + 1);
    return { dayFrom: start.toISOString(), dayTo: end.toISOString() };
  }, []);

  const movements = useQuery({
    queryKey: ['security', 'movements', { from: dayFrom, to: dayTo }],
    queryFn: () => securityApi.movements({ from: dayFrom, to: dayTo }),
  });
  const tankers = useQuery({
    queryKey: ['security', 'tankers', { onSite: true }],
    queryFn: () => securityApi.tankers({ onSite: true }),
  });
  const incidents = useQuery({
    queryKey: ['security', 'incidents', { status: 'open' }],
    queryFn: () => securityApi.incidents({ status: 'open' }),
  });
  const shifts = useQuery({
    queryKey: ['security', 'shifts', { from: dayFrom, to: dayTo }],
    queryFn: () => securityApi.shifts({ from: dayFrom, to: dayTo }),
  });

  const openIncidents = incidents.data || [];
  const todayShifts = shifts.data || [];
  const onDuty = todayShifts.filter((shift) => shift.status === 'active').length;

  return (
    <div className="space-y-6">
      <PageHeading
        title="Security operations"
        description="Today at the gate: what moved, who is on, and what is still open."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={Boxes}
          label="Movements today"
          value={movements.isPending ? '—' : (movements.data || []).length}
          detail={
            movements.error
              ? 'Could not be read'
              : `${(movements.data || []).filter((row) => row.isOutstanding).length} still out`
          }
        />
        <MetricCard
          icon={Droplets}
          tone="emerald"
          label="Tankers on site"
          value={tankers.isPending ? '—' : (tankers.data || []).length}
          detail={tankers.error ? 'Could not be read' : 'Arrived and not yet departed'}
        />
        <MetricCard
          icon={AlertTriangle}
          tone={openIncidents.length ? 'rose' : 'slate'}
          label="Open incidents"
          value={incidents.isPending ? '—' : openIncidents.length}
          detail={
            incidents.error
              ? 'Could not be read'
              : `${openIncidents.filter((row) => ['high', 'critical'].includes(row.severity)).length} high or critical`
          }
        />
        <MetricCard
          icon={ShieldCheck}
          tone="amber"
          label="Shifts today"
          value={shifts.isPending ? '—' : todayShifts.length}
          detail={shifts.error ? 'Could not be read' : `${onDuty} on duty now`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-extrabold text-slate-900">Today&rsquo;s roster</h2>
            <Link
              to="../roster"
              className="text-[11px] font-bold text-indigo-600 hover:text-indigo-700"
            >
              Manage
            </Link>
          </div>

          <div className="mt-4 space-y-3">
            {shifts.isPending ? <Loading /> : null}
            <ErrorText error={shifts.error} />
            {!shifts.isPending && !shifts.error && todayShifts.length === 0 ? (
              <Empty>Nobody is rostered today.</Empty>
            ) : null}
            {todayShifts.map((shift) => (
              <div
                key={shift.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50 p-3.5"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-slate-800">
                    {shift.guardName || 'Guard not named'}
                  </p>
                  <p className="mt-0.5 text-[11px] font-semibold text-slate-400">
                    {shift.postName || 'Post not set'} · {shortDateTime(shift.startsAt)} —{' '}
                    {shortDateTime(shift.endsAt)}
                  </p>
                </div>
                <Pill className={SHIFT_STATUS_STYLES[shift.status]}>{shift.status}</Pill>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-extrabold text-slate-900">Open incidents</h2>
            <Link
              to="../incidents"
              className="text-[11px] font-bold text-indigo-600 hover:text-indigo-700"
            >
              Triage
            </Link>
          </div>

          <div className="mt-4 space-y-3">
            {incidents.isPending ? <Loading /> : null}
            <ErrorText error={incidents.error} />
            {!incidents.isPending && !incidents.error && openIncidents.length === 0 ? (
              <Empty>Nothing open. That is the good outcome.</Empty>
            ) : null}
            {openIncidents.slice(0, 6).map((incident) => (
              <div
                key={incident.id}
                className="rounded-xl border border-slate-100 bg-slate-50 p-3.5"
              >
                <div className="flex items-center gap-2">
                  <Pill className={SEVERITY_STYLES[incident.severity]}>{incident.severity}</Pill>
                  <Pill className={INCIDENT_STATUS_STYLES[incident.status]}>
                    {incident.status}
                  </Pill>
                </div>
                <p className="mt-2 text-xs font-bold text-slate-800">{incident.summary}</p>
                <p className="mt-0.5 text-[11px] font-semibold text-slate-400">
                  {shortDateTime(incident.occurredAt)}
                  {incident.locationText ? ` · ${incident.locationText}` : ''}
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
