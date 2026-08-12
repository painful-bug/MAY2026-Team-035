-- Forward-only nearby community discovery must not disappear just because a community has
-- not configured departments or categories yet. Applications remain limited to
-- matching departments by the existing apply_to_department guard.

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
  with matching_departments as (
    select d.community_id, d.id as department_id, d.name as department_name,
           s.name as skill_name
      from public.departments d
      join public.department_categories dc on dc.department_id = d.id
      join public.complaint_categories cc on cc.id = dc.category_id and cc.skill_id is not null
      join public.service_provider_skills sps
        on sps.skill_id = cc.skill_id and sps.service_provider_id = v_provider.id
      join public.skills s on s.id = cc.skill_id and s.is_active
     where d.is_active
       and (v_mode is null or v_mode = public.professional_membership_role(d.kind::text)::text)
  )
  select c.id, c.name, c.city, c.state, c.community_type,
         round((extensions.st_distance(c.location, v_provider.location) / 1000)::numeric, 2),
         coalesce(
           array_agg(distinct md.skill_name order by md.skill_name)
             filter (where md.department_id is not null),
           '{}'::text[]
         ),
         coalesce(
           jsonb_agg(distinct jsonb_build_object('id', md.department_id, 'name', md.department_name))
             filter (where md.department_id is not null),
           '[]'::jsonb
         )
    from public.communities c
    left join matching_departments md on md.community_id = c.id
   where c.status = 'active'
     and c.location is not null
     and extensions.st_dwithin(c.location, v_provider.location, v_provider.service_radius_km * 1000)
     and (p_query is null or c.name ilike '%' || btrim(p_query) || '%')
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

revoke all on function public.search_serviceable_communities(text, integer, integer) from public, anon;
grant execute on function public.search_serviceable_communities(text, integer, integer) to authenticated;
