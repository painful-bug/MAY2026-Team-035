# Service personnel, job dispatch and security operations

> **Status:** approved, in implementation. Written from `service documentation.md`
> (the service-person dashboard and departments specification) after twelve
> architectural questions were resolved with the product owner; those answers are
> the decisions D1–D15 below.
>
> **This file is frozen.** When reality forces a change, the deviation is
> recorded in the progress document with the fact that forced it — the plan is
> not quietly rewritten to match what happened.
>
> - What exists in the branch today, and what to do next:
>   [`SERVICE_OPERATIONS_PROGRESS.md`](SERVICE_OPERATIONS_PROGRESS.md) — **read
>   this first.**
> - Why the surface stays coherent with the admin and resident backends:
>   [`../design/SERVICE_OPERATIONS_DESIGN.md`](../design/SERVICE_OPERATIONS_DESIGN.md).

## Context

`service documentation.md` describes three things the product does not have: a **service person** who exists independently of any community and works across several of them; a **dispatch engine** that turns a triaged complaint into a scheduled visit by a specific worker; and a **security department** whose work is shifts and registers rather than complaint-driven jobs.

The feature is not greenfield. `0001_baseline.sql` already creates `vendors`, `skills`, `staff_skills`, `worker_availability_rules`, `worker_unavailability`, `work_orders` and `work_order_assignments` — seven tables with no index, no RLS policy, no RPC, no view and no Python reference. `docs/CONFLICT_RESOLUTIONS.md` **R16** parked them deliberately: *"keep all 12, tag each with `Phase 2 — no v1 endpoint, no v1 RLS policy`, and build nothing against them."* `docs/erd/homebandhu.dbml` models the richer versions, including the overlap-exclusion constraint. This plan **un-parks R16** and says so explicitly, per the `docs/design/README.md` rule that a ruling overturning something already written must name what it overturned.

One structural blocker had to be removed first. `docs/product/USER_IDENTIFICATION.md:55-65` and `API.md` §16.1 both state that a staff member has no login *by construction* — *"a staff member is a name on a roster, not an account"* — and `POST /departments/{id}/staff` deliberately leaves `membership_id` null. That is now overturned: a service person registers themselves, and a department manager hires them.

Intended outcome: a service person can register once, be found by managers whose departments need their skills, be hired into several communities, see one unified colour-coded calendar across all of them, and be dispatched to scheduled jobs automatically. Security staff are hired and scheduled by the same machinery but work posts and shifts, and gate operations (registers, tanker logs, offline verification, retention reports) close `US-3.3` through `US-3.6`.

---

## Findings that shaped the design

These are the discoveries that changed decisions, not a summary of the codebase.

**F1. RLS was already multi-community; only Python was not.** `is_community_member(uuid)` (`0019:81`) is an `exists(...)` over every active membership the caller holds. Postgres never assumed one community. The scalar assumption lives in exactly one place — `app/api/deps.py:107-118`, `order by is_default_community desc limit 1`. Making the worker view multi-community is a change to one function, not to the tenancy model.

**F2. Nothing has ever been applied to a database.** `backend/supabase/migrations/README.md:5-7`: *"None of them has been applied to any database yet — including `0001_baseline.sql`."* So there is no data to migrate. Three contradictory vocabularies (`rank`, `shift`) can simply be corrected in place rather than dual-written and backfilled — a fact that removes most of the cost from the reconciliation below.

**F3. Writing a notification already produces a realtime frame.** The trigger `notifications_sse_event` (`0030:229-266`) emits an `audience='member'` SSE row on every `notifications` insert. There is no "remember to also emit" step. The dispatch engine gets live delivery to the worker's open tab for free by calling `notify_member`.

**F4. There is no Python notification API at all.** `app/services/notifications_service.py` only reads. Every notification is written *inside the feature RPC's transaction* by `notify_member` (`0030:174`), `notify_community_roles` (`0032:268`) or `notify_community_staff` (`0031:158`). The engine must therefore do its work in SQL, not Python — which is also what makes it safe across processes.

**F5. The amenity booking system is a working precedent for every hard part of scheduling.** `amenity_bookings` already carries a GiST exclusion constraint over `tstzrange(starts_at, ends_at, '[)')` scoped to live statuses, and conflict resolution happens in a `BEFORE` trigger holding `pg_advisory_xact_lock` (`DECISIONS_NEEDED` E20). Worker double-booking is the same problem and gets the same solution, not a new one.

**F6. The live assignment path is a formatted string.** `frontend/src/pages/AdminDashboard/DepartmentDetail.jsx:184` writes ``assignee: `${staffMember.name} - ${staffMember.role}` `` and reads it back by splitting on `' - '`. `DECISIONS_NEEDED` B2 states the consequence plainly: *"We store a text label; 'complaints assigned to me' stays impossible."* That single line is the entire job list of a worker dashboard, so B2 is answered here as a precondition, not a side effect.

**F7. `complaint_events` is a general audit trail that already renders to prose.** Nine event types, `_EVENT_LABELS` and `_event_message` in `app/services/resident_complaints_service.py:55-103`, with `_is_internal_comment_event` stripping internal shadows from the resident timeline. Work-order lifecycle events belong here rather than in a parallel `work_order_events` table.

**F8. Two notification rules in `ARCHITECTURE.md` conflict with the engine as specified.** *"A status change notifies; an assignee or a progress bar does not"* — but the whole engine is assignment pings, and `US-2.7` explicitly asks for a notification when a complaint is *"reassigned"*. Resolved in D9 below.

