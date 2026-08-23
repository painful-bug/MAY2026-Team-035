-- ---------------------------------------------------------------------------
-- 20260822170000_supervisor_actions.sql
--
-- Amendment 2 of the supervisor dashboard: the buttons on the cards.
--
-- WHAT PHASE ONE LEFT THE SUPERVISOR
--
-- `20260822120000` gave the supervisor a screen that *reads* -- four sections,
-- one round trip -- and exactly one verb, `take_up_complaint`. Everything else
-- they might want to do to a card meant leaving the page: resolving a complaint
-- was an admin's `update_complaint`, talking to the resident was nothing at all,
-- and "assign" was an offer the worker could decline. The four product rulings
-- of 2026-08-22 (`docs/plans/SUPERVISOR_TRIAGE_SPEC.md`, Amendment 2, A1-A4)
-- close that gap, and this file is their storage half.
--
--   * **A1 -- chat is a real thread.** Not a comments panel: a `complaint` kind
--     in the same `dm_threads` the dock already renders, between the resident who
--     raised it and the department that owns it.
--   * **A2 -- Resolved cancels unstarted jobs and blocks on started ones.**
--     A supervisor closing a complaint with a worker already inside somebody's
--     flat is the one case the button must refuse.
--   * **A3 -- open until accepted.** An offered-but-unaccepted job is *not*
--     assigned work; it is an open request nobody has answered, and it belongs in
--     its own section. This re-buckets the phase-one snapshot.
--   * **A4 -- manual assign is a true force-assign.** The supervisor's explicit
--     override of the consent model, through the engine's existing forced
--     mechanics rather than a second set of them.
--
-- THE LESSON OF 20260822150000, APPLIED IN ADVANCE
--
-- Phase one wrote `event_type = 'taken_up'` reasoning from `0001` 70 ("event_type
-- is text with no CHECK") and met `complaint_events_type_check` -- which
-- `20260813105000` 77 bolted on later -- as a live 23514 on the first press of
-- the button. **Any new complaint-event word costs a constraint drop-and-recreate**
-- (runbook 19). This amendment adds exactly one, `priority_changed`, and section
-- 7 below rebuilds the constraint in the same file, in the same shape
-- `20260822150000` used: guard first, drop, add, prove the new word.
--
-- `status_changed`, `note_added`, `job_assigned`, `job_cancelled` and
-- `job_force_assigned` -- the other five words written here -- are already in the
-- list. The static battery derives that claim from the constraint's own text
-- rather than taking this paragraph's word for it.
--
-- WHAT THIS FILE DOES NOT DO, AND WHY
--
--   * **It does not write the `status_changed` event or the resident's
--     notification when a complaint resolves.** `complaints_on_resolved`
--     (`20260813104000` 81) is an `after update of status` trigger that already
--     writes both, and enqueues the 48h warning and the 72h auto-close beside
--     them. `supervisor_resolve_complaint` moves the status, so the trigger fires
--     inside the same transaction and the resident is told once. Writing them
--     here as well would put two "Status changed to Resolved" lines on one
--     timeline and buzz one phone twice. Section 9 asserts the trigger exists:
--     if it does not, this file fails rather than shipping a resolve that tells
--     nobody. **This is the one place Amendment 2's wording ("writes
--     `status_changed`, notifies the raiser") is satisfied by an existing writer
--     instead of a new one.**
--   * **It does not add a `paused` status, a `resolved_by` column, or a second
--     notification topic for take-up.** Deferred in phase one for reasons that
--     have not changed.
--   * **It writes neither `complaints.assigned_to_membership_id` nor
--     `assignee_label`** (2026-08-21 ruling 1). Resolve, priority and notes are
--     all *triage*; who is going is still a work-order assignment.
--
-- IDEMPOTENT. `create or replace`, `add column if not exists`,
-- `create index if not exists`, `drop policy if exists` before every
-- `create policy`, `drop trigger if exists` before every `create trigger`, and a
-- constraint rebuilt by dropping it `if exists` first. The recovery from a
-- half-applied hand-run is to run the file again. Section 9 verifies the whole
-- thing in the same transaction and fails loudly rather than reporting a
-- half-success.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. The complaint thread (ruling A1)
--
-- `0046` built `dm_threads` around two shapes: a `direct` pair, and a
-- `work_order` channel that carries its job's id and locks when the job ends.
-- A complaint chat is the second shape with a different subject, so it is a
-- third `kind` rather than a third table -- the dock, the mailbox view, the
-- unread counts and `post_dm_message` all keep working on a row they already
-- know how to render.
--
-- `complaint_id` is `on delete cascade` and not `set null`, and the choice is
-- forced rather than aesthetic: `dm_threads_complaint_subject_check` below makes
-- `kind = 'complaint'` and a non-null `complaint_id` the same fact, so nulling
-- the column would raise 23514 and refuse to delete the complaint at all. It is
-- also what `work_order_id` already does two columns above, for the same reason:
-- a conversation *about* something that no longer exists is not history anybody
-- can read.
--
-- The unique index is unconditional on `locked_at`, unlike the job thread's.
-- A job never leaves a terminal status, so `0046` could let a locked thread be
-- replaced; a complaint **can** be reopened, and a resident who reopens should
-- find the conversation they were already having rather than a second empty one.
-- The lock trigger in section 2 therefore *unlocks* on the way back out.
-- ---------------------------------------------------------------------------

alter table public.dm_threads
  add column if not exists complaint_id uuid
    references public.complaints(id) on delete cascade;

comment on column public.dm_threads.complaint_id is
  'The complaint this thread is about, for kind = ''complaint'' (2026-08-22 ruling A1). One thread per complaint, shared by the raiser and the department''s supervisors.';

-- Nothing already stored may be outside the new vocabulary, or the ADD would
-- fail with the old constraint already dropped. Checked first, so a failure here
-- leaves `dm_threads_kind_check` standing exactly as it is.
do $$
declare v_bad text;
begin
  select kind into v_bad from public.dm_threads
   where kind not in ('direct', 'work_order', 'complaint') limit 1;
  if v_bad is not null then
    raise exception 'Unknown existing dm thread kind: %', v_bad;
  end if;
end $$;

alter table public.dm_threads drop constraint if exists dm_threads_kind_check;
alter table public.dm_threads add constraint dm_threads_kind_check
  check (kind in ('direct', 'work_order', 'complaint'));

do $$
begin
  -- A complaint thread names its complaint; the other two kinds do not. The
  -- mirror of `dm_threads_subject_check` (`0046` 94), which is left untouched --
  -- it says `(kind = 'work_order') = (work_order_id is not null)`, and a
  -- complaint thread satisfies it by having neither.
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.dm_threads'::regclass
                    and conname  = 'dm_threads_complaint_subject_check') then
    alter table public.dm_threads
      add constraint dm_threads_complaint_subject_check
      check ((kind = 'complaint') = (complaint_id is not null));
  end if;
