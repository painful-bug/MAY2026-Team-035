# Resident backend — design and reasoning

> **What this document is.** The design for the resident-portal backend, written
> *before* the code, plus the evidence it was derived from and the reasoning
> behind each choice. Its companion,
> [`ADMIN_DASHBOARD_DESIGN.md`](ADMIN_DASHBOARD_DESIGN.md), documents the
> already-built admin backend and establishes the paradigms this one follows.
> Where this document says "as in the admin backend", the reasoning is there and
> is not repeated.
>
> **Status: built.** All eight steps of §9 are done, as of 2026-08-04 — every
> endpoint in §6 exists, is tested and is documented. The per-step status lives
> in the §9 table and nowhere else, so there is one place to check and one place
> to update.
>
> **Built is not deployed.** No migration in this workstream has been applied to
> any database — `0001` included — and applying them is not this workstream's to
> do. Until then every endpoint here is code with a passing test suite and no
> schema underneath it.
>
> As the code lands, this document stops being purely prospective. Where a
> section describes something now built, the code is the authority and a
> disagreement between the two is a bug in this file — see
> [`README.md`](README.md).

---

## 1. How the surface was derived, and why that method

The obvious way to find out what the resident backend must do is to read the
frontend's API calls. That does not work here, and the reason shapes everything
downstream.

**Every API call site in `frontend/src` — all 26 of them — is auth, registration,
or admin.** Not one resident page calls the network:

| Frontend area | Wired API calls |
|---|---|
| Auth / session / password | 11 |
| Registration, invitations, onboarding, community search | 8 |
| Admin dashboard, admin amenities, access requests | 7 |
| **Resident portal (8 pages)** | **0** |

The resident portal runs entirely on Zustand slices over `localStorage`. So the
requirement was scraped from **behaviour** instead: what each store action
actually does, what fields it writes, what it refuses to do. That is a better
source than a wishlist — these are the rules the product team already decided,
expressed precisely enough to execute.

Two consequences worth stating plainly:

- **There is no frontend contract to break.** The dummy data shapes are not an
  API contract, and per the standing constraint we are not preserving them. The
  backend gets to pick a coherent shape, and the frontend adapts when its team
  wires it up.
- **Nothing here can be verified against a running client.** These endpoints
  will have tests and no consumer until the frontend team connects them. The
  design is therefore biased toward *obvious* shapes over clever ones.

### Evidence base

| Source | What was taken from it |
|---|---|
| `store/slices/createVisitorsSlice.js` | Pass lifecycle, statuses, code/QR model |
| `store/slices/createComplaintsSlice.js` | Complaint lifecycle, SLA rule, reopen/confirm rules |
| `pages/ResidentDashboard/*.jsx` (8) | Screen-level read shapes, filters, actions |
| `features/amenities/services/*` | Resident booking flow (series, partial cancel) |
| `docs/product/USER_STORIES.md` | Epic 2 — the twelve resident stories |
| `backend/supabase/migrations/*` | What the schema already supports |

---

## 2. What the resident can already do today

Not everything is missing. These operations exist and are already reachable by a
non-admin caller:

| Endpoint | Note |
|---|---|
| `POST /access-requests`, `GET /access-requests/mine`, `POST /access-requests/{id}/withdraw` | The join workflow, complete |
| `POST /invitations/redeem`, `POST /invitations/prepare` | Invite redemption |
| `GET /communities/search` | Finding a community to join |
| `POST /amenities/{id}/bookings/request` | Resident booking — **already resident-scoped**: the flat is read from the caller's own residency, never the body |
| `POST /amenity-bookings/cancel` | Dual-role: a resident may withdraw their own future days; an admin may cancel any |
| `POST /complaints/{id}/comments` | Not admin-guarded; a resident can already comment |
| All of `/auth/*` | Session, refresh, CSRF, password, OAuth |

So the resident booking *write* path exists. What is missing around it is the
read path — which brings us to the first real finding.

---

## 3. Findings that change the design

### 3.1 A resident cannot list the amenities they are allowed to book

There is **no amenity list endpoint at all**. Not an admin-only one — none. The
catalogue reaches a client exactly one way, inside `GET /dashboard/snapshot`,
which is guarded by `require_membership_role("admin", "manager")`. Every other
amenity read (`/amenities/{id}/bookings`, `/approvals`, `/ledger`,
`/ledger/summary`, `/amenity-reports`) carries `dependencies=[_admin]`.

But `POST /amenities/{id}/bookings/request` carries no admin guard — it was
written for residents on purpose, and its docstring says so.

The result is an endpoint a resident may legitimately call with an `amenity_id`
they have no legitimate way to obtain. That is not a security hole; it is worse
in a mundane way — a **feature that cannot be used**. It happened because the
amenity work was built from the admin screens outward: the admin UI gets its
catalogue from the snapshot it was already fetching, so no one ever needed a list
endpoint, and the resident half inherited that absence.

This is the clearest evidence for the design rule in §5.1: role is a property of
the *projection*, not a filter bolted onto one shared payload.

> **Closed, 2026-08-04.** `GET /amenities/available` ships, guarded by any
> active membership. Written as this section argued it should be: a separate
> `BookableAmenity` model rather than a filtered `AmenitySummary`, over a
> resident view of its own (`bookable_amenity`, `0029`) rather than
> `amenity_overview`, so the resident response has no code path that could carry
> `pendingRequests` or `outstandingDues`. The present tense above is left as it
> was — it is the argument that produced the endpoint, and it is worth being able
> to read it as it stood.
>
> Two things were decided at build time that this section did not cover. An
> amenity with a **temporary closure** recorded against it is excluded, using the
> same truthiness test `amenities_service` already applies to that column — the
> test is applied twice, once in the view and once in the service, for the reason
> in §12. And the response is **unpaged** — a `Page` envelope a client renders
> whole, because a catalogue is a fixed list.
>
> `hasMore` was hard-coded `false` when the endpoint shipped, and is now
> computed. The read is bounded at 500 rows; a bound and a permanent `false` in
> the same response is the endpoint asserting completeness it never checked, so
> the count comes back with the rows and `hasMore` means the one thing it can
> usefully mean — the catalogue has outgrown being unpaged. The number is not
> expected to be reached. That is not an argument for leaving it unmeasured.

### 3.2 Complaints cannot record what the resident form collects

The resident complaint form (`createComplaintsSlice.js:42`) writes `urgency`,
`location`, `expectedResolutionAt`, and later `rating`, `residentFeedback`,
`reopenedCount`. The `complaints` table has none of those columns. `0020` added
`progress_percent`, `assignee_label`, `due_at` and `department_id` — all for the
*admin* editor.

`US-2.5` already records this: *"no create endpoint, and no priority column for
the selector to write to."* This design adds both.

### 3.3 The SLA rule is a product decision already made

`getExpectedResolutionAt` encodes High → 24h, Medium → 48h, Low → 72h. It is
sitting in a frontend store slice, which means it is (a) trivially bypassable and
(b) invisible to the admin portal, which has its own `due_at`.

It belongs in the database, computed on insert. Whether the hours stay hard-coded
or become per-community settings is an open question (§8).

### 3.4 The visitor pass model is half-present

`visitor_requests` already has the right skeleton: a `visitor_status` enum
including `pending_approval`, a unique `pass_hash`, `valid_from` / `valid_until`,
and check-in/check-out timestamps. That is a scheduled, time-boxed, hashed access
credential — `USER_STORIES.md` notes with some surprise that the schema arrived
at `US-3.1` without anyone aiming for it.

What it lacks is what the resident form collects: purpose, guest count, and the
**short security code** the resident reads aloud over the phone. That code is not
the same artifact as the QR token and must not be stored the same way (§5.4).

### 3.5 The live stream already crosses roles

> **Closed, 2026-08-04**, by step 1 of §9 —
> [`0028_event_audience.sql`](../../backend/supabase/migrations/0028_event_audience.sql),
> `_Subscriber.accepts` in `app/core/realtime.py`, and `GET /events`. The
> finding is kept in the present tense below because it is the reasoning that
> set the build order, and because a closed finding read as if it had never
> been true is how the same mistake gets made again.

`GET /dashboard/events` is guarded by `get_active_membership`
(`dashboard.py:41`) — **any** active member, not an admin. And the hub fans out
by community alone: `_Subscriber` holds a `community_id` and nothing else
(`realtime.py:103`), so every subscriber in a community receives every event in
it.

The payloads are not innocuous. `0024`'s `access_request.created` carries
`applicant_name`, `requested_relationship`, `created_at` and the community's
pending count. A resident who opens that stream watches their neighbours' join
applications arrive in real time.

Today nothing exploits this, because no resident client connects to anything. The
decision to make every update live across all users is exactly what stops that
being true, so the fix has to land before the resident portal is pointed at the
stream — not after.

> **Correction.** §8 Q5 of the first draft of this document said the stream was
> admin-only. It is not. That mis-stated a live disclosure as a missing feature.

There is a second, cheaper consequence. Twelve tables emit `dashboard.refresh` on
every row change, and the client contract for that frame is *re-read your
snapshot*. Point five hundred residents at a community-wide firehose and every
unrelated row change costs five hundred snapshot fetches. Audience scoping is a
load fix as much as a privacy one.

