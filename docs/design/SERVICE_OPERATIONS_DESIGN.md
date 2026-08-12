# Service operations — the third surface

**Status:** in build. **Steps 1–9 of 12 are done — the backend is complete and
three portals render against it: the worker's, the manager's hiring screen and
the shared hiring conversation**; 10–12 are the documentation sweep, the full
verification and the dead-code pass. **The gate screens are not scheduled by any
step and that is a gap in the plan rather than a decision** —
`plans/SERVICE_OPERATIONS_PROGRESS.md` §4.25. See
[`../plans/SERVICE_OPERATIONS_PROGRESS.md`](../plans/SERVICE_OPERATIONS_PROGRESS.md)
for what exists in the branch today, which is ahead of what this document
describes in two places and behind it in none.
**Audience:** whoever maintains this after us.
**Read first:** [`ADMIN_DASHBOARD_DESIGN.md`](ADMIN_DASHBOARD_DESIGN.md). It
establishes the layering, the authorization seam and the read/write split. This
document says *"as in the admin backend"* and does not repeat them.

**This is not the decision record.** The fifteen decisions, each with the
alternative that was rejected and why, are in
[`../plans/SERVICE_OPERATIONS_PLAN.md`](../plans/SERVICE_OPERATIONS_PLAN.md) —
they were made with the product owner across three rounds of questions and it
would be dishonest to relocate them here as though they were derived. What
follows is the part the plan does not cover: **why the new surface does not
break the two that already exist.**

---

## 1. How the requirement was derived

Not from a written spec. From a product-owner document describing a service
person's dashboard and a departments data model, read against five existing
artifacts — the frontend, the ERD, the class diagram, the component design and
the migrations — with every contradiction surfaced as a question rather than
resolved silently. Twelve questions; twelve answers; `D1`–`D15`.

The method matters because two of the answers **overturned things already
written down**, and the `README.md` convention here requires a ruling that
overturns something to name what it overturned:

- `docs/CONFLICT_RESOLUTIONS.md` **R16** parked twelve baseline tables with
  *"build nothing against them"*. Seven of them are now un-parked.
- `docs/product/USER_IDENTIFICATION.md:55-65` and `API.md` §16.1 both state that
  a staff member has no login *by construction* — *"a staff member is a name on
  a roster, not an account"*. That is now false: a service person registers
  themselves and a department manager hires them.

---

## 2. Findings that changed the design

Full list as `F1`–`F9` in the plan. Three are load-bearing for coherence and are
restated here because a reader of this folder will not otherwise meet them.

### 2.1 RLS was already multi-community. Only Python was not.

`is_community_member(uuid)` (`0019:81`) is an `exists(...)` over every active
membership the caller holds. Postgres has never assumed one community. The
scalar assumption lived in exactly one query — `app/api/deps.py`,
`order by is_default_community desc limit 1`.

This is the single most important fact in the design, because it means the
service person's defining property — *belongs to several communities at once* —
is not a change to the tenancy model. It is a change to one function. Everything
in §2 of the admin document about resolving membership from Postgres on every
request, and never from a JWT claim, survives untouched: the resolver still runs
once per request, still hits the database, still revokes instantly.

### 2.2 Writing a notification already produces a realtime frame

The trigger `notifications_sse_event` (`0030:229-266`) emits an
`audience='member'` SSE row on every `notifications` insert. There is no
"remember to also emit" step, and the dispatch engine gets live delivery to the
worker's open tab for free by calling `notify_member`.

### 2.3 There is no Python notification API at all

`app/services/notifications_service.py` only reads. Every notification in this
system is written **inside the feature RPC's transaction**, by `notify_member`
(`0030:174`), `notify_community_roles` (`0032:268`) or `notify_community_staff`
(`0031:158`).

That is a constraint on the dispatch engine, not a detail: the engine's decisions
must happen in SQL, because a decision and its notification have to commit or
roll back together. Python owns only *when* a decision is made. This is why the
dispatcher is a timer and not a rules engine.

---

## 3. The mechanism, where it is not reconstructible from the code

### 3.1 The engine is a claim loop, and it is `PushSender` with the nouns changed

`app/core/push.py:5-18` states the governing rule for the existing sender: *"The
hub may drop. The sender may not duplicate."* A job offer has exactly the same
property, so it gets exactly the same mechanism rather than a new one —
`claim → act → sleep`, started from the lifespan, never raising, DB work in
`asyncio.to_thread` because supabase-py is synchronous.