end $$;

create unique index if not exists dm_threads_one_per_complaint
  on public.dm_threads (complaint_id)
  where kind = 'complaint';


-- ---------------------------------------------------------------------------
-- 2. The lock, and its one difference from the job thread's
--
-- `lock_work_order_threads` (`0046` 466) is the model: a terminal subject stamps
-- `locked_at`, `post_dm_message` refuses a locked thread with `HB409`, and the
-- transcript stays readable because history that vanishes is not documentation.
--
-- The difference is the `else` arm. A complaint that was `closed` can be
-- reopened by the resident (`reopen_complaint`, `0031` 6), and a channel that
-- stayed shut after that would be a resident with a live complaint and a chat
-- that refuses them for a reason nobody could see. So terminal locks and
-- non-terminal unlocks, and the system line is written once ever rather than
-- once per closing.
-- ---------------------------------------------------------------------------

create or replace function public.lock_complaint_threads()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'UPDATE' and old.status is not distinct from new.status then
    return null;
  end if;

  if new.status in ('closed', 'cancelled') then
    update public.dm_threads
       set locked_at = coalesce(locked_at, now())
     where complaint_id = new.id
       and kind = 'complaint'
       and locked_at is null;

    insert into public.dm_messages (thread_id, author_profile_id, body)
    select t.id, null,
           'This complaint was ' || new.status::text
             || '. This conversation is closed.'
      from public.dm_threads t
     where t.complaint_id = new.id
       and t.kind = 'complaint'
       and t.locked_at is not null
       and not exists (
         select 1 from public.dm_messages m
          where m.thread_id = t.id
            and m.author_profile_id is null
            and m.body like 'This complaint was %'
       );
  else
    -- Reopened, or moved back out of a terminal status by any other writer.
    update public.dm_threads
       set locked_at = null
     where complaint_id = new.id
       and kind = 'complaint'
       and locked_at is not null;
  end if;
  return null;
end;
$$;

drop trigger if exists complaints_lock_dm_threads on public.complaints;
create trigger complaints_lock_dm_threads
  after insert or update of status on public.complaints
  for each row execute function public.lock_complaint_threads();

comment on function public.lock_complaint_threads() is
  'The job-thread lock (0046), for complaints: closed or cancelled shuts the channel and says so in it; anything else opens it again, because a complaint can be reopened and a job cannot.';


-- ---------------------------------------------------------------------------
-- 3. Who may read and write a complaint thread
--
-- A `direct` thread has two participants and they are the whole rule. A
-- complaint thread has two participant *rows* -- the raiser and whichever
-- supervisor pressed the button first -- and a wider rule, because Amendment 2
-- says a later supervisor of the same department **joins the existing thread
-- rather than forking a second one**. With one pair of columns, "joins" cannot
-- mean a third row; it means the department is a participant and the stored pair
-- is only who has spoken so far.
--
-- `can_supervise_complaint` is that rule, once, `security definer` so it can be
-- asked from an RLS policy without depending on whether the caller can select
-- the complaint by any other route. The two policies below and
-- `post_dm_message`'s copy in section 4 all ask it, so read access and write
-- access cannot drift apart.
-- ---------------------------------------------------------------------------

create or replace function public.can_supervise_complaint(p_complaint_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
      from public.complaints c
     where c.id = p_complaint_id
       and c.department_id is not null
       and public.can_supervise_department(c.department_id)
  );
$$;

comment on function public.can_supervise_complaint(uuid) is
  'True when the caller supervises the department this complaint belongs to. can_supervise_department, resolved through the complaint, so a policy can ask it about a thread.';

