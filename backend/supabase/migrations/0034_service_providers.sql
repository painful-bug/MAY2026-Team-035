-- Who a service person is, before any community has hired them.
--
-- Everything in this directory so far describes someone who is already inside a
-- community: a resident with a unit, an admin with a term, a staff member whose
-- whole existence is a row on one department's roster. A service person is the
-- first entity here that exists *before* and *independently of* any community,
-- and goes on existing when every community drops them. That is what this file
-- adds, and it is the reason it adds a table rather than a column.
--
-- It also overturns a ruling. docs/product/USER_IDENTIFICATION.md and API.md
-- 16.1 both state that a staff member has no login by construction -- "a staff
-- member is a name on a roster, not an account" -- and 0019 relaxed
-- staff_assignments.membership_id to null precisely to say so. That stays true
-- for a roster name typed into the departments form. It stops being the only
-- case: a service person registers themselves, holds a profile, and is hired
-- into a membership by 0035. Both populations live in staff_assignments; the
-- difference is whether service_provider_id and membership_id are null.
--
-- WHY SKILLS HANG OFF THE PERSON AND NOT OFF THE ROSTER ROW
--
-- The baseline already models staff_skills(staff_assignment_id, skill_id), and
-- this file leaves it unused on purpose. The search a service person needs most
-- -- "which communities need what I do?" -- has to run before they have been
-- hired anywhere, which is exactly when they have no staff_assignment row to
-- hang a skill on. Keying skills to the roster row makes the search return
-- nothing for precisely the people it exists to serve. So skills belong to the
-- person: service_provider_skills, global, written once.
--
-- WHY complaint_categories GETS A skill_id INSTEAD OF A JOIN TABLE
--
-- The obvious shape is skill_categories(skill_id, complaint_category_id). It is
-- wrong here. `skills` is a global catalogue with a globally unique name, while
-- complaint_categories is per-community -- "Plumbing" in one community is a
-- different row from "Plumbing" in the next. A join table would therefore have
-- to carry one row per (skill, community) pair for what is a single fact, and
-- would be silently incomplete for every community created after the mapping
-- was written.
--
-- One nullable FK on complaint_categories says the same thing once. It is also
-- a real foreign key rather than the match-on-a-label pattern
-- docs/DECISIONS_NEEDED.md B6 objects to elsewhere in this schema.
--
-- The trigger that fills it in by name matters as much as the column. Without
-- it every skill_id is null, the community search returns nothing for everyone,
-- and the feature is dead on arrival behind a form nobody knows to fill in. An
-- admin who types "Plumbing" into the department form has said which trade
-- handles it; this reads that, and leaves the column writable for the cases
-- where a community's vocabulary does not match the catalogue.
--
-- GEOGRAPHY
--
-- latitude and longitude are the stored truth; `location` is generated from
-- them and exists only to be indexed. If PostGIS turns out to be unavailable on
-- the target project, dropping the two generated columns and their two indexes
-- is the entire fallback -- no API shape changes, and haversine_km() below
-- answers the same question at the same precision for the distances this
-- product deals in.
--
-- ROW SECURITY
--
-- service_providers is readable by any authenticated caller: a manager must be
-- able to find someone they have never met, which is the whole point of the
-- hiring search in 0035. It is deliberately narrow -- name, headline, skills,
-- approximate location. The provider's own writes go through RPCs that check
-- auth.uid() against profile_id, so there is no update policy at all, matching
-- the posture of 0031 where every write is a SECURITY DEFINER function.

-- ---------------------------------------------------------------------------
-- 1. PostGIS
--
-- Into `extensions`, matching how 0001 installs pg_trgm and then references it
-- as extensions.gin_trgm_ops. Unguarded, unlike the pg_cron block in 0024: that
-- one schedules a log pruner and degrades to "logs grow" when absent, while
-- everything below is typed on this extension existing. A loud failure here is
-- better than a schema that half-applies.
-- ---------------------------------------------------------------------------

create extension if not exists postgis with schema extensions;

-- ---------------------------------------------------------------------------
-- 2. Distance without PostGIS
--
-- The documented fallback for section 1, and the reason the API can be written
-- before anyone has confirmed the extension. Great-circle distance on a sphere:
-- wrong by roughly 0.3% against the WGS84 ellipsoid, which is metres over the
-- tens of kilometres this product measures, and irrelevant to ordering a list
-- of communities by how far away they are.
-- ---------------------------------------------------------------------------

