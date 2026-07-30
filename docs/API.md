# HomeBandhu API reference

**Version:** v1 · **Base path:** `/api/v1` · **Last updated:** 2026-07-30

> ## ⚠ Sections 5–11 are being revised down to the post-merge surface
>
> `origin/main` @ `94556e5` merged into this branch, and the frontend wiring audit removed **32 of our
> operations** — every read the shared `GET /dashboard/snapshot` already serves, plus the amenity CRUD their
> `/dashboard/amenities` already serves. **The generated [`openapi.yaml`](openapi.yaml) and `/docs` are correct
> right now; the prose in §5–§11 still describes removed endpoints.**
>
> Until that prose is pruned, read this file with **[FRONTEND_WIRING_AUDIT.md](FRONTEND_WIRING_AUDIT.md)** beside
> it — it lists every removal and its evidence. The live surface is 59 operations: 24 from the auth/dashboard
> workstream and the 35 below.
>
> **Our 35 operations, post-audit**
>
> | Section | Live | Removed by the audit |
> |---|---|---|
> | §5 Admin dashboard | *(none — router deleted)* | `GET /dashboard/admin`, `GET /communities/current`, `GET /notices`, `GET /residents` |
> | §6 People | `POST /admins` **(new)** | `GET /admins`, `GET`/`PATCH`/`DELETE /residents…`, `GET /registrations`, `POST /registrations/{id}/approve\|reject` |
> | §7 Complaints | `PATCH /complaints/{id}`, `POST /complaints/{id}/comments` | `GET /complaints`, `GET /complaints/{id}`, `POST …/read`, `POST …/attachments` |
> | §8 Departments | all 8 (reads included — the snapshot stubs `staff: []`) | `GET /complaint-categories` |
> | §9 Money | `POST /invoices`, `POST /invoices/{id}/payments`, `GET`/`PUT /billing-settings` | `GET /invoices`, `GET /invoices/{id}`, `GET /invoices/summary`, `GET /payments`, `POST …/void`, `POST /maintenance-runs` |
> | §10 Amenities | 16 — bookings, approvals, blocks, ledger, reports | the 6 catalogue endpoints |
> | §11 Settings | `GET`/`PUT /settings` | `GET`/`PUT /settings/modules`, `PATCH /settings/modules/{key}` |
> | *new* Notices | `POST /notices` **(new)** | — |
>
> **Two contract-wide changes that apply to every endpoint below.**
>
> 1. **Authentication is cookie-first.** A signed HTTP-only session cookie is the normal credential; the bearer
>    header still works, because their `_extract_token` accepts either. Role checks resolve from
>    `community_memberships` in Postgres, not from a JWT claim — the access-token hook that produced that claim was
>    deleted with the old baseline.
> 2. **Every unsafe request needs `X-CSRF-Token`.** All our writes now enforce it. Reads do not send or require it.
>    A missing or mismatched token is **403** with code `csrf_invalid`, and a wrong `Origin` is **403**
>    `csrf_origin_invalid`.
>
> **Nothing below runs against a database yet.** Migrations `0010`–`0017` were quarantined to
> `backend/supabase/migrations/legacy-preauth/`; only `0018` was rebuilt on the baseline, covering `§11 Settings`,
> `GET`/`PUT /billing-settings` and `POST /notices`.

This document is the contract between the backend and the React frontend. It is
**normative**: if the code and this document disagree, that is a bug in one of them.

> **Standing rule.** Every backend change updates this file in the same commit — new endpoints,
> changed shapes, changed status codes. The frontend team is not in the room, and an endpoint that
> exists only in Python is invisible to them.

An OpenAPI 3.1 schema is generated from the code at **`GET /openapi.json`**, with interactive docs at
**`/docs`** (Swagger UI) and **`/redoc`**. That schema is authoritative for *shapes*; this file adds
what a generated schema cannot: status-code semantics, error codes, caching behaviour, and the
reasons behind the conventions.

The same schema is checked in as **[`openapi.yaml`](openapi.yaml)**, so the contract can be read,
diffed and used to generate clients without running the service.

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

All endpoints except `/health`, `/auth/otp/*`, `/auth/refresh` and `/auth/redeem` require a
Supabase-issued JWT:

```
Authorization: Bearer <access_token>
```

The token is verified against `SUPABASE_JWT_SECRET`. Its `user_role` claim is injected by the Supabase
access-token hook from `profiles.role`, and is what the role guards read.

**Roles are implied, not just matched.** `ADMIN` satisfies a `RESIDENT` requirement
(`app/domain/roles.py`). An endpoint documented as *Resident* therefore also admits an admin.

**Enforcement is layered.** The role guard is the outer check; Postgres Row-Level Security is the
inner one, and it is scoped by community. A guard bypass still cannot read another community's rows.

### 1.3 Field naming — a known inconsistency

| Endpoint group | Case | Example |
|---|---|---|
| `/auth/*`, `/admin/invitations` | `snake_case` | `access_token`, `apartment_id` |
| Everything else | `camelCase` | `pageSize`, `timeAgo`, `unitId` |

This is not a style preference, it is a seam. The React app reads camelCase throughout its seeded data
and **cannot be changed**, so new surfaces emit camelCase. The auth DTOs predate that constraint and
are being modified in parallel by another developer, so converting them during a schema migration
would be a drive-by edit to someone else's in-flight work. They should adopt the same base class when
that code is next touched deliberately.

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

**Not implemented.** No endpoint is rate-limited today, including `/auth/otp/request` and
`/auth/redeem` — both of which need it, being unauthenticated and secret-guessing surfaces. Supabase
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

> **These endpoints describe phone/SMS OTP, which is what the code does today.** The product ruling is
> that OAuth replaces phone/OTP, and that migration has not been made yet. This section will change.
> The resident invite token remains a mandatory second factor regardless.

### `POST /api/v1/auth/otp/request`

