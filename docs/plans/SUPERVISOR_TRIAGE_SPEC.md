# Supervisor triage dashboard — frozen interface spec

Written 2026-08-22 by the orchestrator; approved by the product owner the same
day. Two specialists build against this document in parallel — one on the
backend (migration + endpoints), one on the frontend (the dashboard page).
**Neither side may change anything in the "Frozen" sections without an
orchestrator decision, logged here.** Everything else (internal RPC design,
component structure, styling) is the implementing agent's call.

Product rulings behind this spec: `docs/COMPLAINT_ENGINE_HANDOFF.md` §18.

## The surface

A new supervisor landing page in the worker portal. Leadership rank
(`supervisedEngagement` from `staffVocabulary.js`) lands here instead of the
technician's `WorkerHome`; technicians see no change. Four stacked sections:

1. **New complaints** — untouched work, with a pinned urgent stack (priority
   High) on top, and "reassigned" badges (bounced back / rerouted in /
   inherited by removal).
2. **Taken up by you** — the supervisor pressed *Take up*; no worker engaged
   yet.
3. **Assigned, work pending** — a worker is engaged (offered/accepted/booked)
   but has not started.
4. **Being worked right now** — the worker pressed Start; shows elapsed time.

## Frozen: wire contract

### `GET /api/v1/departments/{departmentId}/triage-snapshot`

Guard: department supervision (`can_supervise_department` at the DB boundary,
same posture as `GET /departments/{id}/complaints`). 200 body (CamelModel):

```jsonc
{
  "departmentId": "uuid",
  "newComplaints":   [TriageComplaint],  // status open, no take-up
  "takenUp":         [TriageComplaint],  // take-up stamped, no engaged worker
  "assignedPending": [TriageWorkOrder],  // worker engaged, not started
  "inProgress":      [TriageWorkOrder]   // status in_progress
}
```

**Bucketing is decided server-side.** The frontend renders the four arrays
as-is and never re-buckets. Definitions:

- *live* work order: status not in `completed | failed | cancelled`.
- *engaged*: a live work order with an assignment row in `offered | accepted`,
  or work-order status `scheduled`.
- `newComplaints`: department's complaints, storage status `open`,
  `taken_up_at is null`.
- `takenUp`: `taken_up_at is not null`, storage status `open|acknowledged`,
  and no engaged and no `in_progress` live work order.
- `assignedPending`: live, engaged, status ≠ `in_progress`.
- `inProgress`: status `in_progress`.
- A taken-up complaint whose job became engaged appears in `assignedPending`
  (as its work order), not in `takenUp`. Sort every array newest-first by
  `createdAt`; the frontend pins the urgent stack itself.

### `TriageComplaint`

```jsonc
{
  "id": "uuid", "title": "", "category": "",        // category as stored (trade name)
  "priority": "High|Medium|Low",                     // wire vocabulary
  "status": "Pending|In Progress|...",               // wire vocabulary
  "location": "", "raisedBy": "", "unitCode": null,
  "createdAt": "iso", "dueAt": "iso|null",
  "returnedToPoolAt": "iso|null",                    // bounced back
  "reopenedCount": 0,
  "reroutedAt": "iso|null",   // latest department-change event that moved it INTO this department, else null
  "takenUpAt": "iso|null", "takenUpByName": "string|null",
  "liveWorkOrderCount": 0,
  "openRequestId": "uuid|null"
}
```

### `TriageWorkOrder`

```jsonc
{
  "id": "uuid", "complaintId": "uuid|null",
  "complaintTitle": "", "complaintCategory": "",
  "priority": "High|Medium|Low",                     // wire vocabulary
  "status": "draft|awaiting_resident|offered|scheduled|in_progress",
  "assigneeName": "string|null",
  "scheduledStartAt": "iso|null", "scheduledEndAt": "iso|null",
  "startedAt": "iso|null",
  "inheritedAt": "iso|null",                         // supervision_inherited_at
  "locationText": "string|null", "skillName": "string|null"
}
```

### `POST /api/v1/complaints/{complaintId}/take-up`

No body. Guard: `can_supervise_department` on the complaint's department.
Effects (one transaction, RPC `take_up_complaint`): stamps
`taken_up_by_membership_id` + `taken_up_at`; moves storage status
`open → acknowledged` (only from `open`); writes a `complaint_events` row
(`event_type = 'taken_up'`). No notification — a passive field change under
ARCHITECTURE.md's rule; the resident sees "In Progress" via the ordinary SSE
re-snapshot. Responses: 200 `{ "message": ... }`; 404 unknown complaint; 403
not this department's supervisor; 409 already taken up by someone else
(message names them). Taking up your own again is a no-op 200.

