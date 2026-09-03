# Apply runbook — the hand-applied migrations

This is a step-by-step guide for the repository owner to apply, by hand, the
migration files that exist in `backend/supabase/migrations/` but are not yet
applied to the linked hosted Supabase project. It assumes you have the
Supabase dashboard and/or a `supabase` CLI linked to the project
(`project_id = "homebandhu"`, see `backend/supabase/config.toml`), and general
competence with Postgres and Supabase, but no context on this branch's work.

> ## Where this stands, 2026-08-22 (evening)
>
> **The title above and §0.2 below are the original seven-file document, and the
> file has grown fifteen sections past it.** They are left in place because
> §1–§12 are the record of how the hosted database reached its current state,
> and a runbook that deletes its own history is one nobody can audit. What is
> *true today* is this:
>
> | | |
> |---|---|
> | **Applied and ledgered** | **everything, through §20 `20260822170000_supervisor_actions.sql`** — confirmed by the owner on the evening of 2026-08-22 |
> | **Not applied, and never to be** | §21 `20260817144725_repair_staff_assignment_employment_type.sql` is applied *already* — it arrived on this branch after the fact, from `origin/main`, and its section exists so the file is not mistaken for outstanding work |
> | **Outstanding** | nothing |
>
> This is the first time since 2026-08-12 that the answer is "nothing". The
> queue that §15–§20 describe is closed; those sections are now history in the
> same sense §1–§7 are, and are kept for their post-checks.
>
> **That "nothing" expired the next day.** Six sections have been written since —
> §23 through §28, all dated 2026-08-23 — each a file in
> `backend/supabase/migrations/`. **Whichever of them are still outstanding,
> apply in filename order**, which is section order here: §23 `20260823120000`,
> §24 `20260823150000`, §25 `20260823153000`, §26 `20260823160000`, §27
> `20260823170000`, §28 `20260823180000`. §27 and §28 each state a dependency on
> the section before them; the rest are independent, and filename order satisfies
> all of it, as it always does. Each section carries its own ledger insert and
> its own post-checks, and each says for itself what the last ledger probe found
> — this paragraph deliberately does not restate that, because a second copy of
> an apply status is the copy that goes stale. **§28 is outstanding as of
> 2026-08-23.**
>
> **Five more sections have been written since — §29 `20260823190000`
> (assignment write repairs), §30 `20260824090000` (supervisor take-up), §31
> `20260826090000` (realtime expansion), §32 `20260827210000` (one live job
> per complaint) and §33 `20260828090000` (residence claim on join).** §30 must
> follow §29 and §29 must follow §28 (each section says so, and re-issues the
> previous one's function bodies); §31 is independent of all of them; §32 must
> follow §28, whose `create_work_order` body it carries forward, and is
> independent of §29–§31; §33 touches none of their objects and depends only on
> the long-applied §23-era state, but comes last because filename order is apply
> order. Filename order — §29, then §30, then §31, then §32, then §33 —
> satisfies all of it, as it always does.
>
> **One more section has been written since — §34 `20260829120000` (drop the
> legacy `approve_access_request` overload).** It touches no object any of
> §29–§33 touches, and depends on none of them: the stray it drops is
> hosted-only prototype code, absent from every migration in this tree, so §34
> applies cleanly whether §33 has landed yet or not, and in either order.
> Filename order puts it last regardless. **§34 is the newest.** If the section
> numbers below run past §34, this paragraph is what needs updating.
>
> So **§0.2's "confirm the highest version present is `0047`" is twenty-two
> migrations stale** and would now stop you on a database that is exactly where
> it should be. Read it as a description of the boundary §1–§7 started from, not
> as a precondition for anything you would run today.
>
> **Order, for the record.** §15, §16 and §17 were independent of each other;
> §18 had to follow §16 (it redeclares `restamp_department_supervision`), §19 had
> to follow §18, and §20 had to follow §19 (both recreate
> `complaint_events_type_check`, and running them backwards drops a word back
> out of the vocabulary). **Filename order satisfied all of it**, as it always
> does, and filename order is what was applied.
>
> **What is left is not an apply — it is a merge.** §22 records the issue #41
> reconciliation: what is on this branch, what is on `origin/main`, and the one
> read-only query the owner still needs to run before that merge lands.

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

**As written in 2026-08-12, for §1–§7 only:** confirm the highest version present
is `0047` or one of the three `20260811…` timestamps (`162409`, `163408`,
`192511`) — i.e. confirm none of the seven files below already has a row here. If
any of the seven is already listed, stop and re-read
`backend/supabase/migrations/README.md`'s boundary paragraph before proceeding;
this runbook assumes a clean start from exactly that boundary.

**As of 2026-08-21, that boundary is long past** (see the box under the title).
The seven *are* listed, and so are `20260812190000`, `20260812200000`,
`20260821113000` and `20260821140000`. For §15 and §16 the check is the opposite
one — confirm the row you need is **present**:

```sql
select version, name
  from supabase_migrations.schema_migrations
 where version in ('20260821113000', '20260821140000',
                   '20260821170000', '20260821200000')
 order by version;
```

`20260821140000` must be there before either. `20260821170000` and
`20260821200000` are what you are about to add, in either order.

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

---

## 13. `20260821113000_location_labels.sql`

Added 2026-08-21, and **the largest single-file rewrite in this runbook** — four
functions and two views are dropped and recreated whole. Read §5x above before
you start; the "if a file fails partway through" advice applies here more than
anywhere else in the document.

**Order.** Filename order, as ever. This one sorts after everything in §§1–12
and after the `20260813…` and `20260820…` files added since this runbook was
last extended, so it goes last: it rebuilds definitions those files depend on
having read, and applying it early would put the old definitions back on top of
it.

**What it does.** Adds `location_label text` (with a `check` of 1–120 characters)
to `service_providers` and to `communities`, then threads that one column through
everything that reads or writes a location:

| Object | Change | Owned before this by |
|---|---|---|
| `service_providers.location_label` | new nullable column + check | — |
| `communities.location_label` | new nullable column + check | — |
| `clean_location_label(text)` | new `immutable` helper: trim, cap at 120, empty becomes null | — |
| `service_provider_overview` | dropped and recreated with one more column | `0034` §8 |
| `community_settings_overview` | replaced with one more column | `20260811162409` §2 |
| `upsert_service_provider` | **dropped**, recreated with an 8th parameter | `0045` §14 |
| `register_service_provider` | **dropped**, recreated with an 8th parameter | `20260811162409` §1 |
| `set_my_community_location` | **dropped**, recreated with a 4th parameter | `20260811162409` §2 |
| `create_founder_community(jsonb)` | replaced; reads one more payload key. Signature unchanged | `20260811162409` §2 |
| `search_hireable_service_providers` | **dropped**, recreated with one more returned column | `20260812090100` |

**Why three functions are dropped rather than replaced, and why that is the
riskiest part.** Adding a defaulted parameter with `create or replace` does not
change the function — it creates a **second** one. After that, every existing
PostgREST call with the old argument count matches both, and Postgres answers
`function public.upsert_service_provider(...) is not unique`, which is a hard
failure on the registration and settings paths. So each is dropped by its exact
old signature first. If the file fails partway, the window in which a function is
dropped and not yet recreated is the one that breaks writes — re-running the
whole file closes it, and re-running is safe.

**What it does not do.** No backfill, no `update`, no `delete`, no `drop
column`, no `drop table`. Every existing provider and community keeps a null
label. **No distance function is touched**: `search_serviceable_communities` is
not named anywhere in the file, the generated `location` columns are untouched,
and every radius predicate and `order by` inside the hiring search is carried
over character for character (asserted in
`backend/tests/test_location_label_migration.py`).

**What to expect.** Roughly forty statements. Expect the "Potential issue
detected" popup on the `drop function` and `drop view` statements → **Run
query**. The last statement is an anonymous `do` block that verifies the result:
if the file applied cleanly it returns "Success. No rows returned"; if any part
of it did not take, it raises with the name of what is missing rather than
reporting success.

**Post-check.** The file's own verification block covers the structure. This
checks the two things it cannot — that no old overload survived, and that the
hiring read did not gain a coordinate:

```sql
select proname, pronargs
  from pg_proc
 where pronamespace = 'public'::regnamespace
   and proname in ('upsert_service_provider', 'register_service_provider',
                   'set_my_community_location', 'search_hireable_service_providers')
 order by proname;
-- expect exactly four rows:
--   register_service_provider         | 8
--   search_hireable_service_providers | 4
--   set_my_community_location         | 4
--   upsert_service_provider           | 8
-- FIVE rows means an old overload survived. Re-run the file.

select count(*) filter (where n.name = 'location_label')            as has_label,
       count(*) filter (where n.name in ('latitude', 'longitude'))  as leaks_coordinates
  from pg_proc pr
  cross join lateral unnest(pr.proargnames) as n(name)
 where pr.pronamespace = 'public'::regnamespace
   and pr.proname = 'search_hireable_service_providers';
-- expect: has_label = 1, leaks_coordinates = 0
```

**Record it in the ledger** (§12 explains why the SQL Editor does not do this
for you):

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260821113000', 'location_labels')
on conflict (version) do nothing;
```

**Functionally, after this file:** open the service-partner registration form,
type a suburb into the address box and press Search — results appear, picking one
drops the pin and fills the label, and saving keeps both. Then open a
department's hiring tab and confirm a candidate card shows the place name beside
the distance.

**Until the file is applied, the code that ships with it does not work, and it
is meant not to.** The repository asks PostgREST for `location_label` by name in
three column lists (the provider profile read, the hiring candidate read, and the
settings read), and asks the four rewritten RPCs for their new argument. Against
a database without the column that is an error, not a degraded response: the
worker profile, the hiring candidate page and the admin settings page all fail to
load, and the two provider writes answer **503** naming the rollout gap
(`location_label_migration_not_deployed` from the profile edit,
`service_provider_registration_not_deployed` from registration). This is the
house pattern from `register_service_provider`'s own rollout, and it is
deliberate: a select list that quietly fell back would hide the fact that the
migration is outstanding, and a write that retried without the label would save a
profile that lost what the person had just typed. **Apply this file before
testing anything from the 2026-08-21 location-picker work.**

### What was checked before this section was written

Static only — nothing below was run against any database. The checks are
automated in `backend/tests/test_location_label_migration.py` rather than done
once by hand, so they re-run on every change to the file.

| Check | Result |
|---|---|
| The file parses as valid PostgreSQL (`pglast.parse_sql`) | Pass |
| It sorts after every file whose definitions it rewrites (`0034`, `0045`, `20260811162409`, `20260812090100`) | Pass |
| No later migration redeclares any of the seven objects it owns | Pass — checked across every `.sql` in the directory |
| Every DDL statement is guarded (`add column if not exists`, `do`-block constraint guards, `drop … if exists` before each create) | Pass — four `drop function if exists`, one `drop view if exists` |
| Each drop names the exact signature the owning migration declared | Pass — each expected signature is re-read out of the owning file rather than typed into the test |
| `search_hireable_service_providers` returns `location_label` and neither `latitude` nor `longitude` | Pass |
| Every predicate and ordering that decides who is hireable survived the rewrite | Pass — the `st_dwithin` bounds, both blacklist/roster `not exists` blocks, the `order by` and the `limit`, compared against `20260812090100` |
| `service_provider_overview` kept every column it had | Pass — the old column list is parsed out of `0034` and each name required in the new body |
| The 120-character cap matches the one the API truncates labels to | Pass — compared against `LOCATION_LABEL_MAX_LENGTH` in `app/domain/geo_schemas.py` |
| No destructive statement | Pass — zero `drop table`, `drop column`, `delete`, `update`, `truncate`, `alter column` |

**Not verifiable statically**, and left for the post-checks above: whether the
hosted project's `service_providers` or `communities` already carries a column of
this name from some path the repository does not know about (the `if not exists`
guard makes the add safe either way, but a pre-existing column with a different
type or no check constraint would make the verification block raise, which is the
intended outcome); and whether any *other* overload of the four rewritten
functions exists on the hosted database from before the repository baseline —
the first post-check query is exactly the probe for that.

---

## 14. `20260821140000_leadership_exclusivity.sql`

Added 2026-08-21, after §13 and **because of** it: it copies §13's
eight-argument `register_service_provider` forward verbatim in order to add one
refusal to it. **Apply §13 first.** Applying this one against a database that has
not had §13 will install a `register_service_provider` whose body calls
`upsert_service_provider` with eight arguments that do not exist there.

**Order.** Filename order. `20260821140000` sorts after `20260821113000`, which
is the whole reason its refusal survives.

**What it enforces.** The three product rulings of 2026-08-21:

1. leadership is invite-only and never from the marketplace pool;
2. leadership is exclusive to one community;
3. removal severs access completely.

| Object | Change | Owned before this by |
|---|---|---|
| `staff_invitations.blocked_reason` | new nullable `text` | — |
| `staff_invitations.blocked_at` | new nullable `timestamptz` | — |
| `staff_assignment_profile(uuid, uuid)` | new predicate: which person a roster row is | — |
| `active_leadership_community(uuid)` | new predicate: where this person currently leads, or null | — |
| `membership_is_live(uuid)` | new predicate, for the notifications policy | — |
| `enforce_leadership_exclusivity()` + trigger on `staff_assignments` | new: rulings 1 and 2 (`HBMKT`, `HBLED`) | — |
| `enforce_provider_not_leadership()` + trigger on `service_providers` | new: ruling 1 from the marketplace side | — |
| `register_service_provider` | replaced; one refusal added, `p_location_label` carried forward | `20260821113000` §3 |
| `invite_staff_member` | replaced; two refusals added | `20260812090200` §3 |
| `update_staff_invitation` | replaced; two refusals added, clears `blocked_reason` | `20260812090200` §3 |
| `department_staff_invitations` | **dropped**, recreated with two more returned columns | `20260812090200` §2 |
| `claim_staff_invitations` | replaced; a blocked invitation is skipped and marked, never raised | `20260812090200` §4 |
| `is_own_staff_assignment` | replaced; now requires the roster row **and** the membership to be live | `0036` §4 |
| `notify_member` | replaced; a message to an ended membership is filed against the person | `0041` §2 |
| `notifications_read_own` policy | replaced; community-scoped rows for an ended membership are hidden | `0041` §1 |
| `dm_threads_read`, `dm_messages_read` policies | replaced; both now require an active membership in the thread's community | `0046` §6 |

**Why `department_staff_invitations` is dropped rather than replaced.** It is the
one object here whose `returns table` signature changes, and `create or replace`
cannot change a return type — it fails with "cannot change return type of
existing function". Its argument list is unchanged, so unlike §13 there is no
overload risk; the drop is simply the only way to widen the projection. The grant
is reissued immediately after, because dropping a function takes its grants with
it.

**What it does not do.** No backfill, no `update` of any existing row, no
`delete`, no `drop column`, no `drop table`. Accounts that *already* break
rulings 1 or 2 are **counted and reported, never repaired** — which community
loses its supervisor, and which identity a person keeps, are somebody's job and
somebody's account. Section 9 of the file raises a `notice` with the counts.
Expect all three to be zero.

**What to expect.** Roughly thirty statements. Expect the "Potential issue
detected" popup on `drop function`, `drop trigger` and `drop policy` → **Run
query**. One anonymous `do` block, the counting block in section 9, which prints
`NOTICE` lines only if something already violates the rulings. There is no
self-verification block: what this file installs is enforced by triggers and
policies whose presence the post-check below queries directly.

**Post-check.** Run all of these. They are reproduced in the file's own section
10 so a reader of the SQL finds them without the runbook.

```sql
-- (a) Both triggers exist.
select tgname
  from pg_trigger
 where tgname in ('staff_assignments_leadership_exclusivity',
                  'service_providers_not_leadership');
-- expect: two rows.

-- (b) The two new columns exist.
select column_name, data_type
  from information_schema.columns
 where table_schema = 'public' and table_name = 'staff_invitations'
   and column_name in ('blocked_reason', 'blocked_at');
-- expect: two rows.

-- (c) Exactly one department_staff_invitations, and it is the wide one.
select pr.pronargs, array_length(pr.proallargtypes, 1) as all_args
  from pg_proc pr
 where pr.pronamespace = 'public'::regnamespace
   and pr.proname = 'department_staff_invitations';
-- expect: one row, pronargs = 2, all_args = 14 (2 in + 12 out).

-- (d) Nobody holds two active leadership postings.
select m.profile_id, count(*)
  from public.staff_assignments sa
  join public.community_memberships m on m.id = sa.membership_id
 where sa.status = 'active' and sa.rank in ('manager', 'supervisor')
   and m.status = 'active' and m.ended_at is null
 group by m.profile_id having count(*) > 1;
-- expect: zero rows. Non-zero means section 9's notice fired and somebody has
--         to decide which posting survives.

-- (e) No active leader also holds a marketplace profile.
select sa.id, sa.community_id, sa.rank
  from public.staff_assignments sa
  join public.community_memberships m on m.id = sa.membership_id
  join public.service_providers p on p.profile_id = m.profile_id
 where sa.status = 'active' and sa.rank in ('manager', 'supervisor')
   and m.status = 'active' and m.ended_at is null;
-- expect: zero rows.

-- (f) The three ruling-3 policies carry their new conditions.
select polname, pg_get_expr(polqual, polrelid) as predicate
  from pg_policy
 where polname in ('dm_threads_read', 'dm_messages_read',
                   'notifications_read_own');
-- expect: three rows; the first two mention is_community_member, the third
--         mentions membership_is_live.

-- (g) The guard actually refuses. Self-contained: finds a marketplace-hired
--     roster row itself, attempts the forbidden promotion inside a
--     subtransaction, and rolls everything back. If no such row exists yet it
--     says so and skips — the trigger's presence is already proven by (a).
do $$
declare
  v_row uuid;
begin
  select sa.id into v_row
    from public.staff_assignments sa
   where sa.service_provider_id is not null
     and sa.rank = 'member'
   limit 1;
  if v_row is null then
    raise notice 'check (g) skipped: no marketplace-hired roster row to test with; trigger presence is proven by check (a).';
    return;
  end if;
  begin
    update public.staff_assignments set rank = 'supervisor' where id = v_row;
    raise exception 'check (g) FAILED: the promotion was not refused';
  exception
    when sqlstate 'HBMKT' then
      raise notice 'check (g) OK: promotion refused with HBMKT, nothing persisted.';
  end;
end $$;
-- expect: NOTICE "check (g) OK ..." (or the skip notice on an empty roster).
--         The caught error rolls the subtransaction back, so the row is
--         untouched either way.
```

**Record it in the ledger** (§12 explains why the SQL Editor does not do this for
you):

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260821140000', 'leadership_exclusivity')
on conflict (version) do nothing;
```

**Functionally, after this file:** try to invite a registered service
professional's email as a supervisor from a department's staff panel — it comes
back 409 naming the marketplace. Sign in as an account invited as a supervisor in
two communities: one posting takes, the other stays `pending` in its department's
list with a sentence saying why. Remove a supervisor from a community and sign in
as them again: that community's threads, calendar, jobs and community-scoped
notifications are gone, and the "You were taken off a roster" notification is
still there.

**Until the file is applied**, the API behaves as it did before, with two
exceptions that are Python-side and ship independently: `HB422` from the invite
RPCs now surfaces as a 422 instead of a 500, and `blockedReason`/`blockedAt` come
back `null` on every invitation (the service reads them with `.get`, so a
database without the columns does not 500 the department page). Nothing else in
the 2026-08-21 leadership work has any effect until the DDL is on the database —
the guards, the claim-time skip and all three ruling-3 fixes are entirely in SQL.

### What was checked before this section was written

Static only — nothing below was run against any database. The checks are
automated in `backend/tests/test_leadership_exclusivity_migration.py` rather than
done once by hand, so they re-run on every change to the file.

| Check | Result |
|---|---|
| The file parses as valid PostgreSQL (`pglast.parse_sql`) | Pass |
| It sorts after every file whose definitions it rewrites (`0036`, `0041`, `0046`, `20260812090200`, `20260821113000`) | Pass |
| No later migration redeclares any of the nine objects it owns | Pass — checked across every `.sql` in the directory |
| Every DDL statement is guarded (`add column if not exists`; `drop trigger`/`policy`/`function if exists` before each create) | Pass |
| `register_service_provider`'s copy kept `p_location_label` **and** the 2026-08-12 separate-account refusal | Pass — both asserted by name, and the new refusal asserted to come first |
| `claim_staff_invitations`' copy kept the rank derivation, the already-a-member skip and both inserts | Pass |
| The claim's blocked branch contains no `raise` and ends in `continue` | Pass — the whole loop body is asserted to contain zero `raise exception` |
| No destructive statement | Pass — zero `drop table`, `drop column`, `truncate`, `delete from`, and no `update` of `community_memberships`, `service_providers` or `staff_assignments` |
| Every custom SQLSTATE the file raises is mapped in `app/core/pg_errors.py` | Pass — and this is the check that found the unmapped `HB422` |

**Not verifiable statically**, and left for the post-checks above: whether the
hosted database already contains an account violating ruling 1 or 2 (section 9
counts them and the file continues either way — a `notice`, not a failure);
whether any `staff_assignments` row is active while the membership it names has
ended, which the new `is_own_staff_assignment` would hide from its owner
(post-checks (d) and (e) will not show it — if you suspect it, compare
`staff_assignments.status = 'active'` against `community_memberships.status` for
the same row); and whether the hosted `notify_member` differs from `0041`'s text,
which is the body this file copied forward.

---

## 15. `20260821170000_blocked_invitee_notice.sql`

Added 2026-08-21, after §14 and **because of** it: it redeclares §14's
`claim_staff_invitations` so that the person whose leadership invitation was
refused is told why, on the same edge that already tells the department.
**Apply §14 first.** Applying this one against a database that has not had §14
would install a function that reads `staff_invitations.blocked_at` and calls
`active_leadership_community`, neither of which exists there — and it would fail
on the first sign-in rather than at apply time, which is worse.

**Order.** Filename order. `20260821170000` sorts after `20260821140000`, which
is the whole reason its addition survives: both files declare the same function
name, and the last one applied is the definition the database keeps.

**Why it exists.** §14 made a blocked claim *survivable* — the invitation is
skipped rather than raised, stays `pending`, gains a `blocked_reason`, and the
inviting department gets one `staff_invitation.blocked` notification. Every one
of those is addressed to the department. The invitee was told nothing: they sign
in with the address that was typed for them, the invitation silently does not
take, and they land wherever their own identity already entitled them to. The
product owner's ruling of 2026-08-21 is that they must be told, on the same edge,
in wording that is frozen and is reproduced in section 1 of the file.

| Object | Change | Owned before this by |
|---|---|---|
| `claim_staff_invitations` | replaced; one `notify_profile` call added inside the existing `blocked_at is null` guard | `20260821140000` §5 |

That is the whole table. **No column, no table, no view, no policy, no trigger, no
grant, no index.** One `create or replace function`, its `comment`, its `revoke`,
and one anonymous `do` block that counts and reports.

**What the copy had to preserve, and does.** The body was extracted mechanically
from §14's file — the house convention from `20260812113000` §1 — so the starting
point is provably the text that was applied to this database. The additions are
marked `-- CHANGED (20260821170000)` to keep them apart from §14's own `-- CHANGED`
markers. `test_the_copied_body_is_purely_additive` asserts that every non-blank
line of the applied version is still present, which is the check that catches a
copy made by retyping: the already-a-member skip, the rank derivation, both
inserts and the claimed-clears-blocked update are all lines that can vanish
without anything erroring.

**The property that matters most is the absence of a `raise`.** This function runs
inside `resolve_session` on every membership-less session read, and
`auth_service._claim_staff_invitations` swallows what it raises. A new call inside
that loop that could throw would abandon every *other* pending invitation in the
same call, silently, behind a screen that looks fine. `notify_profile` cannot
throw for the arguments used here — its two guards are a null profile (impossible;
the function returns early on one) and a blank kind (a literal).

**What it does not do.** No backfill, no `update` of any row other than the
`staff_invitations` row the copied body already marked, no `delete`, no `drop` of
anything. An invitation that was **already** blocked before this file is applied
has already crossed the `blocked_at is null` edge, and its invitee is not told
retroactively — sending for those rows would mean writing `blocked_at` backwards
or bypassing the guard, and either would re-notify anybody the department has
since re-invited. Section 2 of the file counts them into a `raise notice` and
touches nothing. Expect zero: the columns were added the same day, by §14. The
department's own remedy re-arms the edge — `update_staff_invitation` clears
`blocked_reason`/`blocked_at`, so a corrected or re-issued address announces
itself normally on the next sign-in.

**What to expect.** Four statements. Expect **no** "Potential issue detected"
popup: there is no `drop` in the file. The `do` block in section 2 returns
"Success. No rows returned", and prints a `NOTICE` only if pending blocked
invitations already exist.

**Post-check.** Paste the whole block below in one go. Every check either
self-selects the data it needs or reports that there is nothing to check — there
is nothing in it to fill in.

```sql
do $$
declare
  v_src         text;
  v_definitions integer;
begin
  select count(*) into v_definitions
    from pg_proc
   where pronamespace = 'public'::regnamespace
     and proname = 'claim_staff_invitations';

  if v_definitions <> 1 then
    raise exception
      'check FAILED: % definition(s) of claim_staff_invitations, expected exactly 1. An overload makes PostgREST answer "function is not unique".',
      v_definitions;
  end if;

  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace
     and proname = 'claim_staff_invitations';

  -- (a) Both halves of the announcement are present.
  if v_src not like '%staff_invitation.not_applied%' then
    raise exception 'check (a) FAILED: the invitee is still not told. This file did not take, or an older definition won.';
  end if;
  if v_src not like '%staff_invitation.blocked%' then
    raise exception 'check (a) FAILED: the department notification was lost in the copy.';
  end if;

  -- (b) Both sit inside the one edge guard, so each fires once.
  if v_src not like '%if v_row.blocked_at is null then%' then
    raise exception 'check (b) FAILED: the blocked_at edge guard is gone; the messages would re-send on every sign-in.';
  end if;

  -- (c) The refusal is still a skip. A raise here abandons the whole claim.
  if v_src ~* '\mraise\M' then
    raise exception 'check (c) FAILED: the claim can raise again. A refusal spelled as an exception abandons every other pending invitation, silently.';
  end if;

  -- (d) The invitee is addressed as a person, not as a membership.
  if v_src not like '%notify_profile(%' then
    raise exception 'check (d) FAILED: the invitee notification is not person-scoped.';
  end if;

  -- (e) The approved wording, both branches, as stored.
  if v_src not like '%registered as a marketplace service professional, and department leadership can%' then
    raise exception 'check (e) FAILED: the provider sentence is not the approved wording.';
  end if;
  -- Deliberately a clause the *invitee* sentence alone carries: the
  -- department's own blocked_reason also says "already manage or supervise
  -- another community", so a fragment from the shared half would pass even if
  -- the invitee's message had been lost.
  if v_src not like '%once your current engagement ends, the invitation can be applied on your next sign-in.%' then
    raise exception 'check (e) FAILED: the already-leads sentence is not the approved wording.';
  end if;

  raise notice 'checks (a)-(e) OK: one definition, both notifications, one edge guard, no raise, approved wording.';
end $$;

-- (f) What the file could not reach: invitations blocked before it was applied.
--     Their invitees crossed the edge without a message and are not told
--     retroactively. Correcting or re-issuing the address re-arms it.
select count(*) as pending_blocked_before_this_file
  from public.staff_invitations
 where blocked_at is not null and status = 'pending';
-- expect: 0. A non-zero count is not a failure -- it is the list of people the
--         department may want to re-issue an invitation to.

-- (g) The rows this writes are person-scoped and community-less, which is what
--     keeps them readable through every later membership change. Safe to run
--     before any exist: it answers 0/0/0.
select count(*)                                                     as written,
       count(*) filter (where recipient_profile_id is null)         as unaddressed,
       count(*) filter (where recipient_membership_id is not null)  as community_scoped
  from public.notifications
 where kind = 'staff_invitation.not_applied';
-- expect: unaddressed = 0 and community_scoped = 0, whatever `written` is.
```

**Record it in the ledger** (§12 explains why the SQL Editor does not do this for
you):

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260821170000', 'blocked_invitee_notice')
on conflict (version) do nothing;
```

**Functionally, after this file:** invite an address as a supervisor from a
department's staff panel, have the person behind that address register as a
service professional, then sign them in. The department's list shows the
invitation still `pending` with a `blockedReason`, and the person's own
notification bell now carries *"Your invitation couldn't be applied"* with the
approved sentence underneath. Signing in again changes neither: the edge has
passed, and that is the point.

**Until the file is applied**, nothing changes anywhere. There is no Python half
and no frontend half to this work — the only thing that ships with it is the
notification the database writes — so an unapplied file means the invitee keeps
being told nothing, exactly as before. Nothing 500s and nothing degrades.

### What was checked before this section was written

Static only — nothing below was run against any database. The checks are
automated in `backend/tests/test_blocked_invitee_notice_migration.py` rather than
done once by hand, so they re-run on every change to the file.

| Check | Result |
|---|---|
| The file parses as valid PostgreSQL (`pglast.parse_sql`) | Pass |
| It sorts after `0041`, `20260812090200`, `20260821113000` and `20260821140000` — and is the last file that declares `claim_staff_invitations` | Pass — "last file in the directory" until §16 was added on 2026-08-21; being last among the files that declare this function was always the property that mattered |
| The copied body is **purely additive**: every non-blank line of `20260821140000`'s version is still present | Pass — compared line by line against the owning file rather than against a remembered list |
| The signature and `returns table` are unchanged (`create or replace` cannot change a return type, and a defaulted parameter would create an overload) | Pass |
| The loop contains no `raise` of any kind, still ends both refusal paths in `continue`, and never writes `status = 'blocked'` | Pass |
| Both notifications sit inside exactly one `if v_row.blocked_at is null then` guard, and there are exactly two `perform public.notify…` calls in it | Pass |
| The invitee is addressed with `notify_profile(p_profile_id, …)` under a kind distinct from the department's | Pass |
| Both approved sentences are stored character for character, each as one uninterrupted `body` string | Pass — apostrophe-unescaped and compared against the frozen text |
| The payload carries no `url` key, and the kind is in neither `_FALLBACK_URLS` nor `_FALLBACK_TITLES` | Pass — the second half from the API side, `test_api_283` / `test_api_284` |
| Nothing destructive and nothing else declared: one function, no `drop`, no `alter table`, no policy, no trigger, no view | Pass |
| The pre-existing-blocked count is a `notice` that runs no `update` | Pass |

**Not verifiable statically**, and left for the post-checks above: whether the
hosted `claim_staff_invitations` is in fact §14's text (this file's copy is
provably §14's *file*, which is only the same thing if §14 applied cleanly —
post-check (a)'s department-notification assertion is the probe for that); whether
any pending invitation on the hosted database is already blocked, which post-check
(f) counts; and whether `notify_profile` is present and executable by the
function's owner, which nothing can prove until a refusal actually happens and
post-check (g) counts a row.

---

## 16. `20260821200000_departure_continuity.sql`

Added 2026-08-21, after §15 and **independent of it**. It does not declare
`claim_staff_invitations` and reads nothing §15 writes, so the two may be applied
in either order. **§14 is the real precondition:** this file calls
`membership_is_live`, which §14 declares, and it leans on §14's roster trigger
having already settled what a leadership row may be.

**Why it exists.** `work_orders.supervisor_membership_id` (`0036`) is the address
five notification kinds are delivered to — `work_order.no_candidates`,
`work_order.resident_accepted` / `_declined`, `work_order.accepted`,
`work_order.completed` and `work_order.failed` — and nothing anywhere re-pointed
it when the person it named stopped being a supervisor. After
`remove_department_member` the roster row is `inactive` and the membership is
`ended`, and every one of those messages is still written to the departed person;
§14's `notifications_read_own` policy then hides the row. So a department's live
jobs report their progress into a mailbox nobody can open. The complaint itself
is not lost — complaints are department-pooled and the product owner's ruling of
2026-08-21 keeps them that way — but everything downstream of it goes quiet.

| Object | Change | Owned before this by |
|---|---|---|
| `department_supervision_successor(uuid, uuid)` | **new** — the one place "who inherits this department's supervision" is written | — |
| `restamp_department_supervision(uuid, uuid)` | **new** — re-points one department's live work orders away from a membership that has stopped supervising them | — |
| `staff_supervised_work_order_count(uuid)` | **new** — the roster count that replaces a constant zero | — |
| `carry_department_supervision()` | **new** trigger function | — |
| `staff_assignments_carry_supervision` | **new** trigger, `after update of rank, status, membership_id` | — |
| `notify_complaint_staff` | replaced; one recipient arm added so a department's **supervisors** are told about its complaints (ruling R18) | `20260812090300` §2b |
| `department_staff_overview` | dropped and recreated; `active_assignment_count` replaced by `supervised_work_order_count`, every other column carried over | `0045` §12 |

**No column, no table, no policy, no grant revocation, no new SQLSTATE.** Nothing
in the file refuses anything, so `backend/app/core/pg_errors.py` is untouched —
and that is asserted rather than assumed
(`test_it_raises_nothing_so_there_is_no_sqlstate_to_map`).

**Why a trigger and not an edit to `remove_department_member`.** Removal has four
RPC entry paths — the direct route, an immediate departure approval, the
timekeeper's dated removal, and a blacklist — and a fifth that is not an RPC at
all: `staff_assignments_admin_write` is `for all to authenticated` with direct
grants (`20260812200000`), so an admin can flip `status = 'inactive'` straight
through PostgREST. All five end at the same `update public.staff_assignments`, so
one `after update` trigger covers all five where a change to the removal function
would cover four. §14 made the same choice for the same reason. `after` rather
than `before` is also deliberate: by then the departing row is already `inactive`
in the snapshot the successor search reads, so "a remaining active supervisor"
excludes them by construction.

**The target rule.** In order: the least-loaded remaining **active supervisor** of
the same department whose membership is still live (ties broken by `created_at`
then `id`, so a re-run moves nothing); else the department's **manager** — the
roster row holding `rank = 'manager'`, then a `manager` membership pinned to this
department, then one pinned to none; else **nobody**, and the work orders are left
exactly as they are. A wrong address is worse than a stale one. Community admins
are deliberately not a step — they are not on the department's roster — though
they are told about the takeover.

**Scope.** Only work orders that are live (not `completed`, `cancelled` or
`failed`) and only within the department the row belonged to. A completed job
needs no supervisor and renaming one falsifies a record; and a membership can
appear on more than one department's work, which re-stamping by membership alone
would hand entirely to whichever department lost them first.

**The last-supervisor notice.** When the removed row was a `supervisor`, the
department is `kind = 'service'`, and no active supervisor remains, the file sends
one `department.supervision_uncovered` through `notify_department_leadership` —
whose audience, with zero supervisors left, is exactly the community's admins plus
this department's manager. Its url is `/admin/complaints`, which
`frontend/src/features/notifications/portalUrl.js` rewrites to
`/manager/complaints` for a manager reader. Security departments are excluded
because `/security-manager` has no complaints screen and a link that redirects
home is the failure that module exists to prevent.

**The backfill.** Section 7 is a `do` block that finds every live work order whose
`supervisor_membership_id` is not `membership_is_live` and re-stamps it to the
same rule, then prints a `NOTICE` with three numbers: how many were orphaned, how
many moved, and how many were left because their department has nobody to inherit
them. It raises no exception and runs no `update` of its own. **Expect zero or
close to it** on this database. Re-running the file re-runs the block; the second
run reports zero, because it only ever selects rows that are still orphaned.

**What to expect.** Six functions, one trigger (dropped first), one view (dropped
first), the grants, and the `do` block. The SQL Editor **will** show its "Potential
issue detected" popup — there are two `drop` statements, `drop trigger if exists`
and `drop view if exists`, both of which this file recreates immediately. Proceed.
Everything else returns "Success. No rows returned"; the `do` block prints one
`NOTICE`.

**A Python change ships with this one, and it is not optional.**
`departments_repository._STAFF_SELECT` and
`hiring_repository._STAFF_MEMBER_SELECT` now ask PostgREST for
`supervised_work_order_count`. Until this file is applied, that column does not
exist and **every roster read is a 400** — the admin's hiring screen, the
manager's team screen and the employee page. This is the one section in this
runbook where "not applied yet" is not a no-op, so apply it in the same sitting as
the deploy rather than leaving it for later.

**Post-check.** Paste the whole block below in one go. Every check either
self-selects the data it needs or reports that there is nothing to check — there
is nothing in it to fill in.

```sql
do $$
declare
  v_name  text;
  v_src   text;
  v_count integer;
begin
  -- (a) One definition of each new function, and the trigger is wired.
  foreach v_name in array array[
    'department_supervision_successor',
    'restamp_department_supervision',
    'staff_supervised_work_order_count',
    'carry_department_supervision']
  loop
    select count(*) into v_count
      from pg_proc
     where pronamespace = 'public'::regnamespace and proname = v_name;
    if v_count <> 1 then
      raise exception
        'check (a) FAILED: % definition(s) of %, expected exactly 1.', v_count, v_name;
    end if;
  end loop;

  select count(*) into v_count
    from pg_trigger
   where tgrelid = 'public.staff_assignments'::regclass
     and tgname  = 'staff_assignments_carry_supervision'
     and not tgisinternal;
  if v_count <> 1 then
    raise exception
      'check (a) FAILED: the continuity trigger is not on staff_assignments. Removals will silently stop re-stamping.';
  end if;

  select pg_get_triggerdef(oid) into v_src
    from pg_trigger
   where tgrelid = 'public.staff_assignments'::regclass
     and tgname  = 'staff_assignments_carry_supervision';
  if v_src !~* 'AFTER UPDATE OF' then
    raise exception
      'check (a) FAILED: the trigger is not AFTER UPDATE OF. A BEFORE trigger would see the departing row as still active.';
  end if;

  -- (b) The roster view carries the new column and not the old one. The Python
  --     projection asks for the first by name, so this is the check that stands
  --     between the deploy and a 400 on every roster read.
  if not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'department_staff_overview'
       and column_name = 'supervised_work_order_count') then
    raise exception
      'check (b) FAILED: department_staff_overview has no supervised_work_order_count. Every roster read will 400.';
  end if;
  if exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'department_staff_overview'
       and column_name = 'active_assignment_count') then
    raise exception
      'check (b) FAILED: the old constant column is still there, so an older definition of the view won.';
  end if;

  -- (c) The complaint audience reaches supervisors (ruling R18), and still
  --     reaches everybody it reached before.
  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace and proname = 'notify_complaint_staff';
  if v_src not like '%sa.rank in (''manager'', ''supervisor'')%' then
    raise exception 'check (c) FAILED: supervisors are still not told about complaints.';
  end if;
  if v_src not like '%notify_community_roles%' then
    raise exception 'check (c) FAILED: the admins were lost in the copy.';
  end if;
  if v_src not like '%m.department_id = v_complaint.department_id%' then
    raise exception 'check (c) FAILED: the department manager was lost in the copy.';
  end if;

  raise notice 'checks (a)-(c) OK: four functions, one AFTER trigger, the view swapped, the complaint audience widened.';
