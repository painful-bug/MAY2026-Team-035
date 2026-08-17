# Apply runbook — the seven unapplied migrations

This is a step-by-step guide for the repository owner to apply, by hand, the seven
migration files that exist in `backend/supabase/migrations/` but are not yet
applied to the linked hosted Supabase project. It assumes you have the
Supabase dashboard and/or a `supabase` CLI linked to the project
(`project_id = "homebandhu"`, see `backend/supabase/config.toml`), and general
competence with Postgres and Supabase, but no context on this branch's work.

**Static verification of the original six files — parsing, statement-by-statement
idempotence, and cross-file dependency order — was done before this runbook was
written and is summarized at the bottom, in "What was checked before this was
written." Nothing here was run against a database; that verification is
necessarily static.**

The seven files, in the order you must apply them (filename order — this is also
dependency order, confirmed below):

1. `20260812090000_notification_audiences.sql`
2. `20260812090100_skills_and_categories.sql`
3. `20260812090200_staff_provisioning.sql`
4. `20260812090300_complaint_department_routing.sql`
5. `20260812113000_professional_membership_symmetry.sql`
6. `20260812120000_work_order_notification_urls.sql`
7. `20260812160000_legacy_status_defaults.sql` — added 2026-08-12 after the
   owner hit the live failure it fixes. **Independent of files 1–6**: if you
   have not applied the others yet and just need community creation unblocked,
   this one can be applied on its own, in any order relative to the rest.

---

## 0. Preconditions

### 0.1 Back up first, or confirm PITR covers you

If the project is on a plan with Point-in-Time Recovery, confirm it is enabled
and note the current timestamp before you begin (Dashboard → Database →
Backups → Point in Time Recovery). If it is not, take a manual backup now
(Dashboard → Database → Backups → "Create a backup now", or `pg_dump` against
the connection string). None of the seven files contains a `drop table`,
`drop column`, or `delete` — see §5 below — so the realistic risk this backup
covers is an interrupted mid-file apply on file 4, the one with the most
DDL surface (a new column, two new tables, one dropped-and-rebuilt function;
files 2 and 3 also create tables, but nothing they touch is dropped-then-
recreated).

### 0.2 Confirm what is already applied

Run this in the SQL Editor (or `psql "$SUPABASE_DB_URL"`):

```sql
select version
  from supabase_migrations.schema_migrations
 order by version;
```

Confirm the highest version present is `0047` or one of the three
`20260811…` timestamps (`162409`, `163408`, `192511`) — i.e. confirm none of
the seven files below already has a row here. If any of the seven is already
listed, stop and re-read `backend/supabase/migrations/README.md`'s boundary
paragraph before proceeding; this runbook assumes a clean start from exactly
that boundary.

If you are using the Supabase CLI linked to this project instead of the SQL
Editor, the equivalent is:

```sh
npx supabase migration list --linked
```

which marks each local file as applied or not against the remote.

### 0.3 Decide how you will apply them

Two options, either is fine:

- **CLI**: `npx supabase db push --linked` from the `backend/` directory
  applies every not-yet-applied migration in filename order in one run. This
  is the simplest option and matches the order below automatically.
- **SQL Editor**: open each file in this repository, paste its full contents,
  and run it. Do this one file at a time, in the order above, and do not move
  to the next file until you've done that file's post-check (below).

The per-file sections below assume the SQL Editor / one-at-a-time path, since
that is what lets you read each file's `raise notice` output and run its
post-check before moving on. If you use `supabase db push`, run all seven in one
shot, then work through every post-check in §1–§7 afterward, and separately
scroll the CLI output for the `NOTICE` text described in §5 — `db push` prints
notices from every file it runs, not just file 5's.

---

## 1. `20260812090000_notification_audiences.sql`

**What it does.** Splits two notification audiences that were "every admin and
every manager in the community" (`notify_community_staff`) into who can
actually see the resulting link: `settle_amenity_booking_payment` now tells
only admins that an amenity booking was paid (no department owns amenities);
`record_security_incident` now tells admins and, separately, only the
managers of **security-kind** departments about high/critical incidents.
Rewrites both functions' full bodies in place (`0033` and `0040` are applied
and immutable, so this is a `create or replace` on each, not an edit to the
original file).

**What to expect.** No table or index changes — this file is two
`create or replace function` statements, two `comment on function`
statements, and one `grant execute` (the second function,
`record_security_incident`, gets a comment but deliberately no grant —
it is service_role-only and this file restates nothing about that). It
should run silently with `CREATE FUNCTION` / `COMMENT` / `GRANT`
acknowledgements and nothing else.

**Post-check.**

