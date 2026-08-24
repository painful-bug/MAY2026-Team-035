# Assignment eligibility + work_order_assignments drift — frozen spec

Date: 2026-08-23 (evening, live-testing session). Branch `live-app-fixes`.
Orchestrator-owned. Deviations require an orchestrator decision, logged here.

## Context — three live defects reported by the product owner

While force-assigning a "tap leak" job from the supervisor's "Assign this job
outright" modal:

1. The candidate list showed the department **supervisor and manager**
   alongside the two technicians.
2. The assign itself failed — every `POST /work-orders/{id}/assign` returned
   422. Backend log (verbatim):
   `null value in column "assigned_by_membership_id" of relation
   "work_order_assignments" violates not-null constraint`.
3. The owner also reported the complaint was "not autoassigned or slow".

## Recon findings (read-only specialist, 2026-08-23; full citations in its
report, summarized here)

- **Drift, not a resolver bug.** Hosted `work_order_assignments` is a
  pre-baseline hand-built table. It carries `assigned_by_membership_id uuid
  NOT NULL` (no default) plus at least two other legacy columns that the
  repository has never declared and never writes: repo DDL is
  `0001_baseline.sql:74` (five columns) + `0036_work_orders.sql:264-272`
  (eight `add column if not exists`) + `20260813101000:4` (`is_forced`).
  ALL eleven insert sites in the repo omit the legacy column — force-assign
  (`20260822170000:934`), offer (`20260813101000:88`), board claim
  (`20260823170000:288`), ping (`20260812120000:122`), auto-assign
  (`20260812120000:231`), dispatch force (`20260823120000:421`), the 24h
  auto-book (`20260823180000:806`) and facility auto-assign
  (`20260823180000:992`). On hosted, **every write path into the table is
  broken**; the two 2026-08-23 auto-assign handlers would crash on first
  fire, retry 5 times, and retire the task dead. Exact precedent:
  `20260822090000_hosted_work_order_column_drift.sql` fixed the same drift
  on `work_orders`, with test precedent
  `backend/tests/test_hosted_work_order_drift_migration.py`.
- **No rank filter anywhere in the eligibility chain.** The single
  implementation is `dispatch_candidates_at`
  (`20260823180000_resident_sets_the_time.sql:110-267`); the roster join at
  lines 175-179 has no `sa.rank` clause. `staff_assignments.rank` is
  `manager | supervisor | member` (`0035:106-108`); marketplace hires get
  `member`; leadership gets `manager`/`supervisor` via invitation claim and
  has no `service_provider_id`, so the trade gate also short-circuits open
  for them. The one query feeds: the picker (`work_order_candidates` →
  `dispatch_candidates` → `_at`), `find_first_available_slot`
  (`20260823180000:366-377`), `dispatch_resident_timeout`,
  `dispatch_facility_auto_assign`, `dispatch_ping_candidates`,
  `dispatch_auto_assign`, `dispatch_force_assign`. Ordering is
  `load asc` — an idle supervisor sorts FIRST for the auto-book.
  Same hole on the board: `worker_open_jobs()`
  (`20260823170000:128-131`) and `claim_open_work_order`
  (`20260823170000:221-233`) check roster membership with no rank clause —
  a supervisor sees and can claim board jobs.
- **"Not auto-assigned" is to spec.** A resident pick routes the order to
  `offered` (the open board) and arms only `manual_window` at T+24h (T+2h
  when priority is high) — `20260823180000:624-644` + `:1097-1111`. No
  immediate auto-assign exists on this path by design (ruling F1). The
  dispatcher is running (log shows the poll loop alive; silent when idle by
  design; two transient WinError 10035 retries only).

## Rulings

- **R1 (PO, 2026-08-23, verbatim): "its only asigned to the workers who are
  hired from the service men pool"** — work orders may only be
  assigned/offered to rank-`member` staff hired from the marketplace pool;
  managers and supervisors must never appear as candidates, for humans or
  for the engine.
- **R2 (orchestrator, derived from R1):** the same rule closes the board
  door — `worker_open_jobs` stops listing jobs for leadership viewers and
  `claim_open_work_order` refuses leadership claims (supervisors keep their
  own triage dashboard; claiming off the board is assignment by another
  door). Flag to PO in the final report for confirmation.
- **R3 (orchestrator):** the clause is strict `sa.rank = 'member'` — NULL
  and future ranks are excluded by default, not admitted. The runbook gets
  a pre-check listing any hosted `staff_assignments` rows whose rank is
  NULL or outside the closed list, so a legacy technician row silently
  losing eligibility is caught by eyes, not by silence.
- **R4 (orchestrator):** the NOT NULL crash is fixed as a
  **widening drift sweep** mirroring `20260822090000` — prove, drop
  NOT NULL on every hosted `work_order_assignments` column the repository
  has never declared (dynamic over the catalog, protected list derived from
  the three repo DDL sites), verify. NOT by adding a resolver: the repo's
  actor model is `complaint_events.actor_membership_id` via
  `my_membership_in()`, and encoding a hosted-only legacy column into
  eleven call sites is drift in the other direction. Sweep is a no-op on
  baseline-built databases.