---

## 4. Capability inventory

Scraped from the frontend. **Support** is the backend state **as surveyed on 2026-08-03, before any
of this was built** — it is the input the build order in §9 was derived from, and it is deliberately
left standing rather than updated. Every row that reads *No*, *Blocked* or *table yes, no endpoint* is
a row §9 was written to close; for what is true now, read §9 and `API.md` §12–§14, not this table.
The one row that stayed *No* on purpose is gate check-in, and it says why.

### Visitors — `Visitors.jsx`, `DashboardHome.jsx`
| Capability | Support |
|---|---|
| Pre-approve a visitor group (purpose, date, time, guest count) | Table yes, endpoint no |
| Receive a security-raised entry request | Status exists, endpoint no |
| Approve / reject that request | No |
| View expected visitors and history | No |
| Show QR pass, copy security code | No |
| Gate check-in / check-out / verify | **Out of scope** — no staff login (see `USER_IDENTIFICATION.md`) |

### Complaints — `Complaints.jsx`
| Capability | Support |
|---|---|
| Raise with title, description, category, urgency, location, attachments | Partial — no urgency/location columns |
| Derived expected resolution time | No |
| Own list with status/category filters | No |
| Detail with timestamped timeline | Table yes, no resident read |
| Comment | **Yes** |
| Reopen a resolved complaint with a reason | No |
| Confirm resolution with 1–5 rating and feedback | No |
| Unread-update marker | `complaint_read_state` exists, unused |

### Amenities — `Amenities.jsx`
| Capability | Support |
|---|---|
| Browse amenities | **Blocked — no list endpoint exists (§3.1)** |
| Book one or more days as one request | **Yes** |
| Private-booking flag | Yes, via booking rules |
| Cancel selected days | **Yes** |
| List own bookings, grouped by request | No |

### Money — `Payments.jsx`
| Capability | Support |
|---|---|
| List own invoices, split unpaid / paid | Tables yes, no resident read |
| Pay an invoice | `POST /invoices/{id}/payments` exists but is **admin-guarded** |

### Notices, profile, home — `Notices.jsx`, `Profile.jsx`, `DashboardHome.jsx`, `Faq.jsx`
| Capability | Support |
|---|---|
| Read notices with category and urgency | Columns exist (`0018`), no resident read |
| Own profile, flat, tower, status | Partly via `/auth/session` |
| List everyone registered to the flat | Tables yes, no endpoint |
| Add another phone to the flat | No |
| Emergency contact directory | **Hard-coded in the page** — needs a real source |
| Home summary: dues, visitors, complaints, notices, activity | No |
| FAQ | Static; no backend needed |

---

## 5. Design decisions

Each states the decision, the reasoning, and the alternative rejected.

### 5.1 A separate `/resident/snapshot`, not a role-filtered `/dashboard/snapshot`

**Decision.** The resident home gets its own projection endpoint and its own
service, mirroring `dashboard_service` rather than extending it.

**Why.** The two screens want genuinely different aggregates. An admin wants
counts across the community; a resident wants *their* dues, *their* visitors,
*their* complaints. A single payload with role branches inside becomes a function
whose output shape depends on a runtime role — untypable, untestable without
fixtures for every role, and one `if` away from leaking a community-wide count
into a resident response.

Separate projections make the tenancy scope a property of the query, and the
worst case a missing field rather than an over-broad one.

**Rejected.** Adding `?scope=me`. It makes the dangerous case the default and the
safe case an opt-in, which is backwards.

### 5.2 Ownership is enforced in SQL, not in Python

**Decision.** Every resident read filters by the resolved membership id *inside*
the view or RPC.

**Why.** As in the admin backend, tenancy comes from `get_active_membership`,
never a request body. Pushing the ownership predicate down one more level means
a repository cannot accidentally return another resident's row even if a service
forgets a check. Defence in depth, at no cost.

**Rejected.** Fetching then filtering in the service — one forgotten filter is a
cross-tenant leak, and the query still transferred the rows.

### 5.3 Complaint SLA computed in the database

**Decision.** `expected_resolution_at` is set by the insert RPC from the urgency,
alongside a `priority` column.

**Why.** §3.3. One rule, one place, applies to every writer, and the admin's
`due_at` and the resident's expectation stop being two independent numbers.

**Rejected.** Trusting a client-sent timestamp — a resident could send themselves
a one-minute SLA.

### 5.4 The visitor security code is hashed; the display copy is returned once

**Decision.** Store a hash. Return the plaintext code exactly once, in the
response that creates the pass. Never again.

**Why.** The code admits a stranger through a gate. It is a credential, so the
same rule as `resident_invites` applies — that table stores `token_hash` and
`code_hash` and nothing reversible. A code re-readable from a list endpoint is a
code that leaks with any read access to it.

**Cost, stated honestly.** A resident who loses the code cannot recover it and
must reissue. That is the correct trade for a gate credential, and it is exactly
how the invite flow already behaves.

**Rejected.** Storing plaintext for convenience — it makes every read path a
credential disclosure.

### 5.5 Resident payment is a separate endpoint from admin reconciliation

**Decision.** A resident self-service payment endpoint, distinct from the
existing admin `POST /invoices/{id}/payments`.

**Why.** They are different operations wearing similar names. An admin records a
payment that *already happened* elsewhere — arbitrary amount, arbitrary method,
possibly backdated. A resident *initiates* one against their own invoice, for the
full outstanding balance, through whatever gateway exists. Merging them means one
endpoint where half the fields are forbidden depending on who is calling.

**The gateway is a simulator we build, and it says so.** (`PO`, 2026-08-04.) No
real money moves. Payments settle through a deterministic simulator that passes
by default and fails on specific, demonstrable inputs — a card past its expiry
date being the worked example. Full mechanism in §11.

This replaces an earlier note in this section which said no gateway would be
integrated and the endpoint should record an `initiated` payment forever. That
was the right call when the alternative was a fake success; it is not the right
call now that the alternative is an honest simulator. The rule it was protecting
— **never report a payment as succeeded when no money moved** — survives
unchanged and is met differently: the payment row carries `provider =
'simulator'`, so no row in the ledger ever claims to be something it is not.

### 5.6 The emergency contact directory comes from departments

**Decision.** Serve `Profile.jsx`'s contact list from `departments` (which
already carries contact details, hours and a head) rather than a new table.

**Why.** `US-2.9` asks for a *current, verified* directory; the pain point is
that contacts go stale. A hard-coded list in a JSX file is the stale-by-
construction version. Departments are already maintained by admins for other
reasons, so this directory gets updated as a side effect of work that already
happens.

**Known gap.** `US-2.10` wants a *building* representative. Nothing ties a
department head to a building. Out of scope here; recorded in §8.

### 5.7 Reuse `member_activity`; do not invent an activity table

The frontend's `addActivity` calls map onto the existing `member_activity` table.
It is already tenant-scoped with a `payload jsonb`. Adding a second activity
table would mean two feeds that disagree.

> **Superseded by the code, 2026-08-04 (step 7).** The rule survives; the table
> does not. Nothing in this project writes `member_activity` — not a trigger, not
> a service, and not the admin dashboard, which reads `audit_events` instead — so
> the home screen's activity strip would have been empty by construction and
> stayed empty. Meanwhile §5.8 had already made `notifications` the durable
> record of *"every user-visible event"*, which is exactly what that strip shows.
> Writing those events a second time into `member_activity` would have produced
> the two disagreeing feeds this section set out to prevent.
>
> So `GET /resident/snapshot` serves `activity` from the notification feed, and
> `member_activity` stays unwritten and unread. It also therefore keeps no row
> security: per the timing rule, the policy ships with the migration that first
> serves the data, and no migration has.

### 5.8 Delivery is three layers, and the durable one is not SSE

**Decision.** Every user-visible event writes a `notifications` row first. SSE
and Web Push are two *deliveries* of that one row, never the record of it.

**Why.** SSE delivery is at-most-once and connection-scoped by design — §7 of the
admin document makes "the payload is a hint, never truth" load-bearing. A
resident whose phone was locked when a visitor reached the gate must still see
that it happened. If the stream is the notification system, being offline means
the event never existed.

So: one truth, two transports. The `notifications` table is the truth.

**Rejected.** Making SSE the feed and backfilling from `Last-Event-ID`. The
outbox is pruned every 15 minutes (`0024`) precisely because it is ephemeral;
building durability on top of a table designed to be deleted inverts both.

### 5.9 The outbox gets an audience; the subscriber gets an identity

**Decision.** `sse_events` gains `audience` (`community` | `role` | `member`),
`audience_roles text[]` and `recipient_membership_id`. `_Subscriber` gains the
membership id and role, both taken from the verified membership.

**Why.** §3.5. Scoping in the dispatcher rather than at the endpoint means one
filter, applied to every stream, derived from a value the client cannot set —
the same argument as §5.2, one layer further out.

**Rejected.** A separate resident-only stream endpoint with its own topic
allow-list. Two endpoints means two places to get the filter right, and the
allow-list is a denylist wearing a disguise: forget to add a topic and it leaks.