**F9. `POST /complaints/{id}` admin writes are broken today.** `app/services/complaints_service.py:22` calls `people_repo.get_membership_id_for_profile(...)`, which does not exist anywhere in the repo — `app/repositories/people_repository.py` defines only `find_active_membership_by_email` and `set_membership_role`. `tests/api/test_complaints.py` monkeypatches the service, so nothing catches it. Separately, `AddCommentRequest.visibility` defaults to `"resident"` while the RPC and every read path use `'public'`/`'internal'`, so such a comment is stored and then never displayed. Both sit directly under the supervisor triage path and are fixed in Step 4.

---

## Decisions

Each states the decision, the reasoning, and the rejected alternative — the `docs/design/README.md` convention.

**D1. A service person is a `profile` with a global `service_providers` record, hired into communities as `community_memberships.role = 'worker'` (or `'security'`).**
The enum already carries both values (`0001:10`); nothing has ever issued them. One identity system, one guard mechanism, and `require_membership_role("worker")` is a one-line guard.
*Rejected:* a separate serviceman identity table outside `community_memberships`. It reads better against "external to the society", but it duplicates every guard, every RLS predicate and every tenancy path in the codebase for one population.

**D2. Skills belong to the person, not to the posting.** `service_provider_skills(provider_id, skill_id)`, global.
The "show me only communities that need my skills" search must run **before** the person has any membership anywhere. Keying skills to `staff_assignment_id`, as the baseline's `staff_skills` does, gives him nothing to query with until someone has already hired him — the search would be empty for exactly the people who need it.
*Consequence:* `staff_skills` becomes dead and is deleted in Step 12.

**D3. `rank` becomes `manager | supervisor | member`; the trade stays in `job_title`.**
Four vocabularies disagree today: SQL `head|member` (`0019:244`), `API.md` §8 `member|supervisor|head`, the ERD's `staff_rank {manager|supervisor|worker}`, and three different frontend lists. This picks the ERD's, which is also what you specified. Whether a `member` is a technician or a guard is already answered by `departments.kind ∈ {service, security}` — no new column. `API.md` §8's printed rule that *"`rank` and `role` are separate fields on purpose"* is preserved.
*Rejected:* `rank in ('manager','supervisor','technician','security')`. It duplicates `departments.kind` and breaks a rule the docs commit to in print.

**D4. `shift` becomes `Day | Evening | Night | Full Day | Rotating`.** The union of what the code validates and the two frontend screens offer, minus `Morning`, which only the SQL check ever mentioned and which nothing writes. Per **F2** there is no data, so this is a constraint edit, not a migration.

**D5. Work lives in `work_orders`; a complaint may have many.**
Your document requires it: a failed visit is rescheduled, and a reopened complaint goes to a *different* supervisor. Both are second work orders against one complaint. Extending the dead baseline tables additively — exactly as `0019` extended `departments` and `staff_assignments` — is a smaller ERD change than designing fresh, and the chain `work_order → work_order_assignment → staff_assignment → service_provider → skills` is already drawn in `docs/erd/homebandhu.dbml:596-662`.
*Rejected:* assignment columns on `complaints`. Smallest change and it would fix B2, but one complaint could then only ever have one scheduled visit.

**D6. Every work order has a complaint, so `complaint_events` is the audit trail.**
Departments raising work suo motto raise a *complaint* first (your document says so), so `work_orders.complaint_id` is always populated by our RPCs. New event types `job_scheduled`, `job_offered`, `job_accepted`, `job_declined`, `job_started`, `job_failed`, `job_completed` extend the existing nine and render through the existing `_event_message`.
*Rejected:* a parallel `work_order_events` table. It would need its own view, its own renderer and its own RLS, and would split one complaint's story across two timelines.

**D7. PostGIS, with lat/lng as the source of truth and `geography` generated.**
`latitude`/`longitude` are `numeric(9,6)` columns; `location` is `generated always as (extensions.ST_SetSRID(extensions.ST_MakePoint(longitude, latitude), 4326)::geography) stored`, GiST-indexed. If PostGIS turns out to be unavailable on the project, dropping the generated column and one index is the whole fallback — the data and every API shape are unchanged, and distance falls back to the SQL haversine included in Step 1.
*Verify before Step 1 runs* (Supabase SQL editor):
```sql
select name, default_version, installed_version from pg_available_extensions where name in ('postgis','btree_gist','pg_cron','pg_trgm') order by name;
```
`btree_gist` is needed independently — `0023` already requires it, and so does the no-double-booking constraint.

**D8. Timers run in an in-process asyncio dispatcher, claimed atomically in Postgres.**
`app/core/dispatcher.py` mirrors `app/core/push.py` exactly: `claim → act → sleep`, started from the lifespan, never raising, with DB work in `asyncio.to_thread` because supabase-py is sync. Due times live in a `dispatch_tasks` table, so a restart loses nothing, and `claim_dispatch_batch` uses `for update skip locked` so two processes cannot double-fire. `app/core/push.py:5-18` states the governing rule: *"The hub may drop. The sender may not duplicate."*
*Rejected:* `pg_cron`. `0024:118-134` already uses it — but only inside a `DO` block that no-ops when the extension is absent, precisely because nobody knows whether it is available. Betting a log pruner on that is reasonable; betting the core engine on it is not.

**D9. A dispatch offer notifies; a bare assignee change still does not.** This resolves **F8** rather than ignoring it. The rule in `ARCHITECTURE.md` exists to stop progress bars buzzing phones. A dispatch ping is not a passive field change — it is an offer that expires and requires an action, and `US-2.7` names reassignment explicitly. So: offers, acceptances, schedule changes, failed visits and completions notify; `progress_percent` and a supervisor editing an internal note still do not. Recorded in `ARCHITECTURE.md` as an amendment with its reason.

