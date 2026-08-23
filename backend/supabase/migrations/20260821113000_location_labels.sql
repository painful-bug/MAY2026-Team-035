-- ===========================================================================
-- Human-readable location labels: `location_label` on service_providers and
-- communities.
--
-- HOW TO APPLY
--
-- Paste this whole file into the Supabase SQL editor (Dashboard -> SQL Editor
-- -> New query) and run it once. It is idempotent -- the column adds are
-- guarded, every function is recreated whole, and the file ends with a
-- verification block that raises rather than reporting success if any part of
-- it did not take. Nothing here backfills or rewrites a row: every existing
-- provider and community keeps a null label until somebody sets one.
--
-- WHAT THIS ADDS, AND WHY
--
-- Live testing, 2026-08-21: registration asked servicemen for a latitude and a
-- longitude and nothing else. Raw coordinates are not something a person knows
-- about their own house, so the field was either skipped -- leaving a provider
-- with no `location`, invisible to every proximity search in `0034` 9 -- or
-- filled with a guess. The frontend now offers address search and a draggable
-- map pin, and both of those produce a *name* for the point as a side effect.
-- That name is worth keeping, for one reason:
--
--   A hiring manager's candidate card can say "Andheri West, Mumbai" instead of
--   nothing at all. `distance_km` answers *how far*; it does not answer *where*,
--   and "12.4 km away" from a society that spans two suburbs is not an answer a
--   person can picture.
--
-- WHAT THIS DELIBERATELY DOES NOT CHANGE
--
-- **Distance mechanics.** `latitude`/`longitude` remain the stored truth and
-- `location` remains generated from them (`0034` 3 and 6). No search function's
-- geometry, radius or ordering is touched by this file. The label is a
-- decoration on the input, not an input to the maths.
--
-- **The coordinate narrowing on hiring reads.** `search_hireable_service_providers`
-- gains `location_label` and still returns no `latitude`/`longitude`, matching
-- the column list in `service_providers_repository._CANDIDATE_SELECT`. A coarse
-- label is what the person chose to publish; a home coordinate is not, and this
-- file must not become the route by which one leaks. 120 characters is a cap
-- with a purpose: it holds "suburb, city, state" and does not hold a street
-- address with a house number.
--
-- WHY FUNCTIONS ARE DROPPED AND RECREATED RATHER THAN REPLACED
--
-- Three of them gain a parameter and one gains an OUT column. `create or
-- replace` cannot do either: adding a defaulted parameter creates an *overload*
-- (after which a 7-argument call is "function is not unique" and fails), and
-- changing a returned column set is refused outright. Each is therefore dropped
-- by its exact old signature and recreated. Bodies are otherwise carried over
-- verbatim from the file named above each one.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. The columns
--
-- Nullable, with no default and no backfill. A null label means "nobody has
-- named this place yet", which is the truth for every row that exists today and
-- for every future row whose owner declined the optional field.
-- ---------------------------------------------------------------------------

alter table public.service_providers
  add column if not exists location_label text;

alter table public.communities
  add column if not exists location_label text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.service_providers'::regclass
       and conname  = 'service_providers_location_label_check'
  ) then
    alter table public.service_providers
      add constraint service_providers_location_label_check
      check (location_label is null
             or length(btrim(location_label)) between 1 and 120);
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.communities'::regclass
       and conname  = 'communities_location_label_check'
  ) then
    alter table public.communities
      add constraint communities_location_label_check
      check (location_label is null
             or length(btrim(location_label)) between 1 and 120);
  end if;
end $$;

comment on column public.service_providers.location_label is
  'Coarse, human-readable place name ("Andheri West, Mumbai"), suggested by '
  'reverse geocoding and editable by its owner. Shown to hiring managers, who '
  'never receive latitude/longitude. Never used for distance: `location` is.';

comment on column public.communities.location_label is
  'Coarse, human-readable place name for the society''s pin. Set during founder '
  'onboarding or from admin settings; suggested, never authoritative.';

-- A blank string is not a label, and 120 is the constraint above. Every write
-- path below runs its argument through this rather than restating the rule four
-- times and getting one of them wrong.
create or replace function public.clean_location_label(p_label text)
returns text
language sql
immutable
as $$
  select nullif(left(btrim(coalesce(p_label, '')), 120), '');
$$;