```sql
-- Confirm the amenity-payment notification no longer CALLS notify_community_staff.
-- (Match on `perform public.…`, not the bare name: the body keeps a deliberate
-- `-- CHANGED: was notify_community_staff` comment, and comments inside the
-- $$…$$ body are part of prosrc — a bare-name not-like is always false.)
select prosrc like '%perform public.notify_community_roles%'
       and prosrc not like '%perform public.notify_community_staff%' as looks_right
  from pg_proc
 where proname = 'settle_amenity_booking_payment';
-- expect: looks_right = true

-- Confirm the security-incident notification now loops security-department managers
select prosrc like '%d.kind         = ''security''%' as splits_by_department_kind
  from pg_proc
 where proname = 'record_security_incident';
-- expect: splits_by_department_kind = true
```

---

## 2. `20260812090100_skills_and_categories.sql`

**What it does.** Adds `department_skills` (which trades a department has
explicitly claimed, empty by default for every department including existing
ones — no backfill), a trigram suggestion index on `skills.name`, four read
functions (`search_skills`, `community_categories`, `department_skill_list`,
plus the replaced `department_overview` view), and four write functions
(`can_author_skills`, `create_skill`, `add_department_skill`,
`remove_department_skill`, `set_department_skills` — five, correcting the
count). On its way past, it also fixes `department_overview`'s head-of-department
lateral join, which has matched `rank = 'head'` since `0035` renamed that rank
to `'manager'` and has therefore returned null for every department since.
Finally it **changes the behavior** of `search_hireable_service_providers`
(rebased onto `20260811162409`'s version, not `0035`'s): the skills a
department can hire for are now the union of its category-derived skills and
its own directly-claimed skills, rather than the category path alone.

**What to expect.** `CREATE TABLE`, two `CREATE INDEX`, `ALTER TABLE`,
`CREATE POLICY`, `GRANT`, `DROP VIEW` + `CREATE VIEW`, `GRANT`, then nine
`CREATE FUNCTION` + `COMMENT` + `GRANT` groups. No notices, no errors expected.

**Post-check.**

```sql
-- The table exists and starts empty
select count(*) from public.department_skills;  -- expect: 0

-- The suggestion index exists
select indexname from pg_indexes where indexname = 'skills_name_trgm';

-- department_overview's head fields are no longer permanently null for a
-- department that actually has an active manager on staff_assignments
select id, name, head_name, head_staff_id
  from public.department_overview
 where head_name is not null
 limit 5;
-- expect: at least the departments that have an active `rank = 'manager'`
-- staff_assignments row show a non-null head_name here

-- Hiring search now includes department_skills in its skill union
select prosrc like '%union%select distinct ds.skill_id%' as has_department_skill_union
  from pg_proc
 where proname = 'search_hireable_service_providers';
-- expect: has_department_skill_union = true
```

---

## 3. `20260812090200_staff_provisioning.sql`

