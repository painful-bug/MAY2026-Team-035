# HomeBandhu API reference and Postman test guide

This document describes the **currently implemented FastAPI HTTP surface**.
It is intentionally limited to routes registered by `backend/app/main.py` and
`backend/app/api/v1/`: seven application endpoints plus the health probe.
The PostgreSQL workflows in the Supabase migrations (for example,
`transfer_community_admin`) are database RPCs, not public FastAPI endpoints;
they are therefore not listed as REST endpoints below.

## 1. API at a glance

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | None | Liveness and environment check. |
| `POST` | `/api/v1/auth/otp/request` | None | Ask Supabase to send an SMS login OTP for an existing member. |
| `POST` | `/api/v1/auth/otp/verify` | None | Verify an SMS OTP and receive a Supabase session. |
| `POST` | `/api/v1/auth/refresh` | None | Exchange a refresh token for a new session. |
| `GET` | `/api/v1/auth/me` | Bearer access token | Read the authenticated caller's identity profile. |
| `POST` | `/api/v1/admin/invitations` | Bearer access token; active admin of the supplied community | Create a one-time resident invitation. |
| `POST` | `/api/v1/auth/redeem` | None | Redeem an invitation link token or typed code, create the resident account, and receive a session. |

Default interactive documentation is also available while the service is
running:

- `GET /docs` — Swagger UI
- `GET /redoc` — ReDoc UI
- `GET /openapi.json` — machine-readable OpenAPI contract

The API currently has no HTTP routes for complaints, visitors, bookings,
payments, staff assignments, community administration, or access-request
approval. Their database schema/RLS groundwork exists, but client-facing
routes must be added before they can be called through this API.

## 2. Conventions

### Base URL and content type

For local development, use:

```text
http://127.0.0.1:8000
```

All request bodies in this guide are JSON. Set this header on JSON requests:

```http
Content-Type: application/json
```

For protected routes, also set:

```http
Authorization: Bearer <Supabase access token>
```

`access_token` and `refresh_token` are credentials. Do not commit them to a
Postman collection, export them in screenshots, or send them to chat.

### Types and formats

| Value | Format / meaning |
| --- | --- |
| `community_id`, `intended_unit_id`, `invitation_id`, `user_id` | UUID string from Supabase/Postgres. The request schema accepts strings; the database supplies the UUID-level integrity checks. |
| `phone` | Expected as an E.164 number, for example `+919876543210`. The current request schema accepts a string, so clients must normalize it and use the exact same value at invitation and redemption. |
| `token` | Long opaque value from the `/join/<token>` part of an invitation link. It is single-use. |
| `code` | Short human-entered invitation code. It is single-use and case/format normalization is handled by the service. |
| `expires_at` | ISO-8601 timestamp with timezone, for example `2026-07-26T10:30:00+00:00`. |
| `expires_at` in `Session` | Unix timestamp in seconds, or `null` if Supabase did not return one. |
| `role` | One of `RESIDENT`, `WORKER`, `SECURITY`, `MANAGER`, `ADMIN`, or `null` where the auth provider did not expose it in the returned user metadata. API authorization always uses the verified JWT claim, not this response field. |

### Error contract

Expected domain errors use one stable envelope:

```json
{
  "error": {
    "code": "invite_expired",
    "message": "This invite has expired."
  }
}
```

| HTTP status | When it occurs | Typical codes |
| --- | --- | --- |
| `401` | Missing, invalid, expired, or role-less bearer token; invalid/expired SMS OTP; refresh failure. | `authentication_error`, `token_expired`, `missing_role_claim` |
| `403` | Caller is authenticated but is not an `ADMIN` for the route, or is not the active admin of the requested community. | `insufficient_role`, `authorization_error` |
| `404` | Requested record is not available in the caller's RLS scope. | `not_found` |
| `409` | Invite was consumed, or an Auth user already exists for the invited phone. | `invite_used`, `user_exists`, `conflict` |
| `422` | Business-rule validation failure. | `validation_error`, `invite_invalid`, `invite_expired` |

FastAPI/Pydantic malformed-body validation also returns `422`, but with its
standard `detail` array rather than the envelope above. For example, omitting
`phone` produces a response shaped like:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "phone"],
      "msg": "Field required"
    }
  ]
}
```

## 3. Complete Supabase and backend setup

Follow this section once for a new **development** Supabase project. Use a
separate test project from production: invitation redemption creates real Auth
users and consumes one-time credentials.

### 3.1 Create the Supabase project

1. In the [Supabase Dashboard](https://supabase.com/dashboard), create a new
   project and record its project reference (the subdomain in
   `https://<project-ref>.supabase.co`).
2. In **Settings → API Keys** (or the project **Connect** dialog), copy:
   - Project URL;
   - a **Publishable** key (`sb_publishable_...`) or legacy `anon` key; and
   - a **Secret** key (`sb_secret_...`) or legacy `service_role` key.
3. In the project's JWT settings, copy the legacy HMAC JWT secret used to sign
   user access tokens.

The backend variable names retain the earlier terminology:

| Backend setting | Current Supabase value to use | Handling rule |
| --- | --- | --- |
| `SUPABASE_URL` | Project URL | Safe to store in local `.env`; it identifies the project. |
| `SUPABASE_ANON_KEY` | Publishable key, or legacy anon key | Used by the backend's normal/RLS-scoped clients. It is not a user credential. |
| `SUPABASE_SERVICE_ROLE_KEY` | Secret key, or legacy service-role key | Server-only. It creates Auth users and bypasses RLS. Never put it in the frontend or Postman. |
| `SUPABASE_JWT_SECRET` | HMAC JWT secret | Server-only. The current FastAPI verifier explicitly uses `HS256`. Do not switch the project to asymmetric-only signing until the verifier is changed to validate against Supabase JWKS. |

Supabase is migrating from legacy `anon`/`service_role` JWT keys to
publishable/secret API keys. Both types can coexist, but secret keys must stay
on a developer-controlled server and must never be committed or exposed in a
browser. See the official [API key guidance](https://supabase.com/docs/guides/getting-started/api-keys).

### 3.2 Install local tooling and dependencies

From the repository root:

```bash
# Node/npm is required for the Vite frontend.
npm install

# Install uv if it is not already installed, then resolve the Python project.
# macOS/Homebrew option: brew install uv
cd backend
uv sync --extra dev
cd ..
```

Install the Supabase CLI using **one** of these supported options:

```bash
# Option A — macOS global command through Homebrew.
brew install supabase/tap/supabase
supabase --version
```

```bash
# Option B — project-local CLI. Requires Node.js 20+.
# Run every CLI command below as `npx supabase <command>`.
npm install --save-dev supabase
npx supabase --version
```

Do not use `npm install -g supabase`; Supabase does not support a global npm
installation. If Option B is used, replace every later `supabase ...` command
in this guide with `npx supabase ...`.

The repository intentionally keeps migrations under `backend/supabase/`. If
this is the first CLI use in this checkout, initialize that directory; this
creates the CLI configuration without replacing the existing migration files:

```bash
cd backend
supabase init
```

Do not run `supabase db reset --linked` against a shared or production
database: that command is destructive. Use a new development project for this
guide.

### 3.3 Apply the database migrations

From `backend/`, authenticate and link only to the development project:

```bash
supabase login
supabase link --project-ref <your-project-ref>
supabase db push --dry-run
supabase db push
supabase migration list
```

`db push` records applied migration versions in
`supabase_migrations.schema_migrations` and skips them on later runs. Apply
`0001_init.sql` through `0005_tenant_rls_and_workflows.sql` as one ordered set;
do not paste individual schema migrations into the dashboard SQL editor.

If `db push` reports divergent migration history, stop and inspect it with
`supabase migration list`. Do not run `migration repair` unless the actual
database state is understood: it changes migration history only, not schema.
Supabase's [migration deployment guide](https://supabase.com/docs/guides/deployment/database-migrations)
explains the linked-project workflow and recovery options.

### 3.4 Enable Phone/SMS authentication

The implemented login API uses phone SMS OTP only:

```text
POST /api/v1/auth/otp/request
POST /api/v1/auth/otp/verify
```

In the hosted Supabase Dashboard:

1. Open **Authentication → Providers** and enable **Phone**.
2. Configure one supported SMS provider (for example Twilio, Vonage, or
   MessageBird) with development credentials and a sender approved for the
   countries being tested.
3. Review SMS rate limits before repeatedly testing. Supabase documents a
   default request interval and OTP lifetime; wait for the provider's code
   rather than repeatedly sending requests.
4. For India, make sure the provider/template configuration meets TRAI/DLT
   requirements before sending real SMS.

The backend passes `should_create_user=false` when sending an OTP. Thus a
random phone cannot create an account by calling the login endpoint; the first
admin is bootstrapped below and residents are created only by invitation
redemption. Supabase's [Phone Login guide](https://supabase.com/docs/guides/auth/phone-login)
has the provider-specific configuration details.

For local Supabase CLI development, `auth.sms.test_otp` supports fixed test
codes. That option belongs to a local Supabase `config.toml`, not this
repository's `backend/.env`; use it only for a local stack and remove test
credentials from any deployed environment.

### 3.5 Register the custom access-token hook

After migrations finish, register the database function
`public.custom_access_token_hook` in the Supabase Dashboard:

1. Open **Authentication → Hooks**.
2. For **Customize Access Token**, select the Postgres function
   `public.custom_access_token_hook` and save it.
3. Sign out and sign in again after enabling the hook. Existing access tokens
   do not gain a newly added claim.

The hook inserts a coarse uppercase `user_role` claim based on the caller's
active membership. FastAPI uses that claim for route guards; Postgres RLS still
evaluates the caller's active membership in the target community. If the hook
is missing, protected API calls fail with `401` and
`error.code = "missing_role_claim"`.

### 3.6 Create `backend/.env`

From the repository root, create a local file at `backend/.env` by copying
`backend/.env.example`. Fill it with real development values only:

```dotenv
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<publishable-or-legacy-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<secret-or-legacy-service-role-key>
SUPABASE_JWT_SECRET=<legacy-hs256-jwt-secret>

FRONTEND_BASE_URL=http://localhost:5173
INVITE_TTL_HOURS=72
CORS_ORIGINS=http://localhost:5173
ENV=development
```

Important configuration rules:

- `backend/.env` is loaded relative to the backend working directory. Use
  `./dev.sh --backend` or `cd backend && uv run uvicorn app.main:app --reload`;
  starting Uvicorn from the repository root will not automatically discover
  `backend/.env`.
- `FRONTEND_BASE_URL` controls the returned invitation link only. For Postman,
  redemption can use the returned code, so a running frontend is not required.
- `CORS_ORIGINS` is a comma-separated allowlist for browsers. Postman is not
  subject to CORS, but the Vite origin must be present for frontend testing.
- Never add this `.env` file, Postman environment values, or a service/secret
  key to Git.

### 3.7 Bootstrap the first community admin and test unit

This is required once per fresh project. There is deliberately no unauthenticated
"make me admin" endpoint, and the API cannot create the first community/admin
on its own.

1. In **Authentication → Users**, create a development-only user with the
   desired admin phone in E.164 form (for example `+919876543210`). Mark the
   phone confirmed if the dashboard offers that option. The `on_auth_user_created`
   trigger creates the matching `public.profiles` row.
2. In the SQL Editor, verify that the profile exists:

   ```sql
   select id, phone_e164, full_name
   from public.profiles
   where phone_e164 = '+919876543210';
   ```

3. Run the following **development seed data** statement in the SQL Editor.
   Replace the three marked literals before running it. It creates one
   community, one building, one unit, the active admin membership, and the
   required active admin term. It returns the two UUIDs needed in Postman.

   ```sql
   with
   chosen_admin as (
     select id
     from public.profiles
     where phone_e164 = '+919876543210' -- replace admin phone
   ),
   new_community as (
     insert into public.communities (name, community_type, status, city, state)
     values ('Postman Test Community', 'apartment', 'Active', 'Kolkata', 'West Bengal')
     returning id
   ),
   new_building as (
     insert into public.buildings (community_id, name, building_type, code)
     select id, 'Block A', 'block', 'A'
     from new_community
     returning id, community_id
   ),
   new_unit as (
     insert into public.units (
       community_id, building_id, unit_code, unit_type, floor_number, status
     )
     select community_id, id, 'A-101', 'flat', '1', 'active'
     from new_building
     returning id, community_id
   ),
   new_membership as (
     insert into public.community_memberships (
       community_id, profile_id, role, status, joined_at, is_default_community
     )
     select c.id, a.id, 'admin', 'active', now(), true
     from new_community c
     cross join chosen_admin a
     returning id, community_id
   ),
   new_term as (
     insert into public.community_admin_terms (
       community_id, admin_membership_id, role_before_term, started_at
     )
     select community_id, id, 'resident', now()
     from new_membership
   )
   select c.id as community_id, u.id as unit_id
   from new_community c
   cross join new_unit u;
   ```

4. Copy the returned UUIDs into Postman as `community_id` and `unit_id`.
5. Request and verify a **new** admin OTP after the membership exists. The new
   session's JWT must contain `user_role: "ADMIN"`; old tokens still carry the
   role from when they were issued.

This bootstrap SQL is data-only and suitable for an isolated test project. Do
not run it repeatedly with the same phone/community: the schema enforces one
active membership per community and one active admin term per community.

### 3.8 Start and verify the backend

From the repository root:

```bash
./dev.sh --backend
```

In a second terminal, verify it before opening Postman:

```bash
curl --fail http://127.0.0.1:8000/health
# Expected: {"status":"ok","env":"development"}
```

Then open `http://127.0.0.1:8000/docs`. If startup fails, first verify the
four required `SUPABASE_*` settings in `backend/.env`; do not print their
values to the terminal, screenshots, or issue tracker.

## 4. Complete Postman setup

### 4.1 Create a collection from the running API

1. Start the backend and confirm `GET /health` returns `200`.
2. In Postman, create a workspace named `HomeBandhu development`.
3. Select **Import → Link** and enter:

   ```text
   http://127.0.0.1:8000/openapi.json
   ```

   This imports the current request paths and schema descriptions from FastAPI.
   It does not create environment variables or test scripts; add those below.
4. Rename the imported collection to `HomeBandhu API - local`.
5. In the collection's **Authorization** tab, choose **No Auth**. Do not place
   an admin bearer token at collection level: several routes are intentionally
   public, and an inherited token can hide authorization mistakes.

If the import fails, open `http://127.0.0.1:8000/docs` first. A non-`200`
OpenAPI response means the backend must be fixed before testing individual
routes.

### 4.2 Create the environment and protect its secrets

Create an environment named `HomeBandhu local`, select it in the upper-right
environment selector, then add these variables. Put values only in **Current
value** for credentials so an exported collection/environment does not include
them. Keep **Initial value** blank for all tokens, OTPs, invite codes, and
refresh tokens.

| Variable | Initial value | How it is used |
| --- | --- | --- |
| `base_url` | `http://127.0.0.1:8000` | API host and port. |
| `admin_phone` | A provisioned admin E.164 number | OTP login and protected admin call. |
| `admin_otp` | OTP received by SMS/test provider | Admin OTP verification. Do not persist a real value. |
| `community_id` | UUID | Community administered by `admin_phone`. |
| `unit_id` | UUID | Existing unit in `community_id`. |
| `resident_phone` | New E.164 number | Phone to invite and redeem. |
| `resident_otp` | OTP received after redemption | Optional resident OTP test. |
| `admin_access_token` | *(set by test script)* | Admin protected calls. |
| `admin_refresh_token` | *(set by test script)* | Admin refresh test. |
| `resident_access_token` | *(set by test script)* | Resident `/me` test. |
| `resident_refresh_token` | *(set by test script)* | Resident refresh test. |
| `invitation_id` | *(set by test script)* | Trace the invite that was created. |
| `invite_code` | *(set by test script)* | Invitation redemption. Treat as a secret. |

For the first run, set only these Current values yourself:

```text
base_url       = http://127.0.0.1:8000
admin_phone    = +<your development admin number>
community_id   = <community_id returned by bootstrap SQL>
unit_id        = <unit_id returned by bootstrap SQL>
resident_phone = +<unused test phone number>
```

Leave OTP, session, invitation, and refresh variables empty. The normal
requests populate them. Use a new `resident_phone` for each clean invitation
run because an invitation can be redeemed only once and the endpoint then
creates an Auth user for that phone.

### 4.3 Build requests consistently

For every JSON request:

1. Set **Body → raw → JSON**.
2. Set the `Content-Type: application/json` header. Postman usually adds it
   automatically when JSON is selected; verify it rather than relying on it.
3. For protected requests only, use **Authorization → Bearer Token** and set
   the token field to `{{admin_access_token}}` or
   `{{resident_access_token}}` as specified by the endpoint. This sends the
   exact header `Authorization: Bearer <token>`.
4. Open **Scripts → Post-response** (called **Tests** in older Postman UI) and
   paste the endpoint-specific assertion script from this guide.
5. Click **Save** after each request so the collection can be rerun in order.

Recommended collection folders:

```text
00 - System
  GET Health
  GET OpenAPI
10 - Admin session
  POST Request admin OTP
  POST Verify admin OTP
  GET Admin profile
  POST Refresh admin session
20 - Admin actions
  POST Create resident invitation
30 - Resident onboarding
  POST Redeem invitation by code
  POST Reuse invitation (expected 409)
40 - Resident session
  GET Resident profile
  POST Request resident OTP
  POST Verify resident OTP
  POST Refresh resident session
90 - Negative and security checks
  GET Profile without token (expected 401)
  POST Create invitation with resident token (expected 403)
```

Use request-level Authorization for the two profile requests so each test is
explicit about which role it exercises. The app's only role implication is
that `ADMIN` satisfies a resident requirement; staff roles do not imply one
another.

### 4.4 Work with OTPs, sessions, and invitation secrets

- Send the OTP request once, then immediately copy the SMS/test code into the
  matching `admin_otp` or `resident_otp` Current value and run verification.
  Do not keep sending OTPs: earlier codes can become invalid and the provider
  can rate-limit the number.
- An access token is short-lived. When `/auth/me` returns `401 token_expired`,
  run the corresponding refresh request and let its script replace both stored
  tokens.
- The invitation creation response is the only time the plaintext `code` and
  link token are available. Its script stores the code temporarily in
  `invite_code`; clear it after testing.
- Never use `SUPABASE_SERVICE_ROLE_KEY` as a Postman bearer token. It bypasses
  RLS and is not a substitute for a user access token.

Use `{{base_url}}` and the other variables exactly as written in request URLs,
headers, and bodies below. In Postman, select **Body → raw → JSON** for all
request bodies.

Useful reusable Postman test snippets:

**Response is JSON and successful**

```javascript
pm.test("success", function () {
  pm.expect(pm.response.code).to.be.within(200, 299);
  pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json");
});
```

**Save an admin session**

```javascript
const body = pm.response.json();
pm.environment.set("admin_access_token", body.access_token);
pm.environment.set("admin_refresh_token", body.refresh_token);
pm.test("admin session contains tokens", () => {
  pm.expect(body.access_token).to.be.a("string").and.not.empty;
  pm.expect(body.refresh_token).to.be.a("string").and.not.empty;
});
```

**Save a resident session**

```javascript
const body = pm.response.json();
pm.environment.set("resident_access_token", body.access_token);
pm.environment.set("resident_refresh_token", body.refresh_token);
pm.test("resident session contains tokens", () => {
  pm.expect(body.user_id).to.be.a("string").and.not.empty;
  pm.expect(body.access_token).to.be.a("string").and.not.empty;
});
```

## 5. Endpoint reference and Postman tests

### 5.0 FastAPI documentation routes

These framework-provided GET routes require no body or authentication. They do
not execute business workflows, but are useful contract checks in Postman.

| Method and path | Functionality | Success output | Postman assertion |
| --- | --- | --- | --- |
| `GET /openapi.json` | Returns the generated OpenAPI 3 contract for the app routes. | `200` JSON with `info.title = "HomeBandhu API"`, `info.version = "0.1.0"`, and the documented paths. | `pm.response.to.have.status(200); pm.expect(pm.response.json().paths).to.have.property("/api/v1/auth/me");` |
| `GET /docs` | Serves Swagger UI, backed by the OpenAPI contract. | `200` HTML. | `pm.response.to.have.status(200); pm.expect(pm.response.headers.get("Content-Type")).to.include("text/html");` |
| `GET /redoc` | Serves ReDoc, backed by the OpenAPI contract. | `200` HTML. | `pm.response.to.have.status(200); pm.expect(pm.response.headers.get("Content-Type")).to.include("text/html");` |
| `GET /docs/oauth2-redirect` | Internal Swagger UI OAuth callback page generated by FastAPI. It has no application input. | `200` HTML. | `pm.response.to.have.status(200);` |

### 5.1 `GET /health`

**Functionality:** liveness probe. It does not contact Supabase and requires
no credentials.

**Request**

```http
GET {{base_url}}/health
```

**Success response — `200 OK`**

```json
{
  "status": "ok",
  "env": "development"
}
```

`env` is the backend `ENV` setting and can be `development`, `production`, or
another configured string.

**Postman test**

```javascript
pm.test("health check is healthy", () => {
  pm.response.to.have.status(200);
  const body = pm.response.json();
  pm.expect(body.status).to.eql("ok");
  pm.expect(body.env).to.be.a("string");
});
```

### 5.2 `POST /api/v1/auth/otp/request`

**Functionality:** asks Supabase to send an SMS login OTP for an already
provisioned member. The service deliberately uses
`should_create_user=false`, so this endpoint cannot self-register an unknown
phone number. Its response is deliberately non-enumerating: the same success
message is returned without confirming whether the phone exists.

**Request body**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `phone` | string | Yes | Existing member phone in E.164 format. |

```http
POST {{base_url}}/api/v1/auth/otp/request
Content-Type: application/json

{
  "phone": "{{admin_phone}}"
}
```

**Success response — `200 OK`**

```json
{
  "message": "If the number is registered, a code has been sent."
}
```

**Postman test**

```javascript
pm.test("OTP request acknowledged", () => {
  pm.response.to.have.status(200);
  pm.expect(pm.response.json().message)
    .to.eql("If the number is registered, a code has been sent.");
});
```

To test the resident flow later, repeat this request with `{{resident_phone}}`
only **after** that invitation has been redeemed.

### 5.3 `POST /api/v1/auth/otp/verify`

**Functionality:** verifies the one-time SMS code and returns a Supabase
session. The API verifies the code only; route authorization for subsequent
requests comes from the returned access token's signed `user_role` claim.

**Request body**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `phone` | string | Yes | Same E.164 phone used to request the OTP. |
| `token` | string | Yes | SMS OTP, usually six digits. |

```http
POST {{base_url}}/api/v1/auth/otp/verify
Content-Type: application/json

{
  "phone": "{{admin_phone}}",
  "token": "{{admin_otp}}"
}
```

**Success response — `200 OK`**

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "v1...",
  "token_type": "bearer",
  "expires_at": 1784870400,
  "user_id": "c0d00000-0000-4000-8000-000000000001",
  "role": "ADMIN"
}
```

`role` is nullable in the wire contract. Clients must use the access token for
authorization and must not grant UI/API access based solely on a missing or
present response role.

**Expected failure — `401 Unauthorized`**

```json
{
  "error": {
    "code": "authentication_error",
    "message": "Invalid or expired code."
  }
}
```

**Postman test** — add the reusable **Save an admin session** script from
section 4, then add:

```javascript
pm.test("admin OTP is verified", () => {
  pm.response.to.have.status(200);
  pm.expect(pm.response.json().token_type).to.eql("bearer");
});
```

For an invited resident, send the same request with `{{resident_phone}}` and
`{{resident_otp}}`, and replace the save script with **Save a resident
session**.

### 5.4 `POST /api/v1/auth/refresh`

**Functionality:** exchanges a valid Supabase refresh token for a fresh
session. Use it as the "remember me" renewal path, not as an authorization
mechanism by itself.

**Request body**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `refresh_token` | string | Yes | Refresh token returned by OTP verification or invitation redemption. |

```http
POST {{base_url}}/api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "{{admin_refresh_token}}"
}
```

**Success response — `200 OK`**

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "v1...",
  "token_type": "bearer",
  "expires_at": 1784874000,
  "user_id": "c0d00000-0000-4000-8000-000000000001",
  "role": "ADMIN"
}
```

