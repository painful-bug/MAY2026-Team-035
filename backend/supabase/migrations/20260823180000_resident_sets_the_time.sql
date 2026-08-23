-- ---------------------------------------------------------------------------
-- 20260823180000_resident_sets_the_time.sql
--
-- The resident sets the time, and the system books what nobody schedules.
--
-- Live testing surfaced the raise form as the wrong place to decide when a
-- technician turns up: the supervisor was guessing an hour for somebody else's
-- home. The product owner ruled on 2026-08-23
-- (`docs/COMPLAINT_ENGINE_HANDOFF.md` §23) that the raise form loses its
-- date/time for everyone (F1); a resident-subject job asks the RESIDENT to
-- pick, and only their answer puts the job on the open pile; a facility job is
-- booked by the system into the first free hour, but only after the
-- department's urgent (`priority = 'high'`) resident complaints have been
-- allotted; twenty-four hours of resident silence is answered by the system
-- booking the first available hour and assigning the serviceman itself (F2);
-- and pick-mode carries no decline (F3). The orchestrator's adjudications
-- G1-G11 are logged in `docs/plans/RESIDENT_SETS_THE_TIME_SPEC.md`; the
-- section markers below cite them rather than restating them.
--
-- WHAT THIS FILE DELIBERATELY DOES NOT ADD
--
--   * **No new work-order status.** `work_orders_status_check` (`0036`:147) is
--     a closed list, and a new word costs a drop-and-recreate on a constrained
--     column. Pick-mode is `status = 'awaiting_resident' AND
--     scheduled_start_at IS NULL`; approve-mode -- the supervisor-proposed
--     visit that `reschedule_work_order` still creates -- is the same status
--     WITH a slot (G2). The existing sync trigger already arms
--     `resident_timeout` on any `awaiting_resident` entry, so pick-mode
--     inherits its own 24-hour timer for free.
--   * **No new complaint-event word.** `complaint_events_type_check`
--     (`20260822170000`:1021) is a closed 26-word list. The resident's pick
--     writes `job_scheduled` with `resident_set: true`; the timeout's booking
--     writes `job_assigned` with `auto_assigned: true`. The payload carries
--     the distinction, exactly as `20260823170000` D4 did for `claimed`.
--   * **No board change.** `worker_open_jobs` already excludes
--     `awaiting_resident` (D1's status list is `('draft','offered')`), so "not
--     in the pile until the resident answers" needs nothing here (G8). A
--     facility draft inside the courtesy gate stays claimable throughout; a
--     claim simply wins the race and the task no-ops.
--
-- THE ONE CONSTRAINT THIS FILE WIDENS
--
-- `dispatch_tasks_kind_check` (`20260813104000`:5-7), for the new
-- `facility_auto_assign` kind. Section 1 proves no existing row falls outside
-- the new list before it drops anything, in `20260822170000` §7's shape.
--
-- WHY THE SLOT-FINDER IS A REFACTOR AND NOT A SECOND ELIGIBILITY RULE
--
-- Six triggers fire on `work_orders` writes, so the finder must never probe an
-- hour by writing it to the row. `dispatch_candidates` is keyed to the job's
-- STORED slot -- its `job` CTE requires `scheduled_start_at is not null` and
-- every availability, leave, working-hours and overlap clause reads it. So the
-- body moves to `dispatch_candidates_at`, parameterised by a HYPOTHETICAL
-- slot, and the three-argument `dispatch_candidates` becomes a delegate that
-- passes the job's own slot: one eligibility rule, one ordering, one set of
-- grants. A second copy would be a second answer to "who may take this job",
-- and the one that drifts is always the one nobody is testing (G4).
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. The one widened constraint (G6)
--
-- Prove first, then drop, then add, then prove the new word specifically -- a
-- bare existence check would pass against the very constraint being replaced.
-- Widening only: every kind the old constraint accepted is in the list below.
-- ---------------------------------------------------------------------------

do $$
declare v_bad text;
begin
  select kind into v_bad from public.dispatch_tasks where kind not in (
    'ping', 'auto_assign', 'resident_timeout', 'failed_visit_escalation',
    'departure_removal', 'manual_window', 'auto_close_warning', 'auto_close',
    'facility_auto_assign') limit 1;
  if v_bad is not null then
    raise exception 'Unknown existing dispatch task kind: %', v_bad;
  end if;
end $$;

alter table public.dispatch_tasks drop constraint if exists dispatch_tasks_kind_check;
alter table public.dispatch_tasks add constraint dispatch_tasks_kind_check check (kind in (
  'ping', 'auto_assign', 'resident_timeout', 'failed_visit_escalation', 'departure_removal',
  'manual_window', 'auto_close_warning', 'auto_close', 'facility_auto_assign'));

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.dispatch_tasks'::regclass
       and conname  = 'dispatch_tasks_kind_check'
       and pg_get_constraintdef(oid) like '%facility_auto_assign%'
  ) then
    raise exception 'dispatch kind check missing or does not allow facility_auto_assign';
  end if;
end $$;


-- ---------------------------------------------------------------------------
-- 2. Eligibility, asked about an hour that is not on the row yet (G4)
--
-- `20260823120000`'s body verbatim, with `j.slot_start` / `j.slot_end` fed
-- from the arguments instead of from the stored columns. The `job` CTE keeps
-- the null guard -- moved onto the parameters -- so the delegate below
-- reproduces today's behaviour exactly: a job with no hour has no candidates,
-- because none of the leave, working-hours or overlap clauses can be asked
-- without one.
-- ---------------------------------------------------------------------------

