# One live job per complaint — frozen spec (2026-08-27)

Owner ruling (Lee, complaint-engine owner, in-session 2026-08-27): a supervisor
must not be able to raise a new work order against a complaint while a job on
that complaint is still live. Observed live: complaint
`f40e11d4-e322-4847-be2f-8f2caf6df722` collected a second `awaiting_resident`
job fifteen seconds after the resident booked the first one's visit.

This spec freezes the interfaces the three implementation agents and the docs
agent share. Deviations require an orchestrator decision, logged here.

## 1. The live set (shared vocabulary)

`work_orders.status` is a closed list of eight
(`work_orders_status_check`, 0036): `draft`, `awaiting_resident`, `offered`,
`scheduled`, `in_progress`, `completed`, `failed`, `cancelled`.

**LIVE** = `('draft','awaiting_resident','offered','scheduled','in_progress')`
— exactly the set `work_orders_service._OPEN_STATES` and the
`get_schedule_request` resolver already call "live". Terminal =
`completed`, `failed`, `cancelled`.

- SQL: inline list in the new guard, with a comment naming `_OPEN_STATES`.
- Frontend: new export `LIVE_WORK_ORDER_STATUSES` from
  `frontend/src/features/workOrders/workOrderVocabulary.js`, frozen name.

## 2. Backend contract (Agent A)

New migration `backend/supabase/migrations/20260827210000_one_live_job_per_complaint.sql`:

- `create or replace function public.create_work_order(...)` — same signature
  as the `20260823180000` version (no signature change), with two additions:
  1. The initial complaint read becomes `select * ... for update` — serializes
     concurrent raises on one complaint, so the guard cannot race.
  2. After the department checks, before the insert:
     refuse when any live job exists on the complaint. Exact refusal, frozen:

     ```sql
     raise exception
       'A job is already live on this complaint. Finish, fail, or cancel it before raising another.'
       using errcode = 'HB409';
     ```

- `HB409` maps to HTTP 409, envelope `code: "conflict"`, message = the SQL
  sentence above (`app/core/pg_errors.py`). No new envelope code. The client
  never parses the message.
- The route docstring table for `POST /complaints/{complaint_id}/work-orders`
  (`backend/app/api/v1/routers/work_orders.py`) gains the 409 cause, and its
  prose paragraph "A complaint may carry several work orders" is corrected to
  say several **over its life, one live at a time**.
- Runbook: new §32 in `docs/plans/MIGRATION_APPLY_RUNBOOK.md` (hand-applied by
  the owner, like every migration). Post-check must note the leak complaint
  already holds two live jobs — the guard blocks *new* raises; existing rows
  are untouched history, and the extra `awaiting_resident` job
  `1f0bf129-d47d-4236-9082-ecf0a28b245c` is the owner's to cancel from the UI.

## 3. Frontend contract (Agent B)

`frontend/src/pages/AdminDashboard/WorkOrderTriage.jsx`, `ComplaintWorkOrders`:

- Compute `liveJob` from the already-fetched jobs list using
  `LIVE_WORK_ORDER_STATUSES`.
- While the list is pending or errored: render no `CreateForm` (a form drawn
  before the answer arrives is the duplicate-raise window again).
- When `liveJob` exists: render an explanatory panel instead of the form,
  frozen copy:
  > A job is already live on this complaint. Finish it, fail it, or cancel it
  > before raising another.
- When no live job: render `CreateForm` exactly as today. A raced 409 still
  surfaces through the existing `Failure` renderer; no special handling.

## 4. Stream reconnect contract (Agent C)

`frontend/src/lib/realtime/eventStream.js`:

- On `error` with `source.readyState === EventSource.CLOSED` (2): the browser
  will never retry (this is what an HTTP 403/5xx response does to
  `EventSource`). Schedule a reopen: backoff starts at 5 s, doubles to a 60 s
  cap, resets on a successful `open`.
- Reopen only while `subscribers.size > 0`; `close()` cancels any pending
  reopen timer.
- No behavior change for transient errors (readyState CONNECTING) — the
  browser already retries those itself.

## 5. Docs battery (Agent D, second wave — after A's docstring lands)

- Regenerate `docs/openapi.yaml` (`backend/scripts/export_openapi.py`) and the
  mapper (`backend/scripts/regen_mapper.py`).
- `docs/API.md`: the raise endpoint's 409 row + corrected multiplicity prose.
- `docs/COMPLAINT_ENGINE_HANDOFF.md`: record the ruling, its date, and that it
  guards `work_orders` liveness without touching `complaints.status`.
- `docs/plans/REALTIME_AND_CACHING_STANDARD.md`: the fatal-close reconnect
  doctrine (§4).
- `docs/FRONTEND_CHANGES.md` and `docs/CHANGE_LOG.md`: entries for all of the
  above, per the standing change-log rule.
