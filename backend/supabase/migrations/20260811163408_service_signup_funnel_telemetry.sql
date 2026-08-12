-- Narrow, privacy-minimal launch funnel. This is intentionally not an
-- experiment or generic analytics framework.

create table public.service_signup_funnel_events (
  visitor_id uuid not null,
  event_name text not null check (event_name in (
    'cta_impression', 'cta_clicked', 'auth_completed',
    'provider_profile_completed', 'first_application_submitted'
  )),
  occurred_at timestamptz not null default now(),
  primary key (visitor_id, event_name)
);

alter table public.service_signup_funnel_events enable row level security;
revoke all on table public.service_signup_funnel_events from public, anon, authenticated;

create or replace function public.record_service_signup_funnel_event(
  p_visitor_id uuid,
  p_event_name text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_visitor_id is null or p_event_name not in (
    'cta_impression', 'cta_clicked', 'auth_completed',
    'provider_profile_completed', 'first_application_submitted'
  ) then
    raise exception 'Invalid service signup event.' using errcode = '22004';
  end if;
  insert into public.service_signup_funnel_events(visitor_id, event_name)
  values (p_visitor_id, p_event_name)
  on conflict (visitor_id, event_name) do nothing;
end;
$$;

create or replace function public.prune_service_signup_funnel_events()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare removed integer;
begin
  delete from public.service_signup_funnel_events
   where occurred_at < now() - interval '30 days';
  get diagnostics removed = row_count;
  return removed;
end;
$$;

revoke all on function public.record_service_signup_funnel_event(uuid, text) from public, anon, authenticated;
grant execute on function public.record_service_signup_funnel_event(uuid, text) to service_role;
revoke all on function public.prune_service_signup_funnel_events() from public, anon, authenticated;
grant execute on function public.prune_service_signup_funnel_events() to service_role;

-- Retention is a launch invariant, so deployment must fail rather than silently
-- continue when the scheduler cannot be installed.
create extension if not exists pg_cron with schema pg_catalog;

do $$
begin
  perform cron.unschedule('prune-service-signup-funnel')
    where exists (select 1 from cron.job where jobname = 'prune-service-signup-funnel');
  perform cron.schedule(
    'prune-service-signup-funnel',
    '17 3 * * *',
    $cron$select public.prune_service_signup_funnel_events()$cron$
  );
end;
$$;

notify pgrst, 'reload schema';
