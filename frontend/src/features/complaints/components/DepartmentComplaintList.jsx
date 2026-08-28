import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ArrowRightLeft, Clock3 } from 'lucide-react';

import { complaintRoutingApi } from '../routingApi';
import { QUERY_POLICIES } from '../../../lib/api/queryClient';
import { Empty, Pill } from '../../security/components/Primitives';

// One department's complaints, and what the reader may do about them.
//
// **One component for two roles**, because they act on the same rows and
// disagree about exactly one thing: a manager may move a complaint out, a
// supervisor may only ask them to. `canMove` is that one thing. Two components
// would have meant two ideas of what a complaint looks like, and the one that
// got a fix would be whichever the author of the day opened.
//
// The list itself is the manager's answer to the notification they now receive
// when a complaint is routed to their department. Before `complaint_department_routing` there was no
// such notification and no such screen: `notify_community_staff` told *every*
// manager about *every* complaint and sent them to `/admin/complaints`, which
// their portal has no route for.

// All six words the check constraint admits, so no status renders an untinted
// pill. `acknowledged` shares `in_progress`'s tone because the resident already
// reads both as "In Progress".
const STATUS_TONES = {
  open: 'bg-amber-50 text-amber-700',
  acknowledged: 'bg-blue-50 text-blue-700',
  in_progress: 'bg-blue-50 text-blue-700',
  resolved: 'bg-emerald-50 text-emerald-700',
  closed: 'bg-teal-50 text-teal-700',
  cancelled: 'bg-slate-100 text-slate-500',
};

// A complaint that ended is not moved between departments any more — offering
// the transfer controls on it would let somebody file a request nobody can act
// on (amendment 3, rider R1).
const ENDED_STATUSES = ['resolved', 'closed', 'cancelled'];

const PRIORITY_TONES = {
  high: 'bg-rose-50 text-rose-700',
  medium: 'bg-amber-50 text-amber-700',
  low: 'bg-slate-100 text-slate-600',
};

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs ' +
  'font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

function formatDate(value) {
  if (!value) return null;
  return new Date(value).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
  });
}

