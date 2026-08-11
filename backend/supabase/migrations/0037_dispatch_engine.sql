-- ===========================================================================
-- 0037_dispatch_engine.sql — the timers behind the state machine
--
-- `0036` built every transition a work order can make and not one thing that
-- makes a transition happen on its own. A supervisor could propose a visit, a
-- resident could confirm it, and then nothing at all would occur until a human
-- pressed `assign`. This file is the part that presses it.
--
-- **Corrected 2026-08-11.** `work_order.offered` and `work_order.assigned` both
-- linked to `/worker/jobs?job=<id>`, a route the worker portal does not have.
-- Both now say `/worker?job=<id>`. `0036`'s header carries the full reasoning,
-- since three of the five sites are there.
--
-- Due times live in `dispatch_tasks`; a background loop in
-- `app/core/dispatcher.py` claims what is due and asks Postgres to act. **Python
-- owns only *when*.** Every decision — who is free, who gets the offer, what the
-- resident is told — happens in a function here, because there is still no
-- notification API in Python: every notification in this product is written by
-- `notify_member` inside the transaction that caused it, and a dispatcher that
-- decided things in Python would have to give that up.
--
--
-- AT-LEAST-ONCE, WHICH IS THE OPPOSITE OF WHAT THE PUSH SENDER CHOSE
--
-- `app/core/push.py` states its rule in print: *"The hub may drop. The sender
-- may not duplicate."* It claims by marking the row sent **before** the send, so
-- a crash loses a buzz rather than repeating one. That is right for something
-- that vibrates a phone at 3am. It is wrong here.
--
-- A dropped `resident_timeout` is a complaint left in `awaiting_resident`
-- forever with nobody coming — the exact silence this feature exists to end. So
-- `claim_dispatch_batch` takes a **lease**: it stamps `claimed_at`, and a task
-- still unfinished five minutes later is claimable again by whoever is alive.
--
-- The price is that a task can fire twice, and it is paid in one place: **every
-- firing function re-reads the work order and returns without writing if the
-- world has already moved on.** Those status checks at the top of
-- `dispatch_ping_candidates`, `dispatch_auto_assign` and
-- `dispatch_resident_timeout` are not defensive padding — they are what makes
-- the lease safe, and removing one turns a retry into a double booking.
--
-- Claiming is otherwise `claim_push_batch` with the nouns changed, `for update
-- skip locked` and all: two dispatchers in two processes claim disjoint sets.
--
--
-- ONE TRIGGER, NOT FIVE REWRITTEN FUNCTIONS
--
-- The obvious way to enqueue work is to have each RPC in `0036` do it. That
-- means `create or replace` on five functions — some five hundred lines copied
-- to add two lines each — and it means the sixth write path, whenever somebody
-- adds one, silently enqueues nothing.
--
-- Instead there is one `after insert or update` trigger on `work_orders` that
-- keeps `dispatch_tasks` in agreement with the status:
--
--     awaiting_resident      -> resident_timeout, due at resident_deadline_at
--     offered, priority high -> auto_assign, due now
--     offered, otherwise     -> ping, due now
--     failed                 -> close everything, then failed_visit_escalation
--                               in two hours
--     anything else          -> close every open task on this job
--
-- The last row is the one that pays for itself. A cancelled job, an assigned
-- job and a completed job all stop their own timers without anybody
-- remembering to, and `cancel_work_order` did not have to learn what a
-- dispatch task is.
--
-- It also deletes a mechanism the plan described. There is no separate
-- "urgent complaints bypass the offer and auto-assign" path; there is the
-- second row of that table.
--
--
-- FOUR KINDS, FOUR FUNCTIONS
--
-- This file shipped with three. `failed_visit_escalation` was named in
-- `dispatch_tasks_kind_check` and deliberately left unimplemented, because it
-- fires off `work_orders.status = 'failed'` and nothing could write that status
-- until a worker had a way to say *I could not get in*. `0039` is that way, so
-- the fourth handler was added here rather than there: what the engine does
-- living in two files is how the next reader misses half of it.
--
-- Its idempotency check is the one that is not a status check, and the reason is
-- worth reading. A supervisor answering a failed visit raises a **new** work
-- order — plan D5, a failed visit is a second job and not an edit to the first —
-- so the failed one stays `failed` for good, and `if status <> 'failed' then
-- return` would escalate the same job on every redelivery forever. What it
-- checks instead is whether a **newer work order exists on the same complaint**.
-- If one does, a human has already dealt with this.
--
--
-- WHAT THIS FILE DELIBERATELY DOES NOT DO
--
-- * **No `pg_cron`.** `0024` uses it only inside a `do` block that no-ops when
--   the extension is missing, precisely because nobody knew whether it was
--   available. Betting a log pruner on that is reasonable; betting the engine
--   that decides whether anyone turns up is not.
-- * **No auto-resolution of a silent complaint.** The source document asks for a
--   complaint to close itself after 24 hours of resident silence. What
--   `dispatch_resident_timeout` does instead is *proceed with the visit* and say
--   so. Closing a complaint the resident never saw is a product decision, and it
--   is not one this file should make quietly at 2am.
-- * **No endpoints.** Not one operation is added to the API by this migration.
--
-- Depends on: 0036 (work orders), 0035 (staff ranks, service_provider_id on the
-- roster), 0034 (service providers, skills, haversine/PostGIS), 0030
-- (notify_member), 0019 (departments).
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. The queue
--
-- Every future action the engine intends to take is one row here, which makes
-- the engine's entire behaviour inspectable with a single `select`. That is the
-- reason this is a table and not an in-memory timer: a restart loses nothing,
-- and "why did nobody come" has an answer you can read.
-- ---------------------------------------------------------------------------

