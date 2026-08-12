# Identity, membership and where a person lands

**Status:** built, 2026-08-10. Written after the fact, like
[`ADMIN_DASHBOARD_DESIGN.md`](ADMIN_DASHBOARD_DESIGN.md) and unlike
[`RESIDENT_BACKEND_DESIGN.md`](RESIDENT_BACKEND_DESIGN.md) — every claim here
describes code you can go and check, and if this document and the code disagree,
the code wins and this is a bug.

**Why it exists as its own file.** The auth seam has been *shared* since the two
workstreams merged: `app/api/deps.py` and `frontend/src/lib/auth/authService.js`
belong to a parallel workstream, and the service-operations build has needed to
change both. The product owner's ruling on 2026-08-10 was *"you can change the
auth bit too, but do document it separately in detail in a separate file in
`doc/design`."* So this is the review packet for that owner: what changed, what
it fixed, what it deliberately did **not** change, and the four places the
old shape is still visible.

It is also the answer to a question the other three design documents keep
brushing against and none of them owns: **what is a person here, and what is a
membership, and which of the two is a given feature actually about?** Getting
that wrong is not a style disagreement. It produced four separate live defects,
documented in §5, and every one of them was invisible until a population arrived
that the original answer had not imagined.

---

## 1. The one idea

> **Identity is global. Membership is per-community. Almost everything in this
> product is about the second, and a handful of things are about the first — and
> the handful is where every bug was.**

A `profiles` row is a person: one per Supabase auth user, created on first login.
A `community_memberships` row is that person's relationship with **one** society:
their role there, their department there, their unit there. The two are not
interchangeable, and the join between them is many-to-one — one person, several
memberships.

For the first two workstreams that distinction did not pay rent. A resident is a
member of one society. An admin is an admin of one society. So "the caller" and
"the caller's membership" were the same object in practice, and the codebase
quietly used the membership as the identity. `deps.py` resolved exactly one:

```python
.order("is_default_community", desc=True).limit(1)
```

Then the service-operations build introduced two populations that break it:

| Population | What breaks |
|---|---|
| A service person hired by three societies | Holds three memberships. Every "the caller's membership" is one third of an answer |
| A service person who has registered and not been hired | Holds **none**. Every membership-guarded route is a `403`, including the ones that exist to get them hired |

The second is the sharper one, and it is worth stating plainly because it is
counter-intuitive: **the caller most in need of the registration, search,
application and notification screens is the caller with no membership at all.**
A guard that asks "are you a member?" excludes precisely the population those
screens serve.

---

## 2. The backend seam — `MembershipSet`, and why it is additive

`app/api/deps.py` gained one dependency and kept every existing one identical.

`MembershipSet` is a `BaseModel` in `app/domain/schemas.py` — a list of
`MembershipContext` in default-first order, with `default`, `community_ids` and
`for_community(community_id)`.

`get_membership_set` reads all active memberships in one query, ordered
`is_default_community desc, created_at`. `get_active_membership` becomes a
one-line derivation of it:

```python
def get_active_membership(memberships: MembershipSet = Depends(get_membership_set)) -> MembershipContext:
    return memberships.default
```

**Three properties, all deliberate.**

- **Every existing router, guard, test and signature keeps its exact behaviour.**
  A single-membership caller resolves to the same row as before, because
  `default` is the first row of the same ordering the old `limit(1)` used.
- **The number of database reads per request stays at one.** The old query read
  one row of a set; the new one reads the set. Both are one round trip, and
  `tests/test_membership_set.py` pins that the derivation did not become a second
  read.
- **`MembershipSet` itself never raises.** `for_community` returns `None`, and
  the raising lives one level up in `require_community_role(community_id,
  memberships, *roles)` in `deps.py`. That split is the point: absence is a `403`
  or a `404` depending on whether the caller is allowed to learn that the
  community exists, and only the handler knows which. What neither of them ever
  does is read a community id from a request body — a multi-community caller who
  is an admin in society A and a worker in society B must not be able to spend
  society A's admin rights on society B's data, so the lookup is keyed on the
  community the *resource* named.

**What is still true and worth not tidying away.** The membership is read from
Postgres on **every request**, never from a JWT claim. That looks like an obvious
caching opportunity and it is a revocation guarantee: removing somebody from a
society has to take effect on their next request, not on their next token
refresh. `ADMIN_DASHBOARD_DESIGN.md` §2 says this at length; it survives
unchanged here.