### 5.10 One trigger connects notifications to the stream

**Decision.** A trigger on `notifications` emits an `sse_events` row with
`audience = 'member'`. Feature code writes notifications; nothing else touches
the outbox.

**Why.** It makes live delivery a property of the system rather than a checklist
item per feature. Add a notification kind and it streams for free; forget to wire
SSE and there is nothing to forget.

### 5.11 Web Push over VAPID, not a vendor SDK

**Decision.** Standards Web Push (RFC 8291/8292) with our own VAPID keypair.

**Why.** No vendor account, no SDK in the frontend bundle, and no third party
receives who visited which flat and when. Chrome, Edge and Firefox implement it
natively; Safari 16.4+ supports it for installed PWAs.

**Rejected — FCM.** Needs a Google project, a service-account secret, and
`firebase-messaging-sw.js` in a frontend we do not own. For non-Chrome browsers
it wraps this same protocol anyway, so the dependency buys nothing here.

**Rejected — OneSignal / Pusher Beams.** Sends notification content to a third
party. For an app carrying flat numbers and visitor names that is a data-sharing
decision requiring consent, not a build convenience.

**Cost, stated honestly.** On iOS, web push only works if the resident installs
the PWA to the home screen. FCM does not fix that — a web app on iOS gets web
push or nothing.

**And that cost is accepted, not open.** HomeBandhu is a web application; there
is no native client and none is planned (`PO`, 2026-08-03). So browser capability
is the ceiling on every delivery mechanism here, which makes this decision the
only available one rather than the best of several. It also settles the question
permanently: *"use a native app instead"* is not a fix anyone should re-propose
when the iOS limitation is rediscovered, and neither is a vendor SDK, which
carries the same ceiling plus a third party.

---

## 6. Proposed endpoints

Naming follows the existing surface. `M` = any active member, `R` = resident.

### Home
| Method | Path | Guard | Purpose |
|---|---|---|---|
| GET | `/resident/snapshot` | M | Home aggregate: dues, visitors, complaints, notices, activity |

### Visitors
| Method | Path | Guard | Purpose |
|---|---|---|---|
| POST | `/visitor-passes` | R | Pre-approve. Returns the plaintext code **once** |
| GET | `/visitor-passes` | R | Own passes; `?view=current\|history` |
| GET | `/visitor-passes/{id}` | R | One pass, for the QR screen |
| POST | `/visitor-passes/{id}/approve` | R | Approve a gate-raised request |
| POST | `/visitor-passes/{id}/reject` | R | Reject one |
| POST | `/visitor-passes/{id}/cancel` | R | Withdraw a pass not yet used |

### Complaints
| Method | Path | Guard | Purpose |
|---|---|---|---|
| POST | `/complaints` | M | Raise. Computes the SLA |
| GET | `/complaints` | M | Own complaints; status/category filters |
| GET | `/complaints/{id}` | M | Detail with timeline and comments |
| POST | `/complaints/{id}/reopen` | R | Reopen a resolved complaint; reason required |
| POST | `/complaints/{id}/resolution` | R | Confirm with rating 1–5 and feedback |
| POST | `/complaints/{id}/read` | M | Clear the unread marker |

### Amenities
| Method | Path | Guard | Purpose |
|---|---|---|---|
| GET | `/amenities/available` | M | **Closes §3.1.** Bookable amenities, resident projection |
| GET | `/amenity-bookings/mine` | R | Own bookings, grouped by request |

### Money
| Method | Path | Guard | Purpose |
|---|---|---|---|
| GET | `/invoices/mine` | M | Own invoices, unpaid and paid |
| POST | `/invoices/{id}/pay` | R | Self-service payment through the simulator (§5.5, §11) |
| POST | `/amenity-bookings/{id}/pay` | R | Pay a booking's charges — the story `US-2.12` actually asks for |

`POST /amenity-bookings/{id}/pay` is the one endpoint added beyond the original
nineteen for a reason other than infrastructure, and it is worth naming why.
`US-2.12` — the only user story about payment — is about **amenity-booking**
payment: *"payments can fail even after money has been deducted"*, and the
acceptance is that a successful payment always yields a confirmed booking. An
invoice-only payment path leaves that story untouched. The two endpoints share
one simulator and one settlement RPC shape, so this is a second caller, not a
second system.

### Notices and profile
| Method | Path | Guard | Purpose |
|---|---|---|---|
| GET | `/notices` | M | Published notices with category and urgency |
| GET | `/me/household` | M | Everyone registered to the caller's unit |
| POST | `/me/household/phones` | R | Add another number to the flat |
| GET | `/directory/contacts` | M | Management and emergency contacts (§5.6) |

### Live updates and notifications (§10)
| Method | Path | Guard | Purpose |
|---|---|---|---|
| GET | `/events` | M | Canonical audience-scoped SSE stream |
| GET | `/notifications` | M | Own feed; `?unread=true`, paginated |
| POST | `/notifications/{id}/read` | M | Mark one read |
| POST | `/notifications/read-all` | M | Clear the badge |
| GET | `/push/vapid-key` | M | Public key for `PushManager.subscribe` |
| POST | `/push/subscriptions` | M | Register a browser; idempotent on endpoint |
| POST | `/push/subscriptions/unregister` | M | Unregister. A `POST`, not a `DELETE`: it carries the endpoint in a body, and content on a `DELETE` has no defined semantics |

`GET /dashboard/events` stays, unchanged in shape and now audience-scoped, as a
deprecated alias — the admin frontend is already wired to it and this workstream
does not break a working client to tidy a path.

**29 endpoints — 22 feature, 7 infrastructure.**

> **Correction.** Earlier drafts of this section said 19 feature endpoints and 26
> in total. Both were wrong: the tables above have always held more rows than the
> prose counted, and nobody re-counted when rows were added. Counted from the
> tables, the figure was 28 before this session and is 29 now. Recorded rather
> than quietly fixed, because a number in prose that nobody re-derives is exactly
> the kind of claim that decays, and the same mistake is available to the next
> person who adds a row.

The 22 feature endpoints all map to a resident story, which is the point: the
audit found 10 stories mapped to nothing, and this design closes most of the
Epic 2 half. The seven in the last table are cross-cutting infrastructure and
will be annotated `x-no-user-story` with api-type *Non-functional*, except
`GET /notifications`, which serves `US-2.1`, `US-2.4` and `US-2.7` — the three
stories that are *Partial* today precisely because the event fires and nothing
delivers it.

---

## 7. Schema changes required

All additive, idempotent, on top of `0001`, taking numbers from the resident
workstream's range — `0025`–`0039`, per
[`supabase/migrations/README.md`](../../backend/supabase/migrations/README.md).

**Only files that exist are numbered here.** A number is allocated when a file is
written, not when it is planned: this section is a list of schema changes the
design needs, and binding each one to a filename in advance is what makes a
document wrong the first time a step is reordered or turns out not to need one.
It has already happened twice — step 2 was planned with a migration and shipped
without one, and the notification file was reserved as `0029` before the view
below took that number.

Order still matters in one place. The **notification substrate comes before the
feature migrations**, because every feature RPC calls `notify_member(...)` and a
notification retrofitted onto a working write path is how you get an event that
fires for some callers and not others.

**`0028_event_audience.sql`** — closes §3.5, **written**
- `sse_events.audience text not null default 'community'` — check
  `('community','role','member')`
- `sse_events.audience_roles text[]`, `sse_events.recipient_membership_id uuid`
  references `community_memberships(id) on delete cascade`
- `create or replace` on `emit_dashboard_sse_event()` — `dashboard.refresh` becomes
  `audience = 'role'`, roles `{admin,manager}`. Its contract is "re-read the admin
  snapshot"; residents were never its audience and should never have received it
- `create or replace` on `emit_access_request_sse_event()` — same retarget
- Index on `(community_id, id)` retained; add `(recipient_membership_id, id)`

**`0029_bookable_amenity_view.sql`** — closes the §12 divergence, **written**
- `bookable_amenity` view — the resident catalogue projection: the resident
  column list, filtered to active amenities with no temporary closure,
  `security_invoker` like every other view here

**`0030_notifications.sql`** — the substrate, **written**
- Index `notifications (recipient_membership_id, created_at desc)`
- `notifications.push_sent_at timestamptz`, `.push_attempts smallint not null default 0`
- `notification_overview` view — the feed projection
- `notify_member(p_membership_id, p_kind, p_payload)` — the one helper every
  feature RPC calls, in the same transaction as the change it describes
- Trigger on `notifications` → one `sse_events` row, `audience = 'member'` (§5.10)
- `push_subscriptions` — `membership_id`, `endpoint text unique`, `p256dh_key`,
  `auth_key`, `user_agent`, `last_success_at`, `failure_count`; RLS enabled with
  no policy, `service_role` only, exactly as `0024` did to `sse_events`
- `claim_push_batch(p_limit)` — `for update skip locked` (§10.4)

