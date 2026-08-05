# HomeBandhu API reference

**Version:** v1 · **Base path:** `/api/v1` · **Last updated:** 2026-07-30

> ## The prose below now matches the generated spec
>
> §5–§11 have been pruned: the **34 sections documenting removed endpoints are gone**, and every remaining
> `###` heading corresponds to an operation that exists in [`openapi.yaml`](openapi.yaml). That is checked
> mechanically rather than by eye — normalising path parameters and diffing headings against the spec now
> reports zero stale and zero undocumented on our side.
>
> The live surface is **59 operations**: 24 from the auth/dashboard workstream, documented in
> [`../backend/API_REFERENCE.md`](../backend/API_REFERENCE.md), and our **35** below.
>
> **Two contract-wide changes that apply to every endpoint below.**
>
> 1. **Authentication is cookie-first.** A signed HTTP-only session cookie is the normal credential; the bearer
>    header still works, because their `_extract_token` accepts either. Role checks resolve from
>    `community_memberships` in Postgres, not from a JWT claim — the access-token hook that produced that claim was
>    deleted with the old baseline.
> 2. **Every unsafe request needs `X-CSRF-Token`.** All our writes now enforce it. Reads do not send or require it.
>    When no session CSRF cookie exists, the shared browser client first obtains the readable
>    `hb_preauth_csrf` cookie from `GET /auth/csrf`, then echoes it in the write request.
>    A missing or mismatched token is **403** with code `csrf_invalid`, and a wrong `Origin` is **403**
>    `csrf_origin_invalid`.
>
> **The database objects these endpoints need now exist.** Migrations `0019`–`0023` rebuilt the quarantined
> `0013`–`0017` onto the clean baseline: 10 views, 24 write RPCs, and columns on 11 baseline tables. A static
> check confirms every RPC and every column our repositories reference is created by some migration.
>
> **They have not been applied to any database.** No environment has run `0001` yet, so "exists in the migration"
> is as far as the guarantee goes. Applying them is the next step and it has to happen before anyone can say
> these endpoints work.


This document is the contract between the backend and the React frontend. It is
**normative**: if the code and this document disagree, that is a bug in one of them.

