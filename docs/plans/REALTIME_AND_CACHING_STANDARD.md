# Realtime and caching — the standard for every future feature

> **Status:** doctrine, adopted 2026-08-27. Not a plan for one feature — a
> standing rule for how a read gets fast, how it stays coherent when someone
> else writes, and what a new feature must do to hold up its end.
>
> **This file is frozen the way any other doctrine here is:** when reality
> forces a change, the deviation is recorded here with the fact that forced
> it, and a superseding ruling says explicitly what it overturns — the
> `docs/design/README.md` convention, applied to a standard rather than a
> one-off decision.
>
> - The backend transport this depends on — the outbox, the poller, audience
>   scoping, reconnect and retention — is described once, in
>   [`../ARCHITECTURE.md` § Live updates](../ARCHITECTURE.md#live-updates).
>   This file does not repeat that; it is the layer on top of it, plus the
>   client half `ARCHITECTURE.md` never had to describe until today.
> - The migration that added the three newest topics —
>   `20260826090000_realtime_expansion.sql` — is walked statement-by-statement
>   in [`MIGRATION_APPLY_RUNBOOK.md` §31](MIGRATION_APPLY_RUNBOOK.md).
> - The scheduler rules below are also the operating law for
>   `dispatch_tasks` generally; nothing here changes `SERVICE_OPERATIONS_PLAN.md`,
>   it just names the rules that plan's dispatcher already had to follow.

## Context — why this needed writing down today

Three workstreams landed together on 2026-08-27 (routers off the event loop,
a server-side TTL cache for reference data, three new SSE topics plus a
resync guard for reconnects that outlive the outbox's retention window) and
each one, alone, would have been a local optimization. Together they are a
layering rule: a screen has three different mechanisms telling it "your data
might be stale," and if a future feature reaches for the wrong one — a poll
where an SSE trigger belongs, a server cache on data that is not reference
data, a client that treats `dashboard.refresh` as if it meant "resync" — it
degrades quietly, the same way the pre-2026-08-27 dead pollers did. This
document is the checklist that stops that.

---

## 1. The layering rule

Four mechanisms, in the order a reader should reach for them, each answering
a different question:

1. **Client React Query cache — the primary cache, always.** `staleTime` and
   `gcTime` on the query itself decide how long a read is served with no
   network call at all. This is where "is this data fresh enough" is
   answered for every screen, reference data included. See §2.
2. **SSE invalidation — coherence, not truth.** A frame from `GET /events`
   never carries a payload to render; it tells the client which cached
   queries are now allowed to be stale and should be invalidated on next
   read. Over-delivery (a frame that nudges a client about data it cannot
   see) is safe by construction — the client re-reads through the endpoint
   whose own authorization scopes the answer, so a nudge about a row the
   client may not see just re-fetches an empty or unchanged result. See §3.
3. **Server TTL cache — for reference data only, and only with write-through
   invalidation.** `app/core/ttl_cache.py`'s `TTLCache` exists to take
   repeated, near-identical reads of *slow-changing, community-scoped
   catalogue data* off the request path — not as a general cache for
   anything a service happens to read twice. A dataset earns a server cache
   by being read far more often than it is written, and by every writer of
   it calling the matching `invalidate_*` in the same request that changed
   it (write-through, not TTL-only expiry). Today's four: the departments
   catalogue (`departments_service._LIST_CACHE`), complaint categories and
   department skills (`skills_service._CATEGORIES_CACHE`,
   `_DEPARTMENT_SKILLS_CACHE`), and the settings snapshot
   (`settings_service._SNAPSHOT_CACHE`) — the last one invalidated not only
   by its own module but by `money_service.update_billing_settings`, because
   `community_settings_overview` carries billing's own columns and would
   otherwise show stale toggles for up to the TTL after a billing write that
   never touches `settings_service` at all. See §6 for what staleness this
   trades away.
4. **Authenticated HTTP stays no-store, end to end.** Nothing in this stack
   asks the server to cache a response for reuse across requests or across
   callers — every `Cache-Control` on an authenticated read is still
   `no-store`, and the `timeAgo`-style relative-time rendering constraint
   (a timestamp computed server-side is stale the instant a cached response
   is replayed) is exactly why. The TTL cache in §3 does not change this: it
   caches inside one worker process, keyed by tenant, and every response it
   serves is still built fresh into an uncached HTTP response on the way out.

**The ordering is the point.** A feature that reaches for a server cache
before checking whether the client cache already covers its staleness budget
is solving a problem the client already solved; a feature that polls where an
SSE trigger would do is the exact defect this whole workstream retired.

---

## 2. QUERY_POLICIES — the client-side buckets

`frontend/src/lib/api/queryClient.js` exports four buckets, deliberately not
a rule engine — a call site either matches one of these or falls back to the
global default (`staleTime` 30s, `gcTime` 5min, set on the `QueryClient`
itself). A new bucket earns its place by being a distinct, recognizable class
of data with a distinct acceptable staleness — it is not added per screen.

| Bucket | `staleTime` | `gcTime` | For | Why |
|---|---|---|---|---|
| `reference` | 30 min | 60 min | Rarely-changing option lists — skills, complaint categories, department options, geo/community-search lookups | Whoever edits one sees it immediately on their own screen (their mutation invalidates it directly); everyone else can trust a half-hour-old copy |
| `snapshot` | 45 s | 5 min | Dashboard/snapshot reads — worker, resident and admin home, security overview, supervisor triage | The number on screen is a glance, not a ledger; it stops mattering once it's more than about a minute stale |
| `list` | 60 s | 5 min | Paginated/admin list screens — complaints, work orders, notices, people, conversations, hiring rosters, security registers | Short enough that a just-created row shows up on the next look; long enough that a tab switch or filter round-trip doesn't refetch every time |
| `detail` | (falls back to 30 s default) | 5 min | Single-record detail reads — a modal, a detail page | No override on `staleTime`; `gcTime` is still explicit rather than left to Query's own 5-minute default |

Spread the bucket onto the query alongside its key:

```js
useQuery({ queryKey: ['skills'], queryFn: workerApi.skills, ...QUERY_POLICIES.reference });
```

`PAGINATED` (`{ placeholderData: keepPreviousData }`) is a separate, additive
export for paginated/filtered lists — it keeps the previous page's rows on
screen (`isPlaceholderData: true`) while the next page loads, instead of
collapsing the list to a loading state on every page or filter change. Spread
it alongside `QUERY_POLICIES.list`, not instead of it.

**Rule for a new endpoint:** every `useQuery` call declares one of the four
buckets (or the documented reason it falls back to the global default). A
query with no bucket and no reason is a review comment waiting to happen.

---

## 3. SSE — audience rules and the topic table

### Audience is not optional, and it is not a suggestion the client enforces

Every outbox row (`sse_events`) declares who may receive it, and the shape is
a `check` constraint, not convention — a malformed row is unwritable, never
silently undeliverable:

| Audience | Delivered to | Chosen when |
|---|---|---|
| `community` | every subscriber in the community | the readers who may see the underlying row don't map onto a role list, or over-scoping to the whole community is cheaper and safer than guessing narrow (see `work_order.changed` below) |
| `role` | subscribers whose role is in `audience_roles` | the readership genuinely is a role — `dashboard.refresh`, `access_request.*`, both `{admin, manager}` |
| `member` | the one subscriber matching `recipient_membership_id` | the frame is addressed to one person — `notification.created`, `message.created` |

**Frames are hints, never truth, and over-delivery is safe.** A frame that
reaches a client who is not actually allowed to see the row it's about costs
that client one re-read through an endpoint whose own authorization already
scopes the answer — an empty or unchanged result, not a leak. *Under*-scoping
is the failure mode that matters: guessing a narrow `role` list for a
readership that doesn't cleanly map onto roles risks silently dropping the
frame for someone who needed it. This is why `work_order.changed` (added
2026-08-26) is `community`-scoped rather than role-scoped: the four
populations who may read a given job (`can_read_work_order`) don't collapse
onto any role list, and a `role` row would have to guess. **Recorded as
future work, not done today:** narrowing `work_order.changed` to the owning
department once there is a cheap way to compute that audience at trigger
time — today's choice is deliberately the safe, wider one.

### The topic table

| Topic | Audience | Added | Fires on | Payload |
|---|---|---|---|---|
| `dashboard.refresh` | `role` `{admin, manager}` | `0007`, retargeted `0028` | any write to one of 12 domain tables | `{"table": "..."}` |
| `access_request.created` | `role` `{admin, manager}` | `0024`, retargeted `0028` | someone asks to join the community | request id, applicant name, relationship, `pending_count` |
| `access_request.decided` | `role` `{admin, manager}` | same | a request is approved, rejected or blacklisted | request id, `from`, `to`, `pending_count` |
| `notification.created` | `member` | `0030` | any `notifications` insert | notification id, kind |
| **`work_order.changed`** | **`community`** | **`20260826090000`** | insert/update/delete on `work_orders` | table, work order id, complaint id, status |
| **`amenity.changed`** | **`community`** | **`20260826090000`** | insert/update on `amenity_bookings` (and `amenity_booking_series` where the table exists) | table, amenity id |
| **`message.created`** | **`member`** | **`20260826090000`** | insert on `dm_messages`, resolved per recipient's active membership in the thread's community | thread id, message id — no body |
| `stream.resync` | the affected connection | always existed, now has a second trigger | this connection fell more than 64 events behind, **or** reconnected with a `Last-Event-ID` older than the outbox's oldest surviving row | `{"resync": true}` |

The three bold rows are today's addition — filling the gap the runbook's §31
opens with: a work order changing, a slot being booked, and a message
arriving all used to reach nobody outside the admin's `dashboard.refresh`,
so every non-admin surface degraded to "look live, is not."

**`stream.resync` gained a second trigger today, not a second meaning.** It
already fired when a slow consumer fell more than 64 events behind. It now
also fires on reconnect when the client's resume point predates what the
outbox still holds — the prune horizon, two hours out
(`prune_sse_events`, `0024`). Before this, a client away longer than the
retention window reconnected, got a backfill that silently started in the
middle of its history, and believed it was caught up — a gap with no
symptom. `app/core/realtime.py`'s `_backfill` now probes
`dashboard_repository.oldest_event_id()` before replaying the backfill and
prepends a `stream.resync` frame when the oldest surviving row is past the
client's resume point. **The probe fails open**: if it errs, the backfill
proceeds without the resync frame rather than dropping the connection — a
missed resync is a client that stays slightly behind, not one that is denied
service over an unrelated failure.

---

## 4. One `EventSource` per tab, and the uniform fallback

**Consumer-side architecture, `frontend/src/lib/realtime/`:**

- `eventStream.js` — the tab's **one** connection to `GET /api/v1/events`,
  lazily opened on the first subscriber and closed on the last, ref-counted.
  Before this module there were, or were about to be, up to four openers per
  tab (the resident portal, the admin dashboard bootstrap, the notification
  bell, the chat dock) — four `EventSource` objects is four server-side
  asyncio tasks and four outbox fan-outs for one stream every listener
  wants a slice of. `STREAM_TOPICS` lists every named frame the backend can
  emit; `EventSource` only routes a *named* frame to a listener registered
  under that exact name, so a topic missing from this list is silently
  dropped, not delivered as `message`.
- `frameQueries.js` — the pure mapper, `queriesForFrame(frame, map)`: given
  one frame and one portal's map (`always` / `resync` / `topics` / `kinds`),
  returns the query-key prefixes to invalidate. This is the one part of the
  wiring worth unit-testing directly, because its failure is silent — a
  screen that quietly stops updating — while the hook around it
  (`useLiveUpdates.js`) is a subscription plus a `for` loop over the result.
- `portalMaps.js` — the per-portal maps (`WORKER_EVENT_MAP`,
  `MANAGER_EVENT_MAP`, `NOTIFICATION_EVENT_MAP`, `CHAT_EVENT_MAP`); the
  resident map (`residentKeys`) stays with its feature at
  `features/resident/residentEvents.js` because it is written in terms of
  those keys.
- `useLiveUpdates.js` — `useLiveUpdates(map)` mounts the subscription and
  calls `queryClient.invalidateQueries` per returned key; `useStreamLive()`
  exposes connection state; `useSseFallbackInterval(degradedMs?)` turns that
  state into a `refetchInterval` — `false` while the stream is live, the
  slow interval otherwise.

**Mounted portal-wide**, in the layout, so one subscription covers every page
under it rather than resubscribing per navigation: `WorkerLayout`,
`ManagerLayout` (or equivalent) and the resident layout each mount their own
map once. `NotificationBell` and `ChatDock` mount their own small maps
directly, because they render inside portals — admin included — that have no
shared layout mount. The admin portal keeps `DashboardDataBootstrap`, now fed
by the same shared stream through `subscribeToDashboard` rather than opening
its own connection. **The security portal is not wired yet** — deferred, not
forgotten.

**The fallback rule (doctrine, "C3"):** SSE invalidation replaces polling
outright. A poll survives only as a uniform 5-minute (`SSE_FALLBACK_INTERVAL_MS`)
degraded fallback, and only while `useStreamLive()` is false — no
`EventSource` in this runtime, or the connection currently in its `error`
state. This is why `NotificationBell`'s old 60-second poll and `ChatDock`'s
old 20/30/90-second polls are gone: they are now the same call,
`useSseFallbackInterval()`, and fire at the fast interval only when there is
no live stream to trust instead.

**The reconnect rule (doctrine, added 2026-08-27): the client reopens the one
close the browser will not.** `EventSource` retries a *transport* failure by
itself — the connection drops, `readyState` goes back to `CONNECTING`, `open`
fires again, and nothing in this codebase should interfere with that. An HTTP
error **response** is a different event: a `403` or any `5xx` on
`GET /api/v1/events` makes the browser fire `error` once, park `readyState` at
`CLOSED` (2), and never try again. The tab's realtime is then dead for the
lifetime of the page, and only a full unmount and remount of every subscriber
would rebuild it.

The observed trigger is not hypothetical and is not an error: a session that
signs in **before its membership is approved** gets a `403` from the stream
endpoint, and the approval that arrives seconds later has nowhere to land. The
same shape covers any deploy-window `5xx`.

So `eventStream.js` schedules its own reopen on a fatal close, under four rules
that any future change to this module keeps:

1. **Only on a fatal close.** The `error` handler returns early unless
   `readyState` equals `EventSource.CLOSED` — read off the global rather than
   hard-coded, with the spec's `2` as the fallback, so a polyfill that
   renumbers the states is still understood and a stub carrying no `readyState`
   at all reads as *not fatal*. A transient error is left to the browser.
2. **Backoff 5 s, doubling to a 60 s cap, reset on `open`.** A connection that
   got as far as `open` was a working one, so the next outage starts from 5 s
   again rather than from wherever the last one climbed to. The cap is what
   keeps an unapproved tab left open all afternoon from being a poll.
3. **Only while somebody is listening.** The reopen is scheduled only when
   `subscribers.size > 0` and re-checks it when the timer fires; `close()` —
   which runs when the last subscriber unsubscribes — cancels any pending timer
   and resets the delay. The promise that a signed-out tab holds nothing open
   is worth little if a fatal `403` on the way out leaves a timer behind to
   reopen the stream nobody wants.
4. **The wait is covered, not hidden.** `setLive(false)` fires on the way into
   the outage, so `useSseFallbackInterval` is already polling at the degraded
   interval through the whole backoff. The reconnect is an upgrade back to live
   updates, never the only thing standing between a screen and its data — which
   is the same reason §1 puts SSE in layer 3.

A dead handle can also fire a late `error` after it has been replaced; every
listener therefore checks `source !== instance` and returns, so the retiring
connection cannot close the one that succeeded it.

**`dashboard.refresh` is not `stream.resync`, and a map has to say so
explicitly.** `dashboard.refresh` fires on every row change across twelve
tables — treating it as "resync everything" would refetch a portal's whole
world on someone else's unrelated write. `stream.resync` is the only frame
meaning "everything you show may be stale"; a map that wants the broadest
possible reaction to it uses `ALL_QUERIES` (`frameQueries.js`'s frozen `[]`,
which is a prefix of every React Query key), not an enumeration that can
silently fall behind the screens it's supposed to cover.

---

## 5. Scheduler non-interference rules

`dispatch_tasks` and the code that reads its due queue (`dispatch_tasks`
workers, `fire_dispatch_task`, and every RPC a screen's countdown ultimately
depends on) follow four rules, binding on every future feature that adds a
time-based state change:

1. **Time-based state changes happen only through `dispatch_tasks` or
   derive-on-read.** Nothing outside those two paths flips a status because
   a clock reached a value — a cron job, a frontend timer firing a mutation,
   or a lazily-checked "if now > deadline" outside a read path are all the
   same mistake: a state change nobody's transaction caused and nothing
   audits.
2. **Scheduler mutations are idempotent against racing user actions**, and
   signal what they did through the standard triggers (a `notifications`
   row, an `sse_events` frame) rather than a side channel. A resident
   resolving a complaint the instant before the scheduler's own timeout fires
   must not produce two conflicting outcomes or a corrupted timeline —
   the scheduler's write has to be safe to be a no-op against a state the
   user already moved past.
3. **Clients render countdowns from server deadlines, never act on local
   timers.** A screen showing "auto-assigns in 4h12m" reads that deadline
   from the row it fetched; it never independently decides the deadline has
   passed and behaves as if the server-side effect already happened. The
   local clock can be wrong, paused (a backgrounded tab), or simply racing
   the actual dispatch — only the server's own state change is truth.
4. **A backfill that would silently skip past the prune horizon is refused.**
   A reconnecting client (or, by the same logic, any consumer resuming from
   a stored cursor) never gets a backfill that quietly starts in the middle
   of its own history — see §3's `stream.resync` prune-horizon trigger. The
   scheduler side of this rule is the same shape: a due-queue read must never
   silently treat "found nothing due" as "nothing was ever due and missed" —
   if a gap is possible, it has to be visible, not assumed away.

These are not new to this workstream — the dispatcher in
`SERVICE_OPERATIONS_PLAN.md` already had to obey (1)–(3) to be safe across
processes (`F3`/`F4` in that plan). (4) is new, added by today's resync guard,
and is now doctrine for any future scheduler-adjacent feature, not just SSE
reconnects.

---

## 6. Accepted staleness — what §1's layer 3 deliberately trades away

Every server TTL cache entry in §1 accepts up to 60 seconds of staleness
**on the specific fields it caches**, in exchange for taking a repeated,
near-identical read off the request path. Named here so a future bug report
("the departments list didn't update") is checked against this list before
it is treated as a defect:

- **Staff hire or removal does not invalidate the departments list.** The
  cached departments catalogue (`departments_service._LIST_CACHE`) does not
  carry per-staff data as a cache key, so adding or removing a staff member
  does not itself bust the 60-second window; a viewer sees the roster count
  update within that window, not instantly.
- **A renamed global skill's new name is stale in the categories cache** for
  up to the same window — `skills_service._CATEGORIES_CACHE` reads through
  the skill's current name, and a rename does not walk every cached
  community's categories entry to patch it in place.
- **Complaint counts embedded in the cached departments listing** age the
  same way — a complaint raised or resolved in the last 60 seconds may not
  yet be reflected in a department row's count on someone else's cached
  read, even though the resident or admin who caused it sees their own
  change immediately (their own request invalidates the key it just wrote).

None of these is a correctness bug: every write that changes what a cache
key holds still invalidates that key, in the same request, on the worker
that handled it (§1, layer 3) — the trade is scoped to a second reader on a
**different** process seeing the old value for up to one TTL window, the
same trade `app/core/realtime.py`'s SSE hub already accepts for being
per-process rather than shared.

---

## 7. New-feature checklist

Before a feature that adds a read, a mutable surface, or a time-based state
change is called done, confirm all that apply:

- [ ] **(a) Every new `useQuery` declares a `QUERY_POLICIES` bucket** (§2) —
      `reference`, `snapshot`, `list` or `detail` — or states in review why it
      falls back to the global default. A paginated list also spreads
      `PAGINATED`.
- [ ] **(b) Every mutable surface that other users need to see live gets:**
      an SSE trigger on the table it writes (a new `emit_*` function or an
      existing one extended, with the audience chosen per §3's rule — prefer
      `community` over guessing a `role` list that might drop someone), a
      frame-map entry in the relevant portal's `portalMaps.js` (or a new
      portal map, mounted at the layout level per §4), and invalidations
      narrow enough that the feature does not become the next `dashboard.refresh`
      — a map entry names the specific query-key prefixes the new topic makes
      stale, not `ALL_QUERIES`, unless the reads really are too scattered to
      enumerate honestly.
- [ ] **(c) Anything time-based follows all four scheduler rules in §5** —
      in particular, no new cron-like check outside `dispatch_tasks` or a
      derive-on-read path, and no frontend timer that acts rather than
      displays.
- [ ] **(d) The endpoint is documented per the house API-docs standard** —
      `docs/API.md`, `docs/openapi.yaml` (regenerated, never hand-edited) and
      `docs/api_yaml_mapper.md`, status codes included — and, if it adds an
      SSE topic, the topic is added to `docs/API.md` §5.1's frame table, this
      document's §3 table, `ARCHITECTURE.md`'s Topics table, and
      `frontend/src/lib/realtime/eventStream.js`'s `STREAM_TOPICS` (the
      client silently drops any topic missing from that list).
- [ ] **(e) If the feature adds a server-side cache**, it is reference data
      by §1's test (read far more than written, community-scoped, slow to
      change) and every writer of it calls the matching invalidation in the
      same request — TTL-only expiry with no write-through is not this
      pattern, and does not belong in `app/core/ttl_cache.py`'s pattern.

A feature that satisfies (a)–(e) can cite this checklist in its own PR
description or plan document instead of re-deriving the reasoning above.
