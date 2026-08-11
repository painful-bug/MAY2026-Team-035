-- The job: turning a triaged complaint into a visit by a named person at a
-- named time.
--
-- 0001 created work_orders and work_order_assignments and then never touched
-- them again -- no index, no policy, no function, no Python. CONFLICT_RESOLUTIONS
-- R16 parked them deliberately: "keep all 12, tag each Phase 2, and build
-- nothing against them." This file un-parks those two, and says so here because
-- design/README.md requires a ruling that overturns something already written to
-- name what it overturned.
--
-- CORRECTED 2026-08-11 -- THE THREE WORKER NOTIFICATION LINKS
--
-- `work_order.rescheduled`, `.assigned` and `.cancelled` all carried
-- `url = '/worker/jobs/<id>'`. The worker portal has no `jobs` route and never
-- had one: it is `/worker` (the day's work), `calendar`, `availability`,
-- `communities`, `messages`, `profile` and `settings`, and a job opens in
-- `JobDetailModal` over the top of the first of those. `App.jsx`'s catch-all
-- turned all three into a trip to the marketing page.
--
-- They now say `/worker?job=<id>`, which `WorkerDashboardHome` reads. The modal
-- fetches `GET /worker/jobs/{id}` for itself, so the link resolves for any job
-- the worker holds and not only one already on the screen. `0037` carried the
-- same defect in a second spelling (`/worker/jobs?job=`) and was corrected with
-- it. See `docs/potential issues/README.md` for how the whole set was found.
--
-- WHAT THIS FILE DELIBERATELY DOES NOT CONTAIN
--
-- No dispatch_tasks table and no timers. The approved plan describes triage as
-- "enqueues a resident_timeout task 24h out"; that table and the loop that
-- drains it are the next step. Building half of them here would leave rows that
-- nothing reads and a queue that nothing services -- the failure mode where a
-- feature looks present and is not.
--
-- The consequence is a rule this file is arranged around: EVERY TRANSITION THE
-- ENGINE WILL LATER MAKE AUTOMATICALLY IS REACHABLE BY HAND FIRST. That is not
-- a nicety. A state machine whose only exit from a state is a background job is
-- a state machine nobody can test, and the first time it wedges in production
-- there is no lever to pull. Where a manual lever exists specifically because
-- the engine does not yet, it is marked at the function.
--
-- THREE STATUSES ARE DECLARED AND NOT YET REACHABLE
--
-- in_progress, completed and failed are in the CHECK and nothing in this file
-- writes them: they belong to the worker, and the worker's endpoints are step 6.
-- They are declared now rather than in a later constraint edit because the
-- vocabulary is one line and splitting it across two migrations would mean
-- dropping and re-adding the constraint to add three words. Their absence from
-- the writes below is intentional and not an omission.
--
-- WHY A COMPLAINT MAY HAVE MANY WORK ORDERS
--
-- A failed visit is rescheduled and a reopened complaint goes to a different
-- supervisor. Both are a second work order against one complaint, which is why
-- the assignment lives here and not in a column on complaints. The alternative
-- -- assignee columns on complaints -- is a smaller change and would also close
-- DECISIONS_NEEDED B2, but one complaint could then only ever have one
-- scheduled visit, and the second visit is the one that matters.
--
-- THE ONE CONSTRAINT THIS FILE EXISTS TO CARRY
--
-- work_order_assignments_no_overlap. A person cannot be in two places at once,
-- and the schema is where that is said, not the application. This is the same
-- construct amenity_bookings has carried since the baseline -- the same problem
-- gets the same solution rather than a new one -- and it is already drawn in
-- docs/erd/homebandhu.dbml:614, where it has waited to exist.
--
-- The partial predicate is the part worth reading twice: it covers only
-- `accepted` rows. An OFFERED assignment must be allowed to overlap, because
-- step 5 asks several workers and only one of them accepts. Constrain the
-- offers and the dispatcher can only ever ask one person at a time, which
-- defeats the point of asking.
--
-- WHY THERE IS NO PROPOSED-SLOTS COLUMN AND NO SLOT-OPTIONS TABLE
--
-- A supervisor proposes by writing one slot with status awaiting_resident; the
-- resident confirms and it becomes offered; a different time is a reschedule,
-- which is a lever the supervisor already has. No jsonb list, no table holding
-- two rows that are read once and discarded. If it later turns out residents
-- must choose between alternatives, that is a table then -- and it will be a
-- table with a reason.
--
-- WHY THE TIMELINE IS complaint_events AND NOT work_order_events
--
-- 0020 built a general audit trail that already renders to prose, and
-- resident_complaints_service.py already strips internal events from what a
-- resident sees. A parallel table would need its own view, its own renderer and
-- its own RLS, and would split one complaint's story across two timelines. This
-- is also cheaper than the plan assumed: complaint_events.event_type is `text`
-- with no CHECK (0001:70), so the new event types need no migration at all.
--
-- A THIRD VOCABULARY COLLISION, FIXED IN PASSING
--
-- work_orders.priority defaults to 'normal' and is unconstrained, while
-- complaints.priority is checked against low|medium|high and 0031's header
-- already notes that `priority` is the admin's word for the frontend's
-- `urgency`. Two names for one idea is what 0031 refused; two value sets for
-- one name is the same defect one level down. The check and the default are
-- corrected here, and create_work_order inherits the complaint's priority
-- rather than inventing one -- a job's urgency is the complaint's urgency, and
-- nobody should have to keep them in sync by hand.

-- ---------------------------------------------------------------------------
-- 1. The job
--
-- Additive alters on the dead baseline table, exactly as 0019 extended
-- departments. Six columns today, seventeen after this.
-- ---------------------------------------------------------------------------

-- `department_id` carries no inline `references` clause, and that is the point.
-- The composite tenant FK below is the only foreign key on this column: two
-- constraints over one column would fire two referential actions on one
-- department delete, and there is no ordering between them worth relying on.
alter table public.work_orders
  add column if not exists department_id            uuid,
  add column if not exists supervisor_membership_id uuid
    references public.community_memberships(id) on delete set null,
  add column if not exists skill_id                 uuid
    references public.skills(id) on delete set null,
  add column if not exists scheduled_start_at       timestamptz,
  add column if not exists scheduled_end_at         timestamptz,
  add column if not exists subject_kind             text not null default 'resident',
  add column if not exists location_text            text,
  add column if not exists latitude                 numeric(9,6),
  add column if not exists longitude                numeric(9,6),
  add column if not exists failed_attempt_count     smallint not null default 0,
  add column if not exists resident_deadline_at     timestamptz,
  add column if not exists cancelled_reason         text;

alter table public.work_orders alter column status set default 'draft';
alter table public.work_orders alter column priority set default 'medium';

do $$
begin
  -- The baseline default was 'open', which is not in the vocabulary below. No
  -- migration in this directory has ever been applied to any database (see the
  -- README), so this UPDATE is a no-op today and the difference between a clean
  -- apply and a failed one if that ever stops being true.
  update public.work_orders set status = 'draft' where status = 'open';
  update public.work_orders set priority = 'medium' where priority = 'normal';

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.work_orders'::regclass
       and conname  = 'work_orders_status_check'
  ) then
    alter table public.work_orders
      add constraint work_orders_status_check
      check (status in (
        'draft', 'awaiting_resident', 'offered', 'scheduled',
        'in_progress', 'completed', 'failed', 'cancelled'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.work_orders'::regclass
       and conname  = 'work_orders_priority_check'
  ) then
    alter table public.work_orders
      add constraint work_orders_priority_check
      check (priority in ('low', 'medium', 'high'));
  end if;

  -- A job is at a resident's home or it is not. Which one decides whether
  -- anybody has to confirm the time: there is no one to ask about a burst pipe
  -- in the basement.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.work_orders'::regclass
       and conname  = 'work_orders_subject_kind_check'
  ) then
    alter table public.work_orders
      add constraint work_orders_subject_kind_check
      check (subject_kind in ('resident', 'facility'));
  end if;

  -- Both ends or neither, and forward in time. Half a slot is the shape that
  -- silently disables the overlap constraint further down, which is checked on
  -- (start, end) and does nothing when start is null.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.work_orders'::regclass
       and conname  = 'work_orders_slot_check'
  ) then
    alter table public.work_orders
      add constraint work_orders_slot_check
      check (
        (scheduled_start_at is null and scheduled_end_at is null)
        or (scheduled_start_at is not null
            and scheduled_end_at is not null
            and scheduled_end_at > scheduled_start_at));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.work_orders'::regclass
       and conname  = 'work_orders_failed_attempts_check'
  ) then
    alter table public.work_orders
      add constraint work_orders_failed_attempts_check
      check (failed_attempt_count >= 0);
  end if;

  -- The department and the row must agree on the community, so a cross-tenant
  -- work order is unrepresentable rather than merely forbidden. Same shape as
  -- service_applications_department_tenant_fkey (0035) and
  -- staff_assignments_department_tenant_fkey (0019), down to the action.
  --
  -- `cascade` rather than `set null`, and not by taste. A multi-column
  -- `on delete set null` nulls *every* referencing column, including
  -- `community_id`, which the baseline declares `not null` (0001:73) -- so the
  -- gentler-looking action is the one that raises 23502 and refuses to delete
  -- the department at all. It would also collide with the community cascade:
  -- dropping a community deletes its departments and its work orders, and
  -- nothing orders those two against each other. The complaint keeps the story
  -- either way, because the timeline lives in `complaint_events`.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.work_orders'::regclass
       and conname  = 'work_orders_department_tenant_fkey'
  ) then
    alter table public.work_orders
      add constraint work_orders_department_tenant_fkey
      foreign key (department_id, community_id)
      references public.departments (id, community_id)
      on delete cascade;
  end if;
