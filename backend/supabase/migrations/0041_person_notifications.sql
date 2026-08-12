-- The notification substrate stops being addressed to a membership and starts
-- being addressed to a person.
--
-- docs/design/AUTH_AND_SESSION_DESIGN.md 4; docs/plans/SERVICE_OPERATIONS_PROGRESS.md 6.10.
--
-- THE ONE IDEA THIS FILE EXISTS FOR
--
-- `0030` made one decision -- the recipient of a notification is a
-- `community_memberships` row -- and then repeated it eleven times: a `not null`
-- column, an inner join in the feed view, an RLS predicate, a `not null` column
-- on `push_subscriptions`, the claim function's return type, the sender's
-- lookup, and five API guards. It was right for the population it was written
-- for. A resident *is* a membership.
--
-- A service person is not. They register before anybody has hired them, they
-- apply to departments, and they are told the answer -- all of it while holding
-- no membership anywhere. Under `0030` there is no row that can carry that
-- message: `recipient_membership_id` is `not null`, so the notification cannot
-- be written, and if it could the feed view's join would drop it, and if it
-- survived that the read policy would refuse it, and if it passed that the push
-- sender would find no subscriptions because the browser could not have
-- registered one -- `POST /push/subscriptions` requires the membership too.
--
-- So this file moves the address one level down, from the membership to the
-- profile behind it. `recipient_membership_id` stays and keeps its second job:
-- saying which community a notification was *about*, which is what
-- `notification_overview.community_id` and the SSE trigger already use it for.
--
-- WHAT THAT ALSO FIXES, WHICH IS NOT INCIDENTAL
--
-- 1. A person with memberships in two communities could receive Web Push for
--    only one. `push_subscriptions.endpoint` is globally unique *by design* --
--    the endpoint URL is the browser's identity to the push service -- and the
--    row carried a membership, so subscribing the same browser from a second
--    community MOVED the row and silently stopped the first community's pushes.
--    Nothing had ever held two memberships until the service-operations build.
-- 2. `mark_all_notifications_read` cleared one membership's rows while the badge
--    counted the whole feed. One caller, two answers, no error.
--
-- THE RULE THIS OVERTURNS, STATED PLAINLY
--
-- `0030` says, of `is_own_membership`: "Someone who has left the community stops
-- being able to read what was addressed to them." That stops being true here,
-- and `docs/design/README.md` requires a ruling that overturns something already
-- written to name it.
--
-- The reason: with one membership the two predicates agree; with several they do
-- not. A worker removed from one community would lose that community's rows out
-- of a feed that is otherwise theirs, and the badge would fall with no event to
-- explain it. A notification is a copy of something the person was already told,
-- and every inbox in the world retains those. What ending a membership must stop
-- is *new* notifications -- and `notify_community_roles` already filters on
-- `status = 'active'` at the moment of writing, which is where that rule belongs.
--
-- ALSO HERE, BECAUSE THEY ARE THE FIRST TWO WRITERS THAT NEEDED IT
--
-- `post_conversation_message` (0038) has never notified anybody, because the
-- side that most needs telling is the side with no membership. And
-- `POST /notices` has never notified anybody either, for a different reason:
-- `notices_repository.insert_notice` is a plain PostgREST insert with no RPC to
-- add a `perform` to. Both are closed below -- the first inside the existing
-- function, the second as a trigger, which is `0030` section 5's rule applied a
-- second time: delivery is a property of the system, not something each writer
-- remembers.

-- ---------------------------------------------------------------------------
-- 1. The recipient
--
-- `recipient_profile_id` is *always* populated, including for the membership
-- case, so that one predicate answers ownership everywhere and the push claim
-- can return a single column. The check constraint is what stops a row that
-- addresses nobody -- a notification with two null recipients is invisible in
-- the feed and undeliverable by push, which looks exactly like the feature being
-- broken.
-- ---------------------------------------------------------------------------

alter table public.notifications
  add column if not exists recipient_profile_id uuid
    references public.profiles(id) on delete cascade;

alter table public.notifications
  alter column recipient_membership_id drop not null;