Due times live in a `dispatch_tasks` row rather than in an in-memory timer, which
buys two things that matter more than they look:

- a restart loses nothing;
- **the engine's entire pending behaviour is one `select`.** A scheduler you
  cannot inspect is a scheduler you cannot debug at 2 a.m.

`claim_dispatch_batch` uses `for update skip locked`, so two app processes claim
disjoint sets and the loser of a race gets an empty result rather than a
duplicate offer.

### 3.2 Double-booking is an exclusion constraint, not a check in Python

`amenity_bookings` already carries a GiST exclusion constraint over
`tstzrange(starts_at, ends_at, '[)')` scoped to live statuses, with conflict
resolution in a `BEFORE` trigger holding `pg_advisory_xact_lock`
(`DECISIONS_NEEDED` E20). A worker being in two places at once is the same
problem and gets the same solution.

The candidate sweep *also* filters overlapping slots — not as the guard, but so
that the system does not offer a job that could never be accepted. The database
is where correctness lives; the sweep is where politeness lives.

### 3.3 Community colour is derived, never stored

A stable hash of the community UUID indexes a fixed palette. No column, no
migration, no admin setting, and every device agrees. This is the whole of
`D15`, and it is here because the obvious future request — *"let admins pick the
colour"* — should be met by adding a column then, not by anticipating it now.

Built as `frontend/src/lib/communityColor.js`, returning an object of **fully
spelled-out** Tailwind class strings rather than a colour name. Tailwind scans
source text, so a composed `` `bg-${name}-500` `` is scanned as nothing and the
swatch renders transparent — the one implementation detail of `D15` that is not
obvious from the decision.

### 3.4 The worker portal is guarded by identity, not by role

Every other portal in this application is behind `ProtectedRoute`, which reads
`currentUser` and compares its role. The worker portal cannot be, and the reason
is structural rather than stylistic.

`applicationUser(context)` returns **null** when the session carries no
membership. A service person who has registered and not yet been hired holds no
membership anywhere — that is the definition of the state — so `currentUser` is
null and a role-based guard sends them to the login page. The screens behind
that guard are the registration form and the community search: the two things
that state exists to be resolved by.

So `SignedInRoute` requires `sessionContext.identity` and nothing else, and the
portal decides what to render from `GET /worker/snapshot`, whose null `provider`
and empty `communities` are the two empty states. This is the same problem, and
the same answer, as `require_service_provider` on the backend depending on
`get_current_user` rather than on membership.

The rejected alternative was changing `applicationUser` to synthesise a user
from an identity with no membership. It would have worked, and it would have
changed what `currentUser` means for every portal in the product in order to fix
one — and in a file the parallel auth workstream owns.

### 3.5 The service worker makes one small claim, on purpose

`frontend/public/sw.js` exists because a browser cannot receive Web Push without
one, and `US-2.7` had been blocked on that single missing file since the
resident build — the server half has been able to send for weeks.

Its second job is deliberately modest. It caches successful same-origin `GET`s
as they happen and reads that cache only when the network fails, so a reload
during an outage still boots the application. There is **no precache manifest
and no Workbox**: Vite emits content-hashed asset names, so a hand-written
manifest is wrong on the next build and a generated one is a versioning and
invalidation problem nobody has asked to have. `/api/` is excluded outright,
because an API response served from cache would show a worker yesterday's jobs
and call them today's.

The honest description is *the app still opens*, not *offline-first*.

---

## 4. Cost, stated honestly

### 4.1 Seven dead tables come alive, and the ERD moves

The plan un-parks `R16`. That resolution was not arbitrary — it was written to
stop exactly this: a half-built Phase 2 leaking into v1. The mitigation is that
the tables are extended **additively**, in the same shape `0019` used to extend
`departments`, and every column added is used by a shipped endpoint in the same
step. If a step slips, its tables stay dead rather than half-alive.

### 4.2 The dispatcher polls in every process

Two app processes are safe — the claim is atomic — but both poll, at 15-second
intervals, forever. At current scale that is free and it matches `PushSender`
exactly. The ceiling is real and is worth a comment in the file rather than a
solution now.

### 4.3 `app/api/deps.py` is not ours

It belongs to the parallel auth workstream. The change is additive by
construction — `get_active_membership` keeps its signature, its return type, its
403 and its one round trip — but *additive* is an argument, not a guarantee, and
the owner has to agree. If they have a conflicting change in flight, the fallback
is for the worker surface to carry its own resolver at the cost of one extra read
per worker request.

