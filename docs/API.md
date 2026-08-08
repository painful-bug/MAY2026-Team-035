# HomeBandhu API reference

**Version:** v1 · **Base path:** `/api/v1` · **Last updated:** 2026-08-08

> ## Where the numbers stand
>
> The live surface is **99 operations across 86 paths**, all of them in
> [`openapi.yaml`](openapi.yaml), all carrying a user-story verdict (§16). Every `###` heading below
> corresponds to an operation that exists; that is checked mechanically rather than by eye.
>
> **Two contract-wide rules that apply to every endpoint below.**
>
> 1. **Authentication is cookie-first.** A signed HTTP-only session cookie is the normal credential; the
>    bearer header still works, because `_extract_token` accepts either. Permission resolves from
>    `community_memberships` in Postgres, **not** from a JWT claim — the access-token hook that produced
>    that claim was deleted with the old baseline. Full detail in §1.2.
> 2. **Every unsafe request needs `X-CSRF-Token`.** Reads neither send nor require it. When no session
>    CSRF cookie exists, the browser client first obtains the readable `hb_preauth_csrf` cookie from
>    `GET /auth/csrf`, then echoes it. A missing or mismatched token is **403** `csrf_invalid`; a wrong
>    `Origin` is **403** `csrf_origin_invalid`.
>
> **The database objects these endpoints need exist in migrations, and in no database.** `0019`–`0023`
> rebuilt the quarantined `0013`–`0017` onto the clean baseline, and `0024`–`0032` added realtime,
> notifications and visitor passes. A static check confirms every RPC and column the repositories
> reference is created by some migration. **No environment has run `0001` yet**, so "exists in the
> migration" is as far as the guarantee goes — applying them has to happen before anyone can say these
> endpoints work.


This document is the contract between the backend and the React frontend. It is
**normative**: if the code and this document disagree, that is a bug in one of them.

