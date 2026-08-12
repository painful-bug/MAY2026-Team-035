-- 0045_departure_scheduling.sql
--
-- A departure gets a date, and the manager gets the decision.
--
-- THIS OVERTURNS 0043'S CENTRAL RULE, AND SAYS SO
--
-- 0043 refused to approve a departure while anything was booked in the
-- leaver's name: hand everything over first, then approve. The product owner
-- ruled the other way on 2026-08-10 (docs/plans/SERVICE_OPERATIONS_PROGRESS.md
-- §0): *management takes the decision of whether to let the employee leave*,
-- and on approval the leaver's booked work from the effective date onward goes
-- back into the pool for the dispatch engine to re-place — at a queue priority
-- just below urgent. The per-item handover (`reassign_departure_item`) stays
-- as a tool a supervisor may use before the decision; it is no longer a
-- precondition of it. The zero-commitment refusal is DELETED from
-- `decide_staff_departure` and KEPT in `remove_department_member`, so a direct
-- Remove — the path with no decision record — still cannot strand work.
--
-- WHAT A DATE CHANGES ABOUT THE FREEZE
--
-- 0043's freeze was binary: an open departure barred all new work. With a date
-- it becomes three cases, implemented once in `departure_bars_work`:
--
--   pending, no date        — immediate leave requested: bars everything,
--                             exactly 0043's behaviour.
--   pending, dated          — bars work whose slot starts on/after the date,
--                             AND unscheduled work, because a job with no slot
--                             can land anywhere. Work before the date is still
--                             theirs to take: they have not left yet.
--   approved, awaiting the  — bars everything. The PO's words: the timekeeper
--   effective date            "blocks the auto job assignment and prevents
--                             supervisors or managers from assigning jobs to
--                             them."
--
-- THE TIMEKEEPER IS A DISPATCH TASK, NOT A NEW MECHANISM
--
-- "There is a time keeping mechanism that keeps track of when servicemen are
-- to be removed" — that mechanism already exists: `dispatch_tasks` is a
-- durable timer with a lease, a retry ceiling and an at-least-once guarantee,
-- and 0037 §6 promised that a fifth task kind would not touch Python. This
-- file collects on that promise: `work_order_id` loses its NOT NULL,
-- `departure_id` arrives beside it with a num_nonnulls(…) = 1 check, and
-- `departure_removal` becomes the fifth kind. `app/core/dispatcher.py` is
-- untouched.
--
-- "JUST BELOW URGENT" IS A QUEUE POSITION, NOT A NEW LABEL
--
-- The claim query gains `order by priority desc, due_at`. Urgent work — a
-- high-priority work order whose task auto-assigns — enqueues at 2. Work
-- released by a departure enqueues at 1. Everything else stays at 0. The work
-- order's own low/medium/high label is untouched, because relabelling a
-- complaint to move it up a queue would lie to the resident about what they
-- reported.

-- ---------------------------------------------------------------------------
-- 1. The two dates
-- ---------------------------------------------------------------------------

alter table public.staff_departures
  add column if not exists requested_effective_at timestamptz;

alter table public.staff_departures
  add column if not exists effective_at timestamptz;

comment on column public.staff_departures.requested_effective_at is
  'When the worker wants to stop. Null means immediately.';
comment on column public.staff_departures.effective_at is
  'When the manager decided they stop. Stamped at approval; the timekeeper fires on it.';

-- ---------------------------------------------------------------------------
-- 2. The freeze, made time-aware
--
-- One predicate, four users (two triggers, two candidate sweeps).
-- `has_pending_departure` (0043) survives untouched for the views that only
-- ask whether a departure exists.
-- ---------------------------------------------------------------------------

create or replace function public.departure_bars_work(
  p_staff_id  uuid,
  p_starts_at timestamptz
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
      from public.staff_departures d
     where d.staff_assignment_id = p_staff_id
       and (
         (d.status = 'pending'
          and (d.requested_effective_at is null
               or p_starts_at is null
               or p_starts_at >= d.requested_effective_at))
         or
         (d.status = 'approved'
          and d.effective_at is not null
          and d.effective_at > now())
       )
  );
$$;

comment on function public.departure_bars_work(uuid, timestamptz) is
  'May this roster row NOT take work starting at this time? Pending-undated and approved-awaiting-removal bar everything; pending-dated bars the date onward plus unscheduled work, which can land anywhere.';

revoke all on function public.departure_bars_work(uuid, timestamptz)
  from public, anon, authenticated;
grant execute on function public.departure_bars_work(uuid, timestamptz) to authenticated;

-- ---------------------------------------------------------------------------
-- 3. The triggers learn the date — and watch the slot columns
--
-- 0043's triggers fired on `update of status, staff_assignment_id`. Now that
-- the bar depends on WHEN the work starts, an update that moves a slot past
-- the barrier without touching status must fire too, so the column lists grow
-- by the slot column each table has.
-- ---------------------------------------------------------------------------

create or replace function public.block_departing_assignment()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status in ('offered', 'accepted')
     and public.departure_bars_work(new.staff_assignment_id,
                                    new.scheduled_start_at) then
    raise exception 'That person is leaving and cannot take this work.'
      using errcode = 'HB409';
  end if;
  return new;
end;
$$;

drop trigger if exists work_order_assignments_block_departing
  on public.work_order_assignments;
create trigger work_order_assignments_block_departing
  before insert or update of status, staff_assignment_id, scheduled_start_at
  on public.work_order_assignments
  for each row execute function public.block_departing_assignment();

create or replace function public.block_departing_shift()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status in ('scheduled', 'active')
     and public.departure_bars_work(new.staff_assignment_id, new.starts_at) then
    raise exception 'That person is leaving and cannot take this shift.'
      using errcode = 'HB409';
  end if;
  return new;
end;
$$;

drop trigger if exists security_shifts_block_departing on public.security_shifts;
create trigger security_shifts_block_departing
  before insert or update of status, staff_assignment_id, starts_at
  on public.security_shifts
  for each row execute function public.block_departing_shift();

-- ---------------------------------------------------------------------------
-- 4. The sweeps learn the date
--
-- Both recreated whole from their 0043 bodies — a SQL-language function has no
-- smaller edit — with `has_pending_departure(sa.id)` replaced by
-- `departure_bars_work(sa.id, <slot start>)`. Everything else is byte-for-byte
-- 0043, including the adjacency argument and the no-skills-on-roster-rows one.
-- ---------------------------------------------------------------------------

