# HomeBandhu contributor guide

HomeBandhu is a React/Vite frontend and FastAPI backend. The browser calls only
same-origin `/api/v1`; it never imports Supabase or stores provider tokens.

Authentication is provider-configured: Google OAuth is primary by default and
Supabase email/password is the secondary backup. The backend owns PKCE, session
and refresh cookies, CSRF validation, invitation activation, and membership
authorization. An invitation is bound to one authenticated account email. Phone numbers are optional
contact data, never credentials.

Use the root workspace commands:

```bash
npm install
npm run build
npm run lint
cd backend && python3 -m compileall -q app
```

Database development uses the single `backend/supabase/migrations/0001_baseline.sql`
baseline for a fresh Supabase project; compatibility migrations are forward-only
for the existing hosted project. Do not add OTP, magic-link login, demo-login,
browser persistence, or direct browser-Supabase paths. Tenant authorization must
derive from active memberships, not JWT roles.
