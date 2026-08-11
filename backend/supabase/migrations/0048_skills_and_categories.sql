-- 0048_skills_and_categories.sql
--
-- Skills become something an administrator can hold in their hands.
--
-- Everything below follows from one instruction: a master catalogue of skills
-- that can be added to, and departments that hold skills explicitly. Three
-- clauses of it are worth writing down because each rules out a design that
-- would otherwise look reasonable.
--
--   "a master table of skills"        -- skills stay GLOBAL. `skills` has never
--     had a community_id and `name` has been globally unique since the
--     baseline; 0034 39-48 argues the case. Nothing here changes that, and the
--     reason is worth repeating: a per-community catalogue is several
--     vocabularies for one trade, so a plumber registering in two societies
--     has to claim "Plumbing" twice and the hiring search matches neither.
--
--   "department does not inherit any by default"  -- department_skills starts
--     empty for every department, including existing ones. There is no
--     backfill in this file. The category->skill chain 0034 built is NOT a
--     source of default skills: it answers a different question (which trade
--     handles this kind of complaint) and inheriting from it would silently
--     give every department skills nobody chose.
--
--   "if the word is not a direct match ... an add skill button"  -- the button
--     is ONE call, add_department_skill, not create-then-attach from the
--     client. Two calls can half-fail: a skill created and not attached is
--     catalogue litter nobody asked for, and it is the failure mode that
--     happens on a phone at the end of a form.
--
-- WHAT THIS FILE FIXES ON ITS WAY PAST
--
-- 0035's own header says: "leave department_overview matching on 'head' and the
-- admin screen's head field is permanently null. So the function and the view
-- are replaced here too." The function was replaced. THE VIEW WAS NOT. 0035
-- migrated every `rank = 'head'` row to 'manager' and forbade 'head' in the
-- check constraint, so the head lateral in 0019 364 has matched nothing since,
-- and `head_name`/`head_staff_id` have been null for every department in the
-- API. Section 1 replaces the view for the skills columns anyway, so the
-- predicate is corrected in the same breath. It is a one-word fix that has been
-- sitting behind a comment claiming it was already made.
--
-- WHAT THIS FILE CHANGES ABOUT HIRING, DELIBERATELY
--
-- search_hireable_service_providers (0035 509) derives the skills a department
-- needs from its categories alone. Section 5 changes that to the UNION of the
-- category-derived skills and the department's own. Without it, attaching a
-- skill to a department would change nothing anybody can observe -- the whole
-- point of attaching one is that it changes who can be hired for it. This is a
-- behaviour change to a shipped function and is recorded as such in the change
-- log rather than slipped in.
--
-- No table is dropped, no column is removed, and every function here is
-- additive except the two replacements named above.

-- ---------------------------------------------------------------------------
-- 1. department_skills
--
-- `on delete restrict` on skill_id, matching service_provider_skills (0034
-- 345): a skill somebody holds is retired with is_active = false, never
-- deleted, so a department that has needed "Air Conditioning" for two years
-- keeps the row that says so. `on delete cascade` on department_id, because a
-- deleted department's skill list is not information about anything.
-- ---------------------------------------------------------------------------

create table if not exists public.department_skills (
  department_id uuid not null
    references public.departments(id) on delete cascade,
  skill_id      uuid not null
    references public.skills(id) on delete restrict,
  created_at    timestamptz not null default now(),
  primary key (department_id, skill_id)
);

create index if not exists department_skills_skill_idx
  on public.department_skills (skill_id);

comment on table public.department_skills is
  'Skills a department needs, chosen explicitly by an administrator or its '
  'manager. Empty by default -- a department inherits nothing from its '
  'categories.';

-- The trigram index the suggestion box rides on. Partial on is_active for the
-- same reason GET /skills filters on it: a retired trade must not be offered
-- as a suggestion, and an index that holds it would rank it.
create index if not exists skills_name_trgm
  on public.skills using gin (lower(name) extensions.gin_trgm_ops)
  where is_active;

