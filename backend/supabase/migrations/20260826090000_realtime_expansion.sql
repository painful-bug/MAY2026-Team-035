-- 20260826090000_realtime_expansion.sql
--
-- Three audiences the outbox never reached: the people watching a work order,
-- the residents looking at an amenity calendar, and the other end of a direct
-- message. Every emitter below writes a HINT, not truth -- the client re-reads
-- through the endpoint whose authorization already scopes it, which is the
-- doctrine docs/ARCHITECTURE.md states and 0030's notification emitter set the
-- template for. Over-delivery of a hint is safe by the same doctrine: a client
-- nudged about data it may not see re-fetches an empty answer.
--
-- 1. `work_orders` has NO sse trigger. It is not in `0007`'s twelve-table
--    array, and nothing since attached one -- so a resident watching their
--    complaint, and a supervisor watching a queue, learn about a status change
--    only on a manual reload. `work_order.changed` goes to the whole community:
--    the four populations who can read a job (`can_read_work_order`, 0036) do
--    not map onto any role list, and the row itself is not in the frame.
--
-- 2. `amenity_bookings` and `amenity_booking_series` carry only the generic
--    `dashboard.refresh` triggers, which `0028` scoped to {admin, manager}. A
--    resident staring at a slot grid never hears that the slot was just taken.
--    `amenity.changed` is an ADDITIONAL trigger on each table -- the generic
--    ones are kept, admins converge exactly as before -- and carries only the
--    amenity id, so the client re-reads availability it could already read.
--    `amenity_booking_series` exists on no current database under that name
--    (`0023` never creates it and hosted holds only the parked
--    `legacy_amenity_booking_series`), so its attach is guarded by
--    `to_regclass`, exactly as `0007` guarded its own loop.
--
-- 3. `dm_messages` writes a notification through `notify_profile` (0046), and
--    `0030`'s trigger turns that into a `notification.created` frame -- but
--    only for the bell. The chat dock polls. `message.created` is addressed to
--    each recipient participant of the thread, `audience = 'member'`, resolved
--    to their active membership in the thread's community; the sender is
--    excluded by profile id. A system line (`author_profile_id is null`, the
--    lock notice) reaches both participants, which is correct: both of them
--    have a mailbox to refresh. The payload is the thread id and the message
--    id and nothing else -- the body travels only through the RLS-scoped read,
--    for the same reason 0030 refused to put a title in a frame.
--
-- Everything is idempotent: `create or replace function`, and each trigger is
-- a `drop trigger if exists` of THIS FILE'S OWN NAME followed by its
-- recreation, so no generic trigger is ever touched and a re-run replaces only
-- its own work. The do-block at the bottom raises if any trigger this file
-- claims to have made is missing.
--
-- Hand-applied by the owner in the Supabase SQL editor, like every file in
-- this directory. Runbook section 31.

-- ---------------------------------------------------------------------------
-- 1. Work orders
-- ---------------------------------------------------------------------------

create or replace function public.emit_work_order_sse_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  row_data jsonb;
  event_community_id uuid;
begin
  row_data := case when tg_op = 'DELETE' then to_jsonb(old) else to_jsonb(new) end;
  event_community_id := nullif(row_data ->> 'community_id', '')::uuid;

  if event_community_id is not null then
    insert into public.sse_events (community_id, topic, payload, audience)
    values (
      event_community_id,
      'work_order.changed',
      jsonb_build_object(
        'table', tg_table_name,
        'work_order_id', row_data ->> 'id',
        'complaint_id', row_data ->> 'complaint_id',
        'status', row_data ->> 'status'
      ),
      'community'
    );
  end if;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

drop trigger if exists work_orders_sse_event on public.work_orders;
create trigger work_orders_sse_event
  after insert or update or delete on public.work_orders
  for each row execute function public.emit_work_order_sse_event();

-- ---------------------------------------------------------------------------
-- 2. Amenity bookings, for the people the generic trigger stopped reaching
-- ---------------------------------------------------------------------------

create or replace function public.emit_amenity_sse_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  row_data jsonb;
  event_amenity_id uuid;
  event_community_id uuid;
begin
  row_data := case when tg_op = 'DELETE' then to_jsonb(old) else to_jsonb(new) end;
  event_amenity_id := nullif(row_data ->> 'amenity_id', '')::uuid;
  event_community_id := nullif(row_data ->> 'community_id', '')::uuid;

  -- `amenity_bookings` carries `community_id` itself; a series-shaped row may
  -- not, so the amenity resolves it. No community, no event -- the column is
  -- `not null` on `sse_events` for a reason.
  if event_community_id is null and event_amenity_id is not null then
    select a.community_id into event_community_id
      from public.amenities a
     where a.id = event_amenity_id;
  end if;

  if event_community_id is not null then
    insert into public.sse_events (community_id, topic, payload, audience)
    values (
      event_community_id,
      'amenity.changed',
      jsonb_build_object(
        'table', tg_table_name,
        'amenity_id', event_amenity_id
      ),
      'community'
    );
  end if;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

