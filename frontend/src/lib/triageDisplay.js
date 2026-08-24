// Every display decision the supervisor triage dashboard makes, in one file
// with no React in it.
//
// The dashboard renders five arrays the server has already bucketed
// (`docs/plans/SUPERVISOR_TRIAGE_SPEC.md`, "Bucketing is decided server-side").
// So there is very little for the browser to *decide* — and the handful of
// decisions that remain are all about how a row looks, which is exactly the set
// worth pulling out of the page: they are pure, they are the things a test can
// pin cheaply, and every one of them was frozen in the spec rather than left to
// the screen.
//
// `communityColor.js` is the model for the palette half, deliberately: a stable
// hash indexing a fixed palette needs no column, no migration and no field in
// any API response, and the same trade is the same colour on every device
// because nothing was ever written down to drift.

// The eight, spelled out in full. Tailwind scans source text, so a composed
// `bg-${name}-50` is scanned as nothing and the chip renders transparent —
// the same trap `communityColor.js` names.
//
// Chosen to stay clear of the three priority tones below where it matters:
// rose and amber are the High/Medium colours, so neither is in this palette.
// A category chip that looked like a priority chip would be a screen with two
// vocabularies in one colour.
const CATEGORY_PALETTE = Object.freeze([
  'bg-sky-50 text-sky-700 ring-sky-200',
  'bg-emerald-50 text-emerald-700 ring-emerald-200',
  'bg-violet-50 text-violet-700 ring-violet-200',
  'bg-teal-50 text-teal-700 ring-teal-200',
  'bg-indigo-50 text-indigo-700 ring-indigo-200',
  'bg-orange-50 text-orange-700 ring-orange-200',
  'bg-cyan-50 text-cyan-700 ring-cyan-200',
  'bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200',
]);

const CATEGORY_NEUTRAL = 'bg-slate-50 text-slate-600 ring-slate-200';

/**
 * A category's chip classes, derived from its name and never stored.
 *
 * The name is lowercased and trimmed before hashing, so "Plumbing", "plumbing"
 * and " Plumbing " are one colour. Categories are free text per community
 * (`complaint_categories.name`), which is why the key is the name and not an id:
 * two societies that both call it "Plumbing" get the same colour, and a
 * supervisor who works in both reads one screen instead of two.
 */
export function categoryChipClass(category) {
  const key = String(category ?? '').trim().toLowerCase();
  if (!key) return CATEGORY_NEUTRAL;
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash * 31 + key.charCodeAt(i)) | 0;
  }
  return CATEGORY_PALETTE[Math.abs(hash) % CATEGORY_PALETTE.length];
}

// Frozen in the spec: High = rose, Medium = amber, Low = slate. Unknown words
// fall to slate rather than to nothing, because a chip with no classes is an
// invisible chip and the label still has to be readable.
const PRIORITY_TONES = Object.freeze({
  high: 'bg-rose-50 text-rose-700 ring-rose-200',
  medium: 'bg-amber-50 text-amber-700 ring-amber-200',
  low: 'bg-slate-100 text-slate-600 ring-slate-200',
});

/** Tailwind classes for the priority chip. */
export function priorityChipClass(priority) {
  return PRIORITY_TONES[String(priority ?? '').trim().toLowerCase()] || PRIORITY_TONES.low;
}

/**
 * The word on the priority chip, and it is always drawn.
 *
 * Colour alone would put the one field a supervisor triages on into a channel
 * a colour-blind reader cannot use, so the spec froze "text label always
 * present" and this is the half that guarantees it. The wire already sends
 * `High|Medium|Low`; anything else is shown as itself rather than swallowed.
 */
export function priorityLabel(priority) {
  const word = String(priority ?? '').trim();
  if (!word) return 'Unrated';
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
}

/** True for the priority that gets pinned to the top of section 1. */
export const isUrgent = (priority) => String(priority ?? '').trim().toLowerCase() === 'high';

/**
 * Section 1's urgent stack: High on top, everything else under it, **order
 * only**.
 *
 * This is the one rearrangement the browser is allowed to make, and the spec
 * says so in as many words — "the frontend pins the urgent stack itself" — for
 * a reason worth writing down: it is a *sort*, not a bucket. Nothing is
 * dropped, nothing moves between arrays, and the server's newest-first order
 * survives inside each half because this partition is stable. Re-bucketing here
 * is precisely what the contract forbids, and a partition that lost or
 * duplicated a row would be re-bucketing with extra steps.
 */
export function pinUrgent(complaints) {
  const rows = Array.isArray(complaints) ? complaints : [];
  const urgent = rows.filter((row) => isUrgent(row?.priority));
  const rest = rows.filter((row) => !isUrgent(row?.priority));
  return { urgent, rest };
}

