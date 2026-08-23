import { useQuery } from '@tanstack/react-query';
import { Lock } from 'lucide-react';

import { triageApi } from '../../features/triage/triageApi';
import {
  categoryChipClass,
  complaintStatusChipClass,
  complaintStatusLabel,
  priorityChipClass,
  priorityLabel,
  reassignmentBadges,
  staffComplaintFields,
  timelineEntries,
} from '../../lib/triageDisplay';
import { NoteComposer } from './NoteComposer';
import { Chip, Failure, ModalShell, whenText } from './triageParts';

// The eye. One complaint, everything recorded about it, and the same buttons
// the card had.
//
// **Why the actions are repeated in here.** Amendment 2 asks for it and the
// reason is the reading order: a supervisor opens this popup precisely when the
// card did not tell them enough, and the answer to "now I know, do the thing"
// should not be "close this and find that card again". The buttons are the page
// 's own — passed in as a node, wired to the page's mutations — so there is one
// take-up in the app and not two that can drift.
//
// **The read is `GET /complaints/staff/complaints/{id}` and it is not the
// resident's DTO.** It answers `{complaint, events[]}` where `complaint` is the
// database row as Postgres wrote it (snake_case keys, storage vocabulary) and
// each event is a `complaint_events` row plus a rendered `message`.
// `lib/triageDisplay.js` holds that seam; nothing in this file reads a raw key.
//
// **The timeline here is longer than the resident's, deliberately.** Internal
// notes (`note_added` with `internal: true`) are dropped from the resident
// projection and shown here under a lock, which is the entire point of them.

export default function ComplaintDetailModal({
  complaintId,
  fallback = {},
  stage,
  actions,
  onClose,
}) {
  const detail = useQuery({
    queryKey: ['staff-complaint', complaintId],
    queryFn: () => triageApi.staffComplaintDetail(complaintId),
    enabled: Boolean(complaintId),
  });

  const complaint = staffComplaintFields(detail.data?.complaint);
  const events = timelineEntries(detail.data?.events);

  // The card's values are the fallback, not the second opinion: they came from
  // the same database a moment ago, and showing a blank header while the detail
  // loads would make the popup feel slower than the data is.
  const title = complaint.title || fallback.title || 'Complaint';
  const priority = complaint.priority || fallback.priority;
  const category = complaint.category || fallback.category;
  const status = complaint.status || fallback.status;
  const badges = reassignmentBadges({
    returnedToPoolAt: complaint.returnedToPoolAt,
    reopenedCount: complaint.reopenedCount,
    reroutedAt: fallback.reroutedAt,
  });

  return (
    <ModalShell title={title} subtitle={fallback.subtitle} onClose={onClose}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Chip className={priorityChipClass(priority)}>{priorityLabel(priority)}</Chip>
        {category ? <Chip className={categoryChipClass(category)}>{category}</Chip> : null}
        <Chip className={complaintStatusChipClass(status)}>{complaintStatusLabel(status)}</Chip>
        {badges.map((badge) => (
          <Chip key={badge} className="bg-amber-50 text-amber-700 ring-amber-200">{badge}</Chip>
        ))}
      </div>

      {stage ? (
        <p className="rounded-xl bg-slate-50 px-4 py-2.5 text-[11px] font-bold text-slate-600">
          {/* Which of the five sections this card sits in, said in words. The
              status chip above is the complaint's own state machine and the
              job's is a second one; "where is this on my screen" is neither. */}
          Stage · {stage}
        </p>
      ) : null}

      {detail.isPending ? (
        <p className="text-xs font-semibold text-slate-400">Reading the complaint…</p>
      ) : detail.isError ? (
        <Failure error={detail.error} />
      ) : (
        <>
          {complaint.description ? (
            <p className="whitespace-pre-line rounded-xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700">
              {complaint.description}
            </p>
          ) : (
            <p className="text-xs font-semibold text-slate-400">
              No description was written when this was raised.
            </p>
          )}

          <dl className="grid grid-cols-2 gap-3 text-[11px]">
            {[
              ['Where', complaint.location || fallback.location || '—'],
              ['Raised', whenText(complaint.createdAt) || '—'],
              ['Due', whenText(complaint.dueAt) || 'No deadline set'],
              [
                'Taken up',
                whenText(complaint.takenUpAt)
                  || (fallback.takenUpByName ? `by ${fallback.takenUpByName}` : 'Not yet'),
              ],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="font-bold uppercase tracking-wide text-slate-400">{label}</dt>
                <dd className="mt-0.5 font-semibold text-slate-700">{value}</dd>
              </div>
            ))}
          </dl>
        </>
      )}

      {actions ? (
        <div className="space-y-2 border-t border-slate-100 pt-4">
          <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">
            What you can do from here
          </p>
          {actions}
        </div>
      ) : null}

      <div className="border-t border-slate-100 pt-4">
        <NoteComposer complaintId={complaintId} />
      </div>

      <div className="border-t border-slate-100 pt-4">
        <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">Timeline</p>
        {detail.isPending ? null : events.length === 0 ? (
          <p className="mt-2 text-xs font-semibold text-slate-400">
            Nothing has been recorded against this complaint yet.
          </p>
        ) : (
          <ol className="mt-3 space-y-0">
            {events.map((event, index) => (
              <li key={event.id} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span
                    className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${
                      index === events.length - 1 ? 'bg-indigo-600' : 'bg-slate-300'
                    }`}
                  />
                  {index < events.length - 1 ? (
                    <span className="h-full min-h-8 w-px bg-slate-200" />
                  ) : null}
                </div>
                <div className="min-w-0 pb-4">
                  <p className="flex items-center gap-1.5 text-xs font-extrabold text-slate-700">
                    {event.label}
                    {event.internal ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-slate-500">
                        <Lock className="h-2.5 w-2.5" />
                        Internal
                      </span>
                    ) : null}
                  </p>
                  {event.message ? (
                    <p className="mt-0.5 whitespace-pre-line text-[11px] font-semibold leading-relaxed text-slate-500">
                      {event.message}
                    </p>
                  ) : null}
                  <p className="mt-0.5 text-[10px] font-bold text-slate-400">
                    {event.actorName ? `${event.actorName} · ` : ''}
                    {whenText(event.createdAt) || 'time not recorded'}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </ModalShell>
  );
}