create or replace function public.haversine_km(
  p_lat1 numeric, p_lon1 numeric, p_lat2 numeric, p_lon2 numeric
)
returns numeric
language sql
immutable
parallel safe
as $$
  select case
    when p_lat1 is null or p_lon1 is null or p_lat2 is null or p_lon2 is null
      then null
    else round((
      6371 * 2 * asin(sqrt(
          power(sin(radians(p_lat2 - p_lat1) / 2), 2)
        + cos(radians(p_lat1)) * cos(radians(p_lat2))
        * power(sin(radians(p_lon2 - p_lon1) / 2), 2)
      ))
    )::numeric, 3)
  end;
$$;

comment on function public.haversine_km(numeric, numeric, numeric, numeric) is
  'Great-circle distance in kilometres. The documented fallback for the PostGIS '
  'geography columns in this file: accurate to ~0.3%, which is metres at the '
  'range this product orders results over.';

grant execute on function
  public.haversine_km(numeric, numeric, numeric, numeric) to authenticated;

-- ---------------------------------------------------------------------------
-- 3. Where a community is
--
-- 0001 gives communities a postal address and nothing a distance can be
-- computed from. buildings.map_x / units.map_y are percentages on a drawn site
-- map, not earth coordinates, and cannot be promoted into these.
-- ---------------------------------------------------------------------------

alter table public.communities
  add column if not exists latitude  numeric(9,6),
  add column if not exists longitude numeric(9,6);

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.communities'::regclass
       and conname  = 'communities_latitude_check'
  ) then
    alter table public.communities
      add constraint communities_latitude_check
      check (latitude is null or latitude between -90 and 90);
  end if;
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.communities'::regclass
       and conname  = 'communities_longitude_check'
  ) then
    alter table public.communities
      add constraint communities_longitude_check
      check (longitude is null or longitude between -180 and 180);
  end if;
end $$;

alter table public.communities
  add column if not exists location extensions.geography(Point, 4326)
    generated always as (
      case
        when latitude is null or longitude is null then null
        else extensions.st_setsrid(
               extensions.st_makepoint(longitude::float8, latitude::float8),
               4326
             )::extensions.geography
      end
    ) stored;

create index if not exists communities_location_gix
  on public.communities using gist (location);

comment on column public.communities.location is
  'Generated from latitude/longitude, which are the stored truth. Exists to be '
  'indexed. Drop this column and its index to run without PostGIS.';

-- ---------------------------------------------------------------------------
-- 4. The skill catalogue
--
-- `skills` is created by 0001 and has never been read. It is global and its
-- name is globally unique, which is right for a curated trade vocabulary and
-- would be wrong for anything a community authors -- hence the seed below
-- rather than a create-your-own endpoint.
-- ---------------------------------------------------------------------------

alter table public.skills
  add column if not exists is_active  boolean not null default true,
  add column if not exists created_at timestamptz not null default now();

insert into public.skills (name, category, description)
values
  ('Plumbing',      'maintenance', 'Leaks, taps, drainage, sanitary fittings.'),
  ('Electrical',    'maintenance', 'Wiring, fittings, meters, backup power.'),
  ('Carpentry',     'maintenance', 'Doors, windows, furniture, fittings.'),
  ('Masonry',       'maintenance', 'Walls, plaster, tiling, waterproofing.'),
  ('Painting',      'maintenance', 'Interior and exterior painting.'),
  ('Appliance Repair', 'maintenance', 'Pumps, motors, lifts, white goods.'),
  ('Air Conditioning', 'maintenance', 'HVAC installation and servicing.'),
  ('Housekeeping',  'facilities',  'Cleaning of common areas and units.'),
  ('Gardening',     'facilities',  'Landscaping and horticulture.'),
  ('Pest Control',  'facilities',  'Treatment and prevention.'),
  ('Security Guard', 'security',   'Gate duty, patrol, access control.'),
  ('Gate Officer',  'security',    'Visitor verification and gate registers.')
on conflict (name) do nothing;

-- ---------------------------------------------------------------------------
-- 5. Which trade handles a community's category
--
-- The link that makes "communities that need my skills" answerable. Nullable:
-- a community may invent a category the catalogue has no word for, and that
-- must not be an error -- it only means no service person is matched to it.
-- ---------------------------------------------------------------------------

alter table public.complaint_categories
  add column if not exists skill_id uuid references public.skills(id)
    on delete set null;

create index if not exists complaint_categories_skill_idx
  on public.complaint_categories (skill_id) where skill_id is not null;

