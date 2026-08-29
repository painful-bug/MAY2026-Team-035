import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, CalendarClock, ClipboardList, History, MapPin, Plus, UserCheck, X,
} from 'lucide-react';

import { workOrdersApi } from '../../features/workOrders/workOrdersApi';
import {
  WORK_ORDER_STATUSES,
  assignmentLabel,
  permittedActions,
  statusLabel,
  statusTone,
} from '../../features/workOrders/workOrderVocabulary';
import { usePortalScope } from '../../features/hiring/usePortalScope';
import { hiringApi } from '../../features/hiring/hiringApi';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { complaintRoutingApi } from '../../features/complaints/routingApi';

// Work-order triage: the hand path behind the dispatch engine.
//
// **This screen exists because `0036` was arranged around one rule** — *every
// transition the engine will later make automatically is reachable by hand
// first* — and until now the hand had nothing to press. Eight endpoints, no
// caller: when a dispatcher put the wrong person on a job there was no
// supported way to fix it, and a state machine whose only exit is a background
// job is one nobody can test.
//
// **It lives under `AdminDashboard/` and is not only the admin's**, exactly as
// `DepartmentHiring.jsx` does and for the same reason: the endpoints behind it
// admit every kind of staff and narrow inside Postgres, so a manager who
// supervises a department has always been allowed to call them. Every link out
// is built from `usePortalScope().base`; a hardcoded `/admin/...` here is a
// link that bounces a manager home.
//
// **The department id stays in the URL under every portal.** A manager could
// have had it implied by their session, and then this file would carry a branch
// only one portal ever exercises. Typing somebody else's id is not a way in —
// `can_supervise_department` refuses it in the database, which is the posture
// `work_orders.py` states outright: an id arriving in a URL is never an
// authorization decision.
//
// **Two tabs, because there are two questions and one sitting.** The queue is
// "what is happening in this department"; raising work is "this complaint needs
// somebody" — and a supervisor moves between them constantly, because triaging
// a complaint is what puts a row in the queue.
//
// What this screen deliberately does **not** touch is the complaint's own
// lifecycle. `complaints.status` and `work_orders.status` are two state machines
// over one complaint and nothing here couples them; that fork belongs to whoever
// owns the complaint engine (`docs/COMPLAINT_ENGINE_HANDOFF.md` §0 and §8).

const TABS = [
  { id: 'queue', label: 'Queue', icon: ClipboardList },
  { id: 'raise', label: 'Raise work', icon: Plus },
];

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

const PRIORITY_TONES = {
  high: 'bg-rose-50 text-rose-700',
  medium: 'bg-amber-50 text-amber-700',
  low: 'bg-slate-100 text-slate-600',
};