create or replace function public.dispatch_candidates_at(
  p_work_order_id   uuid,
  p_start           timestamptz,
  p_end             timestamptz,
  p_limit           integer,
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
      p_start as slot_start,
      p_end as slot_end
    from public.work_orders w
    where w.id = p_work_order_id
      and p_start is not null
      and p_end is not null
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

comment on function public.dispatch_candidates_at(
  uuid, timestamptz, timestamptz, integer, boolean) is
  'Eligibility ranking for a HYPOTHETICAL hour. The one implementation: the '
  'three-argument dispatch_candidates delegates to it with the job''s stored '
  'slot, and find_first_available_slot walks it hour by hour without ever '
  'writing a trial hour to work_orders -- six triggers fire on that table.';

-- The three-argument entry point keeps its signature, its ordering and its
-- grants; only its body changes, into a delegate. Every existing caller --
-- `dispatch_ping_candidates`, `dispatch_auto_assign`, `work_order_candidates`,
-- `dispatch_force_assign`, and the two-argument wrapper `20260823120000`
-- declared and this file leaves untouched -- is unaffected.
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
  select *
  from public.dispatch_candidates_at(
    p_work_order_id,
    (select w.scheduled_start_at from public.work_orders w where w.id = p_work_order_id),
    (select w.scheduled_end_at from public.work_orders w where w.id = p_work_order_id),
    p_limit,
    p_include_declined
  );
$$;

comment on function public.dispatch_candidates(uuid, integer, boolean) is
  'Internal eligibility ranking for the job''s own hour. A delegate to '
  'dispatch_candidates_at since 20260823180000: the boolean still permits an '
  'explicit override of a prior decline, and availability, departure, overlap '
  'and skill checks always remain enforced.';


-- ---------------------------------------------------------------------------
-- 3. The first hour somebody can actually take (G4, G10)
--
-- Walks the top of each hour from `p_from` forward and returns the first one
-- where the job has at least one eligible candidate, with that candidate. The
-- three constants are hardcoded in the engine's style -- the 24-hour resident
-- deadline has been a literal at four sites since `0036` -- and each says what
-- it is beside it. Nothing here writes anything, which is the point: probing
-- by storing a trial hour on `work_orders` would fire six triggers per probe.
-- ---------------------------------------------------------------------------

create or replace function public.find_first_available_slot(
  p_work_order_id uuid,
  p_from          timestamptz
)
returns table (
  slot_start          timestamptz,
  slot_end            timestamptz,
  staff_assignment_id uuid
)
language plpgsql
security definer
set search_path = public
as $$
declare
  -- How long a synthesized visit is. Nobody asked for a duration, so the
  -- engine picks one, and two hours is the window `dispatch_ping_candidates`
  -- was already offering people.
  v_duration constant interval := interval '2 hours';
  -- How far ahead to look before giving up and handing the job back to a
  -- human. Fourteen days of nobody free is a staffing problem, not a
  -- scheduling one.
  v_horizon  constant interval := interval '14 days';
  v_floor    timestamptz;
  v_cursor   timestamptz;
  v_limit    timestamptz;
  v_pick     record;
begin
  if p_work_order_id is null then
    return;
  end if;

  v_floor  := coalesce(p_from, now());
  -- The first whole hour at or after the floor.
  v_cursor := date_trunc('hour', v_floor);
  if v_cursor < v_floor then
    v_cursor := v_cursor + interval '1 hour';
  end if;
  v_limit := v_cursor + v_horizon;

  while v_cursor < v_limit loop
    select *
      into v_pick
      from public.dispatch_candidates_at(
        p_work_order_id, v_cursor, v_cursor + v_duration, 1, false);
    if found then
      slot_start          := v_cursor;
      slot_end            := v_cursor + v_duration;
      staff_assignment_id := v_pick.staff_assignment_id;
      return next;
      return;
    end if;
    v_cursor := v_cursor + interval '1 hour';
  end loop;

  -- No row. Every caller reads that as "nobody, within the horizon" and says
  -- so to a supervisor rather than silently doing nothing.
  return;
end;
$$;

comment on function public.find_first_available_slot(uuid, timestamptz) is
  'The first top-of-hour at or after p_from where this job has an eligible '
  'candidate, with that candidate. Two-hour visits, fourteen-day horizon, and '
  'no writes: the probe is dispatch_candidates_at, not a trial UPDATE.';


-- ---------------------------------------------------------------------------
-- 4. The raise, forked on whether a slot was sent (G1)
--
-- The API keeps accepting a slot, so a slotted raise keeps today's semantics
-- exactly -- resident + slot is approve-mode `awaiting_resident`, facility +
-- slot is `offered`. What is new is the SLOTLESS raise, which is what every
-- form in the product now sends:
--
--   * resident, no slot -> `awaiting_resident` with a NULL slot and the same
--     24-hour deadline. Pick-mode: the resident is being asked WHEN, not
--     whether. The trigger in section 7 arms the timer from the status alone.
--   * facility, no slot -> `draft`, unchanged, and the trigger arms a
--     `facility_auto_assign` task. Nothing is enqueued here on purpose: the
--     status change already says everything the queue needs, which is the rule
--     `0037` §2 set and every handler since has kept.
--
-- The event word does not move. Nothing was scheduled by a slotless raise, so
-- `job_created` is still the true sentence; the resident's own pick is what
-- writes `job_scheduled` (section 5).
-- ---------------------------------------------------------------------------

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
  v_mode        text;
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

  -- G1, the fork. A resident-subject job is `awaiting_resident` either way and
  -- the slot is the discriminator: present means "does this suit you", absent
  -- means "you say when". A facility job with a slot needs nobody's answer; a
  -- facility job without one is a draft the queue books for itself.
  if v_kind = 'resident' then
    v_status   := 'awaiting_resident';
    -- CHANGED 20260823180000: the deadline now arms in both modes. Silence is
    -- answered by section 6 either way -- by proceeding with the proposed hour,
    -- or by finding one.
    v_deadline := now() + interval '24 hours';
    v_mode     := case when p_scheduled_start_at is null then 'pick' else 'approve' end;
  elsif p_scheduled_start_at is null then
    v_status := 'draft';
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
      'mode', v_mode,
      'note', nullif(btrim(coalesce(p_note, '')), ''))
  );

  -- D9: an offer that expires and requires an action is not the passive field
  -- change ARCHITECTURE.md's rule was written to suppress. A draft work order
  -- notifies nobody, because nothing has been asked of anyone yet -- and a
  -- slotless facility draft asks nobody anything, it just queues itself.
  if v_status = 'awaiting_resident' then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.schedule_requested',
      jsonb_build_object(
        'title', case when v_mode = 'pick'
                      then 'Pick a time for this visit'
                      else 'A visit has been proposed' end,
        'body', v_complaint.title,
        'url', '/resident/complaints?complaint=' || v_complaint.id::text,
        'complaint_id', v_complaint.id,
        'work_order_id', v_id,
        'mode', v_mode,
        'starts_at', p_scheduled_start_at,
        'ends_at', p_scheduled_end_at));
  end if;

  return v_id;