## Frozen: schema additions (migration `20260822120000_supervisor_triage.sql`)

- `complaints.taken_up_by_membership_id uuid references community_memberships(id) on delete set null`
- `complaints.taken_up_at timestamptz`
- `work_orders.started_at timestamptz` — stamped by `start_work_order`
  (`coalesce(started_at, now())`; body copied forward per house convention
  from `0039_worker_actions.sql`).
- `work_orders.supervision_inherited_at timestamptz` — stamped by
  `restamp_department_supervision` (body copied forward from
  `20260821200000_departure_continuity.sql`) on every row it re-stamps.
- New RPCs: `take_up_complaint(uuid)`, `supervisor_triage_snapshot(uuid)`
  (internal shape is the backend agent's; the wire contract above is not).
- Hand-applied by the owner; ships with a runbook section (§18) and a static
  test file in the house idiom.

Explicitly out of scope: any write to `assigned_to_membership_id` or
`assignee_label` (handoff §15 ruling 1); a `paused` status; notifications.

## Frozen: refresh behaviour

The page loads via react-query and refetches when the
`homebandhu:dashboard-refresh` window event fires (dispatched by
`DashboardDataBootstrap` on every SSE beat), plus a 60s `staleTime` fallback.
No new SSE channel.

## Frozen: chips

- **Category chip**: deterministic color from the category name — hash the
  lowercased trimmed name over a fixed 8-color accessible palette so
  "Plumbing" is the same color on every screen, with the name as the label.
- **Priority chip**: High = rose, Medium = amber, Low = slate. Text label
  always present (never color alone).
- Badges in section 1: `returnedToPoolAt` → "Returned to pool",
  `reopenedCount > 0` → "Reopened ×N", `reroutedAt` → "Moved to this
  department", `inheritedAt` (on work orders in §3/§4) → "Inherited".

## Ownership and docs

- **Backend agent** owns `backend/**`, the migration + its static tests +
  runbook §18, `docs/API.md`, regenerated `docs/openapi.yaml`,
  `docs/api_yaml_mapper.md`. Runs `uv run pytest -q` (baseline 1157 passed /
  4 skipped + its new tests; `python -m pytest` does not work on this
  machine).
- **Frontend agent** owns `frontend/**` and `docs/FRONTEND_CHANGES.md`. Runs
  `npx vitest run` (baseline 34 files / 182 tests + its new ones) and
  `npx oxlint src --quiet` (exit 0), both from `frontend/`.
- **Neither agent** touches `docs/CHANGE_LOG.md`,
  `docs/COMPLAINT_ENGINE_HANDOFF.md`, this spec, or the other's files — the
  orchestrator integrates those.
- Phasing: the frontend ships the page shell + Section 1 first and stops for
  product review; sections 2–4 follow on the orchestrator's go.

## Logged decisions (orchestrator, 2026-08-22)

1. **Take-up accepts `{}`.** The house `post()` helper always sends `{}` as
   the JSON body, so the endpoint declares no required body model. Relayed to
   the backend agent mid-build.
2. **The category palette is named now**: sky, emerald, violet, teal, indigo,
   orange, cyan, fuchsia — chosen by the frontend agent specifically to
   exclude the priority tones (rose/amber/slate), so a category chip can
   never be misread as a priority. Pinned by `triageDisplay.test.js`.
3. **The "Inherited" badge ships with phase two**, when §3/§4 get their full
   card treatment — a phasing choice, not a contract change; `inheritedAt`
   stays in the frozen DTO.
4. **Known limitation, deliberately not half-fixed**: a person who supervises
   one community and works as a technician in another lands on the supervisor
   surface, and `WorkerHome`'s `?job=` deep-link handling is unreachable for
   them. Same single-engagement limitation `supervisedEngagement` already
   documents; the honest fix is a portal-wide engagement switcher (backlog).
5. **Take-up on a department-less complaint refuses `HB409`, not `HB403`** —
   what is missing is the routing, not a permission. (Backend agent's call,
   ratified; the spec had not covered the case.)
6. **`supervisor_triage_snapshot` returns `jsonb` with storage vocabulary**;
   `vocabularies.py` translates at the boundary, pinned by a test that no
   wire word appears in the RPC. Internal shape, agent's call per the spec.
7. **The `taken_up` timeline event carries resident-facing copy** ("Taken up
   by the department" / "The department has taken this up." — no supervisor
   identity). Approved verbatim by the product owner 2026-08-22 and frozen in
   `COMPLAINT_ENGINE_HANDOFF.md` §18 ruling 5.

---

# Amendment 2 — the supervisor action surface (2026-08-22, phase 2)

Product rulings taken 2026-08-22 (four AskUserQuestion answers, logged as
decisions A1–A4 below). This amendment supersedes the v1 section list and the
snapshot bucketing; every v1 rule not restated here stays frozen as written.

## The surface, v2

Five stacked sections, and three **universal card actions** that appear on
every card in every section:

- **Eye** — opens a detail popup: full complaint info, category/priority
  chips, stage, complete timeline, and the stage's primary actions repeated
  inside.
- **Chat** — opens a live chat thread with the complaint owner (see the
  chat contract below).
- **Note** — composer for a permanent, internal note appended to the
  complaint's timeline (visible to staff and workers, hidden from the
  resident).

