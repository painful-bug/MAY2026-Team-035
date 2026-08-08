# Admin dashboard backend — design and reasoning

> **What this document is.** The *why* behind the admin-dashboard backend, written
> after the fact for the backend team. `API.md` says what each endpoint does;
> `ARCHITECTURE.md` says how the process is wired; the migrations say what the
> tables are. None of them say why any of it was built that way, which means the
> next person to touch it has to infer intent from code — and inferred intent is
> how a deliberate constraint gets "cleaned up" by someone who thought it was an
> accident.
>
> Read this before changing the layering, the authorization seam, or the
> read/write split. Its companion is
> [`RESIDENT_BACKEND_DESIGN.md`](RESIDENT_BACKEND_DESIGN.md), which applies the
> same paradigms to the resident portal. [`README.md`](README.md) explains what
> this folder is for and how to add to it.

---

## 1. The shape, in one paragraph

An HTTP request enters a **router**, which owns the wire contract and nothing
else. The router calls a **service**, which owns policy — who may do this, what
must be true first, what it means. The service calls a **repository**, which owns
the conversation with Postgres and knows no policy at all. Reads land on a
**database view**; writes land on a **`SECURITY DEFINER` RPC**. Nothing above the
repository knows whether Supabase is PostgREST or raw SQL, and nothing below the
service knows what an HTTP status code is.

That is four layers, and the reason for each boundary is a specific failure it
prevents. They are given below in the order they matter.

---

## 2. Authorization: tenancy is read from the database, never from a token

This is the single most important decision in the backend and the one most
likely to be "simplified" by someone in a hurry.

`app/api/deps.py:103` — `get_active_membership` — resolves the caller's community
and role by querying `community_memberships` on every request:

```python
rows = (get_service_client().table("community_memberships")
        .select("id, community_id, role, department_id")
        .eq("profile_id", principal.user_id)
        .eq("status", "active")
        .is_("ended_at", None) ...)
```

The identity JWT proves *who you are*. It does not prove *what you may do here*.
Those are different facts with different lifetimes, and conflating them is the
classic multi-tenant privilege bug:

- **Roles change mid-session.** An admin demoted at 10:00 keeps a valid token
  until it expires. If the role rode in the token, they would keep admin powers
  for the remainder of that window. Reading from the database makes revocation
  take effect on the next request.
- **A token is a bearer artifact.** Anything inside it is a claim the client
  transports. Tenancy derived from it is tenancy the client had custody of.
- **One human, several communities.** `is_default_community` picks the active
  one. A token minted for one community would silently authorize the other.

The cost is one indexed lookup per request. That is the price of the property,
and it is cheap. **Do not cache the membership into the token to save it.**

`require_membership_role(*roles)` layers on top and checks the *resolved*
membership, not a claim. `require_admin` is the admin-dashboard alias.

### CSRF, and why it exists here at all

The session is an `HttpOnly` cookie, which the browser attaches automatically —
including on requests a hostile page triggers. So every unsafe method carries
`require_csrf_unsafe`: a double-submit token compared against the cookie *and*
against a token derived from the access token itself (`deps.py:79-100`). The
second comparison is what stops a valid-but-stale CSRF cookie from a previous
session being replayed.

Cookies were chosen over `Authorization: Bearer` deliberately: a bearer token
must live somewhere JavaScript can read it, which makes every XSS a full session
theft. `HttpOnly` trades that for CSRF, and CSRF has a complete, cheap defence.
That trade is the reason **no Supabase key or provider token is ever handed to
the browser** — the constraint `ARCHITECTURE.md` calls out, and the reason
Supabase Realtime was rejected for live updates.

---

## 3. Reads through views, writes through RPCs

Two rules, each earning its keep.

### Reads: one view per screen

`department_overview`, `department_staff_overview`, `invoice_overview`,
`payment_overview`, `amenity_overview`, `amenity_booking_overview`,
`amenity_ledger_overview`, `amenity_ledger_summary`, `community_module_overview`,
`community_settings_overview`, `pending_access_request_overview`.

A dashboard row is an aggregate — a department with its head, its staff count,
its categories and its open-complaint count comes from five tables. The
alternative to a view is either N+1 round trips from Python, or a hand-rolled
join assembled in the repository. Both put a query planner in the application.

Putting the shape in a view means:

- **The join is planned by Postgres**, with the statistics to do it well.
- **The shape is one artifact**, so a column added for the UI is added once, not
  in a repository *and* a serializer *and* a test fixture.
- **It is inspectable.** A wrong number on a dashboard can be reproduced with
  one `select` in the SQL editor, without running Python.

The view is a *projection for a screen*, not a general-purpose abstraction. When
a screen's needs diverge, add a view — do not grow one view sideways with
optional columns until it serves three screens badly.