export default function DepartmentComplaintList({
  departmentId,
  canMove,
  highlightId = null,
}) {
  const queryClient = useQueryClient();
  const [movingId, setMovingId] = useState(null);
  const [draft, setDraft] = useState({ departmentId: '', reason: '' });
  const [error, setError] = useState('');

  const complaints = useQuery({
    queryKey: ['departments', departmentId, 'complaints'],
    queryFn: () => complaintRoutingApi.departmentComplaints(departmentId),
    ...QUERY_POLICIES.list,
    enabled: Boolean(departmentId),
  });

  // Every department in the community, so the destination is a name and not a
  // UUID typed from memory. `GET /departments` is admin-only and carries roster
  // counts, categories, hours and skills — `GET /department-options` exists
  // precisely so this dropdown did not become a reason to widen that.
  const departments = useQuery({
    queryKey: ['department-options'],
    queryFn: () => complaintRoutingApi.departmentOptions(),
    ...QUERY_POLICIES.reference,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['departments', departmentId] });
    setMovingId(null);
    setDraft({ departmentId: '', reason: '' });
    setError('');
  };

  const move = useMutation({
    mutationFn: ({ complaintId, toDepartmentId }) =>
      complaintRoutingApi.assignDepartment(complaintId, toDepartmentId),
    onSuccess: refresh,
    onError: (err) => setError(err?.message || 'That complaint could not be moved.'),
  });

  const request = useMutation({
    mutationFn: ({ complaintId, payload }) =>
      complaintRoutingApi.requestChange(complaintId, payload),
    onSuccess: refresh,
    onError: (err) => setError(err?.message || 'That request could not be raised.'),
  });

  if (!departmentId) return null;

  const rows = complaints.data ?? [];

  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-extrabold text-slate-800">Complaints</h2>
        <p className="text-[10px] font-semibold text-slate-400">
          {rows.length} in this department
        </p>
      </div>

      <p className="mt-1 text-[10px] font-semibold leading-relaxed text-slate-400">
        Routed here by the complaint&apos;s category, or by the resident naming
        this department, or by an administrator allotting it.
        {canMove
          ? ' You can move one that is not yours.'
          : ' If one is not yours, ask your manager to move it.'}
      </p>

      {error && (
        <p className="mt-3 text-[11px] font-bold text-rose-600" role="alert">
          {error}
        </p>
      )}

      {complaints.isLoading ? (
        <p className="mt-4 text-xs font-semibold text-slate-400">Loading…</p>
      ) : rows.length === 0 ? (
        <div className="mt-4">
          <Empty>No complaints have been routed to this department.</Empty>
        </div>
      ) : (
        <div className="mt-4 space-y-2">
          {rows.map((complaint) => (
            <article
              key={complaint.id}
              // The one the notification was about. Ringed rather than filtered
              // to: a manager who followed a link still wants the rest of the
              // queue in view, and a list of one hides the fact that there are
              // nine more waiting.
              className={
                complaint.id === highlightId
                  ? 'rounded-xl border-2 border-indigo-400 bg-indigo-50/40 p-3.5'
                  : 'rounded-xl border border-slate-100 p-3.5'
              }
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-xs font-extrabold text-slate-800">
                    {complaint.title}
                  </p>
                  <p className="mt-0.5 text-[10px] font-semibold text-slate-400">
                    {complaint.raisedBy}
                    {complaint.unitCode ? ` · ${complaint.unitCode}` : ''}
                    {complaint.category ? ` · ${complaint.category}` : ''}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  {complaint.priority && (
                    <Pill className={PRIORITY_TONES[complaint.priority]}>
                      {complaint.priority}
                    </Pill>
                  )}
                  <Pill className={STATUS_TONES[complaint.status]}>
                    {complaint.status?.replace('_', ' ')}
                  </Pill>
                </div>
              </div>

              {complaint.description && (
                <p className="mt-2 line-clamp-2 text-[11px] font-semibold text-slate-500">
                  {complaint.description}
                </p>
              )}

              <div className="mt-2.5 flex flex-wrap items-center gap-3">
                {complaint.dueAt && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-bold text-slate-400">
                    <Clock3 className="h-3 w-3" />
                    Due {formatDate(complaint.dueAt)}
                  </span>
                )}

                {/* A transfer is already waiting on somebody. Offering the
                    button again would let a supervisor file a second request
                    and learn about it from a unique-index violation. And an
                    ended row offers nothing at all: there is no department
                    question left to ask about it. */}
                {ENDED_STATUSES.includes(complaint.status) ? null : complaint.openRequestId ? (
                  <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-700">
                    <AlertTriangle className="h-3 w-3" />
                    A move has been requested
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      setMovingId(
                        movingId === complaint.id ? null : complaint.id
                      );
                      setError('');
                    }}
                    className="inline-flex items-center gap-1 text-[10px] font-bold text-indigo-600 hover:text-indigo-700"
                  >
                    <ArrowRightLeft className="h-3 w-3" />
                    {canMove ? 'Move to another department' : 'Not our department'}
                  </button>
                )}
              </div>

              {movingId === complaint.id && !ENDED_STATUSES.includes(complaint.status) && (
                <form
                  className="mt-3 space-y-2 rounded-xl bg-slate-50 p-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (canMove) {
                      if (!draft.departmentId.trim()) {
                        setError('Name the department it should go to.');
                        return;
                      }
                      move.mutate({
                        complaintId: complaint.id,
                        toDepartmentId: draft.departmentId.trim(),
                      });
                      return;
                    }
                    request.mutate({
                      complaintId: complaint.id,
                      payload: {
                        toDepartmentId: draft.departmentId.trim() || null,
                        reason: draft.reason.trim() || null,
                      },
                    });
                  }}
                >
                  <label className="block">
                    <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500">
                      Department
                      {canMove ? '' : ' — leave blank if you do not know'}
                    </span>
                    <select
                      className={inputClass}
                      value={draft.departmentId}
                      onChange={(event) =>
                        setDraft({ ...draft, departmentId: event.target.value })
                      }
                    >
                      {/* A supervisor may legitimately choose nothing: "this
                          isn't ours" is worth saying without knowing whose it
                          is, and the manager can accept it back into triage.
                          A manager moving it must name somewhere. */}
                      <option value="">
                        {canMove ? 'Choose a department…' : 'I do not know'}
                      </option>
                      {(departments.data ?? [])
                        .filter((option) => option.id !== departmentId)
                        .map((option) => (
                          <option key={option.id} value={option.id}>
                            {option.name}
                          </option>
                        ))}
                    </select>
                  </label>

                  {!canMove && (
                    <label className="block">
                      <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500">
                        Why
                      </span>
                      <input
                        className={inputClass}
                        value={draft.reason}
                        placeholder="Not a plumbing job"
                        onChange={(event) =>
                          setDraft({ ...draft, reason: event.target.value })
                        }
                      />
                    </label>
                  )}

                  <div className="flex items-center gap-2">
                    <button
                      type="submit"
                      disabled={move.isPending || request.isPending}
                      className="rounded-lg bg-indigo-600 px-3 py-1.5 text-[10px] font-bold text-white disabled:bg-slate-300"
                    >
                      {canMove ? 'Move it' : 'Ask my manager'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setMovingId(null)}
                      className="rounded-lg px-3 py-1.5 text-[10px] font-bold text-slate-500 hover:bg-slate-100"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