Store both returned tokens again: Supabase may rotate a refresh token.

**Expected failure — `401 Unauthorized`**

```json
{
  "error": {
    "code": "authentication_error",
    "message": "Could not refresh the session."
  }
}
```

**Postman test**

```javascript
const body = pm.response.json();
pm.test("admin session is refreshed", () => {
  pm.response.to.have.status(200);
  pm.expect(body.access_token).to.be.a("string").and.not.empty;
  pm.expect(body.refresh_token).to.be.a("string").and.not.empty;
});
pm.environment.set("admin_access_token", body.access_token);
pm.environment.set("admin_refresh_token", body.refresh_token);
```

Repeat with `{{resident_refresh_token}}` and save to the resident variables to
test a resident session.

### 5.5 `GET /api/v1/auth/me`

**Functionality:** reads the caller's identity profile through a Supabase
client scoped to the caller's bearer token. This endpoint returns identity
only; community memberships, role assignments, and unit residency are not
embedded in a profile.

**Required header**

```http
Authorization: Bearer {{admin_access_token}}
```

**Request**

```http
GET {{base_url}}/api/v1/auth/me
Authorization: Bearer {{admin_access_token}}
```

**Success response — `200 OK`**

```json
{
  "id": "c0d00000-0000-4000-8000-000000000001",
  "full_name": "Community Admin",
  "phone": "+919876543210",
  "email": "admin@example.test",
  "is_active": true
}
```

