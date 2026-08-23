# HomeBandhu API reference

**Version:** v1 · **Base path:** `/api/v1` · **Last updated:** 2026-08-21

> ## Where the numbers stand
>
> The live surface is **201 operations across 170 paths**, all of them in
> [`openapi.yaml`](openapi.yaml), all carrying a user-story verdict (§16). Every `###` heading below
> corresponds to an operation that exists; that is checked mechanically rather than by eye.
>
> *(This banner read **163 across 138** until 2026-08-11 and **179 across 150** until 2026-08-12 —
> the second time it drifted, and by the same mechanism: Sessions 67–68 added the work-order,
> amenity-admin and money operations and retired the four `…/staff` writes, and no hand-maintained
> total moves on its own. It was one of seven such totals found drifting in a sweep on 2026-08-11, in
> documents whose per-endpoint contents were correct throughout; see `CHANGE_LOG` Session 58. What
> **is** checked mechanically is the sentence after this one, and the `--check` that regenerates the
> spec. A count in prose is not.)*
>
> *(And **195 across 164** until 2026-08-20, which is the third time. Only **one** of the four new
> operations is this session's — `POST /complaints/admin-raise`; the spec at `ed9a131` already carried
> **198 across 167**, so three had been sitting in the generated file with this sentence still saying
> 195. Found by counting `openapi.yaml` rather than by reading the line, which is the only way this
> ever gets found.)*
>
> *(And **199 across 168** until 2026-08-21, moved here rather than found stale: §21's two `geo`
> reads are this session's, the count was accurate before them, and the line is updated in the same
> change that invalidated it. Read off `export_openapi.py`'s own summary, not counted by eye.)*
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

## Complaint Engine v2 additions (2026-08-12)

- `POST /complaints/{complaintId}/cancel` accepts `{ mode: "cancel" | "repool", reason? }` and returns the refreshed resident complaint. It is available only before work starts; a stale request returns `409`. **Requires the resident capability since 2026-08-20** (§7.2), like the other three resident verbs.
- `GET /work-orders/{workOrderId}/candidates?includeExcluded=true` returns the supervisor's ranked offer candidates, including workload, distance, leave end and exclusion flag.
- `POST /complaints` accepts optional `skillId`; when present, the database validates the active skill and snapshots its name as the complaint category.
- `POST /work-orders/{workOrderId}/assign` now creates a worker offer. The worker must accept before the job is scheduled. **Since 2026-08-22** it also takes optional `force: true`, which assigns outright and non-declinably instead (§18, amendment 2).
- The staff detail read is `GET /complaints/staff/complaints/{complaintId}`. It uses this non-colliding path because the existing resident `GET /complaints/{complaintId}` is already mounted unprefixed. **Since 2026-08-22** its router guard is active membership rather than `require_admin`; the RPC underneath has always decided `is_community_admin OR can_supervise_department` for itself.

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

**Which source file serves which endpoint** is indexed in
**[`api_yaml_mapper.md`](api_yaml_mapper.md)** — every operation, the handler and line that
implements it, its `operationId` anchor in the spec, and the section of this file that documents it.
Start there when a spec diff is larger than the route diff, or when you need to know what a change to
one repository can break. Its §5 carries the operations whose spec entry is imprecise, and §6 the
scan to run after every pull.

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
| `__Host-hb_remember` | `"1"` when the user ticked **Remember me**; absent otherwise | No |

Local HTTP development drops the `__Host-` prefix (`hb_access`, …), because browsers reject
`__Host-` cookies without `Secure`. The names are the only difference; the contract is identical.

**Session length is the user's choice.** `__Host-hb_access` and `__Host-hb_csrf` always expire with
the access token (~1 hour). `__Host-hb_refresh` is written **without `Max-Age`** unless the sign-in
asked to be remembered — a browser-session cookie, so closing the browser ends the session and the
login page is there again. With **Remember me** it carries `Max-Age = AUTH_SESSION_IDLE_DAYS` (30 days
by default) and the returning visitor is silently signed back in. `__Host-hb_remember` exists only so
`POST /auth/refresh` can carry that choice across token rotation; it holds no secret, and editing it
changes nothing but how long the editor's own session survives.

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

> **Changed 2026-08-20 — that second capability is now conditional.** An admin is granted `resident`
> **only when they hold an active `unit_residencies` row**. It used to be granted to every admin
> outright, which made the session disagree with the per-request guard that asks the same question of
> the same table (§7.2): a flat-less admin was shown the resident affordances and then `403`'d the
> moment they used one. The residency read was already being done to populate `unit`, so agreeing
> with the guard cost a predicate. An admin who does live here is unaffected, and no other role's
> capability list moved.

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
the specific codes it can return** — all 99 operations across 86 paths today, and the exporter refuses to write a spec
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
| `201 Created` | Resource created | 16 current write operations, such as `POST /access-requests` |
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
| `GET /api/v1/auth/oauth/{provider}/start` | **307** to the provider. Plants a signed, HTTP-only PKCE transaction cookie (5-minute TTL). Query: `next?`, `remember?` (default `false`) |
| `GET /api/v1/auth/oauth/{provider}/callback` | **307** back to the frontend, with session cookies set |
| `GET /api/v1/auth/google/start`, `GET /api/v1/auth/google/callback` | Compatibility aliases, so existing bookmarks and registered Google callbacks keep working. `/google/start` takes the same `remember` param |

**A redirect is the success case here**, which is why these four declare `307` and no `2xx`.

`remember=true` is the OAuth spelling of the sign-in card's **Remember me** box. The provider round
trip has nowhere to keep it, so it is written into the signed PKCE transaction cookie on the way out
and read back on the callback, which then sets a persistent refresh cookie (§ 1.2).

GoTrue generates the provider `state` itself; supplying our own makes it reject the callback as
`bad_oauth_state`. The transaction cookie binds the browser to its PKCE verifier instead.

### 3.3 Email and password

| Endpoint | Request | Notes |
|---|---|---|
| `POST /api/v1/auth/password/sign-up` | `{ full_name, email, password, captcha_token?, intent? }` | Password minimum is **15 characters**. `intent` accepts only `service-provider` and is a navigation hint, never a role grant |
| `POST /api/v1/auth/password/sign-in` | `{ email, password, captcha_token?, remember_me? }` | Sets the session cookies. `remember_me` defaults to **`false`**: the refresh cookie then lasts only for the browser session (§ 1.2) |
| `POST /api/v1/auth/email/verify` | `{ token_hash, verification_type }` | Spends the one-time hash from the confirmation email and signs the user in. Never persistent — the confirmation flow never asked |
| `POST /api/v1/auth/email/resend` | `{ email, captcha_token?, intent? }` | Sends the confirmation link again and preserves the allowlisted intent. **200 is not a delivery receipt** — provider errors are swallowed so the response cannot enumerate accounts |

With `AUTH_EMAIL_CONFIRMATION_REQUIRED=true` (the default and mandatory in production), an
unconfirmed address cannot sign in. `POST /auth/password/sign-in` answers `401`
`email_not_confirmed` both when the provider refuses the grant and when it returns a session for an
address nobody has proven they own; that session is revoked. An explicit local/test value of `false`
allows direct sign-in and must agree with local Supabase's confirmation setting. Recovery is
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
| `POST /api/v1/auth/refresh` | Rotate the session from the refresh **cookie** — no body. Re-issues the same persistence the sign-in chose, read from `hb_remember` |
| `POST /api/v1/auth/logout` | Revoke at the provider (best effort) and clear the cookies (authoritative), `hb_remember` included — so signing out ends the silent sign-in for good |

`GET /auth/session` is what the frontend routes on: it returns `onboarding_eligible: true` for a
signed-in identity with no membership yet, and otherwise the membership that decides which portal
loads.

**`membership.unit` names the residency; `membership.unit_id` only identifies it.** When the
membership has an active residency, the opaque id is accompanied by the labels a header can render:

```json
"membership": {
  "id": "…", "community_id": "…", "role": "resident", "department_id": null,
  "unit_id": "c9a2679a-…",
  "unit": { "unit_code": "B-1204", "unit_type": "flat", "building_name": "Tower B", "building_type": "block" }
}
```

`building_name`/`building_type` are `null` for standalone homes, whose `units.building_id` is null —
a community is apartments XOR standalone homes. `unit` itself is `null` when there is no residency,
and also when the unit lookup fails: the labels are display data, and a session that is otherwise
valid is never refused over them.

**`portal` is a closed list**, and it is the only value a client should route on. It is *not* the
membership role: the backend computes it from facts the browser does not hold, which is the whole
reason it exists as a separate field.

| `portal` | Who gets it |
|---|---|
| `resident` | a `resident` membership |
| `admin` | an `admin` membership |
| `worker` | a `worker` membership — **or no membership at all**, if the caller is a registered service provider awaiting hire |
| `security` | a `security` membership with no roster seniority |
| `security-manager` | a `security` membership whose active `staff_assignments.rank` is `manager` or `supervisor`, **or** a `manager` membership whose department is `kind = 'security'` |
| `manager` | a `manager` membership on any other department |

The two spellings of `security-manager` are D3 — rank and role are separate axes — and the first is
the one real people have, because hiring mints only `security` and `worker` memberships. The
authoritative predicate is `gate_admin_community_for` in migration `0040`, which guards the roster
writes; `portal` is derived to agree with it. See
[`docs/design/AUTH_AND_SESSION_DESIGN.md`](design/AUTH_AND_SESSION_DESIGN.md) §5.6.

A session with no membership and no `portal` is somebody about to register a society; `capabilities`
carries `resident` alongside `admin` for an admin, who may use the resident surfaces.

**One write happens inside this read, and it can now decline.** `claim_staff_invitations` turns any
pending leadership invitation naming the caller's verified email into a membership and a roster row
(§8, *Leadership provisioning*). Since 2026-08-21 that claim refuses an invitation the two
exclusivity rulings forbid — the caller is a registered marketplace provider, or already leads
another community.

**It runs on every session read, and until 2026-08-21 it did not** (product ruling 8). The call sat
behind the branch that had already established the caller holds no membership, which meant the whole
population that *does* hold one never reached it: a resident invited to supervise a department, a
worker on one community's roster invited to manage another. Their invitation was neither applied nor
refused — it waited, invisibly, while the inviting department went on seeing `pending` and nothing
anywhere reported a problem. The refusal half was reachable only by the same narrow population, so
the two notifications below never fired for anybody who already belonged somewhere. The guard is
gone. The RPC is idempotent, skips anyone who is already a member of the inviting community, and
costs one indexed read when nothing is pending; the membership re-read after it stays conditional on
something actually having been claimed.

**A refused claim is invisible in this *response*, on purpose, and that is the contract.** It is not
an error and never becomes one: the response is exactly what the caller would have got had no
invitation existed, so a registered provider lands on `portal: "worker"` and anybody else on
`onboarding_eligible: true`. No field is added, no status changes, and no client branches on it. The
alternative design, raising inside the claim, would have been swallowed by
`auth_service._claim_staff_invitations` and would have abandoned every *other* pending invitation in
the same call, silently. See §8 for the full rationale.

**Both parties are told out of band, on the first refusal only.** The refusal writes two
notifications inside the same transaction, guarded by the same `blocked_at is null` edge — the claim
runs on *every* session read, and a blocked person keeps signing in, so a message outside that guard
would be re-sent forever.

| Told | `kind` | Where else it appears |
|---|---|---|
| The inviting department | `staff_invitation.blocked` | `blockedReason` / `blockedAt` on `GET /departments/{id}/staff-invitations` |
| The invitee | `staff_invitation.not_applied` | Nowhere else — this is the only thing they are ever told |

**The invitee's message was added 2026-08-21** (`20260821170000_blocked_invitee_notice.sql`), because
until then they were told nothing at all: they signed in with the address a manager had typed for
them, the invitation silently did not take, and no surface in the product connected the two. The
wording is fixed by the product owner and is stored whole as the notification's `body`, with the
community's name substituted:

> **Registered provider.** "Your invitation to join *{community}* couldn't be applied. This account is
> registered as a marketplace service professional, and department leadership can't be combined with a
> provider profile. Ask the community to invite a different email address."
>
> **Already leads elsewhere.** "Your invitation to join *{community}* couldn't be applied because you
> already manage or supervise another community. Leadership is held in one community at a time — once
> your current engagement ends, the invitation can be applied on your next sign-in."

It is written with `notify_profile`, so it is addressed to the **person** and to no community. That
is load-bearing twice over: a registered provider hired nowhere holds no membership for a
community-scoped row to hang on, and a sitting leader's only membership is in the *other* community —
the one that caused the refusal — so ruling 3's feed scoping (§8) would hide the explanation on the
day that posting ended. It carries **no `url`**: there is no screen anywhere that lists invitations
addressed to you, and `items[].url` comes back `""` (§5.2), which the bell renders as a row that
marks itself read and navigates nowhere.

An invitation that was already blocked *before* that migration was applied stays silent — the edge
has passed. Correcting or re-issuing the address clears `blockedReason`/`blockedAt` and re-arms it.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | No refresh cookie, or it is invalid, expired or revoked |
| `401` | `token_expired` | Access token past its expiry — refresh and retry |

### `POST /api/v1/onboarding/community`

Found a community and make the signed-in caller its first administrator. This bootstrap write is the
exception to the active-membership rule: it creates the caller's membership. It requires a verified
access token and the same `X-CSRF-Token`/cookie pair as every unsafe browser request.

**Request.** Required fields are `name`, `community_type` (`apartment` or `layout_villa`),
`address_line1`, `city`, `state`, `postal_code`, `latitude`, `longitude`, and `admin_profile`. The
profile requires `fullName` and `unitNumber`; optional structures, map locations, feature keys,
contact fields, and a second address line are described by `CommunityOnboardingRequest` in
[`openapi.yaml`](openapi.yaml).

**This body is `snake_case`**, unlike every other request in this API — see §1.3. `location_label`
follows that convention too.

**`latitude`/`longitude` are required and the RPC refuses a community without them**: every
proximity search in the service-operations feature is written against the generated `location`
column, so a society with no pin is a society no serviceman can ever be matched to.
**`location_label`** (optional, ≤120 characters, added 2026-08-21) is the coarse name of that pin —
"Whitefield, Bengaluru" — filled in for the founder by §21's picker and editable before submit. It
is decoration on the coordinate, never a substitute for it.

**200.** Returns `{ "community": { ... }, "admin": { ... } }`: the newly created community and
founder administrator records.

| Status | When |
|---|---|
| `401` | The access token is missing, invalid, expired, or not a verified identity |
| `403` | The CSRF token/cookie pair is missing or invalid |
| `409` | The RPC reports a translated database conflict, or returns a non-object result |
| `422` | The request schema or RPC arguments fail validation |
| `500` | The RPC result is an object but omits `community` or `admin` |
| `503` | The registration RPC is unavailable, missing, or fails without a caller-attributable error |

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
| `409` | `professional_account_separate` | The signed-in identity is a registered service professional. The separate-account rule is bidirectional since `20260812113000` (`HBSEP`, raised by `enforce_professional_membership_mode`) — the same 409 reaches `POST /access-requests` at request time and `POST /admin/access-requests/{id}/approve` for requests that predate the guard |
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

**`GET /dashboard/snapshot` → `weeklyNew`** — the one snapshot field documented here rather than in the
inherited contract, because it was added by this workstream. The dashboard's trend chips ("+2 this week")
were hardcoded in the frontend; the snapshot now carries the real numbers:

```json
"weeklyNew": { "residents": 2, "complaints": 1, "visitorRequests": 0, "bookings": 3 }
```

Each key is the count of rows **created in the trailing 7 days** (`created_at >= now() - 7 days`, UTC):
`residents` counts active resident memberships started in the window, `complaints` complaints raised,
`visitorRequests` visitor requests created, and `bookings` amenity bookings created. Integer values, always
present, `0` when none. They are computed as head-only Postgres count queries
(`dashboard_repository.weekly_new_counts`), never by tallying the capped lists elsewhere in the same
response — so the chips stay honest even when a list is truncated at its row limit.

**`GET /dashboard/snapshot` → `amenities[]`** — the catalogue card projection, fixed 2026-08-23
(issue #48 D2). Every real deployment runs the `legacy=True` branch (`dashboard_repository.list_amenities`
/ `dashboard_service._amenities`), which reads the `amenities` table directly:

| Key | Notes |
|---|---|
| `description` | The real `description` column. It used to repeat `category` — every card described itself as `"Fitness"` — because the legacy `SELECT` never asked for the column at all |
| `image` | `amenities.image_url` — a `https://` URL or a capped base64 `data:image/...` URL (below). `null`/absent when unset |
| `openingTime`, `closingTime` | `amenities.opening_time` / `closing_time`, as `"HH:MM:SS"` text (`""` when unset) |
| `bookingMode`, `status` | Title-cased for display (`Exclusive`, `Active`) — **not** the lowercase machine vocabulary bookings use (below); this projection was not touched by the booking-status fix |

Before this fix the `SELECT` powering this projection did not name `description`, `image_url`,
`opening_time` or `closing_time` at all, even though `0023` had added all four columns — so the admin
catalogue card could never show a photo or an opening hour no matter what the write endpoint accepted.
The non-legacy branch (dead in every environment this product runs in — there is no deployment with
`schema_generation() != "legacy"`) keeps its `image`/hours inside the `booking_rules` jsonb it has
always used; no DDL was added for it.

### 5.1 Live updates — `GET /events`

One stream for every portal. It is how every write in §7–§12 reaches an open screen without a matching read
endpoint.

> **`GET /dashboard/events` is a deprecated alias** for this endpoint — same handler, same behaviour, same
> audience scoping. It stays for compatibility with older deployed clients; current clients use `/events`.
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

The caller's own feed, newest first. **Any signed-in person** — an admin receives `complaint.raised` and
`access_request.created`, and a feed that refused them would mean building a second one later.

**Not "any active member", and the difference is a whole population.** Since `0041` the recipient of a
notification is a **profile**, so these three routes and the three in §5.3 guard on identity alone. A service
person registers before anybody has hired them, applies to departments, and is told the answer — all of it
while holding no membership anywhere. Under the membership-keyed shape the row could not be written, the feed
view's join would have dropped it, and the read policy would have refused it. The caller waiting on an answer
was precisely the caller who could not be told one.

**There is no recipient parameter, and the tenancy here is doubled.** The recipient is the profile behind the
verified session, and `notifications` also carries an RLS policy of its own
(`recipient_profile_id = auth.uid()`), so a query that asked for someone else's rows would come back empty
from the database regardless of what the API did. This is the first table in this backend where that is true.

**One feed across every community.** A person with memberships in four societies reads one list and one
badge, not four summed by the client. `recipient_membership_id` survives on the row and still says which
community a notification was *about* — it is the audience of the SSE frame and the `community_id` on the feed
view — it is simply no longer who the notification is *for*.

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
| `401` / `403` | No session, or a failed CSRF pair on the two writes. **No membership is required** |
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
| `GET /push/vapid-key` | — | `{ publicKey }`. Public by construction, still behind a sign-in guard: an unauthenticated endpoint naming our key is free reconnaissance for no benefit |
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
| `401` / `403` | No session, or a failed CSRF pair. **No membership is required** — see below |
| `422` | The subscription document is missing an endpoint or a key |
| `503` `push_not_configured` | This server has no VAPID keypair. Only `GET /push/vapid-key` and `POST /push/subscriptions` |

**Fail closed, but do not fail loudly.** An environment with no keypair returns `503` on those two routes, the
sender never starts, and **everything else in the product works normally** — including `DELETE`, because
turning notifications off must not depend on an operator not having lost a key. Push is an enhancement; an
unconfigured environment must not be a broken environment.

**A subscription belongs to a person, not to a membership** (`0041`). Two things follow, and both were
defects before it.

- **A service provider with no membership can turn push on.** The worker profile screen shipped a push toggle
  on 2026-08-10 that posted to an endpoint requiring an active membership, so the one caller it was built for
  got a `403`. Out-of-app delivery matters most to exactly that person: what they are waiting for arrives
  while the app is closed.
- **A person in two societies gets both.** `endpoint` is unique across the whole table by design — the
  endpoint URL *is* the browser's identity to the push service — so a row keyed on a membership meant that
  subscribing the same browser from a second society **moved** the row and silently stopped the first
  society's pushes. Nothing had ever held two memberships until the service-operations build.

**Neither write names an owner.** Once the row is keyed on the profile, the only value a caller could
legitimately send is their own id, so accepting one and validating it against the session it arrived in would
be a parameter that exists to be checked. The RPCs read `auth.uid()` instead — the forgery surface is removed
rather than guarded.

> **~~This ships backend-complete and unverifiable end to end.~~ Closed 2026-08-10.** This note said nothing
> in `frontend/public/` was a service worker, so no push could be *observed* arriving. `frontend/public/sw.js`
> now exists — registered from `main.jsx`, handling `push` and `notificationclick` — with
> `src/lib/push/pushClient.js` doing permission, subscription and unsubscription against
> `GET /push/vapid-key`. The backend tests still mock the call to the push service, which is the honest limit
> of an in-process suite; what changed is that the other end of the wire exists. Today the subscribe control
> is on the service partner's profile screen only, which is placement rather than capability — any portal
> turns push on with one call to `enablePush()`.

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
> admins, **the complaint's own department manager** and — since 2026-08-21 — **that department's
> supervisors**. The notification is written **inside the same transaction** as the change that
> caused it, in the RPC rather than in this API, so there is no path that changes a complaint without
> telling anyone — including the paths this API does not own. See §5.2 for how it is delivered.

> **The supervisors were added 2026-08-21** (`20260821200000`, product ruling 7). Ruling R18 —
> *"supervisors now notified on raise and reopen"* — was recorded as settled in the complaint
> engine's own ruling table and never implemented: `notify_complaint_staff` reached admins and the
> department's manager, and stopped. A supervisor is a **rank on a roster row in one department**,
> deliberately (`0043`), so no role-based helper can name them — which is why the gap survived a
> review that read the audience as "admins and managers" and found it correct. The arm added is
> `notify_department_leadership`'s own predicate narrowed to this complaint's department, `distinct`
> and excluding admins so nobody is told twice. It is in the shared helper rather than at the raise
> call site, so it holds for every complaint-shaped event: the raise, the admin raise, a reopen, a
> resident's cancellation, a forced assignment and an all-declined.

> **Corrected 2026-08-12.** That audience used to be `notify_community_staff` — every admin *and
> every manager in the community*. The manager of the plumbing department was told about lift
> complaints, and the link went to `/admin/complaints`, which their portal has no route for, so the
> click silently redirected them home. `complaint_department_routing` replaced it with `notify_complaint_staff`, which needs a
> department on the complaint — which is what §7.1 is about.

### 7.1 Which department owns a complaint

A complaint used to reach a department only once dispatch built a work order from it
(`work_orders.department_id`, `0036`). Before that moment it belonged to nobody, which is why every
manager was told about every complaint: there was no better answer available.

`complaint_department_routing` routes it at the moment it is raised. **The rule, in precedence order** (product owner,
2026-08-12):

1. the complaint's **category**, matched to `complaint_categories` and followed through
   `department_categories` (`0019`) to a department;
2. failing that, **the department the resident named** on the form;
3. failing that, **nothing** — the complaint waits in the admin's triage queue.

Category over the resident's pick is the ruling and it is the right way round: the category mapping is
curated by somebody who knows how this society is organised, and the resident is guessing. The
resident's pick is not decoration — it routes exactly the cases the catalogue cannot, which is the
`Other` category and anything nobody has mapped yet.

**`"Other"` and `"Not sure"` are not special values anywhere.** They are the two inputs that match
nothing and fall through to the next rule. Encoding them as sentinels would have added two more
strings every reader has to know about, to say what the absence of a match already says.

**An ambiguous category goes to a human.** `department_categories` has a composite primary key, so one
category may legally belong to several departments. When it does, the rule routes to *nothing* rather
than picking. A complaint in the triage queue is a visible question answered in one click; a complaint
sent to whichever department claimed the category first is an invisible wrong answer, and the only
person who could notice is the department that did not get it.

#### `GET /api/v1/unassigned-complaints`

The admin's triage queue, oldest first. Resolved complaints are excluded — one answered without ever
being allotted needs nothing from anybody.

**Not `/complaints/unassigned`.** `GET /complaints/{complaintId}` already exists and swallowed it,
reading `unassigned` as a complaint id. Declaring the literal earlier would have worked and would have
left this endpoint's correctness depending on which order two routers are included in.

| | |
|---|---|
| Guard | `admin`, `manager`, `worker`, `security` at the router; `is_community_admin` in the RPC |
| Returns | `200` array of `UnassignedComplaint` |
| Errors | `401`, `403`, `500` |

#### `GET /api/v1/department-options`

Id, name and kind of every active department in the caller's community. Any active member.

It exists because of a control that could not be drawn: `GET /departments` is admin-only and carries
roster counts, categories, hours and skills, so a manager choosing where to move a complaint had no
way to learn any department's name. Three fields rather than widening a real read boundary to serve a
dropdown.

| | |
|---|---|
| Returns | `200` array of `DepartmentOption` — `id`, `name`, `kind` |
| Errors | `401`, `403`, `500` |

#### `PATCH /api/v1/complaints/{complaintId}/department`

Give a complaint to a department, or move it to another one.

**One endpoint, two acts, and which one you are performing is decided in Postgres from what the
complaint currently holds** — not from which route you called or what you claim to be:

* the complaint has **no** department → only an **admin** may allot it;
* the complaint **has** one → only that department's **manager** (or an admin, who passes
  `can_manage_department` everywhere) may move it out.

Authorizing the move on the department the complaint is *leaving* is the load-bearing half. Checking
the caller manages the **destination** instead would let the manager of B reach into A and help
themselves to A's work.

Re-assigning to the department that already holds it is a no-op rather than a `409`, because a
double-clicked button is not an error worth a message.

```json
{ "departmentId": "…" }
```

| | |
|---|---|
| Errors | `401`, `403`, `404`, `422`, `500` |

#### `POST /api/v1/complaints/{complaintId}/department-requests`

A supervisor saying this complaint is not their department's. **A supervisor cannot move it
themselves** — that is the ruling, and it is the only shape that works: a supervisor who could push
work out of their own department could empty it, and the department receiving it would have no say
either way.

`toDepartmentId` is **optional**. A supervisor who knows a lift complaint is not plumbing usually does
not know whose it is, and requiring a destination would either silence them or make them guess.

```json
{ "toDepartmentId": "…", "reason": "Not a plumbing job." }
```

| | |
|---|---|
| Guard | `can_supervise_department` on the department currently holding it |
| `409` | the complaint has no department yet, or a request is already open on it |
| Errors | `401`, `403`, `404`, `409`, `422`, `500` |

#### `PATCH /api/v1/complaints/{complaintId}/department-requests/{requestId}`

The manager's answer: `accept` or `reject`. The manager answering is the manager of the department
**giving the complaint up**, never the one receiving it.

They may name a different destination than the supervisor suggested. **Accepting with no destination
returns the complaint to the admin's triage queue**, which is what "not ours, and I don't know whose
either" honestly means. The supervisor is notified either way — a request that is silently rejected is
one they raise again next week.

```json
{ "decision": "accept", "toDepartmentId": "…" }
```

| | |
|---|---|
| Errors | `401`, `403`, `404`, `409`, `422`, `500` |

#### `GET /api/v1/departments/{departmentId}/complaints`

The department's queue, newest first, for its **manager and its supervisors**. Both read the same list
because they act on the same rows; two endpoints would have meant two projections that must agree
about what a complaint looks like.

Each row carries `openRequestId` when a transfer has already been asked for, so the screen draws the
button correctly without a second read — and a supervisor cannot file the same request twice before
the unique index tells them.

| | |
|---|---|
| Query | `status` — optional, filters on the stored status |
| Guard | `can_supervise_department` |
| Errors | `401`, `403`, `404`, `500` |

#### `GET /api/v1/departments/{departmentId}/complaint-department-requests`

Open transfer requests waiting on this department's manager. **Manager-only**, where the list above is
manager-and-supervisor: a supervisor sees the request they raised as `openRequestId` on the complaint,
and the queue itself is an inbox, which is a manager's.

| | |
|---|---|
| Guard | `can_manage_department` |
| Errors | `401`, `403`, `404`, `500` |

### 7.2 Who holds the resident verbs — changed 2026-08-20

**Resident-ness is an active `unit_residencies` row, and never an implication of the role column.**
There is exactly one `community_memberships` row per person per community
(`memberships_active_person_community`, `0001`:45), so the administrator who owns flat B-402 has one
membership and its role is `admin`. Guarding the resident verbs with `require_membership_role("resident")` therefore refused that
person the verbs on **their own home** — cancelling work in their flat, confirming a resolution they
are the only witness to, answering a visit proposed to them. That was never a policy anybody chose;
it was the role column standing in for a fact it does not record.

`require_resident_capability` (`app/api/deps.py`) replaces it on every one of those routes. It passes
when the role is `resident`, and otherwise asks `unit_residencies` for one active row on the
membership. Cost is one indexed read, and only for callers who are not already `resident` — the
overwhelmingly common case does no query at all.

**`GET /auth/session` was changed in the same pass, in the opposite direction.** It has advertised
`capabilities: ["admin", "resident"]` since Google sign-in landed, but it did so for *every* admin,
which is the same wrong answer the role guard gave and simply inverted: the portal offered the
resident buttons to somebody the per-request layer would refuse. It now grants `resident` only on the
same active-residency test this guard applies, so the two layers answer one question from one table
(§1.2).

**The refusal is byte-identical to the old one**: `403` `community_role_required`, same message. A
client that special-cases the resident 403 keeps working, and nothing in the error envelope moved.

> **This narrows one endpoint as well as widening five.** `POST /complaints` used to require only an
> **active membership**, so a `worker`, `security` or `manager` membership with no flat could raise a
> complaint onto a resident complaint list they have no residence behind. It now answers `403`
> `community_role_required`. Their path is `POST /complaints/admin-raise` if they are an admin, and
> otherwise the association's — a member of staff reporting a fault in a building they do not live in
> is not the same act as a resident reporting one in their home, and the resident list is the wrong
> place for it. **No screen outside the resident portal calls `POST /complaints`** (checked across
> `frontend/src/**` on 2026-08-20), so this closes a hole rather than removing a path anything used.

**Where it applies:** `POST /complaints`, `/cancel`, `/reopen`, `/resolution` (§7), and both resident
scheduling routes, `GET /complaints/{id}/schedule-request` and `POST /complaints/{id}/schedule`
(§18). `GET /complaints`, `GET /complaints/{id}` and `POST /complaints/{id}/read` stay on active
membership: reading and dismissing your own row needs no residency, and the lookups already filter on
the membership.

### The two vocabularies

The database column is `priority`; the form field is `urgency`. Neither side is renamed —
`domain/vocabularies.py` translates, as it does for every other pair.

`status` on the wire is `Pending` | `In Progress` | `Resolved` | `Cancelled`. The stored enum has six
members, and the mapping is deliberately **not** a round trip: `closed` renders as `Resolved`, because
the frontend's select has three options and closed is not one of them. What `closed` means is in
`POST /complaints/{id}/resolution` below.

### `POST /api/v1/complaints/admin-raise`

Raise a complaint **from the admin portal**. **Requires `ADMIN`**, plus CSRF. `201 Created`.

**Request**
```json
{
  "title": "Lobby light out",
  "description": "The light by the B-block postboxes has been out since Friday.",
  "skillId": "…",
  "category": "",
  "priority": "Low",
  "location": "B Block lobby",
  "departmentId": null,
  "forMembershipId": null
}
```

**201** — `{ "id": "…", "message": "Complaint raised." }`

**One optional field decides everything**, and it is `forMembershipId`:

| `forMembershipId` | Owned by | `raised_via` | Where it appears |
|---|---|---|---|
| a resident's membership id | **that resident's** membership | `resident` | Their portal, with the chat, the status, the timeline and the resident verbs — and the admin queue, as before |
| absent | the **admin's own** membership | `admin` | The admin queue only. **Not** on that admin's own resident-portal "My Complaints" |

The first mode is a resident who telephoned the office instead of opening the app. The complaint is
**theirs**: they can confirm the resolution, reopen it and cancel a proposed visit, exactly as if they
had filed it. That the administrator typed it is recorded where it belongs — the `raised` event's
`actorMembershipId` is **always the admin**, and its payload carries `"on_behalf": true`. It is
history, not a property of the complaint, and it must not be able to move the complaint off the list
of the person whose home the problem is in.

The second mode is a burnt-out lobby light, a broken treadmill, a gate that will not close. Somebody
has to own the row and the person who noticed is the honest answer, so it is the admin's — but it is
marked admin-portal-only, because their "My Complaints" is *what happened to them at home* and a
complaint about the lobby is not that.

> **`raisedVia` is derived by the database, never accepted from the client.** A request that could
> send both it and `forMembershipId` is a request that can send them contradicting each other. It is
> `admin` exactly when `forMembershipId` is absent.

> **Why this is not `POST /complaints` with an extra field.** Because an admin *is* a resident (§7.2)
> — one membership row, the resident capability granted whenever they hold a flat — the resident
> endpoint would have **accepted both of these calls** and filed both onto the admin's own resident
> list, where the second does not belong and the first is filed against the wrong person entirely.

`category` is **optional here, exactly as on the resident's form**: send `skillId` and the database
snapshots that trade's current name into `category`. Sending neither is a `422` from
`admin_raise_complaint` — one rule, enforced in one place, for both portals. `priority` is the admin
screens' word for what the resident's form calls `urgency`; both translate to the same column, so the
two portals cannot mean different things by `High`. **`expectedResolutionAt` is not accepted**, for
a stronger version of the reason it is refused on the resident's form: an admin who could send a
deadline could quietly give the association's own complaints a different SLA from the residents'.

**Everything downstream is unchanged.** The same category-then-skill department routing (§7.1), the
same priority-derived SLA, the same `notify_complaint_staff` audience, and the same supervisor → work
order pipeline. An admin-raised complaint is a complaint.

