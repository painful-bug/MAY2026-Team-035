import { useEffect, useState } from 'react';
// The approve sheet renders through a portal to document.body. Under /admin
// it sat inside AdminLayout's `<main class="animate-fade-in">` — a
// fill-forwards opacity animation keeps <main> a stacking context forever, so
// `z-[999]` was trapped at <main>'s own level and the sticky header's `z-40`
// painted above it. Same fix as the departments modals (Departments.jsx).
import { createPortal } from 'react-dom';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { QUERY_POLICIES } from '../../lib/api/queryClient';
import {
  ArrowLeft,
  Calendar,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  DoorOpen,
  MessageCircle,
  Phone,
  Search,
  Shuffle,
  X,
} from 'lucide-react';
import { hiringApi } from '../../features/hiring/hiringApi';
import { usePortalScope } from '../../features/hiring/usePortalScope';
import { openChatDock } from '../../features/messages/messagesApi';
import { rankLabel } from '../../lib/staffVocabulary';
import { useAuthStore } from '../../store/authStore';

// The employee page the doc asked for: tiles on the hiring screen open it, and
// the departure.requested notification deep-links straight to it. One person,
// three panels — who they are, what their week holds, and (when a departure is
// riding along) the decision: what would be stranded, who could take each item,
// approve at the requested date or a later one, or reject.

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

const dayText = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? null
    : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
};

const whenText = (value) => {
  if (!value) return 'no time set';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'no time set'
    : date.toLocaleString(undefined, {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    });
};

