-- Leaving a community is a process a manager approves, not a statement.
--
-- docs/plans/SERVICE_OPERATIONS_PROGRESS.md 6.12.
--
-- WHAT A DEPARTURE USED TO BE
--
-- `remove_department_member` (0035 section 7) is one function and four
-- statements: set the roster row inactive, end the membership, notify, return.
-- It says nothing at all about the work the person was holding, and the work
-- does not go away. A `work_order_assignments` row with `status = 'accepted'`
-- survives untouched -- still pointing at tomorrow's slot, still counted as
-- somebody's load by `dispatch_candidates`, still rendering on the resident's
-- complaint as *someone is coming*. Nobody is coming, and the membership that
-- would have carried the reminder has just ended, so the one person who could
-- have said so has been logged out.
--
-- The same hole is open on the other side of the wall. `security_shifts` rows
-- keep pointing at a guard who is no longer employed, and the gate rota reads
-- as covered.
--
-- WHAT IT IS NOW
--
-- A departure is a **state a person is in** rather than an event that happens
-- to them. Between *I want to leave* and *you have left* there is an interval
-- in which two things are true:
--
--   1. the engine stops giving them new work, immediately, on the request and
--      not on the approval; and
--   2. everything they already hold is moved to somebody else, one item at a
--      time, by a human looking at the list.
--
-- Approval is refused while that list is non-empty. That refusal is the whole
-- feature; everything else in this file exists to make it survivable.
--
-- THE FREEZE IS THE PART THAT IS EASY TO MISS
--
-- Without section 8, handover is a treadmill: a supervisor reassigns three jobs
-- and, while they are doing it, `dispatch_ping_candidates` and
-- `dispatch_auto_assign` hand the same person two more, because nothing in the
-- sweep knows they are leaving. So the sweep learns, and two triggers stand
-- behind it as the guarantee -- the same division of labour `0036` argued for
-- when it put an exclusion constraint behind a double-booking check.
--
-- WHY A BAR DOES NOT WAIT FOR A HANDOVER
--
-- Section 10 is the exception and it is deliberate. Somebody barred for
-- misconduct keeping tomorrow's job until a supervisor has found five
-- successors is the opposite of what a bar is for. So `blacklist_service_
-- provider` *releases* rather than hands over: it withdraws the assignments,
-- returns each work order to `offered` -- which re-arms the dispatch ping by
-- itself through `sync_dispatch_tasks` (0037 section 2), so the engine finds
-- the replacements -- cancels the future shifts, and tells the department how
-- many items it moved. An orderly departure hands over; a bar ejects and the
-- engine re-dispatches.
--
-- NO `handover` STATUS
--
-- `pending | approved | rejected | cancelled`, and "handover in progress" is
-- *pending with a non-zero outstanding count*. A status derivable from a count
-- is a status that can disagree with the count, and the count is the thing the
-- approval is actually gated on.

-- ---------------------------------------------------------------------------
-- 1. The request
-- ---------------------------------------------------------------------------

