# Migrations

Applied in filename order. `0001_baseline.sql` is headed *"Apply only to a new
Supabase project"*; everything after it is additive.

The linked hosted project was verified on 2026-08-11 with every repository
migration through `0047` applied. Those files are immutable. All fixes and new
features now use forward-only timestamped migrations; never edit an applied
file or weaken constraints to accommodate hosted drift.

Rows below that say **corrected `<date>`** describe corrections made before the
linked deployment boundary was verified. They are historical context, not
permission to edit those migrations again.

## Number ranges

Numbers are reserved **by workstream as a range**, and allocated to a file only
when that file is written:

| Range | Workstream |
|---|---|
| `0018`–`0024` | admin dashboard |
| `0025`–`0033` | resident backend |
| `0034`–`0049`, `0050`–`0059` | service operations and security |

Two rules make this work. A workstream takes the lowest free number **in its own
range** at the moment it writes a file, so two people writing at once cannot
collide. And nothing requires the numbers to be contiguous — only filename order
matters, which is why `0028` can ship before `0025` exists.

The alternative — reserving a specific number for each planned migration in
advance — was tried here and removed. It assigns filenames to work whose shape
is not yet decided, so reordering or dropping a step silently makes this file
wrong. The resident build order lives in
[`docs/design/RESIDENT_BACKEND_DESIGN.md`](../../../docs/design/RESIDENT_BACKEND_DESIGN.md) §9,
which is allowed to change; the numbers here follow it rather than binding it.

The third range was split off the resident one on 2026-08-10, when this table
still read `0025`–`0039` for a workstream that had stopped at `0033` and a
service-operations build that was already six files into it. The split is
bookkeeping catching up with what the directory says. The same rule caught its
own worked example immediately: the service plan had reserved `0039` for security
operations, the worker portal needed a migration nobody had planned for, and
`0039` went to whoever wrote first — security operations is `0040`.

**`0050`–`0059` was added to that third range on 2026-08-12**, because `0049` had
taken the last number in `0034`–`0049` and complaint department routing still
needed a file. Two things made this the boring option rather than a decision:
nothing claims `0050`+, and the rule above is *lowest free number in your own
range*, which only works if a range that runs out gets extended rather than
quietly borrowing from a neighbour. Extending is bookkeeping; borrowing is the
collision the rule exists to prevent.

An extension is not a licence to renumber. The rule that a file keeps the number
it was written with still holds — this table grows at the end, never in the
middle.