All fields except `id` and `is_active` may be `null`.

**Expected failure — `401 Unauthorized`** (missing header)

```json
{
  "error": {
    "code": "authentication_error",
    "message": "Missing bearer token."
  }
}
```

**Postman test**

```javascript
pm.test("authenticated caller can read own profile", () => {
  pm.response.to.have.status(200);
  const body = pm.response.json();
  pm.expect(body.id).to.be.a("string").and.not.empty;
  pm.expect(body.is_active).to.be.a("boolean");
});
```

Change the header to `Bearer {{resident_access_token}}` to verify the same
identity-only response under a resident's RLS scope.

### 5.6 `POST /api/v1/admin/invitations`

**Functionality:** lets the active `ADMIN` of a concrete community invite one
resident phone number to one concrete unit. The API creates a `resident_invites`
row through its privileged server-side client, persists only hashes of the
link token and code, and returns the plaintext link and code **once**. The
caller must pass both checks:

1. their signed JWT must carry `user_role=ADMIN`; and
2. their active `community_memberships` record must be `ADMIN` for the
   supplied `community_id`.

The membership check stops a caller from selecting a `community_id` that they
do not administer. **Current limitation:** the endpoint/database does not yet
assert that `intended_unit_id` belongs to that same `community_id`; it checks
only that the unit exists. Always use a unit from the selected community in
Postman, and add a database/API invariant before production use.

