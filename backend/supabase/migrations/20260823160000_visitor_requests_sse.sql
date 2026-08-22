-- 20260823160000_visitor_requests_sse.sql
--
-- `public.visitor_requests` carries no trigger at all on the hosted project.
-- The owner's read-only probe of 2026-08-23 (runbook §22, probe (g)) walked
-- the trigger inventory: `amenity_bookings` has `amenity_bookings_sse`,
-- `visitor_access_requests` has `dashboard_sse_visitor_access_requests`,
-- `legacy_amenity_booking_series` has `dashboard_sse_amenity_booking_series`
-- -- and `visitor_requests`, the table residents actually write through
-- `0032_visitor_passes.sql`, has none. Probe (h) counted the consequence:
-- three real visitor requests, none of which has ever produced an
-- `sse_events` row, so no open dashboard has ever refreshed itself when one
-- arrived.
--
-- `0007_dashboard_realtime_outbox.sql` is the file that lays these triggers.
-- Its loop names twelve tables, `visitor_requests` among them, and builds
-- `dashboard_sse_%I` on each one that exists -- so a *fresh* database gets
-- `dashboard_sse_visitor_requests` from `0007` and always has. Hosted did not,
-- because when `0007` was applied there the baseline table it names did not
-- yet exist: `0032` created it twenty-five files later. The loop is guarded by
-- `to_regclass` and had nothing to attach to, and nothing has revisited the
-- question since.
--
-- What this file does is one statement, and it is `0007`'s own statement for
-- this table -- the same `after insert or update or delete`, the same
-- `for each row`, the same `public.emit_dashboard_sse_event()`
-- (`0007_dashboard_realtime_outbox.sql` 16-37, 51-55), under the same name its
-- loop would have produced. A database that gets the trigger from `0007` and a
-- database that gets it from here end up with the same trigger, which is the
-- point: this is not a second design, it is the first one arriving late.
--
-- The function itself is not touched. `0028_event_audience.sql` 93 rewrote it
-- once, to publish `dashboard.refresh` to the `{admin, manager}` audience
-- rather than the whole community, and that is the definition both databases
-- already carry -- so a visitor request landing here reaches exactly the people
-- whose dashboard lists it.
--
-- `create or replace trigger` rather than a drop-and-create pair, so this is
-- idempotent everywhere: on a fresh database it replaces `0007`'s trigger with
-- a definition identical to it, and on hosted a second run replaces its own.
-- Nothing is ever dropped, so no window exists in which the table has no
-- trigger.
--
-- This is the realtime half of the dashboard split-brain. The read half is a
-- code change in `backend/app/repositories/dashboard_repository.py` -- the
-- legacy projections now read `visitor_requests` and `amenity_bookings`, the
-- tables residents write -- and needs no migration. Without this file the
-- dashboard would show the rows but only on a manual reload.
--
-- Hand-applied by the owner in the Supabase SQL editor, like every file in
-- this directory. Runbook §26.

create or replace trigger dashboard_sse_visitor_requests
after insert or update or delete on public.visitor_requests
for each row execute function public.emit_dashboard_sse_event();

-- The trigger is on the table residents write.
do $$
begin
  if not exists (
    select 1
      from pg_trigger
     where tgrelid = 'public.visitor_requests'::regclass
       and tgname = 'dashboard_sse_visitor_requests'
       and not tgisinternal
  ) then
    raise exception 'dashboard_sse_visitor_requests missing on public.visitor_requests';
  end if;
end;
$$;
