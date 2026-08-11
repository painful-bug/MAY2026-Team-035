-- The conversation a department has with a service person.
--
-- 0035 built the negotiation: apply, invite, decide. This file is what happens
-- around it -- the questions a manager asks before hiring, and the messages
-- that keep flowing after. One thread per (department, provider) pair, forever.
--
-- WHY THE PAIR IS UNIQUE, AND WHY THAT IS THE WHOLE CONCURRENCY STORY
--
-- Two managers of the same department can open the chat with the same plumber
-- in the same second. With a unique constraint on (department_id,
-- service_provider_id) and an ON CONFLICT, they get the same row and neither
-- has to know the other existed. Without it, they get two threads, each holding
-- half the conversation, and no query can put them back together. The
-- constraint is not an optimisation here; it is the only reason
-- open_conversation can be an upsert rather than a lock-and-check.
--
-- The thread outlives every application in it. A provider who applied, was
-- rejected, and applied again a year later is talking to the same department
-- about the same work -- so the thread is keyed to the pair rather than to an
-- application, and nothing in this file has a foreign key to
-- service_applications.
--
-- TWO AUTHOR COLUMNS, EXACTLY ONE SET
--
-- A message is written by one of two parties, and they are not the same kind of
-- thing. The department side is a community_memberships row. The provider side
-- is a service_providers row -- and it has to be, because the provider a
-- manager most needs to reach is one who has NOT been hired yet and therefore
-- holds no membership in this community at all. That is the same fact that
-- makes an invitation unnotifiable (see the journal, 5.9), and it is why this
-- schema cannot address both sides through community_memberships and stop
-- there.
--
-- A hired provider has both a membership and a provider row. Which column gets
-- written is decided by the thread, not by the caller: if you are this thread's
-- provider you author as the provider, otherwise you author as your membership.
-- So `author_provider_id is not null` reads as "the worker said this", in every
-- thread, whether or not they were on the roster at the time.
--
-- NO PARTICIPANTS TABLE
--
-- Participation is derivable -- an admin or manager of the department, or that
-- provider -- and deriving it is exactly what the read policy computes. A
-- participants table would be a second copy of a fact the policy has to
-- establish anyway, free to drift from it, and it would need its own writes
-- kept in step with every hire, removal and manager reassignment. The policy
-- calls can_manage_department (0035 6), which is the same function guarding
-- every other route in this feature, so there is one definition of "may act for
-- this department" rather than two.
--
-- Supervisors are deliberately outside it. This is the hiring conversation; a
-- supervisor's conversation is with a complainant about a job, and that is
-- complaint_comments and 0036.
--
-- NO READ RECEIPTS, NO TRIGGER
--
-- Nothing in the requirement asks for unread counts, and adding one later is a
-- lateral join on created_at against a per-thread timestamp. `last_message_at`
-- is stamped by the RPC that inserts the message, not by a trigger, because
-- section 6 declares READ POLICIES ONLY: there is no path from any client to an
-- insert this file did not perform, so a trigger would be defending against a
-- writer that cannot exist.

-- ---------------------------------------------------------------------------
-- 1. The thread
-- ---------------------------------------------------------------------------

create table if not exists public.conversations (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.communities(id) on delete cascade,
  department_id       uuid not null references public.departments(id) on delete cascade,
  service_provider_id uuid not null
                        references public.service_providers(id) on delete cascade,
  created_at          timestamptz not null default now(),
  last_message_at     timestamptz
);