Send a login code to a registered phone. No authentication.

**Request**
```json
{ "phone": "+919876543210" }
```

**200**
```json
{ "message": "If the number is registered, a code has been sent." }
```

The response is **identical for unknown numbers** — deliberately, to prevent user enumeration.
Unregistered numbers simply never receive a code (`should_create_user=false`).

| Status | Code | Cause |
|---|---|---|
| `200` | — | Always, when the request is well-formed |
| `400` | `app_error` | The SMS provider rejected the send |
| `422` | `request_validation_error` | Missing or malformed `phone` |

### `POST /api/v1/auth/otp/verify`

Exchange the SMS code for a session. No authentication.

**Request**
```json
{ "phone": "+919876543210", "token": "123456" }
```

**200**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "v1.Mr7...",
  "token_type": "bearer",
  "expires_at": 1785312000,
  "user_id": "8f14e45f-ceea-467a-9f1e-1f1a1f0e9c11",
  "role": "RESIDENT"
}
```

| Status | Code | Cause |
|---|---|---|
| `200` | — | Verified |
| `401` | `authentication_error` | Wrong or expired code |
| `422` | `request_validation_error` | Malformed body |

### `POST /api/v1/auth/refresh`

Exchange a refresh token for a new session ("remember me"). No authentication.

**Request** — `{ "refresh_token": "v1.Mr7..." }` · **200** — same `Session` shape as above.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | Refresh token invalid, expired or revoked |

### `GET /api/v1/auth/me`

The caller's own profile. **Any authenticated role.**

**200**
```json
{
  "id": "8f14e45f-ceea-467a-9f1e-1f1a1f0e9c11",
  "role": "RESIDENT",
  "full_name": "Aakash S.",
  "phone": "+919876543210",
  "apartment_id": "B-1204",
  "association_id": "3c6e0b8a-9c15-4f2b-9d1a-2b7c8e4d5a60",
  "status": "Active"
}
```

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | Missing or invalid token |
| `404` | `not_found` | Token is valid but no profile row is visible |

---

## 4. Invitations

### `POST /api/v1/admin/invitations`

Mint a resident invite. **Requires `ADMIN`.**

**Request**
```json
{ "phone": "+919812345678", "apartment_id": "B-1204", "full_name": "Rohan Sharma", "role": "RESIDENT" }
```

**200**
```json
{
  "invitation_id": "b2f1c9d4-...",
  "link": "http://localhost:5173/join/9f2a...",
  "code": "4KJ7-2M",
  "phone": "+919812345678",
  "apartment_id": "B-1204",
  "role": "RESIDENT",
  "expires_at": "2026-08-01T09:00:00+00:00"
}
```

> ⚠️ **`link` and `code` are returned exactly once and are never recoverable.** Only their digests are
> stored. If the admin loses them, the invite must be reissued.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | Not authenticated |
| `403` | `insufficient_role` | Caller is not an admin |
| `422` | `request_validation_error` | Malformed body |

### `POST /api/v1/auth/redeem`

Redeem an invite via magic-link token or typed code. **No authentication** — this is how a new
resident gets their first session.

**Request** — `phone` plus **exactly one** of `token` or `code`:
```json
{ "phone": "+919812345678", "code": "4KJ7-2M" }
```

**200** — a `Session`.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | Token/code does not match |
| `409` | `conflict` | Already redeemed |
| `422` | `validation_error` | Neither or both of `token`/`code`; or the invite has expired |

---

## 5. Admin dashboard

### `GET /api/v1/dashboard/admin`

The admin home aggregate. **Requires `ADMIN`.** `Cache-Control: no-store`.

One request instead of five. The frontend currently derives these counts by filtering whole
collections in the browser, which stops working the moment those collections are paginated.

**200**
```json
{
  "totalResidents": 42,
  "pendingRequests": 0,
  "activeComplaints": 7,
  "collection": { "current": 12750, "target": 17500, "percent": 73 },
  "generatedAt": "2026-07-29T13:35:21.838130+00:00"
}
```

| Field | Status |
|---|---|
| `totalResidents` | **Real.** Active `RESIDENT` memberships. |
| `activeComplaints` | **Real.** Status in `pending`, `in_progress`, `reopened`. |
| `pendingRequests` | **Real** as of step 4. Requests with status `pending`. |
| `collection` | **Real** as of step 7. Read from the same aggregate that serves `GET /invoices/summary`, so the home page and the collections screen cannot disagree. Whole rupees, matching the frontend's own rounding. |

Every field is now real; nothing on this response is a placeholder. `target` is everything billed,
including what is not yet due; `current` is what has actually been received. **`percent` is `0` when
`target` is `0`**, not `NaN` — a founding community has no invoices at all.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community yet |

### `GET /api/v1/communities/current`

The caller's community. **Any authenticated role** — the resident shell needs the name in its header
too.

**200**
```json
{
  "id": "3c6e0b8a-9c15-4f2b-9d1a-2b7c8e4d5a60",
  "name": "HomeBandhu Residency",
  "communityType": "apartment",
  "status": "Active",
  "createdAt": "2026-07-01T09:00:00+00:00"
}
```

| Status | Code | Cause |
|---|---|---|
| `404` | `not_found` | No profile, or the caller belongs to no community |

### `GET /api/v1/residents`

Page through the community's residents. **Requires `ADMIN`.**

| Query | Type | Default | Notes |
|---|---|---|---|
| `search` | string ≤ 100 | — | Case-insensitive across name, flat code and phone |
| `page` | integer | `1` | ≥ 1 |
| `pageSize` | integer | `20` | 1–100 |

**200**
```json
{
  "items": [
    {
      "id": "7d3c1b90-...",
      "profileId": "8f14e45f-...",
      "name": "Aakash S.",
      "email": null,
      "phone": "+919876543210",
      "role": "RESIDENT",
      "displayRole": "Resident",
      "flat": "B-1204",
      "unitId": "a1b2c3d4-...",
      "status": "active",
      "joinedAt": "2026-07-01T09:00:00+00:00"
    }
  ],
  "total": 1, "page": 1, "pageSize": 20, "hasMore": false
}
```

**Every reference carries both a label and an id** — `flat` + `unitId`, `role` + `displayRole`. The
frontend ignores keys it does not know, so the ids are free to send now and adopt one screen at a
time. `id` is the **membership** id, not the profile id; `profileId` is given separately.

`email` is real as of step 4 (migration `0012` adds `profiles.email`, backfilled from `auth.users`).
It can still be `null` for a member who has no address on file.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `422` | `request_validation_error` | `page` < 1, `pageSize` out of 1–100 |

### `PATCH /api/v1/residents/{membershipId}`

Update a resident. **Requires `ADMIN`.** The path parameter is the **membership** id, as returned in
`items[].id` — not `profileId`.

**Request** — a partial update; omitted fields are left unchanged, an explicit `null` clears one.
```json
{ "name": "Rohan Sharma", "email": "rohan@example.com", "phone": "+919812345678", "designation": "Treasurer" }
```

**200** — `{ "message": "Resident updated." }`

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such member in the caller's community |
| `409` | `unique_violation` | Another member already has that value |
| `422` | `request_validation_error` | A field exceeds its maximum length |

> This endpoint writes to two tables and is **not atomic**, unlike approve/remove. A partial failure
> leaves some fields updated and others not — visible to the admin, and fixed by retrying. There is no
> invariant between the two writes, so the extra machinery would buy nothing.

### `DELETE /api/v1/residents/{membershipId}`

Remove a resident. **Requires `ADMIN`.**

**200** — `{ "message": "Resident removed." }`

> ⚠️ **This deactivates; it does not delete.** The membership is marked `inactive` and the open
> residency is ended, so the member leaves active lists and the flat reads as vacant. Complaints,
> invoices and payments reference the membership, so removing the row would either cascade them away
> or fail outright. There is no hard-delete endpoint by design.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin, or the member belongs to another community |
| `404` | `not_found` | No such member |
| `409` | `conflict` | **An admin tried to remove their own membership.** Refused — there is no recovery path from locking a community out of its own dashboard |

---

### `GET /api/v1/notices`

Published notices, newest first. **Any authenticated role.** `Cache-Control: no-store`.

Query parameters: `page`, `pageSize` (§1.6).

**200**
```json
{
  "items": [
    {
      "id": "n1a2b3c4-...",
      "title": "Water tank cleaning scheduled",
      "description": "Annual cleaning of the overhead water tanks...",
      "category": "Maintenance",
      "urgency": "high",
      "date": "July 8, 2026",
      "timeAgo": "Today",
      "publishedAt": "2026-07-08T04:30:00+00:00"
    }
  ],
  "total": 1, "page": 1, "pageSize": 20, "hasMore": false
}
```

Draft and archived notices are never returned here. `urgency` is one of `info | low | medium | high`.

Note that `timeAgo` uses a **day-granularity** vocabulary (`Today`, `Yesterday`, `3d ago`) while
complaints use an hour-granularity one (`2h ago`). That is not an inconsistency on our side — the two
frontend lists genuinely render different vocabularies, and we match each.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | Not authenticated |
| `422` | `request_validation_error` | Bad pagination values |
---

## 6. People

### `GET /api/v1/admins`

Every admin of the caller's community. **Requires `ADMIN`.**

Returned in the standard page envelope for consistency, but **not paginated** — an association has a
committee, not a directory. `total` equals `items.length` and `hasMore` is always `false`.

**200**
```json
{
  "items": [
    {
      "id": "9c1e...", "profileId": "8f14...",
      "name": "Meera Sharma", "email": "meera.admin@homebandhu.com", "phone": "+919876501234",
      "role": "ADMIN", "displayRole": "Admin",
      "designation": "Secretary",
      "flat": "Admin Office", "unitId": null,
      "status": "active", "joinedAt": "2026-07-01T09:00:00+00:00"
    }
  ],
  "total": 1, "page": 1, "pageSize": 1, "hasMore": false
}
```

`designation` is the office held in the residents' association — President, Secretary, Treasurer,
Committee Member, Association Manager, Other. It is a **third axis**, distinct from `role` (what the
system permits) and from staff `jobTitle` (what a worker does).

`flat: "Admin Office"` with `unitId: null` is expected, not an error — it is the literal value the
frontend uses for admins who have no flat, and it correctly resolves to no unit.

### `GET /api/v1/registrations`

Self-signup requests awaiting review. **Requires `ADMIN`.** `Cache-Control: no-store`.

| Query | Type | Default | Notes |
|---|---|---|---|
| `status` | enum | `pending` | `pending` \| `approved` \| `rejected` |
| `page` / `pageSize` | integer | `1` / `20` | §1.6 |

**200**
```json
{
  "items": [
    {
      "id": "4a7b...", "name": "Siddharth Roy",
      "email": "siddharth@gmail.com", "phone": "+919888877777",
      "flat": "C-505", "tower": "C",
      "status": "pending",
      "date": "July 8, 2026", "submittedAt": "2026-07-08T04:30:00+00:00"
    }
  ],
  "total": 1, "page": 1, "pageSize": 20, "hasMore": false
}
```

`flat` is always the **canonical full code**; `tower` is derived from it. Only the code is stored —
storing both invites them to disagree, which is exactly the frontend bug in agenda item 8.

> **Submitting a request is not part of this API.** That is registration, which is out of scope for
> this workstream. These endpoints are the admin-facing review half only.

### `POST /api/v1/registrations/{requestId}/approve`

Approve a request. **Requires `ADMIN`.**

**201 Created** — 201 rather than 200 because this creates an invitation.
```json
{
  "requestId": "4a7b...",
  "invitationId": "b2f1...",
  "link": "http://localhost:5173/join/9f2a...",
  "code": "K7M2QPR9",
  "phone": "+919888877777",
  "flat": "C-505",
  "name": "Siddharth Roy",
  "expiresAt": "2026-08-01T09:00:00+00:00"
}
```

> ⚠️ **Approval does not create an active account.** It marks the request approved and mints an
> **invitation** the applicant redeems, because the invite token is a mandatory second factor. This
> differs from the demo frontend, where `acceptRequest` immediately creates an `Active` resident.
>
> ⚠️ **`link` and `code` are returned exactly once** and are never recoverable — only digests are
> stored. If the admin loses them, reissue via `POST /admin/invitations`.

Both writes happen inside **one Postgres transaction** (an RPC), so a request can never end up
approved with no invitation. The flat is created on first reference if it does not exist.

| Status | Code | Cause |
|---|---|---|
| `201` | | Approved |
| `401` / `403` | `forbidden` | Not authenticated; not an admin; or the request belongs to another community |
| `404` | `not_found` | No such request |
| `409` | `conflict` | Already approved or rejected. Two admins clicking at once serialise, and the second gets this |

### `POST /api/v1/registrations/{requestId}/reject`

Reject a request. **Requires `ADMIN`.** Body is optional.

**Request** — `{ "reason": "Flat already occupied." }` · **200** — `{ "message": "Registration request rejected." }`

The applicant may apply again: the uniqueness rule covers only *pending* requests, so both attempts
survive in the history.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` / `404` / `409` | | As for approve |

