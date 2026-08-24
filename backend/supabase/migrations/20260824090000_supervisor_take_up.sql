-- ---------------------------------------------------------------------------
-- 20260824090000_supervisor_take_up.sql
--
-- The valve `20260823190000` left the department without.
--
-- That file closed three doors at once (rulings R1-R3): the picker, the
-- auto-book and the open board all stop offering work to anybody whose roster
-- rank is not `member`. It is the right rule and the product owner asked for
-- it. What it also did was leave a two-person department -- one supervisor, one
-- technician on leave -- with a complaint nobody in the system may hold.
--
-- The owner's answer, verbatim (R8, 2026-08-24):
--
--     "yes, include an option where a super can take up work ... it sholdnt be
--      something seen in normal routine workflow ... it is available at any
--      time though but as a seperate button orsomething like that."
--
-- So leadership self-assignment exists, and it is a **separate verb**. Not a
-- relaxed candidate filter, not a rank exception inside `dispatch_candidates_at`,
-- not a flag on `assign`: those are the routine flows, and a rule with an
-- exception inside it is the rule nobody can read afterwards. The candidate
-- list, the ping, the auto-book and the board stay member-only, exactly as
-- `20260823190000` left them. This file adds one function a supervisor or a
-- manager can only reach by deliberately pressing "Take this job myself", and
-- it names itself on the timeline so that a month later the record says which
-- door the work came through.
--
-- The frozen spec is `docs/plans/ASSIGNMENT_ELIGIBILITY_AND_DRIFT_SPEC.md`, its
-- addendum of 2026-08-24; the sections below cite rulings R8-R13 rather than
-- restating them.
--
-- WHAT IS IN HERE
--
--   1. One new word for `complaint_events`: `job_taken_up`. The vocabulary is an
--      enumerating CHECK on a live table (`20260813105000` 77, widened by
--      `20260822150000` and again by `20260822170000` 7), so a word is a
--      migration -- the lesson the very first live Take-up press taught as a
--      23514.
--   2. `take_up_work_order`, new. `force_assign_work_order`'s mechanics with the
--      naming taken out: the assignee is not a parameter, it is whoever is
--      calling, and the only question the function asks about them is whether
--      they hold active leadership on this job's own department roster.
--   3. `force_assign_work_order`, re-issued VERBATIM except for R12 -- its two
--      timeline rows stamp the caller instead of the department's standing
--      supervisor. That was R7, backlogged on 2026-08-23 as an attribution
--      smell; it is closed here because this file is already teaching two
--      neighbouring functions to name the person who acted.
--   4. `claim_open_work_order`, re-issued VERBATIM except for R13 -- the board
--      stays shut to leadership (R2 stands) and the refusal now says where the
--      open door is. Same `HB403`.
--
-- WHY THE ASSIGNEE IS NOT A PARAMETER
--
-- A `p_staff_assignment_id` would make this "assign anybody, without the rank
-- check" -- which is the rule of `20260823190000` with a hole in it, reachable
-- by anybody who can call an RPC. There is no such parameter here. The roster
-- row is looked up from `auth.uid()` by the same predicate
-- `claim_open_work_order` uses to find its caller, and a caller who holds no
-- leadership row on this department is refused in words. The most a supervisor
-- can do with this verb is give themselves work.
--
-- WHAT IT IS NOT
--
-- No status vocabulary changes (`work_orders.status` lands on `scheduled`, the
-- word force-assign already writes), no `dispatch_tasks` kind, no new SQLSTATE
-- -- the whole file raises only `HB403`, `HB404` and `HB409`, so
-- `app/core/pg_errors.py` gains nothing (R13). `supervision_inherited_at` is
-- never touched: it has exactly one writer, `restamp_department_supervision`,
-- and `tests/test_supervisor_triage_migration.py` 371 holds that invariant --
-- a supervisor taking a job up is not a supervisor inheriting one.
--
-- One transaction: the SQL editor wraps the paste, so a failure anywhere rolls
-- back everything, which is the arrangement every file in this directory
-- assumes. Idempotent: section 1 drops and recreates the same constraint, and
-- sections 2-4 are `create or replace`.
--
-- Hand-applied by the owner in the Supabase SQL editor, like every file here.
-- Runbook section 30.
--
-- ROLLBACK:
--   * section 1: re-apply `20260822170000` section 7, which is this constraint
--     without `job_taken_up` -- and only once no stored row uses the word.
--   * section 2: `drop function public.take_up_work_order(uuid, timestamptz,
--     timestamptz);`
--   * sections 3-4: re-apply `20260822170000` section 6 and
--     `20260823190000` section 4, which are these bodies without the two ruled
--     diffs.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. The event vocabulary gains exactly one word (R11)
--
-- `job_taken_up`, written by section 2. The shape is `20260822170000` 7's,
-- which is `20260822150000`'s, which is `20260813105000`'s: prove nothing
-- stored is outside the new list *before* dropping anything, so a failure here
-- leaves the old constraint standing; then drop, add, and prove the new word
-- specifically -- a bare existence check would pass against the very constraint
-- being replaced.
--
-- Widening only. Every word the old constraint accepted is in the list below,
-- carried over from `20260822170000` 1021-1025 -- the last file in this
-- directory that defines this constraint, which is the one whose list the
-- database is holding. `tests/test_supervisor_take_up_migration.py` derives that
-- list from that file's own text and fails if this one has dropped a word or
-- invented a second.
--
-- `job_taken_up` and not `taken_up`: the older word is `take_up_complaint`'s and
-- means a supervisor is now *looking at* a complaint. This one means a
-- supervisor is now *going*. Two facts, two words -- the `job_` prefix is the
-- one this table already uses for everything that happens to a work order.
-- ---------------------------------------------------------------------------