-- One thread per pair. Named rather than inline so section 5's ON CONFLICT can
-- point at it and fail loudly if it is ever dropped.
do $$
begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.conversations'::regclass
                    and conname  = 'conversations_one_per_pair') then
    alter table public.conversations
      add constraint conversations_one_per_pair
      unique (department_id, service_provider_id);
  end if;

  -- The denormalised community_id is only as good as whatever last wrote it.
  -- open_conversation derives it from the department, but a thread whose two
  -- columns disagree would be readable by the wrong community's admins -- the
  -- read policy calls is_community_admin(community_id) precisely so it does not
  -- have to join. Same shape and same action as
  -- staff_assignments_department_tenant_fkey (0019).
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.conversations'::regclass
                    and conname  = 'conversations_department_tenant_fkey') then
    alter table public.conversations
      add constraint conversations_department_tenant_fkey
      foreign key (department_id, community_id)
      references public.departments (id, community_id)
      on delete cascade;
  end if;
end $$;

-- The thread list, both sides. A provider sorts their threads by recency across
-- every community at once, so this index carries no community predicate.
create index if not exists conversations_provider_recent_idx
  on public.conversations (service_provider_id, last_message_at desc nulls last);

create index if not exists conversations_department_recent_idx
  on public.conversations (department_id, last_message_at desc nulls last);

comment on table public.conversations is
  'One chat thread per (department, service provider). Created on first use by '
  'open_conversation; the unique constraint makes a duplicate impossible.';

comment on column public.conversations.community_id is
  'Denormalised from the department so the read policy can call '
  'is_community_admin without a join. Kept honest by open_conversation, which '
  'is the only writer.';

-- ---------------------------------------------------------------------------
-- 2. The messages
-- ---------------------------------------------------------------------------

create table if not exists public.conversation_messages (
  id                   uuid primary key default gen_random_uuid(),
  conversation_id      uuid not null
                         references public.conversations(id) on delete cascade,
  author_membership_id uuid references public.community_memberships(id)
                         on delete set null,
  author_provider_id   uuid references public.service_providers(id)
                         on delete set null,
  body                 text not null,
  created_at           timestamptz not null default now()
);

do $$
begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.conversation_messages'::regclass
                    and conname  = 'conversation_messages_body_check') then
    alter table public.conversation_messages
      add constraint conversation_messages_body_check
      check (length(btrim(body)) between 1 and 4000);
  end if;

  -- Exactly one author. `num_nonnulls` rather than a pair of OR'd null tests,
  -- because the interesting failure is BOTH being set -- a hired provider
  -- authoring as themselves and as their membership in the same row -- and the
  -- naive spelling of this check misses it.
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.conversation_messages'::regclass
                    and conname  = 'conversation_messages_one_author') then
    alter table public.conversation_messages
      add constraint conversation_messages_one_author
      check (num_nonnulls(author_membership_id, author_provider_id) = 1);
  end if;
end $$;

-- Reading a thread is always "this conversation, oldest first".
create index if not exists conversation_messages_thread_idx
  on public.conversation_messages (conversation_id, created_at);

comment on table public.conversation_messages is
  'Messages in a hiring conversation. Exactly one of author_membership_id and '
  'author_provider_id is set -- the provider side may hold no membership in '
  'this community, which is why there are two columns rather than one.';

-- ---------------------------------------------------------------------------
-- 3. Is the caller in this thread?
--
-- One definition, used by both read policies, both RPCs and the API. Written
-- once here because a participation test that exists in four places is a
-- participation test that will mean four things.
-- ---------------------------------------------------------------------------

create or replace function public.is_conversation_participant(p_conversation_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
      from public.conversations c
     where c.id = p_conversation_id
       and (
         public.can_manage_department(c.department_id)
         or exists (
           select 1 from public.service_providers p
            where p.id = c.service_provider_id
              and p.profile_id = auth.uid()
         )
       )
  );
$$;

comment on function public.is_conversation_participant(uuid) is
  'True when the caller is one of the two sides of this thread: an admin or '
  'manager of its department, or the service provider it belongs to. '
  'Supervisors are not participants -- this is the hiring conversation.';