### 2.1 The guard the provider routes use is no guard at all

The plan called for a `worker_deps.py` holding `require_worker` and
`require_service_provider`. **It was never written, and that is the decision, not
an omission** (journal §4.4).

Every route in `service_providers.py`, `worker_jobs.py`, `worker_schedule.py` and
`worker_communities.py` declares `Depends(get_current_user)` and nothing else.
The provider is resolved from `auth.uid()` **inside** each `security definer`
RPC, which raises `P0002` when there is no provider row — and
`app.core.pg_errors.translate` already turns that into a `404`. A dependency that
read the same row a moment earlier would add a round trip per request and a
second place for the "are you registered" rule to live, which is the copy that
drifts.

This is the shape the whole of §1 leads to. A provider with no membership must be
able to read their own profile, edit their skills, search societies, apply to
departments, withdraw an application, read the reply, and receive a notification
about all of it. Not one of those is scoped to a community, so not one of them
can be guarded by one. The five notification and push routes in §4 joined this
list on 2026-08-10.

---

## 3. The frontend seam — one route resolver, keyed on `portal`

### 3.1 What was there

Two exported functions answered one question in two vocabularies:

| Function | Lived in | Read | Vocabulary |
|---|---|---|---|
| `homeRouteFor(contextOrUser)` | `lib/auth/authService.js` | `context.membership.role` | lowercase membership role |
| `getDashboardRouteForRole(role)` | `routes/authRoutes.js` | `user.role` | display label — `Admin`, `Worker` |

Every new portal had to be added to both, and the one that got forgotten was
never the same one twice. Step 8 added the worker branch to both by hand and
recorded that as an open item; this closes it.

### 3.2 What is there now

One function, `homeRouteFor(subject)`, in `routes/authRoutes.js` — next to the
constants it returns, in a module that imports nothing, so nothing can cycle. It
takes either a session context from `GET /auth/session` or the user object
`applicationUser` builds from one, because **both carry `portal`**:

```js
const PORTAL_ROUTES = Object.freeze({
  admin: AUTH_ROUTES.ADMIN_DASHBOARD,
  'security-manager': AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD,
  security: AUTH_ROUTES.SECURITY_DASHBOARD,
  worker: AUTH_ROUTES.WORKER_DASHBOARD,
  resident: AUTH_ROUTES.RESIDENT_DASHBOARD,
});
```

**`portal` is the right key, and not because it is convenient.** It is the only
one of the three candidate values that the *backend* computes, and the backend
knows two things the browser does not: whether a manager's department is a
security department, and whether a person holding no membership is a registered
service provider. A frontend mapping from role to route cannot answer either
question, which is exactly why the two functions it replaced both got them wrong.

*Rejected:* keeping both names and having one delegate to the other. Two exported
names for one question is the state that produced the drift; the second name
would still be the one somebody imports.

### 3.3 `applicationUser` learns the portal, and one line lights up a dead portal

```js
const role = context.portal === 'security-manager'
  ? 'SecurityManager'
  : ROLE_LABELS[accessRole] || 'Resident';
```

`ROLE_LABELS` has five values — `Admin`, `Manager`, `Worker`, `Security`,
`Resident` — and `SecurityManager` is not one of them, because it is not a
membership role. It is a *portal*: a manager whose department is the security
department. Four files already branched on the label and one route already
guarded on it, and none of them had ever matched. §5.2 has the consequence.

### 3.4 `SignedInRoute`, and why `applicationUser` was left alone

`ProtectedRoute` reads `currentUser`, and `applicationUser()` returns `null` when
the session carries no membership. So the whole `ProtectedRoute` mechanism is
unavailable to the unhired provider — the same problem as §2.1, one layer up.

`App.jsx` therefore has a second, smaller guard:

```jsx
function SignedInRoute({ children }) {
  if (!isAuthReady) return <RestoringSession />;
  if (!sessionContext?.identity) return <Navigate to={AUTH_ROUTES.LOGIN} replace />;
  return children;
}
```

What the portal then shows is decided by `GET /worker/snapshot`, whose null
`provider` and empty `communities` are the two empty states — the registration
form and the community search.

**The rejected alternative matters more than the chosen one.** The obvious fix is
to make `applicationUser` return a user object for a membership-less session,
synthesising a role. It was rejected because `currentUser` is read by every
portal in the application, and dozens of screens dereference
`currentUser.communityId` without checking it. Changing what `currentUser` means
for one population changes it for all of them, in a file this workstream does not
own. A second guard is additive; a changed `applicationUser` is not.

