-- 0046_direct_messages.sql
--
-- Person-to-person messaging: the chat dock's substrate.
--
-- WHY NOT EXTEND conversations (0038)
--
-- That schema is structurally a department<->provider channel:
-- `service_provider_id` is NOT NULL, and `conversation_messages_one_author`
-- requires exactly one of author_membership_id / author_provider_id. A
-- manager<->admin thread has no provider end to put in the NOT NULL column.
-- Bending it would mean nullable-everything plus a rewritten participation
-- predicate — a second schema wearing the first one's name. The hiring thread
-- stays what it is; this is the other thing: two people, one thread.
--
-- THE PAIR IS THE THREAD
--
-- One row per (community, pair), participants ordered a < b by a CHECK so the
-- same two people cannot arrive as two rows. No participants table, no
-- thread-creation ceremony — `open_direct_thread` is an upsert, the
-- `conversations_one_per_pair` precedent.
--
-- THE WORK-ORDER THREAD, AND THE LOCK (PO ruling, 2026-08-10)
--
-- A worker and the resident whose complaint they are fixing may talk while
-- the job is live — and must stop when it is not: *"a protection to not let
-- servicemen talk with the resident after the work is complete."* So a
-- `work_order` thread carries the job's id, a trigger stamps `locked_at` when
-- the order goes terminal, and `post_dm_message` refuses a locked thread with
-- HB409. The thread stays READABLE — the same ruling asks for chats that
-- "may have to be documented well", and history that vanishes is not
-- documentation.
--
-- NAMES ARE SNAPSHOTS, DELIBERATELY
--
-- `profiles` is readable only by its owner (`profiles_self`, 0001), so a
-- security-invoker view joining it would show every counterpart as null. The
-- open RPCs snapshot both names onto the thread instead — the same trade
-- `staff_assignments.display_name` already makes, with the same known cost: a
-- rename shows the old name until something rewrites it.
--
-- WHO MAY REACH WHOM
--
-- The dock's "to" field autofills people in the caller's department, the
-- admins and the committee — and the committee IS the admin role
-- (docs/product/USER_IDENTIFICATION.md: the offices are not separate roles).
-- `dm_pair_allowed` says a pair is valid when both are active members of the
-- community and either one is an admin/manager or they share a department.
-- Residents therefore reach the office but not each other; their worker
-- contact is the work-order thread, which is exactly the scoping the PO
-- described. `dm_recipients` is the same rule turned into a list, so the
-- directory and the write cannot disagree.

-- ---------------------------------------------------------------------------
-- 1. Tables
-- ---------------------------------------------------------------------------

create table if not exists public.dm_threads (
  id                       uuid primary key default gen_random_uuid(),
  community_id             uuid not null references public.communities(id) on delete cascade,
  kind                     text not null default 'direct',
  work_order_id            uuid references public.work_orders(id) on delete cascade,
  participant_a_profile_id uuid not null references public.profiles(id) on delete cascade,
  participant_b_profile_id uuid not null references public.profiles(id) on delete cascade,
  participant_a_name       text not null default 'Someone',
  participant_b_name       text not null default 'Someone',
  locked_at                timestamptz,
  last_message_at          timestamptz,
  created_at               timestamptz not null default now()
);

do $$
begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.dm_threads'::regclass
                    and conname  = 'dm_threads_kind_check') then
    alter table public.dm_threads
      add constraint dm_threads_kind_check
      check (kind in ('direct', 'work_order'));
  end if;

  -- Canonical order makes the pair a value: (a, b) and (b, a) are the same
  -- thread because only one of them is representable.
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.dm_threads'::regclass
                    and conname  = 'dm_threads_pair_ordered') then
    alter table public.dm_threads
      add constraint dm_threads_pair_ordered
      check (participant_a_profile_id < participant_b_profile_id);
  end if;

  -- A job thread names its job; a direct thread does not.
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.dm_threads'::regclass
                    and conname  = 'dm_threads_subject_check') then
    alter table public.dm_threads
      add constraint dm_threads_subject_check
      check ((kind = 'work_order') = (work_order_id is not null));
  end if;