**D10. Service-provider blacklisting gets its own table.**
`blacklisted_residents` is keyed on `(community_id, profile_id)` and is enforced inside `search_joinable_communities`, so reusing it would also bar the person from *living* there. A plumber barred from working in a community has not been barred from renting a flat in it.
*Rejected:* reuse with a `scope` column — same table, two unrelated lifecycles, and the existing RPC `blacklist_access_request` would have to learn a concept it does not need.

**D11. Security staff share the hiring, availability and scheduling machinery; their *work* is a different entity.**
A guard's shift is a post occupied for a window, not a job dispatched to an address, so `security_shifts` is separate from `work_orders`. But hiring, skills, availability, the offline toggle, blacklisting, messaging and the calendar are identical and are reused verbatim. Gate operations — material registers, tanker logs, incidents, offline verification, retention exports — are built, closing `US-3.3`–`US-3.6`.

**D12. Two register tables, not one typed table.** `material_movements` and `water_tanker_logs` share almost no columns (`is_returnable`/`expected_return_at`/`returned_at` versus `tanker_number`/`volume_litres`/`supplier`), are named by two separate user stories, and produce two separate reports. `security_incidents` covers *"other operational activities"*.
*Rejected:* one `gate_register_entries` table with a `kind` and a `details jsonb`. It would make both halves null-heavy and push validation out of the schema and into Python.

**D13. Offline verification is a signed, time-boxed bundle plus a reconcile endpoint.** `GET /security/offline-bundle` returns the currently-valid pass hashes for the next N hours with an expiry and a signature; the device verifies locally against it; `POST /security/offline-reconcile` accepts the queued entries recorded while disconnected, idempotently by client-generated id. This is what gate systems actually do, and it needs no new verification algorithm — it reuses the existing `pass_hash`.

**D14. `MembershipSet` is added; `get_active_membership` becomes a derivation of it.** Additive at the seam, so every existing router, guard, test and signature keeps its current behaviour, and the number of DB reads per request stays at one. Flagged for the auth owner's review before merge.

**D15. Community colour is derived, never stored.** A stable hash of the community UUID indexes a fixed palette, so the same community is the same colour on every device with no column, no migration and no admin setting.

---

## Data model

Six migrations, `0034`–`0039`. House conventions throughout (`backend/supabase/migrations/README.md`, and the shape of `0029`/`0030`): long prose header naming the one non-obvious decision, numbered `-- ---` sections, `if not exists` everywhere, `drop policy/trigger/view if exists` first, constraints inside `do $$` guarded on `pg_constraint` *pinned by `conrelid`*, `text` + named `_check` constraints rather than new enums, views `with (security_invoker = true)` plus a `comment on view`, `security definer set search_path = public` on every privileged function, `grant ... to authenticated` and never to `anon`.

### `0034_service_providers.sql` — who a service person is, and how they find work

```sql
create extension if not exists postgis with schema extensions;

create table if not exists public.service_providers (
  id                uuid primary key default gen_random_uuid(),
  profile_id        uuid not null unique references public.profiles(id) on delete cascade,
  display_name      text not null,
  headline          text,
  bio               text,
  phone_e164        varchar(20),
  latitude          numeric(9,6),
  longitude         numeric(9,6),
  location          extensions.geography(Point,4326)
                      generated always as (
                        case when latitude is null or longitude is null then null
                        else extensions.ST_SetSRID(
                               extensions.ST_MakePoint(longitude, latitude), 4326)::extensions.geography
                        end) stored,
  service_radius_km numeric(6,2) not null default 15,
  status            text not null default 'active',
  is_available      boolean not null default true,   -- the dashboard offline toggle
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create index if not exists service_providers_location_gix on public.service_providers using gist (location);

create table if not exists public.service_provider_skills (
  service_provider_id uuid not null references public.service_providers(id) on delete cascade,
  skill_id            uuid not null references public.skills(id) on delete restrict,
  proficiency_level   smallint,
  primary key (service_provider_id, skill_id)
);

create table if not exists public.skill_categories (
  skill_id             uuid not null references public.skills(id) on delete cascade,
  complaint_category_id uuid not null references public.complaint_categories(id) on delete cascade,
  primary key (skill_id, complaint_category_id)
);
```

Also here: `latitude`/`longitude`/`location` on `communities` (same generated pattern, same GiST index); `skills.is_active`; the `service_provider_overview` view; and the two search RPCs.

`search_serviceable_communities(p_limit, p_offset)` is the one the dashboard's "find community" field calls. It answers your document's rule — *have his skills within a department, have not blacklisted him, ascending by distance* — as one query:

```sql
select c.id, c.name, c.city,
       extensions.ST_Distance(c.location, sp.location) / 1000.0 as distance_km,
       array_agg(distinct d.name) as matching_departments
  from public.communities c
  join public.departments d          on d.community_id = c.id and d.is_active
  join public.department_categories dc on dc.department_id = d.id
  join public.skill_categories sc    on sc.complaint_category_id = dc.complaint_category_id
  join public.service_provider_skills sps on sps.skill_id = sc.skill_id
       and sps.service_provider_id = sp.id
 where c.status = 'active'
   and not exists (select 1 from public.blacklisted_service_providers b
                    where b.community_id = c.id and b.service_provider_id = sp.id
                      and b.revoked_at is null)
   and not exists (select 1 from public.community_memberships m
                    where m.community_id = c.id and m.profile_id = auth.uid()
                      and m.status = 'active' and m.ended_at is null)
 group by c.id, c.name, c.city, distance_km
 order by distance_km nulls last, c.name;
```

Note there is **no `department_skills` table**. A department declares categories; a skill maps to categories; therefore the department-needs-this-skill relation is derivable, as the join above shows. One table not written.

