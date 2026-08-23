# HomeBandhu

HomeBandhu is a cooperative-housing and residential-community management
platform. It brings resident services, administration, maintenance operations,
amenity bookings, visitor access, security records, notices, and community
finance into one role-aware web application.

The application uses a React/Vite frontend, a FastAPI backend-for-frontend
(BFF), and Supabase/Postgres for authentication and authoritative persistence.

## Principal capabilities

- Resident onboarding through invitations and community access requests.
- Administrator and department management for residents, staff, services, and
  community settings.
- Complaint submission, routing, assignment, work orders, status history,
  service-level expectations, and resident-visible updates.
- Service-professional registration, community discovery, hiring, schedules,
  job actions, and conversations.
- Amenity catalogue, booking, approval, partial multi-day cancellation,
  maintenance blocks, charges, deposits, refunds, and reports.
- Visitor pre-approval, QR/code verification, gate operations, security shifts,
  incidents, material movements, tanker logs, offline reconciliation, and CSV
  reports.
- Notices, durable in-app notifications, optional Web Push, and tenant-scoped
  server-sent event refresh hints.
- Maintenance invoices and administrator-recorded offline payments. Resident
  and amenity payment screens use a clearly labelled simulator; no real payment
  gateway is connected.

## Architecture and security boundaries

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Frontend | React 19, Vite, React Router, TanStack Query, Zustand, Tailwind CSS | Role-specific interfaces and ephemeral render state |
| Backend | FastAPI, Pydantic, HTTPX, PyJWT | API contract, authentication transactions, validation, authorization, and orchestration |
| Persistence | Supabase Auth, Postgres, PostGIS, Storage | Identity, authoritative tenant data, constraints, RPCs, RLS, and migrations |
| Realtime | Postgres outbox, server-sent events, optional Web Push | Refresh hints and notification delivery |
| Verification | Pytest, Vitest, Playwright, Oxlint, Ruff, OpenAPI checks | Unit, API, contract, migration, integration, and browser testing |

The browser calls same-origin `/api/v1` routes only. It does not import the
Supabase SDK, receive provider credentials, or authorize tenant access.
FastAPI owns OAuth/password transactions, HTTP-only access and refresh cookies,
refresh rotation, CSRF validation, invitation activation, and database access.
Active `community_memberships` records determine community scope and roles;
browser-supplied roles and JWT role metadata are not trusted for tenant access.

Google OAuth is the primary configured authentication method. Verified
Supabase email/password authentication is supported as an optional secondary
method. Phone numbers are optional contact information and are never
credentials. Invitations are opaque, single-use records bound to the verified
email address of the account that redeems them.

## Repository layout

