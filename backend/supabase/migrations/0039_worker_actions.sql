-- ===========================================================================
-- 0039_worker_actions.sql — the worker's own side of a job
--
-- `0036` built the supervisor's half of the work-order state machine and `0037`
-- built the timers. Both stop at `scheduled`. Everything past it —
-- `in_progress`, `completed`, `failed` — has been declared in
-- `work_orders_status_check` since Step 4 and unreachable ever since, because
-- the only person who can say *I have started*, *I am done* or *I could not get
-- in* is the person standing at the door, and until Step 2 that person had no
-- account.
--
-- This file is that person's API surface. Five verbs on a job, three on their
-- own working week, and three views that answer "mine" without being asked who
-- is asking.
--
--
-- NOT ONE OF THESE FUNCTIONS TAKES AN IDENTITY
--
-- No worker id, no roster id, no provider id, no community id. Every one of them
-- resolves the caller through `is_own_staff_assignment` (`0036` §4) or through
-- `service_providers.profile_id = auth.uid()`, and the three views apply the
-- same two predicates in their WHERE clause.
--
-- That is what lets the routers above be authenticated-only, which is not
-- laziness and is worth stating once here. The obvious guard —
-- `require_membership_role('worker', 'security')` — reads the role off the
-- caller's **default** membership, and this is the one surface in the product
-- that is deliberately cross-community: a plumber hired by three societies and
-- living in a fourth has a default membership of `resident`, and that guard would
-- refuse them their own job list. The question actually being asked is *does this
-- caller hold this assignment*, which is not a question about roles at all, and
-- it already has exactly one implementation.
--
--
-- ACCEPT IS THE RACE, AND THE LOCK IS THE ANSWER
--
-- `dispatch_ping_candidates` offers one job to five people on purpose. So the
-- ordinary case is two of them tapping *accept* within the same second, and the
-- rule "one accepted assignment per job" has to hold across that.
--
-- `accept_work_order_offer` takes `for update` on the **work order** before it
-- reads anything. The second caller waits, re-reads a row that now says
-- `scheduled`, and is told *somebody has already taken this job* — a sentence a
-- person can act on. `work_order_assignments_no_overlap` is still underneath and
-- still the guarantee; it is just not the thing anybody should have to read.
--
-- The same lock is why the offer→booking transition needs no compare-and-set
-- dance: inside it, "is this job still open" is a plain SELECT.
--
--
-- WHAT THIS FILE DELIBERATELY DOES NOT DO
--
-- * **Completing a job does not resolve the complaint.** The two look like one
--   act and are not: a resident whose tap still drips after the visit has a
--   complaint that is emphatically not resolved, and `0031` already gives them
--   `resolution_confirmed`. A worker's word is evidence, not a verdict.
-- * **Declining writes no `complaint_events` row.** The resident does not need
--   to learn that five people were asked and one said no; the assignment history
--   records it for the supervisor, which is who it is about. It is also what
--   keeps `job_declined` meaning the one thing it already means in
--   `_EVENT_LABELS` — *the resident declined the proposed time*.
-- * **Nothing here enqueues a dispatch task.** `0037`'s trigger is the single
--   writer of that table and stays so; every status this file writes reaches it
--   through `work_orders.status`, including `failed`, whose escalation the
--   trigger arms without this file naming the queue.
--
-- Depends on: 0036 (work orders, assignments, availability columns,
-- `is_own_staff_assignment`), 0035 (roster ranks, `service_provider_id`), 0034
-- (service providers), 0031/0030 (`notify_member`), 0019 (departments).
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. What "mine" means
--
-- Three `security_invoker` views, each filtered to the caller inside SQL. The
-- RLS policies underneath are deliberately wider than this -- a supervisor may
-- read their staff's leave, `0036` §7 -- so a view that only leaned on the policy
-- would show a supervisor their whole department on a screen headed "my week".
-- ---------------------------------------------------------------------------

