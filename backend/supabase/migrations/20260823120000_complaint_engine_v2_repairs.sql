-- Complaint Engine v2: forward-only repairs after reconciliation with main.
--
-- The original repair branch used timestamps older than migrations already
-- recorded by the hosted project and copied whole function bodies from an
-- older branch state. Keep the hosted history monotonic and repair the current
-- definitions here instead.

-- `enqueue_dispatch_task` deliberately accepts a smallint queue priority.
-- PostgreSQL resolves the CASE expression below as integer unless it is cast.
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
        new.id,
        'resident_timeout',
        coalesce(new.resident_deadline_at, now() + interval '24 hours')
      );
    end if;
  elsif new.status = 'offered' then
    if tg_op = 'INSERT'
       or old.status is distinct from new.status
       or old.scheduled_start_at is distinct from new.scheduled_start_at then
      perform public.close_dispatch_tasks(new.id, array['resident_timeout']);
      perform public.enqueue_dispatch_task(
        new.id,
        'manual_window',
        now() + case
          when new.priority = 'high' then interval '2 hours'
          else interval '24 hours'
        end,
        (case when new.priority = 'high' then 2 else 0 end)::smallint
      );
    end if;
  elsif new.status = 'failed' then
    if tg_op = 'INSERT' or old.status is distinct from new.status then
      perform public.close_dispatch_tasks(new.id, null);
      perform public.enqueue_dispatch_task(
        new.id,
        'failed_visit_escalation',
        now() + interval '2 hours'
      );
    end if;
  elsif tg_op = 'INSERT' or old.status is distinct from new.status then
    perform public.close_dispatch_tasks(new.id, null);
  end if;
  return new;
end;
$$;

-- This trigger function serves two tables. A work_order_assignments row has a
-- work_order_id but no complaint_id, so resolve the row shape before reading it.
create or replace function public.project_complaint_from_jobs()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_complaint_id uuid;
  v_live integer;
begin
  if tg_table_name = 'work_orders' then
    v_complaint_id := new.complaint_id;
  elsif tg_table_name = 'work_order_assignments' then
    select w.complaint_id
      into v_complaint_id
      from public.work_orders w
     where w.id = new.work_order_id;
  else
    raise exception 'Unsupported complaint projection source: %', tg_table_name;
  end if;

  if tg_table_name = 'work_order_assignments'
     and tg_op = 'INSERT'
     and new.status = 'offered' then
    update public.complaints
       set status = 'acknowledged', updated_at = now()
     where id = v_complaint_id and status = 'open';
  elsif tg_table_name = 'work_orders' and new.status = 'in_progress' then
    update public.complaints
       set status = 'in_progress', updated_at = now()
     where id = v_complaint_id and status in ('open', 'acknowledged');
  elsif tg_table_name = 'work_orders' and new.status = 'completed' then
    select count(*)
      into v_live
      from public.work_orders w
     where w.complaint_id = v_complaint_id
       and w.id <> new.id
       and w.status in (
         'draft',
         'awaiting_resident',
         'offered',
         'scheduled',
         'in_progress'
       );
    if v_live = 0 then
      update public.complaints
         set status = 'resolved', updated_at = now()
       where id = v_complaint_id
         and status in ('open', 'acknowledged', 'in_progress');
    end if;
  end if;
  return new;
end;
$$;

