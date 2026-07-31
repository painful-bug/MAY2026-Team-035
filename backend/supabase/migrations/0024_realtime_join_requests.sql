-- Realtime for resident join requests, on the baseline.
--
-- `0007_dashboard_realtime_outbox.sql` already puts a generic
-- `dashboard.refresh` trigger on `access_requests`, which is enough to make a
-- connected dashboard re-snapshot. It is not enough to *notify*: the payload
-- carries only `{"table": "..."}`, so a client cannot tell a new join request
-- from a rejected one, and cannot render a count without a round trip.
--
-- This migration adds three things and changes none of theirs:
--
--   1. A second, specific trigger emitting `access_request.created` and
--      `access_request.decided` with a payload worth reading, including the
--      community's live pending count so a badge can update from the event.
--   2. Row level security on `sse_events`. The table is reachable through
--      PostgREST and had no policies, so any authenticated user could read
--      every community's event stream -- table names and community ids for
--      tenants they do not belong to. Enabling RLS with no policy denies all
--      roles except `service_role`, which bypasses it; the backend reads this
--      table only through the service client, so nothing legitimate changes.
--   3. Bounded retention. Twelve tables feed this outbox on every row change
--      and nothing ever deleted from it.
--
-- Also adds `pending_access_request_overview`, the projection behind the
-- dashboard snapshot's `pendingRequests` -- the field the sidebar badge in
-- `AdminLayout.jsx` has always read and the backend has never sent.

-- ---------------------------------------------------------------------------
-- 1. Specific join-request events
-- ---------------------------------------------------------------------------

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

  insert into public.sse_events (community_id, topic, payload)
  values (new.community_id, event_topic, event_payload);

  return new;
end;
$$;

drop trigger if exists access_request_sse on public.access_requests;
create trigger access_request_sse
  after insert or update on public.access_requests
  for each row execute function public.emit_access_request_sse_event();

-- ---------------------------------------------------------------------------
-- 2. Lock the outbox down
-- ---------------------------------------------------------------------------

-- No policy is deliberate. `service_role` bypasses RLS, and it is the only
-- role that should ever see this table: the payloads are cross-tenant by
-- construction and the backend fans them out after checking membership.
alter table public.sse_events enable row level security;

-- ---------------------------------------------------------------------------
-- 3. Retention
-- ---------------------------------------------------------------------------

create or replace function public.prune_sse_events(p_keep interval default interval '2 hours')
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  removed integer;
begin
  delete from public.sse_events where created_at < now() - p_keep;
  get diagnostics removed = row_count;
  return removed;
end;
$$;

revoke all on function public.prune_sse_events(interval) from public, anon, authenticated;
grant execute on function public.prune_sse_events(interval) to service_role;

-- Schedule it when pg_cron is available. Supabase projects can enable the
-- extension from the dashboard; where it is absent this block is a no-op and
-- retention falls to whoever calls `prune_sse_events` -- see the "Live updates"
-- section of docs/ARCHITECTURE.md.
do $$
begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') then
    perform cron.unschedule('prune-sse-events')
      where exists (select 1 from cron.job where jobname = 'prune-sse-events');
    perform cron.schedule(
      'prune-sse-events',
      '*/15 * * * *',
      $cron$select public.prune_sse_events()$cron$
    );
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- 4. The snapshot projection
-- ---------------------------------------------------------------------------

create or replace view public.pending_access_request_overview
with (security_invoker = true) as
  select
    ar.id,
    ar.community_id,
    ar.applicant_name,
    ar.applicant_email::text as applicant_email,
    ar.applicant_phone_e164,
    ar.requested_relationship::text as requested_relationship,
    ar.status,
    ar.created_at,
    ar.requested_unit_id,
    u.unit_code as requested_unit_code,
    c.name as community_name
  from public.access_requests ar
  join public.communities c on c.id = ar.community_id
  left join public.units u on u.id = ar.requested_unit_id
  where ar.status = 'pending';

comment on view public.pending_access_request_overview is
  'Pending join requests per community. Backs DashboardSnapshot.pendingRequests, which drives the admin sidebar badge.';