grant execute on function public.is_conversation_participant(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 4. Reads
-- ---------------------------------------------------------------------------

-- The thread list. Both counterparts are projected on every row rather than one
-- "other side" column, because who the other side is depends on who is asking
-- and the view does not know. The client picks; the API does not have to run
-- the query twice.
drop view if exists public.conversation_overview;
create view public.conversation_overview
with (security_invoker = true) as
select
  c.id,
  c.community_id,
  c.department_id,
  c.service_provider_id,
  c.created_at,
  c.last_message_at,
  com.name          as community_name,
  d.name            as department_name,
  d.kind            as department_kind,
  p.display_name    as provider_display_name,
  p.headline        as provider_headline,
  p.profile_id      as provider_profile_id,
  m.last_body       as last_message_body,
  coalesce(m.message_count, 0) as message_count
from public.conversations c
join public.communities com      on com.id = c.community_id
join public.departments d        on d.id = c.department_id
join public.service_providers p  on p.id = c.service_provider_id
left join lateral (
  select
    (select cm.body
       from public.conversation_messages cm
      where cm.conversation_id = c.id
      order by cm.created_at desc
      limit 1)                                                   as last_body,
    (select count(*) from public.conversation_messages cm2
      where cm2.conversation_id = c.id)                          as message_count
) m on true;

comment on view public.conversation_overview is
  'Thread list with both counterparts named and the last line of each. '
  'security_invoker, so section 6 decides which threads a caller can see.';

grant select on public.conversation_overview to authenticated;

-- One message with its author's name resolved. Two nullable author columns
-- become one label and one side, so a client renders a thread without knowing
-- that the two parties are stored in different tables.
drop view if exists public.conversation_message_overview;
create view public.conversation_message_overview
with (security_invoker = true) as
select
  cm.id,
  cm.conversation_id,
  cm.body,
  cm.created_at,
  case when cm.author_provider_id is not null then 'provider' else 'department' end
                                              as author_side,
  coalesce(p.display_name, pf.full_name, 'Unknown') as author_name,
  coalesce(p.profile_id, mem.profile_id)      as author_profile_id
from public.conversation_messages cm
left join public.service_providers p       on p.id = cm.author_provider_id
left join public.community_memberships mem on mem.id = cm.author_membership_id
left join public.profiles pf               on pf.id = mem.profile_id;

comment on view public.conversation_message_overview is
  'Messages with the author resolved to a name and a side. The name is a '
  'snapshot of the profile as it is now, not as it was when written -- the '
  'same convention complaint comments use.';

grant select on public.conversation_message_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 5. Writes
--
-- Both definer, both checking their own authorization, and between them the
-- only way a row reaches either table.
-- ---------------------------------------------------------------------------

-- Open the thread, or hand back the one that already exists.
--
-- Idempotent by construction. The caller does not ask whether a thread exists
-- and then create one -- that read-then-write is the race the unique constraint
-- was added to remove, and ON CONFLICT is how the constraint is used rather
-- than merely declared.
create or replace function public.open_conversation(
  p_department_id       uuid,
  p_service_provider_id uuid
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_id           uuid;
begin
  select d.community_id into v_community_id
    from public.departments d
   where d.id = p_department_id;

  if v_community_id is null then
    raise exception 'No such department.' using errcode = 'HB404';
  end if;

  if not exists (select 1 from public.service_providers sp
                  where sp.id = p_service_provider_id) then
    raise exception 'No such service provider.' using errcode = 'HB404';
  end if;

  -- Either side may open it: a manager sizing up a candidate, or a provider
  -- asking a question before applying. Anybody else is not in this thread and
  -- creating it would be how they got in.
  if not (
    public.can_manage_department(p_department_id)
    or exists (select 1 from public.service_providers sp
                where sp.id = p_service_provider_id
                  and sp.profile_id = auth.uid())
  ) then
    raise exception 'You cannot open this conversation.' using errcode = 'HB403';
  end if;

  insert into public.conversations (
    community_id, department_id, service_provider_id
  )
  values (v_community_id, p_department_id, p_service_provider_id)
  -- `do update` setting a column to the value it already holds, rather than
  -- `do nothing`: DO NOTHING returns no row, so RETURNING would hand back null
  -- for exactly the case this function exists to serve -- the second caller.
  on conflict on constraint conversations_one_per_pair do update
    set department_id = excluded.department_id
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.open_conversation(uuid, uuid) is
  'Return the thread for this (department, provider) pair, creating it if it is '
  'the first time either side has written. Idempotent: two managers opening it '
  'at once get the same row.';

grant execute on function public.open_conversation(uuid, uuid) to authenticated;

-- Post one message.
--
-- The author column is chosen from the thread rather than from the caller's
-- request, so `author_provider_id is not null` means "the worker said this" in
-- every thread -- including one where the worker has since been hired and holds
-- a membership that would otherwise be an equally true answer.
create or replace function public.post_conversation_message(
  p_conversation_id uuid,
  p_body            text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_conversation public.conversations%rowtype;
  v_provider_id  uuid;
  v_membership   uuid;
  v_id           uuid;
begin
  select * into v_conversation
    from public.conversations
   where id = p_conversation_id;

  if not found then
    raise exception 'No such conversation.' using errcode = 'HB404';
  end if;

  select sp.id into v_provider_id
    from public.service_providers sp
   where sp.id = v_conversation.service_provider_id
     and sp.profile_id = auth.uid();

  if v_provider_id is null then
    -- The department side. The membership recorded is the caller's in THIS
    -- community, which is the one the department belongs to -- not whichever
    -- membership a multi-community admin happens to default to.
    --
    -- No tie-break, because there can be no tie: 0001:45's
    -- memberships_active_person_community is unique on (community_id,
    -- profile_id) where ended_at is null, and this predicate is a subset of it.
    -- An ORDER BY here would be ranking a set that cannot hold two rows.
    select m.id into v_membership
      from public.community_memberships m
     where m.community_id = v_conversation.community_id
       and m.profile_id = auth.uid()
       and m.status = 'active'
       and m.ended_at is null;

    if v_membership is null
       or not public.can_manage_department(v_conversation.department_id) then
      raise exception 'You are not part of this conversation.'
        using errcode = 'HB403';
    end if;
  end if;

  insert into public.conversation_messages (
    conversation_id, author_membership_id, author_provider_id, body
  )
  values (p_conversation_id, v_membership, v_provider_id, btrim(p_body))
  returning id into v_id;

  update public.conversations
     set last_message_at = now()
   where id = p_conversation_id;

  return v_id;
end;
$$;

comment on function public.post_conversation_message(uuid, text) is
  'Append a message, as whichever side of the thread the caller is on, and '
  'stamp last_message_at. Raises HB403 for a non-participant and HB404 for a '
  'thread the caller cannot see.';

grant execute on function public.post_conversation_message(uuid, text)
  to authenticated;

-- ---------------------------------------------------------------------------
-- 6. Row security
--
-- Read policies only, the posture of 0031, 0034 and 0035: every write above is
-- a definer function that checked its own authorization, so there is
-- deliberately no insert, update or delete policy on either table.
--
-- The plan's verification for this step is one sentence -- "RLS denies a
-- non-participant" -- and these two policies are where that is either true or
-- not.
-- ---------------------------------------------------------------------------

alter table public.conversations enable row level security;
alter table public.conversation_messages enable row level security;

drop policy if exists conversations_read on public.conversations;
create policy conversations_read on public.conversations
  for select to authenticated
  using (
    public.can_manage_department(department_id)
    or exists (
      select 1 from public.service_providers p
       where p.id = conversations.service_provider_id
         and p.profile_id = auth.uid()
    )
  );

drop policy if exists conversation_messages_read on public.conversation_messages;
create policy conversation_messages_read on public.conversation_messages
  for select to authenticated
  using (public.is_conversation_participant(conversation_id));

grant select on public.conversations to authenticated;
grant select on public.conversation_messages to authenticated;