```text
MAY2026-Team-035/
|-- backend/
|   |-- app/                  # FastAPI application
|   |-- scripts/              # OpenAPI and repository checks
|   |-- supabase/             # Supabase configuration and SQL migrations
|   `-- tests/                # Pytest suites
|-- docs/                     # Architecture, API, design, and change records
|-- frontend/
|   |-- e2e/                  # Playwright browser tests
|   |-- public/               # Static assets
|   `-- src/                  # React application
|-- dev.sh                    # macOS/Linux development launcher
|-- dev.ps1                   # Windows PowerShell development launcher
|-- package.json              # npm workspace commands
`-- README.md
```

## Prerequisites

- Git.
- Node.js 22.13 or later and npm. Vite also supports Node 20.19 or later, but
  Node 22 is the version used by project CI.
- Python 3.10 or later.
- [uv](https://docs.astral.sh/uv/) for Python dependency and environment
  management. The checked lock file was produced with uv 0.11.32.
- One of the following database environments:
  - Docker Desktop and the Supabase CLI for the reproducible local stack; or
  - an authorized Supabase project whose migrations and Auth configuration
    have already been applied.

Docker is needed only for the local Supabase stack and database-backed tests;
it is not required when the application is connected to an already configured
Supabase project.

## Installation

Clone the repository and enter its root directory:

```bash
git clone https://github.com/painful-bug/MAY2026-Team-035
cd MAY2026-Team-035
```

Install the frontend, Supabase CLI, backend, and test dependencies:

```bash
npm ci
uv sync --project backend --extra dev --locked
```

`npm ci` uses the committed lock file and installs the root npm workspace,
including the React frontend and local Supabase CLI. `uv sync` uses
`backend/uv.lock` and creates or updates the backend environment.

## Database setup

### Option A: local Supabase with Docker (recommended for evaluation)

Run these commands from the repository root:

```bash
npx supabase start --workdir backend
npx supabase db reset --workdir backend
npx supabase status --workdir backend -o env
```

The reset applies every tracked migration in filename order to a clean local
database. Do not run Supabase from a different working directory or create a
second root-level `supabase/` directory; the project configuration and
migrations are under `backend/supabase/`.

The status command prints the local API URL and development credentials. Map
them into `backend/.env` as follows:

| `supabase status -o env` value | `backend/.env` variable |
| --- | --- |
| `API_URL` | `SUPABASE_URL` |
| `ANON_KEY` | `SUPABASE_ANON_KEY` |
| `SERVICE_ROLE_KEY` | `SUPABASE_SERVICE_ROLE_KEY` |
| `JWT_SECRET` | `SUPABASE_JWT_SECRET` |

For a local stack without Google OAuth, use email/password authentication and
disable confirmation consistently in the local backend:

```dotenv
AUTH_PRIMARY_METHOD=email_password
AUTH_ENABLED_METHODS=email_password
AUTH_EMAIL_CONFIRMATION_REQUIRED=false
```

The local Supabase configuration also disables email confirmation. Production
startup refuses that setting; hosted production must keep confirmation enabled.

Stop the local stack when it is no longer needed:

```bash
npx supabase stop --workdir backend
```

### Option B: an existing Supabase project

Use the project URL, anon key, and service-role key supplied through an
authorized channel. Do not commit these values. The target project must have
the repository migration chain, RLS policies, Auth providers, allowed redirect
URLs, and any required Postgres extensions configured already.

Migrations are forward-only. Never edit a migration recorded in a database's
history or run suggested migration-repair commands automatically. The linked
team project has an owner-controlled migration runbook; developers should not
push schema changes to it from this README workflow.

## Environment configuration

Create the backend environment file.

### macOS/Linux

```bash
cp backend/.env.example backend/.env
```

### Windows PowerShell

```powershell
Copy-Item backend/.env.example backend/.env
```

Fill in `backend/.env`. The important settings are:

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Supabase API origin |
| `SUPABASE_ANON_KEY` | Public project key used for user-scoped requests |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only privileged project key |
| `SUPABASE_JWT_SECRET` | Optional legacy/local HS256 verification secret; new asymmetric projects use JWKS |
| `COOKIE_SIGNING_SECRET` | Long random secret for OAuth, session, and CSRF transactions |
| `BACKEND_BASE_URL` | Backend origin; locally `http://localhost:8000` |
| `FRONTEND_BASE_URL` | Frontend origin; locally `http://localhost:5173` |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to call the BFF |
| `AUTH_PRIMARY_METHOD` | First authentication method shown by the application |
| `AUTH_ENABLED_METHODS` | Comma-separated subset of `google,email_password` |
| `AUTH_EMAIL_CONFIRMATION_REQUIRED` | Must be `true` in production |
| `COOKIE_SECURE` | `false` for local HTTP; `true` for production HTTPS |
| `ENV` | `development`, `testing`, or `production` |

Generate a suitable cookie-signing secret rather than reusing the example:

```bash
uv run --project backend python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The frontend requires no Supabase URL, provider secret, or API base URL. Vite
proxies `/api` to `http://localhost:8000` during local development. Copy
`frontend/.env.example` only if optional frontend settings are needed, such as
`VITE_TURNSTILE_SITE_KEY` after CAPTCHA has been configured in Supabase.