## 7. Complaints

Reads and comments are open to **any member** of the community — a resident must be able to follow and
discuss their own complaint. Editing is **admin-only**.

### `GET /api/v1/complaints`

List complaints, newest first. `Cache-Control: no-store`.

| Query | Type | Default | Notes |
|---|---|---|---|
| `status` | string | — | `Pending` \| `In Progress` \| `Resolved` |
| `categoryId` | uuid | — | |
| `departmentId` | uuid | — | |
| `search` | string ≤ 100 | — | Title, description, assignee |
| `page` / `pageSize` | integer | `1` / `20` | §1.6 |

**200**
```json
{
  "items": [
    {
      "id": "c1a2...", "title": "Leaking tap in kitchen",
      "description": "The kitchen sink mixer tap is dripping...",
      "raisedBy": "Aakash S.", "raisedByMembershipId": "7d3c...",
      "flat": "B-1204", "unitId": "a1b2...", "location": "Kitchen",
      "category": "Plumbing", "categoryId": "e5f6...",
      "department": "Plumbing & Water", "departmentId": "d7e8...",
      "status": "In Progress", "urgency": "Medium", "progress": 65,
      "assignee": "Ramesh - Plumber", "assignedToMembershipId": null,
      "date": "July 8, 2026", "timeAgo": "2h ago",
      "submittedAt": "2026-07-08T04:30:00+00:00",
      "updatedAt": "2026-07-08T09:15:00+00:00",
      "expectedResolutionAt": "2026-07-10T04:30:00+00:00",
      "isBreaching": false, "hasUnreadUpdate": true,
      "reopenedCount": 0, "rating": null,
      "residentFeedback": null, "resolutionConfirmed": false
    }
  ],
  "total": 1, "page": 1, "pageSize": 20, "hasMore": false
}
```

