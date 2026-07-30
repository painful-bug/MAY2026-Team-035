# HomeBandhu

HomeBandhu is a residential-community platform with a React frontend, FastAPI
backend, and Supabase/Postgres persistence.

## Authentication

Google is the only sign-in provider. FastAPI owns the OAuth PKCE transaction,
HTTP-only session cookies, refresh rotation, CSRF validation, and tenant
authorization. The browser calls `/api/v1` only and has no Supabase client.
Invitations are opaque, single-use artifacts bound to the recipient's verified
Google email. Phone numbers are optional contact information.

## Local development

```bash
npm install
npm run dev
cd backend && uv run uvicorn app.main:app --reload
```

Copy `backend/.env.example` to `backend/.env`, use a fresh Supabase project,
apply `backend/supabase/migrations/0001_baseline.sql`, then configure Google
OAuth to redirect to `/api/v1/auth/google/callback` on the backend.
