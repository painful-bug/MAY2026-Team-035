-- Complaint Engine v2: worker offers, consent, and critical fallback.

alter table public.work_order_assignments
  add column if not exists is_forced boolean not null default false;
alter table public.work_orders add column if not exists cancelled_by text;
do $$ begin
  if not exists (select 1 from pg_constraint where conrelid = 'public.work_orders'::regclass and conname = 'work_orders_cancelled_by_check') then
    alter table public.work_orders add constraint work_orders_cancelled_by_check
      check (cancelled_by is null or cancelled_by in ('resident', 'staff', 'system'));
  end if;
end $$;

create or replace function public.complaint_excluded_staff(p_complaint_id uuid)
returns table (staff_assignment_id uuid)
language sql stable security definer set search_path = public
as $$
  select a.staff_assignment_id from public.work_order_assignments a
  join public.work_orders w on w.id = a.work_order_id
  where w.complaint_id = p_complaint_id and a.status = 'declined'
  union
  select a.staff_assignment_id from public.work_order_assignments a
  join public.work_orders w on w.id = a.work_order_id
  where w.complaint_id = p_complaint_id and w.status = 'cancelled'
    and w.cancelled_by = 'resident' and a.status in ('accepted', 'withdrawn')
  union
  select a.staff_assignment_id from public.complaints c
  join public.work_orders w on w.complaint_id = c.id
  join public.work_order_assignments a on a.work_order_id = w.id
  where c.id = p_complaint_id and c.reopened_count > 0
    and a.status in ('accepted', 'completed') and w.status = 'completed';
$$;

create or replace function public.work_order_candidates(
  p_work_order_id uuid, p_include_excluded boolean default false
) returns table (
  staff_assignment_id uuid, membership_id uuid, service_provider_id uuid,
  display_name text, has_adjacent_job boolean, open_jobs integer,
  distance_km numeric, away_until timestamptz, excluded boolean
)
language plpgsql security definer set search_path = public
as $$
declare v_order public.work_orders%rowtype;
begin
  select * into v_order from public.work_orders where id = p_work_order_id;
  if not found then raise exception 'No such work order.' using errcode = 'HB404'; end if;
  -- The dispatcher runs without request claims; interactive callers must supervise.
  if not (public.can_supervise_department(v_order.department_id)
          or current_setting('request.jwt.claims', true) is null) then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;
  return query
  with base as (select * from public.dispatch_candidates(p_work_order_id, 100)),
       excluded_staff as (select e.staff_assignment_id from public.complaint_excluded_staff(v_order.complaint_id) e)
  select b.staff_assignment_id, b.membership_id, b.service_provider_id, b.display_name,
         b.has_adjacent_job, b.open_jobs, b.distance_km,
         (select max(u.ends_at) from public.worker_unavailability u
           where (u.staff_assignment_id = b.staff_assignment_id or u.service_provider_id = b.service_provider_id)
             and u.ends_at > now()),
         exists (select 1 from excluded_staff e where e.staff_assignment_id = b.staff_assignment_id)
    from base b
   where p_include_excluded or not exists (select 1 from excluded_staff e where e.staff_assignment_id = b.staff_assignment_id);
end;
$$;

-- CHANGED: manual assignment creates an offer; it never silently books a worker.
create or replace function public.assign_work_order(
  p_work_order_id uuid, p_staff_assignment_id uuid,
  p_scheduled_start_at timestamptz default null, p_scheduled_end_at timestamptz default null
) returns uuid
language plpgsql security definer set search_path = public
as $$
declare v_order public.work_orders%rowtype; v_staff public.staff_assignments%rowtype;
  v_complaint public.complaints%rowtype; v_id uuid; v_start timestamptz; v_end timestamptz;
begin
  select * into v_order from public.work_orders where id = p_work_order_id for update;
  if not found then raise exception 'No such work order.' using errcode = 'HB404'; end if;
  if not public.can_supervise_department(v_order.department_id) then raise exception 'You do not supervise this department.' using errcode = 'HB403'; end if;
  if v_order.status in ('completed', 'cancelled', 'failed') then raise exception 'This job is no longer open.' using errcode = 'HB409'; end if;
  select * into v_staff from public.staff_assignments where id = p_staff_assignment_id and department_id = v_order.department_id and status = 'active' and is_active;
  if not found then raise exception 'That person is not on this department roster.' using errcode = 'HB404'; end if;
  v_start := coalesce(p_scheduled_start_at, v_order.scheduled_start_at); v_end := coalesce(p_scheduled_end_at, v_order.scheduled_end_at);
  if v_start is null or v_end is null or v_end <= v_start then raise exception 'A job offer needs a valid time.' using errcode = 'HB409'; end if;
  if exists (select 1 from public.work_order_assignments a where a.staff_assignment_id = v_staff.id and a.status = 'accepted' and a.work_order_id <> v_order.id and tstzrange(a.scheduled_start_at, a.scheduled_end_at, '[)') && tstzrange(v_start, v_end, '[)')) then
    raise exception '% is already booked during that time.', v_staff.display_name using errcode = 'HB409';
  end if;
  update public.work_order_assignments set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = v_order.id and status in ('offered', 'accepted');
  insert into public.work_order_assignments (work_order_id, staff_assignment_id, status, offered_at, scheduled_start_at, scheduled_end_at)
  values (v_order.id, v_staff.id, 'offered', now(), v_start, v_end)
  returning id into v_id;
  update public.work_orders set status = 'offered', scheduled_start_at = v_start, scheduled_end_at = v_end, updated_at = now() where id = v_order.id;
  select * into v_complaint from public.complaints where id = v_order.complaint_id;
  perform public.notify_member(v_staff.membership_id, 'job.offered', jsonb_build_object(
    'title', 'A job is available', 'body', coalesce(v_complaint.title, 'Scheduled work'),
    'url', '/worker/jobs?job=' || v_order.id::text, 'work_order_id', v_order.id, 'complaint_id', v_order.complaint_id));
  perform public.enqueue_dispatch_task(v_order.id, 'auto_assign', now() + interval '30 minutes');
  return v_id;