end;
$$;


-- ---------------------------------------------------------------------------
-- 5. The resident's pick (G3)
--
-- Complaint-scoped like its siblings, and separate from
-- `respond_to_work_order_schedule` for the reason `0036` §6 gave about that
-- one: the authorization question here is "did you raise this complaint", and
-- the two answers are different verbs. Confirming is agreeing to a time
-- somebody else chose; this is choosing one.
--
-- There is no decline (F3). Pick-mode was never a proposal, so there is
-- nothing to refuse; twenty-four hours of silence is answered by section 6.
-- ---------------------------------------------------------------------------

create or replace function public.resident_set_work_order_schedule(
  p_work_order_id uuid,
  p_start         timestamptz,
  p_end           timestamptz
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order    public.work_orders%rowtype;
  v_resident uuid;
begin
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
    raise exception 'There is nothing to schedule on this complaint right now.'
      using errcode = 'HB409';
  end if;

  -- The discriminator, refused in words. A supervisor who proposed an hour
  -- asked a yes/no question, and answering it by overwriting the hour would
  -- silently turn their proposal into the resident's.
  if v_order.scheduled_start_at is not null then
    raise exception 'The association proposed this visit''s time -- answer that instead.'
      using errcode = 'HB409';
  end if;

  if p_start is null or p_end is null or p_end <= p_start then
    raise exception 'A visit needs a start and an end, and it must end after it starts.'
      using errcode = 'HB409';
  end if;

  if p_start <= now() then
    raise exception 'Pick a time in the future.' using errcode = 'HB409';
  end if;

  -- `offered` is the pile. It arms the existing `manual_window` machinery
  -- through the trigger in section 7 and puts the job on the open-jobs board,
  -- which is exactly what ruling F1 means by "reaches the open pile".
  update public.work_orders
     set scheduled_start_at   = p_start,
         scheduled_end_at     = p_end,
         status               = 'offered',
         resident_deadline_at = null,
         updated_at           = now()
   where id = v_order.id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_resident, 'job_scheduled',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'startsAt', p_start,
      'endsAt', p_end,
      'resident_set', true)
  );

  -- Straight to the supervisor who raised it, not to every admin -- `0036`
  -- §6's posture on the resident's other answer, including its fallback for a
  -- supervisor whose membership has since ended, so an answer is never
  -- delivered to nobody.
  if v_order.supervisor_membership_id is not null then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.resident_scheduled',
      jsonb_build_object(
        'title', 'The resident picked a time',
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', p_start,
        'ends_at', p_end));
  else
    perform public.notify_community_staff(
      v_order.community_id, 'work_order.resident_scheduled',
      jsonb_build_object(
        'title', 'The resident picked a time',
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', p_start,
        'ends_at', p_end));
  end if;
end;
$$;

comment on function public.resident_set_work_order_schedule(
  uuid, timestamptz, timestamptz) is
  'The resident chooses the hour for a visit to their own home (ruling F1). '
  'Refuses a job that is not waiting on them, and refuses one where the '
  'association proposed an hour -- that is respond_to_work_order_schedule''s '
  'question. Moves the job to `offered`, which is the open pile.';


-- ---------------------------------------------------------------------------
-- 6. Twenty-four hours of silence, branched on the discriminator (G5, F2)
--
-- Approve-mode is untouched: a proposed hour nobody answered proceeds, exactly
-- as `0037` §5 decided and for the reason it recorded. Pick-mode expired is
-- the new branch, and it is what ruling F2 asks for in one sentence: the first
-- available time after the 24-hour mark that has a serviceman available, and
-- that serviceman assigned.
--
-- No hit within the horizon is NOT a failure to report and forget. The job
-- goes to `draft`, which puts it on the open-jobs board where any eligible
-- technician can claim it, and the supervisor is told. A job stranded in
-- `awaiting_resident` with a dead timer would be invisible to everybody.
-- ---------------------------------------------------------------------------