*That fallback originally named a `worker_deps.py` module, which was planned and
then deliberately not written — see `SERVICE_OPERATIONS_PROGRESS.md` §4.16. The
fallback itself still stands; it would need a home rather than an existing one.*

### 4.4 Auto-resolving a complaint after 24 hours of resident silence

The product document specifies it. **It is not implemented as specified**, and
this section said otherwise until Step 5 had to make the call: what
`dispatch_resident_timeout` does is *proceed with the proposed visit* and tell
the resident so, rather than close their complaint.

The reasoning is that the two acts differ in who they cost. Proceeding needs no
product decision — it is what the resident was told would happen. Closing a
complaint the resident may never have seen is a decision about accountability,
which is the subject of `US-2.8`, and a background job at 2am is the wrong place
to make one quietly. The resident is notified at the deadline either way, so the
silence is audible.

This remains a **default, not a ruling** — see §5. Making it close the complaint
instead is a three-line change in one function.

**Handed over rather than left here.** This and six other questions of the same
kind are collected in
[`../COMPLAINT_ENGINE_HANDOFF.md`](../COMPLAINT_ENGINE_HANDOFF.md), written for
the owner of the complaint lifecycle. Its §2 adds the part this section did not
know: **the dispatcher's 24-hour timer and the complaint's SLA clock are
different clocks**. `dispatch_tasks.due_at` exists only for complaints that
reached triage; `complaints.expected_resolution_at` exists for every complaint.
So auto-resolving off the dispatcher's timer would close the complaints that got
attention and leave the neglected ones open forever — which is why the rule, if
it is built, belongs to the complaint engine and not here.

---

### 4.5 An offline gate cannot be made safe by a signature

Plan `D13` specified a signed, time-boxed bundle. The signature was dropped when
it was written, and the reason belongs in a section headed *cost* rather than in
a footnote: **there was never a version of it that worked.** The device verifies
the signature against a key the device holds, and the same person who can edit
`localStorage` can delete the check beside it, because both are JavaScript on
their machine. A signature there is a control that looks like a control.

What replaces it is not equivalent and should not be described as such. The
bundle is unverified; what is verified is the *reconcile*. Every admission made
offline is replayed against the live pass, and the server's own verdict is
recorded beside the device's claim in `offline_reconcile_log`, readable by the
community's admins and deliberately not by the guard whose entries are being
checked.

**The residual risk, stated plainly:** between the outage starting and the
reconcile completing, a device that has been tampered with can admit somebody it
should not, and nothing stops it at the time. What the design buys is that the
admission becomes an auditable disagreement rather than an invisible one. That is
the honest ceiling for offline verification on a browser, and a signature would
not have raised it — it would only have made the ceiling harder to see.

The bundle also discloses something, and the disclosure is deliberate: it is a
list of live `code_hash` values, and a six-digit code hashed with SHA-256 is a
10⁶ search space, so the hashing obscures nothing from whoever holds the file.
That is acceptable *precisely here* — the gate device is already authorised to
admit exactly those visitors — and nowhere else, which is why the read is gate
staff only and capped at 48 hours.

---

## 5. Open questions, with a default recorded for each

| Question | Default taken | Who decides |
|---|---|---|
| Is PostGIS available on the project? | Assume yes; `haversine_km` ships in `0034` as the fallback, and losing PostGIS costs one generated column and one index — no API shape changes | PO, before Step 1 closes |
| Should a 24 h silent complaint really auto-resolve? | **No** — the dispatcher proceeds with the visit and says so (§4.4). Closing a complaint is the complaint engine's act, and the question is handed to that owner in [`../COMPLAINT_ENGINE_HANDOFF.md`](../COMPLAINT_ENGINE_HANDOFF.md) §2 | Complaint-engine owner, with PO |
| Who moves a complaint to `resolved` once the work order completes? | Nobody does today, so the resident cannot confirm — `confirm_complaint_resolution` requires `resolved` first. Handoff §1 | Complaint-engine owner |
| Should a job's status move its complaint's status at all? | **No** — the two state machines are uncoupled and nothing in this feature writes `complaints.status`. Handoff §0 | Complaint-engine owner |
| Does the auth owner accept the `deps.py` seam? | Assume yes; fallback in §4.3 | Auth workstream |
| Is an unsigned offline bundle acceptable? | **Yes**, with the reconcile as the real control and the residual risk stated in §4.5. Overturns plan `D13` | Settled while building |
| Which gate does a guard employed by two societies see? | Their default one. There is no request field that could resolve it without becoming a community id in a body; a header set from a gate picker is the honest fix if it ever matters | Open, low stakes |
| Does a bare assignee change notify? | **No** — but a dispatch *offer* does. `ARCHITECTURE.md`'s rule exists to stop progress bars buzzing phones; an offer expires and demands an action, and `US-2.7` names reassignment explicitly. Recorded there as a dated amendment | Settled (`D9`) |

