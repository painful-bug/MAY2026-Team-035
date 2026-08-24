# The open-jobs board — frozen build spec (2026-08-23)

The product owner's rulings are recorded in `docs/COMPLAINT_ENGINE_HANDOFF.md`
§22: department roster technicians holding a job's trade see an open-jobs
board for their department (**C1**); taking a job from it is an instant claim
with accept-an-offer mechanics, supervisor notified, first come first served
(**C2**); unscheduled jobs appear with a "time to be set" marker and are
claimable, slot checks deferred (**C3**). This document freezes the interface
and logs the orchestrator's adjudications. Deviations require an orchestrator
decision before they land.

## Why the obvious reuse paths are closed (recon facts)

- `accept_work_order_offer` (20260812120000:385-527) requires an existing
  `offered` assignment for the caller, `work_orders.status = 'offered'`, and
  a non-null slot (HB409 "This job has no scheduled time yet"). All three
  fail for a board claim; C3 jobs are `draft`.
- RLS `work_orders_read` = `can_read_work_order` (0036:1356-1359, :491-515):
  a technician with no assignment on a job cannot select it at all. The board
  read must be a SECURITY DEFINER RPC.
- `dispatch_candidates` drops unscheduled jobs at the CTE (20260823120000:
  144-147) — not reusable as the board's eligibility source.
- `create_work_order` sets `status='offered'` on a *scheduled facility* job
  with **no assignment rows at all** (0036:720-727), so status alone cannot
  define "open".

## Adjudications (orchestrator, logged before build)

- **D1 — "open" means uncommitted and unpromised.** A job is on the board iff
  `work_orders.status in ('draft','offered')` AND it has **no live assignment**
  (no row in `work_order_assignments` with status `offered` or `accepted`).
  Consequences: a job with a live offer out to somebody else is OFF the board
  (the supervisor has an intention in flight; a decline returns it);
  `awaiting_resident` is off the board (a consent flow is in flight);
  `failed` is off the board in v1 (it has its own escalation task).
- **D2 — the claim mirrors accept, minus the slot demands.** New RPC (see
  Interface). Guards in order: job exists + row lock; job open per D1 else
  HB409 "Somebody has already taken this job."; caller holds an
  active roster row (`status='active' and is_active`) in the job's department
  else HB403; trade rule exactly as `dispatch_candidates` writes it
  (`job.skill_id is null or sa.service_provider_id is null or
  service_provider_skills match`) else HB403; caller not in
  `complaint_excluded_staff(complaint_id)` else HB409; if the job HAS a slot,
  refuse an overlap with the caller's other accepted assignments (mirror
  accept 20260812120000:440-452); if it has NO slot, skip slot-dependent
  checks entirely (ruling C3). The trade short-circuit for provider-less
  roster rows is deliberate: it is the engine's own rule (20260823120000:
  246-255), and inventing a different one here would fork eligibility.
- **D3 — the claimed row takes the accept path's exact shape.** Insert
  assignment `status='accepted'`, `offered_at=now()`, `responded_at=now()`,
  `is_forced=false`, `is_auto_assigned=false`, slot copied from the job (may
  be null); defensively withdraw any `offered` rows (D1 means there are none,
  but the lock window is real); set `work_orders.status='scheduled'` — yes,
  even with a null slot: `force_assign_work_order` already writes that shape
  (20260822170000:942-948), so `scheduled`+null-slot is established
  semantics, and the queue's set-a-time control is the way out of it.
- **D4 — no new event word.** The claim writes `complaint_events` with
  `event_type='job_assigned'` (the accept path's own word, 20260812120000:
  479-481) and payload `{..., accepted: true, claimed: true}`. A new word
  costs a constraint drop-and-recreate (runbook §19 rule); `claimed: true`
  in the payload carries the distinction without it.