**`isBreaching`** is computed server-side so every screen agrees on the definition: the deadline has
passed **and** the complaint is still open. A resolved complaint that took too long is *late*, not
breaching — the tile counts work outstanding now.

**`hasUnreadUpdate` is per caller**, derived from a read receipt rather than a flag on the complaint.
The frontend's single boolean cannot represent an admin and a resident having seen different versions;
this can. No receipt at all means never opened, so unread.

Unknown `status` values are rejected with `422 unknown_status` rather than silently ignored.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | Not authenticated |
| `422` | `unknown_status` / `request_validation_error` | Unrecognised status; bad pagination |

### `GET /api/v1/complaints/{complaintId}`

One complaint plus its timeline, comments and attachments. **Any member.** `Cache-Control: no-store`.

**200** — every field from the list, plus:
```json
{
  "timeline": [
    { "id": "ev1...", "type": "raised", "label": "Complaint raised",
      "message": "The complaint was submitted to the management team.",
      "actor": "Aakash S.", "createdAt": "2026-07-08T04:30:00+00:00" },
    { "id": "ev2...", "type": "assigned", "label": "Technician assigned",
      "message": "Ramesh - Plumber was assigned to this complaint.",
      "actor": "Management", "createdAt": "2026-07-08T06:00:00+00:00" }
  ],
  "comments": [
    { "id": "cm1...", "message": "Plumber will visit at 4pm.",
      "authorName": "Meera Sharma", "authorRole": null,
      "visibility": "resident", "createdAt": "2026-07-08T09:15:00+00:00" }
  ],
  "attachments": [
    { "id": "at1...", "storagePath": "c1a2/leak.jpg",
      "url": "https://...signed...", "attachmentType": "photo",
      "contentType": "image/jpeg", "sizeBytes": 184320,
      "createdAt": "2026-07-08T04:31:00+00:00" }
  ]
}
```

**`timeline` and `comments` are different things** and both are returned. The timeline is an
append-only audit stream — there is no UPDATE or DELETE policy on it in Postgres, so it is
structurally immutable, not immutable by convention. Comments are a conversation: authored, editable
in principle, and subject to visibility.

**Internal comments never reach a non-admin caller.** That is enforced by RLS, not by this layer.

**`attachments[].url`** is a signed link valid for 10 minutes. It is `null` when signing fails or the
storage bucket is missing — one broken attachment must not take down the complaint it belongs to.