- **R5 (orchestrator):** ONE migration carries everything:
  `backend/supabase/migrations/20260823190000_assignment_write_repairs.sql`,
  sections ordered **drift sweep first**, then the rank clause replacements
  (`dispatch_candidates_at`, `worker_open_jobs`, `claim_open_work_order`).
  Single transaction; idempotent on re-apply. Hand-applied by the owner via
  the SQL editor ONLY — nobody runs DDL against hosted. Runbook gains §29.
  Post-checks must be **guard-free structural inspections** (no
  `auth.uid()`-dependent calls, no `kind = 'service'` helpers — both bit us
  in §28).
- **R6 (orchestrator):** defect 3 gets **no code change** — behavior matches
  ruling F1. The report to the PO explains the designed flow and asks
  whether the T+24h escalation window after a prompt resident pick is the
  product they want (a change there is a new ruling, not a fix).
- **R7 (orchestrator, backlog):** `force_assign_work_order` stamps timeline
  events with `v_order.supervisor_membership_id` instead of the acting
  caller (`20260822170000:951-959`) — attribution smell, not this
  migration. Backlogged.

## Frozen interface

- Migration file: `20260823190000_assignment_write_repairs.sql`. New
  functions: none. Replaced functions keep their exact signatures:
  `dispatch_candidates_at(uuid, timestamptz, timestamptz, int, boolean)`
  (copy the current 20260823180000 body verbatim, add ONLY the rank
  clause), `worker_open_jobs()`, `claim_open_work_order(...)` (same rule:
  verbatim body + rank clause / rank guard). Grants unchanged.
- No status-vocabulary changes, no new event types, no dispatch_tasks kind
  changes, no API shape changes, no frontend changes.
- `claim_open_work_order`'s leadership refusal reuses an existing HB
  error-code pattern (pick the closest existing HB code in the function's
  family; do NOT invent a new numbering scheme).
- Tests: mirror `test_hosted_work_order_drift_migration.py` (derive the
  protected column list from the repo DDL text) for the sweep; add
  migration-text assertions that the three replaced functions carry
  `rank = 'member'`; keep every existing test green.
- Docs: runbook §29 (pre-check for odd-rank rows, apply step, guard-free
  post-checks, plus a dispatch_tasks ground-truth query —
  `completed_at is not null` or `last_error is not null` — for confirming
  the dispatcher on hosted). CHANGE_LOG is written by the orchestrator
  after verification. PO ruling R1 recorded in COMPLAINT_ENGINE_HANDOFF.md
  by the orchestrator.

## Verification protocol

Specialist runs `uv run pytest -q` from `backend/` and reports numbers; the
orchestrator re-runs and trusts only its own run. Baseline this session:
1375 passed / 5 skipped / 12 xfailed. Frontend untouched → no frontend run
required unless files change.

---

# Addendum 2026-08-24 — supervisor take-up (leadership self-assignment)

`20260823190000` was applied to hosted on 2026-08-24 and verified: the
pre-check found only the three expected ranks, and the sole failing
`dispatch_tasks` row (manual_window, attempts 5, the NOT NULL error)
predates the apply — the recon-predicted casualty, retired dead. The work
order behind it carries no armed escalation; the PO handles it by hand.

## Rulings (continued)

- **R8 (PO, 2026-08-24, verbatim): "yes, include an option where a super
  can take up work … it sholdnt be something seen in normal routine
  workflow … it is available at any time though but as a seperate button
  orsomething like that."** — leadership self-assignment exists as an
  explicit, deliberate action, separate from every candidate flow.
  Candidate lists, auto-book, ping, and the open board stay member-only.
- **R9 (PO, 2026-08-24):** thin-department outcome accepted — no
  automation fallback; jobs wait for hires; take-up is the manual valve.