### Writes: one RPC per intent, `SECURITY DEFINER`

`create_department`, `update_department`, `delete_department`,
`sync_department_staff`, `apply_department_head`, `issue_invoice`,
`record_payment`, `save_amenity`, `request_amenity_booking`,
`approve_amenity_booking`, `cancel_amenity_occurrences`, `record_amenity_payment`,
`save_community_settings`, `blacklist_access_request` — and the rest.

The reason is **atomicity**, and it is not theoretical. Creating a department
writes `departments`, `department_categories`, `complaint_categories` and
`staff_assignments`. Through PostgREST that is four HTTP calls with no
transaction around them. A failure on the third leaves a department with
categories and no staff, which no screen can display and no code path can
clean up.

A `plpgsql` function is one transaction. It either all happened or none of it
did. Everything else follows:

- **Invariants live next to the data.** `record_payment` refusing an overpayment
  is enforced where the balance is, so a second caller — a future mobile client,
  a support script — cannot bypass it.
- **Concurrency is the database's problem**, which it is good at. The
  `exclude using gist` constraint on `amenity_bookings` makes double-booking
  *impossible* rather than *unlikely*: two simultaneous requests for the same
  slot cannot both win, no matter how the application is scheduled.
- **The error is typed.** `app/core/pg_errors.py` maps SQLSTATE to HTTP, so a
  unique violation becomes a 409 with a stable code rather than a 500.

`SECURITY DEFINER` is what lets the function enforce a rule the caller could
otherwise skip. It is also why each one re-checks the caller's membership
internally (`is_community_admin`) — a definer function that trusts its arguments
is a privilege-escalation primitive.

---

## 4. Migrations are additive, and never edited

`0001_baseline.sql` is not ours. `0018`–`0024` sit on top of it and only ever
`add column if not exists`, `create table if not exists`,
`create or replace function`.

This is not politeness, it is the only workable rule when two workstreams share
a schema and neither controls the other's deploy order. An edited migration is a
migration that has already run somewhere with different content, which makes the
file a lie about the database. Idempotent additive DDL can be re-run, applied out
of order, and merged without conflict.

The corollary that bites: **we cannot fix a baseline mistake by editing the
baseline.** `complaints` has no priority column; the fix is a new migration that
adds one, not a change to line 69 of `0001`.

Every migration was statically validated with `pglast` before commit. **None has
been executed against any database** — including `0001`. Applying them is the
user's to do through the Supabase SQL editor. Treat "the migration exists" and
"the column exists" as separate facts until someone confirms the second.

---

## 5. Schemas: the wire shape is not the table shape

`app/domain/*_schemas.py` holds pydantic models that are deliberately *not*
mirrors of the tables. The API speaks `camelCase` because the consumer is a
JavaScript client; the database speaks `snake_case` because it is Postgres. The
translation happens once, in the domain layer, rather than being negotiated
per-endpoint.

More importantly, the wire model is a **contract that can stay stable while the
table moves**. `progress_percent` becoming a derived value later should not be an
API break. A model that is a table mirror makes every schema change a client
change.

`Page[T]` wraps collections rather than returning a bare array — a bare array has
nowhere to put a cursor when the list grows past one response, and retrofitting
pagination onto a shipped array shape is a breaking change.

---

## 6. Errors: one envelope, declared by the application

Every failure is `ErrorResponse` → `ErrorBody{code, message, details?}`, defined
as pydantic models in `app/core/exceptions.py` and installed as the router's
default responses in `app/main.py`.

- `code` is stable and machine-readable. **Clients branch on it.**
- `message` is prose, safe to show a user, and may be reworded without notice.
- `details` carries field-level failures and is populated only by validation.

The split exists because a client that branches on message text breaks when
someone improves the wording. Giving it a code it can rely on is what makes the
prose free to change.

The models live in the application, not in the spec generator. That ownership
line was settled the hard way (see §8) and is the rule: **the code declares the
contract; the generator only describes it.**

---

## 7. Live updates: an outbox, polled once per process

