-- 20260827210000_one_live_job_per_complaint.sql
--
-- One live job per complaint. Owner ruling (Lee, complaint-engine owner,
-- 2026-08-27), frozen in `docs/plans/ONE_LIVE_JOB_SPEC.md`.
--
-- **What went wrong.** Complaint `f40e11d4-e322-4847-be2f-8f2caf6df722`
-- collected a SECOND `awaiting_resident` work order fifteen seconds after the
-- resident booked the first one's visit. Nothing in the database said no: the
-- raise path has never asked whether a job on this complaint was already
-- running, and the triage screen draws its "Raise it" form from a jobs list it
-- has not finished reading. The resident is then holding two open requests for
-- one problem, `get_schedule_request` picks whichever live row it reaches
-- first, and the second visit is a technician's day spent on work the first one
-- already owns.
--
-- **The rule.** A complaint may carry several work orders over its life -- a
-- failed visit's replacement, a reopened complaint's new job -- but ONE AT A
-- TIME. The successor comes after the predecessor ends, never alongside it.
--
-- **LIVE** = `draft`, `awaiting_resident`, `offered`, `scheduled`,
-- `in_progress`: exactly the five that `work_orders_service._OPEN_STATES` calls
-- open and that the `get_schedule_request` resolver calls live. Terminal =
-- `completed`, `failed`, `cancelled`. The eight are the closed list
-- `work_orders_status_check` (`0036`) allows, so the two sets are exhaustive
-- and this file adds no ninth word.
--
-- **What this file does.** It `create or replace`s `public.create_work_order`
-- with the `20260823180000_resident_sets_the_time.sql` body -- same signature,
-- same G1 fork, same event word, same notification -- plus two additions and
-- nothing else:
--
--   1. The opening complaint read becomes `select * ... for update`. The guard
--      below is a read followed by a write, which is the shape that loses a
--      race: two supervisors (or one supervisor and one double-clicked button)
--      both read "no live job" and both insert. Locking the COMPLAINT row --
--      not the jobs, which is the empty set the guard is checking -- serializes
--      every raise against one complaint, so the second transaction reads the
--      first one's row and refuses. This is the lock
--      `resident_set_work_order_schedule` already takes on the job it is about
--      to move, for the same reason.
--   2. The refusal itself, after the department and community checks and after
--      the slot-shape checks, before the insert. It sits behind the argument
--      validation deliberately: a half-slot is the caller's own request being
--      malformed and deserves its 422, while this is a statement about the
--      world and deserves its 409. Either way it is in front of every write.
--
-- `HB409` is the existing conflict signal (`app/core/pg_errors.py` -> 409,
-- envelope `code: "conflict"`), not a new code. The message is the whole
-- explanation because the envelope carries it verbatim and the client renders
-- it; no client parses it.
--
-- **This file does not touch `complaints.status`, nor any complaint-lifecycle
-- code.** It guards the liveness of `work_orders` and nothing else.
--
-- **Existing duplicates are history and are left alone.** The guard refuses NEW
-- raises; it does not reach back. The leak complaint above already holds two
-- live jobs, and the extra `awaiting_resident` one
-- (`1f0bf129-d47d-4236-9082-ecf0a28b245c`) is the owner's to cancel from the
-- UI. A migration that cancelled rows by hand would be inventing a lifecycle
-- decision that belongs to a person.
--
-- Idempotent: one `create or replace function`, one `comment on function`, and
-- a closing `do` block that reads the installed definition back and raises if
-- what it claims to have done is not there. Hand-applied by the owner in the
-- Supabase SQL editor, like every file in this directory. Runbook section 32.

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
  -- CHANGED 20260827210000: `for update`. The one-live-job guard below reads
  -- the jobs of this complaint and then writes one, so without a lock two
  -- concurrent raises both read the empty answer. The complaint is the thing
  -- every raise on it has in common, so it is the thing to lock.
  select * into v_complaint from public.complaints where id = p_complaint_id
    for update;
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

  -- CHANGED 20260827210000: one live job per complaint.
  --
  -- The five states below are the live set, and the list is inline on purpose:
  -- it mirrors `work_orders_service._OPEN_STATES` exactly -- `draft`,
  -- `awaiting_resident`, `offered`, `scheduled`, `in_progress` -- the same five
  -- the `get_schedule_request` resolver calls live, with `completed`, `failed`
  -- and `cancelled` the terminal remainder of `work_orders_status_check`. A
  -- reader of this function sees the whole rule without following a helper, and
  -- if the Python tuple ever moves, this list moves in the same commit.
  --
  -- `exists`, not a count: the answer is a yes or a no, and the complaint row
  -- is already locked above so it cannot become stale between here and the
  -- insert.
  if exists (
    select 1
      from public.work_orders w
     where w.complaint_id = v_complaint.id
       and w.status in ('draft', 'awaiting_resident', 'offered',
                        'scheduled', 'in_progress')
  ) then
    raise exception
      'A job is already live on this complaint. Finish, fail, or cancel it before raising another.'
      using errcode = 'HB409';
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

comment on function public.create_work_order(
  uuid, uuid, uuid, text, text, timestamptz, timestamptz, text
) is
  'Raise one job against a complaint. A complaint carries several over its '
  'life and one at a time: the complaint row is locked for the duration and '
  'the raise is refused (HB409) while any job on it is still draft, '
  'awaiting_resident, offered, scheduled or in_progress -- the live set '
  'work_orders_service._OPEN_STATES names. Owner ruling 2026-08-27.';

-- ---------------------------------------------------------------------------
-- The function this file installed is the function it describes
--
-- Read back rather than assumed. `create or replace function` succeeds against
-- a body with no guard in it just as happily as against this one, so the only
-- proof that the apply did what the section above claims is to ask the database
-- for the definition it now holds. A half-pasted file cannot look like a
-- successful one.
--
-- The signature is spelled out because `create_work_order` is resolved by
-- argument list, and replacing an overload that is not the one the API calls
-- would leave the leak open with every check below passing.
-- ---------------------------------------------------------------------------

do $$
declare
  v_oid   oid := to_regprocedure(
    'public.create_work_order(uuid, uuid, uuid, text, text, timestamptz, '
    'timestamptz, text)'
  );
  v_def   text;
  v_state text;
begin
  if v_oid is null then
    raise exception
      'create_work_order is absent under the signature this file replaces';
  end if;

  v_def := pg_get_functiondef(v_oid);

  if position('for update' in v_def) = 0 then
    raise exception
      'create_work_order does not lock the complaint row -- the guard can race';
  end if;

  if position('A job is already live on this complaint.' in v_def) = 0 then
    raise exception 'create_work_order carries no live-job refusal';
  end if;

  if position('HB409' in v_def) = 0 then
    raise exception 'create_work_order raises the refusal without an errcode';
  end if;

  if position('w.complaint_id = v_complaint.id' in v_def) = 0 then
    raise exception 'the live-job guard is not scoped to this complaint';
  end if;

  foreach v_state in array array[
    'draft', 'awaiting_resident', 'offered', 'scheduled', 'in_progress'
  ] loop
    if position('''' || v_state || '''' in v_def) = 0 then
      raise exception 'the live set is missing %', v_state;
    end if;
  end loop;
end;
$$;
