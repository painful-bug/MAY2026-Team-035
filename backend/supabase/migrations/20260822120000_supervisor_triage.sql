-- ---------------------------------------------------------------------------
-- 20260822120000_supervisor_triage.sql
--
-- The supervisor's landing surface: four sections, one read, and one verb.
--
-- WHAT THE SCREEN NEEDS THAT THE MODEL COULD NOT SAY
--
-- `docs/plans/SUPERVISOR_TRIAGE_SPEC.md` freezes a dashboard in four stacked
-- sections -- new complaints, taken up by you, assigned but not started, being
-- worked right now. Three of the four are already derivable from what `0036`
-- and `0039` record. The fourth boundary is not, and neither is the second:
--
--   * nothing anywhere records that a supervisor has *picked up* a complaint,
--     so "new" and "mine, not yet dispatched" are the same row;
--   * nothing records the moment a worker pressed **Start** -- `start_work_order`
--     (`0039` 481) moves the status and lets the instant fall into `updated_at`,
--     which the next write overwrites, so "being worked right now" could show a
--     job and not how long it has been going;
--   * `20260821200000` re-stamps a departed supervisor's live work onto whoever
--     inherits it and deliberately leaves no mark, so the inheriting supervisor
--     cannot tell the work they chose from the work that arrived by somebody
--     else's removal.
--
-- THE PRODUCT OWNER'S RULINGS, 2026-08-22 (`docs/COMPLAINT_ENGINE_HANDOFF.md` 18)
--
--   1. **Take-up is explicit and stamped.** `complaints.taken_up_by_membership_id`
--      + `taken_up_at`, written by `take_up_complaint` and by nothing else.
--      Stated against 15's ruling 1 rather than around it: this is *triage
--      ownership*, not dispatch. `assigned_to_membership_id` stays the dead
--      column it is, the complaint still belongs to the department, and
--      dispatch still happens only through work orders. Nothing in this file
--      writes that column or `assignee_label`, and the static battery asserts
--      the absence.
--   2. **Take-up is visible progress.** It moves the complaint `open ->
--      acknowledged`, which `vocabularies.py` already renders to the resident as
--      *In Progress*. Until now `acknowledged` had exactly one writer -- the
--      worker-offer arm of `project_complaint_from_jobs` (`20260813102000` 9) --
--      and it gains this second one deliberately. The two do not race: this one
--      only ever moves `open`, and the trigger's arm only ever moves `open` too,
--      so whichever runs second finds nothing to do.
--   3. **Re-stamped work is marked now.** 16 chose "no new column" for
--      departure-continuity re-stamping. That is *partially* reversed:
--      `work_orders.supervision_inherited_at`, stamped by
--      `restamp_department_supervision`, and nothing else about that design
--      changes. Residents and workers still never see supervisor identity -- no
--      resident-facing or worker-facing read has ever returned it
--      (`resident_complaints_service.py` 194/226, `20260813105000` 34-63) -- so
--      the stamp feeds a supervisor-only surface and needs no suppression.
--   4. **"Being worked right now" is the worker's own Start.**
--      `work_orders.started_at`, stamped `coalesce(started_at, now())` by
--      `start_work_order`. A *Pause* verb is deliberately deferred: a paused
--      status would ripple through the work-order vocabulary, the CHECK
--      constraint, `project_complaint_from_jobs` and the dispatch sweep, and the
--      section stands without it.
--
-- WHY TWO FUNCTIONS ARE REDECLARED WHOLE
--
-- `start_work_order` (`0039`) and `restamp_department_supervision`
-- (`20260821200000`) are somebody else's, and the house convention for changing
-- one is to copy the body forward line by line rather than to patch it
-- (`20260812113000` 1). Both copies below are *provably* additive: every
-- non-blank line of the owning file's version is present here verbatim, and the
-- new stamp is a line added beneath one -- which is why the second assignment in
-- each `update` is written leading-comma style rather than by rewriting the line
-- above it. `tests/test_supervisor_triage_migration.py` compares the two bodies
-- line by line against their owning files and fails on anything lost.
--
-- WHY THE SNAPSHOT IS ONE RPC AND NOT FOUR
--
-- The triage screen today asks for a department's complaints and then asks for
-- each one's work orders, which is the N+1 the four sections would multiply by
-- four. `supervisor_triage_snapshot` answers all four in one round trip. **It
-- is a read and it decides nothing**: no status moves, no notification, no
-- write of any kind. The *bucketing* is decided here rather than in React,
-- because four definitions that must agree are one definition or they are four
-- answers -- and the frozen wire contract says the frontend renders the arrays
-- as it receives them.
--
-- WHAT IS DELIBERATELY NOT HERE
--
--   * No `paused` status, no notification, no new SSE topic. Take-up is a
--     passive field change under ARCHITECTURE.md's rule; the resident sees
--     *In Progress* through the ordinary dashboard re-snapshot.
--   * No write to `complaints.assigned_to_membership_id` or `assignee_label`
--     (15, ruling 1).
--   * No new table and no view. The snapshot is a function because it takes a
--     department and asks its own authorization question; a view would answer
--     that question a second way through RLS and the two would drift.
--
-- IDEMPOTENT. Every statement tolerates its own effect already being present --
-- `add column if not exists`, `create index if not exists`, `create or replace`
-- -- so the recovery from a half-applied hand-run is to run it again. Section 7
-- verifies the whole file in the same transaction and fails loudly rather than
-- reporting a half-success.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. The four columns
--
-- Additive alters, in the shape `0036` 1 used on this same table: the hosted
-- `work_orders` and `complaints` are pre-baseline hand-built tables carrying
-- legacy columns no migration declares (`20260820120000`, `20260822090000`), and
-- `add column if not exists` is what has always applied cleanly around them.
--
-- All four are nullable with no default, and that is the design rather than an
-- omission. `taken_up_at is null` **is** the answer to "is this untouched", and
-- `started_at is null` is the answer to "has anybody actually turned up" -- a
-- default would make every row that predates this file claim a moment nobody
-- lived through.
--
-- `on delete set null` on the membership, matching `work_orders`'
-- `supervisor_membership_id` (`0036` 116): a membership can be deleted, and a
-- complaint whose triage owner's row is gone is still a complaint. The
-- *timestamp* survives that deletion, so the fact that somebody took it up is
-- not lost with the name.
-- ---------------------------------------------------------------------------

