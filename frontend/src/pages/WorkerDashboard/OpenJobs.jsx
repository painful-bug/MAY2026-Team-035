import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Hand, Inbox } from 'lucide-react';
import { workerApi } from '../../features/worker/workerApi';
import { communityColor } from '../../lib/communityColor';

// The open-jobs board (product ruling 2026-08-23, C1-C3): every unclaimed job
// on the caller's department rosters, claimable on the spot.
//
// **The claim is a two-step press, and the second step says what it costs.**
// Ruling C2 makes taking a job instant and first-come-first-served — no
// approval sits between the tap and the commitment, so the confirm wording
// carries the whole of what a supervisor's offer flow would have told them:
// the job is theirs immediately, and the supervisor is told.
//
// **Losing the race is the ordinary case, not the edge one.** Two technicians
// reading the same board will sometimes press the same card. The server
// settles it under a row lock and answers the loser in a sentence — printed on
// the card, and then the refetch takes the card away, because the truthful
// board no longer has that job on it.
//
// **A job with no hour is still on the board (C3).** The "Time to be set"
// marker is drawn from the null slot rather than hidden by it; the hour is set
// afterwards in the supervisor's queue.

const when = new Intl.DateTimeFormat(undefined, {
  weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
});

function OpenJobCard({ job, refusal, confirming, onPress, onConfirm, onDismiss, claiming }) {
  const colour = communityColor(job.communityId);
  const subtitle = [job.departmentName, job.communityName].filter(Boolean).join(' · ');
  return (
    <article className={`rounded-2xl border border-slate-200 border-l-4 bg-white p-4 ${colour.bar}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-extrabold text-slate-900">
            {job.complaintTitle || job.skillName || 'Job'}
          </p>
          {subtitle ? (
            <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs font-semibold text-slate-500">
              <span className={`h-2 w-2 shrink-0 rounded-full ${colour.dot}`} />
              {subtitle}
            </p>
          ) : null}
        </div>
        {job.priority === 'high' && (
          <span className="shrink-0 rounded-full bg-rose-100 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-rose-700">
            urgent
          </span>
        )}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {job.skillName ? (
          <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-[10px] font-bold text-indigo-700">
            {job.skillName}
          </span>
        ) : null}
        <p className="text-xs font-bold tabular-nums text-slate-700">
          {job.scheduledStartAt ? when.format(new Date(job.scheduledStartAt)) : 'Time to be set'}
        </p>
      </div>

      {refusal ? (
        <p className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700">
          {refusal}
        </p>
      ) : null}

      {confirming ? (
        <div className="mt-3 rounded-xl border border-indigo-100 bg-indigo-50/60 p-3">
          <p className="text-xs font-semibold text-slate-700">
            Claiming makes this job yours immediately — no approval step — and
            the supervisor is told. Take it?
          </p>
          <div className="mt-2.5 flex gap-2">
            <button
              type="button"
              disabled={claiming}
              onClick={() => onConfirm(job.workOrderId)}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {claiming ? 'Claiming…' : 'Yes, it is mine'}
            </button>
            <button
              type="button"
              disabled={claiming}
              onClick={onDismiss}
              className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
            >
              Not now
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-3 border-t border-slate-50 pt-3">
          <button
            type="button"
            onClick={() => onPress(job.workOrderId)}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-xs font-bold text-white hover:bg-slate-700"
          >
            <Hand className="h-3.5 w-3.5" />
            Claim this job
          </button>
        </div>
      )}
    </article>
  );
}

export default function OpenJobs() {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(null);
  const [refusals, setRefusals] = useState({});

  // The snapshot answers "does anybody employ you", which decides which of the
  // two empty states an empty board means. Same key as the layout's query, so
  // react-query deduplicates the fetch.
  const snapshot = useQuery({ queryKey: ['worker-snapshot'], queryFn: workerApi.snapshot });
  const board = useQuery({ queryKey: ['worker-open-jobs'], queryFn: workerApi.openJobs });

  const claim = useMutation({
    mutationFn: (workOrderId) => workerApi.claimJob(workOrderId),
    onSuccess: () => {
      setConfirming(null);
      // The claimed job leaves the board and lands on the dashboard, so both
      // reads are stale the moment the claim returns.
      queryClient.invalidateQueries({ queryKey: ['worker-open-jobs'] });
      queryClient.invalidateQueries({ queryKey: ['worker-snapshot'] });
    },
    onError: (error, workOrderId) => {
      setConfirming(null);
      // The server's own sentence — "Somebody has already taken this job." is
      // the one worth printing verbatim — on the card, then refresh: the
      // truthful board no longer carries that job.
      setRefusals((prev) => ({
        ...prev,
        [workOrderId]: error?.message || 'Could not claim that job.',
      }));
      queryClient.invalidateQueries({ queryKey: ['worker-open-jobs'] });
    },
  });

  if (board.isPending || snapshot.isPending) {
    return <p className="py-16 text-center text-sm font-semibold text-slate-400">Reading the board…</p>;
  }
  if (board.isError) {
    return (
      <p className="rounded-2xl bg-rose-50 px-5 py-4 text-sm font-semibold text-rose-700">
        {board.error?.message || 'Could not read the open jobs.'}
      </p>
    );
  }

  const jobs = board.data ?? [];
  const communities = snapshot.data?.communities ?? [];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold text-slate-900">Open jobs</h1>
        <p className="mt-1 text-sm font-medium text-slate-500">
          Unclaimed work on your rosters. First to claim gets it.
        </p>
      </div>

      {jobs.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <Inbox className="mx-auto h-10 w-10 text-slate-300" />
          <p className="mt-4 text-sm font-bold text-slate-600">
            {communities.length === 0
              ? 'Jobs appear here once a community hires you.'
              : 'Nothing is waiting right now.'}
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {jobs.map((job) => (
            <OpenJobCard
              key={job.workOrderId}
              job={job}
              refusal={refusals[job.workOrderId]}
              confirming={confirming === job.workOrderId}
              claiming={claim.isPending && confirming === job.workOrderId}
              onPress={setConfirming}
              onConfirm={(workOrderId) => claim.mutate(workOrderId)}
              onDismiss={() => setConfirming(null)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