drop view if exists public.my_worker_job;
create view public.my_worker_job
with (security_invoker = true) as
select
  a.id                     as assignment_id,
  a.work_order_id,
  a.staff_assignment_id,
  a.status                 as assignment_status,
  a.offered_at,
  a.responded_at,
  a.decline_reason,
  a.is_auto_assigned,
  -- The assignment's slot, falling back to the job's. They agree in every path
  -- that writes both; the coalesce is for the offer written before a supervisor
  -- moved the visit, where the job is the newer of the two.
  coalesce(a.scheduled_start_at, w.scheduled_start_at) as scheduled_start_at,
  coalesce(a.scheduled_end_at, w.scheduled_end_at)     as scheduled_end_at,
  w.status                 as work_order_status,
  w.priority,
  w.subject_kind,
  w.location_text,
  w.failed_attempt_count,
  w.cancelled_reason,
  w.community_id,
  cm.name                  as community_name,
  w.department_id,
  d.name                   as department_name,
  d.kind                   as department_kind,
  w.complaint_id,
  c.title                  as complaint_title,
  c.description            as complaint_description,
  c.category               as complaint_category,
  sk.name                  as skill_name,
  -- Who to look for when you get there. A technician sent to a flat with no
  -- name and no number is a technician standing outside a locked door, and this
  -- view is already narrowed to jobs this caller holds -- they were sent to this
  -- address by the association, which is the authorization for knowing whose it
  -- is. Null on a `facility` job, where there is no door and nobody to meet.
  res.full_name            as resident_name,
  res.phone_e164           as resident_phone_e164,
  res.unit_code            as resident_unit_code
from public.work_order_assignments a
join public.work_orders w        on w.id = a.work_order_id
left join public.communities cm  on cm.id = w.community_id
left join public.departments d   on d.id = w.department_id
left join public.complaints c    on c.id = w.complaint_id
left join public.skills sk       on sk.id = w.skill_id
left join lateral (
  select p.full_name, p.phone_e164, u.unit_code
    from public.community_memberships m
    join public.profiles p on p.id = m.profile_id
    left join lateral (
      select un.unit_code
        from public.unit_residencies ur
        join public.units un on un.id = ur.unit_id
       where ur.membership_id = m.id
         and ur.ended_at is null
       order by ur.is_primary_contact desc, ur.started_at
       limit 1
    ) u on true
   where m.id = c.raised_by_membership_id
     and w.subject_kind = 'resident'
) res on true
where public.is_own_staff_assignment(a.staff_assignment_id);

comment on view public.my_worker_job is
  'Every offer and booking the calling worker holds, with the job, the complaint '
  'behind it and who to meet. Filtered to the caller in the view rather than by '
  'the policy, which is wider on purpose.';

grant select on public.my_worker_job to authenticated;

drop view if exists public.my_worker_unavailability;
create view public.my_worker_unavailability
with (security_invoker = true) as
select
  u.id,
  u.starts_at,
  u.ends_at,
  u.reason,
  u.created_at,
  u.service_provider_id,
  u.staff_assignment_id,
  -- Which of the two subjects this block belongs to, so a client can say
  -- "everywhere" or name the department without inferring it from two nullable
  -- columns.
  case when u.service_provider_id is not null then 'provider' else 'roster' end
    as scope,
  d.name as department_name
from public.worker_unavailability u
left join public.staff_assignments sa on sa.id = u.staff_assignment_id
left join public.departments d        on d.id = sa.department_id
where (
  u.service_provider_id is not null
  and exists (select 1 from public.service_providers p
               where p.id = u.service_provider_id and p.profile_id = auth.uid())
) or (
  u.staff_assignment_id is not null
  and public.is_own_staff_assignment(u.staff_assignment_id)
);

comment on view public.my_worker_unavailability is
  'The calling worker''s own leave, both the global kind keyed to their provider '
  'record and the per-department kind keyed to a roster row.';

grant select on public.my_worker_unavailability to authenticated;