create or replace function public.dispatch_resident_timeout(p_work_order_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order      public.work_orders%rowtype;
  v_complaint  public.complaints%rowtype;
  v_slot       record;
  v_name       text;
  v_member     uuid;
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    return false;
  end if;

  -- They answered, or a supervisor got tired of waiting and assigned by hand
  -- (`0036` allows exactly that, deliberately). Either way this task is moot.
  if v_order.status <> 'awaiting_resident' then
    return false;
  end if;

  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  -- ---- approve-mode: `0037` §5's body, unchanged ----------------------------
  --
  -- **Proceed, do not close.** The source document asks for the complaint to
  -- auto-resolve after 24 hours of silence; resolving a complaint the resident
  -- never saw is a product decision and this is not the place to make it
  -- quietly. Going ahead with the visit needs no such decision and is what the
  -- resident was told would happen.
  if v_order.scheduled_start_at is not null then
    update public.work_orders
       set status               = 'offered',
           resident_deadline_at = null,
           updated_at           = now()
     where id = v_order.id;

    insert into public.complaint_events
      (complaint_id, actor_membership_id, event_type, payload)
    values (
      v_order.complaint_id, v_order.supervisor_membership_id, 'job_scheduled',
      jsonb_build_object(
        'workOrderId', v_order.id,
        'startsAt', v_order.scheduled_start_at,
        'endsAt', v_order.scheduled_end_at,
        'note', 'Proceeding without a response.')
    );

    if v_complaint.raised_by_membership_id is not null then
      perform public.notify_member(
        v_complaint.raised_by_membership_id, 'work_order.proceeding',
        jsonb_build_object(
          'title', 'Your visit is going ahead',
          'body', coalesce(v_complaint.title, 'Scheduled work'),
          'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
          'work_order_id', v_order.id,
          'complaint_id', v_order.complaint_id,
          'starts_at', v_order.scheduled_start_at));
    end if;

    -- The trigger in section 7 arms the ping from here; nothing enqueues it by
    -- hand, because the status change already says everything the queue needs.
    return true;
  end if;

  -- ---- pick-mode expired: the system books it (F2) --------------------------
  select * into v_slot
    from public.find_first_available_slot(v_order.id, now());

  if not found then
    -- Nobody free inside the horizon. Back to the pile, where a technician can
    -- still claim it, and the supervisor is told rather than left guessing.
    update public.work_orders
       set status               = 'draft',
           resident_deadline_at = null,
           updated_at           = now()
     where id = v_order.id;

    if v_order.supervisor_membership_id is not null then
      perform public.notify_member(
        v_order.supervisor_membership_id, 'work_order.no_candidates',
        jsonb_build_object(
          'title', 'Nobody could be assigned',
          'url', '/admin/departments/' || v_order.department_id::text
                 || '/work-orders?job=' || v_order.id::text,
          'work_order_id', v_order.id,
          'complaint_id', v_order.complaint_id,
          'starts_at', null));
    end if;
    return true;
  end if;

  select sa.display_name, sa.membership_id
    into v_name, v_member
    from public.staff_assignments sa
   where sa.id = v_slot.staff_assignment_id;

  -- Withdrawn, not deleted: `0036` §5 and `0037` §5 both made this call, and
  -- "we asked five people and gave it to Anil" is the history a supervisor asks
  -- about.
  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = v_order.id
     and status = 'offered';

  insert into public.work_order_assignments (
    work_order_id, staff_assignment_id, status, is_forced, is_auto_assigned,
    offered_at, responded_at, scheduled_start_at, scheduled_end_at
  )
  values (
    v_order.id, v_slot.staff_assignment_id, 'accepted', false, true,
    now(), now(), v_slot.slot_start, v_slot.slot_end
  );

  update public.work_orders
     set scheduled_start_at   = v_slot.slot_start,
         scheduled_end_at     = v_slot.slot_end,
         status               = 'scheduled',
         resident_deadline_at = null,
         updated_at           = now()
   where id = v_order.id;

  -- No new event word: `job_assigned` with the distinction in the payload, the
  -- rule `20260823170000` D4 set for `claimed`.
  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_order.supervisor_membership_id, 'job_assigned',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assigneeName', v_name,
      'startsAt', v_slot.slot_start,
      'endsAt', v_slot.slot_end,
      'auto_assigned', true)
  );

  if v_member is not null then
    perform public.notify_member(
      v_member, 'work_order.assigned',
      jsonb_build_object(
        'title', 'You have been assigned a job',
        'body', coalesce(v_complaint.title, 'Scheduled work'),
        'url', '/worker?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'starts_at', v_slot.slot_start,
        'ends_at', v_slot.slot_end));
  end if;

  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.assigned',
      jsonb_build_object(
        'title', 'Someone is coming for your complaint',
        'body', v_name,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_slot.slot_start,
        'ends_at', v_slot.slot_end));
  end if;

  if v_order.supervisor_membership_id is not null then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.auto_assigned',
      jsonb_build_object(
        'title', coalesce(v_name, 'A worker') || ' was auto-assigned to '
                 || coalesce(v_complaint.title, 'a job'),
        'body', coalesce(v_name, 'A worker'),
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_slot.slot_start));
  end if;

  return true;
end;
$$;

comment on function public.dispatch_resident_timeout(uuid) is
  'Twenty-four hours of silence, answered two ways (F2). A proposed hour '
  'proceeds, exactly as before. A pick-mode job with no hour is booked into '
  'the first slot a serviceman can take, and that serviceman is assigned; if '
  'nobody is free inside the horizon it returns to the open board and the '
  'supervisor is told. Does not resolve the complaint.';


-- ---------------------------------------------------------------------------
-- 7. The facility job books itself, once the urgent homes are covered (G6)
--
-- Ruling F1's second half: nobody confirms a common-area job, so the system
-- books it -- **but only after all urgent (`priority = 'high'`) resident
-- complaints in the department have been allotted.** The gate is a re-check
-- rather than a queue: the task completes and re-arms an hour later, and the
-- job stays claimable on the open board throughout, so a gated job is never
-- stranded behind a backlog nobody is clearing.
-- ---------------------------------------------------------------------------