alter table public.department_skills enable row level security;

drop policy if exists department_skills_read on public.department_skills;
create policy department_skills_read on public.department_skills
  for select to authenticated
  using (exists (
    select 1 from public.departments d
     where d.id = department_id
       and public.is_community_member(d.community_id)
  ));

-- No write policy, deliberately: the 0031 posture. Every write below is a
-- SECURITY DEFINER function that checks can_manage_department first, so there
-- is no path from the API process to a row these functions did not write.

grant select on public.department_skills to authenticated;

-- ---------------------------------------------------------------------------
-- 2. department_overview, replaced
--
-- Two changes: `rank = 'manager'` (see the header), and the two skill arrays.
--
-- The arrays are on the view rather than fetched separately because the
-- department list renders them per card, and a per-card round trip is the shape
-- that turns a list of twelve departments into thirteen requests.
-- ---------------------------------------------------------------------------

drop view if exists public.department_overview;
create view public.department_overview
with (security_invoker = true) as
select
  d.id,
  d.community_id,
  d.name,
  d.description,
  d.contact_email,
  d.contact_phone_e164,
  d.opens_at,
  d.closes_at,
  d.sla_hours,
  d.kind,
  d.status,
  d.created_at,
  d.updated_at,
  head.display_name                              as head_name,
  head.id                                        as head_staff_id,
  coalesce(st.staff_count, 0)                    as staff_count,
  coalesce(cx.active_complaint_count, 0)         as active_complaint_count,
  coalesce(cx.resolved_complaint_count, 0)       as resolved_complaint_count,
  coalesce(cx.overdue_complaint_count, 0)        as overdue_complaint_count,
  coalesce(cat.category_ids, '{}'::uuid[])       as category_ids,
  coalesce(cat.category_names, '{}'::text[])     as category_names,
  coalesce(sk.skill_ids, '{}'::uuid[])           as skill_ids,
  coalesce(sk.skill_names, '{}'::text[])         as skill_names,
  lower(concat_ws(' ',
    d.name,
    d.description,
    d.contact_email,
    head.display_name,
    array_to_string(coalesce(cat.category_names, '{}'::text[]), ' '),
    array_to_string(coalesce(sk.skill_names, '{}'::text[]), ' '),
    st.staff_names
  ))                                             as search_text
from public.departments d
left join lateral (
  -- 'manager' since 0035. This read said 'head' until 0048 and matched nothing.
  select s.id, s.display_name
    from public.staff_assignments s
   where s.department_id = d.id
     and s.rank = 'manager'
     and s.status = 'active'
   limit 1
) head on true
left join lateral (
  select count(*) as staff_count,
         string_agg(s.display_name, ' ') as staff_names
    from public.staff_assignments s
   where s.department_id = d.id
     and s.status = 'active'
) st on true
left join lateral (
  select
    count(*) filter (
      where c.status in ('open', 'acknowledged', 'in_progress')
    ) as active_complaint_count,
    count(*) filter (
      where c.status in ('resolved', 'closed')
    ) as resolved_complaint_count,
    count(*) filter (
      where c.status in ('open', 'acknowledged', 'in_progress')
        and c.due_at is not null
        and c.due_at < now()
    ) as overdue_complaint_count
    from public.complaints c
   where c.department_id = d.id
) cx on true
left join lateral (
  select array_agg(cc.id   order by cc.name) as category_ids,
         array_agg(cc.name order by cc.name) as category_names
    from public.department_categories dc
    join public.complaint_categories cc on cc.id = dc.category_id
   where dc.department_id = d.id
) cat on true
left join lateral (
  select array_agg(s.id   order by s.name) as skill_ids,
         array_agg(s.name order by s.name) as skill_names
    from public.department_skills ds
    join public.skills s on s.id = ds.skill_id
   where ds.department_id = d.id
     and s.is_active
) sk on true;

comment on view public.department_overview is
  'Departments with staff, category, skill and complaint counts. Runs as the '
  'caller (security_invoker), so RLS applies.';

