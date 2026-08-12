import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { securityApi } from '../../features/security/securityApi';
import ExportButton from '../../features/security/components/ExportButton';
import {
  Empty,
  ErrorText,
  Loading,
  PageHeading,
  Pill,
} from '../../features/security/components/Primitives';
import {
  SHIFT_STATUS_STYLES,
  shortDateTime,
} from '../../features/security/components/vocabulary';

// **This route is a contract, not a convenience.** `0040`'s `schedule_security_shift`
// sends every rostered guard a `shift.scheduled` notification whose `url` is
// `/security/shifts`, and it has done so since Step 7. Until this file existed,
// clicking that notification landed on nothing.
//
// A guard sees their own shifts here even in a community whose gate they do not
// staff, because `0040`'s read policy on `security_shifts` allows
// `is_own_staff_assignment` in addition to the community predicate.
//
// End Shift is the one PATCH on this surface a plain guard may make: `{status}`
// alone, on a shift that is theirs. Sending any second field would escalate the
// request to a security-manager permission and come back 403 — which is why the
// button sends exactly one key and the reschedule controls live in the manager
// portal instead.
//
// **`?shift=` is the second half of that contract.** `0043`'s
// `security_shift.assigned` links the guard a shift was handed *to*, carrying
// its id. Arriving at a fortnight of rows with nothing marking the one the
// notification was about is the same defect as arriving at the wrong page, one
// step later: the link technically worked and the user still cannot see what
// they were told.

const WINDOW_DAYS = 7;