end $$;

-- The supervisor's queue: this department, open first, soonest first.
create index if not exists work_orders_department_idx
  on public.work_orders (department_id, status, scheduled_start_at);

create index if not exists work_orders_complaint_idx
  on public.work_orders (complaint_id);

-- What step 5 sweeps: jobs whose resident has been asked and has not answered.
create index if not exists work_orders_resident_deadline_idx
  on public.work_orders (resident_deadline_at)
  where status = 'awaiting_resident' and resident_deadline_at is not null;

drop trigger if exists work_orders_set_updated_at on public.work_orders;
create trigger work_orders_set_updated_at
  before update on public.work_orders
  for each row execute function public.set_updated_at();

comment on column public.work_orders.subject_kind is
  'resident | facility. A resident job needs the resident to confirm the time; '
  'a facility job has nobody to ask and goes straight to offered.';

comment on column public.work_orders.resident_deadline_at is
  'When an unanswered schedule request stops being worth waiting for. Written '
  'at proposal time and read by the dispatcher; until step 5 exists, the '
  'supervisor''s assign is the hand-operated form of that timeout.';

-- ---------------------------------------------------------------------------
-- 2. Who is doing it, and when
--
-- The baseline row records that somebody was assigned. It does not record
-- whether they agreed, when they were asked, or what time they are expected --
-- which is everything a dispatch engine needs and everything a calendar shows.
-- ---------------------------------------------------------------------------