grant select on public.department_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 3. Reads
-- ---------------------------------------------------------------------------

-- The suggestion box behind "text box which gets autofilled with suggestions
-- based on closest match".
--
-- `set search_path = public, extensions` and a bare similarity() call, the same
-- shape 0008 25 uses for the community search -- pg_trgm lives in `extensions`
-- and the operators have to be resolvable for the GIN index to be used.
--
-- Prefix matches sort ahead of merely-similar ones, because somebody typing
-- "plum" means Plumbing and not Plumbing's trigram neighbours. `is_exact` is
-- returned rather than computed on the client so that one rule -- when to offer
-- the "add" button -- lives in one place. Note it is case- and
-- whitespace-insensitive: typing "  plumbing " must NOT offer to create a
-- second Plumbing.
--
-- No authorization beyond being signed in: the catalogue is global, carries no
-- community's data, and is already readable in full through GET /skills.
create or replace function public.search_skills(
  p_query text default null,
  p_limit integer default 10
)
returns table (
  id          uuid,
  name        text,
  category    text,
  description text,
  is_exact    boolean,
  score       real
)
language sql
stable
security definer
set search_path = public, extensions
as $$
  select
    s.id,
    s.name,
    s.category,
    s.description,
    lower(btrim(s.name)) = lower(btrim(coalesce(p_query, ''))) as is_exact,
    case
      when p_query is null or btrim(p_query) = '' then 0::real
      else similarity(lower(s.name), lower(btrim(p_query)))
    end as score
  from public.skills s
 where s.is_active
   and (
     p_query is null
     or btrim(p_query) = ''
     or lower(s.name) like lower(btrim(p_query)) || '%'
     or similarity(lower(s.name), lower(btrim(p_query))) > 0.15
   )
 order by
   lower(btrim(s.name)) = lower(btrim(coalesce(p_query, ''))) desc,
   case
     when p_query is null or btrim(p_query) = '' then 1
     when lower(s.name) like lower(btrim(p_query)) || '%' then 0
     else 1
   end,
   case
     when p_query is null or btrim(p_query) = '' then 0::real
     else similarity(lower(s.name), lower(btrim(p_query)))
   end desc,
   s.name
 limit greatest(1, least(coalesce(p_limit, 10), 50));
$$;

comment on function public.search_skills(text, integer) is
  'Closest-match skill suggestions for the department form. Exact match first, '
  'then prefix, then trigram similarity. is_exact is returned so that the rule '
  'for offering "add this as a new skill" lives in one place.';

grant execute on function public.search_skills(text, integer) to authenticated;

-- A community's complaint categories, with the trade each one resolves to.
--
-- `skill_name` being null is the case this function exists to make visible.
-- 0034 204-206 accepted that a category matching no trade is not an error, and
-- that is still true -- but it has been INVISIBLE, and an invisible one is a
-- category whose complaints no hiring search will ever match, with nothing
-- anywhere saying so. The admin screen can now show it.
create or replace function public.community_categories(p_membership_id uuid)
returns table (
  id           uuid,
  name         text,
  skill_id     uuid,
  skill_name   text,
  department_count integer
)
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_community uuid;
begin
  select m.community_id into v_community
    from public.community_memberships m
   where m.id = p_membership_id
     and m.profile_id = auth.uid()
     and m.status = 'active'
     and m.ended_at is null
   limit 1;

  if v_community is null then
    raise exception 'You are not a member of this community.'
      using errcode = 'HB403';
  end if;

  return query
    select
      cc.id,
      cc.name,
      cc.skill_id,
      s.name,
      (select count(*)::integer
         from public.department_categories dc
        where dc.category_id = cc.id) as department_count
      from public.complaint_categories cc
      left join public.skills s on s.id = cc.skill_id and s.is_active
     where cc.community_id = v_community
     order by lower(cc.name);
end;
$$;

