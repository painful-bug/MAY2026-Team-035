# 2026-08-11 — departments, skills, manager provisioning, connectivity

**Branch** `services-and-security` · **PR** back to draft for this work.

Four instructions drove this, and each turned out to be a different distance from done:

1. The admin department form should create a department with categories (creating new ones inline),
   skills (creating new ones inline), a manager, an optional supervisor — and should **stop**
   offering to add technicians, who are now outside people.
2. A department manager should be able to add skills, and a new skill should attach to their
   department automatically.
3. Skills are one **global** master table, with closest-match autocomplete so nobody invents a
   duplicate.
4. Everything built on this branch should actually be connected front to back.

> **Read this first if you are short of time:** jump to
> [Contract changes that break somebody](#contract-changes-that-break-somebody) and
> [What to do after pulling](#what-to-do-after-pulling). Everything else is background.

---

## Status

| Phase | State |
|---|---|
| 1 — `0048` + skills/category API | ✅ done |
| 2 — `0049` + manager/supervisor provisioning | ✅ done |
| 3 — frontend plumbing, the two comboboxes | ✅ done |
| 4 — admin department form | ✅ done |
| 5 — `/manager` portal | ✅ done |
| 6 — hiring for the manager portals (issue 14) | ✅ done |
| 7 — the three open questions, answered and built | ✅ done |
| 8 — resident portal wiring (24 ops) | ⏳ |
| 9 — work orders, amenities, money (~27 ops) | ⏳ |
| 10 — docs close-out | ⏳ |

---

## Phase 1 — skills become something you can hold

### What changed and why

Skills already existed as a global catalogue of twelve seeded trades, and a department could only
reach them *sideways*: `department → categories → complaint_categories.skill_id → skills`, with the
last hop bound by exact string equality on the category's name. Nothing could create a skill,
nothing could attach one to a department, and no query anywhere did fuzzy matching on a skill name.

This phase adds the missing direct relationship and the search behind the form's text box. The
catalogue stays global — a per-community catalogue would mean one trade spelled several ways, so a
plumber registering in two societies claims "Plumbing" twice and the hiring search matches neither.

A department **inherits nothing**. In particular it does not inherit skills from its complaint
categories: the two answer different questions — *which trade handles this kind of complaint* versus
*which trades this department employs* — and deriving one from the other would give every department
a skill list nobody chose.

### Endpoints

All additive. Nothing was removed.

| Method | Path | Guard | Notes |
|---|---|---|---|
| `GET` | `/api/v1/skills` | authenticated | **Changed, backward-compatible.** Gains optional `q` and `limit`. Without `q` the behaviour is byte-identical to before — the whole catalogue, alphabetical, unpaginated, which is what the worker registration grid renders. |
| `POST` | `/api/v1/skills` | admin **or** manager | Create-or-return. **201** when created, **200** when a case-insensitive match already existed. A retired trade is reactivated, not duplicated. |
| `GET` | `/api/v1/complaint-categories` | admin **or** manager | Reinstated (see below). Each row carries `skillId`/`skillName` and `departmentCount`. |
| `GET` | `/api/v1/departments/{id}/skills` | admin, or that department's manager | |
| `PUT` | `/api/v1/departments/{id}/skills` | same | Replace by ids. Validates every id **before** deleting anything. |
| `POST` | `/api/v1/departments/{id}/skills` | same | By **name**: creates in the catalogue if absent, then attaches. One call, because create-then-attach can half-fail and leave a skill attached to nothing. 201/200 as above. |
| `DELETE` | `/api/v1/departments/{id}/skills/{skillId}` | same | Detaches only. The skill is global and survives. Detaching one that is not attached is a no-op, not a 404. |

Spec: **179 → 185 operations, 150 → 153 paths.**

Guarding is two-layered and the second layer is the one that matters: the router asks
`require_admin_or_manager` (do you manage *anything*), and `can_manage_department` inside each RPC
asks whether you manage **this** department. A manager of one community cannot edit another's skills
by putting its id in the path.

### Schema — `backend/supabase/migrations/0048_skills_and_categories.sql`

| Object | Change |
|---|---|
| `department_skills` | **New table.** `(department_id, skill_id)` PK. `on delete restrict` on the skill, mirroring `service_provider_skills` — a skill in use is retired with `is_active = false`, never deleted. |
| `skills_name_trgm` | **New index.** GIN trigram on `lower(name)` where `is_active`. `pg_trgm` was already installed; this is the first trigram index on skills. |
| `department_overview` | **Replaced.** Gains `skill_ids[]` / `skill_names[]`, and fixes `rank = 'head'` → `'manager'` (see below). |
| `search_hireable_service_providers` | **Replaced.** Its `needed` CTE is now a union — see the breaking-change section. |
| New RPCs | `search_skills`, `create_skill`, `can_author_skills`, `community_categories`, `department_skill_list`, `add_department_skill`, `remove_department_skill`, `set_department_skills` |

The migration is **written and pglast-parse-clean. It has not been applied anywhere** — no migration
in this repo ever has.

> **The workstream's migration range is now nearly full.** `0034`–`0049` belongs to service
> operations and security; `0048` is taken here and `0049` is taken by phase 2. Anything after that
> needs a range extension agreed in `backend/supabase/migrations/README.md`.

---

## Phase 2 — managers and supervisors who can actually sign in

### What changed and why

**Before this, a plumbing manager could not sign in anywhere.** `_portal_for` returned `"manager"`,
the frontend had no route for it, and — more fundamentally — *nothing in the system had ever minted a
`manager` membership*. `decide_service_application` mints `security` or `worker`, and there was no
other minter. The role existed in the enum and nowhere else.

The ruling settles how leadership comes to exist: **there is no registration process.** An admin
types a name and an email; that person signs in with Google and is a manager. A supervisor is the
same, created by the admin *or* the manager. Servicemen remain the only role in the service section
with a registration flow of their own.

The mechanism is not an endpoint, because at the moment an admin creates a manager **there is no
profile to attach a membership to** — that person has never signed in. So the provisioning is stored
against the email and claimed on first sign-in.

### Endpoints

| Method | Path | Guard |
|---|---|---|
| `GET` | `/api/v1/departments/{id}/staff-invitations` | admin, or that department's manager |
| `POST` | `/api/v1/departments/{id}/staff-invitations` | same — **this is what lets a manager create a supervisor** |
| `DELETE` | `/api/v1/departments/{id}/staff-invitations/{invitationId}` | same |

Spec: **185 → 188 operations, 153 → 155 paths.**

Nothing is mailed. The email is the **matching key**, not a delivery address. A wrong address
produces no bounce and no error — only an invitation that stays `pending` forever, which is why the
GET returns pending rows and the department screen will show them.

### Schema — `backend/supabase/migrations/0049_staff_provisioning.sql`

`staff_invitations` (community, department, email `citext`, name, phone, rank, job title, status,
who claimed it and when, who created it). Rank is checked against `manager|supervisor` — **`member`
is absent on purpose**, since that rank is reached only by hiring a registered service provider.
One open invitation per email per community, mirroring `invites_one_open_email`.

RPCs: `department_staff_invitations`, `invite_staff_member`, `revoke_staff_invitation`,
`claim_staff_invitations`.

**The membership role is derived at claim time, never stored** — same derivation
`decide_service_application` does: a `manager` rank becomes a `manager` membership; a `supervisor`
becomes `security` or `worker` by the department's kind. Deriving late means a department that
changes kind between the invitation and the sign-in cannot mint a membership pointing at the wrong
portal.

### The auth-seam change

`get_session_context` (`app/services/auth_service.py`) gains a claim step **on the path that has
already established the caller has no membership**. Three properties keep it from being a way in for
the wrong person:

- the email comes from `verified_identity(access_token)` — GoTrue — never from `profiles`, because
  treating a table as the authority on who somebody is would make a row a credential;
- `claim_staff_invitations` is **revoked from `authenticated`**: it takes the email as an argument
  and the email *is* the authorization, so a caller who could choose it could admit themselves;
- a failure is swallowed. Claiming enhances a session that is already valid; somebody provisioned who
  meets a database error should land on the account page and be admitted next time, not be refused a
  session they are entitled to.

This is the auth workstream's file, so it comes with
[`docs/design/STAFF_PROVISIONING_DESIGN.md`](../design/STAFF_PROVISIONING_DESIGN.md), which also
records the one-factor trade-off rather than softening it: **whoever controls that mailbox at first
sign-in becomes the manager of that department.** The resident invite's mandatory token is untouched
— leadership got its own table specifically so that rule would not have to bend.

---

## Phases 3–5 — the frontend

### What changed and why

Three things the admin department form could not do, and one portal that did not exist.

**Categories** were a hardcoded six-item checkbox grid (`Departments.jsx:24-31`) while the backend
has accepted arbitrary names since `0019` — so a society with a lift or a swimming pool had no way
to say so. They are now a combobox over the community's real categories, with an add row.

**Skills** were absent from the entire admin surface. They are now a field, backed by the same
combobox, with closest-match suggestions from `pg_trgm`.

**The manager** was a free-text name that created no account. It is now a name plus an **email**,
which provisions a real membership.

**Technicians** are gone from the form. The "Team members" block collected typed-in names with a
rank and a job title and was the only way onto a roster; technicians are outside people now, so a
second quieter way to invent one produced roster rows with no account, no skills and nothing that
could dispatch to them.

### The component

`TokenCombobox` is **one component for both fields**, because they are one problem: stopping
somebody typing "Plumbling" beside "Plumbing". Two implementations would mean the duplicate
prevention had two versions, and the second one edited would be the one that quietly stopped
matching.

The rule it enforces: **`isExact` is never computed in the browser.** It arrives from Postgres,
where the comparison is `lower(btrim(a)) = lower(btrim(b))` against the stored value. A second
implementation in JavaScript would agree on almost every input and disagree on exactly the ones that
matter — a trailing space, a different capitalisation — and disagreeing means offering to create a
duplicate of something that already exists.

Closest matches stay visible **above** the add row. That ordering *is* the duplicate prevention:
somebody typing "Plumbling" sees "Plumbing" before they see the offer to create.

### The `/manager` portal

`/manager` did not exist. `_portal_for` has returned `"manager"` for a non-security department's
manager since the security work, `PORTAL_ROUTES` had no key for it, and that person landed on
`/account`. It was invisible because nothing had ever minted a `manager` membership — `0049` does.

Three screens: **Overview**, **Skills** (the requirement), **Team** (roster + create supervisor +
withdraw a pending invitation).

**No Hiring tab**, and that is recorded rather than quietly omitted —
[`docs/potential issues/14`](../potential%20issues/14-the-manager-has-hiring-permission-and-no-hiring-screen.md).
The hiring endpoints already accept a manager; reusing the admin screen would have shipped four
hardcoded `/admin/...` links that 403 for them. Four broken links is worse than one missing tab.

### Two more things found while building

**`DepartmentDetail.jsx`'s "Assign technician" dropdown had been empty the whole time.** It read
`department.staff`, and `GET /dashboard/snapshot` builds every department as
`{ staff: [], categories: [] }`. It only looked functional because the old form wrote typed-in names
optimistically into the same local array — so it survived until a reload. It now reads the real
roster, is relabelled **"Assign to staff"**, and its empty state links to the hiring screen.

**`handleSubmit` closed the modal on failure.** `createDepartment` is async and the old code did
`if (result) closeModal()` — on a Promise, which is always truthy. A failed create looked like a
successful one. Fixed incidentally by needing `await` to chain the skills and invitation calls.

---

## Phase 6 — hiring, for the two portals that could always do it

### What changed and why

Phase 5 shipped `/manager` without a Hiring tab and wrote that down as
[`docs/potential issues/14`](../potential%20issues/14-the-manager-has-hiring-permission-and-no-hiring-screen.md)
rather than half-build it. This phase closes it, and the audit that ran first found the gap was
wider than the tab.

**The permission was never the supervisor's, and never only the admin's.** `department_hiring.py` is
guarded by `require_admin_or_manager` with `can_manage_department` inside every RPC — admin of the
community, or a manager whose membership names the department. A **supervisor** holds a `worker`
membership and is refused at the router; rank and role are separate axes and only role is checked
here. So the fourteen hiring operations have always accepted exactly two people, and until now the
screens served one of them.

Three things came out of that audit:

1. **The security-department manager had the identical gap.** `_portal_for` sends a `manager` whose
   department is a security department to `/security-manager`, and `SecurityLayout.jsx` carried a
   comment saying staffing "lives in the admin portal's department screens". Same membership role,
   same two guards, same absent screen.
2. **The application notification was a dead link for the person it is addressed to.**
   `apply_to_department` notifies `array['admin', 'manager']`; the link resolved to
   `/admin/departments/{id}/hiring?tab=applications`. For a manager, `ProtectedRoute` does not show
   a 403 — it redirects to their own overview. A click that looks like it did nothing.
3. **Nothing could open a candidate.** Every route into the hiring surface is about somebody *not yet
   on a roster*, and the only person-detail read needs a `staff_assignments` row.

### Endpoints

| Method | Path | Guard | Notes |
|---|---|---|---|
| `GET` | `/api/v1/service-providers/{providerId}` | admin **or** manager | **New.** The read behind every "open this person" click. Narrower than `GET /service-providers/me`: **no `latitude`/`longitude`, no `profileId`**. |

Spec: **188 → 189 operations, 155 → 156 paths.**

The guard is the point of the route existing rather than a plain view read. `service_providers_read`
(`0034` §11) is `auth.uid() is not null`, so Postgres would hand the row to any signed-in caller — a
manager has to be able to find somebody they have never met. `require_admin_or_manager` is what
stops that being a directory of every tradesperson in the country, browsable by every resident.

### Schema

**None. This phase writes no SQL at all**, which matters because `0034`–`0049` is exhausted:

- the candidate read needed no migration — `service_provider_overview` is `security_invoker` and
  already granted to `authenticated`;
- the rank/shift narrowing below needed none — `decide_service_application` already defaults an
  omitted rank to `member` and leaves an omitted shift null.

### The frontend

| Piece | File |
|---|---|
| `usePortalScope()` — base path, department id, `canHire` | `features/hiring/usePortalScope.js` |
| `CandidateDetail` — the person before they work here | `pages/AdminDashboard/CandidateDetail.jsx` |
| `JoinRequests` — accept/reject on the dashboard | `features/hiring/components/JoinRequests.jsx` |
| `portalNotificationUrl()` — the bell's link, per reader | `features/notifications/portalUrl.js` |
| `HIRING_ROUTES` — one fragment, three mounts | `App.jsx` |

**The routes keep the admin's `:departmentId` shape under every portal**, even though a manager's
session already names their department. One shape means one implementation and no branch that only
one portal exercises — and typing somebody else's id is not a way in, because `can_manage_department`
refuses it in Postgres.

**The nav entry is gated on `accessRole`, not `role`.** `/security-manager` is home to two different
people: the department's *manager* (`membership_role = 'manager'`) and a **senior guard**
(`'security'` with a manager-or-supervisor roster rank, routed there so their gate permissions have
screens). They share the display label `SecurityManager` and do not share this permission. Gating on
the label would have put a 403 in a guard's sidebar.

---

## Contract changes that break somebody

### 1. `search_hireable_service_providers` now unions `department_skills`

Its `needed` CTE derived the skills a department wants from its **categories only**. It is now the
union of that and the department's own skills.

```sql
-- was:  distinct cc.skill_id  from department_categories → complaint_categories
-- now:  that, UNION, distinct ds.skill_id from department_skills
```

**Who this affects:** anyone reading `GET /departments/{id}/candidates`, i.e. the hiring screens.

**Why it is not optional:** without it, attaching a skill to a department changes nothing anybody
can observe. The whole point of attaching one is that it changes who can be hired for it.

**Why it is a union rather than a replacement:** every department that has picked no skills yet —
which is all of them, today — must keep hiring exactly as it did yesterday. This adds a second way
to say what a department needs; it does not withdraw the first.

### 2. `department_overview.head_name` was null for every department, and now is not

`0019` defined the head lateral as `where s.rank = 'head'`. `0035` migrated every such row to
`'manager'` and added a check constraint forbidding `'head'`. **`0035`'s own header says it replaced
the view for exactly this reason** — "leave `department_overview` matching on `'head'` and the admin
screen's head field is permanently null" — but it replaced `apply_department_head` and never touched
the view.

So `headName` and `headStaffId` have been `null` on every department since `0035`. `0048` corrects
the predicate while replacing the view for the skill columns.

**Who this affects:** anything rendering a department's head. It will start showing a name where it
showed nothing. If any screen has been coded around "head is always empty", that assumption is now
false. `head` remains the **wire** word; `manager` is what the column stores.

### 3. `DepartmentSummary` gains two fields

`skills: string[]` and `skillIds: string[]` — same positional label+id pairing as `categories` /
`categoryIds` (R23). Both are `[]` for every existing department. Additive; nothing needs to change
to keep working.

### 4. `get_session_context` now writes on a read (phase 2)

`GET /auth/session` can now create a `community_memberships` row and a `staff_assignments` row, for a
caller who had neither. It happens only when the caller has **no membership at all** and a pending
`staff_invitations` row names their verified email.

**Who this affects:** anyone reasoning about `GET /auth/session` as a pure read. It is not one any
more. It is still idempotent — the second call finds nothing pending.

### 5. `GET /departments/{id}` is no longer admin-only, and the router's guard inverted

`departments.py` carried `require_admin` at the **router** level. The manager portal needs to read
its own department — `GET /departments` is admin-only, so a manager cannot look themselves up, and
the only thing that knows which department they run is `membership.department_id`.

FastAPI cannot remove a router dependency for one route, so the router now carries the looser
`require_admin_or_manager` and **eight routes carry `require_admin` explicitly**.

**Who this affects:** anyone adding an endpoint to `departments.py`. The failure mode inverted — a
new route without `ADMIN_ONLY` is now open to every manager in the community, where before the
router caught it. `tests/api/test_departments.py::test_api_186` asserts the whole table for exactly
this reason, and a route added without the guard fails there.

### 6. `applicationUser` gains `departmentId`

`frontend/src/lib/auth/authService.js`. `GET /auth/session` has always carried
`membership.department_id`; nothing copied it onto the user object. Additive.

### 7. `rank` and `shift` are gone from the two hiring requests — **read this one**

`POST /departments/{id}/invitations` and `POST /departments/{id}/applications/{id}/decide` no longer
accept `rank` or `shift`. A product-owner ruling of 2026-08-11:

> *"the only people added from servicemen are technicians (member). no supervisors or managers are
> hired this way. there is no shift or anything. there is no shift system. job assignment is only on
> demand as the auto assign or supervisor does."*

Two separate facts, both load-bearing:

**Rank.** Leadership never comes from this path. An admin or a manager creates a manager or a
supervisor **by email** through `POST /departments/{id}/staff-invitations` (phase 2), and that person
never registered as a service provider. Somebody hired *here* registered themselves and applied, and
joins as a `member`. Promotion afterwards is `PATCH /departments/{id}/staff/{staffId}` — a different
decision with a different guard.

**Shift.** `staff_assignments.shift` is a descriptive text column from `0019`'s typed-roster era and
**nothing schedules from it.** Work reaches a worker through the dispatch sweep (`0037`) or a
supervisor's assignment; a guard's actual rota is `security_shifts` (`0040`), a different table with
real timestamps. The column and its check constraint stay — `security_shifts` is untouched — and the
hiring form simply stops collecting a word nothing reads.

**Who this affects:** anyone calling either endpoint, and anyone reading `staff_assignments.rank` on
a newly hired service person expecting variety. Everybody hired this way is now a `member`.

**How it fails for a stale client:** an unknown field is **ignored, not rejected** — the models do
not forbid extras — so a browser holding a cached bundle that still sends `rank: 'supervisor'` gets
a team member, not a supervisor and not a 422. That is the right failure for a rule like this, and
`tests/api/test_department_hiring.py::test_api_144` pins it.

**It needed no migration.** `0035`'s `p_rank`/`p_shift` parameters still exist; the API stops passing
them, and `coalesce(p_rank, v_app.rank, 'member')` settles it. This is a narrowing of the wire, not
a schema change.

### 8. Notification links are now rewritten per reader

`NotificationBell` no longer navigates to `item.url` verbatim. Several kinds are addressed to
`array['admin', 'manager']` and spell their url `/admin/…`, because SQL cannot know who will read
it; `portalNotificationUrl` maps the hiring sub-tree, `/messages` and the department root onto the
reader's own portal base.

**Who this affects:** anyone adding a notification whose audience includes managers. Put it under a
path the hiring fragment already mounts, or add a rule to `features/notifications/portalUrl.js` —
and if the destination genuinely does not exist for that reader, leave it alone. Three still do:
`/admin/complaints`, `/admin/amenities`, and `/admin/security/incidents` for a *non-security*
manager. Rewriting those would turn a visible failure into a confusing one; they are listed in issue
14 as the honest remainder.

### 9. `GET /api/v1/complaint-categories` is un-retired

It was removed by the frontend wiring audit, and `test_openapi_spec.py` had a guard asserting it
stays removed. That guard has been satisfied deliberately, not deleted quietly — its line is now a
comment recording why.

The retirement reason (audit line 72) was: *"`CreateDepartment.jsx` collects categories as free-text
inputs, not from a vocabulary, and `Departments.jsx` reads `department.categories` off the
department. Nothing fetches a category list."* **Both halves have expired** — `CreateDepartment.jsx`
was deleted in `38927e5`, and the new category combobox exists precisely to fetch that list and stop
duplicates.

The reinstated read is also not the retired one: it carries each category's linked skill, so the
form can warn about categories that match no trade — which today drop out of every hiring search
silently.

---

## Phase 7 — the three open questions, answered and built

Three of the four questions this changelog left open were put back to the product owner on
2026-08-12 and answered. The fourth — complaint **assignment** semantics — stays with whoever owns
the complaint lifecycle and is untouched here. What follows is what each answer turned into.

**One thing changed the shape of two of them before anything was built.** This changelog had recorded
a second factor as needing a new migration, outside the exhausted `0034`–`0049` range. That was wrong
about the cost: `0049` is untracked and unapplied, so it is edited in place, and `0040` is committed
but also unapplied, which this directory's README explicitly allows correcting (`0022`, `0032`,
`0036`, `0037` and `0043` all did). Neither fix needed a number. **That stops being true the moment
anything here is applied to a real database.**

### 7.1 — the staff invitation stays single-factor, and becomes correctable

**The ruling:** *"lets assume that the admin wont make any typos for now and if the admin wants he
can change the email when he notices via an edit option."*

So the second factor was not added, and the failure it guards against was made recoverable instead.
`update_staff_invitation` (edited into `0049`) and `PATCH .../staff-invitations/{id}` correct an
unclaimed invitation. Before this, the only recovery was withdraw-and-recreate, which threw away who
issued the original and when.

Email, name, phone, job title and rank may all change — choosing *supervisor* when you meant
*manager* is the same class of keyboard mistake as mistyping a domain. **The department may not**, and
that absence is load-bearing: it is what `can_manage_department` authorizes the call against, so
allowing a move would let the manager of department A mint staff into department B without B's manager
being asked. Moving an invitation is revoke-and-reissue under the authority of wherever it is going.

`null` means "leave alone" and `""` means "clear it" for the two nullable fields, so a form patching
only the email cannot blank the job title by omission. Both nulls are sent explicitly rather than
omitted, so the Python and the SQL agree on what absence means.

One component now renders the pending list on both the admin's department page and the manager's Team
page (`PendingInvitations.jsx`). Two copies would have meant fixing this twice and discovering later
that one of them had drifted.

### 7.2 — the security-incident audience

**The ruling:** admins and security-department managers.

`record_security_incident` (`0040`) notified `array['admin', 'manager']` — *every* manager in the
community, so the plumbing department's manager was told about gate incidents and sent to
`/admin/security/incidents`, which their portal has no route for. Two wrongs with one cause: the
audience was picked by role alone, and only *some* managers have that screen.

The audience is now the same predicate `_portal_for` uses to decide who sees `/security-manager` at
all — `community_memberships.department_id`, resolved to `departments.kind`. **Deliberately mirrored
rather than approximated:** if the two ever disagree, somebody is notified about a screen they cannot
open, which is exactly the bug being fixed.

A manager whose membership carries no `department_id` is excluded, even though
`can_manage_department` would let them manage the security department — they route to `/manager`,
which has no incidents screen. No path mints such a row.

### 7.3 — complaints get a department

**The ruling, verbatim in substance:** a complaint carries a department field the resident fills in,
with an *unsure* option; the complaint **category takes precedence** over the resident's pick; an
*Other* category goes to the admin, who allots it; a supervisor who thinks a complaint is in the wrong
department asks their manager, who can change it; amenity bookings are admin-only, no department owns
them.

This was by far the largest of the three, and it started as a question about two dead notification
links.

**The rule, in `resolve_complaint_department` (`0050`) and nowhere else:**

1. the complaint's **category** → `complaint_categories` → `department_categories` (`0019`, already
   present) → a department;