alter table public.work_order_assignments
  add column if not exists status             text not null default 'offered',
  add column if not exists offered_at         timestamptz not null default now(),
  add column if not exists responded_at       timestamptz,
  add column if not exists decline_reason     text,
  add column if not exists is_auto_assigned   boolean not null default false,
  add column if not exists scheduled_start_at timestamptz,
  add column if not exists scheduled_end_at   timestamptz;

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.work_order_assignments'::regclass
       and conname  = 'work_order_assignments_status_check'
  ) then
    alter table public.work_order_assignments
      add constraint work_order_assignments_status_check
      check (status in (
        'offered', 'accepted', 'declined', 'withdrawn', 'completed', 'failed'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.work_order_assignments'::regclass
       and conname  = 'work_order_assignments_slot_check'
  ) then
    alter table public.work_order_assignments
      add constraint work_order_assignments_slot_check
      check (
        (scheduled_start_at is null and scheduled_end_at is null)
        or (scheduled_start_at is not null
            and scheduled_end_at is not null
            and scheduled_end_at > scheduled_start_at));
  end if;

  -- The constraint this file exists to carry. See the header for why the WHERE
  -- clause is the interesting half.
  --
  -- btree_gist is required and is not a new requirement: 0001:7 installs it and
  -- 0001:81 already declares `exclude using gist (amenity_id with =, ...)`,
  -- which is a btree operator class inside a GiST index and cannot exist
  -- without it. If the extension were unavailable there would be no baseline,
  -- let alone this file.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.work_order_assignments'::regclass
       and conname  = 'work_order_assignments_no_overlap'
  ) then
    alter table public.work_order_assignments
      add constraint work_order_assignments_no_overlap
      exclude using gist (
        staff_assignment_id with =,
        tstzrange(scheduled_start_at, scheduled_end_at, '[)') with &&
      ) where (status = 'accepted' and scheduled_start_at is not null);
  end if;
end $$;

create index if not exists work_order_assignments_work_order_idx
  on public.work_order_assignments (work_order_id, status);

-- The worker's calendar, in one index: my accepted jobs, in time order.
create index if not exists work_order_assignments_staff_slot_idx
  on public.work_order_assignments (staff_assignment_id, scheduled_start_at)
  where status = 'accepted';

comment on constraint work_order_assignments_no_overlap
  on public.work_order_assignments is
  'One person, one place, one time. Partial on status = accepted so that step '
  '5 may offer the same slot to several workers and let exactly one of them '
  'take it.';

-- ---------------------------------------------------------------------------
-- 3. When a worker is available
--
-- Two more tables the baseline created and nothing ever used. Both key on
-- staff_assignment_id, which is per-department -- fine for a name typed onto a
-- roster, wrong for a registered service person, whose leave is not a fact
-- about one of their four communities.
--
-- So: a nullable service_provider_id beside it, exactly one of the two set.
-- num_nonnulls rather than the naive spelling, because the failure worth
-- catching is BOTH being set -- a rule that is global and per-department at
-- once has no defined meaning.
--
-- Nothing reads these until step 6 puts endpoints on them. They are here rather
-- than in a later file because this is the migration that owns worker
-- scheduling, and a second migration adding two columns to two tables is a
-- second migration for no gain.
-- ---------------------------------------------------------------------------

alter table public.worker_availability_rules
  add column if not exists service_provider_id uuid
    references public.service_providers(id) on delete cascade;
alter table public.worker_availability_rules
  alter column staff_assignment_id drop not null;

alter table public.worker_unavailability
  add column if not exists service_provider_id uuid
    references public.service_providers(id) on delete cascade;
alter table public.worker_unavailability
  alter column staff_assignment_id drop not null;
alter table public.worker_unavailability
  add column if not exists created_at timestamptz not null default now();

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.worker_availability_rules'::regclass
       and conname  = 'worker_availability_rules_one_subject'
  ) then
    alter table public.worker_availability_rules
      add constraint worker_availability_rules_one_subject
      check (num_nonnulls(staff_assignment_id, service_provider_id) = 1);
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.worker_availability_rules'::regclass
       and conname  = 'worker_availability_rules_window_check'
  ) then
    alter table public.worker_availability_rules
      add constraint worker_availability_rules_window_check
      check (end_time > start_time);
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.worker_unavailability'::regclass
       and conname  = 'worker_unavailability_one_subject'
  ) then
    alter table public.worker_unavailability
      add constraint worker_unavailability_one_subject
      check (num_nonnulls(staff_assignment_id, service_provider_id) = 1);
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.worker_unavailability'::regclass
       and conname  = 'worker_unavailability_window_check'
  ) then
    alter table public.worker_unavailability
      add constraint worker_unavailability_window_check
      check (ends_at > starts_at);
  end if;
end $$;

create index if not exists worker_unavailability_provider_idx
  on public.worker_unavailability (service_provider_id, starts_at)
  where service_provider_id is not null;

create index if not exists worker_availability_rules_provider_idx
  on public.worker_availability_rules (service_provider_id, weekday)
  where service_provider_id is not null;

-- ---------------------------------------------------------------------------
-- 4. Who may do what
--
-- Three predicates, each defined once and used by both the policies in section
-- 7 and the functions in section 6. A rule spelled one way in a policy and
-- another way in the function that writes past it is how a hole opens.
-- ---------------------------------------------------------------------------