create or replace function public.dispatch_facility_auto_assign(p_work_order_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order     public.work_orders%rowtype;
  v_complaint public.complaints%rowtype;
  v_slot      record;
  v_name      text;
  v_member    uuid;
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    return false;
  end if;

  -- A supervisor scheduled it, a technician claimed it off the board (C3
  -- keeps drafts claimable, G8), or it was cancelled. All three mean a human
  -- got there first, which is the outcome this task exists to make unnecessary
  -- rather than one to fight.
  if v_order.status <> 'draft' or v_order.subject_kind <> 'facility' then
    return false;
  end if;

  if exists (
    select 1
      from public.work_order_assignments a
     where a.work_order_id = v_order.id
       and a.status in ('offered', 'accepted')
  ) then
    return false;
  end if;

  -- The courtesy gate. An urgent home visit that nobody has been sent to yet
  -- outranks a common-area job, and "allotted" is asked the way the board asks
  -- it: a live offer or an acceptance.
  if exists (
    select 1
      from public.work_orders urgent
     where urgent.department_id = v_order.department_id
       and urgent.id <> v_order.id
       and urgent.subject_kind = 'resident'
       and urgent.priority = 'high'
       and urgent.status in ('draft', 'awaiting_resident', 'offered')
       and not exists (
         select 1
           from public.work_order_assignments a
          where a.work_order_id = urgent.id
            and a.status in ('offered', 'accepted')
       )
  ) then
    -- Re-checked hourly. The job is on the open board the whole time, so the
    -- wait costs nothing but the system's own hand.
    perform public.enqueue_dispatch_task(
      v_order.id, 'facility_auto_assign', now() + interval '1 hour');
    return false;
  end if;

  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  select * into v_slot
    from public.find_first_available_slot(v_order.id, now());

  if not found then
    -- Told once, and the job stays on the board. Re-arming here would notify
    -- the same supervisor every hour about the same empty roster.
    if v_order.supervisor_membership_id is not null then
      perform public.notify_member(
        v_order.supervisor_membership_id, 'work_order.no_candidates',
        jsonb_build_object(
          'title', 'Nobody could be assigned',
          'url', '/admin/departments/' || v_order.department_id::text
                 || '/work-orders?job=' || v_order.id::text,
          'work_order_id', v_order.id,
          'complaint_id', v_order.complaint_id,
          'starts_at', null));
    end if;
    return false;
  end if;

  select sa.display_name, sa.membership_id
    into v_name, v_member
    from public.staff_assignments sa
   where sa.id = v_slot.staff_assignment_id;

  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = v_order.id
     and status = 'offered';

  insert into public.work_order_assignments (
    work_order_id, staff_assignment_id, status, is_forced, is_auto_assigned,
    offered_at, responded_at, scheduled_start_at, scheduled_end_at
  )
  values (
    v_order.id, v_slot.staff_assignment_id, 'accepted', false, true,
    now(), now(), v_slot.slot_start, v_slot.slot_end
  );

  update public.work_orders
     set scheduled_start_at   = v_slot.slot_start,
         scheduled_end_at     = v_slot.slot_end,
         status               = 'scheduled',
         resident_deadline_at = null,
         updated_at           = now()
   where id = v_order.id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_order.supervisor_membership_id, 'job_assigned',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assigneeName', v_name,
      'startsAt', v_slot.slot_start,
      'endsAt', v_slot.slot_end,
      'auto_assigned', true)
  );

  if v_member is not null then
    perform public.notify_member(
      v_member, 'work_order.assigned',
      jsonb_build_object(
        'title', 'You have been assigned a job',
        'body', coalesce(v_complaint.title, 'Scheduled work'),
        'url', '/worker?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'starts_at', v_slot.slot_start,
        'ends_at', v_slot.slot_end));
  end if;

  -- A facility job has no resident to tell, which is the whole reason nobody
  -- confirms it. `raised_by_membership_id` is still notified when the complaint
  -- behind it came from a person -- somebody reported the broken gate.
  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.assigned',
      jsonb_build_object(
        'title', 'Someone is coming for your complaint',
        'body', v_name,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_slot.slot_start,
        'ends_at', v_slot.slot_end));
  end if;

  if v_order.supervisor_membership_id is not null then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.auto_assigned',
      jsonb_build_object(
        'title', coalesce(v_name, 'A worker') || ' was auto-assigned to '
                 || coalesce(v_complaint.title, 'a job'),
        'body', coalesce(v_name, 'A worker'),
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_slot.slot_start));
  end if;

  return true;
end;
$$;

comment on function public.dispatch_facility_auto_assign(uuid) is
  'Nobody confirms a common-area job, so the system books it (F1) -- after '
  'every urgent resident job in the department has somebody on it. Gated: '
  'completes and re-arms an hour later, while the job stays claimable on the '
  'open board. Idempotent: a draft that stopped being a draft is a no-op.';

-- The trigger, redefined so this file is provably the last word on it. Every
-- existing arm is carried forward byte for byte -- the `resident_timeout`
-- re-arm, the `manual_window` enqueue with `20260823120000`'s smallint cast,
-- the failed-visit escalation, and the final `else` that cancels every timer on
-- a status this function does not recognise. `draft` stops falling into that
-- else and gets an arm of its own: it still closes the job's timers on the way
-- in, and on INSERT of a facility draft it arms the new task.
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
  elsif new.status = 'draft' then
    if tg_op = 'INSERT' or old.status is distinct from new.status then
      perform public.close_dispatch_tasks(new.id, null);
    end if;
    -- G6: on INSERT only. A job that RETURNS to draft -- a declined proposal,
    -- a timeout that found nobody -- has already been through the queue and is
    -- on the open board; re-arming there would be the system booking a job a
    -- human just handed back.
    if tg_op = 'INSERT' and new.subject_kind = 'facility' then
      perform public.enqueue_dispatch_task(new.id, 'facility_auto_assign', now());
    end if;
  elsif tg_op = 'INSERT' or old.status is distinct from new.status then
    perform public.close_dispatch_tasks(new.id, null);
  end if;
  return new;