| Status | Code | Cause |
|---|---|---|
| `404` | `not_found` | No such complaint in the caller's community |

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
(**admins only** — never returned to a resident, and never written to the timeline).

| Status | Code | Cause |
|---|---|---|
| `403` | `forbidden` | Not a member, or a non-admin asked for `internal` |
| `404` | `not_found` | No such complaint |
| `409` | `conflict` | Empty message, or unknown visibility |

### `POST /api/v1/complaints/{complaintId}/read`

Clear the caller's unread badge. **Any member.** `200` — `{ "message": "Marked as read." }`

Read state is per person, so this affects only the caller.

### `POST /api/v1/complaints/{complaintId}/attachments`

Register a file already uploaded to Supabase Storage. **Any member.** `201 Created`.

**Request**
```json
{ "storagePath": "c1a2/leak.jpg", "attachmentType": "photo",
  "contentType": "image/jpeg", "sizeBytes": 184320 }
```

**The bytes never pass through this API.** The client uploads straight to Storage and registers the
path here, which keeps large uploads off the application server.

> ⚠️ **Setup required:** the bucket `complaint-attachments` must exist and must be **private**. A
> public bucket would make every complaint photo world-readable by URL, bypassing RLS entirely.

`attachmentType` is `photo` | `document` | `resolution_proof`.

---

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

### `GET /api/v1/complaint-categories`

The category vocabulary behind the department form's checkbox list. **Requires `ADMIN`.** Not
paginated — this is an option list, and a community that needs paging through its own complaint
categories has a different problem. Returned in the standard page envelope for consistency.

**200**
```json
{
  "items": [
    { "id": "9c1d...", "name": "Plumbing", "slaHours": null, "status": "active",
      "departmentIds": ["2f8a..."] }
  ],
  "total": 5, "page": 1, "pageSize": 5, "hasMore": false
}
```

`departmentIds` carries **every** department claiming the category. More than one entry is precisely
the case where the SLA tie-break decides which deadline applies (`DECISIONS_NEEDED.md` A1) — exposed
rather than flattened to a single owner, because flattening would hide the conflict.

Five categories are seeded per community: Plumbing, Electrical, Infrastructure, Cleaning, Security.
The dashboard's checkbox list has a sixth, **`Others`**, which is not seeded and is created the first
time a department claims it.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

---

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

### `GET /api/v1/invoices`

Page through the community's invoices — the maintenance collections table. **Requires `ADMIN`.**

| Query | Type | Default | Notes |
|---|---|---|---|
| `q` | string ≤ 100 | — | Matches invoice title, invoice number, flat code **and the current resident's name** |
| `status` | string | — | `Paid` \| `Unpaid` \| `Void` \| `All` |
| `unitId` | uuid | — | One flat's invoices |
| `invoiceType` | string | — | `maintenance` \| `amenity` \| `penalty` \| `misc` |
| `overdueOnly` | boolean | `false` | Past due with a balance |
| `issuedFrom` / `issuedTo` | date | — | Inclusive bounds on `issuedOn` |
| `page` | integer | `1` | ≥ 1 |
| `pageSize` | integer | `20` | 1–100 |

**200**
```json
{
  "items": [
    {
      "id": "8b31...",
      "invoiceNumber": "INV-2026-00001",
      "title": "Maintenance Fee - July 2026",
      "invoiceType": "maintenance",
      "amount": 4250.0,
      "subtotal": 4250.0,
      "tax": 0.0,
      "outstanding": 4250.0,
      "amountPaid": 0.0,
      "currency": "INR",
      "status": "Unpaid",
      "statusDetail": "issued",
      "isOverdue": false,
      "dueDate": "2026-07-15",
      "issuedOn": "2026-07-01",
      "billPeriod": "July 1, 2026 - July 31, 2026",
      "billingPeriodStart": "2026-07-01",
      "billingPeriodEnd": "2026-07-31",
      "flat": "B-1204",
      "tower": "B",
      "unitId": "6d2c...",
      "userId": "a91f...",
      "residentProfileId": "0c47...",
      "residentName": "Priya Sharma",
      "paidOn": null,
      "paymentMethod": null,
      "notes": null,
      "createdAt": "2026-07-01T09:00:00+00:00",
      "updatedAt": "2026-07-01T09:00:00+00:00"
    }
  ],
  "total": 5, "page": 1, "pageSize": 20, "hasMore": false
}
```

**`amount` is what the flat was billed, not what it still owes** — the column is headed "Amount".
`outstanding` carries the balance. This matters: a partially paid invoice still reports its full
`amount`, so **a client that sums `amount` over `Unpaid` rows overstates receivables.**
`GET /invoices/summary` is the authority on the totals.

**`status` has three wire values over five stored ones.** `partially_paid` reads `Unpaid`, because
money is still owed and the screen's question is whether the flat owes anything. `statusDetail`
carries the real lifecycle value for a client that wants the distinction back. `void` is given its
own value rather than folded into `Unpaid`, so a cancelled bill is not counted as a receivable.

**`isOverdue` is derived on every read**, from the due date and the balance — never stored. A stored
overdue flag is correct only in the instant a cron job sets it. This is a deliberate deviation from
the ERD's `InvoiceStatus`, which lists `OVERDUE` as a status.

`userId` is the **membership id**, matching what `GET /residents` returns as `id`, so the dashboard's
`users.find(u => u.id === pay.userId)` resolves. It is `null` for a vacant flat, which the frontend
already renders as `"Resident"`.

Line items are **not** embedded. Unlike a department's roster, no list screen renders them.

| Status | Code | Cause |
|---|---|---|
| `400` | `invalid_status` | `status` is not `Paid`/`Unpaid`/`Void`/`All` |
| `400` | `invalid_invoice_type` | `invoiceType` outside the four values |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |
| `422` | `request_validation_error` | `page` < 1, `pageSize` out of 1–100, unparseable date |

### `GET /api/v1/invoices/summary`

