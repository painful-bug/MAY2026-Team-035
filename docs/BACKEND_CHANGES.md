# Backend changes

## Security and authentication boundary

FastAPI owns the full authentication lifecycle. Google OAuth is started and
completed by backend routes using Supabase PKCE; the browser receives signed,
HTTP-only session and refresh cookies instead of provider tokens. Unsafe API
requests require the CSRF token exposed in the companion CSRF cookie.

The settings contract fails startup when the server-side Supabase configuration
or `COOKIE_SIGNING_SECRET` is missing. Only Google is accepted by the current
authentication configuration. Membership context is loaded from an active
`community_memberships` row and is used for tenant scope and role checks; no
browser-supplied role or JWT role claims authorize a request.

## Registration and community access

The API router aggregates dedicated routers for:

- authentication and session management;
- community directory search;
- resident access requests and administrator decisions;
- invitations prepared before Google OAuth and redeemed after it;
- founder/community onboarding; and
- dashboard projections and realtime updates.

Services contain the business rules, while repositories isolate Supabase
queries. This separation keeps API route handlers thin and permits the same
flow to support both the fresh baseline schema and the existing legacy hosted
schema during migration.

## Database dashboard projection

`app/api/v1/routers/dashboard.py` exposes:

- `GET /dashboard/snapshot` for the caller's tenant-authorized data;
- `GET /dashboard/events` for a cookie-authenticated SSE stream; and
- administrator/manager-protected amenity create, update, and delete routes.

`app/services/dashboard_service.py` transforms database records into the
existing frontend shape. It maps memberships/profiles/residencies, complaints
and their events, visitor requests, amenities, booking occurrences, invoices
and payments, notices, departments, and audit activity. The service applies
the resident-specific filtering before serializing the snapshot.

`app/repositories/dashboard_repository.py` is the persistence adapter. It
detects the legacy schema only once per process and selects the corresponding
table/relationship shape, allowing the dashboard API to work during the
baseline transition without browser-side schema logic.

## Realtime design

Migration `0007_dashboard_realtime_outbox.sql` creates `sse_events` when it is
not already present and indexes it by `(community_id, id)`. A database trigger
records a small `dashboard.refresh` outbox event for changes to relevant
community tables: memberships, complaints, visitor requests, amenities,
bookings, invoices, payments, notices, departments, and access requests.

The SSE endpoint polls only the active caller's community outbox and emits its
monotonic event ID as the SSE ID. This keeps the frontend simple: it never
receives a cross-tenant row and always refreshes its own authoritative snapshot
after a change. Keepalive comments allow intermediaries to retain the stream.

## Migrations

- `0001_baseline.sql` is the fresh-project schema source of truth.
- `0006_legacy_founder_onboarding_bridge.sql` adds the founder RPC only when a
  legacy project does not already provide it.
- `0007_dashboard_realtime_outbox.sql` is an idempotent compatibility bridge
  for realtime dashboard refreshes.

The bridges are intentionally forward-only. They support an already-created
project without changing the fresh baseline's design.

## Validation

- `python3 -m compileall -q app` checks backend import/compile health.
- The backend test suite covers the Google-only configuration, OAuth PKCE URL,
  registration contracts, migration guards, and unauthenticated dashboard
  route rejection.
- An authenticated smoke test should verify the snapshot contains only the
  active community and that a database mutation results in a
  `dashboard.refresh` SSE event for that community.