2. failing that, **the department the resident named**;
3. failing that, **nothing** — the admin's triage queue.

`"Other"` and `"Not sure"` are **not special values anywhere in the code.** They are the two inputs
that match nothing and fall through. Encoding them as sentinels would have put two more strings in the
system that every reader has to know about, to express what the absence of a match already says.

**An ambiguous category goes to a human.** `department_categories` has a composite primary key, so one
category may legally belong to several departments; when it does, the rule routes to *nothing* rather
than picking — even if the resident named one of the candidates, because letting them break the tie
would quietly invert the precedence rule. A question in the triage queue is answered in one click; a
guess is a wrong answer only the department that *didn't* get it could notice.

**What this made possible, and was really the point.** With a department on the complaint, four
notifications could stop going to everybody:

| Event | Was | Is |
|---|---|---|
| `complaint.raised` | every admin + every manager | admins + the owning department's manager |
| `complaint.reopened` | same | same fix |
| `complaint.resolution_confirmed` | same | same fix |
| `complaint.commented` | same | same fix |
| `amenity.booking_paid` | every admin + every manager | **admins only** — no department owns an amenity |

The first four now go through one new helper, `notify_complaint_staff`, rather than four copies of the
same loop. It lives in `0050` and is called from `0031`, which is an earlier file — safe because
plpgsql bodies are not resolved until they run, and the smaller evil: the alternative was the loop
copied into four call sites, where the fifth author copies whichever one they found.