The three tiles at the top of the Maintenance screen. **Requires `ADMIN`.**

**200**
```json
{
  "totalCollected": 12750.0,
  "totalOutstanding": 4750.0,
  "totalBilled": 17500.0,
  "paidCount": 3,
  "unpaidCount": 2,
  "invoiceCount": 5,
  "collectionPercent": 73,
  "overdueCount": 1,
  "overdueAmount": 500.0,
  "currency": "INR",
  "generatedAt": "2026-07-29T18:10:00+00:00"
}
```

**Aggregated over every invoice in the community, not over a page.** The dashboard derives these by
summing the invoice array it happens to hold (`Maintenance.jsx:11-17`), which is correct only while
every invoice fits in one response. That is agenda item 11.

`totalOutstanding` sums the outstanding **balances**, so a partially paid invoice contributes only
what is still owed. Voided invoices are excluded from every figure — a cancelled bill is neither
collected nor collectable.

A community with no invoices reports zeros with `200`, never a `404`. `collectionPercent` is `0` when
`totalBilled` is `0`, not `NaN`.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

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

### `GET /api/v1/invoices/{invoiceId}`

One invoice with its line items and every payment recorded against it. **Requires `ADMIN`.**

**200** — the list shape plus:
```json
{
  "lineItems": [
    { "id": "aa10...", "description": "Monthly maintenance", "quantity": 1.0,
      "unitAmount": 4250.0, "total": 4250.0 }
  ],
  "payments": [
    { "id": "cc20...", "invoiceId": "8b31...", "invoiceNumber": "INV-2026-00001",
      "invoiceTitle": "Maintenance Fee - July 2026", "amount": 4250.0, "currency": "INR",
      "method": "Net Banking", "status": "succeeded", "reference": "TXN-88213",
      "paidAt": "2026-07-10T06:12:00+00:00", "payerProfileId": "0c47...",
      "payerName": "Priya Sharma", "unitId": "6d2c...", "flat": "B-1204", "notes": null }
  ]
}
```

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such invoice in the caller's community |

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

### `POST /api/v1/invoices/{invoiceId}/void`

Cancel an invoice. **Requires `ADMIN`.**

```json
{ "reason": "Raised against the wrong flat" }
```

**200** — the invoice in its voided state.

Refused once **any** payment has succeeded against it: cancelling a bill somebody has already paid
would strand their money against nothing. Refund first.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such invoice |
| `409` | `conflict` | Already void, or has succeeded payments against it |

### `POST /api/v1/maintenance-runs`

Issue one maintenance invoice per **occupied** flat for a billing period. **Requires `ADMIN`.**

```json
{
  "amount": 4250,
  "periodStart": "2026-08-01",
  "periodEnd": "2026-08-31",
  "dueDate": "2026-08-15",
  "title": "Maintenance Fee - August 2026"
}
```

Every field is optional. `amount` falls back to `billingSettings.defaultMaintenanceAmount`; the
period defaults to the current month; the due date to `maintenanceDueDay` of that month.

**201**
```json
{ "invoiced": 42, "skipped": 0, "totalAmount": 178500.0,
  "periodStart": "2026-08-01", "periodEnd": "2026-08-31" }
```

**Safe to repeat.** A second run for the same period reports every flat as `skipped` and bills
nobody. The guard is a partial unique index on `(community, unit, period)`, so it holds even if two
admins click at the same moment — not a check the API performs and could lose a race on.

**With no amount configured and none supplied, this returns `409` rather than falling back.** The
frontend's hardcoded `4250` is a demo value; adopting it silently would bill a real community a
number nobody chose.

**Vacant flats are not billed.** A real association bills the owner and an empty flat still owes
maintenance — but nothing in the product records ownership, so occupancy is the only signal that
exists. `DECISIONS_NEEDED.md` A14.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `409` | `conflict` | No maintenance amount configured or supplied |
| `422` | `request_validation_error` | `amount` ≤ 0 |

### `GET /api/v1/payments`

The collection log the Maintenance screen's subtitle promises. **Requires `ADMIN`.**

| Query | Type | Default | Notes |
|---|---|---|---|
| `q` | string ≤ 100 | — | Matches invoice number, title, flat, payer name, provider reference |
| `method` | string | — | `UPI` \| `Credit Card` \| `Net Banking` \| `Cash` \| `Cheque` \| `Bank Transfer` |
| `invoiceId` | uuid | — | One invoice's payments |
| `page` / `pageSize` | integer | `1` / `20` | 1–100 |

**200** — a `Page` of the payment objects shown under `GET /invoices/{id}`, newest first.

"What has been received" is a different question from "what does this flat owe" and needs its own
list; it is not derivable from the invoice list, because one invoice can carry several payments.

| Status | Code | Cause |
|---|---|---|
| `400` | `invalid_payment_method` | `method` outside the six values |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

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

### `GET /api/v1/amenities`

The catalogue grid. **Requires `ADMIN`.**

| Query | Type | Default | Notes |
|---|---|---|---|
| `q` | string ≤ 100 | — | Matches name, description, category and location |
| `category` | string | — | `Sports` \| `Fitness` \| `Recreation` \| `Events` \| `Utility` |
| `status` | string | — | `Active` \| `Inactive` \| `All` |
| `page` | int ≥ 1 | `1` | |
| `pageSize` | int 1–100 | `24` | |

**200**
```json
{
  "items": [
    {
      "id": "5c0b…",
      "name": "Clubhouse Gym",
      "description": "A fully equipped fitness centre with cardio, strength, and stretching zones.",
      "category": "Fitness",
      "location": "Clubhouse, Ground Floor",
      "image": "https://images.unsplash.com/photo-1534438327276…",
      "status": "Active",
      "isActive": true,
      "bookingMode": "Shared",
      "capacity": 24,
      "allowPrivateBooking": false,
      "requireApproval": false,
      "cleaningBuffer": 15,
      "maxBookingsPerResident": 5,
      "openingTime": "06:00",
      "closingTime": "22:00",
      "openingHours": "6:00 AM - 10:00 PM",
      "pendingRequests": 1,
      "outstandingDues": 1600.0
    }
  ],
  "total": 6, "page": 1, "pageSize": 24, "hasMore": false
}
```