create or replace function public.dispatch_candidates(
  p_work_order_id uuid,
  p_limit         integer default 5
)
returns table (
  staff_assignment_id uuid,
  membership_id       uuid,
  service_provider_id uuid,
  display_name        text,
  has_adjacent_job    boolean,
  open_jobs           integer,
  distance_km         numeric
)
language sql
security definer
set search_path = public
as $$
  with job as (
    select w.id, w.community_id, w.department_id, w.skill_id,
           w.scheduled_start_at as slot_start,
           w.scheduled_end_at   as slot_end
      from public.work_orders w
     where w.id = p_work_order_id
       and w.scheduled_start_at is not null
       and w.department_id is not null
  ),
  ranked as (
  select
    sa.id                  as sa_id,
    sa.membership_id       as sa_membership_id,
    sa.service_provider_id as sa_provider_id,
    sa.display_name        as sa_display_name,
    exists (
      select 1
        from public.work_order_assignments adj
        join public.work_orders adjw on adjw.id = adj.work_order_id
       where adj.staff_assignment_id = sa.id
         and adj.status = 'accepted'
         and adj.work_order_id <> j.id
         and adjw.community_id = j.community_id
         and adj.scheduled_start_at::date = j.slot_start::date
    ) as adjacent,
    (
      select count(*)
        from public.work_order_assignments open_a
       where open_a.staff_assignment_id = sa.id
         and open_a.status in ('offered', 'accepted')
         and coalesce(open_a.scheduled_start_at, now()) >= now()
    )::integer as load,
    case
      when c.location is null or sp.location is null then null
      else round(
        (extensions.st_distance(c.location, sp.location) / 1000)::numeric, 2)
    end as km
  from job j
  join public.staff_assignments sa
    on sa.department_id = j.department_id
   and sa.status = 'active'
   and sa.is_active
   and sa.membership_id is not null
  join public.communities c
    on c.id = j.community_id
  left join public.service_providers sp
    on sp.id = sa.service_provider_id
 where
   (sp.id is null or (sp.status = 'active' and sp.is_available))
   -- 0045: time-aware. Somebody leaving next month can still take tomorrow's
   -- job; somebody leaving immediately, or already approved to leave, cannot
   -- take anything.
   and not public.departure_bars_work(sa.id, j.slot_start)
   and not exists (
     select 1
       from public.worker_unavailability u
      where (u.staff_assignment_id = sa.id
             or (sp.id is not null and u.service_provider_id = sp.id))
        and tstzrange(u.starts_at, u.ends_at, '[)')
            && tstzrange(j.slot_start, j.slot_end, '[)')
   )
   and (
     not exists (
       select 1 from public.worker_availability_rules r
        where r.staff_assignment_id = sa.id
           or (sp.id is not null and r.service_provider_id = sp.id)
     )
     or exists (
       select 1
         from public.worker_availability_rules r
        where (r.staff_assignment_id = sa.id
               or (sp.id is not null and r.service_provider_id = sp.id))
          and r.weekday = extract(dow from j.slot_start)::smallint
          and r.start_time <= j.slot_start::time
          and r.end_time   >= j.slot_end::time
          and r.effective_from <= j.slot_start::date
          and (r.effective_to is null or r.effective_to >= j.slot_start::date)
     )
   )
   and not exists (
     select 1
       from public.work_order_assignments busy
      where busy.staff_assignment_id = sa.id
        and busy.status = 'accepted'
        and busy.work_order_id <> j.id
        and busy.scheduled_start_at is not null
        and tstzrange(busy.scheduled_start_at, busy.scheduled_end_at, '[)')
            && tstzrange(j.slot_start, j.slot_end, '[)')
   )
   and not exists (
     select 1
       from public.work_order_assignments said_no
      where said_no.staff_assignment_id = sa.id
        and said_no.work_order_id = j.id
        and said_no.status = 'declined'
   )
   and (
     j.skill_id is null
     or sp.id is null
     or exists (
       select 1 from public.service_provider_skills ps
        where ps.service_provider_id = sp.id
          and ps.skill_id = j.skill_id
     )
   )
  )
  select
    cand.sa_id,
    cand.sa_membership_id,
    cand.sa_provider_id,
    cand.sa_display_name,
    cand.adjacent,
    cand.load,
    cand.km
  from ranked cand
  order by
    cand.adjacent desc,
    cand.load asc,
    cand.km asc nulls last,
    cand.sa_display_name
  limit greatest(coalesce(p_limit, 5), 1);
$$;

comment on function public.dispatch_candidates(uuid, integer) is
  'Who could take this job, best first: already in this community today, then least loaded, then nearest. Excludes anyone whose departure bars work at this slot. Reads only.';

create or replace function public.security_shift_candidates(
  p_shift_id uuid,
  p_limit    integer default 5
)
returns table (
  staff_assignment_id uuid,
  membership_id       uuid,
  service_provider_id uuid,
  display_name        text,
  week_load           integer,
  distance_km         numeric
)
language sql
security definer
set search_path = public
as $$
  with shift as (
    select s.id, s.community_id, s.department_id, s.staff_assignment_id,
           s.starts_at, s.ends_at
      from public.security_shifts s
     where s.id = p_shift_id
  ),
  ranked as (
    select
      sa.id                  as sa_id,
      sa.membership_id       as sa_membership_id,
      sa.service_provider_id as sa_provider_id,
      sa.display_name        as sa_display_name,
      (
        select count(*)
          from public.security_shifts w
         where w.staff_assignment_id = sa.id
           and w.status <> 'cancelled'
           and w.starts_at >= sh.starts_at - interval '3 days'
           and w.starts_at <= sh.starts_at + interval '3 days'
      )::integer as load,
      case
        when c.location is null or sp.location is null then null
        else round(
          (extensions.st_distance(c.location, sp.location) / 1000)::numeric, 2)
      end as km
    from shift sh
    join public.staff_assignments sa
      on sa.department_id = sh.department_id
     and sa.id <> sh.staff_assignment_id
     and sa.status = 'active'
     and sa.is_active
     and sa.membership_id is not null
    join public.communities c on c.id = sh.community_id
    left join public.service_providers sp on sp.id = sa.service_provider_id
   where
     (sp.id is null or (sp.status = 'active' and sp.is_available))
     and not public.departure_bars_work(sa.id, sh.starts_at)
     and not exists (
       select 1
         from public.worker_unavailability u
        where (u.staff_assignment_id = sa.id
               or (sp.id is not null and u.service_provider_id = sp.id))
          and tstzrange(u.starts_at, u.ends_at, '[)')
              && tstzrange(sh.starts_at, sh.ends_at, '[)')
     )
     -- `security_shifts_no_overlap` refuses the write anyway; this stops the
     -- handover from proposing somebody it would then be refused for.
     and not exists (
       select 1
         from public.security_shifts busy
        where busy.staff_assignment_id = sa.id
          and busy.status <> 'cancelled'
          and busy.id <> sh.id
          and tstzrange(busy.starts_at, busy.ends_at, '[)')
              && tstzrange(sh.starts_at, sh.ends_at, '[)')
     )
  )
  select
    cand.sa_id,
    cand.sa_membership_id,
    cand.sa_provider_id,
    cand.sa_display_name,
    cand.load,
    cand.km
  from ranked cand
  order by cand.load asc, cand.km asc nulls last, cand.sa_display_name
  limit greatest(coalesce(p_limit, 5), 1);