drop policy if exists dm_threads_read on public.dm_threads;
create policy dm_threads_read on public.dm_threads
  for select to authenticated
  using (
    participant_a_profile_id = auth.uid()
    or participant_b_profile_id = auth.uid()
    or (kind = 'complaint'
        and public.can_supervise_complaint(complaint_id))
  );

drop policy if exists dm_messages_read on public.dm_messages;
create policy dm_messages_read on public.dm_messages
  for select to authenticated
  using (
    exists (
      select 1 from public.dm_threads t
       where t.id = dm_messages.thread_id
         and (t.participant_a_profile_id = auth.uid()
              or t.participant_b_profile_id = auth.uid()
              or (t.kind = 'complaint'
                  and public.can_supervise_complaint(t.complaint_id)))
    )
  );


-- ---------------------------------------------------------------------------
-- 4. `post_dm_message`, copied forward for the department (ruling A1)
--
-- `0046` 396's body, whole, under the house convention for changing somebody
-- else's function (`20260812113000` 1): every line of the owning file's version
-- is present below verbatim, and what is new is three added blocks, each marked.
-- `tests/test_supervisor_actions_migration.py` compares the two bodies line by
-- line and fails on anything lost.
--
-- What is added and why:
--
--   1. the participation test admits a supervisor of the complaint's department.
--      Without it the *second* supervisor to open a card gets `HB404 No such
--      conversation` on a thread their own department owns;
--   2. the notification goes to the resident when the writer is that supervisor.
--      `v_other` is derived from the stored pair, and a writer who is in neither
--      column would otherwise send the resident's own line to the resident;
--   3. the name on that notification is the writer's, for the same reason.
--
-- Everything else -- the 1-4000 length check, the `HB404` that hides other
-- people's threads, the `HB409` lock, `last_message_at`, the `notify_profile` --
-- is `0046`'s and is reproduced unchanged. The lock in particular is the whole of
-- Amendment 2's write-locking requirement: a `closed` or `cancelled` complaint
-- stamps `locked_at` in section 2, and this function was already refusing that.
-- ---------------------------------------------------------------------------

create or replace function public.post_dm_message(
  p_thread_id uuid,
  p_body      text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_thread public.dm_threads%rowtype;
  v_id     uuid;
  v_other  uuid;
  v_name   text;
  -- ADDED (20260822170000): is the writer here as the department rather than as
  -- one of the two stored participants?
  v_as_department boolean := false;
begin
  if auth.uid() is null then
    raise exception 'Sign in required.' using errcode = '42501';
  end if;
  if coalesce(length(btrim(p_body)), 0) not between 1 and 4000 then
    raise exception 'A message is between 1 and 4000 characters.'
      using errcode = '22004';
  end if;

  select * into v_thread from public.dm_threads where id = p_thread_id;

  -- ADDED (20260822170000, ruling A1): a complaint thread belongs to the
  -- department as well as to the two people in its columns, so a supervisor who
  -- arrived after it was opened may write in it. Asked as an `if` and against
  -- `v_thread.id` rather than `found`, so that the `if not found` below is still
  -- reading the SELECT's own result and not this test's.
  if v_thread.id is not null
     and v_thread.kind = 'complaint'
     and auth.uid() not in (v_thread.participant_a_profile_id,
                            v_thread.participant_b_profile_id)
     and public.can_supervise_complaint(v_thread.complaint_id) then
    v_as_department := true;
  end if;

  if not found
     or auth.uid() not in (v_thread.participant_a_profile_id,
                           v_thread.participant_b_profile_id) then
    -- ADDED (20260822170000): the refusal is conditional now, and the line below
    -- keeps its original indentation so this copy is provably additive rather
    -- than additive-looking -- the same reason phase one wrote its added
    -- assignments leading-comma style.
    --
    -- The condition is restated from the row rather than from `found`, and on
    -- purpose: this inner test is the one that decides, so the outer `if` above
    -- can only ever bring us here to be asked again. Whatever `found` says after
    -- the block above it, a participant is never refused their own thread and a
    -- stranger is never let into somebody else's.
    if v_thread.id is null
       or (not v_as_department
           and auth.uid() not in (v_thread.participant_a_profile_id,
                                  v_thread.participant_b_profile_id)) then
    -- One error for missing and for not-yours: a stranger probing thread ids
    -- learns nothing from the difference.
    raise exception 'No such conversation.' using errcode = 'HB404';
    end if;
  end if;

  -- The protection the ruling asked for: the job ended, the channel ended.
  if v_thread.locked_at is not null then
    raise exception 'This conversation is closed.' using errcode = 'HB409';
  end if;

  insert into public.dm_messages (thread_id, author_profile_id, body)
  values (p_thread_id, auth.uid(), btrim(p_body))
  returning id into v_id;

  update public.dm_threads
     set last_message_at = now()
   where id = p_thread_id;

  v_other := case when auth.uid() = v_thread.participant_a_profile_id
                  then v_thread.participant_b_profile_id
                  else v_thread.participant_a_profile_id end;
  v_name  := case when auth.uid() = v_thread.participant_a_profile_id
                  then v_thread.participant_a_name
                  else v_thread.participant_b_name end;

  -- ADDED (20260822170000): the two lines above read the pair, and a supervisor
  -- writing as the department is in neither column -- so without this the
  -- resident's own message would be delivered to the resident, under the
  -- resident's own name.
  if v_as_department then
    select m.profile_id into v_other
      from public.complaints c
      join public.community_memberships m on m.id = c.raised_by_membership_id
     where c.id = v_thread.complaint_id;
    select coalesce(p.full_name, p.display_email::text, 'The department')
      into v_name
      from public.profiles p where p.id = auth.uid();
  end if;

  if v_other is not null then
  perform public.notify_profile(
    v_other, 'dm.message',
    jsonb_build_object(
      'title', coalesce(v_name, 'Someone') || ' sent you a message',
      'body', left(btrim(p_body), 140),
      'threadId', p_thread_id));
  end if;

  return v_id;
end;
$$;

comment on function public.post_dm_message(uuid, text) is
  'Append to a thread the caller is in -- or, since 2026-08-22, one their department owns. HB404 hides other people''s threads; HB409 is the lock, and a closed or cancelled complaint closes its channel like a finished job does.';


-- ---------------------------------------------------------------------------
-- 5. The four complaint verbs
--
-- All four ask `can_supervise_department` and none of them asks anything else:
-- the router's role guard is coarse on purpose (a supervisor holds a `worker`
-- membership -- rank is not role, `0035`), and this is the boundary.
--
-- All four refuse a complaint with **no department** as `HB409` and not `HB403`,
-- the call phase one made and the orchestrator ratified: there is no department
-- to supervise, so refusing it as an authorization failure would tell a
-- supervisor they lack a permission when what is missing is the routing.
-- ---------------------------------------------------------------------------

