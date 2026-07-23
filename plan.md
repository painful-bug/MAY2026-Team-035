# Supabase Backend Integration + RBAC Authentication

## Context

HomeBandhu currently has **no backend** — all domain state lives in Zustand stores seeded
from `frontend/src/data/*.js`, and auth is fully simulated. `backend/models/models.py` is an
empty stub. The team has decided to build the real backend on **Supabase** (Postgres, Auth,
Storage, Realtime) fronted by a **Python FastAPI** service, and to implement proper
**role-based access control** for five roles: `RESIDENT, MANAGER, TECHNICIAN, SECURITY, ADMIN`
(ADMIN is also a RESIDENT).

This plan delivers two things the user asked for:
1. A **single Supabase entry-point util** that every backend operation goes through, using the
   official `supabase` Python SDK.
2. A concrete **auth + RBAC implementation** with two flows:
   - **Login (existing members):** phone **SMS OTP** + "remember me".
   - **Registration (new residents):** admin-initiated, delivered as a **magic link _and_ a
     typable code** — the resident can click the link or paste the code, either activates them.
   - Enforcement = **JWT custom claims + Postgres RLS + FastAPI role guards** (defense in depth).

> **Note — supersedes old docs.** `docs/AGENTS.md` names a future *Node/Express/Prisma* stack.
> That is now replaced by Python/FastAPI/Supabase. Root `AGENTS.md`, `docs/CLAUDE.md`, and
> `README.md` will be updated at the end (tracked as a follow-up task, not part of the code build).

## Decisions locked in (from Q&A)
- **Framework:** FastAPI.
- **Login:** Supabase **phone SMS OTP** (`sign_in_with_otp` / `verify_otp`), `should_create_user=false`
  so only already-provisioned numbers can log in. Remember-me = frontend persists the Supabase
  session (localStorage) vs session-only (sessionStorage); backend exposes a `/auth/refresh` endpoint.
- **Registration:** admin-initiated. Because Supabase's native invite/magic-link is **email-based**
  and this app is **phone-based**, the link+code carrier is a small custom `invitations` table
  (token for the link, short code for manual entry — both hashed at rest, single-use, expiring).
  Supabase still owns identity/session: on redemption we call the **Admin API**
  (`auth.admin.create_user(phone=..., phone_confirm=True)`) and issue a real Supabase session.
  This is the one deliberate deviation from "pure Supabase feature," and it exists only because
  phone invites aren't first-class in GoTrue. (Alternative if we switch to email later: use
  `auth.admin.generate_link(type="invite")` directly and drop the custom table.)
- **RBAC:** role stored on `profiles`, injected into the JWT by a Supabase **custom access-token
  hook**, enforced by **RLS** in Postgres **and** FastAPI dependency guards.

## Prerequisites (config / infra — done in Supabase dashboard, not code)
- A Supabase project; capture `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
  and the project **JWT secret** (for verifying tokens server-side).
- An **SMS provider** wired into Supabase Auth (MSG91 is India-friendly; Twilio/Vonage also work).
  For local/dev, register **test phone numbers with fixed OTPs** in Auth settings so we don't send
  real SMS during development.
- Register the custom **access-token hook** in Auth → Hooks after migration `0003` runs.

## Backend layout (Google Python style: package by layer, small modules, type-hinted, docstringed)

```
backend/
  app/
    main.py                     # FastAPI factory: CORS, routers, exception handlers, health check
    config.py                   # pydantic-settings Settings (env-driven, cached)
    core/
      supabase_client.py        # ★ THE util — single entry point for all Supabase access
      security.py               # JWT verify (Supabase secret), current-user + role-guard deps
      exceptions.py             # AppError hierarchy + FastAPI handlers
      logging.py                # structured logging setup
    domain/
      roles.py                  # Role enum + hierarchy (ADMIN ⊇ RESIDENT), role-check helpers
      schemas.py                # Pydantic DTOs: Profile, Invitation, OtpRequest, Session, ...
    repositories/               # data access — EVERYTHING goes through core.supabase_client
      profiles_repository.py
      invitations_repository.py
    services/                   # business logic (framework-agnostic, unit-testable)
      auth_service.py           # otp request/verify, refresh, me
      invitation_service.py     # create invite (link+code), redeem (link|code) -> provision+session
    api/
      deps.py                   # get_current_user, require_role(...), get_db clients
      v1/routers/
        auth.py                 # /auth/otp/request, /auth/otp/verify, /auth/refresh, /auth/me
        invitations.py          # POST /admin/invitations (admin), POST /auth/redeem (public)
  supabase/migrations/
    0001_init.sql               # enum user_role; associations, units, apartments, profiles, invitations
    0002_rls.sql                # enable RLS + per-role policies
    0003_access_token_hook.sql  # custom hook fn injecting user_role claim + grants
  tests/                        # pytest: pure logic (invitation redeem, role hierarchy)
  .env.example
  pyproject.toml                # deps below
  README.md                     # setup + run
