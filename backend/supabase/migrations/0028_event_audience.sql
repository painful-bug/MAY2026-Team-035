-- Give the SSE outbox an audience, so a stream stops being community-wide.
--
-- `GET /dashboard/events` is guarded by `get_active_membership` -- any active
-- member, not an admin -- and the hub fans out by `community_id` alone. Every
-- subscriber in a community therefore receives every event in it, including
-- `0024`'s `access_request.created`, which carries a neighbour's name, their
-- requested relationship and the community's pending count. A resident who
-- opens that stream watches their neighbours' join applications arrive live.
--
-- Nothing exploits it today because no resident client connects to anything.
-- The resident portal is what makes it exploitable, so the fix lands before
-- the portal, not after. See docs/design/RESIDENT_BACKEND_DESIGN.md 3.5.
--
-- Three columns and a rule:
--
--   community -- everyone in the community. Genuinely community-wide news.
--   role      -- subscribers whose role is in `audience_roles`.
--   member    -- exactly one subscriber, `recipient_membership_id`.
--
-- The check constraint below makes the three shapes mutually exclusive and
-- complete. That matters more than it looks: the reader fails closed on a row
-- it cannot classify, so a malformed row would be silently undeliverable. The
-- constraint means it cannot be written in the first place.
--
-- There is a load argument as well as a privacy one. Twelve tables emit
-- `dashboard.refresh` on every row change and the client contract for that
-- frame is *re-read your snapshot*. Point five hundred residents at a
-- community-wide firehose and one unrelated row change costs five hundred
-- snapshot fetches.

-- ---------------------------------------------------------------------------
-- 1. The audience columns
-- ---------------------------------------------------------------------------

alter table public.sse_events
  add column if not exists audience text not null default 'community';

alter table public.sse_events
  add column if not exists audience_roles text[];

alter table public.sse_events
  add column if not exists recipient_membership_id uuid
    references public.community_memberships(id) on delete cascade;

-- `add constraint if not exists` does not exist, and re-running a migration is
-- meant to be a no-op, so the guard is explicit.
do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.sse_events'::regclass
       and conname = 'sse_events_audience_shape_check'
  ) then
    alter table public.sse_events
      add constraint sse_events_audience_shape_check check (
        (
          audience = 'community'
          and audience_roles is null
          and recipient_membership_id is null
        ) or (
          audience = 'role'
          and audience_roles is not null
          and cardinality(audience_roles) > 0
          and recipient_membership_id is null
        ) or (
          audience = 'member'
          and recipient_membership_id is not null
          and audience_roles is null
        )
      );
  end if;
end;
$$;

comment on column public.sse_events.audience is
  'Who may receive this row: community | role | member. Enforced by sse_events_audience_shape_check and applied by app.core.realtime, never by the client.';

-- Most rows are not member-addressed, so the index that serves the member
-- audience is partial. The existing (community_id, id) index is untouched: it
-- is still what the process-wide poller and the reconnect backfill range-scan.
create index if not exists sse_events_recipient_membership_id_idx
  on public.sse_events (recipient_membership_id, id)
  where recipient_membership_id is not null;

-- ---------------------------------------------------------------------------
-- 2. Retarget the generic refresh trigger
-- ---------------------------------------------------------------------------

-- `dashboard.refresh` means "re-read the admin snapshot". Residents were never
-- its audience: a resident acting on it would fetch a snapshot it is not
-- entitled to and be refused, so this has always been a wasted wake-up for
-- them. Scoping it to {admin,manager} is the load half of the fix above.
create or replace function public.emit_dashboard_sse_event()
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
    insert into public.sse_events (community_id, topic, payload, audience, audience_roles)
    values (
      event_community_id,
      'dashboard.refresh',
      jsonb_build_object('table', tg_table_name),
      'role',
      array['admin', 'manager']
    );
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- 3. Retarget the join-request trigger
-- ---------------------------------------------------------------------------

-- This is the disclosure itself. The payload names the applicant; only the
-- people who act on join requests have any business seeing it.
create or replace function public.emit_access_request_sse_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  pending_count integer;
  event_topic text;
  event_payload jsonb;
begin
  -- An UPDATE that did not move `status` is bookkeeping (a reviewer note, an
  -- `updated_at` touch). The generic dashboard.refresh trigger still fires for
  -- it; there is nothing to notify anyone about.
  if tg_op = 'UPDATE' and old.status is not distinct from new.status then
    return new;
  end if;

  select count(*) into pending_count
    from public.access_requests
   where community_id = new.community_id
     and status = 'pending';

  if tg_op = 'INSERT' then
    event_topic := 'access_request.created';
    event_payload := jsonb_build_object(
      'request_id', new.id,
      'applicant_name', new.applicant_name,
      'requested_relationship', new.requested_relationship,
      'status', new.status,
      'created_at', new.created_at,
      'pending_count', pending_count
    );
  else
    event_topic := 'access_request.decided';
    event_payload := jsonb_build_object(
      'request_id', new.id,
      'applicant_name', new.applicant_name,
      'from', old.status,
      'to', new.status,
      'pending_count', pending_count
    );
  end if;

  insert into public.sse_events (community_id, topic, payload, audience, audience_roles)
  values (
    new.community_id,
    event_topic,
    event_payload,
    'role',
    array['admin', 'manager']
  );

  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- 4. Backfill anything already in the outbox
-- ---------------------------------------------------------------------------

-- Rows written before this migration defaulted to `community` and would keep
-- leaking for the length of the retention window (`prune_sse_events`, two
-- hours). Retarget the two topics that carry applicant detail; anything else
-- already in there is a bare `{"table": "..."}` refresh hint.
update public.sse_events
   set audience = 'role',
       audience_roles = array['admin', 'manager']
 where audience = 'community'
   and recipient_membership_id is null
   and topic in ('dashboard.refresh', 'access_request.created', 'access_request.decided');