alter table public.complaints
  add column if not exists taken_up_by_membership_id uuid
    references public.community_memberships(id) on delete set null,
  add column if not exists taken_up_at timestamptz;

alter table public.work_orders
  add column if not exists started_at               timestamptz,
  add column if not exists supervision_inherited_at timestamptz;

comment on column public.complaints.taken_up_by_membership_id is
  'The supervisor who pressed Take up. Triage ownership, not dispatch -- the complaint still belongs to the department, and who is actually going is a work-order assignment.';
comment on column public.complaints.taken_up_at is
  'When a supervisor took this complaint up. Null means nobody has, which is what puts it in the dashboard''s New complaints section.';
comment on column public.work_orders.started_at is
  'When the worker pressed Start. Was lost into updated_at before 2026-08-22, so "being worked right now" could not say for how long.';
comment on column public.work_orders.supervision_inherited_at is
  'When this job was re-stamped onto its current supervisor by somebody else''s removal. Supervisor-only: no resident-facing or worker-facing read returns a supervisor''s identity.';

-- The dashboard's first read, in one index: this department's complaints,
-- untouched ones first. `created_at desc` matches the order every array in the
-- snapshot is sorted by, so the index answers the sort as well as the filter.
create index if not exists complaints_department_takeup_idx
  on public.complaints (department_id, taken_up_at, created_at desc);