**[§16](#16-user-stories--endpoints) traces every endpoint back to the user story it serves**, and
names the stories nothing serves yet. The stories and the user identification they came from are
checked in under **[`product/`](product/)**.

> **Standing rule.** Every backend change updates this file in the same commit — new endpoints,
> changed shapes, changed status codes. The frontend team is not in the room, and an endpoint that
> exists only in Python is invisible to them.

An OpenAPI 3.1 schema is generated from the code at **`GET /openapi.json`**, with interactive docs at
**`/docs`** (Swagger UI) and **`/redoc`**. The same schema is checked in as
**[`openapi.yaml`](openapi.yaml)**, so the contract can be read, diffed and used to generate clients
without running the service.

**What lives where.** The spec is authoritative for anything a client must agree with mechanically:
shapes, every status code an operation can return, the error envelope, per-parameter meaning, and
the user story each operation traces to. This file carries what a client cannot act on but a
maintainer needs — why a delete is really a deactivation, which guard returns 409 and what it is
protecting, the shape of the gaps in §16. Read the spec to write a client; read this to change one.

Everything a generator cannot infer — error responses, story traceability, and descriptions for the
handlers with no docstring — is supplied by
[`backend/scripts/api_annotations.py`](../backend/scripts/api_annotations.py), one table the
exporter applies. It exists because roughly half these operations sit in another workstream's
routers, and annotating them centrally keeps the spec complete without editing their handlers.

> **Standing rule.** `openapi.yaml` is **generated, never hand-edited**, and is regenerated in the
> same commit as any API change:
>
> ```bash
> cd backend && python scripts/export_openapi.py
> ```
>
> `python scripts/export_openapi.py --check` fails when it is stale, and `tests/test_openapi_spec.py`
> runs that check as part of the suite — a hand-maintained spec drifts the first time a field is
> renamed, and a spec that lies is worse than no spec, because clients generate types from it.

---

## 1. Conventions

### 1.1 Base URL and versioning

| Environment | Base URL |
|---|---|
| Local | `http://localhost:8000/api/v1` |
| Deployed | `https://<host>/api/v1` |

The version is in the path. A breaking change to an existing endpoint means `/api/v2`, not a silent
edit. Additive changes — new fields, new optional query parameters — are **not** breaking, and
clients must ignore unknown response fields.

`GET /health` is deliberately **outside** `/api/v1` — it is a liveness probe for the platform, not
part of the product API.

### 1.2 Authentication

The backend is a **backend-for-frontend**: no provider token is ever handed to JavaScript. Signing in
sets HTTP-only cookies, and the browser simply sends them.

| Cookie | Holds | Readable by JS |
|---|---|---|
| `__Host-hb_access` | Supabase access token | No |
| `__Host-hb_refresh` | Supabase refresh token | No |
| `__Host-hb_csrf` | CSRF token bound to the access token | Yes — it must be echoed in a header |

Local HTTP development drops the `__Host-` prefix (`hb_access`, …), because browsers reject
`__Host-` cookies without `Secure`. The names are the only difference; the contract is identical.

A bearer header is also accepted and takes precedence, which is what server-to-server callers and the
test suite use:

```
Authorization: Bearer <access_token>
```

**Seventeen operations need no token at all** — `GET /health`, the whole of `/auth/*` except
`/auth/session`, and `POST /invitations/prepare`. Everything else requires one. The generated
`openapi.yaml` is authoritative: an operation carrying `security: [{ HTTPBearer: [] }]` needs
credentials, and one without it does not.

**Tokens establish identity, never permission.** They are verified against the project's JWKS
(`SUPABASE_JWT_SECRET` covers legacy HS256 tokens). No role claim is read from them. Authorization is
resolved per request from the caller's **active `community_memberships` row** — see
`get_active_membership` and `require_membership_role` in `app/api/deps.py`. A role written into a
token by a compromised or stale hook therefore grants nothing.

> `app/domain/roles.py` still defines an `ADMIN` ⊇ `RESIDENT` hierarchy, and older revisions of this
> section described it as live. It is not: `role_satisfies` is referenced only by its own unit test,
> and the request guards match membership roles exactly. Where an admin genuinely needs a resident
> surface, `GET /auth/session` says so explicitly by returning `capabilities: ["admin", "resident"]`.

**Unsafe methods also need CSRF.** `POST`, `PATCH`, `PUT` and `DELETE` on browser-facing routes require
an `X-CSRF-Token` header matching the CSRF cookie, and an `Origin` matching the configured frontend.
Before a session exists — sign-up, sign-in, password reset, resend — call `GET /auth/csrf` first to be
issued a pre-authentication token. Missing or mismatched gives `403 csrf_invalid`.

**Enforcement is layered.** The membership guard is the outer check; Postgres Row-Level Security is
the inner one, and it is scoped by community. A guard bypass still cannot read another community's
rows.

### 1.3 Field naming — a known inconsistency

| Endpoint group | Case | Example |
|---|---|---|
| `/auth/*`, `/admin/invitations` | `snake_case` | `token_hash`, `invitee_email`, `intended_unit_id` |
| Everything else | `camelCase` | `pageSize`, `timeAgo`, `unitId` |

This is not a style preference, it is a seam. The React app reads camelCase throughout its seeded data
and **cannot be changed**, so new surfaces emit camelCase. The auth DTOs predate that constraint, and
the frontend already reads them as `snake_case`, so converting them is a coordinated change to both
sides rather than a rename — worth doing deliberately, not as a drive-by.

One cosmetic difference between this file and `openapi.yaml`: path **placeholders** render as
`{membership_id}` there and `{membershipId}` here. A placeholder is not part of any URL a client
sends — `/api/v1/residents/7d3c1b90-…` is the same request either way — so it is a naming artefact of
the Python parameter, not a second convention.

### 1.4 Error envelope

**Every** error response — application errors, request validation, unknown paths, unhandled
exceptions — uses one shape:

```json
{
  "error": {
    "code": "not_found",
    "message": "Community not found."
  }
}
```

`code` is stable and machine-readable; branch on it, not on `message`. `message` is human-readable and
safe to display. Validation failures add a `details` array:

```json
{
  "error": {
    "code": "request_validation_error",
    "message": "The request could not be validated.",
    "details": [{ "field": "query.page", "message": "Input should be greater than or equal to 1" }]
  }
}
```

This envelope is in [`openapi.yaml`](openapi.yaml) as `ErrorResponse`, and **every operation declares
the specific codes it can return** — all 72 of them today, and the exporter refuses to write a spec
in which one does not — each pointing at a shared
`components/responses` entry. Until 2026-08-02 the spec instead carried FastAPI's stock
`HTTPValidationError` — `{"detail": [...]}` — on 59 operations and nothing else anywhere: a shape
this API has never sent, because `register_exception_handlers` replaces the default handlers. A
client generated from that spec would have failed to parse every error it ever received. The
schema has been removed rather than left beside the correct one.

`ErrorResponse`, `ErrorBody` and `ErrorDetail` are **pydantic models in
`app/core/exceptions.py`**, so their shape is generated from the code that emits them rather than
described alongside it. Only the prose on those schemas, and the per-operation code lists, come
from `backend/scripts/api_annotations.py`.

### 1.5 Status codes

| Code | Meaning | When |
|---|---|---|
| `200 OK` | Success | All reads. Includes empty collections — see §1.6 |
| `201 Created` | Resource created | `POST /registrations/{id}/approve`, which mints an invitation |
| `400 Bad Request` | `app_error` | Generic business-rule failure |
| `401 Unauthorized` | `authentication_error` | Missing, malformed or expired bearer token |
| `403 Forbidden` | `authorization_error` / `insufficient_role` | Authenticated but wrong role |
| `404 Not Found` | `not_found` / `http_404` | Resource does not exist, or unknown path |
| `405 Method Not Allowed` | `http_405` | Wrong verb for a known path |
| `409 Conflict` | `conflict` | State conflict — an invite already redeemed, a stale `updated_at` |
| `422 Unprocessable Entity` | `validation_error` / `request_validation_error` | Malformed body or query |
| `429 Too Many Requests` | — | **Not implemented.** See §1.8 |
| `500 Internal Server Error` | `internal_error` | Unhandled exception. Logged in full; the response message is deliberately opaque, because an exception string can leak a table name or a connection string |

**401 vs 403 is not interchangeable.** 401 means *we do not know who you are* — re-authenticate.
403 means *we know exactly who you are and the answer is no* — re-authenticating will not help.

Three rows above are deliberately **absent from every operation** in `openapi.yaml`. `400` is the
`AppError` base default and nothing raises it bare — only its subclasses, which carry their own
statuses. `405` is produced by Starlette's router before any operation is reached, so it belongs to
no path. `429` is not implemented at all (§1.8). Declaring them per operation would advertise
responses that cannot occur, which is the failure this document has just spent a section correcting.

**`422` is the opposite case, and it is declared far more widely than the tables below claim.**
It appears on nearly every operation in the spec because `app/main.py` declares it once on the
whole `include_router(...)`, so every route inherits it; `scripts/api_annotations.py` traces it to
a specific rule on about half that number. The generator unions the two and never subtracts —
narrowing a claim the application itself makes is not the exporter's decision, and a spec that
contradicts the app is worse than one that over-promises. Nor is the wide claim false: FastAPI
returns `422` from any operation with a path, query or body parameter it fails to coerce. Read the
per-endpoint `422` rows below as *the validation this endpoint does on purpose*, and the spec's as
*where a `422` is reachable at all*. The one route that suppresses it deliberately is
`GET /events` (§5.1), whose `Last-Event-ID` is browser-written and reconnects instead.

### 1.6 Pagination

Every collection endpoint returns the same envelope, whether or not there is data:

```json
{ "items": [], "total": 0, "page": 1, "pageSize": 20, "hasMore": false }
```

| Parameter | Type | Default | Range |
|---|---|---|---|
| `page` | integer | `1` | ≥ 1 |
| `pageSize` | integer | `20` | 1–100 |

**An empty collection is `200` with `items: []`, never `404`.** A newly founded community has zero of
everything, and that is the first screen a real founding admin sees. One shape to design against.

Out-of-range pages return an empty `items` with the true `total`, not an error.

### 1.7 Caching

| Endpoint | Header | Why |
|---|---|---|
| `GET /dashboard/admin` | `Cache-Control: no-store` | Live counts |
| `GET /notices` | `Cache-Control: no-store` | Contains `timeAgo` |
| `GET /invoices*`, `GET /payments` | none set | `billPeriod` is a fixed calendar range, not a relative time |
| Everything else | none set | Cacheable by the client |

`no-store` is applied **per endpoint, not globally**, so responses that carry no relative time stay
cacheable. Any response containing a server-rendered relative time is only correct at the instant it
was generated — a cached `"2h ago"` is wrong the moment it is served. Each such DTO also carries the
raw ISO-8601 instant (`publishedAt` beside `date`/`timeAgo`), so a screen that adopts client-side
formatting lets us drop `no-store` for that endpoint. See `FRONTEND_MEETING_AGENDA.md` item 3.

### 1.8 Rate limiting

**Not implemented.** No endpoint is rate-limited today. The surfaces that need it most are the
unauthenticated ones where a secret can be guessed or a cost incurred: `POST /auth/password/sign-in`,
`POST /invitations/prepare` (a token *and* a short code, both guessable in principle),
`POST /auth/email/resend` and `POST /auth/password/reset/request` (each one sends mail). Supabase
applies its own limits to the underlying GoTrue calls, which is a backstop, not a design. Tracked as
open work; when added, it returns `429` with `Retry-After`.

### 1.9 Dates and times

All timestamps are **ISO-8601 with an explicit UTC offset**: `2026-07-08T12:00:00+00:00`.

Human-formatted strings (`date: "July 8, 2026"`, `timeAgo: "2h ago"`) are rendered in **IST
(UTC+05:30)**, because the community timezone is not stored anywhere yet. This is correct for every
Indian community and wrong for any other. See `app/core/formatting.py`.

### 1.10 Concurrency

**Not yet enforced on any endpoint.** The design is to use `updated_at` as an optimistic-concurrency
token rather than a `version` column: send the value you read back verbatim — **do not reformat it**,
truncating microseconds breaks the comparison — and a mismatch answers `409 Conflict`. Every table
carries a trigger-maintained `updated_at` ready for it.

Today, last write wins on `PATCH /residents/{id}`, `PATCH /complaints/{id}`, `PATCH /departments/{id}`
and `PUT /billing-settings`. Two admins editing one row at the same moment silently overwrite each
other. **This was due before step 6 and has now slipped past step 7** — four last-write-wins
surfaces rather than one. Tracked as `DECISIONS_NEEDED.md` F4.

**Money is the exception, and not by optimistic concurrency.** No invoice balance is ever written
by the API: `record_payment` and `void_invoice` take a row lock, recompute the balance from the
payment rows inside the transaction, and a CHECK constraint rejects any balance that disagrees with
its own status. Two admins recording payments at the same moment serialise and both land
correctly — there is no read-modify-write to lose.

**Where it is already enforced, differently:** the approve/reject/remove RPCs take a row lock and
re-check state inside the transaction, so two admins clicking Approve at once serialise and the second
gets `409` rather than minting a duplicate invitation.

---

## 2. System

### `GET /health`

Liveness probe. No authentication.

**200**
```json
{ "status": "ok", "env": "development" }
```

---

## 3. Authentication

Two ways in, one session. **Google OAuth** is the primary method; **email and password** is the
secondary one. Phone/SMS OTP was the original design and **no longer exists** — no OTP endpoint is
served, and `GET /auth/methods` is the authoritative list of what a deployment actually accepts.

Whichever method is used, the outcome is identical: the backend holds the provider tokens and the
browser gets cookies (§1.2). The resident invite token remains a mandatory second factor regardless of
how the person signed in.

### 3.1 Discovery and CSRF

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/auth/methods` | Which methods this deployment enables, and which is primary. Cached 5 minutes, `ETag`-aware |
| `GET /api/v1/auth/csrf` | Issue a pre-authentication CSRF token, required before any unauthenticated `POST` below |

### 3.2 Google OAuth

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/auth/oauth/{provider}/start` | **307** to the provider. Plants a signed, HTTP-only PKCE transaction cookie (5-minute TTL) |
| `GET /api/v1/auth/oauth/{provider}/callback` | **307** back to the frontend, with session cookies set |
| `GET /api/v1/auth/google/start`, `GET /api/v1/auth/google/callback` | Compatibility aliases, so existing bookmarks and registered Google callbacks keep working |

**A redirect is the success case here**, which is why these four declare `307` and no `2xx`.

GoTrue generates the provider `state` itself; supplying our own makes it reject the callback as
`bad_oauth_state`. The transaction cookie binds the browser to its PKCE verifier instead.

### 3.3 Email and password

| Endpoint | Request | Notes |
|---|---|---|
| `POST /api/v1/auth/password/sign-up` | `{ full_name, email, password, captcha_token? }` | Password minimum is **15 characters**. Always answers the same, so it cannot reveal who has registered |
| `POST /api/v1/auth/password/sign-in` | `{ email, password, captcha_token? }` | Sets the session cookies |
| `POST /api/v1/auth/email/verify` | `{ token_hash, verification_type }` | Spends the one-time hash from the confirmation email and signs the user in |
| `POST /api/v1/auth/email/resend` | `{ email, captcha_token? }` | Sends the confirmation link again. **200 is not a delivery receipt** — provider errors are swallowed so the response cannot enumerate accounts |

**An unconfirmed address cannot sign in.** `POST /auth/password/sign-in` answers `401`
`email_not_confirmed` both when the provider refuses the grant and when it returns a session for an
address nobody has proven they own — so the behaviour does not depend on the Supabase **Confirm email**
setting. That error names its reason rather than hiding behind the generic message: reaching it
requires the correct password, so it discloses nothing the caller did not already know. Recovery is
`POST /auth/email/resend`.

Confirmation links must carry the token hash to the frontend
(`…/auth/confirm-email?token_hash={{ .TokenHash }}&type=signup`). A template left on GoTrue's default
`{{ .ConfirmationURL }}` lands on that page with nothing to spend — see `docs/SUPABASE_AUTH_SETUP.md`
step 3.

| Status | Code | Cause |
|---|---|---|
| `401` | `invalid_credentials` | Wrong password, or no such address — deliberately indistinguishable |
| `401` | `email_not_confirmed` | Correct password, unconfirmed address |
| `401` | `password_signup_failed` | Sign-up could not be started |
| `403` | `csrf_invalid` | Missing/mismatched `X-CSRF-Token`, or wrong `Origin` |
| `422` | `captcha_required` | CAPTCHA enabled and no token supplied |
| `422` | `provider_disabled` | Method not in `AUTH_ENABLED_METHODS` |
| `503` | `auth_provider_timeout` | Supabase did not answer within the configured timeout |

### 3.4 Password recovery

Three steps, because the new password is set against a **separate, short-lived recovery session** that
is never usable as an ordinary login.

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/auth/password/reset/request` | Email a recovery link. Always the same answer |
| `POST /api/v1/auth/password/reset/verify` | Spend the hash; sets recovery-only cookies |
| `POST /api/v1/auth/password/reset/complete` | `{ password }`; updates it, then clears every cookie so the user signs in afresh |

`401 recovery_required` means the recovery cookies are absent or expired — request a new link.

### 3.5 Session lifecycle

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/auth/session` | The caller's identity, active membership, portal and capabilities. **Requires a token** |
| `POST /api/v1/auth/refresh` | Rotate the session from the refresh **cookie** — no body |
| `POST /api/v1/auth/logout` | Revoke at the provider (best effort) and clear the cookies (authoritative) |

`GET /auth/session` is what the frontend routes on: it returns `onboarding_eligible: true` for a
signed-in identity with no membership yet, and otherwise the membership that decides which portal
loads.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | No refresh cookie, or it is invalid, expired or revoked |
| `401` | `token_expired` | Access token past its expiry — refresh and retry |

## 4. Invitations

An invite is **bound to an email address and a unit**, and redeeming it needs both halves: the link
*and* the short code. The code is the second factor, and is not optional.

### `POST /api/v1/admin/invitations`

Mint a resident invite. **Requires an active `admin` membership.**

**Request**
```json
{
  "intended_unit_id": "0f1e2d3c-...",
  "invitee_email": "rohan@example.com",
  "phone": "+919812345678",
  "full_name": "Rohan Sharma"
}
```

`phone` and `full_name` are optional labels for the admin's own list. `intended_unit_id` is a unit
**id**, not a display code like `B-1204`.

**200**
```json
{
  "invitation_id": "b2f1c9d4-...",
  "link": "http://localhost:5173/join/9f2a...",
  "code": "4KJ7-2M",
  "invitee_email": "rohan@example.com",
  "community_id": "7a8b9c0d-...",
  "intended_unit_id": "0f1e2d3c-...",
  "expires_at": "2026-08-01T09:00:00+00:00"
}
```

> ⚠️ **`link` and `code` are returned exactly once and are never recoverable.** Only their digests are
> stored. If the admin loses them, the invite must be reissued.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | Not authenticated |
| `403` | `community_role_required` | Caller has no active admin membership |
| `422` | `request_validation_error` | Malformed body |

### `POST /api/v1/invitations/prepare`

Stage an invite before the recipient has signed in — the only invitation endpoint needing no token.

**Request** — `{ "token": "9f2a...", "code": "4KJ7-2M" }`

Both must resolve to the same live invitation. On success the invite id is placed in a signed,
HTTP-only cookie with a **5-minute TTL**; the response body deliberately says nothing about who was
invited. The caller then signs in by whichever method they like and calls redeem.

### `POST /api/v1/invitations/redeem`

Claim the staged invitation for the signed-in identity. **Requires a token.** The body is empty: the
invitation comes from the cookie, never from the request, so a signed-in user cannot redeem an
invitation they did not open.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | Not signed in, or the staging cookie is missing or expired |
| `422` | `invite_unavailable` | The staged invitation no longer exists or has been used |

## 5. Live updates, notifications and the admin dashboard

**No admin-dashboard endpoints of ours live here.** Every one this section documented was removed by the frontend wiring audit,
because their `GET /dashboard/snapshot` already serves the same reads and the frontend already calls it. The
removals were `GET /dashboard/admin`, `GET /communities/current`, `GET /notices` and `GET /residents`. See
[FRONTEND_WIRING_AUDIT.md](FRONTEND_WIRING_AUDIT.md) §3 for the evidence behind each one, and
[`../backend/API_REFERENCE.md`](../backend/API_REFERENCE.md) for the snapshot's contract.

The heading is kept so the section numbering below does not shift; renumbering would break every link and
reference into §7–§17 for no gain. It has since acquired a second job: §5.1–§5.3 are the three delivery
layers of one design, and keeping them together is worth more than a heading that names only one of them.

### 5.1 Live updates — `GET /events`

One stream for every portal. It is how every write in §7–§12 reaches an open screen without a matching read
endpoint.

> **`GET /dashboard/events` is a deprecated alias** for this endpoint — same handler, same behaviour, same
> audience scoping. It stays because the admin frontend is already wired to it. New clients use `/events`.
>
> The stream was never dashboard-specific: its guard has always been *any active membership*, not an admin
> role. What changed is that the rows now carry an audience (below), which is what makes one endpoint correct
> for every role.

**Transport: server-sent events** (`text/event-stream`), same-origin, over the browser's native `EventSource`.
No Supabase key or provider token reaches the browser. Auth is the session cookie.

Rationale and the rejected alternatives — Supabase Realtime, `LISTEN`/`NOTIFY`, client polling — are in
[ARCHITECTURE.md § Live updates](ARCHITECTURE.md#live-updates).

**Who receives what**

Every outbox row carries an audience, added by
[`0028_event_audience.sql`](../backend/supabase/migrations/0028_event_audience.sql):

| Audience | Delivered to | Used by |
|---|---|---|
| `community` | every subscriber in the community | genuinely community-wide news |
| `role` | subscribers whose role is in the row's `audience_roles` | `dashboard.refresh`, `access_request.*` — both `{admin, manager}` |
| `member` | the one subscriber matching the row's `recipient_membership_id` | anything addressed to one person |

The filter runs on the community id, membership id and role of the membership the request already resolved
out of Postgres — never on a header, a query parameter or a `Last-Event-ID`. A client therefore cannot widen
its own stream by replaying someone else's resume point, and cannot widen it at all.

Before `0028` the fan-out was by community alone, so **any** member who opened the stream received
`access_request.created` for their neighbours, applicant name included. Nothing exploited it, because no
non-admin client connected; the fix landed before the resident portal rather than after.

**Request**

| Header | Required | Meaning |
|---|---|---|
| `Last-Event-ID` | no | Resume point. The stream backfills everything after this id **that the caller is in the audience for** before attaching to the live feed, so a reconnect across a network blip loses nothing. Non-numeric or negative values are treated as `0` — the header is written by the browser, not by application code, so a malformed one reconnects rather than `422`s. |

**Frames**

```
id: 4127
event: access_request.created
data: {"request_id":"…","applicant_name":"Asha R","requested_relationship":"tenant","status":"pending","created_at":"2026-07-30T09:14:02Z","pending_count":3}
```

`data` is always JSON. A comment frame (`: keepalive`) is sent every 20s so proxies do not reap an idle stream.

| Event | Audience | When | Payload |
|---|---|---|---|
| `access_request.created` | `{admin, manager}` | someone asks to join the community | `request_id`, `applicant_name`, `requested_relationship`, `status`, `created_at`, `pending_count` |
| `access_request.decided` | `{admin, manager}` | a request is approved, rejected or blacklisted | `request_id`, `applicant_name`, `from`, `to`, `pending_count` |
| `dashboard.refresh` | `{admin, manager}` | any write to one of 12 domain tables | `{"table": "…"}`, or `{"resync": true}` if this connection fell behind and events were dropped |
| `stream.resync` | the affected connection | this connection fell behind and events were dropped | `{"resync": true}` |

`stream.resync` and `dashboard.refresh`-with-`resync` are the same instruction — *you have a gap, re-read
everything*. They differ only in name: an admin gets the topic its listener is already wired to, and every
other role gets one that does not claim to be about the admin dashboard. **Any client that opens this stream
must handle `stream.resync`**; it is the only frame that can arrive without a preceding domain event.

**Contract notes**

- Delivery is **at-most-once**, and the payload is a hint, never truth. The matching `GET` is authoritative;
  treat every event as "re-read", which is what `dashboard.refresh` means literally.
- **A resident does not receive a blanket refresh frame.** `dashboard.refresh` means "re-read the admin
  snapshot", which a resident would be refused; it has always been a wasted wake-up for them. Resident
  screens get specific topics instead — five hundred flats re-fetching on every unrelated row change is a
  thundering herd, not a feature.
- `pending_count` is the community's live count of pending join requests, included so a badge or toast can
  update without a round trip.
- Status codes: `200` (stream opens), `401` (no session), `403` (no active membership).

### 5.2 Notifications — the layer that survives being offline

**Three layers deliver one record, and only one of them is durable.**

| Layer | Mechanism | Lifetime | Reaches |
|---|---|---|---|
| Record | a `notifications` row | until read and pruned | anyone, later |
| In-app live | an SSE frame (§5.1) | the connection | an open tab |
| Out-of-app | Web Push (§5.3) | one delivery attempt | a closed tab, a locked phone |

> **The stream is not the notification system.** SSE is at-most-once and connection-scoped — §5.1 makes *the
> payload is a hint, never truth* load-bearing, and it is only safe **because** of that rule. A push may
> simply not arrive. So every user-visible event writes the row **first**, inside the transaction that caused
> it, and the two transports carry it. A resident whose phone was locked when a visitor reached the gate must
> still find out.

Nothing durable can be built on `sse_events`: it is pruned every fifteen minutes, deliberately, because it is
ephemeral. Building a feed on a table designed to be deleted inverts both.

The notification a resident sees is **rendered strings, not a record**: a title, a body and a deep link. The
record itself is fetched through its own endpoint, where the ownership predicate lives. That has a second
effect worth stating — a field the renderer was not asked for cannot leave the database, which is how the one
absolute rule in §5.3 is enforced rather than remembered.

#### `GET /api/v1/notifications`

The caller's own feed, newest first. **Any active member** — an admin receives `complaint.raised` and
`access_request.created`, and a feed that refused them would mean building a second one later.

**There is no recipient parameter, and the tenancy here is doubled.** The recipient is the membership
`get_active_membership` resolved from Postgres, and `notifications` also carries an RLS policy of its own
(`is_own_membership`), so a query that asked for someone else's rows would come back empty from the database
regardless of what the API did. This is the first table in this backend where that is true.

| Query | Default | Notes |
|---|---|---|
| `unread` | `false` | Only unread rows. `unread` in the *response* still counts the whole feed |
| `page` | `1` | |
| `pageSize` | `20` | Max `100` |

| Response field | Notes |
|---|---|
| `items[].id`, `items[].kind` | `kind` is the vocabulary in `RESIDENT_BACKEND_DESIGN.md` §10.3, e.g. `visitor.approval_requested`. Not an enum on the wire: every later build step adds kinds |
| `items[].title`, `items[].body` | Rendered when the row was written. A notification whose writer set no title falls back to one derived from its `kind` — a blank line in a feed reads as a bug in the app |
| `items[].url` | Where a click goes, as a frontend path. `""` when there is nowhere to route |
| `items[].isUnread`, `items[].createdAt` | |
| `unread` | Unread across the **whole feed**, not this page. It is what a badge renders, and a badge that changed as the resident scrolled would be wrong |

Paged, unlike the amenity catalogue in §10: a feed grows without bound and the screen that reads it shows the
newest handful.

#### `POST /api/v1/notifications/{notificationId}/read`

Marks one read and returns `{ marked, unread }`, so a badge can be set from the response rather than by
re-fetching the feed.

**`404` for a notification that does not exist and for one that is not yours — deliberately the same answer.**
Telling a caller that an id is real but not theirs is how an id space gets enumerated. Idempotent: marking an
already-read notification read is a `200`, and the original `readAt` is kept rather than moved forward.

#### `POST /api/v1/notifications/read-all`

Clears the badge. `marked` is how many rows actually moved, so a second call answers `0` rather than erroring.
`unread` is re-read afterwards instead of assumed to be zero — a notification can arrive between the update
and the count, and a badge told `0` while one is already waiting stays wrong until the next fetch.

| Status | When |
|---|---|
| `200` | Feed returned, or the state was reached |
| `401` / `403` | No session; no active membership, or a failed CSRF pair on the two writes |
| `404` | Only on `/{notificationId}/read` — unknown, or not the caller's |

### 5.3 Web Push — `GET /push/vapid-key`, `POST /push/subscriptions`, `POST /push/subscriptions/unregister`

Standards Web Push (RFC 8291/8292) over this server's own VAPID keypair. **No vendor account, no SDK in the
frontend bundle, and no third party ever learns who visited which flat and when** — Google, Mozilla and Apple
relay ciphertext they cannot read, because RFC 8291 encrypts the payload end to end between this server and
the browser.

**The push body carries the detail.** `US-2.1`'s recorded pain point is a notification that produces *"only a
notification sound without displaying the actual notification"*, so a generic *"open the app"* push would be a
milder version of the exact failure that story exists to fix — and a resident being asked to approve or reject
someone needs the name to decide.

> **One thing may never appear in a push body: the visitor security code.** It is a hashed credential returned
> exactly once (§10 of the design), and a credential on a lock screen is a credential readable by anyone
> holding the phone. Names, purposes, flat numbers and amounts — yes. The thing that opens the gate — never.
> This is enforced by construction: the renderer reads `title`, `body` and `url` and copies no other key, so a
> writer that puts a secret anywhere else in the payload finds it stays in the database.

The push is built from the same stored row the feed renders, so the line on the lock screen and the line in
the list can never tell different stories about one event. `tag` is the entity id where the writer supplies
one, so three gate attempts for one visitor collapse into one notification; without one it is the notification
id, which is unique and therefore never coalesces — wrongly merging two complaints loses a notification, while
wrongly showing two lines costs a scroll.

| Route | Body | Notes |
|---|---|---|
| `GET /push/vapid-key` | — | `{ publicKey }`. Public by construction, still behind a membership guard: an unauthenticated endpoint naming our key is free reconnaissance for no benefit |
| `POST /push/subscriptions` | `PushSubscription.toJSON()` — `{ endpoint, keys: { p256dh, auth }, userAgent? }` | Idempotent on `endpoint`. A repeat is `200`, not `409`: the client is describing a state |
| `POST /push/subscriptions/unregister` | `{ endpoint }` | Always `200`, even when the row had already gone |

**The browser's own document is accepted unchanged.** A transcription step between `PushSubscription.toJSON()`
and our field names is somewhere to put `auth` into the `p256dh` field, and that failure looks like a push
that silently never decrypts.

**Removal takes a body, and is therefore a `POST` to a sub-path rather than a `DELETE`.** A push endpoint URL
is a device identifier, and a request whose whole purpose is to stop tracking a device should not write it
into every access log between here and the browser — which rules out both a query string and a path segment,
and leaves a body. RFC 9110 then leaves content on a `DELETE` with no defined semantics: clients may decline
to send it, intermediaries may strip it, and OpenAPI tooling warns on it. So the body travels on the one
method that guarantees it arrives. This was the second path the original note named as the remedy; it is now
taken, and `_check_request_bodies` in `scripts/export_openapi.py` fails the build if any operation
reintroduces the pattern.

**A client must re-read `GET /push/vapid-key` on load and compare it against the `applicationServerKey` its
stored subscription was created with.** A subscription is bound to the key that created it, the protocol
offers no dual-key period, and a rotation therefore stops push permanently and *silently* — no error anywhere,
pushes simply stop arriving.

| Status | When |
|---|---|
| `200` | Key returned, or subscription registered/removed |
| `401` / `403` | No session; no active membership, or a failed CSRF pair |
| `422` | The subscription document is missing an endpoint or a key |
| `503` `push_not_configured` | This server has no VAPID keypair. Only `GET /push/vapid-key` and `POST /push/subscriptions` |

**Fail closed, but do not fail loudly.** An environment with no keypair returns `503` on those two routes, the
sender never starts, and **everything else in the product works normally** — including `DELETE`, because
turning notifications off must not depend on an operator not having lost a key. Push is an enhancement; an
unconfigured environment must not be a broken environment.

> **This ships backend-complete and unverifiable end to end.** Nothing in `frontend/public/` is a service
> worker, no manifest exists, and no resident page opens a connection of any kind — so no push can be
> *observed* arriving yet. The backend tests cover registration and idempotency, payload construction, the
> `410`-prunes-the-subscription rule and the claim's at-most-once behaviour, with the call to the push service
> mocked. That is honest coverage of this half and should not be described as more. What the frontend must add
> is listed in `RESIDENT_BACKEND_DESIGN.md` §10.6.

## 6. People

**Also intentionally empty**, for the same reason: `GET /admins` is served by the snapshot's `users[]`, which
carries `role` and lets the page filter client-side, and the registration trio duplicated their
`/admin/access-requests` endpoints that the frontend already calls.

The one addition that came out of this area, `POST /admins`, is documented in **[§12](#12-notices-and-administrator-promotion)**
alongside `POST /notices` — both were added together because both served a frontend handler with no endpoint
anywhere.

## 7. Complaints

Reads and comments are open to **any member** of the community — a resident must be able to follow and
discuss their own complaint. Editing is **admin-only**.

Backed by migrations `0020` (the timeline and the two admin writes) and `0031` (the resident's
columns, the SLA rule, the six resident operations, and the notification every complaint write now
emits).

> **Every write in this section notifies somebody.** A status change reaches the resident who raised
> the complaint; raising, reopening, confirming and a resident's own comment reach the community's
> admins and managers. The notification is written **inside the same transaction** as the change that
> caused it, in the RPC rather than in this API, so there is no path that changes a complaint without
> telling anyone — including the paths this API does not own. See §5.2 for how it is delivered.

### The two vocabularies

The database column is `priority`; the form field is `urgency`. Neither side is renamed —
`domain/vocabularies.py` translates, as it does for every other pair.

`status` on the wire is `Pending` | `In Progress` | `Resolved` | `Cancelled`. The stored enum has six
members, and the mapping is deliberately **not** a round trip: `closed` renders as `Resolved`, because
the frontend's select has three options and closed is not one of them. What `closed` means is in
`POST /complaints/{id}/resolution` below.

### `PATCH /api/v1/complaints/{complaintId}`

Update a complaint. **Requires `ADMIN`.** Partial — omitted fields are unchanged.

**Request**
```json
{
  "status": "In Progress",
  "assignee": "Suresh - Electrician",
  "progress": 40,
  "expectedResolutionAt": "2026-07-11T12:00:00+00:00",
  "updateNote": "Electrician scheduled for tomorrow morning."
}
```

**200** — `{ "message": "Complaint updated." }`

The edit **and its timeline entries are written in one transaction**, so a status can never change
without leaving a trace — an audit trail with holes is worse than none, because it looks complete.
`updateNote` writes a resident-visible timeline entry **even when nothing else changes**; it is the
admin's "Resident-visible Update" box.

Resolving stamps `resolvedAt`; moving off `Resolved` clears it, so a reopened complaint does not keep
claiming it was resolved.

| Status | Code | Cause |
|---|---|---|
| `403` | `forbidden` | Not an admin, or the complaint belongs to another community |
| `404` | `not_found` | No such complaint |
| `409` | `conflict` | Unknown status reached the database |
| `422` | `unknown_status` | `status` is not one of the three |

### `POST /api/v1/complaints/{complaintId}/comments`

Add a comment. **Any member.** `201 Created`.

**Request** — `{ "message": "Plumber will visit at 4pm.", "visibility": "resident" }`

`visibility` is `resident` (default, visible to the resident and on the timeline) or `internal`
(**admins only**, never returned to a resident).

> **Correction.** This section previously said an internal comment is "never written to the
> timeline". It is — `0020` writes a `comment_added` event for every comment, because the timeline it
> was written for is admin-facing, and the policy on `complaint_events` scopes rows to the complaint
> rather than to a comment's visibility. So the *event* did reach the resident even though the
> *comment* did not, which would have put a row on their timeline saying something was said and
> refusing to say what. `GET /complaints/{id}` drops those events; the comment itself was never
> reachable.

A public comment notifies the other party — the resident if an admin wrote it, the community's admins
and managers if the resident did. An **internal comment notifies nobody**, for the same reason it
leaves no timeline row.

| Status | Code | Cause |
|---|---|---|
| `403` | `forbidden` | Not a member, or a non-admin asked for `internal` |
| `404` | `not_found` | No such complaint |
| `409` | `conflict` | Empty message, or unknown visibility |

### `GET /api/v1/complaints`

The caller's **own** complaints, newest first. **Requires an active membership** — any role.

**Always the caller's own, whatever their role.** An admin calling this gets the complaints they
personally raised, not the community queue; that is `GET /dashboard/snapshot`. One route that returns
a resident's list to one caller and the whole association's to another is the shape
`RESIDENT_BACKEND_DESIGN.md` §5.1 exists to prevent.

| Query | Notes |
|---|---|
| `status` | `Pending` \| `In Progress` \| `Resolved` \| `Cancelled`. **Unrecognised is `422`, not an empty page** — a filter typo must not be indistinguishable from *you have no resolved complaints*. Matches on what a complaint **displays as**, not on one stored value: `Resolved` covers `resolved` and `closed`, `In Progress` covers `acknowledged` and `in_progress`. Stored words are not accepted — `?status=Closed` is a `422`, because it is a caller guessing at a vocabulary this API does not speak |
| `category` | Exact match |
| `unread` | Only complaints changed since the caller last opened them |
| `page`, `pageSize` | `pageSize` ≤ 100, default 20 |

| Response field | Notes |
|---|---|
| `id`, `title`, `category`, `location` | Null text reads as `""`; a missing `category` reads as `General` |
| `status` | The four wire values above |
| `urgency` | `High` \| `Medium` \| `Low`. The column is `priority` |
| `progress` | `0`–`100`, the admin's slider |
| `assignee` | The label recorded on the complaint, or `Unassigned`. **Not** a membership id — a resident shown one learns an identifier they have no endpoint for |
| `expectedResolutionAt` | Computed on insert from `urgency`. See `POST /complaints` |
| `isOverdue` | Past `expectedResolutionAt` and not resolved. **Computed in the database**, against the same clock the admin's overdue count uses, so the two screens cannot disagree about one complaint |
| `isUnread` | Per-caller, from `complaint_read_state`. Cleared by `POST /complaints/{id}/read` |
| `reopenedCount`, `commentCount`, `lastActivityAt`, `createdAt`, `updatedAt`, `resolvedAt` | |

### `POST /api/v1/complaints`

Raise a complaint. **Requires an active membership.** `201 Created`, and the body is the complaint as
`GET /complaints/{id}` would return it.

**Request**
```json
{
  "title": "Lift stuck between floors",
  "description": "The B-block lift has been stopping between 3 and 4.",
  "category": "Elevator",
  "urgency": "High",
  "location": "B Block"
}
```

> **`expectedResolutionAt` is not accepted.** High → 24h, Medium → 48h, Low → 72h, applied by the
> database on insert. The rule used to live in `createComplaintsSlice.js`, where a resident could have
> sent themselves a one-minute deadline and where the admin portal could not see it at all. The
> admin's `dueAt` is set to the same instant, so the resident's expectation and the association's
> deadline start out as one number rather than two formulas.

The response is the created complaint rather than an acknowledgement, because the SLA deadline is the
one thing the client could not have computed and is exactly what it is about to display.

**Attachments are not accepted yet.** The form collects them, `media` exists in the schema, and no
upload endpoint does — so this endpoint takes what it can honour rather than accepting data it drops.
Tracked in §15.

Raising notifies every active admin and manager of the community.

| Status | Code | Cause |
|---|---|---|
| `422` | `unknown_urgency` | Not `High`, `Medium` or `Low`. **Not defaulted** — a silent fallback would file the complaint under a deadline the resident did not choose |
| `422` | — | Empty or whitespace-only `title` or `category` |

### `GET /api/v1/complaints/{complaintId}`

One complaint with its timeline and public comment thread. **Requires an active membership**, and it
must be the caller's own complaint.

A complaint that exists but belongs to somebody else is a **`404`, identical to one that does not
exist**. The lookup filters on the membership rather than checking afterwards, so there is no code
path in which the two could be told apart.

Adds `description`, `resolutionRating`, `residentFeedback`, `timeline[]`, `comments[]`,
`hasOlderEvents` and `hasOlderComments` to the list row's fields. A timeline entry is
`{ id, type, label, actor, message, createdAt }`; `actor` is the label recorded **at the time of the
event**, not a lookup of what that person is called today. `type` is the raw event type, for a client
choosing an icon; `label` is the heading a human reads, and an unrecognised type falls back to the
type itself rather than vanishing from the history.

> **The timeline and the thread are bounded at 200, and the bound keeps the recent end.** Reading
> them oldest-first and stopping at 200 would keep the *opening* of a long-running complaint and
> discard everything since — on the one screen where the bound could ever bite, exactly inverted, and
> silent about it. Both are read newest-first and reversed for display. `hasOlderEvents` and
> `hasOlderComments` are **measured, not assumed**: a bounded read that reports completeness it never
> checked is the one kind of truncation a client cannot detect for itself. No endpoint serves the
> older entries yet, so today they mean *say earlier history is not shown*, not *offer a button*.

### `POST /api/v1/complaints/{complaintId}/reopen`

Send a resolved complaint back. **Requires `RESIDENT`**, and it must be their own complaint.

**Request** — `{ "reason": "The lift stopped again the same evening." }`

The reason is required by the model *and* by the database: a complaint that comes back with no
statement of what is still wrong gives the association the same row again and no new information.

**The SLA clock restarts from now**, because a reopened complaint carrying its original deadline would
be overdue the instant it reopened — a failure nobody committed. Any `resolutionRating` and
`residentFeedback` are cleared; they described a resolution that is no longer being claimed.

Notifies the community's admins and managers. Returns the complaint.

> **A complaint the resident already confirmed can still be reopened.** Both `resolved` and `closed`
> display as `Resolved`, so from their side it is one state and it behaves as one. `/resolution` is
> the asymmetric half: it accepts only a complaint the association has resolved and the resident has
> not yet answered. Two complaints can therefore both read `Resolved` while only one offers *confirm*
> — the client should key that button off `resolvedAt` with no `resolutionRating`, not off `status`.
> Not from `Cancelled`: the other two are the association saying the work is done, which is a claim a
> resident may disagree with, while a cancelled complaint was withdrawn and reopening it is filing it
> again.

| Status | Code | Cause |
|---|---|---|
| `403` | `community_role_required` | Not a resident |
| `403` | `insufficient_privilege` | Not the resident who raised it |
| `404` | `not_found` | No such complaint |
| `422` | `check_violation` | Not currently resolved, or an empty reason |

### `POST /api/v1/complaints/{complaintId}/resolution`

Accept the resolution and rate it. **Requires `RESIDENT`**, and it must be their own complaint.

**Request** — `{ "rating": 4, "feedback": "Fixed, though it took two visits." }`

> **`Resolved` is what the association says; closed is what the resident agrees.** The baseline's enum
> has carried both since the beginning and nothing has used the distinction — `PATCH /complaints/{id}`
> treats them as one terminal state. This is the only endpoint that closes a complaint.

The rating is required and must be 1–5; the feedback is optional. A rating with no comment is a
complete answer; a comment with no rating is not what `US-2.6` asks for. Returns the complaint.

| Status | Code | Cause |
|---|---|---|
| `422` | — | `rating` outside 1–5 |
| `422` | `check_violation` | The complaint is not `Resolved` |

### `POST /api/v1/complaints/{complaintId}/read`

Clear the unread marker. **Requires an active membership.** `200`, idempotent, and a `200` whether or
not a marker was there to clear.

Per membership, so an admin opening a complaint cannot clear the resident's marker.
`complaint_read_state` has been in the schema since the baseline with nothing writing to it; this is
the writer, and `isUnread` is what it turns off.

`complaint_overview` reads the marker belonging to **whoever is asking**, not to whoever raised the
complaint. Those are the same row on the only surface that reads the view today and stop being the
same row the moment anything else does — a view keyed to the raiser would quietly ignore every marker
this endpoint wrote for anybody else.

## 8. Departments and staff

Backed by migration `0014`. Two read views do the counting; every multi-table write is an RPC.

**Complaints belonging to a department are not served here** — `GET /api/v1/complaints?departmentId=…`
(§7) already returns them in the shape the department detail screen renders. A second endpoint
returning the same rows is a second thing to keep correct.

### `GET /api/v1/departments`

Page through departments, each with its roster. **Requires `ADMIN`.**

| Query | Type | Default | Notes |
|---|---|---|---|
| `q` | string ≤ 100 | — | Matches name, description, head, contact email, **category names and staff names** |
| `status` | string | — | `Active` \| `Inactive`. Omit for both |
| `page` | integer | `1` | ≥ 1 |
| `pageSize` | integer | `20` | 1–100 |

**200**
```json
{
  "items": [
    {
      "id": "2f8a...",
      "name": "Plumbing & Water",
      "description": "Handles water supply, drainage, leakage, and plumbing repairs.",
      "categories": ["Plumbing"],
      "categoryIds": ["9c1d..."],
      "head": "Ramesh Kumar",
      "headStaffId": "51ab...",
      "email": "plumbing@homebandhu.local",
      "phone": "+91 98765 41001",
      "operatingHours": { "start": "08:00", "end": "20:00" },
      "slaHours": 24,
      "kind": "service",
      "status": "Active",
      "staffCount": 2,
      "activeComplaintCount": 3,
      "resolvedComplaintCount": 11,
      "overdueComplaintCount": 1,
      "createdAt": "2026-07-01T09:00:00+00:00",
      "updatedAt": "2026-07-01T09:00:00+00:00",
      "staff": [
        {
          "id": "51ab...",
          "name": "Ramesh Kumar",
          "phone": "+91 98765 41001",
          "role": "Supervisor",
          "rank": "head",
          "shift": null,
          "status": "active",
          "membershipId": null,
          "activeAssignmentCount": 2
        }
      ]
    }
  ],
  "total": 4, "page": 1, "pageSize": 20, "hasMore": false
}
```

**The roster is embedded, not behind a second request.** The dashboard seeds its edit modal straight
from the list row, so splitting them would make one screen render N+1 requests from a client we
cannot change. It costs one extra query per page, not one per department.

**`status` is `Active` / `Inactive` on the wire and `active` / `archived` in the column.** Both
vocabularies have exactly two values, so the mapping is lossless in both directions. Whether the
column should simply say `inactive` is `DECISIONS_NEEDED.md` D5.

`rank` (`member` \| `supervisor` \| `head`) and `role` (`"Technician"`, `"Manager"`) are **separate
fields on purpose.** The seed data proves they are not a function of each other: two departments'
heads render as `Supervisor` and `Manager`. Any derivation rule would silently rewrite one of them.

`activeAssignmentCount` counts open complaints held by that member **within that department**, which
is what the detail screen shows.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |
| `422` | `request_validation_error` | `page` < 1, `pageSize` out of 1–100 |

### `POST /api/v1/departments`

Create a department, its category claims, its roster and its head — **in one transaction.**
**Requires `ADMIN`.** `201 Created`.

**Request**
```json
{
  "name": "Plumbing & Water",
  "description": "Handles water supply, drainage, leakage, and plumbing repairs.",
  "categories": ["Plumbing", "Leaking pipes"],
  "head": "Ramesh Kumar",
  "email": "plumbing@homebandhu.local",
  "phone": "+91 98765 41001",
  "operatingHours": { "start": "08:00", "end": "20:00" },
  "slaHours": 24,
  "kind": "service",
  "status": "Active",
  "staff": [
    { "name": "Ramesh Kumar", "phone": "+91 98765 41001", "role": "Supervisor" },
    { "name": "Mohan Das", "phone": "+91 98765 41002", "role": "Technician" }
  ]
}
```

**200 body shape** — the created `DepartmentDetail`, identical to one item of the list above.

**`categories` are names, and unknown names are created.** The two create screens disagree: the
dashboard modal offers a fixed checkbox list of six, while `CreateDepartment.jsx` is a free-text box
whose placeholder is *"e.g. Leaking pipes"* — a symptom, not a category. Rejecting unknown names
would break one screen; upserting them keeps both working, at the cost of letting a typo become a
category. Raised as `DECISIONS_NEEDED.md` B9.

**`head` is a name, and naming one promotes a staff row.** If the name matches somebody on the
roster, that person's `rank` becomes `head` and the previous head is demoted in the same
transaction; if it matches nobody, a roster entry is created for them. One source of truth for who
leads a department, and the frontend's free-text field still round-trips exactly.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `409` | `conflict` | A department with that name already exists in the community |
| `422` | `request_validation_error` | Missing `name`, `slaHours` ≤ 0, `operatingHours` not `HH:MM`, unknown `kind`, unknown `shift` |

### `GET /api/v1/departments/{departmentId}`

One department with its **active** roster. **Requires `ADMIN`.** Body as above.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such department in the caller's community |

### `PATCH /api/v1/departments/{departmentId}`

Partial update. **Requires `ADMIN`.** Omitted fields are left unchanged; an explicit `null` clears one.

```json
{ "slaHours": 12, "status": "Inactive", "categories": ["Plumbing"] }
```

**200** — the department as it now stands.

Two fields have **collection semantics**: sending `categories` replaces the claim set, and sending
`staff` replaces the roster (identical to `PUT …/staff` below). Omitting either leaves it untouched.

> **Deactivating is not blocked by open complaints.** Only `DELETE` is. The dashboard offers
> deactivation *as the escape hatch* when deletion is refused, so guarding both would leave an admin
> with a stuck department and no action available. This corrects the build plan, which had the guard
> on archiving.

Archiving a department also removes it from complaint routing, so **new** complaints in its
categories go elsewhere. Complaints already assigned to it keep pointing at it.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such department, or a `staff[].id` belongs to another department |
| `409` | `conflict` | The new name is already taken, or `name` was sent empty |
| `422` | `request_validation_error` | Bad `operatingHours`, `slaHours` ≤ 0, unknown `status` |

### `DELETE /api/v1/departments/{departmentId}`

Permanently remove a department. **Requires `ADMIN`.**

**200** — `{ "message": "Department deleted." }`

> ⚠️ **This one really is a delete**, unlike `DELETE /residents/{id}`. Category claims and the staff
> directory go with it. Complaint records survive with their `departmentId` cleared — which is
> exactly what the confirmation dialog promises the admin.

The open-complaint count is taken **inside the deleting transaction**, so a complaint raised between
the check and the delete cannot slip through.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such department |
| `409` | `conflict` | **The department owns open complaints.** Message carries the count. Resolve, reassign, or deactivate instead |

### `PUT /api/v1/departments/{departmentId}/staff`

Replace the whole roster, as the department form submits it. **Requires `ADMIN`.**

**Request**
```json
{ "staff": [
    { "id": "51ab...", "name": "Ramesh Kumar", "role": "Supervisor" },
    { "name": "New Hire", "phone": "+91 98765 41009", "role": "Technician" }
] }
```

**200** — the resulting roster, as an array of staff objects.

Entries carrying an `id` are updated in place; entries without one are added; **active members the
payload omits are deactivated, not deleted.** A complaint's `assignee` records staff by name, so
removing the row would turn a past assignment into an unattributable string.

`PUT` rather than `POST` because this replaces a collection — sending the same roster twice leaves
the same result.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such department, or an `id` belongs to a different department |
| `422` | `request_validation_error` | An entry has an empty `name`, or an unknown `shift` / `status` |

### `POST /api/v1/departments/{departmentId}/staff`

Add one person. **Requires `ADMIN`.** `201 Created`, body = the created staff object.

```json
{ "name": "Mohan Das", "phone": "+91 98765 41002", "role": "Technician", "shift": "Day" }
```

**A staff member needs no account.** `name` is the only required field, matching what the department
form actually collects; `membershipId` stays `null` until someone links them to a profile.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such department |
| `422` | `request_validation_error` | Empty `name`, unknown `shift` (`Day` \| `Evening` \| `Night`) or `status` |

### `PATCH /api/v1/departments/{departmentId}/staff/{staffId}`

Patch one roster entry. **Requires `ADMIN`.** `200`, body = the updated staff object.

```json
{ "role": "Supervisor", "shift": "Evening" }
```

`rank` is **not** patchable here. A department has at most one head, and promoting somebody must
demote the incumbent in the same transaction — `PATCH /departments/{id}` with a `head` name is the
only path that does.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such staff member in the caller's community |
| `422` | `request_validation_error` | The member belongs to a different department (`wrong_department`), or an unknown `shift` / `status` |

### `DELETE /api/v1/departments/{departmentId}/staff/{staffId}`

Take a member off the active roster. **Requires `ADMIN`.**

**200** — `{ "message": "Staff member removed." }`

> ⚠️ **Deactivation, not deletion** — same reasoning as `PUT …/staff` above. Removing the head also
> frees the head slot in the same statement, so the next promotion is unobstructed.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such staff member |
| `422` | `request_validation_error` | The member belongs to a different department |

## 9. Money — invoices and payments

Backed by migration `0015`. Three read views do the aggregating; every write is an RPC, because
issuing an invoice touches three tables and a counter and recording a payment recomputes a balance.

**The unit is the debtor.** `invoices.unitId` is not null and there is no membership foreign key: a
resident who moves out does not take the flat's arrears with them, and a new occupant does not get a
clean slate by moving in. `userId` on an invoice is the flat's **current** occupant, resolved at read
time so the collections table can render a name. It is a display field, not what the debt hangs from.

**Amounts are JSON numbers, deliberately.** The dashboard does
`payments.reduce((a, c) => a + c.amount, 0)`. A JSON string would concatenate into `"42504250"` and
render as a plausible rupee total with nothing in the console to say so. Every total the API reports
is computed by Postgres in `numeric` and read back — nothing is summed in Python.

**Nothing is ever deleted.** There is no `DELETE` in this section. `POST /invoices/{id}/void` marks
an invoice cancelled and leaves it, its lines and its number in place; an invoice number that
disappears is a gap somebody has to account for later.

### `POST /api/v1/invoices`

Issue one invoice against one flat. **Requires `ADMIN`.**

```json
{
  "title": "Clubhouse Event Charge",
  "flat": "B-1204",
  "invoiceType": "misc",
  "lineItems": [
    { "description": "Clubhouse hall — 4 hours", "quantity": 4, "unitAmount": 125 }
  ],
  "dueDate": "2026-08-05",
  "taxPercent": 0,
  "notes": null
}
```

The invoice, its line items and its number are written **in one transaction**, and the totals are
computed from the lines — so a header that disagrees with its own contents cannot be submitted.

The flat is identified by `unitId` **or** by `flat` (`B-1204`, normalised the same way registration
approval normalises it) and is **created on first reference**, because the product has never had a
flat-creation step.

The invoice number comes from a per-community counter consumed under a row lock:
`INV-2026-00001`. It is **unique per community, not globally** — the ERD says globally, but the
prefix defaults to `INV` for everyone, so a global constraint would stop the second community from
issuing its first invoice.

**201** — the created invoice, in the `GET /invoices/{id}` shape.

| Status | Code | Cause |
|---|---|---|
| `400` | `unit_required` | Neither `unitId` nor `flat` supplied |
| `400` | `invalid_invoice_type` | `invoiceType` outside the four values |
| `401` / `403` | | Not authenticated / not an admin / flat in another community |
| `404` | `not_found` | The flat could not be resolved |
| `409` | `conflict` | Lines total zero, or `dueDate` precedes `issuedOn` |
| `422` | `request_validation_error` | Empty `lineItems`, `unitAmount` ≤ 0, `title` missing |

### `POST /api/v1/invoices/{invoiceId}/payments`

Record money received against an invoice. **Requires `ADMIN`.**

```json
{
  "amount": 4250,
  "method": "Net Banking",
  "reference": "TXN-88213",
  "payerProfileId": "0c47...",
  "paidAt": "2026-07-10T06:12:00+00:00",
  "notes": null
}
```

**Idempotent on `reference`.** Sending the same reference twice returns the payment already recorded
rather than crediting the invoice again, so a retried gateway webhook or a double-tapped Pay button
cannot settle a bill twice. This is checked in the RPC *and* enforced by a unique index, so it holds
under concurrency as well as under retry.

`method` accepts the display strings the frontend already writes — `UPI`, `Credit Card`,
`Net Banking`, `Cash`, `Cheque`, `Bank Transfer` — and stores the ERD vocabulary underneath. This
mapping is a true round trip in both directions.

The payment, its audit event and the recomputed invoice balance are one transaction. The balance is
**recomputed from the payment rows**, not decremented, so a later correction cannot leave it drifting.

**201** — the invoice as it now stands, not the payment. The caller's next question is always
"is it settled now", and answering it here saves a second request.

| Status | Code | Cause |
|---|---|---|
| `400` | `invalid_payment_method` | `method` outside the six values |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such invoice |
| `409` | `conflict` | Amount exceeds the outstanding balance, or the invoice is void |
| `422` | `request_validation_error` | `amount` ≤ 0 |

**Overpayment is refused, not absorbed.** Clamping it would accept the money and then lose it, which
is the worst available outcome; a `409` at least tells the admin the two numbers disagree.

### `GET /api/v1/billing-settings`

The community's billing configuration. **Requires `ADMIN`.**

**200**
```json
{
  "communityId": "3c6e...",
  "currency": "INR",
  "invoiceNumberPrefix": "INV",
  "defaultMaintenanceAmount": null,
  "maintenanceDueDay": 15,
  "defaultTaxPercent": 0.0,
  "autoBillingEnabled": false,
  "autoBillingDay": 1,
  "lateFeeEnabled": false,
  "lateFeeAmount": null,
  "lateFeeGraceDays": 10,
  "lateFeePeriod": "weekly",
  "updatedAt": "2026-07-29T18:00:00+00:00"
}
```

The last six fields were added by build step 9 (`0017`) and are the two switches the
**Settings** screen draws, plus the numbers they need. They are readable here and again at
`GET /settings` (§11); this is their only writer. See §11 for what does and does not act on them —
the short version is **nothing runs billing on a schedule and nothing charges a late fee**.

**`defaultMaintenanceAmount` is `null` until an admin sets one, and there is nothing to migrate from.**
The maintenance amount does not exist anywhere in this product: `createPendingRequestsSlice.js`
hardcodes `4250` in the middle of an approval handler, `data/payments.js` repeats it, no screen
configures it, and the ERD has no rate field either. This is agenda item 12.

A community that has never saved settings gets the defaults back with `200` rather than a `404` — the
row is created lazily on first write, and a screen asking what the settings are should not have to
know that.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

### `PUT /api/v1/billing-settings`

Patch the billing configuration. Omitted fields are left unchanged. **Requires `ADMIN`.**

```json
{ "defaultMaintenanceAmount": 4250, "maintenanceDueDay": 15, "invoiceNumberPrefix": "HB" }
```

Every field of the `GET` response except `communityId` and `updatedAt` is writable and optional:
`currency`, `invoiceNumberPrefix`, `defaultMaintenanceAmount`, `maintenanceDueDay`,
`defaultTaxPercent`, `autoBillingEnabled`, `autoBillingDay`, `lateFeeEnabled`, `lateFeeAmount`,
`lateFeeGraceDays`, `lateFeePeriod`.

**Two switches cannot be turned on without the number they act on, and the database is what
refuses.** `autoBillingEnabled: true` with `defaultMaintenanceAmount` still null is a `409`, and so is
`lateFeeEnabled: true` without a `lateFeeAmount` above zero. Both can be sent in one request —
`{ "lateFeeEnabled": true, "lateFeeAmount": 100 }` succeeds — and either can be turned **off** at any
time regardless of the amounts. A toggle that says "on" while the thing it switches on has no rate is
a lie a screen will happily draw, so it is prevented one layer below the API rather than in a
validator that a second writer could skip.

`lateFeePeriod` is one of `weekly`, `monthly`, `once`. `one-time` is also accepted for `once`, because
that is the phrase the screen uses. The response echoes the stored value and `GET /settings` adds a
`lateFeePeriodLabel` for rendering.

**Sending `defaultMaintenanceAmount: null` clears the rate** and stops billing runs until one is set
again — distinct from omitting the field, which leaves it as it was. Key presence is what
distinguishes them, matching the pattern used by the department patch.

`invoiceNumberPrefix` affects only numbers issued from now on. Invoices already issued keep the
number they were given, because a number that changes is not an identifier.

`maintenanceDueDay` is capped at **28** so a due day never lands outside February. A community
wanting month-end passes an explicit `dueDate` to the billing run.

**200** — the settings as they now stand.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `409` | `conflict` | `autoBillingEnabled: true` with no `defaultMaintenanceAmount`, or `lateFeeEnabled: true` with no `lateFeeAmount` above zero |
| `422` | `validation_error` | `lateFeePeriod` outside `weekly` / `monthly` / `once` |
| `422` | `request_validation_error` | `maintenanceDueDay` outside 1–28, `autoBillingDay` outside 1–28, `lateFeeAmount` negative, `lateFeeGraceDays` outside 0–90, prefix with spaces or slashes, `defaultTaxPercent` ≥ 100 |

---

## 10. Amenities — catalogue, bookings, ledger

Backed by migration `0016`. Four read views do the aggregating; every write is an RPC, because a
booking request writes a series, its occurrences, its guests and its charges, and PostgREST has no
client-side transaction.

**The largest surface in the product, and the one that needed the least translation.**
`bookingStatuses.js`, `ledgerStatuses.js` and `bookingTimelineStates.js` already separate the machine
value from its label — the frontend stores `pending` and renders `BOOKING_STATUS_LABELS[pending]`. So
booking status, ledger payment status, booking type and cancellation reason codes pass through
unchanged. Only three vocabularies differ: `bookingMode` (`Shared` on the wire, `shared` stored),
amenity `status` (`Active`/`Inactive`), and weekdays (`Monday` on the wire, ISO day `1` stored, so
the booking rules can be evaluated in SQL without depending on the server's locale).

**Approval belongs to the request, not to the day.** `createResidentAmenityBookingSeries` creates one
booking record per date, and `approveAmenityBookingRequest` approves one of them — so a three-day
request appears in the approvals table three times and can be approved on Monday and rejected on
Tuesday. `GET /amenities/{id}/approvals` returns **one row per request**, carrying its first day plus
`dayCount` and `dates`. One click decides the whole request. The frontend does not render `dayCount`
yet, which is agenda item 16.

**Overlap is guarded by the database, in two places.** An `EXCLUDE USING gist` constraint catches
exclusive-vs-exclusive; a `BEFORE` trigger holding an advisory lock on the amenity catches everything
an exclusion predicate cannot express — exclusive-vs-shared, and capacity. No availability check
happens in the API, because a check-then-act in the service layer loses the race between two
residents booking the last place.

**The cleaning buffer does not block shared bookings here.** In the frontend it does, in every mode —
which means a shared amenity with a non-zero buffer accepts exactly one booking at a time and its
`capacity` of 24 can never be reached. The seeded gym hides this because no two of its bookings
overlap. Here the buffer applies only between uses that occupy the amenity exclusively. **This is a
deliberate behavioural difference from the demo** — `DECISIONS_NEEDED.md` E17 and agenda item 15.

**Four things the frontend stores are derived here:** `pendingRequests` and `outstandingDues` on the
amenity card (both stored as constants in the mock, both already wrong there), `paymentStatus` on the
ledger row, and the `completed` booking status — which means "approved and in the past", a fact about
the clock.

**Amounts are JSON numbers**, for the same reason as §9: the ledger reduces over them in the browser.
Every figure is computed by Postgres in `numeric`, including the reports page's KPIs.

**Nothing is ever deleted except an amenity nobody has booked.** `DELETE /amenities/{id}` returns
`409` the moment anything has been booked on it, because the cascade would take the bookings, their
charges and their financial events with it — including deposits residents are still owed.

### `GET /api/v1/amenities/available`

The bookable catalogue. **Requires an active membership** — any role, not `resident` only, because
nothing in the response is per-resident and a security guard asking what facilities exist is a
reasonable question to answer.

**This is the read that makes `POST /amenities/{id}/bookings/request` usable.** That write has never
been admin-guarded — it was written for residents and its docstring says so — but until this endpoint
the catalogue reached a client exactly once, inside `GET /dashboard/snapshot`, which is guarded by
`ADMIN`/`MANAGER`. The result was a write path a resident could legitimately call with an argument
they had no legitimate way to obtain. See `docs/design/RESIDENT_BACKEND_DESIGN.md` §3.1.

> **"Available" means bookable in principle, not free right now.** Every amenity in the response
> exists, is active, and has no temporary closure recorded against it. It does **not** mean a slot is
> open. Whether a particular slot is free is decided on write, under an advisory lock, by the booking
> guard — a read endpoint that answered it would be describing a moment already in the past by the
> time the resident submitted the form. This is the same rule the rest of §10 follows: *no
> availability check happens in the API.*

**The community comes from the caller's membership**, resolved from Postgres by
`get_active_membership`. There is no community parameter, so there is nothing to tamper with. This
matters more here than elsewhere: `amenities` carries no RLS policy of its own, so the view below
runs as the caller and inherits nothing, and that one filter is the whole tenancy boundary — which is
why it is applied in the query rather than after the fetch.

**This is a different projection from the admin card, not a filtered one.** `AmenitySummary` carries
`pendingRequests` and `outstandingDues` — how many neighbours are waiting on this hall, and how much
the community is still owed against it. `BookableAmenity` is a separate model that has no such
fields, so the resident response cannot grow one by someone adding a column to the admin view. The
query reads its own view, `bookable_amenity` (migration `0029`), rather than `amenity_overview` — two
views over one table, each owned by the surface that reads it. Sharing the admin's would leave the
resident response one column away from an admin field, since the next column added there for the
admin card is in scope here the moment it is added; it would also compute two lateral aggregates per
row that this response discards.

`bookable_amenity` applies the row filter as well as the column list — active, and no temporary
closure — so *bookable* is defined in one place rather than assembled by whoever writes the query.

| Response field | Notes |
|---|---|
| `id`, `name`, `description`, `category`, `location`, `image` | Null text reads as `""`; a missing `category` reads as `Utility` |
| `capacity` | `null` when the amenity sets none. `0` is normalised to `null` |
| `bookingMode` | `Shared` \| `Exclusive` \| `Hybrid` |
| `requiresApproval` | Whether a request lands pending rather than confirmed. Surfaced so the form can say so before submitting |
| `openingTime`, `closingTime` | `HH:MM` wall-clock in the community's own time. `00:00` when unrecorded, never `null` |
| `slotDurationMinutes` | Falls back to `60`. The one limit that is never `null`: a client divides the day by it |
| `minimumBookingDurationMinutes`, `maximumBookingDurationMinutes`, `advanceBookingWindowDays`, `maxActiveBookingsPerResident` | `null` means *this amenity sets no limit*, not *there is no limit* — the booking RPC still applies conflict and capacity rules on write |
| `closedDays` | Weekday names, e.g. `["Sunday"]`. Stored as ISO day numbers; out-of-range entries are dropped rather than rendered |
| `allowPrivateBooking`, `allowGuestBooking`, `allowRecurringBooking`, `allowSameDayBooking` | What the booking form may offer |
| `bookingFee`, `securityDeposit`, `currencyCode` | Two amounts, not a total: the deposit is coming back and the fee is not, and a resident shown one number cannot tell which is which |
| `refundPolicy` | Free text. `""` when unset |

There is no `status` field. Every row returned is active — the filter *is* the meaning, and a
`status` reading `Active` on every row is noise the client has to ignore.

**Unpaged.** `page` is always `1` and `pageSize` is the item count: an amenity catalogue is a fixed
list a client renders whole, and paging it would make the common case two round trips for nothing.
The `Page` envelope is kept anyway so every collection on this API has one shape (§1.6), and so
paging can be added later without changing the response type.

`hasMore` is `false` for any community this product will plausibly see, but it is **computed rather
than asserted**. The read is bounded at 500 rows so a pathological community cannot page the whole
view into memory, and that bound is asked for alongside an exact count. A `true` therefore means one
thing only — the catalogue has outgrown being unpaged and rows are being withheld — which a client
has no other way to detect. A bound that truncates while the envelope reports completeness is the
same defect as a page that lies about its total; it is only harder to notice.

| Code | Error | When |
|---|---|---|
| `401` | `authentication_error` | No session |
| `403` | `active_membership_required` | Authenticated, but no active membership in any community |

### `GET /api/v1/amenities/{amenityId}/bookings`

The day timeline. **Requires `ADMIN`.**

| Query | Type | Default | Notes |
|---|---|---|---|
| `date` | date | — | One day |
| `from` / `to` | date | — | A range |
| `timelineOnly` | boolean | `true` | Drop pending, rejected and cancelled days, matching `isTimelineVisibleBooking` |
| `page` | int ≥ 1 | `1` | |
| `pageSize` | int 1–200 | `50` | |

**200**
```json
{
  "items": [
    {
      "id": "9f3a…",
      "amenityId": "5c0b…",
      "amenityName": "Clubhouse Gym",
      "bookingSeriesId": "77c1…",
      "bookingGroupId": "77c1…",
      "residentId": "b41e…",
      "residentName": "Anita Rao",
      "residentFlat": "B-1204",
      "tower": "B",
      "unitId": "0a12…",
      "bookingTitle": "Resident Booking",
      "date": "2026-07-31",
      "startTime": "07:00",
      "endTime": "09:00",
      "state": "booked",
      "bookingType": "resident",
      "status": "confirmed",
      "source": "resident",
      "requiresApproval": false,
      "isPrivateBooking": false,
      "guestCount": 0,
      "guests": [],
      "notes": "Morning workout reservation.",
      "chargeOverride": null,
      "department": null,
      "dayCount": 1,
      "cancellationReason": null,
      "cancellationDetails": null,
      "cancelledAt": null,
      "cancelledByResident": false,
      "forceCancelled": false,
      "version": 1,
      "createdAt": "2026-07-30T06:00:00+00:00",
      "updatedAt": "2026-07-30T06:00:00+00:00"
    }
  ],
  "total": 4, "page": 1, "pageSize": 50, "hasMore": false
}
```

`state` is the timeline's vocabulary (`booked` | `blocked`); `status` is the lifecycle's. **The
cleaning buffer is not sent as a block** — the frontend synthesises buffers at render time from the
booking's end and the amenity's buffer (`amenityTimeline.createCleaningBuffers`), and sending them
too would give one block two sources.

`status` may read `completed` for a row stored as `approved`: a booking whose end time has passed is
completed, and storing that would need a scheduled job to keep it true.

`residentId` is the requester's **membership id** — what `GET /residents` returns as `id`, so
`users.find(u => u.id === booking.residentId)` resolves. `bookingGroupId` is the series id under the
name the frontend already groups by.

`chargeOverride: null` means "use the amenity's fee"; `0` means "free". They are different answers.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

### `POST /api/v1/amenities/{amenityId}/bookings`

The admin's Create Booking modal. **Requires `ADMIN`.**

```json
{
  "membershipId": "b41e…",
  "bookingTitle": "Kumar Party",
  "bookingType": "private-event",
  "date": "2026-08-02",
  "startTime": "10:00",
  "endTime": "13:00",
  "isPrivateBooking": true,
  "guestCount": 18,
  "guests": [{ "name": "Meera Shah", "phone": "+919876543210" }],
  "notes": "Birthday gathering.",
  "chargeOverride": 0
}
```

Confirmed on creation, never pending — an admin does not queue a booking for their own approval.

**The opening-hours, closed-day, advance-window and duration rules are deliberately not applied**,
matching the frontend: `createAmenityBooking` calls `assertSlotAvailable` and nothing else. An admin
booking the hall outside opening hours is doing their job. The conflict rules still apply.

The flat is resolved from the named resident's residency rather than sent, so the ledger charges a
unit that exists. `chargeOverride` replaces the booking fee and nothing else — a waived fee does not
waive the deposit, which is coming back.

**201** — the created booking.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | End time not after start, unknown booking type |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such amenity |
| `409` | `conflict` | The slot is taken or full; the resident has no active flat |

### `POST /api/v1/amenities/{amenityId}/bookings/request`

A resident asking for one or more days of the same slot. **Requires any authenticated resident.**

```json
{
  "bookingTitle": "Morning Fitness Session",
  "dates": ["2026-08-03", "2026-08-04"],
  "startTime": "10:00",
  "endTime": "11:00",
  "isPrivateBooking": false,
  "guestCount": 0,
  "guests": [],
  "notes": null
}
```

Exists in an admin-scoped build because the approvals tab is otherwise a screen that can never have
anything on it — the same argument §9 made for the invoice write endpoints.

**The flat is not a parameter.** It is read from the caller's own residency, so a resident cannot book
against somebody else's unit by editing the request. Whether the request needs approval is read from
the amenity's settings for the same reason: a client that could choose would be a client that could
opt out.

**Every day is validated before any is written**, so a multi-day request lands whole or not at all.

**201** — a `Page` of every day created, because telling the caller about one day of three is how a
resident is surprised by the other two.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | No dates, end time not after start |
| `401` | | Not authenticated |
| `403` | `forbidden` | The caller has no active residency in the community |
| `404` | `not_found` | No such amenity |
| `409` | `conflict` | Amenity inactive or closed that day; outside the advance window; same-day booking not allowed; duration outside the amenity's limits; guests not allowed; over the per-resident limit; multi-day not allowed; slot taken or full |

### `POST /api/v1/amenities/{amenityId}/blocks`

Reserve a slot administratively. **Requires `ADMIN`.**

```json
{
  "reason": "Deep clean",
  "date": "2026-08-05",
  "startTime": "14:00",
  "endTime": "16:00",
  "department": "Cleaning",
  "notes": "Reserved for administration."
}
```

**Always exclusive**, whatever the amenity's booking mode says: a hall closed for repairs is closed to
everybody. Carries no flat and no charges.

**201** — the created block, with `state: "blocked"` and no resident.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | Missing reason, end time not after start |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such amenity |
| `409` | `conflict` | The slot is taken |

### `GET /api/v1/amenities/{amenityId}/approvals`

The approvals tab — **one row per request, not per day**. **Requires `ADMIN`.**

| Query | Type | Default | Notes |
|---|---|---|---|
| `status` | string | `pending` | `pending` \| `approved` \| `rejected` \| `cancelled` \| `all` |
| `page` | int ≥ 1 | `1` | |
| `pageSize` | int 1–100 | `20` | |

**200** — every field of a booking, plus:
```json
{
  "dayCount": 3,
  "dates": ["2026-08-03", "2026-08-04", "2026-08-05"],
  "outstandingDues": 4250.0,
  "requestedAt": "2026-07-30T09:05:00+00:00",
  "approvedAt": null,
  "rejectedAt": null,
  "rejectionReason": null,
  "rejectionReasonCode": null
}
```

**`outstandingDues` is the flat's balance, not the person's.** The frontend computes it per `userId`
from the maintenance invoices; our invoices attach to the unit and carry no person. Same label,
different number — `DECISIONS_NEEDED.md` E18.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | Unknown `status` |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

### `POST /api/v1/amenity-bookings/{seriesId}/approve`

Approve a whole request — every day of it. **Requires `ADMIN`.**

No body. Days the resident already withdrew keep their cancellation: approving should not resurrect a
day somebody said they no longer wanted.

**200** — a `Page` of the request's days.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such request |
| `409` | `conflict` | Already decided |

### `POST /api/v1/amenity-bookings/{seriesId}/reject`

Reject a whole request and release its slots. **Requires `ADMIN`.**

```json
{ "reasonCode": "outstanding-dues", "reason": null, "notifyResident": true }
```

`reasonCode` is one of `BOOKING_REJECTION_REASONS`; `other` must carry free text in `reason`. A
rejection with neither is an unanswerable support ticket, which is why the database refuses it as
well.

**200** — a `Page` of the request's days.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | Missing reason code; `other` with no text |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such request |
| `409` | `conflict` | Already decided |

### `POST /api/v1/amenity-bookings/cancel`

Cancel selected days of a request. **Requires any authenticated caller.**

```json
{
  "occurrenceIds": ["9f3a…", "9f3b…"],
  "reasonCode": "resident-requested",
  "reason": "Travelling that week"
}
```

Serves residents and admins from one route. A resident may withdraw their own **future** days; an
admin may cancel any. Which of the two you are is read from your token, so there is nothing in the
body to lie about.

**All-or-nothing.** If any selected day cannot be cancelled — wrong owner, already past, already
decided, or an id that matches nothing — the whole call returns `409` rather than cancelling four of
five and reporting success. A request with no live day left is itself marked cancelled, so the
approvals tab stops offering a decision on something that no longer exists.

**200**
```json
{ "message": "2 booking day(s) cancelled." }
```

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | Empty list; `other` with no details |
| `401` | | Not authenticated |
| `403` | `forbidden` | The ids span more than one community |
| `404` | `not_found` | None of the ids exist |
| `409` | `conflict` | One or more days can no longer be cancelled |

### `POST /api/v1/amenity-bookings/{occurrenceId}/force-cancel`

Override a booking the resident still wants. **Requires `ADMIN`.**

```json
{ "reasonCode": "emergency-maintenance", "reason": "Burst pipe in the changing room" }
```

Distinct from an ordinary cancellation because the ledger records who did it and why, and because the
deposit becomes refundable as a result — which the ledger **derives** rather than being told.

**200** — the cancelled booking.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | Missing reason code |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such booking |
| `409` | `conflict` | Not approved or confirmed |

### `GET /api/v1/amenities/{amenityId}/ledger`

The ledger tab. **Requires `ADMIN`.**

| Query | Type | Default | Notes |
|---|---|---|---|
| `paymentStatus` | string | — | `paid` \| `pending` \| `partially_paid` \| `refund_pending` \| `refunded` \| `cancelled` \| `all` |
| `q` | string ≤ 100 | — | Resident name |
| `page` | int ≥ 1 | `1` | |
| `pageSize` | int 1–100 | `20` | |

**200**
```json
{
  "items": [
    {
      "id": "9f3a…",
      "bookingId": "9f3a…",
      "amenityId": "5c0b…",
      "amenityName": "Clubhouse Gym",
      "residentId": "b41e…",
      "residentName": "Aakash S.",
      "residentFlat": "B-1204",
      "bookingDate": "2026-07-18",
      "bookingType": "resident",
      "depositAmount": 500.0,
      "depositPaid": 500.0,
      "bookingCharges": 1000.0,
      "additionalCharges": 100.0,
      "amountPaid": 1100.0,
      "refundAmount": 0.0,
      "damageAmount": 0.0,
      "totalAmount": 1100.0,
      "outstandingDeposit": 0.0,
      "remainingRefund": 500.0,
      "paymentStatus": "refund_pending",
      "bookingStatus": "completed",
      "paymentReference": "PAY-GYM-1001",
      "internalNotes": "Completed without incident.",
      "refundDate": null,
      "refundReason": null,
      "refundProcessedBy": null,
      "damageReason": null,
      "forceCancelled": false,
      "forceCancelReason": null,
      "forceCancelledBy": null,
      "forceCancelledAt": null,
      "refundHistory": [],
      "damageHistory": [],
      "cancellationHistory": [],
      "auditTrail": [
        { "id": "audit-created-9f3a…", "type": "created", "label": "Created",
          "timestamp": "2026-07-16T08:00:00+00:00", "actor": null, "amount": null, "details": null }
      ],
      "availableActions": ["view", "refund", "damage"],
      "createdAt": "2026-07-16T08:00:00+00:00",
      "updatedAt": "2026-07-18T09:00:00+00:00"
    }
  ],
  "total": 5, "page": 1, "pageSize": 20, "hasMore": false
}
```

**Every figure is derived from the charges and the append-only event stream.** Nothing stores a
balance, so no balance can drift out of agreement with the rows that produce it — the rule §9 applied
to `outstandingAmount`, reached here by having nothing to recompute in the first place.

- `totalAmount` = booking + additional charges
- `amountPaid` = payments towards those, deposits excluded (matching the mock: `txn-gym-1001` pays
  1100 against 1000 + 100)
- `outstandingDeposit` = deposit charged − deposit paid
- `remainingRefund` = deposit paid − damage taken − already refunded

`paymentStatus` is a `CASE` over those, and **the order of its arms is its meaning**: a cancelled
booking still holding a refundable deposit is `refund_pending`, not `cancelled`, because somebody is
owed money.

`auditTrail` is assembled from the booking's own lifecycle timestamps and its financial events, not
from a separate audit table — two tables that must agree about when a refund happened are one table
and a reconciliation problem.

`availableActions` is computed from the same rules the write endpoints enforce, so a button the client
renders is a button the API will honour.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

### `GET /api/v1/amenities/{amenityId}/ledger/summary`

The eight cards above the ledger table. **Requires `ADMIN`.**

**200**
```json
{
  "totalBookings": 5,
  "totalRevenue": 4500.0,
  "pendingDeposits": 300.0,
  "refundPending": 2,
  "refundCompleted": 0.0,
  "damageDeductions": 200.0,
  "outstandingRefunds": 1250.0,
  "completedTransactions": 3
}
```

Aggregated by Postgres over every transaction for the amenity, so the figures do not change when the
table is paged. An amenity nobody has booked reports zeros with `200`, never a `404`.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

### `POST /api/v1/amenity-bookings/{occurrenceId}/payments`

Record money received against one charge. **Requires `ADMIN`.**

```json
{
  "amount": 800,
  "chargeType": "booking",
  "method": "UPI",
  "paymentReference": "PAY-GYM-1006",
  "notes": null
}
```

`chargeType` is `booking` | `deposit` | `additional` | `late_cancellation`.

**Idempotent on `paymentReference`** within a charge: a replayed gateway callback returns the event
already recorded rather than double-crediting. **Overpayment returns `409` rather than being
clamped**, because clamping accepts money and then loses it.

**201** — the updated ledger transaction, so the caller sees the derived figures rather than the
request echoed back.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | Amount not above zero; unknown charge type |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such booking |
| `409` | `conflict` | No outstanding charge of that kind; more than is owed |

### `POST /api/v1/amenity-bookings/{occurrenceId}/refund`

Return what is left of the deposit. **Requires `ADMIN`.**

```json
{ "reason": "Deposit returned in full", "notes": null }
```

**The amount is not a parameter.** It is the deposit paid, less damage taken, less anything already
refunded, computed in Postgres — a refund whose amount the caller chooses is a refund somebody can
ask to be larger. The frontend already sends nothing (`processDepositRefund` uses
`normalized.remainingRefund`).

A deposit is refundable only once the booking is cancelled or has finished: refunding a booking that
is still going to happen leaves the amenity unsecured.

**201** — the updated ledger transaction.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such booking |
| `409` | `conflict` | No deposit; booking still ahead of it; nothing left to refund |

### `POST /api/v1/amenity-bookings/{occurrenceId}/damage`

Take damage out of the held deposit. **Requires `ADMIN`.**

```json
{ "amount": 200, "reason": "Broken treadmill belt", "notes": null }
```

Capped at what is left, **and capped in Postgres rather than in the API**: a deduction larger than the
deposit is not a deduction, it is an invoice, and it would drive `remainingRefund` negative — which
the ledger clamps to zero, quietly hiding the error.

**201** — the updated ledger transaction.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | Amount not above zero; missing reason |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such booking |
| `409` | `conflict` | No deposit; nothing left; more than remains |

### `POST /api/v1/amenity-bookings/{occurrenceId}/charges`

Bill something after the fact. **Requires `ADMIN`.**

```json
{ "amount": 1000, "chargeType": "additional", "description": "Additional housekeeping" }
```

`chargeType` is `additional` or `late_cancellation`. **A second charge of the same kind adds to the
first**: the ledger has one `additionalCharges` figure, and housekeeping on Monday plus a broken chair
on Tuesday is two things, not the later one.

**201** — the updated ledger transaction.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | Amount not above zero; charge type not addable |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such booking |

### `GET /api/v1/amenity-reports`

The reports page. **Requires `ADMIN`.**

| Query | Type | Default | Notes |
|---|---|---|---|
| `startDate` / `endDate` | date | — | Booking date range |
| `amenityId` | uuid | — | One amenity |
| `bookingStatus` | string | — | One lifecycle status |
| `page` | int ≥ 1 | `1` | |
| `pageSize` | int 1–200 | `50` | |

**200**
```json
{
  "rows": [
    {
      "id": "9f3a…",
      "bookingId": "9f3a…",
      "amenityId": "5c0b…",
      "amenityName": "Clubhouse Gym",
      "residentName": "Aakash S.",
      "residentFlat": "B-1204",
      "bookingDate": "2026-07-18",
      "bookingStatus": "completed",
      "paymentStatus": "paid",
      "amountPaid": 1100.0
    }
  ],
  "kpis": {
    "totalAmenities": 6,
    "totalActiveBookings": 4,
    "pendingApprovals": 2,
    "totalRevenue": 15300.0,
    "activeAmenities": 5,
    "bookingsThisMonth": 9
  },
  "options": {
    "amenities": [{ "value": "5c0b…", "label": "Clubhouse Gym" }],
    "bookingStatuses": ["pending", "approved", "confirmed", "completed", "cancelled", "rejected", "blocked"]
  }
}
```

**`rows` is a page; `kpis` is an aggregate over every matching row.** That split is the point: a KPI
that describes one page is not a KPI, and this one is labelled "Total Revenue". `calculateAmenityReports`
computes all six in the browser from whatever it has loaded, which is the same failure as the money
tiles (agenda item 11).

`options.bookingStatuses` is the lifecycle's fixed vocabulary rather than the statuses that happen to
be present, so the filter does not lose an option the moment nothing currently has that status.

A block is excluded from every count but not from the revenue — it is not a booking anybody made, but
its money would still be money.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

---

## 11. Settings — community preferences and feature modules

Backed by migration `0017`. Two `security_invoker` views read; three RPCs write.

**Every other section of this document reproduces a shape the frontend already has. This one does
not.** `pages/AdminDashboard/Settings.jsx` is 135 lines: four `useState` toggles and

```js
const handleSave = () => { showToast('Admin Settings Saved Successfully', 'success'); };
```

There is no store slice, no service module, and nothing is persisted. An admin flips four switches,
is told they saved, and loses all four on reload. So **the field names below are ours** — chosen to
say what the screen's own labels say, because there was nothing to match. This is agenda item 17.

**The four switches are four different kinds of thing, which is why they do not live in one table.**

| The screen's label | Where it lives now | Who writes it |
|---|---|---|
| Automated Monthly Maintenance | `community_billing_settings.auto_billing_enabled` | `PUT /billing-settings` (§9) |
| Late Payment Fine Charges | `community_billing_settings.late_fee_enabled` | `PUT /billing-settings` (§9) |
| Gate Security App Pre-approvals | `community_settings.require_visitor_preapproval` | `PUT /settings` |
| Urgent Notice SMS Broadcast | `community_settings.notice_sms_broadcast_enabled` | `PUT /settings` |

The first two are money and money already had a home — this is what the build plan's "billing and
late fines are not settings" means in practice. All four are readable in one `GET /settings`, because
the screen draws them on one card; the billing pair is **read-only here** and writable only at
`PUT /billing-settings`, because two writers is how one rate starts disagreeing with itself.

**Three of the four toggles are stored and acted on by nothing, and this document is where that is
said out loud rather than discovered.**

- **Nothing runs billing on a schedule.** `POST /maintenance-runs` (§9) is manual and ignores
  `autoBillingEnabled` on purpose: an admin pressing the button has said what they want more recently
  than a toggle did.
- **Nothing charges a late fee.** There is no fine engine, no `late_fee` charge row, and no job.
  `lateFeeEnabled`, `lateFeeAmount`, `lateFeeGraceDays` and `lateFeePeriod` are a stored policy
  waiting for one.
- **`requireVisitorPreapproval` is read by nothing, and correctly so.** The visitor backend now
  exists — `visitor_passes` and the resident endpoints in §14 arrived with migration `0032`, which
  also became the first reader of `visitorCodeTtlMinutes`. This toggle is different: it governs
  whether the *gate* may admit someone arriving with no pass at all, and no gate software exists in
  this repository. Storing it is honest; inventing a reader for it would not be.
- **There is no SMS provider in this repository**, so `noticeSmsBroadcastEnabled` is read by nothing.
  It defaults to `false` — it is the only toggle that would spend money every time it fired, and a
  setting like that defaults off.

Storing them is still the point: the screen currently loses them, and a policy that survives a
reload is a policy someone can build against.

**`lateFeeAmount` is `null` until an admin sets one.** The screen's prose mentions ₹100; writing that
in as a default would repeat exactly the mistake `defaultMaintenanceAmount` records in §9 — a number
nobody chose, indistinguishable from one they did.

### Two things the build plan asked for and this step deliberately did not do

**No community rename.** `GET /settings` reports `community.name`, `communityType` and `status`;
nothing writes them. `associations` is the one table this build plan touches whose admin write policy
carries no community clause (build plan §1.2, owned by the auth workstream), and a rename would be
the first of seventy operations to depend on it. It waits for that fix rather than becoming the reason
it was urgent.

**No module enforcement.** Turning a module off does not 403 anything. Two reasons, both only visible
from the seed data: `amenities-booking` ships **disabled** (mirroring `onboardingModules.js`, where
its `defaultEnabled` is `false`), so enforcing would `403` all twenty-two step-8 endpoints on every
community that exists; and six of the ten modules have no backend to gate, so the rule would be real
for four keys and decorative for six. What replaced it is `backendStatus` — the state is reported
honestly instead of enforced wrongly. This is `DECISIONS_NEEDED.md` A24.

### The ten modules

Fixed by `frontend/src/data/onboardingModules.js` and seeded by `0017`. **The ERD says onboarding
selects nine; there are ten** (`DECISIONS_NEEDED.md` D8).

| Key | Name | Default | `backendStatus` |
|---|---|---|---|
| `resident-management` | Resident Management | on | `implemented` |
| `visitor-management` | Visitor Management | on | `none` |
| `complaint-management` | Complaint Management | on | `implemented` |
| `maintenance-billing` | Maintenance & Billing | on | `partial` |
| `notice-board` | Notice Board | on | `partial` |
| `amenities-booking` | Amenities Booking | **off** | `implemented` |
| `security-gate-management` | Security & Gate Management | off | `none` |
| `parking-management` | Parking Management | off | `none` |
| `staff-management` | Staff Management | off | `implemented` |
| `community-marketplace` | Community Marketplace | off | `none` |

**The catalogue drives the list, not the community's rows.** A community with no row for a key reads
as that key's default with `isDefault: true`, rather than the key vanishing from the list — so an
eleventh module added to the catalogue appears everywhere immediately.

**The onboarding wizard promises a screen that does not exist.** `FeatureConfigurationPage.jsx` ends
with *"These features can be changed later from the Admin Settings page."* The Settings page has no
module UI at all, and nothing in the frontend reads `enabledModules` — `AdminLayout.jsx` is a fixed
ten-item nav array. These endpoints are what that promise would need. Agenda item 17.

### `GET /api/v1/settings`

Everything the settings screen needs, in one request. **Requires `ADMIN`.**

**200**
```json
{
  "community": {
    "id": "3c6e...",
    "name": "Green Valley Apartments",
    "communityType": "apartment",
    "communityTypeLabel": "Apartment",
    "status": "Active",
    "createdAt": "2026-01-04T06:20:00+00:00"
  },
  "preferences": {
    "timezone": "Asia/Kolkata",
    "unitLabelSingular": "Flat",
    "unitLabelIsDerived": true,
    "inviteTtlHours": 72,
    "visitorCodeTtlMinutes": 120,
    "requireVisitorPreapproval": true,
    "noticeSmsBroadcastEnabled": false
  },
  "billing": {
    "autoBillingEnabled": false,
    "autoBillingDay": 1,
    "lateFeeEnabled": false,
    "lateFeeAmount": null,
    "lateFeeGraceDays": 10,
    "lateFeePeriod": "weekly",
    "lateFeePeriodLabel": "Weekly",
    "defaultMaintenanceAmount": null
  },
  "modules": {
    "items": [
      {
        "key": "resident-management",
        "name": "Resident Management",
        "description": "Manage residents and their profiles.",
        "enabled": true,
        "isDefault": false,
        "defaultEnabled": true,
        "backendStatus": "implemented",
        "backendStatusLabel": "Implemented",
        "backendNote": "Build step 4. GET/PATCH/DELETE /residents, /admins, /registrations.",
        "sortOrder": 1,
        "updatedAt": "2026-01-04T06:21:00+00:00",
        "updatedBy": "Priya Sharma"
      }
    ],
    "total": 10,
    "enabledCount": 5,
    "enabledWithoutBackend": 1
  },
  "hasSavedSettings": false,
  "version": 1,
  "updatedAt": null,
  "updatedBy": null
}
```

**`hasSavedSettings: false` means every value above is a default, not a choice**, and a screen that
renders the two the same way tells an admin they picked a timezone they have never seen. A community
that has never saved gets a full `200` rather than a `404`; the row is created lazily on first write
and a screen asking what the settings are should not have to know that.

**`unitLabelIsDerived` says the same thing about one field.** With no override stored, the label is
derived from the community type — `Flat` for `apartment`, `Villa` otherwise. It is derived rather than
defaulted at write time because a stored default would go stale the day a community changed type. The
same one-line rule exists in SQL (`community_settings_overview`) and in Python
(`vocabularies.unit_label_for`), and the two are tested against each other.

**`enabledWithoutBackend` is the number worth putting on the screen**: modules switched on that
nothing implements. The snapshot computes it as a SQL aggregate and `GET /settings/modules` computes
it in Python; a test pins them to each other, because the same screen showing two different counts is
worse than showing neither.

`version` increments on every successful `PUT /settings` and is the handle for optimistic concurrency
if F4 is ever adopted. Nothing checks it today.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

### `PUT /api/v1/settings`

Patch the community preferences. Omitted fields are left unchanged. **Requires `ADMIN`.**

```json
{
  "timezone": "Asia/Kolkata",
  "unitLabelSingular": "Villa",
  "inviteTtlHours": 72,
  "visitorCodeTtlMinutes": 120,
  "requireVisitorPreapproval": true,
  "noticeSmsBroadcastEnabled": false
}
```

Every field is optional. The billing toggles are **not** accepted here — they are `PUT /billing-settings`.

**`unitLabelSingular: null` clears the override** and goes back to deriving the word from the
community type, which is not what omitting the field does. An empty string means the same as `null`,
because the form's "clear" gesture is deleting the text rather than typing `null`. Key presence is
what separates them, matching `defaultMaintenanceAmount` in §9.

**`timezone` is validated against the database's own `pg_timezone_names`**, not against a list we
wrote down — an unknown name is a `409`, and the catalogue's spelling is what gets stored, so
`asia/kolkata` is saved as `Asia/Kolkata`. It is checked in the RPC rather than by a `CHECK`
constraint because a `CHECK` must be immutable and the timezone catalogue is loaded from the host and
changes between Postgres releases.

**This field answers `DECISIONS_NEEDED.md` A10, and it vindicates the amenities design rather than
reversing it.** A booking made for 07:00 must still read 07:00 after somebody corrects the community's
timezone, which is only true because `0016` stores wall-clock `date` + `time`. The timezone unlocks
anything that needs an absolute instant — a reminder, a scheduled run — without rewriting what is
already stored.

**`inviteTtlHours` is stored and not yet read.** `invitation_service.py` still takes the TTL from an
environment variable; making it read this column is an auth-workstream change
(`DECISIONS_NEEDED.md` C8). The cap is 720 hours — an invite that outlives a month is not a second
factor any more, it is a credential sitting in an inbox.

**200** — the full snapshot as it now stands, identical in shape to `GET /settings`.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |
| `409` | `conflict` | `timezone` is not a name Postgres knows |
| `422` | `request_validation_error` | `timezone` with whitespace or outside 3–64 chars, `unitLabelSingular` over 24 chars, `inviteTtlHours` outside 1–720, `visitorCodeTtlMinutes` outside 5–1440 |

## 12. Notices and administrator promotion

Added after the merge. Both serve a frontend handler that had **no endpoint anywhere** — the screens have been
writing to browser memory, and since `appStore` stopped persisting tenant data those writes are lost on refresh.

### 12.1 `POST /notices` — post a notice

Admin only. Publishes immediately: there is no draft state and no schedule control on the screen, so a nullable
`publishedAt` left unset would create notices no reader could ever see.

Field names match `addNotice({title, description, category, urgency})` exactly, so the screen needs no payload
mapping. `description` is stored in `notices.body`.

**Request**

```json
{
  "title": "Water tank cleaning on Saturday",
  "description": "Supply will be interrupted between 10:00 and 14:00.",
  "category": "Maintenance",
  "urgency": "important"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | yes | 1–200 chars |
| `description` | string | yes | 1–5 000 chars |
| `category` | string | no | Free text, 1–80 chars. Defaults to `General`. Not an enum — an association's notice categories are its own business, and a CHECK would make "add a category" a migration. |
| `urgency` | string | no | `Info` \| `Important` \| `Urgent`, case-insensitive. Stored lowercase. Defaults to `Info`. |

**Response `201`**

```json
{
  "id": "8f14e45f-…",
  "title": "Water tank cleaning on Saturday",
  "description": "Supply will be interrupted between 10:00 and 14:00.",
  "category": "Maintenance",
  "urgency": "important",
  "publishedAt": "2026-07-30T09:15:00Z",
  "createdAt": "2026-07-30T09:15:00Z"
}
```

| Status | Error code | When |
|---|---|---|
| `201` | | Posted. Fires the `notices` SSE trigger, so every connected client re-snapshots. |
| `401` | `authentication_error` | No valid session cookie or bearer token |
| `403` | `community_role_required` | Caller is not an admin of the community |
| `403` | `csrf_invalid` / `csrf_origin_invalid` | Missing `X-CSRF-Token`, or wrong `Origin` |
| `403` | `active_membership_required` | Authenticated but in no active community |
| `422` | `validation_error` | `urgency` outside the vocabulary |
| `422` | `request_validation_error` | `title` or `description` missing, empty or over length |

> **Known gap, not a bug here.** `category` and `urgency` are stored (migration 0018 adds both columns) but
> `dashboard_service.py:202` projects notices as `{id, title, description, date, createdAt}` and drops them, so
> they round-trip through this response but not through the snapshot. Adding them there is a one-line change owned
> by the dashboard workstream.

### 12.2 `POST /admins` — promote a member to administrator

Admin only. **Promotes an existing member; it does not invite one.**

The obvious implementation — mint an admin-bound invitation — is not available: the shared invitation contract
hardcodes `intended_role = 'resident'` (`invitations_repository.py:40`) and `CreateInvitationRequest` has no role
field, so an admin invite cannot be issued without duplicating token machinery this workstream does not own.
Promotion is also the flow `roles.md` describes — *"Resident → Committee members → Admin"*.

**Request**

```json
{ "email": "asha@example.com", "name": "Asha R", "phone": "+919812345678", "tower": "B", "flat": "B-1204" }
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `email` | string | yes | Matched case-insensitively against `profiles.display_email`, which is `citext` with a unique index, so it cannot match two people. |
| `name`, `phone`, `tower`, `flat` | string | no | **Accepted and ignored.** The Admins screen sends them, but the member already has all four on their profile and residency, and letting a promotion silently rewrite someone's flat would be a worse bug than ignoring the fields. |

**Response `200`** — the promoted member as an `AdminSummary` (`id`, `profileId`, `name`, `email`, `phone`, `role`,
`displayRole`, `designation`, `flat`, `unitId`, `status`, `joinedAt`).

| Status | Error code | When |
|---|---|---|
| `200` | | Promoted |
| `401` | `authentication_error` | No valid session |
| `403` | `community_role_required` | Caller is not an admin |
| `403` | `csrf_invalid` / `csrf_origin_invalid` | CSRF header or origin wrong |
| `404` | `not_found` | **No active member of this community uses that email.** The message tells the caller to invite them first and promote once they have joined. |
| `409` | `conflict` | That member is already an administrator |

> **Frontend consequence — agenda item.** The form accepts any address, so typing a non-member's email returns 404.
> Either pre-filter the field to existing members or surface the 404 as *"invite them first"*.
>
> **Scope note.** This grants the `admin` *role*; it does not touch `community_admin_terms`, which records who holds
> the community's single designated admin office and is guarded by the `community_admin_one_active` partial unique
> index. Writing that here would either violate the index or silently depose the sitting admin.

---

## 13. Visitors

Backed by migration `0032`. Six operations, all of them the **resident's** half of the visitor
lifecycle. The gate's half — presenting a pass, checking a guest in, raising an approval request when
somebody arrives unannounced — belongs to security software that does not exist in this repository,
and the boundary is drawn here rather than left to be inferred.

`visitor_requests` arrived in the baseline already carrying a status enum for the whole lifecycle, a
unique `pass_hash`, a validity window and check-in/check-out timestamps. What `0032` adds is what the
resident's form collects — purpose, guest count, and the short code they read aloud.

**No role guard on any route.** A resident, a manager and an admin all have visitors; the passes each
of them sees are the ones they raised.

### The security code appears in exactly one response

`securityCode` and `passToken` are returned by `POST /visitor-passes` and **by nothing else, ever**.
Both are stored as SHA-256 hashes, and `visitor_pass_overview` does not select the hash columns at
all — so a list read, a detail read and all three decisions are structurally incapable of carrying
one.

Both plaintexts are generated **in the API and never sent to the database**. Only the hashes are RPC
parameters. That is stronger than hashing on the way in: there is no statement log, slow-query log or
replication stream in which the code could appear.

> **The cost, stated plainly.** A resident who loses the code cannot recover it and must issue a new
> pass. That is the correct trade for something that opens a gate, and it is exactly how the invite
> flow already behaves.

> **An obligation on the client, and it is a change from the prototype.** *Show QR* on the Visitors
> screen rebuilds the payload from the visitor in the store, which works because the prototype keeps
> the plaintext in the browser forever. Against this API the code and token arrive once, in the `201`,
> and **no later read can return them** — so a client that wants that button has to keep what it was
> handed for the life of the pass. Clearing storage or signing in on another device loses the QR, not
> the pass; the pass is still there, still valid at the gate for anyone who wrote the six digits down.
> If the product wants recovery rather than reissue, say so — a `POST /visitor-passes/{passId}/code`
> that mints a *fresh* code and invalidates the old one is the shape that keeps the rule, and it is
> not built.

> **An obligation on whoever builds the gate.** The code is six digits because a resident reads it
> down a phone line — about twenty bits, which does not stand alone against online guessing. Three
> things carry the difference: it is unique only among *live* passes in one community, a pass expires
> on the community's TTL, and **any gate-verification endpoint must rate-limit by community**. The
> third does not exist yet. It is recorded here so it is a requirement rather than a rediscovery.

### The setting that nothing read

`community_settings.visitorCodeTtlMinutes` has been writable from the admin settings screen since
`0018` under the comment *"Reserved by the ERD for a subsystem that does not exist. Nothing reads
it."* These endpoints are the reader. A control that stores a value nothing consults is worse than a
missing control, because it looks like it worked.

`requireVisitorPreapproval` still has no reader, and correctly so: it governs whether the **gate** may
admit someone with no pass. Tracked in §15.

### The status nothing ever wrote

`Expired` has been in the visitor status enum since the baseline and no code path has ever set it.
Two things need it to be real: the uniqueness rule above, whose whole argument is that a dead pass
releases its six digits, and the resident's list, where a pass that lapsed last Tuesday should not sit
in `Expected` forever.

`POST /visitor-passes` settles the community's lapsed passes immediately before it mints a code into
that community's live set. Not a trigger — a trigger cannot fire on the passage of time — and not a
scheduled job, which would be a second deployment artifact for a property one statement can hold. The
cost is that a pass lapses *lazily*: between issues it is still `Expected` on the wire, which is what
`isLapsed` is for.

### `GET /api/v1/visitor-passes`

The caller's own passes, newest first. **Requires an active membership.**

| Query | Notes |
|---|---|
| `view` | `current` \| `history`. Omitted returns both. An unrecognised value returns **both**, not a `422` — unlike the complaint status filter. `view` is a tab selector with two known values, and the honest answer to a third is everything, rather than an error about a parameter the caller did not mean to constrain |
| `page`, `pageSize` | `pageSize` ≤ 100, default 20 |

| Response field | Notes |
|---|---|
| `visitorName`, `purpose`, `purposeDetails`, `guestCount` | `purposeDetails` is what the form collects when `purpose` is `Other`; kept separate so a typed "Delivery" stays distinguishable from the selected one |
| `status` | `Expected` \| `Pending Approval` \| `Approved` \| `Rejected` \| `Checked In` \| `Checked Out` \| `Expired` \| `Cancelled`. The column says `denied`; every screen says `Rejected` |
| `validFrom`, `validUntil` | The window. Computed in the database — see `POST` below |
| `isCurrent` | **This is what splits the two tabs**, computed in the view rather than from a status list in the API, so the split cannot drift from the transitions the RPC allows. Open and not past its window — **or `Checked In`**, whatever the window says. A guest who is through the gate is the one pass a resident might actually need to look at, and `Visitors.jsx` keeps them on the front tab for the same reason. The clock only constrains the states where nobody has arrived |
| `isLapsed` | Still open but past its window — the pass the gate will refuse while the resident's screen still says `Expected`. Surfaced as its own fact rather than leaving a resident to compare two timestamps |
| `checkedInAt`, `checkedOutAt`, `decidedAt`, `cancelledAt`, `createdAt` | |

### `POST /api/v1/visitor-passes`

Pre-approve a visitor. **Requires an active membership.** `201 Created`.

**Request**
```json
{
  "purpose": "Guest",
  "purposeDetails": "",
  "guestCount": 3,
  "expectedAt": "2026-08-04T16:00:00Z"
}
```

`expectedAt` is one instant rather than the form's separate date and time fields: two fields is a
rendering decision, one instant is what a validity window is computed from, and the browser is the
only place its own timezone is known.

> **`visitorName` is optional, because the form does not collect one.** The pre-approval screen asks
> for a purpose, a date, a time and a guest count and nothing else, while `visitor_requests` requires
> a name — so `createVisitorsSlice.js` composes one, *"Guest group"* or *"Family event group"*. Sent
> empty or omitted, the API composes the same label from the same rule. It is accepted when present
> because the gate's own screen does collect a name, and that surface is coming. **Requiring it would
> have meant requiring a field no client has.**

> **`validUntil` is not accepted.** The window runs from `expectedAt` (or now) for the community's
> `visitorCodeTtlMinutes`. A resident who could choose it could mint a pass valid for a year. The TTL
> runs from the arrival **or from issue, whichever is later** — the form floors the date at today but
> not the time, so a four-o'clock pre-approval for a nine-o'clock arrival would otherwise mint a pass
> whose window had already closed: unusable, and reported as nothing.

**The status is `Expected`, not `Approved`.** A pre-approved visitor has been *announced*, not
approved by anybody. `Approved` is what answering a gate request produces, and a gate log needs to
keep those apart.

The response is `VisitorPassCreated` — every field of a pass, plus `securityCode` and `passToken`.

> **A code the community is already using is redrawn, not reported.** `(communityId, codeHash)` is
> unique across a community's *live* passes, so two residents can be handed the same six digits and
> the second insert is refused. Nothing about that request was wrong, and the database cannot fix it
> itself — it holds a hash and no way back to a code. The API re-mints, up to five times. Against a
> community holding a thousand live passes at once, one draw collides about once in nine hundred, so
> the `409` below is a bound on the loop rather than an outcome anyone should expect.

| Status | Code | Cause |
|---|---|---|
| `409` | `unique_violation` | Five draws in a row collided with a live pass in the same community |
| `422` | — | Empty or whitespace-only `purpose`; `guestCount` outside 1–50. **Not** an absent `visitorName` |

### `GET /api/v1/visitor-passes/{passId}`

One pass — the QR screen's read. A pass belonging to somebody else is a **`404`, identical to one
that does not exist**; the lookup filters on the membership rather than checking afterwards.

**The QR payload is not reconstructible from this response.** The token it embeds was returned once,
so a client that did not keep it cannot rebuild the credential from a later read.

### `POST /api/v1/visitor-passes/{passId}/approve` · `/reject`

Answer a gate request. Only from `Pending Approval`.

> **No endpoint in this repository creates a `Pending Approval` pass.** The security app does, and it
> does not exist yet. These two routes are built now because they answer `visitor.approvalRequested`,
> which is `US-2.1`'s recorded pain point, and because a reply is the wrong thing to build after the
> notification that prompts it. They are correct and, today, unreachable from our own API.

`reject` stores `denied` and shows `Rejected`. Both notify the community's `security` role, and its
admins — so a community with nobody on security is not told nothing at all. **The visitor's name
travels in the notification; the code never does** (§10.8's one hard rule).

### `POST /api/v1/visitor-passes/{passId}/cancel`

Withdraw a pass that has not been used. From `Expected`, `Pending Approval` or `Approved`.

> **A pass whose guest is already inside cannot be cancelled** — `409`, `pass_already_used`. Once
> someone is through the gate, *cancel* is a physical-world operation and no database write performs
> it; a pass that flipped back would leave a record disagreeing with what happened, and the record is
> all anyone will have later. `PO`, 2026-08-04.

The refusal lives in the RPC, not the route, so it holds for every future caller.

| Status | Code | Cause |
|---|---|---|
| `404` | `not_found` | No such pass, or not the caller's |
| `409` | `pass_already_used` | The guest has checked in or out. **A distinct code from `check_violation` on purpose**: "too late, they are already inside" is a fact about the world, and "that is not a state you can do this from" is a bug in the caller |
| `422` | `check_violation` | A state this decision cannot be made from |

---

## 14. The resident's money and home

Backed by migration `0033`. Nine operations across the surfaces the resident portal has and the
backend did not: their own bills, their own bookings, the notice board, their flat, the numbers they
should be able to ring — and the home screen that summarises all of it.

**One of the nine needed no schema change at all.** `GET /resident/snapshot` is assembled entirely
from endpoints already in this section and the ones before it, which is the point of it: every figure
it reports already has an owner, and a home screen that computed its own would eventually disagree
with the page it links to.

**There is already a money section (§9) and a notices section (§12), and this is deliberately not
either.** §5.5 of the design document: an admin *records* a payment that happened somewhere else,
with an arbitrary amount, an arbitrary method and possibly a backdated date. A resident *initiates*
one against their own bill, for the full balance, through whatever gateway exists. Merging them
produces one endpoint where half the fields are forbidden depending on who is calling.

**No role guard on any route here.** An admin who lives in the community owes maintenance, has a flat
and needs the plumber's number like anybody else.

### 14.1 The gateway is a simulator, and every row it writes says so

The gateway is one we build (`PO`, 2026-08-04). No money moves. Any payment passes by default, with a
few deliberate failure cases — a card past its expiry being the worked example — *"so that we can
show we handle that too, and maintain business logic for this."*

That last clause is the design. The point is not a fake success screen; it is that **every path a
real gateway produces is exercised end to end**, so that swapping in a real one changes one Python
module and nothing else.

> **`provider = 'simulator'` is written on every payment this section creates**, and it is the single
> most important string in the migration. A demo database becomes a staging database becomes,
> occasionally, the thing somebody reconciles against a bank statement. If simulated money were
> recorded as `offline` — which is what the admin's `record_payment` writes — then on the day a real
> gateway arrives, **nobody could ever separate the money that moved from the money that did not.**
> That is not a recoverable mistake; the information was never recorded. One string, written
> correctly on day one, makes it a `where` clause forever.

The row does say `succeeded`, because within the simulated gateway the payment succeeded, and it says
`simulator`, because that is which gateway said so. Both facts are recorded and neither is implied.

`payment_events` gets two rows per attempt — `initiated`, then `simulated_authorized` or
`simulated_declined` — because that is the shape a real integration's audit trail has, arriving at
different times and sometimes from different directions.

### 14.2 A declined payment is a `200`

`POST /invoices/{invoiceId}/pay` and `POST /amenity-bookings/{bookingId}/pay` return `200` with an
outcome object for **both** `succeeded` and `failed`. Branch on `status`; read `failureCode` for the
reason.

A declined card is not a failed API call. The request was well-formed, authorized, processed
correctly and produced a durable record; the *payment* failed. A `402` would mean the client's error
branch — the one handling "your session expired" and "the server is down" — also has to handle a
perfectly ordinary business outcome, and would have to dig a payment id out of an error envelope with
nowhere sensible to put one.

`4xx` still means what it always meant: `404` for somebody else's invoice, `409` for one already
settled, `422` for a body that does not add up.

`failureCode` is a stable identifier and never prose — `card_expired`, `insufficient_funds`,
`payment_declined`. The wording a resident reads is the client's to choose and to translate.

### 14.3 What the simulator accepts, and what it never keeps

| Instrument | Outcome | `failureCode` |
|---|---|---|
| `4242 4242 4242 4242`, expiry in the future | `succeeded` | — |
| **Any test card with an expiry date in the past** | `failed` | `card_expired` |
| `4000 0000 0000 0002` | `failed` | `card_declined` |
| `4000 0000 0000 9995` | `failed` | `insufficient_funds` |
| `4000 0000 0000 0069` | `failed` | `card_expired`, whatever the expiry says |
| CVV not three digits, or a month that is not a month | `failed` | `card_invalid` |
| Any other card number | `failed` | `card_not_supported` |
| UPI `failure@…` or `fail@…` | `failed` | `payment_declined` |
| Any other well-formed `name@handle` | `succeeded` | — |
| **UPI with no handle at all** | `succeeded` | — |

> **Only the published test numbers are accepted, and that is the part worth arguing.** A simulated
> gateway that took any Luhn-valid number is a system that *will* be handed a real card — by a tester
> being thorough, by a demo audience member being helpful, by a marker trying the app the way a
> resident would. At that moment we are an application that received a live PAN, with none of the
> obligations discharged that receiving one implies. Restricting the input closes that by
> construction, which is worth more than a warning banner nobody reads. Stripe's sandbox can accept
> anything because Stripe is PCI-DSS certified infrastructure whose business is holding card data
> safely; copying the affordance without the substrate is the mistake.

> **Nothing about the card is stored, logged, echoed in an error, or written to `payment_events`.**
> The number, the CVV and the expiry are `SecretStr` on the request model — so an accidental `repr()`
> in a log line or a traceback prints `**********` — are read once by a pure function, and are
> discarded in the same call. What survives is `paymentMethod` and `instrumentLabel`, a masked
> receipt line: `•••• 4242`, `resident@upi`, `UPI`.

**The last row of that table is about your screen.** `Payments.jsx` renders UPI as the only enabled
method and its Confirm button collects no instrument at all, so a payment with no handle has to
succeed or the endpoint could not be called from the screen it was built for. The consequence is that
**the failure demonstration is not reachable from the current UI** — showing a decline needs either a
VPA field or the card fields the modal currently disables.

### 14.4 `idempotencyKey` is required, and the rule is the client's

The database has had `unique (communityId, idempotencyKey)` since the baseline and the RPC returns the
existing payment rather than raising on a repeat. What that constraint cannot do is decide when a key
is new:

* **One key per press of Pay.** A double-tap, a flaky network, a retried request — same key, same
  payment returned, and the caller cannot tell whether it settled now or a moment ago. This is the
  case that stops a resident paying twice.
* **A new key for a new attempt.** Once the client has *shown* someone a decline, the next press is a
  different attempt and mints a fresh key. Otherwise a corrected card would replay the old failure
  forever.

The key identifies **an attempt**, not an invoice. Backwards, it produces either a double charge or an
unpayable bill — which is why it is written here rather than left to whoever wires the button.

### `GET /api/v1/invoices/mine`

The caller's own bills, newest first.

| Query | Notes |
|---|---|
| `view` | `unpaid` \| `paid`. Omitted, or unrecognised, returns both. It filters on `status`, **not** on `isPayable` — those two agree on every bill a resident normally holds and part company on the ones that matter, since a cancelled bill is not payable and was never paid |
| `page`, `pageSize` | `pageSize` ≤ 100, default 20 |

**Two rules about which bills appear at all.** A **draft** never does: it is a bill an admin has not
issued, with no number and nothing to pay, and it was previously reaching the resident as an amount
owed on something nobody had sent. A bill raised against the **flat** rather than against a person
always does, even though it carries no membership — it is the caller's to pay, and the list is
filtered by the same `is_own_invoice` the settlement path enforces so that the two can never
disagree about whose bill this is.

| Response field | Notes |
|---|---|
| `status` | `Unpaid` \| `Paid` \| `Cancelled`. Six stored statuses collapse to the two the screen has: `partially_paid`, `issued` and `overdue` all read as `Unpaid`, which is what they are to the person who owes the money |
| `storedStatus` | The real one, beside it |
| `totalAmount`, `amountPaid`, `outstandingAmount` | Aggregates over `succeeded` payments only. An initiated or failed payment has settled nothing |
| `isOverdue` | Derived on every read, never stored. A stored overdue flag is true until the next midnight and a lie afterwards |
| `isPayable` | **The precondition the settlement RPC enforces**, computed once in the database. A Pay button drawn from a different rule than the write path applies is a button that fails |
| `instrumentLabel` | The masked receipt line of whatever settled it |

### `POST /api/v1/invoices/{invoiceId}/pay`

Settle a bill through the simulator. `200` for both outcomes — see §14.2.

**Request**
```json
{
  "amount": "4250.00",
  "idempotencyKey": "pay-8f2c1e04-0001",
  "method": "upi",
  "upi": { "vpa": "resident@okhdfcbank" }
}
```

`amount` must equal the outstanding balance, and it is compared against the balance **the database
computes** rather than accepted as an instruction. It is in the request so a client working from a
stale screen can be told so — not so it can choose what to pay. A partial payment is a policy
question nobody has answered, and accepting one silently would leave a resident believing they had
paid.

| Status | Code | Cause |
|---|---|---|
| `404` | `invoice_not_found` | No such invoice, or not the caller's |
| `409` | `conflict` | Already paid or voided |
| `422` | `check_violation` | The amount is not the outstanding balance |
| `422` | `card_required` | `method` is `card` and no card was sent |
| `422` | — | No `idempotencyKey` |

### `GET /api/v1/amenity-bookings/mine`

The caller's own bookings and what is still owed on each. `?view=upcoming|past`.

> **`amenity_booking_charges` was admin-only until `0033`**, under the reasoning that the ledger
> records what residents were charged and that is not a community-wide fact. Correct about the
> community and wrong about the resident: the one person entitled to know what a booking costs is the
> person being asked to pay for it. The policy now has an own-booking clause and nothing more.

### `POST /api/v1/amenity-bookings/{bookingId}/pay`

**This is the endpoint `US-2.12` asks for**, and the story is not about the gateway. The pain point is
*"amenity booking payments can fail even after money has been deducted"*, which is not a gateway
defect — it is a payment recorded in one transaction and a booking confirmed in another, with a crash
in between.

`settle_amenity_booking_payment` does both or neither:

* on `succeeded` — write the payment, append the event, **confirm the booking**, notify the resident,
  notify the staff. One transaction.
* on `failed` — write the attempt with its reason, **leave the booking exactly as it was**, tell the
  resident it did not go through. Also one transaction.

The second half is the one that gets forgotten, and it is the one the story is about: a failed payment
must not leave a half-confirmed booking a resident believes they hold. A declined attempt is recorded
as `payment_failed` in the ledger — a new event type, because writing it as a `charge` would put a
phantom line in the admin's ledger and writing it as a `payment` would show the booking as paid.

Same request shape and same `200`-on-decline rule as paying an invoice.

### `GET /api/v1/notices`

The community's published notices, newest first. `?category=` is an exact match.

**Drafts never appear.** A notice with no `publishedAt` is one an admin is still writing, and it is
excluded by the resident view *and* by the policy `0033` adds. Two independent reasons, because
half-written words reaching a whole community is not a failure worth having one guard against.

`urgency` is `Info` | `Important` | `Urgent` — title-cased on the wire because that is what
`Notices.jsx` renders, while the CHECK in `0018` stores lower case.

Posting a notice is unchanged and remains an admin action (§12.1).

### `GET /api/v1/me/household`

Everyone and every number registered to the caller's flat. Not paginated: a household is not a
quantity that needs a page control.

| Response field | Notes |
|---|---|
| `source` | `member` \| `contact`. **The field that stops a caller guessing.** A `member` is a person with an account, a membership and a role; a `contact` is a phone number somebody in the flat added so the gate and the office have it — it grants nothing at all, and its holder has no account |
| `status` | `Active` \| `Pending` \| `Suspended` \| `Ended` for a member; `Contact` for a number |

A caller with no residency gets `[]`, not an error. Staff have a membership and no flat, and *nobody*
is a legitimate answer to "who lives in your flat".

### `POST /api/v1/me/household/phones`

Register another number against the caller's own flat — the thing `Profile.jsx` lets a resident do
without waiting for an admin. Returns the whole list, because that is what the screen renders and a
client merging one row into it can merge it wrongly.

> **The flat is not in the request.** It is resolved from the caller's own residency inside the RPC: a
> unit id in a body is a unit id somebody can change, and the entire point of this endpoint is that a
> resident may edit their own flat's list and nobody else's.

> **A flat contact is not a member, and this is a change from the prototype.**
> `createUsersSlice.js` implements *add a number* by inventing a whole user — name, role, status and
> all. That cannot be done here and should not be: `profiles.id` references `auth.users`, so a person
> with no account cannot be a profile, and manufacturing a membership for a phone number would put
> somebody in the community's member count who cannot log in and never agreed to join.

Idempotent on the number: adding the same one twice updates the name rather than failing, since a
correction is the likeliest reason anybody repeats it.

### `GET /api/v1/directory/contacts`

The management and emergency directory (§5.6), served from `departments` rather than a table of its
own — so it stays current as a side effect of admin work that already happens, which is the only kind
of freshness that survives contact with a real committee. `US-2.9` asks for a directory somebody can
trust and names the failure mode as a list nobody updates, which is precisely what five numbers
hard-coded in `Profile.jsx` are.

> **There is no emergency flag, deliberately.** `Profile.jsx` labels its numbers *"Emergency / Gate"*,
> *"Administrative"*, *"Maintenance Staff"*; the nearest thing a department has is `category`, free
> text an admin types. Deciding which categories mean *emergency* by matching strings in SQL would be
> a classification invented in the backend and wrong the first time somebody writes "Emergencies". If
> the product wants that distinction it is one boolean on `departments`, and that table belongs to
> the admin workstream.

`US-2.10` — a designated **building** representative — is still unserved. Nothing in the schema ties a
department or a person to a building. Tracked in §15.

### 14.5 The home aggregate, and why it owns nothing

`GET /resident/snapshot` is a projection of the endpoints above, not a source of truth. Every part of
it is the model the endpoint that owns it returns — `ResidentInvoice`, `VisitorPass`,
`ComplaintSummary`, `Notice`, `NotificationItem` — and the only things computed here are counts over
those.

That is a deliberate constraint rather than an economy. A home screen that renders a bill in its own
bespoke shape is a home screen that will one day show a different amount than the Payments page, and
the resident will believe the smaller one.

**It is separate from `/dashboard/snapshot`, not a role branch inside it.** An admin wants counts
across the community; a resident wants *their* dues, *their* visitors, *their* complaints. One payload
whose shape depends on a runtime role cannot be typed, needs a fixture per role to test, and is one
`if` away from putting a community-wide figure in front of a resident.

**The parts are read in sequence, not in one transaction.** The dues can be a heartbeat older than
the visitors, so `generatedAt` is when the payload was assembled — not when any part of it was true.
A resident refreshing a home screen is not asking for a consistent cut of the database, and paying
for one would be paying for something nobody wanted.

### `GET /api/v1/resident/snapshot`

Everything the resident home screen renders, in one call. **Takes no parameters** — tenancy is the
resolved membership and its community, so there is nothing a caller could send that would widen what
comes back.

| Response field | Notes |
|---|---|
| `unreadNotifications` | The badge. Counted across the **whole feed**, never across the five events below — a badge drawn from the page would be wrong the moment anybody scrolled |
| `dues.outstandingTotal` | Summed over the unpaid bills actually read |
| `dues.isPartialTotal` | True when there were more unpaid bills than one read carries, which makes the total a lower bound. False for any resident with a normal number of them. A number that is quietly too small is worse than a number with a caveat: the resident pays what they are shown and believes they are square |
| `dues.primaryInvoice` | The bill the home screen offers to settle: the maintenance one if there is one, otherwise the **oldest** payable. Never the newest — that would hide an overdue bill behind a fresh one. A whole `ResidentInvoice`, so the home screen's Pay button and the Payments page's are drawn from one `isPayable` |
| `visitors.expectedGuests` | **Guests, not passes.** One pass for a party of twelve counts as twelve. `Expected` and `Approved` are counted together, because to the resident they are one thing: somebody who has not arrived yet |
| `visitors.checkedInGuests` | Guests currently inside, counted the same way |
| `visitors.pendingApproval` | Up to three whole passes, because the home screen approves and rejects from the card without navigating. `pendingCount` is all of them |
| `complaints` | The newest five, and how many the caller has raised. No open/closed split: the screen renders statuses and counts nothing, and a number nobody asked for is a number that has to be kept correct forever |
| `notices` | The three most recent published notices. The one part of this payload that is not personal |
| `activity` | The caller's five most recent notifications |
| `generatedAt` | When the server assembled this |

**`activity` is the notification feed, and the design document said it should not be.** §5.7 of
`RESIDENT_BACKEND_DESIGN.md` reserved `member_activity` for this, reasoning that a second activity
table would mean two feeds that disagree. The reasoning is right; its premise is not. Nothing in this
project writes `member_activity` — not a trigger, not a service, and not the admin dashboard, which
reads `audit_events` instead — so serving the home screen from it would ship a strip that is empty by
construction and stays empty. §5.8 had already made `notifications` the durable record of *every
user-visible event*, which is exactly what an activity strip shows; writing those events a second time
would create the very pair of disagreeing feeds §5.7 set out to prevent. The design document has been
corrected rather than obeyed.

---

## 15. Not yet implemented

**Both build orders are complete.** The admin dashboard's (`ADMIN_DASHBOARD_BUILD_PLAN.md` §4,
steps 3–9) and the resident backend's ([`design/RESIDENT_BACKEND_DESIGN.md`](design/RESIDENT_BACKEND_DESIGN.md)
§9, steps 1–8) are all documented above. Nothing that was planned as an endpoint is outstanding.

This section is what remains anyway, and it is three different kinds of thing: wiring nobody has done,
halves of features that live outside this repository, and stories whose missing part was never an
endpoint. Listed so the frontend team can see what will not answer yet, and why.

**No migration has been applied to any database — `0001` included.** Every endpoint in this document
is code with a passing test suite and no schema underneath it. That is the whole remaining risk, and
it is `DECISIONS_NEEDED.md` F1. `0001`'s GIST exclusion constraint on `amenity_bookings` is the only
thing standing between two residents and the same hall, and it has never executed; nor has `0031`'s
SLA rule, `0032`'s code hashing, or `0033`'s two settlement RPCs — the four places where the database,
not the API, is what makes a guarantee true. The rest of §F is unchanged — the private
Storage bucket `complaint-attachments` does not exist yet (F2), and rate limiting (F3) and optimistic
concurrency (F4) are unowned.

**`POST /notices` emits no notification, and it is the one place the `0030` substrate is not wired.**
Every other user-visible event — complaint transitions, visitor decisions, payments — writes a
notification row in the same statement that writes the thing it is about. Publishing a notice writes
the notice and stops, so a resident who has not opened the app learns nothing. That is `US-2.4`
verbatim, which is why it stays **partial** (§16.4). It is one call to `notify_community_roles` inside
`notices_service.create_notice`, `notices` belongs to the admin workstream, and it is not being
retrofitted here because it should land in the transaction rather than beside it.

**`frontend/public/` has no service worker.** Web Push is served end to end on the backend — VAPID
keys, the subscription table, the sender (§5.3) — and a browser cannot receive a push without a
`sw.js` registering `push` and `notificationclick` handlers. Until it exists, every notification in
this API is only observable inside an open tab, which is the precise thing `US-2.1`, `US-2.4` and
`US-2.7` ask to stop requiring — so all three stay partial on a file this repository does not own.
`RESIDENT_BACKEND_DESIGN.md` §10.5 states the shape it needs; the file itself is the frontend team's.

**Visitors are now half-built, and it is worth being exact about which half.** §13 serves everything
a *resident* does: mint a pass, list and read their own, and answer or withdraw one. Nothing serves
the **gate** — no endpoint presents a pass, verifies a code, checks a guest in or out, or raises the
`Pending Approval` request that `/approve` and `/reject` exist to answer. That is security software,
it is not in this repository, and two things wait on it:

- **A gate-verification endpoint must rate-limit by community** before a six-digit code is exposed to
  guessing. §13 states the obligation; nothing enforces it yet because nothing verifies yet.
- **`requireVisitorPreapproval`** (§11) stays a stored setting with no reader, because the rule it
  expresses — may the gate admit someone with no pass — belongs entirely to the missing half.

`0022` had visitors and security sharing one catalogue row — `absent`, *"no visitor backend"*. `0032`
splits them: `visitor-management` becomes `partial`, and **`security-gate-management` stays
`absent`**, because it is the missing half rather than a partly built one. Rounding it up because a
neighbouring feature moved is how a status board stops being worth reading.

> **Every one of `0022`'s catalogue updates had matched zero rows until 2026-08-04.** It wrote
> `('complaints', 'complaint_management')`, `('visitors', 'visitor_management', 'security')` and four
> more in that shape; the catalogue holds ten hyphenated codes seeded in `0001` and none of those is
> one of them. Nothing failed, because an `update … where` that selects nothing is a success — so
> every module sat at the column default, `absent`, and the Settings screen, which exists precisely
> so a toggle cannot imply a backend that is not there, would have reported that none of this backend
> exists. `0022` is corrected in place; it has never been applied to any database.

**Three things about money remain unbuilt**, and they are the same three as before §14: nothing runs
a billing cycle, nothing charges a late fee, and no real payment gateway is integrated (`0033`'s is a
simulator, and every row it writes says `simulator` so the two can never be confused). The first two
are `DECISIONS_NEEDED.md` A22 and A23.

**A notice still has no effective date**, so `US-2.11` — being reminded before a rule takes effect —
has nothing to build on. It is one column, and `notices` belongs to the admin workstream, so the story
is theirs to schedule.

**Nothing verifies a resident's contact details.** `US-2.9` asks for a *verified* directory; §14
serves a current and maintained one, which is the part a schema can carry. Verification is a process,
and it is nobody's job yet.

**Adding a resident** has no dedicated endpoint and will not get one: it is
`POST /admin/invitations` (§4). The frontend's "Add Resident" creates one user record per phone plus
one shared invite; we mint one invite per phone instead, which is agenda item 5 and still open.

---

## 16. User stories → endpoints

The team's requirements live in **[`product/`](product/)**:
[`USER_IDENTIFICATION.md`](product/USER_IDENTIFICATION.md) (three user tiers) and
[`USER_STORIES.md`](product/USER_STORIES.md) (24 stories, `US-1.1` … `US-3.6`). This section is the
traceability matrix between them and the surface documented above.

> **Standing rule.** An endpoint added, changed or removed updates this matrix in the same commit.
> A matrix that is 80% current is worse than none, because it is believed.
>
> **This is now enforced, not just asked for.** The same mapping is carried per operation in
> [`openapi.yaml`](openapi.yaml) as `x-user-stories`, sourced from
> [`backend/scripts/api_annotations.py`](../backend/scripts/api_annotations.py). The exporter
> refuses to build if an operation has no entry there, or if an entry names a route that no longer
> exists — so adding an endpoint fails the build until somebody says which stories it serves,
> including saying that it serves none. Prose and spec can still disagree about *wording*; they can
> no longer disagree about *which endpoints exist*.

**Read the gaps first.** A matrix that only recorded hits would be a list of things we already knew.
The rows marked *none* and *partial* are the ones that change what anybody does next, so the
shortfall is named in every row rather than being inferable from a blank cell.

### 16.1 Scope, stated once

This branch is the **admin dashboard** backend. Two whole surfaces the stories assume — the resident
mobile app and the security gate — have no workstream. That is the agreed scope, not a miss, and
it accounts for 11 of the 24 stories on its own. The matrix still lists them, because a story with
no owner is a decision that should be visible rather than a silence.

**One structural cause explains most of §3 and half of §2.** A staff member has no login: `POST
/departments/{id}/staff` writes a `staff_assignments` row and leaves `membership_id` null on
purpose. So every story written in the voice of a Security Manager or a Facility Manager is
unreachable by that person *by construction*, not because an endpoint is missing. Closing those
stories starts with deciding whether staff get accounts — see
[`product/USER_IDENTIFICATION.md`](product/USER_IDENTIFICATION.md).

### 16.2 Coverage

| | Served | Partial | None |
|---|---|---|---|
| §1 Administrative staff (6) | 3 | 3 | 0 |
| §2 Resident (12) | 5 | 5 | 2 |
| §3 Security manager (6) | 0 | 1 | 5 |
| **Total (24)** | **8** | **9** | **7** |

The shape of that table was, until 2026-08-04, the honest summary of this branch: **the
administrator's stories substantially built, the resident's built but unreachable, and the security
manager's not started.** Not one resident story was fully served, and the reason was almost never a
missing capability — it was a missing delivery path.

The first three resident stories to close are all complaints (US-2.5, US-2.6, US-2.8), and they
closed together because they were one gap seen from three angles: a surface the resident could
actually reach. **US-2.2 closed next, the same way** — the visitor table had modelled a pre-approval
since the baseline and no endpoint reached it. The pattern is worth naming, because four of the five
remaining partials have the same shape: the capability exists, the projection that would show it to a
resident does not.

**US-2.1 and US-2.2 were compiled as one row and are now two verdicts.** One surface blocked both;
the surface arrived and only one finished. A matrix that keeps stories paired after the thing joining
them is gone reports the weaker of the two as the state of both.

**US-2.12 closed on the transaction, not on the gateway** — which is what the story asks for. Its
recorded reason for being partial was *"no gateway is integrated"*, and that was reading the story as
being about payments; it is about a payment and a booking confirmation happening together. Both are
one statement now, and the gateway that drives them is a simulator the product asked for, labelled as
one on every row it writes. The failure path is the part worth having: with a real provider in test
mode a decline is a card you have to go and find, and here it is one expiry date.

**The totals were briefly level at 8/8/8**, which was a coincidence and not a milestone. It is
recorded because a reader who saw three equal numbers would have assumed somebody rounded — and
because step 7 has since moved US-2.3 off zero, which is the more useful fact.

**US-2.3 moved from none to partial, and stops there for a reason no endpoint can fix.**
`GET /resident/snapshot` is the enabling backend the story's own *"Backend: None"* note asks for:
everything the home screen shows in one call, with pending visitor passes carried whole so that
approving one is a tap rather than a journey. The half that remains is the **home-screen widget** —
an operating-system surface, on a product that is a web application with no native client. Recording
this as served would claim a capability the platform does not have.

**US-2.7 is the deliberate exception.** It is backend-complete and still recorded partial: the
notifications are written, both transports carry them, and no phone can receive one until the
frontend has a service worker. That is the one row in this table where *served* would be a claim
about software this repository does not contain.

### 16.3 Administrative staff

#### US-1.1 — Partial cancellation of multi-day bookings — **served**

| Endpoint | Role |
|---|---|
| [`POST /amenity-bookings/cancel`](#post-apiv1amenity-bookingscancel) | Cancels a **list of occurrence ids**, not a booking |
| [`POST /amenity-bookings/{occurrenceId}/force-cancel`](#post-apiv1amenity-bookingsoccurrenceidforce-cancel) | Admin override when the resident objects |
| [`GET /amenities/{amenityId}/bookings`](#get-apiv1amenitiesamenityidbookings) | The days to choose from |

The story is the reason the cancel route takes `occurrenceIds[]` rather than a booking id. The
all-or-nothing rule is the same story read carefully: an administrator cancelling day 3 of 5 must
not be told "success" when day 3 was the one that failed.

#### US-1.2 — Auto-sync cancellations to accounts — **served**

| Endpoint | Role |
|---|---|
| [`GET /amenities/{amenityId}/ledger`](#get-apiv1amenitiesamenityidledger) | `cancellationHistory`, `refundHistory`, `auditTrail`, `paymentStatus` |
| [`GET /amenities/{amenityId}/ledger/summary`](#get-apiv1amenitiesamenityidledgersummary) | The money totals |
| [`POST /amenity-bookings/{occurrenceId}/refund`](#post-apiv1amenity-bookingsoccurrenceidrefund) | Returns the deposit |

**There is no sync, which is why it cannot fall out of sync.** Every figure the ledger reports is
derived from the same append-only event stream the cancellation writes to; no balance is stored, so
no balance can disagree with the rows beneath it. A cancelled booking still holding a refundable
deposit reports `refund_pending`, not `cancelled` — the interviewee's "not reflected in accounts"
was exactly this case, and the `CASE` arm ordering is what fixes it.

*Caveat worth stating plainly:* "the accounts module" in the interview means their existing finance
system. This satisfies the story for **amenity money**. Invoices (§9) are a separate ledger, and
nothing exports to an external accounting package.

#### US-1.3 — Real-time sync across modules — **partial**

| Endpoint | Role |
|---|---|
| [`GET /events`](#51-live-updates--get-events) | SSE, audience-scoped; one stream serving every portal |
| [`GET /dashboard/events`](#51-live-updates--get-events) | Deprecated alias for the above; the admin frontend is wired to this path |
| `GET /dashboard/snapshot` | The authoritative re-read every event asks for |

**Shortfall:** the story names three consumers — resident app, admin portal, reports. The transport
now serves all roles: `0028_event_audience.sql` gives every outbox row an audience, so a single
stream can reach a resident without also handing them admin traffic. What is still missing is a
**resident client subscribed to it** and resident-facing topics to subscribe to — those arrive with
the notification substrate. Reports remain computed per request rather than pushed. Delivery is also
at-most-once by design: correctness comes from re-reading, not from the event.

> **Correction.** This section previously read "the stream serves the admin portal only", which
> stated a live disclosure as a missing feature. The stream was open to *any* active member and
> fanned out by community alone — a resident who opened it received their neighbours'
> `access_request.created` frames, applicant name included. Nothing exploited it because no
> non-admin client connected. `0028` closes it.

#### US-1.4 — Streamlined resident information update — **partial**

| Endpoint | Role |
|---|---|
| `GET /dashboard/snapshot` | `users[]`, `complaints[]`, `bookings[]`, `payments[]` in **one** response |

**Shortfall: there is no write.** The single-screen *read* is the strongest part of the whole API —
one call returns everything the story asks to see in one place. `PATCH /residents/{id}` and
`DELETE /residents/{id}` existed and were **removed** on 2026-07-30 by the frontend wiring audit,
because no screen called them. That was correct at the time and is wrong against this story: the
interviewee's complaint was *"updating resident details such as email addresses is not sufficiently
streamlined"*, which is a write.

> **Recommendation.** Restore `PATCH /residents/{id}`. It is the cheapest closed gap in this matrix —
> the service and repository code was deleted but is recoverable from history, and the story is a
> direct interviewee quote.

#### US-1.5 — Simplified booking management workflow — **served**

| Endpoint | Role |
|---|---|
| [`POST /amenities/{amenityId}/bookings`](#post-apiv1amenitiesamenityidbookings) | Admin books **on a resident's behalf** — one call, no impersonation |
| [`POST /amenities/{amenityId}/bookings/request`](#post-apiv1amenitiesamenityidbookingsrequest) | The resident path |
| [`GET /amenities/{amenityId}/approvals`](#get-apiv1amenitiesamenityidapprovals) | The queue |
| [`POST /amenity-bookings/{seriesId}/approve`](#post-apiv1amenity-bookingsseriesidapprove) · [`reject`](#post-apiv1amenity-bookingsseriesidreject) | One decision per **request**, not per day |
| [`POST /amenities/{amenityId}/blocks`](#post-apiv1amenitiesamenityidblocks) | Take a slot out of circulation |

"Redundant steps removed" is met structurally: approval covers a whole request rather than one day,
and the cleaning buffer no longer blocks shared bookings. `availableActions` on each ledger row is
computed from the same rules the write endpoints enforce, so the UI cannot offer a step the API will
reject — a class of redundant step the interviewee would have experienced as an error message.

#### US-1.6 — Automated administrative reports — **partial**

| Endpoint | Role |
|---|---|
| [`GET /amenity-reports`](#get-apiv1amenity-reports) | Rows + six KPIs, filtered by date, amenity and status |
| [`GET /amenities/{amenityId}/ledger`](#get-apiv1amenitiesamenityidledger) | Amenity billing, per booking |
| [`GET /billing-settings`](#get-apiv1billing-settings) | The rates the numbers come from |

"Generated automatically" is met — `kpis` aggregates **every matching row**, not the current page,
which is the whole reason that endpoint exists. Two shortfalls:

1. **"Exportable" is not built.** Every response is JSON. Nothing emits CSV or PDF, so export is
   still whatever the browser does with the rows it happens to have loaded.
2. **"Gym subscription reports" have no data model.** There are bookings and there are invoices;
   there is no recurring subscription anywhere in the schema. This is a missing entity, not a
   missing endpoint.

### 16.4 Resident

Read this section against one fact: **no resident-facing client calls this API.** The frontend in
this repo is the admin dashboard. So "partial" below almost always means *the data is right and
nothing shows it to a resident* — a materially different problem from *the backend cannot do it*,
and a much cheaper one.

#### US-2.1 — Visitor approval notifications — **partial** · US-2.2 — Pre-approval — **served**

> **Closed for US-2.2, 2026-08-04**, by `0032` and §13. The two stories were compiled as one row
> because one missing surface blocked both; they separate here because that surface arrived and only
> one of them is finished.
>
> | Endpoint | Role |
> |---|---|
> | [`POST /visitor-passes`](#post-apiv1visitor-passes) | Pre-approval in one call. Purpose, guest count, and a code returned exactly once |
> | [`GET /visitor-passes`](#get-apiv1visitor-passes) | Current and history, split by a column the database computes |
> | [`GET /visitor-passes/{passId}`](#get-apiv1visitor-passespassid) | The QR screen |
> | [`POST /visitor-passes/{passId}/approve`](#post-apiv1visitor-passespassidapprove--reject) · `/reject` | The resident's answer to a gate request |
> | [`POST /visitor-passes/{passId}/cancel`](#post-apiv1visitor-passespassidcancel) | Withdraw an unused pass |
>
> **US-2.1 stays partial for a reason that is not a missing feature.** Its answer exists — approve
> and reject are real, and they notify the gate. What does not exist is the *question*:
> `visitor.approvalRequested` is written when somebody arrives unannounced, and nothing writes it,
> because that is gate software this repository does not contain. On top of that sits the same
> absent service worker as US-2.7. A story about being asked cannot be served by building the reply.
>
> `require_visitor_preapproval` also stays unread, and correctly — see §15.

| Object | State |
|---|---|
| `visitor_requests`, `visitor_events` | **Exist in the baseline** — status enum, `valid_from` / `valid_until`, `pass_hash`, check-in/out timestamps |
| `GET /dashboard/snapshot` → `visitors[]` | **Exists**, and filters to the caller's own for non-admins |
| `community_settings.require_visitor_preapproval` | **Stored by `0018`**, read by nothing |
| Any write endpoint | **Missing** |

The gap is narrower than "no visitor surface". The table models a pre-approval and the read is
already scoped correctly per resident; what is absent is `POST /visitors` and everything after it.
`GET /settings` reports this honestly — `visitor-management` returns its `backendStatus` as not
implemented rather than claiming coverage.

**Push was a separate and larger gap. It is now built** (§5.2, §5.3): a durable `notifications`
record, an audience-scoped SSE frame, and Web Push over our own VAPID keypair — no FCM account, no
device-token table, no vendor SDK. What is still missing for *these two stories* is narrower and
different in kind: **nothing writes a visitor notification yet**, because the visitor write endpoints
that would call `notify_member` do not exist. The transport is no longer the blocker; the emitter is.

The paragraph above is left in place because it was true when the matrix was compiled and it is the
reason the transport was built. The correction is the entry, not a rewrite of the finding.

#### US-2.3 — One-tap quick access — **partial**

| Endpoint | Role |
|---|---|
| [`GET /resident/snapshot`](#get-apiv1residentsnapshot) | Dues, visitors, complaints, notices and recent activity in **one call**, so no common task begins with a navigation |
| [`POST /visitor-passes/{passId}/approve` · `/reject`](#post-apiv1visitor-passespassidapprove--reject) | The action the story names. The snapshot carries pending passes **whole**, so answering one is a tap on the card rather than a journey into the visitors page |
| [`POST /invoices/{invoiceId}/pay`](#post-apiv1invoicesinvoiceidpay) | The other one-tap action: the home screen offers a specific bill, and `primaryInvoice` is the whole invoice so the button beside it is the same button the Payments page draws |

The story's own note reads *"Backend: **None** — a client concern, but it needs endpoints that do not
exist."* Those endpoints exist now, which is why this row moved off zero.

**It stops at partial because of the widget.** The story asks for *"one-tap access, including a
home-screen widget"*, and a home screen in that sense is an operating-system surface. HomeBandhu is a
web application with no native client and none planned (`PO`, 2026-08-03), so the ceiling is what a
browser can do — a PWA install and a shortcut, not an OS widget. No endpoint closes that, and calling
this served would be a claim about the platform rather than about the API.

#### US-2.4 — Notifications for notices — **partial**

| Endpoint | Role |
|---|---|
| [`GET /notices`](#get-apiv1notices) | The resident's read of the board — published notices only |
| [`POST /notices`](#121-post-notices--post-a-notice) | Publishes immediately; fires the `notices` SSE trigger |

**Shortfall, as it was:** the same missing push transport as US-2.1. The event reaches connected
admin browsers. A resident who has not opened the app learns nothing — which is the story verbatim.

**Shortfall now:** the transport exists (§5.2, §5.3) and `POST /notices` does not yet call
`notify_member`. One line inside the write, and it lands with the notice in the same transaction —
which is the discipline the whole design insists on, and the reason it is not being retrofitted here.
`0033` gives residents somewhere to read a notice; the story is about being *told* about one, and a
read endpoint is not a notification.

#### US-2.5 — Simple complaint submission with priority — **served**

| Endpoint | Role |
|---|---|
| [`POST /complaints`](#post-apiv1complaints) | The create endpoint, with `urgency` writing to a real `priority` column (`0031`) |

> **Closed, 2026-08-04, by `0031_resident_complaints.sql`.** Both halves the assessment below asks
> for landed together: the column, and the endpoint that writes it. The form's minimal shape is
> honoured as it stands — five fields, one of them optional — except for attachments, which are
> tracked in §15 rather than half-accepted.
>
> One thing changed on the way in that the assessment did not name. `dashboard_service.py`'s
> permanent `Medium` was not a projection bug so much as a symptom: the field it read did not exist.
> It does now, so that line reports the real value without anyone editing it.
>
> The present tense below is left as it stood. It is the argument that produced the endpoint.

**A resident cannot raise a complaint through this API.** There is no `POST /complaints`. Creation
was never in the admin-dashboard build order, because the admin dashboard reads complaints rather
than filing them.

**The priority selector has nowhere to write.** `complaints` has no priority column — not in the
baseline, not in `0020`. The only `priority` in the schema is on `work_orders`, which is a different
thing. The snapshot still reports an `urgency` on every complaint:
`dashboard_service.py:86` computes it as `str(row.get("priority") or "Medium").title()`, from a
column the non-legacy query does not select and the database does not have — so **every complaint
reports `Medium`, permanently.** This story needs one column before it needs an endpoint.

#### US-2.6 — Complaint status tracking with history — **served**

| Endpoint | Role |
|---|---|
| [`GET /complaints`](#get-apiv1complaints) | The list the tracking starts from — status, progress and expected resolution on every row |
| [`GET /complaints/{complaintId}`](#get-apiv1complaintscomplaintid) | The timestamped update history, read by the resident who raised it |
| [`POST /complaints/{complaintId}/reopen`](#post-apiv1complaintscomplaintidreopen) | The resident's half of the history: back, with a reason |
| [`POST /complaints/{complaintId}/resolution`](#post-apiv1complaintscomplaintidresolution) | Closes the loop the story leaves open |
| [`PATCH /complaints/{complaintId}`](#patch-apiv1complaintscomplaintid) | Writes the status **and its timeline entries in one transaction** |
| [`POST /complaints/{complaintId}/comments`](#post-apiv1complaintscomplaintidcomments) | `resident` visibility reaches the resident; `internal` reaches neither their thread nor their timeline |
| `GET /dashboard/snapshot` → `complaints[]` | Returns `status`, `comments[]` and `history[]`, **filtered to the caller's own complaints** for a non-admin |

> **Closed, 2026-08-04, by `0031`.** The shortfall below was real and is no longer this story's
> problem: `complaint_overview` selects `progress_percent` and `GET /complaints` returns it as
> `progress`, so *"residents cannot see meaningful progress"* has an endpoint that answers it. The
> snapshot still drops the column on its own path — that is unchanged, it is the dashboard
> workstream's line, and it now affects only the admin projection rather than every reader.
>
> *"Repeated calls and follow-ups are often necessary"* is answered from the other side as well: every
> transition notifies the resident, so following a complaint stops meaning asking about it.

The *writing* half answers the first pain point by design rather than by feature. *"Statuses are not
updated consistently"* — a status cannot change without a timeline entry, because the two are one
transaction; an audit trail with holes is worse than none, since it looks complete. Resolving stamps
`resolvedAt` and reopening clears it, so a reopened complaint never keeps claiming it was resolved.
`updateNote` writes a resident-visible entry **even when nothing else changes**, so an administrator
can report progress without faking a status change.

> **Shortfall — and it is the interviewee's own words.** *"Residents cannot see meaningful
> progress."* `0020` adds `progress_percent` as a real column and `PATCH /complaints/{id}` writes it.
> But `dashboard_repository.py:66` selects that column **only in the `legacy` branch**; on the path
> that runs against our migrations it is never fetched, so `dashboard_service.py:85` falls through to
> its default and **every complaint reports progress 0, or 100 once resolved.** The number this story
> is about is written correctly and then not read.

#### US-2.7 — Complaint lifecycle notifications — **partial**

Every transition the story names — acknowledged, updated, reassigned, resolved — writes a
`complaint_events` row (`0020`), and `complaints` is one of the 12 tables on the `dashboard.refresh`
trigger. **The events existed and nothing delivered them.** That was one gap across US-2.1, US-2.4
and US-2.7, not three, and it is why the delivery layer was built as its own step rather than three
times over. With §5.2 and §5.3 in place, what is left for this story is the complaint RPCs calling
`notify_member` — which lands with the complaint endpoints, in the same transaction as the
transition it describes.

> **Backend-complete, 2026-08-04, and still recorded as partial.** `0031` supplies the emitters the
> paragraph above is waiting for: `raise_complaint`, `reopen_complaint`,
> `confirm_complaint_resolution`, and — the ones this story actually names — `update_complaint` and
> `add_complaint_comment`, both replaced so that a status change and a public comment write a
> notification inside the transaction that causes them. Every transition the story lists now produces
> a durable record, an SSE event, and a queued push.
>
> **What is missing is not in this repository's backend.** `frontend/public/` has no service worker
> and no manifest, so a push cannot be received while the app is closed — which is the whole of what
> the story asks for. Reporting this closed would be reporting a phone that does not buzz as a phone
> that buzzes. The in-app half (feed, badge, live update) does work end to end.
>
> One deliberate omission: a **reassignment does not notify**. The story lists it, and an assignee
> changing or a progress bar moving from 40% to 45% is not something to wake a phone for. A resident
> notified about everything stops reading notifications, which costs more than the ones they miss.
> The change is on the timeline either way. Reversing this is one `if` in `0031` §9.

#### US-2.8 — Complaint accountability — **served**

| Endpoint | Role |
|---|---|
| [`GET /complaints`](#get-apiv1complaints) | `assignee`, `expectedResolutionAt` and `isOverdue` reach the resident here |
| [`POST /complaints`](#post-apiv1complaints) | The expected resolution is computed on insert, so it exists before anyone asks |

> **Closed, 2026-08-04, by `0031`.** All three things the story asks for — who is responsible, when to
> expect action, and overdue flagging — now reach the person who raised the complaint. `isOverdue` is
> computed in `complaint_overview` rather than by a client, against the same clock and the same
> predicate `department_overview` already uses for its overdue count, so the resident's screen and the
> admin's cannot disagree about one complaint.
>
> The finding below stands unchanged as a description of the **snapshot**: it still drops those
> fields, it is still one line in someone else's file, and it is still worth reading as one problem
> rather than four. What changed is that it is no longer the only path to the data.

`PATCH /complaints/{complaintId}` accepts `assignee` and `expectedResolutionAt`, stored by `0019` as
`assigned_to_membership_id` / `assignee_label` / `due_at`. Ownership and expected resolution are
therefore **recorded**.

> **Finding — the fourth instance of one bug.** `dashboard_service.py:_complaints()` projects
> `{id, title, description, category, status, progress, urgency, raisedBy, flat, date, comments,
> history}` and **drops `assignee` and `due_at` entirely**. Both fields this story is about are
> written by our endpoint and discarded before any resident or administrator can read them. Overdue
> flagging is therefore impossible client-side: there is no due date to compare against.
>
> It is worth stating as one problem rather than four, because it is one problem. **Our writes and
> their reads disagree about four fields**, in two files, all in the same direction:
>
> | Field | Written by | Lost at |
> |---|---|---|
> | `assignee` / `due_at` | `PATCH /complaints/{id}` | the projection (US-2.8) |
> | `progress_percent` | `PATCH /complaints/{id}` | the non-legacy column list (US-2.6) |
> | `category` / `urgency` on notices | `POST /notices` | the projection (§12.1) |
>
> Each is one line. None is ours to change — `dashboard_service.py` and `dashboard_repository.py`
> belong to the dashboard workstream. Raising them together is more useful than raising them
> separately, because separately each looks like an oversight and together they look like a missing
> convention: **no check anywhere asserts that a field a write endpoint accepts is a field the
> snapshot returns.**

#### US-2.9 — Verified management contact directory — **partial**

| Endpoint | Role |
|---|---|
| [`GET /departments`](#get-apiv1departments) · [`GET /departments/{departmentId}`](#get-apiv1departmentsdepartmentid) | The directory, with `contactEmail`, `contactPhone`, hours and the head |
| [`POST`](#post-apiv1departments) · [`PATCH`](#patch-apiv1departmentsdepartmentid) · [`DELETE /departments/{departmentId}`](#delete-apiv1departmentsdepartmentid) | Keeping it current |
| [`PUT`](#put-apiv1departmentsdepartmentidstaff) · [`POST`](#post-apiv1departmentsdepartmentidstaff) · [`PATCH`](#patch-apiv1departmentsdepartmentidstaffstaffid) · [`DELETE …/staff`](#delete-apiv1departmentsdepartmentidstaffstaffid) | Roster and roles |

*"Outdated, unclear, or insufficiently maintained"* is met on two of three counts. **Clear** —
every entry has a role and a department. **Maintained** — deactivation rather than deletion means a
past assignment stays attributable, so the directory can be tidied without corrupting complaint
history.

**The half that was missing arrived with `0033`.** Until then the directory was maintained and no
resident could read it — [`GET /directory/contacts`](#get-apiv1directorycontacts) is the resident's
projection of the same departments, so it is current for the reason admin screens are: somebody keeps
it up for purposes of their own. `Profile.jsx`'s five hard-coded numbers were the
stale-by-construction version of exactly this.

**Shortfall: "verified" is nobody's job.** No field records who last confirmed a number, or when.
A directory nobody is accountable for re-checking goes stale exactly as the interviewee described,
and the API cannot currently tell a maintained entry from an abandoned one. That is a process, not a
column, which is why serving the read did not close the story.

#### US-2.10 — Designated building representative — **none**

`PATCH /departments/{departmentId}` designates a **head**, and `POST /admins` promotes a member. But
`departments` has no `building_id`, and `staff_assignments` has no building. Buildings exist
(`units.building_id`); nothing connects a person to one. This is a schema gap, and small: one
nullable column on `departments` plus a filter.

#### US-2.11 — Timely notices with effective dates — **none**

`POST /notices` publishes **immediately** — there is no draft state, no schedule, and, decisively,
**no effective date**. The story asks to be reminded *before a rule takes effect*; there is no
stored moment for a reminder to point at. Needs a nullable `effective_at` column, plus the same
absent push transport. §12.1 records why publishing is immediate: the screen has no schedule
control, and a nullable `publishedAt` left unset would create notices nobody could ever see.

#### US-2.12 — Reliable booking payment confirmation — **served**

| Endpoint | Role |
|---|---|
| [`POST /amenity-bookings/{bookingId}/pay`](#post-apiv1amenity-bookingsbookingidpay) | **The story.** Payment and confirmation in one statement, or neither |
| [`GET /amenity-bookings/mine`](#get-apiv1amenity-bookingsmine) | What a resident has booked and what is still owed on it |
| [`POST /amenity-bookings/{occurrenceId}/payments`](#post-apiv1amenity-bookingsoccurrenceidpayments) | The admin's record of a payment taken elsewhere |

The failure the interviewee described — *money deducted, no booking* — is not a gateway defect. It is
a payment recorded in one transaction and a booking confirmed in another, with a crash in between.
`settle_amenity_booking_payment` does both or neither, and on a decline it leaves the booking exactly
as it was rather than half-confirmed.

**This was recorded partial on the grounds that "no payment gateway is integrated", and that was
reading the story as being about payments.** It is about a payment and a confirmation happening
together. One is integrated now — a simulator the product asked for, which writes `provider =
'simulator'` on every row so that simulated money can never be mistaken for money that moved.

**What that costs, stated plainly.** No real money moves, so nothing here has met a real acquirer,
and the asynchronous half a live integration adds — a webhook arriving after the response — is not
built. `payment_events` and the idempotency key are already the right shape for it, which is why they
are used now rather than added later (§14.1, §14.4). What the simulator buys is the part a real
provider makes hardest: **the failure path can be run in front of somebody on demand**, and it is one
expiry date rather than a card you have to go and find.

### 16.5 Security manager

| Story | Verdict |
|---|---|
| US-3.1 event-specific access codes | **partial** — see below |
| US-3.2 auto guest access on booking | **none** |
| US-3.3 digital registers | **none** — no table |
| US-3.4 water tanker log | **none** — no table |
| US-3.5 offline fallback verification | **none** |
| US-3.6 retention + downloadable reports | **none** for gate operations |

**US-3.1 is closer than the rest and nobody planned it that way.** `visitor_requests` carries
`pass_hash` (a hashed code, unique), `valid_from` and `valid_until` (a scheduled window that can be
set days ahead and activate later), and `0018` added `community_settings.visitor_code_ttl_minutes`.
That is four of the story's five requirements modelled already. The fifth — one code admitting
*many* guests — is the only genuine schema change, and it is the one thing the current model cannot
express, since a pass belongs to one request.

> **Updated 2026-08-04 by `0032`.** *Issue* and *revoke* now exist —
> `POST /visitor-passes` and `/cancel`, with the code hashed and returned once. **Scan does not**,
> and it is the requirement the story is actually about: no endpoint verifies a code, and §13
> records the rate-limiting obligation that a verification endpoint will carry. The multi-guest
> requirement is nearer than it was — `guest_count` is a column now — but one code still admits one
> *request*, so the fifth requirement is still the genuine schema change.
>
> The paragraph above is left as compiled. Two of its five requirements moved; the verdict did not,
> because the missing one is the point of the story.

**US-3.2's blocker has moved, not cleared.** `POST /amenities/{amenityId}/bookings` and the approve
route are where "prepare guest access on booking" would hook in, `0007`'s outbox already fires on
amenity tables, and — as of `0032` — `create_visitor_pass` is a real function it could call. What is
missing now is the hook itself, which is a decision nobody has made: whether an approved booking
should mint passes automatically, and for whom. It was blocked on US-2.2; it is now blocked on a
product ruling.

**US-3.6, stated fairly.** Retention is *not* a gap: nothing this backend writes is ever deleted or
aged out, complaint and booking history are append-only, and the ledger reconstructs any past state
from its event stream. So *"records older than three months are unavailable"* is already solved for
everything we store. What is missing is (a) any gate-operations data to retain and (b) the
downloadable report — the same export gap as US-1.6.

### 16.6 Endpoints that serve no story, and why that is fine

**48 of the 99 operations map to no story in the document.** Not a defect — the team wrote stories
about pain points in an existing product, not about the plumbing every product needs.

| Group | Ops | API type | Why no story |
|---|---|---|---|
| `/auth/*` | 16 | Functional | Nobody writes a user story about signing in until it breaks |
| `/access-requests/*`, `/admin/access-requests/*` | 7 | Feature | Joining a community; the interviews were with people already in one |
| `/invitations/*`, `/admin/invitations` | 3 | Feature | Same |
| `/communities/*`, `/onboarding/community` | 3 | Feature | Founding a community — a once-per-community act |
| `/dashboard/amenities` `POST` · `PUT` · `DELETE` | 3 | Master data | Amenity catalogue upkeep; the stories assume amenities already exist |
| `/settings`, `/billing-settings` | 3 (of 4) | Configuration | Configuration behind other features |
| `/amenities/available` | 1 | Feature | Reading the catalogue. The booking stories assume a resident already knows which amenity they are booking |
| `/notifications/{id}/read`, `/notifications/read-all` | 2 | Feature | Managing the list rather than being notified. US-2.1, US-2.4 and US-2.7 all ask to be *told* |
| `/push/vapid-key`, `/push/subscriptions`, `/push/subscriptions/unregister` | 3 | Non-functional | Web Push plumbing. A resident experiences US-2.1; nobody experiences a VAPID key |
| `/complaints/{id}/read` | 1 | Feature | Bookkeeping the unread badge US-2.6 and US-2.8 imply. Nobody narrates having read an update when asked what is wrong with complaints |
| `/invoices/mine`, `/invoices/{id}/pay` | 2 | Feature | **Listing and paying maintenance dues.** A whole screen, and no story: `US-2.12`, the only payment story anybody wrote, is specifically about *amenity booking* payment, and mapping an invoice path onto it would claim coverage the interviews never gave |
| `/invoices/{id}/payments` | 1 | Feature | The admin's record of a maintenance payment taken outside the app. **Moved here from `US-2.12` on 2026-08-04** — see the note below |
| `/me/household`, `/me/household/phones` | 2 | Feature | Who is registered to a flat, and adding a number without waiting for an admin. Drawn from the prototype's Profile screen; the stories are about reaching **management** (US-2.9, US-2.10), not about the household reaching itself |
| `/health` | 1 | Non-functional | Platform liveness, deliberately outside `/api/v1` |

**The API type is the point of this table, not the absence.** Each of these operations carries
`x-no-user-story` in [`openapi.yaml`](openapi.yaml), stating `Not covered by user story` and then
what the operation *is*. `Functional`, `Configuration`, `Master data` and `Non-functional` are
plumbing, and their absence from the story set is expected. **`Feature` is not**: 22 operations here
are user-facing capability nobody wrote a story for. That is a finding about the story set, not
about the API, and §16.7 is where it turns into work.

**One of those 22 arrived by a correction rather than by new code.**
`POST /invoices/{id}/payments` carried `US-2.12` in the generated spec until 2026-08-04, and should
not have: [`USER_STORIES.md`](product/USER_STORIES.md) scopes that story to *amenity booking*
payment, §16.4's own table for it never listed this operation, and the resident invoice path beside
it was already refusing the identical mapping in writing. The role text claimed for it — payment and
record moving together — is true, and is a property of **every** settlement in this backend rather
than of the story. Traceability that flatters is worse than traceability that admits a gap, because
the gap is the finding. The recount below moves with it: **51 serve a story and 48 serve none.**

**The four `0033` added are the sharpest instance of it so far.** `Payments.jsx` is a finished screen
with a modal, two tabs and a gateway dialog, and the story set contains nothing about paying a
maintenance bill — only about paying for an amenity booking, which is a different flow. Nobody was
asked about the thing they do every month; they were asked what had gone wrong lately.

`GET /amenities/available` is the clearest example of what the category means.
`GET /amenities/available` was not derived from a story and could not have been: no interviewee
described the act of finding out which amenities exist, because in the building that is a
noticeboard. It came from the code instead — the resident booking write has never been guarded while
nothing let a resident learn an amenity id, which is a defect no amount of reading the story set
would surface. **A `Feature` row is not always a story someone forgot to write; sometimes it is one
nobody could have written.**

> **The totals move with the surface, and these are recounted, not estimated.** The figures above
> come from `x-user-stories` in the generated spec. **51 operations serve at least one story, 48
> serve none, and 51 + 48 = 99.** `0033` added eight operations, of which four map and four do not,
> and step 7 added a ninth, `GET /resident/snapshot`, which maps. The `Feature` count moved from 17
> to 21 on those eight and then to 22 when `POST /invoices/{id}/payments` gave up a story it had
> never earned. `Functional`, `Configuration`, `Master data` and `Non-functional` are unchanged at
> 16, 3, 3 and 4.
>
> **An earlier version of this section said 33 and was wrong** — a different kind of error, worth
> keeping visible. The groups always summed to 36; the 33 came from subtracting the endpoints
> §16.3–§16.5 name in their tables, which silently assumed every operation not listed as unmapped
> was mapped. Three were neither — the amenity catalogue writes, now their own row. The mistake
> survived a hand review and did not survive machine-checking the same claim, which is the argument
> for counting these from the spec rather than from this document.

The one worth flagging: **`GET /settings` is the only endpoint that reports its own gaps.** Its
`modules[]` carries a `backendStatus` per module. `security-gate-management`, `parking-management` and
`community-marketplace` report themselves unimplemented; `visitor-management` moved to `partial` in
`0032` while `security-gate-management` deliberately did not — which is the table earning its keep,
reporting two halves of one feature separately because only one of them was built. `notice-board` and
`maintenance-billing` moved to `partial` in `0033`. That is the machine-readable form of half this
matrix, and it is already wired.

> **It was also, until 2026-08-04, reporting nothing at all.** `0022` seeded those statuses with
> catalogue codes that do not exist, so every one of its six updates matched zero rows and every
> module would have read `absent` — including the ones this document has called `partial` for weeks.
> The one screen built to be honest about what is missing would have been the one lying. Corrected in
> place; the migration has never been applied.

### 16.7 What the matrix says to do next

Ordered by cost against value, not by story number.

| # | Action | Unblocks | Size |
|---|---|---|---|
| 1 | ~~Stop the snapshot dropping `assignee`, `dueAt` and `progress_percent`~~ — **routed around, not fixed**: `GET /complaints` returns all three, so US-2.6 and US-2.8 no longer depend on it. The snapshot still drops them, and it is still two lines in the dashboard workstream's file | US-2.6, US-2.8 | Two lines, still theirs |
| 2 | Restore `PATCH /residents/{id}` | **US-1.4** | Recoverable from git history |
| 3 | ~~Add `complaints.priority`~~ — **done** (`0031`), with the endpoint that writes it | US-2.5 | Closed |
| 4 | Add `notices.effective_at` | US-2.11 (half) | One column, one field |
| 5 | Add `departments.building_id` | US-2.10 | One column, one filter |
| 6 | ~~Build the visitor write endpoints~~ — **done for the resident half** (`0032`, §13): US-2.2 closes. US-2.1 does not, because nothing raises the request it answers, and US-3.2 does not, because whether an approved booking should mint passes is a ruling nobody has made | US-2.2 | Closed; the gate half is a separate surface |
| 7 | ~~Choose a push transport~~ — **done**: Web Push over our own VAPID keypair (§5.3) | US-2.1, US-2.4, US-2.7 | Was an architecture decision; now the emitters remain |
| 8 | Add CSV export | US-1.6, US-3.6 | Small, and asked for twice |

**Items 2, 4 and 5 are three small changes that close or half-close three stories.** They are the whole
argument for keeping this matrix. None would have been found by reading the code, because none of
them is a bug in any one file: three are fields written by one workstream and dropped by another,
and two are single missing columns behind features that otherwise work. The expensive items — 6 and
7 — were already known, and both have now been built. **What that leaves is a table whose remaining
rows are all small**, which is a better position than it looks: the two entries that needed a design
decision are spent, and nothing left in it is blocked on anything but doing it.

**Item 7 was the largest single lever in the table, and it has been pulled.** Four stories (US-2.1,
US-2.4, US-2.7, and US-2.3 downstream) reduce to *"tell the resident without making them open the
app"*, and none of them could be closed by any amount of backend work until something could deliver
a message to a device. It was worth deciding before more endpoints were written rather than after,
which is exactly where it landed: §5.2 and §5.3 ship before the visitor and complaint writes that
will call into them.

What it did **not** do is close those four stories, and the distinction is worth keeping sharp. A
transport with nothing emitting into it delivers nothing. Each of the four now waits on a one-line
`notify_member` call inside a write that has yet to be built — which is a task, not a decision, and
that is the whole difference this item made.

> **The first of those tasks is done.** `0031` puts `notify_member` inside all five complaint writes,
> including the two that already existed. US-2.7's emitters therefore exist, and the story is *still*
> partial — because what remains is a service worker in `frontend/public/`, which is not a backend
> task at all. The visitor, notice and payment emitters are steps 5 and 6.
>
> Worth recording plainly: **items 1 and 3 closed by different means, and only one of them is a
> fix.** Item 3 was built. Item 1 was routed around — the fields now reach a resident through a
> different endpoint, while the projection that drops them is unchanged. The stories are served
> either way, and the line in someone else's file is still wrong. A matrix that marked item 1 done
> would be recording the story's state as if it were the code's.

---

## 17. Changelog

| Date | Change |
|---|---|
| 2026-08-04 | **Traceability audit of the generated spec, and §16.6 recounted.** Every route the application registers is in [`openapi.yaml`](openapi.yaml) and every operation carries errors, a description and a story verdict — the export guard had held. Two things it cannot check did not: eight parameters were undescribed (`booking_id`, `pass_id`, `notification_id`, the `Last-Event-ID` header), and **`POST /invoices/{id}/payments` was claiming `US-2.12`**, a story [`USER_STORIES.md`](product/USER_STORIES.md) scopes to *amenity-booking* payment — an overclaim three other documents here already contradicted, including the resident invoice path's written refusal of the same mapping. Now `Feature`, untraced, with the reason recorded. Coverage of operations by story is **51 served / 48 none**; §16.6's header also still said *"47 of the 98"* after the surface grew to 99. |
| 2026-08-04 | **§14.5 added — `GET /resident/snapshot`, and the resident backend is complete.** The last endpoint of the build order, and the only one that needed no schema change: it is a projection of the endpoints around it, so a bill on the home screen and the same bill on the Payments page are the same model and cannot disagree. **US-2.3 moves from none to partial** — the enabling backend its own *"Backend: None"* note asks for now exists, and the home-screen widget it also asks for is an OS surface a web application does not have. Coverage is 8 served / 9 partial / 7 none across 99 operations. Records one correction to the design document: `activity` is the notification feed, not `member_activity`, because nothing in this project writes that table and §5.8 had already made notifications the durable record of every user-visible event. Also fixes four defects in step 6 — the invoice list was filtered by a *narrower* ownership rule than the settlement path enforces, so a bill raised against the flat was payable and invisible; the Paid tab was defined as "not payable" and so contained cancelled bills; drafts were reaching residents as amounts owed on unissued bills; and a replayed `idempotencyKey` called the gateway before checking for the duplicate and then reported the new verdict over the stored one. |
| 2026-08-04 | **§14 added — the resident's money and home.** Eight operations backed by `0033`: their own invoices and bookings, a simulated gateway that pays either, the notice board, the flat's roster, and a contact directory served from `departments` instead of five numbers hard-coded in `Profile.jsx`. Adding the section shifted the three meta-sections again — Not yet implemented is now §15, the matrix §16, this changelog §17. **US-2.12 closes**, on the transaction rather than on the gateway; coverage is 8 served / 8 partial / 8 none. Two things worth reading before wiring anything: a declined payment is a `200` with `status: "failed"`, and `idempotencyKey` is required with a rule the API cannot enforce (§14.4). Also records that **every one of `0022`'s module-catalogue updates had matched zero rows** since it was written, so `GET /settings` would have reported that none of this backend exists. |
| 2026-07-31 | **§14 added — the traceability matrix from the team's 24 user stories to this API**, with the stories themselves checked in under [`product/`](product/). Changelog moved from §14 to §15. Coverage is 3 served / 12 partial / 9 none. Four findings came out of writing it, none visible from any single file: `PATCH /complaints/{id}` writes `assignee`, `due_at` and `progress_percent` that the dashboard snapshot then drops; `complaints` has no priority column although the snapshot reads one; `PATCH /residents/{id}` was removed on 2026-07-30 and a direct interviewee quote asks for it; and four resident stories are blocked on one absent push transport. |
| 2026-07-30 | **Merged `origin/main` @ `94556e5`; cut the surface to what the frontend calls.** 32 operations removed — every read the shared `GET /dashboard/snapshot` serves, the amenity CRUD their `/dashboard/amenities` serves, and the registration-review trio duplicating their `/admin/access-requests`. Adds §12: `POST /notices` and `POST /admins`. Two contract-wide changes: cookie-first auth with roles resolved from `community_memberships` instead of a JWT claim, and `X-CSRF-Token` required on every unsafe request. §5–§11 prose still describes removed endpoints — see [FRONTEND_WIRING_AUDIT.md](FRONTEND_WIRING_AUDIT.md). |
| 2026-07-30 | Build step 9 — Settings. Adds five endpoints plus six fields on `/billing-settings`. Records that the admin Settings screen has never persisted anything, so its field names are ours; that the four toggles belong to two different tables; that three of them are stored and acted on by nothing; and that module enforcement and community rename were deliberately not built. Answers A10 (community timezone). |
| 2026-07-30 | Build step 8 — Amenities. Adds twenty-two endpoints across the catalogue, bookings, approvals, the booking ledger and reports. Records that approval now covers a whole request rather than one day, that the cleaning buffer no longer blocks shared bookings, and that the frontend has two unrelated amenity models. |
| 2026-07-29 | Build step 7 — Money. Adds ten endpoints across invoices, payments, maintenance runs and billing settings. `dashboard.collection` stops being a placeholder. Records that the product has no maintenance amount anywhere, and that `isOverdue` is derived rather than stored. |
| 2026-07-29 | Build step 6 — Departments and staff. Adds nine endpoints plus `GET /complaint-categories`. Corrects the archive rule: the open-complaint guard is on `DELETE`, not on deactivation. |
| 2026-07-29 | `docs/openapi.yaml` added — the machine-readable companion to this file, generated from the code and checked in. |
| 2026-07-29 | Build step 5 — Complaints. Adds list, detail, `PATCH`, comments, read receipts and attachments. Retracts the invented SLA urgency multiplier (A3); documents the two competing SLA systems. |
| 2026-07-29 | Build step 4 — People. Adds `GET /admins`, `PATCH`/`DELETE /residents/{id}`, and the three `/registrations` endpoints. `dashboard.pendingRequests` and `residents[].email` stop being placeholders. |
| 2026-07-29 | Initial version. Documents the four read-only dashboard endpoints (build step 3) and the pre-existing auth and invitation endpoints. Records the unified error envelope introduced in the same change. |