**`raise_complaint` is dropped and rebuilt rather than corrected in place.** Adding a parameter changes
the signature, so `create or replace` would have created a second *overload* and made every existing
six-argument call ambiguous — a worse failure than the one being fixed. `0031` carries a pointer
forward so nobody reads its definition and believes it.

**A supervisor may ask and may not move.** That is the ruling and it is the only shape that works: a
supervisor who could push work out of their own department could empty it, and the department
receiving it would have no say either way. The manager who answers is the manager of the department
**giving the complaint up**, never the one receiving it — authorizing on the destination would let the
manager of B reach into A and take A's work. `toDepartmentId` is nullable throughout, because "this
isn't ours" is worth saying without knowing whose it is; accepted with nothing named, the complaint
returns to the triage queue.

**One endpoint exists only because a control could not be drawn.** `GET /department-options` returns
id, name and kind of every active department to any member. `GET /departments` is admin-only and
carries roster counts, categories, hours and skills, so a manager choosing where to move a complaint
had no way to learn any department's name — the destination field would have been a box you type a
UUID into. Three fields, rather than widening a real read boundary to serve a dropdown.

**A route collision the tests found.** `GET /complaints/unassigned` was swallowed by
`resident_complaints.py`'s `GET /complaints/{complaintId}`, which read `unassigned` as a complaint id
and ran the resident's read against it. Declaring the literal earlier would have worked and would have
left the triage queue's correctness depending on which order two files are included in. It is
`GET /unassigned-complaints` — a sibling, not a child, so nothing added later can capture it. Same
reasoning for `/department-options`.