create table if not exists public.dispatch_tasks (
  id            uuid primary key default gen_random_uuid(),
  work_order_id uuid not null references public.work_orders(id) on delete cascade,
  kind          text not null,
  due_at        timestamptz not null default now(),
  attempts      smallint not null default 0,
  claimed_at    timestamptz,
  completed_at  timestamptz,
  last_error    text,
  created_at    timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.dispatch_tasks'::regclass
       and conname  = 'dispatch_tasks_kind_check'
  ) then
    alter table public.dispatch_tasks
      add constraint dispatch_tasks_kind_check
      check (kind in (
        'ping', 'auto_assign', 'resident_timeout', 'failed_visit_escalation'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.dispatch_tasks'::regclass
       and conname  = 'dispatch_tasks_attempts_check'
  ) then
    alter table public.dispatch_tasks
      add constraint dispatch_tasks_attempts_check
      check (attempts >= 0);
  end if;
end $$;

-- One open task of each kind per job, and the upsert in section 2 infers this
-- index by name of its columns and its predicate. Without it a job rescheduled
-- three times carries three live `resident_timeout` rows, two of which fire
-- against a deadline that no longer exists.
create unique index if not exists dispatch_tasks_one_open_per_kind
  on public.dispatch_tasks (work_order_id, kind)
  where completed_at is null;

-- The claim's index. Partial on the open set, because the finished rows are the
-- ones this query is never interested in and they are the ones that accumulate.
create index if not exists dispatch_tasks_due_idx
  on public.dispatch_tasks (due_at)
  where completed_at is null;

comment on table public.dispatch_tasks is
  'Every future action the dispatcher intends to take, one row each. Claimed '
  'under a five-minute lease, so a task may fire more than once and every '
  'firing function is idempotent. service_role only; no RLS policy exists.';

comment on column public.dispatch_tasks.claimed_at is
  'Lease start, not a completion mark. A row still open five minutes after '
  'this is claimable again -- which is how a dispatcher that died mid-task '
  'does not strand the job it was holding.';

-- ---------------------------------------------------------------------------
-- 2. Keeping the queue in agreement with the job
--
-- Two helpers and the trigger that uses them. Nothing outside this file calls
-- `enqueue_dispatch_task` -- the trigger is the only writer, which is what makes
-- the table's contents a function of the work order's status rather than of who
-- remembered.
-- ---------------------------------------------------------------------------

create or replace function public.enqueue_dispatch_task(
  p_work_order_id uuid,
  p_kind          text,
  p_due_at        timestamptz default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  insert into public.dispatch_tasks (work_order_id, kind, due_at)
  values (p_work_order_id, p_kind, coalesce(p_due_at, now()))
  -- Re-arming rather than duplicating. A job rescheduled twice before its
  -- deadline should have one timer pointing at the newest deadline, and the
  -- reset of `claimed_at` and `attempts` is what stops an earlier failure from
  -- retiring a task that now describes a different visit.
  on conflict (work_order_id, kind) where completed_at is null
  do update set
    due_at     = excluded.due_at,
    claimed_at = null,
    attempts   = 0,
    last_error = null
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.enqueue_dispatch_task(uuid, text, timestamptz) is
  'Arm or re-arm one timer for one job. Called only by the work_orders trigger '
  'and by dispatch_ping_candidates when it escalates.';

create or replace function public.close_dispatch_tasks(
  p_work_order_id uuid,
  p_kinds         text[] default null
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_closed integer;
begin
  update public.dispatch_tasks
     set completed_at = now()
   where work_order_id = p_work_order_id
     and completed_at is null
     and (p_kinds is null or kind = any(p_kinds));

  get diagnostics v_closed = row_count;
  return v_closed;
end;
$$;

comment on function public.close_dispatch_tasks(uuid, text[]) is
  'Retire outstanding timers for a job. Null kinds means all of them, which is '
  'what a cancellation, an assignment and a completion all want.';

create or replace function public.sync_dispatch_tasks()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status = 'awaiting_resident' then
    -- Re-armed when the deadline moves, not only when the status changes: a
    -- reschedule while the resident is still deciding is a new question with a
    -- new closing time.
    if tg_op = 'INSERT'
       or old.status is distinct from new.status
       or old.resident_deadline_at is distinct from new.resident_deadline_at then
      perform public.enqueue_dispatch_task(
        new.id, 'resident_timeout',
        coalesce(new.resident_deadline_at, now() + interval '24 hours'));
    end if;

  elsif new.status = 'offered' then
    if tg_op = 'INSERT'
       or old.status is distinct from new.status
       or old.scheduled_start_at is distinct from new.scheduled_start_at then
      -- The resident is no longer the one being waited on, whichever way they
      -- stopped being it.
      perform public.close_dispatch_tasks(new.id, array['resident_timeout']);

      -- The urgent path, and the whole of it. A high-priority job skips the
      -- ask-and-wait and books somebody on the first tick; everything else is
      -- offered around first.
      perform public.enqueue_dispatch_task(
        new.id,
        case when new.priority = 'high' then 'auto_assign' else 'ping' end,
        now());
    end if;

  elsif new.status = 'failed' then
    if tg_op = 'INSERT' or old.status is distinct from new.status then
      -- Everything else about this job is over: the visit did not happen and no
      -- ping or auto-assign against the old slot means anything now.
      perform public.close_dispatch_tasks(new.id, null);

      -- Two hours, and the number is the argument. A supervisor who is at their
      -- desk sees the failure notification `0039` sends and acts on it within
      -- minutes; this is for the failure that arrives at six in the evening and
      -- is still sitting there at eight. Short enough that a resident is not
      -- waiting overnight for somebody to notice, long enough that the ordinary
      -- case never escalates at all.
      perform public.enqueue_dispatch_task(
        new.id, 'failed_visit_escalation', now() + interval '2 hours');
    end if;

  elsif tg_op = 'INSERT' or old.status is distinct from new.status then
    -- draft, scheduled, in_progress, completed, cancelled. None of them is
    -- waiting on a timer, and a job that went back to draft because the resident
    -- declined must not still be pinging workers about the slot they declined.
    perform public.close_dispatch_tasks(new.id, null);
  end if;

  return null;
end;
$$;

comment on function public.sync_dispatch_tasks() is
  'Keeps dispatch_tasks in agreement with work_orders.status. The single writer '
  'of that table, so no future write path has to remember to arm a timer.';

drop trigger if exists work_orders_sync_dispatch on public.work_orders;
create trigger work_orders_sync_dispatch
  after insert or update on public.work_orders
  for each row execute function public.sync_dispatch_tasks();

-- ---------------------------------------------------------------------------
-- 3. The claim
--
-- `claim_push_batch` (0030 section 8) with the nouns changed and one difference
-- that matters, argued at the top of this file: a lease, not a tombstone.
-- ---------------------------------------------------------------------------

create or replace function public.claim_dispatch_batch(p_limit integer default 20)
returns table (
  task_id       uuid,
  work_order_id uuid,
  kind          text,
  due_at        timestamptz,
  attempts      smallint
)
language sql
security definer
set search_path = public
as $$
  update public.dispatch_tasks t
     set claimed_at = now(),
         attempts   = t.attempts + 1
   where t.id in (
     select c.id
       from public.dispatch_tasks c
      where c.completed_at is null
        and c.due_at <= now()
        -- Either never claimed, or claimed by something that is not coming
        -- back. Five minutes is far longer than any task here takes and far
        -- shorter than a resident will wait.
        and (c.claimed_at is null or c.claimed_at < now() - interval '5 minutes')
        -- Five tries and it stops. A task that has failed five times is failing
        -- for a reason that another attempt will not discover, and
        -- `last_error` is where a human finds out why.
        and c.attempts < 5
      order by c.due_at
      limit greatest(coalesce(p_limit, 20), 1)
      for update skip locked
   )
  returning t.id, t.work_order_id, t.kind, t.due_at, t.attempts;
$$;

comment on function public.claim_dispatch_batch(integer) is
  'Atomically lease the next due tasks. for update skip locked, so two '
  'dispatcher processes claim disjoint sets rather than the same one twice.';

create or replace function public.complete_dispatch_task(p_task_id uuid)
returns void
language sql
security definer
set search_path = public
as $$
  update public.dispatch_tasks
     set completed_at = coalesce(completed_at, now()),
         last_error   = null
   where id = p_task_id;
$$;

create or replace function public.fail_dispatch_task(
  p_task_id uuid,
  p_error   text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.dispatch_tasks
     set last_error = left(coalesce(p_error, 'unknown error'), 500),
         -- Released rather than held: the lease exists so a failure retries on
         -- the next tick instead of waiting five minutes for a timeout that
         -- already happened.
         claimed_at = null,
         -- Out of attempts is the one case where the row retires itself, so a
         -- permanently broken task does not occupy the queue forever.
         completed_at = case when attempts >= 5 then now() else completed_at end
   where id = p_task_id;
end;
$$;

comment on function public.fail_dispatch_task(uuid, text) is
  'Record why a task did not fire and release its lease. Retires the task on '
  'the fifth failure; last_error is what survives for a human to read.';

-- ---------------------------------------------------------------------------
-- 4. Who could do this job
--
-- The sweep. One work order in, an ordered shortlist out, and no writes at all
-- -- which is what lets `dispatch_auto_assign` and `dispatch_ping_candidates`
-- share it instead of each carrying its own idea of who is free.
--
-- TWO THINGS IT DELIBERATELY DOES NOT KNOW
--
-- The source document orders candidates by *"within 1 km of an adjacent job"*.
-- No work order carries usable coordinates, and inside one apartment complex
-- every job is a two-minute walk from every other, so a distance measured from
-- the community's own centroid would be the same number twice. That criterion
-- becomes **"already has a job in this community that day"**, which is the same
-- intent -- do not send someone across the city twice -- expressed in data that
-- exists. Cross-community distance is real and is still the third sort key.
--
-- A roster row with no `service_provider_id` is somebody a manager typed in by
-- hand. Nothing records their skills -- `staff_skills` is superseded by D2 and
-- is deleted in step 12 -- so the skill filter cannot judge them, and it does
-- not try. They stay eligible on the strength of the only statement anybody has
-- made about them: a manager put them in this department. Excluding them instead
-- would give a community that types its roster by hand an engine that never
-- dispatches anyone.
-- ---------------------------------------------------------------------------

create or replace function public.dispatch_candidates(
  p_work_order_id uuid,
  p_limit         integer default 5
)
returns table (
  staff_assignment_id uuid,
  membership_id       uuid,
  service_provider_id uuid,
  display_name        text,
  has_adjacent_job    boolean,
  open_jobs           integer,
  distance_km         numeric
)
language sql
security definer
set search_path = public
as $$
  -- Two CTEs and a qualified ORDER BY, which is not a stylistic choice. In a
  -- SQL-language function the RETURNS TABLE column names are in scope as
  -- variables, so an unqualified `order by has_adjacent_job` is ambiguous
  -- against this function's own output parameter. Ranking inside `ranked` and
  -- sorting on `cand.*` puts every name beyond doubt.
  with job as (
    select w.id, w.community_id, w.department_id, w.skill_id,
           w.scheduled_start_at as slot_start,
           w.scheduled_end_at   as slot_end
      from public.work_orders w
     where w.id = p_work_order_id
       -- An unscheduled job has no slot to be free for. Returning nothing is
       -- the honest answer and it keeps every caller from having to ask first.
       and w.scheduled_start_at is not null
       and w.department_id is not null
  ),
  ranked as (
  select
    sa.id                  as sa_id,
    sa.membership_id       as sa_membership_id,
    sa.service_provider_id as sa_provider_id,
    sa.display_name        as sa_display_name,
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
        (extensions.st_distance(c.location, sp.location) / 1000)::numeric, 2)
    end as km
  from job j
  join public.staff_assignments sa
    on sa.department_id = j.department_id
   and sa.status = 'active'
   and sa.is_active
   -- No membership, no notification. A name on a roster with no account cannot
   -- be told it has been offered a job, so it cannot be offered one.
   and sa.membership_id is not null
  join public.communities c
    on c.id = j.community_id
  left join public.service_providers sp
    on sp.id = sa.service_provider_id
 where
   -- The dashboard's offline toggle, honoured. Only applies to somebody who
   -- has a switch to flip.
   (sp.id is null or (sp.status = 'active' and sp.is_available))
   -- Leave, keyed either way: per-provider for a registered service person
   -- (global across their communities) or per-roster-row for a hand-typed name.
   and not exists (
     select 1
       from public.worker_unavailability u
      where (u.staff_assignment_id = sa.id
             or (sp.id is not null and u.service_provider_id = sp.id))
        and tstzrange(u.starts_at, u.ends_at, '[)')
            && tstzrange(j.slot_start, j.slot_end, '[)')
   )
   -- Working hours, if any are declared. **No rules means always available** --
   -- the alternative makes every newly hired worker invisible to the engine
   -- until somebody fills in a form, which is the failure nobody would diagnose.
   --
   -- `weekday` is 0-6 with Sunday at 0, matching `extract(dow ...)`, and the
   -- time comparison happens in the database's timezone because that is the
   -- only clock a `time` column has.
   and (
     not exists (
       select 1 from public.worker_availability_rules r
        where r.staff_assignment_id = sa.id
           or (sp.id is not null and r.service_provider_id = sp.id)
     )
     or exists (
       select 1
         from public.worker_availability_rules r
        where (r.staff_assignment_id = sa.id
               or (sp.id is not null and r.service_provider_id = sp.id))
          and r.weekday = extract(dow from j.slot_start)::smallint
          and r.start_time <= j.slot_start::time
          and r.end_time   >= j.slot_end::time
          and r.effective_from <= j.slot_start::date
          and (r.effective_to is null or r.effective_to >= j.slot_start::date)
     )
   )
   -- Already booked elsewhere in this hour. `work_order_assignments_no_overlap`
   -- would refuse the write anyway; checking here means the engine does not
   -- offer a job that cannot be accepted, which a worker would experience as
   -- an offer that errors when they tap it.
   and not exists (
     select 1
       from public.work_order_assignments busy
      where busy.staff_assignment_id = sa.id
        and busy.status = 'accepted'
        and busy.work_order_id <> j.id
        and busy.scheduled_start_at is not null
        and tstzrange(busy.scheduled_start_at, busy.scheduled_end_at, '[)')
            && tstzrange(j.slot_start, j.slot_end, '[)')
   )
   -- Already said no to THIS job. Without this, the ordinary sequence produces
   -- the worst outcome the engine can produce: five workers are pinged, one
   -- declines, thirty minutes later `dispatch_auto_assign` asks for the single
   -- best candidate -- and the decliner is still in the set, still ranks first on
   -- adjacency and load, and finds the job booked in their name.
   --
   -- Scoped to the work order rather than to the person on purpose. Somebody who
   -- declined last Tuesday is a perfectly good candidate for next Tuesday.
   and not exists (
     select 1
       from public.work_order_assignments said_no
      where said_no.staff_assignment_id = sa.id
        and said_no.work_order_id = j.id
        and said_no.status = 'declined'
   )
   -- The trade. Skipped when the job names no skill, and skipped for a roster
   -- row nobody has recorded skills for -- see the header note.
   and (
     j.skill_id is null
     or sp.id is null
     or exists (
       select 1 from public.service_provider_skills ps
        where ps.service_provider_id = sp.id
          and ps.skill_id = j.skill_id
     )
   )
  )
  select
    cand.sa_id,
    cand.sa_membership_id,
    cand.sa_provider_id,
    cand.sa_display_name,
    cand.adjacent,
    cand.load,
    cand.km
  from ranked cand
  order by
    cand.adjacent desc,
    cand.load asc,
    cand.km asc nulls last,
    cand.sa_display_name
  limit greatest(coalesce(p_limit, 5), 1);
$$;

comment on function public.dispatch_candidates(uuid, integer) is
  'Who could take this job, best first: already in this community today, then '
  'least loaded, then nearest. Reads only. service_role only -- it returns a '
  'department roster and asks the caller nothing.';

-- ---------------------------------------------------------------------------
-- 5. What the engine actually does
--
-- Three functions, one per implemented task kind. Each begins by re-reading the
-- job and checking the status it expects, which is the idempotency the lease
-- requires -- see the header.
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
          'url', '/admin/departments?job=' || v_order.id::text,
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

comment on function public.dispatch_ping_candidates(uuid) is
  'Offer a scheduled job to the best few candidates and set the 30-minute '
  'escalation. Idempotent: does nothing unless the job is still `offered`.';

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
          'url', '/admin/departments?job=' || v_order.id::text,
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

comment on function public.dispatch_auto_assign(uuid) is
  'Book the best candidate outright and tell both sides. The same effect as a '
  'supervisor pressing assign, which is why that lever was built first.';

create or replace function public.dispatch_resident_timeout(p_work_order_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order     public.work_orders%rowtype;
  v_complaint public.complaints%rowtype;
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

  -- **Proceed, do not close.** The source document asks for the complaint to
  -- auto-resolve after 24 hours of silence; resolving a complaint the resident
  -- never saw is a product decision and this is not the place to make it
  -- quietly. Going ahead with the visit needs no such decision and is what the
  -- resident was told would happen.
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

  -- The trigger in section 2 arms the ping from here; nothing enqueues it by
  -- hand, because the status change already says everything the queue needs.
  return true;
end;
$$;

comment on function public.dispatch_resident_timeout(uuid) is
  'The resident never answered: proceed with the proposed visit and say so. '
  'Does not resolve the complaint -- see the note in the body.';

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
        'url', '/admin/departments?job=' || v_order.id::text,
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
        'url', '/admin/departments?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'attempts', v_order.failed_attempt_count));
  end if;

  return true;
end;
$$;

comment on function public.dispatch_failed_visit_escalation(uuid) is
  'Two hours after a failed visit nobody has rebooked, tell the department '
  'manager -- or the community''s admins if the department has none. Idempotent '
  'on the existence of a newer work order for the same complaint.';

-- ---------------------------------------------------------------------------
-- 6. The one function the dispatcher calls
--
-- Python claims a batch and then, for each row, calls this. Which means the
-- mapping from a task kind to an action lives in Postgres beside the actions,
-- and `app/core/dispatcher.py` never learns what a `ping` is -- it is a loop
-- with a timer, and adding a fifth kind will not touch it.
-- ---------------------------------------------------------------------------

create or replace function public.fire_dispatch_task(p_task_id uuid)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_task   public.dispatch_tasks%rowtype;
  v_result text;
  v_id     uuid;
begin
  select * into v_task from public.dispatch_tasks where id = p_task_id
    for update;
  if not found then
    return 'missing';
  end if;

  -- The lease can hand the same task to a second process; the first one having
  -- finished it is not an error.
  if v_task.completed_at is not null then
    return 'already_done';
  end if;

  case v_task.kind
    when 'ping' then
      v_result := 'offered:'
        || public.dispatch_ping_candidates(v_task.work_order_id)::text;

    when 'auto_assign' then
      v_id := public.dispatch_auto_assign(v_task.work_order_id);
      v_result := coalesce('assigned:' || v_id::text, 'no_candidate');

    when 'resident_timeout' then
      v_result := case
        when public.dispatch_resident_timeout(v_task.work_order_id)
        then 'proceeded' else 'skipped' end;

    when 'failed_visit_escalation' then
      v_result := case
        when public.dispatch_failed_visit_escalation(v_task.work_order_id)
        then 'escalated' else 'skipped' end;

    else
      -- Nothing declared reaches here any more -- all four kinds in
      -- `dispatch_tasks_kind_check` have an arm above. It stays because the
      -- CHECK and this `case` are two lists that could drift, and a fifth kind
      -- added to one and not the other should be recorded and retired rather
      -- than retried: a task nothing can handle will not become handleable on
      -- the next tick, and leaving it open would mean the queue always looks
      -- busy.
      update public.dispatch_tasks
         set last_error   = 'No handler for kind: ' || v_task.kind,
             completed_at = now()
       where id = p_task_id;
      return 'unsupported';
  end case;

  update public.dispatch_tasks
     set completed_at = now(),
         last_error   = null
   where id = p_task_id;

  return v_result;
end;
$$;

comment on function public.fire_dispatch_task(uuid) is
  'Run one claimed task and mark it done. The dispatcher''s only verb: the '
  'mapping from kind to action stays in SQL beside the actions.';

-- ---------------------------------------------------------------------------
-- 7. Permissions
--
-- `dispatch_tasks` gets RLS **with no policy at all**, following
-- `push_subscriptions` (0030): it is machine bookkeeping, no client has a reason
-- to read it, and the dispatcher runs on the service client, which bypasses RLS
-- entirely. RLS with no policy denies everyone else by default, which is the
-- shortest way to say what is meant.
--
-- Every function here is `service_role` only, and each one is revoked from
-- PUBLIC first. That order matters and is not decoration: Postgres grants
-- EXECUTE on a new function to PUBLIC by default, so a grant on its own
-- re-states a permission everybody already had. `dispatch_candidates` is the
-- clearest case -- it returns a department's roster and asks the caller
-- nothing, because its callers have already established who they are.
-- ---------------------------------------------------------------------------

alter table public.dispatch_tasks enable row level security;

revoke all on function public.enqueue_dispatch_task(uuid, text, timestamptz)
  from public, anon, authenticated;
revoke all on function public.close_dispatch_tasks(uuid, text[])
  from public, anon, authenticated;
revoke all on function public.claim_dispatch_batch(integer)
  from public, anon, authenticated;
revoke all on function public.complete_dispatch_task(uuid)
  from public, anon, authenticated;
revoke all on function public.fail_dispatch_task(uuid, text)
  from public, anon, authenticated;
revoke all on function public.dispatch_candidates(uuid, integer)
  from public, anon, authenticated;
revoke all on function public.dispatch_ping_candidates(uuid)
  from public, anon, authenticated;
revoke all on function public.dispatch_auto_assign(uuid)
  from public, anon, authenticated;
revoke all on function public.dispatch_resident_timeout(uuid)
  from public, anon, authenticated;
revoke all on function public.dispatch_failed_visit_escalation(uuid)
  from public, anon, authenticated;
revoke all on function public.fire_dispatch_task(uuid)
  from public, anon, authenticated;

grant execute on function public.claim_dispatch_batch(integer) to service_role;
grant execute on function public.complete_dispatch_task(uuid) to service_role;
grant execute on function public.fail_dispatch_task(uuid, text) to service_role;
grant execute on function public.fire_dispatch_task(uuid) to service_role;
