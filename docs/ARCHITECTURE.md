# Current architecture

This document describes the implementation committed in `94556e5`. It replaces
the pre-implementation “current state” assessment in
`plans/AUTH_REGISTRATION_IMPLEMENTATION_PLAN.md` as the architecture reference.

The detailed, source-backed class diagram is available as editable
[PlantUML source](diagrams/HomeBandhu-Architecture-Classes.puml) and a rendered
[PNG](diagrams/HomeBandhu-Architecture-Classes.png).

## Component and trust-boundary diagram

```mermaid
flowchart LR
    User["Resident, administrator, security, or worker"] --> UI

    subgraph Browser["React/Vite browser — no Supabase SDK or provider tokens"]
        UI["Routes and portal pages"]
        AuthStore["authStore\nserver session state"]
        Bootstrap["DashboardDataBootstrap"]
        Cache["appStore\nephemeral render cache"]
        Amenity["Amenity service"]
        UI --> AuthStore
        UI --> Bootstrap
        Bootstrap --> Cache
        UI --> Amenity
    end

    subgraph API["FastAPI — same-origin /api/v1"]
        Auth["Auth router/service\nGoogle PKCE, cookies, CSRF"]
        Registration["Community, onboarding,\naccess-request, invitation routers/services"]
        Dashboard["Dashboard router/service\nsnapshot and SSE"]
        Repositories["Repository layer\nSupabase/PostgREST and RPC adapters"]
        Workers["Background workers\npush sender, job dispatcher"]
        Auth --> Repositories
        Registration --> Repositories
        Dashboard --> Repositories
        Workers --> Repositories
    end

    UI -->|"fetch with HttpOnly cookies\nCSRF on unsafe methods"| Auth
    UI -->|"registration and invitation requests"| Registration
    Bootstrap -->|"GET dashboard/snapshot"| Dashboard
    Bootstrap -->|"EventSource dashboard/events"| Dashboard
    Amenity -->|"authorized amenity CRUD"| Dashboard

    Auth -->|"PKCE authorization/exchange"| SupabaseAuth["Supabase Auth"]
    SupabaseAuth --> Google["Google OAuth"]
    Repositories --> DB["Supabase Postgres\n0001_baseline.sql"]
    DB --> Outbox["sse_events\ndashboard.refresh outbox"]
    Outbox --> Dashboard
    DB --> Queue["dispatch_tasks\ndue-time queue"]
    Queue -->|"claim under a lease,\nthen fire_dispatch_task"| Workers
```

**The workers have no arrow from the browser, and that is what they are for.**
Both run on a timer with no request behind them, on the service client rather
than a caller's — the push sender to reach a resident with nothing open, the job
dispatcher to act at a time nobody is present for. Neither decides anything: the
sender sends what `claim_push_batch` hands it, and the dispatcher calls
`fire_dispatch_task` and records what happened. **Every decision either of them
causes is made in SQL**, which is not a stylistic preference — every notification
in this system is written inside the transaction that caused it, and a worker
deciding things in Python would have to give that up.

## Runtime sequence for authenticated dashboards

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as FastAPI
    participant D as Postgres

    B->>A: GET /auth/session (HTTP-only cookie)
    A-->>B: Safe identity + active membership context
    B->>A: GET /dashboard/snapshot
    A->>D: Tenant-scoped database projection
    D-->>A: Community records
    A-->>B: Normalized dashboard snapshot
    B->>B: hydrateDashboard(render cache)
    B->>A: GET /events (EventSource)
    D->>D: Domain insert/update/delete
    D->>D: Trigger writes sse_events(dashboard.refresh)
    A-->>B: dashboard.refresh SSE event
    B->>A: GET /dashboard/snapshot
    A-->>B: Refreshed authoritative snapshot
