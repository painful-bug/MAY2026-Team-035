-- ---------------------------------------------------------------------------
-- Seven work-order notifications get a screen to land on
--
-- `0037` and `0039` emit seven notifications addressed to whoever supervises a
-- job -- nobody was free, nobody could be assigned, a failed visit was not
-- rebooked, an offer was accepted, a job was completed, a visit failed -- and
-- every one of them links to `/admin/departments?job=<id>`. That path resolves
-- (it is the admin's department list) and the `job` parameter has never been
-- read by anything, so the supervisor arrives at a list of departments and has
-- to find the job themselves. `docs/potential issues/12` item 4 recorded it and
-- deferred it for the only honest reason available at the time: **there was no
-- triage screen anywhere in any portal**, so there was no correct URL to write.
--
-- There is now. `departments/:departmentId/work-orders` is mounted under
-- `/admin`, `/manager` and `/security-manager` (`App.jsx`'s `WORK_ORDER_ROUTES`),
-- and the screen reads `?job=`, `?tab=`, `?status=` and `?complaint=`. The
-- deferral's condition is met, so the seven urls are repointed here.
--
-- ## The inventory this file was written from
--
--   `0037_dispatch_engine.sql:688`  dispatch_ping_candidates       no_candidates
--   `0037_dispatch_engine.sql:741`  dispatch_auto_assign           no_candidates
--   `0037_dispatch_engine.sql:951`  dispatch_failed_visit_escalation  escalated (manager)
--   `0037_dispatch_engine.sql:968`  dispatch_failed_visit_escalation  escalated (admin fallback)
--   `0039_worker_actions.sql:410`   accept_work_order_offer        accepted
--   `0039_worker_actions.sql:637`   complete_work_order            completed
--   `0039_worker_actions.sql:726`   report_work_order_failure      failed
--
-- Seven urls in six functions. No later migration redefines any of the six, so
-- these are the definitions installed today and this file is the eighth
-- statement in the chain rather than a fork of it.
--
-- ## Why the url is the `/admin/…` shape when most readers are not admins
--
-- Because that is the one mechanism there is, and it already works. A
-- notification url is written in SQL, and SQL does not know who will read it;
-- `portalNotificationUrl` (`frontend/src/features/notifications/portalUrl.js`)
-- rewrites `/admin/…` per reader at the point of the click, using the `portal`
-- the session already carries. Emitting a per-reader url from here would mean
-- the notification sender re-deriving `_portal_for`, which is a second
-- implementation of the rule that decides where people live.
--
-- **This required one change on the frontend side, and it is a change to that
-- same mechanism rather than a second one.** `portalUrl.js` recognises a
-- department sub-screen by an explicit list -- `hiring|staff/|candidates/` --
-- and `work-orders` was not in it, so this url would have reached a manager
-- unrewritten and `ProtectedRoute requiredRole="Admin"` would have redirected
-- them home: a click that appears to do nothing, which is the exact failure
-- `docs/potential issues/14` is about. The list gained `work-orders`, and
-- `backend/tests/test_notification_links.py` asserts the route tree has a
-- destination for the rewrite under every portal.
--
-- ## Why the department id is in the path
--
-- The screen is per-department: `can_supervise_department` is what every
-- work-order RPC checks, and the route carries `:departmentId` under all three
-- bases so the component needs no per-portal branch. `work_orders.department_id`
-- is nullable at the column level, but `create_work_order` -- the only write
-- path -- refuses a complaint with no department (`HB409`), so every row these
-- six functions can act on has one. A row that somehow did not would produce an
-- empty path segment; that is not worse than the list-of-departments this file
-- replaces, and guarding it in seven places would cost more than it buys.
--
-- ## Why the whole bodies
--
-- `0037` and `0039` are applied (`backend/supabase/migrations/README.md`). The
-- six bodies below were extracted mechanically from those two files, so the
-- starting point is provably the applied text, and every difference from it is
-- marked `-- CHANGED` in place -- seven lines, all of them the `'url'` key.
--
-- Nothing else is re-declared. `create or replace function` keeps a function's
-- oid, so its `comment on` and its ACL survive untouched, and re-issuing them
-- would mean restating two different postures from memory: `0037`'s three are
-- service_role only (`revoke all … from public, anon, authenticated`) and
-- `0039`'s three are `grant execute … to authenticated`. Getting one of those
-- backwards is a security change disguised as a copy, and the way to not make
-- it is to not write it.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- 1. 0037 -- the dispatch engine's three
-- ---------------------------------------------------------------------------

create or replace function public.dispatch_ping_candidates(p_work_order_id uuid)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order     public.work_orders%rowtype;
  v_complaint public.complaints%rowtype;
  v_row       record;
  v_sent      integer := 0;
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    return 0;
  end if;

  -- The idempotency check. A second delivery of this task after somebody has
  -- already accepted must not re-offer a job that is taken.
  if v_order.status <> 'offered' or v_order.scheduled_start_at is null then
    return 0;
  end if;

  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  for v_row in
    select * from public.dispatch_candidates(p_work_order_id, 5)
  loop
    -- Not re-offering to somebody still holding an open offer. There is no
    -- unique constraint to lean on here and there should not be: a worker who
    -- declined last week may legitimately be asked again.
    if not exists (
      select 1 from public.work_order_assignments a
       where a.work_order_id = v_order.id
         and a.staff_assignment_id = v_row.staff_assignment_id
         and a.status = 'offered'
    ) then
      insert into public.work_order_assignments (
        work_order_id, staff_assignment_id, status, offered_at,
        is_auto_assigned, scheduled_start_at, scheduled_end_at
      )
      values (
        v_order.id, v_row.staff_assignment_id, 'offered', now(),
        true, v_order.scheduled_start_at, v_order.scheduled_end_at
      );

      perform public.notify_member(
        v_row.membership_id, 'work_order.offered',
        jsonb_build_object(
          'title', 'A job is available',
          'body', coalesce(v_complaint.title, 'Scheduled work'),
          'url', '/worker?job=' || v_order.id::text,
          'work_order_id', v_order.id,
          'complaint_id', v_order.complaint_id,
          'starts_at', v_order.scheduled_start_at,
          'ends_at', v_order.scheduled_end_at));

      v_sent := v_sent + 1;
    end if;
  end loop;

  if v_sent = 0 then
    -- Nobody free, which is an ordinary Tuesday in a department of two and must
    -- not look like a fault. The supervisor is told once and the job stays
    -- `offered` for a human to place by hand. Nothing is re-queued: a retry
    -- loop against an empty roster is a busy loop that never learns anything.
    if v_order.supervisor_membership_id is not null then
      perform public.notify_member(
        v_order.supervisor_membership_id, 'work_order.no_candidates',
        jsonb_build_object(
          'title', 'Nobody is free for that visit',
          'body', coalesce(v_complaint.title, 'Scheduled work'),
          -- CHANGED: the triage screen, filtered to this job.
          'url', '/admin/departments/' || v_order.department_id::text
                 || '/work-orders?job=' || v_order.id::text,
          'work_order_id', v_order.id,
          'complaint_id', v_order.complaint_id,
          'starts_at', v_order.scheduled_start_at));
    end if;
    return 0;
  end if;

  -- Ask, wait, decide. If one of them accepts first, the job moves to
  -- `scheduled` and the trigger in section 2 retires this task before it fires
  -- -- which is why there is no second mechanism for "somebody already took it".
  perform public.enqueue_dispatch_task(
    v_order.id, 'auto_assign', now() + interval '30 minutes');

  return v_sent;
end;
$$;

create or replace function public.dispatch_auto_assign(p_work_order_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order      public.work_orders%rowtype;
  v_complaint  public.complaints%rowtype;
  v_pick       record;
  v_assignment uuid;
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    return null;
  end if;

  if v_order.status <> 'offered' or v_order.scheduled_start_at is null then
    return null;
  end if;

  select * into v_pick from public.dispatch_candidates(p_work_order_id, 1);
  if not found then
    -- Same posture as the ping: tell the supervisor, leave the job where a human
    -- can see it, and do not requeue.
    if v_order.supervisor_membership_id is not null then
      perform public.notify_member(
        v_order.supervisor_membership_id, 'work_order.no_candidates',
        jsonb_build_object(
          'title', 'Nobody could be assigned',
          -- CHANGED: the triage screen, filtered to this job.
          'url', '/admin/departments/' || v_order.department_id::text
                 || '/work-orders?job=' || v_order.id::text,
          'work_order_id', v_order.id,
          'complaint_id', v_order.complaint_id,
          'starts_at', v_order.scheduled_start_at));
    end if;
    return null;
  end if;

  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  -- Withdrawn, not deleted: "we asked five people and gave it to Anil" is the
  -- history a supervisor asks about, and section 5 of `0036` made the same call.
  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now()
   where work_order_id = v_order.id
     and status = 'offered';

  -- `work_order_assignments_no_overlap` can still refuse this if somebody was
  -- booked between the sweep and here. That surfaces as a failed task with the
  -- reason in `last_error` and a retry on the next tick, which is the correct
  -- outcome -- the constraint is the guarantee and the sweep is only the guess.
  insert into public.work_order_assignments (
    work_order_id, staff_assignment_id, status, offered_at, responded_at,
    is_auto_assigned, scheduled_start_at, scheduled_end_at
  )
  values (
    v_order.id, v_pick.staff_assignment_id, 'accepted', now(), now(),
    true, v_order.scheduled_start_at, v_order.scheduled_end_at
  )
  returning id into v_assignment;

  update public.work_orders
     set status = 'scheduled', updated_at = now()
   where id = v_order.id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_order.supervisor_membership_id, 'job_assigned',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assigneeName', v_pick.display_name,
      'startsAt', v_order.scheduled_start_at,
      'endsAt', v_order.scheduled_end_at,
      'automatic', true)
  );

  perform public.notify_member(
    v_pick.membership_id, 'work_order.assigned',
    jsonb_build_object(
      'title', 'You have been assigned a job',
      'body', coalesce(v_complaint.title, 'Scheduled work'),
      'url', '/worker?job=' || v_order.id::text,
      'work_order_id', v_order.id,
      'starts_at', v_order.scheduled_start_at,
      'ends_at', v_order.scheduled_end_at));

  -- The resident finds out who is coming, which is the whole point of the
  -- feature from their side and the answer to the phone call it exists to
  -- prevent.
  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.assigned',
      jsonb_build_object(
        'title', 'Someone is coming for your complaint',
        'body', v_pick.display_name,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_order.scheduled_start_at));
  end if;

  return v_assignment;