function ShiftCard({ shift, highlighted = false, onStart, onEnd, busy = false, innerRef }) {
  return (
    <article
      ref={innerRef}
      className={`rounded-2xl border bg-white p-5 shadow-sm ${
        highlighted
          ? 'border-indigo-300 ring-2 ring-indigo-500 ring-offset-2'
          : 'border-slate-100'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Pill className={SHIFT_STATUS_STYLES[shift.status]}>{shift.status}</Pill>
            <span className="text-xs font-bold text-slate-800">
              {shift.postName || 'Post not set'}
            </span>
          </div>
          <p className="mt-2 text-sm font-bold text-slate-900">
            {shortDateTime(shift.startsAt)} — {shortDateTime(shift.endsAt)}
          </p>
          <p className="mt-1 text-[11px] font-semibold text-slate-400">
            {shift.guardName || 'Guard not named'}
            {shift.guardJobTitle ? ` · ${shift.guardJobTitle}` : ''}
          </p>
          {shift.notes ? (
            <p className="mt-1 text-[11px] font-semibold text-slate-500">{shift.notes}</p>
          ) : null}
        </div>

        <div className="flex shrink-0 gap-2">
          {shift.status === 'scheduled' ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => onStart(shift.id)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
            >
              Start shift
            </button>
          ) : null}
          {shift.status === 'active' ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => onEnd(shift.id)}
              className="rounded-xl bg-indigo-600 px-3 py-2 text-[11px] font-bold text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              End shift
            </button>
          ) : null}
        </div>
      </div>
    </article>
  );
}

export default function Shifts() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  // The id `0043`'s notification carries. Null on every other arrival.
  const linkedId = searchParams.get('shift');

  const dismissLink = useCallback(() => {
    const next = new URLSearchParams(searchParams);
    next.delete('shift');
    // `replace` so dismissing a highlight is not a back-button step of its own.
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  // A week either side: enough to see the shift just finished and the one
  // coming, without paging a list the server caps at 200 anyway.
  const { from, to } = useMemo(() => {
    const now = Date.now();
    const day = 24 * 60 * 60 * 1000;
    return {
      from: new Date(now - WINDOW_DAYS * day).toISOString(),
      to: new Date(now + WINDOW_DAYS * day).toISOString(),
    };
  }, []);

  const [note, setNote] = useState('');

  const shifts = useQuery({
    queryKey: ['security', 'shifts', { from, to }],
    queryFn: () => securityApi.shifts({ from, to }),
  });

  const rows = useMemo(() => shifts.data || [], [shifts.data]);
  const linkedIsOnScreen = Boolean(linkedId) && rows.some((row) => row.id === linkedId);

  // **Only when the fortnight above did not already contain it.** A departure is
  // scheduled (`0045`), so the shift handed over can be weeks out; but widening
  // the window is not the fix, because the list is capped at 200 rows ordered by
  // start and a wider range on a busy gate would truncate away the row asked
  // for. `?shiftId=` asks for one row and no window at all.
  const linked = useQuery({
    queryKey: ['security', 'shifts', { shiftId: linkedId }],
    queryFn: () => securityApi.shifts({ shiftId: linkedId }),
    enabled: Boolean(linkedId) && shifts.isSuccess && !linkedIsOnScreen,
  });
  const linkedShift = linked.data?.[0];

  const highlighted = useRef(null);
  useEffect(() => {
    if (!linkedIsOnScreen) return;
    highlighted.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [linkedId, linkedIsOnScreen]);

  const endShift = useMutation({
    mutationFn: (shiftId) => securityApi.updateShift(shiftId, { status: 'completed' }),
    onSuccess: () => {
      setNote('Shift ended.');
      queryClient.invalidateQueries({ queryKey: ['security', 'shifts'] });
    },
  });

  const startShift = useMutation({
    mutationFn: (shiftId) => securityApi.updateShift(shiftId, { status: 'active' }),
    onSuccess: () => {
      setNote('Shift started.');
      queryClient.invalidateQueries({ queryKey: ['security', 'shifts'] });
    },
  });

  const busy = startShift.isPending || endShift.isPending;
  const cardActions = { onStart: startShift.mutate, onEnd: endShift.mutate, busy };

  return (
    <div className="space-y-6">
      <PageHeading
        title="Shifts"
        description="The roster for this gate, a week either side of today."
        action={<ExportButton dataset="shifts" from={from} to={to} />}
      />

      {note ? (
        <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
          {note}
        </p>
      ) : null}

      {linkedId ? (
        <section className="rounded-2xl border border-indigo-100 bg-indigo-50/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[11px] font-extrabold uppercase tracking-wider text-indigo-700">
              From your notification
            </p>
            <button
              type="button"
              onClick={dismissLink}
              className="rounded-xl border border-indigo-200 px-3 py-1.5 text-[11px] font-bold text-indigo-700 hover:bg-white"
            >
              Dismiss
            </button>
          </div>

          <ErrorText error={linked.error} />

          {linkedIsOnScreen ? (
            <p className="mt-2 text-xs font-semibold text-indigo-900">
              Highlighted on the roster below.
            </p>
          ) : null}

          {!linkedIsOnScreen && linked.isPending ? <Loading /> : null}

          {linkedShift ? (
            <>
              <p className="mt-2 mb-3 text-xs font-semibold text-indigo-900">
                This one falls outside the fortnight shown below.
              </p>
              <ShiftCard shift={linkedShift} highlighted {...cardActions} />
            </>
          ) : null}

          {!linkedIsOnScreen && linked.isSuccess && !linkedShift ? (
            <p className="mt-2 text-xs font-semibold text-indigo-900">
              That shift is no longer on the roster you can see — it may have been
              handed on again, or cancelled.
            </p>
          ) : null}
        </section>
      ) : null}

      <ErrorText error={shifts.error} />
      <ErrorText error={endShift.error} />
      <ErrorText error={startShift.error} />
      {shifts.isPending ? <Loading /> : null}
      {!shifts.isPending && !shifts.error && rows.length === 0 ? (
        <Empty>No shifts on the roster for this fortnight.</Empty>
      ) : null}

      <div className="space-y-3">
        {rows.map((shift) => (
          <ShiftCard
            key={shift.id}
            shift={shift}
            highlighted={shift.id === linkedId}
            innerRef={shift.id === linkedId ? highlighted : undefined}
            {...cardActions}
          />
        ))}
      </div>

      <p className="text-[11px] font-semibold text-slate-400">
        Starting and ending your own shift is yours to do. Rescheduling, cancelling or
        assigning a post is the security manager's.
      </p>
    </div>
  );
}
