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

**Still to be rebuilt**, in the order the endpoints matter:

| File | Serves | Note |
|---|---|---|
| `0014_departments.sql` | 8 department/staff endpoints | Highest value — the snapshot stubs `staff: []`, so these are the only source. Baseline already has `departments`, `staff_assignments`, `skills`. |
| `0013_complaint_events.sql` | `PATCH /complaints/{id}`, `POST .../comments` | Baseline has `complaints`, `complaint_events`, `complaint_comments`. Mostly a rename. |
| `0015_money.sql` | `POST /invoices`, `POST .../payments`, billing settings RPCs | Invoice liability moves from unit to `membership_id`. |
| `0016_amenities.sql` | 16 booking/ledger/report endpoints | Largest (2 757 lines) and the real design conflict: our series+occurrences model versus their single `amenity_bookings`. See below. |
| `0010`–`0012` | tenancy, dashboard views, people | Largely superseded — the reads they backed were removed by the wiring audit. Salvage the RLS reasoning, not the views. |

## The amenities decision that is still open

Their `dashboard_service.py` reads `row.get("booking_series_id")` in its legacy
branch, which suggests a series id was anticipated. The cheapest additive path is
therefore to add an `amenity_booking_series` table plus a nullable
`amenity_bookings.booking_series_id`, treating their rows as our occurrences —
their single-table reads keep working, and recurring bookings become
representable. That keeps both models instead of choosing.

Worth noting when this is decided: their own submitted ERD
(`docs/homebandhu_submission_erd.dbml`) models `amenity_booking_series`,
`amenity_booking_occurrences` and a typed `amenity_rules`. On amenities the ERD
agrees with the design in this directory, not with their baseline.