---

## 6. Coherence checklist

Every paradigm this surface preserves, so divergence becomes visible rather than
gradual.

| Paradigm | Established in | Preserved how |
|---|---|---|
| Membership resolved from Postgres per request, never from a JWT claim | Admin §2 | `get_membership_set` runs the same query, one round trip, `limit 1` dropped |
| Router does HTTP, service raises `AppError`, repository reads a view and writes an RPC | Admin §3 | Nine new routers, same triple, no exceptions |
| Every write is a `SECURITY DEFINER` RPC; no insert/update/delete policy exists anywhere | `0031` | Same posture on all six new migrations |
| Notifications are written inside the feature transaction, in SQL | §2.3 | The engine calls RPCs; Python never writes a notification |
| Live updates ride the existing hub; no new transport | Resident §6 | Two new topics, `audience='role'`; `realtime.py` needs no change |
| The spec is generated and cannot drift | Admin §6 | `OPERATIONS` entries per operation; the export fails in both directions without them |
| Audit trail is `complaint_events`, rendered by `_event_message` | Resident §5 | Seven new event types on the existing nine — no parallel timeline |
| `text` + named `_check` rather than new enums | Migration README | Every new status column |
| Grants to `authenticated`, never `anon` | Migration README | Every new object |

**The one place this surface deliberately diverges** is `D3`: `rank` becomes
`manager | supervisor | member` and the trade stays in `job_title`. Four
vocabularies disagreed — SQL `head|member` (`0019:244`), `API.md` §8
`member|supervisor|head`, the ERD's `staff_rank`, and three separate frontend
lists. The ERD's wins. Because no migration has ever been applied to any database
(`plans/SERVICE_OPERATIONS_PROGRESS.md` §7.4), this is a constraint edit rather
than a dual-write and a backfill — which is the single largest cost this feature
avoids, and it will not be avoidable a second time.

## 7. Phase 2 amendment — dated departures, direct messages (2026-08-10)

Added after the PO's *service men leave and further department fine tuning and works.md* and the
four rulings taken in Q&A the same day. Full derivation in
`plans/SERVICE_OPERATIONS_PROGRESS.md` §6.14–§6.22.

**One rule this phase overturns, named per `design/README.md`'s convention.** `0043` made the
departure approval conditional on an empty handover list — *"only an empty list lets the approval
through"* — and §3 of this document described that gate as the feature. **The PO overturned it:**
the decision whether and when somebody leaves is management's, a leave has a date, and approval
*releases* the leaver's booked work from that date onward back to the dispatch pool at a queue
priority just below urgent (`dispatch_tasks.priority`: urgent 2, released 1, normal 0). The freeze
became time-aware (`departure_bars_work`), the removal became a fifth dispatch-task kind
(`departure_removal` — collecting on `0037`'s promise that a new kind touches no Python), and the
zero-commitment gate survives in exactly one place: the direct remove, which has no decision record
and no release step. The per-item handover remains as a tool, not a precondition.

**Two subsystems this phase adds.** The employee page (three reads in `department_hiring.py`; the
coverage check answers "who could take each stranded item" and a zero **is** the answer), and
direct messages (`0046`): one thread per pair per community, `dm_pair_allowed` as the single reach
rule — the association committee *is* the `admin` role — and the worker↔resident job thread that
locks when the work order ends. The lock is the PO's protection clause verbatim; the readable
locked transcript is the same ruling's documentation clause. Counterpart names are snapshots
because `profiles` has been self-read-only since `0001`; the known cost (rename shows stale) is
recorded on the table.

**Settings stop editing identity.** `PATCH /service-providers/me` no longer accepts `displayName`;
`0045` made the upsert coalesce a null name, which is what made the field droppable. Name and email
are identity — the PO's rule — and the registration route is the one place a name is required,
because it is the one moment there is nothing stored to keep.
