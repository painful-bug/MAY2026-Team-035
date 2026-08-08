# Migrations

Applied in filename order. `0001_baseline.sql` is headed *"Apply only to a new
Supabase project"*; everything after it is additive.

**None of them has been applied to any database yet** — including
`0001_baseline.sql`.

## Number ranges

Numbers are reserved **by workstream as a range**, and allocated to a file only
when that file is written:

| Range | Workstream |
|---|---|
| `0018`–`0024` | admin dashboard |
| `0025`–`0039` | resident backend |

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
| `0032_visitor_passes.sql` | the six resident visitor-pass endpoints, the hashed security code, and the first reader `visitor_code_ttl_minutes` has ever had |
| `0033_resident_money_and_home.sql` | the eight resident money and home endpoints, the settlement RPCs the simulated gateway feeds, and RLS on `notices`, `unit_residencies` and `departments`, which had none |

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
