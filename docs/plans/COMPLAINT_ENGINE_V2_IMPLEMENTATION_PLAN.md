# Complaint Engine v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement [`COMPLAINT_ENGINE_PRD.md`](../COMPLAINT_ENGINE_PRD.md) — manual-first assignment with worker consent, forced assignment for critical all-declined jobs, the auto-dispatch fallback, skill-sourced categories, status coupling, resident cancel/re-pool, auto-close, chat auto-open, and the tracker UI — as a delta on the built system, reusing its machinery wherever it exists.

**Architecture:** Every state change stays a SECURITY DEFINER RPC with authorization inside the function; routers stay coarse guards; notifications are written inside the same transaction as their cause; timers are `dispatch_tasks` rows fired by the existing Python dispatcher loop (new kinds touch **only SQL**); the frontend consumes everything through the existing per-feature api modules + react-query. No new dependencies anywhere.

**Tech stack:** Postgres (Supabase, RLS + SECURITY DEFINER RPCs), FastAPI + supabase-py, React + react-query + zustand (shrinking), Tailwind. Tests: pytest, vitest, SQL assertion scripts under `backend/tests/integration/`.

## Global constraints

- **Migration immutability:** everything through `20260812160000` is applied to the hosted project and immutable. All schema/function change happens in **new** files named `202608131NNNNN_*.sql`. A changed function is rebuilt whole in the new file with `-- CHANGED` markers at each edited line (the `20260812090300` convention). A function whose signature changes is `drop function`-ed **by its exact old signature** first (`create or replace` with new parameters makes an overload, not a replacement).
- **Wire vocabulary** (`Pending | In Progress | Resolved`, comment visibility words) changes only in `backend/app/domain/vocabularies.py`. This plan adds **no** wire words.
- **Timeline vocabulary:** new event types are `job_force_assigned`, `returned_to_pool`, `auto_close_warning`, `auto_closed` — nothing else, and never reuse `job_declined` for a worker's refusal.
- **Error codes:** business refusals raise `HB404/HB403/HB409` exactly as the built RPCs do; `pg_errors` mapping already turns them into HTTP statuses.
- **API docs discipline:** every endpoint added or changed lands in `docs/API.md`, regenerated `docs/openapi.yaml`, and `docs/api_yaml_mapper.md` in the same phase that changes the code (project standard).
- **Docs change log:** every `docs/` artifact change gets a line in `docs/CHANGE_LOG.md` with its reason.
- **Five-gate check** for every phase: frontend, ERD (`docs/erd/`), class diagram (`docs/class-diagram/`), component design (`docs/design-of-components.md`), Supabase (hosted schema). Phase 10 reconciles the diagrams.
- **Baseline commands** (run from repo root; all must pass before and after every phase):
  - `python -m pytest backend/tests -x -q` (from `backend/`: `python -m pytest tests -x -q`)
  - `cd frontend && npx vitest run`

## File map (what is created / modified, by responsibility)

**New migrations** (`backend/supabase/migrations/`):
| File | Responsibility |
|---|---|
| `20260813100000_skill_sourced_complaints.sql` | `complaints.skill_id`, `raise_complaint` with skill, `resolve_complaint_department` v2 |
| `20260813101000_offer_consent_and_force.sql` | offer-not-assign, `is_forced`, exclusion, candidates-for-picker, forced assignment, all-declined handling, `cancelled_by` |
| `20260813102000_status_coupling.sql` | forward-only projection triggers, terminal-complaint guard, transfer-with-live-work guard |
| `20260813103000_resident_cancel_repool.sql` | `resident_cancel_work` RPC, `returned_to_pool_at`, queue flags |
| `20260813104000_timers_v2.sql` | `manual_window` + `auto_close_warning` + `auto_close` task kinds, `dispatch_tasks.complaint_id`, high-priority consent change |
| `20260813105000_chat_autopen_and_vocab.sql` | chat thread opened on accept, event-type CHECK, staff complaint detail RPC |

**Backend Python:**
| File | Change |
|---|---|
| `backend/app/domain/complaint_schemas.py` (or wherever `RaiseComplaintRequest` lives — see Task 7.1) | `skillId` on raise; cancel request/response models |
| `backend/app/domain/work_order_schemas.py` | `Candidate` model (+`awayUntil`, `excluded`), `isForced` on job/assignment views |
| `backend/app/api/v1/routers/resident_complaints.py` | `POST /complaints/{id}/cancel` |
| `backend/app/api/v1/routers/work_orders.py` | `GET /work-orders/{id}/candidates`; docstring change on assign (now an offer) |
| `backend/app/api/v1/routers/complaints.py` | `GET /complaints/{id}` staff read |
| `backend/app/services/resident_complaints_service.py` | `_EVENT_LABELS` additions; cancel service; skill-name lookup on raise |
| `backend/app/services/work_orders_service.py` | candidates service passthrough |
| `backend/app/services/complaints_service.py` | staff detail service (reuses the resident renderer) |
| repositories to match (thin RPC passthroughs, same files as their services' current calls) |

**Frontend:**
| File | Change |
|---|---|
| `frontend/src/features/resident/residentApi.js` | `cancelComplaintWork`, `skills` (reuse of `GET /skills`), raise payload `skillId` |
| `frontend/src/pages/ResidentDashboard/Complaints.jsx` | skill dropdown replaces CategoryPicker; tracker; cancel dialog |
| `frontend/src/features/complaints/ComplaintTracker.jsx` + `trackerProjection.js` + test | **new** stepper component + pure projection |
| `frontend/src/features/workOrders/workOrdersApi.js` | `candidates(workOrderId, {includeExcluded})` |
| `frontend/src/pages/AdminDashboard/WorkOrderTriage.jsx` | candidate picker panel; “Assign” → “Offer”; away-until; show-excluded toggle |
| `frontend/src/pages/WorkerDashboard/Dashboard.jsx`, `JobDetailModal.jsx` | forced badge; decline hidden when forced; chat deep link on accept |
| `frontend/src/features/complaints/DepartmentComplaintList` (used by Manager + Worker Complaints pages) | Backlog section, `returned`/`reopened` badges |
| `frontend/src/pages/AdminDashboard/Complaints.jsx` | react-query rewrite over the new staff read |
| `frontend/src/pages/AdminDashboard/DepartmentDetail.jsx` | “Assign to staff” dropdown → “Raise work order” link |
| `frontend/src/store/…/createComplaintsSlice.js` | delete optimistic writes + `assigneeStaffId` |

**Docs:** `docs/API.md`, `docs/openapi.yaml` (regenerated), `docs/api_yaml_mapper.md`, `docs/erd/`, `docs/class-diagram/`, `docs/CHANGE_LOG.md`, `docs/COMPLAINT_ENGINE_STATE.md` (post-implementation update), `docs/COMPLAINT_ENGINE_MANUAL_TESTING.md` (already written).

---

## Phase 0 — Baseline

### Task 0.1: Green baseline and branch

- [ ] **Step 1:** `git checkout -b complaint-engine-v2` from `services-and-security`.
- [ ] **Step 2:** Run `cd backend && python -m pytest tests -x -q` — expect PASS (record count).
- [ ] **Step 3:** Run `cd frontend && npx vitest run` — expect PASS.
- [ ] **Step 4:** Commit nothing; this is the reference point.

---

## Phase 1 — Migration: skill-sourced complaints

### Task 1.1: `20260813100000_skill_sourced_complaints.sql`

**Files:** Create `backend/supabase/migrations/20260813100000_skill_sourced_complaints.sql`
**Interfaces produced:** `raise_complaint(p_membership_id uuid, p_title text, p_description text, p_category text, p_priority text, p_location text, p_department_id uuid, p_skill_id uuid)` (8 args); `resolve_complaint_department(p_community_id uuid, p_category text, p_department_id uuid, p_skill_id uuid)`; column `complaints.skill_id uuid null references skills(id)`.

- [ ] **Step 1: Schema.** Add the column:

```sql
alter table public.complaints
  add column if not exists skill_id uuid references public.skills(id) on delete set null;
comment on column public.complaints.skill_id is
  'The trade the resident filed under, from the global skills catalogue. '
  'category keeps the display-name snapshot; old rows have null here.';
create index if not exists complaints_skill_idx on public.complaints (skill_id);
```

- [ ] **Step 2: Routing v2.** Rebuild `resolve_complaint_department` (source: `20260812090300_complaint_department_routing.sql` — copy the body, then apply the marked change). New precedence, PRD §3.1/§5.1: **(1)** `p_skill_id` maps through `department_skills` to exactly one active department of the community → that department; **(2)** the skill's name (or its trade `skills.category`) case-insensitively equals a `complaint_categories.name` of the community that maps through `department_categories` to exactly one active department → that department (this keeps every existing community's category wiring working untouched); **(3)** the old category-name path for legacy callers (unchanged body); **(4)** `p_department_id` if it names an active department of this community; **(5)** null. The new arms are pure additions on top of the existing function's shape:

```sql
-- CHANGED: skill precedence, PRD §3.1 (R5). Old signature dropped first —
-- an added parameter on create-or-replace makes an overload, not a change.
drop function if exists public.resolve_complaint_department(uuid, text, uuid);

create function public.resolve_complaint_department(
  p_community_id uuid,
  p_category     text,
  p_department_id uuid,
  p_skill_id     uuid default null
) returns uuid
language plpgsql stable security definer set search_path = public
as $$
declare
  v_dept uuid;
  v_n    integer;
begin
  -- (1) the skill held explicitly by exactly one active department
  if p_skill_id is not null then
    select min(d.id::text)::uuid, count(distinct d.id)
      into v_dept, v_n
      from public.department_skills ds
      join public.departments d on d.id = ds.department_id
     where ds.skill_id = p_skill_id
       and d.community_id = p_community_id
       and d.is_active;
    if v_n = 1 then return v_dept; end if;
    if v_n > 1 then return null; end if;  -- ambiguity is a triage question

    -- (2) the skill's name/trade matched against the community's categories
    select min(d.id::text)::uuid, count(distinct d.id)
      into v_dept, v_n
      from public.skills s
      join public.complaint_categories cc
        on cc.community_id = p_community_id
       and lower(btrim(cc.name)) in (lower(btrim(s.name)),
                                     lower(btrim(coalesce(s.category, ''))))
      join public.department_categories dc on dc.category_id = cc.id
      join public.departments d on d.id = dc.department_id and d.is_active
     where s.id = p_skill_id;
    if v_n = 1 then return v_dept; end if;
    if v_n > 1 then return null; end if;
  end if;

  -- (3)+(4)+(5): the applied 20260812090300 body, verbatim from here down.
  …
end $$;
```

- [ ] **Step 3: `raise_complaint` with skill.** Drop the applied 7-arg signature exactly (`drop function public.raise_complaint(uuid, text, text, text, text, text, uuid);`), rebuild with `p_skill_id uuid default null` appended, body copied from `20260812090300`:273 with three `-- CHANGED` edits: (a) when `p_skill_id` is present, validate it exists and `is_active` in `skills` (else `HB404` 'No such trade.') and **derive `v_category := skills.name`** (server-side snapshot — the client stops sending display text); (b) the routing call passes `p_skill_id`; (c) `insert … skill_id = p_skill_id`, and the `raised` event payload gains `'skill_id', p_skill_id` next to the existing `department_chosen_by_resident` key.
- [ ] **Step 4: Post-checks** (the migration ends with `do $$` asserts, project convention): function exists with 8 args; column exists; `resolve_complaint_department(…, p_skill_id => null)` equals old behaviour on a synthetic category (create + rollback inside the check or assert by catalog inspection only, matching how `20260812160000` post-checks).
- [ ] **Step 5:** `python -m pytest tests -x -q` (backend tests monkeypatch RPCs; expect PASS — nothing Python-side changed yet).
- [ ] **Step 6:** Commit: `feat(complaints): skill-sourced raise + routing precedence (R5)`.

---

## Phase 2 — Migration: offer, consent, exclusion, force

### Task 2.1: `20260813101000_offer_consent_and_force.sql`

**Files:** Create `backend/supabase/migrations/20260813101000_offer_consent_and_force.sql`
**Interfaces produced:**
- columns: `work_order_assignments.is_forced boolean not null default false`; `work_orders.cancelled_by text check (cancelled_by in ('resident','staff','system'))` (nullable)
- `complaint_excluded_staff(p_complaint_id uuid) returns table (staff_assignment_id uuid)`
- `work_order_candidates(p_work_order_id uuid, p_include_excluded boolean default false) returns table (staff_assignment_id uuid, membership_id uuid, service_provider_id uuid, display_name text, has_adjacent_job boolean, open_jobs integer, distance_km numeric, away_until timestamptz, excluded boolean)`
- `assign_work_order(...)` same 4-arg signature, now writing an **offer**
- `dispatch_force_assign(p_work_order_id uuid) returns uuid`
- `decline_work_order_offer(...)` — same signature, forced-guard + all-declined handling appended

- [ ] **Step 1: Columns.**

```sql
alter table public.work_order_assignments
  add column if not exists is_forced boolean not null default false;
alter table public.work_orders
  add column if not exists cancelled_by text;
do $$ begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.work_orders'::regclass
                    and conname = 'work_orders_cancelled_by_check') then
    alter table public.work_orders add constraint work_orders_cancelled_by_check
      check (cancelled_by is null or cancelled_by in ('resident','staff','system'));
  end if;
end $$;
```

- [ ] **Step 2: The exclusion set** (PRD §5.5, §8.1, §8.3 — one definition, three consumers):

```sql
create or replace function public.complaint_excluded_staff(p_complaint_id uuid)
returns table (staff_assignment_id uuid)
language sql stable security definer set search_path = public
as $$
  -- (a) anyone who declined any job on this complaint
  select a.staff_assignment_id
    from public.work_order_assignments a
    join public.work_orders w on w.id = a.work_order_id
   where w.complaint_id = p_complaint_id and a.status = 'declined'
  union
  -- (b) anyone the resident cancelled on
  select a.staff_assignment_id
    from public.work_order_assignments a
    join public.work_orders w on w.id = a.work_order_id
   where w.complaint_id = p_complaint_id
     and w.status = 'cancelled' and w.cancelled_by = 'resident'
     and a.status in ('accepted', 'withdrawn')
  union
  -- (c) on a reopened complaint, anyone who did the earlier work
  select a.staff_assignment_id
    from public.complaints c
    join public.work_orders w on w.complaint_id = c.id
    join public.work_order_assignments a on a.work_order_id = w.id
   where c.id = p_complaint_id and c.reopened_count > 0
     and a.status in ('accepted', 'completed')
     and w.status = 'completed';
$$;
```

- [ ] **Step 3: Candidates for the picker.** New function wrapping the existing ranking; **greyed-not-hidden** needs the away-leave people back in, so it re-implements only the *filter relaxations*, not the ranking (source of every predicate: `dispatch_candidates` in `0045`):