comment on function public.community_categories(uuid) is
  'Every complaint category this community has, with the trade it resolves to '
  'and how many departments claim it. A null skill_name is the case worth '
  'showing: those categories match nobody in any hiring search.';

grant execute on function public.community_categories(uuid) to authenticated;

-- The department's own skills, for the screen that edits them.
create or replace function public.department_skill_list(p_department_id uuid)
returns table (
  id          uuid,
  name        text,
  category    text,
  description text,
  created_at  timestamptz
)
language plpgsql
stable
security definer
set search_path = public
as $$
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  return query
    select s.id, s.name, s.category, s.description, ds.created_at
      from public.department_skills ds
      join public.skills s on s.id = ds.skill_id
     where ds.department_id = p_department_id
       and s.is_active
     order by lower(s.name);
end;
$$;

comment on function public.department_skill_list(uuid) is
  'Skills attached to one department. Manager or admin of that department '
  'only.';

grant execute on function public.department_skill_list(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 4. Writes
--
-- Same posture as 0035 7: every one is SECURITY DEFINER and asks its own
-- authorization question about THIS department, never "is the caller an admin
-- somewhere" -- otherwise a manager of one community could edit another's
-- skills by putting its id in a request body.
-- ---------------------------------------------------------------------------

-- May the caller write to the global catalogue at all?
--
-- Admins and managers, and the bar is deliberately no higher. A skill is a
-- word, the catalogue is deduplicated case-insensitively, and retiring a
-- mistake is `is_active = false`. Setting the bar at admin-only would mean a
-- plumbing manager who needs "Lift Maintenance" has to file a ticket to type a
-- word, which is how a catalogue ends up with everything filed under Others.
create or replace function public.can_author_skills()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
      from public.community_memberships m
     where m.profile_id = auth.uid()
       and m.status = 'active'
       and m.ended_at is null
       and m.role in ('admin', 'manager')
  );
$$;

comment on function public.can_author_skills() is
  'True when the caller may add to the global skill catalogue: any active '
  'admin or manager membership.';

grant execute on function public.can_author_skills() to authenticated;