The response is the id and a message rather than the complaint, and that is the deliberate difference
from `POST /complaints`. The resident's raise returns its row because the SLA deadline is the one
thing the client could not have computed and is about to display. The admin has no such gap: the
admin portal's complaint list is `GET /dashboard/snapshot`, which this write refreshes through the
shared SSE trigger, so a read-back would return a row the screen is about to receive anyway — through
the *resident* projection, which is the wrong shape for the screen that asked.

**The snapshot tells the two modes apart.** Every complaint row it projects now carries `raisedVia`,
and a row with `raisedVia: "admin"` reports its `flat` as `"—"`: the admin's own flat number is not
where the lobby light is, and printing it would attribute a common-area fault to a home.

| Status | Code | Cause |
|---|---|---|
| `403` | `forbidden` | Not an active admin of the community — checked by `require_admin` **and again in the RPC**, which is callable by any authenticated role |
| `403` | `forbidden` | `forMembershipId` names a membership in **another community**, or one that is ended or inactive. Refused rather than ignored: filing it into the caller's own community would hand a complaint to a management team that has never heard of the person it names |
| `404` | `not_found` | `skillId` names no active trade |
| `422` | `unknown_priority` | `priority` is not `High`, `Medium` or `Low` |
| `422` | `check_violation` | Neither `category` nor `skillId`, or an empty `title` |

> **`forMembershipId` is not checked for a residency.** An admin filing on somebody's behalf is
> stating that this person's home has a problem, and a membership mid-move or still waiting on its
> `unit_residencies` row is exactly the case where they need somebody to file for them.

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

> **`resident` is a wire word, not a stored one.** The column, both `add_complaint_comment` RPCs and
> every read filter say `public`, and `complaint_comments_visibility_check` allows nothing else. The
> service translates, in `app/domain/vocabularies.py`, alongside the status mapping it sits next to.
> Until 2026-08-09 it did not: the request was forwarded unmapped, so **every comment posted through
> this endpoint failed** with a `23514` surfaced as a `422` — including the frontend's, which sends
> `resident` verbatim. The wire vocabulary documented here is unchanged and is the contract; `public`
> is accepted too, so a client that has learnt the stored word is not forced back through the
> display word.

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
| `409` | `conflict` | Empty message |
| `422` | `unknown_visibility` | `visibility` is not `resident`, `public` or `internal` |

### `GET /api/v1/complaints`

The caller's **own** complaints, newest first. **Requires an active membership** — any role.

**Always the caller's own, whatever their role.** An admin calling this gets the complaints they
personally raised, not the community queue; that is `GET /dashboard/snapshot`. One route that returns
a resident's list to one caller and the whole association's to another is the shape
`RESIDENT_BACKEND_DESIGN.md` §5.1 exists to prevent.

> **Added 2026-08-20 — this list and the detail below filter on `raised_via = 'resident'`.** A
> complaint an admin raised **about the building rather than about a home** is owned by their
> membership and would otherwise appear here, on the one list that means *what happened to me at
> home*. It is `raised_via = 'admin'` and is excluded. A complaint raised on a resident's **behalf**
> is `'resident'` and does appear, on that resident's list, with every verb intact — which is the
> whole point of filing it against their membership. See `POST /complaints/admin-raise`.

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

Raise a complaint. **Requires the resident capability** — the `resident` role, or any membership
holding an active `unit_residencies` row (§7.2). `201 Created`, and the body is the complaint as
`GET /complaints/{id}` would return it.

> **Narrowed 2026-08-20.** This used to require only an active membership, so a `worker`, `security`
> or `manager` membership with no flat could file onto a resident complaint list. It is now `403`
> `community_role_required`. An administrator's path is `POST /complaints/admin-raise`, which is
> above and which is a different act with a different owner.

**Request**
```json
{
  "title": "Lift stuck between floors",
  "description": "The B-block lift has been stopping between 3 and 4.",
  "category": "Elevator",
  "urgency": "High",
  "location": "B Block",
  "departmentId": null
}
```

> **`departmentId` is the resident's guess, and it is a fallback rather than an instruction.** `null`
> is what the form's "Not sure" option sends, and it is the ordinary case. The category decides first
> — see §7.1 — and this is consulted only when the category maps to no department, which is the
> `Other` category and anything nobody has mapped yet. A department id from another community, or one
> that no longer exists, is **ignored rather than refused**: a stale form should file the complaint
> into the triage queue, not fail to file it.

> **`expectedResolutionAt` is not accepted.** High → 24h, Medium → 48h, Low → 72h, applied by the
> database on insert. The rule used to live in `createComplaintsSlice.js`, where a resident could have
> sent themselves a one-minute deadline and where the admin portal could not see it at all. The
> admin's `dueAt` is set to the same instant, so the resident's expectation and the association's
> deadline start out as one number rather than two formulas.

The response is the created complaint rather than an acknowledgement, because the SLA deadline is the
one thing the client could not have computed and is exactly what it is about to display.

**Attachments are not accepted yet.** `media` exists in the schema and no upload endpoint does — so
this endpoint takes what it can honour rather than accepting data it drops. Since 2026-08-12 the
resident form no longer collects them either, for the mirror-image reason: a form field that
promises a resident their photo reached somebody is worse than no field. Tracked in §15.

Raising notifies the community's active admins and **the manager of the department the complaint
routed to**, if it routed to one. Until 2026-08-12 it notified every manager in the community, which
meant a plumbing manager was told about lift complaints and sent to a screen their portal has no route
for.

| Status | Code | Cause |
|---|---|---|
| `403` | `community_role_required` | The caller holds no `resident` role and no active residency (§7.2) |
| `422` | `unknown_urgency` | Not `High`, `Medium` or `Low`. **Not defaulted** — a silent fallback would file the complaint under a deadline the resident did not choose |
| `422` | — | Empty or whitespace-only `title` or `category` |

### `GET /api/v1/complaints/{complaintId}`

One complaint with its timeline and public comment thread. **Requires an active membership**, and it
must be the caller's own complaint.

A complaint that exists but belongs to somebody else is a **`404`, identical to one that does not
exist**. The lookup filters on the membership rather than checking afterwards, so there is no code
path in which the two could be told apart. Since 2026-08-20 it filters on `raised_via = 'resident'`
in the same way and for the same reason, so an admin's own building complaint is a `404` on their
resident portal rather than a row that half-belongs there.

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

Send a resolved complaint back. **Requires the resident capability** (§7.2 — the `resident` role, or
an active residency on any membership), and it must be their own complaint.

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
| `403` | `community_role_required` | No `resident` role and no active residency (§7.2) |
| `403` | `insufficient_privilege` | Not the resident who raised it |
| `404` | `not_found` | No such complaint |
| `422` | `check_violation` | Not currently resolved, or an empty reason |

### `POST /api/v1/complaints/{complaintId}/resolution`

Accept the resolution and rate it. **Requires the resident capability** (§7.2), and it must be their
own complaint.

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
          "rank": "manager",
          "shift": null,
          "status": "active",
          "membershipId": null,
          "serviceProviderId": null,
          "supervisedWorkOrderCount": 2,
          "openCommitmentCount": 0,
          "departureStatus": null
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

`rank` (`member` \| `supervisor` \| `manager`) and `role` (`"Technician"`, `"Plumber"`) are
**separate fields on purpose.** The seed data proves they are not a function of each other: two
departments' heads render as `Supervisor` and `Manager`. Any derivation rule would silently rewrite
one of them. `head` was the third value until `0035`; the department's *head* is still called that
everywhere the API says `head`, and is the person holding `rank = 'manager'`.

That separation is also what the frontend had wrong. `STAFF_ROLES` existed three times with three
different value sets, because one list was answering both questions at once — `Manager` and
`Supervisor` are ranks and `Technician` and `Gate Officer` are trades. One list per question now,
in `frontend/src/lib/staffVocabulary.js`, and `role` is a free-text field with suggestions rather
than a select, because `job_title` carries no check constraint and a closed list would be a screen
inventing a rule the database does not have.