-- Backfill before the constraint, so re-running this file on a database that
-- already has rows cannot fail. No database has any (see the migrations README),
-- which is exactly why this has to be written correctly rather than tested.
update public.notifications n
   set recipient_profile_id = m.profile_id
  from public.community_memberships m
 where m.id = n.recipient_membership_id
   and n.recipient_profile_id is null;

do $$
begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.notifications'::regclass
                    and conname  = 'notifications_has_recipient') then
    alter table public.notifications
      add constraint notifications_has_recipient
      check (recipient_profile_id is not null
             or recipient_membership_id is not null);
  end if;
end $$;

-- The feed read is now "one person, newest first". The 0030 index on
-- (recipient_membership_id, created_at desc) is left alone: it still serves the
-- SSE trigger's lookup and costs one small index on a table nothing scans.
create index if not exists notifications_recipient_profile_created_idx
  on public.notifications (recipient_profile_id, created_at desc);

drop policy if exists notifications_read_own on public.notifications;
create policy notifications_read_own
  on public.notifications
  for select
  to authenticated
  using (recipient_profile_id = auth.uid());

-- ---------------------------------------------------------------------------
-- 2. The two writers
--
-- `notify_member` keeps its signature exactly, so not one of the twenty-odd
-- call sites in 0031-0040 changes. It resolves the profile itself, which is the
-- only way "always populated" can be true without trusting every caller to
-- remember.
-- ---------------------------------------------------------------------------

