import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRightLeft, Check, X } from 'lucide-react';

import { complaintRoutingApi } from '../routingApi';
import { QUERY_POLICIES } from '../../../lib/api/queryClient';

// "This isn't ours" — waiting on the manager who has to answer.
//
// **Only the manager sees this.** A supervisor can see the request they raised,
// as `openRequestId` on the complaint itself; this queue is an inbox, and an
// inbox belongs to whoever has to empty it.
//
// The manager answering is the manager of the department **giving the complaint
// up**, never the one receiving it. Authorizing on the destination would let the
// manager of B reach into A and help themselves to A's work — the same
// authorize-on-the-wrong-end mistake `department_hiring.py` warns about, and the
// RPC refuses it regardless of what this screen offers.
//
// Renders nothing when the queue is empty, rather than an empty state. A
// dashboard that permanently shows "no requests" trains people to stop reading
// the space where the requests would be.

export default function ChangeRequests({ departmentId }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState('');

  const requests = useQuery({
    queryKey: ['departments', departmentId, 'change-requests'],
    queryFn: () => complaintRoutingApi.changeRequests(departmentId),
    ...QUERY_POLICIES.list,
    enabled: Boolean(departmentId),
  });

  const decide = useMutation({
    mutationFn: ({ complaintId, requestId, decision, toDepartmentId }) =>
      complaintRoutingApi.decideChange(complaintId, requestId, {
        decision,
        toDepartmentId,
      }),
    onSuccess: () => {
      setError('');
      queryClient.invalidateQueries({ queryKey: ['departments', departmentId] });
    },
    onError: (err) =>
      setError(err?.message || 'That request could not be answered.'),
  });

  const rows = requests.data ?? [];
  if (!departmentId || rows.length === 0) return null;

  return (
    <section className="space-y-2 rounded-2xl border border-amber-100 bg-amber-50 p-5">
      <div className="flex items-center gap-2">
        <ArrowRightLeft className="h-4 w-4 text-amber-700" />
        <p className="text-xs font-extrabold text-amber-900">
          Complaints your supervisors say are not ours
        </p>
      </div>

      {error && (
        <p className="text-[11px] font-bold text-rose-600" role="alert">
          {error}
        </p>
      )}

      {rows.map((request) => (
        <div
          key={request.id}
          className="flex items-start justify-between gap-3 rounded-xl bg-white/70 px-3.5 py-2.5"
        >
          <div className="min-w-0">
            <p className="truncate text-[11px] font-bold text-amber-900">
              {request.complaintTitle}
            </p>
            <p className="text-[10px] font-semibold text-amber-700">
              {request.requestedBy}
              {request.reason ? ` — “${request.reason}”` : ''}
            </p>
            <p className="mt-0.5 text-[10px] font-semibold text-amber-600">
              {request.toDepartmentName
                ? `Suggested: ${request.toDepartmentName}`
                : 'No destination suggested — accepting returns it to the administrator'}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              disabled={decide.isPending}
              onClick={() =>
                decide.mutate({
                  complaintId: request.complaintId,
                  requestId: request.id,
                  decision: 'accept',
                  toDepartmentId: request.toDepartmentId || null,
                })
              }
              className="rounded-lg bg-emerald-600 p-1.5 text-white disabled:bg-slate-300"
              aria-label={`Accept the move for ${request.complaintTitle}`}
            >
              <Check className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              disabled={decide.isPending}
              onClick={() =>
                decide.mutate({
                  complaintId: request.complaintId,
                  requestId: request.id,
                  decision: 'reject',
                  toDepartmentId: null,
                })
              }
              className="rounded-lg p-1.5 text-amber-700 hover:bg-amber-100"
              aria-label={`Decline the move for ${request.complaintTitle}`}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      ))}
    </section>
  );
}
