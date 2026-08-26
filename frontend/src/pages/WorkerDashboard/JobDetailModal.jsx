import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { QUERY_POLICIES } from '../../lib/api/queryClient';
import { MapPin, Phone, User, X } from 'lucide-react';
import { workerApi } from '../../features/worker/workerApi';
import { communityColor } from '../../lib/communityColor';

const when = new Intl.DateTimeFormat(undefined, {
  weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
});

// Every verb the worker holds over one job, in one place. `GET /worker/jobs/{id}`
// is a separate read from the list because the resident's name, flat and phone
// are only on the detail route -- a worker on their way to a door needs all
// three and a worker scrolling a finished month needs none.

const ACTION_LABEL = {
  accept: 'Accept this job',
  decline: 'Decline',
  start: 'Start work',
  complete: 'Mark complete',
  unable: 'Could not complete',
};

export default function JobDetailModal({ workOrderId, onClose }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');
  const [prompt, setPrompt] = useState(null);
  const job = useQuery({
    queryKey: ['worker-job', workOrderId],
    queryFn: () => workerApi.job(workOrderId),
    ...QUERY_POLICIES.detail,
    enabled: Boolean(workOrderId),
  });

  const act = useMutation({
    mutationFn: ({ action, text }) => {
      if (action === 'accept') return workerApi.acceptJob(workOrderId);
      if (action === 'decline') return workerApi.declineJob(workOrderId, text);
      if (action === 'start') return workerApi.startJob(workOrderId);
      if (action === 'complete') return workerApi.completeJob(workOrderId, text);
      return workerApi.reportJobFailure(workOrderId, text);
    },
    onSuccess: () => {
      // Everything on the portal is a projection of the same job rows, so one
      // action invalidates all of them rather than each screen guessing.
      for (const key of ['worker-snapshot', 'worker-jobs', 'worker-calendar', 'worker-job']) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      setPrompt(null);
      setNote('');
      onClose();
    },
  });

  const data = job.data;
  const colour = communityColor(data?.communityId);
  // `unable` requires a reason (min 3 chars server-side); decline and complete
  // do not. Asking for one anyway on decline is the difference between a
  // dispatcher who can see why an offer keeps bouncing and one who cannot.
  const needsText = prompt === 'decline' || prompt === 'complete' || prompt === 'unable';

  const run = (action) => {
    if (action === 'accept' || action === 'start') return act.mutate({ action });
    if (prompt !== action) return setPrompt(action);
    if (action === 'unable' && note.trim().length < 3) return undefined;
    return act.mutate({ action, text: note.trim() });
  };

  const actions = !data
    ? []
    : data.assignmentStatus === 'offered'
      ? (data.isForced ? ['accept'] : ['accept', 'decline'])
      : data.workOrderStatus === 'in_progress'
        ? ['complete', 'unable']
        : data.assignmentStatus === 'accepted' && data.workOrderStatus === 'scheduled'
          ? ['start', 'unable']
          : [];

  return (
    <div className="fixed inset-0 z-[80] flex items-end justify-center bg-slate-900/50 p-0 backdrop-blur-sm sm:items-center sm:p-6">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-t-3xl bg-white sm:rounded-3xl">
        <div className="sticky top-0 flex items-start justify-between gap-3 border-b border-slate-100 bg-white px-5 py-4">
          <div className="min-w-0">
            <p className="truncate text-base font-extrabold text-slate-900">
              {data?.complaintTitle || data?.skillName || 'Job'}
            </p>
            {data?.communityName && (
              <span className="mt-1 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500">
                <span className={`h-2 w-2 rounded-full ${colour.dot}`} />
                {data.communityName}
                {data.departmentName ? ` · ${data.departmentName}` : ''}
              </span>
            )}
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          {job.isPending && <p className="py-8 text-center text-sm font-semibold text-slate-400">Loading…</p>}
          {job.isError && (
            <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
              {job.error?.message || 'Could not load this job.'}
            </p>
          )}

          {data && (
            <>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-600">
                  {data.workOrderStatus?.replace(/_/g, ' ')}
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-600">
                  offer {data.assignmentStatus}
                </span>
                {data.priority === 'high' && (
                  <span className="rounded-full bg-rose-100 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-rose-700">
                    urgent
                  </span>
                )}
                {data.isForced && (
                  <span className="rounded-full bg-rose-100 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-rose-700">
                    Assigned — critical job
                  </span>
                )}
                {data.failedAttemptCount > 0 && (
                  <span className="rounded-full bg-amber-100 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-amber-800">
                    attempt {data.failedAttemptCount + 1}
                  </span>
                )}
              </div>

              {data.scheduledStartAt && (
                <p className="text-sm font-bold text-slate-800">
                  {when.format(new Date(data.scheduledStartAt))}
                  {data.scheduledEndAt
                    ? ` – ${new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date(data.scheduledEndAt))}`
                    : ''}
                </p>
              )}

              {data.complaintDescription && (
                <p className="whitespace-pre-line rounded-xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700">
                  {data.complaintDescription}
                </p>
              )}

              <div className="space-y-2 text-sm font-medium text-slate-700">
                {data.residentName && (
                  <p className="flex items-center gap-2">
                    <User className="h-4 w-4 text-slate-400" />
                    {data.residentName}
                    {data.residentUnitCode ? ` · ${data.residentUnitCode}` : ''}
                  </p>
                )}
                {data.residentPhoneE164 && (
                  <a href={`tel:${data.residentPhoneE164}`} className="flex items-center gap-2 font-bold text-indigo-600">
                    <Phone className="h-4 w-4" />
                    {data.residentPhoneE164}
                  </a>
                )}
                {data.locationText && (
                  <p className="flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-slate-400" />
                    {data.locationText}
                  </p>
                )}
              </div>

              {needsText && (
                <textarea
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  rows={3}
                  placeholder={
                    prompt === 'unable'
                      ? 'What stopped you? (required)'
                      : prompt === 'complete'
                        ? 'Any notes for the supervisor (optional)'
                        : 'Why are you turning this down? (optional)'
                  }
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium outline-none focus:border-indigo-400"
                />
              )}

              {act.isError && (
                <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
                  {act.error?.message || 'That did not work.'}
                </p>
              )}

              {actions.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {actions.map((action) => (
                    <button
                      key={action}
                      type="button"
                      disabled={act.isPending || (prompt === 'unable' && action === 'unable' && note.trim().length < 3)}
                      onClick={() => run(action)}
                      className={`flex-1 rounded-xl px-4 py-2.5 text-sm font-bold transition-colors disabled:opacity-50 ${
                        action === 'accept' || action === 'start' || action === 'complete'
                          ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                          : 'border border-slate-200 text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      {prompt === action && needsText ? 'Confirm' : ACTION_LABEL[action]}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