### New and changed endpoints

| Method | Path | Guard | Additive? |
|---|---|---|---|
| `PATCH` | `/departments/{id}/staff-invitations/{invitationId}` | admin-or-manager + `can_manage_department` | additive |
| `GET` | `/unassigned-complaints` | `is_community_admin` | additive |
| `GET` | `/department-options` | any active member | additive |
| `PATCH` | `/complaints/{id}/department` | admin if unrouted, else the holding department's manager | additive |
| `POST` | `/complaints/{id}/department-requests` | `can_supervise_department` | additive |
| `PATCH` | `/complaints/{id}/department-requests/{requestId}` | `can_manage_department` | additive |
| `GET` | `/departments/{id}/complaints` | `can_supervise_department` | additive |
| `GET` | `/departments/{id}/complaint-department-requests` | `can_manage_department` | additive |
| `POST` | `/complaints` | unchanged | **gains optional `departmentId`** |

### Schema

`0050_complaint_department_routing.sql` — the first file in the extended range.

* `complaints.department_id`, nullable, single-column FK `on delete set null`. **Not** the composite
  `(department_id, community_id)` FK that `work_orders` uses: that one takes `on delete cascade`
  because a job *is* that department's work, and a complaint is the resident's — deleting a department
  must not delete the complaints it happened to be holding. `set null` on a composite would also null
  `community_id`, which is `not null`, so it would refuse the delete outright.