-- A supervisor is a RANK on a roster row, not a membership role. 0035 settled
-- the vocabulary at manager | supervisor | member; can_manage_department covers
-- the first and the community's admins, and this adds the second.
--
-- Supervisors are why this predicate exists at all: triage is their job, and
-- can_manage_department would hand it to managers only.
create or replace function public.can_supervise_department(p_department_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.can_manage_department(p_department_id)
      or exists (
           select 1
             from public.staff_assignments sa
             join public.community_memberships m on m.id = sa.membership_id
            where sa.department_id = p_department_id
              and sa.status = 'active'
              and sa.rank in ('manager', 'supervisor')
              and m.profile_id = auth.uid()
              and m.status = 'active'
              and m.ended_at is null
         );
$$;

comment on function public.can_supervise_department(uuid) is
  'True when the caller may triage, schedule, assign or cancel work for this '
  'department: whoever can_manage_department admits, plus its supervisors.';

-- Is this roster row the caller? Either half may identify them: a hired service
-- person is reachable through their membership and through their provider row,
-- and a roster name typed into the departments form is reachable through
-- neither -- which is correct, because that person has no account.
create or replace function public.is_own_staff_assignment(p_staff_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
      from public.staff_assignments sa
      left join public.community_memberships m on m.id = sa.membership_id
      left join public.service_providers p     on p.id = sa.service_provider_id
     where sa.id = p_staff_id
       and (m.profile_id = auth.uid() or p.profile_id = auth.uid())
  );
$$;

comment on function public.is_own_staff_assignment(uuid) is
  'True when this roster row belongs to the caller, by membership or by service '
  'provider record.';

-- Four populations can see a work order, and they see it for four different
-- reasons: the community's admins, the department's supervisors, the worker
-- holding an assignment on it, and the resident whose complaint it answers.
--
-- SECURITY DEFINER, so the policy in section 7 can call this against the very
-- table the policy protects without recursing.
create or replace function public.can_read_work_order(p_work_order_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
      from public.work_orders w
      left join public.complaints c on c.id = w.complaint_id
     where w.id = p_work_order_id
       and (
         public.is_community_admin(w.community_id)
         or public.can_supervise_department(w.department_id)
         or public.is_own_membership(c.raised_by_membership_id)
         or exists (
              select 1
                from public.work_order_assignments a
               where a.work_order_id = w.id
                 and public.is_own_staff_assignment(a.staff_assignment_id)
            )
       )
  );
$$;

comment on function public.can_read_work_order(uuid) is
  'The read rule for a job, stated once: an admin of its community, a '
  'supervisor of its department, a worker assigned to it, or the resident who '
  'raised the complaint behind it.';

grant execute on function public.can_supervise_department(uuid) to authenticated;
grant execute on function public.is_own_staff_assignment(uuid) to authenticated;
grant execute on function public.can_read_work_order(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 5. Reads
--
-- security_invoker on both, like every view in this schema, so section 7
-- decides what a caller sees rather than the view's owner.
-- ---------------------------------------------------------------------------

drop view if exists public.work_order_overview;
create view public.work_order_overview
with (security_invoker = true) as
select
  w.id,
  w.community_id,
  w.complaint_id,
  w.department_id,
  w.supervisor_membership_id,
  w.skill_id,
  w.status,
  w.priority,
  w.subject_kind,
  w.location_text,
  w.latitude,
  w.longitude,
  w.scheduled_start_at,
  w.scheduled_end_at,
  w.resident_deadline_at,
  w.failed_attempt_count,
  w.cancelled_reason,
  w.created_at,
  w.updated_at,
  c.title                      as complaint_title,
  c.category                   as complaint_category,
  c.status::text               as complaint_status,
  c.raised_by_membership_id    as resident_membership_id,
  d.name                       as department_name,
  d.kind                       as department_kind,
  s.name                       as skill_name,
  -- The current holder. One accepted assignment at a time is a rule the
  -- functions in section 6 keep rather than the schema, so the lateral takes
  -- the newest and the ordering is what makes it deterministic.
  a.assignment_id,
  a.staff_assignment_id,
  a.assignment_status,
  a.assignee_name,
  a.assignee_membership_id,
  a.assignee_provider_id
from public.work_orders w
left join public.complaints  c on c.id = w.complaint_id
left join public.departments d on d.id = w.department_id
left join public.skills      s on s.id = w.skill_id
left join lateral (
  select
    woa.id                as assignment_id,
    woa.staff_assignment_id,
    woa.status            as assignment_status,
    sa.display_name       as assignee_name,
    sa.membership_id      as assignee_membership_id,
    sa.service_provider_id as assignee_provider_id
    from public.work_order_assignments woa
    left join public.staff_assignments sa on sa.id = woa.staff_assignment_id
   where woa.work_order_id = w.id
     and woa.status = 'accepted'
   order by woa.offered_at desc
   limit 1
) a on true;

comment on view public.work_order_overview is
  'A job with its complaint, its department, its skill and whoever currently '
  'holds it. One row per work order; the assignee is the accepted assignment, '
  'or null while nobody has taken it.';

grant select on public.work_order_overview to authenticated;

drop view if exists public.work_order_assignment_overview;
create view public.work_order_assignment_overview
with (security_invoker = true) as
select
  a.id,
  a.work_order_id,
  a.staff_assignment_id,
  a.status,
  a.offered_at,
  a.responded_at,
  a.decline_reason,
  a.is_auto_assigned,
  a.scheduled_start_at,
  a.scheduled_end_at,
  a.assigned_at,
  a.ended_at,
  w.community_id,
  w.department_id,
  w.complaint_id,
  w.status                as work_order_status,
  w.priority              as work_order_priority,
  w.subject_kind,
  w.location_text,
  sa.display_name         as worker_name,
  sa.phone_e164           as worker_phone_e164,
  sa.membership_id        as worker_membership_id,
  sa.service_provider_id  as worker_provider_id
from public.work_order_assignments a
join public.work_orders w on w.id = a.work_order_id
left join public.staff_assignments sa on sa.id = a.staff_assignment_id;

comment on view public.work_order_assignment_overview is
  'Every offer and acceptance, with the job it belongs to and the person it was '
  'made to. The worker''s job list and the supervisor''s assignment history are '
  'the same rows read from opposite sides.';

grant select on public.work_order_assignment_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 6. Writes
--
-- Every one is SECURITY DEFINER and checks its own authorization, matching the
-- posture 0031 established and 0034, 0035 and 0038 kept: the tables carry read
-- policies and no write policy at all, so there is no path from the API process
-- to a row these functions did not write.
--
-- The custom SQLSTATEs are the house ones -- HB403, HB404, HB409 -- which
-- app/core/pg_errors.py maps to 403, 404 and 409 and whose messages it passes
-- through to the caller. Everything raised here is therefore written to be read
-- by a person.
-- ---------------------------------------------------------------------------

-- Supervisor triage. The fork the whole feature turns on: no slot means the
-- complaint stays a conversation (complaint_comments, unchanged), a slot means
-- a visit is being proposed.
create or replace function public.create_work_order(
  p_complaint_id       uuid,
  p_department_id      uuid default null,
  p_skill_id           uuid default null,
  p_subject_kind       text default 'resident',
  p_location_text      text default null,
  p_scheduled_start_at timestamptz default null,
  p_scheduled_end_at   timestamptz default null,
  p_note               text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_complaint   public.complaints%rowtype;
  v_department  uuid;
  v_actor       uuid;
  v_kind        text := coalesce(nullif(btrim(coalesce(p_subject_kind, '')), ''),
                                 'resident');
  v_status      text;
  v_deadline    timestamptz;
  v_id          uuid;
begin
  select * into v_complaint from public.complaints where id = p_complaint_id;
  if not found then
    raise exception 'No such complaint.' using errcode = 'HB404';
  end if;

  -- The complaint already names a department in most cases; the parameter is
  -- for the case where triage is what decides which department owns it.
  v_department := coalesce(p_department_id, v_complaint.department_id);
  if v_department is null then
    raise exception 'This complaint has no department to schedule work against.'
      using errcode = 'HB409';
  end if;

  if not public.can_supervise_department(v_department) then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;

  -- A supervisor of a department in another community must not be able to
  -- attach work to this complaint by naming their own department. The tenant
  -- foreign key would catch it on insert; this catches it with a sentence.
  if not exists (
    select 1 from public.departments
     where id = v_department and community_id = v_complaint.community_id
  ) then
    raise exception 'That department belongs to another community.'
      using errcode = 'HB403';
  end if;

  if (p_scheduled_start_at is null) <> (p_scheduled_end_at is null) then
    raise exception 'A proposed time needs both a start and an end.'
      using errcode = '22004';
  end if;

  if p_scheduled_start_at is not null
     and p_scheduled_end_at <= p_scheduled_start_at then
    raise exception 'A visit must end after it starts.' using errcode = '22004';
  end if;

  -- draft: nothing proposed, the complaint is still a conversation.
  -- awaiting_resident: a time was proposed for a job at their home.
  -- offered: a time was proposed for a facility job, which nobody confirms.
  if p_scheduled_start_at is null then
    v_status := 'draft';
  elsif v_kind = 'resident' then
    v_status   := 'awaiting_resident';
    v_deadline := now() + interval '24 hours';
  else
    v_status := 'offered';
  end if;

  select id into v_actor
    from public.community_memberships
   where community_id = v_complaint.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null;

  insert into public.work_orders (
    community_id, complaint_id, department_id, supervisor_membership_id,
    skill_id, status, priority, subject_kind, location_text,
    scheduled_start_at, scheduled_end_at, resident_deadline_at
  )
  values (
    v_complaint.community_id, v_complaint.id, v_department, v_actor,
    -- The skill is derivable and is derived: 0034 gave complaint_categories a
    -- skill_id precisely so nobody has to answer "which trade is this" twice.
    -- Matched the way complaint_categories_community_name_key indexes it --
    -- lower(btrim(name)) -- rather than on the raw string, which would miss on
    -- a category typed with different capitalisation.
    coalesce(p_skill_id, (select cc.skill_id
                            from public.complaint_categories cc
                           where cc.community_id = v_complaint.community_id
                             and lower(btrim(cc.name))
                                 = lower(btrim(coalesce(v_complaint.category, '')))
                           limit 1)),
    v_status, v_complaint.priority, v_kind,
    coalesce(nullif(btrim(coalesce(p_location_text, '')), ''), v_complaint.location),
    p_scheduled_start_at, p_scheduled_end_at, v_deadline
  )
  returning id into v_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_complaint.id, v_actor,
    case when p_scheduled_start_at is null then 'job_created'
         else 'job_scheduled' end,
    jsonb_build_object(
      'workOrderId', v_id,
      'startsAt', p_scheduled_start_at,
      'endsAt', p_scheduled_end_at,
      'note', nullif(btrim(coalesce(p_note, '')), ''))
  );

  -- D9: an offer that expires and requires an action is not the passive field
  -- change ARCHITECTURE.md's rule was written to suppress. A draft work order
  -- notifies nobody, because nothing has been asked of anyone yet.
  if v_status = 'awaiting_resident' then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.schedule_requested',
      jsonb_build_object(
        'title', 'A visit has been proposed',
        'body', v_complaint.title,
        'url', '/resident/complaints?complaint=' || v_complaint.id::text,
        'complaint_id', v_complaint.id,
        'work_order_id', v_id,
        'starts_at', p_scheduled_start_at,
        'ends_at', p_scheduled_end_at));
  end if;

  return v_id;
end;
$$;

-- The resident's answer. The only write in this file a resident may make, and
-- the reason it is separate from every other one: the authorization question
-- here is "did you raise this complaint", which no other function asks.
create or replace function public.respond_to_work_order_schedule(
  p_work_order_id uuid,
  p_response      text,
  p_note          text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order    public.work_orders%rowtype;
  v_resident uuid;
  v_answer   text := lower(btrim(coalesce(p_response, '')));
begin
  if v_answer not in ('confirmed', 'declined') then
    raise exception 'Unknown response.' using errcode = '22004';
  end if;

  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such work order.' using errcode = 'HB404';
  end if;

  select raised_by_membership_id into v_resident
    from public.complaints where id = v_order.complaint_id;

  if not public.is_own_membership(v_resident) then
    raise exception 'This visit was not proposed to you.' using errcode = 'HB403';
  end if;

  if v_order.status <> 'awaiting_resident' then
    raise exception 'This visit is no longer waiting on you.'
      using errcode = 'HB409';
  end if;

  if v_answer = 'confirmed' then
    update public.work_orders
       set status = 'offered', resident_deadline_at = null, updated_at = now()
     where id = v_order.id;
  else
    -- Back to draft, and the slot goes with it. Leaving a declined time on the
    -- row would leave a calendar entry for a visit nobody agreed to.
    update public.work_orders
       set status               = 'draft',
           scheduled_start_at   = null,
           scheduled_end_at     = null,
           resident_deadline_at = null,
           updated_at           = now()
     where id = v_order.id;
  end if;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_resident,
    case when v_answer = 'confirmed' then 'job_scheduled' else 'job_declined' end,
    jsonb_build_object(
      'workOrderId', v_order.id,
      'startsAt', v_order.scheduled_start_at,
      'endsAt', v_order.scheduled_end_at,
      'note', nullif(btrim(coalesce(p_note, '')), ''))
  );

  -- Straight to the supervisor who proposed it, not to every admin: they asked
  -- the question and they are the one who has to act on the answer. If the
  -- proposal came from an admin with no membership row on the order -- possible
  -- only if that membership was later ended -- the department's managers get it
  -- instead, so an answer is never delivered to nobody.
  if v_order.supervisor_membership_id is not null then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.resident_' || v_answer,
      jsonb_build_object(
        'workOrderId', v_order.id,
        'complaintId', v_order.complaint_id,
        'startsAt', v_order.scheduled_start_at));
  else
    perform public.notify_community_staff(
      v_order.community_id, 'work_order.resident_' || v_answer,
      jsonb_build_object(
        'workOrderId', v_order.id,
        'complaintId', v_order.complaint_id));
  end if;