A `haversine_km(lat1, lon1, lat2, lon2)` immutable SQL function ships alongside it as the documented PostGIS fallback (D7).

### `0035_department_roles_and_hiring.sql` — three roles, and how someone is hired

- Relaxes `staff_assignments_rank_check` to `('manager','supervisor','member')` and renames the partial unique index to `staff_assignments_one_active_manager on (department_id) where rank = 'manager' and status = 'active'`.
- Corrects `staff_assignments_shift_check` to D4's vocabulary.
- `alter table public.staff_assignments add column if not exists service_provider_id uuid references public.service_providers(id) on delete set null;`
- `blacklisted_service_providers` — mirrors `blacklisted_residents` exactly, including the reversible `revoked_at`/`revoked_by_membership_id` pair and the partial unique index on active rows.
- `service_applications(id, community_id, department_id, service_provider_id, direction, status, message, decided_by_membership_id, decided_at, ...)` with `direction in ('applied','invited')`, `status in ('pending','accepted','rejected','withdrawn','expired')`, and `service_applications_one_open` unique on `(department_id, service_provider_id) where status = 'pending'`.
- Views `service_application_overview`, `hireable_service_provider` (the manager's search: skill-matched to *this* department's categories, not blacklisted, not already on the roster, distance-ordered).
- RPC `decide_service_application(p_application_id, p_decision, p_rank, p_job_title, p_shift)` — the important one. Accepting is three writes in one transaction: insert `community_memberships` with `role = case d.kind when 'security' then 'security' else 'worker' end`, insert `staff_assignments` linking `service_provider_id` **and** the new `membership_id`, update the application. Raises `42501` if the caller is not a manager of that department, `23514` if the provider is blacklisted, `P0002` if the application is gone.
- RPC `remove_department_member` (deactivates, ends the membership — reapplication allowed) and `blacklist_service_provider` (removes and bars permanently), matching your document's remove-versus-blacklist distinction.

### `0036_work_orders.sql` — the job

Extends the two dead baseline tables:

```sql
alter table public.work_orders
  add column if not exists department_id           uuid references public.departments(id) on delete set null,
  add column if not exists supervisor_membership_id uuid references public.community_memberships(id) on delete set null,
  add column if not exists skill_id                uuid references public.skills(id) on delete set null,
  add column if not exists scheduled_start_at      timestamptz,
  add column if not exists scheduled_end_at        timestamptz,
  add column if not exists subject_kind            text not null default 'resident',
  add column if not exists location_text           text,
  add column if not exists latitude                numeric(9,6),
  add column if not exists longitude               numeric(9,6),
  add column if not exists failed_attempt_count    smallint not null default 0,
  add column if not exists resident_deadline_at    timestamptz;
-- work_orders_status_check: draft|awaiting_resident|offered|scheduled|in_progress|completed|failed|cancelled
-- work_orders_subject_kind_check: resident|facility
```

```sql
alter table public.work_order_assignments
  add column if not exists status         text not null default 'offered',
  add column if not exists offered_at     timestamptz not null default now(),
  add column if not exists responded_at   timestamptz,
  add column if not exists decline_reason text,
  add column if not exists is_auto_assigned boolean not null default false,
  add column if not exists scheduled_start_at timestamptz,
  add column if not exists scheduled_end_at   timestamptz;

do $$
begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.work_order_assignments'::regclass
                    and conname  = 'work_order_assignments_no_overlap') then
    alter table public.work_order_assignments
      add constraint work_order_assignments_no_overlap
      exclude using gist (
        staff_assignment_id with =,
        tstzrange(scheduled_start_at, scheduled_end_at, '[)') with &&
      ) where (status = 'accepted' and scheduled_start_at is not null);
  end if;
end $$;
```

That constraint is the one already written down in `docs/erd/homebandhu.dbml:614`; this is where it starts existing. It requires `btree_gist`, which `0023` already requires.

`worker_availability_rules` and `worker_unavailability` are activated by adding a nullable `service_provider_id` beside the existing `staff_assignment_id`, plus a check that exactly one is set — so a self-registered provider's leave is global across every community he serves, while a roster name with no account can still have per-department hours. The dashboard's "mark slots unavailable" writes `worker_unavailability` rows keyed to the provider.

RLS: `work_orders_read` = `is_community_admin(community_id) or is_community_member(community_id) and (the caller's staff_assignment holds an assignment)`; every write is a `SECURITY DEFINER` RPC, matching the posture of `0031` where **no insert/update/delete policy exists anywhere**.

### `0037_dispatch_engine.sql` — the timers and the sweep

```sql
create table if not exists public.dispatch_tasks (
  id            uuid primary key default gen_random_uuid(),
  work_order_id uuid not null references public.work_orders(id) on delete cascade,
  kind          text not null,
  due_at        timestamptz not null,
  attempts      smallint not null default 0,
  claimed_at    timestamptz,
  completed_at  timestamptz,
  last_error    text,
  created_at    timestamptz not null default now()
);
-- dispatch_tasks_kind_check: ping|auto_assign|resident_timeout|failed_visit_escalation
create index if not exists dispatch_tasks_due_idx
  on public.dispatch_tasks (due_at) where completed_at is null;
```

`claim_dispatch_batch(p_limit int)` is `claim_push_batch` with the nouns changed — `for update skip locked`, marking claimed before returning, so the loser of a race gets an empty set rather than a duplicate.

`dispatch_candidates(p_work_order_id)` is the sweep your document specifies, with the one simplification worth naming: **"within 1 km of the adjacent job" becomes "the adjacent job is in the same community"**, because inside one apartment complex every job is a two-minute walk and no job-level coordinates exist to measure against. Cross-community proximity is still real and still used — it orders the community search and bounds `service_radius_km`. The candidate filter is:

1. active `worker`/`security` membership in the work order's community, on the right department;
2. `service_providers.is_available` and `status = 'active'`;
3. no `worker_unavailability` row covering the slot, and the slot falls inside a `worker_availability_rules` window if any exist;
4. no `accepted` assignment overlapping the slot (the exclusion constraint enforces this on write; the sweep checks it to avoid offering a job that cannot be accepted);
5. the provider holds a skill mapped to the complaint's category;
6. ordered by *adjacent job in the same community* first, then fewest open assignments, then nearest.

Three RPCs the dispatcher calls, all `SECURITY DEFINER`, all writing their notification inside the same transaction (**F4**): `dispatch_ping_candidates`, `dispatch_auto_assign` (bypasses the offer and writes an `accepted` assignment directly, which is also the urgent-complaint path), `dispatch_resident_timeout`.

The **urgent** path from your document is not a fourth mechanism: `raise_complaint` with `priority = 'high'` enqueues an `auto_assign` task with `due_at = now()` instead of an `offered` work order, so the first dispatcher tick assigns it.

Every task-enqueueing RPC writes into `dispatch_tasks` rather than scheduling anything itself, so the engine's entire behaviour is inspectable with one `select`.

### `0038_conversations.sql` — the hiring conversation

```sql
create table if not exists public.conversations (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.communities(id) on delete cascade,
  department_id       uuid not null references public.departments(id) on delete cascade,
  service_provider_id uuid not null references public.service_providers(id) on delete cascade,
  created_at          timestamptz not null default now(),
  last_message_at     timestamptz,
  unique (department_id, service_provider_id)
);

create table if not exists public.conversation_messages (
  id                  uuid primary key default gen_random_uuid(),
  conversation_id     uuid not null references public.conversations(id) on delete cascade,
  author_membership_id uuid references public.community_memberships(id) on delete set null,
  author_provider_id   uuid references public.service_providers(id) on delete set null,
  body                text not null check (length(btrim(body)) between 1 and 4000),
  created_at          timestamptz not null default now()
);
```