function Pill({ children, tone = 'bg-slate-100 text-slate-600' }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${tone}`}>
      {children}
    </span>
  );
}

function Empty({ children }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-12 text-center">
      <p className="text-sm font-bold text-slate-500">{children}</p>
    </div>
  );
}

function Failure({ error }) {
  if (!error) return null;
  // A 422's envelope names the offending fields in `details`; the message
  // alone ("The request could not be validated.") leaves the person staring
  // at six inputs with no idea which one the server meant.
  const details = Array.isArray(error.details) ? error.details : [];
  return (
    <p role="alert" className="text-xs font-semibold text-rose-600">
      {error.message}
      {details.map((detail) => (
        <span key={`${detail.field}:${detail.message}`} className="block font-normal">
          {detail.field ? `${detail.field}: ` : ''}{detail.message}
        </span>
      ))}
    </p>
  );
}

const whenText = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? null
    : date.toLocaleString(undefined, {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    });
};

// A `datetime-local` value is local wall-clock with no zone. `new Date(…)`
// reads it in the browser's zone, which is the one the supervisor typed it in,
// and `toISOString` stamps that answer explicitly rather than leaving a naive
// literal for `timestamptz` to interpret with the *connection's* zone — the
// guess `work_orders_service._iso` refuses to make on the server for exactly
// the same reason.
const isoFrom = (value) => (value ? new Date(value).toISOString() : null);

// ---------------------------------------------------------------------------
// One job in the queue
// ---------------------------------------------------------------------------

function JobRow({ order, selected, onOpen }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(order.id)}
      className={`w-full space-y-2 rounded-2xl border p-4 text-left shadow-sm ${
        selected ? 'border-indigo-400 bg-indigo-50/40' : 'border-slate-100 bg-white'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-extrabold text-slate-800">
            {order.complaintTitle || 'Work with no complaint title'}
          </p>
          <p className="mt-0.5 truncate text-[11px] font-semibold text-slate-400">
            {order.skillName || 'No trade set'}
            {order.complaintCategory ? ` · ${order.complaintCategory}` : ''}
            {order.subjectKind === 'facility' ? ' · common area' : ' · at a home'}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <Pill tone={statusTone(order.status)}>{statusLabel(order.status)}</Pill>
          <Pill tone={PRIORITY_TONES[order.priority]}>{order.priority}</Pill>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-slate-50 pt-2.5">
        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-slate-400">
          <CalendarClock className="h-3.5 w-3.5" />
          {/* "No time yet" is not the same as "soon", which is why the queue
              sorts the unscheduled underneath rather than first: a draft with
              no hour is the thing nobody has decided about, not the most
              urgent thing on the screen. */}
          {whenText(order.scheduledStartAt) || 'No time yet'}
        </span>
        {order.locationText ? (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-slate-400">
            <MapPin className="h-3.5 w-3.5" />
            {order.locationText}
          </span>
        ) : null}
        <span className="text-[11px] font-bold text-slate-400">
          {order.assigneeName || 'Nobody booked'}
        </span>
        {order.failedAttemptCount > 0 ? (
          <Pill tone="bg-rose-50 text-rose-700">
            {order.failedAttemptCount} failed{' '}
            {order.failedAttemptCount === 1 ? 'attempt' : 'attempts'}
          </Pill>
        ) : null}
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// One job, opened
// ---------------------------------------------------------------------------

function AssignForm({ order, roster, onSubmit, pending, error }) {
  const [staffAssignmentId, setStaffAssignmentId] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [includeExcluded, setIncludeExcluded] = useState(false);
  const candidates = useQuery({
    queryKey: ['work-orders', 'candidates', order.id, includeExcluded],
    queryFn: () => workOrdersApi.candidates(order.id, { includeExcluded }),
  });
  const { slotRequiredToAssign } = permittedActions(order);

  return (
    <form
      className="space-y-3 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!staffAssignmentId) return;
        onSubmit({
          staffAssignmentId,
          scheduledStartAt: isoFrom(start),
          scheduledEndAt: isoFrom(end),
        });
      }}
    >
      <p className="text-[11px] font-bold uppercase tracking-wide text-indigo-500">
        Offer somebody this job
      </p>
      {/* The roster, not a search. `assign_work_order` refuses anybody without a
          `staff_assignments` row in this department by name — offering a wider
          list would be offering options the database will decline. */}
      <select
        className={inputClass}
        value={staffAssignmentId}
        onChange={(event) => setStaffAssignmentId(event.target.value)}
      >
        <option value="">Choose a candidate…</option>
        {(candidates.data ?? roster).map((member) => (
          <option key={member.staffAssignmentId || member.id} value={member.staffAssignmentId || member.id} disabled={member.excluded}>
            {member.displayName || member.name}
            {member.openJobs !== undefined ? ` · ${member.openJobs} open` : ''}
            {member.awayUntil ? ` · away until ${whenText(member.awayUntil)}` : ''}
            {member.excluded ? ' · declined earlier' : ''}
          </option>
        ))}
      </select>
      <label className="flex items-center gap-2 text-[11px] font-semibold text-slate-600"><input type="checkbox" checked={includeExcluded} onChange={(event) => setIncludeExcluded(event.target.checked)} />Show excluded candidates</label>

      {/* Optional, and it defaults to the job's own hour — sending one assigns
          and reschedules in a single write, which is the common case. On a job
          with no hour at all it stops being optional: the overlap constraint is
          partial on a non-null start, so a booking with no hour is one it
          cannot see. */}
      <div className="grid grid-cols-2 gap-2">
        <label className="block space-y-1.5">
          <span className="text-[11px] font-bold text-slate-500">
            {slotRequiredToAssign ? 'Start (required)' : 'Start (optional)'}
          </span>
          <input
            type="datetime-local"
            className={inputClass}
            required={slotRequiredToAssign}
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-[11px] font-bold text-slate-500">
            {slotRequiredToAssign ? 'End (required)' : 'End (optional)'}
          </span>
          <input
            type="datetime-local"
            className={inputClass}
            required={slotRequiredToAssign}
            value={end}
            onChange={(event) => setEnd(event.target.value)}
          />
        </label>
      </div>

      {slotRequiredToAssign ? (
        <p className="text-[11px] font-semibold text-amber-700">
          This job has no hour yet, so the assignment has to carry one.
        </p>
      ) : null}

      <button
        type="submit"
        disabled={pending || !staffAssignmentId}
        className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
      >
        <UserCheck className="h-4 w-4" />Offer job
      </button>
      <Failure error={error} />
    </form>
  );
}