```

**Dependencies:** `fastapi`, `uvicorn[standard]`, `supabase` (supabase-py v2), `pydantic`,
`pydantic-settings`, `pyjwt[crypto]` (verify Supabase JWT), `httpx`. Dev: `pytest`, `ruff`.

## 1. The Supabase util — `backend/app/core/supabase_client.py`
Single module every other layer imports; no `create_client` call exists anywhere else.

- `get_supabase() -> Client` — **anon-key** client (subject to RLS). Cached singleton.
- `get_service_client() -> Client` — **service-role** client (bypasses RLS). Cached singleton.
  Used only for privileged ops: `auth.admin.create_user`, sending OTP where needed, invite provisioning.
- `get_user_client(access_token: str) -> Client` — a client with the caller's JWT attached
  (`postgrest.auth(token)` / `ClientOptions(headers=...)`) so **RLS runs as that user**. This is
  the default path for request-scoped data reads/writes, giving us DB-enforced RBAC for free.
- Clients built from `config.Settings`; `ClientOptions` sets schema, auto-refresh off for the
  server-side service client. Module docstring documents anon-vs-service safety rules.

## 2. Config — `app/config.py`
`Settings(BaseSettings)` reading `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
`SUPABASE_JWT_SECRET`, `FRONTEND_BASE_URL` (for building `/join/<token>` links), `INVITE_TTL_HOURS`,
`ENV`. `@lru_cache get_settings()`. `.env` git-ignored (already covered by `.gitignore`); ship `.env.example`.

## 3. RBAC model — `app/domain/roles.py`
- `class Role(str, Enum): RESIDENT, MANAGER, TECHNICIAN, SECURITY, ADMIN`.
- Hierarchy: `ADMIN` implies `RESIDENT` (ADMIN passes any `require_role(RESIDENT)` check). Staff roles
  (`MANAGER, TECHNICIAN, SECURITY`) are distinct, non-overlapping capabilities.
- Helpers: `role_satisfies(user_role, required) -> bool`, `ALLOWED = {...}`. Pure, unit-tested.
- Postgres mirror: `create type user_role as enum (...)` in `0001`.

## 4. Database & RLS (`supabase/migrations/`)
- **0001_init.sql** — `user_role` enum; `associations`, `units` (blocks/villas), `apartments`,
  and **`profiles`** (`id uuid pk references auth.users(id) on delete cascade`, `role user_role`,
  `full_name`, `phone`, `apartment_id`, `association_id`, `status`, timestamps). **`invitations`**
  (`id`, `token_hash`, `code_hash`, `phone`, `apartment_id`, `role`, `association_id`,
  `expires_at`, `redeemed_at`, `created_by`). A trigger creates a `profiles` row on `auth.users`
  insert (default role `RESIDENT`).
- **0002_rls.sql** — `alter table ... enable row level security` on every app table; policies keyed
  on `auth.jwt() ->> 'user_role'` and `auth.uid()`. Examples: resident reads/writes only rows for
  their `apartment_id`; technician sees complaints assigned to them; security sees visitor rows;
  admin (`user_role = 'ADMIN'`) full access within their `association_id`.
- **0003_access_token_hook.sql** — `public.custom_access_token_hook(event jsonb) returns jsonb`
  that looks up `profiles.role` for the user and adds a top-level `user_role` claim; grant execute
  to `supabase_auth_admin`; then register it in the dashboard (Auth → Hooks → Access Token).

## 5. Auth implementation
**`core/security.py`** — `decode_token(jwt)` verifies with `SUPABASE_JWT_SECRET` (HS256,
`aud='authenticated'`), returns a `Principal(user_id, role, phone)`. Raises 401 on failure.

**`api/deps.py`**
- `get_current_user` — extracts Bearer token, returns `Principal`.
- `require_role(*roles)` — dependency factory; 403 unless `role_satisfies`. Used as
  `Depends(require_role(Role.ADMIN))` on admin routes.
- `get_request_client` — returns `get_user_client(token)` so downstream repo calls hit RLS as the user.