end;
$$;

-- The handler table, redefined so this file is provably the last word on it.
-- Every existing arm is carried forward; the `else` still completes a task
-- whose kind nothing here handles, with the reason in `last_error`.
create or replace function public.fire_dispatch_task(p_task_id uuid)
returns text language plpgsql security definer set search_path = public
as $$
declare v_task public.dispatch_tasks%rowtype; v_result text; v_id uuid;
begin
  select * into v_task from public.dispatch_tasks where id = p_task_id for update;
  if not found then return 'missing'; end if;
  if v_task.completed_at is not null then return 'already_done'; end if;
  case v_task.kind
    when 'ping' then v_result := 'offered:' || public.dispatch_ping_candidates(v_task.work_order_id)::text;
    when 'auto_assign' then v_id := public.dispatch_auto_assign(v_task.work_order_id); v_result := coalesce('assigned:' || v_id::text, 'no_candidate');
    when 'resident_timeout' then v_result := case when public.dispatch_resident_timeout(v_task.work_order_id) then 'proceeded' else 'skipped' end;
    when 'failed_visit_escalation' then v_result := case when public.dispatch_failed_visit_escalation(v_task.work_order_id) then 'escalated' else 'skipped' end;
    when 'departure_removal' then v_result := case when public.dispatch_departure_removal(v_task.departure_id) then 'removed' else 'skipped' end;
    when 'manual_window' then v_result := case when public.dispatch_manual_window(v_task.work_order_id) then 'fallback_started' else 'skipped' end;
    when 'auto_close_warning' then v_result := case when public.dispatch_auto_close(v_task.complaint_id, true) then 'warned' else 'skipped' end;
    when 'auto_close' then v_result := case when public.dispatch_auto_close(v_task.complaint_id, false) then 'closed' else 'skipped' end;
    when 'facility_auto_assign' then
      -- Closed BEFORE the handler runs, and this is the only arm that needs
      -- it. The handler's courtesy gate re-arms the same kind for the same
      -- job, and `dispatch_tasks_one_open_per_kind` would fold that retry into
      -- this very row -- which the update at the bottom would then complete,
      -- silently cancelling the retry. Completing first makes the retry a new
      -- row. The bottom update is harmless afterwards; it is the same
      -- transaction and therefore the same `now()`.
      update public.dispatch_tasks set completed_at = now(), last_error = null
       where id = p_task_id;
      v_result := case when public.dispatch_facility_auto_assign(v_task.work_order_id) then 'assigned' else 'skipped' end;
    else update public.dispatch_tasks set last_error = 'No handler for kind: ' || v_task.kind, completed_at = now() where id = p_task_id; return 'unsupported';
  end case;
  update public.dispatch_tasks set completed_at = now(), last_error = null where id = p_task_id;
  return v_result;
end;
$$;


-- ---------------------------------------------------------------------------
-- 8. The sixth triage bucket (G7)
--
-- `20260822170000` §8's body with one bucket added and one narrowed. A job
-- waiting on a resident is not an open request: nobody can act on it, and a
-- supervisor scanning "open requests" for something to do was being shown work
-- that is not theirs to move. So `open_requests` becomes `draft|offered` only,
-- and `awaiting_resident` gets its own array -- rendered by the frontend as
-- "Awaiting resident response".
--
-- Everything else is `20260822170000`'s, including the vocabulary: `priority`
-- and `status` go out as stored, because `app/domain/vocabularies.py` is the
-- one place this codebase translates one.
-- ---------------------------------------------------------------------------