end $$;

-- (d) What the backfill could not reach: live work orders still addressed to a
--     membership that has ended. Safe to run on an empty database.
select count(*) as still_orphaned
  from public.work_orders w
 where w.supervisor_membership_id is not null
   and w.status not in ('completed', 'cancelled', 'failed')
   and not public.membership_is_live(w.supervisor_membership_id);
-- expect: 0, or exactly the "left in place" number the file's NOTICE printed.
--         A non-zero count is not a failure -- it is the list of departments
--         with no remaining supervisor and no manager to inherit their work.

-- (e) Which departments those are, if any. Answers zero rows when (d) is 0.
select d.id, d.name, count(*) as jobs
  from public.work_orders w
  join public.departments d on d.id = w.department_id
 where w.supervisor_membership_id is not null
   and w.status not in ('completed', 'cancelled', 'failed')
   and not public.membership_is_live(w.supervisor_membership_id)
 group by d.id, d.name
 order by jobs desc;
-- The remedy is a person, not SQL: invite a supervisor or appoint a manager,
-- and the next removal on that department re-stamps what is left.

-- (f) The new roster count, against real data. Zero rows before anybody is
--     leading anything, which is the ordinary answer on a young database.
select s.display_name, s.rank,
       public.staff_supervised_work_order_count(s.id) as supervises
  from public.staff_assignments s
 where s.status = 'active'
   and s.rank in ('manager', 'supervisor')
 order by supervises desc, s.display_name
 limit 20;
-- expect: no error. Any non-zero row is a number that read 0 before this file.
```

**Record it in the ledger** (§12 explains why the SQL Editor does not do this for
you):

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260821200000', 'departure_continuity')
on conflict (version) do nothing;
```

**Functionally, after this file:** put two supervisors on a service department,
raise a complaint and turn it into a work order under one of them, then remove
that supervisor from the roster tab. The work order's supervisor becomes the
other one, silently — no resident or worker sees anything, because no
resident-facing or worker-facing read has ever returned a supervisor's identity.
Remove the second supervisor and the department's manager gets *"You are covering
…'s complaint queue"* in their bell, and their Complaints screen carries a banner
saying the same thing for as long as it stays true. Raise a third complaint and
every supervisor the department has is notified along with the manager and the
admins.

**Until the file is applied**, the roster reads 400 (see the Python note above),
the hiring screen and the employee page cannot load, and removals go on leaking
notifications to departed people exactly as before.

### What was checked before this section was written

Static only — nothing below was run against any database. The checks are
automated in `backend/tests/test_departure_continuity_migration.py` rather than
done once by hand, so they re-run on every change to the file.

| Check | Result |
|---|---|
| The file parses as valid PostgreSQL (`pglast.parse_sql`) | Pass |
| It sorts after `0036`, `0043`, `0045`, `20260812090300` and `20260821140000` | Pass |
| It declares no `claim_staff_invitations` and mentions no `staff_invitations` — §15's work cannot be reverted by it | Pass |
| It redeclares none of the eleven names the three sibling static-check files pin, and neither `release_staff_commitments` nor `claim_dispatch_batch` (ruling 9) | Pass |
| It never writes `complaints.assigned_to_membership_id` or `assignee_label` (ruling 1) | Pass |
| The successor rule exists exactly once, and both the trigger and the backfill call it rather than searching themselves | Pass |
| The successor is a live supervisor, then the manager, then **null** — no widening fallback | Pass |
| The choice is deterministic: load, then `created_at`, then `id` | Pass |
| Re-stamping touches only live work orders and only within the department | Pass |
| The trigger is `after update of rank, status, membership_id`, guarded on "was live leadership, now is not", and dropped before being created | Pass |
| The trigger asks nothing about `auth.uid()`, so the PostgREST bypass path is covered too | Pass |
| The cover notice has three gates (supervisor, service department, none left), fires once, excludes the departing person, and links to a path `portalUrl.js` can rewrite | Pass |
| The `notify_complaint_staff` copy keeps the null-community guard, the admin call, the department early return and the manager predicate | Pass — compared fragment by fragment against `20260812090300` rather than against a remembered list |
| The added arm is `distinct` and excludes admins, so nobody is told twice | Pass |
| The recreated view keeps every column `0045` gave it except the one being removed, keeps `security_invoker`, and reissues its grant | Pass — column list parsed out of the owning file |
| The new count is `security definer` and granted to `authenticated`, like `staff_open_commitment_count` beside it | Pass |
| The Python wire model and both PostgREST projections agree with the view's new column | Pass |
| The backfill repairs through the shared function, counts what it cannot repair, and raises no exception | Pass |
| Nothing destructive: no `drop table`/`drop column`/`drop function`/`delete`/`alter table`, exactly one `drop view` recreated in place, exactly one `update` statement and it is the re-stamp | Pass |
| No custom SQLSTATE is raised, so `pg_errors` needs nothing | Pass |