```sql
create or replace function public.work_order_candidates(
  p_work_order_id     uuid,
  p_include_excluded  boolean default false
) returns table (
  staff_assignment_id uuid, membership_id uuid, service_provider_id uuid,
  display_name text, has_adjacent_job boolean, open_jobs integer,
  distance_km numeric, away_until timestamptz, excluded boolean
)
language plpgsql stable security definer set search_path = public
as $$
declare v_order public.work_orders%rowtype;
begin
  select * into v_order from public.work_orders where id = p_work_order_id;
  if not found then raise exception 'No such work order.' using errcode = 'HB404'; end if;
  if not public.can_supervise_department(v_order.department_id) then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;

  return query
  with base as (
    select * from public.dispatch_candidates(p_work_order_id, 100)
  ), excl as (
    select e.staff_assignment_id from public.complaint_excluded_staff(v_order.complaint_id) e
  )
  select b.staff_assignment_id, b.membership_id, b.service_provider_id,
         b.display_name, b.has_adjacent_job, b.open_jobs, b.distance_km,
         (select max(u.ends_at) from public.worker_unavailability u
           where (u.staff_assignment_id = b.staff_assignment_id
                  or u.service_provider_id = b.service_provider_id)
             and u.ends_at > now()) as away_until,
         exists (select 1 from excl e
                  where e.staff_assignment_id = b.staff_assignment_id) as excluded
    from base b
   where p_include_excluded
      or not exists (select 1 from excl e
                      where e.staff_assignment_id = b.staff_assignment_id);
end $$;
```

*(“Away until” for people currently on leave: `dispatch_candidates` filters them out only when their block overlaps the slot; those away **now** but free at the slot still appear, with `away_until` populated — exactly the supervisor-planning view the PRD asks for. A second query for slot-excluded workers is deliberately skipped — YAGNI until a supervisor asks to see them.)*