end;
$$;

-- Descriptive edits: what the job is, where it is, how urgent. Not the status
-- and not the time -- those have their own functions, because each of them has
-- a rule and a notification attached and a general-purpose UPDATE is where
-- those get skipped.
create or replace function public.update_work_order(
  p_work_order_id uuid,
  p_skill_id      uuid default null,
  p_subject_kind  text default null,
  p_location_text text default null,
  p_priority      text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order public.work_orders%rowtype;
begin
  select * into v_order from public.work_orders where id = p_work_order_id;
  if not found then
    raise exception 'No such work order.' using errcode = 'HB404';
  end if;

  if not public.can_supervise_department(v_order.department_id) then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;

  if v_order.status in ('completed', 'cancelled') then
    raise exception 'This job is closed.' using errcode = 'HB409';
  end if;

  update public.work_orders
     set skill_id      = coalesce(p_skill_id, skill_id),
         subject_kind  = coalesce(
                           nullif(btrim(coalesce(p_subject_kind, '')), ''),
                           subject_kind),
         location_text = case when p_location_text is not null
                              then nullif(btrim(p_location_text), '')
                              else location_text end,
         priority      = coalesce(
                           nullif(btrim(coalesce(p_priority, '')), ''), priority),
         updated_at    = now()
   where id = p_work_order_id;
end;
$$;

-- Move the visit. The supervisor's alone, and deliberately so: once a worker
-- has been booked, a time change is a change to two people's days, and the
-- resident asking for one is a message to the supervisor rather than a write.
--
-- The accepted assignment moves with it, which is what re-checks
-- work_order_assignments_no_overlap -- rescheduling onto a slot the worker
-- already has is the same double-booking as assigning them there.
create or replace function public.reschedule_work_order(
  p_work_order_id      uuid,
  p_scheduled_start_at timestamptz,
  p_scheduled_end_at   timestamptz,
  p_note               text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order    public.work_orders%rowtype;
  v_actor    uuid;
  v_assigned public.work_order_assignments%rowtype;
  v_status   text;
  v_deadline timestamptz;
  v_resident uuid;
begin
  if p_scheduled_start_at is null or p_scheduled_end_at is null then
    raise exception 'A visit needs both a start and an end.' using errcode = '22004';
  end if;

  if p_scheduled_end_at <= p_scheduled_start_at then
    raise exception 'A visit must end after it starts.' using errcode = '22004';
  end if;

  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such work order.' using errcode = 'HB404';
  end if;

  if not public.can_supervise_department(v_order.department_id) then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;

  if v_order.status in ('completed', 'cancelled', 'failed') then
    raise exception 'This job is closed.' using errcode = 'HB409';
  end if;

  select * into v_assigned
    from public.work_order_assignments
   where work_order_id = v_order.id and status = 'accepted'
   order by offered_at desc
   limit 1;

  -- Already booked: the resident is TOLD, not asked again. Sending a confirmed
  -- job back to awaiting_resident would strand a worker who has the slot in
  -- their calendar on an answer that may never come.
  if found then
    -- Moving a booked job is the same double-booking risk as making the
    -- booking, so it gets the same readable refusal. See assign_work_order.
    if exists (
      select 1
        from public.work_order_assignments a
       where a.staff_assignment_id = v_assigned.staff_assignment_id
         and a.status = 'accepted'
         and a.id <> v_assigned.id
         and a.scheduled_start_at is not null
         and tstzrange(a.scheduled_start_at, a.scheduled_end_at, '[)')
             && tstzrange(p_scheduled_start_at, p_scheduled_end_at, '[)')
    ) then
      raise exception 'That worker is already booked during the new time.'
        using errcode = 'HB409';
    end if;

    v_status := 'scheduled';
    update public.work_order_assignments
       set scheduled_start_at = p_scheduled_start_at,
           scheduled_end_at   = p_scheduled_end_at
     where id = v_assigned.id;
  elsif v_order.subject_kind = 'resident' then
    v_status   := 'awaiting_resident';
    v_deadline := now() + interval '24 hours';
  else
    v_status := 'offered';
  end if;

  update public.work_orders
     set scheduled_start_at   = p_scheduled_start_at,
         scheduled_end_at     = p_scheduled_end_at,
         status               = v_status,
         resident_deadline_at = v_deadline,
         updated_at           = now()
   where id = v_order.id;

  select id into v_actor
    from public.community_memberships
   where community_id = v_order.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_actor, 'job_scheduled',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'startsAt', p_scheduled_start_at,
      'endsAt', p_scheduled_end_at,
      'rescheduled', true,
      'note', nullif(btrim(coalesce(p_note, '')), ''))
  );

  select raised_by_membership_id into v_resident
    from public.complaints where id = v_order.complaint_id;

  if v_resident is not null then
    perform public.notify_member(
      v_resident,
      case when v_status = 'awaiting_resident'
           then 'work_order.schedule_requested'
           else 'work_order.rescheduled' end,
      jsonb_build_object(
        'title', 'Your visit has been rescheduled',
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'complaint_id', v_order.complaint_id,
        'work_order_id', v_order.id,
        'starts_at', p_scheduled_start_at,
        'ends_at', p_scheduled_end_at));
  end if;

  if v_assigned.id is not null and v_assigned.staff_assignment_id is not null then
    perform public.notify_member(
      (select membership_id from public.staff_assignments
        where id = v_assigned.staff_assignment_id),
      'work_order.rescheduled',
      jsonb_build_object(
        'title', 'A job of yours has moved',
        'url', '/worker?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'starts_at', p_scheduled_start_at,
        'ends_at', p_scheduled_end_at));
  end if;