**Not verifiable statically**, and left for the post-checks above: whether the
hosted `notify_complaint_staff` was in fact `20260812090300`'s text before this
file replaced it (post-check (c)'s three fragments are the probe); how many live
work orders on this database are addressed to an ended membership, which the
file's own `NOTICE` and post-check (d) count; whether any department has neither
a supervisor nor a manager to inherit work, which post-check (e) lists; and
whether the trigger actually fires on a real removal, which nothing can prove
until one happens.

## 17. `20260822090000_hosted_work_order_column_drift.sql`

**What breaks without it:** nobody can raise a work order. `POST
/api/v1/complaints/{id}/work-orders` — the "Raise it" button on the triage
screen, supervisor and admin portals alike — answers 422 "Could not raise that
job." on every attempt. Found live on 2026-08-22; the captured Postgres error
is 23502, `null value in column "title" of relation "work_orders"`.

**Why:** the same drift `20260820120000` (§12's neighbourhood) reconciled on
`complaints`. The hosted `work_orders` is the pre-baseline hand-built table;
it carries legacy columns no repository migration declares, and at least one
(`title`) is NOT NULL with no default, so the repository's `create_work_order`
— which rightly writes no such column — can never insert a row.

**What the file does:** drops NOT NULL on every `work_orders` column that the
repository has never declared *and* that is NOT NULL with no default — the
exact set that can reject an insert. It is a sweep rather than a named fix
because these constraints bite one behind the other (the failing row shows
four legacy values; `title` is merely the first). Widening only: no row
accepted before is rejected after, nothing is dropped or written, re-running
is a no-op. Legacy columns that are nullable, or defaulted, are left alone.

**Ordering:** independent of §15 and §16 — apply it before, between, or after
them. It reasons about nothing later than `20260813101000` (the last file to
add a `work_orders` column).

**Apply:** paste the whole file into the SQL editor and run it. Expect one
`NOTICE` per column it loosens (`title` at minimum) — that list is this
database's inventory of the drift, worth keeping in the deploy log. Zero
notices means the drift is already reconciled. The file verifies itself in the
same transaction and fails loudly rather than reporting a half-success.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260822090000', 'hosted_work_order_column_drift')
on conflict (version) do nothing;
```

**Post-check, functional:** as a supervisor, open the department's work-orders
screen, tab "Raise work", pick the test complaint and press **Raise it** with
everything blank. A draft work order appears in the queue — that exact click
is the one that answered 422 before this file.

**What was checked before this section was written:** the static battery in
`backend/tests/test_hosted_work_order_drift_migration.py` — the file parses
(`pglast`), sorts after everything it reasons about, its protected list is
*derived* from `0001` + `0036` + `20260813101000`'s own text and compared
exactly (so a repository column can never be loosened by mistake), the only
DDL shape is the widening, the sweep only NOTICEs and the verification only
EXCEPTIONs. Not verifiable statically: which legacy columns the hosted table
actually has — the file's own NOTICEs are that census.

## 18. `20260822120000_supervisor_triage.sql`

Added 2026-08-22, with the supervisor dashboard. **§17 is a real precondition and
§16 is a hard one.**

* §17 (`20260822090000`) must be applied first *in practice*: until it is, no
  insert into `work_orders` succeeds at all, so a column added to that table is a
  column on a table nobody can write. Nothing in this file depends on it
  syntactically; the ordering is about whether the feature works.
* §16 (`20260821200000`) is the hard one. This file **redeclares
  `restamp_department_supervision`**, copied forward whole from §16 to gain one
  stamp. Applying §16 *after* this one would silently restore the version without
  it — same name, last write wins — and the "Inherited" badge would stop
  appearing with nothing anywhere erroring.

**Why it exists.** The supervisor's landing page in the worker portal is being
rebuilt as four stacked sections — new complaints, taken up by you, assigned but
not started, being worked right now — and three of the facts those sections need
had nowhere in the model to live:

* nothing recorded that a supervisor had **picked a complaint up**, so "new" and
  "mine, not yet dispatched" were the same row;
* nothing recorded when a worker pressed **Start**. `start_work_order` (`0039`)
  moved the status and let the instant fall into `updated_at`, which the next
  write overwrites — so "being worked right now" could show a job and not how
  long it had been going;
* §16 re-stamped a departed supervisor's live work onto whoever inherits it and
  deliberately left **no mark**, so the inheriting supervisor could not tell the
  work they chose from the work that arrived by somebody else's removal.

The product owner's four rulings behind this are
`docs/COMPLAINT_ENGINE_HANDOFF.md` §18; the frozen interface both specialists
built against is `docs/plans/SUPERVISOR_TRIAGE_SPEC.md`.

| Object | Change | Owned before this by |
|---|---|---|
| `complaints.taken_up_by_membership_id` | **new column**, `uuid references community_memberships(id) on delete set null` | — |
| `complaints.taken_up_at` | **new column**, `timestamptz` | — |
| `work_orders.started_at` | **new column**, `timestamptz` | — |
| `work_orders.supervision_inherited_at` | **new column**, `timestamptz` | — |
| `complaints_department_takeup_idx` | **new index** on `(department_id, taken_up_at, created_at desc)` | — |
| `take_up_complaint(uuid)` | **new** — the only writer of the two take-up columns | — |
| `supervisor_triage_snapshot(uuid)` | **new** — the dashboard's four sections in one read; a read, it writes nothing | — |
| `start_work_order(uuid)` | replaced; body copied forward whole, one line added so the moment lands in `started_at` | `0039` §481 |
| `restamp_department_supervision(uuid, uuid)` | replaced; body copied forward whole, one line added so re-stamped rows carry `supervision_inherited_at` | `20260821200000` §2 |

**No table, no view, no trigger, no policy, and nothing dropped.** Unlike §16,
this file has no `drop` statement of any kind — so the SQL Editor's "Potential
issue detected" popup should **not** appear. If it does, something in the file is
not what shipped.

**Three custom SQLSTATEs, all already mapped.** `HB403`, `HB404` and `HB409` go
through `backend/app/core/pg_errors.py` unchanged; no new code, so nothing in
Python needs to learn anything. The `HB409` on take-up **names the person who
already holds the complaint**, and that sentence reaches the screen — `pg_errors`
passes a custom code's message through.

**Take-up is triage ownership and not dispatch.** Ruling 1 of 2026-08-21 keeps
complaints department-pooled and `complaints.assigned_to_membership_id` dead;
this file writes neither that column nor `assignee_label`, and
`tests/test_supervisor_triage_migration.py` asserts the absence rather than
trusting the prose. What is recorded is *who is looking at it*, so two
supervisors do not both start arranging the same visit.

**`acknowledged` gains a second writer, deliberately.** Take-up moves the storage
status `open → acknowledged`, which the resident already reads as *In Progress*.
Until now the only writer was the worker-offer arm of
`project_complaint_from_jobs` (`20260813102000`). The two cannot race: both move
`open` and only `open`, so whichever runs second finds nothing to do. Nothing is
notified — a field changing with no action attached is the passive change
`ARCHITECTURE.md`'s rule exists to suppress.

**What to expect.** Two `alter table`s, one `create index`, four function
definitions, three grants, one revoke-and-regrant, and a `do` block. Everything
returns "Success. No rows returned"; the `do` block prints one `NOTICE` reading
*"supervisor_triage: four columns, four functions, both stamps in place."* If it
raises instead, **nothing has been half-applied** — the block runs in the same
transaction as the statements above it and its exception rolls the file back.

**A Python change ships with this one, and unlike §16's it is not urgent.** The
two new endpoints (`GET /departments/{id}/triage-snapshot`,
`POST /complaints/{id}/take-up`) call functions that do not exist until this file
is applied, so before that they answer with the repository's generic message and
the dashboard shows nothing. **No existing read breaks** — no projection anywhere
asks for the new columns by name, so the rest of the app is unaffected either
way. This is the opposite of §16, where "not applied yet" was a 400 on every
roster read.

**Post-check.** Paste the whole block below in one go. Every check either
self-selects the data it needs or reports that there is nothing to check.

```sql
do $$
declare
  v_name  text;
  v_src   text;
  v_count integer;
begin
  -- (a) The four columns exist, and every one of them is nullable. A NOT NULL
  --     here would mean somebody added a default, and every row that predates
  --     this file would be claiming a moment nobody lived through.
  for v_name in
    select w.col
      from (values ('complaints','taken_up_by_membership_id'),
                   ('complaints','taken_up_at'),
                   ('work_orders','started_at'),
                   ('work_orders','supervision_inherited_at')) w(tbl, col)
     where not exists (
       select 1 from information_schema.columns c
        where c.table_schema = 'public' and c.table_name = w.tbl
          and c.column_name = w.col and c.is_nullable = 'YES')
  loop
    raise exception
      'check (a) FAILED: % is missing, or is NOT NULL when it should be nullable.', v_name;
  end loop;

  -- (b) One definition of each function.
  foreach v_name in array array[
    'take_up_complaint',
    'supervisor_triage_snapshot',
    'start_work_order',
    'restamp_department_supervision']
  loop
    select count(*) into v_count
      from pg_proc
     where pronamespace = 'public'::regnamespace and proname = v_name;
    if v_count <> 1 then
      raise exception
        'check (b) FAILED: % definition(s) of %, expected exactly 1.', v_count, v_name;
    end if;
  end loop;

  -- (c) The two copied bodies carry their stamp AND kept what they had. This is
  --     the check that stands between the deploy and a dashboard section that is
  --     permanently empty with nothing erroring.
  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace and proname = 'start_work_order';
  if v_src not like '%started_at = coalesce(started_at, now())%' then
    raise exception 'check (c) FAILED: start_work_order does not stamp started_at.';
  end if;
  if v_src not like '%work_order.started%' then
    raise exception 'check (c) FAILED: the resident notification was lost in the copy.';
  end if;
  if v_src not like '%job_started%' then
    raise exception 'check (c) FAILED: the timeline event was lost in the copy.';
  end if;

  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace
     and proname = 'restamp_department_supervision';
  if v_src not like '%supervision_inherited_at%' then
    raise exception
      'check (c) FAILED: restamp_department_supervision does not stamp the inheritance. An older definition won — check whether 20260821200000 was applied after this file.';
  end if;
  if v_src not like '%department_supervision_successor%' then
    raise exception 'check (c) FAILED: the successor rule was lost in the copy.';
  end if;

  -- (d) Ruling 1, still true: nothing new writes the dead column.
  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace and proname = 'take_up_complaint';
  if v_src like '%assigned_to_membership_id%' or v_src like '%assignee_label%' then
    raise exception 'check (d) FAILED: take_up_complaint writes a dispatch column.';
  end if;

  raise notice 'checks (a)-(d) OK: four columns, four functions, both stamps, and the dead column still dead.';
end $$;

-- (e) The snapshot answers for a real department. Four empty arrays is the
--     ordinary answer on a young database; an error is not.
select d.name, public.supervisor_triage_snapshot(d.id) as dashboard
  from public.departments d
 where d.kind = 'service'
 order by d.created_at
 limit 1;

-- (f) The new columns against real data. All zero before anybody presses
--     anything, which is what a new column looks like.
select count(*) filter (where taken_up_at is not null) as taken_up,
       count(*)                                        as complaints
  from public.complaints;
select count(*) filter (where started_at is not null)               as started,
       count(*) filter (where supervision_inherited_at is not null) as inherited,
       count(*)                                                     as work_orders
  from public.work_orders;
```

**Record it in the ledger** (§12 explains why the SQL Editor does not do this for
you):

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260822120000', 'supervisor_triage')
on conflict (version) do nothing;
```

**Functionally, after this file:** sign in as a service department's supervisor
and open `/worker`. The four sections appear. A complaint routed to that
department sits in **New complaints**, with its category and priority chips and,
where it applies, a *Returned to pool* / *Reopened ×N* / *Moved to this
department* badge. Press **Take up**: it moves to section 2, the resident's own
screen starts saying *In Progress* within an SSE beat, and the complaint's
timeline gains *"Taken up by the department"*. Raise a job on it and offer it to
somebody, and it leaves section 2 and appears in **Assigned, work pending** as
that job. Have the worker press **Start** in their portal and it moves to **Being
worked right now** with an elapsed time that keeps counting. Finally, remove the
supervisor who owns a live job: the job re-stamps onto whoever inherits it,
exactly as §16 described, and now carries an **Inherited** badge on the new
holder's dashboard.

**Until the file is applied**, both new endpoints fail with the repository's
generic message and the dashboard's four sections stay empty. Nothing else
changes: no existing read asks for any of the four columns.

### What was checked before this section was written

Static only — nothing below was run against any database. The checks are
automated in `backend/tests/test_supervisor_triage_migration.py` (29 tests) rather
than done once by hand, so they re-run on every change to the file.

| Check | Result |
|---|---|
| The file parses as valid PostgreSQL (`pglast.parse_sql`) | Pass |
| The 90-line snapshot query parses **on its own** — a function body is one opaque string to the outer parse, so the whole-file check says nothing about it | Pass |
| It sorts after `0036`, `0039`, `20260812090300`, `20260813102000`, `20260813103000`, `20260821200000` and `20260822090000` | Pass |
| It is the **last** file in the directory declaring `start_work_order` and `restamp_department_supervision` | Pass — computed from the directory, not from a remembered list |
| It redeclares none of the fourteen other names the sibling static-check files pin — in particular the trigger that calls the re-stamp, the successor rule, and the status-projection trigger | Pass |
| It never writes `complaints.assigned_to_membership_id` or `assignee_label` (ruling 1) | Pass |
| `take_up_complaint` is the only writer of both take-up columns, moves the status only from `open`, writes the timeline row, and notifies nobody | Pass |
| It refuses three ways — `HB404` unknown, `HB403` not yours, `HB409` naming the holder — locks the row first, and is a no-op for the person who already holds it | Pass |
| An unrouted complaint is `HB409` and not `HB403`: what is missing is the routing, not a permission | Pass |
| Both copied bodies are **purely additive** — every non-blank line of the owning file's version is present verbatim | Pass — compared line by line against `0039` and `20260821200000`, not against a remembered list |
| Neither copy changes its signature or return type, which `create or replace` would refuse | Pass |
| Each new stamp has exactly one writer, and `started_at` cannot be reset (`coalesce`, never bare `now()`) | Pass |
| The inheritance stamp is written in the same statement, with the same scope, as the re-stamp it marks | Pass |
| The snapshot asks `can_supervise_department` and **refuses** rather than answering empty | Pass |
| The snapshot is `stable` and contains no `insert`, `update`, `delete` or `notify_` | Pass |
| The four bucket predicates are defined in the RPC and nowhere else, and every section is newest-first | Pass |
| The snapshot translates no vocabulary — no `'High'`, `'Low'`, `'Pending'` or `'In Progress'` anywhere in it | Pass |
| `reroutedAt` is derived from `department_assigned` events naming this department, and no column was added for it | Pass |
| The four columns are added `if not exists`, nullable, with no default | Pass |
| Nothing destructive: no `drop` of any kind, no `delete`, no `alter column`, exactly two `alter table`s and both `add column if not exists` | Pass |
| Every SQLSTATE it raises is one `pg_errors` maps | Pass — the set is exactly `{HB403, HB404, HB409}` |
| It verifies itself in the same transaction, probing both `prosrc` stamps, and writes nothing while doing so | Pass |
| Every field the two Python DTOs carry is a column the RPC projects | Pass — read out of `TriageComplaint`/`TriageWorkOrder`'s own `model_fields` |

**Not verifiable statically**, and left for the post-checks above: whether the
hosted `start_work_order` and `restamp_department_supervision` were in fact
`0039`'s and `20260821200000`'s text before this file replaced them (post-check
(c)'s five fragments are the probe); whether the hosted `complaints` and
`work_orders` accept the four new columns without colliding with a legacy column
of the same name, which only the apply will say; and whether the four sections
bucket a real department's work correctly, which needs rows and is post-check
(e).

## 19. `20260822150000_taken_up_event_word.sql`

**What breaks without it:** the Take-up button — the whole point of §18's
migration — answers 422 "Could not take that complaint up." on every press.
Found live on 2026-08-22, on the very first Take-up press after §18 was
applied. The captured Postgres error is 23514: `new row for relation
"complaint_events" violates check constraint "complaint_events_type_check"`.

**Why:** `take_up_complaint` (§18) writes a timeline row with `event_type =
'taken_up'`, a word `complaint_events_type_check` does not allow. §18's file
reasoned from `0001_baseline.sql` ("event_type is text with no CHECK") and
missed that `20260813105000` had bolted an enumerating constraint on later.
The vocabulary changed, so the constraint is what moves.

**What the file does:** recreates `complaint_events_type_check` with the same
twenty-five words plus `taken_up` — the same drop-and-recreate shape as the
file that created the constraint. A guard first proves no stored row is
outside the new list (an exception there leaves the old constraint standing
untouched); a verification block then proves the recreated constraint knows
the new word. Widening only: every row the old constraint accepted, the new
one accepts. Re-running drops and recreates the same constraint — idempotent.

**Ordering:** after `20260813105000` and `20260822120000` (§18), which it
sorts after by name. Independent of everything else.

**Apply:** paste the whole file into the SQL editor and run it. No output
expected on success; it fails loudly rather than reporting a half-success.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260822150000', 'taken_up_event_word')
on conflict (version) do nothing;
```

**Post-check, functional:** as a supervisor, press **Take up** on a complaint
on the dashboard. The card moves to "Taken up by you", and the resident's
timeline gains "Taken up by the department". That exact press is the one that
answered 422 before this file.

**What was checked before this section was written:** the static battery in
`backend/tests/test_taken_up_event_word_migration.py` (6 tests) — the file
parses (`pglast`), sorts after the constraint's creator and the word's
writer, its word list is *derived* from `20260813105000`'s own text plus
exactly `taken_up` (so no allowed word can be dropped by mistake), §18's file
writes no *other* word outside the old list (so this cure has no hidden
sibling), the only DDL is the drop-and-add pair on this one constraint, the
guard runs before the DROP, and the verification probes for `taken_up`
specifically — a bare existence check would pass against the very constraint
this file replaces. Not verifiable statically: the hosted constraint's actual
current word list — the guard and the verification are that probe.

## 20. `20260822170000_supervisor_actions.sql`

Added 2026-08-22 with **amendment 2** of the supervisor dashboard: the buttons on
the cards. §18 gave the supervisor a screen that reads and one verb; this is the
rest of the verbs, the chat behind them, and the one correction to the snapshot
they forced.

**Ordering: after `20260822150000` (§19), which it sorts after by name.** That is
the tight one — this file recreates the *same* `complaint_events_type_check`, and
applying §19 afterwards would silently drop `priority_changed` back out of the
vocabulary and give the Raise-priority button §19's own 23514. It also sorts
after `0046` (whose `dm_threads_kind_check` it widens), `20260813104000` (whose
`complaints_on_resolved` trigger it depends on) and `20260822120000` (§18, whose
snapshot it replaces). Everything it needs is already applied.

**Why it exists.** Four product rulings of 2026-08-22
(`docs/plans/SUPERVISOR_TRIAGE_SPEC.md`, *Amendment 2*):

* **A1** — the card's chat is a *real thread* in the existing dock, between the
  resident who raised the complaint and the department that owns it, not a
  comments panel;
* **A2** — *Resolved* cancels the unstarted jobs and refuses while one is
  running;
* **A3** — an offered job nobody has accepted is an **open request**, not
  assigned work, which re-buckets the dashboard from four sections into five;
* **A4** — the supervisor's *Assign* is a true force-assign: no decline.

| Object | Change | Owned before this by |
|---|---|---|
| `dm_threads.complaint_id` | **new column**, `uuid references complaints(id) on delete cascade` | — |
| `dm_threads_kind_check` | **recreated**: `direct`, `work_order`, **`complaint`** | `0046` §1 |
| `dm_threads_complaint_subject_check` | **new**: `kind = 'complaint'` iff `complaint_id is not null` | — |
| `dm_threads_one_per_complaint` | **new unique index** on `complaint_id where kind = 'complaint'` | — |
| `complaint_events_type_check` | **recreated**: §19's twenty-six words plus `priority_changed` | `20260822150000` |
| `can_supervise_complaint(uuid)` | **new** — the thread's access rule, once, for two policies and one function | — |
| `lock_complaint_threads()` + `complaints_lock_dm_threads` | **new** trigger: closed/cancelled locks the chat, anything else unlocks it | — |
| `dm_threads_read`, `dm_messages_read` | **recreated** policies: the department reads its complaint threads | `0046` §6 |
| `post_dm_message(uuid, text)` | replaced; body copied forward whole, three blocks added so a department supervisor may write in its own complaint thread | `0046` §3 |
| `supervisor_resolve_complaint(uuid)` | **new** | — |
| `raise_complaint_priority(uuid)` | **new** | — |
| `add_complaint_note_internal(uuid, text)` | **new** | — |
| `open_complaint_thread(uuid)` | **new** | — |
| `force_assign_work_order(uuid, uuid, timestamptz, timestamptz)` | **new** — `dispatch_force_assign`'s mechanics, with the picking removed and a guard added | — |
| `supervisor_triage_snapshot(uuid)` | **dropped and recreated**: five sections, `offered_to_name` | `20260822120000` §5 |

**There are four `drop`s and the SQL Editor will warn about them.** Unlike §18,
this file *does* trip the "Potential issue detected" popup: `drop function` on
the snapshot (it is being replaced by a different answer, so the old one should
not be reachable), `drop policy` twice and `drop trigger` once (neither
`create policy` nor `create trigger` has an `or replace`). Every one is followed
immediately by its replacement in the same transaction. **Nothing else is
dropped** — no table, no column, no index, no view — and the static battery
asserts that by name.

**Four custom SQLSTATEs, all already mapped.** `HB403`, `HB404`, `HB409` and
`HB422` go through `backend/app/core/pg_errors.py` unchanged. The messages are
written for a person and reach the screen: *"Somebody is working on this right
now. Finish or cancel the running job first."*, *"This complaint is already at
the highest priority."*, *"Ravi Kumar is already booked during that time."*

**One thing this file deliberately does not do, and it is worth knowing before
you read the code.** `supervisor_resolve_complaint` writes **no** `status_changed`
event and sends **no** notification to the resident. `complaints_on_resolved`
(`20260813104000`) is an `after update of status` trigger that already writes
both and enqueues the 48-hour warning and the 72-hour auto-close; this function
moves the status, so all four happen in the same transaction. Doing it here as
well would put two *"Status changed to Resolved"* lines on one timeline and buzz
one phone twice. **The verification block refuses to apply the file if that
trigger is missing**, because a Resolve that tells the resident nothing is a
failure with no symptom.

**What to expect.** One `alter table … add column`, two constraint swaps each
preceded by its own guard block, one unique index, two policies, one trigger,
nine function definitions, eight grants and two revokes, and a `do` block.
Everything returns "Success. No rows returned"; the final `do` block prints one
`NOTICE` reading *"supervisor_actions: chat kind, five verbs, five sections and
one new event word in place."* If it raises instead, **nothing has been
half-applied** — it runs in the same transaction as the statements above it and
its exception rolls the file back.

**Post-check.** Paste the whole block below in one go.

```sql
do $$
declare
  v_name  text;
  v_src   text;
  v_count integer;
begin
  -- (a) The chat kind, its column, its index and its subject rule.
  if not exists (select 1 from information_schema.columns
                  where table_schema = 'public' and table_name = 'dm_threads'
                    and column_name = 'complaint_id') then
    raise exception 'check (a) FAILED: dm_threads.complaint_id is missing.';
  end if;
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.dm_threads'::regclass
                    and conname = 'dm_threads_kind_check'
                    and pg_get_constraintdef(oid) like '%complaint%') then
    raise exception 'check (a) FAILED: dm_threads_kind_check does not allow complaint threads.';
  end if;
  if not exists (select 1 from pg_indexes
                  where schemaname = 'public' and indexname = 'dm_threads_one_per_complaint') then
    raise exception 'check (a) FAILED: the one-thread-per-complaint index is missing.';
  end if;

  -- (b) The event vocabulary kept BOTH of the last two words added to it. If
  --     priority_changed is there and taken_up is not, this file was applied
  --     before 20260822150000 and the Take-up button is broken again.
  select pg_get_constraintdef(oid) into v_src
    from pg_constraint
   where conrelid = 'public.complaint_events'::regclass
     and conname  = 'complaint_events_type_check';
  if v_src is null or v_src not like '%priority_changed%' then
    raise exception 'check (b) FAILED: the event check does not allow priority_changed.';
  end if;
  if v_src not like '%taken_up%' then
    raise exception 'check (b) FAILED: taken_up was lost -- 20260822150000 (section 19) must be applied BEFORE this file.';
  end if;

  -- (c) One definition of each function.
  foreach v_name in array array[
    'supervisor_resolve_complaint',
    'raise_complaint_priority',
    'add_complaint_note_internal',
    'open_complaint_thread',
    'force_assign_work_order',
    'can_supervise_complaint',
    'lock_complaint_threads',
    'supervisor_triage_snapshot',
    'post_dm_message']
  loop
    select count(*) into v_count
      from pg_proc
     where pronamespace = 'public'::regnamespace and proname = v_name;
    if v_count <> 1 then
      raise exception 'check (c) FAILED: % definition(s) of %, expected exactly 1.', v_count, v_name;
    end if;
  end loop;

  -- (d) The copied body carries its addition AND kept what it had. This is the
  --     check that stands between the deploy and a chat a second supervisor can
  --     open, watch, and never answer in.
  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace and proname = 'post_dm_message';
  if v_src not like '%can_supervise_complaint%' then
    raise exception 'check (d) FAILED: post_dm_message does not admit the department.';
  end if;
  if v_src not like '%This conversation is closed.%' then
    raise exception 'check (d) FAILED: the lock was lost in the copy.';
  end if;
  if v_src not like '%notify_profile%' then
    raise exception 'check (d) FAILED: the counterpart notification was lost in the copy.';
  end if;

  -- (e) The snapshot is the five-section version, and the trigger Resolve leans
  --     on is present.
  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace and proname = 'supervisor_triage_snapshot';
  if v_src not like '%open_requests%' or v_src not like '%offered_to_name%' then
    raise exception 'check (e) FAILED: an older snapshot definition won.';
  end if;
  if not exists (select 1 from pg_trigger
                  where tgrelid = 'public.complaints'::regclass
                    and tgname = 'complaints_on_resolved' and not tgisinternal) then
    raise exception 'check (e) FAILED: complaints_on_resolved is missing; Resolve would tell the resident nothing.';
  end if;

  raise notice 'checks (a)-(e) OK: chat kind, both event words, nine functions, the copy intact, five sections.';
end $$;

-- (f) The snapshot answers, and its keys are the five the frontend renders.
select jsonb_object_keys(public.supervisor_triage_snapshot(
  (select id from public.departments where kind = 'service' order by created_at limit 1)));
-- expect six rows: department_id, new_complaints, taken_up, open_requests,
--                  assigned_pending, in_progress.

-- (g) No complaint thread exists yet, which is what a new kind looks like.
select count(*) filter (where kind = 'complaint') as complaint_threads,
       count(*)                                   as threads
  from public.dm_threads;
```

**Record it in the ledger** (§12 explains why the SQL Editor does not do this for
you):

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260822170000', 'supervisor_actions')
on conflict (version) do nothing;
```

**Functionally, after this file — press each new button once.** Sign in as a
service department's supervisor and open `/worker`.

1. **Note** on any card: type a line, save. It appears on the *staff* timeline
   with your name; open the same complaint on the resident's portal and it is
   **not** there. The admin's own *Update from management* notes still are.
2. **Chat** on any card: it opens the dock on a thread seeded with *"The
   department opened this chat about '…'."* Send a line. The resident sees it in
   their ordinary thread list and can answer. Press the button again — the same
   thread, not a second one.
3. **Raise priority** on a `Low` complaint: the chip goes amber, the timeline
   gains *"The department raised the priority to Medium."*, and a live job on the
   same complaint shows the new urgency. Press it twice more and the third press
   is a `409` naming the ceiling.
4. **Assign** from an *Open job requests* card with the force option: the job
   moves to **Assigned, work pending** immediately, and the worker's own card
   shows it accepted with no Decline button.
5. **Mark as resolved** on a complaint with an offered job: the job is cancelled,
   the offered worker gets *"A job of yours was cancelled"*, the resident's screen
   says *Resolved* and asks them to confirm or reopen. Then try it on a complaint
   whose worker has pressed **Start** — that one is refused, in words.

**Until the file is applied**, the four new endpoints fail with their
repositories' generic messages, `force: true` fails the same way (the default
offer path is unaffected), and the dashboard's fifth section is empty because the
applied snapshot does not emit it. **No existing read breaks**: the four sections
§18 shipped keep working from the old definition until this replaces it.

### What was checked before this section was written

Static only — nothing below was run against any database. The checks are
automated in `backend/tests/test_supervisor_actions_migration.py` (42 tests) and
`backend/tests/api/test_supervisor_actions.py` (17 tests) rather than done once by
hand, so they re-run on every change.

| Check | Result |
|---|---|
| The file parses as valid PostgreSQL (`pglast.parse_sql`) | Pass |
| The five-section snapshot query parses **on its own** — a function body is one opaque string to the outer parse | Pass |
| It sorts after `0036`, `0046`, `20260813101000`, `20260813104000`, `20260813105000`, `20260822120000` and `20260822150000` | Pass |
| It is the **last** file in the directory declaring `post_dm_message` and `supervisor_triage_snapshot` | Pass — computed from the directory, not from a remembered list |
| The new event list is §19's list **plus exactly `priority_changed`** | Pass — derived from `20260822150000`'s own text, so no allowed word can be dropped by mistake |
| Every event word this file *writes* is one the constraint it recreates allows | Pass — the 2026-08-22 23514, asked before the apply rather than after |
| The thread-kind list is `0046`'s **plus exactly `complaint`** | Pass — derived the same way |
| Both constraint swaps run their guard **before** the DROP, so a failure leaves the old constraint standing | Pass |
| The verification proves `priority_changed` specifically — a bare existence check would pass against the constraint being replaced | Pass |
| `post_dm_message` is copied forward **purely additively** — every non-blank line of `0046`'s version present verbatim — with an unchanged signature and return type | Pass — compared line by line |
| Read and write of a complaint thread ask **one** rule (`can_supervise_complaint`), in both policies and the function | Pass |
| The complaint thread is one row per complaint, cascades, and is written by the opener alone | Pass |
| The lock mirrors the job thread's and **unlocks** on the way back out, because a complaint can be reopened | Pass |
| Resolve refuses a running job and a settled complaint, cancels every other live job, withdraws its assignments and notifies their workers with the frozen reason | Pass |
| Resolve writes **no** `status_changed` and **no** resident notification, and the file refuses to apply without `complaints_on_resolved` | Pass |
| Priority is one-way, stops at `high`, carries onto live jobs, leaves the SLA promise alone, translates no vocabulary and notifies nobody | Pass |
| The note is flagged `internal: true`, bounded 1–2000 with `HB422`, and names its author | Pass |
| All five complaint RPCs ask `can_supervise_department`, and all four verbs refuse an unrouted complaint as `HB409` rather than `HB403` | Pass |
| Force-assign writes an `is_forced` accepted row, both timeline events and the same notifications as the engine's own, withdraws the previous holder, refuses a terminal job, and neither redeclares nor calls `dispatch_force_assign` | Pass |
| The five buckets are defined in the RPC and nowhere else; *committed* excludes an unaccepted offer; the two complaint sections exclude **any** live work order | Pass |
| `assigneeName` and `offeredToName` are read from two different assignment statuses | Pass |
| The snapshot is still `stable` with no write verb, is re-granted after being dropped, sorts every section newest-first, and translates no vocabulary | Pass |
| Every field of `TriageComplaint`/`TriageWorkOrder` is a column the RPC projects, and every section key is a `TriageSnapshot` field | Pass — read out of the models' own `model_fields` |
| Nothing destructive beyond the four named `drop`s; the six `alter table` clauses are exactly the ones listed above | Pass |
| Every SQLSTATE it raises is one `pg_errors` maps | Pass — `{HB403, HB404, HB409, HB422}` plus `42501`/`22004` from the copied body |
| Every function it declares is granted to somebody, except the trigger function, which is revoked | Pass |

**Not verifiable statically**, and left for the post-checks above: whether the
hosted `post_dm_message` was in fact `0046`'s text before this file replaced it
(post-check (d)'s three fragments are the probe); whether `complaints_on_resolved`
is present on the hosted database, which decides whether Resolve tells the
resident anything (the apply itself now refuses without it); whether the hosted
`complaint_events_type_check` really carries §19's `taken_up` before this file
rewrites the list (post-check (b) is that probe); and whether the five sections
bucket a real department's work correctly, which needs rows and is post-check (f)
plus the five button presses.

---

## 21. `20260817144725_repair_staff_assignment_employment_type.sql`

> ### ALREADY APPLIED AND LEDGERED on hosted (2026-08-17, applied by the services-and-security workstream) — recorded for completeness; **do NOT run**.
>
> There is no apply step in this section and no ledger insert to paste. The row
> for version `20260817144725` is already in
> `supabase_migrations.schema_migrations`. Everything below is *what happened*,
> written down because the file only reached this branch on 2026-08-22 and a
> reader finding a new `.sql` in the directory with no section would reasonably
> conclude it was outstanding work.

**Where it sits.** By filename it sorts between the addendum files of §10–§12
(`20260812…`) and §13 (`20260821113000`) — that is, before every section from
§13 onward, and after every section before it. It was applied in that position
on the hosted timeline too. Its section number is 21 because this document
numbers sections in the order they were written, and renumbering would break
every cross-reference in it and in `docs/CHANGE_LOG.md`.

**What breaks without it:** hiring a worker. `decide_service_application` — the
one RPC that creates a membership and a roster row in the same transaction
(`0035`, rewritten by `20260811162409`) — inserts `employment_type = 'staff'`.
On the hosted database that insert answered **23514**, `new row for relation
"staff_assignments" violates check constraint
"staff_assignments_employment_type_check"`, and every hire failed. This is the
constraint half of issue #33; the other half was RLS on `staff_assignments`,
which is §11 (`20260812200000`) and was already applied.

**Why:** the hosted `staff_assignments` predates `0001_baseline.sql`. Its
hand-built `employment_type` check allowed `internal` and `vendor` — the
vendor-vs-in-house distinction the pre-baseline schema modelled — and knew
nothing of `staff`, which is the value `0019_departments_on_baseline.sql:216`
made the column's default and which every hiring path in the repository has
written since. `0001_baseline.sql:63` declares the column as a bare
`employment_type text not null` with no check at all, so on a database built
from the baseline the constraint does not exist until this file makes it, and
nothing in the repository ever noticed the hosted list was short.

**What the file does:** two statements, and that is the whole file.

```sql
alter table public.staff_assignments
  drop constraint if exists staff_assignments_employment_type_check;

alter table public.staff_assignments
  add constraint staff_assignments_employment_type_check
  check (employment_type in ('internal', 'vendor', 'staff'));
```

Widening only: both legacy values are kept, one is added, so every row the old
constraint accepted the new one accepts. Re-running drops and recreates the same
constraint — idempotent.

**Provenance, and why it is not rewritten.** The file was written on
`origin/main` (commit `c0956a2`, Aishik Bandyopadhyay, 2026-08-17), applied to
hosted that day, and ledgered. It never existed on `live-app-fixes` until
2026-08-22, when it was copied over **byte for byte** (git blob `52d2f79`,
unchanged) so that git and the ledger describe the same thing under the same
version. A file with a ledger row can never be corrected in place: any edit
makes version `20260817144725` mean one thing on hosted and another in git, and
nothing downstream can tell which it has. That is the disease §22 is about, in
miniature.

**One residual defect, recorded for the record only — do not act on it.** The
file adds the constraint without `not valid` and without a pre-flight scan for
rows that would violate it. Compare §19's shape
(`20260822150000_taken_up_event_word.sql:22-40`), which proves no stored row is
outside the new list *before* it drops anything, so a failure leaves the old
constraint standing and names what is in the way. Had the hosted
`staff_assignments` held an `employment_type` outside the three words, this file
would have failed the `add constraint` with a bare 23514 naming no row. It did
not — the apply succeeded on 2026-08-17 — so the risk is retired and the file is
immutable. It is written down here so the next constraint repair copies §19
rather than this.

**Post-check, if you want to confirm the state you already have:**

```sql
select pg_get_constraintdef(oid) as definition
  from pg_constraint
 where conname = 'staff_assignments_employment_type_check';
-- expect: CHECK ((employment_type = ANY (ARRAY['internal'::text,
--         'vendor'::text, 'staff'::text])))
```

Functionally: hire a service professional into a department from the hiring tab.
Before this file that press answered a 23514-shaped failure; it has worked since.

**What was checked before this section was written:** the static battery in
`backend/tests/test_employment_type_repair_migration.py` (6 tests) — the file
parses (`pglast`); its only DDL is the drop-and-add pair, both naming this one
constraint on this one table; the allowed list is *derived* from the file's own
text and is exactly `{internal, vendor, staff}`; **every `employment_type`
literal any migration in the directory writes is a member of that list**, the six
inserts found by lining each `insert into public.staff_assignments` column list
up with its `values` list positionally, because the column is never named beside
its value; `0001_baseline.sql` still declares the column with no check of its
own; and the file sorts after both *apply-time* writes of the column (the
baseline's declaration and `0019`'s default). Two files that write `staff` —
`20260821140000` and `20260821170000` — sort *after* this one, which is correct
and is asserted as such: their write is a line of plpgsql inside
`claim_staff_invitations` that runs when a manager claims an invitation, not
when the migration is applied. Membership in the allowed list is what protects
them; order cannot. **Not verifiable statically:** whether the hosted table held
a row outside the three words at apply time — the apply itself was that probe,
and it passed.

---

## 22. Reconciliation record — issue #41, hosted vs `origin/main`

**This is not an apply section.** Nothing in it was run against the hosted
database except read-only queries, and nothing in it asks you to run anything.
It was written as the answer to "which of these files is real?", because that
answer had stopped being obvious. Since 2026-08-23 it is also the answer to
"what is the hosted schema, then?" — because the first answer turned out to be
wrong, in the one way this section had pre-registered a stop rule for.

### What is on this branch and on hosted

All six cloud-side migrations named in issue #41, plus
`20260822120000_supervisor_triage.sql` (§18) and
`20260822170000_supervisor_actions.sql` (§20), are **committed and pushed on
`origin/live-app-fixes`** — they arrived with commit `65f852c`. Every one of them
has a numbered section above, a `docs/CHANGE_LOG.md` entry, and a ledger row.
`origin/main`'s `20260817144725` is ledgered on hosted and is now mirrored into
this branch byte for byte (§21). As of the evening of 2026-08-22 the hosted
database and this branch agree, and **no migration is outstanding** — that
remains true, and it is a statement about migration *files*. It is not a
statement about the hosted schema, which the probe campaign below shows diverges
from this directory in ways no migration will ever close.

### Correction — the probe was run, and it came back the other way

**The 2026-08-22 draft of this section was wrong on a point of fact.** It said
the snapshot had "no runbook section, no CHANGE_LOG entry, **and no ledger
row**", and reasoned from the third of those that the file had never been
applied. The query printed below that claim existed to settle it from the ledger
rather than from this document. The owner ran it on 2026-08-23 and it returned
**two rows, not one**:

```
20260817144725|repair_staff_assignment_employment_type
20260818141040|remote_schema
```

The pre-registered stop rule — *if `20260818141040` comes back present, stop and
do not merge; the question changes from "delete the file" to "what is the hosted
schema now"* — fired exactly as written, and the rest of this section is that
investigation.

The withdrawn claim is worth naming precisely, because the same mistake is easy
to make again: **"no paper trail" was treated as evidence of "never applied".**
It is not. It is evidence that nobody wrote the paper. Rule 1 in
`backend/supabase/migrations/README.md` says a file with no runbook section and
no CHANGE_LOG entry *has not been applied* — that rule describes what the team
undertakes to do, not what the database will confirm, and this is the case where
the two came apart. Two of the three legs of the claim stand: there is still no
runbook section for the snapshot and still no CHANGE_LOG entry for it. Only the
ledger leg is withdrawn, and everything that was inferred from it is re-derived
below.

### What the investigation found

**Hosted is not a database this directory built.** `0001_baseline.sql` was never
applied to the linked project — the project predates it — and everything since
has been laid on top of a hand-built pre-baseline schema. That is not news and
it is not damage: `backend/supabase/migrations/README.md` says it in as many
words, and `dashboard_repository.schema_generation()` exists precisely to detect
it, probing for one pre-baseline table and running legacy-mode projections when
it finds one. Hosted is a **deliberate legacy hybrid**, and the repository has
been written that way on purpose for weeks.

**Which is what the snapshot was a picture of.** `supabase db diff` emits the
statements that would transform the local shadow database — built by replaying
this directory from empty — **into** the hosted one. The direction matters and
explains the whole file: every statement in it describes something hosted really
had on 2026-08-18 that a from-scratch replay of this directory does not produce.
The 9,831 lines were not a proposal, an accident, or a plan; they were an
accurate report of the legacy hybrid, rendered as DDL and committed in the one
place where DDL is read as an instruction.

**So the ledger row is not the alarm it first looked like.** Nobody applied
9,831 lines of DDL to hosted. The row says version `20260818141040` was recorded
against the hosted project; the probes below say the hosted schema is the
legacy-hybrid it already was, not the schema those statements would have
produced. The correct reading is a ledger entry written for a file that
described hosted rather than changed it.

### The probe result set, verbatim

Read-only queries, run by the owner against the linked project on 2026-08-22 and
2026-08-23. Nothing here writes.

- **(a) The ledger.** `supabase_migrations.schema_migrations` contains **both**
  `20260817144725|repair_staff_assignment_employment_type` and
  `20260818141040|remote_schema`.
- **(b) Issue #33's constraint.**
  `staff_assignments_employment_type_check` on hosted is
  `CHECK (employment_type = ANY (ARRAY['internal','vendor','staff']))` — §21's
  repair is in place and confirmed.
- **(c) The four "damage" claims, measured.**
  `to_regclass('public.visitor_access_requests')` → **present**;
  `dashboard_sse_amenity_bookings` and `dashboard_sse_visitor_requests` triggers
  → **0**; the seven `0001_baseline.sql` policies (`profiles_self`,
  `memberships_self`, `communities_member`, `units_member`, `invites_admin`,
  `access_requests_admin_read`, `access_requests_applicant_read`) → **0**;
  extension `pg_net` → **0**.
- **(d) The generated columns.** `communities.location` and
  `service_providers.location` both have `attgenerated = 's'` on hosted —
  generated, exactly as this directory declares them. The snapshot's
  `SET DEFAULT` lines against them are diff-rendering noise, and the theory that
  hosted holds them as plain columns is **refuted**.
- **(e) The invite-claim RPC.** Only
  `claim_resident_invite(p_invite_id uuid, p_profile_id uuid)` exists on hosted.
  `claim_email_invitation` **does not exist**, and the backend calls that name.
- **(f) The access-request status type.** `access_requests.status` on hosted is
  the enum `public.request_status` = `{pending, approved, rejected, cancelled}`.
  There is no `withdrawn`.
- **(g) Trigger inventory.** `amenity_bookings` → `amenity_bookings_sse`;
  `visitor_access_requests` → `dashboard_sse_visitor_access_requests`;
  `legacy_amenity_booking_series` → `dashboard_sse_amenity_booking_series`;
  `visitor_requests` → **no trigger**.
- **(h) Row counts.** `visitor_access_requests` = 0, `visitor_requests` = 3,
  `legacy_amenity_booking_series` = 0, `amenity_bookings` = 0.

### The fresh-apply analysis stands; the damage framing does not

**Everything the 2026-08-22 draft said about a *fresh* apply is unchanged and
still true.** Replayed into an empty database — which is what CI's
`database-browser` job does to this directory on every push — the snapshot dies
at its own line 1314 on an `ALTER` of a generated column: Postgres refuses
`set default` on a generated column and refuses `set data type` on a column a
generated expression reads, and the snapshot emits both for `communities.location`,
`service_providers.location` and `invoice_line_items.total_amount`. While a file
of that shape sits in this directory, no branch can go green. And if it *had*
got past line 1314 on a fresh database it would have done every one of the harms
listed: recreated the pre-baseline sentinel table that
`dashboard_repository.schema_generation()` probes for, so a brand-new database
would report itself as the legacy schema and the dashboard would read
projections built for another shape; dropped two `dashboard_sse_*` triggers
without recreating them; dropped seven `0001_baseline.sql` policies it never
replaces; dropped extension `pg_net`; and brought back most of the twenty tables
retired by `94556e5`/`76e1b15`.

**What is corrected is the framing of those same lines as damage *to hosted*.**
Probe (c) measures each of them on the live database and finds the state the
snapshot describes, because the snapshot describes hosted. Taken one at a time:

- The **sentinel table** is present on hosted, and that is the intended
  arrangement, not a wound: it is what makes `schema_generation()` return
  `legacy`, which is the mode the whole dashboard read path was written for.
- The **two "missing" SSE triggers** fire on tables the legacy branch never
  reads. Hosted covers realtime through differently-named triggers on the tables
  it does read — probe (g) lists them. Nothing is silent.
- The **seven "missing" policies** have renamed hosted equivalents for six of
  them; the seventh guards a table only the service role reaches. The names
  differ because hosted's RLS predates the baseline that chose those names.
- **`pg_net`** has zero references anywhere in this repository. The shadow
  database has it because the Supabase CLI's default local stack installs it.
  Its absence on hosted costs nothing.

So the harms are real, and they are real **for a fresh apply and for CI**, which
is reason enough that the file cannot live in this directory. On hosted they are
not harms at all: they are a description of a standing, deliberate arrangement
that predates every file here.

### The remedy — version `20260818141040` is tombstoned

Deletion was the 2026-08-22 plan and it is no longer available: the ledger row
exists, and a version in `supabase_migrations.schema_migrations` with no file
behind it reads as a permanently missing migration to `supabase migration list`
and to anyone auditing the two against each other. The version has to stay.
What goes is the body.

`backend/supabase/migrations/20260818141040_remote_schema.sql` exists on this
branch as a **comment-only file** — a tombstone. It contains no SQL at all: what
the version was, what the original file was, why it could not stay, and a
pointer back to this section. That single move settles all three readers at once:

- **git** — the directory has a file at that version again, with an explanation
  a reader will find before they go looking for the 9,831 lines in history;
- **a fresh `supabase db reset`** — there is nothing to apply, so there is
  nothing to fail, and the CI replay goes green;
- **the hosted ledger** — its row still has a file behind it, under the same
  version, and neither the row nor the hosted schema had to be touched to get
  there.

**No hosted write is needed and none was made.** The reconciliation merge
resolves `origin/main`'s snapshot path to this tombstone and proceeds.

`backend/tests/test_migration_directory_is_fresh_appliable.py` is the standing
guard against the next one: six directory-wide checks, every pattern
case-insensitive because `db diff` writes uppercase SQL and every pin in this
repository was lowercase-only until then. The tombstone passes all six for the
plain reason that a file with no statements in it has nothing for them to catch.

### What is being repaired forward, and where

Three of the probe results are not tolerated divergence — they are live defects
that the campaign confirmed, and each is being fixed **forward-only**, in the
shape rule 2 of `backend/supabase/migrations/README.md` prescribes: a targeted
timestamped migration or code change that names the one thing that is wrong,
with a derivation-pinned test. They get their own numbered sections from §23
onward; nothing about them belongs in this one.

- **The invite-claim RPC name** — probe (e). The backend calls
  `claim_email_invitation`; hosted has only `claim_resident_invite`. Every call
  on that path fails.
- **`request_status` has no `withdrawn`** — probe (f). The application believes
  the value exists.
- **The admin dashboard's split-brain reads** — probes (g) and (h). The rows
  live in `visitor_requests` (3) while the legacy read path looks at
  `visitor_access_requests` (0) and `legacy_amenity_booking_series` (0).

### Version collision — one thing to fix before it is committed

Issue #41's other half. Two different `20260822120000_supervisor_triage.sql`
files existed at once: the one on this branch (§18, applied and ledgered) and an
uncommitted one in the services-and-security workstream's tree. Both were written
the same afternoon and each took "now" as its version; `now` is not unique across
working trees.

**The uncommitted file at version `20260822120000` must be renamed to a timestamp
later than `20260822170000` before it is committed or applied anywhere.** Not
after it is pushed, and certainly not after it is applied: once a version is in
the ledger, a second file wearing it is invisible to `supabase migration list`
and will never be replayed on a fresh database. The rule that prevents the next
one is written down in `backend/supabase/migrations/README.md` — a new migration
timestamps later than the latest file on **any** shared branch, not just your
own.

**Resolved 2026-08-23.** The `services-and-security` branch was merged to `main`
(PR #36, 2026-08-22 17:10 UTC) and deleted by the git manager. The collision
never reached git: PR #36 carried exactly two commits, and the one holding the
local fix committed it as `20260817144725_repair_staff_assignment_employment_type.sql`
— the version the hosted ledger already carried for that repair (§21) — not as
`20260822120000`. No file wearing the colliding version exists in any commit on
any ref (`git log --all --full-history` finds only this branch's
`supervisor_triage`), so the rename this section demanded effectively happened
before commit, exactly as prescribed. Everything the branch ever merged is
contained in `live-app-fixes`: after the 2026-08-23 reconciliation merge the
branch is ahead of `origin/main` and zero behind, and PR #36's surviving files
are byte-identical here (the third, the db-diff snapshot, is deliberately the
§22 tombstone). Nothing remains to merge; only work that never left the
teammate's working tree — none is known — could be outside git.

## 23. `20260823120000_complaint_engine_v2_repairs.sql`

Arrived on this branch from `origin/main` in the reconciliation merge (PR #46,
2026-08-23) and is the only file in that merge carrying DDL. Unlike §21, this
one **is** outstanding work: the owner's ledger probe of 2026-08-23 found no row
for version `20260823120000`, so there is an apply step below and a ledger
insert to paste.

**What it is.** A forward-only re-authoring of the useful database repairs from
the `complaint-engine-v2` branch. That branch carried its fixes as two backdated
migrations, `20260817142354` and `20260817142820` — versions *below*
`20260817144725`, which hosted has already applied and ledgered (§21). A version
below the ledger's high-water mark is a version a fresh replay reaches before
the files that were really applied first, and on hosted it is a file
`supabase migration list` will never show as pending. Both were therefore
dropped and their content re-stated here, at a version above everything.
`backend/supabase/migrations/README.md` records the same decision in its
after-the-boundary table.

**What it touches.** Six `create or replace function` statements over five
names, plus the ACL block on the internal dispatch functions and a
`notify pgrst, 'reload schema'` for the new overload:

| Function | Definition it replaces |
|---|---|
| `sync_dispatch_tasks()` | `20260813104000_timers_v2.sql` (originally `0037`, then `0045`) |
| `project_complaint_from_jobs()` | `20260813102000_status_coupling.sql` |
| `dispatch_candidates(uuid, integer, boolean)` | new overload — nothing before it |
| `dispatch_candidates(uuid, integer)` | `0045_departure_scheduling.sql` (originally `0037`, then `0043`) |
| `work_order_candidates(uuid, boolean)` | `20260813101000_offer_consent_and_force.sql` |
| `dispatch_force_assign(uuid)` | `20260813101000_offer_consent_and_force.sql` |

**Ordering, and the overlap audit.** By filename it sorts after every other file
in the directory, which is where a file replacing this many bodies has to be.
The question worth asking of it is not order but *overlap*: §18
(`20260822120000_supervisor_triage.sql`) and §20
(`20260822170000_supervisor_actions.sql`) also rewrote complaint-engine
functions, and if this file redefined one of theirs it would silently revert a
day's work the way §19 would have reverted §20's vocabulary. It does not. §18
defines `take_up_complaint`, `supervisor_triage_snapshot`, `start_work_order`
and `restamp_department_supervision`; §20 defines `supervisor_resolve_complaint`,
`raise_complaint_priority`, `add_complaint_note_internal`,
`force_assign_work_order`, `can_supervise_complaint`, `open_complaint_thread`,
`post_dm_message` and `lock_complaint_threads`. **The intersection with the six
above is empty.** The two sets meet only through calls — §20's
`force_assign_work_order` is the supervisor's hand on the lever and calls
`dispatch_force_assign` underneath it — and a call is exactly the seam that
survives one side being replaced.

**The four behaviour changes, and the ruling on them.** All four were put to the
complaint-engine owner on 2026-08-23 and **accepted as-is**; the ruling is
recorded in `docs/COMPLAINT_ENGINE_HANDOFF.md` §21 and in `docs/CHANGE_LOG.md`.

1. **The manual-window queue priority is cast.** `sync_dispatch_tasks` passes
   `case when new.priority = 'high' then 2 else 0 end` to
   `enqueue_dispatch_task`, which takes a `smallint`; PostgreSQL resolves that
   `case` as `integer` unless it is told otherwise, and the call did not
   resolve. Now `::smallint`.
2. **The assignment trigger resolves its row shape.**
   `project_complaint_from_jobs` serves two tables, and a
   `work_order_assignments` row has a `work_order_id` where a `work_orders` row
   has a `complaint_id`. It now works out which row it has before reading it.
3. **Declined-worker override becomes explicit.** `dispatch_candidates` gains a
   three-argument overload whose third argument admits a worker who declined
   *this* work order. The two-argument form every existing caller uses is
   unchanged and still strict — one eligibility implementation, two doors.
4. **Critical force assignment stops failing on authorization.**
   `dispatch_force_assign` can run inside a *worker's* decline transaction. It
   used to pick through `work_order_candidates`, the supervisor-facing picker,
   which re-checks the caller's authorization — under a worker's JWT that check
   fails before the critical fallback can select anybody. It now picks through
   `dispatch_candidates(p_work_order_id, 100, true)` instead.

**The one behaviour change inside (4) that is not about authorization, and the
owner's ruling on it.** The old picker also carried
`where away_until is null or away_until <= now()`
(`20260813101000_offer_consent_and_force.sql` 109) — a filter that removed
anyone *currently* inside a leave block, whatever the job's slot. Swapping the
picker drops that filter, and the drop is deliberate rather than incidental:
`dispatch_candidates` already excludes a worker whose unavailability **overlaps
the slot being scheduled**, which is the question that actually decides whether
somebody can do the job. A worker on leave today who is free next Tuesday was
being refused a next-Tuesday critical force-assign for no reason the schedule
knows about. The complaint-engine owner ruled on 2026-08-23 that this is
correct: **only slot-overlapping unavailability blocks a critical force
assignment.** The consent-respecting offer flow is untouched and remains the
default; force stays an explicit flag.

**Apply:** paste the whole file into the SQL editor and run it. It ends with its
own verification block, which raises if the new
`dispatch_candidates(uuid,integer,boolean)` overload is not there afterwards, so
a half-success reports itself. No other output is expected.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260823120000', 'complaint_engine_v2_repairs')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
select p.oid::regprocedure as signature
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('dispatch_candidates', 'dispatch_force_assign',
                     'work_order_candidates', 'sync_dispatch_tasks',
                     'project_complaint_from_jobs')
 order by 1;
-- expect both dispatch_candidates overloads: (uuid,integer) and
-- (uuid,integer,boolean).
```

**Post-check, functional:** as a supervisor, raise a complaint's priority to
high and let every offered worker decline it. Before this file the critical
fallback selected nobody and the work order sat in `failed`; after it, the last
decline force-assigns a worker and the complaint timeline gains
`job_force_assigned`.

**What was checked before this section was written:** the six-check directory
battery in `backend/tests/test_migration_directory_is_fresh_appliable.py` (the
file parses, drops no trigger it does not recreate, creates no retired table, no
unguarded policy or constraint drop), plus the overlap audit above, run as a set
comparison over the `create or replace function` statements of §18, §20 and this
file rather than by reading them. **Not verifiable statically:** that hosted's
current bodies for the five replaced functions are the ones this directory
declares — every one of them is a `create or replace`, so the apply overwrites
whatever is there, which is the intent.

## 24. `20260823150000_hosted_invite_claim_names.sql`

**What breaks without it:** claiming a resident email invitation. Every attempt
on the hosted project answers "This invite could not be claimed." and there is
nothing wrong with the invitation. Confirmed by probe (e) of §22 on 2026-08-23.

**Why:** `memberships_repository.claim_resident_invite`
(`backend/app/repositories/memberships_repository.py` 61) calls the RPC named
`claim_email_invitation`. Hosted has only
`claim_resident_invite(p_invite_id uuid, p_profile_id uuid)`. PostgREST answers
PGRST202 for a function it cannot find, and
`invitation_service.redeem_pending_invitation` (~111) translates every failure on
that path into the one generic message. The divergence is old: hosted predates
`0001_baseline.sql`, and `0001_baseline.sql` 98 is where a fresh database gets
`claim_email_invitation`. The two functions carry the **identical** signature and
return shape `TABLE(membership_id uuid, community_id uuid, unit_id uuid)`, so
this is a naming difference and nothing more.

**What the file does on hosted:** creates `claim_email_invitation(uuid, uuid)`
as a thin wrapper that returns `claim_resident_invite`'s rows unchanged. One
implementation stays; only the entry point is added. The wrapper is
`security definer` with `set search_path = public`, revoked from
`public, anon, authenticated` and granted to `service_role` — `0001`'s exact
posture, so the new door is the same door. The file ends with
`notify pgrst, 'reload schema'`, without which PostgREST would keep answering
PGRST202 from its cache and the fix would look like no fix.

**Why it is a no-op on a fresh database:** the create is guarded on
`claim_resident_invite` existing **and** `claim_email_invitation` not existing.
Nothing in this directory creates `claim_resident_invite` — asserted across every
file in `backend/tests/test_hosted_invite_claim_names_migration.py` — so on a
fresh database the first half is false, and `0001` has already made the second
half false too. Re-running on hosted is a no-op for the same reason: the second
run finds the wrapper the first one made.

**Ordering:** after `20260823120000` (§23), which it sorts after by name.
Independent of it and of everything else; it touches nothing any other file
touches.

**Apply:** paste the whole file into the SQL editor and run it. No output
expected on success.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260823150000', 'hosted_invite_claim_names')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
select p.oid::regprocedure as signature,
       p.prosecdef        as security_definer,
       p.proconfig        as settings
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('claim_email_invitation', 'claim_resident_invite')
 order by 1;
-- expect two rows, both (uuid,uuid), both security_definer = t, both
-- settings = {search_path=public}.
```

**Post-check, functional:** issue a resident invitation from the admin portal,
open its link as the invitee, sign in, and redeem. Before this file that press
answered "This invite could not be claimed."; after it the invitee lands in the
community with a membership and, where the invite named a unit, a residency.

**What was checked before this section was written:** the static battery in
`backend/tests/test_hosted_invite_claim_names_migration.py` (11 tests) — the file
parses (`pglast`); it sorts after every file that already existed; the name it
creates is *derived* from the `.rpc(...)` call in `memberships_repository.py`
rather than typed in, so the pin follows the code; the signature, return shape,
`security definer`, `search_path` and both ACL statements are *derived* from
`0001_baseline.sql`'s own declaration of the function; no later migration
re-grants execute on it; the create is guarded on both halves of the divergence;
nothing in the directory creates `claim_resident_invite`; the wrapper body only
delegates (no insert, update, delete or raise of its own); the file creates
nothing else and drops nothing; and `notify pgrst, 'reload schema'` is its last
statement. **Not verifiable statically:** that hosted's `claim_resident_invite`
does what `0001`'s `claim_email_invitation` does. The probe established the
identical signature and return shape; the bodies are two databases' business and
no test in this repository can see either.

## 25. `20260823153000_hosted_request_status_withdrawn.sql`

**What breaks without it:** an applicant withdrawing their own join request.
`POST /access-requests/{id}/withdraw`
(`backend/app/api/v1/routers/access_requests.py` 43-51) answers a 22P02-shaped
failure on hosted: `invalid input value for enum request_status: "withdrawn"`.
Confirmed by probe (f) of §22 on 2026-08-23.

**Why:** `access_requests_repository.withdraw` (~75-87) writes
`status = 'withdrawn'`, the service reaches it at `access_request_service` ~251,
and the list filter already accepts the word (`routers/access_requests.py` 56).
On hosted `access_requests.status` is not text at all — it is the enum
`public.request_status`, whose labels are
`{pending, approved, rejected, cancelled}`. On a fresh database
`0001_baseline.sql` 57 declares the column as text with
`check (status in ('pending','approved','rejected','withdrawn'))` and **no enum
type of that name exists anywhere in this directory**. So `withdrawn` is a value
the application has always been entitled to write, and the hosted enum is a
pre-baseline artefact that never learned it.

**What the file does on hosted:** adds the fifth label to the enum. Widening
only — every value the type accepted before, it accepts after — and one
catalogue row rather than a table rewrite. Retyping a live
`access_requests.status` from the enum to text was the alternative and was not
taken: it rewrites the table, throws away the guarantee the enum is providing,
and leaves the column's type depending on which database it was built on.

**Why it is a no-op on a fresh database:** the `alter type` runs only where a
`public.request_status` enum exists, and nothing in this directory creates one —
asserted across every file in
`backend/tests/test_hosted_request_status_withdrawn_migration.py`. On hosted the
`if not exists` makes a second run a no-op as well.

**On the idiom, because it has a version boundary in it.**
`alter type ... add value` was refused inside a transaction block — and therefore
inside any `do` body — before PostgreSQL 12. Since 12 it is allowed there, with
the single remaining rule that the new label may not be *used* until the
transaction commits. Reading `pg_enum`, which this file's verification block
does, is a catalogue read and not a use of the value; nothing in the file
compares, casts or stores the new label. Every Supabase project runs well past
that boundary, so the guarded `do` block is safe as a single SQL-editor paste,
and being conditional at all is what keeps the file a no-op on a fresh database.
**If it ever fails on the `alter type` with "cannot run inside a transaction
block"** — a pre-12 server, which the linked project is not — the fallback is to
run this one statement on its own, outside any transaction, and skip the file:

```sql
alter type public.request_status add value if not exists 'withdrawn';
```

**Ordering:** after `20260823150000` (§24), which it sorts after by name.
Independent of it.

**Apply:** paste the whole file into the SQL editor and run it. No output
expected on success; the verification block at the end raises if the type is
present and the label still is not.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260823153000', 'hosted_request_status_withdrawn')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
select e.enumlabel, e.enumsortorder
  from pg_enum e
  join pg_type t on t.oid = e.enumtypid
  join pg_namespace n on n.oid = t.typnamespace
 where n.nspname = 'public' and t.typname = 'request_status'
 order by e.enumsortorder;
-- expect five labels: pending, approved, rejected, cancelled, withdrawn.
```

**Post-check, functional:** as a resident with a pending join request, press
**Withdraw**. Before this file that press answered a 22P02-shaped failure; after
it the request leaves the admin's pending list.

**What was checked before this section was written:** the static battery in
`backend/tests/test_hosted_request_status_withdrawn_migration.py` (10 tests) —
the file parses (`pglast`); it sorts after every file that already existed; the
label it adds is *derived* from the literal `access_requests_repository.withdraw`
actually writes, so a file that added some other word would fail here rather
than at the next press; that label is one `0001_baseline.sql`'s own check already
allows, which is what makes this hosted catching up rather than a fifth request
state being invented; the baseline column is text with a check and names no enum;
nothing in the directory creates the type; the `alter` is guarded on the type
existing *as an enum* (`typtype = 'e'`); the file adds and never removes or
retypes; the new label is never used as a value anywhere in the file, which is
the PostgreSQL 12 rule stated as an assertion; and the verification block is
itself conditional so it cannot raise on a fresh database. **Not verifiable
statically:** hosted's actual current label list — `add value if not exists` is
correct for any superset of the four the probe reported, and the verification
block is the only thing that can see the real answer.

## 26. `20260823160000_visitor_requests_sse.sql`

**What breaks without it:** an open admin dashboard never hears that a visitor
request has arrived. It is half of the split brain probes (g) and (h) of §22
found on 2026-08-23; the other half is a code change and is described at the end
of this section.

**Why:** `public.visitor_requests` carries **no trigger at all** on hosted. The
inventory probe walked the tables: `amenity_bookings` has
`amenity_bookings_sse`, `visitor_access_requests` has
`dashboard_sse_visitor_access_requests`, `legacy_amenity_booking_series` has
`dashboard_sse_amenity_booking_series` — and the one table residents actually
write has none. It holds the only three real visitor requests in the project,
and not one of them has ever produced an `sse_events` row.

`0007_dashboard_realtime_outbox.sql` is the file that lays these triggers. Its
loop names twelve tables, `visitor_requests` among them, and builds
`dashboard_sse_%I` on each one **that exists**. A fresh database has had the
trigger since `0007` for that reason, and hosted has not: when `0007` was applied
there, `visitor_requests` did not yet exist — `0032_visitor_passes.sql` created
it twenty-five files later — the `to_regclass` guard skipped it, and nothing
revisited the question.

**What the file does on hosted:** one statement, and it is `0007`'s own statement
for this table — the same `after insert or update or delete`, the same
`for each row`, the same `public.emit_dashboard_sse_event()`, under the name
`0007`'s loop would have produced. This is not a second design; it is the first
one arriving late. The function itself is untouched: `0028_event_audience.sql` 93
rewrote it once, to publish `dashboard.refresh` to the `{admin, manager}`
audience rather than the whole community, and that is the definition both
databases already carry.

**Why it is idempotent on a fresh database:** `create or replace trigger` rather
than a drop-and-create pair. On a fresh database it replaces `0007`'s trigger
with a definition identical to it; on hosted a second run replaces its own.
Nothing is ever dropped, so there is no window in which the table has no trigger
— and nothing for `test_migration_directory_is_fresh_appliable.py`'s
orphaned-trigger check to catch, because the file drops nothing at all.

**Ordering:** after `20260823153000` (§25) by name, and — the ones that matter —
after `0007` (whose trigger function it names) and after `0032` (which creates
the table it fires on). Both are long applied on hosted and both sort earlier in
a fresh replay.

**The other half, which needs no migration.**
`backend/app/repositories/dashboard_repository.py` was reading the *empty* side
of the same split: its legacy arms asked `visitor_access_requests` (0 rows) and
`legacy_amenity_booking_series` (0 rows) while residents wrote `visitor_requests`
(3) and `amenity_bookings`. Those two arms no longer branch on schema generation
at all — there was never a second source, only a second name for an empty one —
and `weekly_new_counts` follows them. The HTTP response shape of
`GET /dashboard/snapshot` is unchanged, `schema_generation()` is unchanged, and
every other legacy arm (complaints, amenities, invoices, payments) is untouched,
because those are genuinely two shapes of one table. **Without this migration the
dashboard would show the rows but only after a manual reload; without the code
change the trigger would fire about rows nothing projects.** They ship together.

**Apply:** paste the whole file into the SQL editor and run it. No output
expected on success; the verification block at the end raises if the trigger is
not on the table afterwards.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260823160000', 'visitor_requests_sse')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
select c.relname as table_name,
       t.tgname  as trigger_name,
       pg_get_triggerdef(t.oid) as definition
  from pg_trigger t
  join pg_class c on c.oid = t.tgrelid
 where not t.tgisinternal
   and c.relname in ('visitor_requests', 'amenity_bookings')
 order by 1, 2;
-- expect dashboard_sse_visitor_requests on visitor_requests, defined as
-- AFTER INSERT OR DELETE OR UPDATE ... FOR EACH ROW EXECUTE FUNCTION
-- public.emit_dashboard_sse_event().
```

**Post-check, functional:** open the admin dashboard in one browser and, in
another, create a visitor pass as a resident. The admin's visitor list gains the
row without a reload. Both halves are being tested at once by that press — the
trigger for the refresh, the repository change for the row being in the list at
all.

**What was checked before this section was written:** the static battery in
`backend/tests/test_visitor_requests_sse_migration.py` (9 tests) — the file
parses (`pglast`); it sorts after every file that already existed, after `0007`,
and after every file that creates `public.visitor_requests`; the trigger's name,
events, row level and function are *derived from `0007`'s own loop template* and
compared against this file's statement, so the two definitions cannot drift and
the `delete` arm cannot be quietly dropped; `visitor_requests` is one of the
tables `0007`'s array already names, so this is `0007` finishing its own job
rather than a thirteenth table entering the outbox by a side door; every
definition of `emit_dashboard_sse_event` in the directory sorts before this file;
the file drops nothing and holds exactly one `create or replace trigger`; and the
verification names the trigger it made rather than asking whether the table has
any trigger at all — which would have passed against nothing useful, since the
table had none. The repository half is pinned by
`backend/tests/test_realtime.py`, including a cross-check that the table this
trigger fires on is the table `list_visitors` reads. **Not verifiable
statically:** whether hosted's `emit_dashboard_sse_event` is the one this
directory declares. It is a `create or replace` in `0007` and again in `0028`,
and the apply is the only thing that can settle it.

## 27. `20260823170000_open_jobs_board.sql`

**What breaks without it:** the open-jobs board. The product rulings of
2026-08-23 (`docs/COMPLAINT_ENGINE_HANDOFF.md` §22, C1–C3) give department
roster technicians who hold the job's trade a board of their department's
unclaimed work and an instant first-come claim; without this file both backend
endpoints (`GET /worker/open-jobs`, `POST /worker/jobs/{id}/claim`) answer 500
on an RPC that does not exist, and the new "Open jobs" tab in the worker portal
renders its error state. The build spec, adjudications D1–D7 included, is
`docs/plans/OPEN_JOBS_BOARD_SPEC.md`.

**What it does:** two new SECURITY DEFINER functions and one widened trigger.

1. `worker_open_jobs()` — the board read. No arguments; identity is
   `auth.uid()`. Every job with `status in ('draft','offered')` and **no live
   assignment** (D1: uncommitted and unpromised) in every department where the
   caller holds an active roster row, filtered by `dispatch_candidates`' own
   trade clause (D2) and by `complaint_excluded_staff` (D7). A SECURITY DEFINER
   RPC rather than a view because `work_orders_read` correctly hides unheld
   jobs from workers — a board of jobs nobody holds yet is invisible to
   everybody it is for under RLS.
2. `claim_open_work_order(uuid)` — the claim. `accept_work_order_offer`'s
   shapes — the row lock first, the overlap refusal in words, the
   withdrawn-not-deleted sweep, the `job_assigned` event, the resident's
   `work_order.assigned` — minus the demands that assume an offer exists. New
   guards in their place: D1 re-checked under the lock (HB409 "Somebody has
   already taken this job."), active roster row in the job's department
   (HB403), the engine's trade rule (HB403), the complaint's exclusion history
   (HB409). A job with no slot is claimed with no slot (C3) and still moves to
   `scheduled` — the shape `force_assign_work_order` already writes. The
   supervisor is told with a new notification kind, `work_order.claimed`
   (`notifications.kind` is unconstrained by design, `0030`), skipped when the
   claimer is that supervisor. No new complaint-event word: the payload carries
   `claimed: true` inside `job_assigned`, because a new word costs a
   `complaint_events_type_check` rebuild (§19's rule) and this does not.
3. `project_complaint_from_jobs()` re-issued with one branch widened, and
   `work_order_assignments_project_complaint` dropped and recreated with
   `when (new.status in ('offered', 'accepted'))` (D5). On the offer path the
   complaint moved `open → acknowledged` when the *offer* was inserted; a claim
   inserts `accepted` directly, and without this the complaint would sit at
   `open` with a committed job — violating C2's "the same status movements".
   **This knowingly also closes the identical pre-existing hole in
   `force_assign_work_order` and `dispatch_force_assign`**, whose accepted
   inserts never acknowledged either; flagged to the product owner as an engine
   lifecycle change made under C2's authority. The body is `20260823120000`'s —
   the row-shape resolution is kept exactly — so applying this after §23
   overwrites nothing but the one branch.

**Ordering:** after `20260823160000` (§26, the hosted high-water mark) by name.
The bodies it re-issues or reads all sort earlier: `project_complaint_from_jobs`
was last written by §23, `complaint_excluded_staff` by `20260813101000`, and
the trade clause mirrors §23's `dispatch_candidates` without replacing it. The
overlap audit against §18, §20 and §23 is empty — nothing here redefines any
function those files own except `project_complaint_from_jobs`, which §23 wrote
and whose diff is the one widened branch.

**Apply:** paste the whole file into the SQL editor and run it. It ends with
its own verification block, which raises if either function is missing, if the
trigger body was not widened, or if the recreated trigger's WHEN clause does
not name `accepted` — so a half-success reports itself. No other output is
expected.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260823170000', 'open_jobs_board')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
select p.oid::regprocedure as signature,
       p.prosecdef         as security_definer
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('worker_open_jobs', 'claim_open_work_order')
 order by 1;
-- expect worker_open_jobs() and claim_open_work_order(uuid), both with
-- security_definer = true.

select pg_get_triggerdef(oid)
  from pg_trigger
 where tgname = 'work_order_assignments_project_complaint';
-- expect ... AFTER INSERT ... WHEN ((new.status = ANY (ARRAY['offered'::text,
-- 'accepted'::text]))) ... EXECUTE FUNCTION public.project_complaint_from_jobs().
```

**Post-check, functional:** as a technician on a department roster, open the
worker portal's new "Open jobs" tab: a `draft` job of the department with no
assignment rows appears, an unscheduled one with a "Time to be set" marker.
Claim it. The job moves to `scheduled` and onto the worker's dashboard, the
complaint's timeline gains `job_assigned` with `claimed: true`, the complaint —
if it was `open` — reads `acknowledged`, and the supervisor's bell gains
"<worker> took up <job>". A second claim of the same job from another account
answers 409 "Somebody has already taken this job."

**What was checked before this section was written:** the static battery in
`backend/tests/test_open_jobs_board_migration.py` (11 tests) — the file parses
(`pglast`) and sorts after the hosted high-water mark; D1's both-halves
predicate appears in both functions; the trade clause is the engine's own,
short-circuit included, in both; `complaint_excluded_staff` filters the read
and guards the claim; the claim locks before it reads, skips the slot checks
without a slot, and copies the accept path's exact row shape; no event word or
constraint is touched; the supervisor's `work_order.claimed` is present and
self-notification is skipped; the trigger is dropped before it is recreated
with the widened WHEN and the §23 row-shape repair survives the re-issue; and
the grants are explicit with the PostgREST reload at the end. Plus the
directory battery in `test_migration_directory_is_fresh_appliable.py`.
**Not verifiable statically:** that hosted's `project_complaint_from_jobs` is
§23's body before this overwrites it — it is a `create or replace`, so the
apply overwrites whatever is there, which is the intent; and the D5 behaviour
change itself, which only the functional post-check above can show.

## 28. `20260823180000_resident_sets_the_time.sql`

**Apply this AFTER §27.** It sorts after `20260823170000_open_jobs_board.sql`
by name and reads two things §27 established — the board predicate it
deliberately does not change, and `project_complaint_from_jobs`' widened
accepted-insert branch, which is what makes an auto-assigned job acknowledge
its complaint. Applying this first would leave the second half of that
sentence untrue for every job the dispatcher books.

**What breaks without it:** the 2026-08-23 product rulings
(`docs/COMPLAINT_ENGINE_HANDOFF.md` §23, F1–F3). The raise form has already
lost its date and time fields on the frontend, so **without this file every UI
raise creates a `draft` that nobody is asked about and nothing books** — a
resident job that reaches no resident and a facility job that reaches no
queue. `POST /complaints/{id}/schedule-time` answers 500 on an RPC that does
not exist, the resident's card cannot leave pick-mode, and the supervisor
dashboard's new "Awaiting resident response" section renders empty because the
snapshot emits no such key. The build spec, adjudications G1–G11 included, is
`docs/plans/RESIDENT_SETS_THE_TIME_SPEC.md`.

**What it does:** one widened constraint, four new functions, and five
redefinitions — in ten numbered sections.

1. **`dispatch_tasks_kind_check` widened** with `facility_auto_assign`. The one
   constraint this build touches. It proves no existing row falls outside the
   new list *before* it drops anything (§20's shape), then drops, adds, and
   proves the new word specifically — a bare existence check would pass against
   the very constraint being replaced. Widening only: every kind
   `20260813104000` accepted is in the new list, and
   `tests/test_resident_sets_the_time_migration.py` derives that list from
   `20260813104000`'s own text rather than reviewing it by eye.
2. **`dispatch_candidates_at(uuid, timestamptz, timestamptz, integer, boolean)`**
   — `20260823120000`'s eligibility body, parameterised by a **hypothetical**
   hour instead of the job's stored one. The three-argument
   `dispatch_candidates` becomes a delegate that passes the job's own slot:
   same signature, same return table, same ordering (`adjacent desc, load asc,
   km asc nulls last, display_name`), same grants, and the two-argument wrapper
   untouched. A refactor and not a fork — a second copy would be a second answer
   to *who may take this job*, and the one that drifts is always the one nobody
   is testing. Null-slot behaviour is preserved exactly: the guard moved from
   the columns onto the parameters, so a job with no hour still has no
   candidates.
3. **`find_first_available_slot(uuid, timestamptz)`** — the first top-of-hour at
   or after `p_from` where the job has an eligible candidate, with that
   candidate. **Two-hour** visits, **fourteen-day** horizon, hardcoded in the
   engine's style like the 24-hour deadline, each with a comment saying what it
   is. It writes nothing: probing by storing a trial hour on `work_orders`
   would fire six triggers per probe.
4. **`create_work_order` redefined.** The API still accepts a slot and a slotted
   raise keeps today's semantics byte for byte. What is new is the slotless
   raise: `resident` → `awaiting_resident` with a **null slot** and
   `resident_deadline_at = now() + 24h` (pick-mode), notifying the resident
   `work_order.schedule_requested` with `mode: 'pick'`; `facility` → `draft`,
   unchanged, with the trigger in §7 arming its task. Nothing is enqueued
   inside `create_work_order` — the status change already says everything the
   queue needs, which is `0037` §2's rule.
5. **`resident_set_work_order_schedule(uuid, timestamptz, timestamptz)`** — the
   resident's write, complaint-scoped like its siblings and granted to
   `authenticated`. Guards in order: `is_own_membership` against the raiser
   (HB403), status `awaiting_resident` (HB409 *"There is nothing to schedule on
   this complaint right now."*), null slot (HB409 *"The association proposed
   this visit's time — answer that instead."*), and a future hour that ends
   after it starts (HB409). Writes the slot, `status = 'offered'` — the open
   pile — and clears the deadline; event `job_scheduled` with
   `resident_set: true`; supervisor told with the new kind
   `work_order.resident_scheduled`. **No decline** (F3).
6. **`dispatch_resident_timeout` redefined**, branching on the discriminator.
   Slot present: `0037` §5's body unchanged, proceeding to `offered` with the
   same event and the same `work_order.proceeding` notification. Slot null
   (pick-mode expired, F2): `find_first_available_slot(now())`; on a hit the
   stray `offered` rows are withdrawn, an `accepted` row is inserted
   (`is_auto_assigned = true`, `is_forced = false`, `offered_at = responded_at =
   now()`), the found slot is written with `status = 'scheduled'`, the event is
   `job_assigned` with `auto_assigned: true`, and worker, resident and
   supervisor are notified (`work_order.assigned` twice, plus the new
   `work_order.auto_assigned`). No hit inside the horizon: `status = 'draft'`,
   deadline cleared, supervisor told `work_order.no_candidates` — the job lands
   back on the open board, claimable, rather than stranding in
   `awaiting_resident` with a dead timer.
7. **`dispatch_facility_auto_assign(uuid)`**, plus **`sync_dispatch_tasks`** and
   **`fire_dispatch_task` redefined**. The handler bails (completing the task)
   unless the job is still a `draft` facility job with no live assignment — a
   board claim winning the race is the outcome it exists to make unnecessary,
   not one to fight. **The courtesy gate:** if any work order in the same
   department is `subject_kind = 'resident'`, `priority = 'high'`, status in
   `('draft','awaiting_resident','offered')` and has no live
   (`offered|accepted`) assignment, the task completes and re-arms an hour
   later; the job stays claimable on the open board the whole time, so a gated
   job is never stranded. Gate clear: assign exactly as §6's hit branch; no
   candidate: notify `work_order.no_candidates` **once** and complete, leaving
   the job on the board. The trigger is re-issued with every existing arm
   carried forward — the `resident_timeout` re-arm, the `manual_window` enqueue
   with §23's smallint cast, the failed-visit escalation, and the final `else`
   that cancels timers on an unrecognised status — with `draft` lifted out of
   that `else` into an arm that still closes the job's timers and, **on INSERT
   of a facility draft only**, arms the new task. `fire_dispatch_task` gains
   the `when 'facility_auto_assign'` arm, which **completes its own row before
   calling the handler**: the handler's hourly re-arm would otherwise be folded
   into the firing row by `dispatch_tasks_one_open_per_kind` and then completed
   by the update at the bottom, silently cancelling the retry.
8. **`supervisor_triage_snapshot` redefined** with a sixth bucket.
   `awaiting_resident` (uncommitted, status `awaiting_resident`, newest first)
   is new; `open_requests` narrows to `draft`/`offered`. `TriageSnapshot` gains
   `awaitingResident` on the wire, additively.
9. **Grants**, each function's existing audience restated: the dispatch
   internals revoked from `public, anon, authenticated` with no `service_role`
   grant (`0037` §8's posture — only definer callers reach them, and
   `fire_dispatch_task` is the one door the Python dispatcher uses);
   `resident_set_work_order_schedule` to `authenticated`; then
   `notify pgrst, 'reload schema';`, because new functions and a new overload
   change the PostgREST function catalogue.
10. **In-transaction `do $$` proofs**, §23 and §27's shape: `to_regprocedure`
    for the four new signatures and the two surviving `dispatch_candidates`
    entry points, body-string probes proving each of the five redefinitions is
    the one the database now holds, and the widened kind CHECK.

**What it does NOT do, and each absence is deliberate.** No new
`work_orders` status (pick-mode is `awaiting_resident` + null slot); no new
`complaint_events` word (`job_scheduled` / `job_assigned`, distinctions in the
payload — §19's rule); no change to the board predicate, to
`respond_to_work_order_schedule`, to `reschedule_work_order`, or to the
supervisor's offer and force-assign paths.

**Ordering:** after §27 by name, as above. The bodies it re-issues all sort
earlier — `create_work_order` was last written by `0036`,
`dispatch_resident_timeout` by `0037`, `sync_dispatch_tasks` and
`dispatch_candidates` by §23, `fire_dispatch_task` by `20260813104000`, and
`supervisor_triage_snapshot` by §20. The overlap audit against §20, §23 and §27
is: this file is now the last word on those five, which
`tests/test_resident_sets_the_time_migration.py` asserts by scanning the
directory rather than by memory, and `tests/test_supervisor_actions_migration.py`
was re-pointed to say so about the snapshot.

**Apply:** paste the whole file into the SQL editor and run it. It ends with its
own verification block, which raises if any of the four new functions is
missing, if either `dispatch_candidates` entry point was lost, if the
three-argument one is not the delegate, if any of the five redefinitions is not
the live body, or if the widened CHECK does not accept `facility_auto_assign`.
On success it raises one `notice`; no other output is expected.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260823180000', 'resident_sets_the_time')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
-- (a) Six sections, and the new key among them. This inspects the function
--     body rather than calling it: the SQL editor has no auth.uid(), so the
--     supervisor guard would HB403 any direct call -- and on this deployment
--     departments carry kind NULL (the backend defaults NULL to "service" on
--     read and only stores a kind the admin form supplied), so the old
--     `where kind = 'service'` helper found no department and drew HB404.
--     The real six-key call is proven by the app: the supervisor dashboard's
--     GET /triage-snapshot renders the "Awaiting resident response" section.
select pg_get_functiondef(
         'public.supervisor_triage_snapshot(uuid)'::regprocedure)
       like '%''awaiting_resident'', v_awaiting%' as has_sixth_bucket;
-- expect: one row, true.

-- (b) The four new functions, all SECURITY DEFINER, and both older
--     dispatch_candidates entry points still there.
select p.oid::regprocedure as signature, p.prosecdef as security_definer
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('dispatch_candidates', 'dispatch_candidates_at',
                     'find_first_available_slot',
                     'resident_set_work_order_schedule',
                     'dispatch_facility_auto_assign')
 order by 1;
-- expect six rows, every one security_definer = true.

-- (c) The one widened constraint knows the new kind, and nothing else moved.
select pg_get_constraintdef(oid) like '%facility_auto_assign%' as knows_it
  from pg_constraint
 where conrelid = 'public.dispatch_tasks'::regclass
   and conname  = 'dispatch_tasks_kind_check';
-- expect: one row, true.

-- (d) Who may execute the resident's verb, and who may not the internals.
select p.oid::regprocedure as signature, p.proacl
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('resident_set_work_order_schedule',
                     'find_first_available_slot',
                     'dispatch_facility_auto_assign');
-- expect: `authenticated=X` on the first only; the other two carry the owner's
-- entry and nothing else.
```

**Post-check, functional:** as a department supervisor, raise a job against a
resident's complaint with **no time**. The resident's bell gains *"Pick a time
for this visit"*, their complaint card shows a time picker, and the supervisor
dashboard shows the job under **"Awaiting resident response"** and *not* under
open requests. Set a time as the resident: the job moves to `offered`, appears
on the open-jobs board, the timeline gains `job_scheduled` with
`resident_set: true`, and the supervisor's bell gains *"The resident picked a
time"*. Then raise a **facility** job with no time in a department with no
outstanding urgent resident work: within one dispatcher tick (15s) it should be
`scheduled` with a worker on it, the timeline carrying `job_assigned` with
`auto_assigned: true` — or, with no eligible worker, stay a `draft` on the board
with *"Nobody could be assigned"* in the supervisor's bell. Raise the same
facility job while an urgent (`High`) resident job in that department has nobody
on it, and check `dispatch_tasks` instead: the row's `due_at` should move an
hour out and `completed_at` on the previous one be set.

**What was checked before this section was written:** the static battery in
`backend/tests/test_resident_sets_the_time_migration.py` (26 tests) — the file
parses (`pglast`), sorts after §27, and is the last declaration of all five
functions it re-issues; the only constraint it drops or adds is the dispatch
kind check, and the widened list is a strict superset of `20260813104000`'s
derived from that file's own text; no `work_orders` status outside the closed
vocabulary is ever written; `worker_open_jobs` and `claim_open_work_order` are
not mentioned; the finder writes nothing and carries the frozen 2h/1h/14d
constants; the three-argument `dispatch_candidates` re-implements no
eligibility clause and the parameterised body keeps every clause and the exact
ordering; the raise's two slotless branches; the resident verb's guard order,
its four HB409s and its `offered` write; no decline anywhere; both timeout
branches including the no-candidate return to `draft`; the facility handler's
bail conditions, its gate and its hourly re-arm; every arm of both re-issued
dispatch functions plus the complete-before-handler ordering; the sixth bucket,
the narrowed `open_requests` and the DTO agreement; the grants and the
PostgREST reload; the self-verification block; and that every SQLSTATE it
raises is one `pg_errors` can map. Plus the directory battery in
`test_migration_directory_is_fresh_appliable.py` and the 210-operation
`test_openapi_spec.py`. **Not verifiable statically:** that the hourly gate
retry actually produces a *new* `dispatch_tasks` row rather than re-arming the
one being fired — the reasoning is in the `fire_dispatch_task` comment and the
ordering is pinned, but only the functional check above shows it; and the
finder's cost, which walks up to 336 hypothetical hours per expired pick and has
never been run against a real roster.


## 29. `20260823190000_assignment_write_repairs.sql`

**Apply this AFTER §28.** It sorts after
`20260823180000_resident_sets_the_time.sql` by name and re-issues that file's
`dispatch_candidates_at` plus §27's `worker_open_jobs` and
`claim_open_work_order`. Applying it before either would have the earlier file
overwrite all three bodies and take the rank clause straight back out, with
nothing in the apply output to say so.

**What breaks without it:** two live defects from 2026-08-23, and a third that
had not fired yet.

1. **Every assign answers 422.** Force-assigning a tap-leak job from the
   supervisor's "Assign this job outright" modal failed for every caller. The
   server-side log behind it, through `app/core/pg_errors.py`:
   `SQLSTATE 23502: null value in column "assigned_by_membership_id" of relation
   "work_order_assignments" violates not-null constraint`. Hosted
   `work_order_assignments` is the pre-baseline hand-built table and carries
   that column `NOT NULL` with no default; no repository migration has ever
   declared it, so **all eleven** insert sites in the repository omit it. On
   hosted, every write path into the table is broken — the offer, the board
   claim, the ping, force-assign, dispatch force, and both auto-assign
   handlers.
2. **Leadership was in the candidate list.** The picker showed the department's
   supervisor and manager beside its two technicians, because nothing in the
   eligibility chain has ever asked about `staff_assignments.rank`. The same
   hole was on the open-jobs board twice: a supervisor could see and claim their
   own department's work.
3. **The two 2026-08-23 auto-assign handlers were pre-armed to die.**
   `dispatch_resident_timeout`'s pick-mode branch and
   `dispatch_facility_auto_assign` both insert into
   `work_order_assignments` and neither has ever fired on hosted. Without §1
   below, the first firing crashes on the same 23502, retries five times, and
   retires the task dead — a facility job that silently never gets a worker.

The frozen spec, rulings R1–R7 included, is
`docs/plans/ASSIGNMENT_ELIGIBILITY_AND_DRIFT_SPEC.md`. The product owner's
ruling R1, verbatim: *"its only asigned to the workers who are hired from the
service men pool"*.

**What it does:** one widening sweep and three `create or replace`, in five
sections.

1. **The drift sweep (R4)** — §17's shape, one table along. Drops `NOT NULL` on
   every `work_order_assignments` column that (a) the repository has never
   declared, (b) is `NOT NULL` on the hosted table, and (c) has no default —
   exactly the set that can reject an insert written against the repository's
   schema. A sweep and not `assigned_by_membership_id` alone, because §17 and
   the `complaints` drift before it both taught that these constraints bite one
   behind the other. The protected list is the repository's full declaration —
   `0001_baseline.sql`:74, `0036_work_orders.sql`:264-272 and
   `20260813101000`:4 — and
   `backend/tests/test_assignment_write_repairs_migration.py` derives the same
   list from those three files' own text rather than reviewing it by eye. The
   legacy status-ish column that defaults to `'assigned'` **has** a default, so
   the sweep correctly leaves it alone. It walks `pg_attribute` rather than
   `information_schema.columns` — the view filters by the reading role's
   privileges, and this file is pasted into an editor whose role nobody in this
   repository chose. Widening only, no-op on a baseline-built database, no-op on
   re-apply.
2. **`dispatch_candidates_at` re-issued (R1, R3)** — §28's body verbatim with
   `and sa.rank = 'member'` added to the roster join, and nothing else. It is
   the *one* eligibility implementation, so the picker
   (`work_order_candidates` → `dispatch_candidates` → `_at`),
   `find_first_available_slot`, `dispatch_resident_timeout`,
   `dispatch_facility_auto_assign`, `dispatch_ping_candidates`,
   `dispatch_auto_assign` and `dispatch_force_assign` all inherit the rule with
   no change of their own. Signature, return table, ordering (`adjacent desc,
   load asc, km asc nulls last, display_name`), null-slot guard, trade
   short-circuit and grants are untouched.
3. **`worker_open_jobs` re-issued (R2)** — §27's body verbatim with the same
   clause on the same roster join. Taking a job off the board is assignment by
   another door, so the board obeys the same rule; supervisors keep their own
   triage dashboard, which is where their view of this work belongs.
4. **`claim_open_work_order` re-issued (R2)** — §27's body verbatim, the clause
   on the roster re-check, and one branch under it. A deep-linked claim meets
   that re-check even when the board never showed the job, so the clause belongs
   there; the branch exists because a supervisor genuinely **is** on the roster,
   and answering them *"You are not on this department's roster."* would be a
   lie told to the one person able to check it. Leadership gets
   *"Supervisors and managers cannot take up jobs from the board."* with
   **HB403** — the code this function already answers both of its other
   you-may-not-have-this-job refusals with (the roster miss and the trade miss).
   No new numbering scheme.
5. **Post-checks, comment-only.** §28's lesson, written into the file: the SQL
   editor has no `auth.uid()` and this deployment's departments carry `kind`
   NULL, so every post-check here is a guard-free structural inspection —
   `pg_get_functiondef` and `pg_attribute`, nothing called, nothing resolved
   from a caller. They are reproduced below.

**The clause is strict (R3).** `sa.rank = 'member'`, not `rank <> 'manager'`:
a NULL rank, and any rank this repository has not declared, is excluded rather
than admitted. `staff_assignments_rank_check` is `('manager','supervisor',
'member')` since `0035`:106-108 and marketplace hires land as `member`, so on a
clean roster nothing moves — but a legacy row predating that constraint would
lose eligibility silently, which is what the pre-check below exists to catch.

**What it does NOT do, and each absence is deliberate.** No new function and no
new signature; no `work_orders` status word, no `complaint_events` word, no
`dispatch_tasks` kind — no constraint is dropped or added anywhere in the file;
no resolver for `assigned_by_membership_id` (encoding a hosted-only legacy
column into eleven call sites is drift in the other direction — this
repository's actor model is `complaint_events.actor_membership_id` via
`my_membership_in()`); and no code or API change, so nothing needs deploying
alongside it.

**Pre-check, read-only — run this BEFORE the apply and read the result:**

```sql
-- Any roster row whose rank the new clause will exclude. Expect ZERO rows.
-- A row here is a person who can hold a job today and cannot after the apply,
-- so it is a decision, not a diagnostic: NULL or an unknown rank on a real
-- technician means fixing that row (`update public.staff_assignments set rank =
-- 'member' where id = '...'`) before applying, not relaxing the clause.
select sa.id,
       sa.department_id,
       sa.display_name,
       sa.rank,
       sa.status,
       sa.is_active,
       sa.service_provider_id
  from public.staff_assignments sa
 where sa.status = 'active'
   and sa.is_active
   and (sa.rank is null
        or sa.rank not in ('manager', 'supervisor', 'member'))
 order by sa.department_id, sa.display_name;

-- Context for the row above, if there is one: what the roster looks like by
-- rank. Leadership rows here are expected and are what section 2 excludes.
select rank, count(*) as active_rows
  from public.staff_assignments
 where status = 'active' and is_active
 group by rank
 order by 1;
```

**Apply:** paste the whole file into the SQL editor and run it. The editor's
destructive-operation warning **will** fire — it sees `drop not null` and the
`create or replace function` keywords — and it is safe to confirm: the sweep
only ever widens (no row the table accepted before is rejected after), the three
replacements are their predecessors' bodies plus one clause, and the whole paste
is one transaction, so a failure anywhere rolls the entire file back. Section 1
raises one `notice` per legacy column it widens, or one saying it found none;
section 1's verification and section 4's proof raise instead of reporting
success, so a half-applied file cannot look like a successful one. No other
output is expected.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260823190000', 'assignment_write_repairs')
on conflict (version) do nothing;
```

**Post-check, read-only — every one guard-free (§28's lesson):**

```sql
-- (a) The clause is in all three of the functions that decide who may hold a
--     job. Expect three rows, has_rank_clause true on each. This inspects the
--     bodies rather than calling them: the SQL editor has no auth.uid(), so
--     worker_open_jobs would return an empty board and claim_open_work_order
--     would HB403 — neither of which proves anything either way.
select p.oid::regprocedure as signature,
       pg_get_functiondef(p.oid) like '%sa.rank = ''member''%' as has_rank_clause
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and (p.proname in ('worker_open_jobs', 'claim_open_work_order')
        or p.oid::regprocedure::text like 'dispatch_candidates_at(%')
 order by 1;

-- (b) The column that answered every assign with a 422 is nullable now. Expect
--     one row with attnotnull = false — or NO row at all, which is what a
--     database built from 0001_baseline.sql looks like and is equally correct.
select a.attname, a.attnotnull, a.atthasdef
  from pg_attribute a
 where a.attrelid = 'public.work_order_assignments'::regclass
   and a.attname  = 'assigned_by_membership_id';

-- (c) And nothing insert-blocking is left behind it. Expect zero rows.
select a.attname
  from pg_attribute a
 where a.attrelid = 'public.work_order_assignments'::regclass
   and a.attnum > 0
   and not a.attisdropped
   and a.attnotnull
   and not a.atthasdef
   and a.attname not in (
     'id', 'work_order_id', 'staff_assignment_id', 'assigned_at', 'ended_at',
     'status', 'offered_at', 'responded_at', 'decline_reason',
     'is_auto_assigned', 'scheduled_start_at', 'scheduled_end_at', 'is_forced')
 order by a.attname;

-- (d) Ground truth on the dispatcher, which the "not autoassigned or slow"
--     report needs and no log line answers. A task with completed_at set has
--     fired; last_error set means it fired and threw (before this file, the
--     two auto-assign kinds would throw 23502 here); attempts climbing with
--     completed_at null and due_at in the past means the loop is not running.
select kind, due_at, completed_at, attempts, last_error
  from public.dispatch_tasks
 order by due_at desc
 limit 20;
```

**Post-check, functional:** as a department supervisor, open a resident
complaint's "Assign this job outright" modal. The candidate list now holds
**only** the department's technicians — the supervisor and the manager are gone.
Assign one: the call succeeds instead of answering 422, the job moves to
`scheduled`, and the complaint's timeline gains `job_assigned`. Then sign in as
that supervisor in the worker portal: the "Open jobs" tab is empty for them (it
was showing their own department's pile), and a deep-linked claim answers 403
*"Supervisors and managers cannot take up jobs from the board."* A technician on
the same roster still sees the board and can still claim from it.

**What was checked before this section was written:** the static battery in
`backend/tests/test_assignment_write_repairs_migration.py` (19 tests) — the file
parses (`pglast`), sorts after all six files it reasons about, and is the last
declaration of each of the three functions it re-issues; it declares no fourth
function; the sweep's protected list is derived from the three declaring
migrations' own text and compared exactly against both of the file's copies of
it; the sweep touches only NOT-NULL-without-default columns, its one dynamic
statement can only drop `NOT NULL`, it writes no rows, it notices rather than
raises and its verification raises rather than notices; the sweep runs before
any `create or replace`; `assigned_by_membership_id` appears nowhere in the
executable SQL; each of the three copied bodies is diffed line by line against
its predecessor with **zero removals** and no executable addition beyond the
clause (and, for the claim, the pinned leadership branch); the leadership
refusal's code is HB403 and every SQLSTATE the file raises is one `pg_errors`
can map; no closed vocabulary and no dispatch-task kind is named; the grants and
the PostgREST reload are restated; the in-transaction proof looks for the clause
in all three functions and for the delegate still being a delegate; and section
5 is comment-only and calls nothing guarded. Plus the directory battery in
`test_migration_directory_is_fresh_appliable.py`. **Not verifiable statically:**
that hosted's three function bodies are §27's and §28's before this overwrites
them — these are `create or replace`, so the apply overwrites whatever is there,
which is the intent; how many legacy `NOT NULL` columns the sweep will actually
find (only the apply's NOTICEs say); and whether any hosted roster row carries a
rank outside the closed list, which is what the pre-check above is for.


## 30. `20260824090000_supervisor_take_up.sql`

**Apply this AFTER §29.** It re-issues §29's `claim_open_work_order` and
`20260822170000`'s `force_assign_work_order`, and it recreates the
`complaint_events` event CHECK that `20260822170000` §7 last defined. Applying
it before §29 would have §29 overwrite the claim's new refusal and take the
rank clause straight back out of nothing — and applying §29 *after* this file
would replace the claim body with one that still says *"Supervisors and
managers cannot take up jobs from the board"* while the button that answers
that sentence exists. Filename order is apply order and it is already right;
this note is for the case where somebody applies out of order by hand.

**What breaks without it:** nothing crashes — and that is the point. §29 closed
every assignment path to anybody whose roster rank is not `member`, which is
ruling R1 and what the product owner asked for. What it leaves is a department
with no eligible holder: one supervisor, one technician on leave, and a
complaint the picker cannot fill, the auto-book cannot fill, the ping cannot
fill and the board will not show. Ruling R9 accepted that outcome deliberately
— no automation fallback, jobs wait for hires — **on the condition that take-up
is the manual valve**. Without this file there is no valve, and the honest
description of the product is that a thin department's work stops.

The product owner's ruling R8, verbatim: *"yes, include an option where a super
can take up work … it sholdnt be something seen in normal routine workflow … it
is available at any time though but as a seperate button orsomething like
that."* The frozen spec, rulings R8–R13 included, is
[`ASSIGNMENT_ELIGIBILITY_AND_DRIFT_SPEC.md`](ASSIGNMENT_ELIGIBILITY_AND_DRIFT_SPEC.md)'s
*Addendum 2026-08-24*.

**What it does:** one constraint swap and three `create or replace`, in five
sections.

1. **One new event word (R11)** — `job_taken_up`, added to
   `complaint_events_type_check`. §20's shape and §19's before it: prove nothing
   stored is outside the new list *before* dropping anything, so a failure there
   leaves the old constraint standing; then drop, add, and prove the **new** word
   specifically, because a bare existence check passes against the very
   constraint being replaced. The list is `20260822170000` §7's, carried over
   word for word — that is the last file in the directory to define this
   constraint, so its list is the one the database is holding.
   `backend/tests/test_supervisor_take_up_migration.py` derives the same list
   from that file's own text and fails if this one dropped a word or invented a
   second. `job_taken_up` is deliberately **not** `taken_up`: the older word is
   `take_up_complaint`'s and means a supervisor is *looking at* a complaint;
   this one means one is *going*.
2. **`take_up_work_order`, new (R8, R10, R11)** —
   `force_assign_work_order`'s mechanics with the naming taken out. **There is
   no `p_staff_assignment_id`**, and that absence is the design: a parameter
   naming somebody would make this "assign anybody, without the rank check",
   which is §29's rule with a door in it. The holder is the caller's own active
   `manager`- or `supervisor`-ranked roster row on **this job's** department,
   found from `auth.uid()` by the same predicate `claim_open_work_order` uses to
   identify its caller; no such row is `HB403` in words. Both leadership ranks
   qualify (R10): `can_supervise_department` treats them identically and
   `restamp_department_supervision` can leave a manager as a department's only
   leadership. Everything after the pick is force-assign's — the terminal-status
   gate, the slot rule, the named overlap refusal, withdraw-then-insert, the
   `scheduled` update and the resident being told somebody is coming. The
   assignment row is `accepted` with `is_forced` **false** and
   `is_auto_assigned` **false**: nobody's consent was overridden and no engine
   decided anything. Two timeline rows, `job_assigned` and `job_taken_up`, both
   stamping the caller. The department hears `job.taken_up`; the caller does
   not, through `notify_complaint_staff`'s exclusion argument rather than a
   branch. `supervision_inherited_at` is **not** touched — it has exactly one
   writer, `restamp_department_supervision`, and a supervisor choosing a job is
   not one being handed one.
3. **`force_assign_work_order` re-issued (R12, closing R7)** —
   `20260822170000` §6's body verbatim, with one variable declared, one lookup
   added and two identifiers changed. Its two `complaint_events` rows stamped
   `v_order.supervisor_membership_id`, the department's supervisor *of record*,
   who is not necessarily the person who pressed Assign; a manager covering for
   a departed supervisor produced a timeline naming the departed supervisor.
   The actor is now resolved from `auth.uid()` the way `take_up_complaint`
   (`20260822120000`:209) resolves it, assertion included — a null actor is
   refused, not defaulted. Unreachable today, because
   `can_supervise_department` resolves the caller from exactly that row;
   asserted anyway, because the alternative is two timeline entries from
   nobody. **No shape change**: same signature, same refusals, same
   notifications, same `is_forced` row.
4. **`claim_open_work_order` re-issued (R13)** — §29's body verbatim with one
   sentence rewritten. R2 stands and the board stays shut to leadership; what
   changed is that the refusal now names the door that *is* open —
   *"Supervisors and managers cannot claim from the board. Use "Take this job
   myself" from your dashboard."* Same `HB403`, same branch, same position. It
   also stops using the phrase "take up" for the thing that is refused while
   the thing that is allowed is called exactly that.
5. **Proof in the transaction, then comment-only post-checks.** §28's lesson
   again: every post-check is a guard-free structural inspection — the SQL
   editor has no `auth.uid()`, so `take_up_work_order` would answer `HB403`
   there and prove nothing. They are reproduced below.

**What it does NOT do, and each absence is deliberate.** No relaxation of §29 —
`dispatch_candidates_at`, `worker_open_jobs` and the rank clause inside the
claim are untouched, so the picker, the ping, the auto-book and the board stay
member-only, and this file declares no fourth function. No `work_orders` status
word (`scheduled` is what force-assign already writes), no
`work_order_assignments` status word, no `dispatch_tasks` kind, no roster-rank
change. **No new SQLSTATE**: the whole file raises only `HB403`, `HB404` and
`HB409`, so `backend/app/core/pg_errors.py` gains nothing (R13). And nothing is
dropped except the constraint it immediately re-adds.

**Deploy the code with it.** Unlike §29, this migration has a backend half:
`POST /api/v1/work-orders/{workOrderId}/take-up` calls the new RPC. The route
answers `404` from PostgREST until the function exists, so the apply comes
first and the deploy second — but a deployed route with no function is a broken
button, not a broken database.

**Pre-check, read-only — run this BEFORE the apply and read the result:**

```sql
-- (a) §29 is applied. All three markers must be true. If any is false, stop
--     and apply 20260823190000 first: this file re-issues the claim body, and
--     copying it forward onto a database that never took the rank clause would
--     leave the board open to leadership behind a refusal message that says it
--     is closed.
select p.proname,
       pg_get_functiondef(p.oid) like '%sa.rank = ''member''%' as has_rank_clause
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and (p.proname in ('worker_open_jobs', 'claim_open_work_order')
        or p.oid::regprocedure::text like 'dispatch_candidates_at(%')
 order by 1;

-- (b) The constraint this file recreates is the one 20260822170000 left. Both
--     must be true. `knows_priority` false means an older definition won at
--     some point and section 1's list would be widening the wrong list.
select pg_get_constraintdef(oid) like '%taken_up%'         as knows_taken_up,
       pg_get_constraintdef(oid) like '%priority_changed%' as knows_priority,
       pg_get_constraintdef(oid) like '%job_taken_up%'     as already_applied
  from pg_constraint
 where conrelid = 'public.complaint_events'::regclass
   and conname  = 'complaint_events_type_check';

-- (c) Who this feature is actually for. Expect at least one row per department
--     that has leadership; a department with none cannot use the new button,
--     which is correct and is worth seeing before the PO tries it.
select sa.department_id, sa.rank, count(*) as active_rows
  from public.staff_assignments sa
 where sa.status = 'active' and sa.is_active
   and sa.rank in ('manager', 'supervisor')
 group by 1, 2
 order by 1, 2;
```

There is no data risk to check for. The constraint swap only ever widens — no
row the table accepted before is rejected after — and the three functions are
`create or replace`. Nothing in this file writes a row, drops a column or
touches a policy.

**Apply:** paste the whole file into the SQL editor and run it. The editor's
destructive-operation warning **will** fire — it sees `drop constraint` and the
`create or replace function` keywords — and it is safe to confirm: the drop is
followed three lines later by the same constraint with one more word in it, and
the whole paste is one transaction, so a failure anywhere rolls the entire file
back. The only output expected is one notice at the end:
*"supervisor_take_up: one new word, one new verb, and two bodies re-issued."*
Section 1's guard, section 1's verification and section 5's proof all raise
rather than report, so a half-applied file cannot look like a successful one.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260824090000', 'supervisor_take_up')
on conflict (version) do nothing;
```

**Post-check, read-only — every one guard-free (§28's lesson):**

```sql
-- (a) The new verb exists, with the frozen signature and one grant. Expect one
--     row: take_up_work_order(uuid, timestamp with time zone, timestamp with
--     time zone), returning uuid, security definer true, acl naming
--     authenticated. This inspects the catalogue rather than calling anything:
--     the SQL editor has no auth.uid(), so calling it would answer HB403 and
--     prove nothing either way.
select p.oid::regprocedure           as signature,
       pg_get_function_result(p.oid) as returns,
       p.prosecdef                   as security_definer,
       array_to_string(p.proacl, ', ') as acl
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname = 'take_up_work_order';

-- (b) The three assignment verbs, and who each stamps on the timeline. Expect
--     take_up_work_order and force_assign_work_order both `stamps_caller` true
--     and `stamps_standing_supervisor` false; claim_open_work_order carries
--     neither spelling, because it resolves its actor into a variable first.
select p.proname,
       pg_get_functiondef(p.oid) like '%v_actor, ''job_%'
         as stamps_caller,
       pg_get_functiondef(p.oid) like '%v_order.supervisor_membership_id, ''job_%'
         as stamps_standing_supervisor
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('take_up_work_order', 'force_assign_work_order',
                     'claim_open_work_order')
 order by 1;

-- (c) §29 survived this file. Expect three rows with has_rank_clause true --
--     the same query as pre-check (a), asked again, because the whole hazard
--     of copying a body forward is what the copy quietly dropped. Plus the new
--     sentence in the claim.
select p.proname,
       pg_get_functiondef(p.oid) like '%sa.rank = ''member''%'
         as has_rank_clause,
       pg_get_functiondef(p.oid) like '%Take this job myself%'
         as refusal_names_the_verb
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and (p.proname in ('worker_open_jobs', 'claim_open_work_order')
        or p.oid::regprocedure::text like 'dispatch_candidates_at(%')
 order by 1;

-- (d) The vocabulary knows the new word and kept every old one. Expect one
--     row, all three true.
select pg_get_constraintdef(oid) like '%job_taken_up%'     as knows_job_taken_up,
       pg_get_constraintdef(oid) like '%taken_up''%'       as knows_taken_up,
       pg_get_constraintdef(oid) like '%priority_changed%' as knows_priority
  from pg_constraint
 where conrelid = 'public.complaint_events'::regclass
   and conname  = 'complaint_events_type_check';

-- (e) Nothing has been taken up yet, which is what a new word looks like on
--     the day it lands. Expect zero. Run it again after the functional check
--     below and expect one.
select count(*) as taken_up_jobs
  from public.complaint_events
 where event_type = 'job_taken_up';
```

**Post-check, functional:** as a department supervisor in the worker portal,
open a complaint with a scheduled job that nobody holds and press **"Take this
job myself"**. The job moves to `scheduled` with you as its holder, the
complaint's timeline gains **both** `job_assigned` and `job_taken_up` naming
**you** — not the department's supervisor of record — and the resident is
notified that somebody is coming. You receive no notification of your own
action; the department's other leadership does. Then check the two neighbours:
the same job's "Assign this job outright" modal still lists **only**
technicians, and the "Open jobs" board is still empty for you, now refusing a
deep-linked claim with *"Supervisors and managers cannot claim from the board.
Use "Take this job myself" from your dashboard."* Last, as the community admin
— who holds no roster row — the take-up call must answer `403`.

**What was checked before this section was written:** the static battery in
`backend/tests/test_supervisor_take_up_migration.py` (22 tests) — the file
parses (`pglast`), sorts after all five files it reasons about, and is the last
declaration of each of the three functions it issues; it declares no fourth
function; the new word list is derived from `20260822170000`'s own text and
differs by **exactly one word**, with `taken_up` proved kept and proved not
reused; the swap is guarded before the drop and proves the new word
specifically; the new function's signature, `security definer`, `search_path`
and grant are pinned, it carries no `p_staff_assignment_id`, its roster lookup
is rank-limited to `manager`/`supervisor`, both its `HB403`s are accounted for,
its three `HB409`s are force-assign's own three, its row is
`accepted/false/false`, it stamps the caller on both timeline rows, and it
notifies the resident and the department but never itself; the two carried
bodies are diffed line by line against their predecessors with the removals
pinned **by name** — two lines from force-assign, one from the claim, and
nothing else may leave; every SQLSTATE the file raises is one `pg_errors` can
map and the set is exactly `{HB403, HB404, HB409}`; no other closed vocabulary
and no dispatch-task kind is named; `supervision_inherited_at` and both
complaint take-up stamps are untouched; the grants and the PostgREST reload are
stated; the in-transaction proof looks for all three diffs, including R12's as
an *absence*; and the post-checks are comment-only and call nothing guarded.
Plus the API battery in `backend/tests/api/test_supervisor_actions.py` (routing,
slot carry, the read-back body, the `HB403` surfacing as 403, and the CSRF pair
on both halves), the directory battery in
`test_migration_directory_is_fresh_appliable.py`, and the 211-operation
`test_openapi_spec.py`. **Not verifiable statically:** that hosted's
`force_assign_work_order` and `claim_open_work_order` are `20260822170000`'s and
§29's before this overwrites them — these are `create or replace`, so the apply
overwrites whatever is there, which is why pre-check (a) exists; that the hosted
`complaint_events` constraint is the one `20260822170000` left, which is
pre-check (b); and whether any department has leadership to use the button at
all, which is pre-check (c).

## 31. `20260826090000_realtime_expansion.sql`

**Independent of §29 and §30.** It declares no function either of them names,
touches no constraint, and fires on tables neither of them writes to. Filename
order still puts it last, which is fine; it can also be applied on its own.

**What breaks without it:** three screens that look live and are not. The outbox
has carried `dashboard.refresh` since `0007` and `notification.created` since
`0030`, and `0028` scoped the first of those to `{admin, manager}` — correctly,
because it means *re-read the admin snapshot*. What that leaves is every
non-admin surface with no frame of its own:

- **A work order changes and nobody hears it.** `public.work_orders` carries no
  SSE trigger at all. It is not one of the twelve tables `0007`'s loop names,
  and nothing in the thirty files since attached one — so the resident watching
  their complaint, the technician watching their queue and the supervisor
  watching a department all learn about a status change on a manual reload.
- **A slot is taken and the grid does not know.** `amenity_bookings` has only
  the generic trigger, which since `0028` speaks to admins. A resident staring
  at the availability grid finds out the slot went by trying to book it.
- **The chat dock polls.** `0046`'s messages reach the notification bell —
  `notify_profile` writes a `notifications` row and `0030`'s trigger turns that
  into a `notification.created` frame — but the thread itself has no topic, so
  the open conversation refreshes on a timer.

**What it does:** three emitter functions and four triggers, in five sections.
Nothing is dropped that this file did not create, and every function lands via
`create or replace`.

1. **`emit_work_order_sse_event` → `work_order.changed`, audience
   `community`.** `after insert or update or delete` on `public.work_orders`,
   as trigger `work_orders_sse_event`. The payload is the table, the work-order
   id, the complaint id and the status word — nothing renderable. The audience
   is the whole community on purpose: the four populations that may read a job
   (`can_read_work_order`, `0036`) do not map onto any role list, so a `role`
   row would have to guess, and guessing *narrow* silently drops the frame for
   the people who needed it. Over-delivery is safe under the doctrine in
   [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — the frame is a hint, the client
   re-reads through the endpoint whose authorization already scopes it, and a
   client nudged about a job it may not see re-fetches an empty answer.
2. **`emit_amenity_sse_event` → `amenity.changed`, audience `community`.** An
   **additional** trigger on `public.amenity_bookings`, named
   `amenity_bookings_amenity_sse`, beside whatever generic trigger that table
   already carries — hosted's is `amenity_bookings_sse` (§26's inventory
   probe), a fresh database's is `dashboard_sse_amenity_bookings`, and this
   file drops neither, so `0028`'s `{admin, manager}` scoping of
   `dashboard.refresh` is untouched and admins converge exactly as before. The
   payload is the table and the amenity id, so the client re-reads availability
   it could already read. `public.amenity_booking_series` gets the same trigger
   **if it exists**: `0023` renamed hosted's to
   `legacy_amenity_booking_series` and creates nothing under the live name, so
   the attach sits behind `to_regclass`, which is `0007`'s own posture for this
   exact table.
3. **`emit_message_sse_event` → `message.created`, audience `member`.** `after
   insert` only, on `public.dm_messages`, as `dm_messages_sse_event` — `0046`
   exposes no update or delete, so an update arm would be a trigger waiting on
   a write that cannot happen. This is `0030`'s member-addressed emitter with
   one extra hop: the thread is addressed by *profile* (`0046`) and the stream
   by *membership* (`0028`), so each recipient participant is resolved to their
   active `community_memberships` row in the thread's community, and a
   participant with no active membership there gets no frame rather than a
   malformed one. The sender is skipped by `is not distinct from` against
   `author_profile_id`, which also means a system line (null author — `0046`'s
   thread-lock notice) reaches **both** participants, since both have a mailbox
   to refresh. The payload is the thread id and the message id; the body
   travels only through the RLS-scoped read, for the reason `0030` refused to
   put a notification title in a frame.
4. **Grants.** All three are trigger functions, which cannot be called
   directly, but the default `execute` grant to `public` still exists on them
   and is revoked — `0046`'s posture for `lock_work_order_threads`.
5. **Proof in the transaction.** A closing `do` block raises if any trigger
   this file claims to have made is missing, **by name**, on the table it names.
   Named rather than bare: `work_orders` had no trigger at all, so "this table
   has some trigger" would have passed against nothing useful. The
   `amenity_booking_series` arm is conditional on the same `to_regclass` that
   gates its attach, so the guard and the proof cannot disagree.

**Topic names are frozen.** `work_order.changed`, `amenity.changed`,
`message.created` — the frontend listeners are being written against exactly
these strings. Renaming one here means a listener that never fires, with no
error anywhere.

**Nothing is dropped, nothing is rewritten, no row is written.** The file
declares no fourth function, alters no table, touches no policy and no
constraint, and does not redefine `emit_dashboard_sse_event`,
`emit_access_request_sse_event` or `emit_notification_sse_event`. Its only
`drop`s are `drop trigger if exists` of its own four names.

**The code half, which needs no migration and no apply order.**
`app/core/realtime.py`'s reconnect backfill reads `id > last_event_id`, and
`prune_sse_events` (`0024`) drops rows older than two hours, so a client that
was away longer than the retention window was handed the tail of the outbox as
though nothing were missing — a gap with no symptom, because the client
believes it is caught up. The backfill now asks
`dashboard_repository.oldest_event_id()` first and, when the oldest surviving
row sits past the client's resume point, prepends the existing `stream.resync`
frame (`dashboard.refresh` for an admin, whose listener already ships) so the
client refetches instead of trusting the middle of its history. That ships in
the deploy, is independent of this file, and works the same whether or not the
apply has happened. Pre-check (d) below is about it: a project without
`pg_cron` never prunes, so the gap it guards against cannot occur there yet.

**Pre-check, read-only — run this BEFORE the apply and read the result:**

```sql
-- (a) 0028 is applied. This is the one thing the static battery cannot check,
--     and it is a hard dependency: two of the three emitters write an
--     `audience` column, and the member-addressed one writes
--     `recipient_membership_id`. On a database without them the insert fails
--     and the whole file rolls back. Expect three rows.
select column_name, data_type, is_nullable
  from information_schema.columns
 where table_schema = 'public' and table_name = 'sse_events'
   and column_name in ('audience', 'audience_roles', 'recipient_membership_id')
 order by 1;

-- (b) And its shape constraint, which is what makes a malformed row
--     unwritable rather than silently undeliverable. Expect one row naming
--     'community', 'role' and 'member'.
select conname, pg_get_constraintdef(oid) as definition
  from pg_constraint
 where conrelid = 'public.sse_events'::regclass
   and conname  = 'sse_events_audience_shape_check';

-- (c) The four tables this file fires on exist, and what each already carries.
--     Expect: work_orders with NO row at all; amenity_bookings with its
--     generic trigger under whatever name hosted holds (`amenity_bookings_sse`
--     per §26's probe); dm_messages with none of ours. None of this file's own
--     four names may appear yet -- if one does, this section has already been
--     applied and the re-run is a no-op, which is fine.
select c.relname as table_name,
       t.tgname  as trigger_name,
       pg_get_triggerdef(t.oid) as definition
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  left join pg_trigger t on t.tgrelid = c.oid and not t.tgisinternal
 where n.nspname = 'public'
   and c.relname in ('work_orders', 'amenity_bookings', 'dm_messages',
                     'dm_threads', 'amenity_booking_series')
 order by 1, 2;
-- `amenity_booking_series` returning no row at all is the EXPECTED result --
-- 0023 parked hosted's copy as `legacy_amenity_booking_series`. The file's
-- to_regclass guard skips it; nothing to do.

-- (d) Is anything actually pruning? Informational, and it is about the code
--     half above, not about this file. Zero rows means pg_cron is not
--     scheduling `prune-sse-events`, so the outbox grows without bound and no
--     client can fall off the back of it yet.
select jobname, schedule, active
  from cron.job
 where jobname = 'prune-sse-events';
-- If `cron.job` does not exist, the extension is not installed. That is the
-- documented state of a project without pg_cron (see 0024 and ARCHITECTURE.md
-- "Retention"), not a failure of this apply.
```

There is no data risk to check for. The file writes no row, drops no column,
alters no table and touches no policy; the three functions are
`create or replace` and the four triggers are `drop trigger if exists` of names
only this file uses.

**Apply:** paste the whole file into the SQL editor and run it. The editor's
destructive-operation warning may fire — it sees `drop trigger` and
`create or replace function` — and it is safe to confirm: every drop names a
trigger this file created three lines later, the whole paste is one
transaction, so a failure anywhere rolls the entire file back. No output is
expected on success; section 5's `do` block raises if any trigger this file
claims to have made is missing, so a half-applied file cannot look like a
successful one.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260826090000', 'realtime_expansion')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
-- (a) The four triggers, by name, and the generic ones still standing beside
--     them. Expect work_orders_sse_event on work_orders;
--     amenity_bookings_amenity_sse on amenity_bookings ALONGSIDE the generic
--     trigger that was there in pre-check (c); dm_messages_sse_event on
--     dm_messages. `amenity_booking_series_amenity_sse` will be absent, which
--     is correct -- the table is not there.
select c.relname as table_name,
       t.tgname  as trigger_name,
       pg_get_triggerdef(t.oid) as definition
  from pg_trigger t
  join pg_class c on c.oid = t.tgrelid
  join pg_namespace n on n.oid = c.relnamespace
 where not t.tgisinternal
   and n.nspname = 'public'
   and c.relname in ('work_orders', 'amenity_bookings', 'dm_messages')
 order by 1, 2;

-- (b) The three emitters: security definer, search_path pinned, and no grant
--     to public or authenticated. Expect three rows, all `security_definer`
--     true, each `config` naming search_path=public, and no acl mentioning
--     anon or authenticated.
select p.proname,
       p.prosecdef                     as security_definer,
       array_to_string(p.proconfig, ', ') as config,
       coalesce(array_to_string(p.proacl, ', '), '(owner only)') as acl
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('emit_work_order_sse_event', 'emit_amenity_sse_event',
                     'emit_message_sse_event')
 order by 1;

-- (c) The generic emitters were NOT rewritten. Expect dashboard.refresh still
--     going to the {admin, manager} role audience -- true -- and the
--     notification emitter still member-addressed -- true.
select p.proname,
       pg_get_functiondef(p.oid) like '%array[''admin'', ''manager'']%'
         as still_role_scoped
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('emit_dashboard_sse_event', 'emit_access_request_sse_event')
 order by 1;

-- (d) The topic census, before and after the functional check below. Run it
--     now and expect the three new topics absent; run it again after and
--     expect work_order.changed at audience `community`, amenity.changed at
--     `community`, and message.created at `member`. Rows older than two hours
--     may have been pruned away between the two readings, which is the
--     retention working, not a miss.
select topic, audience, count(*) as rows
  from public.sse_events
 group by 1, 2
 order by 1, 2;
```

**Post-check, functional:** the frontend listeners for these three topics are
being written in parallel, so read the stream itself rather than a screen —
open the app as any member, and in the browser devtools **Network → the
`/api/v1/events` request → EventStream** pane watch the frames arrive while a
second browser acts:

1. Move a work order's status (assign it, or complete it). The member's stream
   gains a `work_order.changed` frame carrying the work-order id, its complaint
   id and the new status word — including for a resident, which is the whole
   point of the community audience.
2. Book an amenity slot as one resident. A *second* resident's stream gains
   `amenity.changed` with the amenity id. The admin's stream gains **both**
   that and the generic `dashboard.refresh` it always got — two frames, which
   is the "additional, not a replacement" design being visible.
3. Send a direct message. The recipient's stream gains `message.created` with
   the thread id and the message id and **no body**; the sender's stream gains
   nothing at all. Then check the negative case that matters: a third member of
   the same community, with the same page open, receives nothing — `member`
   audience means one connection, and this is the frame that would be a
   disclosure if it were wrong.

**What was checked before this section was written:** the static battery in
`backend/tests/test_realtime_expansion_migration.py` (16 tests) — the file
parses (`pglast`); it sorts after its named predecessor `20260824090000` and
after every file it reasons about, including `0007` (the outbox), `0028` (the
audience columns), `0030` (the member-emitter template) and every file in the
directory that creates `work_orders`, `amenity_bookings`, `dm_threads` or
`dm_messages`, each derived from the migration texts rather than listed by
hand; all three emitters are `security definer` with a pinned `search_path`;
the only trigger names dropped are this file's own four, the string
`dashboard_sse` does not appear anywhere in it, and it holds no
`create table`, `alter table`, `drop function`, `create policy`, `delete from`
or `update public.`; each payload is asserted for what it carries **and** for
what it must not — no title, body, location, priority or name on the work-order
frame, no booker, slot or status on the amenity frame, no message body on the
message frame; the work-order emitter's `DELETE` arm reads `old` and returns
it; the community-audience frames carry neither `audience_roles` nor
`recipient_membership_id`, which is `0028`'s community shape; the series attach
is proved to sit behind its `to_regclass` guard; the message trigger is proved
`after insert` and nothing else, by exact match on the whole trigger
definition; the sender exclusion, the `is not distinct from` spelling that
carries the system line to both participants, and the active-membership
predicate (`community_id`, `status = 'active'`, `ended_at is null`) are each
pinned; and the closing `do` block is proved to name every trigger and every
table specifically, with `not tgisinternal` and a `raise exception` per arm.
Plus the directory battery in `test_migration_directory_is_fresh_appliable.py`.
The code half is pinned by `backend/tests/test_realtime.py`, which covers both
branches of the prune-horizon guard — a resume point behind the horizon gets
the resync frame **first** and stamped with the client's own id, the contiguous
boundary (`oldest = last + 1`) gets no resync, an empty outbox is not a gap, a
failing horizon probe fails open and still delivers, and the repository read is
ascending. **Not verifiable statically:** that hosted's `sse_events` carries
`0028`'s audience columns and shape constraint — both sort long before this
file and the ledger says they are applied, which is why pre-check (a) and (b)
exist; and whether `pg_cron` is scheduling the pruner at all, which is
pre-check (d).

## 32. `20260827210000_one_live_job_per_complaint.sql`

**Must follow §28 `20260823180000_resident_sets_the_time.sql`; independent of
§29, §30 and §31.** It carries §28's `create_work_order` body forward whole and
adds two things to it, so applying it against a database that has not yet had
§28 would install the guard *and* silently roll the pick-mode fork forward on
top of whatever was there — and applying §28 *after* it would roll the guard
back out, with nothing in the apply output to say so. Filename order puts it
last, which satisfies all of it. It declares nothing §29, §30 or §31 declares
and fires on nothing they touch.

**What breaks without it — and this one was observed, not reasoned about.**
Complaint `f40e11d4-e322-4847-be2f-8f2caf6df722` collected a **second**
`awaiting_resident` work order fifteen seconds after the resident booked the
first one's visit (live, 2026-08-27). Nothing refused it, because nothing has
ever asked: `create_work_order` checks the department, the community and the
shape of the slot, and then inserts. Two things then follow:

- **The resident holds two open requests for one problem.** Both jobs notify
  them, both arm a 24-hour deadline, and `get_schedule_request` returns
  whichever live row it reaches first — so the screen can show the *other* one's
  state than the one the resident answered.
- **A technician's day goes to work another job already owns.** The second job
  dispatches on its own, and nothing anywhere reconciles the two.

The window is the triage screen's own: the "Raise it" form is drawn before the
jobs list has finished loading, so a supervisor can raise against a complaint
whose live job has not appeared on their screen yet. The frontend half of this
ruling closes that window (`WorkOrderTriage.jsx`); **this file is the half that
holds when the frontend is wrong, when two supervisors act at once, and when a
button is double-clicked.**

**The rule, in one sentence.** A complaint carries several work orders over its
life and **one at a time** — a failed visit's replacement or a reopened
complaint's new job comes after the previous job ends, never alongside it.

**LIVE** = `draft`, `awaiting_resident`, `offered`, `scheduled`, `in_progress`.
Terminal = `completed`, `failed`, `cancelled`. The eight are the closed list
`work_orders_status_check` (`0036`) allows, so the two sets are exhaustive and
this file adds no ninth word and touches no constraint. The five are exactly the
tuple `app/services/work_orders_service.py::_OPEN_STATES` holds and the
`get_schedule_request` resolver already calls live; the SQL list is inline with
a comment naming that tuple, and the static suite derives the expected five
**from the Python source** so the two cannot drift apart unnoticed.

**What it does:** one `create or replace function public.create_work_order`,
under the **unchanged eight-argument signature**, with §28's body and exactly
two additions.

1. **The complaint read takes a row lock.**
   `select * into v_complaint from public.complaints where id = p_complaint_id
   for update`. The guard below is a read followed by a write, which is the
   shape that loses a race: without the lock, two concurrent raises both read
   "no live job" and both insert, which is a fair description of what happened
   on 2026-08-27. The **complaint** is locked, not the jobs — locking the empty
   set the guard is checking would lock nothing at all. This is the lock
   `resident_set_work_order_schedule` (§28) already takes on the job it is about
   to move, for the same reason.
2. **The refusal**, after the department and community checks and after the
   slot-shape checks, in front of every write:

   ```sql
   raise exception
     'A job is already live on this complaint. Finish, fail, or cancel it before raising another.'
     using errcode = 'HB409';
   ```

   It sits *behind* the argument validation deliberately: a half-slot or a
   backwards slot is the caller's own request being malformed and deserves its
   422, while this is a statement about the world and deserves its 409.

**The sentence is frozen** (`docs/plans/ONE_LIVE_JOB_SPEC.md` §2). `HB409` is
the existing conflict signal — `app/core/pg_errors.py` maps it to HTTP 409 with
envelope `code: "conflict"` and the message travels to the screen **verbatim**.
No new envelope code, and no client parses the text. Rewording this string here
is rewording it on a supervisor's screen.

**Nothing else moves.** No table, no column, no policy, no constraint, no
trigger, no second function, and no row is written. `complaints.status` is not
touched and neither is any complaint-lifecycle code: the ruling is about
`work_orders` liveness alone. The grant on the function
(`to authenticated`, §28) survives untouched — `create or replace function`
retains the existing ACL — and there is no `notify pgrst, 'reload schema'`
because the signature does not change, so PostgREST's catalogue does not either.
The only other statement in the file is a `comment on function`.

**Existing duplicates are history and this file does not touch them.** The
guard refuses **new** raises; it does not reach back. The leak complaint above
already holds two live jobs and will keep holding them after the apply — and
because it does, *no* further raise against that complaint will be accepted
until one of them ends, which is the guard working. The extra
`awaiting_resident` job `1f0bf129-d47d-4236-9082-ecf0a28b245c` is **the owner's
to cancel from the UI**, not this file's to cancel by hand: which of two live
jobs is the real one is a lifecycle decision that belongs to a person, and a
migration that made it silently would be inventing it. Post-check (d) below is
where to confirm the cancel landed.

**Pre-check, read-only — run this BEFORE the apply and read the result:**

```sql
-- (a) §28 is applied, and this is the body about to be carried forward. Expect
--     ONE row, `has_pick_mode` true (the §28 fork is present),
--     `has_row_lock` and `has_live_guard` both FALSE. If the two guards are
--     already true, this section has been applied and the re-run is a no-op,
--     which is fine. If `has_pick_mode` is false, STOP: §28 has not been
--     applied and applying this file would install its body out of order.
select p.oid::regprocedure                                   as signature,
       pg_get_functiondef(p.oid) like '%''mode'', v_mode%'   as has_pick_mode,
       pg_get_functiondef(p.oid) like '%for update%'         as has_row_lock,
       pg_get_functiondef(p.oid) like '%A job is already live%' as has_live_guard
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public' and p.proname = 'create_work_order'
 order by 1;
-- More than one row means an overload exists. This file replaces the
-- eight-argument one only -- the one `work_orders_repository.create_work_order`
-- calls -- so a second signature would keep an unguarded path open and is worth
-- resolving before the apply, not after.

-- (b) The status vocabulary is still the closed eight. The live set below is
--     five of them and the terminal set is the other three; a ninth word would
--     be a status this guard has no opinion about.
select conname, pg_get_constraintdef(oid) as definition
  from pg_constraint
 where conrelid = 'public.work_orders'::regclass
   and conname  = 'work_orders_status_check';

-- (c) Who is already carrying more than one live job. Informational, and it is
--     the census the guard is about to stop growing. Expect at least
--     f40e11d4-e322-4847-be2f-8f2caf6df722 with two.
select w.complaint_id,
       count(*)                              as live_jobs,
       array_agg(w.id order by w.created_at) as job_ids,
       array_agg(w.status order by w.created_at) as statuses
  from public.work_orders w
 where w.status in ('draft', 'awaiting_resident', 'offered',
                    'scheduled', 'in_progress')
 group by w.complaint_id
having count(*) > 1
 order by 2 desc, 1;

-- (d) The two jobs of the observed leak, by name, so the post-check has a
--     before-picture to compare against.
select id, status, subject_kind, scheduled_start_at, resident_deadline_at,
       created_at
  from public.work_orders
 where complaint_id = 'f40e11d4-e322-4847-be2f-8f2caf6df722'
 order by created_at;
```

There is no data risk to check for. The file writes no row, drops nothing,
alters no table and touches no policy; its one function lands via
`create or replace` under a signature that does not change.

**Apply:** paste the whole file into the SQL editor and run it. No output is
expected on success. The closing `do` block reads the installed definition back
out of the catalogue — signature present, `for update` present, the refusal
sentence present, `HB409` present, the guard scoped to `w.complaint_id =
v_complaint.id`, and each of the five live states present — and raises if any of
it is missing, so a half-pasted file cannot look like a successful one. The
whole paste is one transaction, so a failure anywhere rolls it back.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260827210000', 'one_live_job_per_complaint')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
-- (a) The installed body is this one. Expect ONE row, all three booleans true:
--     §28's fork survived the carry-forward, and both additions are there.
select p.oid::regprocedure                                   as signature,
       pg_get_functiondef(p.oid) like '%''mode'', v_mode%'   as has_pick_mode,
       pg_get_functiondef(p.oid) like '%for update%'         as has_row_lock,
       pg_get_functiondef(p.oid) like '%A job is already live%' as has_live_guard
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public' and p.proname = 'create_work_order'
 order by 1;

-- (b) The grant survived the replace, and the posture did not change. Expect
--     `security_definer` true, `config` naming search_path=public, and an acl
--     that still lists `authenticated=X` -- `create or replace function`
--     retains the ACL, and this check is here because "it silently did not" is
--     the failure that looks exactly like a 403 for every supervisor.
select p.prosecdef                            as security_definer,
       array_to_string(p.proconfig, ', ')     as config,
       coalesce(array_to_string(p.proacl, ', '), '(owner only)') as acl,
       obj_description(p.oid, 'pg_proc')      as comment
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.oid = 'public.create_work_order(uuid,uuid,uuid,text,text,'
               'timestamptz,timestamptz,text)'::regprocedure;

-- (c) Nothing else was rewritten. Expect both true -- the resident's own
--     setter still takes its own lock (§28) and the projection still runs off
--     the jobs, neither of them redefined by this file.
select p.proname,
       pg_get_functiondef(p.oid) like '%for update%' as still_locks
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('resident_set_work_order_schedule',
                     'respond_to_work_order_schedule')
 order by 1;
```

**Post-check, functional — this is the one that proves the ruling, and it needs
two complaints:**

1. **The refusal.** Sign in as a supervisor of a department that owns a
   complaint with a live job on it — any complaint in pre-check (c)'s census, or
   raise a job on a fresh complaint and then try to raise a second. The second
   raise must come back **409** with exactly:

   > A job is already live on this complaint. Finish, fail, or cancel it before
   > raising another.

   Read the response in devtools → Network, not only the screen: the envelope
   must be `{"code": "conflict", "message": "<the sentence>"}`, and a **500** or
   a "Could not raise that job" means `HB409` is not reaching
   `app/core/pg_errors.py` and the guard is raising into a generic handler.
2. **The rule is one at a time, not one ever.** Cancel (or complete, or fail)
   that live job, then raise again on the same complaint. It must succeed. This
   is the half that makes the feature usable — a failed visit's replacement and
   a reopened complaint's new job are exactly what `create_work_order` is for —
   and a guard that refused here would be a complaint nobody can ever work
   again.
3. **A second complaint is unaffected.** Raise a job on a *different* complaint
   in the same department while the first one's job is live. It must succeed:
   the guard is scoped to `complaint_id` and to nothing else.
4. **The lock.** Optional, and the only way to see it directly: open two SQL
   editor sessions, `begin` in both, and call `create_work_order` for the same
   complaint in each without committing. The second call must **block** until
   the first commits, and then refuse. A second call that returns immediately
   with a new id means the `for update` did not land — re-read post-check (a).

**And (d), the housekeeping the guard deliberately does not do.** The leak
complaint `f40e11d4-e322-4847-be2f-8f2caf6df722` still holds two live jobs after
this apply. Cancel the extra `awaiting_resident` one,
`1f0bf129-d47d-4236-9082-ecf0a28b245c`, **from the UI** — the supervisor's
"Cancel" on the work-order triage screen, which writes the cancellation reason,
the event and the resident's notification the way every other cancellation does.
Do not `update public.work_orders set status = 'cancelled'` by hand: that skips
all three. Then re-run pre-check (c); the complaint should have dropped to one
live job, and raising against it should be possible again once that one ends.

**What was checked before this section was written:** the static battery in
`backend/tests/test_one_live_job_migration.py` (18 tests) — the file exists
under the frozen name and parses (`pglast`); it sorts after
`20260823180000`, and is proved to be the **last** declarer of
`create_work_order` in the directory, which is what decides which body the
database ends up holding; the eight-argument signature is unchanged, parameter
by parameter, and the function is still `security definer` with a pinned
`search_path`; **the body is diffed line by line against §28's**, and the only
removed line is the unlocked `select` while every added line is a comment, the
`for update` continuation, or part of the guard — so the fork, the deadline in
both modes, the event word and the notification are proved to have survived the
carry-forward rather than spot-checked; the lock is proved to come before the
guard and the guard before all three writes (`work_orders`,
`complaint_events`, `notify_member`); the refusal sentence is pinned character
for character with its `HB409`, and the file's whole SQLSTATE census is proved
to be `{HB403, HB404, HB409, 22004}` — no new code invented; the five live
states are **derived from `work_orders_service._OPEN_STATES`** and each asserted
present in the guard, the three terminal states asserted absent, and the guard
asserted scoped to `complaint_id` alone (no department, community or supervisor
term); the file is proved to declare exactly one function and to contain no
`create/alter/drop table`, no policy, no constraint, no trigger, no
`update public.work_orders`, no `'cancelled'` and no
`update public.complaints` — the last three being the "it does not touch history
and does not touch the lifecycle" promise stated as absences; the closing
`do` block is proved to probe by explicit signature and to check every clause it
claims; and the route docstring is proved to carry the new 409 row and the
corrected multiplicity prose. Plus the directory battery in
`test_migration_directory_is_fresh_appliable.py`, and the whole backend suite.
`test_resident_sets_the_time_migration.py` was amended in the same commit: its
"last word on every function it redefines" check now excludes
`create_work_order` and asserts instead that this file is its one successor,
which is the property that is actually true after 2026-08-27.
**Not verifiable statically:** that two concurrent raises actually serialize on
the lock, and that `HB409` surfaces as a 409 with the sentence rather than a 500
— post-checks 1 and 4 are the only proof of either.

## 33. `20260828090000_residence_claim_on_join.sql`

**Apply this AFTER §31 and after §32
`20260827210000_one_live_job_per_complaint.sql`.** Not because they share
an object — this file touches `access_requests`, `approve_access_request` and
`pending_access_request_overview`, none of which §29, §30, §31 or §32's
migration name — but because filename order is apply order and this file's
version sorts after all of theirs. If any of them is somehow still outstanding
when you get here, applying this one first breaks nothing; apply them anyway,
and apply all of it in filename order.

**What breaks without it:** every self-service join approval mints a resident
with no residency. The wire contract for a unit exists end to end —
`access_requests.requested_unit_id`, the approve RPC's `p_unit_id`, and a
`unit_residencies` insert that fires when either is set — but both ends send
null: the join form has no unit field and the admin's Accept button posts `{}`.
So `membership.unit` is null, flat/tower render '—' across both portals, and
`_has_active_residency` (`backend/app/api/deps.py`) 403s people who genuinely
live there. Live testing surfaced it on 2026-08-27. An admin cannot even repair
it by hand: apartment communities carry exactly one `units` row (the founder's
own flat, seeded by `20260805144502`), and there is no unit CRUD anywhere in
the product.

The product owner's rulings (2026-08-27, plan-mode Q&A), verbatim:

1. *"Applicant states their residence as **free text at request time** —
   Tower/Block + Flat for `apartment`, Villa number for `layout_villa` — stored
   on `access_requests`. No unit exposure to non-members; the privacy invariant
   stands."*
2. *"**Approval requires a unit**: the RPC refuses a resident approval without
   one, so every approved resident gets a `unit_residencies` row."*
3. *"Inventory gap solved by **find-or-create at approval**: admin
   confirms/edits the claimed residence; the RPC matches an existing active
   unit in that community or creates it (with its building) inline. No
   unit-management screen in this work."*

**What it does:** two columns, one signature change, one view append, in five
sections.

1. **Two claim columns (ruling 1)** — `requested_building_text` and
   `requested_unit_text` on `access_requests`, each null or a non-blank string
   of at most 120 characters (the `rejection_reason` convention with the blank
   refusal added). Two columns and not one so tower and flat stay separable —
   the approval prefill feeds `normalize_unit_code(tower, flat)` on the Python
   side, and a single concatenated field is how the documented C-C-505
   double-prefix hazard happens. `add column if not exists` plus
   `pg_constraint`-guarded CHECK adds, so a re-run is a no-op.
   `backend/tests/test_residence_claim_migration.py::test_both_claim_columns_are_added_idempotently_with_the_trim_length_check`
   pins the shape.
2. **`approve_access_request` re-issued as six arguments (rulings 2 and 3)** —
   the 4-argument signature is **dropped first**, not overloaded: PostgREST
   cannot dispatch overloads, and with both in the catalogue
   `POST /rpc/approve_access_request` answers 300 for every caller
   (`test_the_old_signature_is_dropped_by_name_and_before_the_create`). The
   body is the applied `20260730170036`'s — the lock, the reviewer check, the
   idempotent already-approved return, the membership insert with its
   `unique_violation` fallback, the residency insert with the hosted-only
   `created_by_membership_id`, the final update — proved surviving span by
   span, each span extracted from that file's own text rather than retyped
   (`test_every_load_bearing_statement_of_the_old_body_survives`). Added
   between the existing validation and the membership insert: `p_unit_code` is
   matched case-insensitively against the community's units (found-but-inactive
   refuses in words as `HB422`,
   `test_an_inactive_unit_is_a_refusal_in_words_not_a_silent_duplicate`); not
   found is find-or-create mirroring the founder RPC — for `layout_villa` the
   building code defaults to the unit code itself and each villa gets its own
   `buildings` row (`building_type 'villa'`, `unit_type 'villa'`), apartment
   creates or reuses a `block` from `p_building_code` — both inserts
   `on conflict do nothing` with a re-select, so two admins approving into the
   same new tower race against the unique constraints instead of each other
   (`test_the_find_or_create_is_race_safe_and_mirrors_the_founder_shape`).
3. **THE GATE (ruling 2)** — a resolution that still holds no unit refuses the
   whole approval with the new SQLSTATE `HBUNT`, **before the membership
   insert**, so a refused approval writes nothing and the request stays cleanly
   pending for the retry that carries a unit
   (`test_the_gate_refuses_before_anything_is_written`). The residency insert
   loses its `if target_unit_id is not null` guard: after the gate the
   condition is always true, and a guard that can no longer be false is a
   sentence claiming this function still mints unitless residents
   (`test_the_residency_insert_lost_its_guard_and_nothing_else`). `HBUNT` maps
   in `backend/app/core/pg_errors.py` to a 422 with code
   `approval_requires_unit` — its own code, not `HB422`'s generic
   `validation_error`, because "you forgot the unit" is an omission the client
   can point a form field at
   (`test_the_new_code_is_a_validation_error_the_client_can_point_at_a_field`).
4. **`pending_access_request_overview` re-issued (ruling 1's admin half)** —
   the same columns in the same order with three APPENDED:
   `requested_building_text`, `requested_unit_text`, `community_type` (the
   admin card needs the claim to prefill and the community type to label
   Tower/Flat vs Villa). `create or replace view` permits appending and nothing
   else; the old order is derived from `0024`'s own text and proved surviving
   as a prefix, `security_invoker = true` included
   (`test_the_view_appends_and_keeps_every_column_where_it_was`,
   `test_the_view_keeps_security_invoker_and_reissues_its_comment`).
5. **Proof in the transaction, then comment-only post-checks.** The proof
   raises if the 4-argument signature survived the drop, if the new body lost
   the `HBUNT` gate, or if the view's tail is not exactly the three appended
   columns — each an apply that would otherwise *look* clean. The post-checks
   are reproduced below; every one is a guard-free catalogue inspection
   (§28's lesson — and this RPC is service-role-only and **writes** on
   success, so calling it would either refuse or mint a real membership).

**What it does NOT do, and each absence is deliberate.** The `audit_events`
insert that `20260730170036` dropped is **not restored** — that was a
hosted-compat decision (the hosted table's shape drifted from the migrations')
and it stands; recorded as DERIVED in the change log. No unit CRUD screen —
ruling 3 closes the inventory gap at approval, not with a new surface. No SSE
payload change — the `access_requests` triggers from `0024` fire on the UPDATE
this function already does, and the admin queue refetches through the view,
which now carries the new fields. And `requested_unit_id` keeps working — a
validated FK path invitations already use and a future villa picker could,
still the highest-precedence input after `p_unit_id` itself.

**Deploy the code AFTER the apply.** This migration has a backend half: the
join endpoint stores the two claim columns and the approve endpoint sends
`p_unit_code`/`p_building_code`. The Python repository includes the new RPC
keys **only when non-null**, so the old backend against the new database
degrades gracefully (a 4-key payload binds to the 6-argument function through
its defaults) — but the new backend against the old database does not: an
insert naming `requested_unit_text` errors on the missing column, and an RPC
payload carrying `p_unit_code` finds no 4-argument function that accepts it.
Apply first, deploy second.

**Pre-check, read-only — run this BEFORE the apply and read the result:**

```sql
-- (a) The function being replaced is the 4-argument `20260730170036` body.
--     Expect exactly one row, pronargs = 4. Two rows means an overload
--     already exists and PostgREST is already broken; zero means the drop
--     will no-op and only the create matters. Neither stops the apply.
select p.oid::regprocedure as signature, p.pronargs
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public' and p.proname = 'approve_access_request';

-- (b) The case-insensitive match assumes one unit per spelling. Expect zero
--     rows; a row here means two units in one community differ only by case,
--     and the match will pick one of them arbitrarily (limit 1). Rename one
--     of the pair first if any appear.
select community_id, upper(unit_code) as code, count(*)
  from public.units
 group by 1, 2
having count(*) > 1;

-- (c) The view being replaced is 0024's eleven-column shape. Expect 11; a
--     different number means another definition won at some point, and the
--     append below would not be an append.
select count(*) as view_columns
  from information_schema.columns
 where table_schema = 'public'
   and table_name = 'pending_access_request_overview';
```

There is no data risk to check for. The two columns arrive null everywhere, the
CHECKs accept null, no existing row is touched, and the function and view
swaps replace code, not data. The one behavioural change is the intended one:
an approval that names no unit, which used to half-succeed, now refuses whole.

**Apply:** paste the whole file into the SQL editor and run it. The editor's
destructive-operation warning **will** fire — it sees `drop function` — and it
is safe to confirm: the drop is the overload rule, the create follows in the
same paste, and the whole paste is one transaction, so a failure anywhere rolls
the entire file back. The only output expected is one notice at the end:
*"residence_claim_on_join: two claim columns, a 6-arg approve with the unit
gate, and the view carries the claim."* Section 5's proof raises rather than
reports, so a half-applied file cannot look like a successful one.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260828090000', 'residence_claim_on_join')
on conflict (version) do nothing;
```

**Post-check, read-only — every one guard-free (§28's lesson):**

```sql
-- (a) One approve_access_request, with six arguments, security definer,
--     granted to service_role only. Expect exactly one row, pronargs = 6.
select p.oid::regprocedure           as signature,
       p.pronargs                    as args,
       p.prosecdef                   as security_definer,
       array_to_string(p.proacl, ', ') as acl
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname = 'approve_access_request';

-- (b) The two claim columns and their CHECKs. Expect two rows from each.
select column_name, data_type, is_nullable
  from information_schema.columns
 where table_schema = 'public' and table_name = 'access_requests'
   and column_name in ('requested_building_text', 'requested_unit_text');
select conname, pg_get_constraintdef(oid)
  from pg_constraint
 where conrelid = 'public.access_requests'::regclass
   and conname like 'access_requests_requested_%_text_check';

-- (c) The view's tail is the three appended columns, in this order, and
--     nothing before them moved. Expect 14 rows, positions 12-14 being
--     requested_building_text, requested_unit_text, community_type.
select ordinal_position, column_name
  from information_schema.columns
 where table_schema = 'public'
   and table_name = 'pending_access_request_overview'
 order by ordinal_position;

-- (d) Nobody has claimed a residence yet, which is what day one looks like.
--     Expect zero until the join form ships.
select count(*) as requests_with_a_claim
  from public.access_requests
 where requested_unit_text is not null;
```

**Post-check, functional (after the backend and frontend deploys):** as an
apartment applicant, submit a join request — the form now requires Tower/Block
and Flat Number — and as that community's admin, open Pending Registrations:
the card shows the claim, Accept expands an inline panel prefilled from it, and
Confirm approves. The new resident's `membership.unit` is populated and the
resident-guarded pages load instead of 403ing. Approve a **pre-migration**
pending request by typing the unit into the empty panel. Then approve with the
unit field cleared: the API answers `422` with code `approval_requires_unit`
and the request stays pending. Last, approve into a tower that does not exist
yet and confirm the building and unit rows were created (`select * from
public.units order by created_at desc limit 3`).

**What was checked before this section was written:** the static battery in
`backend/tests/test_residence_claim_migration.py` (21 tests) — the file parses
(`pglast`), sorts after the three files it reasons about, and is the **last**
definer of `approve_access_request`, that list derived by scanning the
directory's own text; it declares no second function; the drop names the exact
4-argument signature and precedes the create; the six-argument signature,
`security definer`, `search_path`, and the service-role-only revoke/grant pair
are pinned on the new signature, with exactly one grant in the file; every
load-bearing statement of `20260730170036`'s body survives, each span
extracted from that file's text; the residency insert's guard is removed and
nothing else around it; the `HBUNT` gate stands before the membership insert
and after the carried validation; the code match is case-insensitive, the
create exact-case, the find-or-create `on conflict`-guarded against both
unique constraints with the villa defaulting rule stated; the SQLSTATE set is
exactly `{HB422, HBUNT}` and both are mapped, `HBUNT` as a `ValidationError`
with code `approval_requires_unit` distinct from `HB422`'s; both columns carry
the trim+length CHECK behind idempotent guards; the view's old column order is
derived from `0024`'s text and survives as a prefix with exactly the three
appended columns and `security_invoker = true`; the in-transaction proof
checks the three failures with no symptom; the file's **last statement** is
`notify pgrst, 'reload schema'`; and the post-checks are comment-only and call
nothing guarded. Plus the directory battery in
`test_migration_directory_is_fresh_appliable.py` and the SQLSTATE precedent
suite in `test_leadership_exclusivity_migration.py`, both green beside it.
**Not verifiable statically:** that hosted's `approve_access_request` is
`20260730170036`'s 4-argument body before the drop (pre-check (a)); that no
community holds two units differing only by case (pre-check (b)); and that the
hosted view is `0024`'s eleven columns (pre-check (c)).

## 34. `20260829120000_drop_legacy_approve_overload.sql`

**Filename order is apply order. This file sorts after §33
`20260828090000_residence_claim_on_join.sql`, so apply it there — but applying
it BEFORE §33 breaks nothing.** The drop targets only the stray 4-argument
overload described below, which shares no name, no object and no dependency
with §33's 6-argument `approve_access_request`. Apply in filename order
regardless.

**Where the stray came from.** The hosted database carries a prototype-era
overload of `approve_access_request` that exists in **no migration in this
tree**:

```sql
approve_access_request(p_access_request_id uuid, p_profile_id uuid,
  p_default_invoice_amount numeric, p_due_at timestamptz)
```

`SECURITY DEFINER`, returns `uuid`. In one call it approves an access request
and inserts a `community_membership`, a `unit_residencies` row, and an ISSUED
`maintenance` invoice numbered `'MNT-YYYYMMDD-<request uuid>'`. It surfaced
during §33's pre-check (a) on 2026-08-29: that query
(`select p.oid::regprocedure, p.pronargs ... where p.proname =
'approve_access_request'`) returns more than the one row §33 assumes it is
replacing, because this stray has sat beside the real overload the whole time,
undeclared anywhere in this repository.

**Why it goes.** It is dead legacy code that, if ever invoked, writes real
membership, residency and invoice rows nobody asked for. Nothing in this tree
references its parameter names (`p_access_request_id`,
`p_default_invoice_amount`, `p_due_at`) or its invoice prefix (`MNT-`) —
verified by grep across the repository — and the current backend calls the
residency-shaped overload by its own named parameters
(`p_request_id`, `p_reviewer_profile_id`, ...), never this one's. Dropping it
also makes `approve_access_request` unambiguous by signature: **after §33 and
§34 are both applied, §33's post-check (a) finally returns its expected
"exactly one row, pronargs = 6"** — before §34, the stray survives §33 (that
file's drop only targets the residency-shaped 4-arg
`(uuid, uuid, uuid, public.residency_relationship)`, not this numeric/timestamp
one) and the census keeps reporting two rows.

**What it does:** one statement of substance —
`drop function if exists public.approve_access_request(uuid, uuid, numeric,
timestamptz);` — idempotent (`if exists`, so a re-run or an already-clean
database no-ops), followed by an in-transaction proof and a schema-cache
reload. It does not create, drop or reference the 6-arg signature §33 installs
— this file owns the stray alone, and applies whether or not §33 has run.

**Pre-check, read-only — run this BEFORE the apply and read the result:**

```sql
-- (a) The overload census. Expect the stray plus whichever real overload is
--     current: two rows if §33 has been applied (pronargs 4 and 6), or two
--     4-arg rows if it has not (the stray, and the residency-shaped one §33
--     has not yet replaced). Either is fine -- this file only removes the
--     numeric/timestamptz stray, identified by name below, not by count.
select p.oid::regprocedure, p.pronargs
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public' and p.proname = 'approve_access_request';

-- (b) Informational only: the stray's ACL, so there is a before-picture. Any
--     result is fine and the drop proceeds regardless -- a SECURITY DEFINER
--     function's grants do not change what dropping it costs.
select proacl from pg_proc
 where oid = 'public.approve_access_request(uuid,uuid,numeric,timestamptz)'::regprocedure;
```

There is no data risk to check for. The statement drops a function, writes no
row, and touches no table, column, policy or constraint.

**Apply:** paste the whole file into the SQL editor and run it. The editor's
destructive-operation warning **will** fire — it sees `drop function` — and it
is safe to confirm: the file's only other statements are the in-transaction
proof and the schema-cache reload, and the whole paste is one transaction, so
a failure anywhere rolls it back. The only output expected is one notice:
*"drop_legacy_approve_overload: the prototype 4-arg approve is gone;
approve_access_request is unambiguous."*

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260829120000', 'drop_legacy_approve_overload')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
-- Re-run the overload census. Expect the stray absent. Once §33 is also
-- applied, expect exactly one row, pronargs = 6 -- the result §33's own
-- post-check (a) was written to find, and the reason this file exists.
select p.oid::regprocedure, p.pronargs
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public' and p.proname = 'approve_access_request';
```

**What was checked before this section was written:** the static battery in
`backend/tests/test_drop_legacy_approve_overload_migration.py` — the file
exists under the frozen name and sorts after `20260828090000`; the drop
statement names exactly the `(uuid, uuid, numeric, timestamptz)` signature
with `if exists`; the in-transaction proof probes that exact signature via
`to_regprocedure` and raises if it survives; the file contains
`notify pgrst, 'reload schema'`; and the file does not name the 6-argument
signature in any `drop` or `create`, proving its independence from §33.
**Not verifiable statically:** that the stray actually exists on the hosted
database before the apply (pre-checks (a) and (b) are the only proof of
that), and that PostgREST's schema cache actually drops the stray signature
rather than continuing to answer for it until the next restart.

## 35. `20260830090000_hiring_skill_union.sql`

**Independent of §32, §33 and §34, and of every file before them.** It replaces
three functions none of those declare, touches no table, and fires on no
trigger. Filename order puts it last; apply it there.

**What breaks without it — reported from the live app, issue #55.** A community
runs a security department. Its complaint category is named "Security" (or
"Security Management"); the skills catalogue holds *Security Guard* and *Gate
Officer*. `link_category_skill` (`0034` 216-233) fills
`complaint_categories.skill_id` by **exact name match**, so that category
derives no skill at all — `skill_id` stays null, silently, and every reader
that gates on the category path alone concludes the department needs nothing.

`20260812090100_skills_and_categories.sql` gave the department a way out of
exactly this — `department_skills`, a list it declares for itself — and taught
**one** reader about it: `search_hireable_service_providers`, whose `needed`
CTE became the union of the two paths (that file's `-- CHANGED` note at 681,
carried forward whole by §14 `20260821113000_location_labels.sql` 524-535).
Three readers were left behind, and the result is a hiring flow that
contradicts itself inside one screen:

- **The manager is offered a candidate and then refused.** The candidate list
  reads `department_skills`, so the guard appears on it. Pressing invite calls
  `invite_service_provider`, which does not, and the manager is told *"This
  person does not have a required skill."* about somebody the same screen just
  recommended.
- **The guard cannot find the community.** `search_serviceable_communities`
  builds its `matching_departments` CTE from categories alone, so the community
  either does not appear with a department to apply to, or appears with none.
- **And could not apply if they did.** `apply_to_department` gates the same
  way and answers *"Your skills do not match this department."*

One table, four readers, one of them taught. A department in this position can
hire nobody through either direction of the handshake, and nothing in the
product says why.

**The rule, in one sentence.** A department needs a skill if it has **declared**
that skill, **or** if one of its complaint categories implies it — the union,
in every function that asks the question.

**UNION, not replacement.** A department that has declared no skills keeps
hiring off its categories exactly as it did yesterday. This file adds a second
way for a department to say what it needs; it withdraws neither the first nor
anything else. Nobody who could be hired before this file can be refused after
it.

**What it does:** three `create or replace function` statements, each carrying
its live body forward **whole** —
`20260811162409_service_professional_onboarding.sql` 566 for
`apply_to_department` and 648 for `invite_service_provider`,
`20260812181443_search_nearby_communities.sql` 5 for
`search_serviceable_communities` — with only the skill-gate predicate
rewritten and marked `-- CHANGED` in place (the `20260812113000` convention).
The two scalar guards gain a `needed` CTE spelled exactly as
`search_hireable_service_providers` spells it; the search gains a
`department_needs` CTE feeding `matching_departments` in place of its inlined
category join. Then the three `revoke`/`grant` pairs, one refreshed
`comment on function`, `notify pgrst, 'reload schema'`, and an in-transaction
proof.

**Signatures are byte-identical**, so the existing ACLs survive the replace
untouched — the grants are reissued anyway, matching what both source files
do. Nothing else moves: no table, no column, no policy, no constraint, no
trigger, no fourth function. `department_skills` is only read.

Idempotent: three `create or replace` statements and their grants may all be
run again. One transaction — the SQL editor wraps the paste, so a failure
anywhere rolls back everything.

**Pre-check, read-only — run this BEFORE the apply and read the result:**

```sql
-- (a) The three deployed bodies are category-only. Expect three rows, each
--     with reads_department_skills = false and reads_categories = true. A row
--     already reading department_skills means somebody applied this file (or
--     something like it) already; stop and find out which.
select p.oid::regprocedure as signature,
       position('department_skills' in pg_get_functiondef(p.oid)) > 0
         as reads_department_skills,
       position('complaint_categories' in pg_get_functiondef(p.oid)) > 0
         as reads_categories
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('apply_to_department', 'invite_service_provider',
                     'search_serviceable_communities');

-- (b) The signature census, so "unchanged" in the post-check has a
--     before-picture. Expect exactly three rows, pronargs 2, 6 and 3
--     respectively. More than one row for any name means an overload this
--     file does not know about, and replacing the wrong one would leave the
--     gate shut with every other check passing -- stop and report it.
select p.proname, p.oid::regprocedure as signature, p.pronargs, p.proacl
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('apply_to_department', 'invite_service_provider',
                     'search_serviceable_communities')
 order by p.proname;

-- (c) The fourth reader, for contrast -- the one that already knows. Expect
--     true. If this is false, section 14 (20260821113000) has not been
--     applied and the union shape this file copies is not on the database
--     yet; that is not a blocker for the apply, but it means the candidate
--     list and these three will still disagree afterwards, in the other
--     direction.
select position('department_skills' in pg_get_functiondef(
         'public.search_hireable_service_providers(uuid, text, integer, integer)'
         ::regprocedure)) > 0 as candidate_search_reads_department_skills;

-- (d) Informational -- the departments this actually unblocks. Rows here are
--     departments with declared skills whose categories derive none, which is
--     the reported shape. Zero rows is fine; the guard is still wrong without
--     it, and the reporter's community may be one you cannot see from here.
select d.id, d.name, d.community_id,
       count(distinct ds.skill_id) as declared_skills,
       count(distinct cc.skill_id) as category_skills
  from public.departments d
  left join public.department_skills ds on ds.department_id = d.id
  left join public.department_categories dc on dc.department_id = d.id
  left join public.complaint_categories cc
    on cc.id = dc.category_id and cc.skill_id is not null
 where d.is_active
 group by d.id, d.name, d.community_id
having count(distinct ds.skill_id) > 0 and count(distinct cc.skill_id) = 0
 order by d.name;
```

There is no data risk to check for. The file replaces three function bodies,
writes no row, and touches no table, column, policy or constraint.

**Apply:** paste the whole file into the SQL editor and run it. The editor's
destructive-operation warning will **not** fire — there is no `drop` in the
file. The only output expected is one notice: *"hiring_skill_union:
apply_to_department, invite_service_provider and search_serviceable_communities
all read department_skills."* Anything else is a failure and the whole paste
rolls back.

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260830090000', 'hiring_skill_union')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
-- (a) Re-run pre-check (a). Expect three rows with reads_department_skills
--     AND reads_categories both true -- the union, not a replacement. A row
--     with reads_categories = false would mean the category path was dropped
--     and a department that has declared nothing just stopped hiring.
select p.oid::regprocedure as signature,
       position('department_skills' in pg_get_functiondef(p.oid)) > 0
         as reads_department_skills,
       position('complaint_categories' in pg_get_functiondef(p.oid)) > 0
         as reads_categories
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('apply_to_department', 'invite_service_provider',
                     'search_serviceable_communities');

-- (b) Re-run pre-check (b). Expect the SAME three rows, same signatures, same
--     pronargs, same proacl. A fourth row is the failure this check exists
--     for: `create or replace` with a changed argument list creates a SECOND
--     function and leaves the category-only original standing for
--     app/repositories/hiring_repository.py to keep calling.
select p.proname, p.oid::regprocedure as signature, p.pronargs, p.proacl
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('apply_to_department', 'invite_service_provider',
                     'search_serviceable_communities')
 order by p.proname;
```

**Post-check, functional — this is the one that proves the ruling, and it needs
a real department.** Pick a department from pre-check (d), or make one: attach
a skill to a department whose categories derive none
(`PUT /api/v1/departments/{id}/skills`), then, signed in as a manager of it:

- **(c)** `GET /api/v1/departments/{id}/candidates` — a provider holding that
  skill appears. This worked before the apply too; it is the control.
- **(d)** `POST /api/v1/departments/{id}/invitations` for that provider —
  **201**, where before the apply it was a **409** reading *"This person does
  not have a required skill."* This is the contradiction the issue reported.
- **(e)** Signed in as that provider, `GET /api/v1/worker/communities/search` —
  the community appears with the department in its `departments` array and the
  skill in `matchingSkillNames`.
- **(f)** `POST /api/v1/worker/applications` with that `departmentId` —
  **201**, where before the apply it was a **403** reading *"Your skills do not
  match this department."*
- **(g)** The other half of the union, and the half a careless fix breaks:
  pick a department with categories that **do** derive skills and no declared
  skills at all, and repeat (c) and (e). The same candidates and the same
  community must still appear. Nobody who could be hired before this file may
  be refused after it.

**Rollback.** Re-apply the pre-image: the `apply_to_department` and
`invite_service_provider` sections of
`20260811162409_service_professional_onboarding.sql` (566-646 and 648-726,
plus their `revoke`/`grant` pairs at 864-867) and
`20260812181443_search_nearby_communities.sql` whole. Both hold the
category-only bodies verbatim — which is exactly why this file copied rather
than retyped them — and both are same-signature `create or replace`, so the
ACLs survive the rollback as they survived the apply. Follow with
`notify pgrst, 'reload schema'`. Rolling back restores the reported defect; it
does not lose data, because this file never wrote any.

**What was checked before this section was written:** the static battery in
`backend/tests/test_hiring_skill_union_migration.py` — the file exists under
the frozen name, parses as PostgreSQL, and sorts after `20260829120000` and
after all four files whose shapes it copies; it is the last declaration of
each of the three functions in the tree; it re-issues **exactly** those three
and no fourth; each signature block is compared character-for-character with
its source and each body is **diffed line by line** against that source, so
any change outside the marked skill gate fails the suite; all three bodies
contain both `department_skills` and the category path joined by `union`; none
of the three category-only join shapes survives anywhere in the file; the
union fragment is asserted to be the same text `20260821113000` uses for
`search_hireable_service_providers`, derived from that file rather than typed
in; the two refusal sentences and their `HB403`/`HB409` codes are unchanged and
no new SQLSTATE is invented; the file declares no other object, writes only the
`service_applications` row those two functions always wrote, reloads the schema
cache, and probes each installed definition by exact signature in an
in-transaction `do` block. **Not verifiable statically:** everything post-check
(c) through (g) covers — that a department whose categories derive no skill can
now actually be found, applied to and hired from, and that a department with
categories and no declared skills sees exactly what it saw before.

## 36. `20260830093000_invoice_total_amount_generated.sql`

**Filename order is apply order. This file sorts after
`20260830090000_hiring_skill_union.sql` (§35, immediately above) and after §34
`20260829120000_drop_legacy_approve_overload.sql`, so apply it there — but its
order relative to either breaks nothing.** It touches one column of
`public.invoice_line_items` and shares no table, view, function or constraint
with them. Apply in filename order regardless.

**What is wrong on hosted.** `0021_money_on_baseline.sql` declares
`public.invoice_line_items.total_amount` as

```sql
total_amount numeric(12, 2)
  generated always as (round(quantity * unit_amount, 2)) stored
```

and the hosted database carries it as a **plain `not null` column** —
`pg_attribute.attgenerated = ''` rather than `'s'`. `0021` anticipated an older
hosted shape and left `issue_invoice` a defence for it (lines 466-476: *"the
older hosted schema has a stored total rather than the baseline's generated
column; populate it only in that shape"*), but that defence is an `update` that
runs **after** the line inserts. The insert at `0021`:450-462 lists
`description, quantity, unit_amount, amount, sort_order` and does **not** list
`total_amount`, because on the declared shape it must not. So on the drifted
shape the first line insert violates the NOT NULL, the whole RPC rolls back, and
the repair statement is never reached. Every invoice create on hosted has been
failing there.

This is the second half of issue #54. The first half — `money_service.create_invoice`
building the payload with key `"lines"` where the RPC reads
`p_payload -> 'line_items'` — is a backend-only code fix in the same change and
needs no SQL. **Both are required:** with only the code fix, the RPC receives the
lines and then dies on this NOT NULL; with only this migration, the RPC still
refuses with *"An invoice needs at least one line item."*

**What it does:** one guarded, idempotent `do` block. It reads `attgenerated`
for that exact column and then:

* `'s'` (already correct) — raises a notice and **returns without acting**. Safe
  to re-run, and this is the branch every fresh replay of the migrations
  directory takes, since `0021` creates the generated column a few files
  earlier.
* `''` (drifted) — probes `pg_depend` for dependents, counts the rows the
  recomputation will change, then `drop column` + `add column … generated always
  as (round(quantity * unit_amount, 2)) stored`.
* column absent, or any other `attgenerated` — raises and stops, rather than
  guessing at a third shape nobody has seen.

Then a `comment on column`, an in-transaction read-back proving the column is
generated with the right expression, and `notify pgrst, 'reload schema'`.

**No `CASCADE`, by census and by probe.** The repository was enumerated first:
`invoice_overview` (`0021`:216) and `resident_invoice_overview` (`0033`:211)
both carry a column called `total_amount`, and in both it is
**`invoices.total_amount`** — the invoice's own total, a different table.
Neither view selects from `invoice_line_items` at all. The only index on the
table is `invoice_line_items_invoice_idx (invoice_id, sort_order)` (`0021`:151).
No materialized view, generated column or column default in
`backend/supabase/migrations/` reads it. (`issue_invoice`,
`money_repository.py` and `dashboard_repository.py` all read the column, and
none of those is a DDL dependency: a plpgsql body is not parsed until it runs
and a PostgREST select is a query. Neither blocks a `drop column`.) Because
hosted has already proved it carries objects this tree never declared, the file
does not rely on that census alone — it probes `pg_depend` for views,
materialized views, rules and indexes attached to this exact column and
**refuses the apply by name** if it finds one, rather than cascading it away.

**Pre-check, read-only — run this BEFORE the apply and read the result:**

```sql
-- (a) The shape. Expect attgenerated = '' (drifted) -- which is what this file
--     repairs. If it comes back 's', the database is already correct and the
--     apply will be a no-op notice; run it anyway to keep the ledger honest.
select a.attgenerated, a.attnotnull, format_type(a.atttypid, a.atttypmod)
  from pg_attribute a
 where a.attrelid = 'public.invoice_line_items'::regclass
   and a.attname  = 'total_amount'
   and a.attnum > 0
   and not a.attisdropped;

-- (b) THE DATA QUESTION. Re-adding the column as generated RECOMPUTES it for
--     every row as round(quantity * unit_amount, 2). These are the rows whose
--     stored value disagrees with their own inputs and will therefore CHANGE.
--     Expect zero: issue_invoice has always written exactly that expression.
--     A non-empty result is not a blocker, but read it before continuing --
--     each row is a stored total that was written by something other than the
--     RPC, and the apply overwrites it.
select li.id,
       li.invoice_id,
       i.invoice_number,
       li.description,
       li.quantity,
       li.unit_amount,
       li.total_amount                       as stored_total,
       round(li.quantity * li.unit_amount, 2) as recomputed_total,
       li.amount                             as sibling_amount
  from public.invoice_line_items li
  join public.invoices i on i.id = li.invoice_id
 where li.total_amount is distinct from round(li.quantity * li.unit_amount, 2)
 order by i.invoice_number, li.sort_order;

-- (c) The dependent census, on the live database. Expect zero rows. Any row is
--     a view, materialized view, rule or index this repository never declared;
--     the apply will REFUSE by name rather than cascade it away, and it must be
--     re-issued around the swap by hand before this file can be applied.
select distinct c.relname, c.relkind
  from pg_depend d
  join pg_rewrite r on r.oid = d.objid
  join pg_class   c on c.oid = r.ev_class
 where d.classid    = 'pg_rewrite'::regclass
   and d.refclassid = 'pg_class'::regclass
   and d.refobjid   = 'public.invoice_line_items'::regclass
   and d.refobjsubid = (select attnum from pg_attribute
                         where attrelid = 'public.invoice_line_items'::regclass
                           and attname  = 'total_amount')
   and c.oid <> 'public.invoice_line_items'::regclass
union
select c.relname, c.relkind
  from pg_depend d
  join pg_class c on c.oid = d.objid
 where d.classid    = 'pg_class'::regclass
   and d.refclassid = 'pg_class'::regclass
   and d.refobjid   = 'public.invoice_line_items'::regclass
   and d.refobjsubid = (select attnum from pg_attribute
                         where attrelid = 'public.invoice_line_items'::regclass
                           and attname  = 'total_amount')
   and c.relkind = 'i';

-- (d) Scale, so the notice the apply prints can be checked against something.
select count(*) as line_items from public.invoice_line_items;
```

**Apply:** paste the whole file into the SQL editor and run it. The editor's
destructive-operation warning **will** fire — it sees `drop column` — and it is
safe to confirm once pre-check (b) has been read: the drop is immediately
followed by the re-add in the same `do` block, the whole paste is one
transaction, so a failure anywhere rolls back everything, and the column's
values are computable from `quantity` and `unit_amount`, which are not touched.
The sibling `amount` column is not touched either.

Expected output on a drifted database, two notices:

> *"invoice_total_amount_generated: repairing the drifted plain column; N row(s)
> will be recomputed to round(quantity * unit_amount, 2)."*
> *"invoice_total_amount_generated: total_amount is generated always as
> round((quantity * unit_amount), 2) stored."*

N must match the row count pre-check (b) returned. On an already-correct
database the only notice is *"total_amount is already GENERATED ALWAYS AS
STORED; nothing to repair."*

**Ledger:**

```sql
insert into supabase_migrations.schema_migrations (version, name)
values ('20260830093000', 'invoice_total_amount_generated')
on conflict (version) do nothing;
```

**Post-check, read-only:**

```sql
-- (a) The shape, re-read. Expect attgenerated = 's'.
select a.attgenerated,
       pg_get_expr(d.adbin, d.adrelid) as generation_expression
  from pg_attribute a
  left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
 where a.attrelid = 'public.invoice_line_items'::regclass
   and a.attname  = 'total_amount'
   and a.attnum > 0
   and not a.attisdropped;

-- (b) Nothing disagrees with its own inputs any more. Expect zero rows --
--     structurally, now, rather than by convention.
select count(*) as still_drifted
  from public.invoice_line_items
 where total_amount is distinct from round(quantity * unit_amount, 2);

-- (c) The index and the policies survived the column swap. Expect
--     invoice_line_items_invoice_idx, and the read policy.
select indexname from pg_indexes
 where schemaname = 'public' and tablename = 'invoice_line_items';
select polname from pg_policy
 where polrelid = 'public.invoice_line_items'::regclass;
```

**Probe insert — the check that actually answers issue #54.** Do this from the
app, not from SQL: sign in as a community admin and create an invoice with one
line from the Maintenance screen. It must now succeed and the line's total must
read `quantity × unit amount`. That single action exercises both halves — the
payload key the backend now sends, and the generated column this file restored
— and it is the only way to see them working together. A SQL-only equivalent is
`select public.issue_invoice('<community uuid>', '{"title":"probe",
"unit_code":"<an existing flat>","line_items":[{"description":"probe",
"quantity":1,"unit_amount":1}]}'::jsonb);` run **as an admin of that community**
(the RPC's first guard is `is_community_admin`, so the SQL editor's default role
will be refused) — and if it is run, delete the probe invoice afterwards.

**Rollback.** The declared shape is the correct one, so there is nothing worth
rolling back to; the pre-repair state is the bug. Should it be needed, it is
re-declaring the plain column, which is what the file header lists:

```sql
alter table public.invoice_line_items drop column total_amount;
alter table public.invoice_line_items add column total_amount numeric(12, 2);
update public.invoice_line_items
   set total_amount = round(quantity * unit_amount, 2);
alter table public.invoice_line_items alter column total_amount set not null;
notify pgrst, 'reload schema';
```

No data is lost either way: the column's values are a function of `quantity` and
`unit_amount`, which this file never touches.

**What was checked before this section was written:** the static battery in
`backend/tests/test_invoice_total_amount_migration.py` — the file exists under
the frozen name, parses with `pglast`, sorts after `0021` and is the last
migration to declare or alter this column; the guard reads
`pg_attribute.attgenerated` for `public.invoice_line_items.total_amount` and
excludes dropped columns; the `'s'` branch returns before the drop; an
unrecognised `attgenerated` raises; the re-add carries `0021`'s expression
**derived from `0021` itself** rather than typed into the test; no `cascade` on
any drop; the `pg_depend` probe runs before the drop and refuses by name; the
sibling `amount` column is not named in any drop, add or update; the file writes
no row, alters no other table, and creates or drops no view, policy, trigger,
constraint or function; the read-back block runs after the repair; and
`notify pgrst, 'reload schema'` is present. The dependent-view census is
re-derived in that suite too — every `create view` statement in the directory is
extracted and none selects from `invoice_line_items`.
**Not verifiable statically:** that the hosted column is in fact drifted before
the apply (pre-check (a) is the only proof), that no hosted-only view or index
depends on it (pre-check (c) and the file's own `pg_depend` probe), how many
rows the recomputation changes (pre-check (b)), and that `issue_invoice` then
succeeds end to end (the probe insert above).