create or replace function public.link_category_skill()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  -- Only ever fills a blank. An explicit skill_id -- from an admin who
  -- disagreed with the catalogue -- is never overwritten by a rename.
  if new.skill_id is null then
    select s.id into new.skill_id
      from public.skills s
     where lower(btrim(s.name)) = lower(btrim(new.name))
       and s.is_active
     limit 1;
  end if;
  return new;
end;
$$;

drop trigger if exists complaint_categories_link_skill on public.complaint_categories;
create trigger complaint_categories_link_skill
  before insert or update of name on public.complaint_categories
  for each row execute function public.link_category_skill();

comment on function public.link_category_skill() is
  'Fills complaint_categories.skill_id by matching the category name against '
  'the skill catalogue. Without it every skill_id is null and the service '
  'person community search returns nothing for everyone. Never overwrites a '
  'skill_id an administrator set deliberately.';

-- Backfill anything 0019 already inserted, on the same rule.
update public.complaint_categories c
   set skill_id = s.id
  from public.skills s
 where c.skill_id is null
   and s.is_active
   and lower(btrim(s.name)) = lower(btrim(c.name));

-- ---------------------------------------------------------------------------
-- 6. The service provider
-- ---------------------------------------------------------------------------

create table if not exists public.service_providers (
  id                uuid primary key default gen_random_uuid(),
  profile_id        uuid not null unique references public.profiles(id)
                      on delete cascade,
  display_name      text not null check (length(btrim(display_name)) between 2 and 120),
  headline          text check (headline is null or length(btrim(headline)) <= 160),
  bio               text check (bio is null or length(btrim(bio)) <= 2000),
  phone_e164        varchar(20),
  latitude          numeric(9,6),
  longitude         numeric(9,6),
  location          extensions.geography(Point, 4326)
                      generated always as (
                        case
                          when latitude is null or longitude is null then null
                          else extensions.st_setsrid(
                                 extensions.st_makepoint(
                                   longitude::float8, latitude::float8),
                                 4326
                               )::extensions.geography
                        end
                      ) stored,
  service_radius_km numeric(6,2) not null default 15,
  status            text not null default 'active',
  -- The dashboard's offline toggle. False means "assign me nothing", and is
  -- read by the dispatch sweep in 0037. Distinct from status: a provider who
  -- has finished for the day is not a provider who has left the platform.
  is_available      boolean not null default true,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.service_providers'::regclass
       and conname  = 'service_providers_status_check'
  ) then
    alter table public.service_providers
      add constraint service_providers_status_check
      check (status in ('active', 'paused', 'suspended'));
  end if;
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.service_providers'::regclass
       and conname  = 'service_providers_radius_check'
  ) then
    alter table public.service_providers
      add constraint service_providers_radius_check
      check (service_radius_km between 1 and 500);
  end if;
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.service_providers'::regclass
       and conname  = 'service_providers_latitude_check'
  ) then
    alter table public.service_providers
      add constraint service_providers_latitude_check
      check (latitude is null or latitude between -90 and 90);
  end if;
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.service_providers'::regclass
       and conname  = 'service_providers_longitude_check'
  ) then
    alter table public.service_providers
      add constraint service_providers_longitude_check
      check (longitude is null or longitude between -180 and 180);
  end if;
end $$;

create index if not exists service_providers_location_gix
  on public.service_providers using gist (location);

drop trigger if exists service_providers_set_updated_at on public.service_providers;
create trigger service_providers_set_updated_at
  before update on public.service_providers
  for each row execute function public.set_updated_at();

comment on table public.service_providers is
  'A service person, independent of any community. Created by the holder of the '
  'profile, not by an administrator. Hired into communities by 0035.';

create table if not exists public.service_provider_skills (
  service_provider_id uuid not null references public.service_providers(id)
                        on delete cascade,
  skill_id            uuid not null references public.skills(id) on delete restrict,
  proficiency_level   smallint check (
                        proficiency_level is null
                        or proficiency_level between 1 and 5),
  created_at          timestamptz not null default now(),
  primary key (service_provider_id, skill_id)
);

create index if not exists service_provider_skills_skill_idx
  on public.service_provider_skills (skill_id);