---

## 4. Notifications: the substrate was addressed to a membership

This is the same idea as §1 applied to a subsystem, and it is the largest single
change in this document. Migration `0041_person_notifications.sql`.

`0030` made one decision — the recipient of a notification is a
`community_memberships` row — and then repeated it eleven times: a `not null`
column, an inner join in the feed view, an RLS predicate, a `not null` column on
`push_subscriptions`, the claim function's return type, the push sender's lookup,
and five API guards.

For a resident that is correct and invisible. For a service provider it is a
closed door with five locks: the row could not be written, and if it could the
feed view's join would drop it, and if it survived that the read policy would
refuse it, and if it passed that the sender would find no subscriptions, because
the browser could not have registered one.

### 4.1 What changed

| Layer | Before | After |
|---|---|---|
| `notifications` | `recipient_membership_id not null` | `recipient_profile_id` always set; membership nullable and means *which community this was about* |
| Read policy | `is_own_membership(recipient_membership_id)` | `recipient_profile_id = auth.uid()` |
| `notification_overview` | `join community_memberships` | `left join` — `community_id` is nullable, which is the truth |
| Writers | `notify_member` | `notify_member` unchanged in signature, plus `notify_profile` |
| `mark_all_notifications_read` | took a membership | takes nothing; reads `auth.uid()` |
| `push_subscriptions` | `membership_id not null` | `profile_id not null`; membership column dropped |
| `register_push_subscription` | took a membership and checked it | takes none; reads `auth.uid()` |
| `claim_push_batch` | returned `membership_id` | returns `profile_id` |
| Five API routes | `get_active_membership` | `get_current_user` |

`notify_member` keeping its exact signature is what makes this cheap: not one of
the twenty-odd call sites across `0031`–`0040` changed. It resolves the profile
itself, which is the only way "always populated" can be true without trusting
every caller to remember.

### 4.2 The rule this overturns, stated plainly

`0030` says, of `is_own_membership`:

> *"`status = 'active'` matters. Someone who has left the community stops being
> able to read what was addressed to them."*

That stops being true. `docs/design/README.md` requires a ruling that overturns
something already written to name what it overturned, so: **named.**

The reason is that the rule only reads correctly for a caller with one
membership. With several, a person removed from one society would lose that
society's rows out of a feed that is otherwise theirs, and the badge would fall
with no event to explain it. A notification is a copy of something the person was
already told; every inbox in the world retains those. What ending a membership
must stop is **new** notifications — and `notify_community_roles` already filters
on `status = 'active'` at the moment of writing, which is where that rule
belongs.

### 4.3 Why the push subscription lost its owner argument

Once the row is keyed on the profile, the only value a caller could legitimately
pass is `auth.uid()`. Passing it in and then validating it against the session it
came from is a parameter that exists to be checked. Deleting it removes the
forgery surface rather than guarding it — which is the argument `0030` itself
made one layer up, when it revoked `authenticated`'s EXECUTE on `notify_member`
because *"a notification that appears to come from the association and leads
anywhere is phishing with the association's name on it."*

### 4.4 What a profile-addressed notification does not get

**No SSE frame.** `sse_events.community_id` is `not null`, and a person with no
membership has no community for a frame to belong to. The feed and Web Push carry
it; the live nudge is skipped. That is a real limit and it costs nothing today,
because the worker portal reads through react-query rather than the event stream.
Giving the outbox a profile audience would mean changing `0028`'s shape
constraint and `realtime.py`'s subscriber matching for a portal that does not
subscribe.

---

## 5. The defects this found, and how each was invisible

None of these was found by reading. Each surfaced when a population arrived that
the original decision had not imagined, which is the argument for writing this
file rather than a diff summary.

*(§5.1–§5.5 were the four found and the one reported during the build itself.
§5.6 was added on 2026-08-11 by a later exercise, and is the sequel to §5.3.)*

### 5.1 The push toggle did not work for the person it was built for

Shipped 2026-08-10 in step 8. `Profile.jsx`'s `PushCard` calls `enablePush()`,
which posts to `POST /push/subscriptions`, which required an active membership.
An unhired service provider — the caller the screen exists for — got a `403`.

**Why nothing caught it:** the frontend cannot see a guard. A `403` on a toggle
looks like a permission the user has not been granted yet.

Now pinned by `test_a_provider_with_no_membership_can_turn_push_on`, which lives
in the backend suite precisely because that is the layer that can assert it.