-- Create a skill, or return the one that already answers to that name.
--
-- NOT an upsert on the unique index, because the index is on `name` exactly and
-- the question being asked is case- and whitespace-insensitive. `INSERT ... ON
-- CONFLICT` would happily create "plumbing" beside "Plumbing", which is the one
-- outcome the whole suggestion box exists to prevent.
--
-- `created` is returned so the API can answer 201 or 200 honestly rather than
-- claiming to have created a row it found.
create or replace function public.create_skill(
  p_name        text,
  p_category    text default null,
  p_description text default null
)
returns table (
  id          uuid,
  name        text,
  category    text,
  description text,
  created     boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_name text := btrim(coalesce(p_name, ''));
  v_row  public.skills%rowtype;
begin
  if not public.can_author_skills() then
    raise exception 'You may not add to the skill catalogue.'
      using errcode = 'HB403';
  end if;

  if v_name = '' or length(v_name) > 80 then
    raise exception 'A skill name of 1 to 80 characters is required.'
      using errcode = 'HB422';
  end if;

  select * into v_row
    from public.skills s
   where lower(btrim(s.name)) = lower(v_name)
   limit 1;

  if found then
    -- A retired trade being asked for again is a request to bring it back, not
    -- a request for a duplicate under a different capitalisation.
    if not v_row.is_active then
      update public.skills set is_active = true
       where public.skills.id = v_row.id
      returning * into v_row;
    end if;
    return query select v_row.id, v_row.name, v_row.category, v_row.description,
                        false;
    return;
  end if;

  -- `category` and `description` are NOT NULL on the wire (Skill in
  -- service_provider_schemas.py) even though the columns are nullable, and the
  -- worker's registration screen groups its chip grid by category. A created
  -- skill with a null category would 500 GET /skills for every service person,
  -- so the defaults are filled here rather than at the edge: 'other' earns a
  -- visible group in that grid, which is honest -- nobody classified it.
  insert into public.skills (name, category, description)
  values (v_name,
          coalesce(nullif(btrim(coalesce(p_category, '')), ''), 'other'),
          coalesce(nullif(btrim(coalesce(p_description, '')), ''), ''))
  returning * into v_row;

  return query select v_row.id, v_row.name, v_row.category, v_row.description,
                      true;
end;
$$;

comment on function public.create_skill(text, text, text) is
  'Add a trade to the global catalogue, or return the existing one whose name '
  'matches case-insensitively. Reactivates a retired trade rather than '
  'duplicating it. Admins and managers only.';

grant execute on function public.create_skill(text, text, text) to authenticated;

-- The "Add skill" button: create if needed, attach, one transaction.
create or replace function public.add_department_skill(
  p_department_id uuid,
  p_name          text
)
returns table (
  id          uuid,
  name        text,
  category    text,
  description text,
  created     boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_skill record;
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  -- create_skill raises HB403/HB422 itself, and returns exactly one row.
  select c.id, c.name, c.category, c.description, c.created
    into v_skill
    from public.create_skill(p_name) c;

  insert into public.department_skills (department_id, skill_id)
  values (p_department_id, v_skill.id)
  on conflict do nothing;

  return query select v_skill.id, v_skill.name, v_skill.category,
                      v_skill.description, v_skill.created;
end;
$$;

comment on function public.add_department_skill(uuid, text) is
  'Attach a skill to a department by name, creating it in the global catalogue '
  'first if no case-insensitive match exists. One call, because a skill created '
  'and not attached is catalogue litter nobody asked for.';

grant execute on function public.add_department_skill(uuid, text) to authenticated;

-- Detach. Never deletes the skill: it is global, and another department almost
-- certainly needs it.
create or replace function public.remove_department_skill(
  p_department_id uuid,
  p_skill_id      uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  delete from public.department_skills
   where department_id = p_department_id
     and skill_id = p_skill_id;
end;
$$;

comment on function public.remove_department_skill(uuid, uuid) is
  'Detach a skill from a department. The skill itself is global and survives.';

grant execute on function public.remove_department_skill(uuid, uuid)
  to authenticated;

-- Replace the whole set, for the department form's save.
--
-- Every id is checked to be a real active skill before anything is deleted, so
-- a request carrying one bad id does not empty the list and then fail.
create or replace function public.set_department_skills(
  p_department_id uuid,
  p_skill_ids     uuid[]
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_ids uuid[] := coalesce(p_skill_ids, '{}'::uuid[]);
  v_bad uuid;
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  select x into v_bad
    from unnest(v_ids) as x
   where not exists (
     select 1 from public.skills s where s.id = x and s.is_active
   )
   limit 1;

  if v_bad is not null then
    raise exception 'No active skill with id %.', v_bad using errcode = 'HB422';
  end if;

  delete from public.department_skills
   where department_id = p_department_id
     and not (skill_id = any(v_ids));

  insert into public.department_skills (department_id, skill_id)
  select p_department_id, unnest(v_ids)
  on conflict do nothing;
end;
$$;

comment on function public.set_department_skills(uuid, uuid[]) is
  'Make a department''s skill set exactly the supplied ids. Validates every id '
  'before deleting anything, so one bad id cannot empty the list.';

grant execute on function public.set_department_skills(uuid, uuid[])
  to authenticated;

-- ---------------------------------------------------------------------------
-- 5. Hiring reads the department's own skills too
--
-- The only change from 0035 509 is the `needed` CTE, which was:
--
--     select distinct cc.skill_id
--       from dept
--       join public.department_categories dc on dc.department_id = dept.id
--       join public.complaint_categories cc  on cc.id = dc.category_id
--      where cc.skill_id is not null
--
-- and is now the union of that with department_skills. Everything else --
-- the HB403 guard, the distance sort, the four exclusion rules, the grouping --
-- is carried over unchanged and deliberately not "improved" in passing, so the
-- diff against 0035 is one CTE.
--
-- UNION, not replacement of the category path: a department that has picked no
-- skills yet must keep hiring exactly as it did yesterday. This file adds a
-- second way to say what a department needs; it does not withdraw the first.
-- ---------------------------------------------------------------------------

create or replace function public.search_hireable_service_providers(
  p_department_id uuid,
  p_query         text default null,
  p_limit         integer default 20,
  p_offset        integer default 0
)
returns table (
  id                   uuid,
  display_name         text,
  headline             text,
  phone_e164           varchar(20),
  status               text,
  is_available         boolean,
  service_radius_km    numeric,
  distance_km          numeric,
  matching_skill_names text[],
  skill_names          text[],
  community_count      integer,
  has_open_application boolean
)
language plpgsql
stable
security definer
set search_path = public
as $$
#variable_conflict use_column
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  return query
  with dept as (
    select d.id, d.community_id, c.location
      from public.departments d
      join public.communities c on c.id = d.community_id
     where d.id = p_department_id
  ),
  needed as (
    select distinct cc.skill_id
      from dept
      join public.department_categories dc on dc.department_id = dept.id
      join public.complaint_categories cc  on cc.id = dc.category_id
     where cc.skill_id is not null
    union
    select distinct ds.skill_id
      from dept
      join public.department_skills ds on ds.department_id = dept.id
  )
  select
    p.id,
    p.display_name,
    p.headline,
    p.phone_e164,
    p.status,
    p.is_available,
    p.service_radius_km,
    case
      when p.location is null or dept.location is null then null
      else round(
        (extensions.st_distance(dept.location, p.location) / 1000)::numeric, 2)
    end as distance_km,
    array_agg(distinct ms.name)                       as matching_skill_names,
    coalesce(
      (select array_agg(s2.name order by s2.name)
         from public.service_provider_skills x
         join public.skills s2 on s2.id = x.skill_id
        where x.service_provider_id = p.id and s2.is_active),
      '{}'::text[])                                   as skill_names,
    (select count(*)::integer
       from public.community_memberships m
      where m.profile_id = p.profile_id
        and m.role in ('worker', 'security')
        and m.status = 'active'
        and m.ended_at is null)                       as community_count,
    exists (
      select 1 from public.service_applications a
       where a.department_id = dept.id
         and a.service_provider_id = p.id
         and a.status = 'pending')                    as has_open_application
  from dept
  join public.service_provider_skills sps on sps.skill_id in (select skill_id from needed)
  join public.service_providers p         on p.id = sps.service_provider_id
  join public.skills ms                   on ms.id = sps.skill_id and ms.is_active
  where p.status = 'active'
    and (p_query is null or p.display_name ilike '%' || btrim(p_query) || '%')
    and not exists (
      select 1 from public.blacklisted_service_providers b
       where b.community_id = dept.community_id
         and b.service_provider_id = p.id
         and b.revoked_at is null
    )
    and not exists (
      select 1 from public.staff_assignments sa
       where sa.department_id = dept.id
         and sa.service_provider_id = p.id
         and sa.status = 'active'
    )
    and not exists (
      select 1 from public.community_memberships m
       where m.community_id = dept.community_id
         and m.profile_id = p.profile_id
         and m.status = 'active'
         and m.ended_at is null
    )
  group by
    p.id, p.display_name, p.headline, p.phone_e164, p.status, p.is_available,
    p.service_radius_km, p.profile_id, distance_km, dept.id
  order by distance_km nulls last, p.display_name
  limit greatest(1, least(coalesce(p_limit, 20), 100))
  offset greatest(0, coalesce(p_offset, 0));
end;
$$;

comment on function public.search_hireable_service_providers(
  uuid, text, integer, integer) is
  'Service people this department could hire: holding a skill the department '
  'claims directly or one of its categories needs, not blacklisted, not '
  'already on its roster, and not already a member of the community. Nearest '
  'first.';

grant execute on function public.search_hireable_service_providers(
  uuid, text, integer, integer) to authenticated;