| File | Serves |
|---|---|
| `0018_settings_on_baseline.sql` | `GET`/`PUT /settings`, `GET`/`PUT /billing-settings`, notice metadata |
| `0019_departments_on_baseline.sql` | the 9 department and staff endpoints, plus the two shared RLS predicates |
| `0020_complaint_events_on_baseline.sql` | `PATCH /complaints/{id}`, `POST .../comments` |
| `0021_money_on_baseline.sql` | `POST /invoices`, `POST .../payments` |
| `0022_settings_views_on_baseline.sql` | the settings read views, and the module catalogue's backend status — **corrected 2026-08-04**: its `where code in (...)` lists were guesses and matched nothing, so every module would have reported `absent` |
| `0023_amenities_on_baseline.sql` | the 16 booking, ledger and report endpoints |
| `0024_realtime_join_requests.sql` | `access_request.created` / `.decided` on the SSE outbox |
| `0028_event_audience.sql` | `GET /events` — gives every outbox row an audience so one stream can serve every role |
| `0029_bookable_amenity_view.sql` | `GET /amenities/available` — the resident's projection of the amenity catalogue |
| `0030_notifications.sql` | the notification record every user-visible event writes, its feed, and the Web Push subscription table |
| `0031_resident_complaints.sql` | the six resident complaint endpoints, the SLA rule, and the notifications every complaint write emits |
| `0032_visitor_passes.sql` | the six resident visitor-pass endpoints, the hashed security code, and the first reader `visitor_code_ttl_minutes` has ever had — **corrected 2026-08-11**: `decide_visitor_pass` linked the gate to `/security/visitors`, a route that has never existed |
| `0033_resident_money_and_home.sql` | the eight resident money and home endpoints, the settlement RPCs the simulated gateway feeds, and RLS on `notices`, `unit_residencies` and `departments`, which had none |
| `0034_service_providers.sql` | who a service person is, and the search that finds them work before anybody has hired them |
| `0035_department_roles_and_hiring.sql` | three ranks, `service_applications`, and the one RPC that creates a membership and a roster row in the same transaction |
| `0036_work_orders.sql` | the job, and the exclusion constraint that stops one person being in two places at once — **corrected 2026-08-11**: three worker notifications linked to `/worker/jobs/<id>`, and the worker portal has no `jobs` route |
| `0037_dispatch_engine.sql` | `dispatch_tasks`, the sweep and the four firing RPCs — no endpoints at all. **Corrected 2026-08-11**: the same broken worker link as `0036`, in a second spelling |
| `0038_conversations.sql` | the hiring thread between a department and a provider |
| `0039_worker_actions.sql` | the worker's own side: three views, five verbs, and their working week |
| `0040_security_operations.sql` | the gate — posts, shifts, two registers, incidents, credential verification and the offline reconcile log — **corrected 2026-08-12**: `record_security_incident` notified `array['admin','manager']`, so every manager in the community was told about gate incidents and sent to a screen only *some* of them have. The audience now mirrors `_portal_for`'s own predicate |
| `0041_person_notifications.sql` | the notification substrate re-addressed from a membership to a person, so a service provider who has not been hired can be told anything at all — plus the conversation's first notification and the notice board's |
| `0042_roster_provider_link.sql` | one column on `department_staff_overview`, so a roster row can say which service provider it is — the write path has filled `staff_assignments.service_provider_id` since `0035` and no read returned it |
| `0043_staff_departures.sql` | leaving a community becomes a process a manager approves: a departure freezes the dispatch engine against that person, every job and shift in their name is handed over through the same ranking auto-assignment uses, and only an empty list lets the approval through — `remove_department_member` gains the refusal, and a bar releases the work instead of queueing behind it. **Corrected 2026-08-11**: `reassign_departure_item` sent the guard receiving a handed-over shift to `/security-manager/shifts`, which is neither a route nor their portal |
| `0044_retire_dead_tables.sql` | drops `staff_skills` (superseded by `service_provider_skills`, D2) and `vendors` plus its `staff_assignments.vendor_id` column (superseded by `service_providers`, D1) — the deletion R16's amendment promised |
| `0045_departure_scheduling.sql` | a departure gets a date and the manager gets the decision: the time-aware freeze (`departure_bars_work`), the queue-priority column on `dispatch_tasks` with the `departure_removal` timekeeper as the fifth kind, windowed release, decide-with-date — **overturns 0043's zero-commitment refusal on Approve** (PO, 2026-08-10; the gate survives on direct Remove) — plus `departure_coverage`, `staff_schedule_items`, and a name that settings can no longer rewrite |
| `0046_direct_messages.sql` | person-to-person chat for the dock on every portal: one thread per pair per community, the worker↔resident job thread that locks when the work order ends, `dm_pair_allowed`/`dm_recipients` ("the committee" is the admin role), and names as snapshots because `profiles` is self-read-only |
| `0047_security_roster.sql` | one read function, `security_roster` — the shift form's guard picker, authorized by `gate_admin_community_for`, because a security-rank manager cannot reach the hiring surface's roster reads. No table, no view; the ERD is untouched |
| `20260811162409_service_professional_onboarding.sql` | atomic provider registration, mandatory coordinates and active skills, radius-bounded PostGIS search in both directions, exact department-manager/admin-fallback hiring authority, worker/security mode enforcement, and community coordinate writes |
| `20260811163408_service_signup_funnel_telemetry.sql` | the narrow five-event signup funnel and its 30-day retention job; no generic analytics or experiment framework |