$$;

comment on function public.security_shift_candidates(uuid, integer) is
  'Who else could stand this shift, best first: fewest shifts that week, then nearest. dispatch_candidates for the gate, minus the adjacency clause, which does not mean anything on a rota.';

-- ---------------------------------------------------------------------------
-- 5. dispatch_tasks learns a second subject and a queue position
-- ---------------------------------------------------------------------------

alter table public.dispatch_tasks
  alter column work_order_id drop not null;

alter table public.dispatch_tasks
  add column if not exists departure_id uuid
    references public.staff_departures(id) on delete cascade;

alter table public.dispatch_tasks
  add column if not exists priority smallint not null default 0;

comment on column public.dispatch_tasks.departure_id is
  '0045 — the timekeeper''s subject. Exactly one of work_order_id / departure_id is set.';
comment on column public.dispatch_tasks.priority is
  '0045 — claim order. 2 = urgent auto-assign, 1 = departure-released work, 0 = everything else.';

do $$
begin
  -- The kind check was added under an if-not-exists guard in 0037, so it must
  -- be dropped by name before the fifth kind can exist.
  if exists (select 1 from pg_constraint
              where conrelid = 'public.dispatch_tasks'::regclass
                and conname  = 'dispatch_tasks_kind_check') then
    alter table public.dispatch_tasks drop constraint dispatch_tasks_kind_check;
  end if;

  alter table public.dispatch_tasks
    add constraint dispatch_tasks_kind_check
    check (kind in ('ping', 'auto_assign', 'resident_timeout',
                    'failed_visit_escalation', 'departure_removal'));

  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.dispatch_tasks'::regclass
                    and conname  = 'dispatch_tasks_one_subject') then
    alter table public.dispatch_tasks
      add constraint dispatch_tasks_one_subject
      check (num_nonnulls(work_order_id, departure_id) = 1);
  end if;
end $$;

-- One open timekeeper per departure, mirroring the per-work-order rule.
create unique index if not exists dispatch_tasks_one_open_per_departure_kind
  on public.dispatch_tasks (departure_id, kind)
  where completed_at is null;

-- The claim now orders by priority first, so the index does too.
drop index if exists public.dispatch_tasks_due_idx;
create index if not exists dispatch_tasks_due_idx
  on public.dispatch_tasks (priority desc, due_at)
  where completed_at is null;

-- ---------------------------------------------------------------------------
-- 6. The queue functions
--
-- `claim_dispatch_batch` and `enqueue_dispatch_task` change signature, and a
-- changed signature is a new function to Postgres — `create or replace` would
-- quietly leave the old one behind as an overload, so both are dropped by
-- their exact old signatures first. Grants are reissued because a drop takes
-- them with it.
-- ---------------------------------------------------------------------------

drop function if exists public.enqueue_dispatch_task(uuid, text, timestamptz);