create table if not exists public.staff_departures (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.communities(id) on delete cascade,
  department_id       uuid not null,
  staff_assignment_id uuid not null references public.staff_assignments(id) on delete cascade,
  service_provider_id uuid references public.service_providers(id) on delete set null,
  initiated_by        text not null default 'worker',
  requested_by_membership_id uuid references public.community_memberships(id) on delete set null,
  reason              text,
  status              text not null default 'pending',
  decided_by_membership_id   uuid references public.community_memberships(id) on delete set null,
  decided_at          timestamptz,
  decision_note       text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

do $$
begin
  -- The composite tenant key, for the reason 4.14 records: a department belongs
  -- to exactly one community, and a departure that named a department in one
  -- community and a community in another would be unnoticeable in every read.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.staff_departures'::regclass
       and conname  = 'staff_departures_department_tenant_fkey'
  ) then
    alter table public.staff_departures
      add constraint staff_departures_department_tenant_fkey
      foreign key (department_id, community_id)
      references public.departments (id, community_id) on delete cascade;
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.staff_departures'::regclass
       and conname  = 'staff_departures_status_check'
  ) then
    alter table public.staff_departures
      add constraint staff_departures_status_check
      check (status in ('pending', 'approved', 'rejected', 'cancelled'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.staff_departures'::regclass
       and conname  = 'staff_departures_initiated_by_check'
  ) then
    alter table public.staff_departures
      add constraint staff_departures_initiated_by_check
      check (initiated_by in ('worker', 'manager'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.staff_departures'::regclass
       and conname  = 'staff_departures_decision_check'
  ) then
    -- A decided row records who decided and when, or it records neither. The
    -- pair is what an audit reads; half of it is worse than none, because it
    -- looks answered.
    alter table public.staff_departures
      add constraint staff_departures_decision_check
      check (
        (status = 'pending' and decided_at is null)
        or (status <> 'pending' and decided_at is not null)
      );
  end if;
end $$;

-- One open request per roster row. The same concurrency story as
-- `service_applications_one_open` in 0035: two clicks race, one row exists.
create unique index if not exists staff_departures_one_open
  on public.staff_departures (staff_assignment_id)
  where status = 'pending';

create index if not exists staff_departures_department_idx
  on public.staff_departures (department_id, status, created_at desc);

comment on table public.staff_departures is
  'A request to leave a department roster, and the handover it is gated on. Opened by the worker or by a manager on their behalf; approved only when nothing is left in their name.';

-- ---------------------------------------------------------------------------
-- 2. Is this person leaving?
--
-- One predicate, used by the sweep, by both triggers and by the read policies,
-- for the reason 0036 section 4 gives: a rule spelled one way in a policy and
-- another way in the function that writes past it is how a hole opens.
-- ---------------------------------------------------------------------------

create or replace function public.has_pending_departure(p_staff_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.staff_departures d
     where d.staff_assignment_id = p_staff_id
       and d.status = 'pending'
  );
$$;

comment on function public.has_pending_departure(uuid) is
  'True while a roster row has an open departure request. The freeze: no new work may be booked against them, and the sweep does not offer them any.';

revoke all on function public.has_pending_departure(uuid)
  from public, anon, authenticated;
grant execute on function public.has_pending_departure(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 3. What is still in their name
--
-- Two kinds, and the answer covers both because the instruction did: *the same
-- applies for all servicemen regardless of department*. A plumber holds work
-- orders and a guard holds shifts, and a departure that counted only the first
-- would approve every security departure on the spot.
--
-- NEITHER IS FILTERED ON `starts_at > now()`, AND THAT IS DELIBERATE
--
-- A scheduled job whose slot was yesterday and which nobody closed is exactly
-- what a departing worker leaves behind. Filtering it out would let the
-- departure approve while a stale job still sat in their name -- the failure
-- this file exists to prevent, reintroduced by a `where` clause that looks like
-- tidiness. The count answers *what does this person still hold*, not *what is
-- still in the future*. A manager who thinks a stale item should simply die has
-- `cancel_work_order` and `update_security_shift` already.
-- ---------------------------------------------------------------------------

create or replace function public.staff_departure_items(p_staff_id uuid)
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
  order by 5 nulls last;
$$;

comment on function public.staff_departure_items(uuid) is
  'Everything still booked in one roster row''s name, jobs and shifts together. The list a handover works through, and the count an approval is refused for.';

-- Deliberately not `select count(*) from staff_departure_items(...)`.
--
-- That function returns complaint titles and post names, so it stays
-- service_role only and the API reads it through a service that has already
-- authorised the caller. The count leaks nothing but a number against a uuid
-- somebody already holds, so it is granted to `authenticated` and the two views
-- below can use it. The predicates are duplicated; the projections are not, and
-- that is the trade being made.
create or replace function public.staff_open_commitment_count(p_staff_id uuid)
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
        and w.status not in ('completed', 'cancelled', 'failed'))
    +
    (select count(*)
       from public.security_shifts s
      where s.staff_assignment_id = p_staff_id
        and s.status in ('scheduled', 'active'))
  )::integer;
$$;

comment on function public.staff_open_commitment_count(uuid) is
  'How many jobs and shifts are still booked against a roster row. Zero is the condition a departure is approved on.';

revoke all on function public.staff_departure_items(uuid)
  from public, anon, authenticated;
grant execute on function public.staff_departure_items(uuid) to service_role;

revoke all on function public.staff_open_commitment_count(uuid)
  from public, anon, authenticated;
grant execute on function public.staff_open_commitment_count(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 4. Reads
--
-- `department_staff_overview` is recreated for the third time in this build,
-- and 0042's header names why that keeps happening: a field only the write path
-- uses looks complete in every test, because the test asserts the write. This
-- time the missing field is being added **before** the screen that needs it,
-- not after it failed. The roster tab has to decide per row whether to offer
-- *Remove* or *Start handover*, and that decision is a count it cannot compute.
--
-- Recreating a view drops its grants (0042, same section), so the grant is
-- reissued below.
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
  -- The two new ones.
  public.staff_open_commitment_count(s.id) as open_commitment_count,
  (select d.status
     from public.staff_departures d
    where d.staff_assignment_id = s.id
      and d.status = 'pending'
    limit 1) as departure_status
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
) a on true;

comment on view public.department_staff_overview is
  'Staff assignments with the number of open complaints each member holds, the service provider behind the row when there is one, how many jobs and shifts are still booked in their name, and whether they are on their way out.';

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
  public.staff_open_commitment_count(d.staff_assignment_id) as open_commitment_count
from public.staff_departures d
join public.staff_assignments s on s.id = d.staff_assignment_id
join public.departments dep     on dep.id = d.department_id;

comment on view public.staff_departure_overview is
  'A departure request with the person it is about and how much of their handover is left.';

grant select on public.staff_departure_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 5. Telling the department
--
-- *"this would notify the supervisors too."*
--
-- No existing helper reaches a supervisor. `notify_community_staff` (0031
-- section 3) is every admin and manager in the community;
-- `notify_community_roles` (0032) is by membership role. A supervisor is
-- neither -- D3 settled that a supervisor is a **rank on a roster row in one
-- department**, on purpose, so that a person can supervise plumbing without
-- being a manager of the society. That decision is exactly why this helper has
-- to exist.
-- ---------------------------------------------------------------------------

create or replace function public.notify_department_leadership(
  p_department_id      uuid,
  p_kind               text,
  p_payload            jsonb default '{}'::jsonb,
  p_exclude_membership uuid default null
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid;
  v_sent      integer := 0;
  v_row       record;
begin
  select community_id into v_community
    from public.departments where id = p_department_id;
  if v_community is null then
    return 0;
  end if;

  for v_row in
    -- `distinct` because a manager of the society who also sits on this
    -- department's roster as its head satisfies both arms, and being told twice
    -- about one departure reads as a bug in the app.
    select distinct m.id
      from public.community_memberships m
     where m.community_id = v_community
       and m.status = 'active'
       and m.ended_at is null
       and (p_exclude_membership is null or m.id <> p_exclude_membership)
       and (
         m.role = 'admin'
         or (m.role = 'manager'
             and (m.department_id is null or m.department_id = p_department_id))
         or exists (
              select 1
                from public.staff_assignments sa
               where sa.department_id = p_department_id
                 and sa.membership_id = m.id
                 and sa.status = 'active'
                 and sa.rank in ('manager', 'supervisor')
            )
       )
  loop
    perform public.notify_member(v_row.id, p_kind, p_payload);
    v_sent := v_sent + 1;
  end loop;

  return v_sent;
end;
$$;

comment on function public.notify_department_leadership(uuid, text, jsonb, uuid) is
  'Notify the people who run one department: its managers and supervisors by rank, plus the community''s admins. The audience notify_community_staff cannot express, because a supervisor is not a membership role.';

revoke all on function public.notify_department_leadership(uuid, text, jsonb, uuid)
  from public, anon, authenticated;
grant execute on function public.notify_department_leadership(uuid, text, jsonb, uuid)
  to service_role;

-- ---------------------------------------------------------------------------
-- 6. Opening, cancelling and deciding
-- ---------------------------------------------------------------------------

create or replace function public.request_staff_departure(
  p_staff_id uuid,
  p_reason   text default null
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
      initiated_by, requested_by_membership_id, reason
    )
    values (
      v_staff.community_id, v_staff.department_id, p_staff_id,
      v_staff.service_provider_id,
      case when v_is_own then 'worker' else 'manager' end,
      v_actor,
      nullif(btrim(coalesce(p_reason, '')), '')
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
               || ' is leaving ' || coalesce(v_department.name, 'a department'),
      'body', case
                when v_is_own then 'They asked to leave. Their work has to be handed over first.'
                else 'Their work has to be handed over before this can be approved.'
              end,
      'url', '/admin/departments/' || v_staff.department_id::text
             || '/hiring?tab=departures&departure=' || v_id::text,
      'departureId', v_id,
      'departmentId', v_staff.department_id,
      'staffId', p_staff_id),
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

comment on function public.request_staff_departure(uuid, text) is
  'Open a departure. Either side may: the person leaving, or a manager on their behalf. Freezes the engine against them from this moment.';

create or replace function public.cancel_staff_departure(p_departure_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_dep    public.staff_departures%rowtype;
  v_is_own boolean;
begin
  select * into v_dep from public.staff_departures where id = p_departure_id;
  if not found then
    raise exception 'No such departure.' using errcode = 'HB404';
  end if;

  if v_dep.status <> 'pending' then
    raise exception 'That departure has already been decided.'
      using errcode = 'HB409';
  end if;

  v_is_own := public.is_own_staff_assignment(v_dep.staff_assignment_id);

  if not (v_is_own or public.can_manage_department(v_dep.department_id)) then
    raise exception 'You may not withdraw this departure.' using errcode = 'HB403';
  end if;

  update public.staff_departures
     set status     = 'cancelled',
         decided_at = now(),
         updated_at = now()
   where id = p_departure_id;

  perform public.notify_department_leadership(
    v_dep.department_id, 'departure.cancelled',
    jsonb_build_object(
      'title', 'A departure was withdrawn',
      'url', '/admin/departments/' || v_dep.department_id::text || '/hiring?tab=departures',
      'departureId', v_dep.id,
      'departmentId', v_dep.department_id),
    v_dep.requested_by_membership_id);
end;
$$;

comment on function public.cancel_staff_departure(uuid) is
  'Withdraw an open departure and lift the freeze. Available to whoever could have opened it.';

create or replace function public.decide_staff_departure(
  p_departure_id uuid,
  p_decision     text,
  p_note         text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_dep      public.staff_departures%rowtype;
  v_staff    public.staff_assignments%rowtype;
  v_decision text := nullif(btrim(lower(coalesce(p_decision, ''))), '');
  v_left     integer;
  v_actor    uuid;
  v_name     text;
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

  -- The refusal this whole file exists for.
  v_left := public.staff_open_commitment_count(v_dep.staff_assignment_id);
  if v_left > 0 then
    raise exception
      '% still has % item(s) to hand over.', v_staff.display_name, v_left
      using errcode = 'HB409';
  end if;

  update public.staff_departures
     set status                   = 'approved',
         decided_by_membership_id = v_actor,
         decided_at               = now(),
         decision_note            = nullif(btrim(coalesce(p_note, '')), ''),
         updated_at               = now()
   where id = p_departure_id;

  -- One removal path, not two. `remove_department_member` ends the membership,
  -- deactivates the row and sends `service_engagement_ended`; it also refuses
  -- when anything is outstanding, which is now impossible here and is the point
  -- -- the guard lives in the function every removal funnels through rather
  -- than in each caller.
  perform public.remove_department_member(
    v_dep.staff_assignment_id,
    nullif(btrim(coalesce(p_note, v_dep.reason, '')), ''));

  perform public.notify_department_leadership(
    v_dep.department_id, 'departure.approved',
    jsonb_build_object(
      'title', coalesce(v_staff.display_name, 'Someone')
               || ' has left ' || coalesce(v_name, 'the department'),
      'url', '/admin/departments/' || v_dep.department_id::text || '/hiring?tab=roster',
      'departureId', v_dep.id,
      'departmentId', v_dep.department_id),
    v_actor);
end;
$$;

comment on function public.decide_staff_departure(uuid, text, text) is
  'Approve or reject a departure. Approval is refused while anything is still booked in that person''s name, and calls remove_department_member when it is not.';

-- ---------------------------------------------------------------------------
-- 7. The handover
--
-- *"the reassignment should follow the same assignment logic as the auto
-- assignment"* -- so it does, literally: `dispatch_candidates` is the ranking,
-- and `assign_work_order` is the writer. Neither is reimplemented here.
-- Reimplementing the second would be a second definition of *book this person
-- on this job*, and it would drift from the first the day one of them learns
-- something the other does not.
--
-- Guards have no sweep, so they get one. The sort key is honestly different:
-- adjacency does not transfer, because a guard's shifts are a rota and not a
-- route, and copying "already in this community today" would be copying a
-- clause that means nothing here.
--
-- AN OFFER AND AN ACCEPTANCE ARE HANDED OVER DIFFERENTLY
--
-- An `accepted` row is a booking and needs a successor. An `offered` row is a
-- question nobody has answered -- the same question is sitting in four other
-- workers' feeds -- so it is withdrawn and the ping re-armed, which lets the
-- engine do what it was already doing. Picking a successor for an offer would
-- convert a question into a booking, quietly, and the person who ends up with
-- the job would never have been asked.
-- ---------------------------------------------------------------------------

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
     and not public.has_pending_departure(sa.id)
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

revoke all on function public.security_shift_candidates(uuid, integer)
  from public, anon, authenticated;
grant execute on function public.security_shift_candidates(uuid, integer) to service_role;

create or replace function public.reassign_departure_item(
  p_departure_id        uuid,
  p_item_kind           text,
  p_item_id             uuid,
  p_staff_assignment_id uuid default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_dep        public.staff_departures%rowtype;
  v_kind       text := nullif(btrim(lower(coalesce(p_item_kind, ''))), '');
  v_assignment public.work_order_assignments%rowtype;
  v_shift      public.security_shifts%rowtype;
  v_successor  uuid := p_staff_assignment_id;
  v_target     public.staff_assignments%rowtype;
  v_pick       record;
  v_new        uuid;
begin
  select * into v_dep from public.staff_departures where id = p_departure_id;
  if not found then
    raise exception 'No such departure.' using errcode = 'HB404';
  end if;

  -- Supervisors do handovers. That is the difference between this guard and
  -- `decide_staff_departure`'s.
  if not public.can_supervise_department(v_dep.department_id) then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;

  if v_dep.status <> 'pending' then
    raise exception 'That departure has already been decided.' using errcode = 'HB409';
  end if;

  if v_successor is not null then
    select * into v_target from public.staff_assignments where id = v_successor;
    if not found or v_target.department_id <> v_dep.department_id
       or v_target.status <> 'active' then
      raise exception 'That person is not on this department''s roster.'
        using errcode = 'HB404';
    end if;
    if v_successor = v_dep.staff_assignment_id then
      raise exception 'They cannot hand the work to themselves.'
        using errcode = 'HB409';
    end if;
  end if;

  if v_kind = 'work_order' then
    select * into v_assignment
      from public.work_order_assignments
     where id = p_item_id and staff_assignment_id = v_dep.staff_assignment_id;
    if not found then
      raise exception 'That job is not in their name.' using errcode = 'HB404';
    end if;

    if v_assignment.status = 'offered' then
      -- Withdraw the question and ask it again. See the section header.
      update public.work_order_assignments
         set status = 'withdrawn', responded_at = now(), ended_at = now()
       where id = v_assignment.id;
      perform public.enqueue_dispatch_task(v_assignment.work_order_id, 'ping', now());
      return null;
    end if;

    if v_successor is null then
      select * into v_pick
        from public.dispatch_candidates(v_assignment.work_order_id, 1);
      if not found then
        raise exception
          'Nobody in this department is free for that slot. Pick someone, reschedule it or cancel it.'
          using errcode = 'HB409';
      end if;
      v_successor := v_pick.staff_assignment_id;
    end if;

    -- The writer, unchanged: it withdraws the incumbent, books the successor,
    -- writes the complaint event and tells both the new worker and the resident.
    v_new := public.assign_work_order(v_assignment.work_order_id, v_successor);
    return v_new;

  elsif v_kind = 'security_shift' then
    select * into v_shift
      from public.security_shifts
     where id = p_item_id and staff_assignment_id = v_dep.staff_assignment_id;
    if not found then
      raise exception 'That shift is not in their name.' using errcode = 'HB404';
    end if;

    if v_successor is null then
      select * into v_pick from public.security_shift_candidates(p_item_id, 1);
      if not found then
        raise exception
          'Nobody else in this department is free for that shift. Pick someone or cancel it.'
          using errcode = 'HB409';
      end if;
      v_successor := v_pick.staff_assignment_id;
    end if;

    -- Written here rather than through `update_security_shift`, which cannot
    -- change who is standing there and whose authorisation is the gate
    -- manager's rather than the department's.
    update public.security_shifts
       set staff_assignment_id = v_successor,
           updated_at          = now()
     where id = p_item_id;

    select * into v_target from public.staff_assignments where id = v_successor;
    if v_target.membership_id is not null then
      -- **Corrected 2026-08-11.** This read `/security-manager/shifts?shift=`,
      -- which is wrong twice over. The recipient is `v_target` -- the guard the
      -- shift was handed *to* -- not the manager who moved it, so the manager
      -- prefix does not belong here at all; and `/security-manager/shifts` is
      -- not a route either, the manager's shift screen being
      -- `/security-manager/roster?tab=shifts`. `/security/shifts` is the guard's
      -- own screen and the same target `0040:893` already uses for
      -- `shift.scheduled`, which is the notification this one is a sequel to.
      perform public.notify_member(
        v_target.membership_id, 'security_shift.assigned',
        jsonb_build_object(
          'title', 'A shift was handed to you',
          'body', to_char(v_shift.starts_at, 'DD Mon, HH24:MI'),
          'url', '/security/shifts?shift=' || p_item_id::text,
          'shiftId', p_item_id,
          'startsAt', v_shift.starts_at,
          'endsAt', v_shift.ends_at));
    end if;

    return v_successor;
  end if;

  raise exception 'A handover item is a work_order or a security_shift.'
    using errcode = '22P02';
end;
$$;

comment on function public.reassign_departure_item(uuid, text, uuid, uuid) is
  'Move one job or shift off a departing person. No successor named means take the best candidate the dispatch ranking returns.';

-- ---------------------------------------------------------------------------
-- 8. The freeze
--
-- Two halves, and both are needed. The sweep learns, so the engine picks
-- somebody who can actually take the work; the triggers stand behind it, so
-- that no other writer -- a supervisor assigning by hand, a worker accepting an
-- offer that predates their own resignation, whatever gets written next year --
-- can put work back into a departing person's name. `0036` made the same
-- division when it put an exclusion constraint behind an overlap check and said
-- so in as many words: the constraint is the guarantee and the sweep is only
-- the guess.
-- ---------------------------------------------------------------------------

create or replace function public.block_departing_assignment()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status in ('offered', 'accepted')
     and public.has_pending_departure(new.staff_assignment_id) then
    raise exception 'That person is leaving and cannot take new work.'
      using errcode = 'HB409';
  end if;
  return new;
end;
$$;

drop trigger if exists work_order_assignments_block_departing
  on public.work_order_assignments;
create trigger work_order_assignments_block_departing
  before insert or update of status, staff_assignment_id
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
     -- The handover itself moves a shift **to** somebody, and the person it
     -- moves it away from is the one who is leaving. Only the new holder is
     -- checked, which is what `new.staff_assignment_id` means here.
     and public.has_pending_departure(new.staff_assignment_id) then
    raise exception 'That person is leaving and cannot take new shifts.'
      using errcode = 'HB409';
  end if;
  return new;
end;
$$;

drop trigger if exists security_shifts_block_departing on public.security_shifts;
create trigger security_shifts_block_departing
  before insert or update of status, staff_assignment_id
  on public.security_shifts
  for each row execute function public.block_departing_shift();

-- ---------------------------------------------------------------------------
-- 9. Removal, with the guard it never had
--
-- Same signature, same four statements, one refusal in front of them and a
-- `url` on the notification it always sent -- the last of the five 0035 hiring
-- notifications the journal recorded as unclickable (5.18). The other four are
-- fixed in `notifications_service.py`, where the fallback title for those same
-- kinds already lives.
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
begin
  select * into v_staff from public.staff_assignments where id = p_staff_id;
  if not found then
    raise exception 'No such roster entry.' using errcode = 'HB404';
  end if;

  if not public.can_manage_department(v_staff.department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  -- The safety net. Every removal path funnels through this function --
  -- including `blacklist_service_provider`, which is why section 10 has to
  -- release first -- so this one check is what makes it true that nobody is
  -- removed while still holding work.
  v_left := public.staff_open_commitment_count(p_staff_id);
  if v_left > 0 then
    raise exception
      '% still holds % job(s) or shift(s). Open a departure and hand them over first.',
      v_staff.display_name, v_left
      using errcode = 'HB409';
  end if;

  select name into v_name from public.departments where id = v_staff.department_id;

  update public.staff_assignments
     set status     = 'inactive',
         is_active  = false,
         rank       = 'member',
         ended_at   = current_date,
         updated_at = now()
   where id = p_staff_id;

  -- A departure that was still open when the row was removed by hand is
  -- answered by the removal. Leaving it pending would leave a freeze on a
  -- roster row nobody can be booked onto anyway, and an open request in a
  -- manager's list that can never be approved.
  update public.staff_departures
     set status                   = 'approved',
         decided_at               = coalesce(decided_at, now()),
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
  'Take somebody off a roster and end their membership. Refuses while anything is still booked in their name -- the handover is opened with request_staff_departure.';

-- ---------------------------------------------------------------------------
-- 10. A bar ejects; it does not queue
--
-- The asymmetry argued at the top of this file, implemented. `release_staff_
-- commitments` is the *other* answer to an outstanding list: instead of finding
-- each item a successor, it puts the jobs back where the engine can see them
-- and cancels the shifts. It is deliberately not offered as a handover option
-- -- a manager who wants this outcome for an ordinary departure wants
-- `cancel_work_order`, one job at a time, with a reason.
-- ---------------------------------------------------------------------------

create or replace function public.release_staff_commitments(
  p_staff_id uuid,
  p_reason   text default null
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row     record;
  v_released integer := 0;
begin
  for v_row in
    select a.id as assignment_id, a.work_order_id, w.status as order_status
      from public.work_order_assignments a
      join public.work_orders w on w.id = a.work_order_id
     where a.staff_assignment_id = p_staff_id
       and a.status in ('offered', 'accepted')
       and w.status not in ('completed', 'cancelled', 'failed')
  loop
    update public.work_order_assignments
       set status       = 'withdrawn',
           responded_at = now(),
           ended_at     = now(),
           decline_reason = nullif(btrim(coalesce(p_reason, '')), '')
     where id = v_row.assignment_id;

    if v_row.order_status = 'offered' then
      -- Status unchanged, so `sync_dispatch_tasks` will not fire. Re-arm by
      -- hand, or the question stops being asked.
      perform public.enqueue_dispatch_task(v_row.work_order_id, 'ping', now());
    else
      -- Back to `offered`, which the trigger turns into a ping -- or into an
      -- auto-assign when the complaint was urgent. The engine already knows
      -- what to do with an unheld job; this is how it is told there is one.
      update public.work_orders
         set status = 'offered', updated_at = now()
       where id = v_row.work_order_id;
    end if;

    v_released := v_released + 1;
  end loop;

  for v_row in
    select s.id
      from public.security_shifts s
     where s.staff_assignment_id = p_staff_id
       and s.status in ('scheduled', 'active')
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

comment on function public.release_staff_commitments(uuid, text) is
  'Empty somebody''s book without finding successors: jobs go back to the engine, shifts are cancelled. What a bar does instead of a handover.';

revoke all on function public.release_staff_commitments(uuid, text)
  from public, anon, authenticated;
grant execute on function public.release_staff_commitments(uuid, text) to service_role;

create or replace function public.blacklist_service_provider(
  p_department_id       uuid,
  p_service_provider_id uuid,
  p_reason              text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_department public.departments%rowtype;
  v_actor      uuid;
  v_id         uuid;
  v_staff      uuid;
  v_released   integer := 0;
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  if coalesce(btrim(p_reason), '') = '' then
    raise exception 'A reason is required.' using errcode = '22004';
  end if;

  select * into v_department from public.departments where id = p_department_id;

  select id into v_actor
    from public.community_memberships
   where community_id = v_department.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null
   limit 1;

  -- Remove them first, wherever in this community they are on a roster. A bar
  -- that leaves the person still working here is not a bar.
  for v_staff in
    select sa.id
      from public.staff_assignments sa
     where sa.community_id = v_department.community_id
       and sa.service_provider_id = p_service_provider_id
       and sa.status = 'active'
  loop
    -- Release before removing, because `remove_department_member` now refuses
    -- to remove somebody holding work. The order is the decision: this is the
    -- one path where the work is taken away rather than handed over.
    v_released := v_released + public.release_staff_commitments(v_staff, btrim(p_reason));

    -- Any open departure is answered by the bar rather than left pending
    -- against a roster row that is about to go inactive.
    update public.staff_departures
       set status        = 'cancelled',
           decided_at    = coalesce(decided_at, now()),
           decision_note = 'Superseded by a bar.',
           updated_at    = now()
     where staff_assignment_id = v_staff
       and status = 'pending';

    perform public.remove_department_member(v_staff, btrim(p_reason));
  end loop;

  -- Any open negotiation is closed rather than left pending against someone who
  -- can no longer be hired.
  update public.service_applications
     set status                   = 'rejected',
         decided_by_membership_id = v_actor,
         decided_at               = now(),
         decision_note            = btrim(p_reason),
         updated_at               = now()
   where community_id = v_department.community_id
     and service_provider_id = p_service_provider_id
     and status = 'pending';

  insert into public.blacklisted_service_providers (
    community_id, service_provider_id, blacklisted_by_membership_id, reason
  )
  values (
    v_department.community_id, p_service_provider_id, v_actor, btrim(p_reason)
  )
  on conflict do nothing
  returning id into v_id;

  -- The department finds out that N jobs are back in the pool. Without this the
  -- release is invisible: the work orders quietly return to `offered` and the
  -- only trace is five workers' feeds lighting up with an offer nobody expected.
  if v_released > 0 then
    perform public.notify_department_leadership(
      p_department_id, 'departure.work_released',
      jsonb_build_object(
        'title', v_released || ' item(s) went back to the pool',
        'body', 'A barred service provider''s jobs and shifts were released.',
        'url', '/admin/departments/' || p_department_id::text || '/hiring?tab=roster',
        'departmentId', p_department_id,
        'releasedCount', v_released),
      v_actor);
  end if;

  return v_id;
end;
$$;

comment on function public.blacklist_service_provider(uuid, uuid, text) is
  'Remove and bar, community-wide. Releases their work to the engine rather than waiting for a handover -- a bar that leaves tomorrow''s job booked is not a bar.';

-- ---------------------------------------------------------------------------
-- 11. The sweep learns about departures
--
-- `dispatch_candidates` recreated whole, for one `not exists`. A SQL-language
-- function has no smaller edit, and the alternative -- leaving the sweep
-- ignorant and letting section 8's trigger refuse the write -- would turn every
-- auto-assign of a departing worker into a failed dispatch task with a retry,
-- rather than an assignment to somebody who can actually go.
--
-- Everything else below is `0037` section 4 verbatim, including its header's
-- two arguments about adjacency and about roster rows nobody recorded skills
-- for.
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
   -- 0043 section 8. Somebody on their way out is not offered the work their
   -- own handover is trying to move; without this the handover is a treadmill.
   and not public.has_pending_departure(sa.id)
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
  'Who could take this job, best first: already in this community today, then least loaded, then nearest. Excludes anyone with an open departure. Reads only.';

-- ---------------------------------------------------------------------------
-- 12. Row security
--
-- Read policy only, like every table this feature has added. Every write above
-- is a definer function that checked its own authorisation.
-- ---------------------------------------------------------------------------

alter table public.staff_departures enable row level security;

drop policy if exists staff_departures_read on public.staff_departures;
create policy staff_departures_read on public.staff_departures
  for select to authenticated
  using (
    public.is_community_admin(community_id)
    or public.can_supervise_department(department_id)
    -- The person leaving reads their own, which is what lets the worker portal
    -- show a pending request without a second endpoint for it.
    or public.is_own_staff_assignment(staff_assignment_id)
  );

grant select on public.staff_departures to authenticated;

-- ---------------------------------------------------------------------------
-- 13. Grants
--
-- Every RPC here authorises its own caller and is reached through PostgREST, so
-- `authenticated` executes them; the two that take a roster row and return
-- other people's rows do not.
-- ---------------------------------------------------------------------------

revoke all on function public.request_staff_departure(uuid, text)
  from public, anon;
grant execute on function public.request_staff_departure(uuid, text) to authenticated;

revoke all on function public.cancel_staff_departure(uuid) from public, anon;
grant execute on function public.cancel_staff_departure(uuid) to authenticated;

revoke all on function public.decide_staff_departure(uuid, text, text)
  from public, anon;
grant execute on function public.decide_staff_departure(uuid, text, text)
  to authenticated;

revoke all on function public.reassign_departure_item(uuid, text, uuid, uuid)
  from public, anon;
grant execute on function public.reassign_departure_item(uuid, text, uuid, uuid)
  to authenticated;
