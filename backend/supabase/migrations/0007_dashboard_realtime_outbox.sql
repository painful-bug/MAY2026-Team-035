-- Forward-only compatibility bridge for projects created before the clean
-- baseline. The dashboard API uses this outbox for same-origin SSE updates.
-- Fresh baseline projects already declare this table, so this is a no-op there.

create table if not exists public.sse_events (
  id bigint generated always as identity primary key,
  community_id uuid not null references public.communities(id) on delete cascade,
  topic text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists sse_events_community_id_id_idx
  on public.sse_events (community_id, id);

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
    insert into public.sse_events (community_id, topic, payload)
    values (event_community_id, 'dashboard.refresh', jsonb_build_object('table', tg_table_name));
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'community_memberships', 'complaints', 'visitor_access_requests',
    'visitor_requests', 'amenities', 'amenity_booking_series',
    'amenity_bookings', 'invoices', 'payments', 'notices', 'departments',
    'access_requests'
  ] loop
    if to_regclass('public.' || table_name) is not null then
      execute format('drop trigger if exists dashboard_sse_%I on public.%I', table_name, table_name);
      execute format(
        'create trigger dashboard_sse_%I after insert or update or delete on public.%I for each row execute function public.emit_dashboard_sse_event()',
        table_name,
        table_name
      );
    end if;
  end loop;
end;
$$;