**What it does.** Creates `staff_invitations` — how a manager or supervisor
comes to exist, since neither has a registration flow: an admin (or, for a
supervisor, the department's own manager) types a name and email, and that
person is admitted on first Google sign-in by matching the verified email.
Adds `invite_staff_member`, `revoke_staff_invitation`,
`update_staff_invitation`, `department_staff_invitations` (all callable by
authenticated users, gated by `can_manage_department`), and
`claim_staff_invitations` — the one function in the whole seven-file set that is
**revoked from `authenticated`**: it is called only by the backend's service
role, from `resolve_session`, because the email is the entire authorization
and must never come from a client-supplied value.

**What to expect.** `CREATE TABLE`, a `do $$ ... $$` block adding four
constraints (silent if it succeeds), three `CREATE INDEX`, `ALTER TABLE`,
`CREATE POLICY`, `GRANT`, then five `CREATE FUNCTION` groups, ending in
`REVOKE ALL ... FROM PUBLIC, ANON, AUTHENTICATED` for `claim_staff_invitations`
only. No notices expected.

**Post-check.**

```sql
-- The table and its four named constraints exist
select conname from pg_constraint
 where conrelid = 'public.staff_invitations'::regclass
 order by conname;
-- expect: staff_invitations_claim_check, staff_invitations_name_check,
--         staff_invitations_rank_check, staff_invitations_status_check
-- (plus the primary key and foreign keys Postgres names itself)

-- claim_staff_invitations is NOT callable by authenticated -- this is the
-- security-critical property of this file. Run this as an anon/authenticated
-- role (not the service role) and confirm it is refused:
select has_function_privilege(
  'authenticated', 'public.claim_staff_invitations(uuid, text)', 'execute'
);
-- expect: false
```

After this file, functionally verify by inviting a test manager from a test
department (Dashboard → SQL Editor, calling `invite_staff_member` as a
service-role query, or through the running app once deployed) and confirming
`select * from public.staff_invitations` shows a `pending` row.

---

## 4. `20260812090300_complaint_department_routing.sql`

**What it does.** Gives every complaint a `department_id` from the moment it
is raised: the resident's chosen category is matched through
`department_categories` first, the resident's own department pick is the
fallback, and "nobody" is a real third outcome that lands the complaint in a
new admin triage queue (`unassigned_complaints`). Adds
`resolve_complaint_department` (the routing rule, in one place),
`notify_complaint_staff` (replaces `notify_community_staff` on
complaint events — admins plus the *owning department's* manager, not every
manager in the community), `assign_complaint_department` (admin allots an
unrouted complaint, or the holding department's manager moves a routed one
out), the "this isn't ours" flow
(`complaint_department_requests`,
`request_complaint_department_change`,
`decide_complaint_department_change`), three read helpers
(`department_complaints`, `unassigned_complaints`, `community_departments`,
`department_change_requests`), and rebuilds `raise_complaint` (dropped by its
old 6-argument signature first, then recreated with a 7th `p_department_id`
argument — this is the one deliberate signature change in the seven files) plus
full-body replacements of `reopen_complaint`, `confirm_complaint_resolution`
and `add_complaint_comment` so their notifications stop going to every
manager too.

**This is the file with the most DDL surface** — a new column, an FK, an
index, two new tables, indexes and RLS on both. It is also the file with the
`drop function` + `create` pair (§5.4 covers what a mid-file failure leaves
here specifically).

**What to expect.** `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, a `do $$` FK
block, `CREATE INDEX`, `COMMENT`, then a long run of `CREATE FUNCTION` /
`COMMENT` / `GRANT` groups (`resolve_complaint_department`,
`notify_complaint_staff`), a `DROP FUNCTION` (for the old 6-arg
`raise_complaint` — this may say `DROP FUNCTION` or, if for any reason it does
not exist under that exact signature, print a `NOTICE ... skipping` line
instead), `CREATE FUNCTION` + `COMMENT` + `GRANT`
for the new 7-arg `raise_complaint` (the grant restates 0031's
authenticated grant on the new signature, since the drop discarded the old
one), `CREATE FUNCTION` +
`CREATE TABLE`/`CREATE INDEX`/`ALTER TABLE`/`CREATE POLICY` for the
department-change-request flow, and finally three more `CREATE FUNCTION`
groups for `reopen_complaint`, `confirm_complaint_resolution` and
`add_complaint_comment`. No notices expected.

**Post-check.**

```sql
-- The column and its FK exist
select column_name, data_type from information_schema.columns
 where table_name = 'complaints' and column_name = 'department_id';

-- raise_complaint now takes 7 arguments, not 6
select pg_get_function_identity_arguments('public.raise_complaint'::regproc);
-- expect: a 7-argument signature ending in "department_id uuid"
-- (if this instead errors "more than one function ... matches", the old
-- 6-arg overload was not dropped -- see the failure-mode note in section 5.4)

-- The new tables exist
select to_regclass('public.complaint_department_requests');

-- The triage queue is queryable (as an admin membership)
select * from public.unassigned_complaints('<a real community_id>');
```

Functionally: raise a test complaint against a category that maps to exactly
one department and confirm `department_id` is set; raise one against a
category that maps to none (or "Other") and confirm it appears in
`unassigned_complaints` for that community.

---

## 5. `20260812113000_professional_membership_symmetry.sql`

**What it does.** The other half of the separate-account rule. Until this
file, `register_service_provider` refused a profile that already held a
resident/manager/admin membership when registering as a professional, but
nothing refused the reverse order: a profile that registered as a
professional *first* could then be admitted as a resident/manager/admin
through an invite claim, an access-request approval, or (as of file 3 above)
a staff-invitation claim. This file rewrites
`enforce_professional_membership_mode()` — the trigger already firing on
every membership write — to refuse that direction too, with a new `HBSEP`
error code the API layer already knows how to shape into a 409
(`app/repositories/memberships_repository.py`,
`claim_resident_invite`).

**⚠️ This file's `do $$ ... $$` block runs a `raise notice` reporting any
row that already violates the rule it is about to start enforcing — READ THIS
OUTPUT.** It does not repair anything (deliberately: which identity to keep
is the account holder's decision, not a migration's), so if the count is
above zero you have existing accounts that will now fail on their next
membership-status update until someone resolves which identity they keep. In
the SQL Editor this appears as a yellow "NOTICE" line in the output pane, not
an error; in `psql` or `supabase db push` it appears on stderr, easy to miss
in a long combined run. If you used `db push` for all seven files at once, this
is one of the things to specifically scroll back for.

Expected count going in: zero (the state has been reachable for about a day,
against a small professional base) — but confirm it, do not assume it.

**What to expect.** `CREATE FUNCTION`, `REVOKE ALL`, then the `do $$` block
(read its `NOTICE` if any), then a `COMMENT ON FUNCTION` for
`search_serviceable_communities` (documentation-only — re-issues a comment
that had gone stale describing behavior `20260811162409` changed; no function
is redefined by this statement).

**Post-check.**

```sql
-- The new refusal is installed
select prosrc like '%HBSEP%' as has_symmetry_refusal
  from pg_proc
 where proname = 'enforce_professional_membership_mode';
-- expect: true

-- Re-run the notice's own query directly, to record the number for your own
-- records independent of scrolling apply output
select count(*)
  from public.community_memberships m
  join public.service_providers p on p.profile_id = m.profile_id
 where m.role not in ('worker', 'security')
   and m.status = 'active'
   and m.ended_at is null;
```

If this is nonzero, that is not a failed apply — the migration applied
correctly and is telling you about pre-existing data. Decide per account
which identity survives (see the file's own header for why the migration
does not decide this for you) before those accounts hit any future
membership-status update, or that update will now fail with `HBSEP`.

Functionally: attempt to claim a resident invite (or a staff invitation, or
an access-request approval) on a profile already holding a `service_providers`
row, and confirm you get a 409 with a "separate account" message rather than
a 500.

---

## 6. `20260812120000_work_order_notification_urls.sql`

**What it does.** Repoints the seven supervisor-facing work-order
notifications that linked to `/admin/departments?job=<id>` (the department
*list*, which has never read a `job` parameter) onto the triage screen that
now exists at `departments/:departmentId/work-orders?job=<id>` under
`/admin`, `/manager` and `/security-manager`. Six functions get their whole
bodies re-declared (`dispatch_ping_candidates`, `dispatch_auto_assign`,
`dispatch_failed_visit_escalation` from `0037`; `accept_work_order_offer`,
`complete_work_order`, `report_work_order_failure` from `0039`) — seven url
lines change across those six functions, nothing else. This file
deliberately does **not** restate any `grant`/`revoke`/`comment` — those
survive `create or replace function` untouched, and restating them from
memory is how a security posture gets silently flipped.

**What to expect.** Six `CREATE FUNCTION` acknowledgements, nothing else. No
notices, no grants, no comments in the output.

**Post-check.**

```sql
-- All seven dead links are gone, all seven live ones are present
select count(*) as dead_links
  from pg_proc
 where proname in (
   'dispatch_ping_candidates', 'dispatch_auto_assign',
   'dispatch_failed_visit_escalation', 'accept_work_order_offer',
   'complete_work_order', 'report_work_order_failure'
 )
   and prosrc like '%/admin/departments?job=%';
-- expect: 0

select sum(
  (length(prosrc) - length(replace(prosrc, '/work-orders?job=', ''))) 
  / length('/work-orders?job=')
) as new_links
  from pg_proc
 where proname in (
   'dispatch_ping_candidates', 'dispatch_auto_assign',
   'dispatch_failed_visit_escalation', 'accept_work_order_offer',
   'complete_work_order', 'report_work_order_failure'
 );
-- expect: 7

-- Grants are unchanged from before this file (0037's three stayed
-- service_role-only, 0039's three stayed granted to authenticated)
select proname, has_function_privilege('authenticated', oid, 'execute') as authenticated_can_call
  from pg_proc
 where proname in (
   'dispatch_ping_candidates', 'dispatch_auto_assign',
   'dispatch_failed_visit_escalation', 'accept_work_order_offer',
   'complete_work_order', 'report_work_order_failure'
 )
 order by proname;
-- expect: dispatch_* = false, accept_work_order_offer/complete_work_order/
--         report_work_order_failure = true
```

Functionally: trigger a dispatch escalation or a worker action in a test
department and click the resulting notification as the department's manager
— confirm it lands on the triage screen filtered to that job, not on the
department list.

---

## 7. `20260812160000_legacy_status_defaults.sql`

**What it does.** Fixes the live failure the owner hit on 2026-08-12: creating
a community through admin onboarding died with

```
new row for relation "communities" violates check constraint
"communities_status_canonical" ... Failing row contains (..., Active, ...)
```

The hosted database predates `0001_baseline.sql` — its legacy tooling created
the status columns with a title-cased default (`'Active'`).
`20260730163759_normalize_community_statuses.sql` normalized the existing
communities *rows* and added the canonical (lowercase) check constraint, but
left the column *default* untouched, so any insert relying on the default —
`create_founder_community` never names `status` — has violated the constraint
ever since. This file sets `communities.status` default to `'active'`, and
does the same for `units` (same legacy tooling, same RPC insert path, but no
constraint to make the failure loud: a title-cased unit is silently invisible
to the baseline's unit-belongs-to-community check at `0001_baseline.sql:217`,
which filters on the unit's `status = 'active'` when a resident invite or
access request names a unit) — including a row normalization for units, which
the 2026-07-30 file never covered. On a database created from the baseline
every statement is a no-op.

**Order note.** This file is independent of files 1–6 (it touches only column
defaults and unit rows; nothing in 1–6 reads or writes them). Applying it
first to unblock community creation, then 1–6 later, is fine.

**What to expect.** One `UPDATE n` (very likely `UPDATE 0` unless legacy
units exist), two `ALTER TABLE` acknowledgements, and one notice:
`communities.status default is now 'active'::text`.

**Post-check.**

```sql
select table_name, column_default
  from information_schema.columns
 where table_schema = 'public'
   and table_name in ('communities', 'units')
   and column_name = 'status';
-- expect: 'active'::text for both

select count(*) as title_cased_units
  from public.units
 where status is distinct from lower(btrim(status));
-- expect: 0
```

Functionally: retry the admin onboarding "Create community" step that failed —
it should now complete.

---

## 5x. If a file fails partway through

None of the seven files wraps its own statements in an explicit
`begin`/`commit`. When you run a whole file's text as one submission through
the SQL Editor or `psql -f`, Postgres treats it as one implicit transaction —
if any statement errors, everything that file did is rolled back and you are
back to the state before that file started. This is the common case and the
safe one: re-running the same file from the top is exactly correct, because
every statement in every one of the seven files is written to be safe to run
twice (see "What was checked before this was written" below) — `create table
if not exists`, `create index if not exists`, `create or replace function`,
`drop policy if exists` before `create policy`, and the one `drop function`
in file 4 drops a signature that, on a retry, no longer exists (so it becomes
a no-op) before recreating the one that does.

The one way to land in a **partial**, non-rolled-back state is running a
file's statements individually (one at a time, not as one paste) and stopping
between them, or applying via a tool that does not wrap the whole file in one
transaction. If you did that and stopped mid-file:

- **Files 1, 2, 3, 5, 6, 7**: every statement in each is independently
  idempotent (see the guard list above; file 7 is an `update` that matches
  nothing on a second run, two `alter ... set default`s that are safe to
  repeat, and a read-only `do` block). Just resume from wherever you
  stopped, or from the top of the file — both are safe.
- **File 4**: the same is true for every statement except the
  `drop function if exists public.raise_complaint(uuid, text, text, text,
  text, text);` / `create or replace function public.raise_complaint(...)`
  pair. If you stopped **between** the drop and the create, `raise_complaint`
  does not exist at all — the API's `POST /complaints` (or whatever endpoint
  calls it) will fail with "function does not exist" until you resume and run
  the `create` statement. Nothing else in the seven files depends on
  `raise_complaint`, so this is contained to that one endpoint and safe to
  leave mid-state briefly. Resuming from the `create or replace` statement
  (or re-running the whole file) fixes it.

If a statement genuinely errors (not just "you stopped"), read the error
text before retrying: `create or replace function` failing generally means a
real problem (a referenced object that does not exist — which the closure
check below found none of — or a syntax issue, which parsing already ruled
out), not something a retry alone fixes.

---

## 8. After all seven are applied

1. **Run the database advisors.** Dashboard → Database → Advisors (Security
   Advisor and Performance Advisor). New tables in this set
   (`department_skills`, `staff_invitations`, `complaint_department_requests`)
   all enable RLS with an explicit `select`-only policy and no write policy
   (writes are `security definer` functions) — confirm the Security Advisor
   doesn't flag any of the three as RLS-disabled or policy-less, which would
   indicate something went wrong in file 2, 3, or 4 respectively.

2. **Run the integration test file, if you have a local stack available.**
   `backend/tests/integration/test_service_professional_supabase.py` is the
   one pytest-based integration suite in that directory today (there is also
   `assert_service_proximity_plan.sql`, a plan-verification script the CI
   `database-browser` job runs separately with `psql`, not a pytest suite —
   between the two, that job's two verification steps are what "the two
   integration suites" in this directory means). Both need a local Supabase
   (`npx supabase start --workdir backend`, then `npx supabase db reset
   --workdir backend` to apply every migration including these seven) and
   `RUN_SUPABASE_INTEGRATION=1`:

   ```sh
   npx supabase start --workdir backend
   npx supabase db reset --workdir backend
   eval "$(npx supabase status --workdir backend -o env)"
   RUN_SUPABASE_INTEGRATION=1 uv run --project backend pytest -q backend/tests/integration
   psql "$SUPABASE_DB_URL" -f backend/tests/integration/assert_service_proximity_plan.sql
   ```

   Note this resets a **local** database by replaying every migration from
   scratch — it does not touch the hosted project you just applied these seven
   files to. It is a way to double-check the same seven files against a clean
   instance, not a step that needs to happen against the hosted project
   itself.

3. **Watch the CI `database-browser` job** on the next push to this branch
   (`.github/workflows/ci.yml`) — it does the same local reset-and-verify,
   plus a PostGIS query-plan assertion and a full Playwright browser smoke
   pass, against a fresh instance built from every migration in the repo,
   these seven included.

---

## 9. What becomes true once applied

Once all seven are live on the hosted project, these are safe to click through
and confirm by hand in the running app:

- **Skills UI**: a department's edit screen can add/remove skills by name
  (with suggest-as-you-type), and a department that has claimed a skill
  directly can now hire a service professional who holds it even with no
  matching complaint category.
- **Staff provisioning**: an admin (or a manager, for a supervisor) can
  invite a manager or supervisor by email with no separate registration
  step; that person is admitted as staff automatically on their first Google
  sign-in.
- **Complaint routing**: a newly raised complaint lands directly on the
  right department's queue when its category maps to exactly one department,
  falls back to the resident's own department pick otherwise, and shows up
  in a new admin triage queue when neither resolves it — plus a supervisor
  can flag "this isn't ours" and their manager can move it.
- **The symmetry rule**: an account already registered as a service
  professional is refused (409, not a 500) when it tries to also become a
  resident, manager or admin.
- **Fixed notification links**: clicking a work-order notification as a
  department manager (or security-department manager, for gate incidents) or
  admin now lands on a screen that shows the job or incident in question,
  not on a department list with nothing to do there.
- **Community creation works**: the admin-onboarding "Create community" step
  completes instead of failing on the `communities_status_canonical`
  constraint.

---

## What was checked before this was written

This section is provenance, not further instructions — everything below was
already done, statically, before this runbook existed. (The table below covers
the original six files. File 7, added 2026-08-12 after the owner hit the live
`communities_status_canonical` failure, was verified separately at the time it
was written: `pglast.parse_sql` clean, 4 statements, every statement
independently idempotent, and it names no object created by files 1–6.)

| Check | Result |
|---|---|
| All six files parse as valid PostgreSQL (`pglast.parse_sql`) | Pass, all six |
| Existing static migration test suite (`test_service_professional_migrations.py`, `test_unit_residencies_rls_migration.py`, `test_professional_membership_symmetry.py`, `test_work_order_notification_urls.py`) | 35 passed, 0 failed |
| Filename/dependency order (each file's references resolve to an earlier-sorting file) | Confirmed for all cross-references named in this file's own headers, and independently by grepping every function/table each of the six names against every earlier migration |
| Idempotence: every `create table`/`index`/`policy`/`function` is guarded (`if not exists`, `create or replace`, or `drop ... if exists` before `create`) | Confirmed statement-by-statement across all six; the one non-idempotent-looking pair (file 4's `drop function` + `create` for `raise_complaint`) is safe on retry because the drop targets the *old* signature, which no longer exists after the first successful run — see §5x |
| Code↔schema closure: every `.rpc("name", ...)` call in `app/repositories` and `app/services` (124 call sites, ~120 distinct names) resolves to a function created by some migration | Confirmed, zero unresolved names |
| The two full-body extractions in file 1 (`settle_amenity_booking_payment` from `0033`, `record_security_incident` from `0040`) preserve every line of the applied body other than the audience change | Confirmed by diff — no lost lines, only the described restructuring |
| The full-body extraction in file 2 (`search_hireable_service_providers` from `20260811162409`) is the applied text plus exactly the `department_skills` union | Confirmed by diff — zero missing lines, only the described addition |

**Coverage gap worth knowing about**: only files 5 and 6
(`professional_membership_symmetry`, `work_order_notification_urls`) have a
dedicated static test file. Files 1–4
(`notification_audiences`, `skills_and_categories`, `staff_provisioning`,
`complaint_department_routing`) have no equivalent
`test_*.py` — the parsing and body-preservation checks for those four in the
table above were done by hand for this runbook (and are reproducible with the
snippets embedded in this document), not by an automated suite that will
catch a future regression the way the other two files' tests would. That gap
is a candidate for its own follow-up; nothing above depends on closing it
before applying.

---

# Addendum — the two privilege migrations (pulled 2026-08-12)

Everything above concerns the original seven files, all of which are now
**applied and verified on the hosted project**. Two further migrations arrived
from a teammate after that runbook was written and are the only files in
`backend/supabase/migrations/` still unapplied:

1. `20260812190000_grant_service_role_data_access.sql`
2. `20260812200000_enable_authenticated_request_client_reads.sql`

**Apply them in that order** — filename order is also dependency order here,
though the coupling is weak (190000 touches only `service_role`, 200000 only
`authenticated`; neither reads anything the other writes).

**Why promptly, and not "next week":** until 200000 is applied,
`public.staff_assignments` on the hosted project has **RLS disabled** — the
repositories and the `department_staff_overview` view were written on the
assumption that it was enabled, and it never was.

**Ground truth as of 2026-08-12.** `supabase_migrations.schema_migrations` has
47 rows; the repository has 49 migration files; the two above are the
difference. Re-confirm with §0.2's query before you start.

**The SQL Editor will interrupt you.** Both files are almost entirely `grant`,
`revoke`, `alter` and `create policy` statements, so the editor's **"Potential
issue detected"** popup ("this query has destructive operation…") **will**
appear on submit for each file. That is keyword-matching, not analysis — answer
**"Run query"**. Neither file contains a `drop table`, `drop column`, `delete`,
`update`, or `truncate`; the only `drop` statements are four
`drop policy if exists` guards immediately followed by the matching
`create policy`. A successful run of either file acknowledges with
**"Success. No rows returned"** and nothing else — no rows, no notices.

---

## 10. `20260812190000_grant_service_role_data_access.sql`

**What it does.** Gives `service_role` the ordinary PostgreSQL object
privileges it was missing — `usage` on schema `public`, full DML on every
table (and view) that exists in `public` at apply time, `usage, select` on
every sequence — because bypassing RLS is a *separate* capability from having
the table privilege in the first place, and the backend's trusted service
clients need both. It then sets matching `alter default privileges` so tables
and sequences created by future migrations inherit the same grants without
anyone remembering to restate them.

**What to expect.** Five statements, all privilege DDL: `GRANT`, `GRANT`,
`GRANT`, `ALTER DEFAULT PRIVILEGES`, `ALTER DEFAULT PRIVILEGES`. Expect the
"Potential issue detected" popup on `grant`/`alter` → **Run query** → **"Success.
No rows returned"**. Every statement is idempotent: re-granting a privilege
already held is a documented no-op, and re-issuing the same
`alter default privileges` overwrites the identical default-ACL entry rather
than accumulating rows.

**One caveat worth knowing.** `alter default privileges` with no `for role`
clause applies only to objects created by *the role running this statement*.
Run it as the same role that applies your migrations (`postgres` in both the
SQL Editor and `supabase db push`) and future migration tables are covered; if
some other role ever creates a table in `public`, that table gets no automatic
service_role grant and needs an explicit one.

**Post-check.**

```sql
select
  has_schema_privilege('service_role', 'public', 'USAGE')                   as schema_usage,
  has_table_privilege('service_role', 'public.communities', 'SELECT')       as sample_select,
  has_table_privilege('service_role', 'public.communities', 'INSERT')       as sample_insert,
  has_table_privilege('service_role', 'public.staff_assignments', 'UPDATE') as sample_update,
  has_table_privilege('service_role', 'public.staff_assignments', 'DELETE') as sample_delete,
  (select count(*)
     from pg_default_acl d
     join pg_namespace n on n.oid = d.defaclnamespace
    where n.nspname = 'public'
      and array_to_string(d.defaclacl, ',') like '%service_role=%')         as default_acl_entries;
-- expect: schema_usage = true, sample_select = true, sample_insert = true,
--         sample_update = true, sample_delete = true, default_acl_entries = 2
--         (one entry for relations, one for sequences)
```

If `default_acl_entries` comes back `1`, only one of the two
`alter default privileges` statements landed — re-run the whole file, which is
safe.

---

## 11. `20260812200000_enable_authenticated_request_client_reads.sql`

**What it does.** Closes the mirror-image gap for the request-scoped client:
FastAPI reads tenant data with the signed-in user's JWT, RLS decides which rows
that user may see, but PostgreSQL still refuses the query outright unless the
`authenticated` role holds `SELECT` on the underlying table — which is why
`department_staff_overview` (a `security_invoker` view over
`staff_assignments`, `0043_staff_departures.sql:300`) could not be read by a
JWT client at all. It enables RLS on `staff_assignments` — the one legacy table
written *for* RLS that never actually turned it on — adds a member/own-provider
read policy and an admin write policy, grants `insert, update` to
`authenticated`, then runs a `do` loop granting `SELECT` to `authenticated` on
every RLS-enabled table in `public`, and finally adds two narrow policies
letting a service applicant read the one community and the one department
joined to their own application.

**Statement order matters and is correct.** The `enable row level security` on
line 9 runs *before* the `do` loop on lines 33–48, so `staff_assignments` is
itself picked up by the loop and receives its `SELECT` grant there — the
explicit grant on line 31 deliberately covers only `insert, update`.

**Scope of the blanket grant.** The loop grants `SELECT` only on tables that
*already* have RLS enabled, so every row it exposes is still filtered by that
table's existing policies; a table with RLS on and no policy (e.g.
`sse_events`, `dispatch_tasks`) stays deny-all for `authenticated` after the
grant. No policy anywhere in the applied chain is `using (true)` or
`as restrictive`, and the two new `communities`/`departments` policies are
permissive additions that only *widen* what an applicant may read — they cannot
narrow what an existing member already sees. Tables created *after* this file
must opt in explicitly; the loop is a point-in-time sweep, not a standing rule,
and the file says so in its own header.

**What to expect.** Eleven statements: `ALTER TABLE`, four
`DROP POLICY`/`CREATE POLICY` pairs, one `GRANT`, and one `DO` block. The
"Potential issue detected" popup fires on `alter`/`grant`/`drop` → **Run
query** → **"Success. No rows returned"**. No notices — the `do` block raises
nothing, it only `execute format(...)`s grants.

**Re-run safety.** Every statement is safe twice: `enable row level security`
on an already-enabled table is a no-op, each `create policy` is preceded by its
own `drop policy if exists`, grants are idempotent, and the `do` loop re-issues
grants that are already held.

**Known nit — do not fix here, and it is latent.** The
`staff_assignments_admin_write` policy is declared `for all`, but only
`insert, update` are granted to `authenticated` (line 31). A JWT client
attempting a `delete` on `staff_assignments` would therefore fail on the
*privilege* check before the policy is ever consulted — a `42501` "permission
denied for table staff_assignments", not the clean policy refusal the `for all`
implies. This is inert today: the backend's only direct table access to
`staff_assignments` is through the service client
(`backend/app/services/auth_service.py:289`), which bypasses both checks, and
every other read goes through `department_staff_overview`. Record it, apply the
file as written (the file is immutable once applied), and let whoever adds a
JWT-path delete decide between granting `delete` and narrowing the policy to
`for insert, update`.

**Post-check.**

```sql
select
  (select count(*)
     from pg_policies
    where schemaname = 'public'
      and policyname in (
        'staff_assignments_read',
        'staff_assignments_admin_write',
        'communities_service_application_read',
        'departments_service_application_read'
      ))                                                                    as new_policies,
  (select relrowsecurity from pg_class
    where oid = 'public.staff_assignments'::regclass)                       as staff_rls_enabled,
  has_table_privilege('authenticated', 'public.staff_assignments', 'SELECT') as auth_select,
  has_table_privilege('authenticated', 'public.staff_assignments', 'INSERT') as auth_insert,
  has_table_privilege('authenticated', 'public.staff_assignments', 'UPDATE') as auth_update,
  has_table_privilege('authenticated', 'public.staff_assignments', 'DELETE') as auth_delete,
  (select count(*)
     from pg_class c
     join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relkind in ('r', 'p')
      and c.relrowsecurity
      and not has_table_privilege('authenticated', c.oid, 'SELECT'))        as rls_tables_still_ungranted;
-- expect: new_policies = 4, staff_rls_enabled = true, auth_select = true,
--         auth_insert = true, auth_update = true, auth_delete = false
--         (that false is the known nit above, not a failure),
--         rls_tables_still_ungranted = 0
```

`new_policies = 4` is the whole file: two on `staff_assignments`, one each on
`communities` and `departments`. Anything less than 4 means a policy pair did
not land — re-run the file, which is safe.

Functionally, after this file: load a department's roster tab as a signed-in
admin and confirm `GET /departments/{id}/staff` returns rows rather than a
permission error, and confirm a service applicant can see the community and
department names on their own application.

---

## 12. Record both in the ledger

Applying SQL through the SQL Editor does **not** write
`supabase_migrations.schema_migrations` — the CLI does that, the editor does
not. Run this once, after both files are in and both post-checks pass, or the
next `supabase db push` / `migration list --linked` will believe these two are
still outstanding and try to replay them:

```sql
insert into supabase_migrations.schema_migrations (version, name)
values
  ('20260812190000', 'grant_service_role_data_access'),
  ('20260812200000', 'enable_authenticated_request_client_reads')
on conflict (version) do nothing;
```

Then confirm the count:

```sql
select count(*) from supabase_migrations.schema_migrations;
-- expect: 49
```

49 rows against 49 files in `backend/supabase/migrations/` means the hosted
project and the repository are fully in step — nothing unapplied, nothing
applied that the repository does not have a file for.

---

## What was checked before this addendum was written

Static only — nothing below was run against any database. Both files were read
in full, and:

| Check | Result |
|---|---|
| Both files parse as valid PostgreSQL (`pglast.parse_sql`) | Pass — 5 statements in 190000, 11 in 200000 |
| Every function the new policies call exists in the applied chain | `public.is_community_member(uuid)` and `public.is_community_admin(uuid)` are both `0019_departments_on_baseline.sql:81` and `:97`, `security definer`, `set search_path = public`, granted to `authenticated` at `:119`–`:120`; `auth.uid()` is used exactly as every applied policy uses it |
| Every table the new policies reference exists and has RLS on | `communities` `0001_baseline.sql:256`, `departments` `0033_resident_money_and_home.sql:1280`, `service_applications` `0035_department_roles_and_hiring.sql:1167`, `service_providers` `0034_service_providers.sql:669` |
| No prior `enable row level security` on `staff_assignments` anywhere in the chain | Confirmed — the table is created in `0001_baseline.sql:63` and altered by `0019:206`, `0035:218`, `0044:32`, none of which enables RLS or grants/revokes on it |
| No prior grant, revoke or policy on `staff_assignments` | Confirmed — the only privilege statements naming it are in 200000 itself |
| The four new policy names are unused elsewhere | Confirmed across every `.sql` in `backend/supabase/migrations/` |
| No applied policy is `using (true)`, `as restrictive`, or granted `to anon`/`to public` in a way the `do` loop's blanket `SELECT` could widen | Confirmed — every policy in the chain is scoped by `auth.uid()` or a membership helper |
| Statement-by-statement re-run safety | Confirmed for all 16 statements: grants are idempotent, `enable row level security` is a no-op when already on, all four `create policy` statements are guarded by `drop policy if exists`, and the `do` loop re-issues already-held grants |
| No destructive statement in either file | Confirmed — zero `drop table`, `drop column`, `delete`, `update`, `truncate` |

**Not verifiable statically**, and left for the post-checks above: whether the
hosted `service_role` and `authenticated` roles already hold any of these
privileges from Supabase's own bootstrap (the grants are idempotent either way,
so this changes nothing about whether to apply); and the exact table count the
`do` loop touches, which depends on the hosted `pg_class` at apply time rather
than on anything in the repository.