comment on function public.clean_location_label(text) is
  'Trim, cap at 120 characters, and treat an empty result as null. The one '
  'place the location-label shape is enforced for writes.';

grant execute on function public.clean_location_label(text) to authenticated;

-- ---------------------------------------------------------------------------
-- 2. Reads
--
-- `service_provider_overview` from `0034` 8, verbatim plus one column.
-- ---------------------------------------------------------------------------

drop view if exists public.service_provider_overview;
create view public.service_provider_overview
with (security_invoker = true) as
select
  p.id,
  p.profile_id,
  p.display_name,
  p.headline,
  p.bio,
  p.phone_e164,
  p.latitude,
  p.longitude,
  p.location_label,
  p.service_radius_km,
  p.status,
  p.is_available,
  p.created_at,
  p.updated_at,
  coalesce(sk.skill_ids,   array[]::uuid[]) as skill_ids,
  coalesce(sk.skill_names, array[]::text[]) as skill_names,
  coalesce(mem.community_count, 0)          as community_count
from public.service_providers p
left join lateral (
  select array_agg(s.id order by s.name)   as skill_ids,
         array_agg(s.name order by s.name) as skill_names
    from public.service_provider_skills sps
    join public.skills s on s.id = sps.skill_id
   where sps.service_provider_id = p.id
) sk on true
left join lateral (
  select count(*) as community_count
    from public.community_memberships m
   where m.profile_id = p.profile_id
     and m.role in ('worker', 'security')
     and m.status = 'active'
     and m.ended_at is null
) mem on true;

comment on view public.service_provider_overview is
  'A service person with their skills and how many communities currently employ '
  'them. Readable by any authenticated caller: a department manager has to be '
  'able to find someone they have never met. Column-level narrowing for the '
  'hiring surface lives in the repository''s select list, not here.';

grant select on public.service_provider_overview to authenticated;

-- `community_settings_overview` from `20260811162409` 2, verbatim plus one
-- column. Recreated whole rather than patched: a view is replaced by its whole
-- definition, and a partial restatement here would silently drop the rest.
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
  c.longitude,
  c.location_label
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
-- 3. The provider's own writes
--
-- `upsert_service_provider` from `0045` 14, plus `p_location_label`. The null
-- coalesce is the same rule the other seven fields already follow: an omitted
-- label leaves the stored one alone, so a PATCH that changes only a headline
-- does not wipe the place name. Clearing a label is therefore not expressible
-- here, exactly as clearing a headline is not -- both are edited by typing
-- something else, which is what the form does.
-- ---------------------------------------------------------------------------

drop function if exists public.upsert_service_provider(
  text, text, text, text, numeric, numeric, numeric);

