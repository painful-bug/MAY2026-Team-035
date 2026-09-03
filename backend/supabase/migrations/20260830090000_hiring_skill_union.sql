-- ---------------------------------------------------------------------------
-- 20260830090000_hiring_skill_union.sql
--
-- Hiring reads the department's declared skills, everywhere. Issue #55 (B+D).
--
-- **What went wrong.** `20260812090100_skills_and_categories.sql` gave a
-- department a second, explicit way to say what it needs -- the
-- `department_skills` table -- and taught exactly ONE reader about it:
-- `search_hireable_service_providers`, whose `needed` CTE became the union of
-- the category path with the new table (that file 681, carried forward whole
-- by `20260821113000_location_labels.sql` 524-535). Three other functions were
-- left gating on the category path alone:
--
--   * `invite_service_provider`   (`20260811162409` 683-692, HB409
--     "This person does not have a required skill.")
--   * `apply_to_department`       (`20260811162409` 600-610, HB403
--     "Your skills do not match this department.")
--   * `search_serviceable_communities` (`20260812181443` 40-51, the
--     `matching_departments` CTE, `cc.skill_id is not null`)
--
-- The category path runs through `complaint_categories.skill_id`, which
-- `link_category_skill` (`0034` 216-233) fills by **exact name match** against
-- the `skills` catalogue. A community that names its category "Security" or
-- "Security Management" gets `skill_id = null` against catalogue entries
-- 'Security Guard' and 'Gate Officer' -- no error, no warning at the point of
-- use, and every one of the three functions above then behaves as though the
-- department needs nothing at all.
--
-- **What that costs, in the order a person meets it.** A manager opens the
-- candidate list and sees the guard they want, because the candidate search
-- already reads `department_skills`. They press invite and are told *"This
-- person does not have a required skill."* -- refused by a second function
-- that does not. The guard, from their own side, cannot find the community at
-- all: `search_serviceable_communities` shows them nothing to apply to, and
-- had it shown them, `apply_to_department` would have refused the
-- application. One table, four readers, one of them taught.
--
-- **What this file does.** `create or replace` on the three, each carrying its
-- live body forward WHOLE -- every guard, every notification, every error code
-- and every comment -- with only the skill-gate predicate rewritten, marked
-- `-- CHANGED` in place. That convention is `20260812113000`'s and the reason
-- still holds: a partial edit to a function body that lives in another file is
-- a diff nobody can review, and a same-signature `create or replace` that
-- retypes the body from memory silently withdraws whatever the original had
-- that the author forgot.
--
-- **UNION, not replacement.** A department that has declared no skills keeps
-- hiring exactly as it did yesterday, off its categories. This file adds a
-- second way for a department to say what it needs; it withdraws neither the
-- first nor anything else.
--
-- **Signatures are byte-identical**, so the existing `revoke`/`grant` pairs
-- survive the replace untouched. They are reissued below anyway, matching what
-- `20260811162409` 864-867 and `20260812181443` 86-87 do -- this is the file a
-- reader finds first if they ask who may call these.
--
-- **Nothing else moves.** No table, no column, no policy, no constraint, no
-- trigger, no fourth function. `department_skills` itself is untouched: this
-- file only reads it.
--
-- Idempotent: three `create or replace` statements and their grants, all of
-- which may be run again. One transaction -- the SQL editor wraps the paste,
-- so a failure anywhere rolls back everything.
--
-- Hand-applied by the owner in the Supabase SQL editor, like every file here.
-- Runbook section 35.
--
-- ROLLBACK: re-run `20260811162409_service_professional_onboarding.sql`
-- sections for `apply_to_department` and `invite_service_provider`, and
-- `20260812181443_search_nearby_communities.sql` whole. Those files hold the
-- pre-image of all three bodies verbatim, which is exactly why this file
-- copied rather than retyped them.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. apply_to_department -- the professional's side of the handshake
--
-- `20260811162409` 566's body, whole, with the one predicate changed.
-- ---------------------------------------------------------------------------

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

  -- CHANGED: was the category path alone. Now the union of it with the
  -- department's own declared skills -- the same `needed` set
  -- `20260812090100` gave `search_hireable_service_providers`, so the list a
  -- department is offered and the list it will accept are one list.
  if not exists (
    with needed as (
      select distinct cc.skill_id
        from public.department_categories dc
        join public.complaint_categories cc on cc.id = dc.category_id
       where dc.department_id = v_department.id and cc.skill_id is not null
      union
      select distinct ds.skill_id
        from public.department_skills ds
       where ds.department_id = v_department.id
    )
    select 1
      from public.service_provider_skills sps
      join needed n on n.skill_id = sps.skill_id
      join public.skills s on s.id = sps.skill_id and s.is_active
     where sps.service_provider_id = v_provider.id
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

revoke all on function public.apply_to_department(uuid, text) from public, anon;
grant execute on function public.apply_to_department(uuid, text) to authenticated;


-- ---------------------------------------------------------------------------
-- 2. invite_service_provider -- the department's side of the same handshake
--
-- `20260811162409` 648's body, whole, with the one predicate changed. The
-- refusal it raises is the one a manager meets after the candidate search --
-- which already reads `department_skills` -- has offered them the person.
-- ---------------------------------------------------------------------------

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
  -- CHANGED: was the category path alone. Now the union of it with the
  -- department's own declared skills -- the same `needed` set
  -- `search_hireable_service_providers` uses to build the candidate list this
  -- invitation is sent from.
  if not exists (
    with needed as (
      select distinct cc.skill_id
        from public.department_categories dc
        join public.complaint_categories cc on cc.id = dc.category_id
       where dc.department_id = v_department.id and cc.skill_id is not null
      union
      select distinct ds.skill_id
        from public.department_skills ds
       where ds.department_id = v_department.id
    )
    select 1
      from public.service_provider_skills sps
      join needed n on n.skill_id = sps.skill_id
      join public.skills s on s.id = sps.skill_id and s.is_active
     where sps.service_provider_id = v_provider.id
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

revoke all on function public.invite_service_provider(uuid, uuid, text, text, text, text) from public, anon;
grant execute on function public.invite_service_provider(uuid, uuid, text, text, text, text) to authenticated;


-- ---------------------------------------------------------------------------
-- 3. search_serviceable_communities -- what a professional can even see
--
-- `20260812181443` 5's body, whole, with the `matching_departments` CTE fed
-- from the union instead of from the category join alone. The forward-only
-- rule that file states is untouched: a community still appears by proximity
-- whether or not it has a matching department, and it is the departments
-- array and `matchingSkillNames` that this widens.
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
  with department_needs as (
    -- CHANGED: was the category path alone, spelled out in the join below.
    -- Now the union of it with each department's own declared skills, lifted
    -- into its own CTE so the join reads one set instead of two.
    select dc.department_id, cc.skill_id
      from public.department_categories dc
      join public.complaint_categories cc on cc.id = dc.category_id and cc.skill_id is not null
    union
    select ds.department_id, ds.skill_id
      from public.department_skills ds
  ),
  matching_departments as (
    select d.community_id, d.id as department_id, d.name as department_name,
           s.name as skill_name
      from public.departments d
      -- CHANGED: `department_needs` in place of the inlined category join.
      join department_needs dn on dn.department_id = d.id
      join public.service_provider_skills sps
        on sps.skill_id = dn.skill_id and sps.service_provider_id = v_provider.id
      join public.skills s on s.id = dn.skill_id and s.is_active
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

comment on function public.search_serviceable_communities(text, integer, integer) is
  'Communities inside the caller''s own service radius they could apply to, '
  'nearest first. A community appears by proximity alone; its departments '
  'array carries only active departments needing a skill the caller holds -- '
  'claimed directly by the department or needed by one of its categories. '
  'Blacklisted communities and communities the caller already belongs to are '
  'hidden.';

notify pgrst, 'reload schema';


-- ---------------------------------------------------------------------------
-- 4. Verification, in the same transaction
--
-- `create or replace function` succeeds against a body with no union in it
-- just as happily as against these three, so the only proof the apply did what
-- the header claims is to ask the database for the definitions it now holds.
-- A half-pasted file cannot look like a successful one.
--
-- Each signature is spelled out because Postgres resolves by argument list:
-- replacing an overload that is not the one the API calls would leave the gate
-- shut with every other check here passing.
-- ---------------------------------------------------------------------------

do $$
declare
  v_signature text;
  v_oid       oid;
  v_def       text;
begin
  foreach v_signature in array array[
    'public.apply_to_department(uuid, text)',
    'public.invite_service_provider(uuid, uuid, text, text, text, text)',
    'public.search_serviceable_communities(text, integer, integer)'
  ] loop
    v_oid := to_regprocedure(v_signature);
    if v_oid is null then
      raise exception '% is absent under the signature this file replaces',
        v_signature;
    end if;

    v_def := pg_get_functiondef(v_oid);

    if position('public.department_skills' in v_def) = 0 then
      raise exception
        '% still gates on the category path alone -- department_skills is not in its body',
        v_signature;
    end if;

    -- The union, not a replacement: the category path has to survive too, or a
    -- department that has declared no skills stops hiring altogether.
    if position('public.complaint_categories' in v_def) = 0 then
      raise exception
        '% lost the category path -- this file unions, it does not replace',
        v_signature;
    end if;

    if position('union' in v_def) = 0 then
      raise exception '% holds both paths but does not union them', v_signature;
    end if;
  end loop;

  -- The two refusals are unchanged text: they are user-facing copy the error
  -- envelope carries verbatim to a screen, and this file changes when they
  -- fire, not what they say.
  if position('This person does not have a required skill.' in
      pg_get_functiondef(to_regprocedure(
        'public.invite_service_provider(uuid, uuid, text, text, text, text)'))) = 0 then
    raise exception 'invite_service_provider lost its refusal message';
  end if;

  if position('Your skills do not match this department.' in
      pg_get_functiondef(to_regprocedure(
        'public.apply_to_department(uuid, text)'))) = 0 then
    raise exception 'apply_to_department lost its refusal message';
  end if;

  raise notice
    'hiring_skill_union: apply_to_department, invite_service_provider and search_serviceable_communities all read department_skills.';
end $$;
