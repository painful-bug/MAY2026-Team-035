# The resident sets the time — frozen build spec (2026-08-23)

Product owner rulings (recorded in `docs/COMPLAINT_ENGINE_HANDOFF.md` §23):

- **F1** — the raise-job form loses its date/time fields for everyone. A
  resident-subject job asks the RESIDENT to pick the date and time (a request
  on their dashboard, like a hiring application reaching a manager); only when
  they set it does the job reach the open pile. A facility job is
  auto-assigned by the system into the first available slot — but only after
  all urgent (`priority = 'high'`) resident complaints in the department have
  been allotted.
- **F2** — if the resident has not picked within 24 hours of the raise, the
  system sets the first available time after the 24-hour mark that has a
  serviceman available to take the job, and assigns that serviceman
  automatically.
- **F3** — the resident's card offers a time picker only; there is no decline
  in pick-mode (the existing decline stays on the supervisor-proposed
  reschedule flow). Silence is answered by F2.
- A new **"Awaiting resident response"** section surfaces the waiting jobs on
  the supervisor dashboard.

Deviations require an orchestrator decision before they land. Two specialists
build this in parallel — **Agent A (SQL + backend)** and **Agent B
(frontend)** — against the frozen interface below; neither may touch the
other's file set.

## Recon facts the design leans on (verified, cited)

- `create_work_order` status decision is 0036_work_orders.sql:717-727: null
  slot → `draft`; resident+slot → `awaiting_resident` + `resident_deadline_at
  = now()+24h`; facility+slot → `offered`. Declared once, never overridden —
  a forward-only redefinition is safe.
- The deadline is already ACTED on: trigger `work_orders_sync_dispatch`
  (live body 20260823120000:10-56) arms a `resident_timeout` task in
  `dispatch_tasks`; the Python dispatcher (backend/app/core/dispatcher.py,
  15s poll, started in the FastAPI lifespan) calls `fire_dispatch_task`
  (live body 20260813104000:111-121) → `dispatch_resident_timeout`
  (0037:821), which today flips the job to `offered` keeping the
  supervisor's proposed slot.
- `dispatch_candidates` (live 20260823120000:118/276) is slot-gated — its job
  CTE requires `scheduled_start_at is not null`, and every availability /
  leave / working-hours / overlap clause is keyed to the job's stored slot.
  Ranking: `adjacent desc, load asc, km asc nulls last, sa_display_name`.
- `respond_to_work_order_schedule` (0036:796) only accepts
  confirmed|declined and only in `awaiting_resident`; declined → `draft`
  with the slot cleared. `reschedule_work_order` (0036:937) re-enters
  `awaiting_resident` WITH a slot (approve-mode) — untouched by this build.
- Constraints that force design choices: `work_orders_status_check`
  (0036:147-151, closed list — avoid a new status);
  `complaint_events_type_check` (20260822170000:1021-1025, closed 26-word
  list — avoid a new event word); `dispatch_tasks_kind_check`
  (20260813104000:5-7, closed list — the ONE constraint this build widens).
- `sync_dispatch_tasks`'s final `else` cancels every timer on an
  unrecognized status; `fire_dispatch_task`'s `else` arm silently swallows
  unknown kinds. Both must gain explicit handling for anything new.
- The board (20260823170000) already excludes `awaiting_resident` (D1 status
  list is `('draft','offered')`), so "not in the pile until the resident
  answers" needs NO board change.
- Six triggers fire on `work_orders` writes; the slot-finder must therefore
  never probe by writing hypothetical slots to the row.

## Adjudications (orchestrator, logged before build)

- **G1 — the API keeps accepting a slot; behavior forks on its presence.**
  `POST /complaints/{id}/work-orders` keeps `scheduledStartAt/EndAt`
  (backward compat; a slotted raise keeps today's semantics exactly:
  resident+slot → approve-mode `awaiting_resident`, facility+slot →
  `offered`). New behavior is for SLOTLESS raises only: resident →
  `awaiting_resident`, null slot, `resident_deadline_at = now()+24h`
  (pick-mode); facility → `draft` + a `facility_auto_assign` task due
  `now()`. The frontend form drops the fields, so all UI raises take the new
  path.
- **G2 — no new status.** Pick-mode is `status = 'awaiting_resident' AND
  scheduled_start_at IS NULL`; approve-mode is the same status with a slot.
  The existing sync trigger already arms `resident_timeout` on any
  `awaiting_resident` entry — pick-mode inherits the timer for free.