create function public.upsert_service_provider(
  p_display_name      text,
  p_headline          text default null,
  p_bio               text default null,
  p_phone_e164        text default null,
  p_latitude          numeric default null,
  p_longitude         numeric default null,
  p_service_radius_km numeric default null,
  p_location_label    text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id    uuid;
  v_label text := public.clean_location_label(p_location_label);
begin
  if auth.uid() is null then
    raise exception 'Sign in required.' using errcode = '42501';
  end if;

  -- A name is required only when there is nothing stored to keep.
  if not exists (select 1 from public.service_providers
                  where profile_id = auth.uid())
     and (p_display_name is null or length(btrim(p_display_name)) < 2) then
    raise exception 'A name is required.' using errcode = '22004';
  end if;

  if p_display_name is not null and length(btrim(p_display_name)) < 2 then
    raise exception 'A name is required.' using errcode = '22004';
  end if;

  insert into public.service_providers as sp (
    profile_id, display_name, headline, bio, phone_e164,
    latitude, longitude, service_radius_km, location_label
  )
  values (
    auth.uid(), btrim(p_display_name), p_headline, p_bio, p_phone_e164,
    p_latitude, p_longitude, coalesce(p_service_radius_km, 15), v_label
  )
  on conflict (profile_id) do update
     set display_name      = coalesce(btrim(p_display_name), sp.display_name),
         headline          = coalesce(p_headline, sp.headline),
         bio               = coalesce(p_bio, sp.bio),
         phone_e164        = coalesce(p_phone_e164, sp.phone_e164),
         latitude          = coalesce(p_latitude, sp.latitude),
         longitude         = coalesce(p_longitude, sp.longitude),
         service_radius_km = coalesce(p_service_radius_km, sp.service_radius_km),
         location_label    = coalesce(v_label, sp.location_label)
  returning sp.id into v_id;

  return v_id;
end;
$$;

comment on function public.upsert_service_provider(
  text, text, text, text, numeric, numeric, numeric, text) is
  'Register or edit a service-provider profile. Since 0045 a null name keeps '
  'the stored one -- settings edit details, never identity. Since 20260821 a '
  'null location label does the same.';

revoke all on function public.upsert_service_provider(
  text, text, text, text, numeric, numeric, numeric, text) from public, anon;
grant execute on function public.upsert_service_provider(
  text, text, text, text, numeric, numeric, numeric, text) to authenticated;

-- `register_service_provider` from `20260811162409` 1, plus `p_location_label`.
-- Coordinates stay required and the label stays optional, which is the whole
-- shape of the feature: the map pin is the fact, the name is the courtesy.

drop function if exists public.register_service_provider(
  text, text, text, numeric, numeric, numeric, uuid[]);

create function public.register_service_provider(
  p_display_name text,
  p_headline text,
  p_phone_e164 text,
  p_latitude numeric,
  p_longitude numeric,
  p_service_radius_km numeric,
  p_skill_ids uuid[],
  p_location_label text default null
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
    p_latitude, p_longitude, coalesce(p_service_radius_km, 15),
    p_location_label
  );
  perform public.set_service_provider_skills(p_skill_ids);
  return v_provider;
end;
$$;

comment on function public.register_service_provider(
  text, text, text, numeric, numeric, numeric, uuid[], text) is
  'Atomically creates or repairs the signed-in professional profile and full '
  'active skill set. Refuses existing non-professional members on first '
  'registration. The location label is optional; the coordinates are not.';

revoke all on function public.register_service_provider(
  text, text, text, numeric, numeric, numeric, uuid[], text) from public, anon;
grant execute on function public.register_service_provider(
  text, text, text, numeric, numeric, numeric, uuid[], text) to authenticated;

-- ---------------------------------------------------------------------------
-- 4. The community's writes
--
-- `set_my_community_location` from `20260811162409` 2, plus `p_location_label`.
-- ---------------------------------------------------------------------------

drop function if exists public.set_my_community_location(uuid, numeric, numeric);

create function public.set_my_community_location(
  p_community_id uuid,
  p_latitude numeric,
  p_longitude numeric,
  p_location_label text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_label text := public.clean_location_label(p_location_label);
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
         location_label = coalesce(v_label, location_label),
         updated_at = now()
   where id = p_community_id;
end;
$$;

revoke all on function public.set_my_community_location(uuid, numeric, numeric, text)
  from public, anon;
grant execute on function public.set_my_community_location(uuid, numeric, numeric, text)
  to authenticated;

-- `create_founder_community` from `20260811162409` 2. Payload-driven, so its
-- signature does not move -- one more key is read out of the same jsonb. The
-- nested call to the pre-location implementation is unchanged, and so is the
-- rule that a founder community without valid coordinates is refused.

create or replace function public.create_founder_community(p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_latitude numeric := (p_payload->>'latitude')::numeric;
  v_longitude numeric := (p_payload->>'longitude')::numeric;
  v_label text := public.clean_location_label(p_payload->>'location_label');
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
     set latitude = v_latitude,
         longitude = v_longitude,
         location_label = v_label,
         updated_at = now()
   where id = v_community;
  return v_result;
end;
$$;

revoke all on function public.create_founder_community(jsonb)
  from public, anon, authenticated;
grant execute on function public.create_founder_community(jsonb) to service_role;

-- ---------------------------------------------------------------------------
-- 5. The hiring read
--
-- `search_hireable_service_providers` from `20260812090100` (the union of the
-- category path with the department's own declared skills), verbatim plus one
-- returned column. Dropped first because a returned column set cannot be
-- replaced in place.
--
-- The added column is `location_label` and NOT the coordinates it was derived
-- from. That asymmetry is the point and it is the same one
-- `_CANDIDATE_SELECT` writes down in Python: a manager may know that somebody
-- is in Andheri West without being told which building.
-- ---------------------------------------------------------------------------

drop function if exists public.search_hireable_service_providers(
  uuid, text, integer, integer);

create function public.search_hireable_service_providers(
  p_department_id uuid,
  p_query text default null,
  p_limit integer default 20,
  p_offset integer default 0
)
returns table (
  id uuid, display_name text, headline text, phone_e164 varchar(20), status text,
  is_available boolean, service_radius_km numeric, distance_km numeric,
  matching_skill_names text[], skill_names text[], community_count integer,
  has_open_application boolean, location_label text
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
    union
    select distinct ds.skill_id
      from public.department_skills ds
     where ds.department_id = p_department_id
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
           where a.department_id = p_department_id and a.service_provider_id = p.id and a.status = 'pending'),
         p.location_label
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
            p.is_available, p.service_radius_km, p.profile_id, p.location,
            p.location_label
   order by extensions.st_distance(v_community.location, p.location), lower(p.display_name), p.id
   limit greatest(1, least(coalesce(p_limit, 20), 20))
   offset greatest(0, coalesce(p_offset, 0));
end;
$$;

comment on function public.search_hireable_service_providers(
  uuid, text, integer, integer) is
  'Service people this department could hire: available, inside their own '
  'chosen radius, holding a skill the department claims directly or one of its '
  'categories needs, not blacklisted, not on its roster, not already a member, '
  'and not already working in the other mode. Nearest first. Carries the '
  'provider''s coarse location label and never their coordinates.';

grant execute on function public.search_hireable_service_providers(
  uuid, text, integer, integer) to authenticated;

notify pgrst, 'reload schema';

-- ---------------------------------------------------------------------------
-- 6. Verification
--
-- Raises rather than reporting success if any part of the file did not take.
-- The argument-count assertions are the ones that matter: a surviving old
-- overload is the failure mode that would not show up until a call said
-- "function is not unique" in production.
-- ---------------------------------------------------------------------------

do $$
begin
  if not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'service_providers'
       and column_name = 'location_label'
  ) then
    raise exception 'service_providers.location_label missing';
  end if;

  if not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'communities'
       and column_name = 'location_label'
  ) then
    raise exception 'communities.location_label missing';
  end if;

  if not exists (
    select 1 from pg_constraint
     where conname = 'service_providers_location_label_check'
  ) then
    raise exception 'service_providers_location_label_check missing';
  end if;

  if not exists (
    select 1 from pg_constraint
     where conname = 'communities_location_label_check'
  ) then
    raise exception 'communities_location_label_check missing';
  end if;

  if not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'service_provider_overview'
       and column_name = 'location_label'
  ) then
    raise exception 'service_provider_overview does not expose location_label';
  end if;

  if not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'community_settings_overview'
       and column_name = 'location_label'
  ) then
    raise exception 'community_settings_overview does not expose location_label';
  end if;

  -- Exactly one overload each, and it is the new one. A leftover old signature
  -- makes every PostgREST call ambiguous.
  if (select count(*) from pg_proc
       where pronamespace = 'public'::regnamespace
         and proname = 'upsert_service_provider') <> 1
     or not exists (select 1 from pg_proc
       where pronamespace = 'public'::regnamespace
         and proname = 'upsert_service_provider' and pronargs = 8) then
    raise exception 'upsert_service_provider must be exactly one 8-argument function';
  end if;

  if (select count(*) from pg_proc
       where pronamespace = 'public'::regnamespace
         and proname = 'register_service_provider') <> 1
     or not exists (select 1 from pg_proc
       where pronamespace = 'public'::regnamespace
         and proname = 'register_service_provider' and pronargs = 8) then
    raise exception 'register_service_provider must be exactly one 8-argument function';
  end if;

  if (select count(*) from pg_proc
       where pronamespace = 'public'::regnamespace
         and proname = 'set_my_community_location') <> 1
     or not exists (select 1 from pg_proc
       where pronamespace = 'public'::regnamespace
         and proname = 'set_my_community_location' and pronargs = 4) then
    raise exception 'set_my_community_location must be exactly one 4-argument function';
  end if;

  if (select count(*) from pg_proc
       where pronamespace = 'public'::regnamespace
         and proname = 'search_hireable_service_providers') <> 1 then
    raise exception 'search_hireable_service_providers must be exactly one function';
  end if;

  if not exists (
    select 1
      from pg_proc pr
      cross join lateral unnest(pr.proargnames) as n(name)
     where pr.pronamespace = 'public'::regnamespace
       and pr.proname = 'search_hireable_service_providers'
       and n.name = 'location_label'
  ) then
    raise exception 'search_hireable_service_providers does not return location_label';
  end if;
end $$;
