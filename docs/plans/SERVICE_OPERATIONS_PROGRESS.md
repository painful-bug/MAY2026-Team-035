# Service operations — live work journal

Companion to [`SERVICE_OPERATIONS_PLAN.md`](SERVICE_OPERATIONS_PLAN.md). That
document is the approved design and is **frozen**; this one is rewritten
constantly and records what actually exists in the branch.

**Branch:** `services-and-security` — local only, no upstream, nothing committed
yet (the whole feature is in the working tree).
**Last updated:** 2026-08-11
**Current step:** service-professional signup/onboarding implementation is in the
working tree. Migrations through `0047` are verified as deployed; the two new
`20260811…` migrations are forward-only and pending deployment. Implementation
and rollout evidence is in
[`SERVICE_PROFESSIONAL_AUTH_IMPLEMENTATION.md`](SERVICE_PROFESSIONAL_AUTH_IMPLEMENTATION.md).

---

## 0. Resume here

*If you are picking this up cold, this section is the only one you have to read
to start working. Everything below is context.*

**Next action: none scheduled — all three phases are complete.** Phase 3 shipped
2026-08-11 (§5.31–§5.33): the gate has both its portals, `US-3.3`–`US-3.6` are
all served, and task #93 is closed.

*(2026-08-11, after Phase 3: a PO-ordered end-to-end compatibility sweep found
two defects and both are fixed — §5.36. `/security-manager` had been unreachable
by any user the system can create, which had left Phase 3 Step 5's whole portal
dark on the day it shipped; and four notification deep links resolved to the
landing page. Three further findings were filed rather than fixed, one file each
under `docs/potential issues/`. Baseline moves to **856 tests**.)*

*(2026-08-11, immediately after: the honest limit that fix left behind is closed
too — §5.37. `security_shift.assigned` reached the right screen and `Shifts` did
not read the `?shift=` it carried, so the guard arrived at a fortnight of rows
with nothing marking theirs. The screen now highlights it, `GET /security/shifts`
gained a `shiftId` filter for the shift the fortnight does not contain, and the
five remaining unread notification parameters are asserted by name rather than
assumed. Baseline moves to **860 tests**; the operation count does not move.)*

*(2026-08-11, same day: those five are now written up one by one as
`docs/potential issues/12-…`, and one of them turned out to be **ours** —
`/worker/messages?conversation=` — so four remain, all other workstreams'. A
`dead_code_sweep.py` beside the API sweep now asks the four questions nothing here
asked; its output split into three deletions of ours and `docs/potential issues/13-…`
for the rest. §5.38. Baselines all unmoved.)*

What remains is not build work:

* **Applying the new migrations.** The linked project already records the chain
  through `0047`; only the timestamped professional-flow migrations are pending.
  Apply them after staging dry-run and hosted data backfill evidence.
* **The first real end-to-end pass**, which only becomes possible afterwards.
  Two things explicitly owe it a look: the notification click-through (§5.25)
  and every gate response shape — Phase 3 verified those against *fixtures I
  wrote from the documentation*, which proves the screens handle the shapes the
  docs describe and not that the database returns them (§5.32).
* **Committing and pushing.** The branch `services-and-security` is local-only
  with nothing committed, and that is the PO's call.

*(2026-08-11: the diagram re-render that used to sit in this list is done —
PO ordered it on 2026-08-10. All three stale images regenerated, old ones
preserved in `docs/archives/2026-08-10-diagram-rerender/` with a NOTE.md;
CHANGE_LOG Session 56 has the details, including that the old committed
domain-model PNG had been silently truncated to 4096×4096 all along.)*

**Four PO rulings from 2026-08-10, so nobody re-litigates them:** (1) approval
releases the leaver's work from the effective date onward back into the pool —
the manager decides whether and when someone leaves; (2) "just below urgent" is
a queue-priority column on `dispatch_tasks` (urgent 2, released 1, normal 0);
(3) chat gets a real person-to-person model — "committee" means the admin role;
(4) the chat dock mounts on **all** portals, and work-order threads lock when
the job completes so a serviceman cannot keep talking to the resident afterwards.

~~**One thing Step 10 could not finish and nobody should assume is done:** the
class diagram's `.svg` and `.png` are stale.~~ *Resolved 2026-08-11 — rendered
with PlantUML 1.2024.8 + Graphviz 15.1.1 on the PO's instruction; the ERD
render was redone the same day (offline toolchain now, see CHANGE_LOG
Session 56). Old images archived in `docs/archives/2026-08-10-diagram-rerender/`.*

~~**Before that, one decision is owed** — §4.25. The gate has a backend
(`0040`, `security_operations.py`, `US-3.3`–`US-3.6`) and **no consumer**, and no
row of the approved build order schedules one. It wants its own step of roughly
Step 8's size. That is the product owner's call; it is not a documentation-sweep
item and should not be quietly folded into one.~~ *Answered 2026-08-11: the PO
ruled "build it" — the gate gets its own build phase (Phase 3, §6.24), sized as
§4.25 recommended. Task #93 closes when Phase 3 does.*

**Everything else is built.** Steps 1 through 9 plus the unnumbered 8b and 9b are
complete, verified and documented — §5.2 through §5.19. `0034`–`0047` exist,
**179 operations across 150 paths, 860 tests**, and five portals render against
the live API: `/worker`, `/admin/departments/:id/hiring`, `/admin/messages`,
`/security` and `/security-manager`. *(This paragraph said `0034`–`0043`, 170
operations, 143 paths, 835 tests, three portals until 2026-08-11 — stale by two
sessions. It is the resume section, so it is the paragraph most expensive to get
wrong; see §5.34, where it was one of six.)*

**Eight things Step 10 inherits and should not rediscover.**

1. **The service worker exists** — `frontend/public/sw.js`, registered from
   `main.jsx`, with `lib/push/pushClient.js` beside it. `US-2.7` is **served**,
   and `US-2.4` joined it when `0041` gave a published notice a writer.
2. **Community colour is `D15` and needs no endpoint** —
   `lib/communityColor.js`. The classes are spelled out in full because Tailwind
   scans source text and a composed `bg-${name}-500` scans as nothing.
3. **The staff vocabulary is one file now** — `lib/staffVocabulary.js`. Three
   `STAFF_ROLES` lists collapsed into `STAFF_RANKS` (closed, because the database
   closes it), `JOB_TITLES` (a datalist on free text, because `job_title` has no
   check constraint) and `SHIFTS` (five values, `Full Day` included).
4. **There is exactly one function that routes a signed-in person home** —
   `homeRouteFor(subject)` in `routes/authRoutes.js`, keyed on `portal`. A new
   portal is one row of `PORTAL_ROUTES` plus one `portal` value from the backend,
   **not** a branch in two files.
5. **A notification is addressed to a person, not a membership** (`0041`).
   `notify_member` for a community audience, `notify_profile` for somebody who
   may hold no membership, `notify_department_leadership` (`0043`) for a
   department's managers *and supervisors* — an audience the first two cannot
   express, because a supervisor is a rank on a roster row rather than a
   membership role.
6. **Nobody can be removed while holding work** (`0043`). The check is inside
   `remove_department_member`, which every removal path funnels through,
   including the bar. A departure freezes the dispatch sweep against that person
   from the moment it is opened, and two triggers stand behind the sweep so no
   future writer has to remember.
7. **The frontend is two halves and the seam is deliberate.** The eleven zustand
   slices are the demo; everything that talks to the real API uses react-query.
   `DepartmentDetail.jsx` has one link into the live half and is otherwise demo.
   Nothing is mid-migration.
8. **`docs/design/AUTH_AND_SESSION_DESIGN.md` exists** and is where anything
   about identity, membership, guards or notification recipients is written up.
   §6 of it lists what was deliberately not changed; §7 lists what is still the
   auth owner's to rule on.

**Still open and not mine to close:** applying any migration — none has ever run
anywhere (§7.4).

## 1. Working agreement — document before doing

Adopted 2026-08-09 at the product owner's instruction, so that a stop at any
point is resumable weeks later by someone who was not here.

The rule is literal: **before each unit of work, the intent is written into §6
of this file; after it, the entry moves to §5 with what actually happened.**
Not a summary at the end of a session — an entry that exists *before* the edit
does.

What counts as a unit of work: one migration, one router-plus-service-plus-repo
triple, one test module, one documentation sweep. Not one line, not one
function.

Why this shape rather than a checklist:

- A checklist records *that* something was done. It does not record the fact
  discovered halfway through that made the plan wrong — and that fact is the
  expensive one to reconstruct. §4 exists for those.
- A stop is not a clean boundary. §0 names the next action precisely enough to
  resume without re-deriving it from the plan, which takes an hour.

---

## 2. Baseline, taken before any change

Recorded so any regression is attributable to this work rather than inherited:

| Check | Result |
|---|---|
| `python -m pytest -q` | **694 passed** |
| `ruff check .` | **153 pre-existing errors** (140 `E501`, 8 `I001`, 4 `N815`, 1 `F401`) |
| `python scripts/export_openapi.py --check` | clean |
| `pglast` | v8.4 present; used to statically validate every migration |

The 153 ruff errors predate this work and are **not** being fixed here — but no
new one is being added either. That is the lint bar for this branch: the count
must not rise.

---

## 3. Step order and status

Mirrors the plan's build order. One row per step; a step is `done` only when its
code, its tests **and** its documentation have landed — the rule from
`RESIDENT_BACKEND_DESIGN.md` §9, *"done means merged, tested and documented, not
written."*

| # | Step | Status |
|---|---|---|
| 0 | Install `ponytail`; confirm PostGIS / `btree_gist` availability | **done** — skill installed; PostGIS confirmed by the PO, `btree_gist` settled from `0001` itself (§7.1) |
| 1 | `0034` + `MembershipSet` seam + `service_providers` API triple | **done, verified** — §5.2, §5.3, §5.5, §5.6; the seam's owner item closed by ruling in 8b (§7.3) |
| — | The four §8 defects, pulled forward out of Step 4 | **done, verified** — §5.8 |
| 2 | `0035` department roles and hiring | **done, verified** — §5.9, §5.10 |
| 3 | `0038` conversations + router | **done, verified** — §5.11 |
| 4 | `0036` work orders + supervisor triage | **done, verified** — §5.12 |
| — | Three latent foreign-key defects in `0036` and `0038` | **done** — §4.14 |
| — | Seven `security definer` functions executable by everyone | **done** — §4.15 |
| 5 | `0037` dispatch engine + `app/core/dispatcher.py` | **done, verified** — §5.13 |
| 6 | `0039` worker actions + jobs, schedule and snapshot endpoints | **done, verified** — §5.14 |
| — | The sweep could auto-assign a worker who had declined the job | **done** — §4.17 |
| 7 | `0040` security operations + CSV export — **renumbered from `0039`, §4.16** | **done, verified** — §5.15 |
| — | `US-3.5` had no online verification to fall back from | **done** — §4.18 |
| — | Three routers had no representative path in `test_every_router_is_mounted` | **done** — §4.19 |
| 8 | Frontend calendar primitive and worker portal | **done, verified** — §5.16 |
| — | The community search returned department names with no ids, so nothing could be applied to | **done** — §4.22 |
| 8b | `0041` — the notification substrate becomes person-addressed; the auth seam and its design document | **done, verified** — §5.17 |
| — | The resident snapshot reads the same feed and was missing from the file table | **done** — §4.23 |
| — | A provider signing in a second time had no route to their own portal | **done** — §4.24 |
| 9 | Frontend manager hiring and vocabulary reconciliation | **done, verified** — §5.18 |
| — | A roster row could not say which service provider it was | **done** — §4.26, `0042` |
| — | The gate backend has no consumer and no step schedules one | **open** — §4.25 |
| — | Leaving a community becomes a handover | **done, verified** — §5.19, `0043` |
| 10 | Documentation sweep | **done** — §5.20, minus the two rendered diagram files |

**Phase 2** — approved 2026-08-10 (`cozy-stirring-sparrow.md`). Phase 1's Steps
11–12 became Steps 1–2 here so the verification and the sweep run before any new
surface is built on top of them.

| # | Step | Status |
|---|---|---|
| 1 | Carried fixes + baseline verification *(was Step 11)* | **done, verified** — §5.21 |
| 2 | Dead-code sweep, `0044_retire_dead_tables.sql` *(was Step 12)* | **done, verified** — §5.22 |
| 3 | `0045_departure_scheduling.sql` + backend | **done, verified** — §5.23 |
| 4 | Employee-management backend endpoints | **done, verified** — §5.24 |
| 5 | Frontend notification feed + deep links | **done, verified** — §5.25 |
| 6 | Employee pages, departure v2 UI, worker Settings | **done, verified** — §5.26 |
| 7 | `0046_direct_messages.sql` + `messages.py` | **done, verified** — §5.27 |
| 8 | Chat dock on all portals + employee-card chat | **done, verified** — §5.28 |
| 9 | Docs sweep | **done** — §5.29 |
| 10 | Full verification | **done** — §5.30. **Phase 2 complete.** |

---

## 4. Facts discovered during the build that changed the plan

The highest-value section in this file. Each entry is something learned *while
building* that the plan got wrong, with what was done instead. The approved plan
is **not** edited to match — it stays as the record of what was intended.

### 4.1 `skill_categories` join table → one nullable FK column

*Found while writing `0034` §5.*

The plan specified `skill_categories(skill_id, complaint_category_id)`. That is
wrong in this schema, for two reasons found on inspection:

- `department_categories` keys the category as `category_id`, not
  `complaint_category_id`;
- **`complaint_categories` is per-community while `skills` is global.** A join
  table would therefore need one row per *(skill, community)* pair, and would be
  silently incomplete for every community created after the migration ran.

Replaced with a single nullable `complaint_categories.skill_id` FK, auto-filled
by a `link_category_skill()` trigger that name-matches against the seeded
catalogue. One column instead of a table, a real foreign key instead of the
label-as-foreign-key pattern `DECISIONS_NEEDED` B6 objects to, and it
self-maintains for communities created later. The trigger only ever fills a
blank, so an admin who deliberately set a different skill is never overwritten by
a category rename.

### 4.2 `blacklisted_service_providers` moved from `0035` to `0034`

*Found while writing `0034` §10.*

`search_serviceable_communities` needs it, and it is a property of the provider
rather than of a department, so `0034` is where it belongs anyway.

### 4.3 `MembershipSet` carries no raising method

*Found while writing `app/domain/schemas.py`.*

The plan sketched `MembershipSet.require(community_id, *roles)` raising
`AuthorizationError`. `AuthorizationError` lives in `app/core`, and nothing in
`app/domain` imports `app/core` — the dependency runs the other way, everywhere.
Adding the first such import for one convenience method is not worth the
inversion. `MembershipSet` therefore exposes `for_community(...) -> ... | None`,
and the raising wrapper `require_community_role(...)` lives in `deps.py`, which
already imports both.

### 4.4 `worker_deps.py` is a Step 6 artifact, not a Step 1 one

*Found while about to write it.*

The plan puts `require_worker` and `get_service_provider` in Step 1. Checked
against Step 1's actual six operations, **neither is used by any of them**:

| Operation | Guard it really needs |
|---|---|
| `POST /service-providers` | authenticated — it *creates* the provider row |
| `GET /service-providers/me` | authenticated; the service's read is what 404s |
| `PATCH /service-providers/me` | authenticated — `upsert_service_provider` is an upsert |
| `PUT /service-providers/me/skills` | authenticated; the RPC raises `P0002` when unregistered |
| `PATCH /service-providers/me/availability` | authenticated; same `P0002` |
| `GET /skills` | authenticated |

Every one of the three write RPCs in `0034` §10 resolves the provider from
`auth.uid()` itself and raises `P0002` if there is no row — which
`app.core.pg_errors.translate` already turns into a 404. A dependency that reads
the same row a moment earlier would add a round trip per request and a second
place for the "are you registered" rule to live.

`require_worker` has no caller at all until `worker_jobs.py` in Step 6.

So the module is deferred to Step 6, where both guards have real callers. **The
reasoning the plan attached to it is the part worth keeping** and is not lost:
`get_service_provider` must depend on `get_current_user` **alone**, never on
membership, because a registered-but-unhired provider has no membership and a
membership-based guard would 403 them out of exactly the screens that let them
apply. Getting that wrong produces a system in which nobody can ever be hired.

### 4.5 Making `get_active_membership` depend on the set broke it

*Found by the suite, which is the only reason it was found.*

The plan's sketch — and the first implementation — wrote:

```python
def get_active_membership(
    memberships: MembershipSet = Depends(get_membership_set),
) -> MembershipContext:
    return memberships.default
```

To FastAPI that reads identically to the old version. To a **direct caller** it
does not, and there are direct callers: `tests/api/test_session_flow.py:603`
invokes `deps.get_active_membership(deps.decode_token(token))` positionally, to
prove the role comes from `community_memberships` rather than from a token claim.
The test failed with `Principal object has no attribute 'default'`.

That is D14's promise — *"additive at the seam, so every existing router, guard,
test and signature keeps its current behaviour"* — being violated in the one way
the framework hides. A changed parameter type is not additive; it only looks
additive from inside dependency injection.

Fixed by keeping the `Principal` parameter and deriving inside the body:

```python
def get_active_membership(
    principal: Principal = Depends(get_current_user),
) -> MembershipContext:
    return get_membership_set(principal).default
```

The cost is that a handler depending on *both* would read twice. None does — a
handler wants either one community or all of them — and the alternative cost was
a broken contract. `tests/test_membership_set.py` now pins the direct-call form
explicitly, so this cannot regress silently a second time.

### 4.7 `hireable_service_provider` cannot be a view

*Found while writing `0035` §6.*

The plan lists it among the views. It cannot be one: a manager's candidate list
is skill-matched against **one department's** categories, and a view takes no
parameter. The shape that would work as a view — cross every department with
every provider, filter afterwards — is a cartesian product of two growing tables
to answer a question about a single row.

It is `search_hireable_service_providers(p_department_id, p_query, p_limit,
p_offset)` instead, which is `0034`'s `search_serviceable_communities` seen from
the other side: same three rules inverted, same paging clamp, same
`nulls last` so a provider who has not set coordinates is sorted last rather than
hidden. Not a new pattern — the pattern already in the file next to it.

### 4.6 Relaxing the `rank` check is not a constraint edit — four things write or read `head`

*Found while about to write `0035` §1.*

The plan, and §6.1 restating it, say: *"relax `staff_assignments_rank_check` to
`('manager','supervisor','member')` and rename the partial unique index."* Doing
only that leaves the schema self-contradictory, because `0019` has four other
references to the word:

| Where | What it does |
|---|---|
| `0019:588-604` `apply_department_head` | writes `rank = 'head'`, demoting the incumbent first |
| `0019:401` `department_overview` | `s.rank = 'head'` is how `head_name` is projected |
| `0019:282` `staff_assignments_one_active_head` | the partial unique index |
| `0019:678, 871` | reset `rank = 'member'` on removal — still valid |

So the moment the check allows only `manager | supervisor | member`, the *only
function that ever sets a rank* raises `23514` on every call, and the department
screen's `head` field goes permanently null. `0035` therefore replaces the
function and the view too, and carries a one-time
`update ... set rank = 'manager' where rank = 'head'` — a no-op today (§7.4), and
correct if `0019` is ever applied before `0035`.

**The wire word `head` does not change.** `departments.js`, `department_schemas.py`
and `API.md` §8 all use it for the person who runs a department, and renaming it
would break the admin screen for no gain. `head` is the wire vocabulary and
`manager` is the stored one, which is what `app/domain/vocabularies.py` exists to
hold — the same seam §5.8 used for comment visibility, three hours earlier.

One crack this closes on the way past: `department_schemas.py:47` already
documents rank as `member | supervisor | head`, and `supervisor` has never been a
value the check allows. The API has been advertising a rank that no write could
produce.

### 4.8 Step 3's route list could not create a thread

Found reading §6.4 against the code, before writing any of it. The plan and the
journal both listed three routes: list, read, post a message. All three take or
return a conversation id, and **nothing creates one** — so the first message in
any thread could never be sent. The gap is invisible in the plan because the
migration says "created on first use", which is true of the RPC and says nothing
about who calls it.

`POST /conversations` was added, taking `(departmentId, serviceProviderId)`. It
is an upsert on the unique constraint rather than a read-then-write, which is
what "one thread per pair, and the constraint is the whole concurrency story"
actually means once something has to act on it: two managers pressing Message in
the same second get the same row, and neither has to know the other existed.

The implementation detail worth recording, because it looks like a mistake:
`on conflict ... do update set department_id = excluded.department_id` sets a
column to the value it already holds. `do nothing` returns no row, so
`returning id` would hand back null for exactly the case the function exists to
serve — the *second* caller.

### 4.9 The `last_message_at` trigger defends against a writer that cannot exist

§6.4 specified a trigger. Writing §6 of the migration made it clear the file
declares **read policies only**, the posture `0031`, `0034` and `0035` already
take: every write is a definer function that checks its own authorization, and
there is no insert policy on either table. So no row reaches
`conversation_messages` except through `post_conversation_message`, and a
trigger would be a twelve-line guard against a second writer the RLS posture
makes impossible. One `update` in the RPC, in the same transaction, does it.

This is the difference between "a trigger cannot be forgotten" — true, and the
usual reason to prefer one — and "there is nobody who could forget".

### 4.10 A tie-break in `0038` over a set that cannot tie

*Found on 2026-08-10 while reading `0001` to settle `btree_gist` — the same read,
one line apart.*

`post_conversation_message` resolved the department-side author with
`order by (m.department_id = ...) desc, m.created_at limit 1`, on the reasoning
that a multi-community admin should not have whichever membership they default to
recorded as the author. The scoping is right and stays. The **ranking** was
nonsense: `0001:45` declares

```sql
create unique index memberships_active_person_community
  on public.community_memberships (community_id, profile_id) where ended_at is null;
```

and the query's predicate is a subset of that index's, so it can return at most
one row. The `ORDER BY` was ranking a set of size ≤ 1 — and worse, the `desc`
put NULLS FIRST, so had a tie ever been possible it would have preferred the
membership naming *no* department over the one naming this department. Removed,
with the index named in a comment so the absence reads as checked rather than
forgotten.

Nothing was broken by it, which is the point worth recording: it is the kind of
line that survives every test because it never changes an answer, and is
expensive later because the next reader assumes it is load-bearing.

---

### 4.11 `work_orders.priority` and `complaints.priority` were two value sets for one name

`0031`'s header argues at length that the schema should not carry two *names*
for one concept, and settles on `priority` over the frontend's `urgency` partly
because *"the admin's existing column for the same idea is `priority` on
`work_orders`"*. It did not look at what that column allows.

`complaints.priority` is checked against `low | medium | high` (`0031`:87).
`work_orders.priority` defaults to `'normal'` and has **no CHECK at all**
(`0001`:73). So the two columns `0031` cited as being the same idea agree on the
name and disagree on every value, and the default on one of them is not a member
of the other's set.

Corrected in `0036` §1: same three words, default `'medium'`, and
`create_work_order` inherits the complaint's priority rather than accepting one.
A job's urgency **is** the complaint's urgency, and a parameter for it would be
a second copy to keep in step.

The lesson is narrower than "check your constraints": **`0031` reasoned about
the column it was citing without opening it.** Citing a column as precedent is
a claim about what it holds, and that claim is checkable in one grep.

### 4.12 The state machine needed a manual exit that the plan gave to a timer

§6.5 said Step 4 builds no timers, which is right. What it did not say is what
that costs.

The plan's `awaiting_resident` state has exactly one exit in the design: the
resident answers, or `dispatch_resident_timeout` fires 24 hours later. Build the
state without the timer and there is a state a job can enter and never leave —
untestable, and unfixable in production without a SQL console.

`assign_work_order` therefore accepts a job in `awaiting_resident`, and the
function says so in a comment naming the timeout it stands in for. That is not a
workaround for the missing engine; it is the rule the whole step is arranged
around, stated once in the migration header: **every transition the engine will
later make automatically is reachable by hand first.**

Worth generalising, because it will recur in Step 5 and Step 7: *a state whose
only exit is a background job is a state nobody can test.* The manual lever is
not scaffolding to be removed when the engine lands — it is the thing the engine
automates, and it stays.

### 4.13 A double-booking was reaching the caller as a bare 400

`app/core/pg_errors.py` maps `23505` (unique violation) to a 409 and has since
it was written. It does not map `23P01` (**exclusion** violation), which is what
a GiST exclusion constraint raises — so a refusal from
`work_order_assignments_no_overlap` fell through to the generic branch and
surfaced as a 400 carrying the repository's default message.

This was not introduced by `0036`. `amenity_bookings` has carried an exclusion
constraint since `0001`:81, so a resident double-booking the clubhouse has been
getting a 400 that could not say why for as long as that path has existed.

Two fixes, and both were needed:

- `23P01 → ConflictError`, beside `23505`, because it is the same kind of answer:
  somebody else has that already.
- A pre-check inside `assign_work_order` raising `HB409` **by name** — *"Ravi
  Kumar is already booked during that time."* — since `pg_errors` passes a
  custom code's message through and a standard code's message is deliberately
  suppressed. The same reasoning `0035` gave for raising `HB409` rather than
  letting a `23505` surface out of the hiring RPC.

The pre-check is not the guarantee and the constraint is not the explanation.
Both are load-bearing, and the comment in the migration says which is which.

### 4.14 A composite `on delete set null` cannot null one column of two

`0036` gave `work_orders` the house cross-tenant guard —
`foreign key (department_id, community_id) references departments (id, community_id)`
— and chose `on delete set null` for it, reasoning that deleting a department
should orphan its jobs rather than destroy them.

That reasoning is right and the mechanism does not implement it. A multi-column
`ON DELETE SET NULL` nulls **every** referencing column, and `community_id` is
`not null` in the baseline (`0001`:73). So the gentle-sounding action is the one
that raises `23502` and refuses to delete the department at all — and it does it
on the *community* cascade too, since dropping a community deletes its
departments and its work orders with no ordering between the two.

The comment above the constraint claimed it was the *"same shape as"*
`service_applications_department_tenant_fkey` (`0035`) and
`staff_assignments_department_tenant_fkey` (`0019`). Both of those are
`on delete cascade`. The comment was true about the columns and false about the
action, which is the sort of thing a comment is worst at catching about itself.

Two edits, one defect:

- The composite FK is now `on delete cascade`, which makes the comment true and
  removes the cascade-ordering hazard. The complaint keeps the story either way,
  because the timeline lives in `complaint_events` — the point of **D6**.
- **`department_id` lost its inline `references` clause entirely.** It had one
  *and* the composite, with two different delete actions, so a department delete
  would have fired a cascade and a set-null at the same row with no defined
  order. One column, one foreign key. `0035` gets away with keeping both only
  because both of its actions agree.

Found by re-reading, not by a test — nothing in the suite deletes a department,
and per §7.4 no migration has run anywhere, so nothing would have caught it
before the day someone applied the stack to a real project.

**And the same read found a gap in `0038`.** `conversations` carries a
denormalised `community_id` whose entire justification is that the read policy
calls `is_community_admin(community_id)` *without joining the department* — so a
row whose two columns disagreed would be readable by the wrong community's
admins. `open_conversation` derives the value correctly; nothing defended it
afterwards. It now carries `conversations_department_tenant_fkey`, matching the
three other tables that hold the same pair.


### 4.15 Seven privileged functions were executable by every signed-in user

Found while deciding what to grant on `0037`'s new functions, by checking what
the house does. `0001` and `0019` pair every lockdown with **two** statements:

```sql
revoke all on function public.f(...) from public, anon, authenticated;
grant  execute on function public.f(...) to service_role;
```

The revoke is not decoration. **Postgres grants `EXECUTE` on a new function to
`PUBLIC` by default**, so a `grant ... to service_role` on its own changes
nothing — it re-states a permission everybody already had. Four of our
migrations wrote only the second line.

| Function | Migration | What a signed-in user could do |
|---|---|---|
| `notify_member` | `0030` | Write a notification to any membership, with the title, body and **url** of their choosing |
| `notify_community_staff` | `0031` | The same, broadcast to a community's admins and managers |
| `notify_community_roles` | `0032` | The same, to any role list they name |
| `claim_push_batch` | `0030` | Mark every pending notification pushed — push goes silent deployment-wide |
| `record_push_failure` | `0030` | Delete a subscription by endpoint: unsubscribe someone else's phone |
| `record_push_success` | `0030` | Clear another subscription's failure streak |
| `expire_visitor_passes` | `0032` | Settle any community's lapsed passes |

The first three are the serious ones. A notification that carries a `url` and
arrives wearing the association's name is a phishing primitive, and the feed is
the one surface in this product a resident is expected to trust without checking.

**Three of the seven were granted to `authenticated` on purpose**, with a comment
explaining why, and the comment was wrong. It argued that the callers are the
feature RPCs and that a resident-initiated write reaches them over the user's
client — the first clause is true and is precisely why the second does not
follow. Inside a `security definer` function the current user *is* the definer,
so the `EXECUTE` check for the inner call is made against the owner, who owns the
inner function too. Verified from the other end as well: nothing in `app/` calls
any of these seven by name (`push_repository.py` reaches the three push functions
on the **service** client, which is unaffected).