-- ---------------------------------------------------------------------------
-- 2. Taking a complaint up
--
-- One transaction, three effects, and a fourth thing that deliberately does not
-- happen.
--
--   * stamps `taken_up_by_membership_id` and `taken_up_at`;
--   * moves the storage status `open -> acknowledged`, **and only from `open`**
--     -- a complaint already `in_progress` because a worker started is not
--     walked backwards by somebody pressing a triage button;
--   * writes a `complaint_events` row so the timeline says who and when.
--     `event_type` is `text` with no CHECK (`0001` 70), so a new word costs no
--     migration -- it costs a label in `resident_complaints_service._EVENT_LABELS`,
--     which is where the timeline learns vocabulary.
--   * **notifies nobody.** A field changing with no action attached is the
--     passive change ARCHITECTURE.md's rule exists to suppress; the resident
--     learns the same fact by the status they already read as *In Progress*.
--
-- THE THREE REFUSALS
--
-- `HB404` for a complaint that does not exist. `HB403` for one in a department
-- the caller does not supervise -- asked as `can_supervise_department`, the same
-- predicate `department_complaints` (`20260813103000` 55) and `create_work_order`
-- (`0036` 692) ask, so the dashboard and the verb agree about who may act.
-- `HB409` when somebody else already holds it, **naming them**: "already taken
-- up" without a name sends a supervisor to ask around an office.
--
-- Taking up your own again is a no-op `200` rather than a 409. A double-clicked
-- button is not an error worth a message (`assign_complaint_department`,
-- `20260812090300`, made the same call for the same reason), and re-stamping
-- `taken_up_at` would move a moment that already happened.
--
-- A complaint with **no department** is `HB409` and not `HB403`. There is no
-- department to supervise, so refusing it as an authorization failure would tell
-- a supervisor they lack a permission when what is missing is the routing.
-- ---------------------------------------------------------------------------

create or replace function public.take_up_complaint(p_complaint_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_complaint public.complaints%rowtype;
  v_actor     uuid;
  v_holder    text;
begin
  select * into v_complaint
    from public.complaints where id = p_complaint_id
    for update;
  if not found then
    raise exception 'No such complaint.' using errcode = 'HB404';
  end if;

  if v_complaint.department_id is null then
    raise exception 'This complaint has not been given to a department yet.'
      using errcode = 'HB409';
  end if;

  if not public.can_supervise_department(v_complaint.department_id) then
    raise exception 'You do not work on this department''s complaints.'
      using errcode = 'HB403';
  end if;

  select m.id into v_actor
    from public.community_memberships m
   where m.community_id = v_complaint.community_id
     and m.profile_id   = auth.uid()
     and m.status       = 'active'
     and m.ended_at is null;
  if v_actor is null then
    -- Unreachable through `can_supervise_department`, which resolves the caller
    -- from exactly this row. Asserted rather than assumed, because a null actor
    -- would write an unattributable stamp and a timeline entry from nobody.
    raise exception 'You do not work on this department''s complaints.'
      using errcode = 'HB403';
  end if;

  if v_complaint.taken_up_by_membership_id is not null then
    if v_complaint.taken_up_by_membership_id = v_actor then
      return;  -- Already yours. A second press is not an error.
    end if;

    select coalesce(p.full_name, 'Another supervisor') into v_holder
      from public.community_memberships m
      left join public.profiles p on p.id = m.profile_id
     where m.id = v_complaint.taken_up_by_membership_id;

    raise exception '% has already taken this complaint up.',
      coalesce(v_holder, 'Another supervisor') using errcode = 'HB409';
  end if;

  update public.complaints
     set taken_up_by_membership_id = v_actor,
         taken_up_at               = now(),
         -- `open` only. A complaint a worker has already started is
         -- `in_progress`, and triage does not walk that backwards.
         status                    = case when status = 'open'
                                          then 'acknowledged'::public.complaint_status
                                          else status end,
         updated_at                = now()
   where id = p_complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    p_complaint_id, v_actor, 'taken_up',
    jsonb_build_object(
      'departmentId', v_complaint.department_id,
      'fromStatus',   v_complaint.status::text)
  );
end;
$$;

comment on function public.take_up_complaint(uuid) is
  'A supervisor picking a new complaint up: stamps who and when, moves open -> acknowledged, and writes the timeline entry. Triage ownership only -- dispatch is still a work order.';


-- ---------------------------------------------------------------------------
-- 3. `start_work_order`, copied forward for the stamp (ruling 4)
--
-- `0039` 481's body, whole, under the house convention. **One line is added and
-- none is changed**: the `update` gains `started_at` on a continuation line so
-- that `set status = 'in_progress', updated_at = now()` survives verbatim and
-- the copy can be proved additive line by line rather than promised to be.
--
-- `coalesce(started_at, now())` rather than `now()`, and the reason is one line
-- above it in the same function: the already-`in_progress` early return means a
-- second press cannot reach this statement *today*, and a future writer that
-- reaches `in_progress` some other way should not be able to reset the clock the
-- dashboard's elapsed time is measured from.
--
-- Nothing else moves. The notification, the `complaint_events` row, both
-- `HB404`s and the `HB409` are `0039`'s and are reproduced unchanged.
-- ---------------------------------------------------------------------------

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
         -- ADDED (20260822120000, ruling 4): the moment itself, which used to
         -- fall into `updated_at` and be overwritten by the next write.
       , started_at = coalesce(started_at, now())
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
  'The worker is on site. Idempotent on a job already in progress, and — since 2026-08-22 — the moment is kept in started_at rather than lost into updated_at.';