> **Four things the build added that this list did not anticipate**, all of them
> consequences of `notifications` being written for the first time.
>
> **RLS on `notifications`, with a policy.** The table is reachable through
> PostgREST and had none, so any authenticated user could read every
> notification in the project — complaint updates, visitor names, invoice
> amounts. Nothing exploited it because nothing wrote the table; this migration
> is what starts writing it, so the policy ships in the same file. Same timing
> rule as `0028`: the fix lands before the thing that makes it exploitable.
>
> **`is_own_membership(uuid)`** — the third shared RLS predicate, beside
> `is_community_member` and `is_community_admin` from `0019`. §5.2 says
> ownership is enforced in SQL; this is the function that lets it be.
>
> **`mark_notification_read` and `mark_all_notifications_read`.** Reads get a
> policy, writes get none, so marking read had to be a function. It is the better
> shape anyway: knowing a notification id is not enough to mark someone else's
> read.
>
> **`register_push_subscription` / `delete_push_subscription`.** The table is
> `service_role` only, so registration cannot be a PostgREST insert. Both check
> `is_own_membership` first — a SECURITY DEFINER function that trusts a
> caller-supplied membership id is one that lets anyone subscribe a device to
> anyone else's notifications.

**`0031_resident_complaints.sql`** — closes §3.2 and §3.3, **written**
- `complaints.priority text` — check `('low','medium','high')`, default `'low'`
- `complaints.location text`
- `complaints.expected_resolution_at timestamptz`
- `complaints.reopened_count integer not null default 0`
- `complaints.resolution_rating smallint` — check `between 1 and 5`
- `complaints.resident_feedback text`
- `complaint_overview` view — the resident detail projection
- `raise_complaint(...)`, `reopen_complaint(...)`, `confirm_complaint_resolution(...)` RPCs

> **The ordering constraint above is not a preference, and this file is where it
> would have been broken.** `0025` was the lowest free number and it was the
> wrong one: every RPC in this file calls `notify_member`, which `0030` creates,
> and migrations apply in filename order. Postgres would not have objected — a
> plpgsql body is not resolved against the catalogue until it runs — so the file
> would have applied cleanly and failed at the first complaint. *Allocate at
> write time* means the number is chosen with the file in front of you; here what
> chose it was the dependency.
>
> **Four things the build added that this list did not anticipate.**
>
> **RLS on `complaints`, and a tightening of the two child policies.** `0020`
> enabled RLS on `complaint_events` and `complaint_comments` and left the parent
> open, so every complaint in the project was readable through PostgREST. That
> was survivable while complaints were an admin surface behind an admin-guarded
> API. This migration is what puts a resident's grievances behind an endpoint
> they call themselves. The child policies used `is_community_member`, which
> would have let any resident read a neighbour's timeline; both now match the
> parent — admins see the queue, a resident sees their own.
>
> **`notify_community_staff(...)`.** `notify_member` writes to one recipient,
> which is right for a substrate that should not know what a community is. But a
> complaint has to reach whoever is on duty, and that is a set. Same audience
> `0028` gave `dashboard.refresh` — admins *and* managers — because a manager who
> sees the dashboard change but never gets a notification is worse off than one
> who gets neither.
>
> **`mark_complaint_read(...)` and `complaint_read_state`.** The table has been
> in the baseline from the beginning with nothing writing to it. It is what makes
> `isUnread` mean anything, and it is per membership, so an admin opening a
> complaint cannot clear the resident's marker.
>
> **`update_complaint` and `add_complaint_comment` replaced.** The events a
> resident most needs to hear about are the ones an *admin* causes, so two of
> `0020`'s functions gained a `notify_member` call inside the transaction they
> already had. §7's rule — a notification retrofitted onto a working write path
> fires for some callers and not others — is exactly why this is a replacement of
> the one writer rather than a trigger or a second path.

**Visitor passes**
- `visitor_requests.purpose text`, `.purpose_details text`, `.guest_count integer not null default 1`
- ~~`visitor_requests.code_hash text unique`~~ — the short code (§5.4). **Built as a partial unique
  index on `(community_id, code_hash)` over live passes only.** Six digits is 900,000 values, so a
  project-wide index collides at a few hundred live passes and every collision is one community's
  pass failing because an unrelated community holds that number. A code has to be unambiguous where
  and when it is used. That in turn requires something to retire a lapsed pass, because an index
  predicate cannot ask the clock — hence `expire_visitor_passes(...)`, without which the space leaks
  rather than recycles. `0032`, 2026-08-04.
- `visitor_pass_overview` view
- `create_visitor_pass(...)`, `decide_visitor_pass(...)` RPCs
- Added in build: `visitor_code_ttl_minutes(...)`, `expire_visitor_passes(...)`,
  `is_community_security(...)`, `notify_community_roles(...)`, and RLS on `visitor_requests` /
  `visitor_events`, which had none since the baseline

**Resident read views** — `0033`, **written**
- `resident_invoice_overview`, `resident_booking_overview`, `household_overview`,
  `management_contact_overview` views, plus `resident_notice_overview`
- ~~Extend the `0007` trigger loop to the tables residents watch~~ — **not done, and
  deliberately.** Every write this step adds already calls `notify_member`, which
  emits an SSE row through `0030`'s trigger. A second path from the same tables
  would deliver the same change twice and give a resident's phone two reasons to
  buzz for one payment. The trigger gap on `0018`–`0023` remains open for the
  tables *nothing* writes through an RPC.

> **Five things the build added that this list did not anticipate.**
>
> **`unit_contacts`, a table.** §6 has `POST /me/household/phones` and §7 assumed
> `household_overview` could serve it from existing rows. It cannot: the
> prototype implements *add a number* by inventing a whole user, and here
> `profiles.id` references `auth.users`, so a person with no account cannot be a
> profile. Manufacturing a membership for a phone number would put somebody in
> the community's member count who cannot log in and never agreed to join. A flat
> contact is a different kind of thing and gets its own table; `source` on the
> view is what keeps the two apart on the wire.
>
> **`resident_notice_overview`.** §7 listed four views and the notice board was
> not one of them, because notices looked like a read of an existing table. Two
> vocabularies (`urgency` is stored lower case and rendered title case) and one
> exclusion (drafts) is a projection, not a filter.
>
> **RLS on `notices`, `unit_residencies` and `departments`.** None of the three
> had any, so every authenticated user in the project could read every notice,
> every residency — *who lives in which flat* — and every department. Fifth
> instance of the timing rule: the policy ships in the migration that first
> serves the data.
>
> **A resident may now read their own booking charges.** `0023` made
> `amenity_booking_charges` admin-only, reasoning that the ledger is not a
> community-wide fact. True of the community and false of the resident: the one
> person entitled to know what a booking costs is the one being asked to pay for
> it.
>
> **`payment_failed`, a fifth `amenity_financial_events` type.** The four that
> existed had no word for *this did not go through*. A decline written as a
> `charge` puts a phantom line in the admin's ledger; written as a `payment` it
> shows the booking as paid. Every aggregate in `amenity_ledger_overview` filters
> on the type, so the new one counts towards nothing.

**Payment simulation** — §11, `0033`, **written**
- `payments.failure_code text` — null unless `status = 'failed'`; the stable
  reason, not prose. A CHECK enforces the "unless", because a code on a succeeded
  payment is a contradiction
- `payments.instrument_label text` — the masked display line (`•••• 4242`,
  `resident@upi`). **No PAN, no CVV, no expiry is stored anywhere** (§11.3)
- `settle_resident_payment(p_invoice_id, p_payload)` — the resident-side
  counterpart to the admin's `record_payment`, and the only writer that may
  record a `failed` payment. Writes `payments` + `payment_events`, recomputes the
  invoice status from `succeeded` rows only, and calls `notify_member(...)`, all
  in one transaction
- `settle_amenity_booking_payment(p_booking_id, p_payload)` — same shape,
  confirms the booking on success and leaves it untouched on failure. This is
  the transaction `US-2.12` is asking for
- **No new index.** The baseline's `unique (community_id, idempotency_key)` is
  already the right constraint; what it needs is a stated rule about who mints
  the key and when (§11.4)

**Not proposed:** a notice `effective_from` column for `US-2.11`. It is a
one-column change, but notices are the admin workstream's table and the story is
theirs to schedule.

---

## 8. Open questions

Answers change the work; they are not blocking, and defaults are noted.

1. **Are the SLA hours per-community?** Default: hard-code 24/48/72 in the RPC,
   matching the frontend. A `community_settings` key would be better and is a
   later, non-breaking change.
2. ~~**May a resident cancel a pre-approved visitor after arrival?**~~
   **Answered: no — keep the default. `checked_in` is terminal for the
   resident** (`PO`, 2026-08-04). Once the guest is through the gate, "cancel"
   is a physical-world operation and no database write performs it; letting the
   pass flip back would produce a record that disagrees with what happened.
   `decide_visitor_pass(...)` and the cancel path therefore reject any
   transition out of `checked_in` with a stable `pass_already_used` code and a
   409, in the RPC rather than the service — same reasoning as §5.2, the
   invariant lives next to the data. What a resident *can* still do afterwards
   is nothing that changes the record: the pass appears under
   `?view=history` and that is the whole affordance.
3. ~~**Should `POST /invoices/{id}/pay` exist before a gateway does?**~~
   **Superseded.** There is a gateway — we are building it, and it is a
   simulator (`PO`, 2026-08-04). See §5.5 and §11. The endpoint ships, and it
   ships able to report both outcomes.