* `complaint_department_requests` — the transfer request, with a **partial** unique index on
  `(complaint_id) where status = 'pending'`.
* Functions: `resolve_complaint_department`, `notify_complaint_staff`, `assign_complaint_department`,
  `request_complaint_department_change`, `decide_complaint_department_change`,
  `department_complaints`, `unassigned_complaints`, `department_change_requests`,
  `community_departments`, and `raise_complaint` rebuilt with a seventh parameter.

Corrected in place, all unapplied: `0031` (three notify sites + a forward pointer), `0033` (the
amenity audience), `0040` (the incident audience), `0049` (the invitation edit).

---

## Files touched, grouped by owner

Nothing in phase 1 touches a file whose main author is someone else. That changes in phase 4, which
edits `Departments.jsx` and `DepartmentDetail.jsx` (Aakash) and
`store/slices/createDepartmentsSlice.js` (Aishik, Vishnu).

**New**

```
backend/supabase/migrations/0048_skills_and_categories.sql
backend/app/api/v1/routers/skills.py
backend/app/domain/skill_schemas.py
backend/app/repositories/skills_repository.py
backend/app/services/skills_service.py
backend/tests/api/test_skills.py
backend/tests/api/test_departments.py     ← the departments router had no API test at all
backend/tests/api/test_staff_provisioning.py                  (phase 2)
backend/supabase/migrations/0049_staff_provisioning.sql       (phase 2)
docs/design/STAFF_PROVISIONING_DESIGN.md                      (phase 2)
docs/changelogs/                          ← this folder
docs/potential issues/14-…                                    (phase 5)

frontend/src/features/departments/departmentsApi.js           (phase 3)
frontend/src/features/departments/components/TokenCombobox.jsx
frontend/src/features/departments/components/SkillPicker.jsx
frontend/src/features/departments/components/CategoryPicker.jsx
frontend/src/features/departments/components/useDebounced.js
frontend/src/layouts/ManagerLayout.jsx                        (phase 5)
frontend/src/pages/ManagerDashboard/{Overview,Skills,Team}.jsx
frontend/src/pages/ManagerDashboard/useManagerDepartment.js

frontend/src/features/hiring/usePortalScope.js                (phase 6)
frontend/src/features/hiring/components/JoinRequests.jsx
frontend/src/features/notifications/portalUrl.js
frontend/src/pages/AdminDashboard/CandidateDetail.jsx
```