-- The strict public/internal dispatch path continues to exclude a worker who
-- declined this work order. The extra argument is for the explicit supervisor
-- override and critical fallback paths only.
create or replace function public.dispatch_candidates(
  p_work_order_id uuid,
  p_limit integer,
  p_include_declined boolean
)
returns table (
  staff_assignment_id uuid,
  membership_id uuid,
  service_provider_id uuid,
  display_name text,
  has_adjacent_job boolean,
  open_jobs integer,
  distance_km numeric
)
language sql
security definer
set search_path = public
as $$
  with job as (
    select
      w.id,
      w.community_id,
      w.department_id,
      w.skill_id,
      w.scheduled_start_at as slot_start,
      w.scheduled_end_at as slot_end
    from public.work_orders w
    where w.id = p_work_order_id
      and w.scheduled_start_at is not null
      and w.department_id is not null
  ),
  ranked as (
    select
      sa.id as sa_id,
      sa.membership_id as sa_membership_id,
      sa.service_provider_id as sa_provider_id,
      sa.display_name as sa_display_name,
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
          (extensions.st_distance(c.location, sp.location) / 1000)::numeric,
          2
        )
      end as km
    from job j
    join public.staff_assignments sa
      on sa.department_id = j.department_id
     and sa.status = 'active'
     and sa.is_active
     and sa.membership_id is not null
    join public.communities c on c.id = j.community_id
    left join public.service_providers sp on sp.id = sa.service_provider_id
    where (sp.id is null or (sp.status = 'active' and sp.is_available))
      and not public.departure_bars_work(sa.id, j.slot_start)
      and not exists (
        select 1
        from public.worker_unavailability u
        where (
          u.staff_assignment_id = sa.id
          or (sp.id is not null and u.service_provider_id = sp.id)
        )
          and tstzrange(u.starts_at, u.ends_at, '[)')
              && tstzrange(j.slot_start, j.slot_end, '[)')
      )
      and (
        not exists (
          select 1
          from public.worker_availability_rules r
          where r.staff_assignment_id = sa.id
             or (sp.id is not null and r.service_provider_id = sp.id)
        )
        or exists (
          select 1
          from public.worker_availability_rules r
          where (
            r.staff_assignment_id = sa.id
            or (sp.id is not null and r.service_provider_id = sp.id)
          )
            and r.weekday = extract(dow from j.slot_start)::smallint
            and r.start_time <= j.slot_start::time
            and r.end_time >= j.slot_end::time
            and r.effective_from <= j.slot_start::date
            and (
              r.effective_to is null
              or r.effective_to >= j.slot_start::date
            )
        )
      )
      and not exists (
        select 1
        from public.work_order_assignments busy
        where busy.staff_assignment_id = sa.id
          and busy.status = 'accepted'
          and busy.work_order_id <> j.id
          and busy.scheduled_start_at is not null
          and tstzrange(
            busy.scheduled_start_at,
            busy.scheduled_end_at,
            '[)'
          ) && tstzrange(j.slot_start, j.slot_end, '[)')
      )
      and (
        p_include_declined
        or not exists (
          select 1
          from public.work_order_assignments said_no
          where said_no.staff_assignment_id = sa.id
            and said_no.work_order_id = j.id
            and said_no.status = 'declined'
        )
      )
      and (
        j.skill_id is null
        or sp.id is null
        or exists (
          select 1
          from public.service_provider_skills ps
          where ps.service_provider_id = sp.id
            and ps.skill_id = j.skill_id
        )
      )
  )
  select
    candidate.sa_id,
    candidate.sa_membership_id,
    candidate.sa_provider_id,
    candidate.sa_display_name,
    candidate.adjacent,
    candidate.load,
    candidate.km
  from ranked candidate
  order by
    candidate.adjacent desc,
    candidate.load asc,
    candidate.km asc nulls last,
    candidate.sa_display_name
  limit greatest(coalesce(p_limit, 5), 1);
$$;

-- Keep every existing two-argument caller strict while sharing one eligibility
-- implementation with the new override path.
create or replace function public.dispatch_candidates(
  p_work_order_id uuid,
  p_limit integer default 5
)
returns table (
  staff_assignment_id uuid,
  membership_id uuid,
  service_provider_id uuid,
  display_name text,
  has_adjacent_job boolean,
  open_jobs integer,
  distance_km numeric
)
language sql
security definer
set search_path = public
as $$
  select *
  from public.dispatch_candidates(p_work_order_id, p_limit, false);
$$;

comment on function public.dispatch_candidates(uuid, integer, boolean) is
  'Internal eligibility ranking. The boolean permits an explicit override of a prior decline; availability, departure, overlap, and skill checks always remain enforced.';

comment on function public.dispatch_candidates(uuid, integer) is
  'Strict eligibility ranking for normal dispatch. Previously declined workers remain excluded.';