- **G3 — the resident's write is a new RPC, complaint-scoped like its
  siblings.** `resident_set_work_order_schedule(p_work_order_id, p_start,
  p_end)`; the endpoint resolves the newest live job via the existing
  `_live_work_order` path. Guards in order:
  `is_own_membership(raised_by_membership_id)` else HB403; status =
  `awaiting_resident` else HB409 "There is nothing to schedule on this
  complaint right now."; `scheduled_start_at IS NULL` else HB409 "The
  association proposed this visit's time — answer that instead."; `p_end >
  p_start` and `p_start > now()` else HB409. Writes slot + `status =
  'offered'` + deadline cleared; event `job_scheduled` (existing word) with
  payload `resident_set: true`; supervisor notified with new kind
  `work_order.resident_scheduled` (kinds are unconstrained). `offered` arms
  the existing `manual_window` machinery and puts the job on the board —
  the pile, exactly as ruled.
- **G4 — the slot-finder probes hypothetical slots without writing them.**
  Refactor: new `dispatch_candidates_at(p_work_order_id, p_start, p_end,
  p_limit, p_include_all)` carries the current `dispatch_candidates` body
  with the hypothetical slot substituted for the stored one; the existing
  3-arg `dispatch_candidates` becomes a thin delegate passing the job's own
  slot (identical signature, grants, and ordering — single source of truth,
  no fork). New `find_first_available_slot(p_work_order_id, p_from)`:
  duration **2 hours** (hardcoded with a comment, like the 24h), candidate
  starts at each top-of-hour from the first whole hour ≥ `p_from`, horizon
  **14 days**; the first start where `dispatch_candidates_at` returns a row
  wins, and its top-ranked candidate is the pick.
- **G5 — the resident timeout branches on the discriminator.**
  `dispatch_resident_timeout`: slot present → today's behavior unchanged
  (proceed to `offered`). Slot null (pick-mode expired) →
  `find_first_available_slot(now())`; on a hit: withdraw stray `offered`
  assignment rows, insert `accepted` (`is_auto_assigned = true, is_forced =
  false`, `offered_at = responded_at = now()`), write the found slot +
  `status = 'scheduled'`, event `job_assigned` payload
  `{auto_assigned: true}`, notify worker + resident with
  `work_order.assigned` (found slot in payload), supervisor with new kind
  `work_order.auto_assigned` ("<worker> was auto-assigned to <job>"). On no
  hit within the horizon: `status = 'draft'`, deadline cleared (job lands on
  the open board, claimable), supervisor notified `work_order.no_candidates`.
- **G6 — facility auto-assign is a new task kind with a courtesy gate.**
  Widen `dispatch_tasks_kind_check` with `facility_auto_assign`
  (drop/re-add). Arm in `sync_dispatch_tasks` (redefined, provably last): on
  INSERT only, `subject_kind = 'facility' and status = 'draft'`, due
  `now()`. Handler `dispatch_facility_auto_assign(p_work_order_id)`: bail
  (complete) unless still `draft`, facility, and no live assignment (a board
  claim won the race — fine). Gate: if any work order in the same
  department with `subject_kind = 'resident'`, `priority = 'high'`, status
  in `('draft','awaiting_resident','offered')` and no live
  (`offered|accepted`) assignment exists → complete this task and enqueue a
  fresh `facility_auto_assign` due `now() + interval '1 hour'` (re-checked
  hourly; the job stays claimable on the board the whole time, so it is
  never stranded). Gate clear: `find_first_available_slot(now())` → assign
  exactly as G5's hit branch; no hit → notify supervisor
  `work_order.no_candidates` once and complete (job stays on the board).
  `fire_dispatch_task` gains the `when 'facility_auto_assign'` arm
  (redefined, provably last).
- **G7 — the sixth triage bucket.** `supervisor_triage_snapshot`
  (20260822170000:1198-1227) redefined: new `awaiting_resident` array (rows
  `not committed and status = 'awaiting_resident'`, newest first);
  `open_requests` drops them (now `draft`/`offered` only). `TriageSnapshot`
  (backend/app/domain/supervisor_triage_schemas.py) gains the field
  (`awaitingResident` on the wire). Frontend renders it as a new
  `<Section id="triage-awaiting-resident">` titled **"Awaiting resident
  response"** between `triage-taken-up` and `triage-open-requests`,
  arrays-as-is per the existing contract.
- **G8 — the board predicate does not change.** `awaiting_resident` was
  already off it; drafts stay claimable (ruling C3), including a facility
  draft inside the gate window (the claim simply wins and the task no-ops).
- **G9 — the ordering tests get re-anchored, not patched a third time.** The
  three NEW_FILES-style migration-ordering tests are converted to the
  named-predecessor idiom (`test_complaint_engine_v2_repair_migration.py:31-33`),
  clearing the E1 backlog item; the new migration's own test asserts it
  sorts after `20260823170000_open_jobs_board.sql` by name.
- **G10 — constants stay hardcoded** in the engine's style: 24h deadline
  (four existing sites untouched), 2h synthesized duration, 14-day horizon,
  1h gate retry — each with a comment saying what it is.
- **G11 — no resident snapshot / DashboardHome change in v1.** The bell
  notification (existing kind `work_order.schedule_requested`, payload gains
  `mode: 'pick'`) plus the complaint-thread card carry the request. A
  home-page nudge is logged as follow-up, not built.

## Frozen interface

### Migration — `backend/supabase/migrations/20260823180000_resident_sets_the_time.sql`
Sorts after `20260823170000_open_jobs_board.sql`. Hand-applied by the owner
(AFTER §27); the build MUST NOT attempt to apply it. Contents, in order:

1. Widen `dispatch_tasks_kind_check` with `facility_auto_assign`.
2. `dispatch_candidates_at(...)` + delegate redefinition of the 3-arg
   `dispatch_candidates` (G4). Preserve the 2-arg wrapper untouched.
3. `find_first_available_slot(p_work_order_id uuid, p_from timestamptz)`
   returns `(slot_start timestamptz, slot_end timestamptz,
   staff_assignment_id uuid)` (G4).
4. Redefine `create_work_order` (G1; slotless-resident branch notifies the
   resident `work_order.schedule_requested` with `mode:'pick'` and url
   `/resident/complaints?complaint=…`; slotless-facility branch relies on
   the trigger to arm its task — do not enqueue inside `create_work_order`).
5. `resident_set_work_order_schedule(p_work_order_id uuid, p_start
   timestamptz, p_end timestamptz)` (G3).
6. Redefine `dispatch_resident_timeout` (G5).
7. `dispatch_facility_auto_assign(p_work_order_id uuid)` + redefine
   `sync_dispatch_tasks` + redefine `fire_dispatch_task` (G6).
8. Redefine `supervisor_triage_snapshot` (G7).
9. Grants: revoke-then-grant per each function's existing audience
   (`resident_set_work_order_schedule` → authenticated; dispatch internals →
   service_role only, matching their current grants); `notify pgrst,
   'reload schema';`
10. In-transaction `do $$` proofs in the 20260823120000/170000 style:
    to_regprocedure checks, body-position checks proving each redefinition
    is last, and the widened kind CHECK accepts `facility_auto_assign`.

### Backend (Agent A)
- `GET /api/v1/complaints/{complaint_id}/schedule-request` response gains
  `mode: "approve" | "pick"` (`pick` iff awaiting + null slot). Existing
  fields unchanged (null proposed times in pick-mode).
- NEW `POST /api/v1/complaints/{complaint_id}/schedule-time`, body
  `{startAt, endAt}` (ISO, both required), CSRF like its sibling; resolves
  the live job, calls the RPC, returns the same response model as
  `GET …/schedule-request` (refreshed). Errors via the existing
  HB403/404/409 mapping.
- `TriageSnapshot` gains `awaitingResident` (same row model as
  `openRequests`).
- Tests: revise the pinned raise-behavior tests (test_work_orders.py:192+)
  and the resident_scheduling fixture-based tests; new API tests for
  schedule-time (happy, approve-mode refusal HB409, foreign resident HB403,
  no live job HB404); new migration test file for 20260823180000 (presence,
  ordering after 170000, decisive body strings); G9 re-anchoring; new
  triage-snapshot bucket test. Follow the existing test-id numbering.
- Docs: API.md (both endpoints + §16 traceability), regenerated
  openapi.yaml via `backend/scripts/export_openapi.py` +
  `backend/scripts/api_annotations.py` entries, api_yaml_mapper.md
  (hand-fill `####`-level rows — the generator only auto-links `###`),
  MIGRATION_APPLY_RUNBOOK.md **§28** (paste + ledger insert + read-only
  post-checks, §27 pattern; note it must be applied after §27).