end $$;

create unique index if not exists dm_threads_one_per_pair
  on public.dm_threads (community_id, participant_a_profile_id, participant_b_profile_id)
  where kind = 'direct';

-- One LIVE thread per job. A locked one is history and does not block the
-- job's next accepted worker from getting their own.
create unique index if not exists dm_threads_one_live_per_work_order
  on public.dm_threads (work_order_id)
  where kind = 'work_order' and locked_at is null;

create index if not exists dm_threads_a_recent_idx
  on public.dm_threads (participant_a_profile_id, last_message_at desc nulls last);
create index if not exists dm_threads_b_recent_idx
  on public.dm_threads (participant_b_profile_id, last_message_at desc nulls last);

create table if not exists public.dm_messages (
  id                uuid primary key default gen_random_uuid(),
  thread_id         uuid not null references public.dm_threads(id) on delete cascade,
  -- Null is a system line — "this thread was locked when the job completed" —
  -- writable only through definer functions, never by a client.
  author_profile_id uuid references public.profiles(id) on delete set null,
  body              text not null,
  created_at        timestamptz not null default now()
);

do $$
begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.dm_messages'::regclass
                    and conname  = 'dm_messages_body_check') then
    alter table public.dm_messages
      add constraint dm_messages_body_check
      check (length(btrim(body)) between 1 and 4000);
  end if;
end $$;

create index if not exists dm_messages_thread_idx
  on public.dm_messages (thread_id, created_at);

-- ---------------------------------------------------------------------------
-- 2. Who may reach whom
-- ---------------------------------------------------------------------------

create or replace function public.dm_pair_allowed(
  p_community_id uuid,
  p_profile_one  uuid,
  p_profile_two  uuid
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
      from public.community_memberships m1
      join public.community_memberships m2
        on m2.community_id = m1.community_id
     where m1.community_id = p_community_id
       and m1.profile_id = p_profile_one
       and m2.profile_id = p_profile_two
       and m1.status = 'active' and m1.ended_at is null
       and m2.status = 'active' and m2.ended_at is null
       and (
         m1.role in ('admin', 'manager')
         or m2.role in ('admin', 'manager')
         or exists (
           select 1
             from public.staff_assignments s1
             join public.staff_assignments s2
               on s2.department_id = s1.department_id
            where s1.membership_id = m1.id
              and s2.membership_id = m2.id
              and s1.status = 'active'
              and s2.status = 'active'
         )
       )
  );
$$;

comment on function public.dm_pair_allowed(uuid, uuid, uuid) is
  'May these two people open a direct thread in this community? Yes when both are active members and either one runs the place (admin/manager — the committee IS the admin role) or they share a department. Residents reach the office, not each other.';

