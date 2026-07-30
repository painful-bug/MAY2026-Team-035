# Migrations

Applied in filename order. `0001_baseline.sql` is headed *"Apply only to a new
Supabase project"*; everything after it is additive.

`0018`–`0024` are the admin-dashboard workstream's. None of them has been
applied to any database yet.

| File | Serves |
|---|---|
| `0018_settings_on_baseline.sql` | `GET`/`PUT /settings`, `GET`/`PUT /billing-settings`, notice metadata |
| `0019_departments_on_baseline.sql` | the 9 department and staff endpoints, plus the two shared RLS predicates |
| `0020_complaint_events_on_baseline.sql` | `PATCH /complaints/{id}`, `POST .../comments` |
| `0021_money_on_baseline.sql` | `POST /invoices`, `POST .../payments` |
| `0022_settings_views_on_baseline.sql` | the settings read views |
| `0023_amenities_on_baseline.sql` | the 16 booking, ledger and report endpoints |
| `0024_realtime_join_requests.sql` | `access_request.created` / `.decided` on the SSE outbox |

Between them these create **11 views and 37 functions**, of which 24 are the
write RPCs the repositories call; the other 13 are trigger functions and the
shared RLS predicates. `pglast` — the real PostgreSQL parser — confirms every
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
