-- ---------------------------------------------------------------------------
-- 20260823170000_open_jobs_board.sql
--
-- The open-jobs board: workers get eyes, and hands.
--
-- Live testing surfaced the gap from the worker's side of the counter: a
-- freshly hired plumber opened their portal and saw nothing, because in the
-- model on record a worker sees only what a supervisor has offered them. The
-- product owner ruled on 2026-08-23 that this changes
-- (`docs/COMPLAINT_ENGINE_HANDOFF.md` §22): department roster technicians who
-- hold the job's trade see an open-jobs board for their department (C1),
-- taking a job from it is an instant claim with accept-an-offer mechanics,
-- supervisor notified, first come first served (C2), and unscheduled jobs are
-- on the board with the slot checks deferred (C3). The orchestrator's
-- adjudications D1-D7 are logged in `docs/plans/OPEN_JOBS_BOARD_SPEC.md`; the
-- section markers below cite them rather than restating them.
--
-- WHY TWO NEW FUNCTIONS RATHER THAN A POLICY AND A REUSED RPC
--
--   * The read cannot be a view over `work_orders`: `work_orders_read` is
--     `can_read_work_order` (`0036` §4), and a technician holding no
--     assignment on a job cannot select it at all. A board of jobs nobody
--     holds yet is, by definition, invisible to everybody it is for -- so the
--     read is a SECURITY DEFINER function that decides eligibility itself.
--   * The claim cannot be `accept_work_order_offer` (`20260812120000` §2):
--     that function requires an existing `offered` assignment for the caller,
--     `work_orders.status = 'offered'`, and a non-null slot. All three fail
--     for a board claim -- a C3 job is `draft` with no slot and no assignment
--     rows at all. The claim below copies its shapes -- the row lock first,
--     the overlap refusal in words, the withdrawn-not-deleted sweep, the
--     `job_assigned` event, the same two notifications -- minus the demands
--     that only make sense once an offer exists.
--
-- WHAT "OPEN" MEANS (D1)
--
-- A job is on the board iff `status in ('draft', 'offered')` AND it has no
-- live assignment (no `work_order_assignments` row in `offered` or
-- `accepted`). A job with an offer out to somebody else is OFF the board: the
-- supervisor has an intention in flight, and a decline returns it.
-- `awaiting_resident` is off (a consent flow is in flight); `failed` is off
-- in v1 (it has its own escalation task). Status alone cannot define open --
-- `create_work_order` sets `status = 'offered'` on a scheduled facility job
-- with no assignment rows at all (`0036` §6) -- which is why both halves of
-- the predicate appear in both functions.
--
-- THE ONE ENGINE LIFECYCLE CHANGE (D5)
--
-- On the offer path the complaint moved `open -> acknowledged` when the offer
-- was INSERTed (`20260813102000`'s projection trigger fires on INSERT only
-- `when (new.status = 'offered')`). A claim inserts `accepted` directly, so
-- without a change the complaint would sit at `open` with a committed job --
-- violating C2's "the same status movements". Section 3 widens the trigger to
-- `('offered', 'accepted')` and teaches the body to treat an accepted insert
-- as at-least-acknowledged. This knowingly also closes the identical
-- pre-existing hole in `force_assign_work_order` and `dispatch_force_assign`,
-- and is flagged to the product owner as an engine lifecycle change made
-- under C2's authority.
--
-- WHAT THIS FILE DOES NOT DO, AND WHY
--
--   * **No new event word.** The claim writes `job_assigned` -- the accept
--     path's own word -- with `claimed: true` in the payload. A new word
--     costs a `complaint_events_type_check` drop-and-recreate (runbook §19
--     rule); the payload carries the distinction without it (D4).
--   * **No trade notion for provider-less roster rows.** The trade rule below
--     is `dispatch_candidates`' clause verbatim (`20260823120000`), including
--     its short-circuit for roster rows with no `service_provider_id`.
--     Inventing a different rule here would fork eligibility (D2).
--   * **No change to the supervisor's offer or force-assign paths.** §22's own
--     boundary. The board is new read+claim surface only.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- 1. The board (C1, D1, D2, D7)
--
-- No arguments: identity is `auth.uid()`, so there is nothing a caller could
-- send that would widen what comes back. One row per open job per active
-- roster row the caller holds in its department, trade-filtered by the
-- engine's own clause, and exclusion-aware -- a worker the complaint's
-- history rules out does not see a job they cannot take (D7); the claim
-- re-checks it anyway, because the list and the click are seconds apart.
--
-- `staff_assignment_id` is the caller's own roster row for that department,
-- returned so the frontend never has to guess which of a multi-community
-- worker's rows a claim would ride on.
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
  join public.staff_assignments sa
    on sa.department_id = w.department_id
   and sa.status = 'active'
   and sa.is_active
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
-- 2. The claim (C2, C3, D2, D3, D4, D6)
--
-- `accept_work_order_offer` minus the demands that assume an offer exists.
-- The whole race is settled on the `for update` line, exactly as it is there:
-- the second claimer waits, re-reads a job that now holds a live assignment,
-- and is told somebody has already taken it -- in words, not as a 23P01.
--
-- Guards in D2's order. The slot-dependent overlap check runs only when the
-- job HAS a slot; a C3 job has none, and none of the slot checks (leave,
-- windows, clashes) can run without one -- the hour is set afterwards in the
-- queue, and `scheduled`+null-slot is established semantics
-- (`force_assign_work_order`, `20260822170000` §6, writes the same shape).
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
     and (m.profile_id = auth.uid() or sp.profile_id = auth.uid())
   limit 1;
  if not found then
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