4. **Who owns the building-representative link (`US-2.10`)?** Needs a
   `buildings` ↔ department-head relation nobody has scoped.
5. ~~**Does the resident portal need live updates?**~~ **Answered: yes — every
   update live for every user, and push notifications as well.** That is the
   requirement §10 is built to. It also promotes §3.5 from a latent flaw to the
   first thing that must be fixed.
6. ~~**May a push body contain names and flat numbers?**~~ **Answered: yes —
   the push carries the detail** (`PO`, 2026-08-04). *"The push body must contain
   all details as it helps with UX of the resident — he knows who is coming and
   can make an easy choice."* **This reverses the default this document
   proposed**, and the default was wrong on the requirements, not merely
   over-cautious: `US-2.1`'s recorded pain point is *"notifications sometimes
   produce only a notification sound without displaying the actual
   notification"*. A generic *"Visitor at the gate"* is a milder version of the
   exact failure the story exists to fix. Detail in §10.8, including the one
   thing that still may never appear in a push body.
7. **Per-kind notification preferences?** Default: all-or-nothing for v1 —
   subscribing opts in, unsubscribing opts out. A `notification_prefs` jsonb on
   the membership is a clean later addition and nothing here forecloses it.
8. ~~**Who generates and holds the VAPID keypair?**~~ **Answered: the same
   person who holds `SUPABASE_SERVICE_ROLE_KEY` for that environment, and it
   lives in the environment exactly as that key does** (`PO` asked for the most
   secure option that fits the existing framework; the answer and the four
   rejected alternatives are §10.5). One pair per environment, never shared
   between them. Generated by `scripts/generate_vapid_keys.py`, which prints to
   stdout and writes nothing.

---

## 9. Build order

Each step is independently shippable and testable.

| # | Step | Closes | Status |
|---|---|---|---|
| 1 | `0028` + audience scoping in the hub + `GET /events` | **§3.5 — the disclosure** | **Done** — 2026-08-04 |
| 2 | `GET /amenities/available` (+ `0029`) | §3.1 — unblocks a shipped write path | **Done** — 2026-08-04 |
| 3 | Notification substrate (`0030`) + feed + push subscriptions + sender | US-2.1, 2.4, 2.7 | **Done** — 2026-08-04 |
| 4 | Complaint endpoints, emitting notifications (`0031`) | US-2.5, 2.6, 2.8 | **Done** — 2026-08-04 |
| 5 | Visitor endpoints (`0032`) | **US-2.2**; US-2.1 only in part | **Done** — 2026-08-04 |
| 6 | The payment simulator, money, notices, household, directory (`0033`) | **US-2.12**; US-2.9 in part | **Done** — 2026-08-04 |
| 7 | `GET /resident/snapshot`, including the unread count | US-2.3 **in part** | **Done** — 2026-08-04 |
| 8 | Regenerate spec, annotate, update `API.md` §16 | Traceability | **Done** — 2026-08-04 |

**Step 7 closes US-2.3 only in part, and the remainder is not an endpoint.** The
story asks for one-tap access *"including a home-screen widget"*. The aggregate
is the enabling backend its own *"Backend: None"* note calls for — everything the
screen shows in one call, with pending passes carried whole so answering one is a
tap. A home-screen widget is an operating-system surface, and this is a web
application with no native client (§4). No endpoint closes that half.

Step 8's section number moved twice while it was pending: the matrix is `API.md`
§16, the changelog §17.

**Done means merged, tested and documented — not written.** A migration is a
separate question again: none has been applied to any database, `0001` included,
and applying them is not this workstream's to do.

The ordering changed when live updates became a requirement. §3.5 is first
because it is the one item that is a defect in shipped code rather than a
missing feature, and because every later step points more clients at the stream
it affects. Step 2 stays near the front for the opposite reason: it is small and
it makes an already-deployed endpoint usable. It was planned as the step that
needed no schema change and shipped as one, then gained `0029` immediately
afterwards — which is why the steps above no longer name a migration each. The
schema changes are listed in §7 and take their numbers, from the resident range,
when they are written.

Steps 4–6 each land their feature *and* its `notify_member` calls together. A
notification retrofitted onto a working write path is how you get an event that
fires for some callers and not others.

Step 6 grew when the payment gateway turned out to be a simulator we build
rather than an integration we defer. It stays one step because the simulator is
a pure function and the settlement RPCs are the same shape as the money RPCs
already in that step — splitting it would separate the two halves of a single
transaction across two shippable units, which is the one thing `US-2.12` is
about not doing.

**Every step also updates its own documentation, and that is part of the step,
not a phase at the end.** New endpoint → its `api_annotations.py` entry with
error codes and `x-user-stories` traced against `docs/product/`, then
`python scripts/export_openapi.py` to regenerate `docs/openapi.yaml`, then the
matching `API.md` section. The exporter's two-way guard fails the build if an
operation has no annotation, so this is enforced rather than remembered. Step 8
is the *matrix* pass — `API.md` §15 as a whole, and the reverse-direction check
that no story silently lost its endpoint — not a catch-up for skipped work.

---

## 10. Live updates and push notifications

The requirement is that **every update is live for every user, and push
notifications are delivered as well.** That is a bigger change than adding a
second stream endpoint, because the existing machinery was built for a handful
of admins watching one screen and is about to serve every resident in a
community.

### 10.1 Three layers, and only one of them is durable

| Layer | Mechanism | Lifetime | Reaches |
|---|---|---|---|
| Record | `notifications` row | Forever, until read and pruned | Anyone, later |
| In-app live | SSE frame | The connection | An open tab |
| Out-of-app | Web Push | One delivery attempt | A closed tab, a locked phone |

The failure to avoid is treating the stream as the notification system. SSE is
at-most-once and connection-scoped — the admin design makes *"the payload is a
hint, never truth"* load-bearing, and it is only safe **because** of that rule.
A resident whose phone was locked when a visitor reached the gate must still
find out. So the row is written first and the two transports carry it (§5.8).

This also makes the whole thing testable without a browser: assert the row
exists and the transports are separately unit-testable.

### 10.2 Audience scoping the outbox

> **Built.** `0028_event_audience.sql` and `_Subscriber.accepts`. Two details
> arrived in the building that this section did not anticipate, both recorded
> below: the shape `check` constraint, and the role-dependent resync topic.

`sse_events` gains three columns and the hub gains a filter.

| `audience` | Delivered to | Used by |
|---|---|---|
| `community` | Every subscriber in the community | Genuinely community-wide news (a published notice) |
| `role` | Subscribers whose role ∈ `audience_roles` | `dashboard.refresh`, `access_request.*` |
| `member` | The one subscriber matching `recipient_membership_id` | Everything a notification produces |

`_Subscriber` carries `membership_id` and `role` alongside `community_id`, both
read from the membership `get_active_membership` resolved — never from a header,
a query parameter or a `Last-Event-ID`. The existing guarantee that *"a client
cannot widen its own stream by replaying someone else's `Last-Event-ID`"* extends
to the audience filter unchanged, because both derive from the same verified
value.

Retargeting `dashboard.refresh` to `{admin,manager}` is the load half of §3.5.
Residents were never its audience: the frame means "re-read the admin snapshot",
and a resident acting on it would fetch a snapshot they are not entitled to and
be refused. It has always been a wasted wake-up for them.

One consequence worth naming: **the resident portal does not get a blanket
refresh frame.** It gets specific topics, from notifications. That is
deliberate — a resident screen re-fetching on every row change in a 500-flat
community is the thundering herd described in §3.5.

**Two things the build added.**

*A `check` constraint, not just a default.* `sse_events_audience_shape_check`
makes the three audiences mutually exclusive and complete: a `role` row must
carry a non-empty `audience_roles`, a `member` row a `recipient_membership_id`,
a `community` row neither. The reader then fails closed on anything it cannot
classify. Either half alone is worse than both: a fail-closed reader without the
constraint turns a malformed row into a silent non-delivery, and a constraint
without a fail-closed reader means the day someone adds a fourth audience value,
every older process treats it as community-wide. The pairing is what makes a
malformed row unwritable rather than undeliverable.

*The resync frame needed a topic per role.* A connection that falls behind is
sent "you have a gap, re-read". The admin frontend already listens for
`dashboard.refresh` and this workstream does not edit frontend code — but `0028`
retargets that *topic* to `{admin,manager}`, so sending it to a resident would
contradict the migration in the same breath as the migration. So the synthesised
frame is `dashboard.refresh` for an admin or manager and `stream.resync` for
everyone else: one instruction, two names, chosen from the subscriber's verified
role. Any resident client must handle `stream.resync`; it is the only frame that
arrives with no domain event behind it.

*And one that stayed as written.* The reconnect backfill applies the filter
twice — narrowed in the query, decided in Python. Not belt-and-braces: the query
has a 100-row cap, so filtering only afterwards would let a burst of admin
traffic fill the page and hide a resident's own events behind it, while
filtering only in the query would put the security decision in a hand-written
PostgREST string. Together, a mistake in that string can lose an event and
cannot leak one.