end;
$$;

-- The supervisor names the person. Writes an ACCEPTED assignment rather than an
-- offer: this is a decision, not a question, and the offer path is step 5's.
--
-- Assigning from awaiting_resident is allowed, and it is the hand-operated form
-- of the resident_timeout the dispatcher will later fire -- see the header. A
-- supervisor whose resident has gone quiet has a lever today rather than after
-- step 5 lands.
create or replace function public.assign_work_order(
  p_work_order_id      uuid,
  p_staff_assignment_id uuid,
  p_scheduled_start_at timestamptz default null,
  p_scheduled_end_at   timestamptz default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order  public.work_orders%rowtype;
  v_staff  public.staff_assignments%rowtype;
  v_actor  uuid;
  v_start  timestamptz;
  v_end    timestamptz;
  v_id     uuid;
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such work order.' using errcode = 'HB404';
  end if;

  if not public.can_supervise_department(v_order.department_id) then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;

  if v_order.status in ('completed', 'cancelled', 'failed') then
    raise exception 'This job is closed.' using errcode = 'HB409';
  end if;

  select * into v_staff from public.staff_assignments where id = p_staff_assignment_id;
  if not found then
    raise exception 'No such roster entry.' using errcode = 'HB404';
  end if;

  if v_staff.department_id is distinct from v_order.department_id
     or v_staff.status <> 'active' then
    raise exception 'That person is not on this department''s roster.'
      using errcode = 'HB409';
  end if;

  v_start := coalesce(p_scheduled_start_at, v_order.scheduled_start_at);
  v_end   := coalesce(p_scheduled_end_at, v_order.scheduled_end_at);

  -- A job with no time is a job that cannot be double-booked, which sounds
  -- convenient and means the overlap constraint does not apply to it. Booking
  -- someone for no particular hour is what leaves a calendar wrong.
  if v_start is null or v_end is null then
    raise exception 'Schedule this job before assigning it.' using errcode = 'HB409';
  end if;

  if v_end <= v_start then
    raise exception 'A visit must end after it starts.' using errcode = '22004';
  end if;

  -- The overlap check, stated twice on purpose. The constraint below is the
  -- enforcement and this is the SENTENCE: 23P01 reaches the caller as "could
  -- not assign that job", which is true and useless, while this names the one
  -- thing they need to change. Same reasoning 0035 gave for raising HB409
  -- rather than letting a 23505 surface out of the hiring RPC.
  --
  -- This is a check and not the guarantee. Two supervisors booking the same
  -- worker into the same hour at the same moment both pass it and the second
  -- one is refused by the constraint -- which is why the constraint exists and
  -- why pg_errors maps 23P01 to a 409 as well.
  if exists (
    select 1
      from public.work_order_assignments a
     where a.staff_assignment_id = p_staff_assignment_id
       and a.status = 'accepted'
       and a.work_order_id <> v_order.id
       and a.scheduled_start_at is not null
       and tstzrange(a.scheduled_start_at, a.scheduled_end_at, '[)')
           && tstzrange(v_start, v_end, '[)')
  ) then
    raise exception '% is already booked during that time.', v_staff.display_name
      using errcode = 'HB409';
  end if;

  -- One holder at a time. The previous acceptance is withdrawn rather than
  -- deleted, so the history of who was booked and unbooked survives -- and so
  -- that the exclusion constraint does not see two accepted rows for the same
  -- job while this transaction is mid-flight.
  update public.work_order_assignments
     set status       = 'withdrawn',
         responded_at = now(),
         ended_at     = now()
   where work_order_id = v_order.id
     and status in ('accepted', 'offered');

  insert into public.work_order_assignments (
    work_order_id, staff_assignment_id, status, offered_at, responded_at,
    scheduled_start_at, scheduled_end_at, is_auto_assigned
  )
  values (
    v_order.id, p_staff_assignment_id, 'accepted', now(), now(),
    v_start, v_end, false
  )
  returning id into v_id;

  update public.work_orders
     set status               = 'scheduled',
         scheduled_start_at   = v_start,
         scheduled_end_at     = v_end,
         resident_deadline_at = null,
         updated_at           = now()
   where id = v_order.id;

  select id into v_actor
    from public.community_memberships
   where community_id = v_order.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_actor, 'job_assigned',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assignmentId', v_id,
      'assigneeName', v_staff.display_name,
      'startsAt', v_start,
      'endsAt', v_end)
  );

  -- D9 again: this is the offer-shaped notification the amendment permits. A
  -- roster row with no membership -- a name typed into the departments form --
  -- has nobody to notify, and that is the whole reason the guard is here.
  if v_staff.membership_id is not null then
    perform public.notify_member(
      v_staff.membership_id, 'work_order.assigned',
      jsonb_build_object(
        'title', 'You have a new job',
        'url', '/worker?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'starts_at', v_start,
        'ends_at', v_end));
  end if;

  return v_id;