```

## Live updates

**What we use: server-sent events over a Postgres outbox, fanned out by a
single in-process poller.** Concretely, three parts:

| Part | Where | Job |
| --- | --- | --- |
| Outbox | `sse_events` + `AFTER` triggers | A domain write records that it happened, on the tables carrying a trigger (see *Guarantees and limits*). |
| Poller | `app/core/realtime.py` | One task reads the outbox on a global cursor and routes rows to subscribers by `community_id`, then by audience. |
| Transport | `GET /events` | Same-origin `text/event-stream`; the browser uses the native `EventSource`. `GET /dashboard/events` is a deprecated alias for the same handler. |

The cost model is the point. The poller is **per process, not per client**, so
one indexed primary-key range scan every 500ms serves every connected admin in
every community; adding viewers adds an in-memory queue and nothing else. When
nobody is connected it does not query at all. Each connection costs one asyncio
task, not one OS thread.

That last distinction is not academic. The earlier implementation was a
*synchronous* generator that called `time.sleep(5)`. Starlette iterates sync
generators in the anyio worker threadpool, so every open dashboard held one of
that pool's 40 threads for the entire life of the stream — and because the pool
is shared with all other synchronous work, the 41st dashboard would not merely
lag, it would starve unrelated requests across the whole process.

### Audience scoping

Community was never a sufficient scope. The endpoint's guard is *any active
membership* — it always was — and until `0028_event_audience.sql` the hub fanned
out on `community_id` alone, so a resident who opened the stream received
`access_request.created` for their neighbours, applicant name and all. Nothing
exploited it because no non-admin client connected; the resident portal is what
would have made it exploitable, so the fix landed first.

Every row now declares who may receive it:

| `audience` | Delivered to | Used by |
| --- | --- | --- |
| `community` | every subscriber in the community | genuinely community-wide news |
| `role` | subscribers whose role is in `audience_roles` | `dashboard.refresh`, `access_request.*` — both `{admin, manager}` |
| `member` | the subscriber matching `recipient_membership_id` | anything addressed to one person |

A `check` constraint makes the three shapes mutually exclusive and complete, and
the reader delivers to nobody anything it cannot classify. The point of pairing
those two is that a malformed row is unwritable rather than silently
undeliverable — guessing `community` would be a disclosure.

`_Subscriber` carries `membership_id` and `role` alongside `community_id`, all
three read from the membership the endpoint resolved out of Postgres. The
existing guarantee that a client cannot widen its own stream by replaying
someone else's `Last-Event-ID` therefore extends to the audience unchanged:
both derive from the same verified value, and the resume point only ever seeks.

There is a load argument as well as a privacy one. Twelve tables emit
`dashboard.refresh` on every row change and that frame means *re-read your
snapshot* — a snapshot a resident would be refused. Point five hundred flats at
a community-wide firehose and one unrelated write costs five hundred fetches.

### Why not the alternatives

- **Supabase Realtime** is the native answer and is where this should end up.
  It is a browser-side WebSocket subscription, so adopting it means handing the
  frontend a Supabase key and moving tenant filtering into RLS. That reverses
  the deliberate decision this endpoint exists to enforce — *no provider token
  is exposed to the browser* — so it is a security trade to make on purpose,
  not a performance tweak to slip in. Revisit when RLS covers every table the
  dashboard reads.
- **`LISTEN`/`NOTIFY`** would be true push with no polling at all. It needs a
  direct Postgres connection, and the service holds only Supabase's PostgREST
  client — no `DATABASE_URL`, no driver. It would mean a new dependency, a new
  secret, and a long-lived connection outside the pooler, to remove a latency
  we do not currently notice.
- **Client polling** was what the dead frontend handlers effectively did. It
  scales with viewers rather than with events, which is the wrong way round.

### Guarantees and limits

- **Ordering** is by `sse_events.id` within a community.
- **Reconnects** are covered: the browser resends `Last-Event-ID`, and the
  stream backfills from the database before attaching to the live feed. The
  backfill applies the audience filter twice — once in the query, so a burst of
  admin traffic cannot fill the 100-row page and hide a resident's own events
  behind it, and again in Python, so a mistake in the hand-written PostgREST
  clause can only lose an event and never leak one.
- **Slow consumers** degrade rather than block. A connection more than 64
  events behind stops receiving detail and is sent a resync frame:
  `dashboard.refresh` with `{"resync": true}` for an admin or manager, whose
  listener already handles it by re-fetching the snapshot, and `stream.resync`
  for every other role — the same instruction, under a name that does not claim
  to be about the admin dashboard. The topic is chosen per subscriber because
  the admin listener already ships and this workstream does not edit frontend
  code.
- **The hub is process-local.** Every worker polls independently and each
  serves its own connections correctly, but this scales by adding queries per
  worker. At more than a handful of workers, move to Supabase Realtime rather
  than raising the poll interval.
- **Delivery is at-most-once** and the payload is a hint, never the source of
  truth. The snapshot is authoritative; an event only says "re-read".
- **Trigger coverage is the 12 tables `0007` names**, plus the specific
  `access_requests` topics `0024` adds. The tables introduced by `0018`–`0023`
  — community settings, billing settings, the two category tables, and the
  amenity guest/charge/financial-event tables — carry no trigger, so a write to
  one of them pushes nothing. The admin who made the change sees it because
  their own request re-reads; a *second* admin with the same screen open does
  not, until they act or reload. Closing this is one additive migration
  extending the `to_regclass`-guarded loop, and is not yet scheduled.
- **Retention** is `prune_sse_events()`, which drops rows older than two hours.
  `0024` schedules it every 15 minutes **only where `pg_cron` is installed** —
  the migration's `do` block is a no-op otherwise, and on a project without the
  extension the outbox grows without bound until someone calls the function.
  Enable `pg_cron` from the Supabase dashboard, or schedule the call yourself.

### Topics

| Topic | Audience | Emitted by | Payload |
| --- | --- | --- | --- |
| `dashboard.refresh` | `{admin, manager}` | `emit_dashboard_sse_event` on 12 tables (`0007`, retargeted by `0028`) | `{"table": "..."}` |
| `access_request.created` | `{admin, manager}` | `emit_access_request_sse_event` (`0024`, retargeted by `0028`) | request id, applicant name, relationship, `pending_count` |
| `access_request.decided` | `{admin, manager}` | same | request id, `from`, `to`, `pending_count` |
| `notification.created` | the one recipient | trigger on `notifications` (`0030`) | notification id, kind |
| `stream.resync` | the affected connection | `app/core/realtime.py`, never the database | `{"resync": true}` |

`pending_count` is included so a badge can update from the event itself. The
frontend currently re-snapshots instead, which is also correct — the field is
there so a toast does not need a round trip.

## Out-of-app delivery: notifications and Web Push

**The stream above is not the notification system, and nothing durable is built
on it.** SSE is at-most-once and connection-scoped, and `sse_events` is pruned
every two hours *because* it is ephemeral. A resident whose phone was locked
when a visitor reached the gate must still find out. So there are three layers
over one record:

| Layer | Where | Lifetime | Reaches |
| --- | --- | --- | --- |
| Record | `notifications` + `notify_member()` / `notify_profile()` (`0030`, `0041`) | until read and pruned | anyone, later |
| In-app live | the SSE frame above | the connection | an open tab |
| Out-of-app | Web Push, `app/core/push.py` | one delivery attempt | a closed tab, a locked phone |

The row is written **first, inside the transaction that caused it**, and both
transports carry it. A notification that can exist without its cause, or a cause
without its notification, is a bug that cannot be reproduced.

**The recipient is a person, not a membership** (`0041`; see
[`design/AUTH_AND_SESSION_DESIGN.md`](design/AUTH_AND_SESSION_DESIGN.md) §4).
`0030` addressed every layer of this to a `community_memberships` row, which is
correct and invisible for a resident and a closed door for a service person who
has registered and not yet been hired — they hold no membership anywhere, and the
thing they are waiting for is an answer. `recipient_membership_id` survives and
still says which community a notification was *about*; `recipient_profile_id`
says who it is *for*. `notify_profile()` is the writer for the membership-less
case, and it produces **no SSE frame**, because `sse_events.community_id` is
`not null` and there is no community for the frame to belong to.

**Transport: standards Web Push (RFC 8291/8292) over our own VAPID keypair.**
No vendor account, no SDK in the frontend bundle, and the relays carry
ciphertext they cannot read — which is the same argument that keeps a Supabase
key out of the browser, one layer further out. Rejected: FCM (a Google project,
a service-account secret and a service worker in a frontend we do not own, and
for non-Chrome browsers it wraps this protocol anyway) and OneSignal/Pusher
Beams (a third party *receives the content*, which for flat numbers and visitor
names is a consent decision, not a build convenience).

**The sender obeys a rule the poller does not.**

> The hub may drop. The sender may not duplicate.

Several processes can each poll the outbox and fan out to their own connections
harmlessly. Two senders reading one unsent notification buzz a phone twice. So
claiming is atomic in Postgres — `claim_push_batch()` with `for update skip
locked` — and marks the row sent *before* the HTTP call, making at-most-once the
deliberate bias. Only the last hour is claimed: if the sender is down for a day,
those notifications stay in the feed and simply never buzz, because a phone that
vibrates at 3am about yesterday's visitor is worse than silence.

Limits worth knowing: **push payloads cap at about 4 KB after encryption**, so
the payload is an id and rendered strings, never a record; **a `410` deletes the
subscription** rather than being retried, because hammering a dead endpoint is
how you get rate-limited; **iOS delivers web push only to an installed PWA**, and
since HomeBandhu is web-only that is a ceiling rather than a choice; and
**rotating the VAPID keypair silently unsubscribes every browser**, because a
subscription is bound to the key that created it and the protocol has no
dual-key period.

**Configuration fails closed and quietly.** `PushSettings` is a second
`pydantic-settings` class reading the same `.env`. With no keypair the sender
never starts, `GET /push/vapid-key` and `POST /push/subscriptions` answer `503
push_not_configured`, and everything else works normally — the same shape as
`0024` scheduling under `pg_cron` when the extension is present.

**Observable end to end since 2026-08-10.** This paragraph read *"not yet
observable — `frontend/public/` has no service worker … nothing can receive a
push today"* from the resident build until the worker portal shipped one.
`frontend/public/sw.js` handles `push` and `notificationclick`;
`src/lib/push/pushClient.js` registers it, asks for permission, reads
`GET /push/vapid-key` and posts `PushSubscription.toJSON()` unchanged. `main.jsx`
registers the worker on load — **registering is not subscribing**, and only the
second needs a permission prompt.

The client drops any existing subscription before taking a new one, which is the
client half of the rotation hazard above: a subscription is bound to the key
that created it, and re-subscribing is the only way a browser recovers from a
rotated keypair.

**The same file also carries a small offline claim, and only a small one.** It
caches successful same-origin GETs as they happen and reads that cache only when
the network fails, so a reload during an outage still boots the application.
There is no precache manifest and no Workbox: Vite emits content-hashed asset
names, so a hand-written manifest is wrong on the next build and a generated one
is a versioning problem nobody asked to have. `/api/` is excluded outright — an
API response served from cache would show a worker yesterday's jobs and call
them today's.

Still open: the subscribe control exists on one screen (the service partner's
profile), so a resident cannot yet turn push on from their own dashboard. That
is placement, not capability — `enablePush()` is one call from anywhere.

### Who writes into it

`notify_member()` and `notify_profile()` are the only writers, and they are
called from inside the RPC that makes the change — never from Python. The
distinction matters: Python writing a second statement after the first can fail
between them.

**One exception, and it proves the rule rather than bending it.**
`notices_notify_residents` (`0041`) is an `after insert` trigger, because
`POST /notices` has no RPC to call from — `insert_notice` is a plain
single-statement PostgREST write, and its docstring defends that. The objection
to triggers is that one "knows nothing about *who* should hear about it or what
it should say". Here it does: the audience is every resident of the notice's own
community, and the words are the notice's own title and body. Where that is not
true, the rule stands.

`notify_community_roles()` (`0032`) is the fan-out for the other direction: one
event, every active member of the community holding one of the given roles.

`notify_community_staff()` (`0031`) is the named audience over it — admins and
managers, the same audience `0028` gives `dashboard.refresh`, deliberately: a
manager who watches the dashboard change but never gets a notification is worse
off than one who gets neither, because only one of those looks like a delivery
bug.

The general function arrived when the visitor writes needed a *different*
audience — `security`, which does not appear in the staff list at all. It
replaced the body of the specific one rather than sitting beside it, because two
copies of a fan-out loop is how one of them ends up filtering on `status =
'active'` and the other does not, and the one that forgets is the one that
notifies people who have left the community.

| Emitter | Kinds | Reaches |
| --- | --- | --- |
| `raise_complaint`, `reopen_complaint`, `confirm_complaint_resolution` (`0031`) | `complaint.raised`, `.reopened`, `.resolution_confirmed` | the community's admins and managers |
| `update_complaint` (`0020`, replaced by `0031`) | `complaint.status_changed`, `.resolved` | the resident who raised it |
| `add_complaint_comment` (`0020`, replaced by `0031`) | `complaint.commented` | whichever side did not write it |
| `decide_visitor_pass` (`0032`) | `visitor.approved`, `.rejected`, `.cancelled` | the community's `security` role, and its admins |
| `settle_resident_payment` (`0033`) | `payment.succeeded`, `.failed` | the resident whose invoice it was |
| `settle_amenity_booking_payment` (`0033`) | `payment.succeeded`, `.failed`, `amenity.booking_paid` | the resident, and — on success only — the community's admins and managers |

| `create_work_order`, `respond_to_work_order_schedule`, `assign_work_order`, `reschedule_work_order`, `cancel_work_order` (`0036`) | `work_order.schedule_requested`, `.resident_confirmed`, `.resident_declined`, `.assigned`, `.rescheduled`, `.cancelled` | the resident whose complaint it is, the worker holding it, or the supervisor who proposed it — one named person each time, not a broadcast |
| `dispatch_ping_candidates`, `dispatch_auto_assign`, `dispatch_resident_timeout`, `dispatch_failed_visit_escalation` (`0037`) | `work_order.offered`, `.assigned`, `.proceeding`, `.no_candidates`, `.escalated` | the shortlisted workers; then the assignee and the resident; `no_candidates` and `escalated` go up the chain — the supervisor for the first, the department's manager or the community's admins for the second |
| `accept_work_order_offer`, `start_work_order`, `complete_work_order`, `report_work_order_failure` (`0039`) | `work_order.accepted`, `.assigned`, `.started`, `.completed`, `.failed` | the resident, whose complaint it is, and the supervisor who raised the job — never the worker, who is the one writing |
| `schedule_security_shift` (`0040`) | `shift.scheduled` | the guard put on the roster — **when they have an account**; a roster name typed in by an admin has no membership and therefore no address, the same wall `0035` met with rejected applications |
| `record_security_incident` (`0040`) | `security.incident` | the community's admins and managers, and **only at `high` or `critical`** |
| `verify_gate_credential` (`0040`) | `visitor.checked_in` | the resident who issued the pass |

Two rules the complaint emitters establish for every later one. **A status change
notifies; an assignee or a progress bar does not** — a resident notified about
everything stops reading notifications, which costs more than the ones they miss.
And **an internal comment notifies nobody**, because a notification leading to a
thread where nothing new is visible tells someone they were discussed and refuses
to say how.

**The work-order emitters amend the first of those rules, and the amendment is
narrower than it looks.** A dispatch offer is not a passive field change: it
expires, it requires an action, and a worker who is not told about it is a worker
the job silently was not given to. `US-2.7` names reassignment explicitly for the
same reason. So offers, acceptances, schedule changes and cancellations notify —
and `work_orders.progress_percent` and a supervisor editing an internal note
still do not. The distinction the original rule was drawing was never
*status versus field*; it was **something is being asked of you** versus
*something changed near you*, and the offer is the first case where those two
came apart.

**`work_order.no_candidates` is the one emitter here that reports an absence**,
and it exists because the alternative is silence that looks identical to success.
A department where nobody was free produces no offer, no assignment and no
notification at all unless something says so; the supervisor is told once, and
the job stays where a human can place it by hand.

**`work_order.escalated` is the second of those, one level up.** A failed visit
already notifies the supervisor immediately, so the escalation two hours later is
not about the failure — it is about *nobody having done anything about it*, which
nothing else in the system would ever say out loud. It goes to the department's
manager, or to the community's admins where the department has no manager on its
roster, which is every department created through the departments form before
anybody was hired.

**Three emitters are deliberately absent from `0039`.** Declining an offer
notifies nobody: the job is still open, the other offers still stand, and telling
a supervisor that one of five people said no is the notification that trains
people to stop reading them. Neither does a worker get told about their own
write — the four kinds above all travel away from whoever caused them.

**`0040`'s three emitters are where the first rule finally gets a threshold
rather than a category.** Everywhere above, whether something notifies is decided
by *what kind of thing happened*. A gate register cannot be sorted that way: a
tanker arriving and a fire alarm at 02:00 are the same kind of row in the same
table, written by the same person on the same screen. So `record_security_incident`
branches on **severity** — `high` and `critical` reach the community's admins and
managers, `low` and `medium` are a record — and that is the only place in this
system where the notification decision is a field's value rather than the
operation's identity.

The two registers notify nobody at all, which is the same rule read the other way:
nobody is waiting to be told that twelve bags of cement came through the gate.

**And a gate check-in notifies the resident**, which is the one emitter in `0040`
that travels to somebody outside the department. It is the arrival a resident is
actually waiting for, and until now the pass they issued went quiet the moment
they issued it.

**The payment emitters add the case the rule above does not cover: a failure
notifies too.** A decline nobody is told about leaves a resident believing they
have paid, which is the same failure `US-2.12` names on the booking side and no
better on the invoice side.

**The gateway itself is deliberately not in this list, or in the database.** It
is one pure function — `app/services/payment_simulator.py` — and both RPCs above
*take* an outcome rather than deciding one. That split is what makes swapping in a
real provider a change to one module: the router, the RPC and the migration are
already the shape a live integration needs, including the `payment_events` trail
and the idempotency key a webhook would arrive with.

**The seam also fixes the order of two calls, and the order is the whole point.**
The service looks a prior attempt up by idempotency key *before* it calls the
gateway, not after. With a pure simulator that ordering is invisible; with a real
provider behind the same function it is the difference between a duplicate request
and a duplicate charge — the one failure the key exists to prevent. Both RPCs
check again themselves, which is what covers two identical requests arriving at
once, and both return the recorded payment rather than an id so that a replay is
described by the row that settled it rather than by the attempt that arrived
second.

## One service that composes services

`resident_snapshot_service` is the only service in the backend that calls other
services rather than repositories, and the exception is deliberate. Every figure
on the resident home screen already has an owner — one module decides what
`Unpaid` means, another which stored complaint statuses render as `In Progress`,
a view which visitor passes are still current. Reaching past those into the
repositories would copy each rule into a second place, and the copies would be
correct on the day they were written.

The cost is a projection built from projections and one round trip per part; the
property bought is that **the home screen and the screen it links to cannot
disagree**, which for a screen whose entire job is to summarise the others is the
only property that matters. The parts are read in sequence rather than in one
transaction, so `generatedAt` is when the payload was assembled and not when any
part of it was true — a resident refreshing a home screen is not asking for a
consistent cut of the database.

~~A notice emitter is still missing.~~ Closed 2026-08-10 by `0041`: publishing a
notice now fans out to every active resident of its community through
`notices_notify_residents`, excluding the author. `US-2.4` is served.

## Responsibilities

| Layer | Responsibility | Does not do |
| --- | --- | --- |
| Browser routes/pages | Render views and collect user intent. | Direct Supabase calls or tenant authorization. |
| `authStore` | Read backend session, begin Google redirect, logout. | Store OAuth credentials or decide roles. |
| `DashboardDataBootstrap` | Hydrate and refresh the dashboard cache. | Persist tenant records in browser storage. |
| API routers | HTTP contracts, cookies/CSRF dependencies, role guards. | Embed database query logic. |
| Services | Registration, invitation, projection, and policy rules. | Trust client-supplied identity or role. |
| Repositories | Supabase/PostgREST and database RPC operations. | Expose raw provider credentials to the browser. |
| Postgres baseline | Community data, membership scope, RLS, RPC transactions, event outbox. | Authenticate browser users directly. |

## Domain model rules

- `auth.users` is external Google-authenticated identity; `profiles` is its
  application contact record.
- `community_memberships` is the sole tenant-role source. Active, non-ended
  membership determines both community scope and portal authorization.
- `resident_invites` stores opaque token/code hashes and binds redemption to
  the authenticated account email; it is not an authentication factor.
- `access_requests` is the resident join-request workflow. Approval creates
  the resident membership and optional `unit_residencies` record atomically.
- `sse_events` is an internal, tenant-scoped refresh outbox. It does not expose
  direct Postgres subscriptions to the browser. RLS is enabled with no policy,
  so only `service_role` can read it: the rows are cross-tenant by construction
  and the backend fans them out only after checking membership. Retention is
  bounded by `prune_sse_events()` (migration `0024`).

## Design status

The ERD in `homebandhu_submission_erd.dbml` now mirrors the table, enum, key,
and relationship definitions in `backend/supabase/migrations/0001_baseline.sql`.
Compatibility migrations `0006`, `0007`, `0008`, and the timestamped
20260730 migrations exist only for an older hosted project. They reconcile the
legacy schema with the fresh baseline—without changing the fresh-baseline
model—including community status normalization, access-request ownership, and
resident decision RPCs.

The amenity management CRUD flow is database-backed. Booking and ledger read
models are loaded through the snapshot, but their remaining client-side action
handlers require their own backend mutation endpoints before they can claim
durable realtime writes.