/**
 * The "reassigned" badges of section 1, as data.
 *
 * All three ride on fields the complaint engine already exposes
 * (`docs/COMPLAINT_ENGINE_HANDOFF.md` §18), and the wording is the spec's. They
 * are returned as a list rather than drawn here so the page keeps every element
 * and this file keeps every rule.
 */
export function reassignmentBadges(complaint) {
  const badges = [];
  if (complaint?.returnedToPoolAt) badges.push('Returned to pool');
  const reopened = Number(complaint?.reopenedCount ?? 0);
  if (reopened > 0) badges.push(`Reopened ×${reopened}`);
  if (complaint?.reroutedAt) badges.push('Moved to this department');
  return badges;
}

/**
 * The badges a **work order** card carries in sections 3–5.
 *
 * One entry today: `inheritedAt` (`work_orders.supervision_inherited_at`),
 * stamped by `restamp_department_supervision` when a departure moved this job's
 * supervision to whoever is reading the screen. Deferred from v1 by decision 3
 * and shipped here, because a job you did not raise and did not book is a
 * different thing to be answerable for than one you did.
 */
export function workOrderBadges(order) {
  return order?.inheritedAt ? ['Inherited'] : [];
}

// ---------------------------------------------------------------------------
// The vocabulary seam the eye popup lands on
// ---------------------------------------------------------------------------

// `GET /complaints/staff/complaints/{id}` answers `to_jsonb(complaints_row)` —
// the **storage** words (`open`, `acknowledged`, `high`), snake-cased, because
// the RPC hands the row back whole and `StaffComplaintDetail` types it as an
// opaque dict rather than a model that could translate it. The snapshot's
// `TriageComplaint.status` is already the wire word. So one screen shows both
// vocabularies, and this is the one place that knows it.
//
// Values copied from `app/domain/vocabularies.py::_COMPLAINT_STATUS_TO_WIRE`,
// including its asymmetry: `closed` reads as `Resolved`, because the frontend's
// status vocabulary has no fourth word.
const STORAGE_STATUS_TO_WIRE = Object.freeze({
  open: 'Pending',
  acknowledged: 'In Progress',
  in_progress: 'In Progress',
  resolved: 'Resolved',
  closed: 'Resolved',
  cancelled: 'Cancelled',
});

/**
 * A complaint status as the screen says it, from either vocabulary.
 *
 * A wire word (`Pending`) passes through as itself; a storage word (`open`)
 * is translated. Anything else is shown as itself rather than swallowed —
 * the enum growing is not a reason for a card to render a blank chip.
 */
export function complaintStatusLabel(status) {
  const word = String(status ?? '').trim();
  if (!word) return 'Pending';
  const wire = STORAGE_STATUS_TO_WIRE[word.toLowerCase()];
  if (wire) return wire;
  return word.charAt(0).toUpperCase() + word.slice(1);
}

/** The chip tone for a complaint status, in either vocabulary. */
export function complaintStatusChipClass(status) {
  const label = complaintStatusLabel(status);
  if (label === 'Resolved') return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  if (label === 'In Progress') return 'bg-indigo-50 text-indigo-700 ring-indigo-200';
  if (label === 'Cancelled') return 'bg-slate-100 text-slate-500 ring-slate-200';
  return 'bg-slate-100 text-slate-600 ring-slate-200';
}

// ---------------------------------------------------------------------------
// Section 5's clock
// ---------------------------------------------------------------------------

/**
 * How long a job has been under way, as a human says it.
 *
 * Whole minutes under an hour, then hours and minutes; a `startedAt` in the
 * future (clock skew between a phone that pressed Start and this browser) reads
 * as `just now` rather than as a negative duration.
 */