-- 5a. Resolve (ruling A2)
--
-- The refusal first, because it is the reason this is not `update_complaint`
-- with a different guard: a job that is `in_progress` means somebody is inside a
-- resident's flat right now, and a complaint marked resolved underneath them
-- would cancel nothing, tell nobody and leave a worker holding a job against a
-- closed complaint. So `HB409`, naming the two ways out.
--
-- Then the cancellations. Every *other* live job -- `draft`,
-- `awaiting_resident`, `offered`, `scheduled` -- is called off, its `offered` and
-- `accepted` assignment rows withdrawn (never deleted: one holder at a time, and
-- the history of who was booked and unbooked survives), and every affected worker
-- told why. The reason is frozen copy: "Complaint resolved by the department".
--
-- Then the status. `resolved`, not `closed`: `closed` is what the *resident*
-- says by confirming (`confirm_complaint_resolution`, `0031` 7), and the whole
-- 48h-warning / 72h-auto-close aftermath hangs off `resolved`. Which is also why
-- nothing here writes a `status_changed` event or notifies the raiser --
-- `complaints_on_resolved` (`20260813104000` 81) does both, plus the two timers,
-- and it fires on this update. Doing it here as well would say it twice.
create or replace function public.supervisor_resolve_complaint(p_complaint_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_complaint public.complaints%rowtype;
  v_actor     uuid;
  v_order     record;
  v_assign    record;
  v_reason    text := 'Complaint resolved by the department';
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

  if v_complaint.status in ('resolved', 'closed') then
    raise exception 'This complaint has already been resolved.'
      using errcode = 'HB409';
  end if;
  if v_complaint.status = 'cancelled' then
    raise exception 'This complaint was cancelled.' using errcode = 'HB409';
  end if;

  if exists (
    select 1 from public.work_orders w
     where w.complaint_id = p_complaint_id
       and w.status = 'in_progress'
  ) then
    raise exception
      'Somebody is working on this right now. Finish or cancel the running job first.'
      using errcode = 'HB409';
  end if;

  select m.id into v_actor
    from public.community_memberships m
   where m.community_id = v_complaint.community_id
     and m.profile_id   = auth.uid()
     and m.status       = 'active'
     and m.ended_at is null;

  for v_order in
    select w.id
      from public.work_orders w
     where w.complaint_id = p_complaint_id
       and w.status in ('draft', 'awaiting_resident', 'offered', 'scheduled')
     for update
  loop
    for v_assign in
      select a.id, sa.membership_id
        from public.work_order_assignments a
        left join public.staff_assignments sa on sa.id = a.staff_assignment_id
       where a.work_order_id = v_order.id
         and a.status in ('offered', 'accepted')
    loop
      update public.work_order_assignments
         set status = 'withdrawn', responded_at = now(), ended_at = now()
       where id = v_assign.id;

      if v_assign.membership_id is not null then
        perform public.notify_member(
          v_assign.membership_id, 'job.cancelled',
          jsonb_build_object(
            'title', 'A job of yours was cancelled',
            'body', v_reason,
            'url', '/worker?job=' || v_order.id::text,
            'work_order_id', v_order.id,
            'complaint_id', p_complaint_id,
            'reason', v_reason));
      end if;
    end loop;

    update public.work_orders
       set status               = 'cancelled',
           cancelled_by         = 'staff',
           cancelled_reason     = v_reason,
           resident_deadline_at = null,
           updated_at           = now()
     where id = v_order.id;

    insert into public.complaint_events
      (complaint_id, actor_membership_id, event_type, payload)
    values (
      p_complaint_id, v_actor, 'job_cancelled',
      jsonb_build_object('workOrderId', v_order.id, 'reason', v_reason)
    );
  end loop;

  update public.complaints
     set status            = 'resolved',
         resolved_at       = coalesce(resolved_at, now()),
         progress_percent  = 100,
         aggregate_version = aggregate_version + 1,
         updated_at        = now()
   where id = p_complaint_id;
end;
$$;

comment on function public.supervisor_resolve_complaint(uuid) is
  'The department saying the work is done: refuses while a job is in progress, calls off every other live job with its workers told why, and moves the complaint to resolved -- from where the resident confirms it, reopens it, or the 72h timer closes it.';


-- 5b. Raise the priority
--
-- One way only: `low -> medium -> high`, and `HB409` at the top. A supervisor
-- who could lower it could quietly un-escalate a complaint somebody escalated,
-- which is a decision worth a different verb and a different audit line than
-- this button carries.
--
-- **Priority is load-bearing and this is deliberate.** `high` is what arms
-- `decline_work_order_offer`'s automatic force-assign when every candidate has
-- said no (`20260813101000` 152), and what shortens the manual dispatch window
-- from 24 hours to 2 (`20260813104000` 39). The live work orders are moved with
-- the complaint for the same reason `create_work_order` never took a priority
-- argument: a job's urgency *is* its complaint's urgency, and a second copy that
-- disagrees is a dispatcher acting on the old answer.
--
-- The SLA deadline is **not** recomputed. `expected_resolution_at` is a promise
-- already made to the resident; moving it because the department reclassified
-- the work would make a complaint overdue for a reason the resident never saw.
create or replace function public.raise_complaint_priority(p_complaint_id uuid)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_complaint public.complaints%rowtype;
  v_actor     uuid;
  v_to        text;
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

  v_to := case coalesce(v_complaint.priority, 'low')
            when 'low'    then 'medium'
            when 'medium' then 'high'
            else null
          end;
  if v_to is null then
    raise exception 'This complaint is already at the highest priority.'
      using errcode = 'HB409';
  end if;

  select m.id into v_actor
    from public.community_memberships m
   where m.community_id = v_complaint.community_id
     and m.profile_id   = auth.uid()
     and m.status       = 'active'
     and m.ended_at is null;

  update public.complaints
     set priority          = v_to,
         aggregate_version = aggregate_version + 1,
         updated_at        = now()
   where id = p_complaint_id;

  update public.work_orders
     set priority   = v_to,
         updated_at = now()
   where complaint_id = p_complaint_id
     and status not in ('completed', 'cancelled', 'failed');

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    p_complaint_id, v_actor, 'priority_changed',
    jsonb_build_object(
      'from', coalesce(v_complaint.priority, 'low'),
      'to',   v_to)
  );

  return v_to;