end;
$$;

-- Call it off. Terminal, and it takes the assignment with it -- a cancelled job
-- that leaves an accepted assignment standing is a slot blocked in a worker's
-- calendar for work nobody is going to do.
create or replace function public.cancel_work_order(
  p_work_order_id uuid,
  p_reason        text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order    public.work_orders%rowtype;
  v_actor    uuid;
  v_reason   text := nullif(btrim(coalesce(p_reason, '')), '');
  v_row      record;
  v_resident uuid;
begin
  if v_reason is null then
    raise exception 'A reason is required.' using errcode = '22004';
  end if;

  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such work order.' using errcode = 'HB404';
  end if;

  if not public.can_supervise_department(v_order.department_id) then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;

  if v_order.status in ('completed', 'cancelled') then
    raise exception 'This job is closed.' using errcode = 'HB409';
  end if;

  for v_row in
    select a.id, sa.membership_id
      from public.work_order_assignments a
      left join public.staff_assignments sa on sa.id = a.staff_assignment_id
     where a.work_order_id = v_order.id
       and a.status in ('accepted', 'offered')
  loop
    update public.work_order_assignments
       set status = 'withdrawn', responded_at = now(), ended_at = now()
     where id = v_row.id;

    if v_row.membership_id is not null then
      perform public.notify_member(
        v_row.membership_id, 'work_order.cancelled',
        jsonb_build_object(
          'title', 'A job of yours was cancelled',
          'url', '/worker?job=' || v_order.id::text,
          'work_order_id', v_order.id,
          'reason', v_reason));
    end if;
  end loop;

  update public.work_orders
     set status               = 'cancelled',
         cancelled_reason     = v_reason,
         resident_deadline_at = null,
         updated_at           = now()
   where id = v_order.id;

  select id into v_actor
    from public.community_memberships
   where community_id = v_order.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_actor, 'job_cancelled',
    jsonb_build_object('workOrderId', v_order.id, 'reason', v_reason)
  );

  select raised_by_membership_id into v_resident
    from public.complaints where id = v_order.complaint_id;

  -- Silent when the supervisor cancelling IS the resident's own membership,
  -- which cannot happen today and costs one comparison to keep true.
  if v_resident is not null and v_resident is distinct from v_actor then
    perform public.notify_member(
      v_resident, 'work_order.cancelled',
      jsonb_build_object(
        'title', 'A scheduled visit was cancelled',
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'complaint_id', v_order.complaint_id,
        'work_order_id', v_order.id,
        'reason', v_reason));
  end if;