drop trigger if exists amenity_bookings_amenity_sse on public.amenity_bookings;
create trigger amenity_bookings_amenity_sse
  after insert or update or delete on public.amenity_bookings
  for each row execute function public.emit_amenity_sse_event();

-- Nothing currently holds this table name -- see the header -- so the attach
-- is conditional, `0007`'s own posture for a table that may not exist.
do $$
begin
  if to_regclass('public.amenity_booking_series') is not null then
    execute 'drop trigger if exists amenity_booking_series_amenity_sse '
            'on public.amenity_booking_series';
    execute 'create trigger amenity_booking_series_amenity_sse '
            'after insert or update or delete on public.amenity_booking_series '
            'for each row execute function public.emit_amenity_sse_event()';
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- 3. Direct messages
-- ---------------------------------------------------------------------------

create or replace function public.emit_message_sse_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_thread     public.dm_threads%rowtype;
  v_recipient  uuid;
  v_membership uuid;
begin
  select * into v_thread from public.dm_threads where id = new.thread_id;
  if not found then
    return new;
  end if;

  foreach v_recipient in array array[
    v_thread.participant_a_profile_id,
    v_thread.participant_b_profile_id
  ] loop
    -- The sender does not need to be told about their own message. A system
    -- line has a null author and `is not distinct from` treats that as "not
    -- the sender" for both participants, which is the intent.
    if v_recipient is null
       or v_recipient is not distinct from new.author_profile_id then
      continue;
    end if;

    -- The stream is addressed by membership (`0028`), the thread by profile
    -- (`0046`); the bridge is the recipient's active membership in the
    -- thread's community. A participant with no active membership there --
    -- removed since the thread opened -- gets no frame, and the message is
    -- still in the thread for whatever access they retain.
    select m.id into v_membership
      from public.community_memberships m
     where m.community_id = v_thread.community_id
       and m.profile_id = v_recipient
       and m.status = 'active'
       and m.ended_at is null
     limit 1;

    if v_membership is not null then
      insert into public.sse_events
        (community_id, topic, payload, audience, recipient_membership_id)
      values (
        v_thread.community_id,
        'message.created',
        jsonb_build_object('thread_id', new.thread_id, 'message_id', new.id),
        'member',
        v_membership
      );
    end if;
  end loop;

  return new;
end;
$$;

drop trigger if exists dm_messages_sse_event on public.dm_messages;
create trigger dm_messages_sse_event
  after insert on public.dm_messages
  for each row execute function public.emit_message_sse_event();

-- ---------------------------------------------------------------------------
-- 4. Grants
--
-- Trigger functions cannot be invoked directly, but the default EXECUTE grant
-- to PUBLIC still exists on them; revoked for the reason 0046 revoked
-- `lock_work_order_threads` -- a grant nobody can use is still a grant nobody
-- audits.
-- ---------------------------------------------------------------------------

revoke all on function public.emit_work_order_sse_event()
  from public, anon, authenticated;
revoke all on function public.emit_amenity_sse_event()
  from public, anon, authenticated;
revoke all on function public.emit_message_sse_event()
  from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- 5. The triggers exist, by name, on the tables this file names
-- ---------------------------------------------------------------------------

do $$
begin
  if not exists (
    select 1
      from pg_trigger
     where tgrelid = 'public.work_orders'::regclass
       and tgname = 'work_orders_sse_event'
       and not tgisinternal
  ) then
    raise exception 'work_orders_sse_event missing on public.work_orders';
  end if;

  if not exists (
    select 1
      from pg_trigger
     where tgrelid = 'public.amenity_bookings'::regclass
       and tgname = 'amenity_bookings_amenity_sse'
       and not tgisinternal
  ) then
    raise exception 'amenity_bookings_amenity_sse missing on public.amenity_bookings';
  end if;

  -- `to_regclass`, not a literal `::regclass` cast: the cast is resolved when
  -- this expression is PLANNED, before the guard on its left is evaluated, so
  -- on a database without the table it raises 42P01 despite the guard.
  -- `to_regclass` returns null there, and `tgrelid = null` is simply false.
  if to_regclass('public.amenity_booking_series') is not null and not exists (
    select 1
      from pg_trigger
     where tgrelid = to_regclass('public.amenity_booking_series')
       and tgname = 'amenity_booking_series_amenity_sse'
       and not tgisinternal
  ) then
    raise exception 'amenity_booking_series_amenity_sse missing on public.amenity_booking_series';
  end if;

  if not exists (
    select 1
      from pg_trigger
     where tgrelid = 'public.dm_messages'::regclass
       and tgname = 'dm_messages_sse_event'
       and not tgisinternal
  ) then
    raise exception 'dm_messages_sse_event missing on public.dm_messages';
  end if;
end;
$$;
