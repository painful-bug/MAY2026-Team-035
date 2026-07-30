# HomeBandhu contributor guide

HomeBandhu is a React/Vite frontend and FastAPI backend. The browser calls only
same-origin `/api/v1`; it never imports Supabase or stores provider tokens.

Authentication is Google-only. The backend owns PKCE, session and refresh
cookies, CSRF validation, invitation activation, and membership authorization.
An invitation is bound to one verified Google email. Phone numbers are optional
contact data, never credentials.

Use the root workspace commands:

```bash
npm install
npm run build
npm run lint
cd backend && python3 -m compileall -q app
```

Database development uses the single `backend/supabase/migrations/0001_baseline.sql`
baseline for a fresh Supabase project. Do not add one-time-code, password, magic-link,
identity-linking, demo-login, browser persistence, or direct browser-Supabase
paths. Tenant authorization must derive from active memberships, not JWT roles.