All seven now carry the revoke. The three deliberate `authenticated` grants are
gone with it, and the stale reasoning is replaced in place rather than deleted,
so the next reader sees the argument and why it fails.

**Nothing in the suite can prove this fix**, and that is the honest statement of
its status: no migration has ever been applied anywhere (§7.4), so these are
permissions that have never existed, on functions that have never run. The
correction is a reading of `GRANT` semantics, not an observation.

`0034`–`0038` were audited in the same pass and are clean — every function they
grant to `authenticated` checks its own caller, which is the whole posture of
those files.

### 4.16 Step 6 needs a migration, so security operations becomes `0040`

*Found while writing §6.7.*

The plan gives Step 6 no migration — it reads as three Python files over
machinery `0036` already built. It is not: `0034` through `0037` contain **no
worker-side write function at all**, because until Step 2 existed there was no
worker holding an account, and Step 4 built the supervisor's side of the same
table. `accept`, `decline`, `start`, `complete` and `unable` have nothing to call.

So Step 6 takes `0039_worker_actions.sql` and Step 7's security operations shift
to `0040`. Nothing else moves; the plan's `0034`–`0038` all landed at the numbers
it gave them.

**The plan's `worker_deps.py` is cancelled in the same breath**, and that is the
more interesting half. §4.4 deferred `require_worker` here on the grounds that it
had no caller yet. Writing the callers shows it should not exist:
`require_membership_role` reads the role off `MembershipSet.default`, which is one
community's membership, and this is the only surface in the API that is
deliberately cross-community. A provider hired in three societies and living in a
fourth would be refused their own job list by a guard that checks the wrong one of
their four memberships. Widening it to *any* worker membership still refuses a
manager who is on a roster and has been offered a job.

The question the guard was reaching for is *does this caller hold this
assignment*, which is not about roles. `is_own_staff_assignment` (`0036` §4)
already answers it, once, and the views and functions of `0039` all use it. So the
routers are authenticated-only and **no new dependency module is written** — the
outcome ponytail's ladder asks for, arrived at by trying to write the rung above
it.

### 4.17 A declined worker could be auto-assigned the job they declined

*Found while reading `0037` for the escalation handler.*

`dispatch_candidates` filters on availability, overlap, leave, skill and the
offline toggle. It does not filter on **having already said no to this job**. The
sequence that produces the bug is the ordinary one: the ping offers to five, one
declines, thirty minutes pass, `dispatch_auto_assign` asks for the single best
candidate — and the decliner is still in the set, still ranks first on
adjacency and load, and gets the job booked in their name.

Nothing in the schema was wrong. `dispatch_ping_candidates` guards against
re-*offering* to somebody holding an open offer, which is the neighbouring case,
and the resemblance is probably why the gap survived review: the sweep was read as
though that guard were part of it.

One `not exists` over a `declined` row for this work order, in the sweep rather
than in the two callers, so it holds for anything that asks the same question
later. A worker who declined last week may still be offered next week's job —
the filter is scoped to the work order, not to the person.

### 4.18 `US-3.5` is a fallback with nothing to fall back from

*Found while writing §6.8, before a line of `0040`.*

The plan gives Step 7 `GET /security/offline-bundle` and
`POST /security/offline-reconcile` and no online verification. `USER_STORIES.md`
US-3.1 says why that cannot work, in print: *"nothing verifies a code at the
gate"*. `0032` mints `code_hash` and `pass_hash`, stores both, indexes one — and
**no RPC, endpoint or policy has ever read either back**. A resident could issue
a pass that no gate could check.

So the online scan is built first and the offline pair sits on top of it, both
calling `verify_gate_credential`. One function, so the two paths cannot drift
into two different answers about the same visitor — which is the failure mode an
offline mode invites and the reason it would not have been caught: the two would
agree in testing and disagree in an outage.

**Two things fell out of building it that the plan did not anticipate.**

*Plan D13's signature is dropped.* It specified a signed bundle. Writing it made
clear the signature protects nothing: the device verifies it against a key the
device holds, and the same person who can edit `localStorage` can delete the
check beside it, because both are JavaScript on their machine. What is actually
load-bearing is that **an offline admission is provisional until reconciled** —
the server re-runs the real verification and records its own verdict beside the
device's claim, so a fabricated entry becomes a flagged row rather than an
admitted guest. `offline_reconcile_log` is the control; the signature would have
been the appearance of one.

*`guest_count` had never been read.* The obvious verification — first scan in,
second scan out — is wrong for the story the scan exists to serve. `US-3.1` is
about *a function with two hundred guests on one code*, and that implementation
admits one of them and turns away a hundred and ninety-nine. The column has been
there since `0032`; nothing had ever asked it a question. `verify_gate_credential`
counts admissions against it, and the last scan is the way out.

That moves **`US-3.1` from partial to served**, which was not in Step 7's scope
and is recorded here rather than quietly banked. §16.5 of `API.md` had predicted
the opposite — *"the one thing the current model cannot express, since a pass
belongs to one request"* — and the correction is stated inline there rather than
by rewriting the paragraph, because the reasoning that led somewhere wrong is
the part worth keeping: it reasoned about the model without checking whether a
column already answered it. The same lesson as §4.11, one file over.

### 4.19 Three routers were mounted and untested for it

*Found while adding `security/posts` to `test_every_router_is_mounted`.*

That test's parametrised list carried a comment reading *"Four routers behind one
`include_router`"* while **eight** were mounted. `worker_jobs`, `worker_schedule`
and then `security_operations` had no representative path, so deleting any one of
their `include_router` lines would have removed operations and raised nothing —
which is the exact failure the test was written to catch.

It would not have stayed invisible for long: `export_openapi.py --check` compares
the checked-in spec against the live app, so a dropped router fails *that*. But
the failure would have read as *the spec is stale*, and the fix somebody reaches
for when the spec is stale is to regenerate it — which would have made the drop
permanent and the check green.

Three paths added, and the comment corrected to nine with a note saying what it
said before. A parametrised list is only as good as its last update, and the
number in its comment is the part that tells you when that was.

### 4.20 The three zustand slices the plan asks for should not exist

The plan lists `createServiceProvidersSlice.js`, `createWorkOrdersSlice.js` and
`createConversationsSlice.js` "alongside the existing eleven". Reading the
existing eleven says not to write them.

**The slices are the demo half of the application.** `createVisitorsSlice` mints
its own ids with `genId('v')` and computes a security code in the browser;
`appStore.js` says in its own header that browser state is *"a render cache
only"*. Meanwhile **every page that talks to the real backend already uses
react-query** — `PendingRegistrations.jsx`, `Residents.jsx`,
`JoinCommunityTab.jsx` — `QueryClientProvider` is mounted in `main.jsx`, and
`queryClient.js` is configured with a stale time and a retry policy.

So three new slices would each hand-roll loading, error and refetch state that
one `useQuery` line already provides, and would file the worker portal under the
demo half of the app rather than the real half. Written instead:
`features/worker/workerApi.js`, thin `api()` wrappers in exactly the shape of
`features/registration/registrationApi.js`, with react-query owning every cache.

### 4.21 Nine worker pages are three questions, not nine

`MyCommunities`, `FindCommunities` and `Applications` are three views of *where
do I work*, and a worker holding a phone at a job site should not have to know
which of three pages their pending application is on. They are one
`Communities.jsx` with three panels.

`TodaySchedule` is not a page either: it is what `GET /worker/snapshot` returns,
which makes it the dashboard home rather than a sibling of it.

Final nav: **Dashboard · Calendar · Availability · Communities · Messages ·
Profile**, plus `JobDetailModal`, which is a modal and never a route.

### 4.22 The community search could not be applied to

Found by building the screen that consumes it, which is the only way it could
have been found.

`GET /worker/communities/search` returned `departmentNames: string[]`.
`POST /worker/applications` takes a **`departmentId`**. And a provider who is
not yet a member of that community cannot read `GET /departments` — the guard
requires membership. So there was no route from a search result to an
application: the screen had a list of names and nothing to press.

**The fix is one column, and the obvious version of it is wrong.** Adding
`array_agg(distinct d.id)` beside `array_agg(distinct d.name)` gives two arrays
that do not correspond: `array_agg(distinct …)` sorts by its own argument, so
the ids come back in uuid order and the names in alphabetical order, and row
three of one names row three of the other only by accident. It would have looked
correct in every test with one department.

So `department_names text[]` becomes `departments jsonb` —
`jsonb_agg(distinct jsonb_build_object('id', d.id, 'name', d.name))` — and
`ServiceableCommunity.department_names` becomes
`departments: list[DepartmentRef]`. Four files: `0034`, `hiring_schemas.py`,
`hiring_service.py`, `API.md`, plus a spec regeneration. Nothing consumed the
old field, because nothing had yet been built that could.

---

### 4.23 The resident's activity list is a notification feed, and §6.10's file table missed it

*Found while changing `notifications_service.list_feed`'s signature.*

`GET /resident/snapshot` renders `activity` from the same `list_feed` the bell
reads. Re-keying the feed on the profile therefore changes what a **resident**
sees, not only what a worker sees, and §6.10's file table named neither
`resident_snapshot_service.py` nor its router.

The change is one the endpoint should welcome rather than tolerate. Its own
docstring already says `unreadNotifications` counts *the whole feed* rather than
the page, because a badge assembled from a page is wrong the moment anybody
scrolls. Under the old shape that sentence was only true within one community: a
resident who also worked in another society saw this community's share of their
activity here and a different number on every other screen. Now the two agree.

The router needed a second dependency to say it — `get_current_user` beside
`get_active_membership` — which costs nothing, because the first already resolves
the second.

### 4.24 A provider who signs in a second time had nowhere to land

*Found while writing the frontend collapse, and it is the reason `auth_service`
was changed twice rather than once.*

§6.10's `D21` was about one thing: a *department* manager was being routed to the
security portal because the portal was derived from the presence of a department
rather than its kind. Correct, and incomplete.

The collapse in `D22` made a second gap visible immediately. `homeRouteFor` reads
`portal`, and `GET /auth/session` returns **no portal at all** for a caller with
no membership — it returns `onboarding_eligible: true`, which routes to
`/get-started`, the *society registration* flow. So a service person who had
registered, applied, and come back the next day was sent to a screen for founding
a housing society, or fell through to `/account`. Either way, nothing pointed at
`/worker`, which is where their applications are.

Under the old two-function shape this was invisible, because neither function
looked at a membership-less session for anything except onboarding.

Fixed where the knowledge is: when there is no membership, `resolve_session`
asks whether the caller has a `service_providers` row and answers
`portal: "worker"` if so. One extra read, and only on the path that by definition
has no membership to read anything else from. The browser cannot answer this
question — which is the same argument that made `portal` the right key for
`homeRouteFor` in the first place.

---

### 4.25 The gate has a backend and nobody scheduled it a screen

*Found while scoping Step 9.*

The approved plan's build order has twelve rows and none of them puts a consumer
in front of `security_operations.py`. Step 7 built `0040` and the router and
closed `US-3.3`–`US-3.6` on the API; Step 8 was the worker portal; Step 9 is
*"manager hiring, messages, vocabulary reconciliation"*. `SecurityDashboard.jsx`
(1070 lines) and `SecurityManagerDashboard.jsx` (556) are both the demo, over
zustand, and neither calls one of those endpoints.

§0 of this journal has claimed since Step 8 that Step 9 includes the gate
screens. That sentence was mine and it was wrong; nothing in the plan supports
it.

**Why this is worth a numbered entry rather than a to-do.** It is the §4.22
shape. The community search returned department *names* with no ids and could
not be applied to, and nothing found that until a screen tried to consume it. A
whole gate surface — material registers, tanker logs, incidents, the offline
bundle, the reconcile endpoint, the CSV exports — has never had a consumer, so
every one of its response shapes is unproven in the only way that finds this
class of defect.

**Recommendation, not a decision.** It wants its own step between 9 and 10, of
roughly Step 8's size. Building it inside Step 9 would have doubled the step and
left neither half reviewable, which is why this is written down instead.

### 4.26 A roster row could not say who it was

*Found while building the hiring screen's roster tab, and it is the third time a
consumer has proved a read one field short.*

The roster tab offers two verbs on one card, and they take two different ids:

| Verb | Endpoint | Wants |
|---|---|---|
| Remove | `POST /departments/{id}/members/{staffId}/remove` | `staff_assignments.id` |
| Blacklist | `POST /departments/{id}/blacklist` | `service_providers.id` |

`0035` added `staff_assignments.service_provider_id` and the write path fills it
— `decide_service_application` inserts the staff row with the provider id and the
membership id in one transaction. **Nothing reads it.**
`department_staff_overview` is from `0019`, predates the column by sixteen
migrations, and projects fourteen fields that do not include it. So every read
the admin dashboard has returns a hired plumber and a name somebody typed into a
form as the same shape.

That is an abstraction leak until a screen needs to act on the difference, and
then it is a wall: one read carries the first id, no read carries the second, and
the two buttons cannot sit on the same card.

Both alternatives were worse. A second request per row to work out who a roster
entry is; or a roster assembled out of `service_applications` filtered to
`accepted`, which would silently omit every typed-in name and still call itself
the roster.

Fixed by `0042_roster_provider_link.sql` — one column added to the view, plus
`_STAFF_SELECT`, `StaffMember` and `_to_staff`. The screen now labels each row
*service partner* or *roster name*, which is what makes the absent Blacklist
button on the second kind read as a fact rather than a bug.

**The pattern is worth naming, because this is three for three.** A field that
only the *write* path uses looks complete in every test, because the test asserts
the write.

### 4.27 `assignTechnician` writes an id **and** keeps the label

*A deliberate departure from `D26`, which said the label would be derived at
render.*

`D26` was written from `DepartmentDetail.jsx` alone. Five other files read
`complaint.assignee` directly — `Complaints.jsx`, `Header.jsx`, the two resident
screens and the seed data in `createComplaintsSlice.js`. Deriving the label at
render means renaming the field in all six and re-seeding, for a demo.

So the assignment is now `assigneeStaffId`, and `assignee` survives beside it as
a denormalised display string. **Every lookup uses the id and no code parses the
label**, which is what `DECISIONS_NEEDED` B2 actually indicts — both string
comparisons are gone:

- `complaint.assignee?.split(' - ')[0]` matched against every staff name, to
  recover the id the write had thrown away;
- `complaint.assignee?.startsWith(member.name)`, which credits "Ravi Kumar" with
  "Ravi Kumaran"'s complaints.

**What this does not fix, stated rather than glossed:** renaming a staff member
still leaves a stale label on their existing assignments in the demo. The id is
correct, so nothing is *lost* — the display is simply out of date until the
complaint is reassigned. On the backend this cannot happen at all, because
`work_order_assignments` stores only the foreign key.

---

### 4.28 The freeze is a trigger, not three rewritten functions

§6.12 said `dispatch_candidates`, `assign_work_order` and `schedule_security_shift` would each gain a
guard against a departing worker. Two of those three are long `plpgsql` bodies that would have had to
be recreated whole to add four lines, and the copy is where transcription errors live.

They are two `before insert or update` triggers instead — `work_order_assignments_block_departing`
and `security_shifts_block_departing` — and the change is not only smaller, it is **larger in
coverage**. The rewrite would have guarded the two writers I could name. The triggers guard every
writer, including the ones I did not think of: `dispatch_auto_assign`, `dispatch_ping_candidates`,
the worker's own accept in `0039`, and whatever gets written next year.

`dispatch_candidates` was still recreated, and had to be. Leaving the sweep ignorant and letting the
trigger refuse the write would turn every auto-assign of a departing worker into a failed dispatch
task with a retry, rather than an assignment to somebody who can actually go. This is the same
division `0036` argued for out loud when it put an exclusion constraint behind an overlap check: the
constraint is the guarantee and the sweep is only the guess.

### 4.29 Four of the five url-less notifications are fixed in Python, not SQL

§6.12 said the five hiring notifications the journal recorded as unclickable (§5.18) would get their
`url` in the same migration. One of them does — `service_engagement_ended`, because
`remove_department_member` was being recreated anyway.

The other four are in `apply_to_department` and `decide_service_application`, neither of which `0043`
otherwise touches. Recreating a hundred and fifty lines of `plpgsql` to add one key to a
`jsonb_build_object` is the transcription risk in 4.28 again, and for less.

They are fixed in `notifications_service.render` instead, in a `_FALLBACK_URLS` table beside the
`_FALLBACK_TITLES` one that **already renders these same seven kinds**. That is not a second
mechanism: `render` returns `(title, body, url)` and two of the three already had a fallback layer;
this completes it. It is also testable in a suite that runs, which the SQL is not.

One sentence had to be corrected to do it. The comment beside `_FALLBACK_TITLES` said the missing
`url` was "a separate gap… since a link is not something a fallback can invent" — I wrote that, and
it is true in general and wrong about these four, whose payloads already carry the id the route
needs. The fallback table says so in as many words, so the next person to add a kind does not read
the rule as broader than it is.

## 5. What has landed, in order

Newest last. Each entry names the intent that preceded it and the outcome.

### 5.1 Step 0 — `ponytail` installed

Six skills under `~/.claude/skills/`: `ponytail`, `-audit`, `-debt`, `-gain`,
`-help`, `-review`. The upstream repo's JS hooks were deliberately **not**
installed — they would require editing `settings.json`, which is out of scope for
a feature branch.

### 5.2 `backend/supabase/migrations/0034_service_providers.sql` — written, statically validated

681 lines, 52 statements, `pglast`-clean. House conventions throughout: prose
header naming the non-obvious decision, numbered `-- ---` sections, `if not
exists` everywhere, constraints inside `do $$` blocks pinned by `conrelid`,
`text` + named `_check` rather than new enums, views with `security_invoker =
true`, `security definer set search_path = public` on privileged functions,
grants to `authenticated` and never `anon`.

Eleven sections:

1. `create extension if not exists postgis with schema extensions`
2. `haversine_km(numeric, numeric, numeric, numeric)` — the immutable SQL
   fallback if PostGIS is unavailable (plan D7)
3. `communities.latitude` / `longitude` + a generated
   `location extensions.geography(Point, 4326)`, GiST index, range checks
4. `skills.is_active` / `created_at`, plus 12 seeded skills — Plumbing,
   Electrical, Carpentry, Masonry, Painting, Appliance Repair, Air Conditioning,
   Housekeeping, Gardening, Pest Control, Security Guard, Gate Officer
5. `complaint_categories.skill_id` + the `link_category_skill()` trigger +
   backfill — **§4.1**
6. `service_providers`
7. `service_provider_skills`
8. `blacklisted_service_providers` — **§4.2**
9. `service_provider_overview` view
10. `search_serviceable_communities()` — the dashboard's "find a community"
    query: skills match a department's categories, not blacklisted, not already a
    member, ascending by distance
11. Write RPCs and RLS

**Not applied to any database** — see §7.4.

### 5.3 The tenancy seam — `app/domain/schemas.py` + `app/api/deps.py`

The one edit to shared code, and the one flagged for the auth owner's review
before merge (plan D14).

`schemas.py` gains `MembershipSet` immediately after `MembershipContext`: a pure
DTO with `default`, `community_ids` and `for_community(...)`. See §4.3 for why it
has no raising method.

`deps.py`:

- **New** `get_membership_set(...)` — the exact query `get_active_membership`
  used to run, with the `limit 1` dropped. Same ordering
  (`is_default_community desc, created_at`), same 403 when there is no active
  membership, same single round trip per request.
- **Changed** `get_active_membership(...)` — now derives from
  `get_membership_set` and returns `memberships.default`. Signature, return type
  and behaviour unchanged for every existing caller.
- **New** `require_community_role(community_id, memberships, *roles)` — for
  handlers whose community comes from the *resource* (a job, an application, a
  department) rather than from whichever membership happens to be the caller's
  default.
- **Untouched** `require_membership_role(...)`.

Why this was needed at all: RLS was *already* multi-community —
`is_community_member(uuid)` (`0019:81`) has always been an `exists` over every
active membership. The single-community assumption lived in exactly one place,
this query. A service person belongs to as many communities as have hired them,
and their calendar is the union of all of them.

### 5.4 Planning documents consolidated into `docs/plans/`

At the PO's instruction. `git mv` for the seven tracked ones, plain `mv` for the
two untracked service-operations files:

`ADMIN_DASHBOARD_BUILD_PLAN.md`, `ADMIN_DASHBOARD_PLAN.md`,
`AUTH_REGISTRATION_IMPLEMENTATION_PLAN.md`, `BACKEND_PLAN.md`,
`IMPLEMENTATION_PLAN.md`, `RECONCILIATION_ADDENDUM.md`,
`SCHEMA_RECONCILIATION_PLAN.md`, `SERVICE_OPERATIONS_PLAN.md`,
`SERVICE_OPERATIONS_PROGRESS.md`.

Every **live** cross-reference was repointed in the same change — links inside
the moved files that pointed up into `docs/` (`../API.md`, `../CHANGE_LOG.md`,
`../../frontend/src/...`), and links from outside that pointed at them
(`docs/ADMIN_REGISTRATION_FLOW.md`, `docs/ARCHITECTURE.md`,
`docs/erd/homebandhu.dbml`, `docs/potential issues/README.md`,
`backend/app/api/v1/admin_api.py`, `0018_settings_on_baseline.sql`).

**`CHANGE_LOG.md`'s historical entries were deliberately left alone.** They are a
dated record of what was true at the time; rewriting forty of them to say
`plans/` would be falsifying the log to make a `grep` tidier. The move is
recorded as a new entry instead.

`AUTH_REGISTRATION_IMPLEMENTATION_PLAN.md` is the auth workstream's document, not
ours. It was moved because the instruction said *all* planning documents — but
it is the one file in the set whose owner should get a veto.

### 5.5 The `service_providers` API triple — six operations

The house layering, no exceptions: the router does HTTP and declares guards at
router level, the service translates vocabulary and raises `AppError` subclasses,
the repository reads a view and writes through an RPC.

| File | What it is |
|---|---|
| `app/domain/service_provider_schemas.py` | Eight wire models on `CamelModel` |
| `app/repositories/service_providers_repository.py` | Reads `service_provider_overview`; writes through the three `0034` RPCs |
| `app/services/service_providers_service.py` | Row → DTO, and the 404 for an unregistered caller |
| `app/api/v1/routers/service_providers.py` | Six routes |
| `app/api/v1/service_api.py` | The aggregate, mounted from `app/api/v1/__init__.py` |

Operations: `GET /skills` · `POST /service-providers` · `GET`/`PATCH
/service-providers/me` · `PUT /service-providers/me/skills` · `PATCH
/service-providers/me/availability`.

**Three decisions in here are worth knowing before changing any of it.**

*No membership guard on any route.* Deliberate, and the whole reason §4.4 exists.
Authorization moved into the RPCs, which resolve the caller from `auth.uid()`,
and into `service_providers` carrying a read policy and no write policy at all.
On routes with no membership guard, CSRF is the only thing standing between a
cross-site form post and someone's registration — which is what
`test_api_130` pins.

*Every write re-reads rather than echoing.* Three fields are not the caller's to
set: `skillNames` comes from the catalogue, `serviceRadiusKm` defaults in SQL,
`communityCount` is counted from live memberships. Echoing the request back would
return everything except the answers.

*One `save_mine` behind both `POST` and `PATCH`,* because `upsert_service_provider`
is one RPC. The two routes differ only in status code, which is a fact about HTTP
rather than about the domain.

An aggregate router was created for one router today because eight more follow it
in this build order, and because `admin_api.py` and `resident_api.py` exist for
the stated reason that two workstreams should never edit the same router list.

### 5.6 Tests, and the verification that closes Step 1's code

`tests/test_membership_set.py` (10 cases) and `tests/api/test_service_providers.py`
(9 cases). The seam module is the evidence offered to the auth workstream with the
review request in §7.3 — it pins the direct-call form, the ordering, the single
round trip, the unchanged 403, and both refusals from `require_community_role`.

The API module's fixture deliberately overrides **only** identity, leaving
`get_active_membership` live. If a membership guard is ever added to one of these
routes, the resolver runs against the sentinel client and the test fails — rather
than the product quietly becoming un-hireable.

| Check | Baseline | Now |
|---|---|---|
| `pytest -q` | 694 passed | **713 passed** |
| `ruff check .` | 153 errors | **153 errors** — not one added |
| `export_openapi.py --check` | clean | **clean**; 105 operations across 91 paths |
| `api_map_scan.py --strict` | 20 findings | **20 findings** — all six new operations documented |
| `pglast` on `0034` | — | **52 statements** |

### 5.7 Documentation for the six operations

- `scripts/api_annotations.py` — six `OPERATIONS` rows plus two new `NO_STORY`
  groups, `service_provider` and `skill_catalogue`. The export raises `SystemExit`
  in *both* directions, so this was never optional.
- `scripts/export_openapi.py` — a description for the new `service-providers` tag;
  the build refuses a tag without one.
- `docs/openapi.yaml` — regenerated, never hand-edited.
- `docs/API.md` — a new **§18**, plus updated surface counts and a changelog row.
- `docs/api_yaml_mapper.md` — a router table and a rescan row.

**§18 sits after the three meta-sections rather than before them,** and the
section says so rather than leaving it to look like a mistake. Inserting it as
§15 would shift §15/§16/§17 and invalidate around twenty cross-references in four
documents mid-build. The renumber is deferred to Step 10, where §19 for security
operations lands too and one pass covers both.

**All six trace to no user story, and that is the honest answer.** Every story
this feature eventually closes — US-2.7, US-2.8, US-3.3 through US-3.6 — is about
work being *done*, which begins at hiring. Registration serves nobody's story.

### 5.8 The four §8 defects, fixed

Intent in §6.0, which was written first. Outcome:

| Defect | Fix | Net lines |
|---|---|---|
| 1 — missing repository function | `MembershipContext` injected at both routes; `_caller_membership` and two repository imports deleted | **−9** |
| 2, 3 — visibility vocabulary | `comment_visibility_to_storage` in `vocabularies.py`; service raises `unknown_visibility` | +14 |
| 4 — ERD | `departments` and `staff_assignments` blocks completed from `0019` | +26 (doc) |

**Defect 1 removed two database reads from each of the two writes** and did not add
a repository function, because the membership the service was trying to
reconstruct had already been resolved by the dependency that guards the route.

**The visibility fix changed no wire vocabulary.** `resident` is still what the
frontend sends and what `API.md` documents; `public` is now also accepted, so a
client that has learnt the stored word is not forced back through the display
word. Two documentation edits followed the failure mode moving out of Postgres
and into the service: `API.md`'s error table and the `OPERATIONS` errors list
both trade `409 conflict — unknown visibility` for `422 unknown_visibility`.

**The tests are the part worth reading.** `test_api_009` and `test_api_010`
monkeypatch the whole service — correct for asserting routing and status codes,
and the reason both defects survived: *a test that replaces the thing under test
cannot find a bug inside it*. Three new cases (`api_133`–`api_135`) let the real
service run and replace only the repository beneath it, with a fake client that
answers `_actor_label`. `api_134` asserts the repository is **not reached**, not
merely that the status is 422. Nine vocabulary cases pin the mapping itself,
including `test_every_stored_visibility_satisfies_the_check_constraint`, whose
sibling would still pass if the map returned `resident` unchanged.

| Check | Before | After |
|---|---|---|
| `pytest -q` | 713 passed | **725 passed** |
| `ruff check .` | 153 errors | **153 errors** |
| `export_openapi.py --check` | clean | **clean** — 105 operations, 91 paths |
| `api_map_scan.py --strict` | 20 findings | **20 findings** |

The ERD block was fixed to what `0019` actually says, **not** to what `0035` will
say. Step 2 changes `rank` and `shift` and adds a column; it updates the block
when it does. Writing tomorrow's values into a diagram that documents today's
migrations is how the block got wrong in the first place.

### 5.9 `0035_department_roles_and_hiring.sql` — written, statically validated

47 statements, `pglast`-clean, house conventions throughout. Eight sections:

1. **Three ranks.** The check relaxed to `manager | supervisor | member`, the
   partial unique index renamed to `staff_assignments_one_active_manager`, and
   the three other places `0019` said `head` — see §4.6.
2. **Two vocabularies that were failing.** `departments_kind_check` →
   `service | security` (§8.5); `staff_assignments_shift_check` → the five words
   of D4 (§8.6). `departments_service._VALID_SHIFTS` widened to match in the same
   change, because a check and a validator that disagree is the defect, not
   either one of them alone.
3. `staff_assignments.service_provider_id`, plus a partial unique index giving a
   provider one *live* roster row per department — a rehire is a second row, so
   the first one's history stays readable.
4. `service_applications` — one table, one `direction`.
5. `service_application_overview`.
6. `search_hireable_service_providers(...)` — §4.7.
7. Five write RPCs plus the `can_manage_department` predicate.
8. Read policies only, no write policy at all — the `0031`/`0034` posture.

