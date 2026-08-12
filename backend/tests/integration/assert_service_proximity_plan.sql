\set ON_ERROR_STOP on

begin;

create temporary table plan_users as
select gen_random_uuid() as id, value
  from generate_series(1, 5000) value;

insert into auth.users (
  instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at
)
select '00000000-0000-0000-0000-000000000000', id, 'authenticated',
       'authenticated', 'plan-' || value || '@example.test', '', now(),
       '{}'::jsonb, '{}'::jsonb, now(), now()
  from plan_users;

insert into public.profiles (id, full_name, display_email)
select id, 'Plan Provider ' || value, 'plan-' || value || '@example.test'
  from plan_users;

insert into public.service_providers (
  profile_id, display_name, latitude, longitude, service_radius_km
)
select id, 'Plan Provider ' || value,
       -80 + (value % 160), -170 + (value % 340), 15
  from plan_users;

analyze public.service_providers;

do $$
declare
  v_line text;
  v_plan text := '';
begin
  for v_line in execute $query$
    explain
    select id
      from public.service_providers
     where status = 'active'
       and is_available
       and location is not null
       and extensions.st_dwithin(
         location,
         extensions.st_setsrid(extensions.st_makepoint(88.363892, 22.572645), 4326)::extensions.geography,
         500000
       )
  $query$ loop
    v_plan := v_plan || E'\n' || v_line;
  end loop;
  if position('service_providers_location_gix' in v_plan) = 0 then
    raise exception 'Expected GiST provider-location index. Plan:%', v_plan;
  end if;
end;
$$;

rollback;