**`serviceProviderId` says whether this row is a person with an account** (`0042`). Null is the
ordinary case and stays so — `0019` A7 made a roster a list of names, and `0035` only stopped that
being the *only* thing it could be. It is projected because the two things a manager can do to a
roster row take two different ids: removal takes this row's `id`, and
[`POST /departments/{id}/blacklist`](#post-apiv1departmentsdepartmentidblacklist) takes the
provider's. Without it one screen cannot offer both, which is how the gap was found.

**`supervisedWorkOrderCount` replaced `activeAssignmentCount` on 2026-08-21** (product ruling 5,
`20260821200000`). It counts the **live work orders this person supervises in this department** —
`work_orders.supervisor_membership_id`, everything not `completed`, `cancelled` or `failed` — and it
is `0` for anybody whose `rank` is not `manager` or `supervisor`. That zero is the truth and not a
placeholder: a team member's number is `openCommitmentCount` below.

What it replaced was a constant. `activeAssignmentCount` counted complaints by
`assigned_to_membership_id` or by a prefix match on `assignee_label` — one column written by nothing
(complaints are department-pooled and ruling 1 keeps them that way) and one no frontend has ever
set — so it was `0` on every row of every roster ever returned, and the hiring screen rendered it as
"0 open complaints" beside a real number. The field is **gone**, not renamed in place: a client
reading `activeAssignmentCount` now gets `undefined` rather than a wrong number, which is the
outcome worth having.

**`openCommitmentCount` is a different number, and the difference matters** (`0043`). That one counts
work this person is accountable *for*; this counts jobs and shifts actually **booked** in their
name — a supervisor holds none of the second, and a worker's job outlives whoever raised it. It is projected
because it decides which verb a roster row offers:
[removal](#post-apiv1departmentsdepartmentidmembersstaffidremove) is refused while it is non-zero, so
a screen that did not know the number could only find out by trying, and a manager would experience
the rule as a button that sometimes errors.

`departureStatus` is `pending` while somebody is on their way out, otherwise null. The dispatch
engine is already frozen against that person when it is set.

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

One department with its **active** roster. **Requires `ADMIN`, or the `MANAGER` of that
department.** Body as above, **plus one field the list does not carry**:

| Field | Type | Notes |
|---|---|---|
| `canHire` | boolean \| null | Whether **this caller** may hire for **this department**. `null` on the list — see below |

**Why this is a field and not something the browser can work out.** Hiring stopped being a property
of the caller when `can_hire_for_department` landed: it belongs to the department's own active
manager — by membership role *or* by an active `staff_assignments` row of rank `manager`, which for
a security department means `membership_role = 'security'` — and community admins are the fallback
**only while it has neither**. So the same admin may hire for one department and not the next one
down the list, and no role check answers it. This field is that function called directly, so the
screen and the RPC cannot disagree.

`null` means *not asked on this read*, which is a different answer from `false`. `GET /departments`
leaves it null because it is one round trip per department and the list has no control that needs
it; defaulting to `false` there would tell twelve screens the admin may hire for none of them.

What it turns off, in `DepartmentHiring.jsx`: the **Applications** and **Find people** tabs.
`GET .../applications` is filtered by the same predicate through RLS and would come back empty, and
`GET .../candidates` raises `HB403` — so without this the screen looked broken rather than
restricted. Roster and departures are `can_manage_department` and are unaffected.

**The one read on this router a manager may make**, and the reason the router's guard changed. Every
other operation here is `ADMIN`-only and now says so per route; the router itself carries the looser
`require_admin_or_manager`, because FastAPI cannot remove a router dependency for a single route.
That inverts the failure mode — a new route added here without `ADMIN_ONLY` would be open to every
manager in the community — so `tests/api/test_departments.py::test_api_186` asserts the whole table
rather than one route at a time.

The manager portal has no other way to read its own department: `GET /departments` is admin-only, so
a manager cannot look themselves up, and the only thing that knows which department they run is
`membership.department_id` from `GET /auth/session`. Narrowing to *their* department is
`can_manage_department` in Postgres, not this route.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / neither an admin nor a manager |
| `404` | `not_found` | No such department in the caller's community |

### `PATCH /api/v1/departments/{departmentId}`

Partial update. **Requires `ADMIN`.** Omitted fields are left unchanged; an explicit `null` clears one.

```json
{ "slaHours": 12, "status": "Inactive", "categories": ["Plumbing"] }
```

**200** — the department as it now stands.

Two fields have **collection semantics**: sending `categories` replaces the claim set, and sending
`staff` replaces the roster. Omitting either leaves it untouched. (The `PUT …/staff` this line once
pointed at was retired 2026-08-12 — see below; the typed `staff` field on this request survives.)

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

### The four staff-write endpoints — retired 2026-08-12

`PUT`/`POST /departments/{id}/staff` and `PATCH`/`DELETE /departments/{id}/staff/{staffId}` were
removed from the API. All four were superseded by the `0035` hiring flow before they ever gained a
caller: roster growth happens through applications and invitations, individual removal through
`POST /departments/{id}/members/{staffId}/remove` (which carries the reason a bare `DELETE` could
not), and there was never a screen that bulk-replaced or field-edited a roster row. The typed
name-only roster entry survives where it was actually used — `staff` on `POST /departments` and
`PATCH /departments/{id}` — and the roster reads are untouched.

Retiring the `staff: []` payload also fixed a live defect: `PATCH /departments/{id}` treats key
presence as *replace this collection*, and the admin form had been sending an empty list on every
edit — silently deactivating the department's whole roster on save. The form no longer sends the
key at all.

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
The maintenance amount existed nowhere in this product when this section was written:
`createPendingRequestsSlice.js` hardcoded `4250` in the middle of an approval handler,
`data/payments.js` repeated it, no screen configured it, and the ERD has no rate field either. This
was agenda item 12.

> **Two thirds of that is false as of 2026-08-12, and the last third is the interesting one.** The
> **Settings** screen now reads and writes this endpoint —
> `frontend/src/pages/AdminDashboard/Settings.jsx:75` and `:137-144`, over
> `moneyApi.getBillingSettings` / `updateBillingSettings` — so a community configures its own rate,
> and `frontend/src/data/payments.js` was deleted with the rest of the demo store. What survives is
> `createPendingRequestsSlice.js:43`, still minting a `4250` invoice inside the demo approval
> handler, and the ERD still has no rate field. So the number an admin now chooses and the number the
> demo still invents are two different numbers, and only one of them is stored.

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
`dayCount` and `dates`. One click decides the whole request. The approvals screen renders
`dayCount` and `dates` since 2026-08-12 (agenda item 16, closed) — and the same wiring fixed a live
bug: the demo had been posting the *occurrence* id to `…/{seriesId}/approve`.

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

### `POST /api/v1/dashboard/amenities` · `PUT /api/v1/dashboard/amenities/{amenityId}`

Create or update one row of the catalogue. **Requires `ADMIN` or `MANAGER`.** Body: `AmenityWrite` —
the one model on this surface with **snake_case field names** rather than the rest of the API's
camelCase, matching the nine fields it already had: `name`, `description`, `category`, `location`,
`capacity`, `booking_mode`, `approval_required`, `hourly_rate`, `is_active`. Plus three added
2026-08-23 to close issue #48 D2, the gap that let the catalogue form collect a photo and a pair of
opening hours the API had nowhere to put:

| Field | Type | Accepted | 422 when |
|---|---|---|---|
| `image` | `string \| null` | An `https://` URL up to 2000 chars, **or** a `data:image/(png\|jpeg\|webp\|gif);base64,...` URL up to 140,000 chars (~100KB of binary — the client downscales to this before it ever submits, so the limit is a backstop, not the normal path). `""` normalises to `null` | Anything else — a `data:` URL over the cap, an unrecognised image type, a bare filename |
| `opening_time`, `closing_time` | `string \| null` | `"HH:MM"` or `"HH:MM:SS"` — the two shapes an `<input type="time">` emits and the two Postgres `time` accepts. `""` normalises to `null` | Malformed clock string; **or** both are set and `opening_time >= closing_time` |

The hours check mirrors the database's own `amenities_hours_check` (`0023` line ~121) so a reversed
pair is a `422` here instead of reaching Postgres as a `500`. `image_url`, `opening_time` and
`closing_time` are real columns on `amenities` since `0023`; before this fix the write handler accepted
none of the three, `description` on the legacy write path was silently dropped even though the column
existed, and there was no way to set a photo or hours on an amenity at all.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin or manager |
| `403` | `csrf_invalid` / `csrf_origin_invalid` | Missing `X-CSRF-Token`, or wrong `Origin` |
| `404` | `not_found` | `PUT`/`DELETE` — no such amenity |
| `409` | `conflict` | `DELETE` — the amenity has bookings; the cascade would take their charges and financial events with it |
| `422` | `request_validation_error` | `name` missing on create, out of length; `image`/`opening_time`/`closing_time` as above |

> **The success response is a known, pre-existing gap, not something this fix touches.** All three
> operations return the raw DB row as a free-form object rather than a modelled schema — `DELETE`
> returns `{"id": ...}` — and the shape differs between the `legacy` and non-legacy branches
> (`api_yaml_mapper.md` §5.1). Resolving that is a separate, larger change than adding three fields to
> the request; only the request side is documented above.

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
      "status": "approved",
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

`state` is the timeline's vocabulary (`booked` | `blocked`); `status` is the lifecycle's — always one
of `pending`, `approved`, `rejected`, `cancelled`, `completed`, `no_show`, lowercase, since 2026-08-23
(issue #48 D4). It never carries Title-case (`"Pending"`, `"No Show"`) and never `confirmed`, which
is not a value the lifecycle has ever had.

**`state: "blocked"` is now derived from `bookingType == "blocked"`, not from `status`.** A block is
stored as an ordinary `approved` booking wearing `bookingType: "blocked"` (`block_amenity_slot`, `0023`
lines 1104-1105) — `public.booking_status` has no `blocked` value at all. Keying the timeline off
`status` — as it did before this fix — painted every admin block as an ordinary resident booking
(issue #48 D3); it now paints from the type, so a block is `state: "blocked"` with
`status: "approved"` on the same row.

`status` may read `completed` for a row stored as `approved`: a booking whose end time has passed is
completed, and storing that would need a scheduled job to keep it true.

`residentId` is the requester's **membership id** — what `GET /dashboard/snapshot` returns as
`users[].membershipId` (there is no `GET /residents`; §6 says so — this line used to cite it, and
the snapshot's `users[].id` is the *profile* id, which would 409 on any booking write). 
`bookingGroupId` is the series id under the name the frontend already groups by.

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

**`bookingType` is the form's own words, mapped onto the database's before the write** (issue #48 D4).
`amenity_bookings_type_check` (`0023` lines 289-291) accepts exactly four values —
`resident` | `admin` | `maintenance` | `blocked` — and the admin booking form offers a different,
human vocabulary describing the same event. The mapping is code-only, applied at the service boundary,
and deliberately lossy:

| Sent as `bookingType` | Stored as | Notes |
|---|---|---|
| `resident` | `resident` | Unchanged |
| `admin` | `admin` | Unchanged |
| `maintenance` | `maintenance` | Unchanged |
| `blocked` | `blocked` | Unchanged (this endpoint does not normally send it — see `POST .../blocks`) |
| `private-event` | `admin` | Which kind of event it was keeps living in `bookingTitle`, `notes` and `department`, exactly where the form already puts it |
| `society-event` | `admin` | Same |
| `maintenance-reservation` | `maintenance` | Same |

Reads present the **stored** value; the request's wording is never round-tripped back. Before this
fix the form's vocabulary was sent straight to the `booking_type` column, which the `CHECK` constraint
rejects for every one of the three aliased words — the failure moved from a clear `422` at the API to
an opaque `500` from Postgres.

**201** — the created booking.

| Status | Code | Cause |
|---|---|---|
| `422` | `validation_error` | End time not after start; `bookingType` outside the table above |
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

**The tab set is exactly the five rows above — `all` fans out to the other four, and there is no
sixth.** `confirmed` sat beside them until 2026-08-23 and matched no row `series_status` could ever
hold (`0023` lines 537-542 name four values, not five), so the "approved" tab's filter was quietly
wider than the status it claimed to show. There is still no `confirmed`/`blocked` tab — an admin
booking staying out of this queue is by design (below), not a gap this fix left open.

| Status | Code | Cause |
|---|---|---|
| `422` | `validation_error` | `status` outside `pending` \| `approved` \| `rejected` \| `cancelled` \| `all` |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

> **By design: admin-created bookings do not appear here, and there is no "Confirmed" tab for them**
> (product ruling, 2026-08-23). `POST /amenities/{amenityId}/bookings` confirms on creation — see
> above — so it was never a candidate for this queue; nothing about issue #48 changes that.

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

> **The idempotency guarantee above was not real before 2026-08-23 (issue #48 D4).**
> `record_amenity_payment` reads exactly three keys off its payload — `amount`, `reference`, `notes`
> (`0023` lines 1295-1330) — and this endpoint sent the reference under the name `payment_reference`,
> which the RPC has never read. A replayed callback therefore recorded a *second* payment instead of
> returning the first. `paymentReference` now maps onto the RPC's `reference` key, which is the fix.
> `method` and `chargeType` have no column of their own on a financial event; both are still accepted
> on the request and are now folded into the stored `notes` text (e.g. `"Charge type: booking; Method:
> UPI; <whatever the admin typed>"`) rather than being silently dropped, which is what happened to them
> before this fix.

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
refunded — `remainingRefund` off `amenity_ledger_overview` — a refund whose amount the caller chooses
is a refund somebody can ask to be larger. The frontend already sends nothing
(`processDepositRefund` uses `normalized.remainingRefund`).

A deposit is refundable only once the booking is cancelled or has finished: refunding a booking that
is still going to happen leaves the amenity unsecured.

> **Fixed 2026-08-23 (issue #48 D4): every refund used to insert with no amount at all.**
> `refund_amenity_deposit` writes its event from an `amount` key in the payload (`0023` line 1348),
> and this endpoint never sent one. The ceiling check on the missing amount passed vacuously and the
> ledger recorded a refund of nothing, every time. The service now reads `remainingRefund` back off the
> ledger row and sends it explicitly as `amount` — the same figure the response already showed as
> refundable, now actually paid out. **When there is nothing left, the service refuses before the RPC
> is ever called** (`422`, below) rather than letting Postgres accept a zero-amount event.

**201** — the updated ledger transaction.

| Status | Code | Cause |
|---|---|---|
| `422` | `validation_error` | `remainingRefund` is `0` — "There is nothing left to refund on this booking." Raised by the service, before the RPC runs |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such booking |
| `409` | `conflict` | No deposit; booking still ahead of it |

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

> **Fixed 2026-08-23 (issue #48 D4): `description` used to land as a `NULL` label.**
> `add_amenity_charge` reads `label`, `amount` and `notes` off its payload (`0023` lines 1459-1474) and
> writes the charge row's `chargeType` itself as `additional`; this endpoint sent the description under
> its own name, `description`, which the RPC has never read. Every added charge was recorded with no
> label at all. `description` now maps onto the RPC's `label` key; the requested `chargeType` (e.g.
> `late_cancellation`) is folded into `notes`, since the RPC hardcodes the stored charge type and a
> late-cancellation fee should still say so somewhere.

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
| `startDate` / `endDate` | date | — | Booking date range — the **only** filter the KPI aggregate sees (below) |
| `amenityId` | uuid | — | One amenity — narrows `rows` only |
| `bookingStatus` | string | — | One of `options.bookingStatuses` (below) — narrows `rows` only |
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
    "totalBookings": 6,
    "totalActiveBookings": 4,
    "cancelledBookings": 1,
    "totalCharged": 16500.0,
    "totalRevenue": 15300.0,
    "totalRefunded": 500.0
  },
  "options": {
    "amenities": [{ "value": "5c0b…", "label": "Clubhouse Gym" }],
    "bookingStatuses": ["pending", "approved", "completed", "cancelled", "rejected"]
  }
}
```

**`rows` is a page; `kpis` is an aggregate over every matching row.** That split is the point: a KPI
that describes one page is not a KPI, and this one is labelled "Total Revenue". `calculateAmenityReports`
computes figures in the browser from whatever it has loaded, which is the same failure as the money
tiles (agenda item 11).

**`kpis` carries exactly the six figures `amenity_report_totals` returns, since 2026-08-23 (issue #48
D4).** The set it replaces — `totalAmenities`, `pendingApprovals`, `activeAmenities`,
`bookingsThisMonth` — named nothing the RPC has ever returned, so all four rendered a hardcoded `0` on
the reports page while looking like measurements. A KPI with no source is a worse answer than no KPI,
so they are gone rather than zeroed. `totalActiveBookings` reads the RPC's `approved_bookings` and
`totalRevenue` reads its `total_paid` — both keep the name the label on the card always promised, even
though it differs from the RPC's own column name.

**The RPC's whole filter vocabulary is `from_date`/`to_date` — it has never read `amenityId` or
`bookingStatus`.** Before this fix the endpoint sent them anyway, so every KPI silently described the
last 30 days of the *whole community* no matter which amenity or status the admin had picked. There is
still no RPC that applies those two filters to an aggregate, so `kpis` continues to reflect the date
range only; `amenityId` and `bookingStatus` now narrow `rows` **honestly**, in Python, against the same
ledger query the table renders, rather than being sent to an aggregate that silently ignored them.

`bookingStatus` arrives in the wire's vocabulary and is translated to the stored enum before it filters
`rows` (`amenity_ledger_overview.booking_status` is the raw enum — `'requested'`, not `'pending'`).

`options.bookingStatuses` is the lifecycle's fixed vocabulary rather than the statuses that happen to
be present, so the filter does not lose an option the moment nothing currently has that status. It
used to also list `confirmed` and `blocked`, and neither is a value `booking_status` can hold — a block
is an `approved` row wearing `bookingType: "blocked"` — so both were always-empty options; removed as
of 2026-08-23 alongside the fix to the `approved` tab that had the same phantom (above).

A block is excluded from every count but not from the revenue — it is not a booking anybody made, but
its money would still be money.

| Status | Code | Cause |
|---|---|---|
| `422` | `validation_error` | `bookingStatus` outside `options.bookingStatuses` |
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
    "createdAt": "2026-01-04T06:20:00+00:00",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "locationLabel": "Whitefield, Bengaluru"
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
  "noticeSmsBroadcastEnabled": false,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "locationLabel": "Whitefield, Bengaluru"
}
```

Every field is optional. The billing toggles are **not** accepted here — they are `PUT /billing-settings`.

**`latitude` and `longitude` travel as a pair or not at all** — sending one without the other is a
`422`. They are written by `set_my_community_location`, a separate SECURITY DEFINER function that
re-checks that the caller administers this community, which is why they are not part of the same
preferences write as everything above them.

**`locationLabel` (2026-08-21) rides with that pair and never alone.** It is an optional place name
of at most 120 characters, suggested by §21's picker; a label sent without coordinates is ignored,
because the RPC that stores it is the one that moves the pin, and naming a place the community is
not would be worse than leaving it unnamed. Omitting it while moving the pin keeps whatever label
was stored. The community's pin is what every proximity search in the service-operations feature
measures from; the label is what a person reads.

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

| Response field | Notes |
|---|---|
| `status` | `pending` \| `approved` \| `rejected` \| `cancelled` \| `completed` \| `no_show` — the lowercase machine vocabulary, the same one every admin amenity endpoint in §10 emits |
| `storedStatus` | The stored enum, which **agrees with `status` on every row** except that it keeps the enum's own `requested` where `status` says `pending` |

**Unlike `GET /invoices/mine` above, `storedStatus` here is not a second, truer answer — it is the
same fact under the enum's own name for one state.** Fixed 2026-08-23 (issue #48 D4):
`resident_booking_overview.status` is Title-case (`"Pending"`, `"No Show"`), and this endpoint used to
pass it straight through, which made it the one booking surface in the product whose status could not
be compared against any other's — not the admin timeline, not the ledger, not the reports page. It now
runs through the same `booking_status_to_wire` translation they do.

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

**~~No migration has been applied to any database~~ Expired 2026-08-11.** Everything through `0047`
(and the `2026081x` timestamped files before the boundary) is applied to the linked hosted project —
so `0001`'s GIST exclusion, `0031`'s SLA rule, `0032`'s code hashing and `0033`'s settlement RPCs
now exist in a real database. What is *not* applied is everything after the boundary: the six
`20260812…` files (skills, staff provisioning, complaint routing, notification audiences, the
professional-membership symmetry, the work-order notification urls). Potential issue 4 tracks the
remainder. The rest of §F is unchanged — the private Storage bucket `complaint-attachments` does not
exist yet (F2), and rate limiting (F3) and optimistic concurrency (F4) are unowned.

**There is no update-booking endpoint.** `0016`/`0023` ship create, block, approve, reject, cancel
and force-cancel, and nothing that *moves* an existing amenity booking. The admin timeline's Edit
Booking modal was removed 2026-08-12 for exactly this reason — once the screen read real data,
"Save Changes" had nowhere to send anything. Reinstating it needs a `PATCH` on the occurrence that
respects the same advisory-lock overlap rules as create.

**~~`POST /notices` emits no notification.~~ Closed 2026-08-10 by `0041`.** This paragraph named the
one place the `0030` substrate was not wired: every other user-visible event wrote a notification in
the same statement that wrote the thing it was about, and publishing a notice wrote the notice and
stopped. It proposed a call inside `notices_service.create_notice` and then declined to make one,
because it belonged *in* the transaction rather than beside it.

The resolution kept that requirement and dropped the call. `notices_notify_residents` is an
`after insert` trigger, so it runs inside the insert's own transaction by construction, and
`insert_notice` stays the single-statement PostgREST write its docstring defends. `US-2.4` is
**served** (§16.4).

**~~`frontend/public/` has no service worker.~~ Closed 2026-08-10.** This paragraph said that Web
Push was served end to end on the backend — VAPID keys, the subscription table, the sender (§5.3) —
and that a browser could not receive one without a `sw.js` registering `push` and
`notificationclick`, so `US-2.1`, `US-2.4` and `US-2.7` all stayed partial *"on a file this
repository does not own"*.

That file now exists: `frontend/public/sw.js`, registered from `main.jsx`, with
`src/lib/push/pushClient.js` handling permission, subscription and unsubscription against
`GET /push/vapid-key`. **`US-2.7` is the one that moves to served** — the service worker was its
only remaining gap. `US-2.4` followed on 2026-08-10 once `0041` gave a published notice a writer.
`US-2.1` stays partial for a reason that was never about the browser: nothing writes the
visitor-approval *question*, because that is gate software this repository does not contain.

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
> exists. `0022` was corrected in place on 2026-08-04, when nothing here had been applied to any
database. That allowance ended on 2026-08-11 — see `backend/supabase/migrations/README.md`.

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

~~This branch is the **admin dashboard** backend. Two whole surfaces the stories assume — the
resident mobile app and the security gate — have no workstream. That is the agreed scope, not a
miss, and it accounts for 11 of the 24 stories on its own.~~

**Overtaken on 2026-08-11, and struck through rather than deleted because the sentence above is the
reason half this section is worded the way it is.** Both of those surfaces now have one. The
resident backend landed in July (§13, §14), the service and gate surfaces in Phase 1 (§18, §19), and
the gate's *frontend* — the last thing standing between `US-3.5` and a served verdict — on
2026-08-11. Nothing in this branch is scoped to the admin dashboard any more; where a paragraph
below still says otherwise it is a record of when it was written, not a claim about today. The
matrix still lists every story, because a story with no owner is a decision that should be visible
rather than a silence.

**One structural cause explains most of §3 and half of §2.** A staff member has no login: a typed
roster entry (`staff` on `POST /departments` or `PATCH /departments/{id}`) writes a
`staff_assignments` row and leaves `membership_id` null on purpose. So every story written in the
voice of a Security Manager or a Facility Manager is unreachable by that person *by construction*,
not because an endpoint is missing. Closing those stories starts with deciding whether staff get
accounts — see [`product/USER_IDENTIFICATION.md`](product/USER_IDENTIFICATION.md).

### 16.2 Coverage

| | Served | Partial | None |
|---|---|---|---|
| §1 Administrative staff (6) | 3 | 3 | 0 |
| §2 Resident (12) | 7 | 3 | 2 |
| §3 Security manager (6) | 5 | 0 | 1 |
| **Total (24)** | **15** | **6** | **3** |

> **Recounted 2026-08-11 from the per-story verdicts in §16.3–§16.5; it previously read 8 / 9 / 7
> with §3 at 0 / 1 / 5, and had been wrong since 2026-08-10.** Worth naming as a class of defect
> rather than fixing quietly: every individual verdict was correct and machine-checked — `US-3.1`,
> `US-3.3`, `US-3.4` and `US-3.6` moved to *served* when `0040` landed, `US-3.5` on 2026-08-11 — and
> the *aggregate of those verdicts* was stale, because `api_map_scan.py` cross-checks each story's
> verdict across this file, [`USER_STORIES.md`](product/USER_STORIES.md) and
> [`api_annotations.py`](../backend/scripts/api_annotations.py), and checks nobody's arithmetic. A
> summary derived by hand from checked inputs is the one line in a verified document that can still
> lie, and it is the line a reader in a hurry reads first.

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

**US-2.7 was the deliberate exception, and stopped being one on 2026-08-10.** It said: *backend
complete and still recorded partial — the notifications are written, both transports carry them, and
no phone can receive one until the frontend has a service worker.* The service worker was then
built, so the row moves to **served** and the exception disappears rather than being explained away.

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
| [`POST /amenity-bookings/{occurrenceId}/damage`](#post-apiv1amenity-bookingsoccurrenceiddamage) | Withholds against the deposit, so the refund figure moves with the finding |
| [`POST /amenity-bookings/{occurrenceId}/charges`](#post-apiv1amenity-bookingsoccurrenceidcharges) | Any other adjustment, recorded as an event rather than a corrected balance |

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
| [`GET /dashboard/events`](#51-live-updates--get-events) | Deprecated compatibility alias; current frontends use the canonical path above |
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
| [`POST /invoices`](#post-apiv1invoices) | Raises the bill a report later counts; the maintenance run is the automated half |

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
> | [`GET /notifications`](#get-apiv1notifications) | Where a visitor notification would arrive. The feed is real; nothing writes a visitor entry into it yet |
>
> **US-2.1 stays partial for a reason that is not a missing feature.** Its answer exists — approve
> and reject are real, and they notify the gate. What does not exist is the *question*:
> `visitor.approvalRequested` is written when somebody arrives unannounced, and nothing writes it,
> because that is gate software this repository does not contain. A story about being asked cannot
> be served by building the reply. *(This also cited "the same absent service worker as US-2.7";
> that file shipped 2026-08-10 and US-2.7 is now served. It was never US-2.1's only gap.)*
>
> `require_visitor_preapproval` also stays unread, and correctly — see §15.

> **The table and paragraph below are the state as compiled on 2026-07-30, kept for the same reason
> the rest of this entry keeps its layers — but two of their rows are now false and an unmarked stale
> row is a trap rather than a record.** `0032` shipped the visitor-pass writes: `POST /visitor-passes`
> plus `approve`, `reject` and `cancel`, all listed in the endpoint table above. So *"any write
> endpoint — missing"* and *"what is absent is `POST /visitors` and everything after it"* are both
> answered. What is **not** answered, and is the whole of US-2.1's remaining gap, is the *question*
> side: nothing writes `visitor.approvalRequested`, because a guard-raised approval request has no
> endpoint (`resident_visitor_passes.py:134-140`). *(Corrected 2026-08-11, while answering "are there
> any user stories left".)*

| Object | State |
|---|---|
| `visitor_requests`, `visitor_events` | **Exist in the baseline** — status enum, `valid_from` / `valid_until`, `pass_hash`, check-in/out timestamps |
| `GET /dashboard/snapshot` → `visitors[]` | **Exists**, and filters to the caller's own for non-admins |
| `community_settings.require_visitor_preapproval` | **Stored by `0018`**, read by nothing |
| Any write endpoint | ~~**Missing**~~ — shipped in `0032`; see the correction above |

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

#### US-2.4 — Notifications for notices — **served**

| Endpoint | Role |
|---|---|
| [`GET /notices`](#get-apiv1notices) | The resident's read of the board — published notices only |
| [`POST /notices`](#121-post-notices--post-a-notice) | Publishes immediately, and every active resident is notified by a trigger |
| [`GET /notifications`](#get-apiv1notifications) | The feed the notice notification lands in |

> **Closed, 2026-08-10, by `0041_person_notifications.sql`.** The last gap was one writer, not one
> transport: `notification_service`'s renderer has carried a title for `notice.published` since the
> substrate shipped, and nothing ever emitted it.

**Why it is a trigger and not a line in the service.** `notices_repository.insert_notice` is a plain
PostgREST insert, deliberately — a single-table, single-statement write, so the transaction PostgREST
gives it for free is the whole transaction it needs. There is no RPC to add a `perform` to, and
adding one purely to hang a notification off it would replace a correct one-statement write with a
function whose only extra job is what a trigger does for nothing. `0030` §5 already made this exact
argument about the SSE outbox: **delivery is a property of the system, not something each writer
remembers.**

`notices_notify_residents` fires `after insert ... when (new.published_at is not null)`, fans out
through `notify_community_roles` to `role = 'resident'`, and excludes the author — an admin who posts
a notice is not told about their own notice. The `when` clause is what keeps a future draft state
silent, and `published_at` has been nullable for that reason since `0018`.

#### US-2.5 — Simple complaint submission with priority — **served**

| Endpoint | Role |
|---|---|
| [`POST /complaints`](#post-apiv1complaints) | The create endpoint, with `urgency` writing to a real `priority` column (`0031`) |
| [`POST /complaints/admin-raise`](#post-apiv1complaintsadmin-raise) | The same submission, performed by the office for a resident who telephoned instead of opening the app. Same minimal form, same priority selector, same routing and SLA |

> **The `admin-raise` trace is the on-behalf mode only, and it is worth saying so rather than
> letting the tag imply more, 2026-08-20.** The story is written from the resident's side — *"as a
> resident, I want to raise a complaint through a minimal form"* — and its pain point is that
> submission feels complicated. Filing **on a resident's behalf** serves that honestly: it is the
> same act, done by the person who took the phone call, and the complaint lands on the resident's
> own list rather than in a notebook. The endpoint's **other** mode — a complaint attached to no
> flat, for a lobby light or a gym treadmill — serves **no user story at all**. It is an
> administrative need the interviews never raised, and it would belong in §16.6 if the operation
> did not already carry a story for its first mode. Recorded here rather than counted as coverage.
>
> **Neither mode moves this story's verdict.** It was already *served* by `POST /complaints`; a
> second way in does not make it more served.

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
| [`POST /complaints/admin-raise`](#post-apiv1complaintsadmin-raise) | The ownership half: a complaint filed **on a resident's behalf** is owned by *their* membership, so the tracking, the timeline and their own verbs are the ones they already have. The admin is the `raised` event's actor, not the complaint's owner |
| [`POST /complaints/{complaintId}/take-up`](#post-apiv1complaintscomplaintidtake-up) | The department's end of the same status: *Pending* stops meaning "nobody has looked at this" the moment somebody has, and the timeline says when |
| [`POST /complaints/{complaintId}/resolve`](#post-apiv1complaintscomplaintidresolve) | And the other end of it, from the screen where the work is actually managed — the confirm-or-reopen aftermath starts here |
| [`POST /complaints/{complaintId}/priority-raise`](#post-apiv1complaintscomplaintidpriority-raise) | Escalation as visible history rather than a private reclassification: the timeline says the department raised it, and to what |
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

#### US-2.7 — Complaint lifecycle notifications — **served**

> **Moved from partial to served, 2026-08-10.** The paragraphs below were written while the verdict
> was *partial* and are left standing, because the reasoning in them is still correct — it just no
> longer describes a gap. The one thing that changed is that `frontend/public/sw.js` now exists.

| Endpoint | Role |
|---|---|
| [`PATCH /complaints/{complaintId}`](#patch-apiv1complaintscomplaintid) | The transition itself. Acknowledged, updated and resolved all pass through here, and each writes its notification inside the same transaction |
| [`GET /notifications`](#get-apiv1notifications) | Where the resident reads it in-app — the half of this story that works end to end today |
| `POST /worker/jobs/{workOrderId}/claim` | Added 2026-08-23 with the open-jobs board: a claim tells the resident who is coming, by name, exactly as accepting an offer does |

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
| `POST /worker/jobs/{workOrderId}/claim` | Added 2026-08-23 with the open-jobs board: "who is responsible" acquires an answer that came from the responsible person — here before any supervisor asked |
| [`GET /complaints/{complaintId}/schedule-request`](#get-apiv1complaintscomplaintidschedule-request) | *When to expect action*, answered with an hour and a name rather than an SLA estimate — and `respondBy` says when the association stops waiting |
| [`POST /complaints/{complaintId}/schedule-time`](#post-apiv1complaintscomplaintidschedule-time) | Added 2026-08-23 with ruling F1: *when to expect action* becomes the resident's own answer, so the visit happens when they said it could instead of at an hour a supervisor guessed and they had to ring up to move |

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
| The `0035` hiring flow (applications · invitations · [`members/{staffId}/remove`](#post-apiv1departmentsdepartmentidmembersstaffidremove)) and [`…/staff-invitations`](#post-apiv1departmentsdepartmentidstaff-invitations) | Roster and roles — the four direct staff-write endpoints were retired 2026-08-12, superseded by these |
| [`POST /admins`](#122-post-admins--promote-a-member-to-administrator) | Who the directory can name as a head; the office and the contact entry stay one thing |

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
| US-3.1 event-specific access codes | **served** — as of `0040`; see below |
| US-3.2 auto guest access on booking | **none** |
| US-3.3 digital registers | **served** — §19 |
| US-3.4 water tanker log | **served** — §19 |
| US-3.5 offline fallback verification | **served** — as of 2026-08-11; the gate screen now caches the bundle and verifies against it |
| US-3.6 retention + downloadable reports | **served** for gate operations — §19 |

> **Four of these six moved on 2026-08-10, and the section below was written when none of them had.**
> `0040` built the gate: two registers, incidents, shifts, posts, credential verification, an offline
> bundle and a CSV export. The paragraphs that follow are left as compiled — they are the record of
> what was true, and the corrections are stated inline rather than by rewriting them, which is this
> folder's convention for a claim that has been overtaken.
>
> **`US-3.1` is served.** The prose below says the fifth requirement — one code admitting *many*
> guests — is *"the one thing the current model cannot express, since a pass belongs to one
> request"*. That turned out to be wrong in a way worth recording: `guest_count` has been a column
> since `0032` and **nothing had ever read it**, so the model could already express the requirement
> and no endpoint had ever asked. `verify_gate_credential` counts admissions against it. The genuine
> schema change the paragraph predicted was never needed.
>
> ~~**`US-3.5` is partial rather than served**, and the missing half is not in the backend. The server
> side is complete — a time-boxed bundle to cache, and a reconcile that re-verifies every queued
> admission and records its own verdict beside the device's claim. What is missing is the gate
> screen that holds the bundle and verifies against it.~~
>
> **Closed 2026-08-11.** The gate screen exists: `frontend/src/pages/SecurityDashboard/GateHome.jsx`
> over `features/security/offline/`. It caches the bundle in `localStorage`, verifies a scanned
> credential locally with `crypto.subtle.digest('SHA-256')` against `codeHash`/`passHash`, queues
> every offline scan under a `crypto.randomUUID()` `sourceClientId`, and reconciles on the browser's
> `online` event or on demand. Three things about it are deliberate and worth stating here because
> they are properties of the *story*, not of the code:
>
> * **Every offline verdict is labelled provisional on screen.** A device holding the bundle can
>   check a hash and a validity window; it cannot know how many of a four-guest party are already
>   inside, or that the resident cancelled the pass after the bundle was cut. The card says so in
>   words rather than looking like the server agreed.
> * **The device never returns `departed`.** The guest-count arithmetic needs `visitor_events`, so an
>   offline second scan reads as another admission and reconcile decides which it was.
> * **Rejected entries survive reconcile and stay on screen until dismissed one at a time.** An
>   admission the server refuses is the single most important thing this mechanism can report, and
>   clearing it with the rest of the batch would throw it away.
>
> This is also the first place in the codebase where `localStorage` holds domain truth rather than a
> render cache, overriding the rule in `store/appStore.js` — deliberately, for one screen, with the
> reasoning written in `offlineGate.js`'s header. The safety property is reconcile, not the cache.
>
> This previously read *"`frontend/public/` has no service worker, which is also why `US-2.7`'s push
> cannot buzz a phone"*. **That file shipped 2026-08-10**, closing US-2.7 — and the sentence
> overstated its role here anyway: `localStorage` holds a bundle without a service worker, and what
> the worker actually buys `US-3.5` is surviving a reload during the outage.
>
> **`US-3.6`'s verdict below is unchanged in its reasoning and changed in its conclusion.** It said
> retention was not the gap and the two real gaps were *(a)* gate data to retain and *(b)* the
> download. §19 supplies both.

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

| Endpoint | Role |
|---|---|
| [`POST /visitor-passes`](#post-apiv1visitor-passes) | Issues the scheduled, time-boxed code. `validFrom` / `validUntil` can be set days ahead |
| [`POST /visitor-passes/{passId}/cancel`](#post-apiv1visitor-passespassidcancel) | Revokes it, so a cancelled function does not leave a working code scheduled to activate |

> **That table is new on 2026-08-08 and is a correction, not new coverage.** The two operations above
> have served this story since `0032` and this section has said so in prose — but `US-3.1` was absent
> from [`api_annotations.py`](../backend/scripts/api_annotations.py)'s story table, so
> [`openapi.yaml`](openapi.yaml) recorded *no operation at all* as serving it. A story marked partial
> whose evidence is prose only is exactly the state the `x-user-stories` guard exists to prevent, and
> the guard could not catch it: it checks that every **operation** declares its stories, never that
> every **story** a verdict credits has an operation declaring it. The totals do not move — both
> operations already carried `US-2.2`, so the traced count stays 51.

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

**124 of the 199 operations map to no story in the document.** Not a defect — the team wrote stories
about pain points in an existing product, not about the plumbing every product needs.

> **~~106 of the 179~~ — recounted 2026-08-12, and the table below rebuilt from the spec a second
> time.** Sessions 67–68 added sixteen net operations and four whole `x-no-user-story` groups the
> table had no rows for at all — department-scoped skills, staff invitations, the complaint
> department-request loop, and the department options list — while the hiring row gained two
> operations it had been under-counting (`/service-providers/{id}` and `/worker/communities/search`,
> both already live on 2026-08-11) and the telemetry write arrived on its own. The rebuild is
> mechanical rather than editorial: every row below is one
> `x-no-user-story` group in [`openapi.yaml`](openapi.yaml), so the diff is the finding. **The one
> thing that changed in kind:** the skills row used to be a single `/skills` entry worth one
> operation; the four department-scoped skill writes belong to the same rationale and now sit with
> it, which is why `Master data` moves 11 → 21 while nothing was reclassified.

> **~~90 of the 163~~ — recounted 2026-08-11, and the table below was rebuilt rather than
> patched.** The old table's rows were a hand-made grouping that had stopped matching the spec: four
> whole families were missing from it (departures, direct messages, the gate roster, the worker's
> own availability), and two others had merged upstream without merging here. It summed to 74 when
> the spec said 106. **Every row below is now one `x-no-user-story` group in
> [`openapi.yaml`](openapi.yaml)** — same grouping, same counts, same rationale, so the next
> divergence is a diff rather than an arithmetic error. The rationale column here is the short form;
> the spec carries each one in full.

| Group | Ops | API type | Why no story |
|---|---|---|---|
| `/auth/*` | 16 | Functional | Nobody writes a user story about signing in until it breaks |
| `/departments/{id}/{applications,candidates,invitations,blacklist,members}`, `/worker/{applications,communities}`, `/service-providers/{id}` | 13 | Feature | Applying, inviting, hiring, removing and barring. It *enables* US-2.7, US-2.8 and US-3.3–US-3.6 without serving any of them — none can begin until somebody has been hired |
| `/access-requests/*`, `/admin/access-requests/*`, `/invitations/*`, `/admin/invitations` | 10 | Feature | Joining a community; the interviews were with people already in one |
| `/departments/{id}/departures/*`, `/departments/{id}/staff/{staffId}`, `/worker/communities/{staffId}/departure` | 10 | Feature | Leaving: a dated request the manager decides, releasing booked work back to the pool. Everybody described being hired and nobody described quitting — the person who quits is not in the room when the society is interviewed |
| `/security/{posts,roster,shifts}` | 7 | Master data | Where a guard stands and who is standing there. All four gate stories assume it exists and none describes creating it; the security manager was not in the room either |
| `/skills`, `/departments/{id}/skills` | 6 | Master data | The global list of trades a service person can offer. The complaint stories assume somebody competent turns up; something still has to say what competent means. Global rather than per-community on purpose — the "which communities need my skills" search runs before the person holds a membership anywhere |
| `/worker/{availability-rules,calendar,unavailability}` | 6 | Feature | A service person's own calendar, leave and working week. The dispatch sweep reads these to decide who can be offered a job, so a wrong answer is a resident told nobody is available — but nobody described their own availability as a problem with their society |
| `/work-orders/{id}`, `/departments/{id}/work-orders`, `/complaints/{id}/{work-orders,schedule}` | 5 | Feature | The supervisor's queue, the job record, the edit. **Three operations on this surface *do* map** — proposing a time, assigning a person, moving or cancelling a visit. Claiming US-2.8 for a screen only the department can open would make the matrix say a resident sees something they cannot |
| `/messages/*` | 5 | Feature | The chat dock, from the PO's 2026-08-10 instruction. No interviewee asked for chat; the PO did, and the thread-lock clause is theirs verbatim |
| `/service-providers*` | 5 | Feature | A service person registering themselves. The stories were collected from residents and committee members; **nobody interviewed the plumber** |
| `/conversations/*` | 4 | Feature | The chat between a department and a service person. Every hiring decision is made after somebody asked a question; today that happens on a phone nobody logs |
| `/departments/{id}/staff-invitations*` | 4 | Master data | Creating the manager who runs a department and the supervisor who helps — hiring needs somebody to do the hiring. Leadership has **no** registration flow by ruling: an administrator types a name and an email. Nobody described appointing their own manager, because in every society interviewed the manager was already there |
| `/worker/jobs*`, `/worker/open-jobs`, `/worker/snapshot` | 5 | Feature | The worker's own queue, the open-jobs board (2026-08-23) and the aggregate behind them. **Five operations on this surface *do* map** — accepting, claiming off the board, starting, completing and reporting a failed visit all reach the resident; the board's *read* is the worker's own screen and maps to nobody's story, like the job list |
| `/communities/*`, `/onboarding/community` | 3 | Feature | Founding a community — a once-per-community act |
| `/complaints/{id}/department-requests*`, `/departments/{id}/complaint-department-requests` | 3 | Feature | A supervisor telling their manager a complaint belongs to another department, and the manager's answer. Entirely inside the staff side of the wall — no resident ever sees it, and the complaint stories are about what happens to *their* complaint, not who ends up holding it |
| `/dashboard/amenities` `POST` · `PUT` · `DELETE` | 3 | Master data | Amenity catalogue upkeep; the stories assume amenities already exist |
| `/push/{vapid-key,subscriptions}` | 3 | Non-functional | Web Push plumbing. A resident experiences US-2.1; nobody experiences a VAPID key |
| `/settings` `PUT`, `/billing-settings` | 2 | Configuration | Configuration behind other features |
| `/invoices/mine`, `/invoices/{id}/pay` | 2 | Feature | **Listing and paying maintenance dues.** A whole screen, and no story: `US-2.12`, the only payment story anybody wrote, is specifically about *amenity booking* payment, and mapping an invoice path onto it would claim coverage the interviews never gave |
| `/me/household`, `/me/household/phones` | 2 | Feature | Who is registered to a flat, and adding a number without waiting for an admin. Drawn from the prototype's Profile screen; the stories are about reaching **management** (US-2.9, US-2.10), not about the household reaching itself |
| `/notifications/{id}/read`, `/notifications/read-all` | 2 | Feature | Managing the list rather than being notified. US-2.1, US-2.4 and US-2.7 all ask to be *told* |
| `/settings` `GET` | 1 | Configuration | Same, **with one exception worth its own row**: `modules[].backendStatus` reports which features are unimplemented, which makes it the only endpoint that describes this matrix's gaps in machine-readable form |
| `/amenities/available` | 1 | Feature | Reading the catalogue. The booking stories assume a resident already knows which amenity they are booking |
| `/complaints/{id}/read` | 1 | Feature | Bookkeeping the unread badge US-2.6 and US-2.8 imply. Nobody narrates having read an update when asked what is wrong with complaints |
| `/invoices/{id}/payments` | 1 | Feature | The admin's record of a maintenance payment taken outside the app. **Moved here from `US-2.12` on 2026-08-04** — see the note below |
| `/department-options` | 1 | Master data | Id and name of each department, so a destination can be picked from a list. It exists because of a control that could not be drawn: `GET /departments` is admin-only, so the only way for a manager or supervisor to name a department was to type a UUID |
| `/telemetry/service-signup` | 1 | Non-functional | Privacy-minimal launch-funnel measurement for operators: one allowlisted event name against a random first-party visitor id. No interviewed user experiences this write as a feature |
| `/health` | 1 | Non-functional | Platform liveness, deliberately outside `/api/v1` |

**The API type is the point of this table, not the absence.** Each of these operations carries
`x-no-user-story` in [`openapi.yaml`](openapi.yaml), stating `Not covered by user story` and then
what the operation *is*. `Functional`, `Configuration`, `Master data` and `Non-functional` are
plumbing, and their absence from the story set is expected. **`Feature` is not**: ~~72~~ **77**
operations here are user-facing capability nobody wrote a story for. That is a finding about the
story set, not about the API, and §16.7 is where it turns into work.

**Twenty-five of those ~~47~~ ~~72~~ 77 arrived together, and they say something the earlier ones did not.** The
service-operations surface — registration, hiring, conversations, and the supervisor's half of
dispatch — maps to no story because the interviews were conducted with people who *live* in a
society and people who *run* one. The service person is the third party in every complaint the
resident stories describe, and not one question was put to them. That is a gap in the research, not
in the API, and it is a different kind of gap from "nobody narrates clearing a badge".

**`0036` is the first of these four migrations to move the *mapped* count, and it moved it by five.**
Proposing a visit, assigning a person, moving one, cancelling one and reading when somebody is coming
all reach the resident, which is what US-2.7 and US-2.8 are about — lifecycle notifications, and
knowing who is responsible and when to expect action. Twenty-one operations of hiring machinery
mapped to nothing; the first ten that put a named person at a door mapped to two stories. That is the
shape of the gap stated precisely: the story set is about outcomes residents experience, and this
feature spent four steps building the thing that produces them.

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

> **Recount, 2026-08-20.** Straight out of `x-user-stories` in the generated spec: **75 operations
> serve at least one story, 124 serve none, 75 + 124 = 199.** By API type the 124 are `Feature` 79,
> `Master data` 21, `Functional` 16, `Non-functional` 5, `Configuration` 3. Only one of the four
> operations added since the previous recount is this session's — `POST /complaints/admin-raise`,
> which is **mapped** (US-2.5, US-2.6) — so the mapped count moved 73 → 75 and the unmapped 122 →
> 124 with three operations arriving between the two recounts unremarked. The 2026-08-12 figures
> this paragraph replaces were **73 / 122 / 195**, `Feature` 77.
> **The mapped count did not move at all** across Sessions 67–68 — twenty new operations arrived
> (work-order triage, the amenity admin surface, the money three, `POST /admins`, telemetry,
> department options, the department-request loop) and four `…/staff` writes were retired, and not
> one of the twenty maps to a story. That is the same finding the paragraphs above make, made once
> more and larger: this branch has spent two sessions building the machinery behind outcomes the
> story set already names, and the story set still has nothing to say about the machinery.
>
> **Recount, 2026-08-11 — the figures then, and the last three lines of history behind them.**
> Straight out of `x-user-stories` in the generated spec: **73 operations serve at least one story,
> 106 serve none, 73 + 106 = 179.** By API type the 106 are `Feature` 72, `Functional` 16,
> `Master data` 11, `Non-functional` 4, `Configuration` 3. The three steps since the count below:
> `0043`/`0045` added the ten departure operations, `0046` the five message operations, and `0047`
> the roster read — **sixteen operations, none of which maps to a story**, which is the same finding
> the paragraphs above make and not a new one. The command that produces these numbers is in
> [`api_yaml_mapper.md`](api_yaml_mapper.md) §6.3.
>
> **The totals move with the surface, and these are recounted, not estimated.** The figures above
> come from `x-user-stories` in the generated spec. **56 operations serve at least one story, 74
> serve none, and 56 + 74 = 130.** `0033` added eight operations, of which four map and four do not,
> and step 7 added a ninth, `GET /resident/snapshot`, which maps. The `Feature` count moved from 17
> to 21 on those eight, then to 22 when `POST /invoices/{id}/payments` gave up a story it had never
> earned, then to 42 when `0034`, `0035` and `0038` added twenty-one operations of which twenty are
> `Feature` and one is `Master data` — **not one of which maps to a story** — and then to **47** on
> `0036`'s ten, five of which do. So the mapped count stood still for three steps and moved for the
> first time on the step that schedules a visit. `Functional`, `Configuration` and `Non-functional`
> are unchanged at 16, 3 and 4; `Master data` is 4.
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
> place on 2026-08-04, which was still allowed then and is not now.

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
| 8 | ~~Add CSV export~~ — **half done**: `GET /security/exports/{dataset}` ships the gate's four datasets (§19), so **US-3.6 closes**. US-1.6 does not — the administrative reports it asks for are a different surface with a different query behind it, and nothing exports them yet | US-1.6, ~~US-3.6~~ | What is left is the admin half |

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
> **That last exception is spent.** `frontend/public/sw.js` was built on 2026-08-10 and US-2.7 is
> **served** in §16.4. Item 7 has now closed three of its four stories; US-2.1 is the one still
> open, and it is open for a reason no transport fixes — nothing raises the approval request it
> answers, which is a missing *write*, not a missing delivery.
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
| 2026-08-23 | **The resident sets the time, and the system books what nobody schedules.** One operation added — `POST /complaints/{complaintId}/schedule-time` (surface **209 → 210 across 179 paths**) — plus `mode` on `GET /complaints/{id}/schedule-request` and `awaitingResident` on `TriageSnapshot`, both additive. Backed by `20260823180000_resident_sets_the_time.sql` and frozen in [`plans/RESIDENT_SETS_THE_TIME_SPEC.md`](plans/RESIDENT_SETS_THE_TIME_SPEC.md) under the 2026-08-23 rulings F1–F3. **The raise form loses its date and time for everyone.** A resident-subject job now arrives as a request to the resident to name the hour, and only their answer puts it on the open pile; a facility job is booked by the system into the first free slot, but only after every urgent (`high`) resident job in the department has somebody on it. Twenty-four hours of resident silence and the dispatcher books the first hour a serviceman can take and assigns them — the existing `resident_timeout` timer, which the deadline already armed, branching on whether a slot exists. **No new work-order status and no new event word**: pick-mode is `awaiting_resident` with a **null slot**, approve-mode is the same status with one, and the distinctions ride in payloads (`mode`, `resident_set`, `auto_assigned`) because both vocabularies are closed CHECKs on live tables. The one constraint widened is `dispatch_tasks_kind_check`, for the new `facility_auto_assign` task. `dispatch_candidates` was **refactored, not forked**: the body moved to `dispatch_candidates_at`, parameterised by a hypothetical hour so `find_first_available_slot` can walk the calendar without writing trial slots to `work_orders` — six triggers fire on that table — and the three-argument entry point became a delegate with the same signature, ordering and grants. The triage snapshot gains a **sixth** array, `awaitingResident`, and `openRequests` narrows to `draft`/`offered`: a job waiting on a resident is not work the supervisor can pick up. `US-2.8` gains two rows; the board predicate, the supervisor's offer and force-assign paths, and `respond_to_work_order_schedule` are untouched. |
| 2026-08-22 | **The supervisor's card actions — amendment 2, four operations and one flag.** `POST /complaints/{complaintId}/resolve`, `/priority-raise`, `/notes` and `/chat` (surface **203 → 207 across 176 paths**), plus `force` on `POST /work-orders/{workOrderId}/assign` and a guard widening on `GET /complaints/staff/complaints/{complaintId}` — backed by `20260822170000_supervisor_actions.sql` and frozen in [`plans/SUPERVISOR_TRIAGE_SPEC.md`](plans/SUPERVISOR_TRIAGE_SPEC.md)'s *Amendment 2*, under four product rulings. **Resolve** cancels every other live job with its workers told why and refuses while one is `in_progress`; it moves the complaint to `resolved` and leaves the timeline entry, the resident's notification and both auto-close timers to `complaints_on_resolved`, which already writes them. **Priority** is one-way `Low → Medium → High`, carried onto the complaint's live jobs because a job's urgency *is* its complaint's, and it is the one new `complaint_events` word this amendment cost (`priority_changed` — an enumerating CHECK means a word is a migration, the lesson of `20260822150000`). **Notes** are internal by a payload flag, invisible to the resident and untouched for the admin's resident-visible ones. **Chat** is a real `dm_threads` thread of a third kind, one per complaint, shared by the raiser and the whole department, locked when the complaint closes and unlocked when it reopens. `force: true` on assign routes to `force_assign_work_order` — the dispatch engine's own forced mechanics with the picking removed and a supervisor's guard added — while `false` is the offer flow byte for byte. The snapshot was **re-bucketed into five arrays**: *engaged* became *committed* (an unaccepted offer no longer counts, ruling A3), `openRequests` was added, and the two complaint sections now exclude **any** live work order, so a complaint appears exactly once across the five. `TriageWorkOrder` gains `offeredToName`, additively. |
| 2026-08-22 | **The supervisor's dashboard — two operations, and three facts the model could not state.** `GET /departments/{departmentId}/triage-snapshot` and `POST /complaints/{complaintId}/take-up` (surface **201 → 203 across 172 paths**), backed by `20260822120000_supervisor_triage.sql` and interface-frozen in [`plans/SUPERVISOR_TRIAGE_SPEC.md`](plans/SUPERVISOR_TRIAGE_SPEC.md), against which the screen was built in parallel. The snapshot answers the dashboard's four sections — new, taken up, assigned-but-not-started, being-worked-right-now — in **one read**, and **buckets them server-side**: *live* and *engaged* are defined once, in the RPC, because four definitions that must agree are one definition or they are four answers. Three new columns exist because three facts had nowhere to live: `complaints.taken_up_at` (+ `taken_up_by_membership_id`), so "new" and "mine, not yet dispatched" stop being the same row; `work_orders.started_at`, because `start_work_order` let the moment fall into `updated_at` and the next write overwrote it; and `work_orders.supervision_inherited_at`, which is §16 of the handoff's "no new column" **partially reversed** so an inheriting supervisor can tell the work they chose from the work that arrived by somebody else's removal. Take-up is **triage ownership and never dispatch** — `assigned_to_membership_id` stays the dead column the 2026-08-21 ruling made it — and it gives `acknowledged` a deliberate second writer beside the worker-offer trigger; both move `open` and only `open`, so they cannot race. It notifies nobody, by ARCHITECTURE.md's passive-change rule: the resident reads the same fact as *In Progress* on the next SSE re-snapshot. `US-2.6`'s new row is take-up only; the dashboard read traces to no story, on the standing verdict that a screen only the department can open must not claim a story about what a resident sees. |
| 2026-08-20 | **`POST /complaints/admin-raise`, and "resident" stops meaning the role column.** One operation added (surface **195 → 199 across 168 paths**, three of the four having arrived unremarked before today). The endpoint files a complaint from the admin portal in two modes decided by one optional `forMembershipId`: **on a resident's behalf**, owned by their membership and appearing on their portal with every resident verb intact, or **attached to no flat**, owned by the admin and admin-portal-only. Provenance lives in the `raised` event — the actor is always the admin, `"on_behalf": true` in the payload — never in the complaint row, so it cannot move a complaint off the list of the person whose home the problem is in. New column `complaints.raised_via` (`'resident'`\|`'admin'`, `20260820150000_admin_raised_complaints.sql`) says which portal owns the raiser-side view; `complaint_overview` exposes it; `GET /complaints` and `GET /complaints/{id}` filter to `'resident'`; the snapshot's complaint rows carry `raisedVia` and print `flat` as `"—"` for `'admin'`. **Six routes widened and one narrowed** by the new `require_resident_capability` (§7.2): resident-ness is an active `unit_residencies` row, so an admin who owns a flat gets the verbs on their own home, while `POST /complaints` — previously any active membership — now refuses a flat-less `worker`, `security` or `manager` with the same `403` `community_role_required` it always used. `GET /auth/session` grants an admin the `resident` capability only with a residency, so the session and the per-request guard stop disagreeing. **`US-2.5`'s new row is the on-behalf mode only** and §16.4 says so; the unattached mode serves no story. |
| 2026-08-09 | **§18 added — service personnel.** Six operations backed by `0034`: registering as a service person, editing that registration, setting which trades you offer, the offline toggle, and the global skill catalogue. **The first surface on this API whose caller holds no community membership** — a plumber exists before any society has heard of them — which is why none of these routes resolves one and why CSRF is the only guard on the four writes. Overturns two things in print and says so: `USER_IDENTIFICATION.md` and §16.1's *"a staff member is a name on a roster, not an account"*, and `CONFLICT_RESOLUTIONS.md` R16's *"build nothing against them"* for `skills`. Coverage is unchanged — all six trace to no story, because every story this feature eventually closes begins at **hiring**, which is `0035` and not built. `app/api/deps.py` gained a multi-community resolver at the same time, additively: `get_active_membership` keeps its signature, its `Principal` parameter and its single round trip, and `tests/test_membership_set.py` is the evidence offered to the auth workstream. §18 sits after the meta-sections deliberately; the renumber is deferred to this feature's documentation sweep. |
| 2026-08-08 | **User-story sweep: the matrix was right and its index was not.** §16's verdicts, `api_annotations.py` and the spec agreed on all 24 stories; [`product/USER_STORIES.md`](product/USER_STORIES.md) — the one-line index of the same matrix — did not, on **six**. US-2.2, US-2.5, US-2.6, US-2.8 and US-2.12 still read *partial* or *none* after they closed, and US-2.3 read *none* after moving to partial. Every one erred toward under-reporting, which is the direction nobody checks. Fixed there, with the stale *reasons* on US-2.1, US-2.4, US-2.9 and US-3.1 rewritten too, and the three `#14-user-stories--endpoints` links under `product/` repointed at §16. Eight operations that carry a story tag were named nowhere in that story's own section — the amenity damage and charges writes (US-1.2), `POST /invoices` (US-1.6), `GET /notifications` (US-2.1, US-2.4, US-2.7), `PATCH /complaints/{id}` (US-2.7, which had no endpoint table at all) and `POST /admins` (US-2.9) — now listed. **US-3.1 was the one real traceability defect**: §16.5 has credited `POST /visitor-passes` and `/cancel` with issuing and revoking a scheduled code since `0032`, while the story was absent from the annotation table, so the spec recorded nothing as serving it. Tagged; counts unmoved at 51 served / 48 none, because both operations already carried US-2.2. Root cause recorded plainly: the export guard checks that every **operation** declares its stories, never that every **story** a verdict credits has an operation — `api_map_scan.py` now asks that too. |
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

---

## 18. Service personnel

Backed by migrations `0034`, `0035`, `0036`, `0037`, `0038`, `0039`, `0043`, `0045` and
`20260822120000`. Fifty-seven operations — `0037` is the engine and adds none of them; `0045` reworks
departures and adds the three employee-management reads; `20260822120000` adds the supervisor's
dashboard and its one verb — and they open with the first callers on this API who are **not
members of any community**. Direct messages (`0046`) are §20, because their audience is every
portal rather than this population alone.

That is the founding idea of the section. Everywhere else, a caller is a resident, a manager, an
admin or a security member *of somewhere*, and the request is scoped by an active membership resolved
from Postgres. A service person — a plumber, an electrician, a guard — registers themselves before
any society has heard of them, and is hired afterwards.

The subsections follow that person forward: **registration** and the trade catalogue (`0034`),
**hiring** (`0035`), the **conversation** that precedes and follows it (`0038`), the **work orders**
they are eventually sent on (`0036`), the **engine** that dispatches those without anybody pressing
anything (`0037`), and finally **the worker's own portal** (`0039`) — the jobs, the five verbs and
the working week. Only the last two are things a resident can feel, and they are the only ones that
map to a user story.

> **Section numbering — a ruling, not a deferral.** This section and §19 sit *after* the three
> meta-sections (§15 Not yet implemented, §16 User stories, §17 Changelog) instead of before them,
> which is not where the two previous content sections went. An earlier draft of this note promised a
> renumber in the documentation sweep. **That sweep happened and cancelled it**, because counting the
> cost changed the answer: of the 142 §15–§19 references across this repository, **49 are in
> `CHANGE_LOG.md`** — a dated record whose whole value is that it did not change afterwards. A
> renumber leaves two options for those 49 and both are worse than an odd ordering: rewrite them, and
> a historical entry says something it did not say; leave them, and every pointer in the log is
> silently wrong, which is worse than an odd ordering because a reader believes a pointer. So the
> numbers stay and this note explains them. Recorded in `plans/SERVICE_OPERATIONS_PROGRESS.md` §6.13.

> **`0039` is the worker portal, not security operations.** The plan reserved that number for gate
> operations; the worker's own endpoints turned out to need a migration of their own — `0034`–`0037`
> contain no worker-side write function at all, because until hiring existed there was no worker
> holding an account to call one — and they come first in the build order. **Security operations is
> `0040`.**

### What this overturns

`docs/product/USER_IDENTIFICATION.md:55-65` and §16.1 both state that a staff member has no login *by
construction* — *"a staff member is a name on a roster, not an account"* — and a typed roster entry
(the `staff` field on the department create/update, in its day `POST /departments/{id}/staff`, retired
2026-08-12) deliberately leaves `membership_id` null. **That is now overturned.** A
service person registers, holds an account, and is issued a real `worker` or `security` membership by
the manager who hires them. The `membership_role` enum has carried both values since the baseline and
nothing has ever issued one.

`docs/CONFLICT_RESOLUTIONS.md` **R16** parked twelve baseline tables with *"build nothing against
them"*. `skills` is the first to be un-parked. `staff_skills` is superseded and is deleted at the end
of this feature, because skills belong to the **person** and not to a roster row — the "which
communities need my skills" search has to run for someone nobody has hired yet, and a skill keyed to
a staff assignment gives that person nothing to search with.

### The catalogue is global; a community's categories are not

`skills` is one seeded list of trades. `complaint_categories` is per-community, and `0034` adds a
nullable `skillId` to it, filled by a trigger that name-matches against the catalogue.

**Without that link the community search returns nothing, for everybody.** It is the only join
between what a person can do and what a society needs done. A community inventing a category the
catalogue has no word for is therefore not an error — it means no service person is matched to it,
and the column stays null.

The written plan had a `skill_categories` join table here. It cannot work: a global skill against
per-community categories needs one row per *(skill, community)* pair, and would be silently
incomplete for every community created after the migration ran. One nullable foreign key replaced it.

### No membership guard, and CSRF is doing real work

None of these routes resolves a membership. A registered-but-unhired provider has none, so requiring
one would refuse them exactly the screens that let them apply for work.

Authorization has not gone away, it has moved: all three write RPCs resolve the caller from
`auth.uid()` themselves, and `service_providers` carries a read policy and **no insert, update or
delete policy at all**. There is no path from the API process to a row it does not own. The 403 on
the four writes is therefore the CSRF pair — which, on routes with no membership guard, is the only
thing standing between a cross-site form post and someone's registration.

### `GET /api/v1/skills`

The global catalogue of trades. **Requires authentication only.**

Returns a bare array rather than a `Page`: without `q` it is the whole catalogue, and paging
reference data would be an envelope around a constant.

```json
[{ "id": "…", "name": "Plumbing", "category": "maintenance",
   "description": "Leaks, taps, drainage, sanitary fittings." }]
```

| Query | Meaning |
|---|---|
| *(none)* | The whole active catalogue, alphabetical. What the service person's registration grid renders. `limit` is **ignored** in this mode — a truncated catalogue would hide trades from somebody choosing their own. |
| `q` | Closest matches (`skills_and_categories`'s `search_skills`): exact first, then prefix, then trigram similarity. What the department form's skill box calls on every keystroke. |
| `limit` | 1–50, default 10. Only meaningful with `q`. |

`category` is free text — `maintenance`, `facilities` or `security` for the seeded twelve, and
`other` for anything added through `POST /skills` — rather than an enum, because the catalogue is
data and a closed enum would mean a code change before an operator could add a trade. A retired
trade is filtered out here rather than deleted, so a provider who has held it for two years keeps
the row that says so.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials, or credentials that no longer verify |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/skills`

Add a trade to the global catalogue. **Admins and department managers only.**

```json
{ "name": "Lift Maintenance", "category": null, "description": null }
```

**The status code is the answer to "did this exist already".** The match is case- and
whitespace-insensitive, so `"  plumbing "` finds `Plumbing`:

| Outcome | Status | Body |
|---|---|---|
| Created | `201` | `{ "id": "…", "name": "Lift Maintenance", "category": "other", "description": "", "created": true }` |
| Already existed | `200` | the same shape with `"created": false` and the **stored** spelling |

Typing a trade that already exists is not an error and is not reported as one. A **retired** trade
asked for again is reactivated rather than duplicated — `is_active` goes back to true and the
provider history hanging off it is untouched.

Omitted `category` becomes `other` rather than null, because `category` is non-null on the wire and
the worker's registration grid groups by it; `other` earns a visible group, which is honest — nobody
classified it.

**The catalogue is global.** A skill one community adds is immediately available to every other, and
that is the point rather than a leak: one vocabulary is what makes a plumber claim "Plumbing" once
and match everywhere. The bar is admin-or-manager rather than admin-only because a manager who needs
"Lift Maintenance" should not have to file a ticket to type a word — that is how a catalogue ends up
with everything under Others.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid`, `role_not_permitted` | The CSRF pair failed, or the caller is neither admin nor manager anywhere |
| 422 | `request_validation_error`, `check_violation` | A blank name, or one over 80 characters |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/complaint-categories`

Every complaint category in the caller's community, with the trade each one resolves to.
**Admins and department managers only.**

```json
[{ "id": "…", "name": "Plumbing", "skillId": "…", "skillName": "Plumbing", "departmentCount": 2 },
 { "id": "…", "name": "Plumbling", "skillId": null, "skillName": null, "departmentCount": 1 }]
```

**`skillName: null` is the row this endpoint exists to surface.** `complaint_categories.skill_id` is
filled by exact name match against the catalogue (`link_category_skill`, `0034`), and a category
matching no trade is not an error — a community may name one the catalogue has no word for. But it
has a consequence nobody could see: that category matches no service person in
`search_hireable_service_providers` or `search_serviceable_communities`, so complaints filed under it
reach nobody, silently. The department form renders it as a warning.

`departmentCount` is how many departments claim the category. Zero means complaints filed under it
route to no department at all.

This path was retired by the frontend wiring audit and **reinstated by `skills_and_categories`** — see
`docs/FRONTEND_WIRING_AUDIT.md`. The reinstated read is not the retired one: it carries the skill
link, which never existed before.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `role_not_permitted` | Not an admin or manager |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/departments/{departmentId}/skills`

The trades one department needs, alphabetically. **Admins, and the manager of that department.**

Returns the same `Skill` shape as `GET /skills`, because it is the same object — a second shape for
it would be two vocabularies for one thing.

**Empty is the normal answer.** A department inherits no skills by default, and in particular
inherits none from its complaint categories. The two answer different questions — which trade handles
this kind of complaint, versus which trades this department employs — and deriving one from the other
would give every department a list nobody chose.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `role_not_permitted`, `HB403` | Not an admin or manager, or a manager of a different department |
| 404 | `not_found` | No such department |
| 500 | `internal_error` | Unhandled |

### `PUT /api/v1/departments/{departmentId}/skills`

Replace the department's skill set. **Admins, and the manager of that department.**

```json
{ "skillIds": ["…", "…"] }
```

Ids rather than names: by the time this is sent every skill exists, because the form's add button
creates one through `POST /departments/{id}/skills` and gets an id back. Accepting names here would
be a second, quieter way to write to the global catalogue.

**Every id is validated before anything is deleted.** A request carrying one retired or unknown id
fails with 422 and leaves the set as it was, rather than emptying the list on its way to failing.

The response is the set read back from the database, not the request echoed, so a caller learns what
actually landed.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid`, `role_not_permitted`, `HB403` | The CSRF pair, the membership role, or a manager of a different department |
| 404 | `not_found` | No such department |
| 422 | `request_validation_error`, `check_violation` | An id naming no active skill |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/departments/{departmentId}/skills`

Add a skill by name, creating it in the global catalogue first if it does not exist.
**Admins, and the manager of that department.**

```json
{ "name": "Lift Maintenance" }
```

**This is the department form's "Add skill" button, and it is deliberately one call.**
Create-then-attach from the client can half-fail, and the half that lands is a skill created and
attached to nothing — catalogue litter nobody asked for, produced by the failure that happens on a
phone at the end of a long form.

Same status-code rule as `POST /skills`: **201** when the trade was newly created, **200** when an
existing one was attached. Attaching a skill the department already has is idempotent, not an error.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid`, `role_not_permitted`, `HB403` | The CSRF pair, the membership role, or a manager of a different department |
| 404 | `not_found` | No such department |
| 422 | `request_validation_error`, `check_violation` | A blank name, or one over 80 characters |
| 500 | `internal_error` | Unhandled |

### `DELETE /api/v1/departments/{departmentId}/skills/{skillId}`

Detach one trade from one department. **Admins, and the manager of that department.**

The skill itself is untouched — it is global, and another department almost certainly needs it.
Detaching one the department does not have is a **no-op, not a 404**: the caller's intent is already
satisfied.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid`, `role_not_permitted`, `HB403` | The CSRF pair, the membership role, or a manager of a different department |
| 422 | `request_validation_error` | A malformed id |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/service-providers`

Register as a service person. **Requires authentication only.**

```json
{ "displayName": "Ravi Kumar", "headline": "Plumber, 12 years",
  "phone": "+919876543210", "latitude": 12.9716, "longitude": 77.5946,
  "locationLabel": "Indiranagar, Bengaluru", "serviceRadiusKm": 15,
  "skillIds": ["…"] }
```

**`locationLabel` is optional and never load-bearing** — added 2026-08-21 with the location picker.
It is a coarse place name of at most 120 characters, filled in for the person by
`GET /geo/search` or `GET /geo/reverse` (§21) and then editable, and it exists so a hiring
manager's candidate card can say *where* rather than only *how far*. Distance is computed from
`latitude`/`longitude` as it always was; nothing reads this field to decide anything. Omitting it,
here or on the `PATCH`, leaves any stored label alone.

**One atomic, idempotent registration.** Profile upsert and full skill replacement share one
PostgreSQL transaction. Invalid or inactive skills roll the whole write back; retrying for the same
identity repairs the existing provider rather than creating another one.

Coordinates and at least one active skill are mandatory. The radius defaults to 15 km and must be
between 1 and 500 km. A first registration is refused when the identity already holds an active
resident, admin or manager membership: professional accounts are separate accounts.

**A manager or supervisor is refused outright, added 2026-08-21** (ruling 1: *leadership is
invite-only and never from the marketplace pool*). This is a different refusal from the one above and
needs to be, because a supervisor holds a **`worker`** membership — rank is not role — so the
separate-account check deliberately lets them through. The message says why there is nothing here for
them rather than merely that they may not: *"You manage or supervise a community, and leadership is
not part of the marketplace. A manager or supervisor is placed by an administrator, never matched by
distance and trade, so there is no professional profile for you to register."* The worker portal
already routes leadership past this form (`WorkerLayout`), so a caller reaching it is using the API
directly or has just been given a posting in another tab.

The response is the full profile read back from the database, not the request echoed with an id
attached — see `GET /service-providers/me` for the three fields that could not be echoed.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid` | The CSRF pair failed |
| 409 | `conflict` | The identity already has an active non-professional membership |
| 409 | `leadership_marketplace_conflict` | The identity currently manages or supervises a community (ruling 1, 2026-08-21) |
| 422 | `request_validation_error`, `missing_value`, `check_violation`, `provider_location_required` | Invalid name, location, radius, duplicate/empty skills, or an unknown/inactive skill |
| 503 | `service_provider_registration_not_deployed` | The registration RPC is not on the database yet — the rollout gap named in §21 |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/service-providers/me`

The caller's own profile. **Requires authentication only.**

```json
{ "id": "…", "displayName": "Ravi Kumar", "headline": "Plumber, 12 years",
  "bio": "", "phone": "+919876543210", "latitude": 12.9716, "longitude": 77.5946,
  "locationLabel": "Indiranagar, Bengaluru", "serviceRadiusKm": 15,
  "status": "active", "isAvailable": true,
  "skillIds": ["…"], "skillNames": ["Plumbing"], "communityCount": 2,
  "createdAt": "…", "updatedAt": "…" }
```

**404 when the caller has never registered, rather than an empty profile.** The two are different
answers and the dashboard routes on the difference: an unregistered caller is sent to the
registration form, not shown a blank one they might take for saved.

**Three fields are not the caller's to set**, which is why every write here re-reads rather than
echoes. `skillNames` comes from the catalogue, `serviceRadiusKm` defaults in SQL when omitted, and
`communityCount` is counted from live `worker` and `security` memberships. That last one drives the
dashboard's empty state — a provider employed nowhere sees the *find work* prompt instead of an empty
calendar.

`status` is `active` or `suspended`. A suspended provider keeps their profile and their history; they
simply stop being offered work.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 404 | `service_provider_not_found` | The caller has not registered |
| 500 | `internal_error` | Unhandled |

### `PATCH /api/v1/service-providers/me`

Edit the details — **everything except the name.** **Requires authentication only.** The `POST`
body minus `displayName`.

**`displayName` is not accepted here, and sending it is a `422`** (the strict models refuse
unknown fields). A service person's name and email are identity, edited nowhere in settings — a
product-owner rule from 2026-08-10. Registration names you; this route never renames you. (`0045`
made the RPC coalesce a null name onto the stored one, which is what made the field droppable.)

**An omitted field is left alone, not cleared.** The RPC coalesces onto the stored value, so a
client may send one changed field without first reading the other six and echoing them back — and a
client that *does* echo them back cannot accidentally erase what it failed to read.

**No 404 — but a name-shaped 422.** The RPC is an upsert, and since `0045` it requires a name only
when there is nothing stored to keep: a `PATCH` from someone who never registered has no stored
name to coalesce onto and comes back `422 missing_value` telling them to register first. The two
routes below are `select into` and raise a real 404.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid` | The CSRF pair failed |
| 422 | `request_validation_error`, `missing_value` | As `POST` |
| 500 | `internal_error` | Unhandled |

### `PUT /api/v1/service-providers/me/skills`

Set which trades this person offers. **Requires authentication only.**

```json
{ "skillIds": ["…", "…"] }
```

```json
{ "skillCount": 2 }
```

**A `PUT` of the whole set, not add and remove.** The screen is a list of checkboxes, and two tabs
toggling different boxes against a delta API is a lost update that nobody notices until a plumber
stops being offered plumbing.

The set must contain at least one unique active skill. An unknown or retired id rejects the whole
replacement, leaving the current set untouched. `skillCount` confirms the committed set size.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid` | The CSRF pair failed |
| 404 | `not_found` | The caller has not registered as a service provider |
| 422 | `request_validation_error` | More than 40 ids, or an id that is not a string |
| 500 | `internal_error` | Unhandled |

### `PATCH /api/v1/service-providers/me/availability`

The dashboard's offline toggle. **Requires authentication only.**

```json
{ "isAvailable": false }
```

```json
{ "isAvailable": false }
```

Going offline stops the dispatch sweep offering new jobs — `dispatch_candidates` (`0037` §4) reads
this column, so the toggle is honoured by the engine itself rather than by a screen. **It does not
cancel work already accepted**: a worker who agreed to be somewhere at four o'clock has made a
commitment a toggle does not retract, and a resident has been told their name. Calling that visit off
is `POST /work-orders/{id}/cancel`, which requires a reason and notifies both of them. The worker's
*own* way to hand a job back arrives with the worker portal.

The value comes back from the database rather than being echoed, for the same reason as everywhere
else here: it is the row's answer, and a caller with no row gets a 404 instead of a cheerful `false`.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid` | The CSRF pair failed |
| 404 | `not_found` | The caller has not registered as a service provider |
| 422 | `request_validation_error` | `isAvailable` missing or not a boolean |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/service-providers/{providerId}`

One service person, as a **hiring manager** sees them. Added 2026-08-11. Admin or manager only — the
one route on this router with a role guard, and the only one about somebody other than the caller.

```json
{
  "id": "e0c4…", "displayName": "Ravi Kumar", "headline": "Plumber, 12 years",
  "bio": "Twelve years on residential plumbing…", "phone": "+919876543210",
  "locationLabel": "Indiranagar, Bengaluru",
  "serviceRadiusKm": 15, "status": "active", "isAvailable": true,
  "skillIds": ["…"], "skillNames": ["Plumbing", "Carpentry"],
  "communityCount": 2, "registeredAt": "2026-07-02T09:00:00Z"
}
```

**Why this exists.** The hiring surface has three ways to arrive at a person — a tile in the
candidate list, a card in the applications inbox, and the `service_application_received`
notification — and all three are about somebody **not yet on a roster**.
`GET /departments/{id}/staff/{staffId}` is the employee page and needs a `staff_assignments` row,
which nobody being *considered* has. Without this route the hiring screens could list people and
never open one.

**Narrower than `GET /service-providers/me`, deliberately.** No `latitude`/`longitude` and no
`profileId`. The candidate list's `distanceKm` already answers where somebody is, measured from the
community's own point, which is the question a manager actually has; a home coordinate is a
different fact, offered for a different purpose. `serviceRadiusKm` is here because it is a statement
the person published about how far they travel.

**`locationLabel` is here for the same reason `serviceRadiusKm` is** — added 2026-08-21. It is a
place name of at most 120 characters that the provider typed or accepted ("Indiranagar,
Bengaluru"), which makes it a statement they published, not a measurement taken of them. The cap is
what keeps the distinction real: it holds a suburb and a city and does not hold a street address.
The coordinates it was derived from remain absent from this response and from the candidate list.

**The guard is the whole point of the route.** `service_providers_read` (`0034` §11) is
`auth.uid() is not null`, so Postgres would hand this row to any signed-in caller — a manager has to
be able to find somebody they have never met. `require_admin_or_manager` is what stops that being a
directory of every tradesperson in the country, browsable by every resident with an account. It is
**not** scoped to a department: the row is the person's own registration and carries no community's
business, and the search that surfaced them already applied this department's blacklist and roster
rules.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `forbidden` | Neither an admin nor a manager |
| 404 | `service_provider_not_found` | No provider with that id |
| 500 | `internal_error` | Unhandled |

### Hiring — one negotiation, two directions

Backed by migration `0035` and the forward-only professional-onboarding migration. The thing to understand before reading any of them
is that **an application and an invitation are one row**. `service_applications` carries a
`direction`: `applied` when the provider opened it, `invited` when the department did. Acceptance
does exactly the same three writes either way, so two tables would have meant two inboxes, two decide
functions and two chances for a hire to be half-done in one of them.

`direction` is what a client switches on to decide which buttons to render. Deriving it from the
caller's role would require the client to know its own role in every community on the screen, which
is exactly what a cross-community list does not have.

#### The hire is one transaction, and that is the whole point

`POST /departments/{id}/applications/{applicationId}/decide` with `accepted` writes **three rows
inside one transaction**: a `community_memberships` row carrying the `worker` or `security` role, a
`staff_assignments` row carrying the terms and pointing at both the membership and the provider, and
the decision itself.

Either all three exist or none does. A membership with no roster row is somebody who can sign in and
has no job; a roster row with no membership is a name on a list with no way in. Neither is repaired
by a client retrying, which is what a client would do — so the atomicity lives in
`decide_service_application` and there is no API path around it.

Which role is issued comes from `departments.kind`: a `security` department hires `security`,
everything else hires `worker`. Both values have been in the `membership_role` enum since the
baseline and **nothing has ever issued either one**.

#### Hiring authority is department-specific

The HTTP layer establishes identity; `can_hire_for_department(uuid)` in PostgreSQL decides whether
that identity can read or mutate this department's hiring data. An active department manager may
decide, whether represented by a scoped manager membership or an active roster row ranked
`manager`. Supervisors never qualify. Active community admins qualify only when the department has
no active manager. Cross-department and cross-community ids are refused by SQL/RLS.

#### Notifications follow the same decision audience

Person-addressed notifications allow an unhired professional to receive invitations and rejection
results. New applications notify only the selected department's active manager(s), with community
admins as the fallback only when no active manager exists. Recipient queries deduplicate membership
and roster representations of the same manager.

### `GET /api/v1/worker/communities`

Every roster the caller is on. **Requires authentication only.**

```json
[{ "staffAssignmentId": "…", "communityId": "…", "communityName": "Green Meadows",
   "communityCity": "Bengaluru", "departmentId": "…", "departmentName": "Plumbing",
   "departmentKind": "service", "membershipId": "…", "membershipRole": "worker",
   "rank": "member", "jobTitle": "Plumber", "shift": "Day", "status": "active",
   "startedAt": "2026-08-09", "endedAt": null }]
```

**A list, not a value**, and this is the surface the tenancy change in `app/api/deps.py` was made
for. A plumber hired by three societies has three memberships and one working week; every screen
downstream of this reads the union rather than a default community.

An empty list drives the dashboard's empty state — a registered provider employed nowhere is shown
the community search rather than a blank calendar. `?activeOnly=false` includes ended engagements,
which is the employment history.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 404 | `service_provider_not_found` | The caller has not registered |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/worker/communities/search`

Where the caller could apply, nearest first. **Requires authentication only.**

`?q=` filters by name, `?limit=` and `?offset=` page (default and maximum 20).

```json
[{ "id": "…", "name": "Green Meadows", "city": "Bengaluru", "state": "Karnataka",
   "communityType": "apartment", "distanceKm": 4.2,
   "matchingSkillNames": ["Plumbing"],
   "departments": [{ "id": "…", "name": "Maintenance" }] }]
```

**`departments` carries ids, not just names, and that is load-bearing.** `POST
/worker/applications` takes a `departmentId`, and a provider who is not yet a member of the
community cannot read `GET /departments` to find one — so a search result naming departments without
identifying them is a screen with nothing to press. Corrected 2026-08-10; it shipped as
`departmentNames: string[]` and the gap only became visible when the screen that consumes it was
built. Two parallel arrays were rejected as the fix: `array_agg(distinct …)` sorts by its own
argument, so the ids would arrive in uuid order and the names in alphabetical order and the two
would correspond only by accident.

Three rules, all applied in SQL: the community has a department whose categories need one of the
caller's skills, it has not blacklisted them, and they are not already a member of it. That last one
is why a resident cannot apply to work in their own society — one person holds one live membership
per community, so the hire would be refused and offering it would be offering a dead end.

Only active matching departments in communities inside the provider-controlled service radius are
returned. Missing community coordinates are excluded; a provider with missing coordinates receives
the typed `provider_location_required` error and repairs the registration form. Ordering is distance,
case-folded community name, then id, so offset paging is stable.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 404 | `not_found`, `provider_location_required` | The professional profile or its coordinates are missing |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/worker/applications`

The caller's own negotiations, across every community, newest first. **Requires authentication
only.** `?status=pending` narrows to the queue.

Both directions in one list — see above. This used to be the *only* way a rejected applicant or an
invited provider learned the outcome, because neither could be notified: the notification substrate
addressed a membership and neither of those people holds one. Since `0041` both are notified and this
is the authoritative read rather than the sole channel.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 404 | `service_provider_not_found` | The caller has not registered |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/worker/applications`

Apply to one department. **Requires authentication only.** `201 Created`.

**Request** — `{ "departmentId": "…", "message": "Available weekday mornings." }`

Returns the negotiation read back from the view, carrying the community name, the provider's skills
and the distance — none of which the request contained.

**One open negotiation per department at a time**, enforced by a partial unique index rather than a
read-then-write: applying twice is a `409`, not a duplicate row a manager has to reconcile. A
*decided* application may be followed by a fresh one, which is what makes removal different from
blacklisting.

**A blacklisted caller gets the same wording as an ordinary refusal.** Telling somebody they have
been barred, and by whom, is the community's decision to communicate rather than this endpoint's to
leak.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or the caller is barred in that community |
| 404 | `not_found` | No such department, or the caller has not registered |
| 409 | `conflict` | An application to this department is already open, or the caller already belongs to this community |
| 422 | `request_validation_error` | A message over 2000 characters |
| 500 | `internal_error` | Unhandled |

### `DELETE /api/v1/worker/applications/{applicationId}`

Withdraw an application the caller opened. **Requires authentication only.**

Returns the withdrawn row rather than `204`, because the screen that called this is a list and the
row stays on it with a new status. Nothing is deleted — `withdrawn` is a status, and the negotiation
remains readable by both sides.

**Only the side that opened a negotiation may withdraw it.** A manager cannot make an application
disappear by withdrawing it instead of rejecting it: a rejection is a record, and this would erase
it.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or the caller did not open this negotiation |
| 404 | `not_found` | No such application |
| 409 | `conflict` | Already decided |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/worker/applications/{applicationId}/decision`

Accept or decline an invitation. **Requires authentication only.**

```json
{ "decision": "accepted", "note": "Available from Monday." }
```

Only `accepted` and `rejected` plus an optional note are accepted. Rank, job title, shift,
membership role and department are not fields in this request; PostgreSQL also ignores any
caller-supplied employment terms for an invitation and commits the stored offer. Acceptance uses the
same atomic membership + staff assignment + decision transaction as the manager-side route.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed or the invitation belongs to another professional |
| 404 | `not_found` | No such application |
| 409 | `conflict` | Already decided, blacklisted, already a member, or mixed worker/security mode |
| 422 | `request_validation_error` | Unknown decision or caller-supplied terms |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/telemetry/service-signup`

Best-effort launch-funnel telemetry. The same-origin client first prepares anonymous CSRF and sends
one allowlisted `eventName`. The server assigns a random HTTP-only, SameSite visitor cookie for 30
days. Storage has only visitor id, event name and occurrence time; duplicate visitor/event pairs are
ignored and failures never block the product flow.

| Status | Code | Cause |
|---|---|---|
| 403 | `csrf_invalid`, `csrf_origin_invalid` | The CSRF pair failed |
| 422 | `request_validation_error` | Event name is outside the five-value allowlist |
| 500 | `internal_error` | Unhandled before the non-blocking storage boundary |

### `GET /api/v1/departments/{departmentId}/applications`

The department's inbox, newest first. **Requires `admin` or `manager`** — and see the two-guard note
above. `?status=pending` narrows to what is actionable.

**Both directions, deliberately.** A manager looking at who wants to work here also needs to see the
invitations already out, or they will invite somebody they invited last week and get a `409` they
cannot explain.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `community_role_required`, `forbidden` | Not an admin or manager, or not of *this* department |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/departments/{departmentId}/candidates`

Service people this department could hire, nearest first. **Requires `admin` or `manager`.**

```json
[{ "id": "…", "displayName": "Ravi Kumar", "headline": "Plumber, 12 years",
   "phoneE164": "+919876543210", "status": "active", "isAvailable": true,
   "serviceRadiusKm": 15, "distanceKm": 4.2,
   "locationLabel": "Indiranagar, Bengaluru",
   "matchingSkillNames": ["Plumbing"], "skillNames": ["Plumbing", "Carpentry"],
   "communityCount": 2, "hasOpenApplication": false }]
```

The mirror of `GET /worker/communities/search`: the same three rules seen from the other end, plus
"not already on this roster".

**`locationLabel` (2026-08-21) is nullable and is not the coordinate.** `distanceKm` is measured
from the community's pin and is the fact; the label is a coarse name the provider wrote for
themselves, and it is on this card because "4.2 km away" does not say *which direction*. The search
function returns no `latitude`/`longitude` and still does not.

**`matchingSkillNames` is the subset that put them on this list**, and it is not `skillNames`.
Showing only the second leaves a manager wondering why an electrician is being offered for a plumbing
department.

`hasOpenApplication` lets the screen offer *view* rather than a second invitation the unique index
would refuse.

This endpoint checks `can_manage_department` **inside the function**, not only at the router. A
`SECURITY DEFINER` function that takes a department id and checks nothing would be an enumeration
endpoint for every service person in the country.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `community_role_required`, `forbidden` | Not a manager of this department |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/departments/{departmentId}/invitations`

Offer somebody a place on the roster. **Requires `admin` or `manager`.** `201 Created`.

**Request** — `{ "serviceProviderId": "…", "jobTitle": "Plumber",
"message": "We need a plumber on Tuesdays." }`

An invitation **carries its terms**, because the person accepting has to know what they are
accepting. They cannot change them: `POST .../decide` ignores `jobTitle` on an invitation.

> **Changed 2026-08-11 — `rank` and `shift` are gone from this request.** A product-owner ruling:
> *"the only people added from servicemen are technicians (member). no supervisors or managers are
> hired this way. there is no shift or anything. there is no shift system. job assignment is only on
> demand as the auto assign or supervisor does."*
>
> Both halves are separate facts and both matter. **Rank**: leadership never comes from this path —
> an admin or a manager creates a manager or a supervisor by email through
> `POST /departments/{id}/staff-invitations`, and that person never registered as a service provider.
> Somebody hired *here* registered themselves and joins as a `member`; a promotion afterwards is
> `PATCH /departments/{id}` with a `head` name — the one path that demotes the incumbent in the
> same transaction. (This line once cited `PATCH …/staff/{staffId}`, which was wrong twice over:
> that handler refused to patch `rank`, and it was retired 2026-08-12.)
> **Shift**: `staff_assignments.shift` is a descriptive text column from `0019`'s typed-roster era and
> **nothing schedules from it** — work reaches a worker through the dispatch sweep (`0037`) or a
> supervisor's assignment, and a guard's actual rota is `security_shifts` (`0040`), a different table
> with real timestamps.
>
> This is a **narrowing of the API, not a schema change**: the column and `0035`'s `p_rank`/`p_shift`
> parameters both stay, and no migration was needed because `decide_service_application` already
> defaults an omitted rank to `member`. A stale client still sending `rank` is **ignored, not
> rejected** — the models do not forbid extra fields — so a cached bundle cannot produce a
> supervisor. `tests/api/test_department_hiring.py::test_api_144` pins that.

**The invited person is notified** — `0041`, and they were not until then. The reason they could not
be was the schema: `notifications.recipient_membership_id` was `not null`, and somebody who has not
been hired here holds no membership to address. That column is nullable now and `notify_profile`
addresses the person, so a trigger on `service_applications` tells them. Their
`GET /worker/applications` screen is still the authoritative read; the notification is what makes
them look at it.

A **rejected** applicant is told too, for the same reason and by the same trigger. Waiting silently
was the worst of the three outcomes and until `0041` it was the only one with no message.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or not a manager of this department |
| 404 | `not_found` | No such service provider |
| 409 | `conflict` | Already invited, blacklisted here, or already a member of this community |
| 422 | `request_validation_error` | `serviceProviderId` missing, or `jobTitle` over 120 characters |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/departments/{departmentId}/applications/{applicationId}/decide`

Answer a pending application. **Requires `admin` or `manager`. The hire happens here.**

**Request** — `{ "decision": "accepted", "jobTitle": "Plumber", "note": null }`

`decision` is `accepted` or `rejected`. **`withdrawn` is deliberately not accepted here**: a manager
withdrawing an application instead of rejecting it would erase the record that they refused somebody.
Withdrawal belongs to the side that opened the negotiation and has its own route.

`jobTitle` is supplied *here* rather than at application time, because on an application nobody has
offered one yet — the manager names it at the moment they say yes.

**Always at rank `member`, and no shift.** `rank` and `shift` were removed from this request on
2026-08-11 — see `POST .../invitations` above for the ruling and why it needed no migration.

Three distinct refusals share the `409`: the row was **already decided** (two managers clicked
accept; the row is locked `for update` and the second one loses), the provider is **blacklisted**
(re-checked at the moment of hiring, not only at application), or they are **already a member** of
this community.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or the caller is not the side entitled to answer |
| 404 | `not_found` | No such application |
| 409 | `conflict` | Already decided, blacklisted, or already a member |
| 422 | `unknown_decision`, `request_validation_error` | A decision outside the two, or `jobTitle` over 120 characters |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/departments/{departmentId}/members/{staffId}/remove`

Take somebody off the roster and end their membership. **Requires `admin` or `manager`.**

**Request** — `{ "reason": "Contract ended." }`

**Deactivates, never deletes.** Complaints record staff by name, so removing the row would turn every
past assignment into an unexplained string — the rule `0019` A7 already committed to for typed roster
names, applied to hired people too. Ending the membership is what removes their access; the row is
what keeps the history readable.

**They may apply again**, which is the whole difference between this and `POST .../blacklist`.

**Refused with a `409` while anything is still booked in their name** (`0043`). This route stays the
one-click answer for the ordinary case — a name typed into the department form by mistake, somebody
never dispatched — and everybody else goes through
[a departure](#post-apiv1departmentsdepartmentiddepartures), which is what `openCommitmentCount` on
the roster row is for. The guard lives in the function every removal path funnels through, including
the bar, so **no path removes somebody holding work**.

**A `POST` and not a `DELETE`, for two reasons.** Nothing is deleted, so the verb would describe
something that does not happen. And `reason` is a note one person writes about another that reaches
them in a notification: a `DELETE` cannot carry a body, and the alternative — a query parameter —
would put it in every access log between the browser and the database.

**Removing a supervisor re-stamps their live work** (`20260821200000`, product ruling 2, 2026-08-21).
`work_orders.supervisor_membership_id` is the address five notification kinds are delivered to —
`work_order.no_candidates`, `work_order.resident_accepted` / `_declined`, `work_order.accepted`,
`work_order.completed` and `work_order.failed` — and until 2026-08-21 nothing re-pointed it. After
the removal those messages went on being written to the departed person's ended membership, where
`notifications_read_own` then hid them: the department's live jobs reported their progress into a
mailbox nobody could open.

Every live work order (anything not `completed`, `cancelled` or `failed`) in **this department**
whose supervisor was the removed person is now re-pointed at the least-loaded remaining active
supervisor, or failing that at the department's manager, or — if there is neither — left exactly as
it is, because a wrong address is worse than a stale one. This happens in an `after update` trigger
on `staff_assignments`, so it covers this route, an immediate departure approval, the timekeeper's
dated removal, a blacklist, **and** an admin flipping `status` straight through PostgREST. Nothing
about the response changes and no request field controls it.

**Residents and workers never see the change**, by construction rather than by suppression: no
resident-facing or worker-facing read has ever returned a supervisor's identity.

**When the removed person was the department's last supervisor**, the department's manager and the
community's admins receive one `department.supervision_uncovered` notification — *"You are covering
…'s complaint queue"* — linking to `/admin/complaints` (rewritten to `/manager/complaints` for a
manager reader by `portalUrl.js`). It fires once, on the edge, and only for `service` departments: a
security department's manager lands in `/security-manager`, which has no complaints screen. The
standing half of the same fact is a banner on the manager's Complaints screen while the department
has no active supervisor. **No new workspace exists behind either** — `can_manage_department`
implies `can_supervise_department` (`0036`), so the manager's screens already exceed the
supervisor's.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or not a manager of this department |
| 404 | `not_found` | No such roster entry |
| 409 | `conflict` | They still hold jobs or shifts — open a departure and hand them over |
| 422 | `request_validation_error` | A reason over 500 characters |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/departments/{departmentId}/blacklist`

Remove, and bar from applying again. **Requires `admin` or `manager`.** `201 Created`.

**Request** — `{ "serviceProviderId": "…", "reason": "Repeated no-shows." }`

**Community-wide, not department-wide**, even though a department id is what identifies the caller's
authority to do it. A community that will not have somebody back has decided that about the
community; letting them reapply to the department next door would make the decision meaningless.

**It is not `blacklisted_residents`.** That table is keyed on a profile and is enforced inside
`search_joinable_communities`, so reusing it would bar this person from *living* here as a side
effect. A plumber a community will not hire has not been refused a flat.

Three things happen in order: every active roster row they hold in this community is removed, every
pending negotiation is rejected, and the bar is recorded. A bar that left them still working here
would not be one.

`reason` is required and stored, because whoever eventually decides whether to revoke it needs to
know what it was for. The row carries `revokedAt`, so this is reversible.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or not a manager of this department |
| 404 | `not_found` | No such department |
| 422 | `request_validation_error`, `missing_value` | No reason, or one under 3 characters |
| 500 | `internal_error` | Unhandled |

### 18.7 Leaving — a dated request the manager decides

Backed by `0043` and reworked by `0045`. Ten operations, counting the three employee-management
reads below.

**A departure used to be one statement.** `remove_department_member` set the roster row inactive,
ended the membership, and said nothing about the work that person was holding — which does not go
away. A `work_order_assignments` row with `status = 'accepted'` survived untouched: still pointing
at tomorrow's slot, still counted as somebody's load by the dispatch sweep, still rendering on the
resident's complaint as *someone is coming*. Nobody was coming, and the membership that would have
carried the reminder had just ended, so the one person who could have said so had been logged out.
The same hole was open on the gate: `security_shifts` kept pointing at a guard who no longer worked
there, and the rota read as covered.

**So a departure is a state a person is in**, not an event that happens to them — and since
`0045` that state has a **date**. The worker asks to leave immediately or on a day
(`requestedEffectiveAt`); until the manager decides, they keep working, but no new work in this
community whose slot starts on or after that day reaches them — and an undated (immediate) request
freezes the engine against them entirely. The manager approves **at the requested date or a later
one at their discretion** (`effectiveAt`), or rejects.

> **What this overturns.** `0043` refused approval with a `409` while anything was booked in the
> leaver's name — *hand everything over first, then approve*. **The product owner overturned that
> on 2026-08-10**: the decision whether and when somebody leaves is the manager's, and on approval
> the leaver's booked work from the effective date onward is **released back to the dispatch pool
> at a queue priority just below urgent** for reassignment by the ordinary mechanics. Work before
> the date stays with the leaver; a timekeeper (`dispatch_tasks`, kind `departure_removal`) removes
> them at the date, and from approval until then the engine gives them nothing new at all. The
> per-item `reassign` hand-over survives as a tool a supervisor may use before the decision; it is
> no longer a precondition of it. The gate itself survives in one place: the direct
> `POST .../members/{staffId}/remove`, which has no decision record and no release step, still
> refuses while work is booked.

**Four statuses and no `handover`** — `pending` \| `approved` \| `rejected` \| `cancelled`.
`approved` with a future `effectiveAt` is *leaving, still on the roster*; the roster view carries
`departureStatus` and `departureEffectiveAt` so a tile can say "leaving Friday". Two counts ride on
every departure: `openCommitmentCount` (everything booked in their name, dateless — informational
since the ruling) and `conflictCount` (items from the effective date onward, plus unscheduled ones
— what approval releases and what the coverage check examines).

#### What counts as outstanding, and the filter that is deliberately absent

Two kinds: `work_order_assignments` in `offered` or `accepted` whose work order is not `completed`,
`cancelled` or `failed`; and `security_shifts` in `scheduled` or `active`. Both, because the
instruction was *the same applies for all servicemen regardless of department* — a departure that
counted only jobs would approve every security departure on the spot.

**Neither is filtered to the future.** A scheduled job whose slot was yesterday and which nobody
closed is exactly what a departing worker leaves behind, and hiding it would let the departure be
approved while that job still sat in their name. The count answers *what does this person still
hold*, not *what is still in the future*. A manager who thinks a stale item should simply die has
[`POST /work-orders/{id}/cancel`](#post-apiv1work-ordersworkorderidcancel) already.

#### The freeze is the part that is easy to miss — and it is time-aware now

Opening a departure bars the dispatch engine **immediately, for the work the leave would strand**:
an undated request bars everything (the `0043` behaviour); a dated one bars slots on or after the
date *plus unscheduled work*, which can land anywhere; an approved departure awaiting its date bars
everything. `departure_bars_work(staff, slot_start)` (`0045`) is the single predicate, wired into
`dispatch_candidates`, `security_shift_candidates` and two `before insert or update` triggers —
whose column lists include the slot columns, so an update that moves a booking past the barrier
without touching its status is caught too. No other writer — a supervisor assigning by hand, a
worker accepting an offer that predates their own resignation — can put barred work into a
departing person's name.

#### `POST /api/v1/worker/communities/{staffId}/departure`

Ask the department's manager to release you, immediately or on a date. **Requires an authenticated
service provider.** `201`.

**Request** — `{ "reason": "Moving cities.", "effectiveAt": "2026-09-01T00:00:00Z" }`. Omit
`effectiveAt` to ask to leave immediately; a past date is a `422` — immediate is spelled by
omission, not by yesterday.

**Response** — a `StaffDeparture`:

```json
{
  "id": "…", "communityId": "…", "departmentId": "…", "departmentName": "Plumbing",
  "staffAssignmentId": "…", "serviceProviderId": "…", "displayName": "Ravi Kumar",
  "rank": "member", "jobTitle": "Plumber", "initiatedBy": "worker", "status": "pending",
  "reason": "Moving cities.", "requestedEffectiveAt": "2026-09-01T00:00:00Z", "effectiveAt": null,
  "decisionNote": null, "decidedAt": null,
  "openCommitmentCount": 3, "conflictCount": 2, "createdAt": "…", "updatedAt": "…"
}
```

**Addressed by roster row, not by community.** A service person hired by three societies is leaving
exactly one of them and nothing in the session says which; deriving it from a default membership
would resign them from whichever sorted first.

**`initiatedBy` is `worker` whenever the row is the caller's own**, even when that caller also
manages the department. Who is leaving decides this, not what else they are allowed to do.

**The department's managers *and its supervisors* are notified.** Supervisors are notified because
they are the people who will do the reassigning — and no existing helper could reach them, because a
supervisor is a **rank on a roster row** (D3) rather than a membership role. `0043` adds
`notify_department_leadership` for exactly that audience.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or that roster row is not yours |
| 404 | `not_found` | Not registered as a service provider, or no such roster entry |
| 409 | `conflict` | A departure is already open on that row, or the row is no longer active |
| 422 | `request_validation_error` | A reason over 500 characters, or a leave date in the past |
| 500 | `internal_error` | Unhandled |

#### `DELETE /api/v1/worker/communities/{staffId}/departure`

Withdraw the request and lift the freeze. **Requires an authenticated service provider.**

**Response** — `{ "message": "Request withdrawn." }`

**Keyed on the roster row rather than the departure id**, because the screen calling this is showing
a community card and not a request: making cancel carry an id would mean it needed a read that
request did not.

**Withdrawing something that is not open is a `404`, not a reassuring `200`.** A success here would
tell a provider their request was withdrawn when the manager had already approved it — and the next
screen they see is the one that no longer lists the community.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or that roster row is not yours |
| 404 | `not_found` | No open request on that row |
| 409 | `conflict` | Already decided between the read and the write |
| 500 | `internal_error` | Unhandled |

### Leadership provisioning — the other way into a department

Everything above this heading is about a service person who registered themselves and negotiated
their way onto a roster. The three endpoints below are about somebody who did neither.

> **The ruling.** *"There is no registration process for the manager or supervisor. The manager is
> created by the admin and the OAuth goes through based on the manager email that is given in the
> creation process. The supervisor is either created by the admin or the manager… The servicemen (of
> technician rank in the hierarchy) are the only ones in the whole service section who have a
> registration process of their own."*

So the service section has two ways in, and they are deliberately asymmetric:

| | Servicemen | Leadership |
|---|---|---|
| Who initiates | The person | An admin, or a manager for a supervisor |
| Registration | `POST /service-providers` | **None** |
| Negotiation | `service_applications` — apply or be invited, then a decision | **None** |
| Admitted when | A manager accepts | They sign in with the address that was typed |
| Rank | `member` | `manager` or `supervisor` |

**Nothing is mailed.** The email is not a delivery address, it is the **matching key**: whoever signs
in with it is admitted at that rank. `claim_staff_invitations` (`staff_provisioning`) runs inside
`GET /auth/session`, on the path that has already established the caller has no membership, and
writes the `community_memberships` row and the `staff_assignments` row in one transaction.

**The membership role is derived at sign-in, not stored** — the same derivation
`decide_service_application` does:

| `rank` | department `kind` | membership role | lands in |
|---|---|---|---|
| `manager` | `service` | `manager` | `/manager` |
| `manager` | `security` | `manager` | `/security-manager` |
| `supervisor` | `service` | `worker` | `/worker` |
| `supervisor` | `security` | `security` | `/security-manager` |

Deriving late means a department that changes kind between the invitation and the sign-in cannot mint
a membership pointing at the wrong portal.

**The trade-off, stated rather than softened.** Email alone is one factor: whoever controls that
mailbox at first sign-in becomes the manager of that department. There is no code to intercept and no
link to forward, so the exposure is narrower than a mailed token — but it is real, and the admin
typing the address correctly is the only check. The resident invite's mandatory token is
**untouched**; leadership has its own table for exactly that reason. See
`docs/design/STAFF_PROVISIONING_DESIGN.md`.

##### Who may hold leadership — two rulings, 2026-08-21

> 1. **Leadership is invite-only and never from the marketplace pool.** A supervisor or a manager is
>    never a freelancer and is never picked from servicemen. A profile holding a `service_providers`
>    row may not hold a `manager` or `supervisor` roster row, and a profile holding an active
>    leadership posting is refused marketplace registration.
> 2. **Leadership is exclusive to one community.** At most one active leadership posting per person
>    across every community. Technicians are unaffected — they may serve several. Being invited to a
>    different community *after* the previous posting has fully ended is legitimate and works.

Both are enforced in Postgres by `20260821140000_leadership_exclusivity.sql`, in triggers on
`staff_assignments` and `service_providers` rather than in each writer, so no API path can route
around them. Three endpoints surface them, and they surface them differently because they run in
different places:

| Entry point | Behaviour | Code |
|---|---|---|
| `POST …/staff-invitations`, `PATCH …/staff-invitations/{id}` | **Refused, loudly.** An admin is at a screen | `409 leadership_marketplace_conflict` / `409 leadership_already_held` |
| `GET /auth/session` (the claim) | **Skipped, silently, and marked.** The invitation stays `pending` and gains `blockedReason` | No error — the session read succeeds |
| `POST /service-providers` | **Refused, loudly.** The registration form renders `error.message` | `409 leadership_marketplace_conflict` |

**An address with no profile behind it is not checked at invite time, and cannot be.** That is the
ordinary case for leadership — the person has never signed in — so the two rules are asked again at
the claim, where the profile finally exists.

**Why the claim does not raise.** `claim_staff_invitations` runs inside `GET /auth/session`, on the
service client, on every membership-less session read, and `auth_service._claim_staff_invitations`
swallows whatever it raises — deliberately, because claiming is an enhancement to a session that is
already valid. So a refusal spelled as an exception would not refuse *that* invitation, it would
abandon the whole call, including any legitimate invitation later in the same loop, silently, behind
a screen that looks fine. Instead the offending invitation is skipped, kept `pending` (the situation
is not terminal — the person may leave the other community tomorrow, and both `PATCH` and `DELETE`
still apply to it), stamped with `blockedReason`/`blockedAt`, and **both parties are notified** on the
transition: the department gets `staff_invitation.blocked`, and — since
`20260821170000_blocked_invitee_notice.sql`, 2026-08-21 — the invitee gets
`staff_invitation.not_applied`, addressed to their profile with no community and no link. §3.5 has
the approved wording and the reasoning behind both choices. **The session read itself is
unaffected**: the caller gets their session, and lands wherever their own identity entitles them to —
the worker portal for a registered provider, the account page for anyone else.

**Why the invitee is told at all, given that the department is.** The department's copy is an
operational record — it is what turns "the supervisor we created never arrived" into a sentence an
administrator can act on. It does nothing for the person sitting in front of the screen where nothing
happened, and that person is the only one who can act on half of it: a registered provider's remedy
is to ask for a different address, and a sitting leader's is simply to wait until their current
posting ends, at which point the invitation applies itself on the next sign-in. Neither sentence is
reachable from any other surface they can see.

##### Removal severs access — ruling 3, 2026-08-21

> *"Once a supervisor/manager is removed from a community and later invited to a different one, they
> must not be able to see ANYTHING from the old community — engagements, complaints,
> conversations/messages, calendar, notifications, anything their portal reads."*

Removal already ended both halves of the posting: `remove_department_member` deactivates the
`staff_assignments` row **and** ends the `community_memberships` row in one transaction, so the
session read stops finding a membership and the claim path re-opens for the next invitation. What the
2026-08-21 audit changed is what a *stale* row still granted. No endpoint's request or response shape
moves; what moves is what comes back in them.

| Surface | Before | Now |
|---|---|---|
| `GET /auth/session` | Clean — `_active_memberships` already filtered on `status`/`ended_at` | unchanged |
| `GET /worker/snapshot` → `communities[]` | Clean — the roster read already asked for active memberships and active assignments | unchanged |
| `GET /departments/{id}/complaints` and the other supervisor complaint reads | Clean — `can_supervise_department` requires an active roster row *and* an active membership | unchanged |
| `GET /worker/jobs`, `/worker/jobs/{id}`, `/worker/calendar`, `/worker/unavailability`, `/worker/availability-rules` | **Leaked.** `is_own_staff_assignment` had no time condition, so a removed worker kept every job, every leave entry and every old work order forever | The predicate now requires the roster row to be active and, on the membership arm, the membership to be live |
| `GET /messages/threads`, `GET /messages/threads/{id}`, `GET /messages/threads/{id}/messages` | **Leaked.** The RLS policies were keyed on the participant columns alone, so a removed supervisor kept reading every community-A thread including the manager's side of their own departure | Both policies now also require an active membership in the thread's community |
| `GET /notifications` | **Leaked**, in the narrow sense: rows keyed to an ended membership stayed in the feed | Community-scoped rows for an ended membership are hidden; rows addressed to the person with no community stay |
| `GET /conversations/*` (the hiring thread) | Clean — supervisors were never participants; it is manager-or-provider only | unchanged |

The notifications change **overturns a decision `0041` recorded**, and names it: that file argued
that "a notification is a copy of something the person was already told, and every inbox in the world
retains those". Ruling 3 says otherwise for the community-scoped ones. The rule is applied uniformly
rather than only to leadership, because `remove_department_member` resets the roster row's `rank` to
`member`, so after a removal nothing in the database still says the person was a supervisor.

**One notification deliberately survives**: the *"you were taken off a roster"* message, which
`remove_department_member` writes *after* ending the membership. `notify_member` now files a message
addressed to an already-ended membership against the **person** and no community, so the one thing a
removed person most needs to read is the one thing the scoping does not hide.

#### `GET /api/v1/departments/{departmentId}/staff-invitations`

Managers and supervisors created here, whether or not they have arrived.
**Requires `admin` or `manager`**, and the RPC additionally requires that they manage *this*
department.

```json
[{ "id": "…", "departmentId": "…", "email": "manager@example.com", "name": "Priya Nair",
   "phone": "+919876543210", "rank": "manager", "jobTitle": "Department manager",
   "status": "pending", "claimedAt": null, "createdAt": "2026-08-11T09:00:00Z",
   "blockedReason": null, "blockedAt": null }]
```

**Claimed rows stay in the list.** An administrator needs to distinguish "still expected" from "has
been working for a month", and a list that dropped each person on arrival would look identical either
way.

`claimedAt` is null until their first sign-in. **A `pending` row that is weeks old is usually a
mistyped address, and this list is the only place that is visible** — nothing is delivered, so
nothing bounces and nothing errors.

**`blockedReason` (added 2026-08-21) is the other reason a row stays pending**, and it is the only
place *this reader* gets that answer. It is a sentence written for the administrator — *"They signed
in, but already manage or supervise another community"* — set when the invitee signed in and one of
the two exclusivity rulings turned them away. The invitee is told separately, in their own words and
their own feed (§3.5); the two sentences are deliberately not the same sentence, because one is a
report about somebody else and the other is an explanation to the person it happened to. `status` is still `pending`, on purpose: they may leave the
other community tomorrow, and both the correct and the withdraw verbs still apply. `blockedAt` is
when it was first set, and does not move on repeat sign-ins. Both are `null` on every ordinary
invitation, and `null` again once one is corrected onto a new address or finally claimed.

Optional `?status=pending|claimed|revoked`.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `role_not_permitted`, `HB403` | Not an admin or manager, or a manager of a different department |
| 404 | `not_found` | No such department |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/departments/{departmentId}/staff-invitations`

Create a manager or a supervisor. **Requires `admin` or `manager`.**

```json
{ "email": "manager@example.com", "name": "Priya Nair", "rank": "manager",
  "phone": "+919876543210", "jobTitle": "Department manager" }
```

`rank` is `manager` or `supervisor` — a closed set on the wire, not only in the database.
**`member` is refused**: that rank is reached solely by hiring a registered service provider, which
is the whole point of removing typed-in technicians from the department form.

**A manager may call this**, which is what lets a manager create a supervisor without being an
administrator. The predicate is `can_manage_department`, the same one that guards hiring.

The response is the row **read back**, not the request echoed: the RPC lowercases and trims the
address, and showing an administrator `Manager@Example.COM` while the database waits for
`manager@example.com` would hide the one thing that decides whether this works.

Returns **409** when that address already belongs to this community — the claim would fail on the
same check, so offering the invitation would be offering a dead end.

**Two more 409s since 2026-08-21**, and they carry their own codes rather than plain `conflict`,
because a client that must offer *"hire them at technician rank instead"* for one and *"wait until
they leave the other society"* for the other cannot tell them apart from a status:

| Code | Meaning |
|---|---|
| `leadership_marketplace_conflict` | That address belongs to a registered service professional. Leadership is never hired out of the marketplace (ruling 1) |
| `leadership_already_held` | That person already manages or supervises another community (ruling 2) |

Both are only reachable when the address already names a profile. An address nobody has signed in
with yet is accepted, and the same two rules are asked again at the claim.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid`, `role_not_permitted`, `HB403` | The CSRF pair, the membership role, or a manager of a different department |
| 404 | `not_found` | No such department |
| 409 | `conflict` | That address already belongs to this community |
| 409 | `leadership_marketplace_conflict` | That address is a registered service professional (ruling 1) |
| 409 | `leadership_already_held` | That person already leads another community (ruling 2) |
| 422 | `request_validation_error`, `check_violation`, `validation_error` | A rank outside the two, a blank name, or an address with no `@` — the last of which is the RPC's own `HB422`, which surfaced as a 500 until 2026-08-21 |
| 500 | `internal_error` | Unhandled |

#### `PATCH /api/v1/departments/{departmentId}/staff-invitations/{invitationId}`

Correct an unclaimed invitation. **Requires `admin` or `manager`.**

**This exists because of how the endpoint above fails.** Nothing is mailed, so a wrong address does
not bounce — the invitation simply sits `pending` and the person never arrives. The pending list is
what makes that visible; this is what the administrator does about it. The product owner's ruling on
2026-08-12 was to keep the single factor and make the mistake correctable rather than add a second
one.

```json
{ "email": "correct@example.com", "name": "Priya Nair", "rank": "supervisor",
  "phone": "+919876543210", "jobTitle": "Shift supervisor" }
```

**Every field is optional and omitted means unchanged**, so a form patching only the email cannot
blank the job title by not sending it. `phone` and `jobTitle` accept `""` to clear; `email`, `name`
and `rank` do not, because an invitation without them binds nothing, names nobody, or admits at no
rank.

`rank` is editable for the same reason `email` is — choosing *supervisor* when you meant *manager* is
a keyboard mistake of the same kind.

> **`departmentId` is not in the body, and its absence is load-bearing.** The department is what
> `can_manage_department` authorizes this call against, so allowing it to move would let the manager
> of one department mint staff into another without that department's manager being asked. Moving an
> invitation is revoke-and-reissue, under the authority of wherever it is going.

The response is the row **read back**, for the same reason as the create — and more pointedly, since
the purpose of this call is to answer *"is the address right now?"* rather than *"is it what I just
typed?"*.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid`, `role_not_permitted`, `HB403` | The CSRF pair, the membership role, or a manager of a different department |
| 404 | `not_found` | No such invitation |
| 409 | `conflict` | Already claimed, already withdrawn, the new address already belongs to this community, or it already has an open invitation |
| 409 | `leadership_marketplace_conflict` | The **new** address is a registered service professional (ruling 1) |
| 409 | `leadership_already_held` | The **new** address already leads another community (ruling 2) |
| 422 | `request_validation_error`, `check_violation`, `validation_error` | A rank outside the two, a blank name, or an address with no `@` |
| 500 | `internal_error` | Unhandled |

A successful correction **clears `blockedReason` and `blockedAt`**: a new address is a new question,
and leaving the old reason behind would leave the pending list accusing the wrong person.

#### `DELETE /api/v1/departments/{departmentId}/staff-invitations/{invitationId}`

Withdraw leadership that has not signed in yet. **Requires `admin` or `manager`.**

**Revoked, not deleted.** Who created an invitation and when is worth keeping — a mistyped address
that was noticed and withdrawn is exactly the history somebody will want later.

Returns **409** once it has been claimed. Removing somebody who has already started is a *departure*,
not a withdrawal, and has its own five endpoints below for the good reason that their work has to go
somewhere first.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid`, `role_not_permitted`, `HB403` | The CSRF pair, the membership role, or a manager of a different department |
| 404 | `not_found` | No such invitation |
| 409 | `conflict` | Already claimed — use the departure flow |
| 422 | `request_validation_error` | A malformed id |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/departments/{departmentId}/departures`

Who is leaving, and how much of their handover is left. **Requires `admin` or `manager`.**

Optional `?status=pending`. Unfiltered it returns settled departures too, newest first, which is
what makes it an answer to *why is this roster shorter than last month*.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `forbidden` | Not a manager of this department |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/departments/{departmentId}/departures/{departureId}`

One departure with its handover list. **Requires `admin` or `manager`.**

**Response** — a `StaffDeparture` plus `items`:

```json
{
  "id": "…", "status": "pending", "openCommitmentCount": 2,
  "items": [
    { "kind": "work_order", "itemId": "…", "referenceId": "…",
      "title": "Leaking tap in B-402", "startsAt": "…", "endsAt": "…", "status": "accepted" },
    { "kind": "security_shift", "itemId": "…", "referenceId": "…",
      "title": "Main gate", "startsAt": "…", "endsAt": "…", "status": "scheduled" }
  ]
}
```

**Jobs and shifts in one array**, told apart by `kind`, because a handover works through one list —
a department running both would otherwise need a screen that knew in advance which halves it was
going to get. `itemId` is what `POST .../reassign` takes; `referenceId` is the work order or the
post behind it, for display and linking only.

**Two database clients, in order, and the order is the authorisation.** The departure is read with
the caller's own client so RLS decides whether they may see it; only then is the item list read
through `staff_departure_items`, which is `service_role` only because it returns complaint titles.
Reading the items first would hand a stranger a department's work list on a guessed uuid.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `forbidden` | Not a manager of this department |
| 404 | `not_found` | No such departure, or the policy hides it |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/departments/{departmentId}/departures`

Start a departure for somebody on the roster, immediately or for a date. **Requires `admin` or
`manager`.** `201 Created`.

**Request** — `{ "staffId": "…", "reason": "Contract ending.", "effectiveAt": "2026-09-01T00:00:00Z" }`
(`effectiveAt` optional; omitted means immediately).

The manager's half of the same process a worker starts from their own portal, through the same RPC.
The person being moved off **is** notified; a worker opening their own is not, because they know.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or not a manager of this department |
| 404 | `not_found` | No such roster entry |
| 409 | `conflict` | A departure is already open, or the row is no longer active |
| 422 | `request_validation_error` | No `staffId`, a reason over 500 characters, or a past date |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/departments/{departmentId}/departures/{departureId}/reassign`

Hand one job or shift to somebody else. **Requires `admin`, `manager` or a supervisor of this
department.**

**Request** — `{ "kind": "work_order", "itemId": "…" }`, or with `"staffAssignmentId": "…"`.

**Omitting `staffAssignmentId` is the ordinary case** and means *take the best candidate the dispatch
ranking returns* — the same ranking auto-assignment uses, ordering by whoever already has a job in
this community that day, then by who is least loaded, then by who is nearest. Naming somebody is the
override for when a manager knows something the ranking does not. The API supplies no default,
because a default here would stop the handover following that ranking at all.

**The writer is `assign_work_order`, unchanged** — the same function the supervisor's own assign
button calls, so it withdraws the incumbent, books the successor, writes the `job_assigned` complaint
event, and notifies both the new worker and the resident. A second implementation beside it would be
a second definition of *book this person on this job*.

**A shift gets its own sweep.** `security_shift_candidates` applies the same exclusions and orders by
**fewest shifts that week, then nearest** — adjacency does not transfer, because a guard's shifts are
a rota rather than a route, and copying that sort key would be copying a clause that means nothing
here.

**An `offered` item is withdrawn rather than handed to a successor**, and the dispatch ping is
re-armed. Nobody had accepted it — the same question is sitting in four other workers' feeds — and
picking somebody would quietly turn a question into a booking that its holder was never asked about.

**A supervisor may do this; only a manager may approve the departure.** Handover is the work; ending
somebody's employment is a different decision.

`409` when nobody in the department is free for that slot. The job is **not** cancelled and the
departure is **not** approved anyway: the three real options — pick somebody, reschedule, cancel —
are endpoints that already exist, and a manager looking at one unmovable job is the right place for
this to stop.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or not a supervisor of this department |
| 404 | `not_found` | No such departure, or that item is not in their name |
| 409 | `conflict` | Nobody free for the slot, the departure is decided, or the successor is the person leaving |
| 422 | `request_validation_error`, `invalid_item_kind` | A `kind` that is neither `work_order` nor `security_shift` |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/departments/{departmentId}/departures/{departureId}/decide`

Approve — at the requested date or a later one — or reject. **Requires `admin` or `manager`.**

**Request** — `{ "decision": "approve" }`, optionally with
`"effectiveAt": "2026-09-15T00:00:00Z"` (the manager's later date; omitted means the requested one,
or now), or `{ "decision": "reject", "note": "…" }`.

**Approving picks the leave date and releases the conflicting work.** Booked items from the
effective date onward — plus unscheduled ones — go back to the dispatch pool at **queue priority 1,
just below urgent auto-assigns at 2**, so their reassignment starts today rather than on the
leaver's last morning. Work before the date stays with the leaver. An immediate approval releases
everything (stale past-dated items included) and removes them now; a dated one arms the timekeeper,
which releases whatever is still booked at the date and then removes them. *Until 2026-08-10 this
route refused approval with a `409` while anything was outstanding; that rule is overturned — a
product-owner ruling, recorded at the top of this subsection.*

**`approve` and `reject`, not `accepted` and `rejected`.** An application ends up in a *state*; a
departure is an *act* somebody performs. Sharing one vocabulary between the two would mean one of
them was named for the other's grammar.

Removal — now or at the date — runs through
[`remove_department_member`](#post-apiv1departmentsdepartmentidmembersstaffidremove) — the same
function the direct removal route calls, so there is **one removal path and not two**. The direct
route keeps its zero-commitment `409`; approval satisfies it by releasing first.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or not a manager of this department |
| 404 | `not_found` | No such departure |
| 409 | `conflict` | Already decided |
| 422 | `request_validation_error`, `invalid_decision` | A decision that is neither `approve` nor `reject` |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/departments/{departmentId}/staff/{staffId}`

One employee, as the employee page sees them. **Requires `admin` or `manager`.**

**Response** — the roster row the roster tab already renders (same view, same shape — one mapping,
not two that drift), plus `departure`: the pending request, or the approved one whose date has not
arrived, or null.

**`404` for a row in another department as much as for a missing one.** The path's department is a
scope: a URL that renders somebody from a different department is a link that lies, and the
schedule read below it would leak complaint titles across department lines.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `forbidden` | Not a manager anywhere |
| 404 | `not_found` | No such roster row in this department, or the policy hides it |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/departments/{departmentId}/staff/{staffId}/schedule`

One employee's jobs and shifts in a window. **Requires `admin` or `manager`.**

`?from=…&to=…` (ISO instants, both optional). Finished work is kept — a schedule shows what
happened, not only what looms — and **unscheduled jobs always appear**, whatever the window: work
with no slot can land anywhere, which is also why a departure treats it as conflicting. Items are
the handover shape (`kind`, `itemId`, `referenceId`, `title`, `startsAt`, `endsAt`, `status`).

Two clients, in order, the [`GET .../departures/{id}`](#get-apiv1departmentsdepartmentiddeparturesdepartureid)
authorisation: the roster row is read with the caller's own client first, so RLS decides whether
they may see this person at all.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `forbidden` | Not a manager anywhere |
| 404 | `not_found` | No such roster row in this department |
| 422 | `request_validation_error` | `from`/`to` that are not instants |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/departments/{departmentId}/departures/{departureId}/coverage`

The manager's match button. **Requires `admin` or `manager`.**

For every item the departure would strand — from the requested (or decided) effective date onward —
up to five people who could take it, ranked by the same sweep auto-assignment uses for jobs and by
lightest week for shifts:

```json
[
  { "kind": "work_order", "itemId": "…", "title": "Leaking tap in B-402",
    "startsAt": "…", "status": "accepted",
    "candidateCount": 2, "candidateNames": ["Asha Nair", "Vikram Shah"] },
  { "kind": "security_shift", "itemId": "…", "title": "Main gate",
    "startsAt": "…", "status": "scheduled",
    "candidateCount": 0, "candidateNames": [] }
]
```

**A `candidateCount` of zero is the answer "there are none"** — the doc's own words: *"If there are
none, it says so."* It renders as a statement, never as an error, because the decision screen needs
to show an unmovable item beside a movable one. An unscheduled job also counts zero: the sweep
cannot place work with no slot, and saying so beats pretending.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `forbidden` | Not a manager anywhere |
| 404 | `not_found` | No such departure, or the policy hides it |
| 500 | `internal_error` | Unhandled |

#### A bar ejects; it does not queue

`POST .../blacklist` is the deliberate exception, and it is worth stating beside the rule it breaks.
Somebody barred for misconduct keeping tomorrow's job until a supervisor has found five successors is
the opposite of what a bar is for. So a bar **releases** rather than hands over: it withdraws their
assignments, returns each work order to `offered` — which re-arms the dispatch ping by itself, so the
engine finds the replacements — cancels their future shifts, and tells the department's leadership
how many items moved. An orderly departure hands over; a bar ejects and the engine re-dispatches.

### What `0035` changed underneath the department screens

Three constraint corrections landed with this step and are visible through §8's endpoints.

**`rank` is now `manager` | `supervisor` | `member`.** It was `head` | `member`, while this document
§8 said `member` | `supervisor` | `head` and the ERD said `manager` | `supervisor` | `worker`.
`supervisor` was advertised in the schema docstring and rejected by the CHECK constraint — an
advertised rank no write could produce. **`head` remains the wire word** for the person who runs a
department; they hold `rank = 'manager'`.

**`departments.kind` is now `service` | `security`.** The CHECK allowed `internal` | `vendor` |
`hybrid`, which nothing writes; Python and this document both validated `service` | `security`. The
two sets did not intersect, so **every department create or update naming a kind was a `422`** until
`0035`. Only requests omitting `kind` worked, which is why it went unnoticed.

**`shift` is now `Day` | `Evening` | `Night` | `Full Day` | `Rotating`.** The CHECK allowed
`Morning` | `Evening` | `Night` | `Full Day` while Python validated `Day` | `Evening` | `Night`.
Three of the five words failed on one side or the other; only `Evening` and `Night` could be saved.

All three were free to correct in place because at the time no migration in this project had ever
been applied to a database. **That is no longer true** — everything through `0047` was verified
applied to the linked hosted project on 2026-08-11, so a correction now costs a forward migration
that repeats the whole function body. They were not free a second time.

### Conversations — the guard that is not in the router

Backed by migration `0038`. Four operations, and they are the only ones in this document with **no
role guard at all**. That is the design, not an omission.

The other two routers in this feature bracket the choice. A provider route is guarded by identity
alone, because the caller may belong to no community yet. A department route is guarded by `admin` or
`manager`, because every path under it names a department. A conversation is neither: it belongs to
**one department and one provider**, so participation is a property of the row rather than of the
caller's role, and there is no role a router could check that would answer it.

So the authorization lives next to the data. `is_conversation_participant` is called by both read
policies and both write functions, and it resolves to the same rule the rest of §18 uses —
`can_manage_department`, plus that provider. **Supervisors are deliberately outside it**: this is the
hiring conversation, and a supervisor's conversation is with a complainant about a job, which is
`complaint_comments` and §7.

The consequence is visible from outside, and it is the reason the status codes below are not
symmetric:

| The caller is not in the thread | The answer |
|---|---|
| `GET /conversations` | The thread is absent from the list |
| `GET /conversations/{id}` | `404`, not `403` |
| `POST /conversations/{id}/messages` | `403` |

**A hidden thread is a `404` on purpose.** A `403` would confirm the thread exists, which would make a
department's conversations with every other provider enumerable by walking ids and reading which
refusals came back. The write is a `403` because by then the caller has named a thread they can
already see.

**There is one thread per (department, provider) pair, forever.** A unique constraint, not a
convention — which is what lets `POST /conversations` be an upsert rather than a read-then-write.
Two managers opening the same chat in the same second get the same thread; without the constraint
they would get two, each holding half the conversation, and no query could put them back together.
The thread outlives every application in it, so a provider who applied, was rejected, and applied
again a year later is still talking in the same place.

**There are no notifications on this surface, and no unread counts.**
`notifications.recipient_membership_id` is not nullable, and the provider a manager most needs to
reach — an invited one, not yet hired — holds no membership in that community. A notification path
that worked for half the threads and silently not for the rest is worse than an honest one: the
conversation list is the delivery mechanism until the worker portal subscribes to events.

### `GET /api/v1/conversations`

Every thread the caller is part of, most recent first. **Requires authentication only.**
`?departmentId=` narrows it to one department.

```json
[
  {
    "id": "…", "communityId": "…", "communityName": "Green Meadows",
    "departmentId": "…", "departmentName": "Plumbing", "departmentKind": "service",
    "serviceProviderId": "…", "providerDisplayName": "Ravi Kumar",
    "providerHeadline": "Plumber, 12 years", "providerProfileId": "…",
    "lastMessageBody": "Can you start Monday?", "messageCount": 2,
    "lastMessageAt": "2026-08-09T10:00:00Z", "createdAt": "2026-08-09T09:00:00Z"
  }
]
```

**One inbox, not one per community.** A service person hired by three societies talks to three
departments and has one screen; omitting `departmentId` is what that screen calls.

**`departmentId` narrows and cannot widen.** It filters on top of what the policy already allows, so
a caller passing a department they have no part in gets an empty list rather than somebody else's
threads. That is why it is safe to take from the query string at all.

Both counterparts are named on every row rather than one "other side" field. Which of them is the
other side depends on who is asking, and the caller knows that better than this endpoint does.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/conversations`

Open the thread for a (department, provider) pair, or return the one that already exists.
**Requires authentication only.**

```json
{ "departmentId": "…", "serviceProviderId": "…" }
```

Responds `201` with the full thread — the same shape as the read below.

**Idempotent, and `201` either way.** This is what a "Message" button calls every time it is pressed,
rather than something a client must call once and remember. The response carries the messages because
a thread that already existed already has some, and the caller is about to render them.

Either side may open it: a manager sizing up a candidate, or a provider asking a question before
applying. **Anyone else gets a `403`** — creating the thread would otherwise be exactly how a stranger
joined it, which is why this is the one operation in the group that refuses by name instead of hiding.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or the caller is neither side of this pair |
| 404 | `not_found` | No such department, or no such service provider |
| 422 | `validation_error` | Missing ids |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/conversations/{conversationId}`

One thread and its messages, oldest first. **Requires authentication only.**

```json
{
  "conversation": { "id": "…", "departmentName": "Plumbing", "…": "…" },
  "messages": [
    {
      "id": "…", "conversationId": "…", "body": "Can you start Monday?",
      "authorSide": "department", "authorName": "Priya Nair",
      "authorProfileId": "…", "createdAt": "2026-08-09T10:00:00Z"
    }
  ]
}
```

**One response rather than two round trips**, because "a thread with no messages" and "a thread you
cannot see" are different answers — `200` with an empty list, and `404` — and splitting the read
would deliver them separately.

**`authorSide` is what a renderer switches on, not the author's id.** The two sides are stored in two
different tables — a membership and a provider row, because an invited provider holds no membership
in the community yet — and the view collapses that into one word so no client has to know it. Which
side a message is from is decided by the *thread*, so a provider who has since been hired, and who
now holds both a membership and a provider row, still reads as `provider` in their own thread.

Author names are resolved as they are now, not as they were when the message was written — the same
convention complaint comments use.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 404 | `not_found` | No such conversation, or the policy hides it |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/conversations/{conversationId}/messages`

Append one message. **Requires authentication only** — and participation, which the database checks.

```json
{ "body": "Monday works." }
```

Responds `201` with the stored message.

**The stored message, not the request.** The body is trimmed and the author's name and side are
resolved server-side, so a client that optimistically appended its own request to the list would be
showing something nobody else sees.

`body` is 1–4000 characters, matching the CHECK constraint exactly, so an empty or over-long message
is a `422` naming the field rather than a `422` naming a constraint.

**The other side is notified, and the two directions are addressed differently.** Added by `0041`;
`0038` shipped this endpoint silent, and the reason it stayed silent for three build steps is the
reason `0041` exists at all — the side most in need of telling is the provider, and a provider who
has not been hired holds no membership for a notification to be addressed to.

- **Provider → department:** `notify_member`, once for each active membership `can_manage_department`
  would accept — the community's admins, plus managers whose membership names that department or
  names no department at all.
- **Department → provider:** `notify_profile`, because that side may belong to no community.

Kind `conversation.message` both ways. Self-notification is impossible by construction rather than by
an exclusion argument: the author is one side of a two-sided thread and every recipient is the other.
The body carries a 140-character preview — a push that says only *"new message"* makes the reader
open the app to find out whether it mattered, and §5.3's absolute rule is about a *secret* in a
payload, which a message somebody typed to you is the opposite of.

**A profile-addressed notification produces no SSE frame**, because `sse_events.community_id` is
`not null` and a person with no membership has no community for the frame to belong to. The feed and
Web Push carry it, which is what the portal reads.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or the caller is not part of this thread |
| 404 | `not_found` | No such conversation |
| 422 | `validation_error` | Empty or over-long body |
| 500 | `internal_error` | Unhandled |

### Work orders — the state machine, before there is an engine to drive it

Backed by migration `0036`. Ten operations, and they are the first in this section that a **resident**
can feel: a complaint stops being a status and becomes a person arriving at an hour.

This un-parks the second half of `CONFLICT_RESOLUTIONS.md` **R16**, which said of `work_orders` and
`work_order_assignments` — *"tag each `Phase 2 — no v1 endpoint, no v1 RLS policy`, and build nothing
against them."* Both tables have existed since `0001` with no index, no policy, no function and no
Python reference. They are extended here rather than replaced, exactly as `0019` extended
`departments`.

#### What is deliberately absent

**No timers, no queue and no dispatcher — in `0036`.** They arrived immediately afterwards in
`0037`; see *The engine* below. `0036` deliberately shipped every transition and not one thing that
makes a transition happen on its own, because building half a queue would have left rows nothing
reads and a loop nothing services — the failure mode where a feature looks present and is not.

The consequence is the rule that step was arranged around, and it outlived the step: **every
transition the engine makes automatically is reachable by hand first.** A state machine whose only
exit from a state is a background job is one nobody can test, and the first time it wedges there is
no lever to pull. That is why `POST /work-orders/{id}/assign` accepts a job still in
`awaiting_resident` — it was the hand-operated form of the resident timeout before `0037` existed,
and it is now the manual override for the same transition.

**Three statuses are declared and not yet reachable.** `in_progress`, `completed` and `failed` are in
the CHECK constraint and nothing writes them: they belong to the worker, and the worker's endpoints
are the next step but one. They are declared now because the vocabulary is one line and splitting it
across two migrations would mean dropping and re-adding a constraint to add three words.

**No proposed-slots column and no slot-options table.** A supervisor proposes *one* time; the
resident confirms or declines; a different time is a reschedule, which the supervisor already has. No
`jsonb` list, no table holding two rows that are read once and discarded. If it later turns out
residents must choose between alternatives, that is a table then — and it will be a table with a
reason.

#### The lifecycle

| Status | Means | Reached by |
|---|---|---|
| `draft` | Raised, nothing proposed. The complaint is still a conversation. | `POST /complaints/{id}/work-orders` with no slot; a resident declining |
| `awaiting_resident` | A time was proposed for a job at somebody's home. | Creating or rescheduling with a slot, `subjectKind: resident` |
| `offered` | A time is settled and nobody holds the job. | The resident confirming; creating with a slot on a `facility` job |
| `scheduled` | Somebody is booked for that hour. | `POST /work-orders/{id}/assign` |
| `cancelled` | Called off, with a reason. Terminal. | `POST /work-orders/{id}/cancel` |
| `in_progress` · `completed` · `failed` | The worker's own transitions. | *Not yet reachable — see above* |

**A complaint may carry several work orders**, and that is why the assignment is not columns on
`complaints`. A failed visit is rescheduled and a reopened complaint goes to a different supervisor;
both are a second job. Assignee columns on `complaints` would have been the smaller change and would
also have closed `DECISIONS_NEEDED` **B2**, but one complaint could then only ever have one scheduled
visit — and the second visit is the one that matters.

#### One asymmetry, stated because it is the only one

The resident may **confirm** a proposed time and may **decline** it. They may not move it afterwards.
**The reschedule after assignment is the supervisor's alone**, because by then it is a change to two
people's days and only one of them is on that screen. A resident who needs a different hour says so
in a comment, and the supervisor reschedules.

#### The constraint this step exists to carry

```sql
exclude using gist (
  staff_assignment_id with =,
  tstzrange(scheduled_start_at, scheduled_end_at, '[)') with &&
) where (status = 'accepted' and scheduled_start_at is not null)
```

Drawn in `erd/homebandhu.dbml:614` since the ERD was written and never built. A person cannot be in
two places at once, and the schema is where that is said. It is the same construct `amenity_bookings`
has carried since the baseline — the same problem gets the same solution rather than a new one — and
it needs `btree_gist`, which is not a new requirement: `0001` both installs the extension and
declares an exclusion constraint that cannot exist without it.

**The `where` clause is the half worth reading twice.** It covers only `accepted` rows, because
`dispatch_ping_candidates` offers one slot to several workers and lets exactly one take it.
Constrain the offers and the dispatcher could only ever ask one person at a time, which defeats the
point of asking.

A double-booking is refused **twice**: `assign_work_order` checks for an overlap and raises `HB409`
naming the worker, and the constraint refuses it again if a concurrent request beat the check.
`23P01` now maps to `409` alongside `23505`, so a race and a mistake are indistinguishable to a
client — which is correct.

#### `POST /api/v1/complaints/{complaintId}/work-orders`

Supervisor triage. **Requires ADMIN, MANAGER, WORKER or SECURITY** — and, in the database, that you
supervise the department.

```json
{
  "departmentId": null,
  "skillId": null,
  "subjectKind": "resident",
  "locationText": "Flat B-402",
  "scheduledStartAt": "2026-08-12T10:00:00Z",
  "scheduledEndAt": "2026-08-12T11:00:00Z",
  "note": "Bringing a replacement cartridge."
}
```

Responds `201` with the work order.

**Omitting the slot is the other half of the fork, not an incomplete request.** Supplying a slot
proposes a visit — `awaiting_resident` plus a notification on a `resident` job, and straight to
`offered` on a `facility` one, because there is nobody whose door is being knocked on.

> **What a slotless raise means changed on 2026-08-23** (ruling F1,
> [`plans/RESIDENT_SETS_THE_TIME_SPEC.md`](plans/RESIDENT_SETS_THE_TIME_SPEC.md) G1). The raise form
> carries no date or time for anyone now, so this is the path every UI raise takes, and
> `create_work_order` decides from the subject:
>
> * **`resident`, no slot** — `awaiting_resident` with a **null slot** and `respondBy` set 24 hours
>   out. The resident is asked *when*, not *whether*, and answers with
>   [`POST /complaints/{id}/schedule-time`](#post-apiv1complaintscomplaintidschedule-time). Only their
>   answer puts the job on the open pile. Twenty-four hours of silence and the dispatcher books the
>   first hour a serviceman can take and assigns them.
> * **`facility`, no slot** — `draft`, unchanged, plus a `facility_auto_assign` task due now. Nobody
>   confirms a common-area job, so the system books it — after every urgent (`high`) resident job in
>   the department has somebody on it. The draft is claimable from the open-jobs board throughout.
>
> **The fields stay on this request** for backward compatibility, and a slotted raise keeps today's
> semantics exactly. **There is no new status**: pick-mode is `awaiting_resident` with a null slot and
> approve-mode is the same status with one, because `work_orders_status_check` is a closed list and a
> new word there costs a constraint rebuild on a live table.

**`departmentId` and `skillId` are both derived when omitted** — the department from the complaint,
the skill from the category. `0034` gave `complaint_categories` a `skill_id` precisely so nobody has
to answer *"which trade is this"* twice.

**`priority` is not a field.** A job's urgency *is* the complaint's urgency and is inherited at
creation. This also corrects a third vocabulary collision found in passing: `work_orders.priority`
defaulted to `normal` and was unconstrained, while `complaints.priority` is checked against `low` |
`medium` | `high`. Two value sets for one name is the same defect `0031` refused when it declined to
carry two *names* for one idea.

**The router guard is coarse and is meant to be.** A department supervisor holds a `worker` membership
with the `supervisor` *rank* on their roster row — rank is not role, and `0035` settled that
deliberately — so the only role filter that admits every legitimate caller admits every worker too.
The real check is `can_supervise_department(uuid)` inside Postgres, applied by every RPC on this
surface. An id arriving in a URL is never an authorization decision.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed; you do not supervise that department; or it belongs to another community |
| 404 | `not_found` | No such complaint |
| 409 | `conflict` | The complaint names no department and none was supplied |
| 422 | `validation_error` | Half a slot, an end before its start, or an unknown `subjectKind` |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/complaints/{complaintId}/work-orders`

Every job raised against one complaint, newest first. **Requires ADMIN, MANAGER, WORKER or SECURITY.**

A read rather than a derivation from the timeline. `complaint_events` records *that* a job was
scheduled, which is the right shape for a narrative and the wrong one for *"is anybody coming on
Tuesday"*.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `forbidden` | Not staff in any community |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/departments/{departmentId}/work-orders`

The department's queue. **Requires ADMIN, MANAGER, WORKER or SECURITY.**

Soonest first, with the unscheduled underneath — a draft with no time is not the most urgent thing on
the screen, it is the thing nobody has decided about yet. Filter with `?status=awaiting_resident` for
the jobs waiting on somebody else, or `?status=draft` for the ones waiting on you.

The filter narrows on top of the policy and never decides visibility: a supervisor asking for another
department's queue gets an empty list from `can_read_work_order`, not somebody else's work.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `forbidden` | Not staff in any community |
| 422 | `validation_error` | Over-long `status` |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/work-orders/{workOrderId}`

One job with its assignment history. **Requires ADMIN, MANAGER, WORKER or SECURITY.**

```json
{
  "id": "…",
  "status": "scheduled",
  "priority": "medium",
  "subjectKind": "resident",
  "complaintTitle": "Kitchen tap leaking",
  "departmentName": "Plumbing",
  "skillName": "Plumber",
  "locationText": "Flat B-402",
  "scheduledStartAt": "2026-08-12T10:00:00Z",
  "scheduledEndAt": "2026-08-12T11:00:00Z",
  "respondBy": null,
  "assigneeName": "Ravi Kumar",
  "staffAssignmentId": "…",
  "assignments": [
    { "id": "…", "status": "accepted",  "workerName": "Ravi Kumar", "isAutoAssigned": false },
    { "id": "…", "status": "withdrawn", "workerName": "Anil Das",   "isAutoAssigned": false }
  ]
}
```

**`assignments` is a history, not a holder.** Withdrawn and declined rows stay, because *"we sent Ravi
and he could not get in, so we sent Anil"* is the question a supervisor actually asks. The current
holder is the top-level `assigneeName`, which is null while nobody has it.

**Four populations can read this, for four different reasons** — the community's admins, the
department's supervisors, the worker holding an assignment, and the resident whose complaint it
answers. That rule is `can_read_work_order` in `0036` §4, stated once and used by both RLS policies
and every endpoint. A job the policy hides is a **`404`, not a `403`**, for the same reason a hidden
conversation is: refusals must not be enumerable.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `forbidden` | Not staff in any community |
| 404 | `not_found` | No such work order, or the policy hides it |
| 500 | `internal_error` | Unhandled |

#### `PATCH /api/v1/work-orders/{workOrderId}`

Edit what the job is. **Requires ADMIN, MANAGER, WORKER or SECURITY.**

```json
{ "skillId": "…", "subjectKind": "facility", "locationText": "Basement pump room", "priority": "high" }
```

**Not the time and not the state.** Those have their own routes because each carries a rule and a
notification — a reschedule moves a worker's booking and tells two people, a cancellation frees a
slot — and a general-purpose `PATCH` is precisely the shape that skips them. The request model has no
field for either, so sending one changes nothing rather than failing loudly, which is the behaviour a
client can rely on.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or you do not supervise that department |
| 404 | `not_found` | No such work order |
| 409 | `conflict` | The job is completed or cancelled |
| 422 | `validation_error` | Unknown `subjectKind` or `priority` |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/work-orders/{workOrderId}/assign`

Book somebody, and book their hour. **Requires ADMIN, MANAGER, WORKER or SECURITY.**

```json
{
  "staffAssignmentId": "…",
  "scheduledStartAt": "2026-08-12T10:00:00Z",
  "scheduledEndAt": "2026-08-12T11:00:00Z",
  "force": false
}
```

Responds `200` with the job and its assignment history.

**`force` — added 2026-08-22, amendment 2 ruling A4.** Optional, defaults to `false`, and `false` is
the offer flow described below byte for byte. `true` is the supervisor's explicit **override of the
consent model**: it calls `force_assign_work_order` instead, which writes an `is_forced` assignment
straight to `accepted` — the worker cannot decline it, and their card already hides the button for a
forced row — and then does what the dispatch engine's own `dispatch_force_assign` does when every
candidate has declined a critical job: the `job_assigned` and `job_force_assigned` timeline entries,
the worker's notification, the staff notice, and the resident being told somebody is coming.

It is a field on the existing request rather than a route of its own because it is the same request —
*this person, on this job, at this hour* — answering one further question: may they say no. Its
refusals are this route's, unchanged, including the double-booking `409` **by name**: forcing
overrides the worker's consent, not physics.

**Writes an `accepted` assignment, not an offer.** A supervisor naming a person is a decision, not a
question; the offer-and-wait path belongs to `0037`. Until that exists, this is also the manual form
of it.

**The slot is optional and defaults to the job's own.** Sending one assigns and reschedules in a
single write, which is the common case. What is *not* allowed is assigning a job that has no time at
all: a booking with no hour is a booking the exclusion constraint cannot see, because the constraint
is partial on `scheduled_start_at is not null`. That is a `409` — *"Schedule this job before
assigning it."*

**Any previous acceptance is withdrawn, not deleted.** One holder at a time, and the record of who
was booked and unbooked survives.

This is the `409` **this step exists to produce**. `0036` refuses a double-booking by name —
*"Ravi Kumar is already booked during that time."* — and the constraint refuses it again underneath.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or you do not supervise that department |
| 404 | `not_found` | No such work order, or no such roster entry |
| 409 | `conflict` | Already booked across that slot · not on this roster · the job has no time yet · the job is closed |
| 422 | `validation_error` | A backwards slot |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/work-orders/{workOrderId}/reschedule`

Move the visit. **Requires ADMIN, MANAGER, WORKER or SECURITY.**

```json
{ "scheduledStartAt": "…", "scheduledEndAt": "…", "note": "Resident asked for the afternoon." }
```

Both ends are required — this is not a partial edit, because the assignment's range moves with the
job and a range needs two ends.

**Where it lands depends on whether anybody holds it.** A job already assigned stays `scheduled` and
the resident is *told*; sending it back to `awaiting_resident` would strand a booked worker on an
answer that may never come. A job nobody holds returns to `awaiting_resident` on a `resident` job —
the resident agreed to a different hour, so they are asked again — or to `offered` on a `facility`
one.

The accepted assignment moving is what re-checks the overlap constraint: putting a booked worker onto
an hour they already have is the same double-booking as assigning them there in the first place.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or you do not supervise that department |
| 404 | `not_found` | No such work order |
| 409 | `conflict` | The job is closed, or the worker is booked across the new time |
| 422 | `validation_error` | A missing or backwards slot |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/work-orders/{workOrderId}/cancel`

Call the job off. **Requires ADMIN, MANAGER, WORKER or SECURITY.**

```json
{ "reason": "Resident is away until the 20th." }
```

Terminal, **and it takes the assignment with it**. A cancelled job that left an accepted assignment
standing would block an hour in a worker's calendar for work nobody is going to do — the kind of bug
that surfaces as *"the dispatcher says everyone is busy"*.

`reason` is required and reaches both the worker and the resident in a notification. A cancellation
nobody can explain is the one that produces the phone call this feature exists to prevent.

**A `POST` and not a `DELETE`**, for the two reasons `POST .../remove` gives in §18's hiring
subsection: nothing is deleted, and `DELETE` cannot carry a reason that must not travel in a query
string.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or you do not supervise that department |
| 404 | `not_found` | No such work order |
| 409 | `conflict` | The job is already completed or cancelled |
| 422 | `validation_error` | Missing or too-short `reason` |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/complaints/{complaintId}/schedule-request`

The visit proposed for my complaint. **Requires the resident capability** — the `resident` role, or an
active `unit_residencies` row on any membership (§7.2). Until 2026-08-20 this was the `resident` role
alone, which refused an administrator the answer to a question about their own flat.

```json
{
  "workOrderId": "…",
  "complaintId": "…",
  "status": "awaiting_resident",
  "departmentName": "Plumbing",
  "skillName": "Plumber",
  "locationText": "Flat B-402",
  "scheduledStartAt": "2026-08-12T10:00:00Z",
  "scheduledEndAt": "2026-08-12T11:00:00Z",
  "respondBy": "2026-08-11T10:00:00Z",
  "awaitingResponse": true,
  "mode": "approve",
  "assigneeName": null
}
```

**`mode` says which question is being asked**, and it arrived with ruling F1 on 2026-08-23.
`approve` — the association proposed an hour, answer it with `POST …/schedule`. `pick` — nobody has
chosen one, `scheduledStartAt` and `scheduledEndAt` are `null`, and the hour is the resident's to set
with [`POST …/schedule-time`](#post-apiv1complaintscomplaintidschedule-time). Both are
`awaiting_resident`: the slot is the discriminator, because the status vocabulary is a closed CHECK.
The derivation is made **once, here**, rather than on every screen that renders the card — a client
that got it wrong would show two buttons where a time picker belongs. `approve` is sent even when
nothing is being asked at all, so a reader never has to branch on `null`.

**Not only the visits awaiting an answer.** A resident who has already confirmed still needs to see
the time and, once somebody is booked, the name — and a screen that had to call a second endpoint for
that would show the confirmation blink out of existence the moment they pressed the button.
`awaitingResponse` is what tells the screen which of the two it is looking at.

**This returns the newest *live* job**, not simply the newest. A complaint may carry several over its
life, and returning the newest would let a cancelled retry hide the visit that replaced it.

`respondBy` is when the association stops waiting and schedules anyway. It is populated the moment a
time is proposed, so the deadline is visible from the first screen rather than arriving as a surprise.

**A narrower projection than `GET /work-orders/{id}` on purpose.** It carries when, where and who; it
does not carry the supervisor's membership id, the skill routing or the failed-attempt count, which
are the association's business *about* the resident rather than theirs.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `community_role_required` | No `resident` role and no active residency in this community (§7.2) |
| 404 | `schedule_request_not_found` | No live job — nothing proposed, or everything proposed was cancelled |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/complaints/{complaintId}/schedule`

Confirm or decline a proposed visit. **Requires the resident capability** (§7.2).

```json
{ "response": "confirmed", "note": null }
```

Responds `200` with the re-read `ScheduleRequest`, so a screen sees the answer land rather than
assuming it.

**Neither resident route takes a work-order id.** A resident should not have to have read one to
answer a question that was put to them, and an endpoint that accepted one would have to decide what
happens when it names a different complaint's job. Resolving the job from the complaint makes that
question unaskable.

**Resident-only, matching the precedent §14 set** for reopening and confirming a resolution: not
because an admin could not press the button, but because this is the resident's verdict about their
own home, and an admin answering for them is a record that says something untrue. The database
refuses it too — `respond_to_work_order_schedule` checks `is_own_membership` against whoever raised
the complaint — so the role guard is the early, clear error rather than the boundary.

> **"Resident-only" means the capability, not the role, since 2026-08-20** (§7.2). The paragraph
> above is unchanged in intent and was being enforced too narrowly: an administrator who owns a flat
> *is* the resident of that flat, has one membership row saying `admin`, and was refused the answer
> to a visit proposed to their own home. `is_own_membership` in the RPC is what actually keeps one
> person from answering for another, and it never depended on the role.

**Declining is not a counter-proposal**, and clears the time with it: leaving a declined slot on the
row would leave a calendar entry for a visit nobody agreed to. Either way the supervisor who proposed
it is notified *directly* rather than the whole admin list — they asked the question, and they are the
one who has to act on the answer.

**You may answer once.** Once the job has left `awaiting_resident` — you confirmed, or the supervisor
assigned somebody rather than keep waiting — this is a `409`.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or the visit was not proposed to you |
| 404 | `schedule_request_not_found` | No live job on this complaint |
| 409 | `conflict` | The visit is no longer waiting on you |
| 422 | `validation_error` | `response` was not `confirmed` or `declined` |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/complaints/{complaintId}/schedule-time`

Pick the time for a visit to my home. **Requires the resident capability** (§7.2). Added 2026-08-23
under ruling F1.

```json
{ "startAt": "2026-09-01T09:00:00Z", "endAt": "2026-09-01T11:00:00Z" }
```

Responds `200` with the re-read `ScheduleRequest`, so a screen sees the booking land rather than
assuming it. Both ends are required: a half slot silently disables
`work_order_assignments_no_overlap`, which is checked on `(start, end)` and does nothing when start is
null.

**The association stopped guessing an hour for somebody else's home.** A resident-subject job now
reaches the resident as a *request to pick* — a dashboard request, the way a hiring application
reaches a manager — and their answer is the hour itself. Setting it moves the job to `offered`, which
is the open pile, and notifies the supervisor who raised it.

**There is no decline here** (ruling F3). Pick-mode was never a proposal, so there is nothing to
refuse; the decline stays on `POST …/schedule`, which answers a supervisor's proposal. Silence is
answered instead: twenty-four hours after the raise the dispatcher finds the first hour a serviceman
can take, books it and assigns them, and both the resident and the worker are notified. If nobody is
free within a fourteen-day horizon the job returns to the open-jobs board and the supervisor is told.

**The two write routes refuse each other's jobs, deliberately.** A job the association gave an hour
is a `409` here — *"The association proposed this visit's time — answer that instead."* — and a job
with no hour cannot be `confirmed`. Sending the wrong one is a mistake with a sentence rather than a
silent overwrite of somebody else's intention.

**Neither resident route takes a work-order id**, this one included: the job is resolved from the
complaint, newest live one, so naming somebody else's is not expressible rather than merely refused.
`resident_set_work_order_schedule` checks `is_own_membership` against whoever raised the complaint,
which is what actually keeps one person from booking in another's name.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or this visit is not yours to schedule |
| 404 | `schedule_request_not_found` | No live job on this complaint |
| 409 | `conflict` | Nothing is waiting on you; the association proposed the time; or the hour is in the past |
| 422 | `validation_error` | A missing end, or an end before its start |
| 500 | `internal_error` | Unhandled |

#### The timeline learns five words, and no migration was needed

`complaint_events.event_type` is `text` with **no CHECK constraint** (`0001`:70), so `job_created`,
`job_scheduled`, `job_declined`, `job_assigned` and `job_cancelled` were added by teaching
`_EVENT_LABELS` and `_event_message` in `resident_complaints_service.py` and nowhere else. The
existing nine event types live in the same two places.

That is why there is no `work_order_events` table: it would need its own view, its own renderer and
its own RLS, and would split one complaint's story across two timelines.

### The engine — `0037`, and why it adds no endpoints

`0037_dispatch_engine.sql` is the only migration in this feature that contributes **zero
operations** to the API. It has no router, no service and no schema module, and that is what it is:
a table of due times, one trigger, and four functions that Postgres runs on its own.

`dispatch_tasks` holds every future action the engine intends to take, one row each — which makes
the whole of its behaviour inspectable with a single `select`, and means a restart loses nothing.
`app/core/dispatcher.py` claims what is due every fifteen seconds and calls `fire_dispatch_task`;
**Python owns only *when***. Every decision — who is free, who gets the offer, what the resident is
told — happens in SQL, because every notification in this product is written inside the transaction
that caused it and a dispatcher deciding things in Python would have to give that up.

Four kinds of task, and since `0039` all four have handlers:

| Kind | Armed when | What it does |
|---|---|---|
| `resident_timeout` | a visit is proposed for a home | Proceeds with the visit and tells the resident. **Does not close the complaint** |
| `ping` | a job reaches `offered` | Offers it to the best few candidates, then arms `auto_assign` for 30 minutes out |
| `auto_assign` | a `high` priority job reaches `offered`, or 30 minutes after a ping | Books the top candidate outright and tells both sides |
| `failed_visit_escalation` | a worker reports a failed visit — two hours later | Tells the department's manager, or the community's admins where there is no manager |

The escalation's idempotency check is the one worth reading, because it is **not** a status check. A
supervisor answering a failed visit raises a *new* work order rather than editing the failed one, so
the failed one stays `failed` for good and a status check would escalate it again on every
redelivery. What it checks instead is whether a newer work order exists on the same complaint — if
one does, a human has already dealt with it.

**Nothing enqueues a task by hand.** One `after insert or update` trigger on `work_orders` keeps the
queue in agreement with the status: `awaiting_resident` arms the timeout, `offered` arms the ping or
the auto-assign, `failed` closes everything and arms the escalation, and *anything else closes every
open task on the job*. That last clause is why
`cancel_work_order` did not have to learn what a dispatch task is, and why a future write path
cannot forget to arm one.

**It is at-least-once, which is the reverse of what push chose.** `app/core/push.py` marks a
notification sent *before* sending it, so a crash loses a buzz rather than repeating one — right for
something that vibrates a phone at 3am, wrong here, because a dropped `resident_timeout` is a
complaint left waiting forever with nobody coming. So the claim takes a five-minute lease, a task can
fire twice, and every firing function re-reads the job and returns without writing if the world has
already moved on.

Two simplifications are worth naming because the source document asks for something else. Ordering
candidates *"within 1 km of an adjacent job"* becomes **"already has a job in this community that
day"** — no work order carries usable coordinates, and inside one complex every job is a two-minute
walk. And a resident who never answers has their **visit go ahead**, not their complaint
auto-resolved: closing a complaint the resident never saw is a product decision, not one a background
job should make quietly at 2am.

The sweep also excludes anybody who has **declined this particular job**. Without that, the ordinary
sequence produces the worst outcome the engine can produce: five workers are pinged, one declines,
thirty minutes later the auto-assign asks for the single best candidate — and the decliner is still
in the set, still ranks first on adjacency and load, and finds the job booked in their name.

### The worker's portal — `0039`, and why none of it has a role guard

Sixteen operations *(fourteen until 2026-08-23, when the open-jobs board added its read and its
claim)*, and the notable thing about all of them is the guard: **authenticated only,
with no membership requirement** — the same as registration and hiring, but here it is a correction
rather than a convenience.

`require_membership_role("worker", "security")` reads the role off the caller's *default*
membership. This is the one surface in the product that is deliberately cross-community: a plumber
hired by three societies and living in a fourth has a default membership of `resident`, and that
guard would refuse them their own job list — silently, and only for the people the feature exists
for. Widening it to *any* worker membership would still refuse a department manager who is on a
roster and has been offered a job.

The question a guard would be reaching for is *does this caller hold this assignment*, which is not
a question about roles at all. It has one implementation — `is_own_staff_assignment` in `0036` — and
the three views and eight functions behind these routes all use it. **No route here takes a worker
id, a provider id or a community id**, so there is nothing a caller could send that would widen what
comes back.

That is also why every refusal on this surface is a `404` rather than a `403`. A job the caller holds
no assignment on does not exist as far as these endpoints are concerned; a `403` would confirm that
the id is real.

#### `GET /api/v1/worker/snapshot`

Everything the worker dashboard renders, in one call. **Requires authentication only.**

```json
{ "provider": { "id": "…", "displayName": "Ravi Kumar", "isAvailable": true, … },
  "communities": [ { "staffAssignmentId": "…", "communityName": "Green Meadows", … } ],
  "pendingOffers": [ { "assignmentId": "…", "complaintTitle": "Leaking tap", … } ],
  "today": [ … ], "nextJob": { … }, "openJobCount": 3,
  "isAvailable": true, "unreadNotifications": 4,
  "generatedAt": "2026-08-10T18:02:11Z" }
```

**A null `provider` is not an error, it is the empty state.** A caller who has never registered gets
a snapshot with nothing in it rather than a `404`, and a registered caller employed nowhere gets an
empty `communities` — so the dashboard decides between *show the registration form*, *show the
community search* and *show the week* from one response instead of interpreting two failures.
`GET /service-providers/me` still `404`s, because there the question being asked is different.

**`communities` is populated independently of `provider`, and the pair `provider: null` plus a
non-empty `communities` is an ordinary answer — it is department leadership.** `provider` answers
*do you have a marketplace profile*; `communities` answers *does anybody employ you*. For a
marketplace professional those two rise and fall together, which is why until 2026-08-21 this
endpoint returned an empty snapshot the moment there was no provider row. For a manager or a
supervisor they do not: `claim_staff_invitations` (`20260812090200` §4) writes a
`community_memberships` row and a `staff_assignments` row keyed on the **membership**, and no
`service_providers` row at all. There is no registration process for leadership — an administrator
types a name and an email — so there never will be one.

The consequence for a client: **decide the registration form on `provider` *and* `communities[].rank`,
never on `provider` alone.** A caller holding an active engagement ranked `manager` or `supervisor`
must not be sent to the marketplace registration form; they were hired into a department and nobody
will ever match them by distance or trade. Technician-rank (`member`) engagements and callers with
no engagement at all keep the form — coordinates and skills are precisely how those people are
found. `rank` is the only place the rank appears in any session-shaped response: nothing on
`GET /auth/session` carries one.

The two reads behind `communities` are chosen by the same question. A caller with a provider row
gets `service_engagement_overview` (provider-keyed, and it carries the open departure on each row);
a caller without one gets the membership-keyed read, which carries no `departure` because both
worker-side departure verbs require a provider row and so can never produce one. `GET
/worker/communities` is unchanged and still `404`s an unregistered caller: there the difference
between *you have not registered* and *nobody has hired you* is the whole point of the endpoint.

`today` and `nextJob` answer different questions and both are needed: at six in the evening today's
list is history, and what a worker wants then is tomorrow morning.

`unreadNotifications` counts across **every** community the caller works in. It is the one place a
user can see the multi-community seam this feature added to `app/api/deps.py`.

Sequential reads, so `generatedAt` is when the payload was assembled rather than when any part of it
was true — the same honesty `GET /resident/snapshot` prints about itself.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/worker/jobs`

Every offer and booking the caller holds, soonest first. **Requires authentication only.**

`?assignmentStatus=offered` · `?status=in_progress` · `?from=` · `?to=`

```json
[{ "assignmentId": "…", "workOrderId": "…", "assignmentStatus": "offered",
   "workOrderStatus": "offered", "priority": "medium", "subjectKind": "resident",
   "scheduledStartAt": "2026-08-11T09:00:00Z", "scheduledEndAt": "2026-08-11T10:00:00Z",
   "isAutoAssigned": false, "communityId": "…", "communityName": "Green Meadows",
   "departmentName": "Plumbing", "complaintTitle": "Leaking tap",
   "skillName": "Plumbing", "locationText": "B-204", "failedAttemptCount": 0 }]
```

**Two status filters, because there are two states and they answer different questions.**
`assignmentStatus` is *what is being asked of me*; `status` is *what is happening to the job*. A
withdrawn assignment on a job that went ahead without you is visible under the first and invisible
under the second, which is exactly the distinction a worker wondering "what happened to that one" is
making.

The `assignmentId` is the row's identity rather than the work order's: two workers can hold two
assignments on one job — one accepted, one withdrawn — and only one of them is the caller's.

Unscheduled rows sort **last**. An offer with no time yet is not the most urgent thing on the screen.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 422 | `validation_error` | A malformed `from` or `to` |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/worker/jobs/{workOrderId}`

One job, with what somebody needs in order to turn up at it. **Requires authentication only.**

Adds to the list shape: `complaintDescription`, `residentName`, `residentPhoneE164`,
`residentUnitCode`.

Those four are on this route and not on the list, deliberately. A worker on their way to a flat needs
all of them; a worker scrolling a month of finished jobs needs none, so the list query does not
select them. They are null on a `facility` job, where there is no door and nobody to meet.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 404 | `worker_job_not_found` | No such job, **or** not one of yours |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/worker/open-jobs`

The open-jobs board (product ruling 2026-08-23, `COMPLAINT_ENGINE_HANDOFF.md` §22): every unclaimed
job in every department where the caller holds an active roster row, trade-filtered, claimable now.
**Requires authentication only.** No parameters — identity is the whole query.

```json
[{ "workOrderId": "…", "complaintId": "…", "complaintTitle": "Leaking tap",
   "departmentId": "…", "departmentName": "Plumbing",
   "communityId": "…", "communityName": "Green Meadows",
   "skillId": "…", "skillName": "Plumbing", "priority": "medium",
   "subjectKind": "resident", "scheduledStartAt": null, "scheduledEndAt": null,
   "createdAt": "2026-08-22T09:00:00Z", "staffAssignmentId": "…" }]
```

**"Open" means uncommitted and unpromised** (adjudication D1, `docs/plans/OPEN_JOBS_BOARD_SPEC.md`):
`draft` or `offered` with **no live assignment**. A job with an offer out to somebody else is off the
board — the supervisor has an intention in flight, and a decline returns it. `awaiting_resident` is
off (a consent flow is in flight); `failed` is off in v1 (it has its own escalation task).

Keyed on the **work order**, not an assignment — the whole point of the board is that nobody holds
one yet, which is also why this read is a SECURITY DEFINER RPC rather than a view:
`can_read_work_order` correctly hides unheld jobs from workers. `staffAssignmentId` is the caller's
own roster row for that department, returned so a client never guesses which of a multi-community
worker's rows a claim would ride on.

A null slot is ruling C3, not missing data: an unscheduled job is on the board with a *time to be
set* marker and is claimable. The trade filter is `dispatch_candidates`' own clause, short-circuit
for provider-less roster rows included; the list is also exclusion-aware — a worker the complaint's
history rules out (a decline on it, a resident cancellation, a reopen after their completed visit)
does not see a job they cannot take.

An empty list is the ordinary answer, not an error: no roster rows, no matching trades, and nothing
waiting all look the same here, and `communities` on the snapshot distinguishes them for a client.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/worker/jobs/{workOrderId}/claim`

Take an unclaimed job straight off the board. **Requires authentication only.** No body.

**Instant, and first come first served** (ruling C2): the claim commits the worker on the spot with
accept-an-offer mechanics — an `accepted` assignment in the accept path's exact shape, the job moved
to `scheduled`, the resident notified with `work_order.assigned` exactly as on accept, the
supervisor with the new `work_order.claimed` kind (skipped when the claimer *is* that supervisor).
There is no approval step; the two-step press lives in the client, whose confirm wording carries
what the offer flow would have said.

Unlike `/accept` there is no offer underneath, so the RPC checks eligibility itself, under the same
row lock that settles the race: the caller holds an active roster row in the job's department, the
job's trade matches theirs by the engine's own rule, and the complaint's history does not exclude
them. The loser of a same-second double-claim reads a job that now holds a live assignment and is
told *somebody has already taken this job* — a sentence, not a constraint violation.

A job with no slot is claimed with no slot (C3): the overlap check is skipped because there is
nothing to overlap, the job still moves to `scheduled` — `force_assign_work_order` already writes
that shape, so `scheduled`+null-slot is established semantics — and the hour is set afterwards in
the supervisor's queue.

The timeline gains `job_assigned` with `claimed: true` in the payload rather than a new event word:
from the resident's side the fact is the same fact — somebody is now coming — and a new word costs a
constraint rebuild (runbook §19 rule).

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid` | Missing or mismatched CSRF pair |
| 403 | `forbidden` | Not on this department's roster, or the wrong trade |
| 404 | `not_found` | No such job |
| 409 | `conflict` | Somebody took it · the complaint's history rules you out · you are booked during its slot |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/worker/jobs/{workOrderId}/accept`

Take an offered job, and book the hour. **Requires authentication only.** No body.

**This is the race the whole feature has been building toward.** `dispatch_ping_candidates` offers
one job to five people on purpose, so two of them tapping this within the same second is the ordinary
case and not the edge one. The RPC locks the work order before it reads anything: the second caller
waits, re-reads a job that now says `scheduled`, and gets *somebody has already taken this job*
rather than an exclusion-constraint violation. `work_order_assignments_no_overlap` is still
underneath and still the guarantee; it is just not the thing anybody should have to read.

Accepting withdraws every other offer on the job — withdrawn, not deleted, so *"we asked five and
Anil took it"* survives. A second tap by the same worker is **not** a conflict: they already hold it,
which is the answer they were asking for.

It also retires the pending `auto_assign` task, through `0037`'s trigger and without this endpoint
naming the queue. That is why "somebody already took it" needs no second mechanism.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid` | Missing or mismatched CSRF pair |
| 404 | `worker_job_not_found` | No such job, or you were never offered it |
| 409 | `conflict` | Somebody took it · the offer is closed · you are already booked then |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/worker/jobs/{workOrderId}/decline`

Say no to an offer. **Requires authentication only.**

```json
{ "reason": "Already committed that morning" }
```

**Nothing else happens, and that is the design.** The job stays `offered`, the other four still hold
their offers, and the `auto_assign` armed alongside the ping is still due in thirty minutes. What
changes is that the dispatch sweep now excludes the caller **from this job** — a worker who declined
and was then auto-assigned the same job anyway is the outcome that would teach everybody to ignore
the button. The exclusion is scoped to the work order, not to the person: next week's job is still
theirs to be offered.

`reason` is optional here and required on `/unable`, and the asymmetry is the point. A worker who was
asked and is not free owes nobody an explanation; a worker who went and could not do the work is
reporting something the next person has to act on.

**An accepted job cannot be declined.** By then a resident has been told a name and an hour, and
getting out of it is `/unable` or a call to the supervisor — both of which tell somebody.

No `complaint_events` row is written. The resident does not need to learn that five people were asked
and one said no; the assignment history records it for the supervisor, who is who it is about.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid` | Missing or mismatched CSRF pair |
| 404 | `worker_job_not_found` | No such job, or you were never offered it |
| 409 | `conflict` | The offer is no longer open — including because you accepted it |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/worker/jobs/{workOrderId}/start`

The worker is on site. **Requires authentication only.** No body.

Moves the job to `in_progress`, writes a `job_started` event and notifies the resident. Idempotent: a
second tap on a job already in progress is a client that lost a response, not an error.

The notification is one D9's amendment permits — this is not a progress bar ticking, it is somebody
about to ring the doorbell.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid` | Missing or mismatched CSRF pair |
| 404 | `worker_job_not_found` | No such job, or you do not hold it |
| 409 | `conflict` | The job is not `scheduled` |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/worker/jobs/{workOrderId}/complete`

The work is done. **Requires authentication only.**

```json
{ "notes": "Replaced the washer and the cartridge." }
```

**The complaint stays open.** Those look like one act and are not: a resident whose tap still drips
after the visit has a complaint that is emphatically not resolved, and `POST
/complaints/{id}/resolution` already gives them the button that says so. A worker's word is evidence,
not a verdict.

Accepted from `scheduled` as well as `in_progress`, and not out of leniency: somebody who fixed the
tap and forgot to press *start* has done the work, and an API that refuses to record it teaches them
the app is lying about what happened.

`notes` reaches the resident in the notification, so it is written to be read by them rather than
filed.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid` | Missing or mismatched CSRF pair |
| 404 | `worker_job_not_found` | No such job, or you do not hold it |
| 409 | `conflict` | The job is cancelled, failed or already closed |
| 500 | `internal_error` | Unhandled |

#### `POST /api/v1/worker/jobs/{workOrderId}/unable`

The visit could not be completed. **Requires authentication only.**

```json
{ "reason": "Nobody was home at the agreed time" }
```

`reason` is **required**. *"Could not be done"* with nothing after it is the report that guarantees a
second wasted visit: nobody downstream can tell *nobody was home* from *the part is out of stock*,
and those need opposite responses. It reaches the resident too, because half the reasons a visit
fails are things only they can fix.

Counts the attempt (`failedAttemptCount`), closes the assignment as `failed`, and moves the job to
`failed` — which is what arms `failed_visit_escalation` two hours out. If nobody has raised a
replacement job by then, the department's manager is told, or the community's admins where the
department has no manager.

The answer to a failed visit is a **new** work order rather than an edit to this one, which is why
the job stays `failed` afterwards and why the escalation asks whether a newer job exists rather than
whether this one moved.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid` | Missing or mismatched CSRF pair |
| 404 | `worker_job_not_found` | No such job, or you do not hold it |
| 409 | `conflict` | The job is not `scheduled` or `in_progress` |
| 422 | `validation_error` | No reason, or one under three characters |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/worker/calendar`

Everything occupying the caller's time in one range, earliest first. **Requires authentication
only.** `?from=` and `?to=` are both **required**.

```json
[{ "kind": "job", "id": "assignment-id", "startsAt": "2026-08-12T09:00:00Z",
   "endsAt": "2026-08-12T10:00:00Z", "title": "Leaking tap", "subtitle": "B-204",
   "communityId": "…", "communityName": "Green Meadows",
   "workOrderId": "…", "status": "scheduled" },
 { "kind": "unavailable", "id": "block-id", "startsAt": "2026-08-13T00:00:00Z",
   "endsAt": "2026-08-15T00:00:00Z", "title": "Family wedding", "status": "provider" }]
```

**One list, two kinds.** A calendar that returned jobs and made the client fetch leave separately
would draw a worker as free on a day they had booked off, for as long as the second request took to
arrive. It is a merge in the service rather than a union in SQL, because both halves are already
views with their own definition of *mine* and a third statement that had to agree with both is one
more place for that to drift.

Both bounds are required. An unbounded calendar read is a request for everything a worker has ever
done, which no screen wants and which gets slower every month.

Declined offers and cancelled jobs are **not** here. A calendar is a claim about where somebody will
be, and a job they turned down is not one.

No colours. `communityId` is on every job entry and plan D15 derives the colour from a hash of it, so
the same society is the same colour on every device with nothing stored and nothing to configure.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 422 | `validation_error` | A missing or malformed bound |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/worker/unavailability` · `POST` · `DELETE /{blockId}`

The caller's own leave. **Requires authentication only.**

```json
{ "startsAt": "2026-08-13T00:00:00Z", "endsAt": "2026-08-15T00:00:00Z",
  "reason": "Family wedding" }
```

**Global across every community that employs the caller**, because a plumber on holiday is on
holiday in all four societies and asking them to say so four times is how three of them end up
booking him. The block is written against their `service_providers` record, which is the distinction
`0036` added the column for. `scope` says which kind a row is: `provider` for the caller's own,
`roster` for one recorded against a single roster row — the second exists for a name typed into the
departments form by an admin, and cannot be written here.

The `GET`'s range filter matches on **overlap**, not on start: a fortnight of leave that a one-week
calendar sits in the middle of belongs in that week's answer, and filtering `startsAt` against both
bounds would drop precisely the block that matters most.

**Overlapping blocks are allowed.** Two rows saying "not available" say the same thing rather than
contradicting each other — the dispatch sweep reads them with `not exists` — and refusing them would
refuse a perfectly sensible *away all week, especially Tuesday*.

Marking a window unavailable does **not** cancel work already accepted. A booking a resident has been
told about is not retracted by a calendar edit.

`DELETE /api/v1/worker/unavailability/{blockId}` answers `204`: unlike a withdrawn application, a
block that is gone leaves nothing on the screen it came from.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid` | Missing or mismatched CSRF pair (writes only) |
| 404 | `service_provider_not_found` | The caller has not registered |
| 404 | `not_found` | No such block, or not one of yours |
| 422 | `validation_error` | The block ends before it starts |
| 500 | `internal_error` | Unhandled |

#### `GET /api/v1/worker/availability-rules` · `PUT`

The week the caller is willing to work. **Requires authentication only.**

```json
{ "rules": [{ "weekday": 1, "startTime": "09:00:00", "endTime": "17:00:00",
              "effectiveFrom": "2026-08-01", "effectiveTo": null }] }
```

**An empty list means always available, not never.** That is how `dispatch_candidates` reads it, and
the opposite reading would make every newly hired worker invisible to the engine until somebody
filled in a form — the kind of failure nobody would diagnose. `weekday` is 0–6 with Sunday at 0,
matching Postgres `extract(dow ...)`, which is what the sweep compares against.

**A `PUT` of the whole set, not add and remove**, for the reason `PUT /service-providers/me/skills`
gives: the screen is a week with seven rows on it, and two tabs editing different days against a
delta API is a lost update nobody notices until somebody is booked on their day off.

The `GET` is not in the written plan and was added while building: a `PUT` of a whole set with no way
to read the current one is an editor that opens blank and silently erases whatever the person set
last week.

Changing the week does not re-check work already accepted. A commitment made on Tuesday is not undone
by deciding on Wednesday that Tuesdays are off.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid` | Missing or mismatched CSRF pair (`PUT` only) |
| 404 | `service_provider_not_found` | The caller has not registered |
| 422 | `validation_error` | A window that ends before it starts, or a weekday outside 0–6 |
| 500 | `internal_error` | Unhandled |

### The supervisor's dashboard — added 2026-08-22

Backed by `20260822120000_supervisor_triage.sql`. Two operations, and the interface between them and
the screen is frozen in [`plans/SUPERVISOR_TRIAGE_SPEC.md`](plans/SUPERVISOR_TRIAGE_SPEC.md) — the
backend and the frontend were built against that document in parallel, so a field renamed on either
side is a section that stops rendering rather than a compile error.

**Why the supervisor got a landing page at all.** `_portal_for` sends every service person to
`/worker`, and rank is not role (`0035`), so a supervisor and the technician they dispatch hold the
same `worker` membership and arrived at the same screen — a technician's day, which a supervisor
holds none of. The dashboard is four stacked sections: **new complaints** (with the High-priority
stack pinned on top), **taken up by you**, **assigned but not started**, and **being worked right
now**.

**Three facts the model could not state**, and the reason there is a migration under this rather than
only a query:

* nothing recorded that a supervisor had *picked a complaint up*, so "new" and "mine, not yet
  dispatched" were the same row — hence `complaints.taken_up_by_membership_id` + `taken_up_at`;
* nothing recorded when a worker pressed **Start**. `start_work_order` moved the status and let the
  instant fall into `updated_at`, which the next write overwrites — hence `work_orders.started_at`,
  which is what makes section 4 able to say *for how long*;
* re-stamping a departed supervisor's live work deliberately left no mark
  (§16 of the handoff), so the inheriting supervisor could not tell the work they chose from the work
  that arrived by somebody else's removal — hence `work_orders.supervision_inherited_at`, which is
  that ruling partially reversed and nothing else about the departure-continuity design changed.

**Take-up is triage ownership and never dispatch.** The 2026-08-21 ruling keeps complaints
department-pooled and `complaints.assigned_to_membership_id` dead, and this does not touch it: the
complaint still belongs to the department, and who is actually going is still a work-order
assignment. What take-up records is *who is looking at it*, so two supervisors do not both start
arranging the same visit.

#### `GET /api/v1/departments/{departmentId}/triage-snapshot`

The dashboard's four sections in one read, for the department's **supervisors and its manager** —
`can_supervise_department`, the same guard and the same posture as
`GET /departments/{departmentId}/complaints`.

```jsonc
{
  "departmentId": "…",
  "newComplaints":   [TriageComplaint],   // status open, nobody has taken it up
  "takenUp":         [TriageComplaint],   // taken up, no worker engaged yet
  "assignedPending": [TriageWorkOrder],   // a worker is engaged and has not started
  "inProgress":      [TriageWorkOrder]    // the worker pressed Start
}
```

**Bucketing is decided server-side and the client never re-derives it.** *Live* means a work order
whose status is not `completed`, `failed` or `cancelled`; *engaged* means a live work order with an
assignment in `offered` or `accepted`, or one whose status is `scheduled`. Those two definitions
appear exactly once, in `supervisor_triage_snapshot`. Four definitions that must agree are one
definition or they are four answers — and the one that drifts is always the one nobody is testing.

A taken-up complaint whose job becomes engaged moves into `assignedPending` **as its work order** and
leaves `takenUp`: the supervisor's question has changed from "who do I send" to "is Ravi going to turn
up", and a row that answered both would be in two places at once.

Every array is newest-first by `createdAt`. **The urgent stack is not sorted for here** — pinning High
above the rest is a layout, and a server that pre-pinned would be deciding one.

`TriageComplaint` carries `priority` and `status` in the **wire** vocabulary (`High`, `In Progress`),
translated through `app/domain/vocabularies.py` like every other complaint surface; the RPC returns
the stored words, because a `case` in SQL turning `high` into `High` would be a second copy of that
table in a language nobody would look in. `TriageWorkOrder.status` is passed through unmapped
(`draft`, `awaiting_resident`, `offered`, `scheduled`, `in_progress`), which is what `WorkOrder` has
always sent — different noun, different vocabulary.

Three fields exist for the "this is not as new as it looks" badges and all three ride on facts the
engine already recorded: `returnedToPoolAt` (a resident sent the work back), `reopenedCount`, and
`reroutedAt`. The last is **derived and not stored** — the newest `department_assigned` timeline event
naming this department as the destination. There is no column for it because a complaint can arrive
here more than once, and because automatic routing at raise time writes `raised` rather than
`department_assigned` and correctly is not a reroute. `TriageWorkOrder.inheritedAt` is the fourth
badge and is supervisor-only by construction: no resident-facing or worker-facing read has ever
returned a supervisor's identity.

**One call rather than the N+1 the triage screen makes today** — a department read followed by a
work-order read per complaint, which four sections would have multiplied by four.

| | |
|---|---|
| Guard | `admin`, `manager`, `worker`, `security` at the router; `can_supervise_department` in the RPC |
| Returns | `200` `TriageSnapshot` — four arrays, empty rather than absent |
| `403` | you do not supervise this department — a refusal and not an empty snapshot, because the two look identical on a screen |
| Errors | `401`, `403`, `404`, `500` |

#### `POST /api/v1/complaints/{complaintId}/take-up`

The supervisor saying *this one is mine to triage*. **No request body**, and none is read: the acting
supervisor is the session, and a body would be a place to name somebody else.

One transaction, three effects: it stamps `takenUpByMembershipId` and `takenUpAt`, moves the storage
status `open → acknowledged` — **and only from `open`**, because a complaint a worker has already
started is not walked backwards by a triage button — and writes a `taken_up` row on the timeline.

**Nobody is notified**, and that is a decision rather than an omission. A field changing with no
action attached is the passive change `ARCHITECTURE.md`'s rule exists to suppress; the resident learns
the same fact from the status their screen already renders as *In Progress*, re-snapshotted within an
SSE beat. `acknowledged` had exactly one writer before this — the worker-offer trigger in
`20260813102000` — and gains a second deliberately. The two cannot race: both move `open` and only
`open`, so whichever runs second finds nothing to do.

Taking up your own again is a **`200` no-op** — a double-clicked button is not an error worth a
message. Somebody else's is a `409` that **names them**, because "already taken up" with no name sends
a supervisor to ask around an office.

| | |
|---|---|
| Guard | `can_supervise_department` on the complaint's own department |
| Returns | `200` `{ "message": "Complaint taken up." }` |
| `409` | somebody else holds it (the message names them), or the complaint has no department yet — which is a conflict and not a `403`, because what is missing is the routing and not a permission |
| Errors | `401`, `403`, `404`, `409`, `500` |

### The supervisor's card actions — amendment 2, added 2026-08-22

Backed by `20260822170000_supervisor_actions.sql`, and frozen in the same spec
([`plans/SUPERVISOR_TRIAGE_SPEC.md`](plans/SUPERVISOR_TRIAGE_SPEC.md), *Amendment 2*) under four
product rulings taken the same day. Phase one gave the supervisor a screen that reads and one verb;
this is the rest of the verbs, plus the one correction to the snapshot they forced.

**The snapshot now returns five arrays**, and `openRequests` sits between `takenUp` and
`assignedPending`:

```jsonc
{
  "departmentId": "…",
  "newComplaints":   [TriageComplaint],   // open, not taken up, and no live job
  "takenUp":         [TriageComplaint],   // taken up, and no live job
  "openRequests":    [TriageWorkOrder],   // raised, live, nobody has committed
  "assignedPending": [TriageWorkOrder],   // a worker accepted, and has not started
  "inProgress":      [TriageWorkOrder]    // the worker pressed Start
}
```

**`engaged` became `committed`, and that is the whole of ruling A3.** A live work order is
*committed* when it has an `accepted` assignment **or** its status is `scheduled`; an offered job
nobody has answered is no longer counted, because "we have asked someone" and "someone is coming" are
different answers to the supervisor's question and only one of them needs chasing. The two complaint
sections now exclude **any** live work order rather than only an engaged one, so *furthest stage
wins*: a complaint appears exactly once across the five — as a complaint until a job exists, and as
that job afterwards.

`TriageWorkOrder` gains **`offeredToName`** (additive), the person a job is currently offered to and
waiting on. `assigneeName` now means the person who **accepted** and nothing else. Two fields because
they are two facts: one field carrying both would make an *Open job requests* card read *"Ravi is
coming"* about a job Ravi has not answered.

Three actions appear on **every** card in every section — a detail popup (the staff read below), a
chat, and an internal note — and the stage-specific ones are *Take up*, *Mark as resolved*, *Raise
priority* and *Assign*.

> **A sixth array arrived on 2026-08-23** with ruling F1
> ([`plans/RESIDENT_SETS_THE_TIME_SPEC.md`](plans/RESIDENT_SETS_THE_TIME_SPEC.md) G7):
> `awaitingResident` sits between `takenUp` and `openRequests`, rendered as **"Awaiting resident
> response"**, and carries the `TriageWorkOrder` rows whose status is `awaiting_resident` and which
> nobody has committed to.
>
> ```jsonc
> "awaitingResident": [TriageWorkOrder],  // the resident has been asked and has not answered
> "openRequests":     [TriageWorkOrder],  // draft or offered — now, and only these two
> ```
>
> **`openRequests` narrows in the same change**, and that half is the one that would go unnoticed: a
> job waiting on a resident is not something the supervisor can act on — they cannot pick the time and
> are not meant to — so listing it beside the work they *can* take up was showing them a queue that
> was not theirs. The split is the RPC's, like every other bucket. The row model is unchanged and the
> section is additive on the wire: a client that ignores the key sees exactly what it saw before,
> minus the rows that moved.

#### `POST /api/v1/complaints/{complaintId}/resolve`

The department saying the work is done. **No request body.** Guard: `can_supervise_department`.

One transaction. Every other **live** job on the complaint is called off — `draft`,
`awaiting_resident`, `offered`, `scheduled` — its `offered` and `accepted` assignment rows withdrawn
(never deleted), and every affected worker notified `job.cancelled` with the reason *"Complaint
resolved by the department"*. A worker holding an offer must not have to find out from an empty
queue.

**A job that is `in_progress` refuses the whole call.** Somebody is inside a resident's flat; the
honest answers are to let them finish or to cancel that visit, and both are somebody's deliberate act
rather than a side effect of this button. That is the `409` — *"Somebody is working on this right
now. Finish or cancel the running job first."*

It moves the complaint to `resolved` and **not** to `closed`. `closed` is what the *resident* says by
confirming with a rating, and the v0 aftermath is unchanged: confirm, reopen, the 48-hour reminder
and the 72-hour auto-close all hang off `resolved` and all still fire — the trigger that arms them
(`complaints_on_resolved`, `20260813104000`) watches the status this writes, which is also why this
endpoint does not write the `status_changed` timeline entry or the resident's notification itself.
One writer, said once.

| | |
|---|---|
| Returns | `200` `{ "message": "Complaint resolved." }` |
| `409` | a job is in progress · the complaint is already resolved, closed or cancelled · it has no department yet |
| Errors | `401`, `403`, `404`, `409`, `500` |

#### `POST /api/v1/complaints/{complaintId}/priority-raise`

`Low → Medium → High`, one step at a time, one direction only. **No request body.** Guard:
`can_supervise_department`. Responds `200` `{ "message": "Priority raised to High." }`.

**One way is the design.** A supervisor who could lower a priority could quietly un-escalate
something somebody else escalated — a different decision, worth its own verb and its own audit line.
At `High` there is nowhere further to go, and that is a `409` rather than a silent no-op: a
supervisor who pressed the button and saw nothing change would press it again.

**Priority is load-bearing, deliberately.** `high` is what arms the dispatch engine's automatic
force-assign when every candidate has declined, and what shortens the manual dispatch window from 24
hours to 2. The complaint's **live jobs move with it**, because a job's urgency *is* its complaint's
urgency — `create_work_order` never took a priority argument for exactly that reason.

The SLA deadline is **not** recomputed. `expectedResolutionAt` is a promise already made to the
resident, and moving it because the department reclassified the work would make a complaint overdue
for a reason the resident never saw.

Nobody is notified — a passive field change under `ARCHITECTURE.md`'s rule — but the timeline gains a
`priority_changed` entry the resident *does* read: *"The department raised the priority to High."*
That word is the one new `complaint_events` type in this amendment, and it cost a constraint rebuild;
see §20 of the migration runbook.

| | |
|---|---|
| Returns | `200` `{ "message": "Priority raised to Medium\|High." }` |
| `409` | already `High` · no department yet |
| Errors | `401`, `403`, `404`, `409`, `500` |

#### `POST /api/v1/complaints/{complaintId}/notes`

Body `{ "note": "…" }`, 1–2000 characters. Guard: `can_supervise_department`. Responds `201`.

A permanent note on the complaint's timeline **for staff and workers**. The resident does not see it:
the product owner's own scoping named those two populations and not them. It is carried by an
`internal: true` flag on the payload of the existing `note_added` event rather than by a new event
word — which would have cost a second constraint rebuild — so the admin's resident-visible *Update
from management* notes (`PATCH /complaints/{id}` with `updateNote`) carry no flag and are untouched.
`resident_complaints_service` drops the flagged ones from the resident's timeline; the staff detail
read below shows them with their author's name.

**Append-only.** No edit and no delete: a timeline that can be rewritten is not a record of what
happened.

| | |
|---|---|
| Returns | `201` `{ "message": "Note added." }` |
| `422` | an empty note, or one over 2000 characters |
| Errors | `401`, `403`, `404`, `409`, `422`, `500` |

#### `POST /api/v1/complaints/{complaintId}/chat`

Open — or get — the one chat thread about this complaint. **No request body.** Guard:
`can_supervise_department`. Responds `200` `{ "threadId": "…" }`.

A **real thread in the existing chat dock** (`dm_threads.kind = 'complaint'`, added by this
amendment's migration), not a comments panel: the resident reaches it from their ordinary thread list
and the department reaches it from the card, and both sides get the notifications, the unread counts
and the transcript the dock already has.

**One thread per complaint.** A second supervisor pressing the button joins the thread that exists
rather than forking one the resident would have to watch two of — which is why this is idempotent and
why the client calls it every time instead of remembering. Reading and writing it belong to the
raiser **and the department**: any supervisor of the complaint's department, not only whoever opened
it. The thread is seeded with a system line — *"The department opened this chat about '…'."*

**A `closed` or `cancelled` complaint locks the thread**: it still reads, and
`POST /messages/threads/{id}/messages` answers `409`, exactly as a finished job's channel does.
Unlike a job, a complaint can be **reopened**, and reopening unlocks it — the conversation the
resident was already having is the one they come back to.

`200` rather than `201`, because the common case is getting the thread that already exists; a status
code that alternated between the two would be describing the database's history rather than the
caller's request.

| | |
|---|---|
| Returns | `200` `{ "threadId": "…" }` |
| `409` | the complaint has no department, nobody to talk to, or is the caller's own |
| Errors | `401`, `403`, `404`, `409`, `500` |

#### `GET /api/v1/complaints/staff/complaints/{complaintId}` — guard widened 2026-08-22

The eye popup's read: the complaint and its whole timeline, internal notes included. **The router
guard dropped from `require_admin` to active membership.** That is not a widening of who may read it:
`staff_complaint_detail` has decided `is_community_admin(...) OR can_supervise_department(...)` inside
Postgres since it was written, and answers `HB404` — not a `403` — to everybody else, so a stranger
walking complaint ids still learns nothing. What `require_admin` was doing was refusing a
department's own supervisors at the door, before the rule that admits them could be asked.

| | |
|---|---|
| Guard | active membership at the router; `is_community_admin OR can_supervise_department` in the RPC |
| Returns | `200` `StaffComplaintDetail` |
| Errors | `401`, `403`, `404`, `500` |

### What is not here yet

**Nothing.** Gate operations — `0040`, renumbered from `0039` for the reason given at the top of this
section — landed on 2026-08-10 and are **§19**. The whole loop exists end to end: a complaint is
triaged into a job, the engine offers it, a worker takes it, starts it, and either finishes it or
says why they could not; and a guard, hired by the same machinery, works a roster and keeps the
registers.

**Thirty-six of these forty-five operations serve no user story**, and saying so is not modesty.
Registration serves nobody's story; hiring and conversations *enable* the stories this feature
eventually closes without serving any of them; a worker reading their own queue or their own leave
form is nobody's story either. The nine that do are the ones a resident can feel: proposing a visit,
assigning a person, moving or cancelling one, reading when somebody is coming, and — since `0039` —
a worker accepting, starting, finishing or failing the visit. All nine land on US-2.7 and US-2.8,
which are about lifecycle notifications and about knowing *who* is responsible and *when* to expect
action.

`POST .../assign` is where `DECISIONS_NEEDED` **B2** is finally answered: the assignee stops being a
formatted string and becomes a roster row. `POST /worker/jobs/{id}/accept` is where that answer stops
being a supervisor's guess about who was free and becomes the responsible person's own word.

The design is in [`design/SERVICE_OPERATIONS_DESIGN.md`](design/SERVICE_OPERATIONS_DESIGN.md); the
decision record and build order are in
[`plans/SERVICE_OPERATIONS_PLAN.md`](plans/SERVICE_OPERATIONS_PLAN.md); what exists in the branch
today is in
[`plans/SERVICE_OPERATIONS_PROGRESS.md`](plans/SERVICE_OPERATIONS_PROGRESS.md).

---

## 19. Security operations — the gate

Backed by migrations `0040` and `0047`. Twenty operations, and the surface that finally gives the
third department kind something to do.

`security` has been a `membership_role` since the baseline and a `departments.kind` since `0035`. A
guard is hired by the same RPC that hires a plumber, holds skills, books leave and appears on the
same calendar — §18's machinery, reused verbatim. What none of it describes is a guard's actual
work, because a shift is a post occupied for a window rather than a job dispatched to an address, and
a gate register is not a complaint.

**This section closes four stories that have read *Backend: None* since they were written** —
`US-3.3`, `US-3.4`, `US-3.5` and `US-3.6` — and finishes a fifth, `US-3.1`, which was not the plan.

### The guard is the opposite of §18's, and that is deliberate

`/worker/*` declares no role at all: a service person's surface is cross-community by construction,
so a role guard there would read the wrong one of a worker's four memberships.

A gate is the mirror image. **A register entry, a shift and an incident are each a fact about exactly
one society**, so this section goes back to the house shape — a role guard at the router, and a
community resolved from the caller's own membership rather than accepted from a request body. **No
route here takes a community id.**

One difference from the admin surface is worth naming. The guard is not
`require_membership_role("security", "admin", "manager")`, which reads the role off the caller's
*default* membership. A guard who lives in one society and works the barrier of another has a default
membership of `resident`, and that check would refuse them their own register. The dependency scans
the caller's memberships for one that holds a gate role instead. Its limit is real and stated rather
than hidden: **a guard employed by two societies gets the first of the two**, ordered by
`isDefaultCommunity`. There is no request field that could resolve that without becoming a community
id in a body.

Underneath, `0040` carries two permission levels rather than one:

| Predicate | Who | What it gates |
|---|---|---|
| `gate_community_for` | Any `security`, `admin` or `manager` membership | The registers, incidents, credential verification, the bundle, the reconcile |
| `gate_admin_community_for` | `admin` or `manager` — **or** a `security` membership whose roster row is ranked `manager` or `supervisor` | Posts and the shift roster |

Two rather than one, because the alternative is a system where every guard can rewrite the rota, and
the alternative to *that* is one where the security manager cannot log a tanker. The second predicate
is the first place `D3`'s rank-and-role split has to be honoured in code rather than described: a
security *manager* is a `security` membership with a rank, not a `manager` membership.

### `GET /api/v1/security/posts`

Every guard post in the caller's community, by name. **Requires `security`, `admin` or `manager`.**

```json
[{ "id": "…", "communityId": "…", "departmentId": "…", "name": "Main Gate",
   "locationText": "North entrance", "latitude": null, "longitude": null,
   "isActive": true, "createdAt": "…", "updatedAt": "…" }]
```

`includeInactive=true` adds the deactivated ones. **A post is deactivated and never deleted**,
because a register entry recorded two years ago still names it and `US-3.6` is a story about reading
records that old.

| Status | Code | Cause |
|---|---|---|
| 401 | `unauthorized` | Not signed in |
| 403 | `community_role_required` | You do not hold a gate role anywhere |

### `POST /api/v1/security/posts`

Create a post. **Requires a security manager, or an admin.**

```json
{ "name": "Basement Ramp", "locationText": "Level -1", "departmentId": "…" }
```

Answers `201` with the post read back. A live post name is unique per community — case- and
whitespace-insensitively, so *Main Gate* and *main gate* are one place.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not a security manager of this community |
| 409 | `conflict` | A live post already has that name here |
| 422 | `post_name_required` | No name was given |

### `PATCH /api/v1/security/posts/{postId}`

Rename, relocate or deactivate a post. **Requires a security manager, or an admin.**

Every field is optional and **an omitted field is left alone rather than blanked** — a form with six
fields and one change should not have to send the other five back. Answers `200` with the post.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not a security manager of this community |
| 404 | `not_found` | No such post in this community |

### `GET /api/v1/security/shifts`

The roster. **Requires `security`, `admin` or `manager`.**

```json
[{ "id": "…", "postId": "…", "postName": "Main Gate", "staffAssignmentId": "…",
   "guardName": "Ravi Kumar", "guardPhoneE164": "+91…", "guardJobTitle": "Gate Officer",
   "guardRank": "member", "startsAt": "…", "endsAt": "…", "status": "scheduled",
   "notes": null }]
```

`from` and `to` filter on **overlap** rather than on start. A night shift that began at 22:00
yesterday is the shift a guard on duty at 01:00 is looking at, and filtering by start alone would
drop exactly the row that matters. `status` and `postId` narrow further.

**`shiftId` is the filter for a caller who arrived from a notification.** `security_shift.assigned`
(`0043`) links the guard a shift was handed *to*, carrying that shift's id, and `0045` lets the
departure behind the handover be scheduled weeks out — so the row is routinely outside whatever
window the screen chose. Widening the window is not the answer: this list is capped at 200 rows
ordered by start, so a wider range on a busy gate can truncate away the very row that was asked for.
One id, one row, no window. An unknown id answers `200 []` and **not `404`** — the same answer as a
quiet fortnight, so this cannot be used to test whether a shift exists somewhere the caller cannot
see.

`guardRank` is the roster rank — `manager`, `supervisor` or `member` — and not the membership role.
`D3` made those separate axes and §8 already prints the rule.

### `POST /api/v1/security/shifts`

Put a guard on a post for a window. **Requires a security manager, or an admin.**

```json
{ "staffAssignmentId": "…", "startsAt": "2026-08-11T22:00:00Z",
  "endsAt": "2026-08-12T06:00:00Z", "postId": "…", "notes": "Handover at 06:00" }
```

**A guard cannot be in two places at once, and that is a GiST exclusion constraint rather than a
check in the application** — the same construct `work_order_assignments` carries and the baseline's
`amenity_bookings` has carried since `0001`. The overlap is refused *by name* first, so the answer is
*Ravi Kumar is already on a shift during that time* rather than a raw `23P01`.

The partial predicate differs from the work-order one and the difference is the point. Assignments
constrain only `accepted` rows, because the dispatcher offers one slot to five workers and one takes
it. Nobody offers a shift to five guards, so the predicate here is everything except `cancelled` — a
*completed* shift still occupied that evening, and a new one written over it is a rota error rather
than a historical curiosity.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not a security manager of this community |
| 404 | `not_found` | No such staff member or post in this community |
| 409 | `conflict` | That guard is already on a shift then |
| 422 | `validation_error` | The shift ends before it starts |

### `PATCH /api/v1/security/shifts/{shiftId}`

Move a shift, or start and end one. **Requires a security manager — except for the caller's own
shift.**

**A guard may send `status` alone for a shift that is theirs**, which is what *End Shift & Logout*
does — a control the security layout has offered since before this table existed. Any other field, or
anybody else's shift, is the security manager's. `0040` decides which of the two applies **from the
shape of the request** rather than from a flag the client sets, because a flag the client sets is a
flag the client can lie about.

`status` is `scheduled`, `active`, `completed`, `cancelled` or `missed`.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | Not your shift, and you do not run the roster |
| 404 | `not_found` | No such shift in this community |
| 422 | `unknown_shift_status` | Not one of the five |

### `GET /api/v1/security/roster`

The guards the shift form may offer. **Requires a security manager, or an admin.** Backed by
migration `0047`.

```json
[{ "staffAssignmentId": "…", "name": "Ravi Kumar", "phoneE164": "+919876543210",
   "jobTitle": "Gate Officer", "rank": "member", "shift": "Night" }]
```

**This endpoint exists because two permission models did not meet.** `POST /security/shifts` needs a
`staffAssignmentId`, and the person who fills that form in is usually a security *manager* — a
`security` membership whose roster rank is `manager` or `supervisor`, because `D3` made rank and role
separate axes. Every roster read this API had lived under §18's department-hiring surface, whose
guard is the *membership* role. So the one person the shift form was built for was the one person who
could not fetch the list of guards to put in it. `0047`'s function answers with the same predicate
the shift write already trusts.

**Deliberately narrower than what the shift RPC accepts.** `schedule_security_shift` will roster any
active staff row in the community — a name typed into the departments form with no membership behind
it is a valid guard. This picker lists only staff of departments whose `kind` is `security`, because
a shift form that offers the plumbing roster is a form that offers a mistake.

`rank` is the roster rank; `shift` is the preference label `0035` constrains (`Day`, `Evening`,
`Night`, `Full Day`, `Rotating`) and **not** a `security_shifts` row.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not a security manager of this community |

### `GET /api/v1/security/material-movements`

The inward/outward register. **Requires `security`, `admin` or `manager`.** `US-3.3`.

```json
[{ "id": "…", "direction": "inward", "description": "12 bags of cement",
   "quantity": 12, "unit": "bags", "isReturnable": false, "expectedReturnAt": null,
   "returnedAt": null, "carrierName": "Suresh", "vehicleNumber": "KL07AB1234",
   "unitId": null, "unitCode": null, "postName": "Main Gate",
   "recordedAt": "…", "isOutstanding": false, "isOverdue": false }]
```

`outstanding=true` is the report the returnable column exists for: **what went out and has not come
back.** `isOverdue` is that same fact past its expected return date. Both are derived in SQL rather
than stored, for the reason `isOverdue` on a complaint is — a stored flag needs somebody to flip it at
midnight and is wrong until they do.

`from`, `to` and `direction` narrow the range.

### `POST /api/v1/security/material-movements`

Write one entry into the register. **Requires `security`, `admin` or `manager`.** `US-3.3`.

```json
{ "direction": "outward", "description": "Ladder", "quantity": 1,
  "isReturnable": true, "expectedReturnAt": "2026-08-12T18:00:00Z",
  "carrierName": "Suresh", "vehicleNumber": "KL07AB1234", "postId": "…",
  "sourceClientId": "gate-1-000481" }
```

Answers `201` with the entry read back.

**`sourceClientId` makes this safe to retry.** A gate device that queued entries while disconnected
and then lost its connection again mid-upload can send the whole queue a second time: the id it
generated is unique per community, and a replay returns the original row rather than a conflict.

A return date on a non-returnable item is refused before the round trip. It is a contradiction that
would otherwise produce a *still out* report quietly disagreeing with itself.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not on duty in this community |
| 422 | `unknown_direction` | Not `inward` or `outward` |
| 422 | `not_returnable` | A return date on a non-returnable item |

### `POST /api/v1/security/material-movements/{movementId}/return`

The returnable item came back. **Requires `security`, `admin` or `manager`.** `US-3.3`.

```json
{ "returnedAt": "2026-08-12T17:40:00Z" }
```

Omit `returnedAt` for now. **Idempotent:** the second guard to press *returned* is telling the truth
and the row already says so, so it is a `200` with the recorded time rather than a conflict about
one.

| Status | Code | Cause |
|---|---|---|
| 404 | `not_found` | No such entry in this community |
| 409 | `conflict` | That entry was not recorded as returnable |

### `GET /api/v1/security/water-tankers`

The tanker log, newest arrival first. **Requires `security`, `admin` or `manager`.** `US-3.4`.

```json
[{ "id": "…", "supplierName": "Kerala Water Supply", "tankerNumber": "KL07TX4412",
   "volumeLitres": 12000, "driverName": "Manoj", "driverPhoneE164": "+91…",
   "arrivedAt": "…", "departedAt": null, "postName": "Main Gate", "isOnSite": true }]
```

`onSite=true` is *still here*; `from` and `to` bound the arrivals.

### `POST /api/v1/security/water-tankers`

Log a tanker at the gate. **Requires `security`, `admin` or `manager`.** `US-3.4`.

```json
{ "tankerNumber": "kl07tx4412", "supplierName": "Kerala Water Supply",
  "volumeLitres": 12000, "driverName": "Manoj", "sourceClientId": "gate-1-000482" }
```

Answers `201`. **The number is stored upper-cased**, because a plate written down by two guards on
two shifts is one vehicle and a report that splits it into two is the report nobody trusts.

`departedAt` may be sent now if the tanker has already left; the usual case is to omit it and `PATCH`
later. `sourceClientId` works exactly as it does on the material register.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not on duty in this community |
| 422 | `validation_error` | No tanker number |

### `PATCH /api/v1/security/water-tankers/{logId}`

Record the departure, or correct a mis-keyed volume. **Requires `security`, `admin` or `manager`.**
`US-3.4`.

```json
{ "departedAt": "2026-08-10T11:20:00Z", "volumeLitres": 11500 }
```

An omitted field is left alone. An auditable record needs both ends of the visit, which is the whole
reason this route exists rather than folding the departure into the arrival.

| Status | Code | Cause |
|---|---|---|
| 404 | `not_found` | No such entry in this community |
| 422 | `validation_error` | It cannot leave before it arrived |

### `GET /api/v1/security/incidents`

Incidents, most recent first. **Requires `security`, `admin` or `manager`.** `US-3.3`.

```json
[{ "id": "…", "category": "Fire alarm", "severity": "high", "status": "open",
   "summary": "Alarm on the third floor", "details": null, "locationText": "Block B",
   "postName": null, "occurredAt": "…", "resolvedAt": null,
   "reportedByName": "Ravi Kumar" }]
```

`status` and `severity` narrow; `from` and `to` bound `occurredAt`.

`category` is the display vocabulary — `Security concern`, `Medical emergency`, `Fire alarm`,
`Unauthorized access`, `Property damage`, `Other`. The column stores snake case and
[`vocabularies.py`](../backend/app/domain/vocabularies.py) holds the map, the same seam §7 uses for
comment visibility.

### `POST /api/v1/security/incidents`

File an incident. **Requires `security`, `admin` or `manager`.** `US-3.3`.

```json
{ "summary": "Alarm on the third floor", "category": "Fire alarm",
  "severity": "high", "details": "Cleared by 02:20, no evacuation",
  "locationText": "Block B", "occurredAt": "2026-08-10T02:00:00Z" }
```

Answers `201`. **This closes a real gap rather than adding a feature**: the form already exists on
the security dashboard and today appends an interpolated *string* to an in-memory activity feed,
which is the same defect `DECISIONS_NEEDED` **B2** names on the complaint assignee.

**`high` and `critical` notify the community's admins and managers; `low` and `medium` are a
record.** That line is where `ARCHITECTURE.md`'s notification rule lands here — a thing that happened
is not automatically a thing worth a push at 2 a.m.

An unrecognised category is a `422` naming the six rather than a silent fall back to `Other`, because
a typed category that quietly becomes *Other* is a report with a hole in it. `Other` is in the set on
purpose: a closed vocabulary with no escape hatch is a form people work around by picking the nearest
wrong option.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not on duty in this community |
| 422 | `unknown_incident_category` | Not one of the six |
| 422 | `unknown_severity` | Not `low`, `medium`, `high` or `critical` |

### `PATCH /api/v1/security/incidents/{incidentId}`

Acknowledge, re-grade or resolve an incident. **Requires `security`, `admin` or `manager`.**
`US-3.3`.

```json
{ "status": "resolved", "details": "Fault in the panel; contractor called" }
```

**Moving an incident back off `resolved` clears `resolvedAt`**, so the timestamp never outlives the
status that justified it.

| Status | Code | Cause |
|---|---|---|
| 404 | `not_found` | No such incident in this community |
| 422 | `unknown_incident_status` | Not `open`, `acknowledged` or `resolved` |

### `POST /api/v1/security/gate/verify`

Check a scanned QR or a typed security code, and act on it. **Requires `security`, `admin` or
`manager`.** `US-3.1`, `US-3.5`.

```json
{ "credential": "483920", "presentedAt": null }
```

```json
{ "verdict": "admitted", "detail": "Admitted. 1 of 2.", "passId": "…",
  "visitorName": "Anil", "guestCount": 2, "unitCode": "B-204",
  "residentName": "Asha Menon", "validFrom": "…", "validUntil": "…" }
```

**This is the half of `US-3.1` that was missing.** `0032` has minted and stored `codeHash` and
`passHash` since the visitor passes shipped, and until now nothing ever read one back — so a resident
could issue a pass and no gate could check it. §13 recorded the obligation; this discharges it.

**The credential is hashed before it leaves the API process.** The same `hash_secret` that minted the
code at creation, so the comparison is hash-to-hash the whole way down and the six digits a visitor
read off their phone never reach a query or a log. Sending either the code or the QR token works —
the gate should not have to tell the API which of the two it just read.

**A refusal is a `200` with a verdict, not a `4xx`.** The guard asked a question and got an answer;
making *that code is not recognised* an error status would split one act across the client's success
and failure paths. The `4xx` codes below are about the guard, not the visitor.

**A second scan admits the next guest, and the last one is the way out.** `guestCount` has been a
column since `0032` and nothing had ever read it — so the obvious first-in-second-out implementation
would have admitted one guest of a two-hundred-guest function and turned the rest away, which is
exactly the failure `US-3.1` describes. Once everybody named on the pass is inside, the next scan
checks the group out. That is why there is no separate check-out endpoint: at a barrier there is one
action, and it is *scan*.

| `verdict` | Means |
|---|---|
| `admitted` | Let them through. `detail` counts the group; the resident is notified |
| `departed` | Everybody was inside; now checked out |
| `refused` | Cancelled, rejected, not yet approved by the resident, or already closed |
| `not_yet_valid` | A real pass, but later |
| `expired` | The window has passed |
| `not_found` | No such code at this gate |

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not on duty in this community |
| 422 | `validation_error` | Nothing was presented |

### `GET /api/v1/security/offline-bundle`

The passes this gate may need while disconnected. **Requires `security`, `admin` or `manager`.**
`US-3.5`.

```json
{ "generatedAt": "…", "expiresAt": "…", "communityId": "…",
  "hashAlgorithm": "sha256",
  "passes": [{ "passId": "…", "codeHash": "…", "passHash": "…",
               "visitorName": "Anil", "guestCount": 2, "unitCode": "B-204",
               "validFrom": "…", "validUntil": "…" }] }
```

`hours` is 1–48 and defaults to 12.

**Hashes only.** There is no plaintext code anywhere in this database to hand out — the resident saw
theirs once, at creation. The device hashes what it scans with SHA-256 and compares locally, which is
why the algorithm is named in the payload rather than assumed.

**The bundle is not signed, and that is a decision rather than an omission.** The plan called for a
signature; writing it showed it would be theatre. A signature the device verifies against a key the
device holds protects nothing — the same person who can edit the cache can delete the check beside
it, because both are JavaScript on their machine. What makes an offline admission safe is that it is
**provisional until reconciled**; see the next endpoint.

**Stated honestly, because it is the one disclosure in this API worth arguing about:** this is a list
of live pass hashes for one community, and a six-digit code hashed with SHA-256 is a 10⁶ search
space, so the hashing obscures nothing from whoever holds the file. That is acceptable *here* and
nowhere else — the gate device is already authorised to admit exactly those visitors, so the bundle
tells the guard what the guard's job is. It is why the read is gate staff only and why it is
time-boxed.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not on duty in this community |

### `POST /api/v1/security/offline-reconcile`

Submit the queue an offline gate built, and get the server's verdicts. **Requires `security`, `admin`
or `manager`.** `US-3.5`.

```json
{ "entries": [{ "sourceClientId": "gate-1-000481", "credential": "483920",
                "presentedAt": "2026-08-10T09:04:00Z", "claimedVerdict": "admitted" }] }
```

```json
{ "accepted": 38, "rejected": 1, "replayed": 1,
  "outcomes": [{ "sourceClientId": "gate-1-000481", "serverVerdict": "admitted",
                 "detail": "Admitted.", "wasReplay": false }] }
```

**Idempotent per entry, on the device's own `sourceClientId`.** A device that lost its connection
mid-upload sends the whole queue again; entries already reconciled come back with `wasReplay: true`
and their original verdict, untouched. That matters more here than anywhere else in this API, because
re-running the verification on a replay would check the visitor *out* — a second scan is a departure.

**Every entry is its own transaction.** A queue of forty in which the eleventh is malformed
reconciles the other thirty-nine, which is the whole point of reconciling rather than submitting: the
device has already discarded its copy by then.

**A rejected entry is not an error either.** It becomes a row in `offline_reconcile_log` holding the
device's claim and the server's answer side by side, readable by the community's admins — deliberately
not by the guard whose entries are being checked. That log is what makes an unsigned bundle safe, and
it is the reason the bundle can be unsigned.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not on duty in this community |
| 422 | `validation_error` | An entry with no client id, or an empty queue |

### `GET /api/v1/security/exports/{dataset}`

One register as CSV. **Requires `security`, `admin` or `manager`.** `US-3.6`.

`dataset` is `material-movements`, `water-tankers`, `incidents` or `shifts`. `from` and `to` bound
the range. Answers `text/csv` with `Content-Disposition: attachment`.

**One route rather than four**, because the four differ in their columns and in nothing else: four
routes would be four copies of the same range validation, the same disposition header and the same
writer, and the fifth dataset would arrive as a fifth copy. An unknown dataset is a `422` naming the
four rather than an empty file.

**Oldest row first**, unlike every list on this surface. A screen wants the most recent thing at the
top; a spreadsheet opened for an audit reads forwards through time, and re-sorting fifteen thousand
rows is the first thing the reader would otherwise do.

**Retention needed no implementation, and the story is still served.** Nothing this backend writes is
ever aged out, so *"six months, one year, or longer"* is answered by `from` and `to` rather than by a
policy. The gap `US-3.6` named for gate operations was only ever two things: data to retain, and the
download. Both exist now.

**Cells beginning `=`, `+`, `-` or `@` are prefixed with an apostrophe.** Those are formula leaders in
every spreadsheet, and every one of them is reachable from a text field a guard types at the
barrier — so without it an export is a path from *anyone who can walk up to the gate* to *code that
runs when the security manager opens the audit report*. CSV quoting does not help: the spreadsheet
strips the quotes before evaluating the cell. The character is prefixed rather than stripped, because
stripping would silently turn a quantity of `-5` into `5`, and a register that alters the numbers it
is auditing is worse than one that shows an apostrophe.

| Status | Code | Cause |
|---|---|---|
| 403 | `forbidden` | You are not on duty in this community |
| 422 | `unknown_dataset` | Not one of the four |

### What this section does not do

**No `GET /security/snapshot`.** Every screen here is a list with a date range, and a snapshot would
be a twentieth read assembled from six that already exist. §18's worker snapshot earns its place
because a worker's dashboard is four unrelated questions; a gate's is one register at a time.

**No notification on a register write.** Nobody needs a push saying a tanker arrived. An incident
notifies, and only at `high` or `critical`, because that is the one entry here somebody is waiting
for.

**Nothing verifies a code at a gate that has never been online.** The bundle has to be fetched before
the outage. That is inherent to the design and not a gap in it — a device that has never
authenticated has no community, and a gate credential system that trusts an unauthenticated device is
not one.

~~**`US-3.5` stays `partial`, and the missing half is not here.** The server side is complete: a
time-boxed bundle to cache, and a reconcile that re-verifies. What is missing is the browser side —
`frontend/public/` has no service worker, which is also why `US-2.7`'s push cannot buzz a phone.
That is Step 8.~~

**`US-3.5` is served as of 2026-08-11.** The browser side shipped with the gate portal —
`GateHome.jsx` over `features/security/offline/`, which caches this bundle, hashes a scanned code
with Web Crypto and compares it locally, queues each offline scan under its own `sourceClientId`,
and posts the queue to `/security/offline-reconcile` when the connection returns. Every locally
decided verdict is shown as **provisional**, and an entry the server rejects stays on the guard's
screen until they dismiss it. The prediction above about the service worker was also wrong in its
reasoning: `localStorage` holds a bundle without one, and the worker (which shipped 2026-08-10 for
`US-2.7`) only buys surviving a reload mid-outage. See §16.5 for the full note.

## 20. Direct messages — the chat dock

Backed by `0046`. Five operations, one audience rule, and a lock. The chat dock mounts on **every
portal** — admin, worker, security, security-manager, resident — which is why this is its own
section rather than a subsection of §18: the population is everyone, not service personnel.

**Two people, one thread.** A direct thread is one row per pair per community, participants stored
in canonical order so the same two people cannot exist as two threads; opening one is an upsert.
This is deliberately not an extension of §18.4's hiring conversation — that schema is structurally
a department↔provider channel, and it stays one. **Counterpart names are snapshots** taken when the
thread opens (and refreshed on re-open), because `profiles` is readable only by its owner; the
known cost is that a rename shows stale until the pair's next open.

**Who may reach whom** is one predicate shared by the directory and the write: both active members
of the community, and either one is an admin or manager — **"the association committee" is the
`admin` role** in this product; the offices are not separate roles (`USER_IDENTIFICATION.md`) — or
they share a department. Residents therefore reach the office and not each other.

**The work-order thread is the one channel a resident and a serviceman share**, and it ends with
the job. Either participant may open it while the work order is live; a trigger locks it — and
writes a system line into the transcript — the moment the order goes terminal. A locked thread
stays readable (*"may have to be documented well"* — the product owner's words) and refuses new
messages with a `409`. That is the protection asked for: no private line survives the work.

### `GET /api/v1/messages/recipients`

`?communityId=…`. **Requires authentication only.** The dock's "to" field: department colleagues,
managers, admins — each `{ profileId, displayName, label }`, where `label` is `Admin`, `Manager` or
a department name, for display and nothing else.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 422 | `request_validation_error` | No `communityId` |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/messages/threads`

**Requires authentication only.** One mailbox across every community; the RLS policy is what makes
the list the caller's. `counterpartName` is resolved per caller — the same row answers "who is this
with" differently for its two participants.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/messages/threads`

Open (or return) a thread. **Requires authentication only.** `201`.

**Request** — `{ "communityId": "…", "recipientProfileId": "…" }` for a person, **or**
`{ "workOrderId": "…" }` for a live job's channel. Exactly one subject; both or neither is a `422`
before anything is written.

Idempotent on the pair: opening a chat that exists returns it, so a client calls this whenever a
name is picked rather than remembering whether it has.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `forbidden` | The CSRF pair failed, or the pair is not allowed |
| 404 | `not_found` | No such work order |
| 409 | `conflict` | The job is already terminal, or has no worker-and-resident pair |
| 422 | `request_validation_error`, `thread_subject_required`, `community_id_required` | Zero or two subjects, or a person without a community |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/messages/threads/{threadId}`

**Requires authentication only.** The thread with its messages, oldest first. A message with a null
`authorProfileId` is a **system line** — "the job ended, this conversation is closed" — written by
the database when the lock landed, so the silence has an explanation in the transcript itself.

**`404` covers missing and not-yours alike**; a stranger walking thread ids learns nothing from the
difference, and the message read happens only after the thread read succeeds.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 404 | `not_found` | No such thread, or the policy hides it |
| 500 | `internal_error` | Unhandled |

### `POST /api/v1/messages/threads/{threadId}/messages`

**Requires authentication only.** `201`. **Request** — `{ "body": "…" }`, 1–4000 characters.

**The `409` is the lock**, not an error path: a work-order thread whose job completed refuses new
messages so a serviceman cannot keep a private line to a resident after the work is done. The
counterpart is notified (`dm.message`) inside the same transaction, through `notify_profile` —
person-addressed, because a provider counterpart may hold no membership at all.

| Status | Code | Cause |
|---|---|---|
| 401 | `authentication_error` | No credentials |
| 403 | `csrf_invalid`, `csrf_origin_invalid` | The CSRF pair failed |
| 404 | `not_found` | No such thread, or the policy hides it |
| 409 | `conflict` | The thread is locked |
| 422 | `request_validation_error` | An empty body, or one over 4000 characters |
| 500 | `internal_error` | Unhandled |

## 21. Address search — the location picker's proxy

Two `GET`s, added 2026-08-21, and the reason for both is a defect that live testing surfaced rather
than a feature anybody asked for.

**The defect.** Registration asked a service person for a latitude and a longitude and offered
nothing else but a browser geolocation button. A latitude is not a fact a person knows about their
own house. So the field was skipped — and a provider with no coordinates has a null generated
`location`, which makes them invisible to `search_hireable_service_providers` and makes
`search_serviceable_communities` refuse to run at all. The most accessibility-hostile field on the
form was also the one that decided whether the account worked. The community-founding wizard and the
admin settings screen asked the same question the same way.

**The fix, in order of prominence on the screen:** type an address and press Search; drag a pin on a
map; use the device's location; or, folded away under a disclosure, type the two numbers. All four
write the same one pair of coordinates. These two endpoints serve the first two.

### Why this is a backend proxy and not a `fetch` from the browser

The upstream is [Nominatim](https://nominatim.openstreetmap.org), OpenStreetMap's own geocoder. It
is free, needs no key, and asks three things in return:

| The policy asks | Where this API honours it |
|---|---|
| An identifying `User-Agent` | Sent on every upstream call. A browser refuses to let script set this header at all. |
| At most **1 request/second** for the whole application | A process-wide async lock held across each upstream call. A thousand tabs cannot coordinate; one process can. |
| Cache results | A bounded 24-hour in-memory cache, keyed on the normalised query or the coordinate rounded to ~1 m. |

It also **forbids autocomplete**. That is why `GET /geo/search` is documented as a button: the picker
submits on Enter or on the Search button and never on an input event. A client that debounces this
into a type-ahead is not using it more responsively, it is using somebody else's free service against
their stated terms.

There is no configuration for the upstream host. A proxy whose destination the caller can influence
is a server-side request forgery with a nicer name, so the host is a constant in
`app/services/geocoding_service.py`.

**Both routes require authentication and nothing more** — no membership. Two of the three screens
that use the picker belong to people who hold no membership at the moment they need it: a service
person registering, and a founder creating the community that will be their first. Neither takes
CSRF, because both are `GET`.

**Upstream failure is `503`, never `500`.** A timeout or a 429 is a true statement about a third
party and the screen stays usable without it — the map pin and the manual fields are right there —
so the client shows a line of prose and carries on.

### `GET /api/v1/geo/search`

**Requires authentication only.** `?q=` is the typed address, 3–120 characters.

```json
[{ "label": "Andheri West, Mumbai, Maharashtra",
   "description": "Andheri West, Mumbai, Mumbai Suburban, Maharashtra, 400053, India",
   "latitude": 19.1364, "longitude": 72.8296 }]
```

Up to five results, best match first. `label` is the short three-part form the picker writes into the
editable `locationLabel` field; `description` is the upstream's own full line, kept because five
results named "Andheri West" need something to tell them apart.

**Never the upstream's payload.** Nominatim answers with roughly thirty fields per result — OSM ids,
bounding boxes, licence strings, place ranks — and none of them are ours to publish or to keep
stable. The three facts a picker needs are the two that place a pin and the one a person reads.

**No match is `200 []`.** The pick-list renders that as *nothing found — drop the pin instead*, which
is a state and not a failure; a `404` would send it down the branch that means the route is missing.

| Status | Code | Cause |
|---|---|---|
| 200 | | Zero to five matches |
| 401 | `authentication_error` | No credentials |
| 422 | `request_validation_error` | `q` missing, under 3 characters, or over 120 |
| 503 | `geocoding_unavailable` | The upstream timed out, refused, or throttled us |
| 500 | `internal_error` | Unhandled |

### `GET /api/v1/geo/reverse`

**Requires authentication only.** `?lat=` and `?lon=`, both required and range-checked. Returns one
object in the shape above.

Called when the pin is dropped or dragged, to refresh the suggested label. **Answers at roughly
suburb precision, not building precision** — a deliberate ceiling rather than a limit of the
upstream. The label it produces is stored on the profile and shown to hiring managers who are never
given the coordinate; a street address returned here would become a different disclosure under the
same field name.

**`404` over the sea.** A point with nothing addressable is not an invalid request: the client keeps
the coordinate and leaves the label for the person to write.

| Status | Code | Cause |
|---|---|---|
| 200 | | A place name for that point |
| 401 | `authentication_error` | No credentials |
| 404 | `geo_place_not_found` | Nothing is addressable there |
| 422 | `request_validation_error` | `lat`/`lon` missing or out of range |
| 503 | `geocoding_unavailable` | The upstream timed out, refused, or throttled us |
| 500 | `internal_error` | Unhandled |

### `locationLabel` — where the answer is kept

Both endpoints exist to fill one optional field, stored by migration
`20260821113000_location_labels.sql` as `location_label text` on **both** `service_providers` and
`communities`, capped at 120 characters by a `CHECK`.

It appears on `POST`/`PATCH`/`GET /service-providers/me`, `GET /service-providers/{providerId}`,
`GET /departments/{departmentId}/candidates`, `GET`/`PUT /settings`, and
`POST /onboarding/community` (as `location_label`, that body being `snake_case`).

**It is never an input to distance.** `latitude`/`longitude` remain the stored truth, `location`
remains generated from them, and every search's geometry, radius and ordering is exactly what it was
before this shipped. The label is a decoration on the *input*, and its one job downstream is to let a
candidate card say "Andheri West, Mumbai" where it previously said nothing.

**Its 120-character cap is a privacy boundary, not a storage decision.** The hiring surface
deliberately withholds coordinates (§18). A label short enough to hold "suburb, city, state" and too
short to hold a street address is what keeps the field on the right side of that line, which is why
the reverse lookup asks for suburb-level detail rather than trimming a building-level answer.