**Modified**

```
backend/app/api/v1/routers/service_providers.py   GET /skills gains q + limit
backend/app/api/v1/service_api.py                 registers the skills router
backend/app/domain/department_schemas.py          skills/skillIds + two request models
backend/app/repositories/departments_repository.py  selects the two new view columns
backend/app/services/departments_service.py       maps them
backend/scripts/api_annotations.py                six new operations
backend/scripts/export_openapi.py                 the `skills` tag description
backend/tests/test_openapi_spec.py                the un-retirement, recorded
backend/app/services/auth_service.py              the claim step  (phase 2, auth seam)
backend/app/domain/hiring_schemas.py              StaffInvitation + InviteStaffRequest
backend/app/repositories/hiring_repository.py     three RPC wrappers
backend/app/services/hiring_service.py            the leadership block
backend/app/api/v1/routers/department_hiring.py   three routes
backend/app/api/v1/routers/departments.py         per-route guards  (phase 5)
backend/tests/api/conftest.py                     a manager fixture
docs/API.md  docs/openapi.yaml  docs/api_yaml_mapper.md  docs/FRONTEND_WIRING_AUDIT.md
docs/COMPLAINT_ENGINE_HANDOFF.md §8              the assignment question

  -- phase 6 --
backend/app/api/v1/routers/service_providers.py   GET /service-providers/{id}
backend/app/domain/service_provider_schemas.py    CandidateProfile
backend/app/repositories/service_providers_repository.py  get_by_id + a narrow select
backend/app/services/service_providers_service.py get_candidate
backend/app/domain/hiring_schemas.py              rank/shift removed from two requests
backend/app/services/hiring_service.py            _RANK_TO_STORAGE deleted with them
backend/app/api/v1/routers/department_hiring.py   the two docstrings
backend/tests/api/test_service_providers.py       api_237-240
backend/tests/api/test_department_hiring.py       api_143/144/150 rewritten
frontend/src/App.jsx                              HIRING_ROUTES, three mounts
frontend/src/layouts/{ManagerLayout,SecurityLayout}.jsx      the Hiring entries
frontend/src/pages/AdminDashboard/{DepartmentHiring,EmployeeDetail}.jsx  de-hardcoded
frontend/src/pages/ManagerDashboard/Overview.jsx  join requests + the hiring button
frontend/src/pages/SecurityManagerDashboard/Overview.jsx      join requests
frontend/src/components/notifications/NotificationBell.jsx    per-reader links
frontend/src/features/hiring/hiringApi.js         candidate() + the invite contract

  -- phase 7 --
backend/supabase/migrations/0050_complaint_department_routing.sql   NEW
backend/supabase/migrations/README.md             range extended to 0050-0059
backend/supabase/migrations/0031_resident_complaints.sql  3 notify sites + a pointer
backend/supabase/migrations/0033_resident_money_and_home.sql  amenity audience
backend/supabase/migrations/0040_security_operations.sql  incident audience
backend/supabase/migrations/0049_staff_provisioning.sql   update_staff_invitation
backend/app/api/v1/routers/complaint_routing.py   NEW — six routes
backend/app/domain/complaint_routing_schemas.py   NEW
backend/app/repositories/complaint_routing_repository.py  NEW
backend/app/services/complaint_routing_service.py NEW
backend/tests/api/test_complaint_routing.py       NEW — api_248-257
backend/app/api/v1/service_api.py                 registers it
backend/app/domain/{hiring,resident_complaint}_schemas.py  two request models
backend/app/repositories/{hiring,resident_complaints}_repository.py
backend/app/services/{hiring,resident_complaints}_service.py
backend/app/api/v1/routers/department_hiring.py   PATCH invitation
backend/scripts/api_annotations.py                seven operations, two NO_STORY keys
backend/scripts/export_openapi.py                 the complaint-routing tag
backend/tests/api/test_staff_provisioning.py      api_241-245
backend/tests/api/test_resident_complaints.py     the departmentId contract
backend/tests/test_notification_links.py          the fifth rewrite rule
frontend/src/features/complaints/                 NEW — routingApi + 2 components
frontend/src/features/departments/components/PendingInvitations.jsx  NEW
frontend/src/pages/ManagerDashboard/Complaints.jsx           NEW
frontend/src/pages/WorkerDashboard/Complaints.jsx            NEW
frontend/src/pages/AdminDashboard/ComplaintTriage.jsx        NEW
frontend/src/features/notifications/portalUrl.js  the complaints rule
frontend/src/features/departments/departmentsApi.js  updateStaffInvitation
frontend/src/App.jsx                              three routes
frontend/src/layouts/{Admin,Manager,Worker}Layout.jsx        three nav entries
frontend/src/pages/ManagerDashboard/Team.jsx      uses PendingInvitations
docs/erd/homebandhu.dbml                          complaint_department_requests
docs/class-diagram/homebandhu-domain.puml         the same, plus Complaint.departmentId

**Aakash's files** — `pages/AdminDashboard/Departments.jsx` (the form rework),
`pages/AdminDashboard/DepartmentDetail.jsx` (the roster fix, and phase 7's pending-invitation panel).
**Shared layout, one line each in phase 7** — `layouts/AdminLayout.jsx` (Aishik, Aakash, Aniket) gains
a *Complaint Triage* nav entry; `layouts/WorkerLayout.jsx` gains *Complaints*. Nav entries rather than
page rewrites, because without one the screen is reachable only from a notification, which is the
failure `docs/potential issues/14` was written about.
**Not touched, deliberately** — `pages/AdminDashboard/Complaints.jsx` (Aishik, Aakash). The admin's
triage queue is a **new page** rather than a tab on theirs: it asks a different question — not how a
complaint is going, but whose it is.
**The auth workstream's files** — `services/auth_service.py` (the claim step, with a design doc),
`lib/auth/authService.js` (`departmentId`). Phase 7 added nothing here: the supervisor's screen gates
on the roster rank the worker snapshot already carries, precisely so a nav entry did not become a
reason to put a rank on the session.
Nothing in `store/slices/createDepartmentsSlice.js` (Aishik, Vishnu) changed.
```

