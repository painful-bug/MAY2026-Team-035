import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Archive, Eye } from 'lucide-react';

import ComplaintDetailModal from './ComplaintDetailModal';
import { Chip, Empty, Failure, IconButton, whenText } from './triageParts';
import { PageHeading } from '../../features/security/components/Primitives';
import { complaintRoutingApi } from '../../features/complaints/routingApi';
import { supervisedEngagement } from '../../lib/staffVocabulary';
import { workerApi } from '../../features/worker/workerApi';
import { categoryChipClass, priorityChipClass, priorityLabel } from '../../lib/triageDisplay';

// The archive: every complaint of this department that ended, read-only
// (amendment 3, ruling B2).
//
// **Why the labels here are not `complaintStatusLabel`'s.** The wire folds
// `closed` into "Resolved" everywhere else, because the frontend's status
// vocabulary has no fourth word and a live queue does not care how a thing will
// end. This screen exists *because* the end conditions differ — resolved is a
// supervisor's word still awaiting the resident, closed is the resident
// confirming it, cancelled is neither — so the amendment freezes three distinct
// labels for this one screen and nothing else adopts them. That is why
// `END_STATES` is local rather than a change to `lib/triageDisplay.js`.
//
// **The read is the whole department's queue, filtered here.** `GET
// /departments/{id}/complaints` takes one `?status=` at most and the archive
// wants three, so it is called bare and the ended rows are kept client-side.
// Unpaginated — accepted and recorded as backlog (W1), not worked around.
//
// **Nothing on this screen writes.** The only interaction is the eye, which
// opens the existing detail popup with `readOnly` so even the note composer is
// unmounted. The full timeline, internal notes included, still renders — that
// look-back is the screen's purpose.

const END_STATES = Object.freeze({
  resolved: {
    label: 'Resolved — awaiting the resident',
    chip: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  },
  closed: {
    label: 'Closed — confirmed',
    chip: 'bg-teal-50 text-teal-700 ring-teal-200',
  },
  cancelled: {
    label: 'Cancelled',
    chip: 'bg-slate-100 text-slate-500 ring-slate-200',
  },
});

const FILTERS = Object.freeze([
  { value: 'everything', label: 'Everything' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
  { value: 'cancelled', label: 'Cancelled' },
]);

// Newest ending first; a row an older backend never stamped `resolvedAt` on
// falls back to when it was raised rather than to the bottom of the list.
const endedWhen = (row) => {
  const stamp = new Date(row?.resolvedAt || row?.createdAt || 0).getTime();
  return Number.isNaN(stamp) ? 0 : stamp;
};

export default function CompletedWork() {
  const [filter, setFilter] = useState('everything');
  const [open, setOpen] = useState(null);

  const snapshot = useQuery({
    queryKey: ['worker-snapshot'],
    queryFn: workerApi.snapshot,
  });
  const engagement = supervisedEngagement(snapshot.data?.communities);
  const departmentId = engagement?.departmentId || null;

  const complaints = useQuery({
    queryKey: ['departments', departmentId, 'complaints'],
    queryFn: () => complaintRoutingApi.departmentComplaints(departmentId),
    enabled: Boolean(departmentId),
  });

  if (snapshot.isLoading) {
    return <p className="text-xs font-semibold text-slate-400">Loading…</p>;
  }

  if (!engagement) {
    return (
      <p className="rounded-2xl border border-slate-100 bg-white p-6 text-xs font-semibold text-slate-500">
        Completed work is shown to supervisors. You are on a roster as a
        technician, and your work arrives as jobs on the dashboard instead.
      </p>
    );
  }

  const ended = (complaints.data ?? [])
    .filter((row) => END_STATES[row?.status])
    .sort((a, b) => endedWhen(b) - endedWhen(a));
  const rows = filter === 'everything' ? ended : ended.filter((row) => row.status === filter);

  return (
    <div className="space-y-5">
      <PageHeading
        title="Completed work"
        description={
          engagement.departmentName
            ? `${engagement.departmentName} — everything that ended, kept for looking back`
            : 'Everything that ended, kept for looking back'
        }
      />

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by end condition">
        {FILTERS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={filter === option.value}
            onClick={() => setFilter(option.value)}
            className={`rounded-full px-3.5 py-1.5 text-[11px] font-bold transition-colors ${
              filter === option.value
                ? 'bg-slate-900 text-white'
                : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {complaints.isLoading ? (
        <p className="text-xs font-semibold text-slate-400">Reading the archive…</p>
      ) : complaints.isError ? (
        <Failure error={complaints.error} />
      ) : rows.length === 0 ? (
        <Empty icon={Archive}>
          {filter === 'everything'
            ? 'Nothing has ended yet. A complaint arrives here when it is resolved, confirmed closed, or cancelled.'
            : 'Nothing ended this way yet.'}
        </Empty>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {rows.map((complaint) => {
            const endState = END_STATES[complaint.status];
            const subtitle = [
              complaint.raisedBy || 'Somebody in this community',
              complaint.unitCode,
              complaint.location,
            ].filter(Boolean).join(' · ');
            const raised = whenText(complaint.createdAt);
            const endedAt = whenText(complaint.resolvedAt);
            const meta = [
              raised ? `Raised ${raised}` : null,
              endedAt ? `ended ${endedAt}` : null,
            ].filter(Boolean).join(' · ');
            return (
              <article
                key={complaint.id}
                className="space-y-3 rounded-2xl border border-slate-100 bg-white p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-extrabold text-slate-800">
                      {complaint.title}
                    </h3>
                    {subtitle ? (
                      <p className="mt-0.5 truncate text-[11px] font-semibold text-slate-400">
                        {subtitle}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1.5">
                    <Chip className={priorityChipClass(complaint.priority)}>
                      {priorityLabel(complaint.priority)}
                    </Chip>
                    {complaint.category ? (
                      <Chip className={categoryChipClass(complaint.category)}>
                        {complaint.category}
                      </Chip>
                    ) : null}
                  </div>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  <Chip className={endState.chip}>{endState.label}</Chip>
                </div>

                {meta ? <p className="text-[11px] font-bold text-slate-400">{meta}</p> : null}

                <div className="flex items-center border-t border-slate-50 pt-3">
                  <IconButton
                    label={`View details of ${complaint.title}`}
                    icon={Eye}
                    onClick={() => setOpen(complaint)}
                  />
                </div>
              </article>
            );
          })}
        </div>
      )}

      {open ? (
        <ComplaintDetailModal
          complaintId={open.id}
          fallback={{
            title: open.title,
            subtitle: [open.raisedBy, open.unitCode].filter(Boolean).join(' · '),
            priority: open.priority,
            category: open.category,
            status: open.status,
            location: open.location,
          }}
          readOnly
          // The popup is part of this screen, so it speaks this screen's
          // labels: the wire's closed→Resolved folding stops at the archive's
          // edge, popup included (orchestrator ruling on amendment 3).
          statusLabel={END_STATES[open.status]?.label}
          onClose={() => setOpen(null)}
        />
      ) : null}
    </div>
  );
}
