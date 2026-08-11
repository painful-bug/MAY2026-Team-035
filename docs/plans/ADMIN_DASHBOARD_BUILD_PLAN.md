# Admin dashboard — backend build plan

**Date:** 2026-07-29
**Scope:** the ten admin dashboard surfaces only. Login and registration are assumed done.
**Code lives in** `backend/`. **Docs live in** `docs/`. **`frontend/` is not touched** — conflicts we
cannot solve from the backend go to [`FRONTEND_MEETING_AGENDA.md`](../FRONTEND_MEETING_AGENDA.md).

---

## 0. What is already in `backend/` — this changes the plan

> **Superseded 2026-07-30 (session 19).** This section describes the tree as it stood before the
> merge of `origin/main` @ `94556e5`. `docs/CLAUDE.md` has since been deleted (it was the file that
> claimed there was no backend), and `0001_init.sql`, `0002_rls.sql` and `0003_access_token_hook.sql`
> were replaced upstream by a single `0001_baseline.sql`. Kept for the reasoning; read
> `docs/FRONTEND_WIRING_AUDIT.md` for the current shape.

`backend/` is not the empty placeholder `docs/CLAUDE.md` describes. It contains a working, cleanly
layered FastAPI service:

```
app/  config · core/{supabase_client,security,tokens,exceptions,logging}
      domain/{roles,schemas} · repositories/ · services/ · api/v1/routers/{auth,invitations}
supabase/migrations/  0001_init.sql · 0002_rls.sql · 0003_access_token_hook.sql
tests/  pytest
```

It is good work and the plan below follows its conventions rather than proposing new ones —
`core/supabase_client.py` as the only place a client is constructed, three clients by trust level
(`anon` / `service` / `user`), DTOs in `domain/schemas.py` kept deliberately separate from row shapes,
`require_role(...)` guards in `api/deps.py`.

### 0.1 I am retracting C3