drop view if exists public.my_worker_availability_rule;
create view public.my_worker_availability_rule
with (security_invoker = true) as
select
  r.id,
  r.weekday,
  r.start_time,
  r.end_time,
  r.effective_from,
  r.effective_to,
  r.service_provider_id,
  r.staff_assignment_id,
  case when r.service_provider_id is not null then 'provider' else 'roster' end
    as scope,
  d.name as department_name
from public.worker_availability_rules r
left join public.staff_assignments sa on sa.id = r.staff_assignment_id
left join public.departments d        on d.id = sa.department_id
where (
  r.service_provider_id is not null
  and exists (select 1 from public.service_providers p
               where p.id = r.service_provider_id and p.profile_id = auth.uid())
) or (
  r.staff_assignment_id is not null
  and public.is_own_staff_assignment(r.staff_assignment_id)
);

comment on view public.my_worker_availability_rule is
  'The calling worker''s declared working week. No rows means always available, '
  'which is what dispatch_candidates reads it as.';

grant select on public.my_worker_availability_rule to authenticated;

-- ---------------------------------------------------------------------------
-- 2. Two things every verb below needs
--
-- Kept as functions rather than repeated inline, because the second copy of an
-- authorization predicate is the one that drifts.
-- ---------------------------------------------------------------------------

-- The caller's own provider record, or null. Not an error on its own: the
-- functions that need one raise their own message, which is more useful than
-- "no rows".
create or replace function public.my_service_provider_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select id from public.service_providers where profile_id = auth.uid() limit 1;
$$;

comment on function public.my_service_provider_id() is
  'The calling profile''s service-provider id, or null when they never '
  'registered.';

-- The membership the caller holds in one community, for the `actor` on a
-- `complaint_events` row. A worker hired in three societies has three, and the
-- one that belongs on the timeline is the one in the community the job is in --
-- which is the entire reason this takes an argument.
create or replace function public.my_membership_in(p_community_id uuid)
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select id
    from public.community_memberships
   where community_id = p_community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null
   limit 1;
$$;

comment on function public.my_membership_in(uuid) is
  'The caller''s active membership in one community, for attributing an event to '
  'the right one of several.';

-- ---------------------------------------------------------------------------
-- 3. The five verbs
--
-- Each begins by locking the work order and finding the caller's own assignment
-- on it. A caller with no assignment gets a 404 rather than a 403, and that is
-- the deliberate choice `0031` made for the same reason: a work-order id the
-- caller has nothing to do with should not be confirmed as existing.
-- ---------------------------------------------------------------------------

