# HomeBandhu Backend API

HomeBandhu's backend is a FastAPI backend-for-frontend over Supabase/Postgres.
The browser calls the backend through `/api/v1`; it does not connect directly to
Supabase or receive provider credentials.

The backend owns authentication transactions, HTTP-only access and refresh
cookies, CSRF protection, invitation activation, founder onboarding, tenant
authorization, API validation, and persistence. Google OAuth is the primary
authentication method by default, with verified Supabase email/password as an
optional secondary method.

## Requirements

- Python 3.10 or newer.
- `uv` 0.11.32 or newer, as required by `pyproject.toml`.
- A Supabase project for running persistent or authentication-dependent API
  workflows.

All Python packages are declared in `pyproject.toml` and locked in `uv.lock`.
Do not copy or reuse another machine's `.venv` directory.

## Install the backend

Run all commands in this README from the `backend` directory.

Install the runtime dependencies:

```bash
uv sync
```

To install the development dependencies used by pytest, Ruff, and the OpenAPI
exporter, use:

```bash
uv sync --extra dev
```

## Configure the environment

Create a local environment file from the supplied template:

```bash
cp .env.example .env
```

At minimum, replace these values in `.env`:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `COOKIE_SIGNING_SECRET`
- `BACKEND_BASE_URL`
- `FRONTEND_BASE_URL`
- `CORS_ORIGINS`

Generate a random cookie-signing secret instead of reusing a password or
provider key. For example:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Place the generated value in `COOKIE_SIGNING_SECRET`. Keep `.env` private and
never include it in source control or a submission archive. Submit
`.env.example` instead.

For a fresh Supabase project, apply the baseline migration in
`supabase/migrations/0001_baseline.sql`. Enable the authentication providers you
intend to use and configure the backend OAuth callback as:

```text
http://localhost:8000/api/v1/auth/google/callback
```

Use the deployed HTTPS backend origin instead of `localhost` in production.
The service-role key is backend-only and must never be exposed to a browser.

`SUPABASE_JWT_SECRET` is optional for legacy HS256 projects. New Supabase
projects should use asymmetric signing keys and the project's JWKS endpoint.

## Run only the backend

The React frontend is not required to start the API. Start FastAPI with:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify that the service is running:

```bash
curl http://127.0.0.1:8000/health
```

The expected response is similar to:

```json
{"status":"ok","env":"development"}
```

The generated API documentation is available while the server is running at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`
- `http://127.0.0.1:8000/openapi.json`

The server can start without the frontend, but browser-based OAuth completion,
invitation links, and other redirect flows require the configured frontend
origin to be reachable.

## Run the tests

The default automated tests do not require real Supabase credentials or a local
`.env`. They provide safe placeholder configuration and replace external service
calls at the test boundary. Tests under `tests/integration` remain skipped unless
their local-Supabase environment flag is enabled.

Install the development dependencies and run the complete test suite:

```bash
uv sync --extra dev
uv run --extra dev pytest
```

Run the API-focused tests only with:

```bash
uv run --extra dev pytest tests/api -vv
```

### Generate the test documentation

Ordinary pytest collection and test runs do not modify tracked documentation.
Regenerate `tests/README.md` and `tests/api/README.md` explicitly from the
collected test docstrings with:

```bash
uv run pytest --collect-only --generate-test-docs
```

Run this command from the `backend` directory and commit the generated README
changes only when the documented test inventory is intended to be refreshed.