do $$
declare v_bad text;
begin
  select event_type into v_bad from public.complaint_events where event_type not in (
    'raised','status_changed','assigned','progress_changed','due_date_changed','note_added','comment_added','reopened','resolution_confirmed',
    'job_created','job_scheduled','job_declined','job_assigned','job_cancelled','job_started','job_completed','job_failed',
    'department_assigned','department_change_requested','department_change_accepted','department_change_rejected',
    'job_force_assigned','returned_to_pool','auto_close_warning','auto_closed','taken_up','priority_changed','job_taken_up') limit 1;
  if v_bad is not null then raise exception 'Unknown existing complaint event type: %', v_bad; end if;
end $$;

alter table public.complaint_events drop constraint if exists complaint_events_type_check;
alter table public.complaint_events add constraint complaint_events_type_check check (event_type in (
  'raised','status_changed','assigned','progress_changed','due_date_changed','note_added','comment_added','reopened','resolution_confirmed',
  'job_created','job_scheduled','job_declined','job_assigned','job_cancelled','job_started','job_completed','job_failed',
  'department_assigned','department_change_requested','department_change_accepted','department_change_rejected',
  'job_force_assigned','returned_to_pool','auto_close_warning','auto_closed','taken_up','priority_changed','job_taken_up'));

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.complaint_events'::regclass
      and conname  = 'complaint_events_type_check'
      and pg_get_constraintdef(oid) like '%job_taken_up%'
  ) then raise exception 'complaint event type check missing or does not allow job_taken_up'; end if;
end $$;