Full reasoning is in [`ARCHITECTURE.md`](../ARCHITECTURE.md#live-updates); the
design summary is that `AFTER` triggers write to an `sse_events` outbox, one
in-process poller reads it on a global cursor every 500ms, and
`GET /dashboard/events` fans rows out to subscribers by `community_id`.

The property that matters: **cost scales with events, not with viewers.** One
indexed range scan serves every connected admin. Client polling — the obvious
alternative — scales the wrong way round.

Three limits worth knowing before relying on it:

- **The payload is a hint, never truth.** An event says "re-read"; the snapshot
  is authoritative. Delivery is at-most-once by design, which is only safe
  *because* of that rule.
- **Trigger coverage is the 12 tables `0007` names**, plus `access_requests` via
  `0024`. The tables `0018`–`0023` added carry no trigger, so a second admin with
  the same screen open will not see those writes until they act or reload.
- **The stream is scoped to a community, not to a role.** `GET /dashboard/events`
  is guarded by `get_active_membership` — any active member — and the hub fans
  out by `community_id` alone. Any member of a community therefore receives every
  event in it, including `0024`'s `access_request.created`, which carries an
  applicant's name. Nothing exploits this today because only the admin frontend
  connects, but it is a property of the design and not an accident of who is
  wired up. The fix is the audience column in
  [`RESIDENT_BACKEND_DESIGN.md` §10.2](RESIDENT_BACKEND_DESIGN.md#102-audience-scoping-the-outbox),
  and it is the first item in that plan's build order.

---

## 8. The OpenAPI spec is generated, never hand-written

`docs/openapi.yaml` is produced by `backend/scripts/export_openapi.py`, which
imports the live app and calls `app.openapi()`. There is no hand-maintained
`paths:` section. A hand-written spec describes the API someone remembers
building; a generated one describes the API that exists.

`--check` fails on drift and a test runs it, so the spec cannot silently rot.

The things a generator cannot infer — which errors an operation can actually
raise, which user story it serves, a description for an endpoint whose docstring
lives in another workstream's router — come from `backend/scripts/api_annotations.py`,
a side-table keyed by `(method, path)`. It exists because ~half the operations
live in routers this workstream must not edit, and annotating from outside was
the only way to document them without touching their code.

Its guard runs **both directions** and raises `SystemExit`: an annotation with no
live operation fails the build, and a live operation with no annotation fails it
too. That is what stops the side-table becoming a graveyard of renamed routes.

Two rules learned by getting them wrong:

- **Union, never replace.** The exporter takes the union of derived error codes
  and codes the application itself declares. An earlier version deleted
  undeclared codes, which would have silently stripped a blanket 422 the router
  layer had just deliberately added. A generator must never narrow a claim the
  application makes.
- **Describe, do not define.** The exporter contributes prose to schemas the app
  owns. It once carried its own hand-written error models, which collided with
  the real ones the moment the application grew them.

Story traceability uses `x-user-stories` / `x-no-user-story`, which are OpenAPI
specification extensions — the standard's own mechanism, so the spec stays
Swagger-valid. Operations with no story carry the literal status
`Not covered by user story` plus an `api-type` from a fixed five-term vocabulary
(Feature, Functional, Configuration, Master data, Non-functional), because "no
story" for a health check and "no story" for a user-facing feature mean opposite
things.

---

## 9. What this workstream deliberately did not do

Recorded so the gaps read as decisions rather than oversights.

| Not done | Why |
|---|---|
| Edit the auth seam | Owned by a parallel workstream. `handle_new_user`, `is_admin`, `invitation_service`, `auth_service`, `core/tokens`, `core/security` are theirs. |
| Edit the frontend | The frontend is a dummy-data demo and its team owns it. One scoped exception was granted, for `PendingRegistrations.jsx`. |
| Apply any migration | No credentials should reach this workstream. The user applies them. |
| Make the invite token optional | It is a mandatory second factor. Redemption binds to the authenticated account's email. |
| Adopt Supabase Realtime | It requires giving the browser a Supabase key, reversing §2's constraint. A security trade to make on purpose, not a performance tweak. |
| Narrow the blanket 422 | `422` is now declared on 69 operations where only 33 have a traceable validation path. Over-claiming an error is cheaper than an exporter overruling a router it does not own. The auth workstream's call. |
| Take money | `record_payment` records a payment that already happened elsewhere — offline reconciliation, `provider = 'offline'`. It is not a gateway and must not be mistaken for one. The resident-side simulated gateway is [§11 of the resident document](RESIDENT_BACKEND_DESIGN.md#11-the-simulated-payment-gateway), and it writes `provider = 'simulator'` precisely so the two never blur. |

---

## 10. If you are extending this

1. **New read?** Add a view. Do not join in Python.
2. **New write touching >1 table?** Add an RPC. Do not sequence PostgREST calls.
3. **New endpoint?** Router → service → repository. If the router contains an
   `if` about *who* the caller is, that belongs in the service.
4. **Never** put the community id in a request body. It comes from the resolved
   membership. A body field is a tenancy bypass with extra steps.
5. Regenerate the spec (`python scripts/export_openapi.py`) and add the
   annotation entry — the build fails without it, by design.
6. Log the change and its reasoning in [`CHANGE_LOG.md`](../CHANGE_LOG.md).