- [ ] **Step 4: `assign_work_order` becomes an offer.** Rebuild whole from `0036`:1083 with these `-- CHANGED` lines: insert/refresh the assignment with `status = 'offered'` (not `accepted`); keep the withdraw-previous-open-offers block (it already handles both); keep every guard including the overlap *pre-check* (an offer to a busy person is pointless even if the constraint would allow it, since the exclusion constraint only covers `accepted`); write **no** `job_assigned` event (that now happens at accept); notify the **worker** (`notify_person`/existing notification writer used by `dispatch_ping_candidates` — copy that pattern, type `job.offered`, URL in the `/worker/jobs?job=` shape the worker portal already deep-links); create/refresh the 30-minute offer-timeout `dispatch_tasks` row (`kind = 'auto_assign'` is **not** reused — see Task 5.1's `offer_timeout` note; until Phase 5 lands, insert kind `auto_assign` due `now() + interval '30 minutes'`, which the engine already interprets as “time up, assign best remaining” — the manual offer simply joins the machinery the engine already has). Work order status moves `scheduled → offered` if not already.
- [ ] **Step 5: Forced assignment.**

```sql
create or replace function public.dispatch_force_assign(p_work_order_id uuid)
returns uuid
language plpgsql security definer set search_path = public
as $$
declare
  v_order public.work_orders%rowtype;
  v_pick  record;
  v_id    uuid;
begin
  select * into v_order from public.work_orders where id = p_work_order_id for update;
  if not found or v_order.status in ('completed','cancelled','failed') then return null; end if;

  select * into v_pick
    from public.work_order_candidates(p_work_order_id, true)  -- decliners visible…
   where away_until is null or away_until <= now()
   order by open_jobs asc, distance_km asc nulls last
   limit 1;
  if v_pick is null then return null; end if;  -- E9: nobody to force

  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = p_work_order_id and status in ('offered');

  insert into public.work_order_assignments
    (work_order_id, staff_assignment_id, status, is_forced, is_auto_assigned,
     scheduled_start_at, scheduled_end_at)
  values (p_work_order_id, v_pick.staff_assignment_id, 'accepted', true, true,
          v_order.scheduled_start_at, v_order.scheduled_end_at)
  returning id into v_id;

  update public.work_orders set status = 'scheduled' where id = p_work_order_id;
  -- events + notifications: job_assigned (resident-facing), job_force_assigned
  -- (audit), worker + supervisor + resident notified — copy the shapes from
  -- dispatch_auto_assign in 0037 and add the force wording.
  …
  return v_id;
end $$;
```

*(`work_order_candidates(p_include_excluded => true)` is called here with the caller being the **dispatcher** (service role), so relax the `can_supervise_department` guard: change the guard in Step 3's function to `if not (public.can_supervise_department(...) or current_setting('request.jwt.claims', true) is null) then` — the same service-role test the 0037 firing functions use. Copy the exact idiom from `dispatch_auto_assign`.)*

- [ ] **Step 6: Decline learns the two new rules.** Rebuild `decline_work_order_offer` from `0039`:424 whole, with `-- CHANGED`: (a) first, `if v_assignment.is_forced then raise exception 'This assignment cannot be declined.' using errcode = 'HB409'; end if;` (b) after recording the decline, the all-declined check:

```sql
  -- Everybody available has now said no?
  if not exists (select 1 from public.work_order_candidates(v_order.id, false)) then
    if v_complaint.priority = 'high' then
      perform public.dispatch_force_assign(v_order.id);   -- §5.6
    end if;
    -- and either way, tell the supervisor the round is over (type
    -- job.all_declined; recipients: the job's creator + the department
    -- manager — reuse notify_complaint_staff's recipient CTE shape).
    …
  end if;
```

- [ ] **Step 7: Post-checks + tests.** Post-check block asserts: `is_forced` column exists; `assign_work_order` writes `offered` (assert by reading `pg_get_functiondef` for the literal `'offered'`, the convention `20260812160000` uses for text asserts); `dispatch_force_assign` exists. Run backend suite. Commit: `feat(work-orders): offers need consent; forced assignment for critical all-declined (R1, R2, R8)`.

---

## Phase 3 — Migration: status coupling and the two guards

### Task 3.1: `20260813102000_status_coupling.sql`

**Interfaces produced:** trigger `work_orders_project_complaint` on `work_orders`; trigger `work_order_assignments_project_complaint` on `work_order_assignments`; `create_work_order` refuses terminal complaints; `assign_complaint_department` + transfer-accept refuse live work.

- [ ] **Step 1: The projection** (PRD §6.1 — forward-only, worked example one file over in `0037`'s `dispatch_tasks` sync trigger):

```sql
create or replace function public.project_complaint_from_jobs()
returns trigger
language plpgsql security definer set search_path = public
as $$
declare
  v_complaint_id uuid;
  v_live integer;
begin
  v_complaint_id := coalesce(new.complaint_id,
    (select w.complaint_id from public.work_orders w
      where w.id = new.work_order_id));   -- assignment rows carry no complaint_id

  if tg_table_name = 'work_order_assignments' and tg_op = 'INSERT'
     and new.status = 'offered' then
    update public.complaints set status = 'acknowledged', updated_at = now()
     where id = v_complaint_id and status = 'open';
  elsif tg_table_name = 'work_orders' and new.status = 'in_progress' then
    update public.complaints set status = 'in_progress', updated_at = now()
     where id = v_complaint_id and status in ('open','acknowledged');
  elsif tg_table_name = 'work_orders' and new.status = 'completed' then
    select count(*) into v_live from public.work_orders w
     where w.complaint_id = v_complaint_id and w.id <> new.id
       and w.status in ('draft','awaiting_resident','offered','scheduled','in_progress');
    if v_live = 0 then
      update public.complaints
         set status = 'resolved', updated_at = now()
       where id = v_complaint_id
         and status in ('open','acknowledged','in_progress');
      -- the resolved event + "confirm or reopen" notification + the two
      -- auto-close tasks are written by the complaint-side trigger in Task 5.2,
      -- which watches complaints.status itself — one writer, however resolved.
    end if;
  end if;
  return new;
end $$;

drop trigger if exists work_orders_project_complaint on public.work_orders;
create trigger work_orders_project_complaint
  after update of status on public.work_orders
  for each row when (new.status in ('in_progress','completed'))
  execute function public.project_complaint_from_jobs();

drop trigger if exists work_order_assignments_project_complaint
  on public.work_order_assignments;
create trigger work_order_assignments_project_complaint
  after insert on public.work_order_assignments
  for each row when (new.status = 'offered')
  execute function public.project_complaint_from_jobs();
```

The `where … status in (…)` clauses are the forward-only guarantee: a hand-set
`resolved`, a `closed`, a `cancelled` complaint is never touched (E28).

- [ ] **Step 2: Terminal-complaint guard (R14).** Rebuild `create_work_order` whole (source: `0036`) with one added check after the complaint is loaded: `if v_complaint.status in ('resolved','closed','cancelled') then raise exception 'Reopen the complaint to raise more work.' using errcode = 'HB409'; end if;`
- [ ] **Step 3: Transfer guard (R15).** Rebuild `assign_complaint_department` and the transfer-request accept RPC (both in `20260812090300`) with the same added check: `if exists (select 1 from public.work_orders w where w.complaint_id = p_complaint_id and w.status in ('draft','awaiting_resident','offered','scheduled','in_progress')) then raise exception 'Cancel or finish the open job first.' using errcode = 'HB409'; end if;`
- [ ] **Step 4:** Post-checks (triggers exist; function defs contain the guard strings). Run suite. Commit: `feat(complaints): job progress projects onto complaint status; guards for terminal/transfer (R17, R14, R15)`.

---

## Phase 4 — Migration: resident cancel and the pool

### Task 4.1: `20260813103000_resident_cancel_repool.sql`

**Interfaces produced:** `complaints.returned_to_pool_at timestamptz null`; `resident_cancel_work(p_complaint_id uuid, p_mode text, p_reason text default null) returns void`; `department_complaints(...)` rows gain `returned_to_pool_at` and `reopened_count`.

- [ ] **Step 1: Column.** `alter table public.complaints add column if not exists returned_to_pool_at timestamptz;` — cleared by `create_work_order` (add `-- CHANGED` line to the Phase 3 rebuild: `update public.complaints set returned_to_pool_at = null where id = p_complaint_id and returned_to_pool_at is not null;` — the flag means “waiting for re-evaluation”, and raising new work is the re-evaluation).
- [ ] **Step 2: The RPC.**

```sql
create or replace function public.resident_cancel_work(
  p_complaint_id uuid, p_mode text, p_reason text default null
) returns void
language plpgsql security definer set search_path = public
as $$
declare
  v_complaint public.complaints%rowtype;
  v_order     public.work_orders%rowtype;
begin
  if p_mode not in ('cancel', 'repool') then
    raise exception 'Unknown cancellation mode: %', p_mode using errcode = '22P02';
  end if;

  select * into v_complaint from public.complaints
   where id = p_complaint_id for update;
  if not found or not public.is_own_membership(v_complaint.raised_by_membership_id) then
    raise exception 'No such complaint.' using errcode = 'HB404';  -- 404 hides not-yours
  end if;

  -- the live job in the cancellable window: accepted, not started (R9)
  select w.* into v_order from public.work_orders w
   where w.complaint_id = p_complaint_id
     and w.status in ('offered','scheduled')
   order by w.created_at desc limit 1 for update;
  if not found then
    raise exception 'There is nothing to cancel right now.' using errcode = 'HB409';
  end if;
  if exists (select 1 from public.work_orders w
              where w.complaint_id = p_complaint_id and w.status = 'in_progress') then
    raise exception 'Work has begun — contact the office to cancel.' using errcode = 'HB409';
  end if;

  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = v_order.id and status in ('offered','accepted');

  update public.work_orders
     set status = 'cancelled', cancelled_by = 'resident' where id = v_order.id;
  -- (the 0046 lock trigger stamps the chat thread's locked_at on this update)

  if p_mode = 'cancel' then
    update public.complaints set status = 'cancelled', updated_at = now()
     where id = p_complaint_id;
    -- timeline: status_changed (actor: resident, note: p_reason)
  else
    update public.complaints set returned_to_pool_at = now(), updated_at = now()
     where id = p_complaint_id;
    -- timeline: returned_to_pool (payload: reason)
  end if;
  -- events via the add-event helper 0031 uses; notifications: assigned worker
  -- + notify_complaint_staff (type complaint.job_cancelled_by_resident),
  -- copied shapes from cancel_work_order in 0036.
  …
end $$;
```

- [ ] **Step 3: Queue flags.** Rebuild `department_complaints` (`20260812090300`:820) whole, adding `c.returned_to_pool_at` and `c.reopened_count` to the returned columns (`-- CHANGED` lines in the `returns table` and select list).
- [ ] **Step 4:** Post-checks; suite; commit: `feat(complaints): resident cancel with re-evaluation pool (R9, R10)`.

---

## Phase 5 — Migration: the three new timers

### Task 5.1: `20260813104000_timers_v2.sql`

**Interfaces produced:** `dispatch_tasks.complaint_id uuid null`; kinds `manual_window`, `auto_close_warning`, `auto_close`; `dispatch_manual_window(p_work_order_id uuid) returns boolean`; `dispatch_auto_close(p_complaint_id uuid, p_warn boolean) returns boolean`; `fire_dispatch_task` with three new arms; resident schedule-accept schedules `manual_window` instead of `ping`; high priority stops skipping consent.

- [ ] **Step 1: Table.**

```sql
alter table public.dispatch_tasks
  add column if not exists complaint_id uuid references public.complaints(id) on delete cascade;
-- kind check: drop + re-add with the three new kinds (constraint name is load-bearing)
alter table public.dispatch_tasks drop constraint if exists dispatch_tasks_kind_check;
alter table public.dispatch_tasks add constraint dispatch_tasks_kind_check
  check (kind in ('ping','auto_assign','resident_timeout','failed_visit_escalation',
                  'departure_removal','manual_window','auto_close_warning','auto_close'));
create unique index if not exists dispatch_tasks_one_open_per_complaint_kind
  on public.dispatch_tasks (complaint_id, kind)
  where completed_at is null and complaint_id is not null;
```

- [ ] **Step 2: The manual window (R1, R7).** Find where the resident's schedule-accept creates the `ping` task (the accept RPC in `resident_scheduling`'s chain / `0037` §2's task-creation trigger — read `0037` §2 for the exact writer) and rebuild that writer so acceptance enqueues `manual_window` due `now() + case when priority = 'high' then interval '2 hours' else interval '24 hours' end` **instead of** an immediate `ping`. Also rebuild the `high`-priority arm that skips straight to auto-assign (`0037`'s trigger table, per its header) into the same `manual_window` path — consent now applies to high (R2). Then the firing function:

```sql
create or replace function public.dispatch_manual_window(p_work_order_id uuid)
returns boolean
language plpgsql security definer set search_path = public
as $$
declare v_order public.work_orders%rowtype;
begin
  select * into v_order from public.work_orders where id = p_work_order_id for update;
  if not found or v_order.status not in ('scheduled') then return false; end if;
  if exists (select 1 from public.work_order_assignments a
              where a.work_order_id = p_work_order_id
                and a.status in ('offered','accepted')) then
    return false;  -- a human beat the timer; idempotency is load-bearing
  end if;
  perform public.dispatch_ping_candidates(p_work_order_id);  -- the engine takes over
  -- notify the job's creator + department manager: 'The system is finding
  -- someone — nobody was offered this job in time.' (type job.fallback_started)
  …
  return true;
end $$;
```

- [ ] **Step 3: Auto-close (R11).** A complaint-side trigger is the single writer for “became resolved”, however it happened (worker projection, admin PATCH):

```sql
create or replace function public.on_complaint_resolved()
returns trigger
language plpgsql security definer set search_path = public
as $$
begin
  if new.status = 'resolved' and old.status is distinct from 'resolved' then
    insert into public.dispatch_tasks (complaint_id, kind, due_at)
    values (new.id, 'auto_close_warning', now() + interval '48 hours'),
           (new.id, 'auto_close',         now() + interval '72 hours')
    on conflict do nothing;
    -- resolved event + "confirm or reopen" resident notification here too,
    -- moved out of confirm/PATCH paths so there is exactly one writer.
  end if;
  return new;
end $$;
drop trigger if exists complaints_on_resolved on public.complaints;
create trigger complaints_on_resolved
  after update of status on public.complaints
  for each row execute function public.on_complaint_resolved();

create or replace function public.dispatch_auto_close(
  p_complaint_id uuid, p_warn boolean
) returns boolean
language plpgsql security definer set search_path = public
as $$
declare v public.complaints%rowtype;
begin
  select * into v from public.complaints where id = p_complaint_id for update;
  if not found or v.status <> 'resolved' then return false; end if;  -- E15, E16
  if p_warn then
    -- notify raiser: 'Confirm or reopen — this closes itself in 24 hours.'
    -- timeline: auto_close_warning
    …
  else
    update public.complaints set status = 'closed', updated_at = now()
     where id = p_complaint_id;
    -- timeline: auto_closed; notify raiser. No rating is written (E17: their
    -- path afterwards is reopen). reopen_complaint accepts 'closed' — kept.
    …
  end if;
  return true;
end $$;
```

- [ ] **Step 4: `fire_dispatch_task` v3.** Rebuild whole from `0045`:1138 adding three arms before the `else`:

```sql
    when 'manual_window' then
      v_result := case when public.dispatch_manual_window(v_task.work_order_id)
                  then 'fallback_started' else 'skipped' end;
    when 'auto_close_warning' then
      v_result := case when public.dispatch_auto_close(v_task.complaint_id, true)
                  then 'warned' else 'skipped' end;
    when 'auto_close' then
      v_result := case when public.dispatch_auto_close(v_task.complaint_id, false)
                  then 'closed' else 'skipped' end;
```

- [ ] **Step 5:** Post-checks (kind check contains all eight; both indexes exist; `pg_get_functiondef(public.fire_dispatch_task(uuid)) like '%manual_window%'`). Run suite (`backend/tests` includes dispatcher tests — `test_realtime.py`, dispatch repository tests must still pass: **no Python change is needed**, which is the architecture paying off). Commit: `feat(dispatch): manual window fallback + auto-close timers (R7, R11)`.

---

## Phase 6 — Migration: chat auto-open, vocabulary lock, staff read

### Task 6.1: `20260813105000_chat_autopen_and_vocab.sql`

**Interfaces produced:** accept-side thread opening; `complaint_events` CHECK; `staff_complaint_detail(p_complaint_id uuid)` returning the complaint row + its events for staff.

- [ ] **Step 1: Chat opens on acceptance (PRD §7).** Rebuild `accept_work_order_offer` whole (source: `20260812120000`:385, the latest body) adding, inside the success branch: find the complaint's raiser profile id and the worker's profile id, upsert the `dm_threads` row for `(kind 'work_order', work_order_id)` exactly the way `messages_service.open_thread`'s SQL does (same ON CONFLICT target), insert a system message (`author nulls`, body `'You''re connected about this job — agree the details here.'`), stamp `last_message_at`. Add the same upsert to `dispatch_force_assign` (Phase 2) and to `dispatch_auto_assign` (rebuild whole, one added block) — every path to an accepted worker opens the channel.
- [ ] **Step 2: Vocabulary lock (R19).**

```sql
alter table public.complaint_events drop constraint if exists complaint_events_type_check;
alter table public.complaint_events add constraint complaint_events_type_check
  check (event_type in (
    'raised','status_changed','assigned','progress_changed','due_date_changed',
    'note_added','comment_added','reopened','resolution_confirmed',
    'job_created','job_scheduled','job_declined','job_assigned','job_cancelled',
    'job_started','job_completed','job_failed',
    'department_assigned','department_change_requested',
    'department_change_accepted','department_change_rejected',
    'job_force_assigned','returned_to_pool','auto_close_warning','auto_closed'));
```

Pre-flight inside the migration: `do $$` assert no existing row violates the list (`select event_type from complaint_events where event_type not in (…) limit 1` → raise with the offending word) — a locked door with somebody inside is worse than no door.
- [ ] **Step 3: Staff read.**

```sql
create or replace function public.staff_complaint_detail(p_complaint_id uuid)
returns jsonb
language plpgsql stable security definer set search_path = public
as $$
declare v public.complaints%rowtype;
begin
  select * into v from public.complaints where id = p_complaint_id;
  if not found then raise exception 'No such complaint.' using errcode = 'HB404'; end if;
  if not (public.is_community_admin(v.community_id)
          or (v.department_id is not null
              and public.can_supervise_department(v.department_id))) then
    raise exception 'No such complaint.' using errcode = 'HB404';  -- same-shape 404
  end if;
  return jsonb_build_object(
    'complaint', to_jsonb(v),
    'events', (select coalesce(jsonb_agg(to_jsonb(e) order by e.created_at), '[]'::jsonb)
                 from public.complaint_events e where e.complaint_id = v.id));
end $$;
```

Staff see internal-comment shadows (that is the point of the staff view); the Python renderer handles labels (Task 7.4).
- [ ] **Step 4:** Post-checks; suite; commit: `feat(complaints): chat opens on accept; event vocabulary locked; staff detail read (R19)`.

---

## Phase 7 — Backend Python

### Task 7.1: Raise payload carries the skill

**Files:** Modify the Pydantic raise model (find with `grep -rn "class .*Complaint.*Request" backend/app/domain/` — the raise model is beside the complaint schemas the resident router imports), `backend/app/api/v1/routers/resident_complaints.py`, its service + repository.

- [ ] **Step 1:** Failing test in `backend/tests/api/test_resident_complaints.py` (extend the existing raise test file — copy its fixture pattern):

```python
def test_raise_complaint_passes_skill_id(client, monkeypatch_rpc):
    captured = {}
    monkeypatch_rpc("raise_complaint", lambda params: captured.update(params) or "cid")
    r = client.post("/api/v1/complaints", json={
        "title": "Tap drips", "description": "Kitchen tap", "priority": "low",
        "skillId": "6b7d…-skill", "departmentId": None}, headers=auth_headers())
    assert r.status_code == 201
    assert captured["p_skill_id"] == "6b7d…-skill"
```

- [ ] **Step 2:** Run: `python -m pytest tests/api/test_resident_complaints.py -x -q` — FAIL (`skillId` unknown / param missing).
- [ ] **Step 3:** Add `skill_id: str | None = Field(default=None, alias="skillId")` to the raise request model; thread it through the service to the RPC call (`p_skill_id`); `category` field becomes optional in the model (the RPC derives the snapshot when `p_skill_id` is present; old category-only calls still work — the RPC kept the legacy arm).
- [ ] **Step 4:** Test passes; whole file passes.
- [ ] **Step 5:** Commit: `feat(api): raise complaint by skill`.

### Task 7.2: Resident cancel endpoint

**Files:** `resident_complaints.py` router + service + repository; request model `CancelWorkRequest(mode: Literal['cancel','repool'], reason: str | None)`.

- [ ] **Step 1:** Failing tests (same file): 200 path calls RPC `resident_cancel_work` with `p_mode`; a 409 from the RPC (simulate `HB409`) surfaces as HTTP 409.
- [ ] **Step 2–4:** `POST /complaints/{id}/cancel` (CSRF, resident role guard like its siblings), service passthrough, tests green.
- [ ] **Step 5:** Commit: `feat(api): resident cancel with cancel/repool modes`.

### Task 7.3: Candidates + staff detail endpoints

**Files:** `work_orders.py` (+schemas), `complaints.py` (+service).

- [ ] **Step 1:** Failing tests: `GET /work-orders/{id}/candidates?includeExcluded=true` maps to `work_order_candidates` RPC and returns camelCase `awayUntil`/`excluded`; `GET /complaints/{id}` (staff) returns the `staff_complaint_detail` shape with rendered timeline labels; a worker without supervision gets 404 (RPC's same-shape 404 passes through).
- [ ] **Step 2–4:** Implement: `Candidate` Pydantic model mirroring the RPC columns; staff detail service **reuses** `resident_complaints_service`'s `_event_message`/`_EVENT_LABELS` renderer on the events array (import the function — do not copy it) but skips `_is_internal_comment_event` stripping (staff see those).
- [ ] **Step 5:** Commit: `feat(api): candidate picker read + staff complaint detail`.

### Task 7.4: New event labels

**Files:** `backend/app/services/resident_complaints_service.py` (`_EVENT_LABELS` / `_event_message`).

- [ ] **Step 1:** Failing test (the renderer has direct tests — extend them): `returned_to_pool` → “Sent back for re-evaluation — the team will assign someone else.”; `auto_closed` → “Closed automatically after no response.”; `auto_close_warning` → “Reminder sent: confirm or reopen.”; `job_force_assigned` → renders for staff as “Assigned without offer (critical)” and is **filtered from the resident view** exactly like internal-comment shadows (add its type to the same strip predicate — the resident-facing fact is the `job_assigned` event that accompanies it).
- [ ] **Step 2–4:** Implement labels; green.
- [ ] **Step 5:** Commit: `feat(timeline): labels for v2 events`.

### Task 7.5: API docs

- [ ] **Step 1:** `docs/API.md`: add `POST /complaints/{id}/cancel`, `GET /work-orders/{id}/candidates`, staff `GET /complaints/{id}`; amend `POST /complaints` (skillId), `POST /work-orders/{id}/assign` (semantics: writes an offer; worker consent required; 409s unchanged) — status codes included, §14 traceability rows added.
- [ ] **Step 2:** Regenerate `docs/openapi.yaml` (`python backend/scripts/export_openapi.py`), update `docs/api_yaml_mapper.md`.
- [ ] **Step 3:** `docs/CHANGE_LOG.md` entries. Commit: `docs(api): complaint engine v2 surface`.

---

## Phase 8 — Frontend: resident

### Task 8.1: Skill-sourced dropdown

**Files:** `frontend/src/features/resident/residentApi.js`; `frontend/src/pages/ResidentDashboard/Complaints.jsx`.

- [ ] **Step 1:** `residentApi.skills = () => api('/skills')` (same endpoint the worker portal calls; residents are authenticated — verify the router guard on `GET /skills` allows any authenticated caller; it does, it serves onboarding pre-membership. If a role guard surprises, loosen in `service_providers.py` with a comment, not a new endpoint).
- [ ] **Step 2:** In the raise dialog, replace the `CategoryPicker` usage with a grouped `<select>` fed by `useQuery(['skills'])`, `<optgroup>` per `skill.category`, option value = `skill.id` — parity with onboarding is now “same endpoint, same grouping”. Payload sends `skillId` (drop `categoryId`); the department “Not sure” picker stays untouched.
- [ ] **Step 3:** Update the page's vitest (raise submits `skillId`). Commit: `feat(resident): raise complaints under trades — one catalogue with onboarding (R5)`.

*(`CategoryPicker.jsx` keeps its department-form consumers; it is not deleted.)*

### Task 8.2: Tracker

**Files:** Create `frontend/src/features/complaints/trackerProjection.js`, `frontend/src/features/complaints/ComplaintTracker.jsx`, `frontend/src/features/complaints/trackerProjection.test.js`; modify `ResidentDashboard/Complaints.jsx` detail view.

- [ ] **Step 1:** Failing projection tests — pure function, the heart of the UI:

```js
import { projectTracker } from './trackerProjection';

test('happy path fills nodes in order', () => {
  const nodes = projectTracker([
    { eventType: 'raised', createdAt: t0 },
    { eventType: 'job_assigned', createdAt: t1, payload: { workerName: 'Ravi' } },
    { eventType: 'job_scheduled', createdAt: t2, payload: { scheduledStartAt: s } },
    { eventType: 'job_started', createdAt: t3 },
    { eventType: 'job_completed', createdAt: t4 },
  ]);
  expect(nodes.map(n => n.state)).toEqual(
    ['done', 'done', 'done', 'done', 'done', 'pending']); // Closed pending
  expect(nodes[1].detail).toContain('Ravi');
});

test('reopen restarts the line and keeps an annotation', () => { /* reopened → nodes reset, annotations contain reopened */ });
test('returned_to_pool annotates without advancing', () => { /* … */ });
test('failed visit annotates, line holds at In progress', () => { /* … */ });
test('auto_closed completes the Closed node with unrated flag', () => { /* … */ });
```

- [ ] **Step 2:** Implement `projectTracker(events) -> { nodes: [{key, label, state, detail}], annotations: [{afterNode, label, at}] }` with the six nodes `raised/assigned/scheduled/in_progress/work_done/closed`; the **latest** `reopened` event truncates consideration to events after it (line restart, PRD §6.2); `resolution_confirmed` or `auto_closed` or `status_changed→closed` completes the last node.
- [ ] **Step 3:** `ComplaintTracker.jsx`: pure presentational; `flex-row` with connecting line ≥`md:`, `flex-col` below (the user's horizontal/vertical rule); Tailwind only; annotation chips under/beside their node. Mount in the resident detail panel above the existing timeline list (the list stays — the tracker summarizes, the list is the record).
- [ ] **Step 4:** `npx vitest run` green. Commit: `feat(resident): order-tracking stepper over the complaint timeline`.

### Task 8.3: Cancel dialog

**Files:** `ResidentDashboard/Complaints.jsx`; `residentApi.js` (`cancelComplaintWork(id, {mode, reason})`).

- [ ] **Step 1:** Cancel button renders only when the detail shows a live accepted/offered job not yet started (drive it from the schedule/job facts already present in the detail response; if absent, derive from the last tracker node — `assigned`/`scheduled` reached, `in_progress` not).
- [ ] **Step 2:** The dialog offers exactly the two PRD choices with honest copy (“Cancel entirely — to raise this again you'll start from scratch” / “Send back for re-evaluation — the team will pick someone else”), optional reason, calls the Task 7.2 endpoint, invalidates the detail + list queries. 409 from a started job renders the server's message.
- [ ] **Step 3:** Vitest for the dialog's two calls. Commit: `feat(resident): cancel or re-pool an assigned job (R9)`.

---

## Phase 9 — Frontend: staff and worker

### Task 9.1: Candidate picker in triage

**Files:** `frontend/src/features/workOrders/workOrdersApi.js` (+`candidates`), `frontend/src/pages/AdminDashboard/WorkOrderTriage.jsx`.

- [ ] **Step 1:** `candidates: (id, { includeExcluded } = {}) => api(\`/work-orders/${id}/candidates${includeExcluded ? '?includeExcluded=true' : ''}\`)`.
- [ ] **Step 2:** In the job detail pane, replace the bare staff dropdown behind the assign action with a candidate list: name, `open_jobs` load chip, distance when present, “another job that day” marker, amber “away until ⟨date⟩” when `awayUntil` is future, greyed row + “declined earlier” note when `excluded` (visible only with the *Show excluded* toggle → `includeExcluded=true`). Button label changes **Assign → Offer job**; the confirmation copy says the worker must accept. The existing `assign` mutation is unchanged (the RPC's semantics changed underneath it).
- [ ] **Step 3:** Offer state renders on the job card (`offered · waiting on ⟨name⟩ · expires in ~30 min`) from the job's assignment rows the detail already returns.
- [ ] **Step 4:** Vitest: candidates render, excluded hidden by default, toggle reveals. Commit: `feat(triage): candidate picker with availability + exclusion (R1, R10)`.

### Task 9.2: Worker portal — forced jobs and chat links

**Files:** `frontend/src/pages/WorkerDashboard/Dashboard.jsx`, `JobDetailModal.jsx`.

- [ ] **Step 1:** Where the offer's Accept/Decline pair renders, hide Decline and show a “Assigned — critical job” badge when the assignment carries `isForced` (surface the flag through the worker snapshot/job schemas — one field in `worker_schemas.py`, already serialized from the assignment row).
- [ ] **Step 2:** After a successful accept mutation, deep-link toast → the ChatDock thread (open the dock on the thread for this job's `dmThreadId`; the thread now exists by construction — expose `dmThreadId` on the job detail by joining `dm_threads` in the worker job read, one `-- CHANGED` select column in the worker snapshot RPC — fold into Phase 6's migration).
- [ ] **Step 3:** Vitest for the forced-badge branch. Commit: `feat(worker): forced assignments are visible and undeclinable; accept lands you in the chat`.

### Task 9.3: Backlog section in the department queue

**Files:** the shared `DepartmentComplaintList` component used by `ManagerDashboard/Complaints.jsx` and `WorkerDashboard/Complaints.jsx` (locate: `grep -rn "DepartmentComplaintList" frontend/src`).

- [ ] **Step 1:** The queue rows now carry `returnedToPoolAt` / `reopenedCount` (Phase 4). Partition: rows with `returnedToPoolAt` set or `reopenedCount > 0` and no live job render under a **Backlog — needs re-evaluation** heading with a `returned` / `reopened` badge; the rest render as today.
- [ ] **Step 2:** Vitest: partition + badges. Commit: `feat(queue): backlog section for returned and reopened complaints (R12)`.

### Task 9.4: Admin complaints screen rewrite

**Files:** `frontend/src/pages/AdminDashboard/Complaints.jsx` (281 lines, rewrite in place), `createComplaintsSlice.js` (shrink), `AdminDashboard/DepartmentDetail.jsx`.

- [ ] **Step 1:** Rewrite the detail flow on react-query: list stays on the snapshot slice (it is real data); opening a complaint fetches `GET /complaints/{id}` (staff read) and renders the **real** timeline (via `ComplaintTracker` + the rendered event list) instead of the client-invented events; the PATCH + comment mutations invalidate that query. Delete the invented-event code paths from `createComplaintsSlice.js`.
- [ ] **Step 2:** Delete `assigneeStaffId`/`assignee` optimistic writes from the slice; in `DepartmentDetail.jsx`, replace the “Assign to staff” dropdown with a “Raise work order” link to `/admin/departments/:id/work-orders?complaint=:complaintId` (the triage screen; it already deep-links by query param — reuse the `?job=` pattern for a `?complaint=` preselect on the raise-work tab) (R13).
- [ ] **Step 3:** Vitest updates for the screen. Commit: `refactor(admin): complaints detail reads the truth; assign control keeps one meaning (R13)`.

---

## Phase 10 — Docs, diagrams, reconciliation

### Task 10.1: Diagrams and design docs

- [ ] ERD (`docs/erd/`): `complaints.skill_id`, `returned_to_pool_at`; `work_order_assignments.is_forced`; `work_orders.cancelled_by`; `dispatch_tasks.complaint_id`. Rerender per `docs/erd/README.md`.
- [ ] Class diagram (`docs/class-diagram/`): new RPCs/service methods per its README's conventions.
- [ ] `docs/design-of-components.md`: ComplaintTracker, candidate picker, cancel dialog entries.
- [ ] `docs/COMPLAINT_ENGINE_STATE.md`: update §10 worklist (items 1, 2, 4, 5, 7, 9-11 are now settled/built) with a pointer to the PRD; note at top that v2 is specified/being built.
- [ ] `docs/COMPLAINT_ENGINE_HANDOFF.md`: append §11 “Rulings, 2026-08-12” — the PRD §12 table, verbatim.
- [ ] `docs/CHANGE_LOG.md`: one line per artifact with reasons. Commit: `docs: complaint engine v2 reconciliation`.

---

## Phase 11 — The testing suite plan

Run order: unit (SQL) → API (mocked RPC) → integration (live Supabase) → frontend → workflow sweeps → regression.

### 11.1 SQL behaviour assertions (`backend/tests/integration/`)

Follow the house pattern (`assert_service_proximity_plan.sql` + the python drivers in `tests/integration/`): each block seeds inside a transaction against the local/branch database, asserts, rolls back. One file per phase, `assert_complaint_engine_v2_*.sql`:

**Routing (Phase 1):**
| # | Seed | Assert |
|---|---|---|
| S1 | skill held by exactly one active dept (department_skills) | `resolve_complaint_department` returns it |
| S2 | skill held by two depts | returns null (triage) |
| S3 | skill matching nothing, resident named valid dept | returns the named dept |
| S4 | stale/foreign dept id | returns null, complaint still created |
| S5 | `raise_complaint` with `p_skill_id` | `complaints.skill_id` set, `category` = skill name, `raised` payload carries `skill_id` |
| S6 | legacy 7-arg-style call (`p_skill_id` null, category text) | behaves byte-identical to pre-migration (no regression for old clients) |

**Consent + force (Phase 2):**
| # | Seed | Assert |
|---|---|---|
| S7 | supervisor calls `assign_work_order` | assignment `offered`, not `accepted`; job `offered`; worker notification row exists; open `auto_assign` task due +30min |
| S8 | second offer on same job | first offer `withdrawn` |
| S9 | worker accepts | `accepted`; `job_assigned` event; `dm_threads` row exists for the job with a system message; resident notified |
| S10 | worker accepts a withdrawn offer | HB409 |
| S11 | decline with reason | `declined` + reason; supervisor notified; excluded thereafter: `work_order_candidates` omits them, `p_include_excluded => true` shows `excluded = true` |
| S12 | decline without reason | refused (existing rule holds) |
| S13 | all candidates decline, priority high | one assignment `accepted, is_forced, is_auto_assigned`; best-ranked picked (seed two candidates with different loads, assert the lighter); `job_force_assigned` + `job_assigned` events; 3 notifications |
| S14 | all decline, priority medium | no forced row; supervisor 'all declined' notification |
| S15 | all candidates busy/away, priority high | no forced row; 'nobody available' notification (E9) |
| S16 | decline a forced assignment | HB409 (S13 setup) |
| S17 | overlapping accepted booking elsewhere | candidate absent from `work_order_candidates` (occupied invisible) |
| S18 | current leave block ending tomorrow, slot next week | candidate present with `away_until` = block end |

**Coupling + guards (Phase 3):**
| # | Seed | Assert |
|---|---|---|
| S19 | first offer on open complaint | complaint `acknowledged` |
| S20 | job starts | complaint `in_progress` |
| S21 | only live job completes | complaint `resolved`; auto-close tasks exist (48h/72h due) |
| S22 | job completes, sibling live | complaint unchanged (E20) |
| S23 | hand-set `closed`, then a (pre-existing) job event fires | complaint stays `closed` (forward-only, E28) |
| S24 | `create_work_order` on resolved/closed/cancelled complaint | HB409 (R14) |
| S25 | `assign_complaint_department` with live job | HB409; without → succeeds (R15/E29) |

**Cancel/repool (Phase 4):**
| # | Seed | Assert |
|---|---|---|
| S26 | raiser cancels mode=cancel pre-start | job `cancelled/cancelled_by=resident`; assignment `withdrawn`; complaint `cancelled`; thread `locked_at` set; worker+staff notified |
| S27 | mode=repool | complaint `open` + `returned_to_pool_at`; `returned_to_pool` event; queue row carries the flag; cancelled-on worker in `complaint_excluded_staff` |
| S28 | job already `in_progress` | HB409 with the office message (E12) |
| S29 | non-raiser calls | HB404 |
| S30 | new work order raised on repooled complaint | `returned_to_pool_at` cleared |

**Timers (Phase 5):**
| # | Seed | Assert |
|---|---|---|
| S31 | resident accepts slot (high) | `manual_window` task due ≈ +2h; no immediate `ping` |
| S32 | same, medium | due ≈ +24h |
| S33 | fire `manual_window` with an open offer | returns false, nothing changes (idempotency) |
| S34 | fire with no offers | `dispatch_ping_candidates` ran (offer rows exist); supervisor notified |
| S35 | fire `auto_close_warning` on still-resolved | warning notification + event; complaint still `resolved` |
| S36 | fire `auto_close` on still-resolved | `closed`, `auto_closed` event, no rating |
| S37 | fire either after confirm/reopen | 'skipped', untouched (E15/E16) |
| S38 | reopen after auto-close | works; complaint `open`; excluded staff includes prior worker (E18 + R12) |
| S39 | event type outside the registry | insert refused by CHECK (R19) |

### 11.2 API tests (pytest, `backend/tests/api/`)

Extend the existing per-router files with the new operations; the house style (monkeypatched service/RPC seam, role/CSRF matrices) applies:

- `test_resident_complaints.py`: raise-with-skill (Task 7.1); cancel 200/409/404/role/CSRF matrix; detail still renders (label additions don't break old events).
- `test_work_orders.py`: candidates 200 shape (camelCase `awayUntil`, `excluded`), 403 non-supervisor, `includeExcluded` passthrough; assign docstring/status unchanged (409s pass through).
- `test_complaints.py`: staff detail 200 admin / 200 dept-supervisor / 404 stranger-same-shape; timeline labels rendered; internal shadows present for staff.
- `test_notifications.py` + `test_notification_links.py`: new notification types resolve to real routes through `portalNotificationUrl`'s contract (extend the link-audit table with `job.offered`, `job.fallback_started`, `job.all_declined`, `complaint.job_cancelled_by_resident`, auto-close pair).
- `test_openapi_spec.py`: regenerated spec contains the three new operations (this suite fails loudly if docs discipline was skipped).

### 11.3 Frontend (vitest)

- `trackerProjection.test.js` — the five projection tests of Task 8.2 plus: unknown event type is preserved raw; empty events → all pending.
- Raise dialog: submits `skillId`; skills grouped by `optgroup`.
- Cancel dialog: two modes call the API with the right body; 409 renders server message.
- Candidate picker: default hides excluded; toggle shows greyed rows; away-until renders.
- Backlog partition: returned/reopened rows separate with badges.
- Admin detail: timeline rendered from fetched events, not invented ones (assert the invented-path helpers are gone).
- Worker: forced badge branch; decline hidden.

### 11.4 Workflow sweeps (integration, live dev Supabase, `backend/tests/integration/test_complaint_workflows.py`)

Eight end-to-end scripts, each one seeded community + real RPC calls in sequence, asserting complaint status, events, notifications and tracker-visible facts after every step:

1. **Happy path:** raise(skill) → route → supervisor slot → resident accept → offer → accept → chat exists → reschedule → start → complete → resolved → rate → closed.
2. **Decline-reassign:** offer → decline → excluded → second offer → accept → …
3. **All-declined critical:** high, two candidates, both decline → forced on best-ranked → cannot decline → complete → resolved.
4. **All-declined medium:** both decline → no force → supervisor notified → manual re-offer to a decliner (override) → accept.
5. **Cancel-repool:** accept → resident repool → backlog flag → new slot → new offer to *other* worker → complete → resolved → auto-close (fire tasks manually) → reopen.
6. **Cancel-entirely:** accept → cancel → complaint cancelled → chat locked → new complaint needed.
7. **Fallback:** resident accepts slot → nobody offers → fire manual_window → engine offers → fire auto_assign → assigned → complete.
8. **Failed visit:** accept → start → failure(reason) → escalation fires → complaint still in_progress → second job → complete → resolved.

### 11.5 Regression

- Full `python -m pytest backend/tests -q` and `npx vitest run` after every phase (the phase gates above).
- The dispatcher loop untouched: `backend/tests` dispatcher/push suites pass unmodified — treat any needed change there as a design smell to investigate, not to patch.
- Amenities, visitors, payments, hiring, messages suites: no file this plan touches feeds them except `vocabularies.py` (additive) and `service_providers.py` (possible guard loosening in Task 8.1) — run their suites explicitly after Phases 7–8.
- Migration apply: run the six new files against a Supabase branch database in order, then re-run 11.1. The hosted apply follows `docs/plans/MIGRATION_APPLY_RUNBOOK.md` conventions (owner applies by hand; every file ends in post-checks).

---

## Self-review notes (kept honest)

- **Spec coverage:** PRD §3.1→Phase 1+8.1; §5.1→Phase 1 (routing) + notify change (folded into Phase 1 Step 3's rebuilt raise via `notify_complaint_staff` recipient CTE — *add supervisors there*, one `-- CHANGED` union arm; test S-extra: raise notifies supervisor); §5.3→2.1; §5.4→2.1; §5.5/5.6→2.1 S13–S16; §5.8→5.1; §6→3.1+8.2; §7→6.1; §8.1→4.1+8.3; §8.2→5.1; §8.3→4.1+9.3; §8.5/8.6→3.1; §9→2.1 S17/S18+9.1; §10→spread, link-audit in 11.2; §11→RPC guards throughout.
- **Known deliberate cuts (ponytail):** no separate `offer_timeout` task kind (the existing `auto_assign` timer already is one); no slot-excluded-workers listing in the picker; no priority re-inheritance (E31, out of scope); `CategoryPicker` left alive for departments.
- **The riskiest task is 1.1 Step 2** (routing rewrite): S1–S6 exist precisely to fence it, and S6 pins legacy behaviour byte-for-byte.
