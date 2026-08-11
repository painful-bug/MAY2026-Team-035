-- The notification substrate: the durable record, and the two transports' hooks.
--
-- docs/design/RESIDENT_BACKEND_DESIGN.md 5.8, 10.3, 10.4.
--
-- THE ONE IDEA THIS FILE EXISTS FOR
--
-- Every user-visible event writes a `notifications` row **first**. SSE and Web
-- Push are two *deliveries* of that row, never the record of it. SSE is
-- at-most-once and connection-scoped -- the admin design makes "the payload is a
-- hint, never truth" load-bearing, and it is only safe because of that rule --
-- and a push may simply not arrive. A resident whose phone was locked when a
-- visitor reached the gate must still find out. So: one truth, two transports.
--
-- `sse_events` cannot be that truth. `0024` prunes it every fifteen minutes,
-- deliberately, because it is ephemeral; building durability on a table designed
-- to be deleted inverts both.
--
-- WHAT WAS ALREADY HERE
--
-- The baseline declares the table and **no backend code has ever touched it**:
--
--   notifications (id, recipient_membership_id, kind, payload, read_at, created_at)
--
-- `recipient_membership_id` is exactly the dimension the outbox lacks -- per
-- recipient, and tenant-scoped transitively through the membership. This file
-- adds the index that read needs, two columns for the push sender's lease, a
-- projection, the writer, the trigger that connects it to the stream, and the
-- subscription table push needs. Nothing about the baseline's five columns
-- changes.
--
-- ROW SECURITY, WHICH WAS MISSING AND IS NOT A SMALL POINT
--
-- `notifications` is reachable through PostgREST and has no policy, so today any
-- authenticated user can read every notification in the project -- other
-- people's complaint updates, visitor names, invoice amounts. Nothing exploits
-- it because nothing writes the table. **This migration is what starts writing
-- it**, so the policy lands in the same file rather than after it. Same
-- reasoning as `0024` enabling RLS on `sse_events`, and the same timing rule as
-- `0028`: the fix ships before the thing that makes it exploitable.
--
-- Reads get a policy (your own rows, through `notification_overview`). Writes
-- get none, so the only way to write or mark a notification is the SECURITY
-- DEFINER functions below -- which is the paradigm the rest of this schema
-- already follows, and here it also means a client cannot mark someone else's
-- notification read by knowing its id.

-- ---------------------------------------------------------------------------
-- 1. Ownership, as a predicate
--
-- The third of the shared RLS predicates, alongside `is_community_member` and
-- `is_community_admin` from 0019. Ownership belongs in SQL rather than in a
-- Python `where` clause: a predicate the database applies cannot be forgotten by
-- the next endpoint that reads the same table.
--
-- `status = 'active'` matters. Someone who has left the community stops being
-- able to read what was addressed to them -- which is already what the API's
-- `get_active_membership` decides, and the two should not disagree.
-- ---------------------------------------------------------------------------

create or replace function public.is_own_membership(p_membership_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.community_memberships m
     where m.id = p_membership_id
       and m.profile_id = auth.uid()
       and m.status = 'active'
       and m.ended_at is null
  );
$$;

comment on function public.is_own_membership(uuid) is
  'True when the membership belongs to the calling user and is still active. Used by RLS policies and the notification RPCs.';

