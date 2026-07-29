# HomeBandhu Backend

FastAPI service over [Supabase](https://supabase.com) (Postgres + Auth + Storage).
Supabase is the entire backend — database, authentication, and row-level
authorization. This service is a thin, typed API layer in front of it that the
React frontend calls.

## Layout

```
app/
  config.py                 # env-driven settings (cached)
  core/
    supabase_client.py      # ★ single entry point for ALL Supabase access
    security.py             # verifies Supabase JWTs -> Principal
    tokens.py               # invite token/code generation + hashing
    exceptions.py           # AppError hierarchy -> JSON responses
    logging.py
  domain/
    roles.py                # Role enum + RBAC hierarchy (ADMIN ⊇ RESIDENT)
    schemas.py              # Pydantic request/response DTOs
  repositories/             # data access — always via core/supabase_client
  services/                 # business logic (auth, invitations)
  api/
    deps.py                 # get_current_user, require_role(...), get_request_client
    v1/routers/             # auth.py, invitations.py
supabase/migrations/        # SQL: baseline (0001-0003), domain (0004), tenant RLS/workflows (0005)
tests/                      # pytest — pure logic (roles, invite decision, hashing)
```

**The Supabase util (`app/core/supabase_client.py`) is the only place that
constructs a client.** It exposes three, by trust level:
- `get_anon_client()` — anon key, RLS with no user context.
- `get_service_client()` — service-role key, **bypasses RLS**; privileged ops only.
- `get_user_client(token)` — anon client carrying the caller's JWT, so **RLS runs
  as that user**. This is the default for request-scoped data access.

## Authentication & RBAC

Roles: `RESIDENT, WORKER, SECURITY, MANAGER, ADMIN` (ADMIN is also a
RESIDENT). Identity lives in `profiles`; tenant roles and residency live in
`community_memberships` and `unit_residencies`. The access-token hook supplies
a coarse `user_role` claim for FastAPI guards, while Postgres RLS always checks
the caller's active membership in the target community.

- **Login (existing members):** phone **SMS OTP** —
  `POST /api/v1/auth/otp/request` then `/api/v1/auth/otp/verify`. Unknown numbers
  can't self-signup (`should_create_user=false`). "Remember me" = the frontend
  persists the returned session; `POST /api/v1/auth/refresh` renews it.
- **Registration (new residents):** admin-initiated.
  `POST /api/v1/admin/invitations` requires a `community_id` and
  `intended_unit_id`, then returns a one-time **magic link** and a typable
  **code**. The resident redeems either at `POST /api/v1/auth/redeem`; the
  database atomically creates their resident membership and unit residency.
  Only hashes of the token/code are stored.

The database also provides trusted SQL workflows for single-admin transfer,
resident-invite claiming, and approval of self-service access requests with a
default maintenance invoice. Browser clients cannot mutate membership, admin,
or financial rows directly.

## Setup

1. Create a Supabase project. Copy `.env.example` to `.env` and fill in the URL,
   anon key, service-role key, and JWT secret (Settings → API).
2. Apply migrations in filename order with `supabase db push`. Migrations
   `0004` and `0005` are forward-only: they rename the original association
   tables to the canonical community/building/unit names and retain
   `profiles.legacy_*` values until the post-deployment backfill audit passes.
   Existing users must refresh their session after `0005`, so its updated
   membership-derived access-token claim is issued.
3. Register the access-token hook: **Authentication → Hooks → Customize Access
   Token** → `public.custom_access_token_hook`.
4. Configure an **SMS provider** under Authentication → Providers → Phone
   (MSG91/Twilio/Vonage). For local dev, add **test phone numbers with fixed
   OTPs** so no real SMS is sent.

## Run

```bash
python -m venv .venv
.venv/Scripts/activate           # Windows;  source .venv/bin/activate on Unix
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

- Health check: `GET http://localhost:8000/health`
- Interactive API docs: `http://localhost:8000/docs`

## Test & lint

```bash
pytest          # unit tests (no network)
ruff check .    # lint
```