export function elapsedSince(startedAt, now = Date.now()) {
  if (!startedAt) return null;
  const started = new Date(startedAt).getTime();
  if (Number.isNaN(started)) return null;
  const minutes = Math.floor((now - started) / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

// ---------------------------------------------------------------------------
// Priority, one way
// ---------------------------------------------------------------------------

/**
 * Whether `POST /complaints/{id}/priority-raise` has anywhere to go.
 *
 * The raise is one-way, `Low → Medium → High`, and `raise_complaint_priority`
 * refuses `HB409` at the top. The button stays on the card at High and is
 * disabled with `raisePriorityBlockedReason` as its title: a control that
 * vanished at the top of the scale would leave a supervisor wondering whether
 * the feature exists, and one that posted would teach them it errors at random.
 */
export function canRaisePriority(priority) {
  return !isUrgent(priority);
}

export function nextPriority(priority) {
  return String(priority ?? '').trim().toLowerCase() === 'medium' ? 'High' : 'Medium';
}

export function raisePriorityBlockedReason(priority) {
  return canRaisePriority(priority)
    ? null
    : 'This is already High — the top of the scale, and the level that arms the automatic force-assign.';
}

// ---------------------------------------------------------------------------
// The staff timeline
// ---------------------------------------------------------------------------

// The label above each timeline line, keyed on `complaint_events.event_type`.
// The *sentence* under it is the server's `message`; this is the noun for the
// kind of thing that happened, which the staff detail does not send.
const EVENT_LABELS = Object.freeze({
  raised: 'Raised',
  status_changed: 'Status changed',
  note_added: 'Internal note',
  comment_added: 'Comment',
  assigned: 'Assigned',
  progress_changed: 'Progress',
  reopened: 'Reopened',
  resolution_confirmed: 'Resident confirmed',
  taken_up: 'Taken up',
  priority_changed: 'Priority raised',
  department_changed: 'Moved department',
  job_created: 'Job raised',
  job_scheduled: 'Visit scheduled',
  job_assigned: 'Worker booked',
  job_declined: 'Time declined',
  job_force_assigned: 'Assigned outright',
  // Ruling R8's own word. `job_assigned` is stamped beside it, so this is the
  // line that says *who* — a supervisor stepping outside the norm rather than
  // a technician being booked onto the job.
  job_taken_up: 'Took up the job themselves',
  job_started: 'Work started',
  job_completed: 'Work finished',
  job_failed: 'Visit failed',
  job_cancelled: 'Job called off',
  returned_to_pool: 'Returned to pool',
});

const text = (value) => (typeof value === 'string' ? value.trim() : '');

// Both spellings of every key, always. The staff detail's `complaint` and
// `events` are `dict[str, Any]` on the Python side, so `CamelModel`'s alias
// generator never reaches inside them and the keys arrive snake-cased — except
// `message`, which the service adds, and except whatever a later backend change
// decides to project properly. Reading both is three lines here and no bug
// later.
const pick = (row, ...names) => {
  for (const name of names) {
    const value = row?.[name];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return null;
};

/**
 * The staff detail's `events[]`, ready to draw.
 *
 * **Not the resident's timeline.** `resident_complaints_service` hides
 * `note_added` events carrying `internal: true`; this list is the staff side and
 * shows them, marked, because that is the whole point of an internal note. The
 * order is the RPC's (`order by created_at`) and is not re-sorted here.
 *
 * A blank `message` is filled from the payload where this file can do it
 * honestly — `priority_changed` is the amendment's new word and an older
 * backend renders it as an empty string, which would draw a timeline line with
 * no sentence on it.
 */
export function timelineEntries(events) {
  const rows = Array.isArray(events) ? events : [];
  return rows.map((row, index) => {
    const type = String(pick(row, 'eventType', 'event_type') || '').trim();
    const payload = (typeof row?.payload === 'object' && row.payload) || {};
    const internal = payload.internal === true;
    let message = text(row?.message);
    if (!message && type === 'priority_changed') {
      const to = text(payload.to);
      message = to
        ? `The department raised the priority to ${priorityLabel(to)}.`
        : 'The department raised the priority.';
    }
    if (!message && type === 'note_added') message = text(payload.note);
    return {
      id: String(pick(row, 'id') || `${type}-${index}`),
      eventType: type,
      label: EVENT_LABELS[type] || (type ? type.replace(/_/g, ' ') : 'Event'),
      message,
      internal,
      actorName: text(pick(row, 'actorName', 'actor_name', 'actorLabel', 'actor_label')),
      createdAt: pick(row, 'createdAt', 'created_at'),
    };
  });
}

/**
 * The complaint half of the staff detail, in the keys this app speaks.
 *
 * Same two-spelling rule as above, and the same reason: the row arrives as
 * Postgres wrote it. Nothing is invented — a field the row does not carry comes
 * back null and the screen says so.
 */
export function staffComplaintFields(complaint) {
  const row = complaint || {};
  return {
    id: pick(row, 'id'),
    title: text(pick(row, 'title')),
    description: text(pick(row, 'description')),
    category: text(pick(row, 'category')),
    priority: pick(row, 'priority'),
    status: pick(row, 'status'),
    location: text(pick(row, 'location')),
    createdAt: pick(row, 'createdAt', 'created_at'),
    dueAt: pick(row, 'dueAt', 'expectedResolutionAt', 'expected_resolution_at'),
    resolvedAt: pick(row, 'resolvedAt', 'resolved_at'),
    takenUpAt: pick(row, 'takenUpAt', 'taken_up_at'),
    returnedToPoolAt: pick(row, 'returnedToPoolAt', 'returned_to_pool_at'),
    reopenedCount: Number(pick(row, 'reopenedCount', 'reopened_count') ?? 0),
  };
}
