import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle } from 'lucide-react';

import { workOrdersApi } from '../../features/workOrders/workOrdersApi';
import { Failure, ModalShell, whenText } from './triageParts';

// Putting somebody on a job whether they like it or not.
//
// **This screen's Assign is not the queue's Offer, and the words are different
// on purpose.** `WorkOrderTriage`'s form says "Offer job": it creates an
// `offered` assignment the worker may decline, and until they accept the job
// stays in the supervisor's "Open job requests". The product owner's ruling A4
// gave this surface the other one — `force: true`, the same mechanics the
// dispatch engine uses when every worker has declined a High complaint:
// `is_forced = true`, no Decline button on the worker's card, a
// `job_force_assigned` event, a `job.force_assigned` notification.
//
// A supervisor overriding the consent model should be reading that they are
// doing it. So the button says *Assign without asking*, the confirm line says
// the worker cannot decline, and no copy on this modal calls it an offer.
//
// **The candidate list is `GET /work-orders/{id}/candidates`** — the same
// ranked read the queue's offer form uses, workload and leave and all. Excluded
// candidates (they declined this job earlier) are shown greyed rather than
// hidden: on a forced assignment "who has already said no" is exactly the
// context the decision needs, and the engine itself force-assigns to somebody
// who declined.

export default function AssignPickerModal({ order, onClose }) {
  const queryClient = useQueryClient();
  const [chosen, setChosen] = useState(null);

  const candidates = useQuery({
    // The queue's own key shape, so a supervisor who was just on that screen
    // reads the same cached list rather than a second fetch of it.
    queryKey: ['work-orders', 'candidates', order.id, false],
    queryFn: () => workOrdersApi.candidates(order.id),
    // `dispatch_candidates` drops unscheduled jobs before it looks at anyone —
    // leave, availability windows, and clashing bookings are all checked
    // against the slot, so with no slot the answer is nobody, always. Don't
    // ask a question whose answer is fixed.
    enabled: Boolean(order.scheduledStartAt),
  });

  const assign = useMutation({
    mutationFn: (staffAssignmentId) =>
      workOrdersApi.assign(order.id, { staffAssignmentId, force: true }),
    onSuccess: () => {
      // The job moves from "Open job requests" to "Assigned, work pending", and
      // that move is the server's to make: a forced assignment is `accepted`
      // from the first instant, which is what *committed* means in the v2
      // bucketing. The page re-reads instead of moving the card itself.
      void queryClient.invalidateQueries({ queryKey: ['supervisor-triage'] });
      void queryClient.invalidateQueries({ queryKey: ['work-orders'] });
      onClose();
    },
  });

  const rows = candidates.data || [];
  const picked = rows.find((row) => row.staffAssignmentId === chosen) || null;

  return (
    <ModalShell
      title="Assign this job outright"
      subtitle={order.complaintTitle || order.skillName || 'Work order'}
      onClose={onClose}
    >
      <p className="flex gap-2 rounded-xl bg-amber-50 px-4 py-3 text-[11px] font-semibold text-amber-800">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span>
          This is not an offer. Whoever you pick is given the job and{' '}
          <b>cannot decline it</b>. They are notified straight away. To let
          somebody choose, offer the job from the work-order queue instead.
        </span>
      </p>

      {!order.scheduledStartAt ? (
        <p className="text-[11px] font-semibold text-slate-500">
          This job has no hour on it yet, and the roster can only be checked
          against one — leave, availability windows, and clashing bookings all
          depend on the slot. Set a time in the work-order queue first, then
          come back here.
        </p>
      ) : candidates.isPending ? (
        <p className="text-xs font-semibold text-slate-400">Reading the roster…</p>
      ) : candidates.isError ? (
        <Failure error={candidates.error} />
      ) : rows.length === 0 ? (
        <p className="text-xs font-semibold text-slate-500">
          Nobody on this department&apos;s roster is eligible for this job at
          this hour — they may lack the trade, be on leave, or already be booked
          over the slot. Hiring, another hour, or a change of trade on the job
          is the way out of that — not this button.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {rows.map((candidate) => {
            const selected = candidate.staffAssignmentId === chosen;
            return (
              <li key={candidate.staffAssignmentId}>
                <button
                  type="button"
                  onClick={() => setChosen(candidate.staffAssignmentId)}
                  aria-pressed={selected}
                  className={`flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                    selected ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 bg-white'
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-extrabold text-slate-800">
                      {candidate.displayName}
                    </span>
                    <span className="block truncate text-[11px] font-semibold text-slate-400">
                      {candidate.openJobs ?? 0} open{' '}
                      {candidate.openJobs === 1 ? 'job' : 'jobs'}
                      {candidate.awayUntil ? ` · away until ${whenText(candidate.awayUntil)}` : ''}
                      {candidate.excluded ? ' · declined this job earlier' : ''}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <Failure error={assign.error} />

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!chosen || assign.isPending}
          onClick={() => assign.mutate(chosen)}
          className="rounded-xl bg-rose-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50"
        >
          {assign.isPending
            ? 'Assigning…'
            : picked
              ? `Assign ${picked.displayName} — they cannot decline`
              : 'Assign without asking'}
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