function RescheduleForm({ onSubmit, pending, error }) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [note, setNote] = useState('');

  return (
    <form
      className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          scheduledStartAt: isoFrom(start),
          scheduledEndAt: isoFrom(end),
          note: note.trim() || null,
        });
      }}
    >
      <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
        Move the visit
      </p>
      {/* Both ends, always. This is not a partial edit: the accepted
          assignment's range moves with the job, and a range needs two ends. */}
      <div className="grid grid-cols-2 gap-2">
        <input
          type="datetime-local"
          required
          className={inputClass}
          value={start}
          onChange={(event) => setStart(event.target.value)}
        />
        <input
          type="datetime-local"
          required
          className={inputClass}
          value={end}
          onChange={(event) => setEnd(event.target.value)}
        />
      </div>
      <input
        className={inputClass}
        value={note}
        placeholder="Why it moved (optional)"
        onChange={(event) => setNote(event.target.value)}
      />
      <button
        type="submit"
        disabled={pending}
        className="inline-flex items-center gap-1.5 rounded-xl bg-slate-800 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
      >
        <CalendarClock className="h-4 w-4" />Move it
      </button>
      <Failure error={error} />
    </form>
  );
}

function EditForm({ order, skills, onSubmit, pending, error }) {
  const [skillId, setSkillId] = useState(order.skillId || '');
  const [subjectKind, setSubjectKind] = useState(order.subjectKind || 'resident');
  const [locationText, setLocationText] = useState(order.locationText || '');
  const [priority, setPriority] = useState(order.priority || 'medium');

  return (
    <form
      className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          skillId: skillId || null,
          subjectKind,
          // The trimmed string and **not** `|| null`, which is the one place
          // this form could lie. `update_work_order` distinguishes the two:
          // a null `p_location_text` keeps whatever is stored, and an empty
          // string clears it. Sending null for a field somebody just emptied
          // would show them the old value coming back.
          locationText: locationText.trim(),
          priority,
        });
      }}
    >
      <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
        What the job is
      </p>
      {/* No time field and no status field, and their absence is the design:
          each of those carries a rule and a notification, and a
          general-purpose edit is precisely the shape that skips them. The
          request model has no field for either, so one added here would go
          nowhere quietly. */}
      <select
        className={inputClass}
        value={skillId}
        onChange={(event) => setSkillId(event.target.value)}
      >
        <option value="">Trade — leave as it is</option>
        {skills.map((skill) => (
          <option key={skill.id} value={skill.id}>{skill.name}</option>
        ))}
      </select>
      <div className="grid grid-cols-2 gap-2">
        <select
          className={inputClass}
          value={subjectKind}
          onChange={(event) => setSubjectKind(event.target.value)}
        >
          <option value="resident">At somebody&apos;s home</option>
          <option value="facility">A common area</option>
        </select>
        <select
          className={inputClass}
          value={priority}
          onChange={(event) => setPriority(event.target.value)}
        >
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </div>
      <input
        className={inputClass}
        value={locationText}
        placeholder="Where (Flat B-402, basement pump room…)"
        onChange={(event) => setLocationText(event.target.value)}
      />
      <button
        type="submit"
        disabled={pending}
        className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 disabled:opacity-60"
      >
        Save the change
      </button>
      <Failure error={error} />
    </form>
  );
}