-- ---------------------------------------------------------------------------
-- 7. Blacklisting
--
-- Modelled on blacklisted_residents (0001/0008) down to the reversible
-- revoked_at pair and the one-active-row partial index, and deliberately NOT
-- that table. It is keyed on (community_id, profile_id) and is enforced inside
-- search_joinable_communities, so reusing it would bar a person from *living*
-- in the community as a side effect of barring them from working in it. A
-- plumber a community will not hire has not been refused a flat.
-- ---------------------------------------------------------------------------

create table if not exists public.blacklisted_service_providers (
  id                       uuid primary key default gen_random_uuid(),
  community_id             uuid not null references public.communities(id)
                             on delete cascade,
  service_provider_id      uuid not null references public.service_providers(id)
                             on delete cascade,
  blacklisted_by_membership_id uuid not null
                             references public.community_memberships(id)
                             on delete restrict,
  reason                   text not null
                             check (length(btrim(reason)) between 3 and 500),
  created_at               timestamptz not null default now(),
  revoked_at               timestamptz,
  revoked_by_membership_id uuid references public.community_memberships(id)
                             on delete set null
);

create unique index if not exists blacklisted_providers_one_active
  on public.blacklisted_service_providers (community_id, service_provider_id)
  where revoked_at is null;

-- ---------------------------------------------------------------------------
-- 8. Reads
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
  'able to find someone they have never met.';

grant select on public.service_provider_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 9. Which communities need me
--
-- The dashboard's "find a community" field, and the answer to the three rules
-- stated in the requirement: the community has a department whose categories
-- match one of my skills, it has not blacklisted me, and the list is ordered by
-- how far away it is.
--
-- A function and not a view because it is written from the caller's own
-- provider row, and because paging a distance-ordered result wants LIMIT
-- pushed down rather than applied by PostgREST after the fact.
-- ---------------------------------------------------------------------------

create or replace function public.search_serviceable_communities(
  p_query     text default null,
  p_limit     integer default 20,
  p_offset    integer default 0
)
returns table (
  id                   uuid,
  name                 text,
  city                 text,
  state                text,
  community_type       text,
  distance_km          numeric,
  matching_skill_names text[],
  -- An array of {id, name}, NOT two parallel text[] columns. Two aggregates
  -- would not line up: array_agg(distinct ...) sorts by its own argument, so
  -- the ids would come back in uuid order and the names in alphabetical order,
  -- and row three of one would name row three of the other only by accident.
  -- The id is here because POST /worker/applications takes a departmentId, and
  -- without it this search is a screen with nothing to press.
  departments          jsonb
)
language sql
stable
security definer
set search_path = public
as $$
  with me as (
    select p.id, p.latitude, p.longitude, p.location
      from public.service_providers p
     where p.profile_id = auth.uid()
  )
  select
    c.id,
    c.name,
    c.city,
    c.state,
    c.community_type,
    case
      when c.location is null or me.location is null then null
      else round(
        (extensions.st_distance(c.location, me.location) / 1000)::numeric, 2)
    end as distance_km,
    array_agg(distinct s.name)  as matching_skill_names,
    jsonb_agg(distinct jsonb_build_object('id', d.id, 'name', d.name))
      as departments
  from me
  join public.communities c
    on c.status = 'active'
  join public.departments d
    on d.community_id = c.id
   and d.is_active
  join public.department_categories dc
    on dc.department_id = d.id
  join public.complaint_categories cc
    on cc.id = dc.category_id
   and cc.skill_id is not null
  join public.service_provider_skills sps
    on sps.skill_id = cc.skill_id
   and sps.service_provider_id = me.id
  join public.skills s
    on s.id = cc.skill_id
  where (p_query is null or c.name ilike '%' || btrim(p_query) || '%')
    and not exists (
      select 1 from public.blacklisted_service_providers b
       where b.community_id = c.id
         and b.service_provider_id = me.id
         and b.revoked_at is null
    )
    -- Already working here. Nothing to apply for.
    and not exists (
      select 1 from public.community_memberships m
       where m.community_id = c.id
         and m.profile_id = auth.uid()
         and m.status = 'active'
         and m.ended_at is null
    )
  group by c.id, c.name, c.city, c.state, c.community_type, distance_km
  order by distance_km nulls last, c.name
  limit greatest(1, least(coalesce(p_limit, 20), 100))
  offset greatest(0, coalesce(p_offset, 0));
$$;

comment on function public.search_serviceable_communities(text, integer, integer) is
  'Communities that have a department needing one of the calling service '
  'person''s skills, have not blacklisted them, and do not already employ them. '
  'Ordered by distance, nearest first; communities with no coordinates sort '
  'last rather than being hidden.';