**The ordering bug worth knowing about.** Section 1 first wrote
`update ... set rank = 'manager'` and *then* dropped the old CHECK. The old check
allows `('head','member')`, so the update would have raised `23514` and taken the
migration down with it — on a database where `0019` had run, which is the only
kind where the statement does anything. Drop, correct, re-add. Caught by reading,
not by a tool; `pglast` parses both orders happily.

**One notification path is deliberately silent, and the migration says so in
print.** `notifications.recipient_membership_id` is `not null` (`0001:90`) and
cannot be otherwise — a notification belongs to somebody in a community. A
*rejected* applicant holds no membership there by definition, so there is no row
to address; the same is true of an invitation. An **acceptance** is notified,
because the membership the accept just created is the address it goes to. That
is the first notification a service person can receive, and it says they were
hired. Everything else on that surface is a read: `GET /worker/applications`.

**`can_manage_department(uuid)` is new and is the authorization spine of this
file.** Not "is the caller an admin somewhere" — an admin of *this* department's
community, or a manager whose own membership names this department (or names
none). Without it, a manager of one community could hire into another by putting
its id in a request body, which is the failure `ADMIN_DASHBOARD_DESIGN.md` §10
names.

**Not applied to any database** — §7.4.

### 5.10 The hiring API — eleven operations, two routers, one atomic write

| File | What it is |
|---|---|
| `app/domain/hiring_schemas.py` | Nine wire models on `CamelModel` |
| `app/repositories/hiring_repository.py` | Two views, two search RPCs, five write RPCs |
| `app/services/hiring_service.py` | Row → DTO, rank translation, decision validation |
| `app/api/v1/routers/worker_communities.py` | Five routes, provider-self |
| `app/api/v1/routers/department_hiring.py` | Six routes, `admin`\|`manager` |

**Four things in here are worth knowing before changing any of it.**

*One negotiation is one shape on the wire.* A manager's inbox row and a
provider's applications row are the same `ServiceApplication`, because the
database serves both from one view. `direction` is what a client switches on to
decide which buttons to draw — deriving it from the caller's role would need the
client to know its own role in every community on the screen, which is precisely
what a cross-community list does not have.

*The router guard on `department_hiring.py` is deliberately the weaker of two.*
`require_admin_or_manager` asks whether the caller manages *anything*, resolved
from their default membership; it cannot ask about the department in the path,
because that department's community is unknown until something reads it. The real
check is `can_manage_department` in Postgres. The coarse one still earns its
place: it turns "signed-in stranger walks department ids" into a 403 before any
query runs.

*`POST .../members/{staffId}/remove`, not `DELETE`.* Two reasons, and both are
real. Nothing is deleted — the roster row is deactivated (`0019` A7). And
`reason` is a note one person writes about another that reaches them in a
notification: `DELETE` cannot carry a body, and the alternative the export
suggested — a query parameter — would put it in every access log on the way. The
export refused the DELETE-with-body outright, which is how this surfaced.

*`head` is accepted as a rank and stored as `manager`.* `_RANK_TO_STORAGE` in
`hiring_service.py`, the same translation seam `vocabularies.py` holds for
statuses. Refusing the word the admin screens have always used would turn a
working screen into a 422 for no gain.

**Tests: 15 cases, `api_136`–`api_150`.** `test_worker_communities.py` reuses
Step 1's guard property — the fixture overrides only identity and leaves
`get_active_membership` live, so a membership guard creeping onto one of these
routes fails the test rather than quietly making the product un-hireable.

`test_department_hiring.py`'s docstring states the limit honestly: **no
in-process test can prove the hire is atomic**, because the transaction is in
Postgres and the RPC is a stub. What the cases can prove is that the API never
offers a path around it — `api_143` asserts one call, carrying the terms, with
nothing beside it. `api_145` asserts the 403 for a manager of another community
arrives *from the repository*, not from the router guard; asserting the guard
would be asserting the check we deliberately do not rely on.

| Check | Before | After |
|---|---|---|
| `pytest -q` | 725 passed | **740 passed** |
| `ruff check .` | 153 errors | **153 errors** |
| `export_openapi.py --check` | clean | **clean** — 116 operations, 101 paths |
| `api_map_scan.py --strict` | 20 findings | **19 findings** — all eleven documented; the remaining ones are all pre-existing (auth, access requests, dashboard amenities) |

### 5.11 Step 3 — `0038`, `conversations.py`, and the guard that is not in the router

Landed 2026-08-09, to the contract in §6.4 including both amendments made to it
before the first line was written.

**The migration.** `0038_conversations.sql`, 35 statements, pglast-clean. Two
tables, two views, three functions, two read policies and no write policy at
all.

**The one decision worth re-reading.** Both other routers in this feature have a
guard that a router *can* state. This one does not, and it is not an omission:
a conversation belongs to one department **and** one provider, so participation
is a property of the row rather than of the caller's role. There is no role a
router could check that would answer it. `is_conversation_participant` is the
single definition, called by both read policies and both RPCs, and the API layer
contains no participation check at all — a fourth copy of a rule already stated
three times in SQL is a fourth thing that can drift, and the copy furthest from
the data is always the one that does.

That produces three different answers to the same fact, which is deliberate:

| A caller not in the thread | Answer | Why |
|---|---|---|
| `GET /conversations` | absent from the list | the policy filters |
| `GET /conversations/{id}` | **404**, not 403 | a 403 confirms the thread exists |
| `POST .../messages` | **403** | the caller has already named a thread they can see |

**Two amendments to §6.4, both made before building — see §4.8 and §4.9.** The
route list gained `POST /conversations` (with three routes, nothing could ever
create a thread) and lost its trigger (with read policies only, there is no
second writer to defend against). Participation narrowed from "managers and
supervisors" to `can_manage_department`.

**Tests: 9 cases, `api_151`–`api_159`.** The module docstring states the limit
in the same terms Step 2's did: the plan's verification is *"RLS denies a
non-participant"* and no in-process test can prove that, because the policy runs
in Postgres. What these cases prove is the thing that would make the policy
irrelevant — that the API offers no path around it. `api_152` pins that
`departmentId` narrows and cannot widen; `api_153` pins 404-not-403; `api_158`
asserts the refusal arrives *from the repository*, so a check added to the
service later would fail the test that says there is none.

**One gap closed that Steps 1 and 2 left open.** `test_every_router_is_mounted`
had no representative path for *any* of the four service-operations routers.
They are mounted behind a single `include_router` in `service_api.py`, so
deleting that one line would have removed twenty operations and raised nothing
anywhere. Four paths added.

| Check | Before | After |
|---|---|---|
| `pytest -q` | 740 passed | **753 passed** |
| `ruff check .` | 153 errors | **153 errors** |
| `export_openapi.py --check` | clean | **clean** — 120 operations, 104 paths |
| `api_map_scan.py --strict` | 19 findings | **19 findings** — all four documented; the rest pre-existing |

### 5.12 Step 4 — `0036`, `work_orders.py`, `resident_scheduling.py`

Landed 2026-08-10, to the contract in §6.5 with the three amendments in §4.11,
§4.12 and §4.13 made as they were found.

**The migration.** `0036_work_orders.sql`, 69 statements, pglast-clean. Four
baseline tables extended (`work_orders`, `work_order_assignments`,
`worker_availability_rules`, `worker_unavailability`), three predicates, two
views, six RPCs, four read policies and **no write policy anywhere** — the
posture `0031`, `0034`, `0035` and `0038` all keep.

This un-parks the second half of `CONFLICT_RESOLUTIONS` **R16**, which said to
build nothing against those tables. The amendment to R16 itself is Step 10's;
the overturn is recorded in the migration header, in `API.md` §18 and in the
change log so it is not discovered by reading code.

**The constraint the step exists to carry:**

```sql
exclude using gist (
  staff_assignment_id with =,
  tstzrange(scheduled_start_at, scheduled_end_at, '[)') with &&
) where (status = 'accepted' and scheduled_start_at is not null)
```

Drawn in `erd/homebandhu.dbml:614` since the ERD was written; this is where it
starts existing. The `where` clause is the half that matters — only `accepted`
rows are constrained, so Step 5 may offer one slot to several workers and let
exactly one take it.

**The state machine, and what is deliberately unreachable.**

| Status | Reached in Step 4 by |
|---|---|
| `draft` | create with no slot · resident declines |
| `awaiting_resident` | create or reschedule with a slot, `subject_kind = resident` |
| `offered` | resident confirms · create with a slot on a `facility` job |
| `scheduled` | `assign_work_order` |
| `cancelled` | `cancel_work_order` |
| `in_progress` · `completed` · `failed` | **nothing** — the worker's transitions, Step 6 |

The last row is declared in the CHECK and written by nothing here. Stated in the
migration header so its absence from the writes reads as intended.

**Ten operations, two routers, one service.** `work_orders.py` (eight) and
`resident_scheduling.py` (two) share `work_orders_service`. Splitting the service
would put the two sides of one state machine in two files, and
`awaiting_resident → offered` would be written in one and read in the other. The
routers differ because the *guards* differ; the state machine does not.

**The router guard is coarse and cannot be otherwise.** A supervisor holds a
`worker` membership with the `supervisor` **rank** — `0035` settled that rank and
role are different things — so
`require_membership_role("admin", "manager", "worker", "security")` is the
narrowest role filter that admits every legitimate caller. `can_supervise_department`
is the boundary, and it is a new predicate: `can_manage_department` would have
handed triage to managers only, and triage is the supervisor's job.

**Neither resident route takes a work-order id.** The job is resolved from the
complaint — newest **live** one, so a cancelled retry cannot hide the visit that
replaced it — which makes naming somebody else's job unexpressible rather than
merely refused.

**The timeline learned five words for free.** `complaint_events.event_type` is
`text` with no CHECK (`0001`:70), so `job_created`, `job_scheduled`,
`job_declined`, `job_assigned` and `job_cancelled` needed only `_EVENT_LABELS`
and `_event_message` in `resident_complaints_service.py`. No `work_order_events`
table, which would have needed its own view, renderer and RLS and would have
split one complaint's story across two timelines.

**Tests: 25 cases, `api_160`–`api_184`,** across
`tests/api/test_work_orders.py` (16) and `test_resident_scheduling.py` (9). The
same limit both earlier modules state: the plan's verification is *"the overlap
constraint rejects a double-booking"*, and no in-process test can prove that
because the constraint runs in Postgres. What these prove is that the API
**reaches** it rather than routing around it.

Three of them assert an **absence**, which is the harder kind to notice going
missing:

- `api_167` — the `PATCH` forwards no status and no time. Both have their own
  routes because both carry a notification.
- `api_168` — assigning without a slot forwards `None`, so `0036` uses the job's
  own times rather than a booking with no hour, which the partial exclusion
  constraint cannot see.
- `api_170`, `api_181`, `api_182` — every 403 and 409 arrives *from the
  repository*, so a check added to the service later fails the test that says
  there is none.

**One user-story count moved for the first time in four steps.** Steps 1–3 added
twenty-one operations that map to nothing. Step 4 added ten, of which five map —
US-2.7 and US-2.8, lifecycle notifications and knowing who is responsible.
`POST .../assign` is where `DECISIONS_NEEDED` **B2** is finally answered: the
assignee stops being a formatted string and becomes a roster row. Recounted from
the spec, not by hand: **56 mapped, 74 unmapped, 130 total.**

| Check | Before | After |
|---|---|---|
| `pytest -q` | 753 passed | **780 passed** |
| `ruff check .` | 153 errors | **153 errors** |
| `export_openapi.py --check` | clean | **clean** — 130 operations, 112 paths |
| `api_map_scan.py --strict` | 19 findings | **19 findings** — all ten documented |
| `pglast` on `0036` | — | **69 statements** |

### 5.13 Step 5 — `0037`, the dispatcher, and the lifespan

Built exactly as §6.6 specified, including both departures from the plan. What
landed:

| File | |
|---|---|
| `backend/supabase/migrations/0037_dispatch_engine.sql` | new — 44 statements: `dispatch_tasks`, two queue helpers, the trigger, the claim, three outcome recorders, the sweep, three firing RPCs, `fire_dispatch_task`, RLS and grants |
| `backend/app/repositories/dispatch_repository.py` | new — `claim_batch`, `fire`, `complete`, `fail`. Service client only |
| `backend/app/core/dispatcher.py` | new — `Dispatcher`, mirroring `PushSender` |
| `backend/app/main.py` | edited — starts beside `sender`, stops before it |
| `backend/tests/test_dispatcher.py` | new — 10 tests |

**The trigger is the single writer of `dispatch_tasks`.** Nothing enqueues by
hand, so cancelling a job stops its timers without `cancel_work_order` knowing
the table exists, and a future write path cannot forget to arm one.

**One test asserts an absence, and it is the one worth keeping.**
`test_the_dispatcher_knows_nothing_about_task_kinds` reads the source of
`Dispatcher` and fails if the string `ping`, `auto_assign` or `resident_timeout`
appears in it. If a branch on `kind` ever grows in Python, the engine has started
living in two places, and that is exactly the kind of drift no other check would
notice.

**A defect `pglast` could not have caught.** `pglast` validates a migration's
outer statements and treats every `$$...$$` body as an opaque string, so a syntax
or scoping error inside a function survives the check. Parsing the three
`language sql` bodies separately found a real one: in a SQL-language function the
`RETURNS TABLE` column names are in scope as variables, so `dispatch_candidates`'
unqualified `order by has_adjacent_job` was ambiguous against its own output
parameter. Restructured into a `ranked` CTE so every reference is qualified. The
throwaway script is worth rebuilding for `0039`.

| Check | Before | After |
|---|---|---|
| `pytest -q` | 780 passed | **790 passed** |
| `ruff check .` | 153 errors | **153 errors** — none added |
| `export_openapi.py --check` | clean, 130 ops | **clean, 130 ops** — unchanged, as intended |
| `api_map_scan.py --strict` | 19 findings | **19 findings** — unchanged |
| `pglast` on `0037` | — | **44 statements**, plus 3 SQL bodies parsed |

Documented in `API.md` §18 (a new *"The engine"* subsection, plus three stale
passages corrected now that the dispatcher exists), `ARCHITECTURE.md` (the
workers in the component diagram, two new emitter rows, and the **D9 amendment**
to the notification rule written out with its reasoning), the submission ERD
(`dispatch_tasks`), and `CHANGE_LOG.md` Session 46.


### 5.14 Step 6 — `0039`, the worker portal, and the fourth handler

Built as §6.7 specified, including the two things that section decided against
building. What landed:

| File | |
|---|---|
| `backend/supabase/migrations/0039_worker_actions.sql` | new — 42 statements: three views, two resolvers, five verbs, three availability writes, grants |
| `backend/supabase/migrations/0037_dispatch_engine.sql` | edited — `dispatch_failed_visit_escalation`, the `failed` trigger branch, the fourth `case` arm, the decline filter in the sweep |
| `backend/app/domain/worker_schemas.py` | new — eleven models |
| `backend/app/repositories/worker_repository.py` | new — three view reads, eight RPCs |
| `backend/app/services/worker_service.py` | new — vocabulary, the calendar merge, the snapshot |
| `backend/app/api/v1/routers/worker_jobs.py` · `worker_schedule.py` | new — 8 and 6 operations |
| `backend/app/api/v1/service_api.py` | edited — two more routers |
| `backend/app/repositories/notifications_repository.py` | edited — `unread_count_for_memberships` |
| `backend/app/services/resident_complaints_service.py` | edited — three timeline labels and their sentences |
| `backend/tests/api/test_worker_jobs.py` · `test_worker_schedule.py` | new — 13 tests |

**No `worker_deps.py`, and no `require_worker`.** The full reasoning is §4.16;
the short form is that a role guard on this surface answers a question about one
of a worker's four communities, and the question worth asking is about the
assignment rather than the role.

**Two things the plan asked for are absent and one is present that it did not
ask for.** No `unreadMessages` in the snapshot — §5.11 shipped conversations
with no read receipts, so there is nothing to count and inventing one would mean
inventing the receipts underneath it. No `complaint_events` row on a decline —
`job_declined` already means *the resident declined the proposed time*, and
reusing it would have rendered a worker's decline on the resident's timeline as
their own. And `GET /worker/availability-rules` was added: a `PUT` of a whole set
with no way to read the current one is an editor that opens blank and silently
erases last week's answer.

**The escalation's idempotency check is the piece most likely to be
misremembered.** Every other firing function in `0037` checks a status. This one
cannot: a supervisor answering a failed visit raises a *new* work order, so the
failed one stays `failed` for good and a status check would escalate it on every
redelivery forever. It asks whether a newer work order exists on the same
complaint instead — and separately whether the complaint was settled some other
way, because escalating a visit for a complaint nobody has any more is the false
alarm that teaches people to ignore the real ones.

| Check | Before | After |
|---|---|---|
| `pytest -q` | 790 passed | **803 passed** |
| `ruff check .` | 153 errors | **153 errors** — three added and all three fixed |
| `export_openapi.py --check` | clean, 130 ops | **clean, 144 ops** across 124 paths |
| `api_map_scan.py --strict` | 19 findings | **19 findings** — unchanged |
| `pglast` | — | `0039` **42 statements**, `0037` **47**; 5 SQL bodies parsed separately |

One finding was briefly 20: the leave trio shares one `API.md` subsection, and
`api_map_scan` matches a documented operation by finding its path in the prose.
The `DELETE` was named as *"the `DELETE`"* rather than by its path. Spelling it
out fixed it, and the scanner was right to ask — a heading nobody can search for
is a heading nobody will find.

Documented in `API.md` §18 (the new *"worker's portal"* subsection, the engine's
task table corrected to four handlers, the operation and story counts moved to
45 and 9, and the `0039`/`0040` renumber stated where somebody looking for
security operations will hit it), `ARCHITECTURE.md` (two emitter rows and why
`work_order.escalated` reports an absence), the submission ERD (three notes that
said "no endpoint reads this yet" and were about to become false),
`api_yaml_mapper.md` (two router blocks) and `CHANGE_LOG.md` Session 47.

### 5.15 Step 7 — `0040`, the gate, and a story nobody expected to close

Built as §6.8 specified, plus the two things writing it turned up (§4.18). What
landed:

| File | |
|---|---|
| `backend/supabase/migrations/0040_security_operations.sql` | new — 100 statements: six tables, four views, two permission predicates, twelve functions, six read policies, fourteen grants |
| `backend/app/domain/security_schemas.py` | new — twenty wire models |
| `backend/app/domain/vocabularies.py` | edited — incident categories, both directions |
| `backend/app/repositories/security_repository.py` | new — four views, one table read, twelve RPCs |
| `backend/app/services/security_service.py` | new — vocabulary, the reconcile loop, the CSV writer |
| `backend/app/api/v1/routers/security_operations.py` | new — nineteen operations |
| `backend/app/api/v1/service_api.py` | edited — the ninth and last router |
| `backend/tests/api/test_security_operations.py` | new — 15 tests, `api_198`–`api_212` |
| `backend/tests/test_openapi_spec.py` | edited — three missing router paths (§4.19) |

**The guard is the opposite of Step 6's, and getting that right was the whole
design question.** `0039` takes no identity anywhere because a worker's surface
is cross-community by construction. A gate is the mirror image — a register
entry, a shift and an incident are each a fact about one society — so this file
goes back to a role guard and a community resolved from the caller's membership.

But not `require_membership_role`, and the reason is the same fact §4.16 turned
on, seen from the other side: that guard reads the role off
`MembershipSet.default`, and **a guard who lives in one society and works the
barrier of another has a default membership of `resident`.** It would refuse them
their own register. `require_gate_membership` scans the set for a membership that
holds a gate role instead. Its limit is real and is written into the router
docstring rather than discovered later: a guard employed by two societies gets the
first of the two.

**Two permission levels, not one.** `gate_community_for` is any gate staff and
covers the registers, incidents and verification; `gate_admin_community_for` adds
posts and the shift roster and admits an `admin`, a `manager`, **or** a `security`
membership whose roster row is ranked `manager` or `supervisor`. That last clause
is the first place `D3`'s rank-and-role split has to be *honoured in code* rather
than described — a security manager is a `security` membership with a rank, and
every previous mention of that fact has been prose.

**`security_shifts` is `work_order_assignments` with the nouns changed**, and §0
was right that reading `0036` §2 first would matter. Same exclusion constraint,
same `btree_gist`, same reason. The partial predicate is where they differ and it
has to: assignments constrain only `accepted` rows because five workers are
offered one slot, and nobody offers a shift to five guards — so the predicate here
is everything except `cancelled`.

**The CSV export is the only non-JSON success body in the repository**, and it
carries an explicit `responses={200: {"content": {"text/csv": …}}}` because
FastAPI cannot infer a schema from a bare `Response`. Without it the spec would
advertise an operation with no success content, and a generated client would
return nothing.

**One security fix that is not in the plan, the migration or the story.** Every
text column on these registers is typed by whoever is standing at the barrier,
and `=`, `+`, `-` and `@` are formula leaders in every spreadsheet. So an export
is a path from *anyone who can walk up to the gate* to *code that runs when the
security manager opens the audit report* — and `csv` quoting does not help,
because the spreadsheet strips the quotes before evaluating the cell. Cells are
prefixed with an apostrophe rather than stripped, because stripping turns a
quantity of `-5` into `5` and a register that alters the numbers it is auditing is
worse than one that shows an apostrophe. `api_211` pins it with the payload a real
attempt uses.

**Five story verdicts moved, and one of them twice.** `US-3.3`, `US-3.4` and
`US-3.6` go from **none** to **served**; `US-3.5` from none to **partial**,
because its missing half is a service worker in `frontend/public/` and not a
backend gap; and `US-3.1` from partial to **served**, which was not in scope —
see §4.18. Recounted from the spec rather than by hand: **73 mapped, 90 unmapped,
163 total.**

| Check | Before | After |
|---|---|---|
| `pytest -q` | 803 passed | **821 passed** |
| `ruff check .` | 153 errors | **153** — six added, all six fixed |
| `export_openapi.py --check` | clean, 144 ops | **clean, 163 ops** across 138 paths |
| `api_map_scan.py --strict` | 19 findings | **19** — 62 at the midpoint, all 43 new ones documented |
| `pglast` on `0040` | — | **100 statements**; all fourteen bodies are plpgsql and unparseable, so §5.13's SQL-body trick finds nothing here |

Documented in `API.md` (a new **§19**, the §16.5 verdicts with the overtaken
paragraphs left in place and corrected inline, the header counts, and §18's *what
is not here yet* reduced to *nothing*), `ARCHITECTURE.md` (three emitter rows and
the note that `severity` is the only field in the schema whose **value** decides
whether something notifies), the submission ERD (six tables), `api_yaml_mapper.md`
(a router block and the non-JSON note), `product/USER_STORIES.md` (five verdicts),
the migrations README, and `CHANGE_LOG.md` Session 48.

### 5.16 Step 8 — the worker portal, the calendar primitive, and the file two stories were waiting on

Built to §6.9's contract. Sixteen new frontend files, four edited, and one
backend defect the screens found (§4.22).

**`frontend/public/sw.js` — the file that was the whole of two "partial"
verdicts.** `0030` has stored push subscriptions and `app/core/push.py` has been
able to send since the resident build; `US-2.7` was blocked on a browser having
nowhere to receive them. It handles `push` and `notificationclick`, and it
caches successful same-origin GETs so a reload with no connectivity still boots
the app. It deliberately skips `/api/`: an API response served from cache would
show a worker yesterday's jobs and call them today's.

`lib/push/pushClient.js` does registration, permission, subscribe and
unsubscribe, returning `{ ok, reason }` rather than throwing — every failure
here is something to say calmly to a person, not an exception. It drops any
existing subscription before taking a new one, because a subscription is bound
to the key that created it and the protocol has no dual-key period, so a rotated
key leaves a dead subscription rather than a stale one.

**The calendar primitive is four files and no dependency.** `useCalendarRange`
owns the cursor, the grid and the `from`/`to` pair the endpoint takes; the range
covers the **whole rendered grid**, not the whole month, so the tail of the
previous month is not drawn as days off. `CalendarMonth` truncates at two
entries a cell and counts the rest. `CalendarWeek` is seven columns of entries
in time order and **not** an hour-ruled time grid — that geometry exists to make
overlaps visible, and `work_order_assignments_no_overlap` refuses to write one.

**Six routes, not nine pages** (§4.21), and the guard is the interesting part.
`SignedInRoute` in `App.jsx` requires a signed-in identity and nothing else,
because `ProtectedRoute` reads `currentUser` and `applicationUser()` returns
null for anybody with no membership — which is exactly the service person who
has registered and not been hired, the population these screens exist for. Same
problem and same answer as §4.4 on the backend.

| Verification | Result |
|---|---|
| `npm run build` | **clean**, 2076 modules; `dist/sw.js` present |
| `npx oxlint` | **7 warnings, all pre-existing**, none in the new files |
| `npm run test` | passes |
| `pytest -q` | **821** — unchanged, so nothing crossed the seam |
| `ruff check .` | **153** — baseline held |
| `export_openapi.py --check` | up to date after §4.22's regeneration |
| `api_map_scan.py --strict` | **19** — the pre-existing baseline |