### 10.3 The notification record

> **Built.** `0030_notifications.sql`, `notifications_repository`,
> `notifications_service`, `GET /notifications` and the two mark-read routes.
>
> **What this step does not do, stated plainly.** It does not close US-2.1,
> US-2.4 or US-2.7. A transport with nothing emitting into it delivers nothing,
> and the writes that will call `notify_member` — the visitor pass, the complaint
> transition, the published notice — are steps 4 to 6. Each is one line inside a
> write that has yet to exist, which is the difference between an architecture
> decision and a task, and it is the whole reason this step came first. Reporting
> those three stories as closed here would be reporting a pipe as water.

The baseline already declares the table, and **no backend code has ever touched
it**:

```
notifications (id, recipient_membership_id, kind, payload jsonb, read_at, created_at)
```

`recipient_membership_id` is exactly the dimension the outbox lacks — per
recipient, and tenant-scoped transitively through the membership. It needs an
index on `(recipient_membership_id, created_at desc)`, two columns for the push
sender's lease, and nothing else.

Rows are written by `notify_member(...)`, called **inside the RPC that makes the
change, in the same transaction**. Same discipline as the outbox and for the same
reason: a notification that can exist without its cause, or a cause without its
notification, is a bug that cannot be reproduced.

Kinds, derived from the resident screens and the admin ones already built:

| Recipient | Kinds |
|---|---|
| Resident | `complaint.status_changed`, `complaint.commented`, `complaint.resolved`, `visitor.approval_requested`, `visitor.checked_in`, `amenity.booking_decided`, `invoice.issued`, `invoice.due_soon`, `notice.published`, `payment.succeeded`, `payment.failed` |
| Admin / manager | `access_request.created`, `complaint.raised`, `complaint.reopened`, `amenity.booking_requested`, `payment.recorded` |

`payload` holds an id, a short title and a deep link — enough to render a feed
row and route a click, not a copy of the record. The record is fetched through
its own endpoint, where the ownership predicate already lives (§5.2).

`invoice.due_soon` is the one kind with no triggering write; it needs a scheduled
job. `0024` already establishes the pattern — schedule under `pg_cron` when the
extension is present, no-op when it is not.

### 10.4 The push sender: one worker, and a rule the hub does not have

> **Built.** `app/core/push.py`, `claim_push_batch`, and the two outcome
> recorders. Two details arrived in the building.
>
> *It is started from the application lifespan, not lazily.* The hub is started
> by its first subscriber, so a process serving no streams never polls. The
> sender is the opposite by definition: it exists to reach someone with nothing
> open, so a sender that waited for a connection would only ever run when it was
> not needed.
>
> *Nothing retries a send.* A transient failure increments the subscription's
> counter and the **next** notification is the retry. Retrying one notification
> against a struggling push service is how a backlog becomes a herd against
> Google's endpoint — and the row is in the feed regardless.

The sender mirrors `RealtimeHub` — one background task per process, not one per
client — and obeys one extra constraint:

> **The hub may drop. The sender may not duplicate.**

The hub tolerates multiple processes: each polls on its own cursor and fans out
to its own clients, so two workers means two harmless copies. The sender does
not: two copies reading the same unsent notification send the same push twice,
and a resident's phone buzzes twice for one visitor.

Claiming is therefore atomic, in the database:

```sql
claim_push_batch(p_limit int)
  update public.notifications n
     set push_sent_at = now(), push_attempts = push_attempts + 1
   where n.id in (
     select id from public.notifications
      where push_sent_at is null
        and created_at > now() - interval '1 hour'
      order by created_at
      limit p_limit
      for update skip locked)
  returning ...
```

`for update skip locked` is the whole mechanism. It is also why the claim marks
`push_sent_at` *before* the HTTP call rather than after: at-most-once is the
correct bias for a notification that buzzes a phone, and the row is still in the
feed either way.

The one-hour window is deliberate. If the sender is down for a day, those
notifications are still in the feed — they simply do not buzz. A phone that
vibrates at 3am about a visitor from yesterday is worse than silence.

Failure handling, which is most of the work in practice:

| Response | Meaning | Action |
|---|---|---|
| `201` / `200` | Accepted | `last_success_at = now()`, reset `failure_count` |
| `404` / `410` | Subscription is gone | **Delete the row.** Retrying a dead endpoint forever is how you get rate-limited by a push service |
| `429`, `5xx` | Transient | Increment `failure_count`, back off, drop after 5 |
| `413` | Payload too large | Log it. This is a bug in our payload, not a transport failure |

Each subscription is dispatched concurrently with its exception captured per
subscription — one dead endpoint must not stall a batch. `pywebpush` is
synchronous, so it runs in a thread, exactly as `supabase-py` does in the hub.

### 10.5 Where the VAPID keypair lives, and who holds it

> **Built.** `app/core/push_config.py` (`PushSettings`, a second `BaseSettings`
> reading the same `.env`), `GET /push/vapid-key`, and
> `backend/scripts/generate_vapid_keys.py`.
>
> **No real key was generated, held or seen while building this.** The script
> prints three lines to stdout and writes no file; it is run by whoever holds
> that environment's service-role key. The tests use strings shaped like keys —
> unpadded base64url of the right lengths — which sign nothing, because a real
> private key has no business in a repository.
>
> One thing the build added: `configuration_problem()` returns prose for a log
> line and **never echoes the value it rejected**. Half a private key in a log
> file is a leaked private key.

Web Push needs `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT` (a
`mailto:`). The private key never leaves the server. The public key is served by
`GET /push/vapid-key` — it is public by construction; that is what the pair is
for.

**Decision. Environment variables, read through a second `BaseSettings` class,
one keypair per environment, held by whoever holds that environment's
`SUPABASE_SERVICE_ROLE_KEY`.**

**Why this is the *most* secure option here and not merely the easiest.** The
instinct is to reach for something stronger than a `.env` file. The reason not
to is that the environment is *already* this application's trust root, and it
holds something considerably more dangerous:

> `SUPABASE_SERVICE_ROLE_KEY` bypasses row-level security on every table in the
> project. The VAPID private key signs a JWT that lets us push to endpoints an
> attacker would have to steal separately, from a table that is `service_role`
> only. **The secret we already keep in the environment is strictly the more
> valuable of the two.**

Putting the weaker secret behind a stronger mechanism while the stronger secret
stays in `.env` does not reduce risk. It adds a moving part, a second failure
mode, and a false sense of having done something. The way to actually raise the
floor is to protect the environment better — which protects both keys — not to
give one of them a private arrangement.

**Why it fits the framework we have.** `app/config.py` uses `pydantic-settings`
with `env_file=".env"` and `extra="ignore"`. A second `BaseSettings` subclass
with the same `model_config` reads the same file, ignores everything that is not
its own, and needs **no edit to `app/config.py` at all**. It inherits the
existing `.env` gitignore, the `.env.example` documentation habit, the
`@lru_cache` accessor pattern and the deploy story, for free.

| Rejected | Why |
|---|---|
| **Supabase Vault / a `secrets` table** | Reading it requires `SUPABASE_SERVICE_ROLE_KEY`, so the environment stays the root secret and nothing moved. Adds a network call on a startup path, and puts a private key into every database backup. |
| **Generate a keypair at boot** | Not inelegant — **broken.** `applicationServerKey` is baked into every browser subscription at `PushManager.subscribe` time, so a new key silently kills every stored subscription. With multiple uvicorn workers, each would generate a different one and pushes would fail at random. |
| **A cloud secret manager (AWS/GCP/Azure)** | The first infrastructure dependency outside Supabase, and it needs its own credential in the environment regardless. Real value at an org with a secrets platform; here it is one more thing to hold wrong. |
| **Committing a dev keypair "just for local"** | A committed private key is a leaked private key on the day the repository is shared, and the habit is what leaks the production one later. |

**Format: base64url, unpadded, single-line** — the raw P-256 private scalar and
the uncompressed public point, which is precisely what `py-vapid`, `pywebpush`
and the browser's `applicationServerKey` all want. A PEM in an environment
variable needs newline escaping, and escaped newlines are how a key gets
corrupted in a CI secret store at 2am.

**One pair per environment, never shared.** A subscription is bound to the key
that created it, so a shared development key means a developer's laptop can push
to production residents' phones. Different values, same discipline.

**Assignment (`PO`, 2026-08-04).** The keypair is an ops artifact, not a build
artifact. It belongs to the person who already holds that environment's
service-role key. `backend/scripts/generate_vapid_keys.py` makes this
reproducible: it prints three lines to stdout, writes no file, and is run by that
person. **This workstream neither generates nor sees a real key.**

**Fail closed, but do not fail loudly.** Missing or malformed keys set
`push_enabled = False`: the sender task does not start, `GET /push/vapid-key` and
`POST /push/subscriptions` return 503 with a stable `push_not_configured` code,
and **everything else in the product works normally.** Push is an enhancement, so
an unconfigured environment must not be a broken environment — the same shape as
`0024` scheduling under pg_cron when the extension is present and no-opping when
it is not. It is checked at startup so the answer is known before a resident
subscribes, rather than discovered on the first send.