### Frontend (Agent B)
- `WorkOrderTriage.jsx` CreateForm: remove the start/end datetime fields and
  `halfASlot`; payload sends no slot. New explainer copy, subject-aware:
  resident → "The resident picks the visit time — this sends them the
  request. If they have not answered in 24 hours, the system books the
  first free hour a serviceman can take."; facility → "Nobody confirms a
  common-area job — the system books the first free hour a serviceman can
  take, once urgent home visits are covered."
- `ResidentDashboard/Complaints.jsx` `ProposedVisit`: branch on `mode`.
  `approve` unchanged. `pick`: heading "Pick a time for this visit", two
  datetime-local inputs (start/end, both required, end after start), submit
  via `residentApi.scheduleTime(complaintId, {startAt, endAt})`
  (`POST /complaints/{id}/schedule-time`), caption "If you have not picked
  a time within 24 hours, the association books the first available hour."
  Server HB409 sentences surface on the card.
- `residentApi.js`: add `scheduleTime`, and fix the stale `/** Accept a slot
  or propose a time */` comment (`:59`) to describe reality.
- `SupervisorDashboard.jsx`: new `<Section id="triage-awaiting-resident">`
  titled "Awaiting resident response" between taken-up and open-requests,
  fed by `snapshot.awaitingResident`, rendering with the existing
  `orderCard`; row popup offers the existing open-the-queue action only (no
  new writes).
