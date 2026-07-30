# Current architecture

This document describes the implementation committed in `94556e5`. It replaces
the pre-implementation “current state” assessment in
`AUTH_REGISTRATION_IMPLEMENTATION_PLAN.md` as the architecture reference.

The detailed, source-backed class diagram is available as editable
[PlantUML source](diagrams/HomeBandhu-Architecture-Classes.puml) and a rendered
[PNG](diagrams/HomeBandhu-Architecture-Classes.png).

## Component and trust-boundary diagram

```mermaid
flowchart LR
    User["Resident, administrator, security, or worker"] --> UI

    subgraph Browser["React/Vite browser — no Supabase SDK or provider tokens"]
        UI["Routes and portal pages"]
        AuthStore["authStore\nserver session state"]
        Bootstrap["DashboardDataBootstrap"]
        Cache["appStore\nephemeral render cache"]
        Amenity["Amenity service"]
        UI --> AuthStore
        UI --> Bootstrap
        Bootstrap --> Cache
        UI --> Amenity
    end

    subgraph API["FastAPI — same-origin /api/v1"]
        Auth["Auth router/service\nGoogle PKCE, cookies, CSRF"]
        Registration["Community, onboarding,\naccess-request, invitation routers/services"]
        Dashboard["Dashboard router/service\nsnapshot and SSE"]
        Repositories["Repository layer\nSupabase/PostgREST and RPC adapters"]
        Auth --> Repositories
        Registration --> Repositories
        Dashboard --> Repositories
    end

    UI -->|"fetch with HttpOnly cookies\nCSRF on unsafe methods"| Auth
    UI -->|"registration and invitation requests"| Registration
    Bootstrap -->|"GET dashboard/snapshot"| Dashboard
    Bootstrap -->|"EventSource dashboard/events"| Dashboard
    Amenity -->|"authorized amenity CRUD"| Dashboard

    Auth -->|"PKCE authorization/exchange"| SupabaseAuth["Supabase Auth"]
    SupabaseAuth --> Google["Google OAuth"]
    Repositories --> DB["Supabase Postgres\n0001_baseline.sql"]
    DB --> Outbox["sse_events\ndashboard.refresh outbox"]
    Outbox --> Dashboard
```

## Runtime sequence for authenticated dashboards

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as FastAPI
    participant D as Postgres

    B->>A: GET /auth/session (HTTP-only cookie)
    A-->>B: Safe identity + active membership context
    B->>A: GET /dashboard/snapshot
    A->>D: Tenant-scoped database projection
    D-->>A: Community records
    A-->>B: Normalized dashboard snapshot
    B->>B: hydrateDashboard(render cache)
    B->>A: GET /dashboard/events (EventSource)
    D->>D: Domain insert/update/delete
    D->>D: Trigger writes sse_events(dashboard.refresh)
    A-->>B: dashboard.refresh SSE event
    B->>A: GET /dashboard/snapshot
    A-->>B: Refreshed authoritative snapshot
```

## Responsibilities

| Layer | Responsibility | Does not do |
| --- | --- | --- |
| Browser routes/pages | Render views and collect user intent. | Direct Supabase calls or tenant authorization. |
| `authStore` | Read backend session, begin Google redirect, logout. | Store OAuth credentials or decide roles. |
| `DashboardDataBootstrap` | Hydrate and refresh the dashboard cache. | Persist tenant records in browser storage. |
| API routers | HTTP contracts, cookies/CSRF dependencies, role guards. | Embed database query logic. |
| Services | Registration, invitation, projection, and policy rules. | Trust client-supplied identity or role. |
| Repositories | Supabase/PostgREST and database RPC operations. | Expose raw provider credentials to the browser. |
| Postgres baseline | Community data, membership scope, RLS, RPC transactions, event outbox. | Authenticate browser users directly. |

## Domain model rules

- `auth.users` is external Google-authenticated identity; `profiles` is its
  application contact record.
- `community_memberships` is the sole tenant-role source. Active, non-ended
  membership determines both community scope and portal authorization.
- `resident_invites` stores opaque token/code hashes and binds redemption to a
  verified Google email; it is not an authentication factor.
- `access_requests` is the resident join-request workflow. Approval creates
  the resident membership and optional `unit_residencies` record atomically.
- `sse_events` is an internal, tenant-scoped refresh outbox. It does not expose
  direct Postgres subscriptions to the browser.

## Design status

The ERD in `homebandhu_submission_erd.dbml` now mirrors the table, enum, key,
and relationship definitions in `backend/supabase/migrations/0001_baseline.sql`.
Compatibility migrations `0006` and `0007` exist only for an older hosted
project; they do not change the fresh-baseline model.

The amenity management CRUD flow is database-backed. Booking and ledger read
models are loaded through the snapshot, but their remaining client-side action
handlers require their own backend mutation endpoints before they can claim
durable realtime writes.
