import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle } from 'lucide-react';

import { workOrdersApi } from '../../features/workOrders/workOrdersApi';
import { Failure, ModalShell, whenText } from './triageParts';

// A supervisor putting the job on themselves.
//
// **Why this is not the picker next door.** Ruling R1 shut leadership out of
// every candidate flow there is — `dispatch_candidates` filters to
// `rank = 'member'`, so a supervisor is not in the assign picker's list, not on
// the open board, not pinged and not auto-booked. That was the product owner's
// instruction and it is not being softened here. R8 is the door they asked for
// beside it: *"it sholdnt be something seen in normal routine workflow … it is
// available at any time though but as a seperate button"* — an exception, always
// reachable, never the ordinary way work moves.
//
// So the banner is the whole design of this screen. It does not warn about a
// consequence to somebody else (nobody's consent is being overridden — the
// supervisor is assigning themselves), it names the *norm being stepped
// outside*: technicians do this work, and a department whose supervisor is on
// the tools is a department that is short of hires. `POST /work-orders/{id}/
// take-up` carries no `staffAssignmentId` at all — `take_up_work_order` resolves
// the assignee from `auth.uid()` — so there is nothing on this modal to choose
// and nothing to get wrong; the only question is yes or no.
//
// **The hour is the job's, and this modal does not move it.** `take_up` mirrors
// `force_assign`'s slot rule: the overlap constraint is partial on
// `scheduled_start_at is not null`, so a job with no hour cannot be assigned to
// anybody, the supervisor included. The RPC accepts an optional slot; v1 sends
// none and says where the hour is set instead, the same sentence and the same
// destination `AssignPickerModal` uses for the same state.

export default function TakeUpModal({ order, onClose }) {
  const queryClient = useQueryClient();

  const takeUp = useMutation({
    mutationFn: () => workOrdersApi.takeUp(order.id),
    onSuccess: () => {
      // Same re-read as the force-assign: the job leaves "Open job requests" for
      // "Assigned, work pending" the instant this succeeds, and which bucket a
      // row belongs in is the server's answer and never this screen's guess.
      void queryClient.invalidateQueries({ queryKey: ['supervisor-triage'] });
      void queryClient.invalidateQueries({ queryKey: ['work-orders'] });
      onClose();
    },
  });

  const scheduled = whenText(order.scheduledStartAt);
  const unscheduled = !order.scheduledStartAt;

  return (
    <ModalShell
      title="Take this job yourself"
      subtitle={order.complaintTitle || order.skillName || 'Work order'}
      onClose={onClose}
    >
      <p className="flex gap-2 rounded-xl bg-amber-50 px-4 py-3 text-[11px] font-semibold text-amber-800">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span>
          Jobs normally go to your technicians — this assigns it to you.
        </span>
      </p>

      <dl className="space-y-1.5 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
        <div className="flex gap-2 text-[11px] font-semibold">
          <dt className="w-20 shrink-0 text-slate-400">Job</dt>
          <dd className="min-w-0 text-slate-700">
            {order.complaintTitle || 'Work with no complaint title'}
          </dd>
        </div>
        {order.skillName ? (
          <div className="flex gap-2 text-[11px] font-semibold">
            <dt className="w-20 shrink-0 text-slate-400">Trade</dt>
            <dd className="min-w-0 text-slate-700">{order.skillName}</dd>
          </div>
        ) : null}
        {order.locationText ? (
          <div className="flex gap-2 text-[11px] font-semibold">
            <dt className="w-20 shrink-0 text-slate-400">Where</dt>
            <dd className="min-w-0 text-slate-700">{order.locationText}</dd>
          </div>
        ) : null}
        <div className="flex gap-2 text-[11px] font-semibold">
          <dt className="w-20 shrink-0 text-slate-400">When</dt>
          <dd className="min-w-0 text-slate-700">
            {scheduled ? `Booked for ${scheduled}` : 'No time set yet'}
          </dd>
        </div>
      </dl>

      {unscheduled ? (
        <p className="text-[11px] font-semibold text-slate-500">
          This job has no hour on it yet, and nobody can be booked onto one —
          yourself included, because the hour is what a clashing booking is
          checked against. Set a time in the work-order queue first, then come
          back here.
        </p>
      ) : (
        <p className="text-[11px] font-semibold text-slate-500">
          The job becomes yours straight away and the resident is told to expect
          you. It shows up in your own calendar like any other booking, and it
          leaves the department&apos;s open pile.
        </p>
      )}

      <Failure error={takeUp.error} />

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={unscheduled || takeUp.isPending}
          onClick={() => takeUp.mutate()}
          className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50"
        >
          {takeUp.isPending ? 'Taking it up…' : 'Take up this job — assign it to me'}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600"
        >
          Cancel
        </button>
      </div>
    </ModalShell>
  );
}