-- ---------------------------------------------------------------------------
-- 2. `take_up_work_order` -- the separate button (R8, R10, R11)
--
-- `force_assign_work_order` (`20260822170000` 863) is the model, and the diff
-- between them is the whole design:
--
--   * **no `p_staff_assignment_id`.** Force-assign names somebody; this one
--     cannot. The assignee is the caller's own roster row, found from
--     `auth.uid()` by the predicate `claim_open_work_order` uses for the same
--     job -- membership profile or provider profile -- so the most a supervisor
--     can do here is give themselves work.
--   * **the guard is the rank, not the department alone.** Force-assign asks
--     `can_supervise_department`, which is true for a community admin as well;
--     that is right for a verb that names a technician and wrong for one that
--     books the caller. An admin holds no roster row, has no calendar and no
--     trade, and putting them in `work_order_assignments` would be a booking
--     nobody can keep. So the question here is the roster's: an active
--     `manager`- or `supervisor`-ranked row on THIS job's department (R10 --
--     `can_supervise_department` treats the two ranks identically, and
--     `restamp_department_supervision` can leave a manager as a department's
--     only leadership). No row, `HB403`, in words that name the door.
--   * **nobody notifies the caller.** Force-assign tells the assignee they have
--     been given a job; here the assignee just pressed the button.
--     `notify_complaint_staff`'s fourth argument is the exclusion, so the rest
--     of the department hears `job.taken_up` and the actor does not hear their
--     own echo -- the shape `claim_open_work_order` already uses for the same
--     reason.
--
-- Everything after the pick is force-assign's, deliberately: the status gate,
-- the slot rule, the named overlap refusal, withdraw-then-insert, the
-- `scheduled` update and the resident being told somebody is coming. A job
-- that behaved differently depending on which door assigned it would be two
-- mechanisms wearing one name.
--
-- The assignment row is `status 'accepted'`, `is_forced false`,
-- `is_auto_assigned false` (R11). Both flags are false and each is a sentence:
-- nobody's consent was overridden -- the holder is the person who asked for it
-- -- and no engine decided anything. `is_forced` is what the worker's card
-- reads to hide the Decline button, and there is nothing to decline.
--
-- Two timeline rows. `job_assigned` because from the resident's side the fact
-- is the same fact -- somebody is now coming, and their name is this -- and
-- `job_taken_up` beside it because from the department's side it is not: this
-- job did not go through the pool, and the record has to say so without anybody
-- having to reconstruct it from a rank. Both stamp the caller, resolved from
-- `auth.uid()` and asserted non-null (`take_up_complaint`, `20260822120000`
-- 209-221): an unattributable take-up is the one entry this word exists to
-- prevent.
--
-- `supervision_inherited_at` is NOT touched. Its single writer is
-- `restamp_department_supervision`; a supervisor choosing a job is not a
-- supervisor being handed one.
-- ---------------------------------------------------------------------------

create or replace function public.take_up_work_order(
  p_work_order_id      uuid,
  p_scheduled_start_at timestamptz default null,
  p_scheduled_end_at   timestamptz default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order     public.work_orders%rowtype;
  v_staff     public.staff_assignments%rowtype;
  v_complaint public.complaints%rowtype;
  v_actor     uuid;
  v_start     timestamptz;
  v_end       timestamptz;
  v_id        uuid;
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such work order.' using errcode = 'HB404';
  end if;

  -- The caller's own leadership row on this job's department, and nothing else
  -- is admitted: R8 made this a separate deliberate verb, not a hole in the
  -- member-only rule. `20260823190000` 511's caller predicate, with
  -- `rank = 'member'` turned around -- the same lookup, on the other side of
  -- the line it drew.
  select sa.* into v_staff
    from public.staff_assignments sa
    left join public.community_memberships m  on m.id  = sa.membership_id
    left join public.service_providers sp     on sp.id = sa.service_provider_id
   where sa.department_id = v_order.department_id
     and sa.status = 'active'
     and sa.is_active
     and sa.rank in ('manager', 'supervisor')
     and (m.profile_id = auth.uid() or sp.profile_id = auth.uid())
   limit 1;
  if not found then
    raise exception 'Only this department''s supervisor or manager can take up a job.'
      using errcode = 'HB403';
  end if;

  -- The actor, and the assertion. `take_up_complaint`'s pattern: the roster row
  -- above proves the caller may act, and this row is who they are on the
  -- timeline. A null here would write two entries from nobody, so it refuses
  -- with the same sentence rather than falling back to a stand-in.
  select m.id into v_actor
    from public.community_memberships m
   where m.community_id = v_order.community_id
     and m.profile_id   = auth.uid()
     and m.status       = 'active'
     and m.ended_at is null;
  if v_actor is null then
    raise exception 'Only this department''s supervisor or manager can take up a job.'
      using errcode = 'HB403';
  end if;

  if v_order.status in ('completed', 'cancelled', 'failed') then
    raise exception 'This job is no longer open.' using errcode = 'HB409';
  end if;

  v_start := coalesce(p_scheduled_start_at, v_order.scheduled_start_at);
  v_end   := coalesce(p_scheduled_end_at,   v_order.scheduled_end_at);
  if v_start is not null and v_end is not null and v_end <= v_start then
    raise exception 'A job needs a valid time.' using errcode = 'HB409';
  end if;

  -- The sentence, before the constraint says the same thing without one:
  -- `work_order_assignments_no_overlap` (`0036`) refuses this too, as `23P01`,
  -- which reaches the caller as a 409 with no name in it. Second person and not
  -- a name, because the person double-booked is the person reading it -- the
  -- wording `claim_open_work_order` uses for the other self-service verb.
  if v_start is not null and v_end is not null and exists (
    select 1 from public.work_order_assignments a
     where a.staff_assignment_id = v_staff.id
       and a.status = 'accepted'
       and a.work_order_id <> v_order.id
       and tstzrange(a.scheduled_start_at, a.scheduled_end_at, '[)')
           && tstzrange(v_start, v_end, '[)')
  ) then
    raise exception 'You are already booked during that time.'
      using errcode = 'HB409';
  end if;

  -- One holder at a time. Withdrawn and not deleted, for the reason `0036` 6
  -- and `0037` 5 gave: the history of who was booked and unbooked is the answer
  -- to the question a supervisor actually asks.
  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = v_order.id
     and status in ('offered', 'accepted');

  insert into public.work_order_assignments (
    work_order_id, staff_assignment_id, status, is_forced, is_auto_assigned,
    offered_at, responded_at, scheduled_start_at, scheduled_end_at)
  values (
    v_order.id, v_staff.id, 'accepted', false, false,
    now(), now(), v_start, v_end)
  returning id into v_id;

  update public.work_orders
     set status             = 'scheduled',
         scheduled_start_at = v_start,
         scheduled_end_at   = v_end,
         updated_at         = now()
   where id = v_order.id;

  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values
    (v_order.complaint_id, v_actor, 'job_assigned',
     jsonb_build_object('workOrderId', v_order.id,
                        'assignmentId', v_id,
                        'assigneeName', v_staff.display_name, 'takenUp', true)),
    (v_order.complaint_id, v_actor, 'job_taken_up',
     jsonb_build_object('workOrderId', v_order.id,
                        'assigneeName', v_staff.display_name));

  -- The department, minus the person who did it. The fourth argument is
  -- `notify_complaint_staff`'s exclusion (`20260821200000` 466), which is how
  -- this verb keeps its promise of no self-notification without a branch.
  perform public.notify_complaint_staff(
    v_order.complaint_id, 'job.taken_up',
    jsonb_build_object('title', v_staff.display_name || ' took up '
                                || coalesce(v_complaint.title, 'a job'),
                       'complaint_id', v_order.complaint_id),
    v_actor);

  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.assigned',
      jsonb_build_object(
        'title', 'Someone is coming for your complaint',
        'body', v_staff.display_name,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'complaint_id', v_order.complaint_id));
  end if;

  return v_id;
