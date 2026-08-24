import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Filter,
  HelpCircle,
  MapPin,
  MessageSquare,
  Plus,
  RotateCcw,
  Search,
  Send,
  Star,
  UserRound,
  Wrench,
  X,
} from 'lucide-react';
import { residentApi } from '../../features/resident/residentApi';
import { residentKeys, useResidentLiveUpdates } from '../../features/resident/residentEvents';
import { residentFaqs } from '../../data/residentFaqs';
import { ComplaintTracker } from '../../features/complaints/ComplaintTracker';
import { canCancelUnstartedWork } from '../../features/complaints/trackerProjection';

// The resident's complaints, over the live API: `GET /complaints`,
// `GET /complaints/{id}`, and the four writes that belong to the person who
// raised it — read, reopen, resolution, and the answer to a proposed visit.
//
// It replaces a zustand slice that computed the product's rules in the browser:
// the SLA deadline, the reopen's restarted clock, the timeline entries. All
// three are the database's now (API.md §7), which is why nothing here derives a
// date or writes a timeline row — a client that recomputes a rule the server
// also applies is a client that will one day disagree with it.
//
// **Two things the demo did that this deliberately does not.**
//
//   Attachments — the form collected up to three photos and there is no upload
//   endpoint. `RaiseComplaintRequest` does not accept them, so collecting them
//   would be promising a resident their photo reached somebody.
//
//   Filtering by urgency and free text — neither is a query parameter, so both
//   narrow the page that was fetched rather than pretending to search the lot.
//   Status and category *are* parameters and are sent.


// The four words a complaint displays as, which is also what `?status=` matches
// on: two stored statuses render as `Resolved` and two as `In Progress`, so
// filtering by the word on the row returns every row shown under it.
const STATUSES = ['Pending', 'In Progress', 'Resolved', 'Cancelled'];
const CATEGORIES = ['Plumbing', 'Electrical', 'Infrastructure', 'Cleaning', 'Security', 'Others'];

const STATUS_STYLES = {
  Pending: 'border-amber-100 bg-amber-50 text-amber-700',
  'In Progress': 'border-blue-100 bg-blue-50 text-blue-700',
  Resolved: 'border-emerald-100 bg-emerald-50 text-emerald-700',
  Cancelled: 'border-slate-200 bg-slate-100 text-slate-500',
};

const URGENCY_STYLES = {
  High: 'bg-rose-50 text-rose-700',
  Medium: 'bg-amber-50 text-amber-700',
  Low: 'bg-slate-100 text-slate-600',
};

const COMPLAINT_FAQS = residentFaqs.filter((faq) => faq.category === 'Complaints');

const PAGE_SIZE = 20;

const formatDateTime = (value) => {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
};

const emptyForm = {
  title: '',
  description: '',
  category: '',
  skillId: '',
  urgency: 'Medium',
  location: '',
  departmentId: '',
};

function Field({ label, children }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
        {label}
      </label>
      {children}
    </div>
  );
}

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';
const selectClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:outline-none';

// A `datetime-local` value is local wall-clock with no zone. `new Date(…)`
// reads it in the browser's zone — the one the resident typed it in — and
// `toISOString` stamps that answer explicitly rather than handing `timestamptz`
// a naive literal to interpret with the connection's zone. Same reasoning, and
// the same one-liner, as `WorkOrderTriage.jsx`'s `isoFrom`.
const isoFrom = (value) => (value ? new Date(value).toISOString() : null);

// `min` on a `datetime-local` wants the same local wall-clock shape the input
// produces, so "now" has to be shifted out of UTC before it is sliced. The
// server refuses a start in the past anyway (HB409); this is the browser
// saying so before the round trip rather than instead of it.
const localNow = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
};

/**
 * The visit request on a complaint, and the resident's answer to it.
 *
 * A `404` here is *nothing to schedule*, which is the ordinary case and not an
 * error on screen — most complaints never get a scheduled visit, and a red box
 * on every one of them would teach a resident to ignore the box.
 *
 * **Two questions, one card, and the server says which is being asked.**
 * `mode: 'approve'` is the department proposing an hour: confirm it or decline
 * it, unchanged since the day this card shipped. `mode: 'pick'` is ruling F1 —
 * the department raised the job and is asking the *resident* for the hour. The
 * mode is read off the response rather than guessed from the null times,
 * because "no time proposed" and "you are the one proposing" are two different
 * states and only the server knows which of them this is. Anything that is not
 * the word `pick` renders as `approve`, which is what keeps this card correct
 * against a backend that has not shipped the field yet.
 *
 * Pick-mode has no decline (ruling F3). Declining exists to send a supervisor's
 * proposal back for another one; there is nothing to send back when the
 * resident is the one being asked, and silence already has an answer — 24 hours
 * later the association books the first free hour itself.
 */