end;
$$;

comment on function public.raise_complaint_priority(uuid) is
  'One-way escalation, low -> medium -> high, carried onto the complaint''s live jobs because a job''s urgency is its complaint''s. HB409 at the top. No notification: a field changing with no action attached is the passive change ARCHITECTURE.md suppresses.';


-- 5c. The internal note (ruling A5)
--
-- The product owner's phrasing for who reads these enumerated staff and workers
-- and did not include the resident, so the note is internal -- and the flag is in
-- the payload rather than in a new event word, because `note_added` already
-- exists, already renders on the staff timeline with its author, and a second
-- word would have cost the constraint rebuild in section 7 twice over.
-- `resident_complaints_service` drops `note_added` rows carrying
-- `internal: true`; the admin's resident-visible notes (`update_complaint`'s
-- `p_update_note`) carry no such flag and are untouched.
--
-- Append-only. There is no edit and no delete, which is what makes a timeline
-- worth reading back.
create or replace function public.add_complaint_note_internal(
  p_complaint_id uuid,
  p_note         text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_complaint public.complaints%rowtype;
  v_actor     uuid;
  v_label     text;
  v_note      text := nullif(btrim(coalesce(p_note, '')), '');
  v_id        uuid;
begin
  select * into v_complaint from public.complaints where id = p_complaint_id;
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

  if v_note is null or length(v_note) > 2000 then
    raise exception 'A note is between 1 and 2000 characters.'
      using errcode = 'HB422';
  end if;

  select m.id, coalesce(p.full_name, 'The department')
    into v_actor, v_label
    from public.community_memberships m
    left join public.profiles p on p.id = m.profile_id
   where m.community_id = v_complaint.community_id
     and m.profile_id   = auth.uid()
     and m.status       = 'active'
     and m.ended_at is null;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, actor_label, event_type, payload)
  values (
    p_complaint_id, v_actor, coalesce(v_label, 'The department'), 'note_added',
    jsonb_build_object('note', v_note, 'internal', true)
  )
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.add_complaint_note_internal(uuid, text) is
  'A permanent internal note on a complaint''s timeline: staff and workers read it, the resident does not (payload internal = true). Append-only.';