1. **New complaints** — as v1, plus the universal actions. *Take up* stays
   on the card and also appears inside the eye popup.
2. **Taken up by you** — full cards now: **Raise job request** (deep-links
   to the work-order queue's raise form, `?tab=raise&complaint={id}` — the
   established mechanism) and **Resolved**.
3. **Open job requests** *(new section)* — raised jobs no worker has
   accepted yet. Actions: **Mark as resolved**, **Raise priority**,
   **Assign** (true force-assign), plus the universals.
4. **Assigned, work pending** — monitor-only full cards (universals only);
   the "Inherited" badge from v1 decision 3 ships here.
5. **Being worked right now** — monitor-only full cards with elapsed time
   since `startedAt`.

## Frozen: snapshot v2 re-bucketing

`GET /departments/{id}/triage-snapshot` returns five arrays; `openRequests`
sits between `takenUp` and `assignedPending`.

- *committed* (replaces v1's *engaged*): a live work order with an
  assignment row in `accepted`, **or** work-order status `scheduled`. An
  unaccepted offer no longer counts (ruling A3).
- `newComplaints` [TriageComplaint]: status `open`, no take-up, **and no
  live work order**.
- `takenUp` [TriageComplaint]: take-up stamped, status `open|acknowledged`,
  no live work order.
- `openRequests` [TriageWorkOrder]: live, not committed — status
  `draft|awaiting_resident|offered`.
- `assignedPending` [TriageWorkOrder]: live, committed, status
  ≠ `in_progress`.
- `inProgress` [TriageWorkOrder]: status `in_progress`.

Furthest stage wins: a complaint with any live work order appears only as
that work order in sections 3–5, never in 1–2. Exactly one card per
complaint chain. Sort stays newest-first.

`TriageWorkOrder` gains `offeredToName: string|null` — the pending offeree
shown on §3 cards ("Offered to …, awaiting acceptance"). Additive only.

## Frozen: new wire endpoints

### `POST /api/v1/complaints/{complaintId}/resolve`

Supervisor resolve (rulings A2). Guard `can_supervise_department`. One
transaction, RPC `supervisor_resolve_complaint`:

- Refuses `HB409` if any of the complaint's work orders is `in_progress`
  ("finish or cancel the running job first").
- Cancels every other live work order (draft/awaiting_resident/offered/
  scheduled), withdrawing `offered|accepted` assignment rows and notifying
  affected staff `job.cancelled` with reason "Complaint resolved by the
  department".
- Sets storage status `resolved` (+`resolved_at`), writes `status_changed`,
  notifies the raiser `complaint.resolved`.
- Resident aftermath is unchanged v0 machinery: confirm-with-rating
  (`resolution_confirmed`), reopen, 48h warning / 72h auto-close.
- 200 / 403 / 404 / 409 (running job, or already resolved/closed/cancelled).

### `POST /api/v1/complaints/{complaintId}/priority-raise`

One-way raise `Low → Medium → High`, no body. Guard
`can_supervise_department`. RPC `raise_complaint_priority`: refuses `HB409`
at High. Writes a **new event word `priority_changed`** (payload
`{from, to}`) — resident-visible timeline line "The department raised the
priority to {High}." Priority is load-bearing: High arms the dispatch
engine's automatic force-assign on all-declined, deliberately. No
notification (passive field change). 200 / 403 / 404 / 409.

### `POST /api/v1/complaints/{complaintId}/notes`

Body `{ note }` (1–2000 chars). Guard `can_supervise_department`. RPC
`add_complaint_note_internal`: appends a `note_added` event with payload
`{note, internal: true}`. `resident_complaints_service` hides
`note_added` events whose payload carries `internal: true` (the admin
PATCH's resident-visible "Update from management" notes are untouched).
Staff detail shows them with author name. Append-only, no edit/delete. 201.

### `POST /api/v1/complaints/{complaintId}/chat`

Open-or-get the complaint's chat thread (ruling A1). Guard
`can_supervise_department`. Returns `{ threadId }`.

- Migration: `dm_threads.kind` CHECK gains `'complaint'`; new
  `dm_threads.complaint_id uuid` FK; unique index on `complaint_id` where
  kind = 'complaint' (one thread per complaint).
- Participants: the complaint's raiser (profile) + the calling supervisor.
  A later supervisor of the same department joins the existing thread
  rather than forking a second one.
- Seeded system message: "The department opened this chat about
  '{complaint title}'."
- Write-locking mirrors the job-thread idiom: a `closed|cancelled`
  complaint locks its thread (409 on send).
- Frontend: the card's chat button calls this endpoint then dispatches the
  existing `hb:chat-open` window event with `{threadId}`; `ChatDock` learns
  to open a specific thread from that detail. The resident reaches the same
  thread through their ordinary dock thread list.

### `POST /api/v1/work-orders/{workOrderId}/assign` — `force` flag

`AssignWorkOrderRequest` gains optional `force: boolean` (default false =
the existing offer flow, byte-for-byte unchanged). `force: true` (ruling
A4) calls new RPC `force_assign_work_order(work_order_id,
staff_assignment_id)`, modeled on the engine's `dispatch_force_assign`:
inserts the assignment with `is_forced = true` (non-declinable — the worker
UI already hides Decline for forced rows), writes the existing
`job_force_assigned` event (resident-hidden, as today), notifies the worker
`job.force_assigned`. Schedule fields remain optional exactly as in the
offer flow. Same guard surface as the existing assign endpoint.

### `GET /api/v1/complaints/staff/complaints/{complaintId}` — guard widened

Router guard drops from `require_admin` to active-membership; the RPC
(`staff_complaint_detail`) already decides `is_community_admin OR
can_supervise_department` at the DB boundary and keeps doing so. New
frontend wrapper in `triageApi` feeds the eye popup.

## Frozen: event vocabulary

One new `complaint_events` word this amendment: `priority_changed`. Per the
2026-08-22 lesson (runbook §19), it ships inside this amendment's single
migration as a constraint drop-and-recreate — creator list + `taken_up` +
`priority_changed`. Every other event this amendment writes
(`status_changed`, `note_added`, `job_force_assigned`) is already allowed.

## Migration

One hand-applied file (next timestamp in sequence): chat kind + column +
index, the four new/changed RPCs, the snapshot v2 RPC (drop-and-recreate),
and the constraint widening. Ships with a static test battery in the house
idiom and a runbook section.

## Logged decisions (amendment 2, product owner, 2026-08-22)

- **A1 — chat is a real thread**, not a comments panel: new `complaint`
  thread kind in the existing chat dock, resident + supervisor.
- **A2 — Resolved cancels unstarted jobs and blocks on started ones**:
  auto-cancel draft/offered/scheduled with worker notification; refuse
  while any job is `in_progress`.
- **A3 — open until accepted**: an offered-but-unaccepted job stays in
  "Open job requests"; "Assigned, work pending" means a worker committed.
- **A4 — manual assign is a true force-assign**: no decline, supervisor's
  explicit override of the consent model, via the engine's existing forced
  mechanics.
- **A5 (orchestrator)** — notes are internal-only: the product owner's
  phrasing enumerated staff and workers, not the resident; hidden via
  payload flag, admin resident-visible notes unchanged.
- **A6 (orchestrator)** — "Raise job request" deep-links to the existing
  work-order raise form rather than duplicating it inline; an inline form
  is a possible later refinement.
- **Proposed resident-facing copy, pending explicit approval**: priority
  line "The department raised the priority to {level}."; chat seed "The
  department opened this chat about '{title}'."; job-cancel reason
  "Complaint resolved by the department."
  *(Approved by the product owner with the plan, 2026-08-22.)*

## Adjudications (orchestrator, post-build 2026-08-22)

Deviations the backend specialist flagged, ruled after both builds landed:

- **A7 — resolve delegates the timeline line and the notification.** The
  contract's "writes `status_changed`, notifies the raiser" describes the
  *outcome*; the `complaints_on_resolved` trigger (`20260813104000`) already
  produces both plus the auto-close timers when status moves. Writing them
  in the RPC too would double the timeline line and the notification.
  Accepted; the migration hard-fails its apply if that trigger is missing.
- **A8 — a priority raise propagates onto the complaint's live work
  orders.** The codebase's own rule ("a job's urgency *is* the complaint's
  urgency" — `work_orders.py` create path) demands it; a dispatcher acting
  on the pre-escalation value would be the alternative. SLA
  `expected_resolution_at` deliberately not recomputed.
- **A9 — `assigneeName` narrowed to the accepted holder only**; the pending
  offeree travels in `offeredToName`. Forced by ruling A3: the old
  accepted-else-newest-offer fallback would print a worker's name on an
  *Open job requests* card.
- **A10 — `force_assign_work_order` gains two optional schedule arguments**
  (frozen 2-arg call unchanged), and force-assign notifications mirror the
  engine's existing set (`work_order.assigned` to the worker,
  `job.force_assigned` to staff, arrival notice to the resident) rather
  than inventing a new topic.
- **A11 — reopening a complaint unlocks its chat thread** (the terminal
  lock is not permanent; a resident with a live reopened complaint must be
  able to talk). The lock's system line mirrors the job-thread copy and is
  orchestrator-approved, not PO-reviewed.
- **A12 (wart, backlog)** — the resolve cascade notifies `job.cancelled`
  per this amendment while the older `cancel_work_order` sends
  `work_order.cancelled` for the same event; two topics, one meaning. No
  functional effect (no topic CHECK; clients render title/body). Also
  backlog: the mailbox overview cannot label a complaint thread by its
  complaint (`dm_thread_overview` lacks `complaint_id`), and a
  third-supervisor participant may see the other supervisor's name as
  `counterpartName`.

---

## Amendment 3 — the supervisor's chrome, and the archive (2026-08-23, phase 3)

Live testing moved past the dashboard to the portal around it. Two product
observations from the owner: the chrome a supervisor sees is a marketplace
serviceman's chrome ("Where I work", Find work, a provider Profile, a hiring
inbox, "Service Partner" in two places), and there is nowhere to look back at
work that ended. Three rulings were taken with the product owner
(AskUserQuestion, 2026-08-23), and this amendment freezes them plus the
orchestrator's riders. **Everything in this amendment is frontend-only** — the
data layer it reads exists already and nothing here writes.