### 5.2 `/security-manager` was unreachable by any real session

`ProtectedRoute` guarded it with `requiredRole="SecurityManager"`.
`applicationUser` produced `role` from `ROLE_LABELS`, which has no such value, and
put `security-manager` in a *separate* `portal` field. So `homeRouteFor` routed to
`/security-manager` on the portal field, `ProtectedRoute` read the role field, did
not match, and bounced the caller to `/security`.

`Header.jsx` (twice), `SecurityLayout.jsx` and `SecurityDashboard.jsx` all branch
on the same label and were all dead for the same reason.

> **`SecurityDashboard.jsx` no longer exists** — the gate frontend replaced it on
> 2026-08-11 (`SECURITY_PORTAL_DESIGN.md`), and the citation is kept because the
> defect it records was real in the file that was there. Two neighbouring reads
> in the same two files went the other way: `currentUser.departmentName` and
> `.staffRole`, which `applicationUser()` has never set, rendered a literal
> `undefined • undefined` to every gate user until the same build removed them.
> One label with no value bounced a whole portal; two more just looked broken.

**Why nothing caught it:** the redirect target was a real, working page. The
security manager landed somewhere plausible, saw the guard's fallback, and had no
signal that a different portal existed.

Fixed by §3.3 — one line in `applicationUser`, which turns on a route guard and
four branches nobody had to touch.

### 5.3 Every department manager was a security manager

`auth_service.py` derived the portal from the *presence* of a department:

```python
portal = "security-manager" if role == "manager" and membership.get("department_id") else role
```

So the manager of a plumbing department was routed to the gate portal — the exact
person Step 9's hiring screens are for. `departments.kind ∈ {service, security}`
has existed since `0019` and answers this; nothing asked it.

**Why nothing caught it:** until this feature there were no service-department
managers. Every manager in the fixtures was a security manager, so the shortcut
and the correct answer agreed on every case anyone had ever run.

### 5.4 A person with two memberships could receive push for only one

`push_subscriptions.endpoint` is unique across the whole table **by design** —
`0030` §6 says *"the endpoint URL is the browser's identity to the push
service"*, and the uniqueness is what stops two people sharing a laptop from
receiving each other's notifications. But the row carried a membership, so
subscribing the same browser from a second society **moved** the row and silently
stopped the first society's pushes.

**Why nothing caught it:** no caller held two memberships until this feature. The
marker that the multi-community caller had arrived is `unread_count_for_memberships`,
written in step 6 specifically to sum a badge across societies — and now deleted,
because a person-addressed feed does not need summing.

### 5.5 The one that was reported rather than found

`0038` shipped with no notification on a new conversation message, and the
journal carried it as an open item across three build steps with the note *"an
invited provider holds no membership to notify."* That was an accurate diagnosis
and the wrong-sized fix: adding the call without §4 would have written a row
addressed to a null membership into a `not null` column. It closes here, in
`post_conversation_message`, with the two directions addressed differently —
`notify_member` per manager one way, `notify_profile` the other.

### 5.6 The corrected predicate was still satisfiable by nobody

*Found 2026-08-11 by the end-to-end compatibility sweep; fixed the same day.*

§5.3 narrowed the portal test from *"a manager with a department"* to *"a manager
whose department is a security department"*, and that was the right narrowing of
the wrong question. **Nothing in this product writes a `manager` membership.**
`hire_service_applicant` (`0035:918`) is the only code path that creates a
department membership at all, and it mints `security` or `worker`:

```sql
-- A security department hires security; everything else hires a worker.
v_role := case when v_department.kind = 'security' then 'security' else 'worker' end;
```

So `security-manager` was satisfiable by no user the system can create, and the
whole portal — four pages, `GET /security/roster`, and migration `0047`, two of
them built the day before — was unreachable. §5.2 had turned the portal *on* and
this kept it dark.

**The answer was already written down, in SQL, with a comment saying so.**
`gate_admin_community_for` (`0040:589`) is the live guard on posts CRUD and shift
scheduling, and it opens:

> A security *manager* holds a `security` membership with a roster rank, not a
> `manager` membership — D3 made rank and role separate axes and this is the
> first place that distinction has to be honoured rather than described.

`_portal_for` now asks that same question — a `security` membership with an
active `staff_assignments.rank ∈ (manager, supervisor)` — so the portal and the
authorization agree by construction. A portal that disagreed with that predicate
could only be wrong in one of two ways: unreachable, which it was, or full of
screens whose writes 403.