For hosted Google OAuth or production email/password configuration, follow
[`docs/SUPABASE_AUTH_SETUP.md`](docs/SUPABASE_AUTH_SETUP.md). The backend OAuth
callback is:

```text
<BACKEND_BASE_URL>/api/v1/auth/google/callback
```

Optional VAPID settings enable Web Push. Leaving them empty disables push and
does not prevent the rest of the application from running.

## Running the application

### macOS/Linux

From the repository root:

```bash
./dev.sh
```

Run only one service when required:

```bash
./dev.sh --frontend
./dev.sh --backend
```

### Windows PowerShell

From the repository root:

```powershell
.\dev.ps1
```

Run only one service when required:

```powershell
.\dev.ps1 -Frontend
.\dev.ps1 -Backend
```

If local PowerShell policy blocks the script, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\dev.ps1
```

### Manual two-terminal startup

Terminal 1 - frontend:

```bash
npm run dev
```

Terminal 2 - backend:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

The running services are available at:

| Service | URL |
| --- | --- |
| Frontend | `http://localhost:5173` |
| Backend | `http://127.0.0.1:8000` |
| Health check | `http://127.0.0.1:8000/health` |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| ReDoc | `http://127.0.0.1:8000/redoc` |

Press `Ctrl+C` in the launcher terminal to stop both development servers.

## Tests and quality checks

Run frontend tests, lint, and the production build from the repository root:

```bash
npm run test -w frontend
npm run lint
npm run build
```

Run backend checks from `backend/`:

```bash
cd backend
uv lock --check
uv run python -m compileall -q app
uv run pytest
uv run python scripts/export_openapi.py --check
uv run python scripts/api_map_scan.py --max-findings 20
```

Run the default Playwright browser suite from the repository root:

```bash
npx playwright install chromium
npm run test:e2e -w frontend
```

Database-backed integration and full-stack Playwright scenarios require a
reset local Supabase stack and opt-in environment variables. The complete,
credential-safe sequence used by CI is recorded in
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Production build

Create the frontend production bundle with:

```bash
npm run build
```

Vite writes the static output to `frontend/dist/`. The FastAPI application is
started from `backend/` with an ASGI server such as:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Production requires HTTPS, secure cookies, exact frontend/backend origins,
configured Auth redirect URLs, confirmed email delivery when password auth is
enabled, and server-side protection of the service-role key and other secrets.

## Troubleshooting

- **The backend fails during startup:** confirm that `backend/.env` exists and
  contains the required Supabase keys and a non-placeholder
  `COOKIE_SIGNING_SECRET`.
- **The database reports missing functions, tables, or columns:** run
  `npx supabase db reset --workdir backend` against the local stack. Do not run
  Supabase from the repository root without `--workdir backend`.
- **Google sign-in redirects incorrectly:** add the exact backend callback URL
  to Supabase Auth's allowed redirect URLs and ensure `BACKEND_BASE_URL` matches
  the browser-visible backend origin.
- **Email/password sign-in is rejected as unconfirmed:** make the Supabase
  project's confirmation setting and `AUTH_EMAIL_CONFIRMATION_REQUIRED` agree.
  Only local/test environments may disable confirmation.
- **Cookies, CSRF, or CORS fail:** use the same hostname consistently. For
  example, do not mix `localhost` and `127.0.0.1` between `FRONTEND_BASE_URL`,
  `BACKEND_BASE_URL`, `CORS_ORIGINS`, and the URL opened in the browser.
- **Web Push endpoints return `push_not_configured`:** configure the VAPID
  variables in `backend/.env`, or leave push disabled for local development.
- **A development port is already in use:** stop an earlier Vite/Uvicorn
  process or start the affected service on another port and update the related
  origin configuration.