create or replace function public.notify_member(
  p_membership_id uuid,
  p_kind text,
  p_payload jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  new_id     uuid;
  v_profile  uuid;
begin
  if p_membership_id is null then
    raise exception 'notify_member requires a recipient membership'
      using errcode = '22004';
  end if;

  if coalesce(btrim(p_kind), '') = '' then
    raise exception 'notify_member requires a kind' using errcode = '22004';
  end if;

  select m.profile_id into v_profile
    from public.community_memberships m
   where m.id = p_membership_id;

  -- A membership that does not exist is a caller bug, not a silent no-op: the
  -- row would satisfy the check constraint through its membership column and
  -- then be unreadable by anyone, because the policy asks about the profile.
  if v_profile is null then
    raise exception 'notify_member was given a membership that does not exist'
      using errcode = '23503';
  end if;

  insert into public.notifications (
    recipient_membership_id, recipient_profile_id, kind, payload
  )
  values (
    p_membership_id, v_profile, btrim(p_kind), coalesce(p_payload, '{}'::jsonb)
  )
  returning id into new_id;

  return new_id;
end;
$$;

comment on function public.notify_member(uuid, text, jsonb) is
  'Write one notification about one community, in the caller''s transaction. Resolves the recipient profile itself so ownership has a single predicate.';

revoke all on function public.notify_member(uuid, text, jsonb)
  from public, anon, authenticated;
grant execute on function public.notify_member(uuid, text, jsonb) to service_role;

-- The membership-less writer. Same discipline, same grants, and deliberately no
-- community: a notification that has no membership has no community either, and
-- inventing one would put a row in somebody's feed under a heading they have no
-- relationship to.
create or replace function public.notify_profile(
  p_profile_id uuid,
  p_kind text,
  p_payload jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  new_id uuid;
begin
  if p_profile_id is null then
    raise exception 'notify_profile requires a recipient profile'
      using errcode = '22004';
  end if;

  if coalesce(btrim(p_kind), '') = '' then
    raise exception 'notify_profile requires a kind' using errcode = '22004';
  end if;

  insert into public.notifications (recipient_profile_id, kind, payload)
  values (p_profile_id, btrim(p_kind), coalesce(p_payload, '{}'::jsonb))
  returning id into new_id;

  return new_id;
end;
$$;

comment on function public.notify_profile(uuid, text, jsonb) is
  'Write one notification to a person who may hold no membership at all -- a service provider who has registered and not yet been hired. No community, so no SSE frame; the feed and Web Push carry it.';

revoke all on function public.notify_profile(uuid, text, jsonb)
  from public, anon, authenticated;
grant execute on function public.notify_profile(uuid, text, jsonb) to service_role;

-- ---------------------------------------------------------------------------
-- 3. The feed projection
--
-- `join` becomes `left join`: a profile-addressed row has no membership, and an
-- inner join is how it would vanish between being written and being read.
-- `community_id` is therefore nullable now, which is the truth -- the API never
-- filtered on it and the wire model never carried it.
--
-- `recipient_profile_id` is added to the projection because it is what the
-- repository filters on. `recipient_membership_id` stays: it is what the admin
-- dashboard's per-community reads would need if they are ever written, and
-- removing a column from a view is a breaking change for a benefit of nothing.
-- ---------------------------------------------------------------------------

drop view if exists public.notification_overview;
create view public.notification_overview
with (security_invoker = true) as
select
  n.id,
  n.recipient_membership_id,
  n.recipient_profile_id,
  m.community_id,
  n.kind,
  n.payload,
  n.read_at,
  (n.read_at is null) as is_unread,
  n.created_at
from public.notifications n
left join public.community_memberships m on m.id = n.recipient_membership_id;

comment on view public.notification_overview is
  'A person''s notification feed, across every community they belong to and including rows that belong to none. Runs as the caller (security_invoker), so the notifications RLS policy applies.';

grant select on public.notification_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 4. Marking read
--
-- `mark_notification_read` keeps its signature and swaps its predicate.
--
-- `mark_all_notifications_read` loses its argument, and that is a correction
-- rather than a simplification. It cleared one membership's rows while the badge
-- it exists to clear counts the whole feed; for a resident with one membership
-- those are the same set, which is why nothing ever caught it. With the argument
-- gone the two cannot disagree.
-- ---------------------------------------------------------------------------

create or replace function public.mark_notification_read(p_notification_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  updated integer;
begin
  update public.notifications n
     set read_at = coalesce(n.read_at, now())
   where n.id = p_notification_id
     and n.recipient_profile_id = auth.uid();

  get diagnostics updated = row_count;
  return updated > 0;
end;
$$;

-- The old two-argument form has to go explicitly: `create or replace` cannot
-- change a signature, so without this drop both would exist and PostgREST would
-- resolve whichever the caller's arguments matched.
drop function if exists public.mark_all_notifications_read(uuid);

create or replace function public.mark_all_notifications_read()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  updated integer;
begin
  update public.notifications
     set read_at = now()
   where recipient_profile_id = auth.uid()
     and read_at is null;

  get diagnostics updated = row_count;
  return updated;
end;
$$;

comment on function public.mark_all_notifications_read() is
  'Clear the caller''s whole badge. No argument: the set it clears and the set the badge counts are the same set by construction.';

revoke all on function public.mark_all_notifications_read() from public, anon;
grant execute on function public.mark_all_notifications_read() to authenticated;

-- ---------------------------------------------------------------------------
-- 5. push_subscriptions is keyed on the person
--
-- The column change is the small half. The argument change is the point: once
-- the column is the profile, the only value the caller could legitimately pass
-- is `auth.uid()`, so passing it in and validating it against the session it
-- came from is a parameter that exists to be checked. Deleting it removes the
-- forgery surface instead of guarding it -- the same reasoning `0030` applied to
-- `notify_member`'s grant, one layer up.
-- ---------------------------------------------------------------------------

alter table public.push_subscriptions
  add column if not exists profile_id uuid references public.profiles(id) on delete cascade;

update public.push_subscriptions s
   set profile_id = m.profile_id
  from public.community_memberships m
 where m.id = s.membership_id
   and s.profile_id is null;

-- Any row still without a profile addresses a membership that no longer exists,
-- so it can reach nobody. Delete before the not-null rather than fail on it.
delete from public.push_subscriptions where profile_id is null;

alter table public.push_subscriptions
  alter column profile_id set not null;

-- Dropping the column drops `push_subscriptions_membership_idx` with it.
alter table public.push_subscriptions
  drop column if exists membership_id;

create index if not exists push_subscriptions_profile_idx
  on public.push_subscriptions (profile_id);

drop function if exists public.register_push_subscription(uuid, text, text, text, text);

create or replace function public.register_push_subscription(
  p_endpoint text,
  p_p256dh text,
  p_auth text,
  p_user_agent text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  subscription_id uuid;
begin
  if auth.uid() is null then
    raise exception 'Sign in before registering a browser for push'
      using errcode = '42501';
  end if;

  if coalesce(btrim(p_endpoint), '') = ''
     or coalesce(btrim(p_p256dh), '') = ''
     or coalesce(btrim(p_auth), '') = '' then
    raise exception 'A push subscription needs an endpoint and both keys'
      using errcode = '22004';
  end if;

  -- Idempotent on `endpoint`, unchanged from 0030 and for the same reason: the
  -- browser re-subscribes on every service-worker update and after any VAPID
  -- rotation. What changes is what the conflict overwrites -- the owning person
  -- rather than the owning membership, so a shared laptop still moves to
  -- whoever subscribed last and a person's own second community no longer
  -- steals the row from their first.
  insert into public.push_subscriptions (
    profile_id, endpoint, p256dh_key, auth_key, user_agent
  )
  values (
    auth.uid(), btrim(p_endpoint), btrim(p_p256dh), btrim(p_auth), p_user_agent
  )
  on conflict (endpoint) do update
     set profile_id    = excluded.profile_id,
         p256dh_key    = excluded.p256dh_key,
         auth_key      = excluded.auth_key,
         user_agent    = excluded.user_agent,
         failure_count = 0
  returning id into subscription_id;

  return subscription_id;
end;
$$;

drop function if exists public.delete_push_subscription(uuid, text);

create or replace function public.delete_push_subscription(p_endpoint text)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  removed integer;
begin
  -- Both predicates, exactly as 0030 had it. The endpoint is unique, so the
  -- owner adds nothing to the lookup -- it is there so that knowing someone
  -- else's endpoint is not enough to unsubscribe their phone.
  delete from public.push_subscriptions
   where endpoint = btrim(p_endpoint)
     and profile_id = auth.uid();

  get diagnostics removed = row_count;
  return removed;
end;
$$;

revoke all on function public.register_push_subscription(text, text, text, text)
  from public, anon;
grant execute on function public.register_push_subscription(text, text, text, text)
  to authenticated;
revoke all on function public.delete_push_subscription(text) from public, anon;
grant execute on function public.delete_push_subscription(text) to authenticated;

-- ---------------------------------------------------------------------------
-- 6. The sender's claim returns a person
-- ---------------------------------------------------------------------------

drop function if exists public.claim_push_batch(integer);

create or replace function public.claim_push_batch(p_limit integer default 50)
returns table (
  notification_id uuid,
  profile_id      uuid,
  kind            text,
  payload         jsonb,
  created_at      timestamptz
)
language sql
security definer
set search_path = public
as $$
  update public.notifications n
     set push_sent_at  = now(),
         push_attempts = n.push_attempts + 1
   where n.id in (
     select c.id
       from public.notifications c
      where c.push_sent_at is null
        and c.created_at > now() - interval '1 hour'
      order by c.created_at
      limit greatest(coalesce(p_limit, 50), 1)
      for update skip locked
   )
  returning n.id, n.recipient_profile_id, n.kind, n.payload, n.created_at;
$$;

comment on function public.claim_push_batch(integer) is
  'Atomically claim un-pushed notifications from the last hour. service_role only; at-most-once by design.';

revoke all on function public.claim_push_batch(integer)
  from public, anon, authenticated;
grant execute on function public.claim_push_batch(integer) to service_role;

-- ---------------------------------------------------------------------------
-- 7. The conversation finally says something
--
-- `0038` shipped with no notification at all, and the journal has carried it as
-- an open item across three steps. The reason it stayed open is section 1 of
-- this file: the side that most needs telling is the provider, and the provider
-- may hold no membership.
--
-- The two directions are addressed differently and cannot be merged. A
-- department is a set of people, so it takes `notify_member` once per manager;
-- a provider is one person who may be nobody's member, so it takes
-- `notify_profile`. Self-notification is impossible by construction rather than
-- by an exclusion argument: the author is on one side and the recipients are
-- all on the other.
--
-- The body carries a 140-character preview. That is a deliberate exception to
-- nothing -- section 10.8's rule is that a *secret* never enters a payload, and
-- a message someone typed to you is the opposite of a secret. A push that says
-- only "new message" makes the reader open the app to find out whether it
-- mattered.
-- ---------------------------------------------------------------------------

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
  v_text         text;
  v_preview      text;
  v_row          record;
  v_department   text;
  v_provider     text;
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

  v_text := btrim(p_body);

  insert into public.conversation_messages (
    conversation_id, author_membership_id, author_provider_id, body
  )
  values (p_conversation_id, v_membership, v_provider_id, v_text)
  returning id into v_id;

  update public.conversations
     set last_message_at = now()
   where id = p_conversation_id;

  v_preview := left(v_text, 140);

  select d.name into v_department
    from public.departments d
   where d.id = v_conversation.department_id;

  select sp.display_name into v_provider
    from public.service_providers sp
   where sp.id = v_conversation.service_provider_id;

  if v_provider_id is not null then
    -- Worker to department. The audience is exactly what can_manage_department
    -- accepts, spelled out here because that function answers about the caller
    -- and this needs the set.
    for v_row in
      select m.id
        from public.community_memberships m
       where m.community_id = v_conversation.community_id
         and m.status = 'active'
         and m.ended_at is null
         and (
           m.role = 'admin'
           or (m.role = 'manager'
               and (m.department_id is null
                    or m.department_id = v_conversation.department_id))
         )
    loop
      perform public.notify_member(
        v_row.id,
        'conversation.message',
        jsonb_build_object(
          'title', coalesce(v_provider, 'A service partner') || ' replied',
          'body',  v_preview,
          'url',   '/admin/messages?conversation=' || p_conversation_id::text
        )
      );
    end loop;
  else
    -- Department to worker, who may hold no membership anywhere. This call is
    -- the entire reason section 1 of this file exists.
    perform public.notify_profile(
      (select sp.profile_id from public.service_providers sp
        where sp.id = v_conversation.service_provider_id),
      'conversation.message',
      jsonb_build_object(
        'title', coalesce(v_department, 'A department') || ' replied',
        'body',  v_preview,
        'url',   '/worker/messages?conversation=' || p_conversation_id::text
      )
    );
  end if;

  return v_id;
end;
$$;

comment on function public.post_conversation_message(uuid, text) is
  'Append a message, as whichever side of the thread the caller is on, stamp '
  'last_message_at, and notify the other side -- the department by membership, '
  'the provider by profile, because the provider may hold no membership.';

grant execute on function public.post_conversation_message(uuid, text)
  to authenticated;

-- ---------------------------------------------------------------------------
-- 8. A published notice reaches the people it is for
--
-- US-2.4 has been "partial" since the resident build on one missing writer, and
-- `notifications_service._FALLBACK_TITLES` has carried `notice.published` the
-- whole time -- the vocabulary was written and nothing ever emitted it.
--
-- A trigger rather than a service call, because there is nothing to add a call
-- TO. `notices_repository.insert_notice` is a plain PostgREST insert and its
-- docstring defends that: "a single-table, single-statement write, so the
-- transaction PostgREST gives it for free is the whole transaction it needs."
-- Adding an RPC purely to hang a notification off it would replace a correct
-- one-statement write with a function whose only extra job is the thing a
-- trigger does for free -- and 0030 section 5 already made this exact argument
-- about the SSE outbox.
--
-- `when (new.published_at is not null)` is what keeps a future draft state
-- silent. The column is already nullable for that reason.
-- ---------------------------------------------------------------------------

create or replace function public.emit_notice_published()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.notify_community_roles(
    new.community_id,
    array['resident'],
    'notice.published',
    jsonb_build_object(
      'title', new.title,
      'body',  left(coalesce(new.body, ''), 140),
      'url',   '/resident/notices'
    ),
    new.author_membership_id
  );
  return new;
end;
$$;

comment on function public.emit_notice_published() is
  'Fan a published notice out to every active resident of its community, excluding its author.';

drop trigger if exists notices_notify_residents on public.notices;
create trigger notices_notify_residents
  after insert on public.notices
  for each row
  when (new.published_at is not null)
  execute function public.emit_notice_published();

-- ---------------------------------------------------------------------------
-- 9. The two hiring notifications that could not be written before
--
-- `0035` has five notification sites and two holes, and both holes have the
-- same one-line explanation, which its own comment gives:
--
--   "The provider may hold no membership anywhere, so there is nobody to
--    notify_member."
--
-- Section 2 removed that constraint, so:
--
--   * An **invited** provider is told they were invited. Today
--     `invite_service_provider` notifies nobody and the invitation waits on the
--     provider happening to open their applications screen.
--   * A **rejected applicant** is told they were rejected. `decide_service_
--     application` notifies `v_membership`, which is the membership the
--     acceptance creates -- so it is null on a rejection and the applicant hears
--     nothing at all. Waiting silently is the worst of the three outcomes and it
--     was the only one with no message.
--
-- A TRIGGER RATHER THAN A REWRITE, AND THE SCOPING IS THE WHOLE DESIGN.
--
-- Both functions are long, and re-declaring a hundred lines of plpgsql in this
-- file to add one `perform` would make this migration the place those functions
-- live -- which is how a schema ends up with its logic scattered across the
-- files that last touched it. The trigger adds only what is absent, and its
-- WHEN clauses are written to be disjoint from what `0035` already sends:
--
--   insert, direction = 'invited'   -> 0035 sends nothing. This sends.
--   update to 'rejected', 'applied' -> 0035 sends nothing. This sends.
--   update to 'accepted', 'applied' -> 0035 notifies the new membership. Silent
--                                      here, or the person would be told twice.
--   any 'invited' decision          -> 0035 notifies the managers. Silent here.
--
-- WHILE WE ARE HERE: one of `0035`'s notifications only starts working today.
--
-- `remove_department_member` notifies the membership it has just ended. Under
-- `0030`'s read policy -- `is_own_membership`, which requires `status =
-- 'active'` -- that row was unreadable by its own recipient the moment it was
-- written. Section 1's policy asks about the profile, so being told you have
-- been taken off a roster now actually reaches you. Nothing had to change for
-- that; it is a consequence of the ownership predicate and is recorded here
-- because a reader comparing the two files deserves to know it was not always
-- so.
-- ---------------------------------------------------------------------------

create or replace function public.emit_service_application_notice()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_profile    uuid;
  v_department text;
  v_community  text;
begin
  select sp.profile_id into v_profile
    from public.service_providers sp
   where sp.id = new.service_provider_id;

  if v_profile is null then
    return new;
  end if;

  select d.name into v_department
    from public.departments d
   where d.id = new.department_id;

  select c.name into v_community
    from public.communities c
   where c.id = new.community_id;

  if tg_op = 'INSERT' then
    perform public.notify_profile(
      v_profile,
      'service_invitation_received',
      jsonb_build_object(
        'title', coalesce(v_community, 'A community') || ' invited you to work with them',
        'body',  coalesce(v_department, 'A department')
                 || coalesce(' — ' || nullif(btrim(coalesce(new.job_title, '')), ''), ''),
        'url',   '/worker/communities?tab=applications'
      )
    );
  else
    perform public.notify_profile(
      v_profile,
      'service_application_rejected',
      jsonb_build_object(
        'title', 'Your application was not accepted',
        'body',  coalesce(v_department, 'The department')
                 || ' at ' || coalesce(v_community, 'the community'),
        'url',   '/worker/communities?tab=applications'
      )
    );
  end if;

  return new;
end;
$$;

comment on function public.emit_service_application_notice() is
  'Tell a service provider they were invited, or that their application was refused. Addressed by profile because neither of those people holds a membership.';

drop trigger if exists service_applications_notify_invited on public.service_applications;
create trigger service_applications_notify_invited
  after insert on public.service_applications
  for each row
  when (new.direction = 'invited')
  execute function public.emit_service_application_notice();

drop trigger if exists service_applications_notify_rejected on public.service_applications;
create trigger service_applications_notify_rejected
  after update of status on public.service_applications
  for each row
  when (old.status = 'pending'
        and new.status = 'rejected'
        and new.direction = 'applied')
  execute function public.emit_service_application_notice();
