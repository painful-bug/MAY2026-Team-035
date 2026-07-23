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
supabase/migrations/        # SQL: schema (0001), RLS (0002), access-token hook (0003)
tests/                      # pytest — pure logic (roles, invite decision, hashing)
```

**The Supabase util (`app/core/supabase_client.py`) is the only place that
constructs a client.** It exposes three, by trust level:
- `get_anon_client()` — anon key, RLS with no user context.
- `get_service_client()` — service-role key, **bypasses RLS**; privileged ops only.
- `get_user_client(token)` — anon client carrying the caller's JWT, so **RLS runs
  as that user**. This is the default for request-scoped data access.

## Authentication & RBAC

Roles: `RESIDENT, MANAGER, TECHNICIAN, SECURITY, ADMIN` (ADMIN is also a
RESIDENT). The role lives on `profiles.role`, is injected into every access
token as a `user_role` claim by a Supabase **access-token hook**, and is enforced
in **three layers**: Postgres RLS, FastAPI `require_role(...)` guards, and the
verified `Principal`.

- **Login (existing members):** phone **SMS OTP** —
  `POST /api/v1/auth/otp/request` then `/api/v1/auth/otp/verify`. Unknown numbers
  can't self-signup (`should_create_user=false`). "Remember me" = the frontend
  persists the returned session; `POST /api/v1/auth/refresh` renews it.
- **Registration (new residents):** admin-initiated.
  `POST /api/v1/admin/invitations` (ADMIN only) returns a one-time **magic link**
  and a typable **code**. The resident redeems either one at
  `POST /api/v1/auth/redeem`, which provisions their Supabase user, sets their
  role, and returns a session. Only hashes of the token/code are stored.

## Setup

1. Create a Supabase project. Copy `.env.example` to `.env` and fill in the URL,
   anon key, service-role key, and JWT secret (Settings → API).
2. Apply migrations (`supabase db push`, or paste `supabase/migrations/*.sql`
   into the SQL editor in order).
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