**`services/auth_service.py`**
- `request_login_otp(phone)` → `get_service_client().auth.sign_in_with_otp({phone, options:{should_create_user:false}})`.
- `verify_login_otp(phone, token)` → `verify_otp({phone, token, type:'sms'})` → return session (access+refresh, expiry).
- `refresh(refresh_token)` → `auth.refresh_session(refresh_token)` (remember-me path).
- `me(principal)` → profile via `profiles_repository`.

**`services/invitation_service.py`**
- `create_invitation(admin_principal, phone, apartment, role)` — admin-guarded. Generate a random
  URL-safe **token** (the link) and a short **code** (e.g. 8 chars); store **hashes** only
  (reuse the hashing idea from `frontend/src/lib/tokens.js`); set `expires_at`. Return
  `{ link: f"{FRONTEND_BASE_URL}/join/{token}", code }` **once** (plaintext never re-shown).
- `redeem(token_or_code, phone)` — pure validity decision mirrors
  `frontend/src/lib/invites.js#applyRedeem` (valid / used / expired). On success:
  `get_service_client().auth.admin.create_user({phone, phone_confirm:True, user_metadata})`,
  upsert `profiles.role`, mark invitation `redeemed_at`, then issue a session so the resident lands
  logged in. Idempotent + single-use enforced in a transaction.

**`api/v1/routers/`**
- `auth.py`: `POST /auth/otp/request`, `POST /auth/otp/verify`, `POST /auth/refresh`, `GET /auth/me`.
- `invitations.py`: `POST /admin/invitations` (`require_role(ADMIN)`), `POST /auth/redeem` (public).

## Build order
1. Scaffolding: `pyproject.toml`, `.env.example`, `config.py`, `core/supabase_client.py`, `core/logging.py`, `main.py` (health check). Verify server boots + connects.
2. `domain/roles.py` + `domain/schemas.py` + `core/security.py` + `api/deps.py` (+ unit tests).
3. Migrations `0001`–`0003`; apply to Supabase; register access-token hook.
4. `repositories/` + `services/auth_service.py` + `routers/auth.py` — SMS-OTP login end-to-end.
5. `services/invitation_service.py` + `routers/invitations.py` — invite create + redeem (link & code).
6. Update project docs (root `AGENTS.md`, `docs/CLAUDE.md`, `README.md`) to the new stack.

## Files created (representative)
`backend/app/core/supabase_client.py`, `backend/app/config.py`, `backend/app/core/security.py`,
`backend/app/domain/roles.py`, `backend/app/services/auth_service.py`,
`backend/app/services/invitation_service.py`, `backend/app/api/v1/routers/auth.py`,
`backend/app/api/v1/routers/invitations.py`, `backend/supabase/migrations/0001_init.sql`
(+`0002`,`0003`), `backend/pyproject.toml`, `backend/.env.example`, `backend/README.md`.
(The existing empty `backend/models/models.py` is removed; models live in `app/domain/`.)

## Verification
- **Boot:** `uvicorn app.main:app --reload` from `backend/`; `GET /health` returns ok and the
  Supabase util connects (a trivial `select` via service client).
- **Unit tests:** `pytest` — role hierarchy (`ADMIN` satisfies `RESIDENT`, `SECURITY` does not),
  invitation redeem states (valid/used/expired), token/code hashing round-trip. No network.
- **Login flow (dev):** configure a **test phone + fixed OTP** in Supabase Auth; `POST /auth/otp/request`
  then `/auth/otp/verify` returns a session; decode the JWT and confirm the `user_role` claim is present
  (proves the access-token hook works); unknown numbers are rejected (`should_create_user=false`).
- **RBAC:** call an admin-only route with a RESIDENT token → 403; with an ADMIN token → 200. Confirm
  a resident JWT can only read its own apartment rows (RLS) via a direct PostgREST query.
- **Invite flow:** `POST /admin/invitations` (admin token) returns link + code; redeem once via the
  **code** and once (fresh invite) via the **link token** → resident provisioned + session issued;
  second redeem of the same invite → rejected (single-use); expired invite → rejected.

## Follow-ups (noted, not in this build)
- Wire the frontend's amenities `services/*Service.js` and store slices to call these endpoints
  (they were intentionally written as a swappable API seam).
- Remaining domain tables (complaints+stages, amenities+multi-day bookings, visitors/passes,
  notices/policies, payments, staff/roster) — schema + RLS in a phase-2 migration set.