create or replace function public.supervisor_triage_snapshot(p_department_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_new      jsonb;
  v_taken    jsonb;
  v_awaiting jsonb;
  v_open     jsonb;
  v_pending  jsonb;
  v_progress jsonb;
begin
  if p_department_id is null then
    raise exception 'No such department.' using errcode = 'HB404';
  end if;

  if not public.can_supervise_department(p_department_id) then
    raise exception 'You do not work on this department''s complaints.'
      using errcode = 'HB403';
  end if;

  if not exists (select 1 from public.departments d where d.id = p_department_id) then
    raise exception 'No such department.' using errcode = 'HB404';
  end if;

  with complaint_rows as (
    select
      c.id,
      c.title,
      c.category,
      c.priority,
      c.status::text                          as status,
      c.location,
      c.created_at,
      c.due_at,
      c.returned_to_pool_at,
      coalesce(c.reopened_count, 0)           as reopened_count,
      c.taken_up_at,
      coalesce(p.full_name, 'A resident')     as raised_by,
      u.unit_code,
      r.id                                    as open_request_id,
      tp.full_name                            as taken_up_by_name,
      (select ev.created_at
         from public.complaint_events ev
        where ev.complaint_id = c.id
          and ev.event_type   = 'department_assigned'
          and ev.payload->>'to_department_id' = p_department_id::text
        order by ev.created_at desc
        limit 1)                              as rerouted_at,
      (select count(*)
         from public.work_orders w
        where w.complaint_id = c.id
          and w.status not in ('completed', 'cancelled', 'failed'))
                                              as live_work_order_count
    from public.complaints c
    left join public.community_memberships m on m.id = c.raised_by_membership_id
    left join public.profiles p on p.id = m.profile_id
    left join public.unit_residencies ur
           on ur.membership_id = m.id and ur.ended_at is null
    left join public.units u on u.id = ur.unit_id
    left join public.complaint_department_requests r
           on r.complaint_id = c.id and r.status = 'pending'
    left join public.community_memberships tm on tm.id = c.taken_up_by_membership_id
    left join public.profiles tp on tp.id = tm.profile_id
    where c.department_id = p_department_id
      and c.status::text in ('open', 'acknowledged')
  ),
  work_order_rows as (
    select
      w.id,
      w.complaint_id,
      c.title                                 as complaint_title,
      c.category                              as complaint_category,
      w.priority,
      w.status,
      w.scheduled_start_at,
      w.scheduled_end_at,
      w.started_at,
      w.supervision_inherited_at              as inherited_at,
      w.location_text,
      s.name                                  as skill_name,
      w.created_at,
      (select sa.display_name
         from public.work_order_assignments woa
         left join public.staff_assignments sa on sa.id = woa.staff_assignment_id
        where woa.work_order_id = w.id
          and woa.status = 'accepted'
        order by woa.offered_at desc
        limit 1)                              as assignee_name,
      (select sa.display_name
         from public.work_order_assignments woa
         left join public.staff_assignments sa on sa.id = woa.staff_assignment_id
        where woa.work_order_id = w.id
          and woa.status = 'offered'
        order by woa.offered_at desc
        limit 1)                              as offered_to_name,
      (w.status = 'scheduled'
       or exists (
            select 1
              from public.work_order_assignments a
             where a.work_order_id = w.id
               and a.status = 'accepted'
          ))                                  as committed
    from public.work_orders w
    left join public.complaints c on c.id = w.complaint_id
    left join public.skills     s on s.id = w.skill_id
    where w.department_id = p_department_id
      and w.status not in ('completed', 'cancelled', 'failed')
  )
  select
    coalesce((
      select jsonb_agg(to_jsonb(sec) order by sec.created_at desc)
        from (select cr.* from complaint_rows cr
               where cr.status = 'open' and cr.taken_up_at is null
                 and cr.live_work_order_count = 0) sec
    ), '[]'::jsonb),
    coalesce((
      select jsonb_agg(to_jsonb(sec) order by sec.created_at desc)
        from (select cr.* from complaint_rows cr
               where cr.taken_up_at is not null
                 and cr.live_work_order_count = 0) sec
    ), '[]'::jsonb),
    coalesce((
      select jsonb_agg(to_jsonb(sec) order by sec.created_at desc)
        from (select wr.* from work_order_rows wr
               where not wr.committed
                 and wr.status = 'awaiting_resident') sec
    ), '[]'::jsonb),
    coalesce((
      select jsonb_agg(to_jsonb(sec) order by sec.created_at desc)
        from (select wr.* from work_order_rows wr
               where not wr.committed
                 and wr.status in ('draft', 'offered')) sec
    ), '[]'::jsonb),
    coalesce((
      select jsonb_agg(to_jsonb(sec) order by sec.created_at desc)
        from (select wr.* from work_order_rows wr
               where wr.committed and wr.status <> 'in_progress') sec
    ), '[]'::jsonb),
    coalesce((
      select jsonb_agg(to_jsonb(sec) order by sec.created_at desc)
        from (select wr.* from work_order_rows wr
               where wr.status = 'in_progress') sec
    ), '[]'::jsonb)
  into v_new, v_taken, v_awaiting, v_open, v_pending, v_progress;

  return jsonb_build_object(
    'department_id',      p_department_id,
    'new_complaints',     v_new,
    'taken_up',           v_taken,
    'awaiting_resident',  v_awaiting,
    'open_requests',      v_open,
    'assigned_pending',   v_pending,
    'in_progress',        v_progress
  );
end;
$$;

comment on function public.supervisor_triage_snapshot(uuid) is
  'The supervisor dashboard''s six sections in one read: new complaints, taken up, awaiting the resident''s chosen time, open job requests nobody has accepted, assigned and waiting, and being worked right now. A read — it moves nothing and notifies nobody.';


-- ---------------------------------------------------------------------------
-- 9. Grants
--
-- Each function's existing audience, restated. The dispatch internals are
-- revoked from everybody: they expose roster data and bypass request-level role
-- checks, so only definer callers reach them -- the posture `0037` §8 and
-- `20260823120000` both take, and `fire_dispatch_task` (already granted to
-- `service_role` by `0037`) is the only door the Python dispatcher uses.
-- `resident_set_work_order_schedule` is `authenticated`, like every other
-- function a person calls: it resolves the caller from `auth.uid()` and refuses
-- a stranger itself.
--
-- The redefinitions below keep the ACLs `create or replace` preserves; they are
-- restated anyway, because an ACL nobody can see in the file is an ACL nobody
-- checks.
-- ---------------------------------------------------------------------------

revoke all on function public.dispatch_candidates_at(
  uuid, timestamptz, timestamptz, integer, boolean)
  from public, anon, authenticated;
revoke all on function public.find_first_available_slot(uuid, timestamptz)
  from public, anon, authenticated;
revoke all on function public.dispatch_facility_auto_assign(uuid)
  from public, anon, authenticated;
revoke all on function public.dispatch_candidates(uuid, integer, boolean)
  from public, anon, authenticated;
revoke all on function public.dispatch_resident_timeout(uuid)
  from public, anon, authenticated;
revoke all on function public.sync_dispatch_tasks()
  from public, anon, authenticated;
revoke all on function public.fire_dispatch_task(uuid)
  from public, anon, authenticated;
grant execute on function public.fire_dispatch_task(uuid) to service_role;

revoke all on function public.resident_set_work_order_schedule(
  uuid, timestamptz, timestamptz)
  from public, anon, authenticated;
grant execute on function public.resident_set_work_order_schedule(
  uuid, timestamptz, timestamptz) to authenticated;

grant execute on function public.create_work_order(
  uuid, uuid, uuid, text, text, timestamptz, timestamptz, text) to authenticated;
grant execute on function public.supervisor_triage_snapshot(uuid) to authenticated;

-- New functions and a new overload change the PostgREST function catalogue.
-- Refresh it immediately instead of waiting for the schema-cache polling
-- interval.
notify pgrst, 'reload schema';


-- ---------------------------------------------------------------------------
-- 10. Prove it, in the same transaction
--
-- `20260823120000` and `20260823170000`'s shape: declarations by
-- `to_regprocedure`, and each redefinition proved to be the one the database
-- now holds by looking for a string only this file's body contains. A
-- `create or replace` that lost an arm is the failure with no symptom.
-- ---------------------------------------------------------------------------

do $$
begin
  if to_regprocedure(
    'public.dispatch_candidates_at(uuid,timestamptz,timestamptz,integer,boolean)'
  ) is null then
    raise exception 'dispatch_candidates_at missing';
  end if;
  if to_regprocedure('public.find_first_available_slot(uuid,timestamptz)') is null then
    raise exception 'find_first_available_slot missing';
  end if;
  if to_regprocedure(
    'public.resident_set_work_order_schedule(uuid,timestamptz,timestamptz)'
  ) is null then
    raise exception 'resident_set_work_order_schedule missing';
  end if;
  if to_regprocedure('public.dispatch_facility_auto_assign(uuid)') is null then
    raise exception 'dispatch_facility_auto_assign missing';
  end if;

  -- The two older dispatch_candidates entry points survive untouched.
  if to_regprocedure('public.dispatch_candidates(uuid,integer,boolean)') is null
     or to_regprocedure('public.dispatch_candidates(uuid,integer)') is null then
    raise exception 'a dispatch_candidates entry point was lost';
  end if;
  if position(
    'dispatch_candidates_at'
    in pg_get_functiondef('public.dispatch_candidates(uuid,integer,boolean)'::regprocedure)
  ) = 0 then
    raise exception 'the three-argument dispatch_candidates is not the delegate';
  end if;

  -- Each redefinition is the live one.
  if position(
    '''mode'', v_mode'
    in pg_get_functiondef(
      'public.create_work_order(uuid,uuid,uuid,text,text,timestamptz,timestamptz,text)'::regprocedure)
  ) = 0 then
    raise exception 'create_work_order is not the pick-mode version';
  end if;
  if position(
    'find_first_available_slot'
    in pg_get_functiondef('public.dispatch_resident_timeout(uuid)'::regprocedure)
  ) = 0 then
    raise exception 'dispatch_resident_timeout does not branch on the null slot';
  end if;

  -- The trigger keeps every arm it had, and gains one.
  if position(
    '''facility_auto_assign'''
    in pg_get_functiondef('public.sync_dispatch_tasks()'::regprocedure)
  ) = 0
    or position(
    '''resident_timeout'''
    in pg_get_functiondef('public.sync_dispatch_tasks()'::regprocedure)
  ) = 0
    or position(
    '(case when new.priority = ''high'' then 2 else 0 end)::smallint'
    in pg_get_functiondef('public.sync_dispatch_tasks()'::regprocedure)
  ) = 0 then
    raise exception 'sync_dispatch_tasks lost an arm in the redefinition';
  end if;

  if position(
    'when ''facility_auto_assign'''
    in pg_get_functiondef('public.fire_dispatch_task(uuid)'::regprocedure)
  ) = 0
    or position(
    'when ''auto_close'''
    in pg_get_functiondef('public.fire_dispatch_task(uuid)'::regprocedure)
  ) = 0 then
    raise exception 'fire_dispatch_task lost an arm in the redefinition';
  end if;

  if position(
    '''awaiting_resident'',  v_awaiting'
    in pg_get_functiondef('public.supervisor_triage_snapshot(uuid)'::regprocedure)
  ) = 0 then
    raise exception 'the triage snapshot has no awaiting-resident bucket';
  end if;

  -- The one widened constraint accepts the new kind.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.dispatch_tasks'::regclass
       and conname  = 'dispatch_tasks_kind_check'
       and pg_get_constraintdef(oid) like '%facility_auto_assign%'
  ) then
    raise exception 'dispatch_tasks_kind_check does not allow facility_auto_assign';
  end if;

  raise notice
    'resident_sets_the_time: pick-mode, the slot finder, the facility gate and the sixth bucket are in place.';
end;
$$;


-- ---------------------------------------------------------------------------
-- 11. Post-apply checks
--
-- Run these in the SQL Editor after this file. Nothing below runs as part of
-- the migration; the block in section 10 is the only thing that executes. They
-- are reproduced in `docs/plans/MIGRATION_APPLY_RUNBOOK.md` §28.
--
--   -- (a) Six sections, and the new key among them. Inspect the body rather
--   -- than calling the function: the SQL editor has no auth.uid() (the guard
--   -- would HB403), and hosted departments carry kind NULL, so the older
--   -- `where kind = 'service'` helper finds no department and draws HB404.
--   select pg_get_functiondef(
--            'public.supervisor_triage_snapshot(uuid)'::regprocedure)
--          like '%''awaiting_resident'', v_awaiting%' as has_sixth_bucket;
--   -- expect: one row, true.
--
--   -- (b) The four new functions, all SECURITY DEFINER.
--   select p.oid::regprocedure as signature, p.prosecdef as security_definer
--     from pg_proc p join pg_namespace n on n.oid = p.pronamespace
--    where n.nspname = 'public'
--      and p.proname in ('dispatch_candidates_at', 'find_first_available_slot',
--                        'resident_set_work_order_schedule',
--                        'dispatch_facility_auto_assign')
--    order by 1;
--
--   -- (c) No task has an unknown kind, and the constraint knows the new one.
--   select pg_get_constraintdef(oid) like '%facility_auto_assign%' as knows_it
--     from pg_constraint
--    where conrelid = 'public.dispatch_tasks'::regclass
--      and conname  = 'dispatch_tasks_kind_check';
-- ---------------------------------------------------------------------------