In [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §2 I argued for **no bespoke API server** —
reads through views, writes through RPC. **That was written without knowing this service existed, and
it is the wrong recommendation for this team.** The FastAPI layer is a better answer than views for
our specific problem: it is where the frontend's exact response shapes get composed, and unlike a
Postgres view it can compose them without pushing display concerns into the schema.

Everything C3 worried about is solved by a layer that already exists.

### 0.2 The schema in the database is not the schema in the ERD

The existing migrations define a different, smaller model than
`erd/homebandhu-v1-milestone1.dbml`. **One collision is actively dangerous:**

| Concept | Live DB (0001) | ERD v1 | Note |
|---|---|---|---|
| The community | `associations` | `communities` | rename |
| A block or villa | **`units`** | `buildings` | ⚠️ |
| A flat / home | `apartments` | **`units`** | ⚠️ |
| Role + placement | `profiles.role`, `.association_id`, `.apartment_id` (text) | `community_memberships`, `unit_residencies` | structural |
| Role vocabulary | `RESIDENT, MANAGER, TECHNICIAN, SECURITY, ADMIN` | `resident, worker, security, manager, admin` | `TECHNICIAN` ≠ `worker` |
| Invitations | `invitations` (token_hash + code_hash) | `resident_invites` | the live one is **better** — it already has both digests, which is exactly R2 |

**`units` means the opposite thing in each.** A developer reading the ERD and writing a query against
the database gets flats when they wanted blocks, silently and with no type error. This has to be
resolved before the dashboard adds tables that reference either.

**Note in passing:** the live `invitations` table already does what R2 proposed, independently. That
is a point in favour of the working schema, not against it.

---

## 1. Three findings that outrank the dashboard

Found while reading the migrations. All three are independent of this plan.

> **Ownership, decided 2026-07-29:** §1.1 and §1.2 are **owned by the auth/security developer** and
> are being fixed in parallel. This plan does not touch them. §1.3 is unowned and is not auth-adjacent.
>
> **Consequence for this plan — the dashboard is no longer blocked by them.** See §1.4 for how the two
> streams stay out of each other's way, which took two concrete decisions rather than none.

### 1.1 Privilege escalation through signup metadata — **critical**

`0001_init.sql`, `handle_new_user()`:

```sql
coalesce((new.raw_user_meta_data ->> 'role')::public.user_role, 'RESIDENT')
```

`raw_user_meta_data` is **client-supplied**. Supabase writes `signUp({ options: { data } })` straight
into it, so a self-service signup that passes `{ "role": "ADMIN" }` gets an ADMIN profile — and the
access-token hook then mints an ADMIN claim, which both the FastAPI guards and RLS trust.

Today this is held shut only by `should_create_user=false` on the OTP path. **The OAuth switch opens
it**, because OAuth sign-in creates users by design. This must be fixed before OAuth goes live.

**Fix:** never read a role from user metadata. Default every new profile to `RESIDENT` and set
elevated roles only through a service-role path that verifies an invitation.

### 1.2 `is_admin()` is global, not per-community — **high**

`0002_rls.sql` defines `is_admin()` as `jwt_role() = 'ADMIN'`, and the policies use it unscoped:

```sql
create policy associations_admin_write on public.associations
  for all using (public.is_admin()) with check (public.is_admin());

create policy profiles_self_select on public.profiles
  for select using (id = auth.uid() or public.is_admin());
```

**Any admin of any community can read every profile in the database and write every association.**
There is no tenant boundary for admins at all — and admins are precisely the role this dashboard is
built for, so every surface we add inherits the hole.

**Fix:** scope on the caller's association, not on the role alone:

```sql
create or replace function public.current_association_id() returns uuid
language sql stable security definer set search_path = public as $$
  select association_id from public.profiles where id = auth.uid();
$$;
```
and make every admin policy `public.is_admin() and association_id = public.current_association_id()`.

**This is step 1 of the build.** Ten new admin surfaces on top of an unscoped admin policy multiplies
the exposure by ten.

### 1.3 `backend/.venv` is committed — **medium**

`git ls-files backend` returns 4,100+ files, nearly all of them `.venv/`, including Windows `.pyd`
binaries. It bloats every clone, breaks on non-Windows machines, and buries real diffs. Add
`.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `*.egg-info/` to `.gitignore` and
`git rm -r --cached`. `.env.example` is correctly committed and contains no secrets.

**Not started** — `git rm -r --cached` rewrites the index across 4,100+ paths, so it wants to be its
own commit on a clean tree rather than something folded into a migration PR. Say the word.

### 1.4 Running two migration streams in parallel — two decisions

Splitting the work across two developers creates two collisions that are cheap to prevent now and
painful to unpick later. Both are already applied in `0010_memberships.sql`.

**1. Migration numbers are reserved by range.** The auth workstream will naturally reach for `0004_`,
and so would this one. Two files with the same number in one branch is a merge conflict in the one
place a merge conflict is worst — schema ordering.

| Range | Owner |
|---|---|
| `0004`–`0009` | auth / security workstream (§1.1, §1.2) |
| `0010`+ | admin dashboard (this plan) |

**2. The dashboard does not inherit §1.2 while the fix is in flight.** This is the finding that
mattered. Every table added by this plan carries `community_id`, and its RLS policies are
community-scoped from the first line rather than reusing bare `is_admin()`:

```sql
using (public.is_admin() and community_id in (select public.current_community_ids()))
```

So the ten new surfaces are *not* exposed by the unscoped-admin hole, and this plan does not have to
wait for §1.2 to land. It does mean this stream must not define `current_association_id()` itself —
that name belongs to §1.2. `0010` uses a deliberately distinct helper, `current_community_ids()`,
which returns a set because a person may belong to more than one community. When §1.2 lands, adopting
it is a one-line change per policy, or nothing at all.

**Where the two streams touch, they compose.** The fixed `handle_new_user()` owns the profile INSERT
and defaults every new profile to `RESIDENT`; `0010`'s sync trigger owns every subsequent change to
`profiles.role`. Different moments in a row's life, so neither overwrites the other — and the fixed
version is *more* correct under `0010`, because the role now has a real source to come from.

---

## 2. How the frontend constraint is met now

We cannot change `frontend/src/`. So the FastAPI DTO layer absorbs every mismatch, and
**two compromises I withdrew last session come back** — correctly, because the premise changed again:

| | Last session (frontend changeable) | Now (frontend fixed) |
|---|---|---|
| **R24** `timeAgo` | dropped; frontend formats | **restored.** The DTO emits `timeAgo` **and** an ISO instant. Consequence stands: those responses are `Cache-Control: no-store`. On the meeting agenda. |
| **R23** label + id | transition measure | **permanent for now.** Every DTO carries the frontend's display string *and* the id. Extra keys are ignored by the frontend, so this is zero-risk. |
| **C1** free-text assignee | select over staff | **accepted as free text.** `assignee_label text` plus a nullable FK. On the meeting agenda. |
| **C2** N:M categories | one-to-many recommended | **join table.** `Departments.jsx:211` produces N:M and we cannot change it, so the schema must accept what the UI emits. SLA ambiguity gets a deterministic tie-break (lowest `sla_hours` wins) and goes on the agenda. |

**C2 is now the third position I have taken on it.** Join table → one-to-many → join table. The
reasoning is not circular, the premise moved twice: it turns on whether the UI can be changed, and
that answer changed twice. The SLA ambiguity I raised is real and unresolved — a tie-break is a
workaround, not an answer, which is why it is agenda item 2.

---

## 3. The schema decision

Three options for reconciling §0.2. **Recommendation: additive now, rename by agreement.**

| Option | Verdict |
|---|---|
| Build the dashboard on the live names (`associations`, `apartments`) and treat the ERD as fiction | Rejected. The ERD is the milestone-1 submission and the class diagram matches it. |
| Rename everything to ERD names first | Right destination, wrong time. It touches `auth.py`, `invitations.py`, both repositories and the access-token hook — all auth code, which is the area we were told to leave alone. |
| **Add dashboard tables with ERD names; keep the four live tables; publish a naming map; rename later by agreement** | **Chosen.** Unblocks all ten surfaces immediately, touches no auth code, and the rename stays a single mechanical migration. |

**But `community_memberships` lands now, in step 2, not later.** Every dashboard table needs an actor
FK — `raised_by`, `created_by`, `assigned_to`, `approved_by`. Pointed at `profiles`, all of them need
repointing when memberships arrive; pointed at `community_memberships`, they never move. This is the
same cheap-now-invasive-later argument as R4, and it applies with more force here.

**The coordination cost is zero, which is the point.** Keep `profiles.role` as a compatibility column
maintained by a trigger from the membership row. The access-token hook, `jwt_role()`, `is_admin()`
and every existing guard keep reading `profiles.role` and **no auth code changes at all.**

---

## 4. Build order

Each step is one PR. Steps 1–2 ship no endpoints.

**All nine steps are written as of 2026-07-30** — eight migrations (`0010`–`0017`), 70 operations across
55 paths, 275 tests. **No migration has been applied to any database and no verification query has ever
been run**, which is now the whole remaining risk in this workstream (`DECISIONS_NEEDED.md` E1, F1).

### ~~Step 0 — Security~~ — *reassigned*
§1.1 and §1.2 are owned by the auth/security developer, in parallel. Not in this stream. The
regression test that matters to us — *an admin of community A reads zero rows of community B* — is
still written here, against the dashboard tables, because §1.4 makes those tables independently
scoped.

### Step 1 — `0010_memberships.sql` ✅ **written, not yet applied**
`community_memberships` and `unit_residencies` in ERD shape, backfilled from `profiles.role` /
`association_id` / `apartment_id`; the trigger that keeps `profiles.role` correct as a compat column;
community-scoped RLS; composite FKs (R4). Three verification queries are in the file footer.

Two things in it are worth knowing about because they are judgement calls, not transcription:

- **`is_primary` is granted to exactly one occupant per flat during backfill** — the earliest-created.
  `unit_residencies_primary_uq` permits one, and flagging every occupant primary would make the index
  reject all but the first, silently dropping the rest of the household. Found by writing the
  constraint and the backfill together rather than in separate steps.
- **Flats are created from `profiles.apartment_id` on first reference.** That free-text column holds
  codes like `B-1204` for flats that may have no `apartments` row, because the frontend never had a
  flat-creation step. Backfill creates them, matching the find-or-create rule the API will use.

### Step 2 — `0011_dashboard_core.sql` ✅ **written, not yet applied**
Ten tables: `departments`, `complaint_categories`, `department_categories`, `staff_assignments`,
`complaints`, `complaint_comments`, `complaint_read_receipts`, `complaint_attachments`, `notices`,
`community_modules`. R4 composite FKs and R3 `updated_at` triggers throughout, community-scoped RLS,
and seeding of the five categories and ten module rows per community. Three verification queries in
the footer.

**Four assumptions are recorded in the migration header as `A1`–`A4`**, so they are visible in the
schema rather than only in a doc. Each is cheap to reverse while the file is unapplied.

- **A1 — role vocabulary (open decision 2): not prejudged.** `public.user_role` is untouched. Staff
  `rank` and `job_title` are plain text, not enum members, because they are department-local
  descriptions that never reach a JWT. Reconciling the enum stays a separate change.
- **A2 — SLA tie-break (open decision 3):** category override wins; else lowest `sla_hours` among
  active claiming departments. Encoded once in `resolve_category_sla_hours()`.
- **A3 — urgency multiplier: invented, needs a ruling.** R9 says `due_at` comes from "the category SLA
  and urgency" but no multiplier was ever specified. Assumed high = ½ SLA, medium = 1×, low = 2×,
  isolated in `complaint_due_at()`.
- **A4 — R1 is deliberately *not* applied.** See below.

#### A4 — a correction to this plan

This plan previously said R1's two partial unique indexes belonged on `apartments`, *"whose current
`unique (association_id, code)` has exactly the defect R1 describes."* **Reading the column, it does
not.**

R1 addresses a **block-relative** label — `101` recurring in every building — where a nullable
`building_id` makes NULLs distinct and lets duplicates through. But `apartments.code` is community-wide
by construction: the frontend builds it as `` `${tower}-${flatNumber}` ``, giving `B-1204`. The block
is already inside the string, so uniqueness per community is the correct rule, and swapping in R1's
two partial indexes would have **loosened a constraint that works today** — the opposite of R1's
purpose. R1 becomes relevant only if the ERD's separate `unit_label` column is introduced.

Found by opening the column rather than trusting the plan's own summary of it.

#### Three other decisions worth knowing about

- **`job_title` is stored, not derived from `rank`.** R8 splits rank from job title, which invites
  deriving the displayed string from the rank. The seed data proves that mapping is not a function:
  `dept-plumbing`'s head renders as `Supervisor`, `dept-facilities`' head as `Manager` — same rank,
  different label. Any derivation rule silently rewrites one of them.
- **`complaints.department_id` is stored, not derived.** Re-resolving the routing on every read would
  make an edit to the category mapping retroactively rewrite where past complaints went.
- **`complaint_categories.sla_hours` survives R5 as a nullable *override*.** C2 moved ownership to the
  join table, but keeping the override means a single explicit value ends the ambiguity for that
  category outright — the escape hatch if the frontend meeting rules that two owners are legitimate.
- **`notices.category` stays free text** while `complaint_categories` is a table. The difference is
  behavioural: a complaint category routes to a department and carries an SLA; a notice category is a
  display label with nothing attached.

### Step 3 — Read-only shell ✅ **written, imports clean, 14 existing tests still pass**
`GET /dashboard/admin`, `GET /communities/current`, `GET /residents`, `GET /notices`, in
`api/v1/routers/dashboard.py` → `services/dashboard_service.py` → `repositories/dashboard_repository.py`,
following the existing layering. Documented in [`API.md`](../API.md).

Conventions established here that every later surface copies:

| Convention | Where |
|---|---|
| `Page` envelope — `{items, total, page, pageSize, hasMore}`, identical when empty | `domain/dashboard_schemas.py` |
| `timeAgo` + ISO instant side by side, `Cache-Control: no-store` **per endpoint** | `core/formatting.py` |
| Label + id on every reference (`flat` + `unitId`) | `ResidentSummary` |
| One error envelope for *all* failures | `core/exceptions.py` |

**Three things found by running the code rather than reading it:**

- **The app would not have started on Windows.** `zoneinfo.ZoneInfo("Asia/Kolkata")` raises
  `ZoneInfoNotFoundError` unless the `tzdata` package is installed — at import time. Replaced with a
  fixed `UTC+05:30`, which is not a workaround: India has never observed daylight saving, so the
  offset holds year-round. `tzdata` becomes a real dependency only if a DST-observing community is
  ever supported.
- **There were three error shapes on the wire, not one.** `register_exception_handlers` claimed to
  handle uncaught exceptions but only registered `AppError`, so request-validation failures returned
  FastAPI's `{"detail": [...]}` and unhandled exceptions returned `{"detail": "Internal Server
  Error"}`. A client cannot parse errors generically against three shapes. Handlers added for
  `RequestValidationError`, `StarletteHTTPException` and bare `Exception`; the 500 message is
  deliberately fixed, since an exception string can carry a table name or a connection string.
- **`email` on the residents list is a real gap, not an omission.** `profiles` has no email column —
  the address lives in `auth.users` and needs the service-role key. Returned as `null` and documented,
  with `profiles.email` to be added in step 4.

**Two deliberate compromises, both recorded in `API.md`:**

- **`/auth/*` is snake_case, everything else camelCase.** The frontend reads camelCase and cannot
  change; the auth DTOs are being edited in parallel by the security workstream, so converting them
  during this change would be a drive-by edit to someone else's in-flight work.
- **`pendingRequests` and `collection` are hardcoded zeros** until steps 4 and 7. Present from day one
  so the response shape does not change later, and flagged as placeholders in `API.md` rather than
  looking like real counts.

### Step 4 — People ✅ **written; 57 tests pass (was 14)**
`0012_people.sql` plus `GET /admins`, `PATCH`/`DELETE /residents/{id}`, and the three
`/registrations` endpoints. `dashboard.pendingRequests` and `residents[].email` stop being
placeholders. Documented in [`API.md`](../API.md) §6.

**The finding that shaped this step: PostgREST has no client-side transaction.** Every
`.table(...).insert()/.update()` is its own transaction, so any operation spanning two tables from
FastAPI can half-succeed. Approving a registration is exactly that shape — mark the request approved
*and* create the invitation — and a crash between them leaves a request approved that nobody can act
on, unrecoverable from the UI. **The only way to get atomicity through PostgREST is a Postgres
function called via RPC**, so `approve_registration_request`, `reject_registration_request` and
`deactivate_membership` live in SQL. Each takes a row lock, so two admins clicking Approve at the same
instant serialise and the second gets a 409 instead of minting a duplicate invitation.

Those functions are `SECURITY DEFINER`, which means **RLS does not run for them** — so each performs
its own authorization check as its first act. A `SECURITY DEFINER` function without an explicit check
is a hole with an API in front of it.

**Not everything got an RPC, and the distinction is deliberate.** `PATCH /residents` also writes two
tables but stays plain: a partial failure there leaves some fields updated and others not, which the
admin can see and retry. There is no invariant between the two writes. Approval has one.

**Three product decisions worth flagging:**

- **Approval mints an invitation; it does not create an active account.** The frontend's
  `acceptRequest` creates an `Active` resident immediately. We cannot, because the invite token is a
  mandatory second factor — a standing ruling. The admin still sees the request leave the pending
  list, which is what the screen reacts to.
- **"Remove resident" deactivates, it does not delete.** Complaints, invoices and payments reference
  the membership; deleting the row would cascade them away or fail. There is no hard-delete endpoint.
- **An admin cannot remove their own membership** — 409. There is no recovery path in the product from
  locking a community out of its own dashboard.

**A live frontend bug, found while building approval.** `createPendingRequestsSlice.js:36` builds
`` `${tower}-${flat}` ``, but seeded requests already store `flat: 'C-505'` — so approving a seeded
request yields **`C-C-505`**, while a form-submitted one (bare `505`) yields `C-505`. Two code paths
disagree about what `flat` holds. Absorbed by `app/domain/units.py` (13 tests), raised as agenda
item 8.

**`profiles.email` is backfilled but not self-maintaining.** Keeping it current for new users belongs
in `handle_new_user()`, which the auth workstream owns — so it is **not** edited here. The API writes
the address on the paths it controls. **Coordination item for the auth owner:** add `email` to
`handle_new_user()`'s insert. Their fix to that function does not otherwise collide — invite redeem
sets the role explicitly afterwards (`invitation_service.py:187`), so dropping the metadata role is
safe for our paths.

### Step 5 — Complaints ✅ **written; 80 tests pass**
`0013_complaint_events.sql` plus six endpoints: list, detail, `PATCH`, comments, read receipts,
attachments. Documented in [`API.md`](../API.md) §7.

**Two gaps in `0011` that only surfaced on reading the frontend closely:**

- **`complaint_events` was never created.** R9 resolved "management notes" with *"no column —
  `complaint_events` already has `note`"*, but that table existed only in the ERD. The frontend keeps
  `comments[]` **and** `timeline[]` as separate things, and the admin's "Resident-visible Update" box
  writes the timeline. Created in `0013`, and **append-only structurally** — no `UPDATE` or `DELETE`
  policy exists, so it cannot be edited even by an admin. An event that can be edited stops being
  evidence.
- **`complaints.location` was missing** — `raiseComplaint` stores a free-text "where in the building",
  distinct from the flat the complaint belongs to.

**A3 is retracted.** `0011` assumed `due_at` = category SLA × an urgency multiplier (high 0.5×,
low 2×). The multiplier was invented, and reading `createComplaintsSlice.js:5` showed it was also
wrong: the frontend already computes `expectedResolutionAt` from **urgency alone** — High 24h,
Medium 48h, Low 72h — ignoring the category.

So the product has **two independent SLA systems that never meet**: `departments[].slaHours` (4–48h)
and this urgency table. They never collide today only because complaints do not reference departments
in the frontend at all. A Low-urgency security complaint is due in 72h by one rule and 4h by the
other — **an 18× disagreement**. New rule: category override → department SLA → urgency table, with
no multiplier, since urgency already picks the fallback. Which system *should* win is a product
question — `DECISIONS_NEEDED.md` A1.

**Two more things worth knowing:**

- **The admin can edit the deadline directly** — `Complaints.jsx` has a `datetime-local` input for
  "Expected Resolution". So `due_at` is writable, not purely derived.
- **`reopened` and `closed` render as `Pending` and `Resolved`.** The frontend's status select has
  three options and `reopenComplaint` sets status back to `Pending` while incrementing a counter. The
  database keeps the distinction the UI does not show, rather than discarding it to make a mapping
  table symmetrical.

### Step 6 — Departments and staff ✅ **written; 111 tests pass**
`0014_departments.sql` plus ten endpoints: department CRUD, roster replace/add/patch/remove, and the
category list. Documented in [`API.md`](../API.md) §8.

**The archive rule as written above was wrong.** It said a department "cannot be archived while it
owns unresolved complaints". Reading the screen shows the frontend blocks **deletion** on that
condition and offers **deactivation as the escape hatch** — `Departments.jsx:569` renders a
"Deactivate" button precisely when deletion is refused. Guarding deactivation as well would remove
the only remaining action and leave the admin holding a department they can neither delete nor
deactivate. **So the guard is on `DELETE` alone**, and the count is taken inside the deleting
transaction so a complaint raised mid-check cannot slip through. Raised for confirmation as
`DECISIONS_NEEDED.md` A11.

**Three things reading the frontend settled that the resolutions did not:**

- **`head` is a name, not a link.** `departments[].head` is free text that also appears in `staff[]`.
  `0011` modelled the head as `staff_assignments.rank = 'head'` (R8), which is the better shape, so
  naming a head **promotes** the matching roster row — or creates one when nothing matches — and
  demotes the incumbent in the same transaction. The partial unique index makes that ordering
  load-bearing: the demotion has to be its own statement.
- **The two department-create screens disagree about categories.** `Departments.jsx:22` is a fixed
  checkbox list of six; `CreateDepartment.jsx:79` is a free-text box whose placeholder is
  *"e.g. Leaking pipes"* — a symptom, not a category. `0011` seeds five, and `Others` is not among
  them. Categories are therefore **upserted by name**, so both screens work; the cost is that a typo
  becomes a new category. Raised as B9.
- **Removing a staff member deactivates the row.** `complaints.assignee_label` records staff by name
  (C1), so deleting the row turns every past assignment into an unattributable string. The partial
  head index only constrains *active* rows, so a deactivated head frees the slot.

**Two implementation notes worth carrying forward:**

- **Reads go through views, not RPCs.** A list endpoint needs filtering, ordering, paging and an exact
  count; PostgREST gives all four on a view for free. `security_invoker = true` (PG15+) is what keeps
  RLS applying to the caller — without it a view is a hole straight through RLS.
- **`GET /departments` embeds each roster** rather than leaving it to a second call, because the
  dashboard seeds its edit modal from the list row. One extra query per page, not one per department.

### Step 6a — API description as a maintained artifact ✅
`docs/openapi.yaml` now covers **all 33 operations**, generated by `backend/scripts/export_openapi.py`
and kept honest by `--check` plus `tests/test_openapi_spec.py`. Generated, never hand-edited:
a hand-maintained spec drifts the first time a field is renamed, and a stale spec is worse than none
because clients generate types from it. `API.md` is not replaced by it — a generator cannot say why a
delete is really a deactivation.

### Step 7 — Money ✅
`0015_money.sql` plus ten endpoints: invoice list, collection summary, issue, detail, record payment,
void, maintenance run, payment log, and billing settings read/write. Documented in
[`API.md`](../API.md) §9.

**Liability attaches to the unit, not the person** — and that is structural, not a convention.
`invoices.unit_id` is NOT NULL and there is no membership foreign key, so a resident who moves out
cannot take the flat's arrears with them and a new occupant cannot get a clean slate by moving in.
The `userId` the dashboard reads is the flat's *current* occupant, resolved at read time for display.

**The step-4 line about the first invoice was overtaken, not skipped.** `0012` recorded that
*"approve creates residency AND first invoice in one transaction"* would be completed here. It is
not, because the premise changed: approval mints an **invitation**, not a resident, so nobody has
moved in at that moment. Seeding an invoice there would put a receivable against a flat that may
never be occupied — money nobody owes, in the admin's receivables tile. Billing is explicit instead,
per occupied unit per period. Raised as A13/A14.

**What reading the frontend found:**

- **There is no maintenance amount anywhere in the product.** Not in a screen, not in the ERD. It is
  the literal `4250` inside an approval handler. `community_billing_settings` is a new table with no
  ERD counterpart, and a billing run with no amount configured is **refused** rather than falling
  back to the demo constant. Raised as A13 and agenda item 12.
- **No screen can bill anybody.** The Maintenance screen lists invoices and shows three tiles; there
  is no invoice-creation, offline-payment, billing-run or rate-setting UI anywhere. The endpoints
  exist regardless — agenda item 12, the largest gap found so far.
- **The money tiles are summed in the browser**, so they will report the total of one page the moment
  the list pages. `GET /invoices/summary` exists to replace that — agenda item 11.

**Three implementation notes worth carrying forward:**

- **The double-billing guard is an index, not a check.** `(community, unit, period) where type =
  'maintenance' and status <> 'void'`. A service-layer check loses the race between two admins; the
  index does not, and a repeat run reports every flat as `skipped`.
- **Money needs no optimistic concurrency, for a structural reason.** No balance is ever written by
  the API: `record_payment` locks the row, recomputes the balance from the payment rows, and a CHECK
  rejects any balance that disagrees with its own status. There is no read-modify-write to lose.
- **`overdue` is derived, never stored.** A stored flag is correct only until the next midnight, and
  a status that is legal to store invites someone to store it — so it is out of the CHECK entirely.
  An ERD deviation, recorded as D6.

### Step 8 — Amenities ✅
`0016_amenities.sql` — seven tables, four views, twenty-one functions — plus twenty-two endpoints across
the catalogue, bookings, approvals, the booking ledger and reports. Documented in [`API.md`](../API.md)
§10.

The four service modules were the cleanest seam in the codebase, and they turned out to be the least
translation of any surface so far: `bookingStatuses.js`, `ledgerStatuses.js` and
`bookingTimelineStates.js` already separate the machine value from its label, so booking status,
payment status, booking type and reason codes pass through unchanged. Only three vocabularies
differ — booking mode, amenity status, and weekdays (names on the wire, ISO numbers stored, so the
booking rules can be evaluated in SQL without depending on the server's locale).

**What reading the frontend found:**

- **There are two unrelated amenity products.** `features/amenities/` (114 files) and
  `data/amenities.js` + `createAmenitiesSlice.js` (3 files) share no ids, no field names and no status
  vocabulary, and both are live. **No backend can serve both shapes at once** — the one item on the
  frontend agenda where "we already absorbed it" is not available. Raised as A17 and agenda item 14.
- **The cleaning buffer makes shared capacity unreachable.** `validateBookingSlot` applies buffers in
  every mode, so the seeded gym — capacity 24, buffer 15 minutes — accepts exactly one booking at a
  time. The buffer here applies only between exclusive uses, which means **the API accepts bookings
  the demo refuses**: A18 and agenda item 15.
- **A three-day request is approved one day at a time**, so an admin can approve Monday and reject
  Tuesday. One decision now covers the request; the row needs to render `dayCount` to say so. Agenda
  item 16.

**Three implementation notes worth carrying forward:**

- **The ERD's overlap note is only correct for exclusive amenities.** A blanket exclusion constraint
  would make every shared amenity single-occupancy and `capacity` a number nothing reads. Overlap is
  guarded by a scoped `EXCLUDE USING gist` **plus** a trigger holding an advisory lock, because an
  `EXCLUDE` predicate is per-row and cannot express "conflict if *either* side is exclusive", nor
  count.
- **Generated columns are filled after `BEFORE` triggers run.** The guard recomputes its own ranges;
  reading `NEW.blocking_slot` would have given NULL, and every `&&` would have returned NULL — a
  guard that passes everything while looking like it checks.
- **The privacy boundary had to be a table boundary.** A resident must see that a slot is taken
  without seeing who took it, and RLS cannot hide a column — so occurrences carry no personal data and
  the series row that names the requester is readable only by them and by admins.

### Step 9 — Settings ✅ — **the build order is complete**
`0017_settings.sql` — two tables, two views, five functions, six added columns — plus five endpoints
and six new fields on `/billing-settings`. Documented in [`API.md`](../API.md) §11. **275 tests pass**
(was 237); `openapi.yaml` now covers **70 operations across 55 paths**.

This step's one-line brief — *"Only `community_modules` and real community settings. Billing and late
fines are not settings"* — turned out to be right about the boundary and to understate the work behind
it, because the screen it serves has never saved anything.

**What reading the frontend found:**

- **The admin Settings screen persists nothing.** `Settings.jsx` is 135 lines: four `useState` toggles
  and a `handleSave` that shows a success toast. No store slice, no service module, no `persist` entry.
  **So this is the only step with no existing data shape to reproduce — the field names are ours**,
  which is why it went to the frontend team as agenda item 17 and B17 rather than just being built.
- **The four toggles are four different kinds of thing.** Two are billing (and land in
  `community_billing_settings`, where step 7 already put money — this is what the brief's "billing and
  late fines are not settings" means in practice); two describe features with no backend at all. **One
  table would have been the mistake.**
- **Two of the four, plus both billing toggles, are read by nothing.** There is no visitor table, no SMS
  provider, no scheduler and no fine engine. They are stored because the screen currently *loses* them;
  `API.md` §11 says so plainly rather than letting it be discovered. A22, A23.
- **The onboarding wizard promises a screen that does not exist**, and `enabledModules` is read only
  inside the flow that writes it — `AdminLayout.jsx:32-43` is a fixed ten-item nav array. Agenda item 6
  is now the only item where the backend is finished and the frontend half is untouched.

**Two things this step deliberately did not do:**

- **No module enforcement.** `amenities-booking` ships **disabled** (`defaultEnabled: false`, seeded that
  way by `0011`), so enforcing would `403` **all twenty-two step-8 endpoints on every community that
  exists** — a data-driven outage, not a feature. And six of the ten modules have no backend to gate, so
  the rule would be real for four keys and decorative for six. `module_catalogue.backend_status` reports
  the state honestly instead. A24.
- **No community rename.** `associations` is the one table this plan touches whose admin write policy
  carries no community clause (§1.2), and a rename would be the first of seventy operations to depend on
  it. An admin cannot fix a typo in their community's name; that gap is deliberate and waits for the auth
  workstream. C7.

**Three implementation notes worth carrying forward:**

- **This step answers A10 and vindicates step 8 rather than reversing it.** `community_settings.timezone`
  now exists. A booking made for 07:00 must still read 07:00 after somebody *corrects* a wrong timezone,
  which is only true because `0016` stores wall-clock `date` + `time`. The timezone unlocks what needs an
  absolute instant — and **nothing reads it yet**, because adopting it changes the date strings on every
  screen at once and deserves its own change.
- **The timezone is validated against `pg_timezone_names` inside the RPC, not by a `CHECK`.** A `CHECK`
  must be immutable; the timezone catalogue is host-loaded and changes between Postgres releases.
- **A toggle that claims to be on with nothing behind it is prevented below the API.** Two cross-field
  `CHECK`s plus a `BEFORE` trigger raising `HB409`, rather than a validator a second writer could skip.
  Silently ignoring the key would have returned `200` and let the toggle spring back on the next read —
  the bug the current screen already has in another form.

---

## 5. Five-gate check

| Gate | Impact |
|---|---|
| **Frontend** | **Zero files changed**, through step 9 — the whole build order, with `frontend/src/` never touched. The DTO layer matches the seeded shapes exactly, including `timeAgo`, the free-text assignee and `payments[]` field for field. **Seventeen** things we cannot fix from the backend are on the meeting agenda; item 12 — no screen can bill anybody — is the largest gap, item 14 — two unrelated amenity products — is the largest open question, and **item 17 is the one where their answer changes our field names**, because the Settings screen persists nothing and so supplied no shape to match. |
| **ERD / DBML** | Steps 2–3 add ERD-shaped tables. The live schema still diverges in four table names (§0.2) until the rename is agreed. **The ERD is not edited by us** — teammates own it. Step 7 diverges from it in three named ways plus one new table with no counterpart (`community_billing_settings`) and one new column (`invoices.title`); all five are written up as `DECISIONS_NEEDED.md` D6 and A13 for its owner to accept or reject, rather than edited in. Step 8 diverges in five more (D7), the largest being `amenity_settings` in place of the versioned, weekday-scoped `amenity_rules`, which covers 8 of the ~30 fields the settings tab saves and has no screen writing either of its axes. Step 9 diverges in four more (D8) — the ERD's `enabled_modules jsonb` is a table here, because a jsonb array cannot record when a module was switched off or by whom; currency, the invoice prefix and the six billing toggles stay with money in `community_billing_settings`; and `module_catalogue` has no ERD counterpart at all, since the ERD names a home for the module *selection* and none for the module *definitions*. **One ERD correction requested rather than absorbed:** it says onboarding selects nine feature modules; there are ten, in `onboardingModules.js`, in `0011` and in the catalogue. |
| **Class diagram** | Unchanged by this plan. R29–R31 remain open requests to its owner. Note it currently matches the ERD, not the live database. Step 9 adds two entities it has no counterpart for — `CommunitySettings` and `ModuleCatalogue` — and since the diagram already tracks the ERD rather than the schema, they are listed in D8 for its owner alongside the ERD changes rather than drawn in by us. |
| **Design of components** | §3's department rules and §6's complaint requirements drive steps 6–7. Its §1 per-tab session claim stays prototype-only. No edits by us. Step 9 checked it and found module selection specified **only as an onboarding step** — §2 says *"allow the administrator to select the functional modules required by the association"* and nothing anywhere says they may change that choice later. So the frontend's own promise that features *"can be changed later from the Admin Settings page"* is not backed by the component design either; `PATCH /settings/modules` implements a capability no design artifact asked for, and the four toggles are specified by no artifact at all — which is part of why their field names had to be invented. |
| **Supabase** | RLS as the enforcement boundary, community-scoped from step 1; access-token hook already in place and unchanged; `auth.admin.createUser` for staff in step 6; Storage for attachments in step 5; **no `pg_cron` for invoices after all** — this plan assumed a scheduled job would flip invoices to `overdue`, but a stored overdue flag is correct only between runs, so the view derives it from the due date and the balance and there is nothing to schedule (D6); `btree_gist` exclusion constraints for amenities in step 8 — **used, and found to be only half the answer**: an `EXCLUDE` predicate is per-row, so it cannot express the exclusive-vs-shared rule or count against capacity, and a trigger holding `pg_advisory_xact_lock` does the rest. Step 9 leans on Postgres for two more things a service layer would have done worse: `pg_timezone_names` validates the community timezone (so the catalogue, not a list we wrote down, is the authority), and cross-field `CHECK`s plus a `BEFORE` trigger make a billing toggle unswitchable without the number it acts on. **Still no `pg_cron`** — `auto_billing_enabled` is stored policy and nothing schedules anything (A22). FastAPI stays a thin typed layer, per `backend/README.md`. |

---

## 6. Decisions needed before step 2

1. ~~**Confirm additive-now / rename-later**~~ — **proceeded on this assumption** rather than blocking,
   since it touches no auth code and the rename stays one mechanical migration either way.
   `0010_memberships.sql` is written but **not applied**, so reversing costs deleting one file.
2. **Role vocabulary** — the live enum has `TECHNICIAN`, the ERD has `worker`, the frontend renders
   `Admin | Resident | Security | SecurityManager`. Three vocabularies. `displayRole` maps the third;
   the first two need one owner. **Not prejudged** — `0011` keeps staff rank and job title out of the
   enum entirely (A1), so this decision stays free.
3. **C2 SLA tie-break** — lowest `sla_hours` wins when two departments claim a category. **Implemented
   as A2**, in one function, pending the frontend meeting.
4. **Urgency multiplier for `due_at` (new, A3)** — high = ½ SLA, medium = 1×, low = 2×. **Invented by
   this migration.** R9 required urgency to affect the deadline but never said how. Needs a product
   ruling; it is the one assumption here with no evidence behind it.
5. Items 2–8 from [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §8 remain open.
