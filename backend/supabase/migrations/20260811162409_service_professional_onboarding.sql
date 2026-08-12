-- Service-professional onboarding, proximity, and hiring authorization.
-- Forward-only: 0034/0035 are deployed and must remain immutable.

-- ---------------------------------------------------------------------------
-- 1. Atomic registration and complete skill sets
-- ---------------------------------------------------------------------------

create or replace function public.set_service_provider_skills(p_skill_ids uuid[])
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_provider uuid;
  v_requested integer;
  v_valid integer;
begin
  select id into v_provider
    from public.service_providers
   where profile_id = auth.uid();
  if v_provider is null then
    raise exception 'No service provider profile.' using errcode = 'P0002';
  end if;

  v_requested := cardinality(coalesce(p_skill_ids, array[]::uuid[]));
  if v_requested = 0 then
    raise exception 'Choose at least one skill.' using errcode = '22004';
  end if;
  if v_requested <> cardinality(array(select distinct unnest(p_skill_ids))) then
    raise exception 'Skill ids must be unique.' using errcode = '22004';
  end if;

  select count(*) into v_valid
    from public.skills
   where id = any(p_skill_ids)
     and is_active;
  if v_valid <> v_requested then
    raise exception 'Every skill must exist and be active.' using errcode = '22004';
  end if;

  delete from public.service_provider_skills
   where service_provider_id = v_provider
     and skill_id <> all(p_skill_ids);

  insert into public.service_provider_skills (service_provider_id, skill_id)
  select v_provider, unnest(p_skill_ids)
  on conflict do nothing;

  return v_valid;
end;
$$;