end;
$$;

create or replace function public.dispatch_force_assign(p_work_order_id uuid)
returns uuid language plpgsql security definer set search_path = public
as $$
declare v_order public.work_orders%rowtype; v_pick record; v_id uuid; v_complaint public.complaints%rowtype;
begin
  select * into v_order from public.work_orders where id = p_work_order_id for update;
  if not found or v_order.status in ('completed', 'cancelled', 'failed') then return null; end if;
  select * into v_pick from public.work_order_candidates(p_work_order_id, true)
   where away_until is null or away_until <= now() order by open_jobs, distance_km nulls last limit 1;
  if not found then return null; end if;
  update public.work_order_assignments set status = 'withdrawn', responded_at = now(), ended_at = now() where work_order_id = p_work_order_id and status = 'offered';
  insert into public.work_order_assignments (work_order_id, staff_assignment_id, status, is_forced, is_auto_assigned, scheduled_start_at, scheduled_end_at)
  values (p_work_order_id, v_pick.staff_assignment_id, 'accepted', true, true, v_order.scheduled_start_at, v_order.scheduled_end_at) returning id into v_id;
  update public.work_orders set status = 'scheduled', updated_at = now() where id = p_work_order_id;
  select * into v_complaint from public.complaints where id = v_order.complaint_id;
  insert into public.complaint_events (complaint_id, actor_membership_id, event_type, payload) values
    (v_order.complaint_id, v_order.supervisor_membership_id, 'job_assigned', jsonb_build_object('workOrderId', v_order.id, 'assigneeName', v_pick.display_name, 'forced', true)),
    (v_order.complaint_id, v_order.supervisor_membership_id, 'job_force_assigned', jsonb_build_object('workOrderId', v_order.id, 'assigneeName', v_pick.display_name));
  perform public.notify_member(v_pick.membership_id, 'work_order.assigned', jsonb_build_object('title', 'You have been assigned a critical job', 'body', coalesce(v_complaint.title, 'Scheduled work'), 'url', '/worker/jobs?job=' || v_order.id::text, 'work_order_id', v_order.id));
  perform public.notify_complaint_staff(v_order.complaint_id, 'job.force_assigned', jsonb_build_object('title', 'Critical job force-assigned', 'complaint_id', v_order.complaint_id));
  if v_complaint.raised_by_membership_id is not null then perform public.notify_member(v_complaint.raised_by_membership_id, 'work_order.assigned', jsonb_build_object('title', 'Someone is coming for your complaint', 'body', v_pick.display_name, 'url', '/resident/complaints?complaint=' || v_order.complaint_id::text, 'complaint_id', v_order.complaint_id)); end if;
  return v_id;
end;
$$;

drop function if exists public.decline_work_order_offer(uuid, text);
create function public.decline_work_order_offer(p_work_order_id uuid, p_reason text default null)
returns uuid language plpgsql security definer set search_path = public
as $$
declare v_assignment public.work_order_assignments%rowtype; v_order public.work_orders%rowtype; v_complaint public.complaints%rowtype;
begin
  select * into v_order from public.work_orders where id = p_work_order_id for update;
  if not found then raise exception 'No such job.' using errcode = 'HB404'; end if;
  select * into v_assignment from public.work_order_assignments a where a.work_order_id = p_work_order_id and public.is_own_staff_assignment(a.staff_assignment_id) order by a.offered_at desc limit 1;
  if not found then raise exception 'No such job.' using errcode = 'HB404'; end if;
  if v_assignment.status = 'declined' then return v_assignment.id; end if;
  if v_assignment.is_forced then raise exception 'This assignment cannot be declined.' using errcode = 'HB409'; end if;
  if v_assignment.status <> 'offered' then raise exception 'That offer is no longer open.' using errcode = 'HB409'; end if;
  if nullif(btrim(coalesce(p_reason, '')), '') is null then raise exception 'Please say why you cannot take this job.' using errcode = 'HB409'; end if;
  update public.work_order_assignments set status = 'declined', decline_reason = btrim(p_reason), responded_at = now(), ended_at = now() where id = v_assignment.id;
  select * into v_complaint from public.complaints where id = v_order.complaint_id;
  -- The worker is not a supervisor, so this internal all-declined test cannot
  -- call the supervisor-facing picker. It uses the same ranking source and the
  -- shared exclusion set directly.
  if not exists (
    select 1 from public.dispatch_candidates(v_order.id, 100) candidate
     where not exists (
       select 1 from public.complaint_excluded_staff(v_order.complaint_id) excluded
        where excluded.staff_assignment_id = candidate.staff_assignment_id
     )
  ) then
    if v_complaint.priority = 'high' then perform public.dispatch_force_assign(v_order.id); end if;
    perform public.notify_complaint_staff(v_order.complaint_id, 'job.all_declined', jsonb_build_object('title', 'All available workers declined', 'complaint_id', v_order.complaint_id));
  end if;
  return v_assignment.id;
end;
$$;
grant execute on function public.decline_work_order_offer(uuid, text) to authenticated;

do $$ begin
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='work_order_assignments' and column_name='is_forced') then raise exception 'is_forced missing'; end if;
  if not exists (select 1 from pg_proc where pronamespace='public'::regnamespace and proname='dispatch_force_assign') then raise exception 'dispatch_force_assign missing'; end if;
end $$;