**[§14](#14-user-stories--endpoints) traces every endpoint back to the user story it serves**, and
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
protecting, the shape of the gaps in §14. Read the spec to write a client; read this to change one.

Everything a generator cannot infer — error responses, story traceability, and descriptions for the
handlers with no docstring — is supplied by
[`backend/scripts/api_annotations.py`](../backend/scripts/api_annotations.py), one table the
exporter applies. It exists because roughly half these operations sit in the other workstream's
routers, which are not ours to edit.

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

This envelope is in [`openapi.yaml`](openapi.yaml) as `ErrorResponse`, and **every one of the 70
operations declares the specific codes it can return**, each pointing at a shared
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

### `POST /api/v1/auth/refresh`

Exchange a refresh token for a new session ("remember me"). No authentication.

**Request** — `{ "refresh_token": "v1.Mr7..." }` · **200** — same `Session` shape as above.

| Status | Code | Cause |
|---|---|---|
| `401` | `authentication_error` | Refresh token invalid, expired or revoked |

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

## 5. Admin dashboard

**No endpoints of ours live here.** Every one this section documented was removed by the frontend wiring audit,
because their `GET /dashboard/snapshot` already serves the same reads and the frontend already calls it. The
removals were `GET /dashboard/admin`, `GET /communities/current`, `GET /notices` and `GET /residents`. See
[FRONTEND_WIRING_AUDIT.md](FRONTEND_WIRING_AUDIT.md) §3 for the evidence behind each one, and
[`../backend/API_REFERENCE.md`](../backend/API_REFERENCE.md) for the snapshot's contract.

The heading is kept so the section numbering below does not shift; renumbering would break every link and
reference into §7–§15 for no gain.

### 5.1 Live updates — `GET /dashboard/events`

Owned by the dashboard workstream, documented here because our migrations feed it and because it is how every
write in §7–§12 reaches an open screen without a matching read endpoint.

**Transport: server-sent events** (`text/event-stream`), same-origin, over the browser's native `EventSource`.
No Supabase key or provider token reaches the browser. Auth is the session cookie; the stream is bound to the
community on the caller's verified membership, so a client cannot widen its own scope by replaying someone
else's `Last-Event-ID`.

Rationale and the rejected alternatives — Supabase Realtime, `LISTEN`/`NOTIFY`, client polling — are in
[ARCHITECTURE.md § Live updates](ARCHITECTURE.md#live-updates).

**Request**

| Header | Required | Meaning |
|---|---|---|
| `Last-Event-ID` | no | Resume point. The stream backfills everything after this id for the caller's community before attaching to the live feed, so a reconnect across a network blip loses nothing. Non-numeric values are treated as `0`. |

**Frames**

```
id: 4127
event: access_request.created
data: {"request_id":"…","applicant_name":"Asha R","requested_relationship":"tenant","status":"pending","created_at":"2026-07-30T09:14:02Z","pending_count":3}
```

`data` is always JSON. A comment frame (`: keepalive`) is sent every 20s so proxies do not reap an idle stream.

| Event | When | Payload |
|---|---|---|
| `access_request.created` | someone asks to join the community | `request_id`, `applicant_name`, `requested_relationship`, `status`, `created_at`, `pending_count` |
| `access_request.decided` | a request is approved, rejected or blacklisted | `request_id`, `applicant_name`, `from`, `to`, `pending_count` |
| `dashboard.refresh` | any write to one of 12 domain tables | `{"table": "…"}`, or `{"resync": true}` if this connection fell behind and events were dropped |

**Contract notes**

- Delivery is **at-most-once**, and the payload is a hint. `GET /dashboard/snapshot` is authoritative; treat
  every event as "re-read", which is what `dashboard.refresh` means literally.
- `pending_count` is the community's live count of pending join requests, included so a badge or toast can
  update without a round trip.
- Status codes: `200` (stream opens), `401` (no session), `403` (no active membership).

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

## 14. User stories → endpoints

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

### 14.1 Scope, stated once

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

### 14.2 Coverage

| | Served | Partial | None |
|---|---|---|---|
| §1 Administrative staff (6) | 3 | 3 | 0 |
| §2 Resident (12) | 0 | 8 | 4 |
| §3 Security manager (6) | 0 | 1 | 5 |
| **Total (24)** | **3** | **12** | **9** |

The shape of that table is the honest summary of this branch: **the administrator's stories are
substantially built, the resident's are built but unreachable, and the security manager's are not
started.** Not one resident story is fully served, and the reason is almost never a missing
capability — it is a missing delivery path. Three separate resident stories are blocked on the same
absent push transport, and three more are blocked on one projection dropping fields our own
endpoints wrote (§14.4).

### 14.3 Administrative staff

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
| [`GET /dashboard/events`](#51-live-updates--get-dashboardevents) | SSE; `dashboard.refresh` fires on writes to 12 tables, including bookings |
| `GET /dashboard/snapshot` | The authoritative re-read every event asks for |

**Shortfall:** the story names three consumers — resident app, admin portal, reports. The stream
serves the **admin portal only**. There is no resident client subscribed to it, and reports are
computed per request rather than pushed. Delivery is also at-most-once by design: correctness comes
from re-reading the snapshot, not from the event.

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

### 14.4 Resident

Read this section against one fact: **no resident-facing client calls this API.** The frontend in
this repo is the admin dashboard. So "partial" below almost always means *the data is right and
nothing shows it to a resident* — a materially different problem from *the backend cannot do it*,
and a much cheaper one.

#### US-2.1 / US-2.2 — Visitor notifications and pre-approval — **partial**

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

**Push is a separate and larger gap.** Both stories are fundamentally about *notification delivery*,
and this system has no push transport at all: no FCM/APNs registration, no device token table, no
web-push subscription. SSE requires an open browser, which is the precise thing the interviewee said
they should not need. Nothing in the admin-dashboard build order provides one.

#### US-2.3 — One-tap quick access — **none**

A client concern. Recorded rather than dismissed because the widget it describes needs endpoints
that do not exist (visitor approve/deny), so it is blocked on US-2.1 regardless of client work.

#### US-2.4 — Notifications for notices — **partial**

| Endpoint | Role |
|---|---|
| [`POST /notices`](#121-post-notices--post-a-notice) | Publishes immediately; fires the `notices` SSE trigger |

**Shortfall:** the same missing push transport as US-2.1. The event reaches connected admin
browsers. A resident who has not opened the app learns nothing — which is the story verbatim.

#### US-2.5 — Simple complaint submission with priority — **none**

**A resident cannot raise a complaint through this API.** There is no `POST /complaints`. Creation
was never in the admin-dashboard build order, because the admin dashboard reads complaints rather
than filing them.

**The priority selector has nowhere to write.** `complaints` has no priority column — not in the
baseline, not in `0020`. The only `priority` in the schema is on `work_orders`, which is a different
thing. The snapshot still reports an `urgency` on every complaint:
`dashboard_service.py:86` computes it as `str(row.get("priority") or "Medium").title()`, from a
column the non-legacy query does not select and the database does not have — so **every complaint
reports `Medium`, permanently.** This story needs one column before it needs an endpoint.

#### US-2.6 — Complaint status tracking with history — **partial**

| Endpoint | Role |
|---|---|
| [`PATCH /complaints/{complaintId}`](#patch-apiv1complaintscomplaintid) | Writes the status **and its timeline entries in one transaction** |
| [`POST /complaints/{complaintId}/comments`](#post-apiv1complaintscomplaintidcomments) | `resident` visibility appears on the timeline; `internal` never does |
| `GET /dashboard/snapshot` → `complaints[]` | Returns `status`, `comments[]` and `history[]`, **filtered to the caller's own complaints** for a non-admin |

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
trigger. **The events exist and nothing delivers them.** Same missing transport as US-2.1 and
US-2.4; this is one gap, not three.

#### US-2.8 — Complaint accountability — **partial**

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

**Shortfall: "verified" is nobody's job.** No field records who last confirmed a number, or when.
A directory nobody is accountable for re-checking goes stale exactly as the interviewee described,
and the API cannot currently tell a maintained entry from an abandoned one.

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

#### US-2.12 — Reliable booking payment confirmation — **partial**

| Endpoint | Role |
|---|---|
| [`POST /amenity-bookings/{occurrenceId}/payments`](#post-apiv1amenity-bookingsoccurrenceidpayments) | Records the payment against the booking |
| [`POST /invoices/{invoiceId}/payments`](#post-apiv1invoicesinvoiceidpayments) | The maintenance equivalent |

The failure the interviewee described — *money deducted, no booking* — cannot happen **within this
API**, because the payment and the booking state are one database transaction and `paymentStatus` is
derived from the payment rows rather than set alongside them.

**Shortfall: no payment gateway is integrated.** These endpoints record a payment somebody else
already took. The interviewee's failure happens between the gateway and the backend, which is
precisely the seam this API does not yet have. Closing the story means a webhook and an idempotency
key — `idempotency_records` exists in the schema and nothing writes to it.

### 14.5 Security manager

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
express, since a pass belongs to one request. No endpoint issues, scans or revokes any of it.

**US-3.2 has a trigger point ready.** `POST /amenities/{amenityId}/bookings` and the approve route
are exactly where "prepare guest access on booking" would hook in, and `0007`'s outbox already fires
on amenity tables. What is missing is the visitor write endpoint it would call — so US-3.2 is
blocked on US-2.2, not on amenities.

**US-3.6, stated fairly.** Retention is *not* a gap: nothing this backend writes is ever deleted or
aged out, complaint and booking history are append-only, and the ledger reconstructs any past state
from its event stream. So *"records older than three months are unavailable"* is already solved for
everything we store. What is missing is (a) any gate-operations data to retain and (b) the
downloadable report — the same export gap as US-1.6.

### 14.6 Endpoints that serve no story, and why that is fine

**36 of the 70 operations map to no story in the document.** Not a defect — the team wrote stories
about pain points in an existing product, not about the plumbing every product needs.

| Group | Ops | API type | Why no story |
|---|---|---|---|
| `/auth/*` | 16 | Functional | Nobody writes a user story about signing in until it breaks |
| `/access-requests/*`, `/admin/access-requests/*` | 7 | Feature | Joining a community; the interviews were with people already in one |
| `/invitations/*`, `/admin/invitations` | 3 | Feature | Same |
| `/communities/*`, `/onboarding/community` | 3 | Feature | Founding a community — a once-per-community act |
| `/dashboard/amenities` `POST` · `PUT` · `DELETE` | 3 | Master data | Amenity catalogue upkeep; the stories assume amenities already exist |
| `/settings`, `/billing-settings` | 3 (of 4) | Configuration | Configuration behind other features |
| `/health` | 1 | Non-functional | Platform liveness, deliberately outside `/api/v1` |

**The API type is the point of this table, not the absence.** Each of these operations carries
`x-no-user-story` in [`openapi.yaml`](openapi.yaml), stating `Not covered by user story` and then
what the operation *is*. `Functional`, `Configuration`, `Master data` and `Non-functional` are
plumbing, and their absence from the story set is expected. **`Feature` is not**: 13 operations here
are user-facing capability nobody wrote a story for. That is a finding about the story set, not
about the API, and §14.7 is where it turns into work.

> **This number was 33 and was wrong.** The groups above always summed to 36; the earlier total was
> arrived at by subtracting the endpoints §14.3–§14.5 name in their tables, which silently assumed
> that every operation not listed as unmapped was mapped. Three were neither — the amenity catalogue
> writes, now their own row. The error survived a hand review and did not survive machine-checking
> the same claim: the exporter's coverage guard requires a verdict per operation, and three
> operations had none. **34 operations serve at least one story, 36 serve none, and 34 + 36 = 70.**

The one worth flagging: **`GET /settings` is the only endpoint that reports its own gaps.** Its
`modules[]` carries a `backendStatus` per module, and `visitor-management`, `notice-board`,
`security-gate-management` and `parking-management` all report themselves unimplemented. That is
the machine-readable form of half this matrix, and it is already wired.

### 14.7 What the matrix says to do next

Ordered by cost against value, not by story number.

| # | Action | Unblocks | Size |
|---|---|---|---|
| 1 | Stop the snapshot dropping `assignee`, `dueAt` and `progress_percent` (§14.4) | **US-2.6, US-2.8** | Two lines, dashboard workstream |
| 2 | Restore `PATCH /residents/{id}` | **US-1.4** | Recoverable from git history |
| 3 | Add `complaints.priority` | US-2.5 (half) | One column; the read already expects it |
| 4 | Add `notices.effective_at` | US-2.11 (half) | One column, one field |
| 5 | Add `departments.building_id` | US-2.10 | One column, one filter |
| 6 | Build the visitor write endpoints | US-2.1, US-2.2, US-3.2 | A surface |
| 7 | Choose a push transport | US-2.1, US-2.4, US-2.7 | An architecture decision, not a task |
| 8 | Add CSV export | US-1.6, US-3.6 | Small, and asked for twice |

**Items 1–5 are five small changes that close or half-close five stories.** They are the whole
argument for keeping this matrix. None would have been found by reading the code, because none of
them is a bug in any one file: three are fields written by one workstream and dropped by another,
and two are single missing columns behind features that otherwise work. The expensive items — 6 and
7 — were already known.

**Item 7 is the largest single lever in the table.** Four stories (US-2.1, US-2.4, US-2.7, and
US-2.3 downstream) reduce to *"tell the resident without making them open the app"*, and none of
them can be closed by any amount of backend work until something can deliver a message to a device.
It is worth deciding before more endpoints are written, not after.

---

## 15. Changelog

| Date | Change |
|---|---|
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