- Query invalidations on schedule-time success: the schedule-request query
  and the complaint thread, mirroring the existing respond mutation.
- Tests: revise WorkOrders.test.jsx raise cases (fields gone, no-slot
  payload), ProposedVisit pick-mode cases (picker renders, submit payload,
  approve-mode untouched, HB409 surfacing), SupervisorDashboard.test.jsx
  (sixth section renders its array), vocabulary test only if labels change.
- Docs: FRONTEND_CHANGES.md entry.

### File-set boundary
Agent A: `backend/**`, `docs/API.md`, `docs/openapi.yaml`,
`docs/api_yaml_mapper.md`, `docs/plans/MIGRATION_APPLY_RUNBOOK.md`.
Agent B: `frontend/**`, `docs/FRONTEND_CHANGES.md`.
Nobody touches `docs/CHANGE_LOG.md`, `docs/COMPLAINT_ENGINE_HANDOFF.md`, or
this spec (orchestrator's).

## Out of scope (logged, not built)

- Resident DashboardHome nudge card (G11 follow-up).
- Any change to `respond_to_work_order_schedule`, `reschedule_work_order`,
  the supervisor offer/force-assign paths, or the board predicate.
- A per-department or configurable deadline/duration (G10).
- Stale-comment sweep beyond the files already being edited (recon logged
  the full list; the essay at 0036:73-80 is historical and stays).

## Adjudications on the build (orchestrator, post-build 2026-08-23)

Agent A (SQL + backend) deviations, each reviewed against source:

- **H1 — `mode` in the complaint-event payload: accepted.** Additive;
  `complaint_events.payload` is unconstrained and the timeline should record
  which question was asked.
- **H2 — `notify_community_staff` fallback when the raising supervisor's
  membership is gone: accepted.** It mirrors
  `respond_to_work_order_schedule`'s own posture (0036:874) — an answer is
  never delivered to nobody.
- **H3 — null/backwards resident times raise HB409, not 22004: accepted.**
  G3's letter; keeps the endpoint's declared code set at exactly
  HB403/404/409.
- **H4 — the CSRF test on schedule-time: accepted.** A new unsafe route
  without one would have been the gap.
- **H5 — `test_supervisor_actions_migration.py` re-anchored: accepted.** G7
  moves `supervisor_triage_snapshot`'s last word to the new file; the test's
  claim had to move with it. `post_dm_message` stays pinned to 20260822170000.
- **H6 — the runbook header's stale "Outstanding: nothing" corrected:
  accepted.**

Agent B (frontend) interpretations: the new supervisor section's row popup
uses a new `queueLink` (`?tab=queue&job=…`) because the "existing"
navigation action the spec pointed at did not exist — **accepted**,
navigation-only, built on the queue's own pre-existing deep-link parameter.
`ProposedVisit` gained its first test file (it had none) — accepted.

Orchestrator verification (own runs, not the agents'): backend **1375
passed / 5 skipped / 12 xfailed, 0 failed** (baseline 1342/5/12; +33 = 26
migration tests + 6 scheduling API tests + 1 triage test); frontend **47
files, 312 passed + 4 expected-fail** (baseline 46/298+4; +14 = the build's
own tests), oxlint exit 0. Migration reviewed line-by-line; the
"carried-forward verbatim" claims were spot-checked against sources and
hold: `sync_dispatch_tasks` is the live 20260823120000 body plus the draft
arm (the offered arm's `close resident_timeout` was already there);
`dispatch_candidates_at` is the live candidates body with the slot moved
onto parameters (the job CTE never filtered status, so the delegate is
behavior-identical); `create_work_order`'s guards match 0036 word for word;
the worker/resident notification shapes match `dispatch_auto_assign`
(0037:788-811) including the `/worker?job=` URL. The one genuinely novel
mechanic — completing the firing `facility_auto_assign` task row BEFORE the
handler runs — was verified against `enqueue_dispatch_task`'s
`on conflict … do update` (0037:187-216): without it the gate's hourly
retry would be folded into the firing row and closed with it.

Backlog from this build: `docs/API.md` §18's `GET /triage-snapshot` prose
still describes FOUR sections (two amendments behind; pre-existing, not
this build's); `workOrderVocabulary.js`'s `draft` label ("Draft — nothing
proposed") now reads oddly for a facility draft the system is about to
book — wants a small product ruling; runbook §23's stale "outstanding"
prose about 20260823120000 (ledger says applied 2026-08-23) remains from
the previous backlog. Correction to the previous entry's backlog: the
`test_api_369` duplication did NOT reproduce in the current tree — one
definition exists; that item is closed.