`0028` is the resident range's first file rather than `0025` because §9 puts it
first: it closes a disclosure in code that already ships instead of adding a
feature, and it was numbered when it was written. `0029` is the rule working as
intended — it was drafted as the notification migration, that step has not been
written yet, and the number went instead to the file that was.

**`0031` is where the rule needed a second half.** `0025` was free and it would
have been wrong: migrations apply in filename order, every RPC in that file calls
`notify_member`, and `notify_member` is created by `0030`. Postgres would not
have objected — a plpgsql body is not resolved against the catalogue until it
runs — so the file would have applied cleanly and failed at the first complaint.
*Allocate a number when the file is written* does not mean *take the smallest
free one*; it means the number is chosen with the file in front of you, and what
decides it is dependency order. `0025`–`0027` stay free, and a later migration
may take one only if it depends on nothing above it.

`0032` and `0033` are the same constraint applied without incident: both call
`notify_member`, so both go above `0030` and the free numbers below stay free.
Once a rule has a worked example, following it stops being a decision.

**`0018`–`0033` and `0034`–`0040` are counted separately below, because the
second range's figures are new and the first's have been checked repeatedly.**
The service-operations range adds **14 views and 62 functions** across its seven
files — nearly as many functions as the thirteen before it, which is what a
posture of *no write policy anywhere* costs: every write is a function, so a
surface with nineteen write endpoints has at least nineteen of them. That is the
trade `0031` made and every file since has kept, and it is worth being able to
see the price of.

The paragraph that follows describes `0018`–`0033` and is left as counted.

Between them these create **20 views and 69 functions**. Of the functions, **43
are called by name from `app/repositories` or `app/services`**; the other 26 are
called by triggers, by policies or by each other. They are the trigger functions,
the six shared authorization predicates (`is_community_member`,
`is_community_admin`, `is_own_membership`, `is_community_security`,
`is_own_invoice`, `is_own_booking`), the notification fan-out (`notify_member`,
`notify_community_roles`, `notify_community_staff`), the pricing and SLA helpers
(`amenity_charge_for`, `complaint_sla_hours`), `expire_visitor_passes`, and the
two outcome-shape helpers `0033` added — `payment_as_outcome` and
`booking_payment_as_outcome`, which exist so that the settlement RPC, its replay
branch and the pre-flight lookup all describe a payment from the row rather than
assembling three versions of the same five fields. Every figure here is recounted from the files, not carried
forward. `pglast` — the real
PostgreSQL parser — confirms every
file above parses, that every RPC the repositories call is created by one of
them, and that every column they select exists on the table or view selected
from.

## The gap at 0009–0017

Those numbers were used once, by eight migrations written against the schema
`0001_init.sql`, `0002_rls.sql` and `0003_access_token_hook.sql` created —
`associations`, `apartments`, `profiles.association_id`, and a two-table
`amenity_booking_series` + `amenity_booking_occurrences` model. `origin/main`
@ `94556e5` deleted all three of those files and replaced them with
`0001_baseline.sql`, which renamed or reshaped nearly every table they depend
on. There were 256 references to deleted tables across the eight.

They were quarantined in `legacy-preauth/`, then rebuilt as `0018`–`0023` and
removed from the tree. The numbers are not reused, so that a database whose
history includes the old files cannot silently take a new one in its place.

To read an original — several of the rebuilt files carry over its reasoning
rather than repeating it:

```
git show e593084:backend/supabase/migrations/legacy-preauth/0014_departments.sql
git show e593084:backend/supabase/migrations/legacy-preauth/README.md
```

`0010`–`0012` were never rebuilt and will not be: the reads they backed were
removed by the frontend wiring audit, and their RLS reasoning is absorbed into
`0019`–`0023`.

## Three tables that are referenced but will never exist

`dashboard_repository.py` reads `amenity_booking_series`,
`amenity_booking_occurrences` and `visitor_access_requests` in its `legacy=True`
branch. Those are deliberately not created: that branch exists to support a
database predating the baseline, and the non-legacy branch beside it reads the
baseline shape. Nothing in `0018`–`0024` references them.