**Required header**

```http
Authorization: Bearer {{admin_access_token}}
```

**Request body**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `community_id` | UUID string | Yes | Community the admin manages. |
| `intended_unit_id` | UUID string | Yes | Existing unit the new resident will occupy. |
| `phone` | string | Yes | New resident's E.164 phone number. |
| `full_name` | string or `null` | No | Invited resident's display name. |
| `email` | string or `null` | No | Invited resident's email address. |

```http
POST {{base_url}}/api/v1/admin/invitations
Authorization: Bearer {{admin_access_token}}
Content-Type: application/json

{
  "community_id": "{{community_id}}",
  "intended_unit_id": "{{unit_id}}",
  "phone": "{{resident_phone}}",
  "full_name": "Ananya Resident",
  "email": "ananya@example.test"
}
```

**Success response — `200 OK`**

```json
{
  "invitation_id": "d0d00000-0000-4000-8000-000000000002",
  "link": "http://localhost:5173/join/<opaque-token>",
  "code": "AB12CD34",
  "phone": "+919812345678",
  "community_id": "a0d00000-0000-4000-8000-000000000003",
  "intended_unit_id": "b0d00000-0000-4000-8000-000000000004",
  "expires_at": "2026-07-26T10:30:00+00:00"
}
```

The returned `link` and `code` are delivery secrets. Show/deliver them to the
resident exactly once, then clear them from the Postman environment after the
test.