create function public.enqueue_dispatch_task(
  p_work_order_id uuid,
  p_kind          text,
  p_due_at        timestamptz default null,
  p_priority      smallint default 0
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  insert into public.dispatch_tasks (work_order_id, kind, due_at, priority)
  values (p_work_order_id, p_kind, coalesce(p_due_at, now()),
          coalesce(p_priority, 0))
  -- Re-arming rather than duplicating (0037). The priority follows the newest
  -- enqueue for the same reason the due time does: the task describes the
  -- current need, not the history of needs.
  on conflict (work_order_id, kind) where completed_at is null
  do update set
    due_at     = excluded.due_at,
    priority   = excluded.priority,
    claimed_at = null,
    attempts   = 0,
    last_error = null
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.enqueue_dispatch_task(uuid, text, timestamptz, smallint) is
  'Arm or re-arm one timer for one job, at a queue priority. Called only by the work_orders trigger, dispatch_ping_candidates, and the release path.';

create or replace function public.enqueue_departure_task(
  p_departure_id uuid,
  p_kind         text,
  p_due_at       timestamptz default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  insert into public.dispatch_tasks (departure_id, kind, due_at)
  values (p_departure_id, p_kind, coalesce(p_due_at, now()))
  on conflict (departure_id, kind) where completed_at is null
  do update set
    due_at     = excluded.due_at,
    claimed_at = null,
    attempts   = 0,
    last_error = null
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.enqueue_departure_task(uuid, text, timestamptz) is
  'Arm or re-arm the timekeeper for one departure. A re-approval with a new date moves the one timer rather than adding a second.';

drop function if exists public.claim_dispatch_batch(integer);

create function public.claim_dispatch_batch(p_limit integer default 20)
returns table (
  task_id       uuid,
  work_order_id uuid,
  departure_id  uuid,
  kind          text,
  due_at        timestamptz,
  attempts      smallint,
  priority      smallint
)
language sql
security definer
set search_path = public
as $$
  update public.dispatch_tasks t
     set claimed_at = now(),
         attempts   = t.attempts + 1
   where t.id in (
     select c.id
       from public.dispatch_tasks c
      where c.completed_at is null
        and c.due_at <= now()
        and (c.claimed_at is null or c.claimed_at < now() - interval '5 minutes')
        and c.attempts < 5
      -- "Just below urgent", implemented: within the due set, urgent
      -- auto-assigns (2) go first, departure-released work (1) next,
      -- everything else (0) after, oldest deadline first within a rank.
      order by c.priority desc, c.due_at
      limit greatest(coalesce(p_limit, 20), 1)
      for update skip locked
   )
  returning t.id, t.work_order_id, t.departure_id, t.kind, t.due_at,
            t.attempts, t.priority;
$$;

comment on function public.claim_dispatch_batch(integer) is
  'Atomically lease the next due tasks, highest queue priority first. for update skip locked, so two dispatcher processes claim disjoint sets.';

create or replace function public.sync_dispatch_tasks()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status = 'awaiting_resident' then
    if tg_op = 'INSERT'
       or old.status is distinct from new.status
       or old.resident_deadline_at is distinct from new.resident_deadline_at then
      perform public.enqueue_dispatch_task(
        new.id, 'resident_timeout',
        coalesce(new.resident_deadline_at, now() + interval '24 hours'));
    end if;

  elsif new.status = 'offered' then
    if tg_op = 'INSERT'
       or old.status is distinct from new.status
       or old.scheduled_start_at is distinct from new.scheduled_start_at then
      perform public.close_dispatch_tasks(new.id, array['resident_timeout']);

      -- The urgent path, and the whole of it (0037) — now with its queue rank
      -- attached: an urgent job outranks even departure-released work.
      perform public.enqueue_dispatch_task(
        new.id,
        case when new.priority = 'high' then 'auto_assign' else 'ping' end,
        now(),
        case when new.priority = 'high' then 2 else 0 end);
    end if;

  elsif new.status = 'failed' then
    if tg_op = 'INSERT' or old.status is distinct from new.status then
      perform public.close_dispatch_tasks(new.id, null);
      perform public.enqueue_dispatch_task(
        new.id, 'failed_visit_escalation', now() + interval '2 hours');
    end if;

  elsif tg_op = 'INSERT' or old.status is distinct from new.status then
    perform public.close_dispatch_tasks(new.id, null);
  end if;

  return null;
end;
$$;

-- ---------------------------------------------------------------------------
-- 7. Release becomes windowed
--
-- 0043's release emptied the whole book — right for a bar, wrong for a dated
-- leave, where work before the date is still the leaver's to finish. The
-- window: items whose slot starts on/after `p_from`, plus unscheduled items,
-- which can land anywhere. Null `p_from` means everything, which is what the
-- bar path passes and why `blacklist_service_provider` needs no edit.
-- ---------------------------------------------------------------------------

drop function if exists public.release_staff_commitments(uuid, text);

create function public.release_staff_commitments(
  p_staff_id uuid,
  p_reason   text default null,
  p_from     timestamptz default null,
  p_priority smallint default 0
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row      record;
  v_released integer := 0;
begin
  for v_row in
    select a.id as assignment_id, a.work_order_id,
           w.status as order_status, w.priority as order_priority
      from public.work_order_assignments a
      join public.work_orders w on w.id = a.work_order_id
     where a.staff_assignment_id = p_staff_id
       and a.status in ('offered', 'accepted')
       and w.status not in ('completed', 'cancelled', 'failed')
       and (p_from is null
            or coalesce(a.scheduled_start_at, w.scheduled_start_at) is null
            or coalesce(a.scheduled_start_at, w.scheduled_start_at) >= p_from)
  loop
    update public.work_order_assignments
       set status       = 'withdrawn',
           responded_at = now(),
           ended_at     = now(),
           decline_reason = nullif(btrim(coalesce(p_reason, '')), '')
     where id = v_row.assignment_id;

    if v_row.order_status <> 'offered' then
      -- Back to `offered`; the trigger arms a timer at rank 0, and the enqueue
      -- below immediately re-arms the same timer at the release's rank. Two
      -- writes to one row, not two timers.
      update public.work_orders
         set status = 'offered', updated_at = now()
       where id = v_row.work_order_id;
    end if;

    perform public.enqueue_dispatch_task(
      v_row.work_order_id,
      case when v_row.order_priority = 'high' then 'auto_assign' else 'ping' end,
      now(),
      case when v_row.order_priority = 'high' then 2
           else coalesce(p_priority, 0) end);

    v_released := v_released + 1;
  end loop;

  for v_row in
    select s.id
      from public.security_shifts s
     where s.staff_assignment_id = p_staff_id
       and s.status in ('scheduled', 'active')
       and (p_from is null or s.starts_at >= p_from)
  loop
    update public.security_shifts
       set status     = 'cancelled',
           notes      = coalesce(notes, nullif(btrim(coalesce(p_reason, '')), '')),
           updated_at = now()
     where id = v_row.id;
    v_released := v_released + 1;
  end loop;

  return v_released;
end;
$$;

comment on function public.release_staff_commitments(uuid, text, timestamptz, smallint) is
  'Empty somebody''s book from a moment onward: jobs go back to the engine at a queue priority, shifts are cancelled. Null window = everything (the bar path).';

-- ---------------------------------------------------------------------------
-- 8. Removal keeps its gate, gains an auditor and a service path
--
-- Same signature as 0043, three changes: the manager check is skipped when
-- there is no session (auth.uid() is null happens only inside service_role
-- machinery — the timekeeper — since the function is granted to no one
-- anonymous); the auto-approved departure row now records WHO, not just when;
-- and the refusal message stops promising that approval needs a handover,
-- because it no longer does.
-- ---------------------------------------------------------------------------

create or replace function public.remove_department_member(
  p_staff_id uuid,
  p_reason   text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_staff public.staff_assignments%rowtype;
  v_left  integer;
  v_name  text;
  v_actor uuid;
begin
  select * into v_staff from public.staff_assignments where id = p_staff_id;
  if not found then
    raise exception 'No such roster entry.' using errcode = 'HB404';
  end if;

  if auth.uid() is not null
     and not public.can_manage_department(v_staff.department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  v_left := public.staff_open_commitment_count(p_staff_id);
  if v_left > 0 then
    raise exception
      '% still holds % job(s) or shift(s). Approve a departure, which releases them, or hand them over first.',
      v_staff.display_name, v_left
      using errcode = 'HB409';
  end if;

  select name into v_name from public.departments where id = v_staff.department_id;

  select id into v_actor
    from public.community_memberships
   where community_id = v_staff.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null
   limit 1;

  update public.staff_assignments
     set status     = 'inactive',
         is_active  = false,
         rank       = 'member',
         ended_at   = current_date,
         updated_at = now()
   where id = p_staff_id;

  update public.staff_departures
     set status                   = 'approved',
         decided_at               = coalesce(decided_at, now()),
         decided_by_membership_id = coalesce(decided_by_membership_id, v_actor),
         effective_at             = coalesce(effective_at, now()),
         decision_note            = coalesce(
                                      decision_note,
                                      nullif(btrim(coalesce(p_reason, '')), '')),
         updated_at               = now()
   where staff_assignment_id = p_staff_id
     and status = 'pending';

  if v_staff.membership_id is not null then
    update public.community_memberships
       set status     = 'ended',
           ended_at   = now(),
           updated_at = now()
     where id = v_staff.membership_id;

    perform public.notify_member(
      v_staff.membership_id, 'service_engagement_ended',
      jsonb_build_object(
        'title', 'You were taken off a roster',
        'body', coalesce(v_name, 'A department'),
        'url', '/worker/communities',
        'departmentId', v_staff.department_id,
        'reason', nullif(btrim(coalesce(p_reason, '')), '')));
  end if;
end;
$$;

comment on function public.remove_department_member(uuid, text) is
  'Deactivate a roster row and end its membership. Still refuses while work is booked — approval and the timekeeper release first; a direct Remove has no release step and keeps the guard.';

-- ---------------------------------------------------------------------------
-- 9. Opening and deciding, with dates
-- ---------------------------------------------------------------------------

drop function if exists public.request_staff_departure(uuid, text);

create function public.request_staff_departure(
  p_staff_id     uuid,
  p_reason       text default null,
  p_effective_at timestamptz default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_staff      public.staff_assignments%rowtype;
  v_department public.departments%rowtype;
  v_is_own     boolean;
  v_can_manage boolean;
  v_actor      uuid;
  v_id         uuid;
begin
  select * into v_staff from public.staff_assignments where id = p_staff_id;
  if not found then
    raise exception 'No such roster entry.' using errcode = 'HB404';
  end if;

  if v_staff.status <> 'active' then
    raise exception 'That person is no longer on this roster.'
      using errcode = 'HB409';
  end if;

  -- Immediate is spelled by omitting the date, not by a date in the past.
  if p_effective_at is not null and p_effective_at <= now() then
    raise exception 'A leave date must be in the future. Leave it out to ask to leave immediately.'
      using errcode = '22P02';
  end if;

  v_is_own     := public.is_own_staff_assignment(p_staff_id);
  v_can_manage := public.can_manage_department(v_staff.department_id);

  if not (v_is_own or v_can_manage) then
    raise exception 'You may not open a departure for this person.'
      using errcode = 'HB403';
  end if;

  select * into v_department from public.departments where id = v_staff.department_id;

  select id into v_actor
    from public.community_memberships
   where community_id = v_staff.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null
   limit 1;

  begin
    insert into public.staff_departures (
      community_id, department_id, staff_assignment_id, service_provider_id,
      -- Their own row makes it a resignation even when the person pressing the
      -- button also manages the department. Who is leaving decides this, not
      -- what else they are allowed to do.
      initiated_by, requested_by_membership_id, reason, requested_effective_at
    )
    values (
      v_staff.community_id, v_staff.department_id, p_staff_id,
      v_staff.service_provider_id,
      case when v_is_own then 'worker' else 'manager' end,
      v_actor,
      nullif(btrim(coalesce(p_reason, '')), ''),
      p_effective_at
    )
    returning id into v_id;
  exception when unique_violation then
    raise exception 'A departure is already open for this person.'
      using errcode = 'HB409';
  end;

  perform public.notify_department_leadership(
    v_staff.department_id, 'departure.requested',
    jsonb_build_object(
      'title', coalesce(v_staff.display_name, 'Someone')
               || ' asked to leave ' || coalesce(v_department.name, 'a department'),
      'body', case
                when p_effective_at is null then 'They want to leave immediately. Your decision releases their booked work back to the pool.'
                else 'They want to leave on '
                     || to_char(p_effective_at, 'DD Mon YYYY')
                     || '. Work booked from that day is released when you approve.'
              end,
      'url', '/admin/departments/' || v_staff.department_id::text
             || '/staff/' || p_staff_id::text
             || '?departure=' || v_id::text,
      'departureId', v_id,
      'departmentId', v_staff.department_id,
      'staffId', p_staff_id,
      'requestedEffectiveAt', p_effective_at),
    v_actor);

  -- A manager opening this on somebody else's behalf is news to that person.
  -- A worker opening their own is not.
  if not v_is_own and v_staff.membership_id is not null then
    perform public.notify_member(
      v_staff.membership_id, 'departure.requested',
      jsonb_build_object(
        'title', 'You are being taken off a roster',
        'body', v_department.name,
        'url', '/worker/communities',
        'departureId', v_id,
        'departmentId', v_staff.department_id));
  end if;

  return v_id;
end;
$$;

comment on function public.request_staff_departure(uuid, text, timestamptz) is
  'Open a departure, immediately or for a future date. Either side may. The freeze applies from this moment — wholly for an immediate leave, from the date for a scheduled one.';

drop function if exists public.decide_staff_departure(uuid, text, text);

create function public.decide_staff_departure(
  p_departure_id uuid,
  p_decision     text,
  p_note         text default null,
  p_effective_at timestamptz default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_dep       public.staff_departures%rowtype;
  v_staff     public.staff_assignments%rowtype;
  v_decision  text := nullif(btrim(lower(coalesce(p_decision, ''))), '');
  v_actor     uuid;
  v_name      text;
  v_eff       timestamptz;
  v_immediate boolean;
  v_released  integer := 0;
begin
  if v_decision not in ('approve', 'reject') then
    raise exception 'A departure is approved or rejected.' using errcode = '22P02';
  end if;

  select * into v_dep from public.staff_departures where id = p_departure_id for update;
  if not found then
    raise exception 'No such departure.' using errcode = 'HB404';
  end if;

  -- Approval is the manager's alone. Supervisors run the handover -- see
  -- `reassign_departure_item` -- because that is the work; ending somebody's
  -- employment is not.
  if not public.can_manage_department(v_dep.department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  if v_dep.status <> 'pending' then
    raise exception 'That departure has already been decided.' using errcode = 'HB409';
  end if;

  select * into v_staff from public.staff_assignments where id = v_dep.staff_assignment_id;
  select name into v_name from public.departments where id = v_dep.department_id;

  select id into v_actor
    from public.community_memberships
   where community_id = v_dep.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null
   limit 1;

  if v_decision = 'reject' then
    update public.staff_departures
       set status                   = 'rejected',
           decided_by_membership_id = v_actor,
           decided_at               = now(),
           decision_note            = nullif(btrim(coalesce(p_note, '')), ''),
           updated_at               = now()
     where id = p_departure_id;

    if v_staff.membership_id is not null then
      perform public.notify_member(
        v_staff.membership_id, 'departure.rejected',
        jsonb_build_object(
          'title', 'Your request to leave was not approved',
          'body', coalesce(nullif(btrim(coalesce(p_note, '')), ''), v_name),
          'url', '/worker/communities',
          'departureId', v_dep.id,
          'departmentId', v_dep.department_id));
    end if;
    return;
  end if;

  -- 0043 refused here while anything was booked. That refusal is gone: the
  -- 2026-08-10 ruling makes the decision the manager's, and the release below
  -- is what happens to the work. The manager may keep the requested date or
  -- set a later one; either way the floor is now.
  v_eff := coalesce(p_effective_at, v_dep.requested_effective_at, now());
  if v_eff < now() then
    v_eff := now();
  end if;
  v_immediate := v_eff <= now();

  update public.staff_departures
     set status                   = 'approved',
         effective_at             = v_eff,
         decided_by_membership_id = v_actor,
         decided_at               = now(),
         decision_note            = nullif(btrim(coalesce(p_note, '')), ''),
         updated_at               = now()
   where id = p_departure_id;

  if v_immediate then
    -- Everything goes back to the pool -- including stale past-dated items,
    -- which is why the window is null rather than now(). Then the removal,
    -- whose gate passes because the book was just emptied.
    v_released := public.release_staff_commitments(
      v_dep.staff_assignment_id,
      coalesce(nullif(btrim(coalesce(p_note, '')), ''), 'Departure approved.'),
      null, 1);

    perform public.remove_department_member(
      v_dep.staff_assignment_id,
      nullif(btrim(coalesce(p_note, v_dep.reason, '')), ''));
  else
    -- Work from the leave date onward is released now, so its reassignment
    -- starts today rather than on their last morning. Work before the date
    -- stays theirs: they have not left yet. The timekeeper does the removal.
    v_released := public.release_staff_commitments(
      v_dep.staff_assignment_id,
      'Released for a departure on ' || to_char(v_eff, 'DD Mon YYYY') || '.',
      v_eff, 1);

    perform public.enqueue_departure_task(v_dep.id, 'departure_removal', v_eff);

    if v_staff.membership_id is not null then
      perform public.notify_member(
        v_staff.membership_id, 'departure.approved',
        jsonb_build_object(
          'title', 'Your leave was approved',
          'body', 'You leave ' || coalesce(v_name, 'the department')
                  || ' on ' || to_char(v_eff, 'DD Mon YYYY') || '.',
          'url', '/worker/communities',
          'departureId', v_dep.id,
          'departmentId', v_dep.department_id,
          'effectiveAt', v_eff));
    end if;
  end if;

  perform public.notify_department_leadership(
    v_dep.department_id, 'departure.approved',
    jsonb_build_object(
      'title', case
                 when v_immediate then
                   coalesce(v_staff.display_name, 'Someone')
                   || ' has left ' || coalesce(v_name, 'the department')
                 else
                   coalesce(v_staff.display_name, 'Someone')
                   || ' leaves ' || coalesce(v_name, 'the department')
                   || ' on ' || to_char(v_eff, 'DD Mon YYYY')
               end,
      'body', case
                when v_released > 0 then
                  v_released || ' booked item(s) went back to the pool for reassignment.'
                else 'Nothing was booked in their name.'
              end,
      'url', '/admin/departments/' || v_dep.department_id::text
             || '/staff/' || v_dep.staff_assignment_id::text
             || '?departure=' || v_dep.id::text,
      'departureId', v_dep.id,
      'departmentId', v_dep.department_id,
      'staffId', v_dep.staff_assignment_id,
      'effectiveAt', v_eff,
      'releasedCount', v_released),
    v_actor);
end;
$$;

comment on function public.decide_staff_departure(uuid, text, text, timestamptz) is
  'Approve (at the requested date or a later one) or reject. Approval releases booked work from the effective date onward at queue priority 1 and either removes now or arms the timekeeper. Overturns 0043''s zero-commitment refusal — PO ruling, 2026-08-10.';

-- ---------------------------------------------------------------------------
-- 10. The timekeeper's action, and the fifth arm
-- ---------------------------------------------------------------------------

create or replace function public.dispatch_departure_removal(p_departure_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_dep   public.staff_departures%rowtype;
  v_staff public.staff_assignments%rowtype;
begin
  select * into v_dep from public.staff_departures where id = p_departure_id;
  if not found or v_dep.status <> 'approved' then
    return false;
  end if;

  select * into v_staff from public.staff_assignments
   where id = v_dep.staff_assignment_id;
  -- A bar, or anything else that already ended the roster row, has done this
  -- task's work for it.
  if not found or v_staff.status <> 'active' then
    return false;
  end if;

  -- Whatever is still booked -- a job they were meant to finish before leaving
  -- and did not, a shift running past midnight -- is released, because after
  -- this moment there is nobody to do it. Then the removal, gate passing.
  perform public.release_staff_commitments(
    v_dep.staff_assignment_id,
    'Departure effective ' || to_char(v_dep.effective_at, 'DD Mon YYYY') || '.',
    null, 1);

  perform public.remove_department_member(
    v_dep.staff_assignment_id,
    coalesce(v_dep.decision_note, v_dep.reason));

  return true;
end;
$$;

comment on function public.dispatch_departure_removal(uuid) is
  'What the timekeeper does at the effective date: release whatever is still booked, then remove. Skips (false) when the departure is no longer approved or the roster row already ended.';

create or replace function public.fire_dispatch_task(p_task_id uuid)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_task   public.dispatch_tasks%rowtype;
  v_result text;
  v_id     uuid;
begin
  select * into v_task from public.dispatch_tasks where id = p_task_id
    for update;
  if not found then
    return 'missing';
  end if;

  if v_task.completed_at is not null then
    return 'already_done';
  end if;

  case v_task.kind
    when 'ping' then
      v_result := 'offered:'
        || public.dispatch_ping_candidates(v_task.work_order_id)::text;

    when 'auto_assign' then
      v_id := public.dispatch_auto_assign(v_task.work_order_id);
      v_result := coalesce('assigned:' || v_id::text, 'no_candidate');

    when 'resident_timeout' then
      v_result := case
        when public.dispatch_resident_timeout(v_task.work_order_id)
        then 'proceeded' else 'skipped' end;

    when 'failed_visit_escalation' then
      v_result := case
        when public.dispatch_failed_visit_escalation(v_task.work_order_id)
        then 'escalated' else 'skipped' end;

    when 'departure_removal' then
      v_result := case
        when public.dispatch_departure_removal(v_task.departure_id)
        then 'removed' else 'skipped' end;

    else
      update public.dispatch_tasks
         set last_error   = 'No handler for kind: ' || v_task.kind,
             completed_at = now()
       where id = p_task_id;
      return 'unsupported';
  end case;

  update public.dispatch_tasks
     set completed_at = now(),
         last_error   = null
   where id = p_task_id;

  return v_result;
end;
$$;

comment on function public.fire_dispatch_task(uuid) is
  'Run one claimed task and mark it done. The dispatcher''s only verb: the mapping from kind to action stays in SQL beside the actions. Five kinds since 0045.';

-- ---------------------------------------------------------------------------
-- 11. Reads
--
-- `staff_departure_items` gains a window so the conflict list — what would be
-- stranded if they left on the date they named — is the same query as the
-- release. `staff_conflict_count` is its count, granted wide for the views.
-- `staff_schedule_items` is the employee page's calendar. `departure_coverage`
-- answers the manager's button: for each conflicting item, who could take it —
-- and "nobody" is an answer, not an error.
-- ---------------------------------------------------------------------------

drop function if exists public.staff_departure_items(uuid);

create function public.staff_departure_items(
  p_staff_id uuid,
  p_from     timestamptz default null
)
returns table (
  item_kind    text,
  item_id      uuid,
  reference_id uuid,
  title        text,
  starts_at    timestamptz,
  ends_at      timestamptz,
  item_status  text
)
language sql
stable
security definer
set search_path = public
as $$
  select
    'work_order'::text,
    a.id,
    w.id,
    coalesce(nullif(btrim(coalesce(c.title, '')), ''), 'Scheduled work'),
    coalesce(a.scheduled_start_at, w.scheduled_start_at),
    coalesce(a.scheduled_end_at, w.scheduled_end_at),
    a.status
  from public.work_order_assignments a
  join public.work_orders w on w.id = a.work_order_id
  left join public.complaints c on c.id = w.complaint_id
 where a.staff_assignment_id = p_staff_id
   and a.status in ('offered', 'accepted')
   and w.status not in ('completed', 'cancelled', 'failed')
   and (p_from is null
        or coalesce(a.scheduled_start_at, w.scheduled_start_at) is null
        or coalesce(a.scheduled_start_at, w.scheduled_start_at) >= p_from)
  union all
  select
    'security_shift'::text,
    s.id,
    s.post_id,
    coalesce(nullif(btrim(coalesce(p.name, '')), ''), 'Shift'),
    s.starts_at,
    s.ends_at,
    s.status
  from public.security_shifts s
  left join public.security_posts p on p.id = s.post_id
 where s.staff_assignment_id = p_staff_id
   and s.status in ('scheduled', 'active')
   and (p_from is null or s.starts_at >= p_from)
  order by 5 nulls last;
$$;

comment on function public.staff_departure_items(uuid, timestamptz) is
  'Everything still booked in one roster row''s name from a moment onward (null = everything, unscheduled items always included). The conflict list a decision is made against.';

create or replace function public.staff_conflict_count(
  p_staff_id uuid,
  p_from     timestamptz default null
)
returns integer
language sql
stable
security definer
set search_path = public
as $$
  select (
    (select count(*)
       from public.work_order_assignments a
       join public.work_orders w on w.id = a.work_order_id
      where a.staff_assignment_id = p_staff_id
        and a.status in ('offered', 'accepted')
        and w.status not in ('completed', 'cancelled', 'failed')
        and (p_from is null
             or coalesce(a.scheduled_start_at, w.scheduled_start_at) is null
             or coalesce(a.scheduled_start_at, w.scheduled_start_at) >= p_from))
    +
    (select count(*)
       from public.security_shifts s
      where s.staff_assignment_id = p_staff_id
        and s.status in ('scheduled', 'active')
        and (p_from is null or s.starts_at >= p_from))
  )::integer;
$$;

comment on function public.staff_conflict_count(uuid, timestamptz) is
  'How many booked items would be stranded by a departure effective at a moment. Null = all of them; the number an approval releases.';

create or replace function public.staff_schedule_items(
  p_staff_id uuid,
  p_from     timestamptz default null,
  p_to       timestamptz default null
)
returns table (
  item_kind    text,
  item_id      uuid,
  reference_id uuid,
  title        text,
  starts_at    timestamptz,
  ends_at      timestamptz,
  item_status  text
)
language sql
stable
security definer
set search_path = public
as $$
  select
    'work_order'::text,
    a.id,
    w.id,
    coalesce(nullif(btrim(coalesce(c.title, '')), ''), 'Scheduled work'),
    coalesce(a.scheduled_start_at, w.scheduled_start_at),
    coalesce(a.scheduled_end_at, w.scheduled_end_at),
    a.status
  from public.work_order_assignments a
  join public.work_orders w on w.id = a.work_order_id
  left join public.complaints c on c.id = w.complaint_id
 where a.staff_assignment_id = p_staff_id
   and a.status not in ('declined', 'withdrawn')
   and (
     coalesce(a.scheduled_start_at, w.scheduled_start_at) is null
     or (
       (p_from is null or coalesce(a.scheduled_start_at, w.scheduled_start_at) >= p_from)
       and (p_to is null or coalesce(a.scheduled_start_at, w.scheduled_start_at) < p_to)
     )
   )
  union all
  select
    'security_shift'::text,
    s.id,
    s.post_id,
    coalesce(nullif(btrim(coalesce(p.name, '')), ''), 'Shift'),
    s.starts_at,
    s.ends_at,
    s.status
  from public.security_shifts s
  left join public.security_posts p on p.id = s.post_id
 where s.staff_assignment_id = p_staff_id
   and s.status <> 'cancelled'
   and (p_from is null or s.starts_at >= p_from)
   and (p_to is null or s.starts_at < p_to)
  order by 5 nulls last;
$$;

comment on function public.staff_schedule_items(uuid, timestamptz, timestamptz) is
  'One employee''s calendar: jobs and shifts in a window, unscheduled jobs always shown. Unlike staff_departure_items it keeps finished work — a schedule page shows what happened, not only what looms.';

create or replace function public.departure_coverage(p_departure_id uuid)
returns table (
  item_kind       text,
  item_id         uuid,
  reference_id    uuid,
  title           text,
  starts_at       timestamptz,
  ends_at         timestamptz,
  item_status     text,
  candidate_count integer,
  candidate_names text[]
)
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_dep     public.staff_departures%rowtype;
  v_barrier timestamptz;
  v_item    record;
  v_count   integer;
  v_names   text[];
begin
  select * into v_dep from public.staff_departures where id = p_departure_id;
  if not found then
    raise exception 'No such departure.' using errcode = 'HB404';
  end if;

  v_barrier := coalesce(v_dep.effective_at, v_dep.requested_effective_at);

  for v_item in
    select * from public.staff_departure_items(v_dep.staff_assignment_id, v_barrier)
  loop
    if v_item.item_kind = 'work_order' then
      select count(*)::integer, coalesce(array_agg(c.display_name), '{}')
        into v_count, v_names
        from public.dispatch_candidates(v_item.reference_id, 5) c;
    else
      select count(*)::integer, coalesce(array_agg(c.display_name), '{}')
        into v_count, v_names
        from public.security_shift_candidates(v_item.item_id, 5) c;
    end if;

    item_kind       := v_item.item_kind;
    item_id         := v_item.item_id;
    reference_id    := v_item.reference_id;
    title           := v_item.title;
    starts_at       := v_item.starts_at;
    ends_at         := v_item.ends_at;
    item_status     := v_item.item_status;
    candidate_count := v_count;
    candidate_names := v_names;
    return next;
  end loop;
end;
$$;

comment on function public.departure_coverage(uuid) is
  'The manager''s match button: each item this departure would strand, with up to five people who could take it. A zero count IS the answer "there are none" — an unscheduled job also counts zero, because the sweep cannot place work with no slot.';

-- ---------------------------------------------------------------------------
-- 12. The views learn the dates
--
-- Both recreated (a recreate drops grants; reissued below). The roster view's
-- departure subquery widens from pending-only to pending-or-approved-awaiting,
-- because a roster row whose leave is approved for Friday should read
-- "leaving Friday", not nothing.
-- ---------------------------------------------------------------------------

drop view if exists public.department_staff_overview;
create view public.department_staff_overview
with (security_invoker = true) as
select
  s.id,
  s.community_id,
  s.department_id,
  s.membership_id,
  s.service_provider_id,
  s.display_name,
  s.phone_e164,
  s.job_title,
  s.rank,
  s.shift,
  s.status,
  s.created_at,
  s.updated_at,
  coalesce(a.active_assignment_count, 0) as active_assignment_count,
  public.staff_open_commitment_count(s.id) as open_commitment_count,
  dep.status       as departure_status,
  dep.effective_at as departure_effective_at
from public.staff_assignments s
left join lateral (
  select count(*) as active_assignment_count
    from public.complaints c
   where c.department_id = s.department_id
     and c.status in ('open', 'acknowledged', 'in_progress')
     and (
       (s.membership_id is not null and c.assigned_to_membership_id = s.membership_id)
       or (
         s.display_name is not null
         and length(s.display_name) > 0
         and c.assignee_label is not null
         and left(c.assignee_label, length(s.display_name)) = s.display_name
       )
     )
) a on true
left join lateral (
  select d.status,
         coalesce(d.effective_at, d.requested_effective_at) as effective_at
    from public.staff_departures d
   where d.staff_assignment_id = s.id
     and (d.status = 'pending'
          or (d.status = 'approved'
              and d.effective_at is not null
              and d.effective_at > now()))
   order by d.created_at desc
   limit 1
) dep on true;

comment on view public.department_staff_overview is
  'Staff assignments with open-complaint and booked-item counts, the provider behind the row, and — when they are on their way out — the departure''s status and date.';

grant select on public.department_staff_overview to authenticated;

drop view if exists public.staff_departure_overview;
create view public.staff_departure_overview
with (security_invoker = true) as
select
  d.id,
  d.community_id,
  d.department_id,
  d.staff_assignment_id,
  d.service_provider_id,
  d.initiated_by,
  d.reason,
  d.status,
  d.requested_effective_at,
  d.effective_at,
  d.decided_at,
  d.decision_note,
  d.created_at,
  d.updated_at,
  s.display_name,
  s.rank,
  s.job_title,
  s.membership_id,
  dep.name as department_name,
  dep.kind as department_kind,
  public.staff_open_commitment_count(d.staff_assignment_id) as open_commitment_count,
  public.staff_conflict_count(
    d.staff_assignment_id,
    coalesce(d.effective_at, d.requested_effective_at)) as conflict_count
from public.staff_departures d
join public.staff_assignments s on s.id = d.staff_assignment_id
join public.departments dep     on dep.id = d.department_id;

comment on view public.staff_departure_overview is
  'A departure with the person it is about, its dates, everything they hold (open_commitment_count) and what the leave would actually strand (conflict_count).';

grant select on public.staff_departure_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 13. Grants
--
-- Dropped-and-recreated functions lost theirs; `create or replace` kept the
-- rest. Everything follows the 0037/0043 posture: revoke from PUBLIC first,
-- then grant narrowly.
-- ---------------------------------------------------------------------------

revoke all on function public.enqueue_dispatch_task(uuid, text, timestamptz, smallint)
  from public, anon, authenticated;

revoke all on function public.enqueue_departure_task(uuid, text, timestamptz)
  from public, anon, authenticated;

revoke all on function public.claim_dispatch_batch(integer)
  from public, anon, authenticated;
grant execute on function public.claim_dispatch_batch(integer) to service_role;

revoke all on function public.release_staff_commitments(uuid, text, timestamptz, smallint)
  from public, anon, authenticated;
grant execute on function public.release_staff_commitments(uuid, text, timestamptz, smallint)
  to service_role;

revoke all on function public.request_staff_departure(uuid, text, timestamptz)
  from public, anon, authenticated;
grant execute on function public.request_staff_departure(uuid, text, timestamptz)
  to authenticated;

revoke all on function public.decide_staff_departure(uuid, text, text, timestamptz)
  from public, anon, authenticated;
grant execute on function public.decide_staff_departure(uuid, text, text, timestamptz)
  to authenticated;

revoke all on function public.dispatch_departure_removal(uuid)
  from public, anon, authenticated;
grant execute on function public.dispatch_departure_removal(uuid) to service_role;

revoke all on function public.staff_departure_items(uuid, timestamptz)
  from public, anon, authenticated;
grant execute on function public.staff_departure_items(uuid, timestamptz) to service_role;

revoke all on function public.staff_conflict_count(uuid, timestamptz)
  from public, anon, authenticated;
grant execute on function public.staff_conflict_count(uuid, timestamptz) to authenticated;

revoke all on function public.staff_schedule_items(uuid, timestamptz, timestamptz)
  from public, anon, authenticated;
grant execute on function public.staff_schedule_items(uuid, timestamptz, timestamptz)
  to service_role;

revoke all on function public.departure_coverage(uuid)
  from public, anon, authenticated;
grant execute on function public.departure_coverage(uuid) to service_role;

-- ---------------------------------------------------------------------------
-- 14. The name stops being editable from settings
--
-- The same 2026-08-10 ruling's other half: a service person's name and email
-- are identity, changed nowhere in settings. 0034's upsert overwrote
-- `display_name` unconditionally and required it, which forced every profile
-- edit to restate the name — and therefore allowed every profile edit to
-- change it. A null name now coalesces onto the stored value, exactly like
-- the other six fields; only registration, which has nothing stored to
-- coalesce onto, still requires one.
-- ---------------------------------------------------------------------------

create or replace function public.upsert_service_provider(
  p_display_name      text,
  p_headline          text default null,
  p_bio               text default null,
  p_phone_e164        text default null,
  p_latitude          numeric default null,
  p_longitude         numeric default null,
  p_service_radius_km numeric default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  if auth.uid() is null then
    raise exception 'Sign in required.' using errcode = '42501';
  end if;

  -- A name is required only when there is nothing stored to keep.
  if not exists (select 1 from public.service_providers
                  where profile_id = auth.uid())
     and (p_display_name is null or length(btrim(p_display_name)) < 2) then
    raise exception 'A name is required.' using errcode = '22004';
  end if;

  if p_display_name is not null and length(btrim(p_display_name)) < 2 then
    raise exception 'A name is required.' using errcode = '22004';
  end if;

  insert into public.service_providers as sp (
    profile_id, display_name, headline, bio, phone_e164,
    latitude, longitude, service_radius_km
  )
  values (
    auth.uid(), btrim(p_display_name), p_headline, p_bio, p_phone_e164,
    p_latitude, p_longitude, coalesce(p_service_radius_km, 15)
  )
  on conflict (profile_id) do update
     set display_name      = coalesce(btrim(p_display_name), sp.display_name),
         headline          = coalesce(p_headline, sp.headline),
         bio               = coalesce(p_bio, sp.bio),
         phone_e164        = coalesce(p_phone_e164, sp.phone_e164),
         latitude          = coalesce(p_latitude, sp.latitude),
         longitude         = coalesce(p_longitude, sp.longitude),
         service_radius_km = coalesce(p_service_radius_km, sp.service_radius_km)
  returning sp.id into v_id;

  return v_id;
end;
$$;

comment on function public.upsert_service_provider(text, text, text, text, numeric, numeric, numeric) is
  'Register or edit a service-provider profile. Since 0045 a null name keeps the stored one — settings edit details, never identity.';