Documented in `API.md` (the search response shape and why the ids are
load-bearing), `product/USER_STORIES.md` (**`US-2.7` moves to served**, and
`US-3.5`'s overstated claim corrected), `ARCHITECTURE.md`,
`design-of-components.md`, `SERVICE_OPERATIONS_DESIGN.md` and `CHANGE_LOG.md`
Session 49.

---

### 5.17 Step 8b — the notification substrate becomes person-addressed, and the auth seam gets its own design document

Landed 2026-08-10, to the contract in §6.10, with the two amendments in §4.23
and §4.24 made before the code they affect.

**The permission that made it possible.** *"you can change the auth bit too. but
do document it separately in detail in a separate file in doc/design. fix the
notification issue too. we need to implement that too."* Two rulings in one
sentence, and they turned out to be one piece of work: the notification gap
`0038` left open could not be closed without changing who a notification is
addressed to, and who a notification is addressed to is an auth question.

**The migration.** `0041_person_notifications.sql`, 51 statements, pglast-clean,
one `language sql` body re-parsed on its own. It does eight things, and the first
six are one thing done at six layers: `recipient_profile_id` on `notifications`;
a nullable `recipient_membership_id` that now means *which community this was
about*; a read policy of `recipient_profile_id = auth.uid()`; a `left join` in
the feed view; `notify_profile` beside `notify_member`; `profile_id` on
`push_subscriptions` with `membership_id` dropped; `claim_push_batch` returning a
person. Then the two writers that needed it — `post_conversation_message` and a
trigger on `notices`.

**`notify_member` kept its exact signature, and that is what made this cheap.**
Not one of the twenty-odd call sites across `0031`–`0040` changed. It resolves
the profile itself, which is the only way "always populated" can be true without
trusting every future caller to remember.

**Four defects, none of them reported, all found by building.** They are written
up in §5 of the new design document rather than here, because the pattern is the
point: every one was invisible until a population arrived that the original
decision had not imagined.

| Defect | Where it hid |
|---|---|
| The Step 8 push toggle 403s for an unhired provider | The frontend cannot see a guard; a 403 on a toggle looks like a permission not yet granted |
| `/security-manager` is unreachable by any session | The bounce target was a real working page |
| Every *department* manager was routed to the security portal | Until this feature there were no service-department managers, so the shortcut and the right answer agreed on every case anybody ran |
| A person in two societies could receive push for only one | No caller held two memberships until this feature |

**The rule that was overturned, named as `design/README.md` requires.** `0030`
states in print that someone who leaves a community stops being able to read what
was addressed to them. Under a profile-addressed policy they do not. The reason
is in `0041`'s header and in the design document: the rule only reads correctly
for a caller with one membership, and what ending a membership must stop is
*new* notifications — which `notify_community_roles` already enforces at the
moment of writing.

**One thing deleted.** `notifications_repository.unread_count_for_memberships`,
written in Step 6 to sum a badge across societies. A person-addressed feed does
not need summing, and the function was the marker that the multi-community caller
had arrived rather than a solution to it.

**The frontend collapse.** `getDashboardRouteForRole` is gone;
`homeRouteFor(subject)` is the one resolver, in `routes/authRoutes.js`, keyed on
`portal` — the only one of the three candidate values that the *backend*
computes, which is why it is the only one that can know whether a manager's
department is a security department. Eight call sites across seven files.

**Documentation.** `docs/design/AUTH_AND_SESSION_DESIGN.md` is new and is the
deliverable the PO's ruling asked for: eight sections, including one listing what
was deliberately **not** changed so a reviewer can tell restraint from oversight,
and one listing what is still open for the auth owner to rule on. Registered in
`design/README.md` outside the read-in-order list, because it is not a fourth
surface — it cuts across all three.

`US-2.4` moved to **served** in all three places the export gate compares, which
is what `api_map_scan.py --strict` checks and what caught the same move being
half-done in Session 49.

| Check | Before | After |
|---|---|---|
| `pytest -q` | 821 passed | **824 passed** — three new cases, all for the caller with no membership |
| `ruff check .` | 153 errors | **153 errors** |
| `export_openapi.py --check` | clean | **clean** — 163 operations, 138 paths, unchanged |
| `api_map_scan.py --strict` | 19 findings | **19 findings** |
| `pglast` on `0041` | — | **51 statements**; `claim_push_batch` re-parses |
| `npm run build` / `npx oxlint` / `npm run test` | clean / 7 warnings / pass | **unchanged** |

### 5.18 Step 9 — the manager's side of hiring, and one vocabulary instead of four

Landed 2026-08-10, to the contract in §6.11, with the three amendments in §4.25,
§4.26 and §4.27.

**Two new screens, both react-query, both beside the demo rather than through
it.** `DepartmentHiring.jsx` at `/admin/departments/:departmentId/hiring` —
Applications · Find people · Roster in one route — and `Messages.jsx` at
`/admin/messages`, plus `features/hiring/hiringApi.js` and one nav entry.
`DepartmentDetail.jsx` gains a single link, which is the one door from the demo
half into the live one.

**`/admin/messages` was a URL before it was a screen.** `0041` wrote
`url: '/admin/messages?conversation=<id>'` into the department side's
notification a day before anything served that path. The thread selection is
therefore a search parameter and not component state — state cannot be linked
to, and a notification whose click lands on the wrong thread is worse than one
that does not link at all.

**The vocabulary.** `frontend/src/lib/staffVocabulary.js` replaces three
`STAFF_ROLES` lists with three constants, and the split is the point rather than
the deduplication: the lists disagreed because one list was answering two
questions. `STAFF_RANKS` is closed because the database closes it; `JOB_TITLES`
is a **datalist on a free-text input** because `job_title` has no check
constraint and a closed list would invent a rule the schema does not have;
`SHIFTS` gains `Full Day`, which has been a legal value since `0035` and which no
screen could express.

**One backend change, and it came out of building the consumer.** §4.26 —
`0042_roster_provider_link.sql` adds `service_provider_id` to
`department_staff_overview`, and `StaffMember` projects it. Without it the
roster's two verbs could not sit on one card.

**Two notification holes closed on the way**, both in `0041` §9, both of which
`0035` had documented as impossible: an invited provider is now told they were
invited, and a rejected applicant is now told they were rejected. Waiting
silently was the worst of the three outcomes and it was the only one with no
message. Triggers rather than a rewrite of two long plpgsql functions, with
`when` clauses written to be disjoint from what `0035` already sends — the
accepted case stays where it is, or the person would hear it twice.

The stale docstring on `POST /departments/{id}/invitations` is corrected rather
than deleted: it gave `notifications.recipient_membership_id is not null` as the
reason nobody could be told, and naming what changed is more useful than quietly
removing a sentence that was true when it was written.

**One thing named and not fixed.** The five `0035` hiring notifications carry ids
in their payloads rather than rendered strings, so they now render a real title
from `_FALLBACK_TITLES` but still carry no `url` and are not clickable. Adding
one key to three `jsonb_build_object` calls is the fix, and it belongs with the
next change to those functions rather than in a migration whose subject is
something else.

| Check | Before | After |
|---|---|---|
| `pytest -q` | 824 passed | **824 passed** — no frontend edit crossed the seam |
| `ruff check .` | 153 errors | **153 errors** |
| `export_openapi.py --check` | clean | **clean** — `StaffMember` gained a field, spec regenerated |
| `api_map_scan.py --strict` | 19 findings | **19 findings** |
| `pglast` on `0041` / `0042` | — | **57** and **4** statements |
| `npm run build` | clean | **clean** |
| `npx oxlint` | 7 warnings | **7 warnings**, all pre-existing files |
| `npm run test` | passes | **passes** |

### 5.19 Step 9b — leaving becomes a process, and a removal that could never have been safe

Contracted in §6.12, with the two amendments in §4.28 and §4.29 applied. `0043_staff_departures.sql`,
sixty-nine statements, `pglast`-clean. Seven operations, two screens, eleven new tests.

**The instruction was about a live defect, and it was worth finding out which one.** The PO asked for
manager approval and a handover. Reading `remove_department_member` to see where the check would go
showed the reason it was needed: **the function has been able to strand work since `0035`.** It sets
the roster row inactive, ends the membership, sends one notification, returns. Nothing touches
`work_order_assignments`, so a row with `status = 'accepted'` survives a removal untouched — still
pointing at tomorrow's slot, still counted as somebody's load by `dispatch_candidates`, still
rendering on the resident's complaint as *someone is coming*. Nobody is coming, and the membership
that would have carried the reminder has just ended, so the one person who could have said so has
been logged out. `security_shifts` had the identical hole and the rota read as covered.

That reframed the work. A confirmation dialog answers the instruction; it does not answer the defect.
What answers both is making a departure **a state a person is in** — with an interval between *I want
to leave* and *you have left* in which the engine stops giving them work and the work they hold is
moved, one item at a time, by a human looking at the list.

**Nine sections in `0043`.**

1. `staff_departures` — four statuses (`pending | approved | rejected | cancelled`) and no
   `handover`, because that state is `pending` with a non-zero outstanding count and a status
   derivable from a count is a status that can disagree with it. One open request per roster row, on
   a partial unique index, which is the whole concurrency story exactly as
   `service_applications_one_open` was in `0035`. A `decision_check` constraint that refuses half an
   audit trail: a decided row records who and when, or it records neither.
2. `has_pending_departure(staff_id)` — one predicate, used by the sweep, both triggers and the read
   policy, for the reason `0036` §4 states: a rule spelled one way in a policy and another way in the
   function writing past it is how a hole opens.
3. `staff_departure_items` and `staff_open_commitment_count`. Two functions rather than the second
   counting the first, because the first returns complaint titles and post names and stays
   `service_role` only, while a count leaks nothing but a number against a uuid the caller already
   holds and is granted to `authenticated` so two views can use it. The predicates are duplicated;
   the projections are not, and the comment names that as the trade being made.
4. `department_staff_overview` recreated with `open_commitment_count` and `departure_status`.
   **Added before the screen needed it**, which is the first time in this build that has happened —
   §4.22, §4.26 and `0042`'s header are three consecutive occasions where a consumer proved a read
   one field short *after* it failed. `staff_departure_overview` beside it.
5. `notify_department_leadership` — the PO asked for *"this would notify the supervisors too"* and
   no existing helper could. `notify_community_staff` (`0031`) is community-wide admin and manager;
   `notify_community_roles` (`0032`) is by membership role. A supervisor is neither, because D3
   settled that a supervisor is a **rank on a roster row in one department**, on purpose, so somebody
   can supervise plumbing without being a manager of the society. That decision is exactly why the
   helper had to exist.
6. `request_staff_departure`, `cancel_staff_departure`, `decide_staff_departure`. Approval is refused
   with `HB409` naming the count; approving then calls `remove_department_member`, so there is **one
   removal path and not two**.
7. The handover. `reassign_departure_item` takes the ranking from `dispatch_candidates` and the write
   from `assign_work_order` — neither reimplemented, because a second implementation of *book this
   person on this job* drifts from the first the day one of them learns something the other does not.
   `security_shift_candidates` is new and honestly different: adjacency does not transfer, because a
   guard's shifts are a rota and not a route, so it orders by fewest shifts that week then nearest and
   says so rather than copying a sort key that means nothing there.
8. The freeze — §4.28.
9. `remove_department_member` with its refusal, and `release_staff_commitments` +
   `blacklist_service_provider` with the exception: **a bar ejects rather than queues.** It withdraws
   the assignments, returns each work order to `offered` — which re-arms the ping through
   `sync_dispatch_tasks` by itself — cancels the future shifts and tells the leadership how many items
   moved. Somebody barred for misconduct keeping tomorrow's job until a supervisor has found five
   successors is the opposite of what a bar is for. Written in the migration header where a reader
   comparing the two functions will find it, rather than left to be discovered as an inconsistency.

**Two distinctions the code makes that the plan did not name.**

*An offer is not a booking.* An `accepted` assignment needs a successor; an `offered` one is a
question nobody has answered — the same question is in four other workers' feeds — so it is withdrawn
and the ping re-armed. Picking somebody for an offer would quietly convert a question into a booking
that its holder was never asked about.

*Supervisors do handovers; managers approve departures.* `reassign_departure_item` guards on
`can_supervise_department`, `decide_staff_departure` on `can_manage_department`. Handover is the work;
ending somebody's employment is a different decision.

**The API.** Seven operations, no new router — the manager's verbs beside the hiring verbs, the
worker's beside their engagements, so `test_every_router_is_mounted` needs no new entry. The worker's
own status needs no eighth operation: `GET /worker/communities` carries the open departure per row,
from one extra read rather than one per card.

**The screens.** A fourth tab on `DepartmentHiring.jsx`, each departure expanding to its list with a
*Hand over* button (auto-pick) and a successor select beside it, and an **Approve** that is disabled
*with the count on the button* rather than hidden — a manager who cannot find the button assumes the
feature is broken, where one that says "2 to hand over" explains itself. The roster tab's Remove
becomes *Start handover* when the count is non-zero, so the button that would `409` is never offered.
`WorkerDashboard/Communities.jsx` gains *Ask to leave*, its pending state and *Stay after all*.

**One stale claim corrected in passing.** `worker_communities.py`'s `GET /worker/applications`
docstring still said that list was *"the only way a rejected applicant learns the outcome"* because
`recipient_membership_id` was not nullable. `0041` made it nullable eight hours earlier. That
docstring is the OpenAPI description, so the claim was wrong in a generated artifact too.

| Check | Result |
|---|---|
| `pytest -q` | **835 passed** (was 824; 11 new — 3 worker, 5 manager, 3 notification url) |
| `ruff check .` | **153** — baseline held |
| `export_openapi.py --check` | up to date, **170 operations / 143 paths** |
| `api_map_scan.py --strict` | **19** — pre-existing baseline |
| `pglast` on `0043` | 69 statements |
| `npm run build` / `npx oxlint` / `npm run test` | clean / 7 pre-existing / passes |

### 5.20 Step 10 — the documentation sweep, and the renumber it cancelled

Contracted in §6.13, and the contract's own first item was the interesting one.

**The `§15`–`§19` renumber is cancelled.** §6.13 has the counting; the short version is that 49 of
the 142 references live in `CHANGE_LOG.md`, which is a dated record, and a renumber makes those
either false or misleading. `API.md` §18's note stops promising a renumber and becomes a ruling with
its reason, naming what it overturns per `docs/design/README.md`.

**R16 amended.** Seven of the twelve parked tables are no longer parked — five live, two superseded —
and the amendment lists the still-parked three as well, because a reader who sees only the first list
cannot tell an un-parked table from an overlooked one. It also records what R16 got right, which is
more than half of it: the shapes held for two years of nobody using them.

**The class diagram gained a Service Personnel package** — fifteen classes, nine enumerations,
thirty-four associations, and the constraint notes that carry the reasoning rather than only the
cardinality. One modelling correction while writing it: `SkillCategory` was drafted as an association
class between `Skill` and `ComplaintCategory`, and this model has no `ComplaintCategory` — a
complaint's category is a `String` attribute on `Complaint`. It became a plain entity with a note.

**The rendered SVG and PNG are stale and labelled so.** `plantuml.jar` and Graphviz `dot` are not
installed and installing either is a download decision that is not mine to make. The `.puml` is the
source of truth and is correct; the directory README says at the top which files disagree with it and
what re-rendering takes. An image that silently disagrees with its source is worse than one labelled
stale — this is the one item of Step 10 that is **not** finished, and it is finished by whoever has
the two tools.

**US-3.2's stale pointer** corrected: `§14` → `API.md` §16.5.

**`DECISIONS_NEEDED.md`** — B2 answered with its residue stated, A12 revisited (the reasoning it
rested on is gone and the answer survives, plus the condition `0043` added that the entry never had),
A22 partially answered (D8 removes the blocker the question named without answering the question,
and the entry says which).

| Check | Result |
|---|---|
| `pytest -q` | **835 passed** — nothing here touches code |
| `ruff check .` | **153** — baseline |
| `export_openapi.py --check` | up to date |
| `api_map_scan.py --strict` | **19** — baseline |
| every `§` pointer added by this step | resolves to an existing heading |

**Not done, and named:** the two rendered class-diagram files.

### 5.21 Phase 2 Step 1 — one fix, one non-defect, and the baseline re-pinned

Contracted in §6.14 as two defects; building it showed the second was not one.

**Fixed:** `Header.jsx` — the search panel's input called `handleSearchChange`,
defined nowhere, so typing in the drawer threw. It now writes
`setSearchQuery(event.target.value)` directly; the setter was already
destructured from the store at the top of the component.

**Not a defect, and worth recording so nobody "fixes" it later:** admin
`Messages.jsx` invalidating only `['conversations']` after a send. React-query
invalidation is **prefix-matched** — `['conversations']` already covers
`['conversations', selectedId]`. The worker screen's explicit double
invalidation is redundant, not superior. The exploration report that called
this a lag bug was wrong; the file is untouched.

Baseline, re-pinned 2026-08-10 after the Header fix:

| Check | Result |
|---|---|
| `pytest -q` | **835 passed** |
| `ruff check .` | **153** |
| `export_openapi.py --check` | up to date (170 ops / 143 paths) |
| `api_map_scan.py --strict` | **19** |
| `npm run build` | clean |
| `npx oxlint` | **7 warnings**, all pre-existing files |
| `npm run test` | exit 0 |

### 5.22 Phase 2 Step 2 — the sweep, and what it refused to delete

Contracted in §6.15. Three deletions promised; two landed as written, one
landed smaller than promised, and that shrinkage is the entry's real content.

**`0044_retire_dead_tables.sql`** — three statements, pglast-clean. Drops
`staff_skills` and `vendors`, with `staff_assignments.vendor_id` going first
because its FK would otherwise block the table. The grep pass found zero live
references to either — only the baseline DDL, a `0019` comment, and the ERDs.
The submission ERD loses both blocks, each replaced by a comment naming what
superseded it; R16's amendment gains its "Done" line; the migrations README
gains the `0044` row.

**`roles.py`** — the promised deletion was six names and the grep allowed five.
`Role` is imported by `memberships_repository.py` (a parameter type) and
`invitations_repository.py` (`Role.RESIDENT.value`), so it stays, with a
docstring note saying why the sweep kept it. The hierarchy — `_IMPLIED_ROLES`,
`effective_roles`, `role_satisfies`, `satisfies_any`, `parse_role` — and
`tests/test_roles.py` are gone. The module docstring no longer claims to be
the single source of truth for authorization; it names the real guards.
**835 → 829 tests**, all passing; ruff held at 153.

**The frontend sweep found four candidates and deleted one.** The fallow MCP
analyzer timed out at 120 s three times (full, then scoped to one issue type),
so the sweep fell back to a resolver-based import scan
(scratchpad `dead_scan.py`) — which promptly demonstrated why tool output gets
verified: it flagged `AmenityReportsPage.jsx`, which is alive behind a
`React.lazy` dynamic import the regex could not see. Of the three real
orphans, only `AdminDashboard/CreateDepartment.jsx` was deleted (its route has
been a redirect since the reconciliation; the `staffVocabulary.js` history
comment now says the page is gone). `AmenityTabPlaceholder.jsx` and
`SignupPage.jsx` are also unreferenced but belong to the amenities and auth
workstreams — recorded in `CHANGE_LOG.md` for their owners, not deleted.
Ownership rules apply outside issue-fixing mode, and neither file is one this
feature affects.

`potential issues/` item 2 marked resolved with the `Role` amendment noted.
Build clean, oxlint 7, frontend tests exit 0.

### 5.23 Phase 2 Step 3 — a departure gets a date, and the manager gets the decision

Contracted in §6.16 and built as contracted: `0045_departure_scheduling.sql`
(88 statements, pglast-clean) plus the Python threading. The header of the
migration names what it overturns — 0043's zero-commitment refusal on
Approve — and why the refusal stays on direct Remove: that path has no
decision record and no release step.

What landed, briefly, because §6.16 already describes it: the two date
columns; `departure_bars_work` wired into both freeze triggers (whose
column lists grew by the slot column — an update moving a slot past the
barrier without touching status must fire too) and both candidate sweeps;
`dispatch_tasks` with a nullable `work_order_id`, a `departure_id`, a
`num_nonnulls` check, the fifth kind and the `priority` column; the claim
ordering `priority desc, due_at`; windowed release; decide-with-date;
`dispatch_departure_removal` behind the new `fire_dispatch_task` arm;
`departure_coverage`, `staff_schedule_items`, `staff_conflict_count`; both
views recreated with dates (`department_staff_overview`'s departure subquery
widened to approved-awaiting rows, so a roster tile can say "leaving Friday").

Two details that surfaced while writing it:

1. **The timekeeper needed `remove_department_member` to run without a
   session.** Its manager guard reads `auth.uid()`, and the dispatcher has
   none. The guard became `if auth.uid() is not null and not can_manage...` —
   safe because every authenticated caller has a uid; a null uid exists only
   inside service_role machinery, which cannot be reached by clients. The same
   recreate stamps `decided_by_membership_id` on auto-approved departures
   (§6.14's audit gap) and stops the refusal message promising a handover
   that is no longer required.
2. **A released job whose work order was reset to `offered` would have been
   re-armed by the trigger at priority 0**, silently losing the bump. The
   release loop now upserts the same timer after the status write — the
   `on conflict` re-arm is what makes two writes produce one timer — and
   high-priority work orders keep rank 2 over the release's rank 1.

Python: `StaffDeparture` gained `requestedEffectiveAt` / `effectiveAt` /
`conflictCount` (with `openCommitmentCount` re-documented as informational);
`CoverageItem` and `ScheduleItem`; both request models gained `effectiveAt`;
repo gained `departure_coverage` and `staff_schedule` (service-client, for
Step 4); `StaffMember` gained `departureEffectiveAt`. Router docstrings —
which feed the OpenAPI descriptions — rewritten so the spec stops describing
the overturned rule.

Tests: api_216 rewritten (it asserted the 409 refusal; it now asserts the
date is forwarded untouched and no gate is consulted), api_221 added
(worker's date forwarded as the same instant), fixtures widened.

| Check | Result |
|---|---|
| `pytest -q` | **830 passed** (829 + api_221; api_216 replaced in place) |
| `ruff check .` | **153** — baseline |
| `pglast` on `0045` | 88 statements |
| `export_openapi.py` | regenerated; 143 paths / 170 operations, suite green |

### 5.24 Phase 2 Step 4 — the employee page's three reads

Contracted in §6.17, built as contracted. `department_hiring.py` is fourteen
routes now: `GET .../staff/{staffId}` (the identity card — the same
`department_staff_overview` row the roster tab renders, mapped by the same
`departments_service._to_staff`, imported rather than duplicated, plus the
open departure), `GET .../staff/{staffId}/schedule?from&to` (windowed
`staff_schedule_items`, two-clients-in-order like `get_departure`), and
`GET .../departures/{id}/coverage` (the match button; `candidateCount: 0`
**is** the answer "there are none").

One scope rule worth naming: the staff reads 404 for a roster row in another
department, checked against the path's `department_id` in the repo read
itself — a URL that renders somebody from a different department is a link
that lies, and the schedule read below it would leak complaint titles across
department lines. api_223 pins this.

Schemas: `StaffMemberDetail` (`StaffMember` + `departure`). Annotations for
the three ops; the `departure` NO_STORY prose and the 409 comment block
rewritten to stop describing the overturned gate.

| Check | Result |
|---|---|
| `pytest -q` | **834 passed** (830 + api_222–225) |
| `ruff check .` | **153** |
| `export_openapi.py` | 145 paths / 173 operations |
| `api_map_scan.py --strict` | **23** — the three new ops' mapper and API.md rows are Step 9's sweep; the baseline check at Step 10 expects ≤ 19 again after it |

### 5.25 Phase 2 Step 5 — the feed gets read, and the deep links land

Contracted in §6.18. The backend has served `GET /notifications` since `0030`
and re-addressed it to a person in `0041`; until this step nothing in the
frontend called it — the only bell was a hard-coded red dot over demo data,
and only the push service worker honoured a notification's `url`.

**Built:** `features/notifications/notificationsApi.js` (list / markRead /
markAllRead, thin like every real-API file); `components/notifications/
NotificationBell.jsx` — real unread badge, 60 s `refetchInterval` (the one
element on screen that should notice the world changed while the tab idled),
dropdown with click-away and Escape, click = mark read + `navigate(url)`;
mark-all. Mounted in `Header.jsx` and in `WorkerLayout`, whose header strip
— previously mobile-only — now stays at every width because the bell lives
in it and a worker whose leave was decided finds out from this feed.

**One deviation from §6.18:** the demo drawer's notification half was to be
"replaced". Cutting its opener would have made the entire drawer dead code
while the demo still wants its notice board, so the real bell took the bell
slot and the drawer kept an opener behind a Megaphone button beside it. The
demo keeps running — the standing rule — and nothing renders a fake unread
dot any more.

**Deep links:** `DepartmentHiring.jsx` and worker `Communities.jsx` moved tab
state to `useSearchParams` with validation against the tab list, so
`?tab=departures` and `?tab=applications` — emitted by SQL and the Python
fallback table since `0043` — finally select the tab they name. `setTab`
uses `replace: true` so tab-hopping does not fill the back stack.

**Honest limit:** no migration has ever been applied anywhere (§7.4), so the
click-through was verified by build + code path, not against a live feed.
The first real E2E pass owes this screen a look. Build clean, oxlint 7,
frontend tests exit 0.

### 5.26 Phase 2 Step 6 — the two screens, and the field the PATCH stopped taking

Contracted in §6.19; built with one deviation, named below.

**The name stopped being editable.** `PATCH /service-providers/me` now takes
`UpdateServiceProviderRequest` — the old shape minus `displayName`, which the
strict models turn into a `422` if sent. Registration
(`SaveServiceProviderRequest`) subclasses it and adds the name back, because
the one moment a name is required is the moment there is nothing stored to
keep. `0045` §14 recreates `upsert_service_provider` to coalesce a null name,
which is what made the old always-overwrite behaviour — and therefore the old
always-required field — unnecessary. Spec regenerated; suite 834.

**`EmployeeDetail.jsx`** at `/admin/departments/:departmentId/staff/:staffId`
— the page tiles open and `departure.requested` notifications deep-link to.
Identity card (with *Start a departure* when none is open), windowed weekly
schedule over the Step 4 endpoint, and when a departure is riding along: the
dates, the conflict count phrased as what approval releases, **Check
coverage** (per item: candidate names, or *"No one can take this"* in rose —
a statement, not an error), per-item hand-over with the successor select
lifted from `DepartureCard`, **Approve** in a centred-sheet modal (requested
date pre-selected, *a later date* as the discretion the doc grants, floor
now) and Reject. Roster tiles and `DepartureCard` names link in;
`DepartureCard` gained the dates and lost its disabled-approve gate — the
card approves at the requested date, the page holds the date-picking.

**Worker Settings** at `/worker/settings` — nav entry added. Account card
shows name + email read-only with the reason in one line. The details form
moved from `Profile.jsx` minus the name field; `PushCard` moved too (its own
comment had asked for a settings home since Step 8). The **leave flow** is a
modal — *on a date* (min tomorrow) or *immediately*, plus a reason — and the
engagement cards show the requested/approved date and keep *Stay after all*.
`Profile.jsx` slimmed to the read-only public-profile view with an
*Edit in Settings* link.

**Deviation:** §6.19 kept a leave button on Communities; built as a **link to
Settings** instead. Two modals doing the same write drift, and the doc places
the flow in Settings — the card keeps the status line and the cancel, which
belong beside the community.

| Check | Result |
|---|---|
| `pytest -q` | **834 passed** |
| `export_openapi.py` | regenerated (PATCH schema); 145 paths / 173 ops |
| `ruff` / `npm run build` / `oxlint` / `npm run test` | 153 / clean / 7 / exit 0 |

### 5.27 Phase 2 Step 7 — two people, one thread, and a channel that ends with the job

Contracted in §6.20; built as contracted with one amendment discovered at the
schema: **counterpart names are snapshots on the thread**, not joins.
`profiles` has carried a self-only read policy since `0001`
(`profiles_self`), so a security-invoker view joining it would render every
counterpart as null. The open RPCs snapshot both names — the
`staff_assignments.display_name` trade, cost included: a rename shows the old
name until the pair's next `open_direct_thread` upsert refreshes it (the
`do update` clause exists for exactly that).

**`0046_direct_messages.sql`** (47 statements, pglast-clean): `dm_threads`
with a canonical-order pair check (`a < b` makes (a,b) and (b,a) one value),
one-per-pair-per-community partial unique, **one live thread per work order**
(`where locked_at is null` — a locked thread is history and does not block
the job's next worker); `dm_messages` with a nullable author for system
lines. `dm_pair_allowed` — both active members, and either one runs the
place (admin/manager; the committee IS the admin role) or they share a
department — with `dm_recipients` as the same rule turned into the dock's
"to" list, so directory and write cannot disagree. The **lock**: a trigger
stamps `locked_at` when the work order goes terminal and writes a system
line ("The job ended…"), `post_dm_message` refuses with HB409, the thread
stays readable — the PO's documented-history point, verbatim.
`post_dm_message` notifies the counterpart (`dm.message`) via
`notify_profile` in the same transaction.

**Python:** `message_schemas.py`, `messages_repository.py`,
`messages_service.py` (the one real shaping: counterpart resolution per
caller), `routers/messages.py` — five routes, identity-only guard for the
`conversations.py` reason, mounted in `service_api.py` (ten routers now).
Annotations under a new `NO_STORY["dm"]`; a `messages` tag description added
to `export_openapi.py` (its coverage check refused the tagless tag — working
as designed).

Tests api_226–231: counterpart per caller, subjectless/double-subject opens
422 before any write, community-less direct open 422, the lock's 409
surfaced unchanged, hidden-thread 404 reads no messages, sent message
read back from the view.

| Check | Result |
|---|---|
| `pytest -q` | **840 passed** (834 + 6) |
| `ruff check .` | **153** (one new E501 introduced and removed in-step) |
| `pglast` on `0046` | 47 statements |
| `export_openapi.py` | 149 paths / 178 operations |

### 5.28 Phase 2 Step 8 — one dock, five portals

Contracted in §6.21, built as contracted. `components/chat/ChatDock.jsx` +
`features/messages/messagesApi.js`, mounted once in `App.jsx` beside
`ToastContainer` — outside `<Routes>`, rendered only when a session exists —
so every portal gets it without five layouts learning about chat, which is
how "all of them including the supervisor" costs one mount (a supervisor is
a worker-portal user).

Three views in one 28-rem panel: the mailbox (counterpart name, preview,
lock badge, relative time), **New message** (community select where the
caller has more than one, a "to" filter over `GET /messages/recipients`,
tap-to-open), and the thread (bubbles by `authorProfileId`, **centred system
lines for null authors** — the database explaining a silence — composer
replaced by a lock notice on locked threads). Unread is a last-seen stamp in
`localStorage`, deliberately: a read-receipt model is a schema and a policy,
and a dot that clears on open is what the screen needs.

Cross-tree opening is a window event (`hb:chat-open` via `openChatDock`),
because the dock lives outside the router and its openers are scattered
across portals. First user: `EmployeeDetail.jsx`'s **Message** button, shown
only when the row has a `membershipId` — a roster name with no account has
nobody to deliver to. The dock's community list is derived (default
membership + thread communities + whatever an opener passes) rather than
fetched from any portal-specific API, which keeps the component genuinely
portal-agnostic; the cost is that a brand-new user's compose view needs an
opener or a membership to know a community, and the code says so.

Build clean, oxlint 7, frontend tests exit 0.

### 5.29 Phase 2 Step 9 — the sweep, and the ruling written where readers will find it

Contracted in §6.22, done as contracted. `API.md`: §18.7 rewritten around the
dated model with the overturning note where the old gate's celebration stood
(the decide operation's 409 row loses "items still outstanding"; the direct
remove's gate is named as the survivor); three employee-management reads
documented; **§20 Direct messages** written whole; the settings `PATCH`
narrowed and its no-404 note corrected to the name-shaped 422 `0045` actually
produces. `api_yaml_mapper.md` gained the eight rows and a `messages.py`
section — **`api_map_scan.py --strict` is back at its 19 baseline**. The
submission ERD gained the departure dates, the reworked `dispatch_tasks` and
the two DM tables; the class diagram gained the dates, `DirectMessageThread`
/ `DirectMessage`, `DEPARTURE_REMOVAL` and `DmThreadKind`, and its
`StaffDeparture` note now records the overturned refusal in italics rather
than asserting it (renders still stale-labelled). Migrations README rows for
`0045`/`0046`; `CHANGE_LOG.md` Session 55; `DECISIONS_NEEDED.md` A12 gains
its third visit ("three premises in, the answer has not moved");
`design/SERVICE_OPERATIONS_DESIGN.md` gains §7, the Phase 2 amendment naming
what it overturns.

### 5.30 Phase 2 Step 10 — verification, and Phase 2 closes

Run 2026-08-10, every number against its §6.23 expectation:

| Check | Result | Expectation |
|---|---|---|
| `pytest -q` | **840 passed** | 840 |
| `ruff check .` | **153** | 153 (pre-existing baseline) |
| `export_openapi.py --check` | up to date, **149 paths / 178 operations** | 149/178 |
| `api_map_scan.py --strict` | **19** | 19 (pre-existing baseline) |
| `pglast` `0044` / `0045` / `0046` | **3 / 90 / 47 statements**, all parse | parse clean |
| `npm run build` | **clean** (`✓ built in 376ms`) | clean |
| `npx oxlint` | **7 warnings**, all pre-existing files | 7 |
| `npm run test` | **exit 0** | pass |

Phase 2 is built, tested and documented: dated departures with
release-on-approve, the queue priority, the timekeeper, the employee page,
the notification feed, worker Settings, direct messages, and the chat dock.
The test count travelled 835 → 829 (Step 2's deletion) → 840; the two lint
baselines and the map-scan baseline never moved.

**Still true and still not mine:** no migration has ever been applied
anywhere (§7.4) — `0044`–`0046` join a stack of thirty-three files (27
numbered, 6 timestamped) that have never run,
and every SQL predicate in this phase is unexecuted until they do. The class
diagram's rendered `.svg`/`.png` are stale (tooling not installed — a
download decision). Task #93 — whether the gate/security backend gets its
own frontend step — is a product decision that has now survived two phases
unanswered. The branch is local-only with nothing committed.

### 5.31 Phase 3 Step 1 — the read that two permission models had left out

`0047_security_roster.sql` is sixty lines and one function, and the interesting
part is why it was missing rather than what it does.

**The hole.** `POST /security/shifts` takes a `staffAssignmentId`. The person who
fills that form in is a security *manager* — which, since `D3` split rank from
role, means a `security` membership whose `staff_assignments.rank` is `manager`
or `supervisor`, **not** a `manager` membership. `0040` knew that: its
`gate_admin_community_for` predicate names exactly that population and the shift
write has trusted it since Step 7. But every roster *read* in this API lives
under §18's department-hiring router, whose guard is `require_admin_or_manager`
— the membership role. So the one person the shift form exists for was the one
person who could not fetch the guards to put in it. Nobody noticed for two
phases because **nothing had ever called the shift form**; this is precisely the
class of defect §4.25 warned an unconsumed API hides, surfacing in the first
hour of building its consumer.

`security_roster(p_membership_id)` closes it with the predicate the write
already uses — no new authorization concept, no second rule to disagree with the
first. It is a function rather than a view because the answer depends on who is
asking and a view cannot raise `HB403`.

**One deliberate narrowing, recorded so it does not read as a bug.**
`schedule_security_shift` will roster *any* active staff row in the community —
a name typed into the departments form with no membership behind it is a valid
guard, and that is right for the write. The picker lists only staff of
departments whose `kind = 'security'`, because a shift form offering the
plumbing roster is a form offering a mistake. The write stays permissive; the
suggestion is conservative.

**`AUDIT` — one of my own defects, fixed in passing.** `GET /security/posts`
took `include_inactive` in snake_case while every other query parameter on the
surface is camelCase and `API.md` had promised `includeInactive` since Step 7.
Nothing consumed it, so the alias was added rather than documented as a wart.

| Check | Result |
|---|---|
| `pytest -q` | **843 passed** (840 + three roster cases) |
| `ruff check .` | **153** — baseline unmoved |
| `export_openapi.py --check` | up to date, **150 paths / 179 operations** |
| `api_map_scan.py --strict` | **19** — rose to 21 for the undocumented endpoint, back to baseline once `API.md` §19 and the mapper row landed |
| `pglast` `0047` | parses clean |

No table, no view, no column — the ERD and the class diagram are untouched, and
§19 is twenty operations rather than nineteen.

### 5.32 Phase 3 Steps 2–5 — the gate gets a consumer, and it finds things

Four steps, and the honest summary is that **building the consumer found three
defects that two phases of building the API had not** — which is precisely what
§4.25 said would happen and the argument on which the PO funded this work.

**What shipped.** `features/security/securityApi.js` and a `download()` sibling
to `api()` (the CSV export is the first non-JSON response this client has ever
met); seven shared components; five guard screens; four manager screens; the
offline module; `/admin/security/incidents`. Both demo dashboards deleted — 1646
lines of dummy data over zustand, replaced by nine route-per-file screens.

**The three defects, in the order they surfaced:**

1. **The roster hole** (§5.31) — found in the first hour, building the shift
   form.
2. **`undefined • undefined`.** `Header.jsx` and `SecurityLayout.jsx` both read
   `currentUser.departmentName` and `.staffRole`, and `applicationUser()` has
   never set either field. Every gate user has been shown those two literal
   words since the screens shipped. The same root cause is why
   `SecurityManagerDashboard` was *permanently* stuck on its "department
   unavailable" card — not sometimes, always. Neither field belongs in a
   session: a guard's post is a property of their shift, and now comes from the
   API.
3. **"End Shift & Logout" ended no shift.** It called `logout()`. Ending a shift
   is now a real `PATCH /security/shifts/{id}` with `{status}` alone — the one
   mutation on this surface a plain guard may make on their own row — and the
   button is plain *Logout*.

**Two more found by the smoke pass**, which is worth recording because both were
in code I had just written and neither would have failed a build:

* The rejected-entry panel said *"admitted here at 02:41 as not_found"* —
  telling a guard they admitted somebody they had turned away. Now *"scanned
  here… decided offline as…"*.
* A provisional verdict card outlived the sync that settled it, so the screen
  showed *"the server has not seen it yet"* underneath a banner saying the
  server had just refused it. Two contradictory sentences, and the stale one was
  the reassuring one. The card now clears when an outcome arrives.

**How they were found without a database.** There is no live backend and the
portal is auth-gated, so a temporary harness (`smoke.html` + `smokeEntry.jsx`,
both deleted afterwards) mounted the nine screens against a stubbed `fetch` with
fixtures shaped like the documented responses, plus a toggle that made every
call 403. That proved: the screens render real response shapes; the
`community_role_required` card appears instead of a raw error; the guard picker
consumes `0047`; the overdue-returnable highlight fires; and the whole offline
path works — banner, local SHA-256 verdict, provisional label, queued entry in
`localStorage` with its UUID, auto-sync on the `online` event, and a rejected
entry surviving with the server's own words. **This is not a substitute for an
E2E pass against a real database** (§7.4) — the fixtures are my reading of the
API, and if that reading is wrong the harness agrees with me.

### 5.33 Phase 3 Step 6 — close-out

`CHANGE_LOG` Session 57; `API.md` §16.5 and §19 both flip `US-3.5` to **served**
with the old paragraphs struck rather than deleted; new
`docs/design/SECURITY_PORTAL_DESIGN.md` records the route map, the three
notification URLs that are routing contracts, and the offline threat reasoning.
Task #93 closes with the ruling on record.

| Check | Result | Baseline |
|---|---|---|
| `pytest -q` | **843 passed** | 840 + three roster cases |
| `ruff check .` | **153** | 153, unmoved |
| `export_openapi.py --check` | up to date, **150 paths / 179 operations** | was 149/178 |
| `api_map_scan.py --strict` | **19** | 19, unmoved |
| `pglast` `0047` | parses clean | — |
| `npm run build` | **clean** | clean |
| `npm run test` | **3 suites pass** (client, download, offlineGate) | was 1 |
| `npx oxlint` | **7** | 7, unmoved |

**Still true and still not mine:** no migration has ever been applied anywhere
(§7.4) — `0047` joins thirty-four files that have never run. The branch is
local-only with nothing committed.

### 5.34 The coherence sweep — seven stale summaries over inputs that were correct

PO asked for a sweep across the whole surface: *"check if everything fits in…
then check if yaml files are updated for the apis and the user stories are
mapped too."* Both of those hold. `export_openapi.py --check` reports the spec
up to date at 150 paths / 179 operations, and `api_map_scan.py --strict` reports
19 — the same nineteen inherited findings, with **all 24 stories agreeing across
`USER_STORIES.md`, `API.md` §16 and `api_annotations.py`**, which is the check
that would fire if a story's verdict were mapped in one place and not another.

**What the sweep found is a class, not a list.** Seven numbers were wrong, and
every one of them was a **hand-derived summary of inputs that were themselves
correct and machine-checked**:

| Where | Said | Actually |
|---|---|---|
| `API.md` banner, line 7 | 163 operations, 138 paths | **179**, **150** |
| `API.md` §16.2 coverage table | 8 / 9 / 7, security at 0 served | **15 / 6 / 3**, security at 5 |
| `API.md` §16.6 headline | 90 of 163 unmapped | **106 of 179** |
| `API.md` §16.6 table | rows summing to 74 | four families missing entirely |
| `api_yaml_mapper.md` header | 99 operations, 686 tests, @ `98d557a` | **179, 843**, this branch |
| `api_yaml_mapper.md` §6.2 | 20 findings | **19** |
| this file, §0 | `0034`–`0043`, 170 ops, 835 tests | `0034`–`0047`, **179**, **843** |

**The lesson is precise and worth not losing.** `api_map_scan.py` compares each
story's verdict across three files and has done since 2026-08-08; it never
looked at §16.2, because §16.2 does not *state* a verdict — it adds them up. The
scanner checks agreement, not arithmetic. So in the one document where every
contentful claim is machine-checked, the summary line stayed wrong for a day,
and the summary line is what a reader in a hurry reads first.

**The fix is structural where it could be.** §16.6's table was rebuilt so that
each row *is* one `x-no-user-story` group in the generated spec — same grouping,
same counts, same rationales — and `api_yaml_mapper.md` §6.3 now carries the
one-line recount that produces the headline. A family that splits or merges in
`api_annotations.py` now surfaces as a row that no longer matches, rather than as
a total that quietly stops adding up. The other five were prose and were simply
corrected in place, with what they replaced left visible.

**Three smaller things, all doc-side:** `docs/design/README.md` pointed the story
matrix at `API.md` **§15**, which has been *"Not yet implemented"* since the
resident backend renumbered the sections behind it, and still described two
design documents and predicted a third "if the gate ever gets an owner" — it has
five and the gate got one. `AUTH_AND_SESSION_DESIGN.md` §5.2 cites
`SecurityDashboard.jsx`, which §5.32 deleted; kept with a note, per that folder's
convention that a stale citation is a signal rather than a link to tidy away.

**Two findings raised and deliberately not acted on:**

1. ~~**`api_yaml_mapper.md`'s `API.md:NNNN` line references have drifted broadly** —
   the roster row points at `:5987` for a heading now at `:6008`, and spot checks
   elsewhere are off by ~70 lines, because API.md has grown above them. They are
   an aid, not a contract; the `operationId` in the same row is the mapping that
   actually works, and §1 says so. Fixing 179 of them by hand would go stale
   again on the next edit. If it is worth fixing it is worth generating, and that
   is a decision, not a chore.~~ **The PO took the decision the same day — §5.35.**
2. **Two orphan frontend files** — `features/amenities/components/AmenityTabPlaceholder.jsx`
   and `pages/Signup/SignupPage.jsx` — are imported by nothing. Both are
   teammates', both pre-date this branch, and the standing rule is that others'
   code is not touched outside issue-fixing mode.

**Nothing in application code changed.** Every baseline is where §5.33 left it:
843 tests, ruff 153, spec up to date, map-scan 19, oxlint 7, build and three
frontend suites green. `CHANGE_LOG` Session 58 records the same as `AUDIT`.
*(Map-scan is **20** as of §5.35, later the same day — a false negative in the
scanner, not a new gap.)*

### 5.35 §3 of the mapper becomes generated, and catches the scanner

PO: *"regenerate the mapping and everything else to match the current api
state."* §5.34 had raised the drifted `API.md:NNNN` references and declined to
fix them by hand — *"if it is worth fixing it is worth generating"* — so this is
that decision taken.

**`backend/scripts/regen_mapper.py`** rewrites all 179 rows of §3 from the live
app and the generated spec: route, `handler :line`, `operationId`, success
schema. **166 of the 179 rows changed, and every single change was a line number
or a handler position.** Not one route, `operationId` or schema was wrong. That
distribution *is* the finding: the file's contents had been maintained faithfully
endpoint by endpoint while its coordinates rotted underneath, because `API.md`
grows above a heading and everything below it moves.

**The split it keeps is the point.** It generates what can be derived and
preserves what cannot — which `API.md` section covers an operation is an
editorial call (`mention only — § 3.4 Password recovery` is somebody choosing a
paragraph), so the label is kept verbatim and only its line re-resolved; and
`**bold**` is kept, because `**200 free-form object**` means "§5 defect" and the
unbolded form does not. When a heading a cell points at no longer exists it drops
the number and keeps the label, rather than repointing at whatever is nearest —
a missing reference is a finding, a confidently wrong one is a trap.

**Doing it mechanically caught a bug in my own scanner.**
`GET /communities/search` had been marked `**missing**` in §3 while
`api_map_scan.py` reported it documented. **The hand-written row was right.** The
scan asked whether a path appeared anywhere in `API.md` as a bare substring, and
§18 documents `GET /worker/communities/search` — a *different* endpoint that
happens to end the same way. A genuinely undocumented operation had been
reporting clean for as long as the check existed. Fixed with a left-boundary
anchor; **the operation-side baseline moves 19 → 20.** That is a defect
surfacing, not a regression, and it overturns a line I wrote in §5.34 that
listed this endpoint as having "since gained coverage" — written by trusting the
scan over the row it disagreed with. Also normalised: a handful of rows quoted
the route in camelCase, against §1's own rule.

| Check | Result |
|---|---|
| `regen_mapper.py --check` | up to date after one run — **idempotent** |
| `api_map_scan.py --strict` | **20** — new baseline, `/communities/search` no longer hiding |
| `pytest -q` | 843 passed |
| `ruff check .` | **153** — the new script lints clean |
| `export_openapi.py --check` | up to date, 150 paths / 179 operations |

**No application code changed** — the two files touched are both scripts of mine.

### 5.36 The compatibility sweep — the call layer is clean and both defects are one layer up

PO: *"can you do a compatability sweep to check that the workflow works from
start to finish. every single component. from auth to resident to admin to all
service people."* Then, on its output: *"lets fix findings 1 and 2 … go into
detail about each and every other finding and store them as separate files."*

**The headline is the negative result.** 124 frontend call sites against 179 live
operations: **zero mismatches** in path or method. Every real defect was in
*reachability* — whether a person can get to a screen, and whether a link leads
anywhere — which is precisely the layer that has no compiler and, until now, no
test.

**Finding 1 — `/security-manager` was reachable by nobody.** §5.2 turned the
portal on; §5.3 narrowed its predicate to *a `manager` membership whose
department is a security department*; and nothing in this product writes a
`manager` membership. `hire_service_applicant` (`0035:918`) is the only minter
and it writes `security` or `worker`. So the portal that Phase 3 Step 5 built
the day before — four pages, `GET /security/roster`, migration `0047` — was dark
on arrival.

The correct predicate had been sitting in `0040:589` since Step 7, with a comment
naming the rule it implements: a security manager is a `security` membership with
`staff_assignments.rank ∈ (manager, supervisor)`, *"D3 made rank and role
separate axes."* `_portal_for` now asks that, so the portal cannot disagree with
the guard that decides the same question — the only two ways it could disagree
being unreachable (what it was) or screens whose writes 403. `/security/*` also
now admits `SecurityManager`; without that, the fix would have started bouncing
newly-senior guards off `/security/shifts`, the target of two notifications.

**What I take from this one.** Three layers were individually correct — route
guard matched label, label came from portal, portal came from a predicate — and
the predicate described a person the database cannot hold. There was no test on
portal derivation at all. `tests/test_session_portal.py` is now the seven cases
that would have caught it, including *which tables are read*, so the roster
lookup cannot quietly start firing for every resident.

**Finding 2 — four notification `url`s landed on the marketing page.**
`SECURITY_PORTAL_DESIGN.md` had already written down the risk in words. `0032`
sent the gate to `/security/visitors` (never existed), `0036` ×3 and `0037` ×2
sent workers to `/worker/jobs/…` (no such route — jobs open in a modal over
`/worker`), and `0043` sent the guard *receiving* a handed-over shift to
`/security-manager/shifts` — a manager's prefix on a guard's notification, and
not a route either.

`tests/test_notification_links.py` replaces the words with a check: it parses
`App.jsx`'s nested `<Route>` tree, resolves `AUTH_ROUTES`, and asserts all 53
`url` literals across the migrations resolve. Four parametrised cases assert the
matcher still *rejects* the historical values, because a link checker that cannot
fail is worth nothing. Query strings are dropped deliberately — an ignored
parameter is a missing feature, an unroutable path is a broken link.

**The migrations were corrected in place** rather than superseded by an `0048`:
seven literals inside seven functions of ~600 lines, each defined exactly once, so
a fix migration would re-declare all seven and the copies would then be free to
drift. `0022` set that precedent on 2026-08-04; the migrations README now states
the rule *and* its expiry — once anything has been applied anywhere, this stops
being available.

**Findings 3–5 were filed, not fixed**, one file each under `docs/potential
issues/` per the ruling: the resident portal still being a demo (24 endpoints
never called), the 51 operations with no consumer, and §1.3's naming contract
being false for 28 properties on three non-auth surfaces. That last is the one
worth re-reading — **the code is consistent and the document is wrong**, which is
the same failure mode as issue 2 in that directory. The sweep itself ships as
`backend/scripts/frontend_api_sweep.py` so those files' *How to confirm* step is a
command rather than a claim, and it declares its one blind spot rather than
letting it inflate the unreached list.

| Check | Result | Baseline |
|---|---|---|
| `pytest -q` | **856 passed** | 843 + 7 portal + 6 link |
| `ruff check .` | **153** | 153, unmoved |
| `npx oxlint` | **7** | 7, unmoved |
| `export_openapi.py --check` | up to date, 150 paths / 179 operations | unmoved |
| `regen_mapper.py --check` | up to date | unmoved |
| `api_map_scan.py --strict` | **20** | 20, unmoved |
| `pglast` `0032`/`0036`/`0037`/`0043` | all parse clean | — |
| `npm run build` / `npm run test` | clean / 3 suites pass | unmoved |

**Still true:** no migration has ever been applied anywhere, so this sweep is
static analysis throughout. It proves the client calls a route that exists and
that a link names a route that is mounted — not that either returns what the
screen reads.

### 5.37 The parameter, not just the path — `?shift=` is honoured

PO: *"fix the gap about the shifts screen. plan and execute."* The gap is the one
§5.36 declared on itself: `0043`'s `security_shift.assigned` was corrected to
`/security/shifts?shift=<id>` and `Shifts` never read `shift`, so the guard
arrived at a fortnight of roster rows with nothing marking the one they had been
told about.

**This is the same defect as the wrong path, one step later.** The link works, so
nothing reports it — not the console, not the API log, not the suite. A user who
taps *"A shift was handed to you"* and lands on a list they must now search by eye
has not been served by the notification.

**The half that made it more than a highlight.** The screen queries a fixed ±7-day
window, and a handover is driven by `0045`'s *scheduled* departure, whose date can
be weeks out — so the linked shift is routinely not in the list to highlight.
Widening the window is worse than useless: `list_shifts` caps at 200 rows ordered
by `starts_at`, so a wider range on a multi-post gate can truncate away the very
row asked for. `GET /security/shifts` therefore takes a **`shiftId` filter**: one
id, one row, no window. The screen runs it only when the fortnight did not already
contain the shift, and pins the answer above the roster saying so.

**A filter, deliberately, and not `GET /security/shifts/{id}`.** The worker
precedent that shape would copy (`GET /worker/jobs/{id}`) exists because it
returns a *richer* model — the resident's name, flat and the complaint in full.
There is no richer shift model; a second path would serve the same `SecurityShift`
and cost an operation, moving the `179 operations / 150 paths` counts in five
documents for nothing. A filter beside the `postId` filter already there is the
honest expression of *the same list, narrowed to one*. An unknown id answers
`200 []` and not `404`, so the read cannot be used to test whether a shift exists
in a community the caller cannot see.

**The blind spot is now an inventory.** §5.36 dropped query strings before
matching and said why. That was right for the *path* check and wrong as a stopping
point: ten notification links carry a parameter and, before this change, six of
the screens they land on ignored it. `test_notification_links.py` now resolves each
route to the component `App.jsx` mounts and asserts the ignoring set **by
equality** against `IGNORED_QUERY_PARAMETERS`. Equality rather than a subset, so it
cannot decay into an allow-list nobody prunes — a screen that starts honouring its
parameter has to leave the list, and one that stops has to join it in a diff
somebody reviews.

The five that remain are not mine to fix and each names its owner in the constant's
comment: `/resident/complaints` and `/admin/complaints` (issue 09 and the
complaint-engine handoff), `/admin/departments?job=` (issue 10 — there is no
supervisor triage screen at all, so there is no parameter to read yet),
`/admin/amenities?booking=`, and `/worker/messages?conversation=`.

> **Wrong about the last one — corrected in §5.38.** `/worker/messages` is this
> workstream's screen, from Phase 2 Step 8. Four remain, not five.

| Check | Result | Baseline |
|---|---|---|
| `pytest -q` | **860 passed** | 856 + 2 shift filter + 2 parameter inventory |
| `ruff check .` | **153** | 153, unmoved |
| `npx oxlint` | **7** | 7, unmoved |
| `export_openapi.py --check` | up to date, 150 paths / 179 operations | **unmoved — the point of the filter** |
| `regen_mapper.py --check` | up to date | regenerated, 21 rows differed (line numbers) |
| `api_map_scan.py --strict` | **20** | 20, unmoved |
| `npm run build` / `npm run test` | clean / 3 suites pass | unmoved |

**Still true, unchanged:** no migration has been applied anywhere. The new test
proves `Shifts.jsx` reads the parameter the migration writes. It does not prove
the row comes back.

### 5.38 The four that are not ours, and everything nothing reaches

PO: *"are the 5 issues you identified documented? if not document them in potential
issues. fix all other issues that we have identified and after that do a full sweep
for dead or stale stuff."*

**They were not documented.** They were in a test constant, which keeps a list
honest but tells nobody outside the suite what an entry costs a user or who can fix
it. `docs/potential issues/12-notification-parameters-no-screen-reads.md` now gives
each pair its emitting migration lines, its emission count, the screen, the owner
and what a fix would be — not batched, because the four need four different
answers. `/resident/complaints?complaint=` is **eleven of the twenty-three open
emissions** and the least fixable of them: the screen reads a zustand demo store,
so honouring the parameter would highlight a seeded row unrelated to the complaint.
`/admin/departments?job=` has nothing to fix in isolation — there is no supervisor
triage screen, so the parameter has no reader rather than the wrong one.

**One of the five was ours, and §5.37 said otherwise.** `0041:611` notifies the
provider at `/worker/messages?conversation=<id>` and the screen held the open
thread in `useState`, which cannot be linked to. Moved to `useSearchParams`,
mirroring the admin twin that got it right the day it was written. Opening a thread
is a real history entry on purpose: on the phone this screen is built for, the
hardware back button then closes the thread rather than leaving the portal. An
**error branch** came with it — the id can now arrive from a link, and a closed or
foreign thread previously rendered as a blank body under a real header, which reads
as *no messages* rather than as an error.

**`backend/scripts/dead_code_sweep.py`** asks four questions nothing here asked:
frontend modules nothing imports, frontend exports nothing outside the file
mentions, backend module-level names occurring exactly once, and relative Markdown
links in `docs/` resolving to nothing. Two dead-code sweeps had been done by hand;
this is the same work, repeatable, with its blind spots in the docstring rather
than in someone's head.

Ours, deleted: `security_service.export_datasets()` (no caller — `export_csv`
consults `_DATASETS` directly), `vocabulary.js`'s `SHIFT_STATUSES` and
`startOfToday()`, and the unnecessary `export` on `offlineGate.js`'s storage keys.
Not ours, filed as issue 13: three backend names with zero references, two orphan
modules, eight unused exports — **all three of `phone.js`'s, the shape of a module
left behind by the phone/OTP design** — and `graphify-out/`, 57 tracked files and
2.6 MB of tool output nothing refers to. `require_active_role` is flagged for a
second look rather than a delete, because issue 2 kept `Role` in `roles.py` on the
grounds that this file imports it.

Stale, corrected: issue 4 said the migration directory held 22 files (`0001`–`0032`)
and it holds **37** — every one still unapplied, so the finding did not change, only
its size. Four dangling links, all to files deleted in the change that made the
document true; the two agenda items keep their text and gain dated notes, one
**resolved** and one **overtaken but not resolved**, because the question item 8
asks is still open even though the second code path is gone.

| Check | Result | Baseline |
|---|---|---|
| `pytest -q` | **860 passed** | unmoved — the inventory asserts four instead of five |
| `ruff check .` | **153** | 153, unmoved (the new script lints clean) |
| `npx oxlint` | **7** | 7, unmoved |
| `export_openapi.py --check` | up to date, 150 paths / 179 operations | unmoved |
| `regen_mapper.py --check` | up to date | — |
| `api_map_scan.py --strict` | **20** | 20, unmoved |
| `dead_code_sweep.py` | 0 dangling links, nothing of ours | new |
| `npm run build` / `npm run test` | clean / 3 suites pass | unmoved |

**The honest limit is the same one.** Every fix here is verified statically. No
migration has been applied anywhere, so the parameter tests prove the screens read
what the migrations write, not that the rows come back.

---

## 6. Work in flight, written before it is built

### 6.0 ~~The four §8 defects~~ — done, §5.8
### 6.1–6.3 ~~Step 2~~ — done, §5.9 and §5.10

### 6.5 ~~Step 4~~ — done, §5.12. Kept below as written, with its three amendments (§4.11–§4.13) applied

`0036_work_orders.sql`, then `work_orders.py` and `resident_scheduling.py`. The
plan's verification is *"B2 answered; supervisor triage — the overlap constraint
rejects a double-booking."*

**What Step 4 is not.** It creates **no `dispatch_tasks` table and no timers.**
The plan's description of triage says a work order "enqueues a `resident_timeout`
task 24 h out"; that table and the engine that drains it are Step 5, and building
half of them here would leave rows nothing reads. Step 4 stops at the state
machine. Every transition the engine will later make automatically is reachable
by hand first, which is also how it gets tested.

**The two dead baseline tables are extended, not replaced** (plan D5, un-parking
`CONFLICT_RESOLUTIONS` R16). `work_orders` has six columns today and needs
twelve; `work_order_assignments` has four and needs eleven. Additive `alter`s,
exactly as `0019` extended `departments`.

- `work_orders` gains `department_id`, `supervisor_membership_id`, `skill_id`,
  `scheduled_start_at`, `scheduled_end_at`, `subject_kind`, `location_text`,
  `latitude`, `longitude`, `failed_attempt_count`, `resident_deadline_at`.
  Status becomes
  `draft | awaiting_resident | offered | scheduled | in_progress | completed | failed | cancelled`.
- `work_order_assignments` gains `status`, `offered_at`, `responded_at`,
  `decline_reason`, `is_auto_assigned`, `scheduled_start_at`,
  `scheduled_end_at`.

**The one constraint the whole step exists to carry:**

```sql
exclude using gist (
  staff_assignment_id with =,
  tstzrange(scheduled_start_at, scheduled_end_at, '[)') with &&
) where (status = 'accepted' and scheduled_start_at is not null)
```

Already drawn in `docs/erd/homebandhu.dbml:614` and never built. `btree_gist` is
settled (§7.1) and this is the same construct `amenity_bookings` has carried
since the baseline — **the same problem gets the same solution rather than a new
one** (plan F5). The partial predicate matters: an *offered* assignment must be
allowed to overlap, because two workers can be asked and only one can accept.

**No proposed-slots column and no slot-options table.** A supervisor proposes by
writing `scheduled_start_at`/`scheduled_end_at` with status `awaiting_resident`;
the resident confirms and it becomes `offered`; a different time is a reschedule,
which is a `PATCH` the supervisor already has. One slot, no `jsonb` list, no
table holding two rows that are read once and discarded. If it later turns out
residents must choose between alternatives, that is a table then — and it will be
a table with a reason.

**`complaint_events` carries the lifecycle** (plan D6), and this is cheaper than
the plan assumed: `complaint_events.event_type` is `text` with **no CHECK
constraint** (`0001:70`), so `job_scheduled`, `job_offered`, `job_accepted`,
`job_declined`, `job_started`, `job_failed` and `job_completed` need no migration
at all — only `_EVENT_LABELS` and `_event_message` in
`resident_complaints_service.py` extended, where the existing nine live. A
parallel `work_order_events` table would need its own view, renderer and RLS, and
would split one complaint's story across two timelines.

**`worker_availability_rules` and `worker_unavailability` are activated** by
adding a nullable `service_provider_id` beside the existing
`staff_assignment_id`, plus a check that exactly one is set — the
`num_nonnulls(...) = 1` shape `0038` used. A self-registered provider's leave is
global across every community they serve; a roster name with no account can still
have per-department hours.

**RLS.** Read policy on both work-order tables; **no insert, update or delete
policy anywhere**, the posture of `0031`, `0034`, `0035` and `0038`. Every write
is a definer RPC that checks its own authorization.

**Routers.** `work_orders.py` — `POST /complaints/{id}/work-orders` (the
supervisor triage fork: omitting a schedule leaves the complaint in conversation
via `complaint_comments`, supplying one creates the work order),
`GET`/`PATCH /work-orders/{id}`, `POST /work-orders/{id}/assign`,
`/reschedule`, `/cancel`, `GET /departments/{id}/work-orders`.
`resident_scheduling.py` — `GET /complaints/{id}/schedule-request` and
`POST /complaints/{id}/schedule`. The resident may confirm and may decline; the
**reschedule after assignment is the supervisor's alone**, which is the one
asymmetry in this step worth stating in `API.md`.

**Tests and documentation.** `tests/api/test_work_orders.py` and
`test_resident_scheduling.py` from `api_160`; `OPERATIONS` rows; two `_TAGS`
entries; regenerated spec; an `API.md` §18 subsection; two mapper tables; the
ERD; `api_map_scan.py --strict` back to 19 findings.

### 6.4 ~~Step 3~~ — done, §5.11. Kept below as written, with its two amendments in place

`0038_conversations.sql`, then `conversations.py`. The plan's verification is
**RLS denies a non-participant**, and that is the only hard part: everything else
here is a table with a body column.

**The migration.**

- `conversations(id, community_id, department_id, service_provider_id,
  created_at, last_message_at)` with `unique (department_id,
  service_provider_id)`. **One thread per pair**, so there is no thread-creation
  step and no duplicate threads — the unique constraint is the whole concurrency
  story, and two managers opening the chat at once is an upsert rather than a
  race.
- `conversation_messages(id, conversation_id, author_membership_id,
  author_provider_id, body, created_at)` with `length(btrim(body)) between 1 and
  4000`. Two nullable author columns rather than one, because **an invited
  provider may hold no membership in this community** — the same fact that makes
  invitations unnotifiable (§5.9). A check requires exactly one of them.
- **No `conversation_participants` table.** Participation is derivable — the
  department's managers and supervisors, plus that provider — and deriving it is
  exactly what the RLS policy computes. A table would be a second copy of a fact
  the policy already has to establish, free to drift from it.
- **No read receipts.** Nothing in the requirement or the stories asks for them,
  and an unread count added later is one lateral join on `created_at`.
- ~~A trigger keeps `last_message_at` current.~~ **Amended before building.**
  `last_message_at` is stamped by the one RPC that inserts a message, because
  there is no second writer and cannot be one: like `0031`, `0034` and `0035`,
  this file declares **read policies only**, so an insert that did not come
  through `post_conversation_message` has no path to the table. A trigger would
  be a guard against a writer the RLS posture makes impossible, and it is twelve
  lines to the RPC's one.

**The router.** ~~Three routes.~~ **Amended before building: four.** `GET
/conversations` (mine, both roles), `GET /conversations/{id}` with its messages,
`POST /conversations/{id}/messages` — and `POST /conversations`, which the
written-down list omitted. Nothing else creates a thread: an id is required to
post, so with three routes the first message could never be sent. It takes
`(departmentId, serviceProviderId)` and is an upsert, which is exactly what "one
thread per pair, and the unique constraint is the whole concurrency story"
means in practice — two managers opening the chat at once get the same row.

The guard is neither of the two used so far — **participant**, which is a
property of the row rather than of the caller's membership. That means the
authorization lives in the policy and the router declares identity only, the
`worker_communities.py` posture rather than the `department_hiring.py` one.

**Who is a participant, narrowed from §6.4's first draft.** That draft said "the
department's managers and supervisors, plus that provider". It is
`can_manage_department(department_id)` plus that provider — so admins and
managers, **not** supervisors. This is the *hiring* conversation; a supervisor's
conversation is with a complainant about a job, and that is `complaint_comments`
and Step 4. Reusing the function every other hiring route already guards with
also means there is one definition of "may act for this department" rather than
two that can drift.

**No notification on a new message, deliberately.** Same wall as §5.9:
`notifications.recipient_membership_id` is `not null`, and the provider a
manager most needs to reach — an invited one, not yet hired — holds no
membership in that community. A notification path that works for half the
threads is worse than an honest one that says the thread list is the delivery
mechanism. It becomes free the moment Step 6 gives the worker portal an SSE
subscription.

The supervisor ↔ complainant conversation is **not** this. It reuses
`complaint_comments` unchanged, per the PO's answer during planning.

**Tests and documentation.** `tests/api/test_conversations.py`, `OPERATIONS`
rows, regenerated spec, an `API.md` §18 subsection, a mapper table, and
`api_map_scan.py --strict` back to 19 findings.

### 6.6 ~~Step 5~~ — done, §5.13. Kept below as written, and it needed no amendments

**What it is.** Step 4 built every transition and no timers. Step 5 supplies the
thing that makes them happen unattended: due times in a table, a claim that two
processes can race safely, and four RPCs that Postgres executes. Python owns
*when*; Postgres owns *what*, because **F4** stands — there is still no
notification API in Python and every notification must be written inside the
feature transaction.

**Zero new endpoints.** This step adds nothing to `OPERATIONS`, nothing to
`openapi.yaml` and nothing to `api_yaml_mapper.md`. It is the first step of the
twelve with no API surface at all, which is worth stating up front so the
verification numbers below reading *unchanged* is a pass and not a miss.

#### The one decision that reverses a precedent: at-**least**-once

`app/core/push.py` is the model for this file and says so in print:

> **The hub may drop. The sender may not duplicate.**

It claims by marking `push_sent_at` *before* the send, so a crash mid-flight
loses a buzz rather than repeating one. That bias is correct for something that
vibrates a phone at 3am and **wrong here**. A dropped `resident_timeout` is a
complaint that sits in `awaiting_resident` forever with nobody coming — the exact
silence this feature exists to end.

So Step 5 claims with a **lease** rather than a tombstone: `claimed_at` is set on
claim and the reclaim window is five minutes, so a task whose process died is
picked up by the next one. Which means a task can fire twice, which means **every
firing RPC must be idempotent** — and each is, in the same way: it re-reads the
work order, checks the status it expects, and returns without writing if the
world has already moved on. That check is not defensive padding; it is what makes
the lease safe, and the migration header will say so.

The claim itself is `claim_push_batch` with the nouns changed, including
`for update skip locked` — the plan's *"two dispatchers claim disjoint sets"*.

#### A trigger, not five rewritten functions

The plan says the state-changing RPCs enqueue tasks. Doing that literally means
`create or replace`-ing five functions out of `0036` — roughly five hundred lines
copied to add two lines each, and a sixth write path in Step 6 that forgets.

Instead: **one `after insert or update` trigger on `work_orders`** that reads the
new status and keeps `dispatch_tasks` in agreement with it.

| Status after the write | What the trigger does |
|---|---|
| `awaiting_resident` | enqueue `resident_timeout` at `resident_deadline_at` |
| `offered`, priority `high` | enqueue `auto_assign` at `now()` — the urgent path |
| `offered`, otherwise | enqueue `ping` at `now()` |
| anything else | complete every open task on the job |

This is smaller, it cannot be forgotten by a future writer, and it puts the rule
in one readable place. It is also the house pattern already: `0030`'s
`notifications_sse_event` is a trigger for the same reason — **F3** exists
because somebody made that call once already.

It also deletes the plan's separate "urgent complaints bypass the offer" path.
There is no bypass; there is one row in the table above.

#### `dispatch_candidates` — the sweep, and what it will not pretend to know

A set-returning function over one work order. Filters, in order of how much they
cut:

1. an **active roster row** in the job's department, with a `membership_id` — a
   name typed onto a roster with no account cannot be pinged, so it cannot be a
   candidate;
2. if that row links a `service_provider`, the provider is `active` and
   `is_available` — the dashboard's offline toggle, honoured here;
3. no `worker_unavailability` row covering the slot, keyed either way (`0036` §3
   made that column pair legal);
4. if the subject has any `worker_availability_rules` at all, the slot falls
   inside one — *no rules means always available*, which is the only reading that
   does not make a brand-new worker invisible;
5. no `accepted` assignment overlapping the slot. The exclusion constraint
   already refuses this on write; the sweep checks it so the engine does not
   offer a job that cannot be accepted;
6. the provider holds `work_orders.skill_id`, when the job names one.

Ordered by `has_adjacent_job desc, open_jobs asc, distance_km asc`. **The
plan's *"within 1 km of the adjacent job"* becomes *"has another job in this
community that day"***, and that is a downgrade made on purpose: inside one
apartment complex every job is a two-minute walk, no work order carries usable
coordinates, and a distance computed from the *community's* centroid for two jobs
in the same community is the same number twice. Cross-community distance is real
and is still used — it is the third sort key, via `haversine_km` or PostGIS
exactly as `0034` §5 does it.

#### Four kinds, three functions

`dispatch_tasks_kind_check` declares `ping | auto_assign | resident_timeout |
failed_visit_escalation`. Only the first three get an RPC.

`failed_visit_escalation` fires off `work_orders.status = 'failed'`, which
**nothing can write until Step 6** builds the worker portal. Declaring the kind
now and the function later is the same posture `0036` took with `in_progress`,
`completed` and `failed`: put the vocabulary in the CHECK so the later step needs
no migration, and do not write a function with no caller. Ponytail's ladder,
applied to SQL.

- `dispatch_ping_candidates` — offer to the top few, one `work_order_assignments`
  row each at `status = 'offered'`, `notify_member` each, and **enqueue
  `auto_assign` thirty minutes out**. That is the escalation chain: ask, wait,
  decide. If somebody accepts first, the status moves to `scheduled` and the
  trigger cancels the pending `auto_assign` — no second mechanism.
- `dispatch_auto_assign` — take the top candidate, write an `accepted`
  assignment, move the job to `scheduled`, notify the worker and the resident.
  Identical in effect to the supervisor pressing *assign*, which is why §4.12 was
  worth insisting on: the manual lever came first and this is the same lever.
- `dispatch_resident_timeout` — the resident never answered. Move
  `awaiting_resident` → `offered` and tell them it is going ahead. **Not
  auto-resolve.** The plan's risk 3 flagged closing a complaint the resident never
  saw as needing a product decision; this proceeds with the visit instead, which
  needs no such decision and is the behaviour the PO's document actually asks for.

Every one of them writes a `complaint_events` row, so the resident timeline keeps
telling the whole story — **D6**, and `_EVENT_LABELS` already learned the five
words in Step 4.

#### What has no candidate

A sweep that returns nothing is the normal case for a community that has hired
nobody, and it must not look like a failure. `dispatch_ping_candidates` with an
empty set notifies the **supervisor** — *"nobody in this department is free for
that slot"* — completes the task, and enqueues nothing. A retry loop against an
empty roster is a busy loop.

#### Files

| File | What |
|---|---|
| `backend/supabase/migrations/0037_dispatch_engine.sql` | new — the table, the trigger, the sweep, three RPCs, RLS |
| `backend/app/repositories/dispatch_repository.py` | new — `claim_batch`, `fire`, `complete`, `fail`; service client only |
| `backend/app/core/dispatcher.py` | new — `Dispatcher`, mirroring `PushSender` |
| `backend/app/main.py` | edited — two lines in `_lifespan` |
| `backend/tests/test_dispatcher.py` | new — modelled on `test_push_sender.py` |

`dispatch_tasks` gets **RLS enabled with no policy at all**, following
`push_subscriptions` (`0030`): it is machine bookkeeping, no client has any
reason to read it, and the dispatcher runs on the service client which bypasses
RLS. Nothing is granted to `authenticated`; `claim_dispatch_batch` and the three
firing RPCs are granted to `service_role` alone.

#### Verification

`pytest`, `ruff` at 153, `pglast` on `0037` — and `export_openapi.py --check`
plus `api_map_scan.py --strict` **unchanged**, per the no-endpoints note above.

### 6.7 ~~Step 6~~ — done, §5.14. Kept below as written, and it needed no amendments

**What it is.** Every state in `work_orders_status_check` past `scheduled` is
unreachable today: `in_progress`, `completed` and `failed` are declared and
nothing writes them. Step 6 is the person who writes them. It is also the first
step whose caller is *the worker*, which changes one thing structurally and is
the reason the guard question below gets a whole subsection.

Fourteen operations across two routers, one migration, and one amendment to
`0037` that finally gives `failed_visit_escalation` a body.

#### `0039_worker_actions.sql`, and the renumber it forces

The plan reserves `0039` for security operations. Step 6 comes first and needs a
migration of its own — there are no worker-side write functions anywhere in
`0034`–`0037`, because until now there was no worker holding an account to call
one. So **`0039` is worker actions and security operations becomes `0040`.**
Recorded in §4.16 rather than left as a surprise for whoever opens Step 7.

Eight functions and three views. The functions:

| Function | What it settles |
|---|---|
| `accept_work_order_offer` | the offer becomes the booking; every other offer on that job is withdrawn; the job goes `scheduled` |
| `decline_work_order_offer` | this worker's offer alone is declined; the job is untouched |
| `start_work_order` | `scheduled` → `in_progress` |
| `complete_work_order` | `in_progress` → `completed`; the assignment closes with it |
| `report_work_order_failure` | → `failed`, `failed_attempt_count + 1` |
| `set_worker_unavailability` / `delete_worker_unavailability` | the dashboard's "mark slots unavailable" |
| `set_worker_availability_rules` | the working-week editor, replaced whole |

Three `security_invoker` views — `my_worker_job`, `my_worker_unavailability`,
`my_worker_availability_rule` — each filtered inside SQL to the caller. That is
what makes the routers thin: **no endpoint here takes a worker id, a provider id
or a community id**, so there is no id in a request that could widen what comes
back, and the repository is ordinary PostgREST rather than an RPC per read.

**`accept` is where the interesting rule lives.** Two workers tapping *accept*
on the same offer in the same second are the double-booking this feature has
been building toward, and neither the check inside the function nor
`work_order_assignments_no_overlap` alone is the whole answer: the function
takes `for update` on the work order first, so the second caller queues, re-reads
a job that is now `scheduled`, and is told *somebody has already taken this job*
— a sentence, rather than a `23P01` about an exclusion constraint.

#### The guard: identity only, and `worker_deps.py` is **not** written

§4.4 deferred `require_worker` and `get_service_provider` to this step. Building
Step 6 is what shows the first of them should not be built at all.

`require_membership_role("worker", "security")` checks the role on
`MembershipSet.default` — **one community's** membership. This surface is the one
place in the API that is deliberately cross-community: a plumber hired by three
societies and living in a fourth has a default membership of `resident`, and that
guard would 403 them out of their own job list. Widening it to "any membership
with role worker or security" fixes that case and still refuses a department
manager who is also on a roster and has been offered a job — a narrower hole, in
the same wall.

The rule the guard is reaching for is *does this caller hold this assignment*,
which is not a fact about roles at all. It is already stated, once, in
`is_own_staff_assignment` (`0036` §4) — used by the three views and by every
function above. So the routers here are **authenticated-only**, exactly like
`service_providers.py` and `worker_communities.py`, and the reasoning §4.4 wrote
down survives intact: a registered provider hired nowhere must reach
`GET /worker/snapshot`, because the empty snapshot *is* the "find work" screen.

`get_service_provider` goes the same way for the same reason it was deferred: the
views and the RPCs resolve the provider from `auth.uid()` themselves, and a
dependency that re-read the row a moment earlier would add a round trip per
request and a second home for the "are you registered" rule. **No new module.**

#### `failed_visit_escalation` gets a handler, in `0037` rather than here

Step 5 declared the kind in the CHECK and left it unimplemented because nothing
could write `status = 'failed'`. `report_work_order_failure` is that writer, so
the handler lands now — and it belongs beside its three siblings in `0037`, not
in `0039`, because "what the engine does" living in two files is how the next
person misses one. Nothing has been applied anywhere (§7.4), so editing `0037` in
place is free.

Three edits there:

1. `dispatch_failed_visit_escalation(uuid)` — fires two hours after a failed
   visit. **Its idempotency check is not the status**, which is the subtlety: a
   supervisor responding to a failed visit raises a *new* work order (D5), so the
   failed one stays `failed` forever and a status check would escalate every time.
   It checks instead for a **newer work order on the same complaint** — if one
   exists, a human already dealt with it.
2. `sync_dispatch_tasks` learns a `failed` branch, so the enqueue is the trigger's
   like every other one and `report_work_order_failure` never names the queue.
3. `fire_dispatch_task` gains the fourth `case` arm. Its `else` branch stops
   being reachable by any declared kind, which is the point.

#### One defect found while reading, fixed in the same pass

`dispatch_candidates` does not exclude a worker who has **declined** this job. A
decline is followed thirty minutes later by `dispatch_auto_assign`, which picks
the best candidate — and today that can be the person who just said no, who then
finds the job assigned to them anyway. One `not exists` on a `declined` row for
this work order. §4.17.

#### The endpoints

| Route | |
|---|---|
| `GET /worker/snapshot` | the whole dashboard in one call |
| `GET /worker/jobs` | mine, filterable by status and date range |
| `GET /worker/jobs/{id}` | one job with the complaint behind it |
| `POST /worker/jobs/{id}/accept` · `/decline` · `/start` · `/complete` · `/unable` | the five verbs |
| `GET /worker/calendar` | jobs **and** leave in one time-ordered list |
| `GET`/`POST`/`DELETE /worker/unavailability` | mark slots unavailable |
| `GET`/`PUT /worker/availability-rules` | the working week |

`GET /worker/availability-rules` is not in the plan's list and is added: a `PUT`
of a whole set with no way to read the current one is an editor that opens blank
and silently erases whatever the person set last week.

**The calendar is a merge, not a query.** Two reads and a sort in Python, because
the two sources are already views with their own filters and a SQL union would be
a third place that has to agree with both. Colour is not in the response at all —
D15 derives it from the community id on the client.

**`unreadMessages` is not in the snapshot**, although the plan lists it. §5.11
shipped conversations with no read receipts, deliberately, so there is nothing to
count; inventing a count here would mean inventing the receipts under it. The
snapshot carries `unreadNotifications` instead, counted across *all* the caller's
memberships — the one place the `MembershipSet` seam pays off visibly.

#### Files

| File | What |
|---|---|
| `backend/supabase/migrations/0039_worker_actions.sql` | new — three views, eight functions, grants |
| `backend/supabase/migrations/0037_dispatch_engine.sql` | edited — the escalation handler, the trigger branch, the `case` arm, the decline filter |
| `backend/app/domain/worker_schemas.py` | new — `WorkerJob`, `WorkerJobDetail`, `WorkerSnapshot`, the calendar and availability shapes |
| `backend/app/repositories/worker_repository.py` | new — three view reads, eight RPCs |
| `backend/app/services/worker_service.py` | new — vocabulary, the calendar merge, the snapshot assembly |
| `backend/app/api/v1/routers/worker_jobs.py` · `worker_schedule.py` | new |
| `backend/app/api/v1/service_api.py` | edited — two more routers |
| `backend/app/repositories/notifications_repository.py` | edited — an unread count over several memberships |
| `backend/tests/api/test_worker_jobs.py` · `test_worker_schedule.py` | new |

#### Verification

`pytest`, `ruff` at 153, `pglast` on `0039` and re-run on `0037`, and — unlike
Step 5 — `export_openapi.py --check` and `api_map_scan.py --strict` **must move**:
130 operations becomes 144, and every one needs an `OPERATIONS` row, an `API.md`
section and an `api_yaml_mapper.md` entry or the export raises `SystemExit` in
one direction or the other.

### 6.8 ~~Step 7~~ — done, §5.15. Kept below as written, with its two amendments (§4.18) applied

**What it is.** The third department kind finally gets its own work. Hiring,
availability, the calendar, blacklisting and messaging are `security`'s already —
D11 reused every one of them verbatim — but a guard's *work* is not a job
dispatched to an address, so none of `0036`–`0039` describes it. Five tables, one
reconcile log, one router, and the four stories `US-3.3`–`US-3.6` that have said
**Backend: None** since they were written.

The migration is **`0040`, not `0039`** — Step 6 took that number (§4.16).

#### The guard is the opposite of Step 6's, and that is the point

Step 6's surface is deliberately cross-community, so it has no role guard at all.
This one is the mirror image: **a gate belongs to one society.** A register entry,
a shift, a post and an incident are all facts about one community, the caller's
community is their default membership, and `is_community_security(community_id)`
already exists (`0032`:239) and is exactly the predicate every read policy wants.

So Step 7 goes back to the house shape — `require_membership_role` at router
level, `is_community_security(...) or is_community_admin(...)` in RLS — and
**no route takes a community id**, for the reason `ADMIN_DASHBOARD_DESIGN.md` §10
gives: a community id in a request body is a tenancy hole with a plausible
excuse.

The role list is `security | admin | manager`, and the third is not padding: a
security *manager* holds a `security` membership with `rank = 'manager'` (D3 —
rank and role are separate axes), while a facilities `manager` may legitimately
need the tanker log. `is_community_security` covers only `role = 'security'`, so
the policies pair it with `is_community_admin` exactly as `0032` does.

#### The tables

1. **`security_posts`** — the gate, the lobby, the basement ramp. Named,
   optionally located, deactivatable rather than deletable.
2. **`security_shifts`** — `work_order_assignments` with the nouns changed, and
   §0 was right to say read `0036` §2 first: same GiST exclusion over
   `staff_assignment_id` and `tstzrange(starts_at, ends_at, '[)')`, same
   `btree_gist` dependency, same reason. **The partial predicate is where the two
   differ, and it has to.** `work_order_assignments` constrains only `accepted`
   rows because several workers are offered one slot and one takes it. Nobody
   offers a shift to five guards, so there is no equivalent — the predicate is
   `status <> 'cancelled'`, which also stops a new shift being written over a
   completed one.
3. **`material_movements`** — `US-3.3`. Direction, description, quantity, and the
   returnable trio. Two CHECKs the story implies and the plan did not name: a
   return date on a non-returnable item is a contradiction, and so is a return.
4. **`water_tanker_logs`** — `US-3.4`. Arrival, departure, supplier, volume.
5. **`security_incidents`** — the frontend's own form, which already exists and
   already writes to nothing: `SecurityDashboard.jsx:166` collects a type, a
   location and details, and `logIncident` appends a *string* to an activity
   feed. That is `DECISIONS_NEEDED` B2's defect one surface over.
6. **`offline_reconcile_log`** — see below.

**Two tables and not one typed table** (plan D12) stands, and the reading that
confirmed it: `is_returnable`/`expected_return_at`/`returned_at` and
`tanker_number`/`volume_litres`/`supplier_name` share nothing, are named by two
separate stories and produce two separate reports. One table with a `kind` and a
`details jsonb` would be null-heavy in both halves and would move validation out
of the schema and into Python.

#### `US-3.5` needs a thing that does not exist, and that is the finding

The plan gives Step 7 `GET /security/offline-bundle` and
`POST /security/offline-reconcile` — **an offline fallback with nothing to fall
back from.** `USER_STORIES.md` US-3.1 says it in print: *"nothing verifies a code
at the gate"*. `0032` mints `code_hash` and `pass_hash` and stores them; no RPC,
no endpoint and no policy ever reads one back to answer *may this person in*.

So Step 7 builds the online verification first and the offline pair on top of it,
and both call the same function. Recorded as §4.18 rather than absorbed silently,
because it changes what the step closes: US-3.1 moves from **Partial** as well.

**And the bundle is not signed**, which departs from plan D13. A signature the
device verifies against a key the device holds is theatre — the same attacker who
can edit `localStorage` can disable the check beside it, because both are
JavaScript on their machine. What is actually load-bearing is that **every
offline admission is provisional until reconciled**: the server re-verifies each
one against the live pass and records its own verdict, so a fabricated entry
becomes a flagged row rather than an admitted guest. The bundle gets an expiry and
a community scope and no signature. Stated in the migration header, because the
absence of a thing the plan named needs to read as decided.

Honest about what the bundle *is*: a list of live `code_hash` values for one
community, and a six-digit code hashed with SHA-256 is a 10⁶ search space, so the
hashing obscures nothing from anybody holding the file. That is acceptable and it
is not a shrug — the gate device is *already* authorised to admit exactly those
visitors, so the bundle discloses to the guard what the guard's job is. It is not
acceptable to send it anywhere else, which is why it is security-and-admin only
and time-boxed.

#### Idempotency, in two places for two reasons

- Each register table carries a nullable `source_client_id` with a partial unique
  index. A queued material entry replayed twice is one row.
- `offline_reconcile_log` is for the gate admissions, whose replay outcome is a
  **verdict** rather than a row. There is nothing in `visitor_requests` a unique
  index could hang off, and the answer *this code was not valid at that time* has
  to be recorded somewhere or the reconcile silently swallows it.

#### The endpoints — nineteen

| Route | |
|---|---|
| `GET`/`POST /security/posts` · `PATCH /security/posts/{postId}` | the roster of places |
| `GET`/`POST /security/shifts` · `PATCH /security/shifts/{shiftId}` | who is on the gate, and *End Shift* — which `SecurityLayout.jsx` already offers |
| `GET`/`POST /security/material-movements` · `POST .../{movementId}/return` | US-3.3 |
| `GET`/`POST /security/water-tankers` · `PATCH /security/water-tankers/{logId}` | US-3.4 |
| `GET`/`POST /security/incidents` · `PATCH /security/incidents/{incidentId}` | the form that currently writes a string |
| `POST /security/gate/verify` | US-3.1's missing half, and US-3.5's prerequisite |
| `GET /security/offline-bundle` · `POST /security/offline-reconcile` | US-3.5 |
| `GET /security/exports/{dataset}` | US-3.6 — **one route, five datasets** |

**One export route rather than five.** The datasets differ in their columns and
in nothing else; five routes would be five copies of the same date-range
validation, the same `Content-Disposition` line and the same CSV writer, and the
sixth dataset would arrive as a sixth copy. `dataset` is a path parameter with a
closed vocabulary, so an unknown one is a 422 naming the five rather than an empty
file.

`csv` is in the standard library and the response is a `Response` with
`text/csv`, so nothing is added to `requirements.txt` — ponytail's ladder, and the
rung is *stdlib*.

#### Vocabulary

`security_incidents.category` gets a stored vocabulary and a wire translation in
`app/domain/vocabularies.py`, the seam §5.8 and §4.6 both used: the frontend sends
*"Security concern"* and the column stores `security_concern`. `other` is in the
set on purpose — a closed vocabulary with no escape hatch is a form people work
around by picking the wrong option.

#### Files

| File | What |
|---|---|
| `backend/supabase/migrations/0040_security_operations.sql` | new — six tables, the views, the verify function, the write RPCs, RLS |
| `backend/app/domain/security_schemas.py` | new |
| `backend/app/repositories/security_repository.py` | new |
| `backend/app/services/security_service.py` | new — including the CSV writer |
| `backend/app/api/v1/routers/security_operations.py` | new — nineteen operations |
| `backend/app/api/v1/service_api.py` | edited — the ninth router |
| `backend/app/domain/vocabularies.py` | edited — incident categories |
| `backend/tests/api/test_security_operations.py` | new |

#### Verification

`pytest`, `ruff` at 153, `pglast` on `0040` with its SQL bodies parsed
separately (§5.13's lesson), and both spec checks **must move**: 144 operations
becomes 163, and every one needs an `OPERATIONS` row, an `API.md` section and an
`api_yaml_mapper.md` entry or the export raises `SystemExit` in one direction or
the other.

### 6.9 ~~Step 8~~ — done, §5.16. Kept below as written, with its three amendments (§4.20–§4.22) applied

Written 2026-08-10 before a line of it exists. This is the first step of this
build that touches the frontend, so it is also the first that has to say what
"done" means for a surface with no test runner worth the name: `npm run test` is
**one** node script over the API client, and `npm run lint` is `oxlint`. There
is no component test infrastructure and Step 8 is not the place to introduce
one — the plan's own verification column for this step says *"manual
walkthrough"*.

#### The reading that shaped it, before any of it is built

**A. `ROLE_LABELS` already has `WORKER`.** `lib/auth/authService.js:3` maps
`WORKER → 'Worker'` and `MANAGER → 'Manager'`, and has since long before this
feature. So a hired provider *already* resolves to `currentUser.role ===
'Worker'` — and then both routers send them to `/account`, because neither
`getDashboardRouteForRole` (`routes/authRoutes.js:23`) nor `homeRouteFor`
(`authService.js:78`) has a `worker` branch. The role has existed and led
nowhere.

**B. An unhired provider cannot reach any screen at all, and that is the whole
empty state.** `applicationUser(context)` returns `null` when
`context.membership` is null (`authService.js:67`), `ProtectedRoute` bounces a
null `currentUser` to `/login`, and a service person who has registered but been
hired nowhere holds **no membership**. So the screens that exist to let them
find work are behind a guard that requires them to have already found it.

This is the frontend half of the same problem §4.4 solved on the backend, where
`require_service_provider` was made to depend on `get_current_user` alone rather
than on membership. The frontend answer is the same shape: **the worker portal's
guard reads `sessionContext.identity`, not `currentUser`.** Being signed in is
enough to reach `/worker`; what the portal then shows — register, find a
community, or the dashboard — is decided by `GET /worker/snapshot`, which was
designed to answer exactly this and says so in its own docstring: *"`provider`
being null is the whole empty state."*

That keeps `applicationUser` untouched, which matters because it is
auth-workstream code (§7.3).

**C. There are two functions that route a signed-in user home, in two
vocabularies.** `homeRouteFor` branches on the lowercase membership role;
`getDashboardRouteForRole` branches on the display label. Both need the worker
branch, and adding it twice is the cost of a duplication this step did not
create and will not fix — noted here so Step 9 or the auth owner can collapse
them knowingly.

#### Two places the approved plan is not followed, and why

Both are recorded as §4.20 and §4.21 rather than being done quietly.

**§4.20 — no new zustand slices.** The plan lists
`createServiceProvidersSlice.js`, `createWorkOrdersSlice.js` and
`createConversationsSlice.js` "alongside the existing eleven". The reading says
not to. Every slice in `store/slices/` is **demo state** — `createVisitorsSlice`
mints its own ids with `genId('v')` and computes a security code in the browser
— while every page that talks to the real backend already uses **react-query**:
`PendingRegistrations.jsx`, `Residents.jsx`, `JoinCommunityTab.jsx`.
`QueryClientProvider` is mounted in `main.jsx` and `queryClient.js` is
configured. Three hand-rolled slices carrying loading, error and refetch state
would be fifty lines each reinventing what one `useQuery` line already does, and
would put the worker portal in the demo half of the app rather than the real
half. So: **react-query, and one `workerApi.js` of thin `api()` wrappers**,
matching `registrationApi.js` exactly.

**§4.21 — six routes, not nine pages.** The plan names nine worker pages.
`MyCommunities`, `FindCommunities` and `Applications` are three views of one
question — *where do I work* — and a worker holding a phone at a job site does
not want three sidebar entries for it. They collapse into one `Communities.jsx`
with three panels. `TodaySchedule` is not a page either: it is what
`GET /worker/snapshot` returns, so it **is** the dashboard home. Final nav:
**Dashboard · Calendar · Availability · Communities · Messages · Profile**, plus
`JobDetailModal` which is a modal and never a route.

#### What gets written

| File | Why |
|---|---|
| `frontend/public/sw.js` | new — push, plus a runtime cache so a reload offline still boots |
| `frontend/src/lib/push/pushClient.js` | new — register, subscribe, `POST /push/subscriptions` |
| `frontend/src/lib/communityColor.js` | new — `D15`, derived, no endpoint |
| `frontend/src/features/calendar/useCalendarRange.js` | new — month and week ranges, one hook |
| `frontend/src/features/calendar/CalendarMonth.jsx` | new |
| `frontend/src/features/calendar/CalendarWeek.jsx` | new |
| `frontend/src/features/calendar/CalendarEvent.jsx` | new — one entry, coloured by community |
| `frontend/src/features/worker/workerApi.js` | new — every worker endpoint, thin |
| `frontend/src/layouts/WorkerLayout.jsx` | new — modelled on `SecurityLayout.jsx` |
| `frontend/src/pages/WorkerDashboard/*.jsx` | new — six routes + `JobDetailModal` |
| `frontend/src/routes/authRoutes.js` | edited — `WORKER_DASHBOARD` + the role branch |
| `frontend/src/lib/auth/authService.js` | edited — one line in `homeRouteFor`; **auth-workstream file, flag it** |
| `frontend/src/App.jsx` | edited — the `/worker` subtree and its identity-only guard |
| `frontend/src/main.jsx` | edited — one call to register the service worker |

#### The service worker, kept to what is actually claimed

`US-2.7` needs `push` and `notificationclick`. That is the whole reason the file
has to exist, and `GET /push/vapid-key` already ships the key it needs.

It gets **no precache and no Workbox**. A build-time precache manifest is a
versioning and invalidation problem nobody asked to have, and Vite's hashed
asset names make a hand-written one wrong on the next build. Instead: cache each
successful same-origin `GET` as it happens, and serve from that cache only when
the network fails. About twenty lines, no dependency, and it degrades to *the
app still boots* rather than claiming to be an offline-first application.

One correction to §0 while writing this: §0 item 1 says `US-3.5` "cannot cache
an offline bundle" without a service worker. That is **wrong** — `localStorage`
caches the bundle perfectly well. What the service worker actually buys `US-3.5`
is surviving a *reload* while disconnected. The gate's offline UI itself is not
in this step; it lands with the security screens in Step 9.

#### Verification

`npx oxlint`, `npm run build` (the real check — an unresolved import fails it),
`npm run test`, and the backend suite re-run untouched at **821** to prove no
frontend edit reached across the seam. Manual walkthrough is the plan's own
column and stays the honest answer for the rendering.

---

### 6.10 ~~Step 8b~~ — done, §5.17. Kept below as written, with its two amendments (§4.23, §4.24) applied

Written 2026-08-10, before any code, at the product owner's instruction:
*"you can change the auth bit too. but do document it separately in detail in a
separate file in doc/design. fix the notification issue too. we need to
implement that too."*

Two permissions arrive with that sentence, and both change what §7.3 says.
`app/api/deps.py`, `frontend/src/lib/auth/authService.js` and
`backend/app/services/auth_service.py` stop being *flagged for another owner's
review* and become **this workstream's to change**, on the condition that the
result is written up as a design document rather than as a diff. §7.3 is
rewritten accordingly when this lands.

#### The reading, before the decisions

**R1. The notification substrate is addressed to a membership at every layer,
and a service person may not have one.** `notifications.recipient_membership_id`
is `not null` in the baseline; `notification_overview` inner-joins
`community_memberships`; the read policy is
`is_own_membership(recipient_membership_id)`; `push_subscriptions.membership_id`
is `not null`; `claim_push_batch` returns a membership; `push.py:151` resolves a
recipient's browsers by membership; and `GET /notifications`,
`POST /notifications/{id}/read`, `POST /notifications/read-all`,
`POST /push/subscriptions` and `POST /push/subscriptions/unregister` all depend
on `get_active_membership`, which raises `403 active_membership_required` for a
caller who holds none.

That is one decision, taken once in `0030` and then repeated eleven times. It
was right for the population `0030` was written for — a resident is a
membership — and it is wrong for the population this feature added.

**R2. So the gap §0 has carried since Step 3 is not one missing `perform`.** The
journal has described it as *"`0038` shipped no notification on a new message,
because an invited provider holds no membership to notify"*. Adding the call
without R1's change would write a row addressed to a null membership into a
`not null` column. The honest fix is the substrate, not the call site.

**R3. Three further defects fall out of R1, and two of them are mine.**

- **Step 8's push card does not work for the person it was built for.**
  `Profile.jsx`'s `PushCard` calls `enablePush()`, which posts to
  `POST /push/subscriptions`, which requires an active membership. An unhired
  service provider — the exact caller that screen exists to serve — gets a 403.
  I shipped that on 2026-08-10 and did not notice, because the frontend cannot
  see a guard.
- **A person with two memberships can receive push for only one of them.**
  `push_subscriptions.endpoint` is globally unique *by design*
  (`0030` §6: "the endpoint URL **is** the browser's identity"), and the row
  carries a membership. So the same browser subscribed from a second community
  **moves** the row rather than adding one, and the first community's pushes
  stop. Nothing has ever exercised this because no caller held two memberships
  until this feature; `unread_count_for_memberships` (Step 6) is the marker that
  the multi-community caller had already arrived.
- **`mark_all_notifications_read(p_membership_id)` and the badge count different
  sets.** The router's own docstring says `unread` "counts the entire feed"; the
  RPC clears one membership's rows. For a single-membership resident these are
  the same set, which is why it has never shown.

**R4. `POST /notices` cannot notify from where it stands.**
`notices_repository.insert_notice` is a plain PostgREST insert — deliberately,
and its docstring says why: *"a single-table, single-statement write, so the
transaction PostgREST gives it for free is the whole transaction it needs."*
There is no RPC to add a `perform notify_community_roles` to. But `0030` §5
already established the pattern that makes this free: **a trigger**, so that
"delivery is a property of the system" rather than something each writer
remembers. `notice.published` has had a fallback title in
`notifications_service._FALLBACK_TITLES` since the resident build — the
vocabulary was written and the writer never was.

**R5. `portal` is derived from the presence of a department, not its kind.**
`auth_service.py:282`:

```python
portal = "security-manager" if role == "manager" and membership.get("department_id") else role
```

Every department manager is therefore routed to the security portal — including
the manager of a plumbing department, which is the exact person Step 9's hiring
screens are for. `departments.kind ∈ {service, security}` has existed since
`0019` and answers this; nothing asked it.

**R6. `/security-manager` is unreachable by any real session.** `ProtectedRoute`
guards it with `requiredRole="SecurityManager"` (`App.jsx:303`), and
`applicationUser` can never produce that role: it reads `ROLE_LABELS`, whose
five values are Admin, Manager, Worker, Security and Resident, and puts
`security-manager` in a *separate* `portal` field. So `homeRouteFor` sends the
caller to `/security-manager` on the portal field, `ProtectedRoute` reads the
role field, does not match, and bounces them to
`getDashboardRouteForRole('Security')` = `/security`. Four other files
(`Header.jsx:73`, `Header.jsx:120`, `SecurityLayout.jsx:22`,
`SecurityDashboard.jsx:130`) already branch on `role === 'SecurityManager'` and
are all dead for the same reason. This is what §7.3 predicted in the abstract —
"two functions doing one job in two vocabularies" — showing up as a concrete
dead route.

#### Decisions

**D16. The notification recipient becomes a person; the membership stays as
context.** `notifications` gains `recipient_profile_id`, always populated —
`notify_member` derives it from the membership it is given, so no call site
changes — and `recipient_membership_id` becomes nullable and means *which
community this was about*, which is what `notification_overview.community_id`
and the SSE trigger already use it for.

*Rejected:* a parallel `provider_notifications` table. It would need its own
feed endpoint, its own policy, its own push claim and its own renderer, and the
worker's bell would then have two sources to merge — for a row that differs from
an existing one by which column is null.

*Rejected:* leaving the substrate alone and notifying only the *hired* provider.
That is the case that already works. The unhired provider is the whole point:
they are the one waiting to hear back about an application.

**D17. The read policy becomes `recipient_profile_id = auth.uid()`, and this
overturns a rule `0030` states in print.** That file says: *"`status = 'active'`
matters. Someone who has left the community stops being able to read what was
addressed to them."* Under D16 they keep it. Named here rather than left to be
discovered, per `docs/design/README.md`.

The reason for overturning it: with one membership the two predicates agree, and
with several they do not — a worker removed from one community would silently
lose that community's rows out of a feed that is otherwise theirs, and a badge
would jump downwards with no event to explain it. A notification is a copy of
something the person was already told; retaining their own history is the
ordinary behaviour of every inbox. What ending a membership must stop is *new*
notifications, and `notify_community_roles` already filters on
`status = 'active'` at the point of writing, which is where that rule belongs.

**D18. `push_subscriptions` is keyed on the profile and loses its membership
column — and `register_push_subscription` loses its first argument with it.**
The browser belongs to a person. Once the column is the profile, the argument
can only ever be `auth.uid()`, so passing it in and then checking it with
`is_own_membership` is a parameter that exists to be validated against the
session it came from. Deleting it removes the forgery surface rather than
guarding it — the shape `0030` itself argued for on `notify_member`.

**D19. The conversation notifies both directions, addressed differently.**
Provider → department: `notify_member` to each active membership that
`can_manage_department` would accept, which is admins of the community plus
managers whose membership names that department or names none. Department →
provider: `notify_profile`, because that side may hold no membership at all.
Kind `conversation.message` both ways, `p_exclude_membership`-style
self-exclusion by construction (the author is one side, the recipients the
other).

**D20. The notice notification is a trigger, not a service call.** `0030` §5's
rule, applied a second time: the writer stays a plain insert, and
`after insert on notices when published_at is not null` fans out to
`role = 'resident'`, excluding the author. Adding a draft state later changes
the `when` clause and nothing else.

**D21. `portal` is derived from `departments.kind`.** A manager of a `security`
department gets `security-manager`; a manager of a `service` department gets
`manager`, which routes where every plain manager routes today. This is a
correction, not a new surface: no route is added, and Step 9 decides where a
department manager's home actually is.

**D22. One home-routing function, in `routes/authRoutes.js`.**
`getDashboardRouteForRole` is deleted and `homeRouteFor` moves next to the route
constants it returns — `authRoutes.js` imports nothing, so nothing can cycle.
`applicationUser` starts producing `role: 'SecurityManager'` when the portal
says so, which is what makes R6's four dead branches and one dead route live
without touching any of them.

*Rejected:* keeping both and making them delegate. Two exported names for one
question is the state §7.3 already complained about; the second name would still
be the one somebody imports.

#### What gets written

| File | Change |
|---|---|
| `backend/supabase/migrations/0041_person_notifications.sql` | **new** — D16–D20 |
| `backend/app/repositories/notifications_repository.py` | profile-keyed; `unread_count_for_memberships` **deleted** |
| `backend/app/services/notifications_service.py` | signatures follow |
| `backend/app/api/v1/routers/notifications.py` | `get_active_membership` → `get_current_user` |
| `backend/app/repositories/push_repository.py` | profile-keyed; two RPC signatures shrink |
| `backend/app/services/push_service.py` | signatures follow |
| `backend/app/api/v1/routers/push.py` | `get_active_membership` → `get_current_user` |
| `backend/app/core/push.py` | recipient is a profile |
| `backend/app/services/worker_service.py` (snapshot) | one unread count, not a summed one |
| `backend/app/services/auth_service.py` | D21 |
| `frontend/src/routes/authRoutes.js` | D22 — the one resolver |
| `frontend/src/lib/auth/authService.js` | D22 — `applicationUser` learns the portal |
| six frontend call sites | import the one name |
| `docs/design/AUTH_AND_SESSION_DESIGN.md` | **new** — the document the PO asked for |

#### Verification

The backend suite, `ruff` at 153, `export_openapi.py --check`,
`api_map_scan.py --strict` at 19, `pglast` on `0041`, and on the frontend
`npm run build` / `npx oxlint` / `npm run test`. `US-2.4` moves to **served** in
all three places the gate checks, or it moves in none.

---

### 6.11 ~~Step 9~~ — done, §5.18. Kept below as written, with its three amendments (§4.25–§4.27) applied

Written 2026-08-10, before any code.

#### The reading, before the decisions

**R1. The admin dashboard is the demo half, and Step 8 established which half a
screen belongs to.** `Departments.jsx` (1095 lines), `DepartmentDetail.jsx` (713)
and `CreateDepartment.jsx` (222) all read and write the zustand slices through
`useApp()`. `PendingRegistrations.jsx` and `Residents.jsx` are react-query over
the real API. Both patterns are current and the choice per screen is deliberate,
not a migration half-done — `appStore.js` says browser state is *"a render cache
only"*.

The eleven hiring operations have **no demo equivalent at all**: there is no
`serviceProviders` slice, no mock candidate, nothing to convert. So the hiring
screens are new react-query surfaces beside the demo, exactly as Step 8's portal
was, and nothing is migrated.

**R2. `POST /departments/{id}/applications/{applicationId}/decide` is the only
place `rank`, `jobTitle` and `shift` are ever set, and it takes all three.** On
an *application* the terms are null until the manager names them at the moment
they say yes; on an *invitation* they are already in the row and `decide` cannot
change them, so a provider accepting cannot promote themselves. That asymmetry
decides the shape of the accept control: it is a small form on an application and
a bare button on an invitation.

**R3. `HireableProvider.hasOpenApplication` exists so the candidate list can
offer the right verb.** The unique index `service_applications_one_open` refuses
a second pending row for the same *(department, provider)* pair, so a screen that
always offered "Invite" would produce a 409 on exactly the candidates a manager
is most likely to click twice.

**R4. `STAFF_ROLES` is three lists and none of them is `rank`.**

| File | Values |
|---|---|
| `Departments.jsx:33` | Technician · Security Guard · Gate Officer · Supervisor · Manager · Coordinator |
| `CreateDepartment.jsx:6` | Technician · Manager · Supervisor |
| `SecurityManagerDashboard.jsx:22` | Security Guard · Gate Officer · Supervisor |

Read against `D3`, all three are **`job_title` values with two `rank` values mixed
in**. `Manager` and `Supervisor` are ranks; `Technician`, `Security Guard`, `Gate
Officer` and `Coordinator` are trades. That is why the lists disagree: each screen
was picking the subset it needed out of a set that answers two questions at once.

**R5. `SHIFTS` in `SecurityManagerDashboard.jsx:23` is missing `Full Day`,**
which `D4` settled and `0035` writes into the check constraint. A screen that
cannot express a value the database accepts has a missing option rather than a
wrong one, which is the kind of gap nobody reports.

**R6. `assignTechnician` (`DepartmentDetail.jsx:184`) writes a formatted string
into demo state and reads it back by splitting on `' - '`.**
`DECISIONS_NEEDED` B2 names the consequence: *"We store a text label; 'complaints
assigned to me' stays impossible."*

Two things are true about it, and the plan's verification column
(*"`assignTechnician` no longer writes a string"*) names only the second:

- **B2 is already closed where it matters.** `work_order_assignments` holds a
  `staff_assignment_id` foreign key and `POST /work-orders/{id}/assign` is the
  real write. A worker's job list is `GET /worker/jobs`, which exists and has a
  consumer.
- **The demo still stores a label**, so a staff member renamed after an
  assignment silently orphans it.

#### Decisions

**D23. Two new react-query screens on the admin routes, and nothing migrated.**
`AdminDashboard/DepartmentHiring.jsx` at
`/admin/departments/:departmentId/hiring` and `AdminDashboard/Messages.jsx` at
`/admin/messages`. The first is three tabs over one department — Applications ·
Candidates · Roster — following Step 8's `Communities.jsx`, which collapsed three
of the plan's pages into one route for the same reason: they are three views of
one question.

*Rejected:* rebuilding `DepartmentDetail.jsx` over the real API so hiring sits
inside it. That is the whole admin dashboard's migration off the demo store,
which is a project rather than a step, and it would put a real roster beside a
mock complaint list on one screen — the worst of both halves.

**D24. `/admin/messages` is the URL `0041` already points at.** The notification
`post_conversation_message` writes for the department side carries
`url: '/admin/messages?conversation=<id>'`. That was written yesterday against a
screen that did not exist; this is the step that makes the link land. The query
parameter selects a thread, so a notification click opens the right one.

**D25. One `STAFF_ROLES` becomes three exported constants, because it was always
more than one question.** `frontend/src/lib/staffVocabulary.js`:

- `STAFF_RANKS` — `manager` · `supervisor` · `member`, the stored vocabulary from
  `D3`, with display labels beside them because `member` is not a word to show a
  user.
- `JOB_TITLES` — the trades, as a **suggestion list on a free-text field** rather
  than a closed select. `job_title` is `text` in `0019` with no check constraint,
  and a closed list on an open column is a screen inventing a rule the database
  does not have. A society with a gardener should not need a migration.
- `SHIFTS` — `D4`'s five values, `Full Day` included.

**D26. `assignTechnician` stores an id, and the label is derived at render.** The
smallest change that makes the demo's shape honest, and it is worth being precise
about what it does not do: it does not wire the admin dashboard to
`POST /work-orders/{id}/assign`. B2 is closed on the backend; this stops the
frontend contradicting it.

#### The gate screens are not in this step, and that is a gap in the approved plan

§0 of this journal has said since Step 8 that Step 9 includes "the gate screens".
That was mine and it was wrong: the approved plan's build order has no row for
them. Step 7 built `0040` and `security_operations.py` and closed `US-3.3`–`US-3.6`
on the API; Step 8 was the worker portal; Step 9 is *"manager hiring, messages,
vocabulary reconciliation"*. Nothing schedules a consumer for the gate.

That is the §4.22 shape again — an endpoint set with no screen is an endpoint set
whose defects nobody finds — and it is raised as §4.25 rather than quietly
absorbed into this step, because adding a second large surface here would leave
neither of them reviewable.

#### What gets written

| File | Change |
|---|---|
| `frontend/src/features/hiring/hiringApi.js` | **new** — thin `api()` wrappers, shaped like `workerApi.js` |
| `frontend/src/lib/staffVocabulary.js` | **new** — `D25` |
| `frontend/src/pages/AdminDashboard/DepartmentHiring.jsx` | **new** — three tabs |
| `frontend/src/pages/AdminDashboard/Messages.jsx` | **new** — `D24` |
| `frontend/src/App.jsx` | two routes |
| `frontend/src/layouts/AdminLayout.jsx` | one nav entry |
| `Departments.jsx`, `CreateDepartment.jsx`, `SecurityManagerDashboard.jsx` | import the shared vocabulary; `rank` and `job_title` become separate controls |
| `DepartmentDetail.jsx` | `D26`, plus a link into the hiring screen |

#### Verification

`npm run build` (an unresolved import fails it), `npx oxlint` at 7 pre-existing
warnings, `npm run test`, and the backend suite re-run at **824** to prove no
frontend edit crossed the seam. The demo must still run: creating a department,
adding staff and assigning a complaint all still work against the zustand store.

---

### 6.12 ~~Step 9b~~ — done, §5.19. Kept below as written, with its two amendments (§4.28, §4.29) applied

*Written before any of it is built, per §1. PO instruction, 2026-08-10:*

> *"leaving a community requires manager permission. this would mean that there
> would be a process that requires the jobs be reassigned to others and only when
> everything has been handed over to other workers can the leave be approved.
> this would notify the supervisors too. the reassignment should follow the same
> assignment logic as the auto assignment we talked about earlier (the previous
> job and next job location and time). this reassignment has to take place before
> the person is removed the same applies for all servicemen regardless of
> department."*

#### The one idea

Today a departure is a single statement. `remove_department_member` (`0035` §7)
sets the roster row inactive, ends the membership, sends one notification, and
returns. It says nothing at all about the **work that person was holding**, and
the work does not go away: a `work_order_assignments` row with `status =
'accepted'` survives untouched, still pointing at the slot, still counted by
`dispatch_candidates` as somebody's load, still rendering on the resident's
complaint as *someone is coming*. Nobody is coming. The membership that would
have carried the reminder has just ended.

So the fix is not a confirmation dialog on the remove button. It is to make
**departure a state a person is in** rather than an event that happens to them,
so that between *I want to leave* and *you have left* there is an interval in
which two things are true: the engine stops giving them new work, and the work
they already hold is moved to somebody else, one item at a time, by a human who
can see the list.

#### What counts as outstanding, and why the obvious filter is wrong

For a roster row, two kinds:

- `work_order_assignments` where `status in ('offered','accepted')` and the work
  order is not `completed`, `cancelled` or `failed`;
- `security_shifts` where `status in ('scheduled','active')`.

**Neither is filtered on `starts_at > now()`,** and that is deliberate. A
scheduled job whose slot was yesterday and which nobody closed is exactly the
thing a departing worker leaves behind; filtering it out would let the departure
approve while a stale job still sits in their name, which is the failure this
whole step exists to prevent. The count answers *what does this person still
hold*, not *what is still in the future*. A manager who thinks a stale item
should simply die has `cancel_work_order` and `update_security_shift` already —
the handover panel links to those rather than growing its own escape hatch.

#### Statuses: four, and no `handover`

`pending | approved | rejected | cancelled`. There is no separate `handover`
state, because "handover in progress" is *`pending` with a non-zero outstanding
count* — and a status that is derivable from a count is a status that can
disagree with the count. One open request per roster row, enforced by a partial
unique index on `status = 'pending'`, which is the whole concurrency story the
same way `service_applications_one_open` was in `0035`.

#### The freeze is the part that is easy to miss

`request_staff_departure` must make the person invisible to the dispatch engine
immediately, not on approval. Without it the handover is a treadmill: a
supervisor reassigns three jobs, and while they are doing it `dispatch_ping` and
`dispatch_auto_assign` hand the same person two more, because nothing in
`dispatch_candidates` (`0037` §4) knows they are leaving. So:

- `dispatch_candidates` gains one `not exists` against a pending departure;
- `assign_work_order` (`0036` §6) refuses to book somebody who is leaving —
  otherwise a supervisor undoes the handover by hand, one row at a time;
- `schedule_security_shift` (`0040` §9) refuses for the same reason.

#### Reassignment reuses the ranking, and the writer

The PO asked for *"the same assignment logic as the auto assignment"*. That is
`dispatch_candidates`, which already orders by *already has a job in this
community that day* → *fewest open jobs* → *nearest* (`0037` §4, and the header
there argues why adjacency is expressed as same-community-same-day rather than
as a kilometre). `reassign_departure_item` with no explicit successor takes
`dispatch_candidates(work_order_id, 1)` — and because the freeze is already in
place, the departing person cannot be their own successor and no third rule is
needed to say so.

It then calls **`assign_work_order` itself** rather than writing the assignment
inline. That function already withdraws the incumbent row, inserts the new
`accepted` one, writes the `job_assigned` complaint event, notifies the new
assignee and notifies the resident. Reimplementing that beside it would be a
second definition of *book this person on this job* which would drift from the
first. Ponytail's ladder stops at "already in this codebase" here.

Security shifts have no sweep, so they get one: `security_shift_candidates`,
same shape and same exclusions (roster, active, available, no unavailability
covering the window, no overlapping shift, no pending departure), ordered by
**fewest shifts in the surrounding week, then nearest**. Adjacency does not
transfer — a guard's shifts are a rota, not a route — and the header will say
so rather than copying a sort key that does not mean anything here. The shift
write is inline: `update_security_shift` cannot change `staff_assignment_id`,
and widening it would mix the gate manager's authorisation path with the
department manager's.

#### When nobody is free

`reassign_departure_item` raises `HB409` naming the item. It does **not** cancel
the job, and it does not approve the departure anyway. The three real options —
pick somebody explicitly, reschedule, cancel — are all endpoints that already
exist, and a manager staring at one unmovable job is the correct place for this
to stop.

#### Notifying the supervisors

`notify_community_staff` (`0031` §3) is community-wide admin and manager;
`notify_community_roles` (`0032`) is by membership role. Neither reaches a
*supervisor*, because a supervisor is not a role — it is `rank = 'supervisor'`
on a roster row in one department (D3). So one new helper,
`notify_department_leadership(department_id, kind, payload, exclude)`: every
active roster row in that department with `rank in ('manager','supervisor')` and
a membership, plus every community admin, deduplicated by membership id. Five
kinds, each with a `title` and a `url` — `departure.requested`,
`departure.approved`, `departure.rejected`, `departure.cancelled`,
`security_shift.assigned`.

#### Two doors, and why not one

`remove_department_member` keeps its signature and its place, and gains a
refusal: `HB409` when the roster row holds anything outstanding. It stays the
one-click answer for the ordinary case — a name typed into the department form
by mistake, somebody who has never been dispatched — and requiring a four-step
handover for that would be ceremony. Everyone else goes through
`request_staff_departure`, which a manager may open on somebody else's behalf
(`initiated_by = 'manager'`) exactly as a worker opens their own.

The safety net is that **no path removes somebody holding work**: the refusal
lives in the function every removal path already funnels through, including
`blacklist_service_provider`, which loops over rosters calling it.

#### The exception, stated rather than discovered

A **bar is not an orderly departure and must not wait for one.** Somebody barred
for misconduct keeping tomorrow's job until a supervisor finds five successors
is the opposite of what a bar is for. So `blacklist_service_provider` *releases*
rather than hands over: it withdraws their assignments, returns each work order
to `offered` — which re-arms the dispatch ping automatically through
`sync_dispatch_tasks` (`0037` §2), so the engine finds the replacements — and
cancels their future shifts, then tells the department's leadership how many
items it moved. An orderly departure hands over; a bar ejects and the engine
re-dispatches. That asymmetry is the design, not an oversight, and it is written
in the migration header where somebody comparing the two functions will find it.

#### Surface

Seven operations, no new router — the manager's verbs belong beside the hiring
verbs and the worker's beside their engagements:

| Operation | Router | Guard |
|---|---|---|
| `POST /worker/communities/{staffId}/departure` | `worker_communities.py` | provider-self |
| `DELETE /worker/communities/{staffId}/departure` | `worker_communities.py` | provider-self |
| `GET /departments/{id}/departures` | `department_hiring.py` | `admin`\|`manager` |
| `GET /departments/{id}/departures/{departureId}` | `department_hiring.py` | `admin`\|`manager` |
| `POST /departments/{id}/departures` | `department_hiring.py` | `admin`\|`manager` |
| `POST /departments/{id}/departures/{departureId}/reassign` | `department_hiring.py` | `admin`\|`manager` |
| `POST /departments/{id}/departures/{departureId}/decide` | `department_hiring.py` | `admin`\|`manager` |

The worker's own status needs no eighth: `GET /worker/communities` already
returns one row per engagement and gains `departureStatus` there.

#### The read that will otherwise be one field short

Three times in this build a consumer has proved a read stopped one field short
(§4.22, §4.26, and `0042`'s header names the pattern). The roster tab is about
to need *how many things does this person still hold* on every row, to decide
whether to offer **Remove** or **Start handover** — so
`department_staff_overview` is recreated once more with `open_commitment_count`,
before the screen is written rather than after it fails. Noting it here so that
if it turns out to be unnecessary, that is visible too.

#### Frontend

`DepartmentHiring.jsx` gains a fourth tab, **Departures**: the open requests,
each expanding to its outstanding list with a *Reassign* button per item
(auto-pick) and a successor select beside it, and an **Approve** that is disabled
with the count beside it until the count is zero. The roster tab's Remove button
becomes conditional on the same count. `WorkerDashboard/Communities.jsx` gains
*Request to leave* on each roster card, its pending state, and cancel. Existing
design language throughout — `rounded-2xl border border-slate-100 bg-white p-5
shadow-sm` cards, rose for the destructive verb, `lucide-react` icons, the shared
`inputClass`, react-query and not the demo store.

#### Also in this unit

The five hiring notifications §5.18 named and deferred — they render a fallback
title and carry no `url`, so they are not clickable. They are `0035` payloads and
this step is already rewriting two `0035` functions, so they go in the same
migration rather than waiting for a third occasion.

#### Verification

`pytest -q` above the 824 baseline with new cases in `tests/api/` for both
sides and a `tests/test_departure_rules.py` for the outstanding-count and
freeze predicates; `ruff check .` at 153; `export_openapi.py --check`;
`api_map_scan.py --strict` at 19; `pglast` on `0043`; `npm run build`,
`npx oxlint`, `npm run test`.

### 6.13 ~~Step 10~~ — done, §5.20. Kept below as written; its first item was a decision and the decision stood

*Written before any of it is done, per §1.* The plan defines this step as *"docs sweep"* and lists
five things. Four are straightforward; the first turns out to be a decision rather than a chore, and
it is written up here before it is acted on because it overturns something this project committed to
in print.

#### The `§15`–`§19` renumber, and why it is being cancelled

`API.md` §18 carries a note I wrote: the two new content sections sit *after* the three
meta-sections (§15 Not yet implemented, §16 User stories, §17 Changelog) instead of before them, and
*"the renumber is deferred to the documentation sweep at the end of this feature."* This is that
sweep, and the renumber should not happen. Counting the cost is what changed the answer:

| Where | `§15`–`§19` references |
|---|---|
| `API.md` itself | 42 |
| **`CHANGE_LOG.md`** | **49** |
| everything else — 11 files | 51 |

The middle row is the argument. `CHANGE_LOG.md` is a **dated record**: an entry written in Session 30
says *"§16"* because §16 meant *User stories* on that day. A renumber leaves exactly two options for
those 49, and both are worse than the problem:

- **rewrite them** — which makes a historical record say something it did not say, in the one
  document whose whole value is that it did not change afterwards; or
- **leave them** — which makes every pointer in the log silently wrong, and a wrong pointer is worse
  than an odd ordering because a reader believes it.

Against that, the cost of not renumbering is one visible note explaining why two content sections
follow the meta-sections. So the note stops apologising and becomes a **ruling with its reason**,
and this journal entry names what it overturns, per `docs/design/README.md`.

#### The other four

1. **`CONFLICT_RESOLUTIONS.md` R16.** R16 parked twelve orphan baseline tables with
   *"build nothing against them"*. This feature un-parked five of them — `work_orders`,
   `work_order_assignments`, `worker_availability_rules`, `worker_unavailability`, `skills` — and
   superseded two, `staff_skills` (D2) and `vendors` (D1). The amendment has to say which, and which
   of the twelve are still parked, or the next reader cannot tell an un-parked table from an
   overlooked one.
2. **The class diagram.** `homebandhu-domain.puml` predates this feature and has no
   `ServiceProvider`, `ServiceApplication`, `Conversation`, `DispatchTask`, `SecurityShift`,
   `StaffDeparture` or gate register. Its `WorkOrder` is the design ERD's richer version, so the
   classes go in beside it rather than replacing it. **The rendered SVG and PNG cannot be
   regenerated here** — the procedure in that directory's README needs `plantuml.jar` and Graphviz
   `dot`, and neither is installed. The `.puml` is the source of truth and will be correct; the two
   rendered files will be stale, and saying so in the README is the honest outcome rather than
   quietly shipping a diagram that does not match its source.
3. **`USER_STORIES.md` US-3.2's stale pointer.** It says *"see §14"*; §14 has been the resident's
   money and home since the resident backend landed. It means §16.5.
4. **`DECISIONS_NEEDED.md`.** **B2 is answered** — the free-text assignee was the reason
   *"complaints assigned to me"* was impossible, and `work_order_assignments` plus `assigneeStaffId`
   is the answer (§4.27 records the residue: the label is kept beside the id, and why). **A12 is
   revisited** — removal now deactivates a real linked row rather than an unattributable string, and
   `0043` added the condition it happens under. **A22 is partially answered** — a scheduler now
   exists and D8 says what runs it, though the two billing switches it asks about still promise
   machinery this product does not contain.

#### Verification

`pytest -q`, `ruff check .`, `export_openapi.py --check` and `api_map_scan.py --strict` all have to
stay where they are; nothing in this step touches code except comments. The one thing worth checking
afterwards is that no `§` pointer added by this step points at a heading that does not exist.

### 6.14 ~~Phase 2 Step 1~~ — done, §5.21. One of its two "defects" was not one.

---

### 6.15 ~~Phase 2 Step 2~~ — done, §5.22. Two amendments: `Role` is not dead, and fallow never answered.

### 6.16 ~~Phase 2 Step 3~~ — done, §5.23. Built as contracted; two details surfaced while writing it (recorded there).

The PO's rulings (§0) implemented. One migration, then the Python threading.

**The migration, in dependency order:**

1. `staff_departures` + `requested_effective_at` (null = immediate) and
   `effective_at` (stamped at approval).
2. `departure_bars_work(p_staff_id, p_starts_at)` — pending+undated bars all;
   pending+dated bars slots `>= date` **and unscheduled work** (a job with no
   slot can land anywhere); approved-awaiting-removal bars all. Rewired into
   both freeze triggers, `dispatch_candidates` (recreated **from the 0043
   body**) and `security_shift_candidates`.
3. `dispatch_tasks`: `work_order_id` loses NOT NULL; `departure_id` FK added
   with `num_nonnulls = 1`; kind check dropped and re-added with
   `departure_removal`; partial unique `(departure_id, kind)`; **`priority
   smallint not null default 0`**. `claim_dispatch_batch` orders
   `priority desc, due_at`. `enqueue_dispatch_task` gains `p_priority`;
   `enqueue_departure_task` is new; `sync_dispatch_tasks` gives urgent
   auto-assigns priority 2; `fire_dispatch_task` gains the `departure_removal`
   arm → `dispatch_departure_removal` (skip unless still approved and staff
   still active; release remaining at priority 1; remove). `dispatcher.py`
   unchanged — the claim's extra columns ride through the repo untouched.
4. `release_staff_commitments(p_staff_id, p_reason, p_from, p_priority)` —
   windowed (slot `>= p_from`, null slot counts as conflicting; null window =
   everything, which keeps the blacklist path whole).
5. `request_staff_departure` + `p_effective_at` (HB409 if past);
   `decide_staff_departure` + `p_effective_at`: approve resolves the date
   (manager's override wins, floored at now), **deletes the zero-commitment
   HB409** (PO overturned §5.19's rule — the manager decides, the pool
   absorbs), releases from the date, and either removes now or arms the
   timekeeper. `remove_department_member` keeps its gate (direct Remove is
   still refused while work is booked) and now stamps
   `decided_by_membership_id`.
6. Reads: `departure_coverage(p_departure_id)` (per conflicting item, how many
   candidates could take it, top names — "if there are none, it says so");
   `staff_schedule_items(p_staff_id, p_from, p_to)` for the employee page;
   `staff_departure_overview` recreated with the dates and a conflict count.
7. Notification URLs move to the employee page:
   `/admin/departments/{id}/staff/{staffId}?departure={id}`.

**Python:** `StaffDeparture` + `requestedEffectiveAt`/`effectiveAt`/
`conflictCount`; `RequestDepartureRequest.effectiveAt`;
`DecideDepartureRequest.effectiveAt`; new `CoverageItem`, `ScheduleItem`;
repo/service/router threading in `worker_communities.py` and
`department_hiring.py`. Tests: request-with-date, decide-with-date
(immediate and future), decide no longer 409s on open items, coverage op.

Expected: pytest > 829, ruff 153, spec regenerated, pglast clean on `0045`.

### 6.17 ~~Phase 2 Step 4~~ — done, §5.24.

Three reads, no new router — they live in `department_hiring.py` beside the
departures they serve. The doc's ask: employee tiles → a detailed page with
the schedule; the departure notification lands on that page; the manager's
match button.

1. `GET /departments/{department_id}/staff/{staff_id}` →
   `StaffMemberDetail`: the roster row (from `department_staff_overview`, via
   the departments repo the roster tab already reads) plus the open departure
   when there is one. 404 when the row is not in this department — the path's
   department is a scope, not decoration.
2. `GET /departments/{department_id}/staff/{staff_id}/schedule?from&to` →
   `list[ScheduleItem]` over `staff_schedule_items` (service client — the
   guard is the roster read that precedes it, the `get_departure` pattern).
3. `GET /departments/{department_id}/departures/{departure_id}/coverage` →
   `list[CoverageItem]` over `departure_coverage` (service client, same
   order-is-the-authorisation: departure read first with the caller's client).

Schemas: `StaffMemberDetail` = `StaffMember` + `departure: StaffDeparture |
None`. Annotations for three operations, spec regenerated, API.md §18.7 rows
in Step 9's sweep. Tests: detail 404s across departments, schedule window
forwarded, coverage reads departure-first (the api_219/220 shape).

### 6.18 ~~Phase 2 Step 5~~ — done, §5.25. One deviation: the demo drawer kept an opener instead of dying.

### 6.19 ~~Phase 2 Step 6~~ — done, §5.26. One deviation: Communities' leave button became a link to Settings rather than a second modal.

The two screens the doc describes, plus the one backend edit the settings
rule forces.

**Backend first (small):** `PATCH /service-providers/me` stops accepting
`displayName` — the PO's rule is that name and email are not editable in
settings. New `UpdateServiceProviderRequest` without the field;
`upsert_service_provider` learns to coalesce a null `p_display_name` (a
`create or replace` in `0045` — same file, appended section, since nothing
has ever been applied); registration still requires the name.

**Employee page (admin portal).** `EmployeeDetail.jsx` at
`/admin/departments/:departmentId/staff/:staffId`:
- identity card from `GET .../staff/{staffId}` (name, rank, trade, shift,
  phone, provider pill, open-commitment count);
- schedule card, windowed over `GET .../schedule` (this-week default,
  prev/next), items rendered like `DepartureCard`'s list;
- departure panel when one is riding along: dates, reason, conflict count,
  **Check coverage** button (`GET .../coverage`) rendering per-item candidate
  names or *"no one can take this"*, per-item Hand-over + successor select
  (lifted from `DepartureCard`), **Approve** in a centred-sheet modal with a
  date input prefilled from the request, and **Reject** with a note.
- Roster tiles in `DepartmentHiring.jsx` link here; `?departure=` in the URL
  is accepted (the notification deep link) but the panel shows whatever open
  departure the read returns.
- `hiringApi` gains `staffMember`, `staffSchedule`, `coverage`.

**Worker Settings.** `/worker/settings` + nav entry (Profile stays for the
public-profile view; the editing form moves):
- identity card: name + email **read-only**, with one line saying why;
- details form: headline, bio, phone, radius, coordinates, skills — lifted
  from `Profile.jsx`, minus the name field;
- `PushCard` moves here (its own comment asks for this);
- **Leave section**: per active engagement, a proper modal (no more
  `window.prompt`): radio *immediately / on a date* + date input + reason;
  pending shows the requested date and conflict count; approved-with-date
  shows "leaving <date>". `workerApi.requestDeparture` gains the date.

Verify: build, oxlint, frontend tests; backend suite for the PATCH change.

### 6.20 ~~Phase 2 Step 7~~ — done, §5.27. One design amendment: names are snapshots, because `profiles` is self-read-only.

Person-to-person chat, which the conversations schema structurally cannot
express (`conversation_messages_one_author` + a NOT NULL provider
counterparty). New tables, not an extension; the hiring threads stay for
hiring.

**Model.**
- `dm_threads(id, community_id, kind in ('direct','work_order'),
  work_order_id null, participant_a_profile_id, participant_b_profile_id,
  locked_at, last_message_at, created_at)`. Canonical pair order (`a < b`
  check) + partial unique `(community_id, a, b) where kind='direct'` — one
  thread per pair per community, no duplicates, no thread-picker. Partial
  unique `(work_order_id) where kind='work_order'`.
- `dm_messages(id, thread_id, author_profile_id null, body 1..4000,
  created_at)` — a null author is a system line, written only by definer
  functions (the receipt-only case the PO named).
- **The lock**: a trigger on `work_orders` stamps `locked_at` on the job's
  thread when the order goes terminal; `post_dm_message` refuses a locked
  thread with `HB409`. Locked threads stay readable — documented history,
  the PO's audit point — and the serviceman cannot keep talking to the
  resident after the work is done, which is the protection asked for.

**Who may reach whom** (`dm_recipients(p_community_id)`): the caller's
department colleagues (roster rows with memberships), plus the community's
admins and managers — "committee" being `role = 'admin'` per
`USER_IDENTIFICATION.md`. Residents get admins and managers only; their
worker contact is the work-order thread, opened by either participant while
the job is live. `open_direct_thread` validates the pair against the same
rule, so the directory and the write cannot disagree.

**RPCs:** `open_direct_thread(p_community_id, p_recipient_profile_id)` (an
upsert, the `conversations_one_per_pair` precedent),
`open_work_order_thread(p_work_order_id)` (participants = accepted
assignee's profile + complainant's profile; refuses when either is missing),
`post_dm_message(p_thread_id, p_body)` (stamps `last_message_at`; system
lines via a service-only variant later if needed). RLS: read =
participant-by-profile; no write policies.

**Router `messages.py`** — `GET /messages/recipients?communityId=`,
`GET /messages/threads`, `POST /messages/threads` (recipient+community, or
workOrderId), `GET /messages/threads/{id}`, `POST
/messages/threads/{id}/messages`. Views `dm_thread_overview` (counterpart
name resolved per caller in the service — the view carries both names) and
`dm_message_overview`. Identity-only guard like `conversations.py`; the RLS
and RPC checks are the real ones.

**Tests** `tests/api/test_messages.py`: recipients scoped, pair dedupe (the
409-free upsert), locked-thread 409 surfaced, thread read 404 when RLS hides
it, message post shape.

### 6.21 ~~Phase 2 Step 8~~ — done, §5.28.

The PO's mount ruling ("all of them including the supervisor") implemented
as one component in one place: `App.jsx` beside `ToastContainer`, outside
`<Routes>`, rendered only when a session exists — so admin, worker, security,
security-manager and resident all get it without five layouts learning about
chat. A supervisor is a worker-portal user; "including the supervisor" is
already covered by mounting everywhere.

1. **`features/messages/messagesApi.js`** — recipients / threads / thread /
   openThread / send, thin as always.
2. **`components/chat/ChatDock.jsx`** — collapsed: a bubble bottom-right
   (`z-[900]`, under toasts at 9999) with an unread dot when any thread's
   last message is newer than the dock's last-seen stamp (localStorage — a
   read-receipt model is deliberately out of scope). Expanded: a panel with
   the thread list (counterpart name, preview, lock badge), a **New message**
   view whose community selector + recipient list come from
   `GET /messages/recipients`, and a thread view — bubbles by
   `authorProfileId`, centred system lines for null authors, composer
   disabled with a lock notice on locked threads. react-query keys
   `['dm-threads']`, `['dm-thread', id]`, `['dm-recipients', communityId]`,
   30 s refetch on the list while open.
3. **Community picker source** — the session's memberships are not in any
   one API the dock can rely on across portals, so the dock derives the
   community list from the threads it has plus a manual entry point on the
   employee page; the admin side passes community context when opening.
   The employee-card action: `EmployeeDetail.jsx` gains **Message** (visible
   when the row has a `membershipId`), which calls
   `openThread({communityId, recipientProfileId})` — needing the person's
   profile id, which `department_staff_overview` does not carry. **The view
   gains `profile_id` via 0046's already-written pattern?** No — smaller: the
   dock's recipients list for that community already names every staff
   member for a manager, so the employee page opens the dock's New-message
   view pre-filtered. No schema change.

Verify: build, oxlint, frontend tests.

### 6.22 ~~Phase 2 Step 9~~ — done, §5.29.

The endpoint standard applied to eight new operations and one changed one,
plus the artifacts that track the schema.

1. **`API.md`** — §18.7 rewritten for the dates (the overturned refusal named
   per the design README's rule), three employee-management operations added,
   a new **§20 Direct messages** (five operations, the lock's 409, the
   committee-is-admin note), the settings PATCH change in §18.1's route, §18
   header counts updated.
2. **`api_yaml_mapper.md`** — rows for the eight new operations plus a rescan
   note; `api_map_scan.py --strict` back to ≤ 19.
3. **Submission ERD** — `staff_departures` dates, `dispatch_tasks`
   (nullable `work_order_id`, `departure_id`, `priority`, fifth kind),
   `dm_threads` / `dm_messages` with provenance notes.
4. **Class diagram `.puml`** — `StaffDeparture` gains the dates and loses the
   approve-gate note's absolutism; `DirectMessageThread` / `DirectMessage`
   added. Renders stay stale-labelled (tooling still not installed).
5. **`CHANGE_LOG.md`** — Session 55 block, `PO`/`DERIVED`/`AUDIT` attributed.
6. **`DECISIONS_NEEDED.md`** — nothing new opened; note under B2/A12 that the
   departure gate ruling changed on 2026-08-10.
7. **`docs/design/SERVICE_OPERATIONS_DESIGN.md`** — a Phase 2 amendment
   section naming the overturned rule and the new subsystems.

### 6.23 ~~Phase 2 Step 10~~ — done, §5.30. Every number matched its expectation.

### 6.24 Phase 3 — the security-gate frontend (task #93, PO: "build it", 2026-08-11)

Written before it is built. The full plan is
`~/.claude/plans/cozy-stirring-sparrow.md`; this is the contract in brief.

**Why.** §4.25's warning stands unamended: nineteen operations under
`/api/v1/security` and not one frontend call — the fields-missing defect class
that only a consumer surfaces (it happened three times in Phase 1) has had
nowhere to surface. `API.md` §16.5 grades US-3.5 "partial — the server side is
complete; the browser side is not." The demo `SecurityManagerDashboard` is
permanently stuck on its "department unavailable" card because it reads
`currentUser.departmentName`, which `applicationUser()` never sets.

**Six steps, each verified before the next starts:**

1. **`0047_security_roster.sql` + `GET /security/roster`.** One security-definer
   read function authorized entirely by the existing `gate_admin_community_for`;
   returns active staff in `departments.kind = 'security'` — deliberately
   narrower than `schedule_security_shift`, which accepts any active staff row
   (the migration comment says so). Function only: no table, no view, **no ERD
   or class-diagram change**. Plus an `AUDIT` touch-up: `GET /security/posts`
   gains `alias="includeInactive"` — the router's one snake_case query param
   was my oversight, the docs already promise camelCase, and no consumer exists
   yet to break.
2. **Frontend plumbing.** `features/security/securityApi.js` (hiringApi's
   shape), a `download()` sibling to `api()` in `lib/api/client.js` (the CSV
   export is the first non-JSON response the client meets), and seven shared
   components under `features/security/components/`.
3. **Guard portal, phone-first.** Five one-file-per-route pages replacing the
   1070-line demo: GateHome (verify + expected visitors), Registers
   (`?tab=materials|tankers`), Incidents, Shifts, Emergency. `/security/shifts`
   is a **routing contract** — `0040:893` already deep-links `shift.scheduled`
   there. Layout nav rewritten; `Header.jsx`'s always-undefined
   `departmentName`/`staffRole` reads removed.
4. **Offline mode — the US-3.5 browser half.** `features/security/offline/`:
   bundle cached in localStorage (`hb.security.offlineBundle.v1`), local
   SHA-256 verify with **provisional** verdicts (the client cannot know guest
   counts or revocations; reconcile is authoritative and the UI says so),
   scan queue (`hb.security.offlineQueue.v1`, `sourceClientId =
   crypto.randomUUID()`), reconcile on the `online` event + a manual button;
   accepted/replayed entries clear, rejected ones stay visible until
   dismissed. This is the repo's **first deliberate exception** to
   `appStore.js:16` ("localStorage is deliberately never a source of domain
   truth") and the module header must say so.
5. **Manager portal + the admin contract route.** Overview, Roster
   (`?tab=shifts|posts`, guard picker fed by Step 1), ManagerIncidents,
   Exports; gate/registers/emergency shared from the guard folder. And
   `/admin/security/incidents` — `0040:1233` already sends admins there on
   high/critical incidents; the route must exist.
6. **Docs close-out.** CHANGE_LOG session; §16.5 US-3.5 partial→served (done
   in step 4, where the story actually completes); §14 map; design-doc note;
   task #93 closed; full check table (pytest 840+, ruff ≤153, spec check at
   179 ops/150 paths, map-scan ≤19, pglast 0047, build/test/oxlint ≤7).

**Dropped from the demo, on the record:** guard-raised approval requests (no
backend — the gap is documented at `resident_visitor_passes.py:134-140`), the
fake "Society Management Office" number (the real 112/101/108 stay), the
manager's editable staff array + `operatingHours` (hiring lives in the admin
portal's `DepartmentHiring`). The resident-facing visitors slice stays —
resident demo screens still use it.

---

## 7. Open items — not mine to close

### 7.1 ~~PostGIS and `btree_gist` availability is unconfirmed~~ — both closed

Closed 2026-08-09: **the PO confirms PostGIS is enabled on the Supabase
project.** So `0034`'s generated `location extensions.geography(Point, 4326)`
column, its GiST index and `ST_Distance` ordering all stand as written, and the
PostGIS fallback of plan D7 is not taken.

`haversine_km` stays in `0034` anyway. It is nine lines, it costs nothing, and it
is the only way to ask "how far apart are these two points" from a context that
does not want a `geography` — deleting it would be tidying, not simplifying.
Ponytail's *deletion over addition* is about code that has no caller, and this
one is documented as the escape hatch.

**`btree_gist` — closed 2026-08-10, by reading rather than by asking.** It was
carried as an open item on the grounds that the exclusion constraints in Steps 4
and 7 need it independently of PostGIS. They do. But the question was already
answered two thousand lines earlier in the same directory:

- `0001_baseline.sql:7` — `create extension if not exists btree_gist;`
- `0001_baseline.sql:81` — `amenity_bookings` declares
  `exclude using gist (amenity_id with =, tstzrange(starts_at, ends_at, '[)') with &&)`.

The second line is the one that settles it. `amenity_id with =` is a **btree**
operator class inside a **GiST** index, which is the entire purpose of
`btree_gist` and is impossible without it. So the baseline does not merely
install the extension — it *depends* on it, in the first file anyone applies. If
`btree_gist` were unavailable on this project, `0001` would fail on line 7 and
there would be no database to have this conversation about.

**Step 4 therefore adds no new extension requirement.**
`work_order_assignments_no_overlap` is the same construct as a constraint the
baseline already carries, one table over. Nothing to confirm, nothing to run, no
fallback to design.

Worth recording *why this sat open for three steps*: the plan's D7 named
`btree_gist` next to PostGIS in one verification query, and PostGIS genuinely was
unknown. The two travelled together from then on, and confirming one left the
other looking unanswered when it had never been in doubt. **A question inherits
its uncertainty from the company it keeps** — which is an argument for checking
what the repo already says before asking anyone anything.

One cosmetic difference, checked and harmless: `0001` creates `btree_gist` with
no `with schema extensions`, while `0008` and `0034` schema-qualify their
extensions. `if not exists` makes the schema moot on any project where Supabase
has already provisioned it, and `extensions` is on the default `search_path`
either way, so the operator classes resolve from both. Not worth a migration to
tidy.

### 7.2 ~~The suite has not been re-run since the `deps.py` seam change~~ — closed

Closed 2026-08-09. It has been run, it failed, and the failure was real: see
§4.5. **713 passing now**, 694 of them the pre-existing ones, unchanged. Kept
visible rather than deleted, because the item did its job — this is the one open
item in this file that ever caught anything.

### 7.3 ~~`app/api/deps.py` belongs to the parallel auth workstream~~ — closed by a ruling, not by a review

Closed 2026-08-10. The product owner's instruction — *"you can change the auth
bit too. but do document it separately in detail in a separate file in
doc/design"* — replaced the review request with a condition, and the condition is
met: [`docs/design/AUTH_AND_SESSION_DESIGN.md`](../design/AUTH_AND_SESSION_DESIGN.md).

**What this item used to be holding.** Two files awaiting another owner's eyes:
`app/api/deps.py`'s additive `MembershipSet` seam, and the one-line worker branch
Step 8 added to `homeRouteFor` in `frontend/src/lib/auth/authService.js`. It also
recorded, as an aside, that `homeRouteFor` and `getDashboardRouteForRole` were
two functions doing one job in two vocabularies, and that collapsing them was
that owner's to decide.

**What happened instead.** The collapse was done here (§5.17, `D22`), and it
immediately produced three live defects that the abstract complaint had not
predicted — a dead `/security-manager` route, every department manager routed to
the security portal, and a provider with no landing place. Those are in §5 of the
design document with the reason each was invisible.

**What is still that owner's, and is now written down rather than pending.** §7 of
the design document lists four open questions — the wording of
`active_membership_required` for a caller who belongs nowhere, whether
`SessionContext.capabilities` is a feature or dead weight, the stale RBAC block
in `app/domain/roles.py`, and whether "signed in and that is the whole guard"
deserves a named dependency so it is legible. None blocks anything.

### 7.4 No migration has ever been applied anywhere

Per `backend/supabase/migrations/README.md`, **not one** of the twenty-three
existing migrations has run — including `0001_baseline.sql`. This plan adds six
more. Every predicate in all of them is unexecuted until someone applies them,
and applying them is the PO's to do.

---

## 8. Defects found in passing

Not caused by this work. They were parked for Step 4 because they sit directly
under the supervisor triage path this feature builds on; the PO pulled them
forward on 2026-08-09, so the fixes are §6.0 and the outcome is §5.8.

**1. `complaints_service.py:22` calls a repository function that does not exist.**
`people_repo.get_membership_id_for_profile(...)` appears exactly once in the
codebase — at the call site. `app/repositories/people_repository.py` defines
`find_active_membership_by_email` and `set_membership_role`, and nothing else.
Both admin complaint writes raise `AttributeError` → 500 on the first line they
reach. `tests/api/test_complaints.py` monkeypatches the whole service, so the
suite has never executed the line.

**2. `AddCommentRequest.visibility` defaults to a word the database rejects.**
Corrected 2026-08-09 — *this entry previously said such a comment is "stored and
then never displayed", and that is wrong in the direction that matters.* Traced
through: the default `"resident"` reaches `add_complaint_comment`, which
coalesces only blanks (`0020:280`, `0031:812`), so `'resident'` survives to the
insert and violates `complaint_comments_visibility_check` — `visibility in
('public','internal')` (`0020:101`). That is a `23514`, which
`app.core.pg_errors.translate` turns into a **422**.

So nothing is stored invisibly. **Every comment posted through this endpoint
fails outright**, including the frontend's, which hardcodes the same word
(`createComplaintsSlice.js:182`). A comment that is rejected is a better failure
than one that vanishes — but it is a total one, and the endpoint is unusable.

**3. Four places spell the same concept two ways, and none of them is the
database.** Found while fixing 2, and it is the actual defect — 2 is a symptom.
`createComplaintsSlice.js:182`, `API.md:776-778`, `AddCommentRequest.visibility`
and `tests/api/test_complaints.py:71` all say `resident`; `complaint_comments`,
both RPCs and every read filter say `public`. The test asserts the wrong
vocabulary round-trips, which is why it passes.

**5. `departments.kind` — Python and the database allow disjoint sets.** Found
while writing `0035` §1, looking for how a security department is recognised.
`departments_service._VALID_KINDS` is `("service", "security")`, `API.md` and
`department_schemas.py` say the same, and `departments_kind_check` (`0019:150`)
allows `internal | vendor | hybrid`. **The two sets do not intersect**, so every
create or update that names a kind is a `23514` → 422. Only requests that omit
`kind` entirely work, which is why it has not been noticed. Fixed in `0035`,
because D1's hire needs `kind` to decide between a `worker` and a `security`
membership.

**6. `staff_assignments.shift` — the two vocabularies overlap in two values out
of five.** `_VALID_SHIFTS` is `("Day", "Evening", "Night")`;
`staff_assignments_shift_check` allows `Morning | Evening | Night | Full Day`.
`Day` is accepted by Python and rejected by Postgres; `Morning` and `Full Day`
are the reverse. This is the defect D4 was written to fix — the plan called it a
vocabulary tidy-up, and it is actually a live failure on three of the five words.

**7. The submission ERD's `departments` and `staff_assignments` blocks are still
baseline-only** — missing every column `0019` added. Step 2 edits two constraints
on `staff_assignments` and adds a column to it, so the block has to be right
before this feature's own rows are added to it.