grant execute on function public.is_own_membership(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 2. The record: indexes, the push lease, and the policy
-- ---------------------------------------------------------------------------

alter table public.notifications
  -- The lease. `push_sent_at` is set when a sender *claims* the row, not when
  -- the push succeeds -- see section 7 for why at-most-once is the correct bias
  -- for something that buzzes a phone.
  add column if not exists push_sent_at timestamptz,
  add column if not exists push_attempts smallint not null default 0;

-- The feed read: one recipient, newest first. Also serves the unread count,
-- which is this index plus a filter on a column already in the row.
create index if not exists notifications_recipient_created_idx
  on public.notifications (recipient_membership_id, created_at desc);

-- The sender's claim. Partial, because the rows it wants are a vanishing
-- fraction of the table: everything ever notified is in here forever, and
-- unsent rows exist for seconds.
create index if not exists notifications_push_pending_idx
  on public.notifications (created_at)
  where push_sent_at is null;

alter table public.notifications enable row level security;

-- `drop` first: `create policy` has no `if not exists`, and re-running a
-- migration is meant to be a no-op.
drop policy if exists notifications_read_own on public.notifications;
create policy notifications_read_own
  on public.notifications
  for select
  to authenticated
  using (public.is_own_membership(recipient_membership_id));

-- No insert, update or delete policy, deliberately. Writing is `notify_member`,
-- marking read is `mark_notification_read`, and both are SECURITY DEFINER. A
-- resident holding a notification id still cannot touch the row directly.

-- ---------------------------------------------------------------------------
-- 3. notification_overview
--
-- The feed projection. It exists for the same reason every other read here goes
-- through a view: the column list and the row filter live in one place, and a
-- repository cannot select a column the projection did not intend.
--
-- `community_id` is carried through the membership join. The API never filters
-- on it -- the RLS policy and the recipient predicate are the boundary -- but a
-- notification that cannot say which community it belongs to is one that cannot
-- be reasoned about later.
-- ---------------------------------------------------------------------------

drop view if exists public.notification_overview;
create view public.notification_overview
with (security_invoker = true) as
select
  n.id,
  n.recipient_membership_id,
  m.community_id,
  n.kind,
  n.payload,
  n.read_at,
  -- Computed rather than left to each client: "unread" is a rule, and three
  -- readers deciding independently whether a null timestamp means unread is
  -- three chances to disagree.
  (n.read_at is null) as is_unread,
  n.created_at
from public.notifications n
join public.community_memberships m on m.id = n.recipient_membership_id;

comment on view public.notification_overview is
  'A member''s notification feed. Runs as the caller (security_invoker), so the notifications RLS policy applies and a caller sees only their own rows.';

grant select on public.notification_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 4. notify_member: the one writer
--
-- Every feature RPC calls this **inside the transaction that makes the change**.
-- Same discipline as the outbox and for the same reason: a notification that can
-- exist without its cause, or a cause without its notification, is a bug that
-- cannot be reproduced.
--
-- There is no check constraint on `kind`. A vocabulary list here would have to
-- be edited by every later step that adds a kind, and a migration that must be
-- amended to add a feature is the rigidity this project already decided against
-- for migration numbering. The kinds are documented in RESIDENT_BACKEND_DESIGN.md
-- 10.3 and asserted in the API's tests.
--
-- `payload` is an id, a short title and a deep link -- enough to render a feed
-- row and route a click, never a copy of the record. The record is fetched
-- through its own endpoint, where the ownership predicate already lives.
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
  new_id uuid;
begin
  if p_membership_id is null then
    raise exception 'notify_member requires a recipient membership'
      using errcode = '22004';
  end if;

  if coalesce(btrim(p_kind), '') = '' then
    raise exception 'notify_member requires a kind' using errcode = '22004';
  end if;

  insert into public.notifications (recipient_membership_id, kind, payload)
  values (p_membership_id, btrim(p_kind), coalesce(p_payload, '{}'::jsonb))
  returning id into new_id;

  return new_id;
end;
$$;

comment on function public.notify_member(uuid, text, jsonb) is
  'Write one notification, in the caller''s transaction. The only writer of public.notifications.';

-- `service_role` only, and the reasoning that used to say otherwise was wrong.
--
-- It read: "the callers are the feature RPCs, which run as their own definer,
-- and a resident-initiated write reaches them over the user's client." The first
-- half is true and is exactly why the second half does not follow. Inside a
-- SECURITY DEFINER function the current user *is* the definer, so the EXECUTE
-- check on this call is made against the owner, who owns this function too. The
-- grant to `authenticated` was never load-bearing.
--
-- It was, however, a forgery surface: any signed-in user could call this
-- directly with any membership id and any payload, and `payload.url` is what a
-- notification links to. A notification that appears to come from the
-- association and leads anywhere is phishing with the association's name on it.
--
-- The default EXECUTE grant to PUBLIC is revoked for the same reason. A grant to
-- one role does not remove it; only a revoke does, which is why 0001 pairs the
-- two on every function it locks down and why this file now does too.
revoke all on function public.notify_member(uuid, text, jsonb)
  from public, anon, authenticated;
grant execute on function public.notify_member(uuid, text, jsonb) to service_role;

-- ---------------------------------------------------------------------------
-- 5. The trigger that makes delivery a property of the system
--
-- Feature code writes notifications; nothing else touches the outbox. Add a
-- notification kind and it streams for free -- there is no per-feature "remember
-- to also emit an SSE row" step to forget.
--
-- The row is `audience = 'member'`, which `0028`'s shape constraint requires to
-- carry a `recipient_membership_id` and no `audience_roles`.
--
-- The payload is the id and the kind and nothing else. That is not economy: SSE
-- frames are hints, the client re-reads through `GET /notifications` where the
-- ownership predicate lives, and a stream frame that carried the title would be
-- a second copy of it able to drift from the first.
-- ---------------------------------------------------------------------------

create or replace function public.emit_notification_sse_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  event_community_id uuid;
begin
  select m.community_id into event_community_id
    from public.community_memberships m
   where m.id = new.recipient_membership_id;

  -- No community, no event. The row is still in the feed; only the live nudge
  -- is skipped, and `sse_events.community_id` is `not null` for a reason.
  if event_community_id is null then
    return new;
  end if;

  insert into public.sse_events (
    community_id, topic, payload, audience, recipient_membership_id
  )
  values (
    event_community_id,
    'notification.created',
    jsonb_build_object('notification_id', new.id, 'kind', new.kind),
    'member',
    new.recipient_membership_id
  );

  return new;
end;
$$;

drop trigger if exists notifications_sse_event on public.notifications;
create trigger notifications_sse_event
  after insert on public.notifications
  for each row execute function public.emit_notification_sse_event();

-- ---------------------------------------------------------------------------
-- 6. push_subscriptions
--
-- One row per browser, not per resident: a resident with a phone and a laptop
-- has two, and both should buzz.
--
-- `endpoint` is unique across the table rather than per membership. The endpoint
-- URL *is* the browser's identity to the push service, so the same endpoint
-- appearing under two memberships would mean one device receiving another
-- person's notifications -- which is what happens when two people share a
-- laptop and the second one subscribes. Unique on `endpoint` makes the second
-- subscribe move the row instead of duplicating it.
--
-- RLS enabled with no policy: `service_role` only, exactly as `0024` did to
-- `sse_events`. `p256dh_key` and `auth_key` are the browser's encryption
-- material, and a table any authenticated user could read is a table from which
-- an attacker collects the ability to send push notifications as us.
-- Registration therefore goes through the SECURITY DEFINER function below.
-- ---------------------------------------------------------------------------

create table if not exists public.push_subscriptions (
  id              uuid primary key default gen_random_uuid(),
  membership_id   uuid not null references public.community_memberships(id) on delete cascade,
  endpoint        text not null unique,
  p256dh_key      text not null,
  auth_key        text not null,
  user_agent      text,
  created_at      timestamptz not null default now(),
  last_success_at timestamptz,
  -- Dropped after five consecutive failures (10.4). `smallint` because the
  -- number that matters is 5 and anything past it is noise.
  failure_count   smallint not null default 0
);

create index if not exists push_subscriptions_membership_idx
  on public.push_subscriptions (membership_id);

alter table public.push_subscriptions enable row level security;

create or replace function public.register_push_subscription(
  p_membership_id uuid,
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
  -- The membership is an argument, so it has to be checked. A SECURITY DEFINER
  -- function that trusts a caller-supplied id is a function that lets anyone
  -- subscribe a device to anyone else's notifications.
  if not public.is_own_membership(p_membership_id) then
    raise exception 'Not your membership' using errcode = '42501';
  end if;

  if coalesce(btrim(p_endpoint), '') = ''
     or coalesce(btrim(p_p256dh), '') = ''
     or coalesce(btrim(p_auth), '') = '' then
    raise exception 'A push subscription needs an endpoint and both keys'
      using errcode = '22004';
  end if;

  -- Idempotent on `endpoint`: the browser re-subscribes on every service-worker
  -- update and after any VAPID key rotation, and each of those must refresh the
  -- row rather than accumulate one. `failure_count` resets because a browser
  -- that just told us its endpoint is not a browser that is failing.
  insert into public.push_subscriptions (
    membership_id, endpoint, p256dh_key, auth_key, user_agent
  )
  values (
    p_membership_id, btrim(p_endpoint), btrim(p_p256dh), btrim(p_auth), p_user_agent
  )
  on conflict (endpoint) do update
     set membership_id   = excluded.membership_id,
         p256dh_key      = excluded.p256dh_key,
         auth_key        = excluded.auth_key,
         user_agent      = excluded.user_agent,
         failure_count   = 0
  returning id into subscription_id;

  return subscription_id;
end;
$$;

create or replace function public.delete_push_subscription(
  p_membership_id uuid,
  p_endpoint text
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  removed integer;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'Not your membership' using errcode = '42501';
  end if;

  -- Both predicates. The endpoint is unique, so the membership adds nothing to
  -- the lookup -- it is there so that knowing someone else's endpoint is not
  -- enough to unsubscribe their phone.
  delete from public.push_subscriptions
   where endpoint = btrim(p_endpoint)
     and membership_id = p_membership_id;

  get diagnostics removed = row_count;
  return removed;
end;
$$;

comment on table public.push_subscriptions is
  'One browser''s Web Push registration. service_role only: the keys are encryption material.';

grant execute on function public.register_push_subscription(uuid, text, text, text, text) to authenticated;
grant execute on function public.delete_push_subscription(uuid, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 7. Marking read
--
-- Two functions rather than one with a null argument. "Mark this one" and
-- "clear the badge" are different intentions and the second is the one that can
-- be got wrong at scale; keeping them apart means the all-rows update cannot be
-- reached by omitting a parameter.
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
     and public.is_own_membership(n.recipient_membership_id);

  get diagnostics updated = row_count;
  return updated > 0;
end;
$$;

comment on function public.mark_notification_read(uuid) is
  'Mark one notification read. Idempotent: an already-read row keeps its original read_at.';

create or replace function public.mark_all_notifications_read(p_membership_id uuid)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  updated integer;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'Not your membership' using errcode = '42501';
  end if;

  update public.notifications
     set read_at = now()
   where recipient_membership_id = p_membership_id
     and read_at is null;

  get diagnostics updated = row_count;
  return updated;
end;
$$;

grant execute on function public.mark_notification_read(uuid) to authenticated;
grant execute on function public.mark_all_notifications_read(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 8. The push sender's claim
--
-- The hub may drop. The sender may not duplicate.
--
-- `RealtimeHub` tolerates several processes: each polls on its own cursor and
-- fans out to its own clients, so two workers means two harmless copies of a
-- frame. The sender does not have that luxury -- two copies reading the same
-- unsent notification send the same push twice, and a resident's phone buzzes
-- twice for one visitor. `for update skip locked` is the whole mechanism: the
-- second worker's `select` walks straight past the rows the first has locked.
--
-- The claim sets `push_sent_at` **before** the HTTP call, not after. That makes
-- a crash mid-send lose a buzz rather than repeat one, which is the correct bias
-- for a notification -- and the row is in the feed either way.
--
-- The one-hour window is deliberate. If the sender is down for a day, those
-- notifications are still in the feed; they simply do not buzz. A phone that
-- vibrates at 3am about a visitor from yesterday is worse than silence.
-- ---------------------------------------------------------------------------

create or replace function public.claim_push_batch(p_limit integer default 50)
returns table (
  notification_id uuid,
  membership_id   uuid,
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
  returning n.id, n.recipient_membership_id, n.kind, n.payload, n.created_at;
$$;

comment on function public.claim_push_batch(integer) is
  'Atomically claim un-pushed notifications from the last hour. service_role only; at-most-once by design.';

-- `service_role` only. This is the sender's function and it runs on the service
-- client; there is no resident-facing reason to reach it. The revoke is what
-- makes that sentence true -- EXECUTE defaults to PUBLIC, so until this line the
-- comment above described an intention rather than a permission, and any
-- signed-in user could mark every pending notification as pushed and silence
-- push for the whole deployment.
revoke all on function public.claim_push_batch(integer)
  from public, anon, authenticated;
grant execute on function public.claim_push_batch(integer) to service_role;

-- ---------------------------------------------------------------------------
-- 9. Push delivery outcomes
--
-- The sender records these through the service client, which bypasses RLS, so
-- these exist for the same reason the RPCs above do: the rule about what a `410`
-- means belongs next to the table, not in whichever process happens to be
-- sending.
-- ---------------------------------------------------------------------------

create or replace function public.record_push_success(p_endpoint text)
returns void
language sql
security definer
set search_path = public
as $$
  update public.push_subscriptions
     set last_success_at = now(),
         failure_count   = 0
   where endpoint = p_endpoint;
$$;

create or replace function public.record_push_failure(
  p_endpoint text,
  p_gone boolean default false
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  -- `404`/`410` mean the subscription no longer exists at the push service.
  -- Delete it. Retrying a dead endpoint forever is how you get rate-limited by
  -- Google or Mozilla, and no amount of retrying will revive it.
  if p_gone then
    delete from public.push_subscriptions where endpoint = p_endpoint;
    return;
  end if;

  update public.push_subscriptions
     set failure_count = failure_count + 1
   where endpoint = p_endpoint;

  -- Five consecutive transient failures is a subscription that is not coming
  -- back. Dropping it is the same decision as the `410` branch, reached by
  -- observation instead of by being told.
  delete from public.push_subscriptions
   where endpoint = p_endpoint
     and failure_count >= 5;
end;
$$;

-- Both service_role only, and both revoked from PUBLIC first. `record_push_failure`
-- with `p_gone => true` deletes a subscription by endpoint, so leaving it on the
-- default grant meant anyone holding another resident's endpoint string could
-- unsubscribe their phone.
revoke all on function public.record_push_success(text)
  from public, anon, authenticated;
revoke all on function public.record_push_failure(text, boolean)
  from public, anon, authenticated;
grant execute on function public.record_push_success(text) to service_role;
grant execute on function public.record_push_failure(text, boolean) to service_role;