create or replace function public.dm_recipients(p_community_id uuid)
returns table (
  profile_id   uuid,
  display_name text,
  label        text
)
language sql
stable
security definer
set search_path = public
as $$
  -- The same rule as dm_pair_allowed, turned into a list for the dock's "to"
  -- field: everyone the CALLER may open a thread with, named and labelled.
  with me as (
    select m.id, m.role
      from public.community_memberships m
     where m.community_id = p_community_id
       and m.profile_id = auth.uid()
       and m.status = 'active' and m.ended_at is null
     limit 1
  ),
  candidates as (
    -- The office: admins and managers, reachable by every member.
    select m.profile_id,
           initcap(m.role) as label
      from public.community_memberships m, me
     where m.community_id = p_community_id
       and m.status = 'active' and m.ended_at is null
       and m.role in ('admin', 'manager')
    union
    -- Department colleagues of a staff caller.
    select m2.profile_id,
           coalesce(d.name, 'Department') as label
      from me
      join public.staff_assignments s1 on s1.membership_id = me.id and s1.status = 'active'
      join public.staff_assignments s2 on s2.department_id = s1.department_id and s2.status = 'active'
      join public.community_memberships m2 on m2.id = s2.membership_id
        and m2.status = 'active' and m2.ended_at is null
      left join public.departments d on d.id = s2.department_id
    union
    -- An admin or manager reaches every staff member — the employee card's
    -- chat button is this row set.
    select m2.profile_id,
           coalesce(d.name, 'Department') as label
      from me
      join public.staff_assignments s2 on s2.community_id = p_community_id and s2.status = 'active'
      join public.community_memberships m2 on m2.id = s2.membership_id
        and m2.status = 'active' and m2.ended_at is null
      left join public.departments d on d.id = s2.department_id
     where me.role in ('admin', 'manager')
  )
  select c.profile_id,
         coalesce(p.full_name, p.display_email::text, 'Someone') as display_name,
         min(c.label) as label
    from candidates c
    join public.profiles p on p.id = c.profile_id
   where c.profile_id <> auth.uid()
   group by c.profile_id, p.full_name, p.display_email
   order by 2;
$$;

comment on function public.dm_recipients(uuid) is
  'Who the caller may start a direct thread with in one community: the office (admins and managers — the committee), their department colleagues, and for admins/managers every staff member. The dock''s "to" field.';

-- ---------------------------------------------------------------------------
-- 3. Opening and posting
-- ---------------------------------------------------------------------------