create or replace function public.register_service_provider(
  p_display_name text,
  p_headline text,
  p_phone_e164 text,
  p_latitude numeric,
  p_longitude numeric,
  p_service_radius_km numeric,
  p_skill_ids uuid[]
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_provider uuid;
begin
  if auth.uid() is null then
    raise exception 'Sign in required.' using errcode = '42501';
  end if;
  if p_display_name is null or length(btrim(p_display_name)) not between 2 and 120 then
    raise exception 'A name between 2 and 120 characters is required.' using errcode = '22004';
  end if;
  if p_latitude is null or p_longitude is null then
    raise exception 'Your location is required.' using errcode = 'HBLOC';
  end if;
  if p_latitude not between -90 and 90 or p_longitude not between -180 and 180 then
    raise exception 'Your location is invalid.' using errcode = 'HBLOC';
  end if;
  if coalesce(p_service_radius_km, 15) not between 1 and 500 then
    raise exception 'Service radius must be between 1 and 500 kilometres.' using errcode = '22004';
  end if;

  if not exists (
    select 1 from public.service_providers where profile_id = auth.uid()
  ) and exists (
    select 1
      from public.community_memberships
     where profile_id = auth.uid()
       and role not in ('worker', 'security')
       and status = 'active'
       and ended_at is null
  ) then
    raise exception 'Use a separate account for your professional profile.' using errcode = 'HB409';
  end if;

  v_provider := public.upsert_service_provider(
    btrim(p_display_name), p_headline, null, p_phone_e164,
    p_latitude, p_longitude, coalesce(p_service_radius_km, 15)
  );
  perform public.set_service_provider_skills(p_skill_ids);
  return v_provider;
end;
$$;

comment on function public.register_service_provider(text, text, text, numeric, numeric, numeric, uuid[]) is
  'Atomically creates or repairs the signed-in professional profile and full active skill set. Refuses existing non-professional members on first registration.';

revoke all on function public.set_service_provider_skills(uuid[]) from public, anon;
grant execute on function public.set_service_provider_skills(uuid[]) to authenticated;
revoke all on function public.register_service_provider(text, text, text, numeric, numeric, numeric, uuid[]) from public, anon;
grant execute on function public.register_service_provider(text, text, text, numeric, numeric, numeric, uuid[]) to authenticated;

-- ---------------------------------------------------------------------------
-- 2. Community coordinates
-- ---------------------------------------------------------------------------

-- Keep the compatibility-heavy deployed founder implementation intact and put
-- the new location invariant around it. A nested function call shares this
-- transaction, so a failed coordinate write rolls the community creation back.
alter function public.create_founder_community(jsonb)
  rename to create_founder_community_without_location;

create function public.create_founder_community(p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_latitude numeric := (p_payload->>'latitude')::numeric;
  v_longitude numeric := (p_payload->>'longitude')::numeric;
  v_result jsonb;
  v_community uuid;
begin
  if v_latitude is null or v_longitude is null
     or v_latitude not between -90 and 90
     or v_longitude not between -180 and 180 then
    raise exception 'A valid community location is required.' using errcode = 'HBLOC';
  end if;

  v_result := public.create_founder_community_without_location(p_payload);
  v_community := (v_result->'community'->>'id')::uuid;
  update public.communities
     set latitude = v_latitude, longitude = v_longitude, updated_at = now()
   where id = v_community;
  return v_result;
end;
$$;

revoke all on function public.create_founder_community_without_location(jsonb) from public, anon, authenticated;
revoke all on function public.create_founder_community(jsonb) from public, anon, authenticated;
grant execute on function public.create_founder_community(jsonb) to service_role;

create or replace function public.set_my_community_location(
  p_community_id uuid,
  p_latitude numeric,
  p_longitude numeric
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_latitude is null or p_longitude is null
     or p_latitude not between -90 and 90
     or p_longitude not between -180 and 180 then
    raise exception 'A valid community location is required.' using errcode = 'HBLOC';
  end if;

  if not exists (
    select 1
      from public.community_memberships
     where community_id = p_community_id
       and profile_id = auth.uid()
       and role = 'admin'
       and status = 'active'
       and ended_at is null
  ) then
    raise exception 'Only a community admin may update its location.' using errcode = 'HB403';
  end if;

  update public.communities
     set latitude = p_latitude,
         longitude = p_longitude,
         updated_at = now()
   where id = p_community_id;
end;
$$;

revoke all on function public.set_my_community_location(uuid, numeric, numeric) from public, anon;
grant execute on function public.set_my_community_location(uuid, numeric, numeric) to authenticated;

create or replace view public.community_settings_overview
with (security_invoker = true) as
select
  c.id as community_id,
  c.name as community_name,
  c.community_type,
  c.status as community_status,
  c.created_at as community_created_at,
  coalesce(cs.timezone, c.timezone, 'Asia/Kolkata') as timezone,
  coalesce(cs.unit_label_singular,
    case c.community_type when 'apartment' then 'Flat' else 'Villa' end
  ) as unit_label_singular,
  (cs.unit_label_singular is null) as unit_label_is_derived,
  coalesce(cs.invite_ttl_hours, 72) as invite_ttl_hours,
  coalesce(cs.visitor_code_ttl_minutes, 120) as visitor_code_ttl_minutes,
  coalesce(cs.require_visitor_preapproval, true) as require_visitor_preapproval,
  coalesce(cs.notice_sms_broadcast_enabled, false) as notice_sms_broadcast_enabled,
  (cs.community_id is not null) as has_saved_settings,
  coalesce(cs.version, 0) as version,
  cs.updated_at as settings_updated_at,
  pr.full_name as settings_updated_by_name,
  coalesce(bs.auto_billing_enabled, false) as auto_billing_enabled,
  coalesce(bs.auto_billing_day, 1) as auto_billing_day,
  coalesce(bs.late_fee_enabled, false) as late_fee_enabled,
  bs.late_fee_amount,
  coalesce(bs.late_fee_grace_days, 10) as late_fee_grace_days,
  coalesce(bs.late_fee_period, 'weekly') as late_fee_period,
  bs.default_maintenance_amount,
  coalesce(mo.modules_total, 0) as modules_total,
  coalesce(mo.modules_enabled, 0) as modules_enabled,
  coalesce(mo.modules_enabled_without_backend, 0) as modules_enabled_without_backend,
  c.latitude,
  c.longitude
from public.communities c
left join public.community_settings cs on cs.community_id = c.id
left join public.community_billing_settings bs on bs.community_id = c.id
left join public.community_memberships m on m.id = cs.updated_by_membership_id
left join public.profiles pr on pr.id = m.profile_id
left join lateral (
  select count(*) as modules_total,
         count(*) filter (where v.enabled) as modules_enabled,
         count(*) filter (where v.enabled and v.backend_status = 'absent') as modules_enabled_without_backend
    from public.community_module_overview v
   where v.community_id = c.id
) mo on true;

grant select on public.community_settings_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 3. Hiring-specific authority and worker/security mode
-- ---------------------------------------------------------------------------

create or replace function public.hiring_department_managers(p_department_id uuid)
returns table(membership_id uuid, profile_id uuid)
language sql
stable
security definer
set search_path = public
as $$
  select m.id, m.profile_id
    from public.departments d
    join public.community_memberships m on m.community_id = d.community_id
     and m.role = 'manager'
     and m.department_id = d.id
     and m.status = 'active' and m.ended_at is null
   where d.id = p_department_id
  union
  select m.id, m.profile_id
    from public.departments d
    join public.staff_assignments sa on sa.department_id = d.id
     and sa.rank = 'manager' and sa.status = 'active'
    join public.community_memberships m on m.id = sa.membership_id
     and m.status = 'active' and m.ended_at is null
   where d.id = p_department_id;
$$;

create or replace function public.professional_membership_role(p_department_kind text)
returns public.membership_role
language sql
immutable
security definer
set search_path = public
as $$
  select case when p_department_kind = 'security' then 'security' else 'worker' end
         ::public.membership_role;
$$;

revoke all on function public.hiring_department_managers(uuid) from public, anon, authenticated;
revoke all on function public.professional_membership_role(text) from public, anon, authenticated;

create or replace function public.can_hire_for_department(p_department_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  with department as (
    select id, community_id from public.departments where id = p_department_id
  ), managers as (
    select profile_id
      from public.hiring_department_managers(p_department_id)
  )
  select exists(select 1 from managers where profile_id = auth.uid())
      or (
        not exists(select 1 from managers)
        and exists (
          select 1 from department d
          join public.community_memberships m on m.community_id = d.community_id
           and m.profile_id = auth.uid()
           and m.role = 'admin'
           and m.status = 'active' and m.ended_at is null
        )
      );
$$;

comment on function public.can_hire_for_department(uuid) is
  'Hiring-only authority: the selected department manager, with community admins as fallback only when no active manager exists. Supervisors never qualify.';
revoke all on function public.can_hire_for_department(uuid) from public, anon;
grant execute on function public.can_hire_for_department(uuid) to authenticated;

create or replace function public.enforce_professional_membership_mode()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.role not in ('worker', 'security')
     or new.status <> 'active'
     or new.ended_at is not null
     or not exists (select 1 from public.service_providers where profile_id = new.profile_id) then
    return new;
  end if;

  if exists (
    select 1 from public.community_memberships m
     where m.profile_id = new.profile_id
       and m.id <> new.id
       and m.role in ('worker', 'security')
       and m.role <> new.role
       and m.status = 'active'
       and m.ended_at is null
  ) then
    raise exception 'A professional account cannot mix worker and security memberships.' using errcode = 'HB409';
  end if;
  return new;
end;
$$;

drop trigger if exists community_memberships_professional_mode on public.community_memberships;
create trigger community_memberships_professional_mode
before insert or update of role, status, ended_at on public.community_memberships
for each row execute function public.enforce_professional_membership_mode();

revoke all on function public.enforce_professional_membership_mode() from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- 4. Radius-bounded, stable proximity searches
-- ---------------------------------------------------------------------------

create or replace function public.search_serviceable_communities(
  p_query text default null,
  p_limit integer default 20,
  p_offset integer default 0
)
returns table (
  id uuid, name text, city text, state text, community_type text,
  distance_km numeric, matching_skill_names text[], departments jsonb
)
language plpgsql
stable
security definer
set search_path = public
as $$
#variable_conflict use_column
declare
  v_provider public.service_providers%rowtype;
  v_mode text;
begin
  select * into v_provider from public.service_providers where profile_id = auth.uid();
  if not found then
    raise exception 'Register as a service provider first.' using errcode = 'HB404';
  end if;
  if v_provider.location is null then
    raise exception 'Set your location before searching for communities.' using errcode = 'HBLOC';
  end if;

  select m.role::text into v_mode
    from public.community_memberships m
   where m.profile_id = auth.uid()
     and m.role in ('worker', 'security')
     and m.status = 'active' and m.ended_at is null
   order by m.joined_at limit 1;

  return query
  select c.id, c.name, c.city, c.state, c.community_type,
         round((extensions.st_distance(c.location, v_provider.location) / 1000)::numeric, 2),
         array_agg(distinct s.name order by s.name),
         jsonb_agg(distinct jsonb_build_object('id', d.id, 'name', d.name))
    from public.communities c
    join public.departments d on d.community_id = c.id and d.is_active
    join public.department_categories dc on dc.department_id = d.id
    join public.complaint_categories cc on cc.id = dc.category_id and cc.skill_id is not null
    join public.service_provider_skills sps on sps.skill_id = cc.skill_id and sps.service_provider_id = v_provider.id
    join public.skills s on s.id = cc.skill_id and s.is_active
   where c.status = 'active'
     and c.location is not null
     and extensions.st_dwithin(c.location, v_provider.location, v_provider.service_radius_km * 1000)
     and (p_query is null or c.name ilike '%' || btrim(p_query) || '%')
     and (v_mode is null or v_mode = public.professional_membership_role(d.kind::text)::text)
     and not exists (
       select 1 from public.blacklisted_service_providers b
        where b.community_id = c.id and b.service_provider_id = v_provider.id and b.revoked_at is null
     )
     and not exists (
       select 1 from public.community_memberships m
        where m.community_id = c.id and m.profile_id = auth.uid()
          and m.status = 'active' and m.ended_at is null
     )
   group by c.id, c.name, c.city, c.state, c.community_type, c.location
   order by extensions.st_distance(c.location, v_provider.location), lower(c.name), c.id
   limit greatest(1, least(coalesce(p_limit, 20), 20))
   offset greatest(0, coalesce(p_offset, 0));
end;
$$;

create or replace function public.search_hireable_service_providers(
  p_department_id uuid,
  p_query text default null,
  p_limit integer default 20,
  p_offset integer default 0
)
returns table (
  id uuid, display_name text, headline text, phone_e164 varchar(20), status text,
  is_available boolean, service_radius_km numeric, distance_km numeric,
  matching_skill_names text[], skill_names text[], community_count integer,
  has_open_application boolean
)
language plpgsql
stable
security definer
set search_path = public
as $$
#variable_conflict use_column
declare
  v_department public.departments%rowtype;
  v_community public.communities%rowtype;
  v_role text;
begin
  if not public.can_hire_for_department(p_department_id) then
    raise exception 'You may not hire for this department.' using errcode = 'HB403';
  end if;
  select * into v_department from public.departments where id = p_department_id and is_active;
  if not found then raise exception 'No such department.' using errcode = 'HB404'; end if;
  select * into v_community from public.communities where id = v_department.community_id;
  if v_community.location is null then
    return;
  end if;
  v_role := public.professional_membership_role(v_department.kind::text);

  return query
  with needed as (
    select distinct cc.skill_id
      from public.department_categories dc
      join public.complaint_categories cc on cc.id = dc.category_id
     where dc.department_id = p_department_id and cc.skill_id is not null
  )
  select p.id, p.display_name, p.headline, p.phone_e164, p.status, p.is_available,
         p.service_radius_km,
         round((extensions.st_distance(v_community.location, p.location) / 1000)::numeric, 2),
         array_agg(distinct ms.name order by ms.name),
         coalesce((
           select array_agg(s2.name order by s2.name)
             from public.service_provider_skills x
             join public.skills s2 on s2.id = x.skill_id and s2.is_active
            where x.service_provider_id = p.id
         ), '{}'::text[]),
         (select count(*)::integer from public.community_memberships m
           where m.profile_id = p.profile_id and m.role in ('worker', 'security')
             and m.status = 'active' and m.ended_at is null),
         exists(select 1 from public.service_applications a
           where a.department_id = p_department_id and a.service_provider_id = p.id and a.status = 'pending')
    from public.service_providers p
    join public.service_provider_skills sps on sps.service_provider_id = p.id and sps.skill_id in (select skill_id from needed)
    join public.skills ms on ms.id = sps.skill_id and ms.is_active
   where p.status = 'active'
     and p.is_available
     and p.location is not null
     -- Constant outer bound lets the GiST index prune the global provider set;
     -- the next predicate applies each professional's stricter chosen radius.
     and extensions.st_dwithin(p.location, v_community.location, 500000)
     and extensions.st_dwithin(p.location, v_community.location, p.service_radius_km * 1000)
     and (p_query is null or p.display_name ilike '%' || btrim(p_query) || '%')
     and not exists (select 1 from public.blacklisted_service_providers b
       where b.community_id = v_department.community_id and b.service_provider_id = p.id and b.revoked_at is null)
     and not exists (select 1 from public.staff_assignments sa
       where sa.department_id = p_department_id and sa.service_provider_id = p.id and sa.status = 'active')
     and not exists (select 1 from public.community_memberships m
       where m.community_id = v_department.community_id and m.profile_id = p.profile_id
         and m.status = 'active' and m.ended_at is null)
     and not exists (select 1 from public.community_memberships m
       where m.profile_id = p.profile_id and m.role in ('worker', 'security') and m.role::text <> v_role
         and m.status = 'active' and m.ended_at is null)
   group by p.id, p.display_name, p.headline, p.phone_e164, p.status,
            p.is_available, p.service_radius_km, p.profile_id, p.location
   order by extensions.st_distance(v_community.location, p.location), lower(p.display_name), p.id
   limit greatest(1, least(coalesce(p_limit, 20), 20))
   offset greatest(0, coalesce(p_offset, 0));
end;
$$;

revoke all on function public.search_serviceable_communities(text, integer, integer) from public, anon;
grant execute on function public.search_serviceable_communities(text, integer, integer) to authenticated;
revoke all on function public.search_hireable_service_providers(uuid, text, integer, integer) from public, anon;
grant execute on function public.search_hireable_service_providers(uuid, text, integer, integer) to authenticated;

drop policy if exists service_applications_read on public.service_applications;
create policy service_applications_read on public.service_applications
  for select to authenticated
  using (
    public.can_hire_for_department(department_id)
    or exists (
      select 1 from public.service_providers p
       where p.id = service_provider_id and p.profile_id = auth.uid()
    )
  );

-- Notify only the selected department's active manager. Community admins are
-- the audience only while that department has no manager.
create or replace function public.notify_hiring_deciders(
  p_department_id uuid,
  p_kind text,
  p_payload jsonb default '{}'::jsonb
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_recipient uuid;
  v_count integer := 0;
begin
  for v_recipient in
    with department as (
      select id, community_id from public.departments where id = p_department_id
    ), manager_recipients as (
      select membership_id as id
        from public.hiring_department_managers(p_department_id)
    ), recipients as (
      select id from manager_recipients
      union
      select m.id
        from department d
        join public.community_memberships m on m.community_id = d.community_id
         and m.role = 'admin' and m.status = 'active' and m.ended_at is null
       where not exists (select 1 from manager_recipients)
    )
    select distinct id from recipients
  loop
    perform public.notify_member(v_recipient, p_kind, p_payload);
    v_count := v_count + 1;
  end loop;
  return v_count;
end;
$$;

create or replace function public.apply_to_department(
  p_department_id uuid,
  p_message text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_provider public.service_providers%rowtype;
  v_department public.departments%rowtype;
  v_community public.communities%rowtype;
  v_role text;
  v_id uuid;
begin
  select * into v_provider from public.service_providers where profile_id = auth.uid();
  if not found then
    raise exception 'Register as a service provider first.' using errcode = 'HB404';
  end if;
  if v_provider.location is null then
    raise exception 'Set your location before applying.' using errcode = 'HBLOC';
  end if;

  select * into v_department from public.departments where id = p_department_id and is_active;
  if not found then raise exception 'No such department.' using errcode = 'HB404'; end if;
  select * into v_community from public.communities
   where id = v_department.community_id and status = 'active' and location is not null;
  if not found
     or not extensions.st_dwithin(v_community.location, v_provider.location,
                                   v_provider.service_radius_km * 1000) then
    raise exception 'This department is outside your service area.' using errcode = 'HB404';
  end if;

  if not exists (
    select 1
      from public.department_categories dc
      join public.complaint_categories cc on cc.id = dc.category_id
      join public.service_provider_skills sps on sps.skill_id = cc.skill_id
       and sps.service_provider_id = v_provider.id
      join public.skills s on s.id = sps.skill_id and s.is_active
     where dc.department_id = v_department.id
  ) then
    raise exception 'Your skills do not match this department.' using errcode = 'HB403';
  end if;

  if exists (select 1 from public.blacklisted_service_providers
    where community_id = v_department.community_id
      and service_provider_id = v_provider.id and revoked_at is null) then
    raise exception 'This department is not accepting your application.' using errcode = 'HB403';
  end if;
  if exists (select 1 from public.community_memberships
    where community_id = v_department.community_id and profile_id = auth.uid()
      and status = 'active' and ended_at is null) then
    raise exception 'You already belong to this community.' using errcode = 'HB409';
  end if;

  v_role := public.professional_membership_role(v_department.kind::text);
  if exists (select 1 from public.community_memberships
    where profile_id = auth.uid() and role in ('worker', 'security')
      and role::text <> v_role and status = 'active' and ended_at is null) then
    raise exception 'A professional account cannot mix worker and security memberships.' using errcode = 'HB409';
  end if;

  insert into public.service_applications (
    community_id, department_id, service_provider_id, direction, message
  ) values (
    v_department.community_id, v_department.id, v_provider.id, 'applied',
    nullif(btrim(coalesce(p_message, '')), '')
  ) returning id into v_id;

  perform public.notify_hiring_deciders(
    v_department.id, 'service_application_received',
    jsonb_build_object(
      'applicationId', v_id, 'departmentId', v_department.id,
      'departmentName', v_department.name, 'providerName', v_provider.display_name
    )
  );
  return v_id;
end;
$$;

create or replace function public.invite_service_provider(
  p_department_id uuid,
  p_service_provider_id uuid,
  p_message text default null,
  p_rank text default 'member',
  p_job_title text default null,
  p_shift text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_department public.departments%rowtype;
  v_community public.communities%rowtype;
  v_provider public.service_providers%rowtype;
  v_actor uuid;
  v_role text;
  v_id uuid;
begin
  if not public.can_hire_for_department(p_department_id) then
    raise exception 'You may not hire for this department.' using errcode = 'HB403';
  end if;
  select * into v_department from public.departments where id = p_department_id and is_active;
  if not found then raise exception 'No such department.' using errcode = 'HB404'; end if;
  select * into v_community from public.communities where id = v_department.community_id;
  select * into v_provider from public.service_providers
   where id = p_service_provider_id and status = 'active' and is_available and location is not null;
  if not found then raise exception 'No such available service provider.' using errcode = 'HB404'; end if;
  if v_community.location is null
     or not extensions.st_dwithin(v_provider.location, v_community.location,
                                   v_provider.service_radius_km * 1000) then
    raise exception 'This person is outside the community service area.' using errcode = 'HB404';
  end if;
  if not exists (
    select 1 from public.department_categories dc
    join public.complaint_categories cc on cc.id = dc.category_id
    join public.service_provider_skills sps on sps.skill_id = cc.skill_id
     and sps.service_provider_id = v_provider.id
    join public.skills s on s.id = sps.skill_id and s.is_active
    where dc.department_id = v_department.id
  ) then
    raise exception 'This person does not have a required skill.' using errcode = 'HB409';
  end if;
  if exists (select 1 from public.blacklisted_service_providers
    where community_id = v_department.community_id
      and service_provider_id = v_provider.id and revoked_at is null) then
    raise exception 'This person is blacklisted in your community.' using errcode = 'HB409';
  end if;
  if exists (select 1 from public.community_memberships
    where community_id = v_department.community_id and profile_id = v_provider.profile_id
      and status = 'active' and ended_at is null) then
    raise exception 'This person already belongs to your community.' using errcode = 'HB409';
  end if;

  v_role := public.professional_membership_role(v_department.kind::text);
  if exists (select 1 from public.community_memberships
    where profile_id = v_provider.profile_id and role in ('worker', 'security')
      and role::text <> v_role and status = 'active' and ended_at is null) then
    raise exception 'A professional account cannot mix worker and security memberships.' using errcode = 'HB409';
  end if;

  select id into v_actor from public.community_memberships
   where community_id = v_department.community_id and profile_id = auth.uid()
     and status = 'active' and ended_at is null limit 1;
  insert into public.service_applications (
    community_id, department_id, service_provider_id, direction, message,
    rank, job_title, shift, created_by_membership_id
  ) values (
    v_department.community_id, v_department.id, v_provider.id, 'invited',
    nullif(btrim(coalesce(p_message, '')), ''),
    coalesce(nullif(btrim(coalesce(p_rank, '')), ''), 'member'),
    nullif(btrim(coalesce(p_job_title, '')), ''),
    nullif(btrim(coalesce(p_shift, '')), ''), v_actor
  ) returning id into v_id;
  return v_id;
end;
$$;

create or replace function public.decide_service_application(
  p_application_id uuid,
  p_decision text,
  p_rank text default null,
  p_job_title text default null,
  p_shift text default null,
  p_note text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_app public.service_applications%rowtype;
  v_department public.departments%rowtype;
  v_provider public.service_providers%rowtype;
  v_decision text := lower(btrim(coalesce(p_decision, '')));
  v_is_manager boolean;
  v_is_owner boolean;
  v_actor uuid;
  v_membership uuid;
  v_staff uuid;
  v_role text;
  v_rank text;
  v_job_title text;
  v_shift text;
begin
  if v_decision not in ('accepted', 'rejected', 'withdrawn') then
    raise exception 'Unknown decision.' using errcode = '22004';
  end if;
  select * into v_app from public.service_applications
   where id = p_application_id for update;
  if not found then raise exception 'No such application.' using errcode = 'HB404'; end if;
  if v_app.status <> 'pending' then
    raise exception 'This application has already been decided.' using errcode = 'HB409';
  end if;
  select * into v_department from public.departments where id = v_app.department_id;
  select * into v_provider from public.service_providers where id = v_app.service_provider_id;
  v_is_manager := public.can_hire_for_department(v_app.department_id);
  v_is_owner := v_provider.profile_id = auth.uid();

  if v_decision = 'withdrawn' then
    if not ((v_app.direction = 'applied' and v_is_owner)
            or (v_app.direction = 'invited' and v_is_manager)) then
      raise exception 'Only the side that opened this may withdraw it.' using errcode = 'HB403';
    end if;
  elsif v_app.direction = 'applied' then
    if not v_is_manager then
      raise exception 'Only the department may answer an application.' using errcode = 'HB403';
    end if;
  elsif not v_is_owner then
    raise exception 'Only the invited person may answer an invitation.' using errcode = 'HB403';
  end if;

  select id into v_actor from public.community_memberships
   where community_id = v_app.community_id and profile_id = auth.uid()
     and status = 'active' and ended_at is null limit 1;

  if v_app.direction = 'applied' then
    v_rank := coalesce(nullif(btrim(coalesce(p_rank, '')), ''), v_app.rank, 'member');
    v_job_title := coalesce(nullif(btrim(coalesce(p_job_title, '')), ''), v_app.job_title);
    v_shift := coalesce(nullif(btrim(coalesce(p_shift, '')), ''), v_app.shift);
  else
    -- The invited professional accepts the stored offer; caller-supplied terms
    -- are deliberately ignored at the database trust boundary.
    v_rank := coalesce(v_app.rank, 'member');
    v_job_title := v_app.job_title;
    v_shift := v_app.shift;
  end if;

  if v_decision = 'accepted' then
    if exists (select 1 from public.blacklisted_service_providers
      where community_id = v_app.community_id
        and service_provider_id = v_app.service_provider_id and revoked_at is null) then
      raise exception 'This person is blacklisted in this community.' using errcode = 'HB409';
    end if;
    if exists (select 1 from public.community_memberships
      where community_id = v_app.community_id and profile_id = v_provider.profile_id
        and status = 'active' and ended_at is null) then
      raise exception 'This person already belongs to this community.' using errcode = 'HB409';
    end if;
    v_role := public.professional_membership_role(v_department.kind::text);
    if exists (select 1 from public.community_memberships
      where profile_id = v_provider.profile_id and role in ('worker', 'security')
        and role::text <> v_role and status = 'active' and ended_at is null) then
      raise exception 'A professional account cannot mix worker and security memberships.' using errcode = 'HB409';
    end if;

    insert into public.community_memberships (
      community_id, profile_id, department_id, role, status, joined_at
    ) values (
      v_app.community_id, v_provider.profile_id, v_app.department_id,
      v_role::public.membership_role, 'active', now()
    ) returning id into v_membership;
    insert into public.staff_assignments (
      community_id, department_id, membership_id, service_provider_id,
      display_name, phone_e164, job_title, rank, shift, status,
      employment_type, started_at
    ) values (
      v_app.community_id, v_app.department_id, v_membership, v_provider.id,
      v_provider.display_name, v_provider.phone_e164, v_job_title, v_rank,
      v_shift, 'active', 'staff', current_date
    ) returning id into v_staff;
  end if;

  update public.service_applications
     set status = v_decision,
         rank = v_rank,
         job_title = v_job_title,
         shift = v_shift,
         decided_by_membership_id = v_actor,
         decided_at = now(),
         decision_note = nullif(btrim(coalesce(p_note, '')), ''),
         updated_at = now()
   where id = v_app.id;

  if v_decision <> 'withdrawn' and v_app.direction = 'applied' and v_membership is not null then
    perform public.notify_member(
      v_membership, 'service_application_' || v_decision,
      jsonb_build_object('applicationId', v_app.id, 'communityId', v_app.community_id,
                         'departmentName', v_department.name)
    );
  elsif v_decision <> 'withdrawn' and v_app.direction = 'invited' then
    perform public.notify_hiring_deciders(
      v_app.department_id, 'service_invitation_' || v_decision,
      jsonb_build_object('applicationId', v_app.id, 'departmentId', v_app.department_id,
                         'departmentName', v_department.name,
                         'providerName', v_provider.display_name)
    );
  end if;
  return coalesce(v_staff, v_app.id);
end;
$$;

revoke all on function public.notify_hiring_deciders(uuid, text, jsonb) from public, anon, authenticated;
revoke all on function public.apply_to_department(uuid, text) from public, anon;
grant execute on function public.apply_to_department(uuid, text) to authenticated;
revoke all on function public.invite_service_provider(uuid, uuid, text, text, text, text) from public, anon;
grant execute on function public.invite_service_provider(uuid, uuid, text, text, text, text) to authenticated;
revoke all on function public.decide_service_application(uuid, text, text, text, text, text) from public, anon;
grant execute on function public.decide_service_application(uuid, text, text, text, text, text) to authenticated;

notify pgrst, 'reload schema';