function Pill({ tone = 'bg-slate-100 text-slate-600', children }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-bold ${tone}`}>
      {children}
    </span>
  );
}

const STATUS_STYLES = {
  pending: 'bg-amber-50 text-amber-700',
  approved: 'bg-emerald-50 text-emerald-700',
  rejected: 'bg-rose-50 text-rose-700',
  cancelled: 'bg-slate-100 text-slate-500',
};

// Monday-started week window, stepped whole weeks at a time.
function weekRange(offset) {
  const now = new Date();
  const day = (now.getDay() + 6) % 7;
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - day + offset * 7);
  const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 7);
  return { from: start.toISOString(), to: end.toISOString(), start, end };
}

// Approve, with the date the manager actually means.
//
// The requested date is pre-selected because it is the ordinary case; "a later
// date" is the discretion the doc grants. A centred sheet rather than
// window.prompt, because a date is not a string somebody should type freehand.
function ApproveModal({ departure, busy, onApprove, onClose }) {
  const requested = departure.requestedEffectiveAt;
  const [mode, setMode] = useState('requested');
  const [date, setDate] = useState('');
  const [note, setNote] = useState('');

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  const submit = () => {
    if (mode === 'later' && !date) return;
    onApprove({
      decision: 'approve',
      note: note.trim() || null,
      effectiveAt: mode === 'later' ? new Date(`${date}T00:00:00`).toISOString() : null,
    });
  };

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Approve the leave"
      className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="max-h-[calc(100dvh-2rem)] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-extrabold text-slate-900">Approve the leave</h2>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Booked work from the leave date onward goes back to the pool for
              reassignment.
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-full bg-slate-100 p-2">
            <X className="h-4 w-4 text-slate-500" />
          </button>
        </div>

        <div className="mt-5 space-y-2">
          <label className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-xs font-bold text-slate-700">
            <input
              type="radio"
              checked={mode === 'requested'}
              onChange={() => setMode('requested')}
            />
            {requested ? `As requested — ${dayText(requested)}` : 'Immediately, as requested'}
          </label>
          <label className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-xs font-bold text-slate-700">
            <input type="radio" checked={mode === 'later'} onChange={() => setMode('later')} />
            On a later date
            {mode === 'later' && (
              <input
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
                className={`${inputClass} ml-auto max-w-[10rem]`}
              />
            )}
          </label>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Note (optional)"
            rows={2}
            className={inputClass}
          />
        </div>

        <button
          type="button"
          disabled={busy || (mode === 'later' && !date)}
          onClick={submit}
          className="mt-4 w-full rounded-xl bg-emerald-600 py-2.5 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {busy ? 'Approving…' : 'Approve'}
        </button>
      </div>
    </div>,
    document.body
  );
}

export default function EmployeeDetail() {
  // `staffId` still comes from the URL; the department and the portal base come
  // from `usePortalScope`, because this page is mounted under /admin, /manager
  // and /security-manager and the one link out of it has to lead back into
  // whichever of them the reader is in.
  const { staffId } = useParams();
  const { base: basePath, departmentId } = usePortalScope();
  const queryClient = useQueryClient();
  const communityId = useAuthStore(
    (state) => state.sessionContext?.membership?.community_id
  );
  const [weekOffset, setWeekOffset] = useState(0);
  const [showCoverage, setShowCoverage] = useState(false);
  const [approving, setApproving] = useState(false);

  const member = useQuery({
    queryKey: ['hiring', departmentId, 'staff', staffId],
    queryFn: () => hiringApi.staffMember(departmentId, staffId),
    ...QUERY_POLICIES.detail,
  });

  const range = weekRange(weekOffset);
  const schedule = useQuery({
    queryKey: ['hiring', departmentId, 'staff', staffId, 'schedule', range.from],
    queryFn: () => hiringApi.staffSchedule(departmentId, staffId, { from: range.from, to: range.to }),
    ...QUERY_POLICIES.detail,
  });

  const departure = member.data?.departure || null;
  const coverage = useQuery({
    queryKey: ['hiring', departmentId, 'departure', departure?.id, 'coverage'],
    queryFn: () => hiringApi.coverage(departmentId, departure.id),
    ...QUERY_POLICIES.detail,
    enabled: showCoverage && Boolean(departure),
  });

  // The roster feeds the successor select, same as the departures tab.
  const department = useQuery({
    queryKey: ['hiring', departmentId, 'roster'],
    queryFn: () => hiringApi.department(departmentId),
    ...QUERY_POLICIES.detail,
    enabled: Boolean(departure),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['hiring', departmentId] });
  };

  const reassign = useMutation({
    mutationFn: (payload) => hiringApi.reassign(departmentId, departure.id, payload),
    onSuccess: () => {
      invalidate();
      if (showCoverage) coverage.refetch();
    },
  });
  const decide = useMutation({
    mutationFn: (payload) => hiringApi.decideDeparture(departmentId, departure.id, payload),
    onSuccess: () => {
      setApproving(false);
      invalidate();
    },
  });
  const startDeparture = useMutation({
    mutationFn: (reason) => hiringApi.openDeparture(departmentId, { staffId, reason }),
    onSuccess: invalidate,
  });

  if (member.isLoading) {
    return <p className="text-sm font-semibold text-slate-500">Loading…</p>;
  }
  if (member.error) {
    return (
      <p role="alert" className="text-sm font-semibold text-rose-600">{member.error.message}</p>
    );
  }

  const person = member.data;
  const successors = (department.data?.staff || []).filter(
    (row) => row.id !== staffId && row.status === 'active'
  );
  const items = schedule.data || [];

  return (
    <div className="space-y-6">
      <div>
        <Link
          to={`${basePath}/departments/${departmentId}/hiring?tab=roster`}
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-indigo-600"
        >
          <ArrowLeft className="h-4 w-4" />Back to the roster
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">{person.name}</h1>
          <Pill tone={person.serviceProviderId ? 'bg-indigo-50 text-indigo-700' : undefined}>
            {person.serviceProviderId ? 'service partner' : 'roster name'}
          </Pill>
          {person.departureStatus ? (
            <Pill tone="bg-amber-50 text-amber-700">
              {person.departureEffectiveAt
                ? `leaving ${dayText(person.departureEffectiveAt)}`
                : 'leaving'}
            </Pill>
          ) : null}
        </div>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          {rankLabel(person.rank)}
          {person.role ? ` · ${person.role}` : ''}
          {person.shift ? ` · ${person.shift}` : ''}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[20rem_1fr]">
        {/* Identity */}
        <div className="space-y-4">
          <section className="space-y-3 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-400">
              Details
            </h2>
            {person.phone ? (
              <p className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                <Phone className="h-4 w-4 text-slate-400" />{person.phone}
              </p>
            ) : null}
            <p className="flex items-center gap-2 text-xs font-semibold text-slate-600">
              <Clock className="h-4 w-4 text-slate-400" />
              {person.openCommitmentCount} booked {person.openCommitmentCount === 1 ? 'item' : 'items'}
            </p>
            {/* Was "N open complaints" from `activeAssignmentCount`, which read
                two columns nothing writes and so said 0 for everybody, always
                (product ruling 5, 2026-08-21). The replacement is leadership's
                real number and is therefore only rendered for leadership — a
                technician's number is the booked-items line above. */}
            {person.supervisedWorkOrderCount > 0 ? (
              <p className="text-xs font-semibold text-slate-600">
                {person.supervisedWorkOrderCount} supervised {person.supervisedWorkOrderCount === 1 ? 'job' : 'jobs'}
              </p>
            ) : null}
            {person.membershipId ? (
              // Opens the chat dock's New-message view for this community —
              // the employee card's chat box. A roster name with no account
              // has nobody to deliver to, so no button.
              <button
                type="button"
                onClick={() => openChatDock({ communityId })}
                className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-indigo-200 py-2.5 text-xs font-bold text-indigo-700 hover:bg-indigo-50"
              >
                <MessageCircle className="h-4 w-4" />Message
              </button>
            ) : null}
            {!departure && person.status === 'active' ? (
              <button
                type="button"
                disabled={startDeparture.isPending}
                onClick={() => {
                  const reason = window.prompt('Why are they leaving? (optional)');
                  if (reason === null) return;
                  startDeparture.mutate(reason.trim() || null);
                }}
                className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
              >
                <DoorOpen className="h-4 w-4" />Start a departure
              </button>
            ) : null}
            {startDeparture.error ? (
              <p role="alert" className="text-xs font-semibold text-rose-600">
                {startDeparture.error.message}
              </p>
            ) : null}
          </section>

          {/* The decision, when there is one to make */}
          {departure ? (
            <section className="space-y-4 rounded-2xl border border-amber-100 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-400">
                  Departure
                </h2>
                <Pill tone={STATUS_STYLES[departure.status]}>{departure.status}</Pill>
              </div>
              <p className="text-xs font-bold text-amber-700">
                {departure.status === 'approved' && departure.effectiveAt
                  ? `Leaving ${dayText(departure.effectiveAt)}.`
                  : departure.requestedEffectiveAt
                    ? `Wants to leave ${dayText(departure.requestedEffectiveAt)}.`
                    : 'Wants to leave immediately.'}
              </p>
              {departure.reason ? (
                <p className="rounded-xl bg-slate-50 p-3 text-xs font-semibold text-slate-600">
                  “{departure.reason}”
                </p>
              ) : null}
              {departure.status === 'pending' ? (
                <>
                  <p className="text-[11px] font-semibold text-slate-500">
                    {departure.conflictCount === 0
                      ? 'Nothing booked would be stranded by this leave.'
                      : `${departure.conflictCount} booked ${departure.conflictCount === 1 ? 'item' : 'items'} would need reassignment — approval releases them to the pool.`}
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setApproving(true)}
                      className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-emerald-600 py-2.5 text-xs font-bold text-white hover:bg-emerald-700"
                    >
                      <Check className="h-4 w-4" />Approve…
                    </button>
                    <button
                      type="button"
                      disabled={decide.isPending}
                      onClick={() => {
                        const note = window.prompt('Why is this being refused? (optional)');
                        if (note === null) return;
                        decide.mutate({ decision: 'reject', note: note.trim() || null });
                      }}
                      className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2.5 text-xs font-bold text-slate-600 disabled:opacity-60"
                    >
                      <X className="h-4 w-4" />Reject
                    </button>
                  </div>
                </>
              ) : null}
              {decide.error ? (
                <p role="alert" className="text-xs font-semibold text-rose-600">
                  {decide.error.message}
                </p>
              ) : null}
            </section>
          ) : null}
        </div>

        {/* Schedule + coverage */}
        <div className="space-y-4">
          <section className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-slate-400">
                <Calendar className="h-4 w-4" />Schedule
              </h2>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setWeekOffset((value) => value - 1)}
                  className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-50"
                  aria-label="Previous week"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-[11px] font-bold text-slate-500">
                  {range.start.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                  {' – '}
                  {new Date(range.end.getTime() - 1).toLocaleDateString(undefined, {
                    day: 'numeric', month: 'short',
                  })}
                </span>
                <button
                  type="button"
                  onClick={() => setWeekOffset((value) => value + 1)}
                  className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-50"
                  aria-label="Next week"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>

            {schedule.isLoading ? (
              <p className="text-xs font-semibold text-slate-400">Loading…</p>
            ) : schedule.error ? (
              <p role="alert" className="text-xs font-semibold text-rose-600">
                {schedule.error.message}
              </p>
            ) : items.length === 0 ? (
              <p className="text-xs font-semibold text-slate-400">Nothing this week.</p>
            ) : (
              <ul className="space-y-2">
                {items.map((item) => (
                  <li
                    key={`${item.kind}:${item.itemId}`}
                    className="flex items-start justify-between gap-2 rounded-xl border border-slate-100 p-3"
                  >
                    <div>
                      <p className="text-xs font-extrabold text-slate-700">{item.title}</p>
                      <p className="text-[11px] font-semibold text-slate-400">
                        {whenText(item.startsAt)} · {item.status}
                      </p>
                    </div>
                    <Pill tone={item.kind === 'security_shift'
                      ? 'bg-sky-50 text-sky-700'
                      : 'bg-indigo-50 text-indigo-700'}
                    >
                      {item.kind === 'security_shift' ? 'shift' : 'job'}
                    </Pill>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {departure && departure.status === 'pending' ? (
            <section className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-400">
                  If they leave{' '}
                  {departure.requestedEffectiveAt
                    ? dayText(departure.requestedEffectiveAt)
                    : 'now'}
                </h2>
                <button
                  type="button"
                  onClick={() => setShowCoverage(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-indigo-700"
                >
                  <Search className="h-3.5 w-3.5" />Check coverage
                </button>
              </div>

              {!showCoverage ? (
                <p className="text-xs font-semibold text-slate-400">
                  Check who could take each item that would be stranded.
                </p>
              ) : coverage.isLoading ? (
                <p className="text-xs font-semibold text-slate-400">Checking…</p>
              ) : coverage.error ? (
                <p role="alert" className="text-xs font-semibold text-rose-600">
                  {coverage.error.message}
                </p>
              ) : (coverage.data || []).length === 0 ? (
                <p className="text-xs font-semibold text-emerald-600">
                  Nothing would be stranded.
                </p>
              ) : (
                <ul className="space-y-2">
                  {(coverage.data || []).map((item) => (
                    <li
                      key={`${item.kind}:${item.itemId}`}
                      className="space-y-2 rounded-xl border border-slate-100 p-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-xs font-extrabold text-slate-700">{item.title}</p>
                          <p className="text-[11px] font-semibold text-slate-400">
                            {whenText(item.startsAt)} · {item.status}
                          </p>
                        </div>
                        <Pill tone={item.kind === 'security_shift'
                          ? 'bg-sky-50 text-sky-700'
                          : 'bg-indigo-50 text-indigo-700'}
                        >
                          {item.kind === 'security_shift' ? 'shift' : 'job'}
                        </Pill>
                      </div>
                      {/* Zero is an answer, stated rather than errored. */}
                      {item.candidateCount === 0 ? (
                        <p className="text-[11px] font-bold text-rose-600">
                          No one can take this.
                        </p>
                      ) : (
                        <p className="text-[11px] font-semibold text-slate-500">
                          Could go to: {item.candidateNames.join(', ')}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={reassign.isPending || item.candidateCount === 0}
                          onClick={() => reassign.mutate({ kind: item.kind, itemId: item.itemId })}
                          className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white disabled:opacity-60"
                        >
                          <Shuffle className="h-3.5 w-3.5" />Hand over now
                        </button>
                        <select
                          className={`${inputClass} max-w-[14rem]`}
                          defaultValue=""
                          disabled={reassign.isPending}
                          onChange={(event) => {
                            if (!event.target.value) return;
                            reassign.mutate({
                              kind: item.kind,
                              itemId: item.itemId,
                              staffAssignmentId: event.target.value,
                            });
                            event.target.value = '';
                          }}
                        >
                          <option value="">…or pick someone</option>
                          {successors.map((row) => (
                            <option key={row.id} value={row.id}>{row.name}</option>
                          ))}
                        </select>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {reassign.error ? (
                <p role="alert" className="text-xs font-semibold text-rose-600">
                  {reassign.error.message}
                </p>
              ) : null}
            </section>
          ) : null}
        </div>
      </div>

      {approving && departure ? (
        <ApproveModal
          departure={departure}
          busy={decide.isPending}
          onApprove={(payload) => decide.mutate(payload)}
          onClose={() => setApproving(false)}
        />
      ) : null}
    </div>
  );
}