create or replace function public.open_direct_thread(
  p_community_id        uuid,
  p_recipient_profile_id uuid
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_a    uuid;
  v_b    uuid;
  v_id   uuid;
  v_a_name text;
  v_b_name text;
begin
  if auth.uid() is null then
    raise exception 'Sign in required.' using errcode = '42501';
  end if;
  if p_recipient_profile_id = auth.uid() then
    raise exception 'That is you.' using errcode = '22P02';
  end if;
  if not public.dm_pair_allowed(p_community_id, auth.uid(), p_recipient_profile_id) then
    raise exception 'You cannot message this person here.' using errcode = 'HB403';
  end if;

  v_a := least(auth.uid(), p_recipient_profile_id);
  v_b := greatest(auth.uid(), p_recipient_profile_id);

  select coalesce(full_name, display_email::text, 'Someone') into v_a_name
    from public.profiles where id = v_a;
  select coalesce(full_name, display_email::text, 'Someone') into v_b_name
    from public.profiles where id = v_b;

  insert into public.dm_threads (
    community_id, kind, participant_a_profile_id, participant_b_profile_id,
    participant_a_name, participant_b_name
  )
  values (p_community_id, 'direct', v_a, v_b,
          coalesce(v_a_name, 'Someone'), coalesce(v_b_name, 'Someone'))
  -- `do update` rather than `do nothing`, so RETURNING yields a row for the
  -- second caller too (the 0038 precedent) — and the names refresh, which is
  -- as close as a snapshot gets to healing a rename.
  on conflict (community_id, participant_a_profile_id, participant_b_profile_id)
    where kind = 'direct'
  do update set participant_a_name = excluded.participant_a_name,
                participant_b_name = excluded.participant_b_name
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.open_direct_thread(uuid, uuid) is
  'One thread per pair per community, upserted. Refuses a pair dm_pair_allowed refuses, so the directory and the write agree.';

create or replace function public.open_work_order_thread(p_work_order_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order     public.work_orders%rowtype;
  v_worker    uuid;
  v_resident  uuid;
  v_a uuid; v_b uuid;
  v_a_name text; v_b_name text;
  v_id uuid;
begin
  if auth.uid() is null then
    raise exception 'Sign in required.' using errcode = '42501';
  end if;

  select * into v_order from public.work_orders where id = p_work_order_id;
  if not found then
    raise exception 'No such work order.' using errcode = 'HB404';
  end if;
  if v_order.status in ('completed', 'cancelled', 'failed') then
    raise exception 'That job is over; its conversation is closed.'
      using errcode = 'HB409';
  end if;

  -- The worker end: whoever holds the accepted assignment, resolved to a
  -- profile through their membership. A roster name with no account has no
  -- profile and therefore no thread — there is nobody to deliver it to.
  select m.profile_id into v_worker
    from public.work_order_assignments a
    join public.staff_assignments sa on sa.id = a.staff_assignment_id
    join public.community_memberships m on m.id = sa.membership_id
   where a.work_order_id = p_work_order_id
     and a.status = 'accepted'
   order by a.assigned_at desc
   limit 1;

  -- The resident end: whoever raised the complaint behind the job.
  select m.profile_id into v_resident
    from public.complaints c
    join public.community_memberships m on m.id = c.raised_by_membership_id
   where c.id = v_order.complaint_id;

  if v_worker is null or v_resident is null or v_worker = v_resident then
    raise exception 'This job has no worker and resident pair to talk.'
      using errcode = 'HB409';
  end if;

  if auth.uid() not in (v_worker, v_resident) then
    raise exception 'You are not part of this job.' using errcode = 'HB403';
  end if;

  v_a := least(v_worker, v_resident);
  v_b := greatest(v_worker, v_resident);
  select coalesce(full_name, display_email::text, 'Someone') into v_a_name
    from public.profiles where id = v_a;
  select coalesce(full_name, display_email::text, 'Someone') into v_b_name
    from public.profiles where id = v_b;

  select t.id into v_id
    from public.dm_threads t
   where t.work_order_id = p_work_order_id
     and t.kind = 'work_order'
     and t.locked_at is null
   limit 1;
  if v_id is not null then
    return v_id;
  end if;

  insert into public.dm_threads (
    community_id, kind, work_order_id,
    participant_a_profile_id, participant_b_profile_id,
    participant_a_name, participant_b_name
  )
  values (v_order.community_id, 'work_order', p_work_order_id, v_a, v_b,
          coalesce(v_a_name, 'Someone'), coalesce(v_b_name, 'Someone'))
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.open_work_order_thread(uuid) is
  'The worker<->resident channel for one live job. Either participant may open it; it refuses once the job is terminal, and the lock trigger closes it then anyway.';

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
begin
  if auth.uid() is null then
    raise exception 'Sign in required.' using errcode = '42501';
  end if;
  if coalesce(length(btrim(p_body)), 0) not between 1 and 4000 then
    raise exception 'A message is between 1 and 4000 characters.'
      using errcode = '22004';
  end if;

  select * into v_thread from public.dm_threads where id = p_thread_id;
  if not found
     or auth.uid() not in (v_thread.participant_a_profile_id,
                           v_thread.participant_b_profile_id) then
    -- One error for missing and for not-yours: a stranger probing thread ids
    -- learns nothing from the difference.
    raise exception 'No such conversation.' using errcode = 'HB404';
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

  perform public.notify_profile(
    v_other, 'dm.message',
    jsonb_build_object(
      'title', coalesce(v_name, 'Someone') || ' sent you a message',
      'body', left(btrim(p_body), 140),
      'threadId', p_thread_id));

  return v_id;
end;
$$;

comment on function public.post_dm_message(uuid, text) is
  'Append to a thread the caller is in. HB404 hides other people''s threads; HB409 is the lock — a finished job''s channel does not reopen.';

-- ---------------------------------------------------------------------------
-- 4. The lock
-- ---------------------------------------------------------------------------

create or replace function public.lock_work_order_threads()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status in ('completed', 'cancelled', 'failed')
     and (tg_op = 'INSERT' or old.status is distinct from new.status) then
    update public.dm_threads
       set locked_at = coalesce(locked_at, now())
     where work_order_id = new.id
       and kind = 'work_order'
       and locked_at is null;

    -- The system line the mailbox shows instead of a silence: readable
    -- history, closed channel.
    insert into public.dm_messages (thread_id, author_profile_id, body)
    select t.id, null,
           'The job ended (' || new.status || '). This conversation is closed.'
      from public.dm_threads t
     where t.work_order_id = new.id
       and t.kind = 'work_order'
       and t.locked_at is not null
       and not exists (
         select 1 from public.dm_messages m
          where m.thread_id = t.id
            and m.author_profile_id is null
            and m.body like 'The job ended%'
       );
  end if;
  return null;
end;
$$;

drop trigger if exists work_orders_lock_dm_threads on public.work_orders;
create trigger work_orders_lock_dm_threads
  after insert or update of status on public.work_orders
  for each row execute function public.lock_work_order_threads();

-- ---------------------------------------------------------------------------
-- 5. Views
-- ---------------------------------------------------------------------------

drop view if exists public.dm_thread_overview;
create view public.dm_thread_overview
with (security_invoker = true) as
select
  t.id,
  t.community_id,
  c.name as community_name,
  t.kind,
  t.work_order_id,
  t.participant_a_profile_id,
  t.participant_b_profile_id,
  t.participant_a_name,
  t.participant_b_name,
  t.locked_at,
  t.last_message_at,
  t.created_at,
  last_m.body as last_message_body
from public.dm_threads t
join public.communities c on c.id = t.community_id
left join lateral (
  select m.body
    from public.dm_messages m
   where m.thread_id = t.id
   order by m.created_at desc
   limit 1
) last_m on true;

comment on view public.dm_thread_overview is
  'The mailbox: one row per thread the caller is in (RLS scopes it), both names as snapshots, the lock state, and a one-line preview.';

grant select on public.dm_thread_overview to authenticated;

drop view if exists public.dm_message_overview;
create view public.dm_message_overview
with (security_invoker = true) as
select
  m.id,
  m.thread_id,
  m.author_profile_id,
  m.body,
  m.created_at
from public.dm_messages m;

comment on view public.dm_message_overview is
  'Messages of a thread. The author''s name is not joined here — the client maps author_profile_id onto the thread''s two snapshot names, and a null author is a system line.';

grant select on public.dm_message_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 6. RLS — read what you are in; write through the functions
-- ---------------------------------------------------------------------------

alter table public.dm_threads enable row level security;
alter table public.dm_messages enable row level security;

drop policy if exists dm_threads_read on public.dm_threads;
create policy dm_threads_read on public.dm_threads
  for select to authenticated
  using (
    participant_a_profile_id = auth.uid()
    or participant_b_profile_id = auth.uid()
  );

drop policy if exists dm_messages_read on public.dm_messages;
create policy dm_messages_read on public.dm_messages
  for select to authenticated
  using (
    exists (
      select 1 from public.dm_threads t
       where t.id = dm_messages.thread_id
         and (t.participant_a_profile_id = auth.uid()
              or t.participant_b_profile_id = auth.uid())
    )
  );

-- ---------------------------------------------------------------------------
-- 7. Grants
-- ---------------------------------------------------------------------------

revoke all on function public.dm_pair_allowed(uuid, uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.dm_pair_allowed(uuid, uuid, uuid) to authenticated;

revoke all on function public.dm_recipients(uuid)
  from public, anon, authenticated;
grant execute on function public.dm_recipients(uuid) to authenticated;

revoke all on function public.open_direct_thread(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.open_direct_thread(uuid, uuid) to authenticated;

revoke all on function public.open_work_order_thread(uuid)
  from public, anon, authenticated;
grant execute on function public.open_work_order_thread(uuid) to authenticated;

revoke all on function public.post_dm_message(uuid, text)
  from public, anon, authenticated;
grant execute on function public.post_dm_message(uuid, text) to authenticated;

revoke all on function public.lock_work_order_threads()
  from public, anon, authenticated;
