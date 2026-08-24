-- ---------------------------------------------------------------------------
-- 20260823190000_assignment_write_repairs.sql
--
-- Two defects reported from the same modal, and one that had not fired yet.
--
-- On 2026-08-23 the product owner force-assigned a tap-leak job from the
-- supervisor's "Assign this job outright" modal. The candidate list offered the
-- department's SUPERVISOR and MANAGER alongside its two technicians, and every
-- `POST /work-orders/{id}/assign` answered 422. The server-side log behind that
-- 422, through `app/core/pg_errors.py`:
--
--     SQLSTATE 23502: null value in column "assigned_by_membership_id" of
--     relation "work_order_assignments" violates not-null constraint
--
-- The frozen spec is `docs/plans/ASSIGNMENT_ELIGIBILITY_AND_DRIFT_SPEC.md`; the
-- section markers below cite its rulings R1-R5 rather than restating them.
--
-- WHY THE 422 IS DRIFT AND NOT A MISSING RESOLVER (R4)
--
-- No repository migration has ever declared `assigned_by_membership_id`.
-- `work_order_assignments` is declared in exactly three places --
-- `0001_baseline.sql`:74 (five columns), `0036_work_orders.sql`:264-272 (eight
-- `add column if not exists`) and `20260813101000`:4 (`is_forced`) -- and the
-- column is in none of them. So all ELEVEN insert sites in this repository
-- rightly write no such value: force-assign (`20260822170000`:934), the offer
-- (`20260813101000`:88), the board claim (`20260823170000`:288), the ping and
-- auto-assign handlers (`20260812120000`:122, :231), the dispatch force
-- (`20260823120000`:421), and the two 2026-08-23 auto-assign handlers
-- (`20260823180000`:806, :992). On the hosted database EVERY write path into
-- this table is broken -- including the two handlers that have never fired,
-- which would crash, retry five times and retire their task dead.
--
-- The story is `20260822090000_hosted_work_order_column_drift.sql`'s, one table
-- along: the linked project is not a `0001_baseline.sql` project, its
-- `work_order_assignments` is the pre-baseline hand-built table, and every
-- migration since extends it with `add column if not exists` -- which applied
-- cleanly around the legacy columns until an insert met the one that is NOT
-- NULL with no default. The fix is that file's fix: a widening sweep. Encoding
-- a hosted-only legacy column into eleven call sites would be drift in the
-- other direction -- this repository's actor model is
-- `complaint_events.actor_membership_id` via `my_membership_in()`.
--
-- WHY LEADERSHIP WAS IN THE PICKER (R1, R2)
--
-- Because nothing anywhere asked. `dispatch_candidates_at`
-- (`20260823180000`:110-267) is the single eligibility implementation behind
-- the picker, `find_first_available_slot`, `dispatch_resident_timeout`,
-- `dispatch_facility_auto_assign`, `dispatch_ping_candidates`,
-- `dispatch_auto_assign` and `dispatch_force_assign`, and its roster join
-- carried no `sa.rank` clause. `staff_assignments.rank` is
-- `manager | supervisor | member` (`0035`:106-108); marketplace hires get
-- `member`, leadership gets `manager`/`supervisor` through an invitation claim
-- and carries no `service_provider_id` -- so the trade gate short-circuits open
-- for them as well. The ordering is `load asc`, which sorts an idle supervisor
-- FIRST for the auto-book. The board had the same hole twice
-- (`20260823170000`:128-131 and :221-233): a supervisor could see, and take,
-- their own department's open work.
--
-- The product owner's ruling (R1, verbatim): "its only asigned to the workers
-- who are hired from the service men pool". So the clause is `sa.rank =
-- 'member'`, in the three places that decide who may hold a job -- and strict
-- (R3): a NULL rank, or a rank this repository does not declare, is excluded
-- rather than admitted, with a runbook pre-check (§29) so a legacy roster row
-- losing eligibility is caught by eyes rather than by silence.
--
-- WHAT THIS IS NOT
--
-- No new function, no new signature, no new status word, no new event word, no
-- dispatch-task kind, no API or frontend change. Sections 2-4 are their
-- predecessors' bodies VERBATIM plus the one clause -- comments, ordering,
-- return tables and grants unchanged. Section 1 only ever widens: no row the
-- hosted table accepted before is rejected after, and on a database built from
-- `0001_baseline.sql` it finds nothing and says so. Re-running the whole file
-- is a no-op. One transaction (R5): the SQL editor wraps the paste, so a
-- failure anywhere rolls back everything.
--
-- ROLLBACK:
--   * section 1: `alter table public.work_order_assignments alter column
--     <name> set not null;` per column named in this file's NOTICEs, and only
--     while every row still has a value in it.
--   * sections 2-4: re-apply `20260823180000_resident_sets_the_time.sql`
--     section 2 and `20260823170000_open_jobs_board.sql` sections 1-2, which
--     are these bodies without the clause.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. The drift sweep (R4)
--
-- `20260822090000` §1's shape, one table along: walk the catalogue, and drop
-- NOT NULL on every `work_order_assignments` column that (a) the repository has
-- never declared, (b) is NOT NULL on the hosted table, and (c) has no default
-- -- i.e. exactly the set that can reject an insert written against the
-- repository's schema. A sweep and not `assigned_by_membership_id` alone,
-- because `20260820120000` §3 taught the lesson that these constraints bite one
-- behind the other: the log row that carried the 422 also showed a legacy
-- status-ish column defaulting to 'assigned', which HAS a default and is
-- therefore correctly left alone here. Legacy columns that are nullable, or
-- NOT NULL with a default, block nothing.
--
-- The protected list is the repository's full declaration of the table:
-- `0001_baseline.sql`:74 (id, work_order_id, staff_assignment_id, assigned_at,
-- ended_at), `0036_work_orders.sql`:264-272 (status, offered_at, responded_at,
-- decline_reason, is_auto_assigned, scheduled_start_at, scheduled_end_at, and
-- ended_at again) and `20260813101000_offer_consent_and_force.sql`:4
-- (is_forced). `tests/test_assignment_write_repairs_migration.py` derives the
-- same list from those three files' own text and fails if this one ever
-- disagrees with them -- a repository column wrongly missing from the list
-- would have its NOT NULL silently dropped on the hosted table.
--
-- `pg_attribute` rather than `information_schema.columns`: the view filters by
-- the reading role's privileges, and this file is pasted by a person into an
-- editor whose role nobody in this repository chose.
-- ---------------------------------------------------------------------------
do $$
declare
  v_column  record;
  v_dropped integer := 0;
begin
  for v_column in
    select a.attname as column_name
      from pg_attribute a
     where a.attrelid = 'public.work_order_assignments'::regclass
       and a.attnum > 0
       and not a.attisdropped
       and a.attnotnull
       and not a.atthasdef
       and a.attname not in (
         'id', 'work_order_id', 'staff_assignment_id', 'assigned_at',
         'ended_at',
         'status', 'offered_at', 'responded_at', 'decline_reason',
         'is_auto_assigned', 'scheduled_start_at', 'scheduled_end_at',
         'is_forced'
       )
     order by a.attname
  loop
    execute format(
      'alter table public.work_order_assignments alter column %I drop not null',
      v_column.column_name
    );
    v_dropped := v_dropped + 1;
    raise notice 'work_order_assignments.% was a legacy NOT NULL column; '
      'now nullable', v_column.column_name;
  end loop;

  if v_dropped = 0 then
    raise notice 'no legacy NOT NULL columns found on work_order_assignments '
      '-- either already applied, or this is a baseline-built database';
  end if;
end $$;

-- Verification, in the same transaction as the change. `20260822090000` §2's
-- shape: if the file claims to have fixed something, it fails rather than
-- reporting success.
do $$
declare
  v_leftover text;
begin
  select string_agg(a.attname, ', ' order by a.attname)
    into v_leftover
    from pg_attribute a
   where a.attrelid = 'public.work_order_assignments'::regclass
     and a.attnum > 0
     and not a.attisdropped
     and a.attnotnull
     and not a.atthasdef
     and a.attname not in (
       'id', 'work_order_id', 'staff_assignment_id', 'assigned_at',
       'ended_at',
       'status', 'offered_at', 'responded_at', 'decline_reason',
       'is_auto_assigned', 'scheduled_start_at', 'scheduled_end_at',
       'is_forced'
     );

  if v_leftover is not null then
    raise exception 'work_order_assignments still carries insert-blocking '
      'legacy NOT NULL columns: %', v_leftover;
  end if;
end $$;


-- ---------------------------------------------------------------------------
-- 2. Eligibility learns the rank (R1, R3)
--
-- `20260823180000` §2's body, VERBATIM, with one clause added to the roster
-- join and a comment saying why. Signature, return table, ordering, the
-- hypothetical-hour parameters, the null-slot guard, the trade short-circuit
-- and the `comment on function` are all untouched: this is the ONE
-- implementation, and the three-argument `dispatch_candidates`,
-- `find_first_available_slot` and every dispatch handler read it through
-- delegates that need no change at all.
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
    -- R1 (product owner, 2026-08-23): a job is only ever assigned to a
    -- worker hired from the servicemen pool. Marketplace hires land on the
    -- roster as rank `member`; managers and supervisors are invited, and
    -- carry no service_provider_id -- so the trade clause below
    -- short-circuits open for them and they sorted FIRST on `load asc`.
    -- R3: the clause is strict equality. A NULL rank, and any rank this
    -- repository has not declared, is excluded rather than admitted.
    join public.staff_assignments sa
      on sa.department_id = j.department_id
     and sa.status = 'active'
     and sa.is_active
     and sa.membership_id is not null
     and sa.rank = 'member'
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

-- ---------------------------------------------------------------------------
-- 3. The board stops showing leadership the pile (R2)
--
-- `20260823170000` §1's body, VERBATIM, with the same clause on the same
-- roster join. R2 closes the board door because taking a job off the board is
-- assignment by another door; supervisors keep their own triage dashboard,
-- which is where their view of this work belongs.
-- ---------------------------------------------------------------------------

create or replace function public.worker_open_jobs()
returns table (
  work_order_id       uuid,
  complaint_id        uuid,
  complaint_title     text,
  department_id       uuid,
  department_name     text,
  community_id        uuid,
  community_name      text,
  skill_id            uuid,
  skill_name          text,
  priority            text,
  subject_kind        text,
  scheduled_start_at  timestamptz,
  scheduled_end_at    timestamptz,
  created_at          timestamptz,
  staff_assignment_id uuid
)
language sql
stable
security definer
set search_path = public
as $$
  select
    w.id                 as work_order_id,
    w.complaint_id,
    c.title              as complaint_title,
    w.department_id,
    d.name               as department_name,
    w.community_id,
    co.name              as community_name,
    w.skill_id,
    sk.name              as skill_name,
    w.priority,
    w.subject_kind,
    w.scheduled_start_at,
    w.scheduled_end_at,
    w.created_at,
    sa.id                as staff_assignment_id
  from public.work_orders w
  -- R1/R2: taking a job off the board is assignment by another door, so
  -- the board obeys the same rule -- only the marketplace-hired members
  -- of the roster are shown the pile. R3: strict, so a NULL rank is out.
  join public.staff_assignments sa
    on sa.department_id = w.department_id
   and sa.status = 'active'
   and sa.is_active
   and sa.rank = 'member'
  left join public.community_memberships m  on m.id  = sa.membership_id
  left join public.service_providers sp     on sp.id = sa.service_provider_id
  left join public.complaints c             on c.id  = w.complaint_id
  left join public.departments d            on d.id  = w.department_id
  left join public.communities co           on co.id = w.community_id
  left join public.skills sk                on sk.id = w.skill_id
  where (m.profile_id = auth.uid() or sp.profile_id = auth.uid())
    -- D1: uncommitted and unpromised.
    and w.status in ('draft', 'offered')
    and not exists (
      select 1
        from public.work_order_assignments a
       where a.work_order_id = w.id
         and a.status in ('offered', 'accepted')
    )
    -- D2: the engine's own trade clause, short-circuit included.
    and (
      w.skill_id is null
      or sa.service_provider_id is null
      or exists (
        select 1
          from public.service_provider_skills ps
         where ps.service_provider_id = sa.service_provider_id
           and ps.skill_id = w.skill_id
      )
    )
    -- D7: not actionable for the excluded is not shown to the excluded.
    and not exists (
      select 1
        from public.complaint_excluded_staff(w.complaint_id) e
       where e.staff_assignment_id = sa.id
    )
  order by w.scheduled_start_at asc nulls last, w.created_at desc;
$$;

comment on function public.worker_open_jobs() is
  'The open-jobs board (C1): every uncommitted, unpromised job (D1) in every '
  'department where the caller holds an active roster row, filtered by the '
  'dispatch engine''s own trade rule (D2) and the complaint''s exclusion '
  'history (D7). SECURITY DEFINER because RLS correctly hides unheld jobs '
  'from workers; identity is auth.uid() alone.';

-- ---------------------------------------------------------------------------
-- 4. And refuses a leadership claim in words (R2)
--
-- `20260823170000` §2's body, VERBATIM, with the clause on the roster re-check
-- and one branch under it. The re-check is what a deep-linked claim meets when
-- the board never showed the job, so it is where the rank guard belongs; the
-- branch exists because a supervisor genuinely IS on the roster, and answering
-- them "you are not on this department's roster" would be a lie told to the one
-- person able to check it. HB403 for both, the code this function already
-- answers its roster and trade refusals with -- no new numbering.
-- ---------------------------------------------------------------------------

create or replace function public.claim_open_work_order(p_work_order_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order      public.work_orders%rowtype;
  v_staff      public.staff_assignments%rowtype;
  v_complaint  public.complaints%rowtype;
  v_actor      uuid;
  v_id         uuid;
begin
  -- The whole race is settled on this line. See the header.
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  -- D1, re-checked under the lock: open means uncommitted and unpromised.
  if v_order.status not in ('draft', 'offered') or exists (
    select 1
      from public.work_order_assignments a
     where a.work_order_id = v_order.id
       and a.status in ('offered', 'accepted')
  ) then
    raise exception 'Somebody has already taken this job.' using errcode = 'HB409';
  end if;

  -- C1: hiring remains the gate to a department's work. The board never
  -- showed this job to an outsider; a deep-linked claim is refused in words.
  select sa.* into v_staff
    from public.staff_assignments sa
    left join public.community_memberships m  on m.id  = sa.membership_id
    left join public.service_providers sp     on sp.id = sa.service_provider_id
   where sa.department_id = v_order.department_id
     and sa.status = 'active'
     and sa.is_active
     and sa.rank = 'member'
     and (m.profile_id = auth.uid() or sp.profile_id = auth.uid())
   limit 1;
  if not found then
    -- R2: a supervisor DOES hold a roster row, so the refusal above would be
    -- a lie told to the one person who can check it. Claiming off the board is
    -- assignment by another door, and R1 closes that door too -- so leadership
    -- is told which door it is. HB403, the code this function already answers
    -- both of its other you-may-not-have-this-job refusals with.
    if exists (
      select 1
        from public.staff_assignments sa
        left join public.community_memberships m  on m.id  = sa.membership_id
        left join public.service_providers sp     on sp.id = sa.service_provider_id
       where sa.department_id = v_order.department_id
         and sa.status = 'active'
         and sa.is_active
         and sa.rank is distinct from 'member'
         and (m.profile_id = auth.uid() or sp.profile_id = auth.uid())
    ) then
      raise exception 'Supervisors and managers cannot take up jobs from the board.'
        using errcode = 'HB403';
    end if;
    raise exception 'You are not on this department''s roster.'
      using errcode = 'HB403';
  end if;

  -- D2: the engine's own trade clause, verbatim -- short-circuit included.
  if not (
    v_order.skill_id is null
    or v_staff.service_provider_id is null
    or exists (
      select 1
        from public.service_provider_skills ps
       where ps.service_provider_id = v_staff.service_provider_id
         and ps.skill_id = v_order.skill_id
    )
  ) then
    raise exception 'This job needs a trade you have not listed.'
      using errcode = 'HB403';
  end if;

  -- D2/D7: the complaint's history rules some people out -- a decline on this
  -- complaint, a resident cancellation, a reopen after their completed visit.
  if exists (
    select 1
      from public.complaint_excluded_staff(v_order.complaint_id) e
     where e.staff_assignment_id = v_staff.id
  ) then
    raise exception 'This complaint''s history rules you out of this job.'
      using errcode = 'HB409';
  end if;

  -- The slot-dependent check, only when there is a slot (C3). Named here so
  -- the worker is told which of their own bookings is in the way, rather
  -- than reading a 23P01 about an exclusion constraint.
  if v_order.scheduled_start_at is not null and exists (
    select 1
      from public.work_order_assignments busy
     where busy.staff_assignment_id = v_staff.id
       and busy.status = 'accepted'
       and busy.work_order_id <> v_order.id
       and busy.scheduled_start_at is not null
       and tstzrange(busy.scheduled_start_at, busy.scheduled_end_at, '[)')
           && tstzrange(v_order.scheduled_start_at, v_order.scheduled_end_at, '[)')
  ) then
    raise exception 'You are already booked during that time.'
      using errcode = 'HB409';
  end if;

  -- Defensive: D1 means there are no offered rows, but the lock window is
  -- real -- an offer inserted between the board read and this lock is
  -- withdrawn, not deleted, for the reason `0036` §6 and `0037` §5 gave.
  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = v_order.id
     and status = 'offered';

  -- D3: the accept path's exact row shape. `offered_at = responded_at`: the
  -- worker asked themselves and answered in the same breath.
  insert into public.work_order_assignments (
    work_order_id, staff_assignment_id, status, is_forced, is_auto_assigned,
    offered_at, responded_at, scheduled_start_at, scheduled_end_at)
  values (
    v_order.id, v_staff.id, 'accepted', false, false,
    now(), now(), v_order.scheduled_start_at, v_order.scheduled_end_at)
  returning id into v_id;

  -- `scheduled` even with a null slot: `force_assign_work_order` already
  -- writes that shape, and the queue's set-a-time control is the way out.
  update public.work_orders
     set status = 'scheduled', updated_at = now()
   where id = v_order.id;

  v_actor := public.my_membership_in(v_order.community_id);
  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  -- D4: `job_assigned`, the accept path's own word -- from the resident's
  -- side the fact is the same fact: somebody is now coming, and their name is
  -- this. `claimed: true` carries the distinction without a new word.
  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_actor, 'job_assigned',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assignmentId', v_id,
      'assigneeName', v_staff.display_name,
      'startsAt', v_order.scheduled_start_at,
      'endsAt', v_order.scheduled_end_at,
      'accepted', true,
      'claimed', true)
  );

  -- D6, first audience: the raising resident, exactly as on accept.
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

  -- D6, second audience: the supervisor was NOT asking a question this time,
  -- so the kind is `work_order.claimed` rather than `.accepted` -- a fact
  -- arriving unprompted reads differently from an answer. `notifications.kind`
  -- is unconstrained by design (`0030` §2), so no schema or renderer change.
  -- Skipped when the claimer IS that supervisor, which a small department
  -- makes entirely possible.
  if v_order.supervisor_membership_id is not null
     and v_order.supervisor_membership_id is distinct from v_actor then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.claimed',
      jsonb_build_object(
        'title', v_staff.display_name || ' took up '
                 || coalesce(v_complaint.title, 'a job'),
        'body', v_staff.display_name,
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_order.scheduled_start_at));
  end if;

  return v_id;
end;
$$;

comment on function public.claim_open_work_order(uuid) is
  'The board''s instant claim (C2): accept-an-offer mechanics without the '
  'offer -- row lock, D1 open check, roster + trade + exclusion guards, the '
  'slot-overlap refusal only when a slot exists (C3), an accepted assignment '
  'in the accept path''s exact shape, job_assigned with claimed: true, and '
  'the supervisor told with work_order.claimed. First come, first served.';

-- The audiences are exactly what they were: `create or replace` preserves the
-- ACLs, and they are restated anyway, because an ACL nobody can see in the file
-- is an ACL nobody checks. `dispatch_candidates_at` stays a definer-only
-- internal (`0037` §8's posture); the two board verbs stay `authenticated`,
-- deciding eligibility themselves from `auth.uid()`.
revoke all on function public.dispatch_candidates_at(
  uuid, timestamptz, timestamptz, integer, boolean)
  from public, anon, authenticated;

revoke all on function public.worker_open_jobs()
  from public, anon, authenticated;
grant execute on function public.worker_open_jobs() to authenticated;

revoke all on function public.claim_open_work_order(uuid)
  from public, anon, authenticated;
grant execute on function public.claim_open_work_order(uuid) to authenticated;

-- No signature changed, so PostgREST's catalogue has not moved -- the reload is
-- here for the same reason the grants are: the files that re-issue these
-- functions all end this way, and a habit with an exception is not a habit.
notify pgrst, 'reload schema';

-- Prove it, in the same transaction. `20260823170000` §5 and `20260823180000`
-- §10's shape: each redefinition proved to be the one the database now holds by
-- looking for a string only this file's body contains. A `create or replace`
-- that silently lost the clause is the failure with no symptom -- it looks
-- exactly like a successful apply and leaves the supervisor in the picker.
do $$
begin
  if to_regprocedure(
    'public.dispatch_candidates_at(uuid,timestamptz,timestamptz,integer,boolean)'
  ) is null then
    raise exception 'dispatch_candidates_at missing';
  end if;
  if to_regprocedure('public.worker_open_jobs()') is null then
    raise exception 'worker_open_jobs missing';
  end if;
  if to_regprocedure('public.claim_open_work_order(uuid)') is null then
    raise exception 'claim_open_work_order missing';
  end if;

  if position(
    'sa.rank = ''member'''
    in pg_get_functiondef(
      'public.dispatch_candidates_at(uuid,timestamptz,timestamptz,integer,boolean)'::regprocedure)
  ) = 0 then
    raise exception 'dispatch_candidates_at did not take the rank clause';
  end if;
  if position(
    'sa.rank = ''member'''
    in pg_get_functiondef('public.worker_open_jobs()'::regprocedure)
  ) = 0 then
    raise exception 'worker_open_jobs did not take the rank clause';
  end if;
  if position(
    'sa.rank = ''member'''
    in pg_get_functiondef('public.claim_open_work_order(uuid)'::regprocedure)
  ) = 0 then
    raise exception 'claim_open_work_order did not take the rank clause';
  end if;

  -- The delegate is still the delegate: nothing here re-implemented
  -- eligibility, so the three-argument entry point must still be one line of
  -- pass-through to the body section 2 just rewrote.
  if position(
    'dispatch_candidates_at'
    in pg_get_functiondef('public.dispatch_candidates(uuid,integer,boolean)'::regprocedure)
  ) = 0 then
    raise exception 'the three-argument dispatch_candidates is no longer the delegate';
  end if;
end $$;


-- ---------------------------------------------------------------------------
-- 5. Post-checks, to be run AFTER the transaction commits
--
-- Comment-only on purpose: these belong in the SQL editor's next tab, not in
-- the apply. Every one is a GUARD-FREE structural inspection -- no `auth.uid()`
-- (the editor has none, so any definer verb that resolves a caller answers
-- HB403) and no `kind = 'service'` helper (this deployment's departments carry
-- kind NULL). Both bit us in runbook §28. Runbook §29 carries them too.
--
--   -- (a) The clause is in all three of the functions that decide who may
--   --     hold a job. Expect three rows, `has_rank_clause` true on each.
--   select p.oid::regprocedure as signature,
--          pg_get_functiondef(p.oid) like '%sa.rank = ''member''%'
--            as has_rank_clause
--     from pg_proc p
--     join pg_namespace n on n.oid = p.pronamespace
--    where n.nspname = 'public'
--      and (p.proname in ('worker_open_jobs', 'claim_open_work_order')
--           or p.oid::regprocedure::text like 'dispatch_candidates_at(%')
--    order by 1;
--
--   -- (b) The column that answered every assign with a 422 is nullable now.
--   --     Expect one row, `attnotnull` false -- or NO row at all, which is
--   --     what a database built from 0001_baseline.sql looks like and is
--   --     equally correct.
--   select a.attname, a.attnotnull, a.atthasdef
--     from pg_attribute a
--    where a.attrelid = 'public.work_order_assignments'::regclass
--      and a.attname  = 'assigned_by_membership_id';
--
--   -- (c) And nothing insert-blocking is left behind it. Expect zero rows.
--   select a.attname
--     from pg_attribute a
--    where a.attrelid = 'public.work_order_assignments'::regclass
--      and a.attnum > 0
--      and not a.attisdropped
--      and a.attnotnull
--      and not a.atthasdef
--      and a.attname not in (
--        'id', 'work_order_id', 'staff_assignment_id', 'assigned_at',
--        'ended_at', 'status', 'offered_at', 'responded_at', 'decline_reason',
--        'is_auto_assigned', 'scheduled_start_at', 'scheduled_end_at',
--        'is_forced')
--    order by a.attname;
-- ---------------------------------------------------------------------------