---

## What to do after pulling

1. **Nothing to install** — no new dependency.
2. `cd backend && python scripts/export_openapi.py --check` should say *up to date*. If it does not,
   you have a local spec change; regenerate rather than hand-editing `openapi.yaml`.
3. **Do not apply `0048`.** No migration here has ever been applied to a database and applying them
   is the repo owner's to do, in order, from `0001`.
4. `GET /auth/session` is no longer a pure read — see change **4**.
5. If you are working on the hiring screens, re-read change **1** above — candidate lists will start
   including people the department's own skills match.
6. If you are working on any department screen, re-read change **2** — `headName` now arrives
   populated.

## Verification at the end of phase 7

| Check | Result |
|---|---|
| `pytest -q` | **908 passed** (was 891; +17) |
| `ruff check .` | **153** — unchanged |
| `export_openapi.py --check` | clean — **197 operations / 163 paths** (was 189 / 156) |
| `regen_mapper.py --check` | clean — regenerated **last**, after every API.md edit |
| `api_map_scan.py` | **20** — back to baseline |
| pglast parse `0031`, `0033`, `0040`, `0049`, `0050` | clean |
| `npm run build` | clean |
| `npm run test` | 3 node suites pass |
| `npx oxlint` | **7** — unchanged |
| `dead_code_sweep.py` | no new findings; **0 dangling documentation links** |
| `frontend_api_sweep.py` | 145 call sites / 197 operations / **139 reached** (was 136 / 188 / 130) |

**All eight new operations are reached by a call site.** That is the point of building the screens in
the same pass: an endpoint with no caller is `docs/potential issues/10`, and this workstream has
written that file once already.

### Three things worth carrying forward

**The route collision was found by a test, not by reading.** `GET /complaints/unassigned` resolved as
a complaint whose id is the word "unassigned" and ran the resident's read against it — the symptom
was `'object' object has no attribute 'table'` from a stubbed client, about as far from the cause as
an error can land. The fix is a path that *cannot* collide rather than a declaration order that
happens not to.

**`test_notification_links.py` caught `/admin/complaint-triage` immediately**, because it checks
blind — it does not know an audience, only whether a link resolves for a reader. That is why the
admin-only triage link had to be recorded on `UNREWRITTEN_FOR_A_MANAGER` with its reason. The
bluntness is the feature: a test that re-implemented `notify_community_roles` in a regex would agree
with the SQL by construction.