create or replace function public.accept_work_order_offer(p_work_order_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order      public.work_orders%rowtype;
  v_assign     public.work_order_assignments%rowtype;
  v_staff      public.staff_assignments%rowtype;
  v_complaint  public.complaints%rowtype;
  v_actor      uuid;
begin
  -- The whole race is settled on this line. See the header.
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  select * into v_assign
    from public.work_order_assignments a
   where a.work_order_id = p_work_order_id
     and public.is_own_staff_assignment(a.staff_assignment_id)
   order by a.offered_at desc
   limit 1;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  -- Idempotent on the caller's own second tap: they already hold it, so this is
  -- the answer they were asking for rather than a conflict to explain.
  if v_assign.status = 'accepted' then
    return v_assign.id;
  end if;

  if v_assign.status <> 'offered' then
    raise exception 'That offer is no longer open.' using errcode = 'HB409';
  end if;

  if v_order.status <> 'offered' then
    raise exception 'Somebody has already taken this job.' using errcode = 'HB409';
  end if;

  if v_order.scheduled_start_at is null or v_order.scheduled_end_at is null then
    raise exception 'This job has no scheduled time yet.' using errcode = 'HB409';
  end if;

  select * into v_staff
    from public.staff_assignments where id = v_assign.staff_assignment_id;

  -- The sweep checked this when it made the offer; between then and now the
  -- caller may have been booked elsewhere by a supervisor. Named here so the
  -- worker is told which of their own jobs is in the way, rather than reading a
  -- 23P01 about an exclusion constraint.
  if exists (
    select 1
      from public.work_order_assignments busy
     where busy.staff_assignment_id = v_assign.staff_assignment_id
       and busy.status = 'accepted'
       and busy.work_order_id <> v_order.id
       and busy.scheduled_start_at is not null
       and tstzrange(busy.scheduled_start_at, busy.scheduled_end_at, '[)')
           && tstzrange(v_order.scheduled_start_at, v_order.scheduled_end_at, '[)')
  ) then
    raise exception 'You are already booked during that time.'
      using errcode = 'HB409';
  end if;

  -- Everybody else's offer is withdrawn, not deleted -- `0036` §6 and `0037` §5
  -- both made this call, and the history of who was asked is the answer to the
  -- question a supervisor asks when a job goes wrong.
  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = v_order.id
     and id <> v_assign.id
     and status in ('offered', 'accepted');

  update public.work_order_assignments
     set status             = 'accepted',
         responded_at       = now(),
         scheduled_start_at = coalesce(scheduled_start_at, v_order.scheduled_start_at),
         scheduled_end_at   = coalesce(scheduled_end_at, v_order.scheduled_end_at)
   where id = v_assign.id;

  -- Which retires the pending `auto_assign` through `0037`'s trigger, and is the
  -- whole of why "somebody already took it" needs no second mechanism.
  update public.work_orders
     set status = 'scheduled', updated_at = now()
   where id = v_order.id;

  v_actor := public.my_membership_in(v_order.community_id);
  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  -- `job_assigned` rather than a new `job_accepted`: from the resident's side
  -- the fact is the same fact -- somebody is now coming, and their name is this.
  -- A second event type would render as a second sentence saying it again.
  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_actor, 'job_assigned',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assignmentId', v_assign.id,
      'assigneeName', v_staff.display_name,
      'startsAt', v_order.scheduled_start_at,
      'endsAt', v_order.scheduled_end_at,
      'accepted', true)
  );

  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.assigned',
      jsonb_build_object(
        'title', 'Someone is coming for your complaint',
        'body', v_staff.display_name,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_order.scheduled_start_at));
  end if;

  -- The supervisor asked a question and this is the answer to it. Skipped when
  -- the supervisor is the accepting worker, which a small department makes
  -- entirely possible.
  if v_order.supervisor_membership_id is not null
     and v_order.supervisor_membership_id is distinct from v_actor then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.accepted',
      jsonb_build_object(
        'title', 'A job was accepted',
        'body', v_staff.display_name,
        'url', '/admin/departments?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_order.scheduled_start_at));
  end if;

  return v_assign.id;
end;
$$;

comment on function public.accept_work_order_offer(uuid) is
  'Take an offered job. Withdraws every other offer on it and books the hour; '
  'the loser of the race is told somebody already took it.';

create or replace function public.decline_work_order_offer(
  p_work_order_id uuid,
  p_reason        text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_assign public.work_order_assignments%rowtype;
begin
  select * into v_assign
    from public.work_order_assignments a
   where a.work_order_id = p_work_order_id
     and public.is_own_staff_assignment(a.staff_assignment_id)
   order by a.offered_at desc
   limit 1;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  if v_assign.status = 'declined' then
    return v_assign.id;
  end if;

  -- A worker who accepted and then cannot go has not *declined* -- they have a
  -- booking a resident has been told about, and getting out of it is
  -- `report_work_order_failure` or a call to their supervisor. Declining an
  -- acceptance would silently unbook a visit nobody was told was cancelled.
  if v_assign.status <> 'offered' then
    raise exception 'That offer is no longer open.' using errcode = 'HB409';
  end if;

  update public.work_order_assignments
     set status         = 'declined',
         responded_at   = now(),
         ended_at       = now(),
         decline_reason = nullif(btrim(coalesce(p_reason, '')), '')
   where id = v_assign.id;

  -- Nothing else happens, and that is the design. The job stays `offered`, the
  -- `auto_assign` task `0037` armed at the same time as the ping is still due in
  -- thirty minutes, and the sweep now excludes this worker by name. Pulling that
  -- task forward would make this function the second writer of `dispatch_tasks`
  -- to save a supervisor half an hour of not knowing something they are not
  -- waiting on.
  --
  -- No `complaint_events` row either: see the header.
  return v_assign.id;
end;
$$;

comment on function public.decline_work_order_offer(uuid, text) is
  'Say no to an offer. Touches this worker''s row and nothing else -- the job '
  'stays open and the escalation already scheduled still runs.';

create or replace function public.start_work_order(p_work_order_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order     public.work_orders%rowtype;
  v_assign    public.work_order_assignments%rowtype;
  v_staff     public.staff_assignments%rowtype;
  v_complaint public.complaints%rowtype;
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  select * into v_assign
    from public.work_order_assignments a
   where a.work_order_id = p_work_order_id
     and a.status = 'accepted'
     and public.is_own_staff_assignment(a.staff_assignment_id)
   limit 1;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  if v_order.status = 'in_progress' then
    return;
  end if;

  if v_order.status <> 'scheduled' then
    raise exception 'This job cannot be started from here.' using errcode = 'HB409';
  end if;

  update public.work_orders
     set status = 'in_progress', updated_at = now()
   where id = v_order.id;

  select * into v_staff
    from public.staff_assignments where id = v_assign.staff_assignment_id;
  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_staff.membership_id, 'job_started',
    jsonb_build_object(
      'workOrderId', v_order.id, 'assigneeName', v_staff.display_name)
  );

  -- D9's amendment covers this: it is not a progress bar, it is somebody
  -- ringing the doorbell in the next few minutes.
  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.started',
      jsonb_build_object(
        'title', 'Work on your complaint has started',
        'body', v_staff.display_name,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id));
  end if;
end;
$$;

comment on function public.start_work_order(uuid) is
  'The worker is on site. Idempotent on a job already in progress.';

create or replace function public.complete_work_order(
  p_work_order_id uuid,
  p_notes         text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order     public.work_orders%rowtype;
  v_assign    public.work_order_assignments%rowtype;
  v_staff     public.staff_assignments%rowtype;
  v_complaint public.complaints%rowtype;
  v_notes     text := nullif(btrim(coalesce(p_notes, '')), '');
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  select * into v_assign
    from public.work_order_assignments a
   where a.work_order_id = p_work_order_id
     and a.status = 'accepted'
     and public.is_own_staff_assignment(a.staff_assignment_id)
   limit 1;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  if v_order.status = 'completed' then
    return;
  end if;

  -- `scheduled` is accepted as well as `in_progress`, and not out of leniency: a
  -- worker who fixed the tap and forgot to press *start* has done the work, and
  -- an API that refuses to record it teaches them the app is lying about what
  -- happened. The timeline still shows only what was actually reported.
  if v_order.status not in ('scheduled', 'in_progress') then
    raise exception 'This job cannot be completed from here.' using errcode = 'HB409';
  end if;

  update public.work_order_assignments
     set status = 'completed', ended_at = now()
   where id = v_assign.id;

  update public.work_orders
     set status = 'completed', updated_at = now()
   where id = v_order.id;

  select * into v_staff
    from public.staff_assignments where id = v_assign.staff_assignment_id;
  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_staff.membership_id, 'job_completed',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assigneeName', v_staff.display_name,
      'notes', v_notes)
  );

  -- **The complaint is not resolved by this.** See the header: the person who
  -- decides whether the problem is gone is the person who has the problem.
  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.completed',
      jsonb_build_object(
        'title', 'The visit for your complaint is finished',
        'body', coalesce(v_notes, v_staff.display_name),
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id));
  end if;

  if v_order.supervisor_membership_id is not null
     and v_order.supervisor_membership_id is distinct from v_staff.membership_id then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.completed',
      jsonb_build_object(
        'title', 'A job was completed',
        'body', v_staff.display_name,
        'url', '/admin/departments?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id));
  end if;
end;
$$;

comment on function public.complete_work_order(uuid, text) is
  'The work is done. Closes the assignment and the job -- and deliberately not '
  'the complaint, which is the resident''s to confirm.';

create or replace function public.report_work_order_failure(
  p_work_order_id uuid,
  p_reason        text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order     public.work_orders%rowtype;
  v_assign    public.work_order_assignments%rowtype;
  v_staff     public.staff_assignments%rowtype;
  v_complaint public.complaints%rowtype;
  v_reason    text := nullif(btrim(coalesce(p_reason, '')), '');
begin
  -- Required, unlike the completion note. "Could not be done" with no reason is
  -- the report that guarantees a second wasted visit: nobody downstream can tell
  -- *nobody was home* from *the part is out of stock*, and those need opposite
  -- responses.
  if v_reason is null then
    raise exception 'Say what went wrong.' using errcode = '22004';
  end if;

  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  select * into v_assign
    from public.work_order_assignments a
   where a.work_order_id = p_work_order_id
     and a.status = 'accepted'
     and public.is_own_staff_assignment(a.staff_assignment_id)
   limit 1;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  if v_order.status not in ('scheduled', 'in_progress') then
    raise exception 'This job cannot be reported from here.' using errcode = 'HB409';
  end if;

  update public.work_order_assignments
     set status = 'failed', ended_at = now(), decline_reason = v_reason
   where id = v_assign.id;

  -- Which arms `failed_visit_escalation` through `0037`'s trigger. Nothing here
  -- names the queue.
  update public.work_orders
     set status               = 'failed',
         failed_attempt_count = failed_attempt_count + 1,
         updated_at           = now()
   where id = v_order.id;

  select * into v_staff
    from public.staff_assignments where id = v_assign.staff_assignment_id;
  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_staff.membership_id, 'job_failed',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assigneeName', v_staff.display_name,
      'reason', v_reason,
      'attempt', v_order.failed_attempt_count + 1)
  );

  if v_order.supervisor_membership_id is not null
     and v_order.supervisor_membership_id is distinct from v_staff.membership_id then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.failed',
      jsonb_build_object(
        'title', 'A visit could not be completed',
        'body', v_reason,
        'url', '/admin/departments?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'attempts', v_order.failed_attempt_count + 1));
  end if;

  -- The resident waited in for this. Telling them it did not happen is the
  -- whole difference between a bad afternoon and the phone call this feature
  -- exists to prevent -- and the reason is theirs to read, because half the
  -- reasons a visit fails are things only they can fix.
  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.failed',
      jsonb_build_object(
        'title', 'The visit for your complaint could not be completed',
        'body', v_reason,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id));
  end if;