grant execute on function
  public.search_serviceable_communities(text, integer, integer) to authenticated;

-- ---------------------------------------------------------------------------
-- 10. Writes
--
-- All three check auth.uid() themselves rather than relying on a policy: there
-- is no update policy on service_providers at all, matching 0031 where every
-- write is a definer function and the table carries read policies only.
-- ---------------------------------------------------------------------------

create or replace function public.upsert_service_provider(
  p_display_name      text,
  p_headline          text default null,
  p_bio               text default null,
  p_phone_e164        text default null,
  p_latitude          numeric default null,
  p_longitude         numeric default null,
  p_service_radius_km numeric default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  if auth.uid() is null then
    raise exception 'Sign in required.' using errcode = '42501';
  end if;
  if p_display_name is null or length(btrim(p_display_name)) < 2 then
    raise exception 'A name is required.' using errcode = '22004';
  end if;

  insert into public.service_providers as sp (
    profile_id, display_name, headline, bio, phone_e164,
    latitude, longitude, service_radius_km
  )
  values (
    auth.uid(), btrim(p_display_name), p_headline, p_bio, p_phone_e164,
    p_latitude, p_longitude, coalesce(p_service_radius_km, 15)
  )
  on conflict (profile_id) do update
     set display_name      = btrim(p_display_name),
         headline          = coalesce(p_headline, sp.headline),
         bio               = coalesce(p_bio, sp.bio),
         phone_e164        = coalesce(p_phone_e164, sp.phone_e164),
         latitude          = coalesce(p_latitude, sp.latitude),
         longitude         = coalesce(p_longitude, sp.longitude),
         service_radius_km = coalesce(p_service_radius_km, sp.service_radius_km)
  returning sp.id into v_id;

  return v_id;
end;
$$;

create or replace function public.set_service_provider_skills(
  p_skill_ids uuid[]
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_provider uuid;
  v_count    integer;
begin
  select id into v_provider
    from public.service_providers
   where profile_id = auth.uid();
  if v_provider is null then
    raise exception 'No service provider profile.' using errcode = 'P0002';
  end if;

  delete from public.service_provider_skills
   where service_provider_id = v_provider
     and skill_id <> all (coalesce(p_skill_ids, array[]::uuid[]));

  insert into public.service_provider_skills (service_provider_id, skill_id)
  select v_provider, s.id
    from public.skills s
   where s.id = any (coalesce(p_skill_ids, array[]::uuid[]))
     and s.is_active
  on conflict do nothing;

  select count(*) into v_count
    from public.service_provider_skills
   where service_provider_id = v_provider;
  return v_count;
end;
$$;

create or replace function public.set_service_provider_availability(
  p_is_available boolean
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_updated boolean;
begin
  update public.service_providers
     set is_available = coalesce(p_is_available, true)
   where profile_id = auth.uid()
  returning is_available into v_updated;

  if v_updated is null then
    raise exception 'No service provider profile.' using errcode = 'P0002';
  end if;
  return v_updated;
end;
$$;

comment on function public.set_service_provider_availability(boolean) is
  'The dashboard offline toggle. Turning it off stops the dispatch sweep in '
  '0037 offering new work; it does not cancel work already accepted.';

grant execute on function public.upsert_service_provider(
  text, text, text, text, numeric, numeric, numeric) to authenticated;
grant execute on function
  public.set_service_provider_skills(uuid[]) to authenticated;
grant execute on function
  public.set_service_provider_availability(boolean) to authenticated;

-- ---------------------------------------------------------------------------
-- 11. Row security
-- ---------------------------------------------------------------------------

alter table public.service_providers            enable row level security;
alter table public.service_provider_skills      enable row level security;
alter table public.blacklisted_service_providers enable row level security;

drop policy if exists service_providers_read on public.service_providers;
create policy service_providers_read on public.service_providers
  for select using (auth.uid() is not null);

drop policy if exists service_provider_skills_read on public.service_provider_skills;
create policy service_provider_skills_read on public.service_provider_skills
  for select using (auth.uid() is not null);

-- No policy on blacklisted_service_providers. It is read by definer functions
-- only, and a provider learning which communities have barred them -- and on
-- what stated reason -- is a disclosure nobody has asked for. Matches the
-- posture of blacklisted_residents, which likewise enables RLS with no policy.

grant select on public.service_providers       to authenticated;
grant select on public.service_provider_skills to authenticated;
grant select on public.skills                  to authenticated;