**Rotation has a cost worth writing down.** Because subscriptions are bound to
the key, rotating it unsubscribes every browser *silently* — no error, pushes
simply stop arriving. There is no dual-key period to engineer; the protocol does
not offer one. The mitigation is on the client and is listed in §10.6: compare
`GET /push/vapid-key` against the stored `applicationServerKey` on load and
re-subscribe when they differ. Treat rotation as an incident response, not
routine hygiene.

**Boundary, unchanged.** `app/config.py` belongs to the auth workstream and this
one does not edit it — which is what the separate settings class is for. If the
auth owner would rather these three live in the central `Settings`, moving them
is a two-line change; flagged rather than assumed.

`pywebpush` is a new backend dependency and the first this workstream has added.

### 10.6 What the frontend must add before any of this is visible

Not our work — the standing constraint is that we do not touch `frontend/src` —
but it has to be said, because without it the feature is invisible:

- a service worker at `frontend/public/sw.js` with `push` and `notificationclick`
  handlers;
- a web app manifest, without which iOS cannot install the PWA and iOS gets no
  push at all (§5.11) — and since the product is web-only, an unreachable iOS
  resident stays unreachable;
- `Notification.requestPermission()` at a moment the resident understands, not on
  page load — a permission prompt fired on load is the reliable way to get
  permanently denied;
- a check on load that `GET /push/vapid-key` still matches the
  `applicationServerKey` the existing subscription was created with, and a
  re-subscribe when it does not — without this, a key rotation stops push
  permanently and silently (§10.5);
- an `EventSource` on `/events`.

None of these exist today: `frontend/public/` contains a favicon and an icon
sprite, and no resident page opens a connection of any kind.

So push ships **backend-complete and unverifiable end to end** until they do
that. Backend tests will cover subscription registration and idempotency, claim
atomicity under concurrent workers, payload construction, and `410` pruning, with
the HTTP call to the push service mocked. That is honest coverage of our half and
it should not be described as more.

### 10.7 Limits worth knowing now

- **Push payloads are capped at about 4 KB** after encryption. Another reason the
  payload is an id and a title, not a record.
- **One connection per tab.** Three tabs open is three streams. Fine at community
  scale; worth remembering before anyone reports "too many connections".
- **A buffering reverse proxy defeats SSE.** The existing endpoint already sends
  `X-Accel-Buffering: no` and `Cache-Control: no-cache`; the new one must too.
- **`sse_events` is pruned to two hours** (`0024`). Nothing durable may be built
  on it — which is §5.8, stated as an operational fact.
- **Delivery is not read-receipt.** A push that leaves our process may still not
  arrive. Nothing in the product may depend on a push having been seen.

### 10.8 What a push actually carries

**The push body carries the detail** — who is at the gate, which flat, which
complaint, how much (`PO`, 2026-08-04). This reverses the cautious default this
document originally proposed, and the reversal is correct on the requirements,
not merely a preference:

> `US-2.1`'s recorded pain point is *"visitor approval notifications sometimes
> produce only a notification sound without displaying the actual
> notification"*, and the story asks for *a visible push notification for every
> visitor-approval request, so that I never have to open the application*.

A generic *"Visitor at the gate — open the app"* is a milder version of the exact
failure `US-2.1` exists to fix. It also defeats the point: the resident is being
asked to approve or reject someone, and a decision needs the name.

**The privacy objection does not survive contact with the protocol.** RFC 8291
encrypts the payload end-to-end between our server and the browser, keyed to the
subscription's own `p256dh` and `auth` values. Google, Mozilla and Apple relay
**ciphertext they cannot read**. This is exactly consistent with why §5.11
rejected OneSignal and Pusher Beams — the objection there was that a third party
*receives the content*, and self-hosted VAPID is the option that does not have
that problem. Having paid for that property, we should use it.

What remains is the resident's own lock screen, showing information about the
resident's own flat, on a device where both Android and iOS already offer
"hide sensitive notification content when locked". That is their decision to
make and the OS already offers it.

**One thing may never appear in a push body: the visitor security code.** §5.4
makes it a hashed credential returned exactly once. A credential that arrives on
a lock screen is a credential readable by anyone holding the phone, and it would
undo the whole reason it is hashed. Names, purposes, flat numbers and amounts —
yes. The thing that opens the gate — never.

**"All details" is bounded by what a web push can render**, which is worth
stating because this is not a native notification (`PO`). What we get is:

| Available | Not available |
|---|---|
| `title`, `body`, `icon`, `badge` | Custom sounds, arbitrary layouts |
| `tag` — coalesce repeats into one notification | Guaranteed ordering |
| `data` — the deep link `notificationclick` opens | Anything while the browser is fully closed on desktop |
| Up to two `actions` (Approve / Reject) — **not on iOS** | Reliable delivery timing |

So the design is: **title and body carry the detail and are complete on their
own**, `tag` is the entity id so three gate attempts collapse into one line
rather than three, `data.url` is the deep link, and actions are progressive
enhancement that the flow never depends on — a resident who taps the body lands
on the same screen.

Two rules that hold regardless:

- **The push is rendered from `notifications.payload`, not composed separately.**
  One source, so the feed row and the lock-screen line can never tell different
  stories.
- **Still an id and rendered strings, not a record.** The 4 KB post-encryption
  cap in §10.7 is unchanged by this ruling, and the authoritative read is still
  the endpoint where the ownership predicate lives (§5.2).

---

## 11. The simulated payment gateway

**The requirement** (`PO`, 2026-08-04): the gateway is one we build. No money
moves. Any payment passes by default, with a few deliberate failure cases — a
card whose expiry date has passed being the worked example — *"so that we can
show we handle that too, and maintain business logic for this."*

That last clause is the whole brief. The point is not a fake success screen;
the point is that **every path a real gateway produces is exercised end to end**,
so that swapping in a real one later changes one module and nothing else.

### 11.1 A simulated payment must never be indistinguishable from a real one

This is the first decision and it constrains everything after it.

`payments.provider` already exists in the baseline, defaults to `'offline'`, and
the admin's `record_payment` writes exactly that. Resident payments settle with:

```
provider = 'simulator'
```

**Why it matters more than it looks.** A demo database becomes a staging
database becomes, occasionally, the thing somebody reconciles against a bank
statement. If simulated payments are written as `'offline'` — or worse, as a real
provider name — then the moment a real gateway is integrated, **nobody can ever
separate the money that moved from the money that did not.** That is not a
recoverable mistake; the information was never recorded. One string, written
correctly on day one, makes it a `where` clause forever.

It also gives the honest answer to the rule §5.5 has carried since the first
draft — *never report a payment as succeeded when no money moved.* The row does
say `succeeded`, because within the simulated gateway the payment did succeed;
and it says `simulator`, because that is which gateway said so. Both facts are
recorded, neither is implied.

The same reasoning gives `payment_events` its job. Every transition appends a row
— `initiated`, then `simulated_authorized` or `simulated_declined` — so the
audit trail has the same shape a real integration will produce (`authorized`,
`captured`, `webhook_received`). The table exists in the baseline and nothing has
ever written to it.

### 11.2 The outcome rules

Deterministic, derived from the input, no randomness. A demo that fails one time
in ten is a demo nobody can run twice.

**Cards** — the published Stripe test numbers, because they are the convention
every tester and reviewer already recognises, and they are values that cannot be
a real card:

| Instrument | Outcome | `failure_code` |
|---|---|---|
| `4242 4242 4242 4242`, expiry in the future | `succeeded` | — |
| **Any test card with an expiry date in the past** | `failed` | `card_expired` |
| `4000 0000 0000 0002` | `failed` | `card_declined` |
| `4000 0000 0000 9995` | `failed` | `insufficient_funds` |
| `4000 0000 0000 0069` | `failed` | `card_expired` (expiry-independent variant) |
| CVV not 3 digits, or expiry not a real month | `failed` | `card_invalid` |
| Anything else | rejected before the simulator runs | `card_not_supported` |

**UPI** — the only method the frontend currently enables:

| VPA | Outcome |
|---|---|
| `failure@…` or `fail@…` | `failed`, `payment_declined` |
| Any other well-formed `name@handle` | `succeeded` |

**Independent of instrument**, checked first, because these are business rules
rather than gateway behaviour: the invoice must belong to the caller's own
membership, must not already be `paid` or `void`, and the amount must equal the
outstanding balance. Each has a stable code — `invoice_already_paid`,
`amount_mismatch` — and each is enforced in the RPC, not the service (§5.2).

### 11.3 The simulator accepts test cards only, and stores none of them

**Decision.** A card number that is not on the published test list is rejected
with `card_not_supported` before the simulator evaluates anything.

**Why, and this is the part worth arguing.** A simulated gateway that accepts any
Luhn-valid number is a system that *will* be handed a real card — by a tester
being thorough, by a demo audience member being helpful, by a marker trying the
app the way a resident would. At that moment we are an application that received
a live PAN, with none of the obligations discharged that receiving one implies.
Restricting the input closes that by construction, which is worth more than a
warning banner that nobody reads.

It costs nothing against the brief. `4242 4242 4242 4242` with a future expiry
passes; the same card with a past expiry fails with `card_expired` — exactly the
demonstration that was asked for. And UPI, the path the frontend actually
enables today, accepts any well-formed VPA and passes.

