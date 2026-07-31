# HomeBandhu API

FastAPI is the sole browser-facing authentication boundary. It implements
Google PKCE and email/password login, HTTP-only session and refresh cookies,
session context, CSRF protection, email-bound invitation activation, and founder onboarding.

Google OAuth is primary by default and Supabase email/password is the supported
secondary method. `AUTH_PRIMARY_METHOD` and `AUTH_ENABLED_METHODS` are
validated at startup so unsupported methods cannot accidentally appear in the
browser. A new verified identity without a membership continues through the
unified create-or-join registration workflow.

Set the values in `.env.example`, including `COOKIE_SIGNING_SECRET` and
`BACKEND_BASE_URL`, then run `uv run uvicorn app.main:app --reload`.

Use a fresh Supabase project with Google and Email enabled. Configure the backend
callback `https://<api-host>/api/v1/auth/google/callback`, asymmetric JWT signing
keys, private storage, and the email/Turnstile settings in
`docs/SUPABASE_AUTH_SETUP.md`.