create or replace function public.work_order_candidates(
  p_work_order_id uuid,
  p_include_excluded boolean default false
)
returns table (
  staff_assignment_id uuid,
  membership_id uuid,
  service_provider_id uuid,
  display_name text,
  has_adjacent_job boolean,
  open_jobs integer,
  distance_km numeric,
  away_until timestamptz,
  excluded boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order public.work_orders%rowtype;
begin
  select *
    into v_order
    from public.work_orders
   where id = p_work_order_id;
  if not found then
    raise exception 'No such work order.' using errcode = 'HB404';
  end if;
  if not (
    public.can_supervise_department(v_order.department_id)
    or current_setting('request.jwt.claims', true) is null
  ) then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;

  return query
  with base as (
    select *
    from public.dispatch_candidates(
      p_work_order_id,
      100,
      p_include_excluded
    )
  ),
  excluded_staff as (
    select e.staff_assignment_id
    from public.complaint_excluded_staff(v_order.complaint_id) e
  )
  select
    b.staff_assignment_id,
    b.membership_id,
    b.service_provider_id,
    b.display_name,
    b.has_adjacent_job,
    b.open_jobs,
    b.distance_km,
    (
      select max(u.ends_at)
      from public.worker_unavailability u
      where (
        u.staff_assignment_id = b.staff_assignment_id
        or u.service_provider_id = b.service_provider_id
      )
        and u.ends_at > now()
    ),
    exists (
      select 1
      from excluded_staff e
      where e.staff_assignment_id = b.staff_assignment_id
    )
  from base b
  where p_include_excluded
     or not exists (
       select 1
       from excluded_staff e
       where e.staff_assignment_id = b.staff_assignment_id
     );
end;
$$;

-- This internal function can run from a worker's decline transaction. Calling
-- the supervisor-facing picker here would retain the worker JWT and fail its
-- authorization check before the critical fallback can select anyone.
create or replace function public.dispatch_force_assign(p_work_order_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order public.work_orders%rowtype;
  v_pick record;
  v_id uuid;
  v_complaint public.complaints%rowtype;
begin
  select *
    into v_order
    from public.work_orders
   where id = p_work_order_id
   for update;
  if not found or v_order.status in ('completed', 'cancelled', 'failed') then
    return null;
  end if;

  select *
    into v_pick
    from public.dispatch_candidates(p_work_order_id, 100, true)
   order by open_jobs, distance_km nulls last
   limit 1;
  if not found then
    return null;
  end if;

  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = p_work_order_id and status = 'offered';

  insert into public.work_order_assignments (
    work_order_id,
    staff_assignment_id,
    status,
    is_forced,
    is_auto_assigned,
    scheduled_start_at,
    scheduled_end_at
  ) values (
    p_work_order_id,
    v_pick.staff_assignment_id,
    'accepted',
    true,
    true,
    v_order.scheduled_start_at,
    v_order.scheduled_end_at
  )
  returning id into v_id;

  update public.work_orders
     set status = 'scheduled', updated_at = now()
   where id = p_work_order_id;

  select *
    into v_complaint
    from public.complaints
   where id = v_order.complaint_id;

  insert into public.complaint_events (
    complaint_id,
    actor_membership_id,
    event_type,
    payload
  ) values
    (
      v_order.complaint_id,
      v_order.supervisor_membership_id,
      'job_assigned',
      jsonb_build_object(
        'workOrderId', v_order.id,
        'assigneeName', v_pick.display_name,
        'forced', true
      )
    ),
    (
      v_order.complaint_id,
      v_order.supervisor_membership_id,
      'job_force_assigned',
      jsonb_build_object(
        'workOrderId', v_order.id,
        'assigneeName', v_pick.display_name
      )
    );

  perform public.notify_member(
    v_pick.membership_id,
    'work_order.assigned',
    jsonb_build_object(
      'title', 'You have been assigned a critical job',
      'body', coalesce(v_complaint.title, 'Scheduled work'),
      'url', '/worker?job=' || v_order.id::text,
      'work_order_id', v_order.id
    )
  );
  perform public.notify_complaint_staff(
    v_order.complaint_id,
    'job.force_assigned',
    jsonb_build_object(
      'title', 'Critical job force-assigned',
      'complaint_id', v_order.complaint_id
    )
  );
  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id,
      'work_order.assigned',
      jsonb_build_object(
        'title', 'Someone is coming for your complaint',
        'body', v_pick.display_name,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'complaint_id', v_order.complaint_id
      )
    );
  end if;
  return v_id;
end;
$$;

-- Internal dispatch functions expose roster data and bypass request-level role
-- checks, so only definer callers and the service role may execute them.
revoke all on function public.dispatch_candidates(uuid, integer, boolean)
  from public, anon, authenticated;
revoke all on function public.dispatch_candidates(uuid, integer)
  from public, anon, authenticated;
revoke all on function public.dispatch_force_assign(uuid)
  from public, anon, authenticated;
grant execute on function public.dispatch_force_assign(uuid) to service_role;

revoke all on function public.work_order_candidates(uuid, boolean)
  from public, anon, authenticated;
grant execute on function public.work_order_candidates(uuid, boolean)
  to authenticated;

-- Function overloading changes the PostgREST function catalogue. Refresh it
-- immediately instead of waiting for the schema-cache polling interval.
notify pgrst, 'reload schema';

do $$
begin
  if to_regprocedure('public.dispatch_candidates(uuid,integer,boolean)') is null then
    raise exception 'three-argument dispatch_candidates missing';
  end if;
  if position(
    '(case when new.priority = ''high'' then 2 else 0 end)::smallint'
    in pg_get_functiondef('public.sync_dispatch_tasks()'::regprocedure)
  ) = 0 then
    raise exception 'manual-window priority cast missing';
  end if;
  if position(
    'tg_table_name = ''work_order_assignments'''
    in pg_get_functiondef('public.project_complaint_from_jobs()'::regprocedure)
  ) = 0 then
    raise exception 'assignment trigger row-shape repair missing';
  end if;
  if position(
    '/worker/jobs?job='
    in pg_get_functiondef('public.dispatch_force_assign(uuid)'::regprocedure)
  ) > 0 then
    raise exception 'obsolete worker notification URL restored';
  end if;
end;
$$;