end;
$$;

comment on function public.report_work_order_failure(uuid, text) is
  'The visit did not happen. Counts the attempt, tells both sides, and lets '
  '0037''s trigger arm the two-hour escalation.';

-- ---------------------------------------------------------------------------
-- 4. The working week
--
-- Both write against the caller's **provider** record, which makes leave global
-- across every community that employs them -- the point `0036` §3 made when it
-- added `service_provider_id` beside `staff_assignment_id`. A plumber on holiday
-- is on holiday in all four societies, and asking them to say so four times is
-- how three of them end up booking him.
--
-- The per-roster half of those columns stays writable by nobody, deliberately:
-- it exists for a hand-typed roster name, who has no account to write with.
-- ---------------------------------------------------------------------------

create or replace function public.set_worker_unavailability(
  p_starts_at timestamptz,
  p_ends_at   timestamptz,
  p_reason    text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_provider uuid := public.my_service_provider_id();
  v_id       uuid;
begin
  if v_provider is null then
    raise exception 'Register as a service provider first.' using errcode = 'P0002';
  end if;
  if p_starts_at is null or p_ends_at is null then
    raise exception 'Both ends of the block are required.' using errcode = '22004';
  end if;
  if p_ends_at <= p_starts_at then
    raise exception 'A block must end after it starts.' using errcode = '22004';
  end if;

  -- No overlap check and no merging of touching blocks. Two overlapping "not
  -- available" rows are not a contradiction -- `dispatch_candidates` reads them
  -- with `not exists`, so two rows saying the same thing say the same thing --
  -- and a constraint here would refuse a perfectly sensible "away all week,
  -- especially Tuesday".
  insert into public.worker_unavailability
    (service_provider_id, starts_at, ends_at, reason)
  values
    (v_provider, p_starts_at, p_ends_at, nullif(btrim(coalesce(p_reason, '')), ''))
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.set_worker_unavailability(timestamptz, timestamptz, text) is
  'Mark a window unavailable, across every community that employs the caller.';

create or replace function public.delete_worker_unavailability(p_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_provider uuid := public.my_service_provider_id();
  v_deleted  integer;
begin
  if v_provider is null then
    raise exception 'Register as a service provider first.' using errcode = 'P0002';
  end if;

  delete from public.worker_unavailability
   where id = p_id and service_provider_id = v_provider;
  get diagnostics v_deleted = row_count;

  -- Somebody else's block and a block that never existed get the same answer,
  -- which is the same posture the verbs above take with a work-order id.
  if v_deleted = 0 then
    raise exception 'No such unavailable block.' using errcode = 'HB404';
  end if;
end;
$$;

comment on function public.delete_worker_unavailability(uuid) is
  'Remove one of the caller''s own unavailable blocks.';

create or replace function public.set_worker_availability_rules(p_rules jsonb)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_provider uuid := public.my_service_provider_id();
  v_count    integer;
begin
  if v_provider is null then
    raise exception 'Register as a service provider first.' using errcode = 'P0002';
  end if;
  if p_rules is null or jsonb_typeof(p_rules) <> 'array' then
    raise exception 'Send a list of rules.' using errcode = '22004';
  end if;

  -- Replaced whole, like `set_service_provider_skills`. The screen is a week
  -- with seven rows on it, and a delta API against a week two tabs are both
  -- editing is a lost update nobody notices until somebody is booked on their
  -- day off.
  delete from public.worker_availability_rules where service_provider_id = v_provider;

  insert into public.worker_availability_rules
    (service_provider_id, weekday, start_time, end_time, effective_from, effective_to)
  select
    v_provider,
    (rule->>'weekday')::smallint,
    (rule->>'startTime')::time,
    (rule->>'endTime')::time,
    coalesce((rule->>'effectiveFrom')::date, current_date),
    nullif(rule->>'effectiveTo', '')::date
  from jsonb_array_elements(p_rules) as rule;

  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

comment on function public.set_worker_availability_rules(jsonb) is
  'Replace the caller''s declared working week. An empty list means always '
  'available, which is what an absent rule set already meant.';

-- ---------------------------------------------------------------------------
-- 5. Permissions
--
-- No new table, so no new policy: everything above writes through
-- `work_orders`, `work_order_assignments`, `worker_unavailability` and
-- `worker_availability_rules`, all four of which `0036` §7 gave a read policy
-- and no write policy at all.
--
-- Every function is granted to `authenticated` and every one of them resolves
-- the caller itself -- which is the condition `0037` §7 stated for the
-- distinction: a function that asks who is calling may be called by anyone, and
-- a function that takes the answer as an argument may not.
-- ---------------------------------------------------------------------------

grant execute on function public.my_service_provider_id() to authenticated;
grant execute on function public.my_membership_in(uuid) to authenticated;
grant execute on function public.accept_work_order_offer(uuid) to authenticated;
grant execute on function public.decline_work_order_offer(uuid, text) to authenticated;
grant execute on function public.start_work_order(uuid) to authenticated;
grant execute on function public.complete_work_order(uuid, text) to authenticated;
grant execute on function public.report_work_order_failure(uuid, text) to authenticated;
grant execute on function public.set_worker_unavailability(
  timestamptz, timestamptz, text) to authenticated;
grant execute on function public.delete_worker_unavailability(uuid) to authenticated;
grant execute on function public.set_worker_availability_rules(jsonb) to authenticated;