end;
$$;

grant execute on function public.create_work_order(
  uuid, uuid, uuid, text, text, timestamptz, timestamptz, text) to authenticated;
grant execute on function public.respond_to_work_order_schedule(uuid, text, text)
  to authenticated;
grant execute on function public.update_work_order(uuid, uuid, text, text, text)
  to authenticated;
grant execute on function public.reschedule_work_order(
  uuid, timestamptz, timestamptz, text) to authenticated;
grant execute on function public.assign_work_order(
  uuid, uuid, timestamptz, timestamptz) to authenticated;
grant execute on function public.cancel_work_order(uuid, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 7. Row security
--
-- Read policies only, on all four tables. Every write above is a definer
-- function that checked its own authorization first.
--
-- Both work-order policies are one function call, because the rule they state
-- is the same rule and stating it twice is how the two drift.
-- ---------------------------------------------------------------------------

alter table public.work_orders                enable row level security;
alter table public.work_order_assignments     enable row level security;
alter table public.worker_availability_rules  enable row level security;
alter table public.worker_unavailability      enable row level security;

drop policy if exists work_orders_read on public.work_orders;
create policy work_orders_read on public.work_orders
  for select to authenticated
  using (public.can_read_work_order(id));

drop policy if exists work_order_assignments_read on public.work_order_assignments;
create policy work_order_assignments_read on public.work_order_assignments
  for select to authenticated
  using (public.can_read_work_order(work_order_id));

-- Availability is the worker's own, plus whoever schedules them. A supervisor
-- who cannot see when someone is on leave will book them anyway, and the first
-- anyone learns of it is a missed visit.
drop policy if exists worker_availability_rules_read
  on public.worker_availability_rules;
create policy worker_availability_rules_read on public.worker_availability_rules
  for select to authenticated
  using (
    (staff_assignment_id is not null
     and (public.is_own_staff_assignment(staff_assignment_id)
          or exists (select 1 from public.staff_assignments sa
                      where sa.id = staff_assignment_id
                        and public.can_supervise_department(sa.department_id))))
    or (service_provider_id is not null
        and exists (select 1 from public.service_providers p
                     where p.id = service_provider_id
                       and p.profile_id = auth.uid()))
  );

drop policy if exists worker_unavailability_read on public.worker_unavailability;
create policy worker_unavailability_read on public.worker_unavailability
  for select to authenticated
  using (
    (staff_assignment_id is not null
     and (public.is_own_staff_assignment(staff_assignment_id)
          or exists (select 1 from public.staff_assignments sa
                      where sa.id = staff_assignment_id
                        and public.can_supervise_department(sa.department_id))))
    or (service_provider_id is not null
        and exists (select 1 from public.service_providers p
                     where p.id = service_provider_id
                       and p.profile_id = auth.uid()))
  );

grant select on public.work_orders to authenticated;
grant select on public.work_order_assignments to authenticated;
grant select on public.worker_availability_rules to authenticated;
grant select on public.worker_unavailability to authenticated;