- **D5 — the complaint advances on claim, and the force-assign hole closes
  with it.** Ruling C2 says "the same status movements" as accepting an
  offer; on the offer path the complaint moved `open → acknowledged` when the
  *offer* was inserted (projection trigger fires on INSERT only `when
  (new.status = 'offered')`, 20260813102000:26-27). A claim inserts
  `accepted` directly, so without a change the complaint would sit at `open`
  with a committed job — violating C2. Adjudication: extend the projection
  trigger to fire on INSERT `when (new.status in ('offered','accepted'))`
  and teach the function body to treat an accepted insert as at-least-
  `acknowledged`. This knowingly also closes the identical pre-existing hole
  in `force_assign_work_order` and `dispatch_force_assign`. **Flagged to the
  product owner as an engine lifecycle change made under C2's authority.**
- **D6 — notifications.** Mirror the accept path's audience and add the
  supervisor: raising resident gets `work_order.assigned` (same payload shape
  as accept, 20260812120000:495-505); the supervisor audience accept resolves
  (20260812120000:510-523) gets a new kind **`work_order.claimed`** with a
  supplied title ("<worker> took up <job>") — `notifications.kind` is
  unconstrained by design (0030:200-203) so no schema or renderer change is
  needed; skip the notification when the claimer IS that supervisor.
- **D7 — board visibility is also exclusion-aware.** A worker in
  `complaint_excluded_staff` for a job's complaint does not see that job on
  their board (it is not actionable for them); the claim RPC still guards it
  independently (D2) because the list and the click are seconds apart.

## Frozen interface

### Migration — `backend/supabase/migrations/20260823170000_open_jobs_board.sql`
Sorts after `20260823160000_visitor_requests_sse.sql` (hosted high-water
mark). Hand-applied by the owner via the Supabase SQL editor — the build MUST
NOT attempt to apply it. Contents:

1. `public.worker_open_jobs()` — SECURITY DEFINER, `set search_path = public`,
   no args (identity from `auth.uid()`), returns table:
   `work_order_id uuid, complaint_id uuid, complaint_title text,
   department_id uuid, department_name text, community_id uuid,
   community_name text, skill_id uuid, skill_name text, priority text,
   subject_kind text, scheduled_start_at timestamptz,
   scheduled_end_at timestamptz, created_at timestamptz,
   staff_assignment_id uuid` — the caller's own roster row for that
   department, so the frontend never guesses it. Rows: every D1-open job in
   every department where the caller holds an active roster row, filtered by
   the D2 trade rule and D7 exclusion, ordered
   `scheduled_start_at asc nulls last, created_at desc`.
2. `public.claim_open_work_order(p_work_order_id uuid)` — SECURITY DEFINER,
   `set search_path = public`, returns the new assignment id; guards and
   writes per D2/D3/D4/D5/D6.
3. The projection-trigger extension per D5 (drop/recreate trigger with the
   widened WHEN; `create or replace` the function).
4. Grants: `revoke all ... from public, anon, authenticated;` then
   `grant execute ... to authenticated` for both new functions;
   `notify pgrst, 'reload schema';` at the end.

### Backend
- `GET /api/v1/worker/open-jobs` → `list[OpenJob]` (worker_jobs router; same
  no-membership-guard stance as its siblings, CSRF not needed on GET).
- `POST /api/v1/worker/jobs/{work_order_id}/claim` → `WorkerJob` (read back
  through the existing `_read_back`/`my_worker_job` path, exactly like
  accept). CSRF via the router's existing `require_csrf_unsafe`.
- `OpenJob` schema in `backend/app/domain/worker_schemas.py` (CamelModel):
  camelCase of the RPC columns above. Error mapping via the existing
  HB403/HB404/HB409 translation.

### Frontend
- New page `frontend/src/pages/WorkerDashboard/OpenJobs.jsx`, route
  `open-jobs` in `frontend/src/App.jsx`, query key `['worker-open-jobs']`,
  api methods `workerApi.openJobs()` and `workerApi.claimJob(id)`.
- Nav item "Open jobs" in `WorkerLayout.jsx` with `marketplaceOnly: true`
  (visible to technicians and marketplace pros, hidden from leadership —
  leadership has the queue). Placed directly after Dashboard.