-- ---------------------------------------------------------------------------
-- 4. `restamp_department_supervision`, copied forward for the mark (ruling 3)
--
-- `20260821200000` 2's body, whole. **One line is added and none is changed**:
-- the `update` gains `supervision_inherited_at` between the two assignments it
-- already had.
--
-- 16 argued for no new column and this reverses that in one respect and one
-- only: the *supervisor's* dashboard can now badge work that arrived by somebody
-- else's removal rather than by their own hand. The successor rule, the scope,
-- the return value and the trigger that calls this are all untouched --
-- `department_supervision_successor` and `carry_department_supervision` are not
-- redeclared here at all, because nothing about them changes and a body copied
-- forward to gain nothing is a body the next author has to diff.
--
-- `now()` and not the removal's own timestamp: this function is called from an
-- `after update` trigger inside the removing transaction, so the two are the
-- same instant to any reader, and reaching back into `staff_assignments` for it
-- would make this function depend on its caller.
-- ---------------------------------------------------------------------------

create or replace function public.restamp_department_supervision(
  p_department_id  uuid,
  p_from_membership uuid
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_target  uuid;
  v_moved   integer := 0;
begin
  if p_department_id is null or p_from_membership is null then
    return 0;
  end if;

  if not exists (
    select 1 from public.work_orders w
     where w.supervisor_membership_id = p_from_membership
       and w.department_id            = p_department_id
       and w.status not in ('completed', 'cancelled', 'failed')
  ) then
    return 0;
  end if;

  v_target := public.department_supervision_successor(
    p_department_id, p_from_membership);
  if v_target is null then
    return 0;
  end if;

  update public.work_orders w
     set supervisor_membership_id = v_target,
         -- ADDED (20260822120000, ruling 3): so the inheriting supervisor's
         -- dashboard can tell the work they chose from the work that arrived.
         supervision_inherited_at = now(),
         updated_at               = now()
   where w.supervisor_membership_id = p_from_membership
     and w.department_id            = p_department_id
     and w.status not in ('completed', 'cancelled', 'failed');

  get diagnostics v_moved = row_count;
  return v_moved;
end;
$$;

comment on function public.restamp_department_supervision(uuid, uuid) is
  'Re-point one department''s live work orders away from a membership that has stopped supervising them, marking each with supervision_inherited_at. Returns how many moved; 0 when there is nothing to move or nobody to move it to.';


-- ---------------------------------------------------------------------------
-- 5. The four sections, in one read
--
-- The bucketing frozen in `docs/plans/SUPERVISOR_TRIAGE_SPEC.md`, stated once
-- and in SQL:
--
--   * *live* work order  -- status not in `completed | failed | cancelled`;
--   * *engaged*          -- a live work order with an assignment row in
--                           `offered | accepted`, or work-order status
--                           `scheduled`;
--   * `new_complaints`   -- storage status `open`, `taken_up_at is null`;
--   * `taken_up`         -- `taken_up_at is not null`, status `open|acknowledged`,
--                           and no live work order that is engaged or
--                           `in_progress`;
--   * `assigned_pending` -- live, engaged, status <> `in_progress`;
--   * `in_progress`      -- status `in_progress`.
--
-- A taken-up complaint whose job became engaged therefore appears in
-- `assigned_pending` **as its work order** and drops out of `taken_up`: the
-- supervisor's question has changed from "who do I send" to "is Ravi going to
-- turn up", and a row that answered both would be in two places at once.
--
-- Every array is newest-first by `created_at`. The urgent stack is the
-- frontend's own pinning and is deliberately not sorted for here -- a server
-- that pre-pinned would decide a layout, and the wire contract says it does not.
--
-- WHAT IS PROJECTED AND WHY
--
-- `priority` and `status` go out **as stored** -- `low|medium|high`,
-- `open|acknowledged|...`. `app/domain/vocabularies.py` is the one place this
-- codebase translates a vocabulary, and a second translation written in SQL is a
-- second answer free to disagree with it.
--
-- `rerouted_at` is derived and not stored: the newest `department_assigned`
-- event whose payload names *this* department as the destination. `raise_complaint`
-- writes `raised` rather than `department_assigned` (`20260812090300` 3), so
-- automatic routing at raise time is correctly not a reroute -- only an admin
-- allotting, a manager moving, or an accepted transfer request is.
--
-- `security definer`, and the guard is `can_supervise_department`, raised as
-- `HB403` rather than returned as an empty snapshot. An empty dashboard and a
-- refused one look identical on a screen, and the difference is the whole
-- content of the answer.
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

  -- Sections 1 and 2: complaints. One scan, two filters, because both arms need
  -- the same six joins and the same three derived columns.
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
                                              as live_work_order_count,
      exists (
        select 1
          from public.work_orders w
         where w.complaint_id = c.id
           and w.status not in ('completed', 'cancelled', 'failed')
           and (
             w.status = 'in_progress'
             or w.status = 'scheduled'
             or exists (
                  select 1
                    from public.work_order_assignments a
                   where a.work_order_id = w.id
                     and a.status in ('offered', 'accepted')
                )
           )
      )                                       as has_engaged_work
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
      a.assignee_name,
      -- `has_open_offer` and not `assignee_name is not null`: a roster row can
      -- be deleted out from under an assignment (`staff_assignment_id` is
      -- `on delete set null` in `0001`), and a job offered to somebody whose
      -- row has gone is still a job that has been put to somebody. Deriving
      -- *engaged* from the name would drop it out of the dashboard entirely.
      (w.status = 'scheduled' or coalesce(a.has_open_offer, false)) as engaged
    from public.work_orders w
    left join public.complaints c on c.id = w.complaint_id
    left join public.skills     s on s.id = w.skill_id
    left join lateral (
      -- The person the job is currently with: accepted first, then the newest
      -- open offer. `work_order_overview` (`0036` 5) shows the accepted one
      -- only, which is the right answer for "who is coming" and the wrong one
      -- for a dashboard section whose whole subject is work that has been put to
      -- somebody and not yet taken up.
      select sa.display_name as assignee_name,
             true            as has_open_offer
        from public.work_order_assignments woa
        left join public.staff_assignments sa on sa.id = woa.staff_assignment_id
       where woa.work_order_id = w.id
         and woa.status in ('offered', 'accepted')
       order by (woa.status = 'accepted') desc, woa.offered_at desc
       limit 1
    ) a on true
    where w.department_id = p_department_id
      and w.status not in ('completed', 'cancelled', 'failed')
  )
  select
    coalesce((
      select jsonb_agg(to_jsonb(sec) order by sec.created_at desc)
        from (select cr.* from complaint_rows cr
               where cr.status = 'open' and cr.taken_up_at is null) sec
    ), '[]'::jsonb),
    coalesce((
      select jsonb_agg(to_jsonb(sec) order by sec.created_at desc)
        from (select cr.* from complaint_rows cr
               where cr.taken_up_at is not null
                 and not cr.has_engaged_work) sec
    ), '[]'::jsonb),
    coalesce((
      select jsonb_agg(to_jsonb(sec) order by sec.created_at desc)
        from (select wr.* from work_order_rows wr
               where wr.engaged and wr.status <> 'in_progress') sec
    ), '[]'::jsonb),
    coalesce((
      select jsonb_agg(to_jsonb(sec) order by sec.created_at desc)
        from (select wr.* from work_order_rows wr
               where wr.status = 'in_progress') sec
    ), '[]'::jsonb)
  into v_new, v_taken, v_pending, v_progress;

  return jsonb_build_object(
    'department_id',    p_department_id,
    'new_complaints',   v_new,
    'taken_up',         v_taken,
    'assigned_pending', v_pending,
    'in_progress',      v_progress
  );