end;
$$;

create or replace function public.dispatch_failed_visit_escalation(
  p_work_order_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order     public.work_orders%rowtype;
  v_complaint public.complaints%rowtype;
  v_manager   uuid;
  v_sent      integer := 0;
begin
  select * into v_order from public.work_orders where id = p_work_order_id;
  if not found then
    return false;
  end if;

  -- Not a status check, and the header says why: the failed job stays failed
  -- for good, because the answer to a failed visit is a NEW work order (D5) and
  -- not an edit to this one. So the question this asks is "has a human already
  -- done something about it", and the evidence for that is a newer job on the
  -- same complaint.
  if v_order.complaint_id is not null and exists (
    select 1
      from public.work_orders newer
     where newer.complaint_id = v_order.complaint_id
       and newer.id <> v_order.id
       and newer.created_at > v_order.created_at
  ) then
    return false;
  end if;

  -- Or the complaint itself was settled some other way -- resolved on the phone,
  -- closed as a duplicate. Escalating a visit for a complaint nobody has any
  -- longer is the false alarm that teaches people to ignore the real ones.
  select * into v_complaint from public.complaints where id = v_order.complaint_id;
  if v_complaint.status::text in ('resolved', 'closed') then
    return false;
  end if;

  -- The department's manager first, because the escalation is theirs: a
  -- supervisor who has not rescheduled in two hours is the person being escalated
  -- past, so notifying them again would be telling somebody what they already
  -- decided not to do.
  select m.id into v_manager
    from public.staff_assignments sa
    join public.community_memberships m on m.id = sa.membership_id
   where sa.department_id = v_order.department_id
     and sa.rank = 'manager'
     and sa.status = 'active'
     and m.status = 'active'
     and m.ended_at is null
   limit 1;

  if v_manager is not null then
    perform public.notify_member(
      v_manager, 'work_order.escalated',
      jsonb_build_object(
        'title', 'A visit failed and has not been rebooked',
        'body', coalesce(v_complaint.title, 'Scheduled work'),
        -- CHANGED: the triage screen, filtered to this job. This is the reader
        -- the repoint is most for -- a department manager, whose portal mounts
        -- the same route and who `portalUrl.js` now rewrites for.
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'attempts', v_order.failed_attempt_count));
    v_sent := 1;
  end if;

  -- A department with no manager on its roster is not a rare misconfiguration;
  -- it is every department created through the departments form before anybody
  -- was hired. The community's admins are the fallback, and there is always at
  -- least one of those.
  if v_sent = 0 then
    perform public.notify_community_roles(
      v_order.community_id, array['admin'], 'work_order.escalated',
      jsonb_build_object(
        'title', 'A visit failed and has not been rebooked',
        'body', coalesce(v_complaint.title, 'Scheduled work'),
        -- CHANGED: the triage screen, filtered to this job.
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'attempts', v_order.failed_attempt_count));
  end if;

  return true;
end;
$$;

-- ---------------------------------------------------------------------------
-- 2. 0039 -- the worker's three answers to their supervisor
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
        -- CHANGED: the triage screen, filtered to this job.
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_order.scheduled_start_at));
  end if;

  return v_assign.id;
end;
$$;

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
        -- CHANGED: the triage screen, filtered to this job.
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id));
  end if;
end;
$$;

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
        -- CHANGED: the triage screen, filtered to this job.
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
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