### Ruling B1 — leadership loses the marketplace chrome, and the model is simplified

The owner's words: hide all five marketplace nav items, "but also let's assume
we are not implementing the worker promotion model right now. Let's assume that
we directly hire supervisors and managers from outside the marketplace."

Consequences, frozen:

- **The discriminator is the leadership rank alone**: `holdsLeadershipEngagement`
  of the worker snapshot's `communities[]`. No provider-profile test, because by
  assumption leadership never has one. (This retires, for now, the hybrid
  "registered provider promoted to supervisor" population; if the promotion
  model ever ships, this amendment is the place that recorded the assumption.)
- Five nav items are hidden from leadership via a new `marketplaceOnly: true`
  flag on the NAV entries in `WorkerLayout.jsx`, filtered symmetrically to the
  existing `supervisorOnly` flag: **Calendar, Availability, Communities,
  Messages, Profile**. The leadership rail becomes: Dashboard, Complaints,
  Work orders, Completed work (new, below), Settings.
- Hiding the nav item is never the guard (portal convention). Each of the five
  pages answers a leadership deep-link with a short plain-English refusal in
  the page's own voice, the way `Complaints.jsx` refuses technicians.
  `Availability`, `Profile` and `Settings` already discriminate; **`Calendar`
  is the gap** — it fires `GET /worker/communities` unconditionally and 404s on
  every leadership mount (the exact defect handoff §18 ruled against on the
  landing page, never propagated). Its queries gain `enabled:` gating and the
  page gains the refusal.