end;
$$;

comment on function public.take_up_work_order(uuid, timestamptz, timestamptz) is
  'Leadership self-assignment (ruling R8): force_assign_work_order''s mechanics with no assignee parameter -- the holder is the caller''s own active manager/supervisor roster row on this job''s department, or HB403. The deliberate exception to the member-only rule, and the only one.';


-- ---------------------------------------------------------------------------
-- 3. `force_assign_work_order` stamps whoever pressed it (R12, closing R7)
--
-- `20260822170000` 6's body, VERBATIM, with one variable declared, one lookup
-- added and two identifiers changed -- and nothing else. The guard, the roster
-- check, the status gate, the slot rule, the named overlap refusal, the
-- withdraw, the insert, the `scheduled` update, all three notifications and the
-- `comment on function` are untouched.
--
-- The defect it closes was logged on 2026-08-23 as R7 and backlogged as an
-- attribution smell: the two `complaint_events` rows stamped
-- `v_order.supervisor_membership_id`, the department's standing supervisor for
-- that job, who is not necessarily the person who pressed Assign. A manager
-- covering for a departed supervisor (`restamp_department_supervision`) forcing
-- an assignment produced a timeline saying the departed supervisor did it. It
-- is closed here rather than in its own file because this migration is already
-- teaching two neighbouring functions to name the actor, and a timeline where
-- one of three assignment verbs attributes differently is worse than either
-- rule applied consistently.
--
-- The resolution is `take_up_complaint`'s (`20260822120000` 209-221) including
-- its assertion: a null actor is refused, not defaulted. Force-assign is
-- reachable only through `can_supervise_department`, which resolves the caller
-- from exactly this row, so the branch is unreachable today -- and asserted
-- anyway, because the alternative is two timeline entries from nobody.
--
-- Nothing else in the function reads `v_order.supervisor_membership_id`, so the
-- change is the two rows and no more; the in-transaction proof in section 5
-- looks for the old spelling and fails if any of it survived.
-- ---------------------------------------------------------------------------