function CancelForm({ onSubmit, pending, error }) {
  const [reason, setReason] = useState('');
  const tooShort = reason.trim().length < 3;

  return (
    <form
      className="space-y-3 rounded-xl border border-rose-100 bg-rose-50/50 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (tooShort) return;
        onSubmit(reason.trim());
      }}
    >
      <p className="text-[11px] font-bold uppercase tracking-wide text-rose-600">
        Call it off
      </p>
      {/* Required, and not because a form needed a field. It reaches both the
          worker and the resident in a notification: a cancellation nobody can
          explain is the one that produces the phone call this feature exists to
          prevent. */}
      <input
        className={inputClass}
        value={reason}
        placeholder="Why (the worker and the resident both read this)"
        onChange={(event) => setReason(event.target.value)}
      />
      <button
        type="submit"
        disabled={pending || tooShort}
        className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
      >
        <X className="h-4 w-4" />Cancel this job
      </button>
      <Failure error={error} />
    </form>
  );
}

function JobDetail({ jobId, roster, skills, onChanged, onClose }) {
  const [open, setOpen] = useState(null);

  const job = useQuery({
    queryKey: ['work-orders', 'job', jobId],
    queryFn: () => workOrdersApi.detail(jobId),
  });

  const settle = () => { setOpen(null); onChanged(); };

  const assign = useMutation({
    mutationFn: (payload) => workOrdersApi.assign(jobId, payload),
    onSuccess: settle,
  });
  const reschedule = useMutation({
    mutationFn: (payload) => workOrdersApi.reschedule(jobId, payload),
    onSuccess: settle,
  });
  const update = useMutation({
    mutationFn: (payload) => workOrdersApi.update(jobId, payload),
    onSuccess: settle,
  });
  const cancel = useMutation({
    mutationFn: (reason) => workOrdersApi.cancel(jobId, reason),
    onSuccess: settle,
  });

  if (job.isPending) {
    return (
      <div className="rounded-2xl border border-slate-100 bg-white p-6">
        <p className="text-sm font-semibold text-slate-500">Opening the job…</p>
      </div>
    );
  }
  if (job.error) {
    return (
      <div className="rounded-2xl border border-rose-100 bg-white p-6">
        {/* A job the policy hides is a 404 and not a 403, so that refusals are
            not enumerable. The message the API sent is the honest one. */}
        <Failure error={job.error} />
      </div>
    );
  }

  const order = job.data;
  const actions = permittedActions(order);
  const assignments = order.assignments || [];

  return (
    <section className="space-y-4 rounded-2xl border border-indigo-100 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-extrabold text-slate-900">
            {order.complaintTitle || 'Work order'}
          </h2>
          <p className="mt-0.5 text-[11px] font-semibold text-slate-400">
            {order.departmentName || 'No department'}
            {order.skillName ? ` · ${order.skillName}` : ''}
            {order.locationText ? ` · ${order.locationText}` : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
          aria-label="Close this job"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={statusTone(order.status)}>{statusLabel(order.status)}</Pill>
        <Pill tone={PRIORITY_TONES[order.priority]}>{order.priority}</Pill>
        <Pill>{order.subjectKind === 'facility' ? 'common area' : 'at a home'}</Pill>
        <span className="text-[11px] font-bold text-slate-400">
          {whenText(order.scheduledStartAt) || 'No time yet'}
          {order.scheduledEndAt ? ` – ${whenText(order.scheduledEndAt)}` : ''}
        </span>
      </div>

      {order.residentDeadlineAt ? (
        <p className="text-[11px] font-semibold text-amber-700">
          Waiting on the resident until {whenText(order.residentDeadlineAt)}.
        </p>
      ) : null}
      {order.cancelledReason ? (
        <p className="rounded-xl bg-slate-50 p-3 text-xs font-semibold text-slate-600">
          Called off — “{order.cancelledReason}”
        </p>
      ) : null}

      {/* The history, not the holder. Withdrawn and declined rows stay, because
          "we sent Ravi and he could not get in, so we sent Anil" is the
          question a supervisor actually asks; the current holder is the
          top-level assignee above. */}
      <div className="space-y-2 border-t border-slate-50 pt-3">
        <p className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-400">
          <History className="h-3.5 w-3.5" />
          Who has been on it
        </p>
        {assignments.length === 0 ? (
          <p className="text-xs font-semibold text-slate-400">Nobody has been offered this job.</p>
        ) : (
          <ul className="space-y-1.5">
            {assignments.map((entry) => (
              <li key={entry.id} className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-extrabold text-slate-700">
                  {entry.workerName || 'Unnamed worker'}
                </span>
                <Pill
                  tone={entry.status === 'accepted'
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-slate-100 text-slate-500'}
                >
                  {assignmentLabel(entry.status)}
                </Pill>
                <span className="text-[11px] font-semibold text-slate-400">
                  {whenText(entry.scheduledStartAt) || 'no hour'}
                </span>
                {/* Until the dispatcher runs, every row here was a supervisor's
                    decision. The flag is worth showing anyway: a job somebody
                    was *given* reads differently from one they were offered. */}
                {entry.isAutoAssigned ? <Pill tone="bg-sky-50 text-sky-700">by the engine</Pill> : null}
                {entry.declineReason ? (
                  <span className="text-[11px] font-semibold text-rose-600">
                    “{entry.declineReason}”
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Which verbs a status still accepts is not uniform, and the screen says
          so by drawing only the ones the database will take. A failed visit can
          still be edited and called off; it cannot be re-booked, because the
          answer to a failed visit is a new job. */}
      <div className="flex flex-wrap gap-2 border-t border-slate-50 pt-3">
        {actions.assign ? (
          <button
            type="button"
            onClick={() => setOpen(open === 'assign' ? null : 'assign')}
            className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white"
          >
            {order.assigneeName ? 'Reassign' : 'Assign'}
          </button>
        ) : null}
        {actions.reschedule ? (
          <button
            type="button"
            onClick={() => setOpen(open === 'reschedule' ? null : 'reschedule')}
            className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600"
          >
            Reschedule
          </button>
        ) : null}
        {actions.edit ? (
          <button
            type="button"
            onClick={() => setOpen(open === 'edit' ? null : 'edit')}
            className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600"
          >
            Edit
          </button>
        ) : null}
        {actions.cancel ? (
          <button
            type="button"
            onClick={() => setOpen(open === 'cancel' ? null : 'cancel')}
            className="rounded-xl border border-rose-200 px-4 py-2.5 text-xs font-bold text-rose-700"
          >
            Cancel
          </button>
        ) : null}
        {!actions.edit && !actions.assign ? (
          <p className="text-xs font-semibold text-slate-400">
            This job is closed. A new one is how the work comes back.
          </p>
        ) : null}
      </div>

      {open === 'assign' ? (
        <AssignForm
          order={order}
          roster={roster}
          pending={assign.isPending}
          error={assign.error}
          onSubmit={(payload) => assign.mutate(payload)}
        />
      ) : null}
      {open === 'reschedule' ? (
        <RescheduleForm
          pending={reschedule.isPending}
          error={reschedule.error}
          onSubmit={(payload) => reschedule.mutate(payload)}
        />
      ) : null}
      {open === 'edit' ? (
        <EditForm
          order={order}
          skills={skills}
          pending={update.isPending}
          error={update.error}
          onSubmit={(payload) => update.mutate(payload)}
        />
      ) : null}
      {open === 'cancel' ? (
        <CancelForm
          pending={cancel.isPending}
          error={cancel.error}
          onSubmit={(reason) => cancel.mutate(reason)}
        />
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Raising work against a complaint
// ---------------------------------------------------------------------------

function CreateForm({ complaintId, skills, onCreated }) {
  const [subjectKind, setSubjectKind] = useState('resident');
  const [skillId, setSkillId] = useState('');
  const [locationText, setLocationText] = useState('');
  const [note, setNote] = useState('');

  const create = useMutation({
    mutationFn: (payload) => workOrdersApi.create(complaintId, payload),
    onSuccess: onCreated,
  });

  return (
    <form
      className="space-y-3 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        // `departmentId` is deliberately not sent. It is derived from the
        // complaint, and every complaint on this screen was listed *because*
        // it is already routed to this department — sending it again would be
        // this screen re-deciding routing it does not own.
        //
        // Neither is the slot, and that is ruling F1 rather than an omission:
        // nobody on this side of the screen picks the hour any more. A
        // resident-subject job asks the resident for it; a common-area job is
        // booked by the system into the first hour somebody can take. The API
        // still *accepts* `scheduledStartAt`/`scheduledEndAt` for older
        // callers (adjudication G1), which is exactly why this one has to be
        // deliberate about sending neither.
        create.mutate({
          subjectKind,
          skillId: skillId || null,
          locationText: locationText.trim() || null,
          note: note.trim() || null,
        });
      }}
    >
      <p className="text-[11px] font-bold uppercase tracking-wide text-indigo-500">
        Raise a job against this complaint
      </p>

      <div className="grid grid-cols-2 gap-2">
        <select
          className={inputClass}
          value={subjectKind}
          onChange={(event) => setSubjectKind(event.target.value)}
        >
          <option value="resident">At somebody&apos;s home</option>
          <option value="facility">A common area</option>
        </select>
        <select
          className={inputClass}
          value={skillId}
          onChange={(event) => setSkillId(event.target.value)}
        >
          {/* Blank is the ordinary answer: the trade is derived from the
              complaint's category, which is what `0034` gave
              `complaint_categories.skill_id` for — so nobody has to answer
              "which trade is this" twice. */}
          <option value="">Trade — from the category</option>
          {skills.map((skill) => (
            <option key={skill.id} value={skill.id}>{skill.name}</option>
          ))}
        </select>
      </div>

      <input
        className={inputClass}
        value={locationText}
        placeholder="Where (Flat B-402, basement pump room…)"
        onChange={(event) => setLocationText(event.target.value)}
      />

      <input
        className={inputClass}
        value={note}
        placeholder="A note for the timeline (optional)"
        onChange={(event) => setNote(event.target.value)}
      />

      {/* There used to be a start and an end here, and the fork the whole
          screen turned on was whether they were filled in. Ruling F1 took the
          question away from this form for everyone: who answers "when" is
          decided by *who the job is about*, and the two answers are the two
          sentences below. */}
      <p className="text-[11px] font-semibold text-slate-500">
        {subjectKind === 'facility'
          ? 'Nobody confirms a common-area job — the system books the first free hour a serviceman can take, once urgent home visits are covered.'
          : 'The resident picks the visit time — this sends them the request. If they have not answered in 24 hours, the system books the first free hour a serviceman can take.'}
      </p>

      <button
        type="submit"
        disabled={create.isPending}
        className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
      >
        <Plus className="h-4 w-4" />Raise it
      </button>
      <Failure error={create.error} />
    </form>
  );
}

function ComplaintWorkOrders({ complaintId, skills, onOpenJob, onChanged }) {
  const jobs = useQuery({
    queryKey: ['work-orders', 'complaint', complaintId],
    queryFn: () => workOrdersApi.forComplaint(complaintId),
  });

  return (
    <div className="space-y-3">
      <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">
        Jobs already raised
      </p>
      {jobs.isPending ? (
        <p className="text-xs font-semibold text-slate-400">Loading…</p>
      ) : jobs.error ? (
        <Failure error={jobs.error} />
      ) : (jobs.data || []).length === 0 ? (
        <p className="text-xs font-semibold text-slate-400">
          {/* Not an error state. A complaint with no work order is the ordinary
              case for one nobody has triaged yet. */}
          None yet. Nothing has been scheduled against this complaint.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {(jobs.data || []).map((job) => (
            <li key={job.id}>
              <button
                type="button"
                onClick={() => onOpenJob(job.id)}
                className="flex w-full flex-wrap items-center gap-2 rounded-xl border border-slate-100 p-2.5 text-left"
              >
                <Pill tone={statusTone(job.status)}>{statusLabel(job.status)}</Pill>
                <span className="text-[11px] font-bold text-slate-500">
                  {whenText(job.scheduledStartAt) || 'no time yet'}
                </span>
                <span className="text-[11px] font-semibold text-slate-400">
                  {job.assigneeName || 'nobody booked'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Several jobs on one complaint is normal and not a mistake: a failed
          visit is rescheduled as a second job and a reopened complaint goes to
          a different supervisor. That is why the assignment lives on the work
          order and not in a column on the complaint. */}
      <CreateForm complaintId={complaintId} skills={skills} onCreated={onChanged} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// The screen
// ---------------------------------------------------------------------------

export default function WorkOrderTriage() {
  const { base: basePath, departmentId } = usePortalScope();
  const queryClient = useQueryClient();

  // Tab, filter, open job and open complaint all live in the URL rather than in
  // `useState`, for the reason `DepartmentHiring` gives about its own tab: a
  // deep link that lands on the default view is a link that lies. `?job=` is
  // also the parameter `0037`'s three supervisor notifications already carry.
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const tab = TABS.some((entry) => entry.id === tabParam) ? tabParam : 'queue';
  const statusFilter = searchParams.get('status') || '';
  const jobId = searchParams.get('job');
  const complaintId = searchParams.get('complaint');

  const setParam = (key, value) => {
    setSearchParams((params) => {
      const copy = new URLSearchParams(params);
      if (value) copy.set(key, value);
      else copy.delete(key);
      return copy;
    }, { replace: true });
  };

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['work-orders'] });
  };

  const queue = useQuery({
    queryKey: ['work-orders', departmentId, 'queue', statusFilter],
    queryFn: () => workOrdersApi.forDepartment(departmentId, { status: statusFilter || undefined }),
    enabled: Boolean(departmentId),
  });

  // The roster and the department's trades, both from one read. `staff[].id` is
  // the `staff_assignments` row id, which is exactly what `assign` takes — and
  // `GET /departments/{id}` is the admin-or-manager read, unlike the departments
  // *list*, which is admin-only and would 403 for half the people on this page.
  //
  // Admin-or-*manager* — and a service-department supervisor holds a `worker`
  // membership, so under the worker portal this read can only ever 403. It is
  // not asked for there at all rather than asked and refused: react-query
  // retries and refetches an error on every mount and focus, which showed up in
  // the backend log as a stream of 403s tracking the supervisor around their
  // own screen. The gate is the portal and not the person, because the portal
  // is the one fact the browser holds that cannot drift from `_portal_for`.
  const inWorkerPortal = basePath === AUTH_ROUTES.WORKER_DASHBOARD;
  const department = useQuery({
    queryKey: ['work-orders', departmentId, 'department'],
    queryFn: () => hiringApi.departmentDetail(departmentId),
    enabled: Boolean(departmentId) && !inWorkerPortal,
  });

  const complaints = useQuery({
    queryKey: ['work-orders', departmentId, 'complaints'],
    queryFn: () => complaintRoutingApi.departmentComplaints(departmentId),
    enabled: Boolean(departmentId) && tab === 'raise',
  });

  const roster = (department.data?.staff || []).filter((member) => member.status === 'active');
  // `skills` and `skillIds` are parallel arrays — the label+id pairing the
  // departments DTO uses everywhere — so they are zipped here rather than the
  // select being drawn from names it cannot submit.
  const skills = (department.data?.skillIds || []).map((id, index) => ({
    id,
    name: department.data?.skills?.[index] || 'Unnamed trade',
  }));

  if (!departmentId) {
    return (
      <p className="rounded-2xl border border-amber-100 bg-amber-50 p-6 text-xs font-semibold text-amber-800">
        No department is attached to your account yet, so there is no queue to
        show. An administrator sets this when they create you.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          to={basePath === '/admin' ? `${basePath}/departments/${departmentId}` : basePath}
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-slate-700"
        >
          <ArrowLeft className="h-4 w-4" />
          {basePath === '/admin' ? 'Back to department' : 'Back to overview'}
        </Link>
        <h1 className="mt-3 text-2xl font-extrabold tracking-tight text-slate-900">Work orders</h1>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          Every visit this department has scheduled, and the levers to change one
          by hand.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setParam('tab', id)}
            className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-xs font-bold ${
              tab === id ? 'bg-indigo-600 text-white' : 'border border-slate-200 bg-white text-slate-600'
            }`}
          >
            <Icon className="h-4 w-4" />{label}
          </button>
        ))}
      </div>

      {tab === 'queue' ? (
        <div className="space-y-4">
          {/* The filter narrows on top of the policy and never decides
              visibility: another department's queue comes back empty from
              `can_read_work_order`, not as somebody else's work. */}
          <div className="flex flex-wrap gap-1.5">
            {['', ...WORK_ORDER_STATUSES].map((value) => (
              <button
                key={value || 'all'}
                type="button"
                onClick={() => setParam('status', value)}
                className={`rounded-full px-3 py-1.5 text-[11px] font-bold ${
                  statusFilter === value
                    ? 'bg-slate-800 text-white'
                    : 'border border-slate-200 bg-white text-slate-500'
                }`}
              >
                {value ? statusLabel(value) : 'Everything'}
              </button>
            ))}
          </div>

          {jobId ? (
            <JobDetail
              jobId={jobId}
              roster={roster}
              skills={skills}
              onChanged={invalidate}
              onClose={() => setParam('job', null)}
            />
          ) : null}

          {queue.isPending ? (
            <p className="text-sm font-semibold text-slate-500">Loading the queue…</p>
          ) : queue.error ? (
            <Failure error={queue.error} />
          ) : (queue.data || []).length === 0 ? (
            <Empty>
              {statusFilter
                ? `Nothing in this department is ${statusLabel(statusFilter).toLowerCase()}.`
                : 'No work has been raised in this department yet.'}
            </Empty>
          ) : (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {(queue.data || []).map((order) => (
                <JobRow
                  key={order.id}
                  order={order}
                  selected={order.id === jobId}
                  onOpen={(id) => setParam('job', id)}
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {jobId ? (
            <JobDetail
              jobId={jobId}
              roster={roster}
              skills={skills}
              onChanged={invalidate}
              onClose={() => setParam('job', null)}
            />
          ) : null}

          {complaints.isPending ? (
            <p className="text-sm font-semibold text-slate-500">Loading the complaints…</p>
          ) : complaints.error ? (
            <Failure error={complaints.error} />
          ) : (complaints.data || []).length === 0 ? (
            <Empty>No complaints have been routed to this department.</Empty>
          ) : (
            <div className="space-y-3">
              {(complaints.data || []).map((complaint) => (
                <article
                  key={complaint.id}
                  className="space-y-3 rounded-2xl border border-slate-100 bg-white p-4 shadow-sm"
                >
                  <button
                    type="button"
                    onClick={() =>
                      setParam('complaint', complaint.id === complaintId ? null : complaint.id)}
                    className="flex w-full items-start justify-between gap-3 text-left"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-extrabold text-slate-800">
                        {complaint.title}
                      </p>
                      <p className="mt-0.5 truncate text-[11px] font-semibold text-slate-400">
                        {complaint.raisedBy}
                        {complaint.unitCode ? ` · ${complaint.unitCode}` : ''}
                        {complaint.category ? ` · ${complaint.category}` : ''}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      {complaint.priority ? (
                        <Pill tone={PRIORITY_TONES[complaint.priority]}>{complaint.priority}</Pill>
                      ) : null}
                      {/* The complaint's own status, and it is not the job's.
                          Nothing on this screen writes it: the two are separate
                          state machines over one complaint, and coupling them
                          is the complaint engine's call. */}
                      <Pill>{complaint.status?.replace('_', ' ')}</Pill>
                    </div>
                  </button>

                  {complaint.id === complaintId ? (
                    <ComplaintWorkOrders
                      complaintId={complaint.id}
                      skills={skills}
                      onOpenJob={(id) => setParam('job', id)}
                      onChanged={invalidate}
                    />
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </div>
      )}

      {/* The department read is *context*, and its absence is not a page
          failure. `GET /departments/{id}` is guarded `require_admin_or_manager`
          (`departments.py:47`), and a service-department supervisor holds a
          `worker` membership — so under the worker portal the read is gated off
          above rather than fired and refused, while every work-order endpoint
          admits them. What is lost is the trade list; the roster is not,
          because the assign box reads `GET /work-orders/{id}/candidates`, which
          admits them. One sentence for both arms, because it is true in both:
          the supervisor whose portal never asks, and the admin or manager whose
          ask genuinely failed. */}
      {inWorkerPortal || department.error ? (
        <p className="rounded-2xl border border-slate-100 bg-white p-4 text-[11px] font-semibold text-slate-500">
          This department&apos;s trade list is not available here, so the trade
          box offers nothing to pick and the job takes the trade its complaint
          category implies. Nothing else on this screen is affected.
        </p>
      ) : null}
    </div>
  );
}