**Expected failures**

- `401` — no or invalid admin token.
- `403` — token is for a non-admin role, or the caller is not an active admin
  of `community_id`.
- `422` — malformed request body or a business validation error from the
  backing service/database.

**Postman test**

```javascript
const body = pm.response.json();
pm.test("admin creates a one-time resident invite", () => {
  pm.response.to.have.status(200);
  pm.expect(body.invitation_id).to.be.a("string").and.not.empty;
  pm.expect(body.code).to.be.a("string").and.not.empty;
  pm.expect(body.link).to.include("/join/");
  pm.expect(body.phone).to.eql(pm.environment.get("resident_phone"));
  pm.expect(body.community_id).to.eql(pm.environment.get("community_id"));
  pm.expect(body.intended_unit_id).to.eql(pm.environment.get("unit_id"));
});
pm.environment.set("invitation_id", body.invitation_id);
pm.environment.set("invite_code", body.code);
```

**Negative Postman tests**

1. Send the request with a resident token. Expect `403` and
   `error.code = "insufficient_role"`.
2. Keep the admin token but replace `community_id` with a different community.
   Expect `403` or a record-scope failure; the invitation must not be created.
3. Remove `intended_unit_id`. Expect FastAPI `422` with a `detail` array.
4. Do **not** use a valid unit from a different community as a negative test:
   this is a known missing invariant, so it may create an inconsistent invite.

