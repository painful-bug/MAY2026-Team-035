import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Inbox } from 'lucide-react';

import { complaintRoutingApi } from '../../features/complaints/routingApi';
import { Empty, Pill } from '../../features/security/components/Primitives';

// Complaints nothing could route, and the administrator who allots them.
//
// **A separate page rather than a panel on `/admin/complaints`.** That screen is
// a teammate's, and this is a different question: theirs is "how is this
// complaint going?", this is "whose is it?". A complaint leaves this queue the
// moment it is answered, so the two lists barely overlap.
//
// **What lands here**, and none of it is a special case in the code — all three
// are just the routing rule in `complaint_department_routing` finding nothing:
//
//   * the category names no department, which is what "Other" means;
//   * the category is mapped to *several* departments, so the rule refuses to
//     guess between them;
//   * the resident said "Not sure", or named a department that no longer exists.
//
// The second is worth knowing about: `department_categories` has a composite
// primary key, so one category may legally belong to two departments. A guess
// there would go wrong invisibly — only the department that *didn't* get the
// complaint could ever notice — so it becomes a question here instead.

const PRIORITY_TONES = {
  high: 'bg-rose-50 text-rose-700',
  medium: 'bg-amber-50 text-amber-700',
  low: 'bg-slate-100 text-slate-600',
};

const inputClass =
  'rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold ' +
  'text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

export default function ComplaintTriage() {
  const queryClient = useQueryClient();
  const [choices, setChoices] = useState({});
  const [error, setError] = useState('');

  const complaints = useQuery({
    queryKey: ['unassigned-complaints'],
    queryFn: complaintRoutingApi.unassigned,
  });

  const departments = useQuery({
    queryKey: ['department-options'],
    queryFn: complaintRoutingApi.departmentOptions,
  });

  const allot = useMutation({
    mutationFn: ({ complaintId, departmentId }) =>
      complaintRoutingApi.assignDepartment(complaintId, departmentId),
    onSuccess: () => {
      setError('');
      queryClient.invalidateQueries({ queryKey: ['unassigned-complaints'] });
    },
    onError: (err) => setError(err?.message || 'That complaint could not be allotted.'),
  });

  const rows = complaints.data ?? [];
  const options = departments.data ?? [];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          Complaint triage
        </h1>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          Complaints the category catalogue could not route. Give each one a
          department and it moves to that department&apos;s own queue.
        </p>
      </div>

      {error && (
        <p className="text-[11px] font-bold text-rose-600" role="alert">
          {error}
        </p>
      )}

      <section className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        {complaints.isLoading ? (
          <p className="text-xs font-semibold text-slate-400">Loading…</p>
        ) : rows.length === 0 ? (
          <Empty>
            Nothing is waiting. Every complaint has a department — which usually
            means the category catalogue is doing its job.
          </Empty>
        ) : (
          <div className="space-y-2">
            {rows.map((complaint) => (
              <article
                key={complaint.id}
                className="rounded-xl border border-slate-100 p-3.5"
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
                  {complaint.priority && (
                    <Pill className={PRIORITY_TONES[complaint.priority]}>
                      {complaint.priority}
                    </Pill>
                  )}
                </div>

                {complaint.description && (
                  <p className="mt-2 line-clamp-2 text-[11px] font-semibold text-slate-500">
                    {complaint.description}
                  </p>
                )}

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <select
                    className={inputClass}
                    value={choices[complaint.id] || ''}
                    onChange={(event) =>
                      setChoices({ ...choices, [complaint.id]: event.target.value })
                    }
                  >
                    <option value="">Choose a department…</option>
                    {options.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={!choices[complaint.id] || allot.isPending}
                    onClick={() =>
                      allot.mutate({
                        complaintId: complaint.id,
                        departmentId: choices[complaint.id],
                      })
                    }
                    className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-[11px] font-bold text-white disabled:bg-slate-300"
                  >
                    <Inbox className="h-3.5 w-3.5" />
                    Allot
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