- **R10 (orchestrator, flagged to PO in plan, plan approved):** take-up is
  open to both `supervisor` and `manager` rank (active roster row in the
  job's department). `can_supervise_department` treats them identically
  and manager-cover (`restamp_department_supervision`) can leave a manager
  as the only leadership.
- **R11 (orchestrator):** mechanics — new RPC; actor = the caller resolved
  from `auth.uid()` (the `take_up_complaint` pattern incl. its null-actor
  assertion, `20260822120000:209-221`); new timeline word `job_taken_up`;
  assignment row `status 'accepted', is_forced false, is_auto_assigned
  false`; `supervision_inherited_at` is never touched (single-writer
  invariant, `test_supervisor_triage_migration.py:371-413`).
- **R12 (orchestrator):** backlogged R7 is closed in the same migration —
  `force_assign_work_order` redefined verbatim except its two
  `complaint_events` rows stamp the resolved caller, not
  `v_order.supervisor_membership_id`.
- **R13 (orchestrator):** the board stays closed (R2 stands);
  `claim_open_work_order` redefined verbatim except the leadership refusal
  message now points at the new verb. Same `HB403`; the whole migration
  raises only HB403/HB404/HB409, so `pg_errors.py` gains no entries.
- **R14 (orchestrator, post-implementation):** `job_taken_up` is hidden
  from the resident timeline by `_is_hidden_from_resident`
  (`resident_complaints_service.py`), for exactly
  `job_force_assigned`'s reason: the RPC writes `job_assigned` beside it,
  which already carries the resident's fact; which door the assignment
  came through is staffing, not service. Both specialists reached this
  conclusion independently (the backend one flagged the gap, the frontend
  one left the resident tracker untouched for the same reason). Label
  still registered belt-and-braces per house style; pinned by
  `test_api_374`.

## Implementation record (2026-08-24)

Built per this addendum by two parallel specialists; orchestrator-verified.
Approved deviations, all reported by the specialists and accepted:
- No `begin;`/`commit;` in the migration — house style (the SQL editor
  wraps the paste; no sibling migration carries them; R5's wording).
- No missing-slot HB409: `force_assign_work_order` has none (only
  end<=start when both non-null); "mirrors force-assign" wins over the
  brief's listing. The frontend gate covers the UX.
- Overlap refusal says "You are already booked during that time." —
  echoing the caller's own display name back at them would read as a bug.
- `test_assignment_write_repairs_migration.py`'s last-word test extended
  with the `LAST_WORD` dict pattern (precedent:
  `test_supervisor_actions_migration.py`) now that `20260824090000` owns
  `claim_open_work_order`'s body.
- `job_assigned` payload carries `'takenUp', true` (mirrors `'forced'`
  / `'claimed'`); no self-notification via `notify_complaint_staff`'s
  existing `p_exclude_membership` argument.

## Frozen interface (take-up)

- Migration: `backend/supabase/migrations/20260824090000_supervisor_take_up.sql`.
  Single transaction, idempotent, hand-applied by the PO only. Sections in
  order: (1) widen the `complaint_events` event CHECK
  (`20260822170000:1021-1025` list) with exactly one word `job_taken_up`;
  (2) new function; (3) `force_assign_work_order` verbatim + R12 diff;
  (4) `claim_open_work_order` verbatim + R13 diff; (5) in-transaction
  structural proof (style of `20260823190000:718-736`) + comment-only
  post-checks.
- New function, exact signature:
  `take_up_work_order(p_work_order_id uuid, p_scheduled_start_at
  timestamptz default null, p_scheduled_end_at timestamptz default null)
  returns uuid`, `security definer`, `set search_path = public`,
  `grant execute … to authenticated`. NO `p_staff_assignment_id` — the
  assignee is always the caller's own leadership roster row (HB403 when
  the caller holds none in the job's department). Status gate, slot rule,
  overlap check, withdraw-then-insert, `work_orders → scheduled` update
  all mirror `force_assign_work_order` (`20260822170000:863-992`).
  Timeline: `job_assigned` + `job_taken_up`, actor = caller. Notifications:
  resident `work_order.assigned` (url `/resident/complaints?complaint=`),
  `notify_complaint_staff` kind `job.taken_up`; no self-notification.
- Endpoint: `POST /api/v1/work-orders/{work_order_id}/take-up` on the
  existing work_orders router (router deps unchanged). Request
  `TakeUpWorkOrderRequest(_SlotFields)` — optional slot only. Response
  `WorkOrderDetail` via `_read_back_detail`. Repo method
  `take_up_work_order()` wrapped in
  `translate(exc, default_message="Could not take up that job.")`.
- Frontend: worker portal only. Button "Take this job myself" in
  `SupervisorDashboard.jsx` `openRequestActions` (and `popupActions`),
  same enable condition as the assign modal (order has a scheduled slot);
  `TakeUpModal.jsx` built on `ModalShell` (`triageParts.jsx`) with an
  amber exception-path banner; `workOrdersApi.takeUp(id)`; invalidate
  `['supervisor-triage']` and `['work-orders']`; a display label for
  `job_taken_up` where event words render. `WorkOrderTriage.jsx` (shared
  with admin) untouched in v1.
- Tests: `backend/tests/test_supervisor_take_up_migration.py` mirroring
  `test_assignment_write_repairs_migration.py` (incl. verbatim-body diffs
  for the two redefinitions and the every-SQLSTATE-mappable check); API
  tests in the `test_supervisor_actions.py` house style; frontend tests
  for button visibility + modal.
- Docs: API.md, regenerated openapi.yaml, api_yaml_mapper.md, runbook §30
  (§29 ends the file today). CHANGE_LOG + handoff entries by the
  orchestrator after verification. Baseline now 1443 passed / 5 skipped.