### 5.7 `POST /api/v1/auth/redeem`

**Functionality:** public onboarding endpoint for a resident invited by an
admin. It validates the single-use invitation, verifies the supplied phone
matches the invitation, provisions the Supabase Auth user, ensures the
identity profile exists, then calls the transactional database claim workflow.
That workflow consumes the invitation and creates the resident membership and
unit residency together. The endpoint logs the resident in immediately and
returns a session; later logins use SMS OTP.

Send **exactly one** of `token` or `code`. If both are supplied, the current
implementation resolves by `token` first, so clients should never rely on a
code being considered in that case.

**Request body**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `phone` | string | Yes | Must exactly match the invited E.164 phone. |
| `token` | string or `null` | Conditional | Opaque value from the `/join/<token>` invitation link. |
| `code` | string or `null` | Conditional | Typed invitation code returned when the invite was created. |

**Code redemption request**

```http
POST {{base_url}}/api/v1/auth/redeem
Content-Type: application/json

{
  "phone": "{{resident_phone}}",
  "code": "{{invite_code}}"
}
```

**Link-token redemption request**

```http
POST {{base_url}}/api/v1/auth/redeem
Content-Type: application/json

{
  "phone": "{{resident_phone}}",
  "token": "<copy only the token after /join/ from the invitation link>"
}
```