export function ProposedVisit({ complaintId }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');
  const [startAt, setStartAt] = useState('');
  const [endAt, setEndAt] = useState('');

  const request = useQuery({
    queryKey: residentKeys.schedule(complaintId),
    queryFn: () => residentApi.scheduleRequest(complaintId),
    // A 404 is an answer, not a failure to get one; retrying it three times
    // would only delay the empty state.
    retry: false,
  });

  // Both writes land in the same place, so both refresh the same three things:
  // the card's own read, the thread the answer wrote an entry on, and the list
  // whose row shows the complaint's state.
  const settle = (visit) => {
    queryClient.setQueryData(residentKeys.schedule(complaintId), visit);
    queryClient.invalidateQueries({ queryKey: residentKeys.schedule(complaintId) });
    queryClient.invalidateQueries({ queryKey: residentKeys.complaint(complaintId) });
    queryClient.invalidateQueries({ queryKey: residentKeys.complaintList() });
  };

  const respond = useMutation({
    mutationFn: (response) =>
      residentApi.schedule(complaintId, { response, note: note.trim() || null }),
    onSuccess: (visit) => {
      settle(visit);
      setNote('');
    },
  });

  const pickTime = useMutation({
    mutationFn: () =>
      residentApi.scheduleTime(complaintId, {
        startAt: isoFrom(startAt),
        endAt: isoFrom(endAt),
      }),
    onSuccess: (visit) => {
      settle(visit);
      setStartAt('');
      setEndAt('');
    },
  });

  if (request.isLoading) return null;
  if (request.error) {
    // 404 — nothing is proposed. Anything else is worth saying out loud, since
    // the resident may be waiting on a visit the screen cannot see.
    if (request.error.status === 404) return null;
    return (
      <p role="alert" className="text-xs font-semibold text-rose-600">
        Could not load the proposed visit. {request.error.message}
      </p>
    );
  }

  const visit = request.data;
  if (!visit) return null;

  // The discriminator, and the reason it is `=== 'pick'` rather than a check
  // for missing times: a backend that has not shipped the field yet sends no
  // `mode` at all, and that has to keep rendering the card it always did.
  const picking = visit.mode === 'pick' && Boolean(visit.awaitingResponse);
  const badRange =
    Boolean(startAt) && Boolean(endAt) && new Date(endAt) <= new Date(startAt);
  const canPick = Boolean(startAt) && Boolean(endAt) && !badRange;
  const writeError = respond.error || pickTime.error;

  const window = visit.scheduledStartAt
    ? `${formatDateTime(visit.scheduledStartAt)}${
        visit.scheduledEndAt
          ? ` – ${new Intl.DateTimeFormat('en-IN', {
              hour: 'numeric',
              minute: '2-digit',
            }).format(new Date(visit.scheduledEndAt))}`
          : ''
      }`
    : 'A time has not been proposed yet.';

  return (
    <section className="space-y-3 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-4">
      <div className="flex items-start gap-2">
        <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
        <div>
          <p className="text-sm font-extrabold text-indigo-900">
            {picking
              ? 'Pick a time for this visit'
              : visit.awaitingResponse
                ? 'A visit has been proposed'
                : 'Your visit'}
          </p>
          {/* No hour line in pick-mode: there is no proposed time to print,
              and "a time has not been proposed yet" would read as a delay
              rather than as the question the card is asking. */}
          {picking ? null : <p className="mt-1 text-xs font-bold text-slate-700">{window}</p>}
          <p className="mt-0.5 text-[11px] font-semibold text-slate-500">
            {[visit.departmentName, visit.skillName, visit.locationText]
              .filter(Boolean)
              .join(' · ')}
          </p>
          {visit.assigneeName && (
            <p className="mt-0.5 text-[11px] font-semibold text-slate-500">
              {visit.assigneeName} is booked for it.
            </p>
          )}
        </div>
      </div>

      {picking ? (
        <div className="space-y-2">
          {visit.respondBy && (
            <p className="text-[10px] font-bold uppercase tracking-wide text-indigo-600">
              Pick by {formatDateTime(visit.respondBy)}.
            </p>
          )}
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (!canPick) return;
              pickTime.mutate();
            }}
          >
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="block space-y-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Starts
                </span>
                <input
                  type="datetime-local"
                  required
                  min={localNow()}
                  value={startAt}
                  onChange={(event) => setStartAt(event.target.value)}
                  className={inputClass}
                />
              </label>
              <label className="block space-y-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Ends
                </span>
                <input
                  type="datetime-local"
                  required
                  min={startAt || localNow()}
                  value={endAt}
                  onChange={(event) => setEndAt(event.target.value)}
                  className={inputClass}
                />
              </label>
            </div>
            {badRange && (
              <p className="text-[11px] font-semibold text-rose-600">
                The visit has to end after it starts.
              </p>
            )}
            <button
              type="submit"
              disabled={pickTime.isPending || !canPick}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-700 disabled:bg-slate-300"
            >
              {pickTime.isPending ? 'Setting the time…' : 'Set this time'}
            </button>
          </form>
          {/* Ruling F3: no decline here. There is no proposal to send back, and
              silence is not an unanswered question — it is answered for the
              resident 24 hours after the job was raised. */}
          <p className="text-[10px] font-semibold text-slate-500">
            If you have not picked a time within 24 hours, the association books
            the first available hour.
          </p>
        </div>
      ) : visit.awaitingResponse ? (
        <div className="space-y-2">
          {visit.respondBy && (
            <p className="text-[10px] font-bold uppercase tracking-wide text-indigo-600">
              Answer by {formatDateTime(visit.respondBy)} — after that the
              association schedules it anyway.
            </p>
          )}
          <textarea
            rows={2}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note for the supervisor…"
            className="w-full resize-none rounded-xl border border-indigo-100 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-400 focus:outline-none"
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => respond.mutate('confirmed')}
              disabled={respond.isPending}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-700 disabled:bg-slate-300"
            >
              That time works
            </button>
            <button
              type="button"
              onClick={() => respond.mutate('declined')}
              disabled={respond.isPending}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:text-slate-300"
            >
              It does not
            </button>
          </div>
          {/* Declining is not a counter-proposal and it clears the time: the
              supervisor proposes again rather than the screen collecting an
              alternative there is nowhere to put. */}
          <p className="text-[10px] font-semibold text-slate-500">
            Declining sends it back to the supervisor, who will propose another time.
          </p>
        </div>
      ) : (
        <p className="text-[11px] font-bold text-emerald-700">
          {visit.status === 'cancelled'
            ? 'This visit was cancelled.'
            : 'You have answered this one. Nothing more to do.'}
        </p>
      )}

      {/* Both writes surface here, verbatim and on the card. The server's 409s
          are whole sentences about this complaint — "The association proposed
          this visit's time — answer that instead." — and a paraphrase would be
          this screen guessing at a state the server has already named. */}
      {writeError && (
        <p role="alert" className="text-[11px] font-semibold text-rose-600">
          {writeError.message}
        </p>
      )}
    </section>
  );
}