**Rejected — accept any Luhn-valid number, as Stripe's sandbox does.** Stripe can
afford that because Stripe is PCI-DSS certified infrastructure whose entire
business is holding card data safely. We are a student project with a mock
gateway. Copying the affordance without the substrate is the mistake.

**What is stored:** `payment_method` (`card` | `upi`) and `instrument_label`, a
masked display line — `•••• 4242`, `resident@upi` — for the receipt row.

**What is never stored, logged, echoed in an error `details` block, or written to
`payment_events`: the card number, the CVV, and the expiry.** They are validated
by a pure function and discarded in the same call. The pydantic model carries
them as `SecretStr` so an accidental `repr()` in a log line or a traceback prints
`**********` rather than a number. Belt and braces, deliberately, because the
failure mode here is silent and permanent.

### 11.4 Idempotency, and what a retry means

The baseline's `unique (community_id, idempotency_key)` is already exactly the
right constraint, and `record_payment` already returns the existing row rather
than raising on a repeat. The resident path reuses both. What needs stating is
the client-side rule, because the constraint alone does not imply it:

- **One key per press of Pay.** A double-tap, a flaky network, a retried request
  — same key, same row returned, and the caller cannot tell whether it settled
  now or a moment ago. This is the case that stops a resident paying twice.
- **A new key for a new attempt.** After the client has *shown* the resident a
  decline, the next press is a different attempt and mints a fresh key.
  Otherwise a corrected card would replay the old failure forever.

The distinction is: the key identifies *an attempt*, not *an invoice*. Getting
that backwards produces either a double charge or an unpayable invoice, which is
why it is written here rather than left to whoever wires the button.

### 11.5 A declined payment is `200`, not an HTTP error

**Decision.** `POST /invoices/{id}/pay` returns `200` with an outcome object —
`{ paymentId, status, failureCode?, instrumentLabel, invoiceStatus }` — for both
`succeeded` and `failed`. HTTP errors are reserved for the request being wrong.

**Why.** A declined card is not a failed API call. The request was well-formed,
authorized, processed correctly, and produced a durable record; the *payment*
failed. Returning `402` would mean the client's error branch — the one that
handles "your session expired" and "the server is down" — also has to handle a
perfectly ordinary business outcome, and would have to dig a payment id out of an
`ErrorResponse` that has nowhere sensible to put one.

The client branches on `status`, which is a field. That is the same principle as
the error envelope's stable `code` (§6 of the admin document): give the consumer
something designed to be branched on.

`4xx` still means what it always meant — `403` for someone else's invoice, `404`
for one that does not exist, `409` for `invoice_already_paid`, `422` for a
malformed body.

### 11.6 The seam: where a real gateway will slot in

The simulator lives in **one Python module** — `app/services/payment_simulator.py`
— as a pure function:

```
simulate(instrument, amount) -> SimulatedOutcome(status, failure_code, instrument_label)
```

No database, no I/O, no clock beyond the expiry comparison. The service calls it,
then calls **one RPC** that atomically writes `payments` + `payment_events`,
recomputes the invoice status from `succeeded` rows only, and calls
`notify_member(...)`.

That split is the entire point of the design:

| Layer | Simulated today | With a real gateway |
|---|---|---|
| Router | unchanged | unchanged |
| Service | calls `simulate(...)` | calls the provider's SDK / HTTP API |
| **RPC** | **unchanged** | **unchanged** |
| Migration | unchanged | adds a webhook-receipt path |

**The simulator sits exactly where the real gateway will sit.** Swapping it is a
change to one module and one settings value, not a redesign — and every business
path downstream of it has already been exercised, because the simulator can
produce outcomes a real gateway would only produce by accident and never on
demand. That is the strongest argument for building the simulator properly rather
than stubbing a success: **the failure paths are the ones that are hard to test
against a real provider.**

Two consequences to hold on to:

- A real integration adds an **asynchronous** settlement path — the provider's
  webhook, arriving after the response. `payment_events` and the
  `idempotency_key` are already the right shape for it, which is why they are
  used now rather than added later.
- `provider` stays a column, never a constant. A community on a real gateway and
  a community still on the simulator can coexist in one database.

### 11.7 `US-2.12` is about the transaction, not the gateway

The story is *"a successful payment always yields a confirmed booking"*, from the
pain point *"amenity booking payments can fail even after money has been
deducted"*. That failure is not a gateway defect. It is a **payment recorded in
one transaction and a booking confirmed in another**, with a crash in between.

So `settle_amenity_booking_payment(...)` does both, or neither:

- on `succeeded` — write the payment, append the event, confirm the booking,
  notify the resident, notify the admins. One transaction.
- on `failed` — write the payment with its `failure_code`, append the event,
  **leave the booking exactly as it was**, notify the resident that it did not go
  through. Also one transaction.

The second half is the one that gets forgotten, and it is the one the story is
about: a failed payment must not leave a half-confirmed booking that a resident
believes they hold. A `failed` row also never enters the balance — every
recomputation sums `status = 'succeeded'` only, which is what `record_payment`
already does and what the resident path copies rather than reinvents.

This is why the simulator being able to fail *on demand* matters. `US-2.12` is
only demonstrably served if the failure path can be run in front of someone, and
with a real gateway in test mode that is a card you have to go and find. Here it
is one expiry date.

---

## 12. Coherence checklist

Every item is a paradigm from the admin backend that this design preserves.

- [x] Router → service → repository; no policy in routers, no SQL in services
- [x] Tenancy from `get_active_membership`, never from a body or a token claim
- [x] `require_membership_role` for role guards; CSRF on every unsafe method
- [x] Reads through views, writes through `SECURITY DEFINER` RPCs — **was an
      exception for one step; closed by `0029`, see below**
- [x] Additive, idempotent, `pglast`-validated migrations; baseline never edited
- [x] `camelCase` wire models in `app/domain/`, `Page[T]` for collections
- [x] `ErrorResponse` envelope; stable `code`, disposable `message`
- [x] Spec regenerated from the live app; annotation entry per operation
- [x] Every endpoint traced to a user story, or explicitly typed as not covered
- [x] Credentials hashed at rest, plaintext returned once (§5.4)
- [x] Live updates through the existing outbox — extended, not replaced (§10.2)
- [x] The stream's audience derived from the verified membership, never the client
- [x] One background worker per process, not one per connection (§10.4)
- [x] No provider token or third-party SDK reaches the browser (§5.11)
- [x] Secrets read from the environment through `pydantic-settings`, never
      committed, never generated at boot (§10.5)
- [x] Payment settlement is one transaction, as `record_payment` already is
      (§11.7)
- [x] Money is recomputed from `succeeded` rows, never accumulated (§11.7)
- [x] `provider` records which gateway settled a payment — simulated payments
      are permanently distinguishable from real ones (§11.1)
- [x] Credentials never appear in a push body, a log line or an error `details`
      (§10.8, §11.3)
- [x] Business outcomes are fields; HTTP errors mean the request was wrong
      (§11.5)

### The item that was not a clean tick, and how it was closed

For one step, `GET /amenities/available` read the `amenities` table directly.
Every other read in either backend goes through a view, so it was marked `[~]`
rather than quietly counted as compliance — the whole point of this checklist is
that divergence stays visible while it lasts.

The reason the paradigm exists is that a view is where the projection and its
RLS live, so a repository cannot select a column the projection did not intend.
The only view available then was `amenity_overview`, which exists to give the
*admin* card its badges: two lateral aggregates per row, counting bookings and
summing charges against payments. Reading it would compute both for a response
that discards them, and — the part that actually matters — would leave the
resident projection one column away from an admin field, because the next column
added to that view for the admin card is immediately in scope here. So the
choice at step 2 was between sharing a source that only one of the two consumers
gets to change and reading the base table with an explicit column list. The
column list was narrower in every sense that counts, and 3.1 is a finding about
exactly this failure — an amenity read shaped for one role and then handed to
another.

> **Closed, 2026-08-04, by `0029_bookable_amenity_view.sql`.** The third option
> — a resident view of its own — was rejected at step 2 on a schedule argument
> rather than a design one: it would have made the schema change of a step whose
> premise was *this needs no migration* non-zero. That argument expires the
> moment the next step needs a migration anyway, which step 3 does, so the view
> was written before it.
>
> `bookable_amenity` is two views over one table, each owned by the surface that
> reads it. It carries the resident column list, applies the row filter — active,
> not temporarily closed — and is `security_invoker` like every other view here.
> *Bookable* is now defined in one place instead of assembled by whoever writes
> the query.
>
> **One duplication is deliberate.** The service still applies the
> temporary-closure test in Python, on a column the view exposes and has already
> filtered on. No migration in this project has been applied to any database yet,
> so the view's predicate has never executed while the service's has tests behind
> it; the endpoint should not depend on which of the two is true. It is written
> as an exact transcription — every `jsonb` value Python reads as false, spelled
> out — because two readers disagreeing about whether the pool is shut is worse
> than either answer alone. When the migrations are applied and the SQL is real,
> the Python pass is the half to drop.