- Cards show complaint title, department + community, trade, priority, and
  either the slot or a "Time to be set" marker (C3). Claim is a two-step
  press (press → confirm wording that says the job is theirs immediately and
  the supervisor is told). On success invalidate `['worker-open-jobs']` and
  `['worker-snapshot']`. A claim that loses the race surfaces the server's
  HB409 sentence on the card and refreshes the list.
- Empty states: no roster rows → "Jobs appear here once a community hires
  you."; roster but no open jobs → plain "Nothing is waiting right now."

### Docs (per the API docs standard)
`docs/API.md` (both endpoints, status codes, §16 user-story traceability),
regenerated `docs/openapi.yaml` via the export script,
`docs/api_yaml_mapper.md`, `docs/FRONTEND_CHANGES.md`,
`docs/plans/MIGRATION_APPLY_RUNBOOK.md` new section (§27) with read-only
post-checks, and a `docs/CHANGE_LOG.md` build entry. Correct the
`backend/supabase/migrations/README.md` row that still says `20260823120000`
is "Not yet applied to hosted" (the ledger says it was applied 2026-08-23).

## Out of scope (logged, not built)

- Any change to the supervisor's offer/force-assign paths (§22's own
  boundary).
- A trade notion for provider-less roster rows (the engine has none; the
  board inherits its short-circuit).
- `failed`-job re-pooling onto the board; pagination of the board.
- The dead `GET /worker/jobs` frontend wiring (`workerApi.jobs` has zero call
  sites; the `worker-jobs` query key is invalidated but never produced) —
  noted as pre-existing, not this build's problem.

## Adjudications on the build (orchestrator, post-build 2026-08-23)

- **E1 — the three migration-ordering tests.** `test_hosted_invite_claim_names_migration.py`,
  `test_hosted_request_status_withdrawn_migration.py` and
  `test_visitor_requests_sse_migration.py` each assert "my migration sorts
  after every file that already existed", implemented as *after everything
  except a hardcoded `NEW_FILES` set* — so any later migration falsifies them.
  The frozen filename `20260823170000_open_jobs_board.sql` did exactly that.
  The specialist added the new filename to each set with a dated comment; the
  brief said report-don't-edit tests, and this deviation is **accepted** — the
  filename was frozen, so the tests were the only movable part, and their own
  comments anchor the claim to the authoring moment. Backlog: re-anchor the
  class to a named predecessor (the idiom `test_complaint_engine_v2_repair_migration.py`
  already uses) so the next migration does not break them a third time.
- **E2 — accepted as specced**, verified by the orchestrator's own reads: the
  claim RPC's schema dependencies are real (`work_orders.supervisor_membership_id`
  — 0037 usage throughout; `my_membership_in` — 0039:249, granted :895), the
  recreated trigger name matches 20260813102000:26 exactly (no duplicate
  trigger risk), and the supervisor notification URL uses the accept path's
  own admin-shaped convention (20260812120000:519) which the portal rewrite
  layer handles.
- **E3 — mapper cells hand-filled.** `regen_mapper.py` only auto-links `###`
  headings and the worker-portal endpoints sit under `####`; the two new rows
  were filled by hand in the siblings' style and survive a regen. Generator
  limitation noted, not fixed.

Verification (orchestrator's own runs, not the agent's): frontend 298 passed /
0 failed (+4 expected-fail rows from a concurrent workstream's repro files),
oxlint exit 0; backend re-run recorded in `docs/CHANGE_LOG.md` alongside this
entry. OpenAPI regenerated: 226 added lines, 0 removed — only the two new
endpoints and the `OpenJob` schema.

Backlog from the build report: the ordering-test re-anchor (above); duplicate
test id `test_api_369` (pre-existing); stale "not yet applied" prose about
`20260823120000` in runbook §23 and handoff §21 (the ledger says applied
2026-08-23; only the migrations README row was corrected); untracked
`backend/tests/test_issue48_amenity_repro.py` from a concurrent workstream
needs an owner to commit or remove it.