function ComplaintDrawer({ complaintId, onClose }) {
  const queryClient = useQueryClient();
  const [rating, setRating] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [comment, setComment] = useState('');
  const [isReopening, setIsReopening] = useState(false);
  const [reopenReason, setReopenReason] = useState('');
  const [cancelMode, setCancelMode] = useState(null);
  const [cancelReason, setCancelReason] = useState('');

  const detail = useQuery({
    queryKey: residentKeys.complaint(complaintId),
    queryFn: () => residentApi.complaint(complaintId),
  });

  const afterWrite = (complaint) => {
    queryClient.setQueryData(residentKeys.complaint(complaintId), complaint);
    queryClient.invalidateQueries({ queryKey: residentKeys.complaintList() });
    queryClient.invalidateQueries({ queryKey: residentKeys.snapshot() });
  };

  const confirmResolution = useMutation({
    // `{ rating, feedback }` — the rating is required and the feedback is not.
    // Confirming is what *closes* a complaint: `Resolved` is what the
    // association says, closed is what the resident agrees.
    mutationFn: () => residentApi.resolveComplaint(complaintId, { rating, feedback }),
    onSuccess: (complaint) => {
      afterWrite(complaint);
      setFeedback('');
    },
  });

  // The one write on this screen that does **not** answer with the complaint:
  // `POST /complaints/{id}/comments` is a `201` with a message, so the detail is
  // re-read rather than replaced from the response.
  //
  // `visibility: 'resident'` is the wire word, not the stored one — the column,
  // both RPCs and every read filter say `public`, and the service translates. It
  // is sent explicitly rather than left to the default because a resident may
  // only ever write this one, and a screen that relies on a server-side default
  // for a permission boundary is a screen that changes meaning if the default
  // does.
  const addComment = useMutation({
    mutationFn: () =>
      residentApi.addComplaintComment(complaintId, {
        message: comment.trim(),
        visibility: 'resident',
      }),
    onSuccess: () => {
      setComment('');
      queryClient.invalidateQueries({ queryKey: residentKeys.complaint(complaintId) });
      queryClient.invalidateQueries({ queryKey: residentKeys.complaintList() });
    },
  });

  const reopen = useMutation({
    mutationFn: () => residentApi.reopenComplaint(complaintId, { reason: reopenReason }),
    onSuccess: (complaint) => {
      afterWrite(complaint);
      setIsReopening(false);
      setReopenReason('');
      setRating(0);
    },
  });
  const cancelWork = useMutation({
    mutationFn: () => residentApi.cancelComplaintWork(complaintId, { mode: cancelMode, reason: cancelReason }),
    onSuccess: (complaint) => {
      afterWrite(complaint);
      setCancelMode(null);
      setCancelReason('');
    },
  });

  const complaint = detail.data;
  const canCancelWork = canCancelUnstartedWork(complaint?.timeline);

  return (
    <div
      className="fixed inset-0 z-[999] bg-slate-900/50 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside className="absolute inset-y-0 right-0 w-full max-w-2xl overflow-y-auto bg-white shadow-2xl">
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-100 bg-white/95 px-6 py-5 backdrop-blur">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-extrabold text-slate-900">
                {complaint?.title || 'Complaint'}
              </h2>
              {complaint && (
                <span
                  className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${
                    STATUS_STYLES[complaint.status] || STATUS_STYLES.Pending
                  }`}
                >
                  {complaint.status}
                </span>
              )}
            </div>
            <p className="mt-1 truncate text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Ticket {complaintId}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close complaint details"
            className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {detail.isLoading ? (
          <p className="px-6 py-16 text-center text-sm font-bold text-slate-400">Loading…</p>
        ) : detail.error ? (
          <div role="alert" className="space-y-3 px-6 py-16 text-center">
            <p className="text-sm font-extrabold text-rose-700">
              We could not open this complaint.
            </p>
            <p className="text-xs font-semibold text-rose-600">{detail.error.message}</p>
          </div>
        ) : (
          <div className="space-y-6 p-6">
            <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
              <p className="text-xs font-semibold leading-relaxed text-slate-600">
                {complaint.description || 'No description was given.'}
              </p>
              <div className="mt-4 grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
                <div className="flex gap-2">
                  <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                  <div>
                    <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                      Location
                    </p>
                    <p className="mt-0.5 font-bold text-slate-700">
                      {complaint.location || 'Not given'}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Wrench className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                  <div>
                    <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                      Assigned technician
                    </p>
                    <p className="mt-0.5 font-bold text-slate-700">
                      {complaint.assignee || 'Awaiting assignment'}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                  <div>
                    <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                      Expected resolution
                    </p>
                    {/* Set by the database from the urgency on insert, not
                        computed here — the client that recomputes an SLA is the
                        client that eventually disagrees with the admin's. */}
                    <p className="mt-0.5 font-bold text-slate-700">
                      {formatDateTime(complaint.expectedResolutionAt)}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Clock3 className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                  <div>
                    <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                      Latest update
                    </p>
                    <p className="mt-0.5 font-bold text-slate-700">
                      {formatDateTime(complaint.lastActivityAt)}
                    </p>
                  </div>
                </div>
              </div>
              {complaint.reopenedCount > 0 && (
                <p className="mt-3 text-[10px] font-bold uppercase tracking-wide text-amber-600">
                  Reopened {complaint.reopenedCount} time
                  {complaint.reopenedCount === 1 ? '' : 's'}
                </p>
              )}
            </div>

            <ProposedVisit complaintId={complaintId} />

            {canCancelWork && (
              <section className="rounded-2xl border border-amber-100 bg-amber-50/50 p-4">
                {cancelMode ? (
                  <div className="space-y-3">
                    <p className="text-xs font-bold text-amber-800">
                      {cancelMode === 'cancel'
                        ? 'Cancel entirely — to raise this again you’ll start from scratch.'
                        : 'Send back for re-evaluation — the team will pick someone else.'}
                    </p>
                    <textarea value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} placeholder="Optional reason" className="w-full rounded-xl border border-amber-100 bg-white p-3 text-xs" />
                    <div className="flex gap-2"><button type="button" disabled={cancelWork.isPending} onClick={() => cancelWork.mutate()} className="rounded-xl bg-amber-600 px-3 py-2 text-xs font-bold text-white">{cancelWork.isPending ? 'Saving…' : 'Confirm'}</button><button type="button" onClick={() => setCancelMode(null)} className="text-xs font-bold text-slate-600">Back</button></div>
                    {cancelWork.error && <p role="alert" className="text-xs font-semibold text-rose-600">{cancelWork.error.message}</p>}
                  </div>
                ) : <div className="flex flex-wrap gap-2"><button type="button" onClick={() => setCancelMode('cancel')} className="rounded-xl border border-rose-200 bg-white px-3 py-2 text-xs font-bold text-rose-700">Cancel entirely</button><button type="button" onClick={() => setCancelMode('repool')} className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-xs font-bold text-amber-800">Send back for re-evaluation</button></div>}
              </section>
            )}

            <ComplaintTracker events={complaint.timeline ?? []} />

            <section>
              <h3 className="text-sm font-extrabold text-slate-800">Ticket timeline</h3>
              {complaint.hasOlderEvents && (
                <p className="mt-1 text-[10px] font-semibold text-slate-400">
                  Earlier history is not shown.
                </p>
              )}
              <div className="mt-4 space-y-0">
                {(complaint.timeline ?? []).map((event, index, events) => (
                  <div key={event.id} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <div
                        className={`h-3 w-3 rounded-full ${
                          index === events.length - 1 ? 'bg-indigo-600' : 'bg-slate-300'
                        }`}
                      />
                      {index < events.length - 1 && (
                        <div className="h-full min-h-14 w-px bg-slate-200" />
                      )}
                    </div>
                    <div className="pb-5">
                      <p className="text-xs font-extrabold text-slate-700">{event.label}</p>
                      {event.message && (
                        <p className="mt-1 text-[11px] font-semibold leading-relaxed text-slate-500">
                          {event.message}
                        </p>
                      )}
                      <p className="mt-1 text-[9px] font-bold text-slate-400">
                        {event.actor} · {formatDateTime(event.createdAt)}
                      </p>
                    </div>
                  </div>
                ))}
                {(complaint.timeline ?? []).length === 0 && (
                  <p className="text-xs font-semibold text-slate-400">Nothing recorded yet.</p>
                )}
              </div>
            </section>

            <section>
              <h3 className="flex items-center gap-2 text-sm font-extrabold text-slate-800">
                <MessageSquare className="h-4 w-4 text-indigo-500" />
                Conversation
              </h3>
              {complaint.hasOlderComments && (
                <p className="mt-1 text-[10px] font-semibold text-slate-400">
                  Earlier messages are not shown.
                </p>
              )}
              <div className="mt-3 space-y-3">
                {(complaint.comments ?? []).length === 0 ? (
                  <p className="rounded-xl bg-slate-50 p-4 text-xs font-semibold text-slate-400">
                    No messages yet.
                  </p>
                ) : (
                  complaint.comments.map((item) => (
                    <div key={item.id} className="mr-6 rounded-xl bg-slate-50 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-[10px] font-extrabold text-slate-700">{item.author}</p>
                        <p className="text-[9px] font-semibold text-slate-400">
                          {formatDateTime(item.createdAt)}
                        </p>
                      </div>
                      <p className="mt-1 text-xs font-semibold leading-relaxed text-slate-600">
                        {item.message}
                      </p>
                    </div>
                  ))
                )}
              </div>
              <form
                className="mt-3 flex gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (comment.trim()) addComment.mutate();
                }}
              >
                <input
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder="Write a message…"
                  className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={!comment.trim() || addComment.isPending}
                  className="rounded-xl bg-indigo-600 px-4 text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  aria-label="Send message"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
              {addComment.error && (
                <p role="alert" className="mt-2 text-[11px] font-semibold text-rose-600">
                  {addComment.error.message}
                </p>
              )}
            </section>

            {complaint.status === 'Resolved' && (
              <section className="rounded-2xl border border-emerald-100 bg-emerald-50/50 p-4">
                {complaint.resolutionRating ? (
                  <div>
                    <p className="flex items-center gap-2 text-sm font-extrabold text-emerald-800">
                      <CheckCircle2 className="h-4 w-4" />
                      Resolution confirmed
                    </p>
                    <div className="mt-2 flex gap-1">
                      {[1, 2, 3, 4, 5].map((value) => (
                        <Star
                          key={value}
                          className={`h-4 w-4 ${
                            value <= complaint.resolutionRating
                              ? 'fill-amber-400 text-amber-400'
                              : 'text-slate-300'
                          }`}
                        />
                      ))}
                    </div>
                    {complaint.residentFeedback && (
                      <p className="mt-2 text-xs font-semibold text-slate-600">
                        “{complaint.residentFeedback}”
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div>
                      <p className="text-sm font-extrabold text-emerald-800">
                        Is the issue resolved?
                      </p>
                      <p className="mt-1 text-[11px] font-semibold text-emerald-700/70">
                        Rate the work, or reopen the complaint if the issue remains.
                      </p>
                    </div>
                    <div className="flex gap-1">
                      {[1, 2, 3, 4, 5].map((value) => (
                        <button
                          type="button"
                          key={value}
                          onClick={() => setRating(value)}
                          aria-label={`${value} stars`}
                        >
                          <Star
                            className={`h-6 w-6 ${
                              value <= rating
                                ? 'fill-amber-400 text-amber-400'
                                : 'text-slate-300'
                            }`}
                          />
                        </button>
                      ))}
                    </div>
                    <textarea
                      rows={2}
                      value={feedback}
                      onChange={(event) => setFeedback(event.target.value)}
                      placeholder="Optional feedback…"
                      className="w-full resize-none rounded-xl border border-emerald-100 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-emerald-400 focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => confirmResolution.mutate()}
                      disabled={rating === 0 || confirmResolution.isPending}
                      className="rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      {confirmResolution.isPending ? 'Sending…' : 'Confirm Resolution'}
                    </button>
                    {confirmResolution.error && (
                      <p role="alert" className="text-[11px] font-semibold text-rose-600">
                        {confirmResolution.error.message}
                      </p>
                    )}
                  </div>
                )}

                {/* Disputing a resolution *is* reopening it: there is no second
                    endpoint that records disagreement, and one that only said so
                    would leave the complaint closed. */}
                <div className="mt-4 border-t border-emerald-100 pt-4">
                  {!isReopening ? (
                    <button
                      type="button"
                      onClick={() => setIsReopening(true)}
                      className="flex items-center gap-1.5 text-xs font-bold text-rose-600 hover:text-rose-700"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      Not fixed — reopen this complaint
                    </button>
                  ) : (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        if (reopenReason.trim()) reopen.mutate();
                      }}
                      className="space-y-2"
                    >
                      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        Why is the issue unresolved?
                      </label>
                      <textarea
                        required
                        rows={2}
                        value={reopenReason}
                        onChange={(event) => setReopenReason(event.target.value)}
                        className="w-full resize-none rounded-xl border border-rose-100 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-rose-400 focus:outline-none"
                      />
                      <p className="text-[10px] font-semibold text-slate-400">
                        The deadline restarts and any rating you gave is cleared.
                      </p>
                      <div className="flex gap-2">
                        <button
                          type="submit"
                          disabled={reopen.isPending}
                          className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-700 disabled:bg-slate-300"
                        >
                          {reopen.isPending ? 'Reopening…' : 'Reopen Complaint'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setIsReopening(false)}
                          className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600"
                        >
                          Cancel
                        </button>
                      </div>
                      {reopen.error && (
                        <p role="alert" className="text-[11px] font-semibold text-rose-600">
                          {reopen.error.message}
                        </p>
                      )}
                    </form>
                  )}
                </div>
              </section>
            )}

            {complaint.isOverdue && complaint.status !== 'Resolved' && (
              <div className="flex gap-2 rounded-xl border border-amber-100 bg-amber-50 p-3 text-xs font-semibold text-amber-700">
                <AlertCircle className="h-4 w-4 shrink-0" />
                The expected resolution time has passed.
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

function RaiseComplaintModal({ onClose, onCreated }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(emptyForm);

  // The routing picker, served from `departments` — the admin department list
  // 403s a resident and this is the read that does not.
  const directory = useQuery({
    queryKey: residentKeys.directory(),
    queryFn: () => residentApi.directoryContacts(),
    staleTime: 5 * 60_000,
  });
  const skills = useQuery({ queryKey: ['skills'], queryFn: residentApi.skills, staleTime: 5 * 60_000 });

  const create = useMutation({
    mutationFn: () =>
      residentApi.createComplaint({
        title: form.title.trim(),
        description: form.description.trim(),
        skillId: form.skillId || null,
        urgency: form.urgency,
        location: form.location.trim(),
        // "Not sure" is the default and the honest answer most of the time. It
        // sends `null`, which lets the server route by category instead — the
        // catalogue is curated by somebody who knows how this society is
        // organised, and a resident's wrong guess is worse than no guess.
        departmentId: form.departmentId || null,
      }),
    onSuccess: (complaint) => {
      queryClient.invalidateQueries({ queryKey: residentKeys.complaintList() });
      queryClient.invalidateQueries({ queryKey: residentKeys.snapshot() });
      onCreated(complaint);
    },
  });

  const set = (field) => (event) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-3xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-extrabold text-slate-900">Raise a Complaint</h2>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Add enough detail to help the team respond quickly.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close complaint form"
            className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form
          className="mt-6 space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!form.title.trim() || !form.skillId) return;
            create.mutate();
          }}
        >
          <Field label="Issue title">
            <input
              autoFocus
              required
              value={form.title}
              onChange={set('title')}
              placeholder="e.g. Leaking tap in kitchen"
              className={inputClass}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Trade">
              <select required disabled={skills.isLoading || skills.isError} value={form.skillId} onChange={set('skillId')} className={selectClass}>
                <option value="">{skills.isLoading ? 'Loading trades…' : skills.isError ? 'Trades unavailable' : 'Choose a trade…'}</option>
                {Object.entries((skills.data ?? []).reduce((groups, skill) => {
                  const group = skill.category || 'Other';
                  (groups[group] ||= []).push(skill);
                  return groups;
                }, {})).map(([group, options]) => (
                  <optgroup key={group} label={group}>
                    {options.map((skill) => <option key={skill.id} value={skill.id}>{skill.name}</option>)}
                  </optgroup>
                ))}
              </select>
              {skills.isError ? <p role="alert" className="text-[10px] font-semibold text-rose-600">{skills.error?.message || 'Trades could not be loaded. Please try again.'}</p> : null}
            </Field>
            <Field label="Urgency">
              <select value={form.urgency} onChange={set('urgency')} className={selectClass}>
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
              </select>
            </Field>
          </div>

          <Field label="Who should handle this?">
            <select
              value={form.departmentId}
              onChange={set('departmentId')}
              className={selectClass}
            >
              <option value="">Not sure</option>
              {(directory.data ?? []).map((contact) => (
                <option key={contact.id} value={contact.id}>
                  {contact.name}
                  {contact.category ? ` — ${contact.category}` : ''}
                </option>
              ))}
            </select>
            <p className="text-[10px] font-semibold text-slate-400">
              {directory.error
                ? 'The department list could not be loaded; “Not sure” still files it correctly.'
                : '“Not sure” is fine — the category routes it when you leave this alone.'}
            </p>
          </Field>

          <Field label="Exact location">
            <div className="relative">
              <MapPin className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={form.location}
                onChange={set('location')}
                placeholder="e.g. Kitchen, below the sink"
                className={`${inputClass} pl-10`}
              />
            </div>
          </Field>

          <Field label="Description">
            <textarea
              rows={4}
              value={form.description}
              onChange={set('description')}
              placeholder="Describe what happened and when it started…"
              className={`${inputClass} resize-none`}
            />
          </Field>

          {create.error && (
            <p role="alert" className="text-xs font-semibold text-rose-600">
              {create.error.message}
            </p>
          )}

          <div className="flex justify-end gap-3 border-t border-slate-100 pt-5">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 hover:bg-indigo-700 disabled:bg-slate-300"
            >
              <Send className="h-3.5 w-3.5" />
              {create.isPending ? 'Submitting…' : 'Submit Complaint'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Complaints() {
  const queryClient = useQueryClient();
  useResidentLiveUpdates();

  const [isRaiseModalOpen, setIsRaiseModalOpen] = useState(false);
  const [selectedComplaintId, setSelectedComplaintId] = useState(null);
  const [statusFilter, setStatusFilter] = useState('All');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [urgencyFilter, setUrgencyFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const [openFaqId, setOpenFaqId] = useState(COMPLAINT_FAQS[0]?.id ?? null);

  const params = useMemo(
    () => ({
      status: statusFilter === 'All' ? undefined : statusFilter,
      category: categoryFilter === 'All' ? undefined : categoryFilter,
      page,
      pageSize: PAGE_SIZE,
    }),
    [statusFilter, categoryFilter, page]
  );

  const list = useQuery({
    queryKey: residentKeys.complaints(params),
    queryFn: () => residentApi.complaints(params),
  });

  // Per membership, so opening a thread clears the resident's own marker and
  // nobody else's. Fired on open and never rendered — the badge going away is
  // the whole of its user-visible effect.
  const markRead = useMutation({
    mutationFn: (complaintId) => residentApi.markComplaintRead(complaintId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: residentKeys.complaintList() });
      queryClient.invalidateQueries({ queryKey: residentKeys.snapshot() });
    },
  });

  useEffect(() => {
    if (!isRaiseModalOpen && !selectedComplaintId) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsRaiseModalOpen(false);
        setSelectedComplaintId(null);
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isRaiseModalOpen, selectedComplaintId]);

  const openComplaint = (complaintId) => {
    setSelectedComplaintId(complaintId);
    markRead.mutate(complaintId);
  };

  const items = list.data?.items ?? [];
  const query = searchTerm.trim().toLowerCase();
  const visible = items.filter((complaint) => {
    const matchesUrgency = urgencyFilter === 'All' || complaint.urgency === urgencyFilter;
    const matchesSearch =
      !query ||
      [complaint.title, complaint.location, complaint.assignee, complaint.id].some((value) =>
        String(value || '').toLowerCase().includes(query)
      );
    return matchesUrgency && matchesSearch;
  });

  const changeFilter = (setter) => (value) => {
    setter(value);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">My Complaints</h1>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Report an issue and follow every update through resolution.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsRaiseModalOpen(true)}
          className="flex items-center justify-center gap-1.5 self-start rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-colors hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" />
          Raise Complaint
        </button>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-100 bg-white p-4">
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search this page of complaints…"
            className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-xs font-semibold text-slate-700 placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          {['All', ...STATUSES].map((status) => (
            <button
              type="button"
              key={status}
              onClick={() => changeFilter(setStatusFilter)(status)}
              className={`rounded-lg px-3 py-1.5 text-[10px] font-bold transition-colors ${
                statusFilter === status
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-50 text-slate-500 hover:text-slate-800'
              }`}
            >
              {status}
            </button>
          ))}
          <select
            value={categoryFilter}
            onChange={(event) => changeFilter(setCategoryFilter)(event.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[10px] font-bold text-slate-600 focus:border-indigo-500 focus:outline-none"
          >
            <option value="All">All categories</option>
            {CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
          <select
            value={urgencyFilter}
            onChange={(event) => setUrgencyFilter(event.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[10px] font-bold text-slate-600 focus:border-indigo-500 focus:outline-none"
          >
            <option value="All">All urgency</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
          <span className="ml-auto text-[10px] font-bold text-slate-400">
            {list.data ? `${list.data.total} tickets` : ''}
          </span>
        </div>
      </div>

      {list.isLoading ? (
        <div className="rounded-2xl border border-slate-100 bg-white px-6 py-14 text-center text-sm font-bold text-slate-400">
          Loading your complaints…
        </div>
      ) : list.error ? (
        <div
          role="alert"
          className="space-y-3 rounded-2xl border border-rose-100 bg-rose-50 px-6 py-12 text-center"
        >
          <p className="text-sm font-extrabold text-rose-800">
            We could not load your complaints.
          </p>
          <p className="text-xs font-semibold text-rose-700">{list.error.message}</p>
          <button
            type="button"
            onClick={() => list.refetch()}
            className="rounded-xl bg-rose-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-rose-700"
          >
            Try again
          </button>
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-2xl border border-slate-100 bg-white px-6 py-14 text-center">
          <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500" />
          <p className="mt-3 text-sm font-extrabold text-slate-700">No complaints found</p>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Try changing the filters, or raise a new complaint.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {visible.map((complaint) => (
            <article
              key={complaint.id}
              role="button"
              tabIndex={0}
              onClick={() => openComplaint(complaint.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') openComplaint(complaint.id);
              }}
              className="cursor-pointer rounded-2xl border border-slate-100 bg-white p-5 shadow-sm transition-all hover:border-indigo-200 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-100"
            >
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-sm font-extrabold text-slate-800">
                      {complaint.title}
                    </h2>
                    {complaint.isUnread && (
                      <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-[9px] font-extrabold text-white">
                        New update
                      </span>
                    )}
                    <span
                      className={`rounded-full px-2 py-0.5 text-[9px] font-extrabold ${
                        URGENCY_STYLES[complaint.urgency] || URGENCY_STYLES.Low
                      }`}
                    >
                      {complaint.urgency}
                    </span>
                    {complaint.isOverdue && (
                      <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[9px] font-extrabold text-amber-700">
                        Overdue
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-semibold text-slate-400">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3.5 w-3.5" />
                      {complaint.location || complaint.category}
                    </span>
                    <span className="flex items-center gap-1">
                      <UserRound className="h-3.5 w-3.5" />
                      {complaint.assignee || 'Awaiting assignment'}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock3 className="h-3.5 w-3.5" />
                      Updated {formatDateTime(complaint.lastActivityAt)}
                    </span>
                    {complaint.commentCount > 0 && (
                      <span className="flex items-center gap-1">
                        <MessageSquare className="h-3.5 w-3.5" />
                        {complaint.commentCount}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${
                      STATUS_STYLES[complaint.status] || STATUS_STYLES.Pending
                    }`}
                  >
                    {complaint.status}
                  </span>
                  <ChevronRight className="h-4 w-4 text-slate-300" />
                </div>
              </div>
            </article>
          ))}

          {(page > 1 || list.data?.hasMore) && (
            <div className="flex items-center justify-between rounded-2xl border border-slate-100 bg-white px-4 py-3">
              <button
                type="button"
                disabled={page === 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
                className="rounded-lg px-3 py-1.5 text-[11px] font-bold text-slate-600 disabled:text-slate-300"
              >
                Previous
              </button>
              <span className="text-[10px] font-bold text-slate-400">Page {page}</span>
              <button
                type="button"
                disabled={!list.data?.hasMore}
                onClick={() => setPage((value) => value + 1)}
                className="rounded-lg px-3 py-1.5 text-[11px] font-bold text-slate-600 disabled:text-slate-300"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}

      <section className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
            <HelpCircle className="h-4.5 w-4.5" />
          </div>
          <div>
            <h2 className="text-sm font-extrabold text-slate-800">Complaint FAQs</h2>
            <p className="mt-1 text-[11px] font-semibold text-slate-400">
              Quick answers about updates, resolution, and emergencies.
            </p>
          </div>
        </div>

        <div className="mt-4 divide-y divide-slate-100 border-t border-slate-100">
          {COMPLAINT_FAQS.map((faq) => {
            const isOpen = openFaqId === faq.id;
            return (
              <div key={faq.id}>
                <button
                  type="button"
                  onClick={() => setOpenFaqId(isOpen ? null : faq.id)}
                  className="flex w-full items-center justify-between gap-4 py-4 text-left"
                  aria-expanded={isOpen}
                >
                  <span className="text-xs font-bold text-slate-700">{faq.question}</span>
                  <ChevronDown
                    className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${
                      isOpen ? 'rotate-180' : ''
                    }`}
                  />
                </button>
                {isOpen && (
                  <p className="pb-4 pr-8 text-xs font-semibold leading-relaxed text-slate-500">
                    {faq.answer}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {isRaiseModalOpen && (
        <RaiseComplaintModal
          onClose={() => setIsRaiseModalOpen(false)}
          onCreated={(complaint) => {
            setIsRaiseModalOpen(false);
            if (complaint?.id) setSelectedComplaintId(complaint.id);
          }}
        />
      )}

      {selectedComplaintId && (
        <ComplaintDrawer
          complaintId={selectedComplaintId}
          onClose={() => setSelectedComplaintId(null)}
        />
      )}
    </div>
  );
}
