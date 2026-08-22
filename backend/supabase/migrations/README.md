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
| `0034`–`0047` | service operations and security (closed — see below) |

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

**The ranges stopped at `0047`, and nothing should be added to them.** The last
number allocated is `0047`; everything after the deployment boundary is a
timestamp. That is not a third range, it is the end of ranges: numbers exist to
stop two people picking the same next integer, and a timestamp cannot collide,
so the problem the table solves does not arise again. The table is kept because
it explains files that already exist.

This replaced a `0050`–`0059` extension written on 2026-08-12, hours before the
hosted deployment was verified. It was correct under the rule at the time and is
now moot: those three files are `20260812…` and a number was never needed.

The one rule that survives unchanged: **a file keeps the name it was written
with.** This list grows at the end, never in the middle.

## After the boundary

| File | Serves |
|---|---|
| `20260811162409_service_professional_onboarding.sql` | atomic provider registration, mandatory coordinates and active skills, radius-bounded PostGIS search both ways, `can_hire_for_department`, worker/security mode enforcement |
| `20260811163408_service_signup_funnel_telemetry.sql` | the five-event signup funnel and its 30-day retention |
| `20260811192511_fix_unit_residencies_rls_recursion.sql` | the RLS recursion on `unit_residencies` |
| `20260812090000_notification_audiences.sql` | two audiences that were `notify_community_staff` because nothing narrower existed: amenity payments become admin-only, and gate incidents go to admins and **security-department** managers. Rewrites `settle_amenity_booking_payment` (`0033`) and `record_security_incident` (`0040`) in full, because both files are applied |
| `20260812090100_skills_and_categories.sql` | `department_skills`, the trigram search, create-and-attach, and the hiring search reading a department's own skills — **rebased onto `20260811162409`**, whose definition of `search_hireable_service_providers` this would otherwise have silently reverted |
| `20260812090200_staff_provisioning.sql` | `staff_invitations` and the email-bound claim: how a manager or supervisor comes to exist, given that neither has a registration process |
| `20260812090300_complaint_department_routing.sql` | `complaints.department_id`, category-then-pick-then-triage resolution, the supervisor's change request, and the three `0031` complaint notifications that went to every manager because a complaint had no department to send them to |
| `20260812113000_professional_membership_symmetry.sql` | the other direction of the separate-account rule (PO ruling 2026-08-12): `enforce_professional_membership_mode` now refuses a resident/manager/admin membership on a profile holding a `service_providers` row (`HBSEP` → 409). Whole trigger body from `20260811162409`, one predicate added. Also re-issues the stale `search_serviceable_communities` comment from `0034` |
| `20260812120000_work_order_notification_urls.sql` | the seven work-order notifications that pointed at the department list, repointed at the triage screen that now exists; six whole bodies from `0037` and `0039`, seven url lines changed |
| `20260817144725_repair_staff_assignment_employment_type.sql` | `staff_assignments_employment_type_check` recreated as `internal`\|`vendor`\|`staff`. The hosted table predates `0001_baseline.sql` and its hand-built constraint knew only the first two, so every hire through the atomic hiring RPC — which has written `staff` since `0019` gave the column that default — answered 23514 (issue #33). Written on `origin/main` (`c0956a2`, 2026-08-17), **applied and ledgered on hosted the same day**, and copied here byte for byte on 2026-08-22; see the boundary rule below for why it is not rewritten. Runbook §21 |

**This table stops at `20260812120000` apart from the row above.** It was not
kept up as the timestamped files multiplied, and the complete per-file record
after that point is `docs/plans/MIGRATION_APPLY_RUNBOOK.md`, which has a
numbered section for every one of them. The row above is here because that file
arrived from another branch and its provenance needed somewhere to live that a
reader of this directory would find.

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
| `0040_security_operations.sql` | the gate — posts, shifts, two registers, incidents, credential verification and the offline reconcile log — `record_security_incident`'s audience was wrong and is **corrected forward** by `20260812090000`, not here: this file is applied |
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

## How the hosted project gets written, and how drift is reconciled

Written down 2026-08-22, after issue #41. All three rules were already practice;
none of them was anywhere a person could read them, and the one file that broke
all three got committed without anybody having to argue against a sentence.

**1. Only the owner writes the hosted project, by hand, from a runbook section.**
There is no automated deploy and no `db push` against the linked project. A new
migration reaches hosted when it has a numbered section in
[`docs/plans/MIGRATION_APPLY_RUNBOOK.md`](../../../docs/plans/MIGRATION_APPLY_RUNBOOK.md)
saying what it does, what to expect, what to check afterwards, and the
`insert into supabase_migrations.schema_migrations` line that ledgers it — and
an entry in [`docs/CHANGE_LOG.md`](../../../docs/CHANGE_LOG.md) saying why it
exists. A file with neither has not been applied, whatever else is true about it.
That is not bureaucracy; it is the only paper trail there is, because the SQL
Editor writes no ledger row by itself (runbook §12).

**2. Hosted-vs-git drift is reconciled forward-only, and never by committing a
`supabase db diff`.** The hosted database predates `0001_baseline.sql` and
carries hand-built columns, defaults and constraints that no migration here
declares. When one of them bites, the cure is a **targeted** timestamped
migration that names the one thing that is wrong, verifies itself, and ships
with a derivation-pinned `test_*_migration.py` — `20260820120000_hosted_complaint_column_drift.sql`
and `20260822090000_hosted_work_order_column_drift.sql` are the worked examples,
and `20260817144725` above is the smallest possible one.

A `supabase db diff` snapshot is the opposite of that and must never be
committed as a migration. It is a *difference*, not a decision: it restates
every object it saw, so it recreates tables the project retired, drops triggers
and policies it has no opinion about, and alters generated columns, which
Postgres refuses outright. `20260818141040_remote_schema.sql` on `origin/main`
is 9,831 lines of exactly that, and a fresh apply of this directory dies inside
it. That version is ledgered on the hosted project, so it cannot simply be
deleted; the file at that name here is a comment-only **tombstone** carrying
the record and no SQL, which is what keeps this directory, a fresh
`supabase db reset` and the hosted ledger in agreement (runbook §22).
`backend/tests/test_migration_directory_is_fresh_appliable.py` now sweeps
the whole directory for that file's shape — six checks, every pattern
case-insensitive, because `db diff` writes uppercase SQL and every pin in this
repository was lowercase-only until then.

**3. Every timestamped migration gets a `backend/tests/test_*_migration.py`.**
Nothing in this repository ever runs these files, so a test is the only reader
they will have before the owner pastes them into a live database. The house
style is *derivation-pinned*: whatever list the migration depends on — allowed
values, protected columns, a function body it copies forward — is read out of
the declaring file's own text and compared, never typed into the test from a
review. A test that re-states the reviewer's belief passes for the same reason
the migration is wrong.

**Versions must sort after every shared branch, not just your own.** A new file
timestamps later than the latest migration on **any** branch someone else might
push — as of 2026-08-22 that is `20260822170000`. Timestamps were adopted
precisely because they cannot collide (see the end of "Number ranges" above),
and issue #41 is the incident that showed the argument had a hole in it: two
different `20260822120000_supervisor_triage.sql` files existed at once, one on
this branch and one uncommitted in another workstream, because both were written
the same afternoon and each took "now" as its version. `now` is not unique
across working trees. Check the directory on `origin/main` and on every live
feature branch before you name a file, and if you are holding an uncommitted
migration whose version has since been taken, rename it upward before it is
committed or applied anywhere.

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