create or replace function public.force_assign_work_order(
  p_work_order_id      uuid,
  p_staff_assignment_id uuid,
  p_scheduled_start_at timestamptz default null,
  p_scheduled_end_at   timestamptz default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order     public.work_orders%rowtype;
  v_staff     public.staff_assignments%rowtype;
  v_complaint public.complaints%rowtype;
  v_start     timestamptz;
  v_end       timestamptz;
  v_id        uuid;
  -- R12 (2026-08-24): the person who pressed the button, resolved below.
  v_actor     uuid;
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such work order.' using errcode = 'HB404';
  end if;

  if not public.can_supervise_department(v_order.department_id) then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;

  -- R12 (2026-08-24), closing the backlogged R7: the two timeline rows below
  -- used to stamp the order's standing supervisor column -- the department's
  -- supervisor of record, who may not be the person in front of the screen.
  -- The actor is resolved the way `take_up_complaint` (`20260822120000` 209)
  -- resolves it, from `auth.uid()` in this order's own community, and asserted
  -- rather than assumed: a null actor writes two timeline entries from nobody.
  select m.id into v_actor
    from public.community_memberships m
   where m.community_id = v_order.community_id
     and m.profile_id   = auth.uid()
     and m.status       = 'active'
     and m.ended_at is null;
  if v_actor is null then
    raise exception 'You do not supervise this department.' using errcode = 'HB403';
  end if;

  if v_order.status in ('completed', 'cancelled', 'failed') then
    raise exception 'This job is no longer open.' using errcode = 'HB409';
  end if;

  select * into v_staff from public.staff_assignments
   where id = p_staff_assignment_id
     and department_id = v_order.department_id
     and status = 'active'
     and is_active;
  if not found then
    raise exception 'That person is not on this department roster.'
      using errcode = 'HB404';
  end if;

  v_start := coalesce(p_scheduled_start_at, v_order.scheduled_start_at);
  v_end   := coalesce(p_scheduled_end_at,   v_order.scheduled_end_at);
  if v_start is not null and v_end is not null and v_end <= v_start then
    raise exception 'A job needs a valid time.' using errcode = 'HB409';
  end if;

  -- The sentence, before the constraint says the same thing without one:
  -- `work_order_assignments_no_overlap` (`0036`) refuses this too, as `23P01`,
  -- which reaches the caller as a 409 with no name in it.
  if v_start is not null and v_end is not null and exists (
    select 1 from public.work_order_assignments a
     where a.staff_assignment_id = v_staff.id
       and a.status = 'accepted'
       and a.work_order_id <> v_order.id
       and tstzrange(a.scheduled_start_at, a.scheduled_end_at, '[)')
           && tstzrange(v_start, v_end, '[)')
  ) then
    raise exception '% is already booked during that time.', v_staff.display_name
      using errcode = 'HB409';
  end if;

  -- One holder at a time. Withdrawn and not deleted: "we sent Ravi and he could
  -- not get in, so we sent Anil" is the question a supervisor actually asks.
  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = v_order.id
     and status in ('offered', 'accepted');

  insert into public.work_order_assignments (
    work_order_id, staff_assignment_id, status, is_forced, is_auto_assigned,
    offered_at, responded_at, scheduled_start_at, scheduled_end_at)
  values (
    v_order.id, v_staff.id, 'accepted', true, false,
    now(), now(), v_start, v_end)
  returning id into v_id;

  update public.work_orders
     set status             = 'scheduled',
         scheduled_start_at = v_start,
         scheduled_end_at   = v_end,
         updated_at         = now()
   where id = v_order.id;

  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values
    (v_order.complaint_id, v_actor, 'job_assigned',
     jsonb_build_object('workOrderId', v_order.id,
                        'assigneeName', v_staff.display_name, 'forced', true)),
    (v_order.complaint_id, v_actor, 'job_force_assigned',
     jsonb_build_object('workOrderId', v_order.id,
                        'assigneeName', v_staff.display_name));

  if v_staff.membership_id is not null then
    perform public.notify_member(
      v_staff.membership_id, 'work_order.assigned',
      jsonb_build_object(
        'title', 'You have been assigned a job',
        'body', coalesce(v_complaint.title, 'Scheduled work'),
        'url', '/worker?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id));
  end if;

  perform public.notify_complaint_staff(
    v_order.complaint_id, 'job.force_assigned',
    jsonb_build_object('title', 'A job was assigned without an offer',
                       'complaint_id', v_order.complaint_id));

  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.assigned',
      jsonb_build_object(
        'title', 'Someone is coming for your complaint',
        'body', v_staff.display_name,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'complaint_id', v_order.complaint_id));
  end if;

  return v_id;
end;
$$;

comment on function public.force_assign_work_order(uuid, uuid, timestamptz, timestamptz) is
  'The supervisor''s explicit override of the consent model: a named person, an is_forced assignment they cannot decline, and the engine''s own force-assign aftermath. dispatch_force_assign without the picking, and with a guard.';


-- ---------------------------------------------------------------------------
-- 4. The board's refusal points at the open door (R13)
--
-- `20260823190000` 4's body, VERBATIM, with one sentence rewritten. R2 stands
-- and the board stays shut: taking a job off the pile is assignment by another
-- door, and leadership does not go through it.
--
-- What changed is what the refusal is *for*. On 2026-08-23 there was nowhere
-- else to send them, so the message could only close: "Supervisors and managers
-- cannot take up jobs from the board." Since section 2 there is somewhere,
-- and a refusal that names the working alternative is the difference between a
-- rule and a wall. It also stops using the phrase "take up" for the thing that
-- is refused while the thing that is allowed is called exactly that.
--
-- Same `HB403`, same branch, same position -- no new code, no new numbering.
-- The message is written as two adjacent literals so the line stays inside the
-- margin the rest of this directory keeps; SQL concatenates them, and the
-- sentence that reaches the supervisor is one sentence.
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
      raise exception 'Supervisors and managers cannot claim from the board. '
        'Use "Take this job myself" from your dashboard.'
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


-- The audiences. `create or replace` preserves the ACLs of the two functions
-- carried forward, so those two lines are a restatement -- an ACL nobody can
-- see in the file is an ACL nobody checks. The new function's grant is not a
-- restatement of anything: a function created without one is callable by
-- nobody, and PostgREST would answer 404 for a route that exists.
revoke all on function public.take_up_work_order(uuid, timestamptz, timestamptz)
  from public, anon, authenticated;
grant execute on function public.take_up_work_order(uuid, timestamptz, timestamptz)
  to authenticated;

grant execute on function public.force_assign_work_order(uuid, uuid, timestamptz, timestamptz)
  to authenticated;

revoke all on function public.claim_open_work_order(uuid)
  from public, anon, authenticated;
grant execute on function public.claim_open_work_order(uuid) to authenticated;

-- A new function IS a catalogue change, unlike the last two files that ended
-- this way: without the reload PostgREST answers `POST /rpc/take_up_work_order`
-- with a 404 until it next restarts, and the button reads as broken.
notify pgrst, 'reload schema';


-- ---------------------------------------------------------------------------
-- 5. Proof, in the same transaction -- and the post-checks that follow it
--
-- `20260823190000` 718-736's shape: each redefinition proved to be the one the
-- database now holds by looking for a string only this file's body contains. A
-- `create or replace` that silently lost its diff is the failure with no
-- symptom -- it looks exactly like a successful apply, and leaves the supervisor
-- pressing a button that answers HB403 or a timeline naming the wrong person.
-- ---------------------------------------------------------------------------
do $$
begin
  if to_regprocedure(
    'public.take_up_work_order(uuid,timestamptz,timestamptz)'
  ) is null then
    raise exception 'take_up_work_order missing';
  end if;
  if to_regprocedure(
    'public.force_assign_work_order(uuid,uuid,timestamptz,timestamptz)'
  ) is null then
    raise exception 'force_assign_work_order missing';
  end if;
  if to_regprocedure('public.claim_open_work_order(uuid)') is null then
    raise exception 'claim_open_work_order missing';
  end if;

  -- Section 2: the assignee is leadership on this department, and the caller.
  if position(
    'sa.rank in (''manager'', ''supervisor'')'
    in pg_get_functiondef(
      'public.take_up_work_order(uuid,timestamptz,timestamptz)'::regprocedure)
  ) = 0 then
    raise exception 'take_up_work_order does not restrict the holder to leadership';
  end if;
  if position(
    'v_actor, ''job_taken_up'''
    in pg_get_functiondef(
      'public.take_up_work_order(uuid,timestamptz,timestamptz)'::regprocedure)
  ) = 0 then
    raise exception 'take_up_work_order does not stamp the caller on the new word';
  end if;

  -- Section 3: R12. The old spelling must be gone, not merely joined.
  if position(
    'v_order.supervisor_membership_id, ''job_assigned'''
    in pg_get_functiondef(
      'public.force_assign_work_order(uuid,uuid,timestamptz,timestamptz)'::regprocedure)
  ) <> 0 then
    raise exception 'force_assign_work_order still stamps the standing supervisor';
  end if;
  if position(
    'v_actor, ''job_force_assigned'''
    in pg_get_functiondef(
      'public.force_assign_work_order(uuid,uuid,timestamptz,timestamptz)'::regprocedure)
  ) = 0 then
    raise exception 'force_assign_work_order did not take the resolved caller';
  end if;

  -- Section 4: R13, and R2 still standing underneath it.
  if position(
    'Take this job myself'
    in pg_get_functiondef('public.claim_open_work_order(uuid)'::regprocedure)
  ) = 0 then
    raise exception 'claim_open_work_order does not point leadership at the new verb';
  end if;
  if position(
    'sa.rank = ''member'''
    in pg_get_functiondef('public.claim_open_work_order(uuid)'::regprocedure)
  ) = 0 then
    raise exception 'claim_open_work_order lost the rank clause in the copy';
  end if;

  raise notice
    'supervisor_take_up: one new word, one new verb, and two bodies re-issued.';
end $$;


-- ---------------------------------------------------------------------------
-- Post-checks, to be run AFTER the transaction commits
--
-- Comment-only on purpose: these belong in the SQL editor's next tab, not in
-- the apply. Every one is a GUARD-FREE structural inspection -- no `auth.uid()`
-- (the editor has none, so `take_up_work_order` would answer HB403 and prove
-- nothing) and no `kind = 'service'` helper (this deployment's departments carry
-- kind NULL). Both bit us in runbook section 28. Runbook section 30 carries
-- them too.
--
--   -- (a) The new verb exists, with the frozen signature and one grant.
--   --     Expect one row: three arguments, uuid, security definer true.
--   select p.oid::regprocedure          as signature,
--          pg_get_function_result(p.oid) as returns,
--          p.prosecdef                   as security_definer,
--          array_to_string(p.proacl, ', ') as acl
--     from pg_proc p
--     join pg_namespace n on n.oid = p.pronamespace
--    where n.nspname = 'public'
--      and p.proname = 'take_up_work_order';
--
--   -- (b) The three assignment verbs, and who each stamps on the timeline.
--   --     Expect: take_up and force_assign both `stamps_caller` true and
--   --     `stamps_standing_supervisor` false; claim carries neither spelling
--   --     because it resolves its actor into a variable first, which is right.
--   select p.proname,
--          pg_get_functiondef(p.oid) like '%v_actor, ''job_%'
--            as stamps_caller,
--          pg_get_functiondef(p.oid) like '%v_order.supervisor_membership_id, ''job_%'
--            as stamps_standing_supervisor
--     from pg_proc p
--     join pg_namespace n on n.oid = p.pronamespace
--    where n.nspname = 'public'
--      and p.proname in ('take_up_work_order', 'force_assign_work_order',
--                        'claim_open_work_order')
--    order by 1;
--
--   -- (c) The board is still shut, and now says where the door is.
--   --     Expect one row, both true.
--   select pg_get_functiondef(p.oid) like '%sa.rank = ''member''%'
--            as board_still_member_only,
--          pg_get_functiondef(p.oid) like '%Take this job myself%'
--            as refusal_names_the_verb
--     from pg_proc p
--     join pg_namespace n on n.oid = p.pronamespace
--    where n.nspname = 'public'
--      and p.proname = 'claim_open_work_order';
--
--   -- (d) The vocabulary knows the new word and kept the old one.
--   --     Expect one row, both true.
--   select pg_get_constraintdef(oid) like '%job_taken_up%' as knows_job_taken_up,
--          pg_get_constraintdef(oid) like '%priority_changed%' as knows_priority
--     from pg_constraint
--    where conrelid = 'public.complaint_events'::regclass
--      and conname  = 'complaint_events_type_check';
--
--   -- (e) Nothing has been taken up yet, which is what a new word looks like
--   --     on the day it lands. Expect zero.
--   select count(*) as taken_up_jobs
--     from public.complaint_events
--    where event_type = 'job_taken_up';
-- ---------------------------------------------------------------------------