-- 5d. Open (or get) the complaint's chat thread (ruling A1)
--
-- Open-or-get, like `open_direct_thread` and `open_work_order_thread` before it,
-- and for the same reason: a client calls this every time the button is pressed
-- rather than remembering what it opened last time.
--
-- The existing-thread lookup happens **before** the pair is resolved, because
-- that is what "a later supervisor joins the existing thread" means -- the second
-- supervisor gets the thread that is already there, with the first one's name
-- still in the column and their own right to write it coming from section 3
-- rather than from the row.
--
-- The complaint row is locked first, so two supervisors pressing at the same
-- moment produce one thread and one winner rather than a unique-violation.
create or replace function public.open_complaint_thread(p_complaint_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_complaint public.complaints%rowtype;
  v_resident  uuid;
  v_a uuid; v_b uuid;
  v_a_name text; v_b_name text;
  v_id uuid;
begin
  if auth.uid() is null then
    raise exception 'Sign in required.' using errcode = '42501';
  end if;

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

  select t.id into v_id
    from public.dm_threads t
   where t.complaint_id = p_complaint_id
     and t.kind = 'complaint'
   limit 1;
  if v_id is not null then
    return v_id;
  end if;

  select m.profile_id into v_resident
    from public.community_memberships m
   where m.id = v_complaint.raised_by_membership_id;

  if v_resident is null then
    raise exception 'This complaint has nobody to talk to.'
      using errcode = 'HB409';
  end if;
  if v_resident = auth.uid() then
    raise exception 'This is your own complaint -- use your resident screen.'
      using errcode = 'HB409';
  end if;

  v_a := least(v_resident, auth.uid());
  v_b := greatest(v_resident, auth.uid());
  select coalesce(full_name, display_email::text, 'Someone') into v_a_name
    from public.profiles where id = v_a;
  select coalesce(full_name, display_email::text, 'Someone') into v_b_name
    from public.profiles where id = v_b;

  insert into public.dm_threads (
    community_id, kind, complaint_id,
    participant_a_profile_id, participant_b_profile_id,
    participant_a_name, participant_b_name, locked_at
  )
  values (
    v_complaint.community_id, 'complaint', p_complaint_id, v_a, v_b,
    coalesce(v_a_name, 'Someone'), coalesce(v_b_name, 'Someone'),
    -- A thread opened on an already-settled complaint is history from the start:
    -- readable, and refusing writes exactly as section 2 would have made it.
    case when v_complaint.status in ('closed', 'cancelled') then now() end
  )
  returning id into v_id;

  insert into public.dm_messages (thread_id, author_profile_id, body)
  values (
    v_id, null,
    'The department opened this chat about '''
      || coalesce(nullif(btrim(v_complaint.title), ''), 'this complaint')
      || '''.'
  );
  update public.dm_threads set last_message_at = now() where id = v_id;

  return v_id;
end;
$$;

comment on function public.open_complaint_thread(uuid) is
  'One chat per complaint, between the resident who raised it and the department that owns it. Open-or-get: a later supervisor joins the thread that exists rather than forking a second one.';


-- ---------------------------------------------------------------------------
-- 6. Force-assign, by hand (ruling A4)
--
-- `dispatch_force_assign` (`20260813101000` 101) is the model and is deliberately
-- left alone: it *picks* the worker, which is the half a supervisor pressing
-- "Assign" is replacing. What this keeps is everything after the pick -- the
-- `is_forced` accepted assignment, both timeline events, the worker
-- notification, the staff notice, and the resident being told somebody is coming
-- -- because a forced assignment that behaved differently depending on who
-- forced it would be two mechanisms wearing one name.
--
-- What it adds is the guard. The dispatcher runs with no request claims and
-- checks nothing; this is a person, so it asks `can_supervise_department` on the
-- work order's own department and refuses a roster row from anywhere else.
--
-- `is_auto_assigned` stays **false**. The column is what the worker's card reads
-- to say who decided; the dispatcher deciding and a supervisor overriding are not
-- the same sentence.
--
-- The two optional slot parameters keep the offer flow's shape ("the slot is
-- optional and defaults to the job's own"), so a supervisor who picked the person
-- and the hour in one gesture does not need a second call. Both default to null,
-- so the frozen two-argument call is exactly this function.
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
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such work order.' using errcode = 'HB404';
  end if;

  if not public.can_supervise_department(v_order.department_id) then
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
    (v_order.complaint_id, v_order.supervisor_membership_id, 'job_assigned',
     jsonb_build_object('workOrderId', v_order.id,
                        'assigneeName', v_staff.display_name, 'forced', true)),
    (v_order.complaint_id, v_order.supervisor_membership_id, 'job_force_assigned',
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
-- 7. The event vocabulary gains exactly one word
--
-- `priority_changed`, written by 5b. The shape is `20260822150000`'s, which is
-- `20260813105000`'s: prove nothing stored is outside the new list *before*
-- dropping anything, so a failure here leaves the old constraint standing; then
-- drop, add, and prove the new word specifically -- a bare existence check would
-- pass against the very constraint being replaced.
--
-- Widening only. Every word the old constraint accepted is in the list below,
-- and `tests/test_supervisor_actions_migration.py` derives that list from
-- `20260822150000`'s own text rather than reviewing it by eye.
-- ---------------------------------------------------------------------------

do $$
declare v_bad text;
begin
  select event_type into v_bad from public.complaint_events where event_type not in (
    'raised','status_changed','assigned','progress_changed','due_date_changed','note_added','comment_added','reopened','resolution_confirmed',
    'job_created','job_scheduled','job_declined','job_assigned','job_cancelled','job_started','job_completed','job_failed',
    'department_assigned','department_change_requested','department_change_accepted','department_change_rejected',
    'job_force_assigned','returned_to_pool','auto_close_warning','auto_closed','taken_up','priority_changed') limit 1;
  if v_bad is not null then raise exception 'Unknown existing complaint event type: %', v_bad; end if;
end $$;

alter table public.complaint_events drop constraint if exists complaint_events_type_check;
alter table public.complaint_events add constraint complaint_events_type_check check (event_type in (
  'raised','status_changed','assigned','progress_changed','due_date_changed','note_added','comment_added','reopened','resolution_confirmed',
  'job_created','job_scheduled','job_declined','job_assigned','job_cancelled','job_started','job_completed','job_failed',
  'department_assigned','department_change_requested','department_change_accepted','department_change_rejected',
  'job_force_assigned','returned_to_pool','auto_close_warning','auto_closed','taken_up','priority_changed'));

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.complaint_events'::regclass
      and conname  = 'complaint_events_type_check'
      and pg_get_constraintdef(oid) like '%priority_changed%'
  ) then raise exception 'complaint event type check missing or does not allow priority_changed'; end if;
end $$;


-- ---------------------------------------------------------------------------
-- 8. The snapshot, re-bucketed into five sections (ruling A3)
--
-- Dropped and recreated rather than replaced, because this is a different answer
-- to the same question and the old one should not be reachable by any caller who
-- missed the change.
--
-- What moved, and it is one word: *engaged* became **committed**. An offered job
-- nobody has accepted is not assigned work -- it is an open request, and the
-- supervisor's question about it ("is anybody going to take this?") is a
-- different question from the one section 4 answers ("is Ravi going to turn
-- up?"). So:
--
--   * *live*            -- status not in `completed | failed | cancelled`;
--   * *committed*       -- a live work order with an `accepted` assignment, or
--                          work-order status `scheduled`;
--   * `new_complaints`  -- status `open`, no take-up, **and no live work order**;
--   * `taken_up`        -- stamped, status `open|acknowledged`, no live work order;
--   * `open_requests`   -- live, not committed: `draft|awaiting_resident|offered`;
--   * `assigned_pending`-- live, committed, status <> `in_progress`;
--   * `in_progress`     -- status `in_progress`.
--
-- **Furthest stage wins**, and the two complaint sections now say so by
-- excluding any live work order rather than only an engaged one: a complaint
-- whose job exists appears once, as that job, in whichever of sections 3-5 the
-- job has reached. Exactly one card per complaint chain.
--
-- `offered_to_name` is the new projection and the reason section 3 can say
-- "Offered to Ravi, awaiting acceptance". It is the *pending offer*, and
-- `assignee_name` is now the *accepted* holder only -- two fields because the two
-- facts are different and a card that showed a name without saying which one it
-- was would read as "Ravi is coming" when Ravi has not answered.
--
-- Everything else is phase one's, including the vocabulary: `priority` and
-- `status` go out as stored, because `app/domain/vocabularies.py` is the one
-- place this codebase translates one.
-- ---------------------------------------------------------------------------

drop function if exists public.supervisor_triage_snapshot(uuid);

create function public.supervisor_triage_snapshot(p_department_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_new      jsonb;
  v_taken    jsonb;
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
      -- The accepted holder, and nobody else. `assignee_name` used to fall back
      -- to an open offer; ruling A3 makes that a different fact with its own
      -- field, because a card showing one name for both would say "Ravi is
      -- coming" about a job Ravi has not answered.
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
      -- `committed`: somebody has said yes, or the job is booked. Asked as an
      -- EXISTS on the assignment rather than from the name above, because a
      -- roster row can be deleted out from under an assignment
      -- (`staff_assignment_id` is `on delete set null` in `0001`) and a job
      -- somebody accepted is still accepted when their row has gone.
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
                 and wr.status in ('draft', 'awaiting_resident', 'offered')) sec
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
  into v_new, v_taken, v_open, v_pending, v_progress;

  return jsonb_build_object(
    'department_id',    p_department_id,
    'new_complaints',   v_new,
    'taken_up',         v_taken,
    'open_requests',    v_open,
    'assigned_pending', v_pending,
    'in_progress',      v_progress
  );
end;
$$;

comment on function public.supervisor_triage_snapshot(uuid) is
  'The supervisor dashboard''s five sections in one read: new complaints, taken up, open job requests nobody has accepted, assigned and waiting, and being worked right now. A read — it moves nothing and notifies nobody.';


-- ---------------------------------------------------------------------------
-- 9. Grants
--
-- `authenticated` on everything a person calls, because every one of them
-- resolves the caller from `auth.uid()` and refuses a stranger itself -- the
-- posture `0036` 6 and `0046` 7 both take. The snapshot's grant is not optional
-- housekeeping: section 8 **dropped** it, and a dropped function takes its ACL
-- with it.
--
-- The trigger function is granted to nobody: it runs as the trigger's owner and
-- has no business being callable.
-- ---------------------------------------------------------------------------

grant execute on function public.can_supervise_complaint(uuid) to authenticated;
grant execute on function public.supervisor_triage_snapshot(uuid) to authenticated;
grant execute on function public.supervisor_resolve_complaint(uuid) to authenticated;
grant execute on function public.raise_complaint_priority(uuid) to authenticated;
grant execute on function public.add_complaint_note_internal(uuid, text) to authenticated;
grant execute on function public.open_complaint_thread(uuid) to authenticated;
grant execute on function public.force_assign_work_order(uuid, uuid, timestamptz, timestamptz)
  to authenticated;

revoke all on function public.post_dm_message(uuid, text)
  from public, anon, authenticated;
grant execute on function public.post_dm_message(uuid, text) to authenticated;

revoke all on function public.lock_complaint_threads()
  from public, anon, authenticated;


-- ---------------------------------------------------------------------------
-- 10. Verification, in the same transaction as the change
--
-- `20260822090000` 2's shape. Nothing below writes anything, and the two checks
-- that matter most are the last two: a `create or replace` that lost the
-- department clause from `post_dm_message` would leave a chat button that opens a
-- thread the second supervisor cannot write in, and a missing
-- `complaints_on_resolved` would leave a Resolve button that tells the resident
-- nothing -- neither of which errors anywhere.
-- ---------------------------------------------------------------------------

do $$
declare
  v_missing text;
  v_src     text;
begin
  if not exists (
    select 1 from information_schema.columns c
     where c.table_schema = 'public'
       and c.table_name   = 'dm_threads'
       and c.column_name  = 'complaint_id'
  ) then
    raise exception 'supervisor_actions: dm_threads.complaint_id was not added.';
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.dm_threads'::regclass
       and conname  = 'dm_threads_kind_check'
       and pg_get_constraintdef(oid) like '%complaint%'
  ) then
    raise exception 'supervisor_actions: dm_threads_kind_check does not allow complaint threads.';
  end if;

  if not exists (
    select 1 from pg_indexes
     where schemaname = 'public' and indexname = 'dm_threads_one_per_complaint'
  ) then
    raise exception 'supervisor_actions: the one-thread-per-complaint index is missing.';
  end if;

  select string_agg(name, ', ' order by name) into v_missing
    from (values
      ('supervisor_resolve_complaint'),
      ('raise_complaint_priority'),
      ('add_complaint_note_internal'),
      ('open_complaint_thread'),
      ('force_assign_work_order'),
      ('can_supervise_complaint'),
      ('lock_complaint_threads'),
      ('supervisor_triage_snapshot'),
      ('post_dm_message')
    ) as wanted(name)
   where not exists (
     select 1 from pg_proc
      where pronamespace = 'public'::regnamespace and proname = wanted.name
   );
  if v_missing is not null then
    raise exception 'supervisor_actions: these functions are not declared: %', v_missing;
  end if;

  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace and proname = 'supervisor_triage_snapshot';
  if v_src not like '%open_requests%' or v_src not like '%offered_to_name%' then
    raise exception
      'supervisor_actions: the snapshot is not the five-section version. An older definition won.';
  end if;

  select prosrc into v_src
    from pg_proc
   where pronamespace = 'public'::regnamespace and proname = 'post_dm_message';
  if v_src not like '%can_supervise_complaint%' then
    raise exception
      'supervisor_actions: post_dm_message does not admit the department. An older definition won.';
  end if;
  if v_src not like '%This conversation is closed.%' then
    raise exception
      'supervisor_actions: post_dm_message lost the lock in the copy.';
  end if;

  -- The resolve verb writes no status_changed event and notifies nobody itself,
  -- because this trigger does both and enqueues the two auto-close timers. If it
  -- is not here, Resolve would silently tell the resident nothing.
  if not exists (
    select 1 from pg_trigger
     where tgrelid = 'public.complaints'::regclass
       and tgname  = 'complaints_on_resolved'
       and not tgisinternal
  ) then
    raise exception
      'supervisor_actions: complaints_on_resolved is missing -- apply 20260813104000_timers_v2.sql first, or supervisor_resolve_complaint will resolve silently.';
  end if;

  raise notice
    'supervisor_actions: chat kind, five verbs, five sections and one new event word in place.';
end $$;


-- ---------------------------------------------------------------------------
-- 11. Post-apply checks
--
-- Run these in the SQL Editor after this file. They are also reproduced in
-- `docs/plans/MIGRATION_APPLY_RUNBOOK.md` 20. Nothing below runs as part of the
-- migration; the block in section 10 is the only thing that executes.
--
--   -- (a) Five sections, and the two new keys among them.
--   select jsonb_object_keys(public.supervisor_triage_snapshot(
--     (select id from public.departments where kind = 'service' limit 1)));
--   -- expect: department_id, new_complaints, taken_up, open_requests,
--   --         assigned_pending, in_progress.
--
--   -- (b) The constraint knows both of the last two words added to it.
--   select pg_get_constraintdef(oid) like '%taken_up%'         as knows_taken_up,
--          pg_get_constraintdef(oid) like '%priority_changed%' as knows_priority
--     from pg_constraint
--    where conrelid = 'public.complaint_events'::regclass
--      and conname  = 'complaint_events_type_check';
--   -- expect: one row, both true.
--
--   -- (c) No complaint thread exists yet, which is what a new kind looks like.
--   select count(*) filter (where kind = 'complaint') as complaint_threads,
--          count(*)                                   as threads
--     from public.dm_threads;
-- ---------------------------------------------------------------------------