One thread per `(department, provider)`, so there is no thread-creation step and no duplicate threads — the unique constraint is the whole concurrency story. **No `conversation_participants` table**: participation is derivable (the department's managers and supervisors, plus that provider), which is exactly what the RLS policy computes. The supervisor ↔ complainant conversation from your document reuses `complaint_comments` unchanged, per your answer.

Read receipts are deliberately absent — nothing in the document or the stories asks for them, and adding an unread count later is one lateral join against `created_at`.

### `0039_security_operations.sql` — posts, shifts, registers, offline

- `security_posts(id, community_id, department_id, name, location_text, latitude, longitude, is_active)`.
- `security_shifts(id, community_id, department_id, post_id, staff_assignment_id, starts_at, ends_at, status)` with the same GiST exclusion constraint pattern as `work_order_assignments`, so one guard cannot hold two posts at once.
- `material_movements(id, community_id, direction in ('inward','outward'), description, quantity, unit, is_returnable, expected_return_at, returned_at, carrier_name, vehicle_number, unit_id, recorded_by_membership_id, recorded_at, source_client_id)`.
- `water_tanker_logs(id, community_id, supplier_name, tanker_number, volume_litres, driver_name, driver_phone_e164, arrived_at, departed_at, recorded_by_membership_id, source_client_id)`.
- `security_incidents(id, community_id, category, severity, summary, details, occurred_at, reported_by_membership_id, status)`.
- `offline_reconcile_log(source_client_id unique, ...)` — the idempotency key that makes `POST /security/offline-reconcile` safe to retry. Every register table carries a nullable `source_client_id` for the same reason.

RLS on all five: `is_community_security(community_id) or is_community_admin(community_id)`, reusing the predicate `0032:232` already created.

---

## Backend

### The tenancy seam — `backend/app/api/deps.py`

The only edit to existing shared code, and it is additive (D14). One query, all rows, and `get_active_membership` keeps its exact signature and behaviour:

```python
@dataclass(frozen=True)
class MembershipSet:
    """Every active membership the caller holds, across all their communities."""
    memberships: tuple[MembershipContext, ...]

    @property
    def default(self) -> MembershipContext:
        return self.memberships[0]

    @property
    def community_ids(self) -> tuple[str, ...]:
        return tuple(m.community_id for m in self.memberships)

    def require(self, community_id: str, *roles: str) -> MembershipContext:
        """The membership for one community, or 403. Never trusts a request body."""
        allowed = {r.lower() for r in roles}
        for m in self.memberships:
            if m.community_id == community_id and (not allowed or m.role in allowed):
                return m
        raise AuthorizationError(
            "You do not have permission in this community.",
            code="community_role_required",
        )


def get_membership_set(principal: Principal = Depends(get_current_user)) -> MembershipSet:
    rows = (
        get_service_client().table("community_memberships")
        .select("id, community_id, role, department_id")
        .eq("profile_id", principal.user_id).eq("status", "active").is_("ended_at", None)
        .order("is_default_community", desc=True).order("created_at")
        .execute().data or []
    )
    if not rows:
        raise AuthorizationError(
            "An active community membership is required.", code="active_membership_required")
    return MembershipSet(tuple(
        MembershipContext(id=r["id"], community_id=r["community_id"],
                          role=str(r["role"]).lower(), department_id=r.get("department_id"))
        for r in rows))


def get_active_membership(
    memberships: MembershipSet = Depends(get_membership_set),
) -> MembershipContext:
    """Resolve tenancy from Postgres, never from an identity JWT claim."""
    return memberships.default
```

`require_membership_role` is untouched. Two new guards live in a new `backend/app/api/worker_deps.py`: `require_worker` (any `worker`/`security` membership exists) and `get_service_provider` (the caller's `service_providers` row, 404 if they have not registered). A provider who has registered but been hired nowhere has **no membership at all**, so `get_membership_set`'s 403 would lock them out of the very screens that let them apply — `require_service_provider` therefore depends on `get_current_user` alone, not on membership.

### New routers, services, repositories, schemas

Each follows the house triple: router does HTTP only and declares guards at router level; service translates vocabulary and raises `AppError`; repository reads a view and writes through an RPC. Roughly **46 operations**.

| Router (`backend/app/api/v1/routers/`) | Operations | Guard |
|---|---|---|
| `service_providers.py` | `POST /service-providers` · `GET`/`PATCH /service-providers/me` · `PUT /service-providers/me/skills` · `PATCH /service-providers/me/availability` · `GET /skills` | authenticated; provider-self |
| `worker_communities.py` | `GET /worker/communities` · `GET /worker/communities/search` · `GET`/`POST`/`DELETE /worker/applications` | provider-self |
| `worker_jobs.py` | `GET /worker/snapshot` · `GET /worker/jobs` · `GET /worker/jobs/{workOrderId}` · `POST .../accept` · `/decline` · `/start` · `/complete` · `/unable` | `worker`\|`security` |
| `worker_schedule.py` | `GET /worker/calendar` · `GET`/`POST`/`DELETE /worker/unavailability` · `PUT /worker/availability-rules` | provider-self |
| `department_hiring.py` | `GET /departments/{id}/applications` · `POST /departments/{id}/applications/{applicationId}/decide` · `GET /departments/{id}/candidates` · `POST /departments/{id}/invitations` · `DELETE /departments/{id}/members/{staffId}` · `POST /departments/{id}/blacklist` | `admin`\|`manager` |
| `conversations.py` | `GET /conversations` · `GET /conversations/{id}` · `POST /conversations/{id}/messages` | participant |
| `work_orders.py` | `POST /complaints/{id}/work-orders` · `GET`/`PATCH /work-orders/{id}` · `POST /work-orders/{id}/assign` · `/reschedule` · `/cancel` · `GET /departments/{id}/work-orders` | `admin`\|`manager`\|supervisor |
| `resident_scheduling.py` | `GET /complaints/{id}/schedule-request` · `POST /complaints/{id}/schedule` | `resident` |
| `security_operations.py` | posts · shifts · `material-movements` · `water-tankers` · `incidents` · `offline-bundle` · `offline-reconcile` · `exports` | `security`\|`admin`\|`manager` |

`GET /worker/snapshot` is the dashboard's single call, following the precedent of `GET /resident/snapshot`: today's jobs, the next job, unread offers, availability state, community list with colours, unread message count. One request, one screen.

**Supervisor triage** — your document's fork between "just chat" and "assign a work schedule" — is `POST /complaints/{id}/work-orders`. Omitting a schedule leaves the complaint in conversation via `complaint_comments`; supplying one creates a work order in `awaiting_resident` and enqueues a `resident_timeout` task 24 h out. The resident's slot choice (`POST /complaints/{id}/schedule`) moves it to `offered` and enqueues the `ping` and `auto_assign` tasks. `POST /work-orders/{id}/assign` is the supervisor override, and `PATCH` with new times is the post-assignment reschedule your document grants the supervisor and withholds from the resident.

### The engine — `backend/app/core/dispatcher.py`

```python
class Dispatcher:
    """Fire due dispatch tasks: ping, auto-assign, time out, escalate."""

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="job-dispatcher")

    async def _run(self) -> None:
        """Claim and fire forever. Never raises: a transient database failure
        must not silently stop every dispatch in the process."""
        while True:
            try:
                for row in await asyncio.to_thread(self._claim):
                    await asyncio.to_thread(self._fire, row)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - loop must survive anything
                logger.exception("Dispatch batch failed; retrying")
            await asyncio.sleep(self._poll_interval)
```

`POLL_INTERVAL_SECONDS = 15.0` — the tightest deadline in the document is a 30-minute repeat, so a quarter-minute of latency is invisible and the query is trivially indexed. `_fire` calls one RPC per task kind and lets Postgres own the decision; Python owns only *when*.

`backend/app/main.py` gains three lines in `_lifespan`, beside `sender`:

```python
    await sender.start()
    await dispatcher.start()
    yield
    await dispatcher.stop()
    await sender.stop()
    await hub.stop()
```

### Realtime

Two new SSE topics, both `audience = 'role'` with `audience_roles = {worker, security}`: `worker.job_offered` and `worker.schedule_changed`. `app/core/realtime.py` needs **no change** — `_Subscriber.accepts` already matches on any role string (`realtime.py:141-146`), and the resync path already emits the role-neutral `stream.resync` for non-admin roles, which `ARCHITECTURE.md` describes as *"the same instruction, under a name that does not claim to be about the admin dashboard."* That precedent was written for exactly this case.

Per-worker delivery needs nothing new at all: `notify_member` already emits an `audience='member'` frame via trigger (**F3**).

---

## Frontend

Scoped exception granted for this work; recorded in `ADMIN_DASHBOARD_DESIGN.md` §9 beside the existing `PendingRegistrations.jsx` exception.

**`frontend/src/features/calendar/`** — generalised from the amenity timeline rather than written fresh, per your answer. `BookingTimeline.jsx`, `TimelineSlot.jsx` and `utils/amenityTimeline.js` already do slot geometry; `Settings/AvailabilitySettingsCard.jsx` + `DaySelector.jsx` + `TimeField.jsx` already do weekday-plus-window editing, which *is* the availability editor. New: `CalendarMonth.jsx`, `CalendarWeek.jsx`, `CalendarEvent.jsx`, `useCalendarRange.js`, all on `lib/dates.js` and `Intl.DateTimeFormat`. No new dependency.

**`frontend/src/lib/communityColor.js`** — D15, the whole file:

```js
const PALETTE = ['sky', 'emerald', 'amber', 'violet', 'rose', 'teal', 'indigo', 'orange'];

/** Stable per-community colour. Derived from the id so every device agrees. */
export function communityColor(communityId) {
  let hash = 0;
  for (let i = 0; i < communityId.length; i += 1) hash = (hash * 31 + communityId.charCodeAt(i)) | 0;
  return PALETTE[Math.abs(hash) % PALETTE.length];
}
```

**New pages** — `WorkerLayout.jsx` (modelled on `SecurityLayout.jsx`, which already branches by role and already says "End Shift & Logout"), then `WorkerDashboard/` with `Calendar.jsx`, `TodaySchedule.jsx`, `JobDetailModal.jsx`, `Availability.jsx`, `FindCommunities.jsx`, `MyCommunities.jsx`, `Applications.jsx`, `Messages.jsx`, `Profile.jsx`. Route `/worker`, role `Worker`, added to `routes/authRoutes.js` and `getDashboardRouteForRole`.

**Manager side** — `AdminDashboard/DepartmentHiring.jsx` (candidate search, applications inbox, invitations, roster with remove-versus-blacklist) and `Messages.jsx`. `DepartmentDetail.jsx:184`'s `assignTechnician` stops writing a formatted string and starts posting a work order against a staff id, which is where **F6**/B2 is actually closed.

**Reconciliation** — `STAFF_ROLES` in `Departments.jsx:33`, `CreateDepartment.jsx:6` and `SecurityManagerDashboard.jsx:22` are three different lists for one concept. They collapse to one exported constant, with `rank` and `job_title` as separate controls per D3.

**Store** — `createServiceProvidersSlice.js`, `createWorkOrdersSlice.js`, `createConversationsSlice.js` alongside the existing eleven.

**Empty state** — your document's point 6: a worker in no community sees the join prompt rather than an empty calendar, driven by `GET /worker/snapshot` returning an empty `communities` array.

---

## Build order

Each step is independently shippable and updates its own docs, following `RESIDENT_BACKEND_DESIGN.md` §9's rule: *"Done means merged, tested and documented — not written."*

| # | Step | Closes | Verify |
|---|---|---|---|
| 0 | Install the `ponytail` skill; confirm PostGIS/`btree_gist` availability (D7) | — | `pg_available_extensions` query returns both |
| 1 | `0034` + `MembershipSet` seam + `service_providers` router/service/repo/schemas | provider registration | suite green, seam behaviour unchanged |
| 2 | `0035` + `department_hiring.py` + `worker_communities.py` | apply, invite, hire, remove, blacklist | hire creates membership **and** staff row atomically |
| 3 | `0038` + `conversations.py` | manager ↔ provider chat | RLS denies a non-participant |
| 4 | `0036` + `work_orders.py` + `resident_scheduling.py`; **fix F9's two live defects** | B2 answered; supervisor triage | overlap constraint rejects a double-booking |
| 5 | `0037` + `app/core/dispatcher.py` + lifespan wiring | ping, auto-assign, timeout, escalation | two dispatchers claim disjoint sets |
| 6 | `worker_jobs.py` + `worker_schedule.py` + `GET /worker/snapshot` | the dashboard's API contract | one call fills the screen |
| 7 | `0039` + `security_operations.py` + CSV export | US-3.3, US-3.4, US-3.5, US-3.6, §16.7 item 8 | reconcile is idempotent on replay |
| 8 | Frontend: calendar primitive, `WorkerLayout`, worker pages | the dashboard | manual walkthrough |
| 9 | Frontend: manager hiring, messages, vocabulary reconciliation | F6/B2 end to end | `assignTechnician` no longer writes a string |
| 10 | Docs sweep (below) | — | `api_map_scan.py --strict` clean |
| 11 | Full verification (below) | — | all green |
| 12 | Dead-code sweep and deletion | — | `fallow` + grep |

---

## Documentation

Non-optional here — the export build *fails* without step 2 of this list, in both directions.

- **`backend/scripts/api_annotations.py`** — an `OPERATIONS` entry per new operation with `errors=[...]` and either `stories=[...]` or `no_story=...`; new `STORIES` rows for `US-3.3`–`US-3.6` as their verdicts change. `_check_coverage` raises `SystemExit` if an operation is missing or an entry has no live route.
- **`docs/openapi.yaml`** — regenerated by `python scripts/export_openapi.py`, never hand-edited.
- **`docs/API.md`** — a new §18 for service personnel and dispatch, a new §19 for security operations, extensions to §7 (complaints) and §8 (departments), and §16 verdict updates. Each endpoint in the house shape: `### ` + backticked method and path, one-line purpose + **`Requires ROLE.`**, request/response JSON, bolded-claim prose paragraphs, closing `| Status | Code | Cause |` table.
- **`docs/product/USER_STORIES.md`** — `**Backend:**` lines for US-2.7, US-2.8, US-2.9, US-3.1–3.6. Also fix US-3.2's stale *"see §14"*, which should point at §16.5.
- **`docs/api_yaml_mapper.md`** — a §7 rescan row and per-operation index entries.
- **`docs/design/SERVICE_OPERATIONS_DESIGN.md`** — the third design document `design/README.md` anticipates (*"a third would be justified by, say, the gate/security surface if it ever gets an owner"*). Six-part shape, rejected alternatives included.
- **`docs/CHANGE_LOG.md`** — one entry per step, `PO`/`DERIVED`/`AUDIT` attributed.
- **`docs/CONFLICT_RESOLUTIONS.md`** — R16 amended: which tables are un-parked and why.
- **`docs/diagrams/homebandhu_submission_erd.dbml`** — the only ERD that tracks the migrations. New tables added with `note:` provenance tags, and the **pre-existing** gap fixed while we are in there: its `departments` and `staff_assignments` blocks are still baseline-only, missing every `0019` column. Re-render on dbdiagram.io.
- **`docs/class-diagram/homebandhu-domain.puml`** — `ServiceProvider`, `WorkOrder`, `SecurityShift` and friends; re-render per the README's local-`plantuml.jar`-plus-Graphviz procedure, since the online renderers 400 on these files.
- **`docs/design-of-components.md`** — §3 and §6 extended, or a new §11. Its own convention requires this to be logged.
- **`docs/DECISIONS_NEEDED.md`** — **B2 answered** (F6), A12 revisited (removal now deactivates a real linked row, not an unattributable string), A22 partially answered (a scheduler now exists and D8 says what runs it).
- **`docs/ARCHITECTURE.md`** — the D9 notification amendment, the two new topics, and the dispatcher in the component diagram.

---

## Verification

```bash
cd backend && python -m pytest -q && ruff check . && python scripts/export_openapi.py --check && python scripts/api_map_scan.py --strict
```

Current baseline is **694 passing**. New tests follow the house conventions exactly — `tests/api/` uses `TestClient` with `dependency_overrides` for identity, the Supabase client as a bare `object()` sentinel that must never be called, the service monkeypatched on the *router module's* imported reference, and the `endpoint / input_data / expected_output / actual_output` naming with `api_NNN` case ids.

- `tests/api/test_service_providers.py`, `test_worker_jobs.py`, `test_worker_communities.py`, `test_department_hiring.py`, `test_conversations.py`, `test_work_orders.py`, `test_security_operations.py`.
- `tests/test_dispatcher.py` — modelled on `tests/test_push_sender.py` (16 tests): claim-and-fire, a failing RPC does not kill the loop, cancellation is clean, two dispatchers claim disjoint sets.
- `tests/test_membership_set.py` — the seam. Explicitly asserts `get_active_membership` returns what it returned before for a single-membership caller, and that `MembershipSet.require` refuses a community the caller is not in.
- `tests/test_dispatch_rules.py` — the candidate sweep as a pure function over fixtures: unavailable excluded, overlapping excluded, skill mismatch excluded, ordering correct.
- `tests/test_openapi_spec.py` — extend `test_every_router_is_mounted` with one representative path per new router.
- `pglast` static validation of all six migrations, as steps 33–38 did.

**Manual end-to-end**, once migrations are applied to a real project (still `DECISIONS_NEEDED` F1, and still yours to run — I will not touch Supabase credentials): register a provider with a skill · search communities and confirm distance ordering · apply · manager sees and accepts · membership and staff row both appear · resident raises a complaint in that category · supervisor requests a schedule · resident picks a slot · confirm the ping arrives on the worker's dashboard and as Web Push · let the auto-assign timer fire · accept, start, complete · confirm the resident timeline shows the whole story.

---

## Dead code

Run at the end, per your instruction and ponytail's *deletion over addition*.

- **`fallow`** covers `frontend/` only — its SKILL.md excludes non-JavaScript projects. Use `mcp__fallow__analyze` and `mcp__fallow__get_cleanup_candidates` across `frontend/src`, then `mcp__fallow__audit` on the changed set for a verdict.
- **Python and SQL get grep and the existing scripts**, since fallow cannot see them. Expected removals: `staff_skills` (superseded by D2), `vendors` (superseded by `service_providers`; confirm nothing references it), the stale RBAC block in `backend/app/domain/roles.py` — `Role`, `_IMPLIED_ROLES`, `effective_roles`, `role_satisfies`, `satisfies_any`, `parse_role` and `tests/test_roles.py`, keeping only `display_role`. That is `docs/potential issues/` item 2, whose own text says *"Every clause of that is now false"* and which it flags as **"the file someone will open when adding a `worker` role"** — which is precisely what this plan does.
- Anything deleted gets a `CHANGE_LOG.md` line saying what replaced it.

---

## Risks and open questions, with defaults

1. **PostGIS may be unavailable.** Default: the haversine fallback in D7. Confirmed at step 0, before anything depends on it.
2. **`app/api/deps.py` belongs to the parallel auth workstream.** Default: the additive shape in D14, flagged for their review before merge. If they have a conflicting change in flight, `worker_deps.py` can carry its own resolver at the cost of one extra read per worker request.
3. **Auto-resolving a complaint after 24 h of resident silence** is your document's rule and is implemented as written — but it closes a complaint the resident never saw, and `US-2.8` is a story about accountability. Default: implement it, and notify the resident at both the 24 h mark and on auto-resolution so the silence is at least audible. Worth a product decision.
4. **No migration has ever been applied anywhere** (`DECISIONS_NEEDED` E1/F1, `potential issues` #4). This plan adds six more to a stack of twenty-three that have never run. Every predicate here is unexecuted until you apply them.
5. **Scale.** The dispatcher is in-process; two app processes are safe (the claim is atomic) but every process polls. At current scale this is free and matches `PushSender`; the ceiling is worth a comment in the file rather than a solution now.
6. **US-3.5 offline verification** assumes the guard device can cache a bundle. A browser can (`localStorage` plus a service worker) — but `frontend/public/` has no service worker at all today, which is also why `US-2.7`'s push cannot buzz a phone yet. Registering one is in step 8 and benefits both.