- The sidebar `AvailabilityToggle` already returns null without a provider row;
  untouched.

### Ruling B3 — the branding names the rank

The two hard-coded "Service Partner" strings (`WorkerLayout.jsx` sidebar
eyebrow and header title) render the caller's actual roster rank for
leadership — "Supervisor" or "Manager", read from the first active leadership
engagement on the snapshot the layout already fetches. Non-leadership keeps
"Service Partner".

### Ruling B2 — Completed work, the read-only archive

A new nav item **Completed work** (`supervisorOnly`), route
`/worker/completed`. The owner's definition: **all ended complaints** —
resolved, closed, and cancelled — "but keep a filtering mechanism on the front
end so that it can be sorted across each kind of end condition."

Frozen shape:

- **Data**: `GET /api/v1/departments/{id}/complaints` (existing; RPC
  `department_complaints`, supervisors pass `can_supervise_department`). Called
  with no `?status=`; the page keeps rows with status ∈
  `{resolved, closed, cancelled}` client-side. The endpoint is unpaginated —
  accepted for now and recorded as backlog (W1 below), not worked around.
- **Filter chips**: Everything · Resolved · Closed · Cancelled. In this one
  screen the three end conditions are **labelled distinctly** — "Resolved —
  awaiting the resident", "Closed — confirmed", "Cancelled" — a deliberate,
  display-only departure from the wire's closed→Resolved asymmetry, confined to
  the archive because distinguishing end conditions is this screen's entire
  point. Nothing else adopts these labels.