end;
$$;

comment on function public.supervisor_triage_snapshot(uuid) is
  'The supervisor dashboard''s four sections in one read: new complaints, taken up but undispatched, assigned but not started, and being worked right now. A read — it moves nothing and notifies nobody.';


-- ---------------------------------------------------------------------------
-- 6. Grants
--
-- `authenticated` on both, because both resolve the caller from `auth.uid()`
-- and refuse a stranger themselves -- the posture every function in `0036` 6
-- takes. `start_work_order` and `restamp_department_supervision` keep the ACLs
-- their owning files gave them (`create or replace` does not reset them); the
-- grants are reissued below so a hand-run of this file alone still lands a
-- callable function, and so that reading this file tells you who may call what.
-- ---------------------------------------------------------------------------

grant execute on function public.take_up_complaint(uuid) to authenticated;
grant execute on function public.supervisor_triage_snapshot(uuid) to authenticated;
grant execute on function public.start_work_order(uuid) to authenticated;

revoke all on function public.restamp_department_supervision(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.restamp_department_supervision(uuid, uuid)
  to service_role;


-- ---------------------------------------------------------------------------
-- 7. Verification, in the same transaction as the change
--
-- The shape `20260822090000` 2 ends with, and for the same reason: a file that
-- claims to have added something should fail rather than report success. Nothing
-- below writes anything.
-- ---------------------------------------------------------------------------

do $$
declare
  v_missing text;
  v_src     text;
begin
  select string_agg(name, ', ' order by name) into v_missing
    from (values
      ('complaints', 'taken_up_by_membership_id'),
      ('complaints', 'taken_up_at'),
      ('work_orders', 'started_at'),
      ('work_orders', 'supervision_inherited_at')
    ) as wanted(tbl, name)
   where not exists (
     select 1 from information_schema.columns c
      where c.table_schema = 'public'
        and c.table_name   = wanted.tbl
        and c.column_name  = wanted.name
   );
  if v_missing is not null then
    raise exception 'supervisor_triage: these columns were not added: %', v_missing;
  end if;

  select string_agg(name, ', ' order by name) into v_missing
    from (values
      ('take_up_complaint'),
      ('supervisor_triage_snapshot'),
      ('start_work_order'),
      ('restamp_department_supervision')
    ) as wanted(name)
   where not exists (
     select 1 from pg_proc
      where pronamespace = 'public'::regnamespace and proname = wanted.name
   );
  if v_missing is not null then
    raise exception 'supervisor_triage: these functions are not declared: %', v_missing;
  end if;

  -- The two copied bodies carry their stamp. A `create or replace` that lost it
  -- would leave a dashboard section that is permanently empty and nothing that
  -- errors, which is the failure this check exists for.
  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace and proname = 'start_work_order';
  if v_src not like '%started_at = coalesce(started_at, now())%' then
    raise exception
      'supervisor_triage: start_work_order does not stamp started_at. An older definition won.';
  end if;

  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace
     and proname = 'restamp_department_supervision';
  if v_src not like '%supervision_inherited_at%' then
    raise exception
      'supervisor_triage: restamp_department_supervision does not stamp supervision_inherited_at. An older definition won.';
  end if;

  raise notice
    'supervisor_triage: four columns, four functions, both stamps in place.';
end $$;


-- ---------------------------------------------------------------------------
-- 8. Post-apply checks
--
-- Run these in the SQL Editor after this file. They are also reproduced in
-- `docs/plans/MIGRATION_APPLY_RUNBOOK.md` 18. Nothing below runs as part of the
-- migration; the block in section 7 is the only thing that executes.
--
--   -- (a) The snapshot answers for a department you supervise. Zero rows in
--   --     every array on a young database is the ordinary answer.
--   select public.supervisor_triage_snapshot(
--     (select id from public.departments where kind = 'service' limit 1));
--
--   -- (b) Nothing has been taken up yet, which is what a new column looks like.
--   select count(*) filter (where taken_up_at is not null) as taken_up,
--          count(*)                                        as complaints
--     from public.complaints;
--
--   -- (c) The two copied bodies kept everything they had.
--   select proname,
--          prosrc like '%work_order.started%'          as still_notifies,
--          prosrc like '%started_at = coalesce%'       as stamps_start
--     from pg_proc
--    where pronamespace = 'public'::regnamespace and proname = 'start_work_order';
--   -- expect: one row, both true.
-- ---------------------------------------------------------------------------
