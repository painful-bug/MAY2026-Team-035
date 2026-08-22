import { api } from '../../lib/api/client';

// The supervisor triage dashboard's calls.
//
// Same shape as `features/complaints/routingApi.js` and
// `features/worker/workerApi.js`: no state, no caching, no error translation.
// react-query owns all three and is already mounted.
//
// **Why a module of its own rather than two more lines in `routingApi`.** That
// file answers one question — *which department owns this complaint* — and its
// endpoints live behind the routing router. These two are the supervisor's
// working surface: an aggregate read that replaces the N+1 the triage screen
// does today, and the write that records who picked a complaint up. Folding
// them in would have suggested they share a guard and an audience with the
// admin's allotment queue, which they do not.
//
// **Every call here is a frozen contract** (`docs/plans/SUPERVISOR_TRIAGE_SPEC.md`
// and its amendment 2), and as of this writing all but `staffComplaintDetail`
// await a hand-applied migration: `taken_up_at`, `started_at`,
// `supervision_inherited_at`, the complaint thread kind, and the four
// amendment-2 RPCs. Until it lands they 404, which is why every test that
// exercises this dashboard mocks the boundary rather than the server.

const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });

export const triageApi = {
  /**
   * All five sections of one department's dashboard, in one read.
   *
   * The bucketing is the server's and the browser never re-does it. Guarded at
   * the database boundary by `can_supervise_department`, the same posture as
   * `GET /departments/{id}/complaints` — so the id in the URL is a scope and
   * never an authorization decision.
   */
  snapshot: (departmentId) => api(`/departments/${departmentId}/triage-snapshot`),

  /**
   * "I have this one."
   *
   * No body: everything the write needs is the complaint in the path and the
   * caller in the session. Stamps `taken_up_by_membership_id` + `taken_up_at`
   * and moves the storage status `open → acknowledged`, which the resident
   * already reads as "In Progress". It is *triage ownership* and not dispatch —
   * `assigned_to_membership_id` stays dead (handoff §15 ruling 1, restated in
   * §18 ruling 1) and work still reaches a worker only through a work order.
   *
   * A 409 is the interesting refusal: somebody else got there first, and the
   * message names them.
   */
  takeUp: (complaintId) => post(`/complaints/${complaintId}/take-up`),

  // --- amendment 2: the action surface ---------------------------------------

  /**
   * One complaint as staff read it: the row and every event on it.
   *
   * `{ complaint, events[] }`, and **neither half is the resident's DTO** —
   * `staff_complaint_detail` hands back `to_jsonb(complaints_row)` and the raw
   * `complaint_events` rows with a rendered `message` added, so the keys are the
   * database's and the vocabulary is storage's. `lib/triageDisplay.js` owns that
   * seam (`staffComplaintFields`, `timelineEntries`) rather than the popup.
   *
   * The internal notes below are in this list and are **not** in the resident's:
   * `resident_complaints_service` hides `note_added` events whose payload
   * carries `internal: true`. Amendment 2 widens the router guard from
   * `require_admin` to active membership; the RPC's
   * `is_community_admin OR can_supervise_department` was always the real
   * boundary and is unchanged.
   */
  staffComplaintDetail: (complaintId) => api(`/complaints/staff/complaints/${complaintId}`),

  /**
   * "This is done." — the supervisor's resolve (ruling A2).
   *
   * Not a status dropdown. It cancels every unstarted job on the complaint and
   * notifies whoever held them, and it **refuses `HB409` while any job is
   * `in_progress`** — "finish or cancel the running job first". That refusal is
   * the interesting answer and the screen shows it verbatim on the card it
   * belongs to, exactly as it does the take-up 409.
   */
  resolve: (complaintId) => post(`/complaints/${complaintId}/resolve`),

  /**
   * One step up the scale, never down: `Low → Medium → High`, `HB409` at High.
   *
   * Load-bearing rather than cosmetic — High is what arms the dispatch engine's
   * automatic force-assign when every worker declines. The resident sees the
   * step on their timeline (`priority_changed`); nobody is notified, because a
   * field change is a passive one under ARCHITECTURE.md's rule.
   */
  raisePriority: (complaintId) => post(`/complaints/${complaintId}/priority-raise`),

  /**
   * A permanent internal note on the complaint's timeline. 1–2000 characters.
   *
   * Staff and workers read it; the resident does not (ruling A5) — the payload
   * carries `internal: true` and the resident projection drops those. The
   * admin's resident-visible "Update from management" note is a different write
   * on a different endpoint and is untouched. Append-only: no edit, no delete,
   * because a timeline somebody can rewrite is not a record.
   */
  addNote: (complaintId, note) => post(`/complaints/${complaintId}/notes`, { note }),

  /**
   * Open — or re-open — the chat thread about this complaint. `{ threadId }`.
   *
   * Idempotent on the complaint (ruling A1): one thread per complaint, the
   * raiser and the department's supervisors in it, so a second supervisor joins
   * the conversation rather than starting a parallel one the resident has to
   * watch. The caller then dispatches `hb:chat-open` with the id and the dock
   * takes it from there.
   */
  openChat: (complaintId) => post(`/complaints/${complaintId}/chat`),
};
