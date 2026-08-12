import { api } from '../../lib/api/client';

// The supervisor's side of a work order: raise it, edit it, book somebody,
// move it, call it off.
//
// Same shape as `features/hiring/hiringApi.js` and
// `features/complaints/routingApi.js`: no state, no caching, no error
// translation. react-query is already mounted and owns all three.
//
// **Eight operations and three different ids in the path**, which is the API's
// own division and not a grouping invented here. A complaint owns the *creation*
// of work (`/complaints/{id}/work-orders`) because a job exists to answer one;
// a department owns the *queue* (`/departments/{id}/work-orders`) because that
// is who is looking at it; and every job that already exists is addressed by its
// own id, because by then the complaint it came from is history rather than
// identity — `0036` lets one complaint carry several jobs, so the complaint is
// not a way to name one of them.
//
// **Nothing here decides who may call what.** The router guard admits every kind
// of staff on purpose and `can_supervise_department` inside Postgres is the
// boundary; a department id in one of these paths is a subject, never a
// permission. Re-stating the rule in the browser would be a second copy of it
// with nothing keeping the two in step.

const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });
const patch = (path, body = {}) => api(path, { method: 'PATCH', body: JSON.stringify(body) });

const query = (params) => {
  const pairs = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== ''
  );
  const search = new URLSearchParams(pairs).toString();
  return search ? `?${search}` : '';
};

export const workOrdersApi = {
  // --- raising work against a complaint --------------------------------------
  /**
   * Every job raised against one complaint, newest first.
   *
   * A read rather than a derivation from the timeline. `complaint_events`
   * records *that* a job was scheduled, which is the right shape for a
   * narrative and the wrong one for "is anybody coming on Tuesday".
   */
  forComplaint: (complaintId) => api(`/complaints/${complaintId}/work-orders`),

  /**
   * Triage. `{ departmentId?, skillId?, subjectKind, locationText?, note?,
   * scheduledStartAt?, scheduledEndAt? }`.
   *
   * **Sending no slot is the other half of the fork, not an incomplete
   * request.** No slot creates a `draft` — the supervisor wants to ask the
   * resident something first and the conversation carries on in the complaint's
   * comments. A slot proposes a visit: `awaiting_resident` on a `resident` job,
   * straight to `offered` on a `facility` one, because there is nobody whose
   * door is being knocked on.
   *
   * `departmentId` and `skillId` are both derived when omitted, and `priority`
   * is not a field at all — a job's urgency *is* the complaint's.
   */
  create: (complaintId, payload) => post(`/complaints/${complaintId}/work-orders`, payload),

  // --- the queue -------------------------------------------------------------
  /**
   * One department's queue, soonest first with the unscheduled underneath.
   *
   * `status` narrows on top of the policy and never decides visibility: asking
   * for another department's queue returns an empty list from
   * `can_read_work_order`, not somebody else's work.
   */
  forDepartment: (departmentId, params = {}) =>
    api(`/departments/${departmentId}/work-orders${query(params)}`),

  // --- one job ---------------------------------------------------------------
  /**
   * The job and every offer ever made on it.
   *
   * `assignments` is a history, not a holder: withdrawn and declined rows stay,
   * because "we sent Ravi and he could not get in, so we sent Anil" is the
   * question a supervisor actually asks. The current holder is the top-level
   * `assigneeName`.
   */
  detail: (workOrderId) => api(`/work-orders/${workOrderId}`),
  candidates: (workOrderId, { includeExcluded = false } = {}) =>
    api(`/work-orders/${workOrderId}/candidates${includeExcluded ? '?includeExcluded=true' : ''}`),

  /**
   * Change what the job is: `{ skillId?, subjectKind?, locationText?, priority? }`.
   *
   * **Not the time and not the state.** Those have their own calls below,
   * because each carries a rule and a notification that a general-purpose
   * `PATCH` is exactly the shape to skip. The request model has no field for
   * either, so sending one changes nothing rather than failing.
   */
  update: (workOrderId, payload) => patch(`/work-orders/${workOrderId}`, payload),

  /**
   * Book somebody, and book their hour. `{ staffAssignmentId, scheduledStartAt?,
   * scheduledEndAt? }`.
   *
   * The slot is optional and defaults to the job's own, so sending one assigns
   * and reschedules in a single write — the common case, where the supervisor
   * picked the person and the hour at the same moment. A job with *no* hour at
   * all cannot be assigned: the overlap constraint is partial on
   * `scheduled_start_at is not null`, so booking somebody for no particular
   * hour is what leaves a calendar wrong. That is the `409`
   * *"Schedule this job before assigning it."*
   *
   * The other `409` this call exists to produce is the double-booking, refused
   * by name and refused again by the constraint underneath.
   */
  assign: (workOrderId, payload) => post(`/work-orders/${workOrderId}/assign`, payload),

  /**
   * Move the visit. `{ scheduledStartAt, scheduledEndAt, note? }` — both ends
   * required, because the accepted assignment's range moves with the job and a
   * range needs two ends.
   *
   * **The supervisor's alone.** A resident may confirm a proposed time and may
   * decline it; by the time somebody is booked it is a change to two people's
   * days and only one of them is on this screen.
   */
  reschedule: (workOrderId, payload) => post(`/work-orders/${workOrderId}/reschedule`, payload),

  /**
   * Call the job off. `{ reason }`, required and at least three characters.
   *
   * Terminal, and it takes the assignment with it — a cancelled job that left
   * an accepted assignment standing would block an hour in a worker's calendar
   * for work nobody is going to do. The reason reaches both the worker and the
   * resident in a notification, which is why it cannot be omitted and why this
   * is a `POST` rather than a `DELETE`.
   */
  cancel: (workOrderId, reason) => post(`/work-orders/${workOrderId}/cancel`, { reason }),
};
