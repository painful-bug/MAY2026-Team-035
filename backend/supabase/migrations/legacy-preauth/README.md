# Pre-baseline migrations — reference only, do not apply

**Do not run any file in this directory against a database.** They target a
schema that no longer exists.

## What happened

These eight migrations were written for the schema that `0001_init.sql`,
`0002_rls.sql` and `0003_access_token_hook.sql` created. `origin/main` @ `94556e5`
deleted all three and replaced them with a single `0001_baseline.sql`, headed
*"Apply only to a new Supabase project"*, which renamed or reshaped most of the
tables these files depend on:

| These files use | The baseline has |
|---|---|
| `associations` | `communities` |
| `apartments (association_id, code)` | `units (community_id, unit_code)` |
| `profiles.association_id` | `community_memberships.community_id` |
| `amenity_booking_series` + `amenity_booking_occurrences` | one `amenity_bookings` with a GIST exclusion constraint |
| `amenity_rules` (typed) | `amenities.booking_rules jsonb` |
| `module_catalogue` + `community_modules` | `feature_catalog` + `community_features` |
| `registration_requests` | `access_requests` |
| invoices liable by unit | `invoices.membership_id` |
| a `custom_access_token_hook` putting `role` in the JWT | no hook; role resolved from `community_memberships` |

There are **256 references to deleted tables** across the eight files.

## Why they are kept

They are 7 315 lines of reviewed SQL — RLS policies, RPCs, CHECK constraints and
the reasoning behind each — and the rebuild is a translation, not a redesign. The
comments are the expensive part. Deleting them would throw away the analysis and
keep only the conclusion.

## Why they are quarantined rather than left in place

Before this move there were two mutually exclusive sets of unapplied SQL sitting
in one directory: the baseline, which requires a fresh project, and `0010`–`0017`,
which assume `0001`–`0003` ran first. Applying the wrong set first is a way to
lose a database. Numbering them as though they follow `0007` was the hazard.

## What replaces them

`../0018_settings_on_baseline.sql` re-creates, on baseline tables, the part the
surviving endpoints need: `community_settings`, `community_billing_settings`,
`notices.category`/`.urgency`, RLS for the two new tables, and an extension of the
shared SSE outbox over them.

**All of them have now been rebuilt.** Migrations `0019`–`0023` sit beside `0018`
in the parent directory and target the baseline:

| Rebuilt as | Replaces | Serves |
|---|---|---|
| `0019_departments_on_baseline.sql` | `0014` | 9 department/staff endpoints, plus the two shared RLS predicates |
| `0020_complaint_events_on_baseline.sql` | `0013` | `PATCH /complaints/{id}`, `POST .../comments` |
| `0021_money_on_baseline.sql` | `0015` | `POST /invoices`, `POST .../payments`, `GET`/`PUT /billing-settings` |
| `0022_settings_views_on_baseline.sql` | `0017` (views only) | `GET`/`PUT /settings` |
| `0023_amenities_on_baseline.sql` | `0016` | the 16 booking, ledger and report endpoints |

`0010`–`0012` were **not** rebuilt and will not be: the reads they backed were
removed by the wiring audit, and their RLS reasoning has been absorbed into the
five files above.

Between them these create 10 views and 24 write RPCs. A static check
(`pglast`, the real PostgreSQL parser) confirms every migration parses, that
every RPC our repositories call is created by one of them, and that every column
our repositories select exists on the table or view they select it from.

**None of this has been applied to a database.** That is still F1, and it is now
the only thing standing between these endpoints and working.

## The amenities decision, settled

The section that used to sit here argued for keeping our series + occurrences
model, on the grounds that their own submitted ERD modelled it too.

**That argument no longer holds.** `origin/main` @ `db85c04` rewrote the ERD to
match the baseline: `amenity_booking_series`, `amenity_booking_occurrences` and
the typed `amenity_rules` are gone, and `amenity_bookings`,
`amenity_operating_hours`, `amenity_maintenance_blocks`, `booking_charges` and
`booking_refunds` are in. On amenities the ERD now agrees with their baseline,
not with the design in this directory.

Conforming exactly would have cost a product behaviour, though. A resident books
up to thirty dates in one request and an admin approves the whole request with
one click, so one row per date with nothing joining them would mean approving a
twelve-date request twelve times.

`0023` therefore keeps the baseline's single `amenity_bookings` as the only
booking table and adds **one nullable `booking_group_id` column** to it. No
series entity, no second table, the ERD's table set unchanged, the GIST
exclusion constraint still preventing double-booking per row — and a multi-date
request is still one thing to approve. The column name converges with
`bookingGroupId`, which their own `dashboard_service.py:149` already emits.

## What is still referenced but will never exist

Their `dashboard_repository.py` reads `amenity_booking_series`,
`amenity_booking_occurrences` and `visitor_access_requests` in its `legacy=True`
branch. Those three tables are deliberately not created: the branch exists to
support a database that predates the baseline, and the non-legacy branch beside
it reads the baseline shape. Nothing of ours references them.