**The mapper needed a section heading written by hand.** `regen_mapper.py` is organised by router
file and fills tables under `### \`backend/…\`` headings; a brand-new router has no heading, so its
seven operations were silently absent and `api_map_scan` reported them as missing. Worth knowing
before the next new router: **add the section, then regenerate.**

---

## Verification at the end of phase 6

| Check | Result |
|---|---|
| `pytest -q` | **891 passed** (was 884; +7) |
| `ruff check .` | **153** (unchanged) |
| `export_openapi.py --check` | clean — 189 operations / 156 paths |
| `api_map_scan.py` | **20 findings** (unchanged baseline) |
| `regen_mapper.py --check` | clean |
| migrations | **none written** — the range is exhausted and this phase needed none |
| `npm run build` | clean |
| `npm run test` | 3 node suites pass |
| `npx oxlint` | **7** (unchanged) |
| `dead_code_sweep.py` | no new findings; **0 dangling doc links** |
| `frontend_api_sweep.py` | 137 call sites, 189 operations, **131 reached** |

**Two things worth saying rather than hiding in a green table.**

`tests/api/test_auth.py::test_api_005` failed once during this phase and passed on the three runs
either side of it. It is a **flake, not a regression**: it returned `503 auth_provider_timeout`
against a **1 ms** `AUTH_PROVIDER_TIMEOUT_SECONDS`, with the dispatcher's retry loop running in the
background of a full-suite run. Nothing in this phase touches sign-in. Worth knowing about before
somebody wires a CI gate to a single run.

`regen_mapper.py` rewrote **531 rows** at the start of this phase, all of them API.md line
references. That was drift left by phase 5, whose `--check` ran *before* its last API.md edit. The
lesson is procedural and now followed here: **regenerate the mapper last**, after the final
documentation change, not in the middle of the docs pass.

## Verification at the end of phase 5

| Check | Result |
|---|---|
| `pytest -q` | **884 passed** (was 860; +25 new, −1 retired-endpoint parameter) |
| `ruff check .` | **153** (unchanged) |
| `export_openapi.py --check` | clean — 188 operations / 155 paths |
| `api_map_scan.py` | **20 findings** (unchanged baseline) |
| `regen_mapper.py --check` | clean |
| pglast parse `0048`, `0049` | clean |
| `npm run build` | clean |
| `npx oxlint` | **7** (unchanged) |
| `dead_code_sweep.py` | no new findings from this work |
| `frontend_api_sweep.py` | 136 call sites, 188 operations, **130 reached** (was 124 / 179 / 120) |

## Open questions — and how they were settled

Raised at the end of phase 5, put to the product owner on 2026-08-11.

### Settled

**Category → skill binding stays exact string equality.** `link_category_skill` (`0034`) fills
`complaint_categories.skill_id` by matching `lower(btrim(name))` against the catalogue, so a category
named "Water leakage" or "Plumbling" binds to nothing and nobody is told. Left as it is, for a reason
that arrived with phase 1: `search_hireable_service_providers` now **unions the department's own
skills**, so a mis-bound category no longer breaks hiring on its own, and `CategoryPicker` warns when
a category matches no trade. A fuzzy auto-bind was considered and rejected — a wrong guess is worse
than a null the screen already flags.

**`can_author_skills` stays admin-or-manager.** Any active admin or manager membership, in any
community, may add to the global catalogue. That is deliberately loose and it is what requirement 2
asked for: a manager who needs "Lift Maintenance" should not file a ticket to type a word. The
closest-match box is the control against drift, and making authoring admin-only would have deleted
the manager Skills screen's whole purpose.

**Hiring terms: rank and shift removed.** See breaking change 7 — this was the answer to "what terms
does the accept button collect", and it removed the question rather than answering it.

**Scope of the hiring screens: the department manager *and* the security-department manager.** Both
hold `membership_role = 'manager'` and both lacked a screen; building one and not the other would
have shipped the same bug one role along.

### Settled on 2026-08-12 — see phase 7

**The staff-invitation single factor stays, and becomes correctable.** The ruling was to assume the
admin does not mistype, and to give them an edit when they notice. So no token, no acceptance step,
nothing mailed — and `PATCH .../staff-invitations/{id}`. A typo still fails *silently* until somebody
looks at the pending list, which is stated plainly in
[`STAFF_PROVISIONING_DESIGN.md`](../design/STAFF_PROVISIONING_DESIGN.md) rather than dressed up. The
resident invite's mandatory token is untouched.

**`/admin/security/incidents` no longer reaches every manager.** `0040` was corrected to notify
admins and *security-department* managers — the same predicate `_portal_for` uses to hand out
`/security-manager`. A plumbing manager is no longer told about gate incidents.

**Complaints get a department**, which closed the two dead notification links this changelog had
recorded as unfixable, at the source rather than in the router. See phase 7.3.

### Still open

- **Complaint assignment semantics** — *which staff member* is working a complaint, as distinct from
  *which department holds it*. Three options in
  [`COMPLAINT_ENGINE_HANDOFF.md` §8](../COMPLAINT_ENGINE_HANDOFF.md). Belongs to whoever owns the
  complaint lifecycle and stays routed there. Phase 7 deliberately did not touch it: `0050` decides
  which department owns a complaint and says nothing about who does the work.
- **A supervisor's screen shows one department.** `WorkerDashboard/Complaints.jsx` picks the first
  roster row where the caller ranks supervisor or manager. Somebody supervising two departments in
  two societies is possible and rare, and a portal-wide department switcher is a bigger idea than
  that screen — it wants `communities[]` in a shared context every worker page reads. Recorded rather
  than half-built.
- **The complaint category catalogue can still be mis-mapped**, and now it has a visible consequence
  rather than a silent one: an unmapped category sends the complaint to the admin's triage queue
  instead of nowhere. That is an improvement, not a fix — the fix is somebody curating the catalogue,
  which is what `CategoryPicker`'s warning is for.