-- ---------------------------------------------------------------------------
-- 3. The projection trigger learns that acceptance can arrive first (D5)
--
-- The body is `20260823120000`'s -- the row-shape resolution is kept exactly
-- -- with one branch widened: an INSERTed assignment in `offered` OR
-- `accepted` moves the complaint `open -> acknowledged`. On the offer path
-- nothing changes (the offer insert still acknowledges); on the claim, force
-- -assign and dispatch-force paths the accepted insert now acknowledges too,
-- instead of leaving a committed job on an `open` complaint.
-- ---------------------------------------------------------------------------

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
     and new.status in ('offered', 'accepted') then
    -- D5: an accepted insert is at-least-acknowledged. `where status = 'open'`
    -- keeps this monotone -- a complaint already further along is not dragged
    -- back.
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

drop trigger if exists work_order_assignments_project_complaint
  on public.work_order_assignments;
create trigger work_order_assignments_project_complaint
  after insert on public.work_order_assignments
  for each row when (new.status in ('offered', 'accepted'))
  execute function public.project_complaint_from_jobs();

-- ---------------------------------------------------------------------------
-- 4. Grants
--
-- Both functions decide eligibility themselves from `auth.uid()`, so
-- `authenticated` is the right audience; nothing here is for `anon`, and the
-- definer-owned internals stay revoked from everybody else, as always.
-- ---------------------------------------------------------------------------

revoke all on function public.worker_open_jobs()
  from public, anon, authenticated;
grant execute on function public.worker_open_jobs() to authenticated;

revoke all on function public.claim_open_work_order(uuid)
  from public, anon, authenticated;
grant execute on function public.claim_open_work_order(uuid) to authenticated;

-- New functions change the PostgREST function catalogue. Refresh it
-- immediately instead of waiting for the schema-cache polling interval.
notify pgrst, 'reload schema';

-- ---------------------------------------------------------------------------
-- 5. Prove it, in the same transaction
-- ---------------------------------------------------------------------------

do $$
begin
  if to_regprocedure('public.worker_open_jobs()') is null then
    raise exception 'worker_open_jobs missing';
  end if;
  if to_regprocedure('public.claim_open_work_order(uuid)') is null then
    raise exception 'claim_open_work_order missing';
  end if;
  if position(
    'new.status in (''offered'', ''accepted'')'
    in pg_get_functiondef('public.project_complaint_from_jobs()'::regprocedure)
  ) = 0 then
    raise exception 'projection trigger body was not widened to accepted inserts';
  end if;
  if not exists (
    select 1
      from pg_trigger
     where tgname = 'work_order_assignments_project_complaint'
       and position('accepted' in pg_get_triggerdef(oid)) > 0
  ) then
    raise exception 'assignment projection trigger WHEN clause was not widened';
  end if;
end;
$$;
