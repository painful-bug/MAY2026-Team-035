// What a work order's status means, and which levers it still has.
//
// **This is a display layer and deliberately not a translation table.**
// `app/domain/work_order_schemas.py` states the rule it is written against: the
// stored vocabulary *is* the wire vocabulary here, because nothing had ever
// rendered a work order and inventing a second set of words would have created
// the divergence `app/domain/vocabularies.py` exists to absorb. So every value
// this module *writes* is the API's own — `statusLabel` produces a sentence for
// a human and never a value for a request body.
//
// ## Why the permissions are here rather than discovered by pressing the button
//
// Every one of the four supervisor writes refuses a closed job with an `HB409`,
// and the two sets of "closed" are **not the same set** — which is the whole
// reason this is a function and not a boolean:
//
//   `update_work_order`     refuses  completed · cancelled
//   `cancel_work_order`     refuses  completed · cancelled
//   `assign_work_order`     refuses  completed · cancelled · failed
//   `reschedule_work_order` refuses  completed · cancelled · failed
//
// A failed visit can still be edited and can still be called off; it cannot be
// re-booked or moved, because `0036` answers a failed visit with a *new* work
// order rather than an edit to the dead one. A screen that offered all four
// verbs on every job would teach a supervisor that two of them randomly error.
//
// The database remains the enforcement. These are what decides whether a
// control is drawn.

/** Every status the CHECK constraint allows, in lifecycle order. */
export const WORK_ORDER_STATUSES = [
  'draft',
  'awaiting_resident',
  'offered',
  'scheduled',
  'in_progress',
  'completed',
  'failed',
  'cancelled',
];

/**
 * The five states in which a job is still *live* — the complement of the three
 * terminal ones (`completed`, `failed`, `cancelled`).
 *
 * This is the same set the backend has always called live:
 * `work_orders_service._OPEN_STATES` and the `get_schedule_request` resolver.
 * It is exported because one live job per complaint is now a **rule**, not a
 * convention: `backend/supabase/migrations/20260827210000_one_live_job_per_complaint.sql`
 * inlines this exact list in a guard on `create_work_order` and answers a
 * second raise with `HB409`. So the screen that draws the raise form and the
 * function that would refuse it must be reading the same five words — a
 * narrower list here draws a form the database will reject, and a wider one
 * hides a form that would have worked.
 */
export const LIVE_WORK_ORDER_STATUSES = [
  'draft',
  'awaiting_resident',
  'offered',
  'scheduled',
  'in_progress',
];

// Closed to an *edit* of what the job is, and to calling it off. A job that has
// already been called off cannot be called off again.
const CLOSED_TO_EDIT = ['completed', 'cancelled'];

// Closed to booking somebody and to moving the hour. `failed` joins the set:
// the answer to a failed visit is a new job, not a second attempt at this one.
const CLOSED_TO_BOOKING = ['completed', 'cancelled', 'failed'];

const LABELS = {
  draft: 'Draft — nothing proposed',
  awaiting_resident: 'Waiting on the resident',
  offered: 'Time settled, nobody booked',
  scheduled: 'Booked',
  in_progress: 'Under way',
  completed: 'Done',
  failed: 'Visit failed',
  cancelled: 'Called off',
};

const TONES = {
  draft: 'bg-slate-100 text-slate-600',
  awaiting_resident: 'bg-amber-50 text-amber-700',
  offered: 'bg-sky-50 text-sky-700',
  scheduled: 'bg-indigo-50 text-indigo-700',
  in_progress: 'bg-blue-50 text-blue-700',
  completed: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-rose-50 text-rose-700',
  cancelled: 'bg-slate-100 text-slate-500',
};

// The assignment's own five words, which are not the job's. An assignment is
// `withdrawn` when somebody else was put on the job; the job itself never is.
const ASSIGNMENT_LABELS = {
  offered: 'offered',
  accepted: 'holds it',
  declined: 'declined',
  withdrawn: 'withdrawn',
  completed: 'completed it',
  failed: 'could not do it',
};

/** A sentence for a human. Unknown words come back as themselves, readably. */
export function statusLabel(status) {
  if (!status) return 'Unknown';
  return LABELS[status] || String(status).replace(/_/g, ' ');
}

/** Tailwind classes for the status pill. */
export function statusTone(status) {
  return TONES[status] || 'bg-slate-100 text-slate-600';
}

/** What became of one offer. */
export function assignmentLabel(status) {
  if (!status) return 'unknown';
  return ASSIGNMENT_LABELS[status] || String(status).replace(/_/g, ' ');
}

/**
 * Which of the four supervisor writes this job will still accept.
 *
 * `slotRequiredToAssign` is the fifth answer and the one a supervisor cannot
 * guess: a job with no hour *can* be assigned, but only by sending an hour with
 * the assignment — `assign_work_order` coalesces the request's slot over the
 * job's and refuses when both are null, because the overlap constraint is
 * partial on `scheduled_start_at is not null` and a booking it cannot see is a
 * calendar that is quietly wrong.
 *
 * @param {{ status?: string, scheduledStartAt?: string|null, scheduledEndAt?: string|null }} order
 */
export function permittedActions(order) {
  const status = order?.status || '';
  const hasSlot = Boolean(order?.scheduledStartAt && order?.scheduledEndAt);

  return {
    edit: !CLOSED_TO_EDIT.includes(status),
    cancel: !CLOSED_TO_EDIT.includes(status),
    assign: !CLOSED_TO_BOOKING.includes(status),
    reschedule: !CLOSED_TO_BOOKING.includes(status),
    slotRequiredToAssign: !hasSlot,
  };
}