`supervisor` is in the list deliberately, because `gate_admin_community_for`
grants supervisors the manager's writes; routing them to the guard portal would
hand somebody permissions with no screen to spend them on. The `manager` branch
is kept beside it — `manager` is a real `membership_role` value, an admin surface
may yet write one, and a *plumbing* manager must keep landing in their own
portal, which is the whole point of §5.3.

**One consequence outside this file.** `ProtectedRoute` guarded `/security` on
the label `Security` alone, so the fix would have started bouncing newly-senior
guards out of the gate screens — including the targets of two notifications,
`shift.scheduled` (`0040:893`) and `security_shift.assigned` (`0043:950`). That
route now admits `['Security', 'SecurityManager']`.

**Why nothing caught it:** the same shape as §5.2 and §5.3, one level deeper.
Every layer was individually correct — the frontend mapped `security-manager` to
a route, the route guard matched the label, the label came from the portal, the
portal came from a predicate — and the predicate described a person the database
cannot contain. No test asserted on portal derivation at all; the ones that exist
now are `backend/tests/test_session_portal.py`.

---

## 6. What was deliberately not changed

Listed so that a reviewer can tell restraint from oversight.

| Not changed | Why |
|---|---|
| The per-request membership read | It is a revocation guarantee, not a cache miss (§2) |
| `applicationUser` returning `null` without a membership | Changing what `currentUser` means changes it for every portal (§3.4) |
| `is_own_membership` | Five other migrations use it for complaints, visitors, money and gate registers. Only the notification callers moved off it |
| `notifications.recipient_membership_id` | Still the SSE frame's audience and the feed view's `community_id`. It stopped being *who*, not *what about* |
| `require_membership_role` | Untouched. Single-community role checks are still the common case and still correct |
| `ROLE_LABELS` | `SecurityManager` is a portal, not a role, and adding it there would put a non-membership value in a membership map |

---

## 7. Open, and for the auth owner to rule on

1. **`get_membership_set`'s `403` is `active_membership_required`.** Every route
   that still depends on it gives an unhired provider that error. That is correct
   for those routes — they are about a community — but the *message* reads like a
   fault. Whether it should distinguish "you belong to no society" from "you
   belong to the wrong one" is a product call.
2. **`capabilities` is not used by anything.** `SessionContext.capabilities`
   carries `[role]` plus `resident` for admins, and no frontend code reads it. It
   is either the beginnings of the role-switching the admin portal wants or dead
   weight; it should be one or the other before the sweep in step 12.
3. **`app/domain/roles.py` is still the stale RBAC block.** `Role`,
   `_IMPLIED_ROLES`, `effective_roles`, `role_satisfies`, `satisfies_any` and
   `parse_role` describe a hierarchy this codebase does not have.
   `docs/potential issues/` item 2 flags it as *"the file someone will open when
   adding a `worker` role"* — which happened, and the file was correctly ignored.
   Deleting all but `display_role` is queued for step 12.
4. **"Signed in, and that is the whole guard" is now expressed in two places.**
   `SignedInRoute` in `App.jsx`, and a bare `Depends(get_current_user)` on
   roughly thirty backend routes. Neither is wrong, but the backend version is
   invisible — a route that guards on identity alone looks identical to a route
   whose author forgot the guard. Whether that deserves a named dependency
   (`require_signed_in`) purely so the intent is legible is a call for the auth
   owner; this workstream declined to add one for no behaviour.

---

## 8. Where to look

| Question | File |
|---|---|
| How is a membership resolved? | `backend/app/api/deps.py` |
| Why do the provider routes guard on identity alone? | `docs/plans/SERVICE_OPERATIONS_PROGRESS.md` §4.4 |
| What does `GET /auth/session` return, and how is `portal` derived? | `backend/app/services/auth_service.py` |
| Where does a signed-in person land? | `frontend/src/routes/authRoutes.js` |
| What is `currentUser`? | `frontend/src/lib/auth/authService.js` |
| Who can read a notification? | `backend/supabase/migrations/0041_person_notifications.sql` §1 |
| What proves an unhired provider is not locked out? | `backend/tests/api/test_notifications.py`, last three cases |
| What proves a security manager reaches their own portal? | `backend/tests/test_session_portal.py` |
| Who is a security manager, authoritatively? | `gate_admin_community_for`, `backend/supabase/migrations/0040_security_operations.sql:589` |