**Success response — `200 OK`**

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "v1...",
  "token_type": "bearer",
  "expires_at": 1784870400,
  "user_id": "e0d00000-0000-4000-8000-000000000005",
  "role": "RESIDENT"
}
```

**Expected failures**

| Case | Status | Response code / expected outcome |
| --- | --- | --- |
| Neither token nor code sent | `422` | `validation_error` |
| Random token/code, or valid invite with a different phone | `422` | `invite_invalid` (does not disclose another resident's invite) |
| Invitation expired | `422` | `invite_expired` |
| Invitation previously redeemed | `409` | `invite_used` |
| The invited phone already has a Supabase Auth account | `409` | `user_exists` |

**Postman test**

```javascript
const body = pm.response.json();
pm.test("resident redeems invite and receives a session", () => {
  pm.response.to.have.status(200);
  pm.expect(body.role).to.eql("RESIDENT");
  pm.expect(body.user_id).to.be.a("string").and.not.empty;
  pm.expect(body.access_token).to.be.a("string").and.not.empty;
  pm.expect(body.refresh_token).to.be.a("string").and.not.empty;
});
pm.environment.set("resident_access_token", body.access_token);
pm.environment.set("resident_refresh_token", body.refresh_token);
```

Immediately repeat the identical request once to confirm one-time use. Expect
`409` and `error.code = "invite_used"`. Do not re-run the success request
after that: create a new invite first.

## 6. Full end-to-end Postman walkthrough

Run this manually the first time. A Postman Collection Runner cannot pause to
wait for an SMS, so it is best used only after OTP variables have been entered.
The endpoint sections above contain the exact body and Post-response script for
each request.

1. **System check.** Send `GET {{base_url}}/health` in `00 - System`.
   - Expected: `200`, `status = "ok"`, and `env = "development"`.
   - If this fails, stop. Postman cannot diagnose Supabase configuration until
     the FastAPI process itself is healthy.

2. **Confirm the OpenAPI contract.** Send `GET {{base_url}}/openapi.json`.
   - Expected: `200` JSON and paths such as `/api/v1/auth/me`.
   - This confirms Postman is targeting the intended backend rather than an
     old process on the same port.

3. **Request the initial admin OTP.** Send `POST /api/v1/auth/otp/request`
   with `{{admin_phone}}`.
   - Expected: the generic `200` acknowledgement, even for an unknown number.
   - Copy the received six-digit code into the environment's **Current value**
     for `admin_otp`. Do not add it to Initial value.

4. **Verify the admin OTP.** Send `POST /api/v1/auth/otp/verify` and attach the
   **Save an admin session** script from section 4.
   - Expected: `200`; `admin_access_token` and `admin_refresh_token` now have
     Current values.
   - If this returns `missing_role_claim` on a later protected request, enable
     the hook and repeat this step to mint a new token.

5. **Prove the admin session works.** Send `GET /api/v1/auth/me` with
   **Authorization → Bearer Token → `{{admin_access_token}}`**.
   - Expected: `200` and the admin profile. This verifies local JWT signature
     validation, bearer header construction, and profile RLS in one request.

6. **Create a resident invitation.** Send `POST /api/v1/admin/invitations`
   with the bootstrapped `{{community_id}}`, `{{unit_id}}`, and a new
   `{{resident_phone}}`. Attach the invitation test script from section 5.6.
   - Expected: `200`; `invitation_id` and `invite_code` become environment
     values.
   - Confirm that the response IDs exactly match `community_id` and `unit_id`.
     If they do not, do not redeem it.

7. **Redeem exactly once.** Send `POST /api/v1/auth/redeem` using
   `{{resident_phone}}` and `{{invite_code}}`. Attach the **Save a resident
   session** script.
   - Expected: `200`; the response role is `RESIDENT` and resident tokens are
     saved.
   - Do not click Send a second time until the next step: it is a deliberate
     state-changing request.

8. **Verify one-time use.** Duplicate the redemption request into the negative
   folder and send it once more without changing body values.
   - Expected: `409` with `error.code = "invite_used"`.
   - If it instead succeeds, stop testing: the one-time invitation invariant
     is broken.

9. **Verify the database side effects.** In the Supabase SQL Editor, run this
   read-only check after a successful redemption (replace the literal phone):

   ```sql
   select
     p.id as profile_id,
     cm.id as membership_id,
     cm.role,
     cm.status,
     ur.unit_id,
     ur.relationship_type,
     ri.status as invitation_status
   from public.profiles p
   join public.community_memberships cm on cm.profile_id = p.id
   join public.unit_residencies ur on ur.membership_id = cm.id
   join public.resident_invites ri on ri.redeemed_by_profile_id = p.id
   where p.phone_e164 = '+919812345678'; -- replace resident phone
   ```

   Expected: one active `resident` membership, an active unit residency, and a
   `redeemed` invitation. This validates the transactional claim workflow,
   not merely its HTTP response.

10. **Prove resident access.** Send `GET /api/v1/auth/me` with
    `{{resident_access_token}}`.
    - Expected: `200` identity profile for the new resident.
    - This endpoint intentionally does not return membership/unit details;
      they were checked in the previous SQL query.

11. **Prove the resident can log in later.** Request an OTP for
    `{{resident_phone}}`, put the received code in `resident_otp`, then verify
    it. Save the resulting resident session again.
    - Expected: both requests return `200`.
    - This confirms that the invitation-created Auth user can use the standard
      SMS OTP path.

12. **Exercise session refresh.** Send `POST /api/v1/auth/refresh` with either
    stored refresh token. Its script must replace the old access and refresh
    token values with the response values.
    - Expected: `200` and a usable fresh bearer token.

13. **Run authorization negatives.**
    - Remove the bearer token from `/auth/me`; expect `401` and
      `authentication_error`.
    - Call `/admin/invitations` using `{{resident_access_token}}`; expect
      `403` and `insufficient_role`.
    - Submit redemption with neither token nor code; expect `422` and
      `validation_error`.

After the walkthrough, clear Current values for `admin_otp`, `resident_otp`,
both access tokens, both refresh tokens, and `invite_code`. Keep only
non-sensitive IDs and test phone labels if the environment will be shared.

## 7. Troubleshooting

| Symptom | Likely cause | Resolution |
| --- | --- | --- |
| API fails at startup with missing settings | `backend/.env` is absent or incomplete. | Copy `.env.example`; supply the four Supabase credentials and restart Uvicorn. |
| OTP request returns the generic acknowledgement but no SMS arrives | Phone is not an existing Auth user, provider/test number is not configured, or the phone is not E.164. | Check Supabase Phone provider/test configuration and use a provisioned number. The API intentionally does not reveal registration status. |
| Protected route returns `missing_role_claim` | Access-token hook is not registered, or token was minted before migration `0005`/the hook update. | Register the hook, then sign in again to obtain a newly minted access token. |
| `POST /admin/invitations` returns `403` despite an admin title elsewhere | The caller is not an active `ADMIN` member of the exact supplied community. | Verify `community_memberships` and the target `community_id`; use a freshly minted token. |
| Redemption returns `invite_invalid` | Wrong code/token, wrong phone, or secret was altered/copied incorrectly. | Use a new invitation and the exact invited E.164 phone. |
| Redemption returns `user_exists` | That phone already exists in Supabase Auth. | Log in using OTP instead, or create a fresh invitation for an unused test phone. |
| Browser client is blocked but Postman works | CORS is configured for the wrong frontend origin. | Add the exact browser origin to comma-separated `CORS_ORIGINS`; Postman does not enforce browser CORS. |

## 8. Postman hygiene

- Keep the collection unshared or remove live environment values before
  exporting it. Access tokens, refresh tokens, invitation codes, and
  invitation links are credentials.
- Use Supabase test phone numbers for repeatable local runs. A successful
  redemption consumes its invitation, so each clean test run needs a fresh
  phone/invite pair.
- Do not put `SUPABASE_SERVICE_ROLE_KEY` in Postman. It is an API-server-only
  credential and must never be sent from a client.
- Before testing a changed schema/RLS migration, take a database backup and use
  a non-production Supabase project first.

## 9. Official Supabase references

- [Database migrations and linked-project deployment](https://supabase.com/docs/guides/deployment/database-migrations)
- [Phone login and SMS provider configuration](https://supabase.com/docs/guides/auth/phone-login)
- [API key handling: publishable versus secret keys](https://supabase.com/docs/guides/getting-started/api-keys)
- [Supabase CLI configuration, including local test OTPs and Auth hooks](https://supabase.com/docs/guides/local-development/cli/config)