`pendingRequests` counts requests awaiting a decision and `outstandingDues` sums the unpaid charges
against this amenity's bookings — both from the view. The mock stores `pendingRequests: 5` for an
amenity with one pending request and `outstandingDues: 4800` against 1600 in charges; a badge that
disagrees with the tab it links to is worse than no badge.

`capacity: null` means **no limit** (the Reading Lounge has none). `image: ""` is supported — the card
branches on it and renders a placeholder icon.

Inactive amenities are included. The resident screen renders them greyed out with "disabled by the
administrator" rather than hiding them, so filtering them away here would change what residents see.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | `status` is not one of the three values |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | The caller belongs to no community |

### `POST /api/v1/amenities`

Create an amenity. **Requires `ADMIN`.**

```json
{
  "name": "Squash Court",
  "description": "Single glass-backed court.",
  "category": "Sports",
  "location": "Sports Zone, West Wing",
  "image": "",
  "capacity": 2,
  "bookingMode": "Exclusive",
  "requireApproval": true,
  "isActive": true,
  "settings": { "openingTime": "07:00", "closingTime": "21:00", "securityDeposit": 250 }
}
```

Only `name` is required. A settings row is created from the defaults, so an amenity is never missing
one; `settings` may be omitted entirely or sent in part.

**201** — the full `AmenityDetail` (see `GET /amenities/{id}`).

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | Missing name, unknown category or booking mode, closing time not after opening, maximum duration shorter than minimum |
| `401` / `403` | | Not authenticated / not an admin |
| `409` | `conflict` | The community already has an amenity of that name |

### `GET /api/v1/amenities/{amenityId}`

One amenity with all five settings groups. **Requires `ADMIN`.**

**200** — every field of the summary above, plus:
```json
{
  "bookingSlotDuration": 60,
  "operatingHours": {
    "openingTime": "06:00", "closingTime": "22:00",
    "slotDurationMinutes": 60, "cleaningBufferMinutes": 15
  },
  "bookingSettings": {
    "mode": "Shared", "maxActiveBookingsPerResident": 5,
    "requireAdminApproval": false, "allowPrivateBooking": false,
    "allowRecurringBooking": false, "allowGuestBooking": true,
    "allowSameDayBooking": true, "enableWaitlist": false, "enableAutoApproval": false
  },
  "paymentSettings": {
    "bookingFee": 800.0, "securityDeposit": 300.0,
    "lateCancellationCharge": 0.0, "damageDeposit": 0.0,
    "refundPolicy": "", "currency": "INR"
  },
  "availabilitySettings": {
    "closedDays": ["Monday"], "maintenanceDays": [], "holidayOverrides": ["2026-08-15"],
    "temporaryClosure": false,
    "minimumBookingDurationMinutes": 60, "maximumBookingDurationMinutes": 180,
    "advanceBookingWindowDays": 30
  },
  "maintenanceSettings": {
    "interval": "Monthly", "defaultDurationMinutes": 60,
    "autoBlockSlots": false, "notes": ""
  },
  "version": 3,
  "createdAt": "2026-07-01T06:00:00+00:00",
  "updatedAt": "2026-07-29T11:20:00+00:00"
}
```

`bookingMode`, `requireApproval`, `cleaningBuffer` and `maxBookingsPerResident` appear **both** at the
top level and inside a settings group, because `normalizeAmenityRecord` writes both and different
components read different ones. The database stores each once; the duplication stops at the DTO.

`closedDays` and `maintenanceDays` are English day names on the wire and ISO day numbers in the
column. An unrecognised name in a write is dropped rather than stored — a `CHECK` rejects the whole
array for one bad element, which would turn a typo in one checkbox into a failed save of all thirty
settings.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such amenity in the caller's community |

### `PATCH /api/v1/amenities/{amenityId}`

Update the catalogue fields, the settings, or both. **Requires `ADMIN`.**

Same body as `POST`, every field optional. **A field left out is left alone**, which is not the same
as a field sent as `null` — `maxActiveBookingsPerResident: null` clears the limit.

The settings tab saves thirty fields on one click and they go in **one transaction**; splitting that
across two calls would let the second fail after the first had already been written.

**200** — the full `AmenityDetail`.

| Status | Code | Cause |
|---|---|---|
| `400` | `validation_error` | As `POST` |
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such amenity |
| `409` | `conflict` | Renaming onto an existing name |

### `PATCH /api/v1/amenities/{amenityId}/status`

The availability toggle on the card. **Requires `ADMIN`.**

```json
{ "isActive": false }
```

Its own route rather than a partial update, because the toggle sends one boolean and routing it
through a twelve-field patch is how a toggle ends up blanking a description.

**200** — the full `AmenityDetail`.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such amenity |

### `DELETE /api/v1/amenities/{amenityId}`

Delete an amenity nobody has booked. **Requires `ADMIN`.**

**204** — no body.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | No such amenity |
| `409` | `conflict` | The amenity has bookings on record. The message names the count and points at deactivating instead |

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
- **There is no visitor backend**, so `requireVisitorPreapproval` is read by nothing. Visitors are
  frontend dummy data — no table, no endpoint, not in any migration.
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

### `GET /api/v1/settings/modules`

The ten feature modules and this community's setting for each.

**Any authenticated role**, unlike the rest of this section. If module state ever gates navigation
then every shell needs it, and a resident learning that the marketplace is switched off discloses
nothing.

**200** — the `modules` object from `GET /settings`, on its own:

```json
{
  "items": [ { "key": "resident-management", "...": "..." } ],
  "total": 10,
  "enabledCount": 5,
  "enabledWithoutBackend": 1
}
```

**Not paginated, and that is deliberate.** There are exactly ten, fixed by `onboardingModules.js`.
A client that has to ask for page 2 of a ten-row fixed list is a client we made work for nothing.
Ordered by the catalogue's `sortOrder`, which is the order the onboarding wizard shows the same ten
cards in.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | Not authenticated |
| `404` | `not_found` | The caller belongs to no community |

### `PATCH /api/v1/settings/modules/{moduleKey}`

Turn one module on or off. **Requires `ADMIN`.**

```json
{ "enabled": true }
```

**One key at a time is the point.** Two admins toggling two different modules in the same minute must
not undo each other, which is exactly what a whole-set write does.

**200** — the one `ModuleSummary`, as it now stands.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | `moduleKey` is not in the catalogue, or the caller belongs to no community |
| `422` | `request_validation_error` | `enabled` missing, or `moduleKey` over 64 chars |

### `PUT /api/v1/settings/modules`

Replace the whole module set from the list of keys that should be on. **Requires `ADMIN`.**

```json
{ "moduleKeys": ["resident-management", "complaint-management", "amenities-booking"] }
```

**The shape the onboarding wizard already produces**: `enabledModules` is an array of enabled keys and
every other key is off by omission. That omission is honoured — a key dropped from the array is
written to `false`, not left at whatever it was, because "these are the modules that are on" is what
the array means.

**Every key is validated before anything is written**, so one typo does not leave a community
half-configured. Duplicates and casing are normalised.

**An empty array is legitimate and turns everything off.** A *missing* `moduleKeys` is a `422` rather
than the same thing — a caller who forgot the field would otherwise disable the whole product by
accident.

**200** — the full `ModuleCollection`.

| Status | Code | Cause |
|---|---|---|
| `401` / `403` | | Not authenticated / not an admin |
| `404` | `not_found` | A key is not in the catalogue, or the caller belongs to no community |
| `422` | `request_validation_error` | `moduleKeys` missing or `null`, or more than 50 entries |

---

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

## 13. Not yet implemented

Planned in the build order (`ADMIN_DASHBOARD_BUILD_PLAN.md` §4). Listed so the frontend team can see
what is coming and in what order — **none of these exist yet**, and calling them returns `404`.

Nothing from the build order is outstanding: steps 3–9 are all documented above.

What remains is not endpoints but wiring, tracked in `DECISIONS_NEEDED.md` §F: the migrations
`0010`–`0017` have not been applied to any database, the private Storage bucket
`complaint-attachments` does not exist yet (F2), and rate limiting (F3) and optimistic concurrency
(F4) are unowned.

Two whole surfaces the frontend has and the backend does not, neither of them in the admin-dashboard
build order: **visitors** and **notices beyond reading them**. Both are frontend dummy data with no
table of their own — `visitor-management` and `notice-board` report this as their `backendStatus` at
`GET /settings/modules` (§11).

**Adding a resident** has no dedicated endpoint and will not get one: it is
`POST /admin/invitations` (§4). The frontend's "Add Resident" creates one user record per phone plus
one shared invite; we mint one invite per phone instead, which is agenda item 5 and still open.

---

## 14. Changelog

| Date | Change |
|---|---|
| 2026-07-30 | **Merged `origin/main` @ `94556e5`; cut the surface to what the frontend calls.** 32 operations removed — every read the shared `GET /dashboard/snapshot` serves, the amenity CRUD their `/dashboard/amenities` serves, and the registration-review trio duplicating their `/admin/access-requests`. Adds §12: `POST /notices` and `POST /admins`. Two contract-wide changes: cookie-first auth with roles resolved from `community_memberships` instead of a JWT claim, and `X-CSRF-Token` required on every unsafe request. §5–§11 prose still describes removed endpoints — see [FRONTEND_WIRING_AUDIT.md](FRONTEND_WIRING_AUDIT.md). |
| 2026-07-30 | Build step 9 — Settings. Adds five endpoints plus six fields on `/billing-settings`. Records that the admin Settings screen has never persisted anything, so its field names are ours; that the four toggles belong to two different tables; that three of them are stored and acted on by nothing; and that module enforcement and community rename were deliberately not built. Answers A10 (community timezone). |
| 2026-07-30 | Build step 8 — Amenities. Adds twenty-two endpoints across the catalogue, bookings, approvals, the booking ledger and reports. Records that approval now covers a whole request rather than one day, that the cleaning buffer no longer blocks shared bookings, and that the frontend has two unrelated amenity models. |
| 2026-07-29 | Build step 7 — Money. Adds ten endpoints across invoices, payments, maintenance runs and billing settings. `dashboard.collection` stops being a placeholder. Records that the product has no maintenance amount anywhere, and that `isOverdue` is derived rather than stored. |
| 2026-07-29 | Build step 6 — Departments and staff. Adds nine endpoints plus `GET /complaint-categories`. Corrects the archive rule: the open-complaint guard is on `DELETE`, not on deactivation. |
| 2026-07-29 | `docs/openapi.yaml` added — the machine-readable companion to this file, generated from the code and checked in. |
| 2026-07-29 | Build step 5 — Complaints. Adds list, detail, `PATCH`, comments, read receipts and attachments. Retracts the invented SLA urgency multiplier (A3); documents the two competing SLA systems. |
| 2026-07-29 | Build step 4 — People. Adds `GET /admins`, `PATCH`/`DELETE /residents/{id}`, and the three `/registrations` endpoints. `dashboard.pendingRequests` and `residents[].email` stop being placeholders. |
| 2026-07-29 | Initial version. Documents the four read-only dashboard endpoints (build step 3) and the pre-existing auth and invitation endpoints. Records the unified error envelope introduced in the same change. |