- **Order**: `resolvedAt` descending, `createdAt` as the fallback key.
- **Interaction**: a card opens the existing `ComplaintDetailModal` fed by the
  staff detail endpoint (which already fetches ended complaints — no status
  predicate). **Read-only**: no `actions` node is passed, and the modal gains a
  `readOnly` prop that unmounts the `NoteComposer` (today mounted
  unconditionally). The full timeline, internal notes included, renders as the
  look-back the owner asked for; nothing on the screen writes.
- The read-only boundary is **UI-level**. `add_complaint_note_internal` has no
  status guard in the database; a note on an ended complaint would succeed if
  posted by hand. Recorded (W2), not changed — refusing it server-side is an
  engine-lifecycle call the owner can take separately.

### Orchestrator riders (logged, not separately ruled)

- **R1** — `DepartmentComplaintList` (the supervisor Complaints page) today
  offers "Not our department" / move-request buttons on every row including
  ended ones, and its `STATUS_TONES` map is missing `acknowledged`, `closed`
  and `cancelled` (they render an untinted pill). Both fixed in passing: ended
  rows lose the move controls, the tone map learns the missing words.
- **R2** — the possessive marketplace fallbacks a supervisor can still see
  (`'your community'` in `Complaints.jsx`, `'Your community'` in
  `SupervisorDashboard.jsx`) prefer the actual community name the snapshot
  carries, with a neutral "the community" as the last resort.

### Backlog opened by this amendment

- **W1** — `department_complaints` has no pagination or multi-status filter; a
  department with years of history returns everything in one array. Fine at
  current scale; the archive is where it will pinch first.
- **W2** — no server-side write-freeze on ended complaints (notes RPC).

### Adjudications on Amendment 3 (orchestrator, post-build 2026-08-23)

The build specialist flagged six deviations rather than deciding them. Rulings:

- **B-A1 (accepted)** — the layout reads `supervisedEngagement(...)` instead of
  `holdsLeadershipEngagement(...)`: one call yields both the boolean gate and
  the rank that ruling B3 renders. Same predicate, same first-row rule.
- **B-A2 (accepted)** — on ended rows, `DepartmentComplaintList` drops the
  whole transfer block including the informational "a move has been requested"
  notice, not just the buttons. A stale transfer notice on a resolved
  complaint is noise; R1's word "controls" is read broadly.
- **B-A3 (accepted)** — the filter chips carry the short words (Everything ·
  Resolved · Closed · Cancelled); the distinct long labels live on each card's
  status chip. Matches the intent: the chip row filters, the card explains.
- **B-A4 (ruled, follow-up implemented)** — the detail popup opened from the
  archive is part of the archive screen, so it speaks the archive's labels: a
  `closed` complaint's popup chip must read "Closed — confirmed", not the
  wire's "Resolved". `ComplaintDetailModal` gains an optional `statusLabel`
  override; absent, behavior is unchanged, and the dashboard passes nothing.
  This narrows Amendment 3's "nothing else adopts these labels" to: no screen
  *outside* the archive.
- **B-A5 (accepted)** — sentence-position capitalization of the "the
  community" fallback.
- **B-A6 (fixed in follow-up)** — the FRONTEND_CHANGES.md section is moved to
  sit with its sibling feature sections rather than after the legacy tail.

Also recorded: the archive shares the `['departments', {id}, 'complaints']`
query key with the supervisor Complaints page — one cached read serves both,
deliberately.
