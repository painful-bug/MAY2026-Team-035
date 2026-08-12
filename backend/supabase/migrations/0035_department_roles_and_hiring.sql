-- How a service person becomes a member of a community.
--
-- 0034 created someone who exists independently of every community. This file
-- is the door: a provider applies, or a manager invites, and accepting turns
-- one row into three -- a membership, a roster entry, and a decided application
-- -- in one transaction. Either all three exist or none of them do. A person on
-- a roster with no account, or an account with no roster row, is the failure
-- mode this whole file is arranged to prevent, and it is why hiring is an RPC
-- rather than three PostgREST calls the repository makes in a row.
--
-- THREE RANKS, AND THE FOUR THINGS THAT SAY `head`
--
-- Four vocabularies disagreed about what a staff rank is: this schema said
-- head|member, API.md 8 said member|supervisor|head, the ERD said
-- manager|supervisor|worker, and three frontend screens carried three more
-- lists. This file settles on manager|supervisor|member -- the ERD's, minus the
-- part that duplicates departments.kind.
--
-- Relaxing the CHECK is not, on its own, the change. 0019 has four other
-- references to the word `head`, and the one that matters is
-- apply_department_head, which is the ONLY function in this schema that ever
-- sets a rank. Leave it writing 'head' against a check that no longer allows it
-- and every department update raises 23514; leave department_overview matching
-- on 'head' and the admin screen's head field is permanently null. So the
-- function and the view are replaced here too, and a one-time UPDATE carries
-- any existing rows across.
--
-- `head` REMAINS THE WIRE WORD. departments.js, department_schemas.py and
-- API.md 8 all call the person who runs a department the head, and renaming
-- that would break the admin screen to no purpose. `head` is what the API says
-- and `manager` is what the column stores, which is the same seam
-- app/domain/vocabularies.py already holds for statuses and comment visibility.
--
-- TWO CHECK CONSTRAINTS THAT ARE LIVE FAILURES, NOT TIDY-UPS
--
-- departments_kind_check allows internal|vendor|hybrid. Nothing writes those:
-- departments_service._VALID_KINDS is ("service", "security"), and so is
-- API.md. The two sets do not intersect, so every department create or update
-- that names a kind is a 23514 today. It is corrected here rather than in a
-- later cleanup because this file needs `kind` to be true: it is what decides
-- whether an accepted application issues a `worker` membership or a `security`
-- one.
--
-- staff_assignments_shift_check has the same shape of bug with a smaller blast
-- radius: it allows Morning|Evening|Night|Full Day while Python validates
-- Day|Evening|Night. Three of the five words fail on one side or the other. The
-- corrected set is the union of what the code and the two frontend screens
-- offer, minus Morning, which only this constraint ever mentioned.
--
-- Both are constraint edits and nothing more, because no migration in this
-- directory has ever been applied to any database -- see the README. That will
-- not be true a second time.
--
-- WHY AN APPLICATION IS ONE TABLE WITH A DIRECTION
--
-- An application and an invitation are the same negotiation started from
-- opposite ends: someone proposes, the other side decides, and acceptance does
-- exactly the same three writes either way. Two tables would mean two inboxes,
-- two decide functions and two chances for the hire to be half-done in one of
-- them. `direction` records who started it, which is the only thing that
-- actually differs -- and it decides who is allowed to answer.
--
-- WHY A PROVIDER WHO IS ALREADY A MEMBER IS REFUSED
--
-- community_memberships is unique on (community_id, profile_id) among live
-- rows, so a resident of a community cannot also hold a worker membership in
-- it. That is not a limitation this file invents: 0034's
-- search_serviceable_communities already excludes communities the caller
-- belongs to, so such a community never appears in the search. The RPC raises
-- HB409 rather than letting a unique violation surface, because "you already
-- belong to this community" is an answer a person can act on and
-- 23505 is not.
--
-- WHY THE CANDIDATE SEARCH IS A FUNCTION AND NOT A VIEW
--
-- A manager's candidate list is skill-matched against ONE department's
-- categories, and a view cannot take a parameter. The alternative -- a view
-- crossing every department with every provider and filtering afterwards -- is
-- a cartesian product of two growing tables to answer a question about one row.
-- 0034's search_serviceable_communities is the same shape from the other side,
-- so this is the pattern already in the codebase rather than a new one.

-- ---------------------------------------------------------------------------
-- 1. Three ranks
-- ---------------------------------------------------------------------------

-- Drop, correct, re-add -- and in that order, which is not incidental. The old
-- CHECK allows ('head', 'member'), so an UPDATE writing 'manager' while it is
-- still in place raises 23514 and takes the whole migration with it. The
-- correction is a no-op on an empty database (nothing here has ever been
-- applied) and the difference between a clean apply and a failed one if 0019
-- ran first.
do $$
begin
  if exists (
    select 1 from pg_constraint
     where conrelid = 'public.staff_assignments'::regclass
       and conname  = 'staff_assignments_rank_check'
  ) then
    alter table public.staff_assignments
      drop constraint staff_assignments_rank_check;
  end if;

  update public.staff_assignments set rank = 'manager' where rank = 'head';

  alter table public.staff_assignments
    add constraint staff_assignments_rank_check
    check (rank in ('manager', 'supervisor', 'member'));
end $$;

-- At most one active manager per department. Partial, so deactivating one frees
-- the slot immediately (0019 A7). Replaces staff_assignments_one_active_head.
drop index if exists public.staff_assignments_one_active_head;

create unique index if not exists staff_assignments_one_active_manager
  on public.staff_assignments (department_id)
  where rank = 'manager' and status = 'active';

-- The only function in this schema that sets a rank. Rewritten for the new
-- vocabulary; the demotion still runs as a separate statement first, because
-- the partial unique index would otherwise be violated mid-statement by a
-- single UPDATE touching both rows.
create or replace function public.apply_department_head(
  p_department_id uuid,
  p_head_name     text
)
returns void
language plpgsql
as $$
declare
  v_name text := btrim(coalesce(p_head_name, ''));
  v_id   uuid;
begin
  update public.staff_assignments
     set rank = 'member'
   where department_id = p_department_id
     and rank = 'manager';

  if v_name = '' then
    return;
  end if;

  select id into v_id
    from public.staff_assignments
   where department_id = p_department_id
     and status = 'active'
     and lower(btrim(display_name)) = lower(v_name)
   limit 1;

  if v_id is not null then
    update public.staff_assignments set rank = 'manager' where id = v_id;
  end if;
end $$;

revoke all on function public.apply_department_head(uuid, text)
  from public, anon, authenticated;

comment on function public.apply_department_head(uuid, text) is
  'Promote one roster row to manager, demoting the incumbent. `head` is the '
  'wire word for this person; `manager` is the stored rank.';

-- ---------------------------------------------------------------------------
-- 2. Two vocabularies that were failing
--
-- See the header. Both are the same defect -- Python and Postgres validating
-- disjoint sets of words for one column.
-- ---------------------------------------------------------------------------

do $$
begin
  if exists (
    select 1 from pg_constraint
     where conrelid = 'public.departments'::regclass
       and conname  = 'departments_kind_check'
  ) then
    alter table public.departments drop constraint departments_kind_check;
  end if;

  alter table public.departments
    add constraint departments_kind_check
    check (kind is null or kind in ('service', 'security'));

  if exists (
    select 1 from pg_constraint
     where conrelid = 'public.staff_assignments'::regclass
       and conname  = 'staff_assignments_shift_check'
  ) then
    alter table public.staff_assignments
      drop constraint staff_assignments_shift_check;
  end if;

  alter table public.staff_assignments
    add constraint staff_assignments_shift_check
    check (
      shift is null
      or shift in ('Day', 'Evening', 'Night', 'Full Day', 'Rotating')
    );
end $$;

comment on column public.departments.kind is
  'service | security. Decides which membership role an accepted application '
  'issues: a security department hires `security`, everything else hires `worker`.';

-- ---------------------------------------------------------------------------
-- 3. A roster row may now point at a registered person
--
-- Three populations share this table after this file, and which columns are
-- null is what tells them apart:
--
--   membership_id null, service_provider_id null  -- a name typed into the
--     departments form, which is what 0019 was built for
--   membership_id set,  service_provider_id set   -- a service person hired
--     through this file
--   membership_id set,  service_provider_id null  -- an existing member given a
--     department role by an admin
-- ---------------------------------------------------------------------------

alter table public.staff_assignments
  add column if not exists service_provider_id uuid
    references public.service_providers(id) on delete set null;

create index if not exists staff_assignments_service_provider_idx
  on public.staff_assignments (service_provider_id)
  where service_provider_id is not null;

-- One live roster row per provider per department. A provider removed and
-- rehired gets a second row, which is what keeps the first one's history
-- readable.
create unique index if not exists staff_assignments_one_active_provider
  on public.staff_assignments (department_id, service_provider_id)
  where service_provider_id is not null and status = 'active';

-- ---------------------------------------------------------------------------
-- 4. The negotiation
-- ---------------------------------------------------------------------------

create table if not exists public.service_applications (
  id                     uuid primary key default gen_random_uuid(),
  community_id           uuid not null references public.communities(id)
                           on delete cascade,
  department_id          uuid not null references public.departments(id)
                           on delete cascade,
  service_provider_id    uuid not null references public.service_providers(id)
                           on delete cascade,
  -- Who started it, which is also who is NOT allowed to decide it.
  direction              text not null,
  status                 text not null default 'pending',
  message                text,
  -- The terms the hiring side is offering, decided when the manager accepts an
  -- application or extends an invitation. Null until then.
  rank                   text,
  job_title              text,
  shift                  text,
  created_by_membership_id uuid references public.community_memberships(id)
                           on delete set null,
  decided_by_membership_id uuid references public.community_memberships(id)
                           on delete set null,
  decided_at             timestamptz,
  decision_note          text,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.service_applications'::regclass
       and conname  = 'service_applications_direction_check'
  ) then
    alter table public.service_applications
      add constraint service_applications_direction_check
      check (direction in ('applied', 'invited'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.service_applications'::regclass
       and conname  = 'service_applications_status_check'
  ) then
    alter table public.service_applications
      add constraint service_applications_status_check
      check (status in (
        'pending', 'accepted', 'rejected', 'withdrawn', 'expired'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.service_applications'::regclass
       and conname  = 'service_applications_rank_check'
  ) then
    alter table public.service_applications
      add constraint service_applications_rank_check
      check (rank is null or rank in ('manager', 'supervisor', 'member'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.service_applications'::regclass
       and conname  = 'service_applications_message_check'
  ) then
    alter table public.service_applications
      add constraint service_applications_message_check
      check (message is null or length(btrim(message)) <= 2000);
  end if;

  -- The department and the row must agree on the community, so a cross-tenant
  -- application is unrepresentable rather than merely forbidden. Same shape as
  -- staff_assignments_department_tenant_fkey (0019).
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.service_applications'::regclass
       and conname  = 'service_applications_department_tenant_fkey'
  ) then
    alter table public.service_applications
      add constraint service_applications_department_tenant_fkey
      foreign key (department_id, community_id)
      references public.departments (id, community_id)
      on delete cascade;
  end if;
end $$;

-- One open negotiation per pair. Partial, so a rejected application can be
-- followed by a fresh one -- which is the difference between removal and
-- blacklisting that section 7 turns on.
create unique index if not exists service_applications_one_open
  on public.service_applications (department_id, service_provider_id)
  where status = 'pending';

create index if not exists service_applications_department_idx
  on public.service_applications (department_id, status, created_at desc);

create index if not exists service_applications_provider_idx
  on public.service_applications (service_provider_id, status, created_at desc);

drop trigger if exists service_applications_set_updated_at
  on public.service_applications;
create trigger service_applications_set_updated_at
  before update on public.service_applications
  for each row execute function public.set_updated_at();

comment on table public.service_applications is
  'One negotiation between a department and a service person. `direction` '
  'records who opened it and therefore who may decide it: an application is '
  'answered by the department, an invitation by the provider.';

-- ---------------------------------------------------------------------------
-- 5. Reads
--
-- One view serves both inboxes. The manager''s list and the provider''s list
-- are the same rows filtered by the policy in section 8, so a second projection
-- would only be a second place for the two sides to describe the same
-- negotiation differently.
-- ---------------------------------------------------------------------------

drop view if exists public.service_application_overview;
create view public.service_application_overview
with (security_invoker = true) as
select
  a.id,
  a.community_id,
  a.department_id,
  a.service_provider_id,
  a.direction,
  a.status,
  a.message,
  a.rank,
  a.job_title,
  a.shift,
  a.decision_note,
  a.decided_at,
  a.created_at,
  a.updated_at,
  c.name                                      as community_name,
  d.name                                      as department_name,
  d.kind                                      as department_kind,
  p.display_name                              as provider_display_name,
  p.headline                                  as provider_headline,
  p.phone_e164                                as provider_phone_e164,
  p.status                                    as provider_status,
  coalesce(sk.skill_names, '{}'::text[])      as provider_skill_names,
  case
    when c.location is null or p.location is null then null
    else round((extensions.st_distance(c.location, p.location) / 1000)::numeric, 2)
  end                                         as distance_km
from public.service_applications a
join public.communities c        on c.id = a.community_id
join public.departments d        on d.id = a.department_id
join public.service_providers p  on p.id = a.service_provider_id
left join lateral (
  select array_agg(s.name order by s.name) as skill_names
    from public.service_provider_skills sps
    join public.skills s on s.id = sps.skill_id
   where sps.service_provider_id = p.id
     and s.is_active
) sk on true;

comment on view public.service_application_overview is
  'Applications and invitations with the department, the provider and the '
  'distance between them. security_invoker, so section 8 decides which side of '
  'a negotiation a caller can see.';

grant select on public.service_application_overview to authenticated;

-- Where a service person actually works. One row per live engagement, across
-- every community that has hired them -- which is the whole reason the tenancy
-- seam in app/api/deps.py stopped assuming one community.
--
-- Built from staff_assignments rather than from community_memberships, because
-- the roster row is what carries the terms (rank, job title, shift) and the
-- membership only carries the right to be there. A membership with no roster
-- row cannot occur: section 7 writes both or neither.
--
-- No security_invoker gymnastics needed for the provider's own rows -- the
-- policy in section 8 does not cover staff_assignments, which 0019 already
-- governs. The predicate here is the provider identity, and it is stated in the
-- view rather than left to the caller to remember.
drop view if exists public.service_engagement_overview;
create view public.service_engagement_overview
with (security_invoker = true) as
select
  sa.id                as staff_assignment_id,
  sa.community_id,
  sa.department_id,
  sa.membership_id,
  sa.service_provider_id,
  sa.rank,
  sa.job_title,
  sa.shift,
  sa.status,
  sa.started_at,
  sa.ended_at,
  c.name               as community_name,
  c.city               as community_city,
  d.name               as department_name,
  d.kind               as department_kind,
  m.role::text         as membership_role,
  p.profile_id
from public.staff_assignments sa
join public.service_providers p on p.id = sa.service_provider_id
join public.communities c       on c.id = sa.community_id
join public.departments d       on d.id = sa.department_id
left join public.community_memberships m on m.id = sa.membership_id
where sa.service_provider_id is not null;

comment on view public.service_engagement_overview is
  'Every roster row belonging to a registered service person, with its '
  'community and department. The union across communities that a worker''s '
  'calendar and community list are built from.';

grant select on public.service_engagement_overview to authenticated;

-- Internal: is the caller entitled to act for this department?
--
-- An admin of the community, or a manager -- and a manager only for the
-- department their own membership names. `community_memberships.department_id`
-- is what scopes a manager, and it has existed since the baseline.
create or replace function public.can_manage_department(p_department_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
      from public.departments d
      join public.community_memberships m
        on m.community_id = d.community_id
       and m.profile_id = auth.uid()
       and m.status = 'active'
       and m.ended_at is null
     where d.id = p_department_id
       and (
         m.role = 'admin'
         or (m.role = 'manager'
             and (m.department_id is null or m.department_id = d.id))
       )
  );
$$;

comment on function public.can_manage_department(uuid) is
  'True when the caller may hire, remove or blacklist for this department: an '
  'admin of its community, or a manager whose membership names it (or names no '
  'department at all).';

grant execute on function public.can_manage_department(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 6. Who a manager could hire
--
-- The mirror of 0034's search_serviceable_communities, from the department's
-- side. The same three rules, inverted: hold a skill this department's
-- categories need, not blacklisted here, not already on this roster.
--
-- A provider with no coordinates sorts last rather than being hidden. Somebody
-- who has not filled in where they work is still somebody a manager may want.
--
-- PLPGSQL RATHER THAN SQL, AND THE REASON IS THE FIRST FOUR LINES OF THE BODY.
-- 0034's search_serviceable_communities is a plain SQL function and is safe
-- being one, because everything it returns is scoped to the caller's OWN
-- provider row via auth.uid(). This one is scoped by a department id the caller
-- supplies. A definer function that takes an id and checks nothing is an
-- enumeration endpoint: any signed-in person could read every service person in
-- the country by walking department ids. The check has to be inside, because
-- SECURITY DEFINER means RLS on the tables below does not apply.
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
    -- Already on this roster. Nothing to offer.
    and not exists (
      select 1 from public.staff_assignments sa
       where sa.department_id = dept.id
         and sa.service_provider_id = p.id
         and sa.status = 'active'
    )
    -- Already a member of this community in some other capacity -- a resident
    -- who is also a plumber. The membership uniqueness in section 7 would
    -- refuse the hire, so offering them here would be offering a dead end.
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
  'Service people this department could hire: holding a skill its categories '
  'need, not blacklisted, not already on its roster, and not already a member '
  'of the community. Nearest first.';

grant execute on function public.search_hireable_service_providers(
  uuid, text, integer, integer) to authenticated;

-- ---------------------------------------------------------------------------
-- 7. Writes
--
-- Every one of these is SECURITY DEFINER and checks its own authorization,
-- matching the posture 0031 established: the tables below carry read policies
-- and no write policy at all, so there is no path from the API process to a row
-- these functions did not write.
--
-- The authorization question differs by function and is stated at each one. It
-- is never "is the caller an admin somewhere" -- it is always about THIS
-- department or THIS provider, because a manager of one community must not be
-- able to hire into another by putting its id in a request body.
-- ---------------------------------------------------------------------------

-- A provider applies to a department.
create or replace function public.apply_to_department(
  p_department_id uuid,
  p_message       text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_provider   public.service_providers%rowtype;
  v_department public.departments%rowtype;
  v_id         uuid;
begin
  select * into v_provider
    from public.service_providers
   where profile_id = auth.uid();
  if not found then
    raise exception 'Register as a service provider first.' using errcode = 'HB404';
  end if;

  select * into v_department
    from public.departments
   where id = p_department_id
     and is_active;
  if not found then
    raise exception 'No such department.' using errcode = 'HB404';
  end if;

  if exists (
    select 1 from public.blacklisted_service_providers
     where community_id = v_department.community_id
       and service_provider_id = v_provider.id
       and revoked_at is null
  ) then
    -- Deliberately the same wording a rejection gets. Telling someone they have
    -- been barred, and by whom, is a decision for the community to communicate,
    -- not for this endpoint to leak.
    raise exception 'This department is not accepting your application.'
      using errcode = 'HB403';
  end if;

  if exists (
    select 1 from public.community_memberships
     where community_id = v_department.community_id
       and profile_id = auth.uid()
       and status = 'active'
       and ended_at is null
  ) then
    raise exception 'You already belong to this community.' using errcode = 'HB409';
  end if;

  insert into public.service_applications (
    community_id, department_id, service_provider_id, direction, message
  )
  values (
    v_department.community_id, v_department.id, v_provider.id, 'applied',
    nullif(btrim(coalesce(p_message, '')), '')
  )
  returning id into v_id;

  perform public.notify_community_roles(
    v_department.community_id,
    array['admin', 'manager'],
    'service_application_received',
    jsonb_build_object(
      'applicationId', v_id,
      'departmentId', v_department.id,
      'departmentName', v_department.name,
      'providerName', v_provider.display_name
    )
  );

  return v_id;
end;
$$;

-- A manager invites a provider.
create or replace function public.invite_service_provider(
  p_department_id      uuid,
  p_service_provider_id uuid,
  p_message            text default null,
  p_rank               text default 'member',
  p_job_title          text default null,
  p_shift              text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_department public.departments%rowtype;
  v_provider   public.service_providers%rowtype;
  v_actor      uuid;
  v_id         uuid;
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  select * into v_department from public.departments where id = p_department_id;
  select * into v_provider
    from public.service_providers where id = p_service_provider_id;
  if not found then
    raise exception 'No such service provider.' using errcode = 'HB404';
  end if;

  if exists (
    select 1 from public.blacklisted_service_providers
     where community_id = v_department.community_id
       and service_provider_id = v_provider.id
       and revoked_at is null
  ) then
    raise exception 'This person is blacklisted in your community.'
      using errcode = 'HB409';
  end if;

  if exists (
    select 1 from public.community_memberships
     where community_id = v_department.community_id
       and profile_id = v_provider.profile_id
       and status = 'active'
       and ended_at is null
  ) then
    raise exception 'This person already belongs to your community.'
      using errcode = 'HB409';
  end if;

  select id into v_actor
    from public.community_memberships
   where community_id = v_department.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null
   limit 1;

  insert into public.service_applications (
    community_id, department_id, service_provider_id, direction, message,
    rank, job_title, shift, created_by_membership_id
  )
  values (
    v_department.community_id, v_department.id, v_provider.id, 'invited',
    nullif(btrim(coalesce(p_message, '')), ''),
    coalesce(nullif(btrim(coalesce(p_rank, '')), ''), 'member'),
    nullif(btrim(coalesce(p_job_title, '')), ''),
    nullif(btrim(coalesce(p_shift, '')), ''),
    v_actor
  )
  returning id into v_id;

  -- The provider may hold no membership anywhere, so there is nobody to
  -- notify_member. The invitation surfaces on their applications screen, which
  -- is the one place a provider with no community can still be reached.
  return v_id;
end;
$$;

-- Decide a pending negotiation. The one that has to be atomic.
--
-- Who may decide is the mirror of who opened it: an application is answered by
-- the department, an invitation by the provider. Anything else is a 403, and
-- that check is why `direction` is a column rather than a comment.
--
-- Accepting writes THREE rows -- a membership, a roster entry and the decision
-- -- inside this one transaction. A membership without a roster row is a person
-- who can log in and has no job; a roster row without a membership is a name on
-- a list with no way in. Neither is recoverable by retrying, which is exactly
-- what a client would do.
create or replace function public.decide_service_application(
  p_application_id uuid,
  p_decision       text,
  p_rank           text default null,
  p_job_title      text default null,
  p_shift          text default null,
  p_note           text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_app        public.service_applications%rowtype;
  v_department public.departments%rowtype;
  v_provider   public.service_providers%rowtype;
  v_decision   text := lower(btrim(coalesce(p_decision, '')));
  v_is_manager boolean;
  v_is_owner   boolean;
  v_actor      uuid;
  v_membership uuid;
  v_staff      uuid;
  v_role       text;
  v_rank       text;
begin
  if v_decision not in ('accepted', 'rejected', 'withdrawn') then
    raise exception 'Unknown decision.' using errcode = '22004';
  end if;

  -- FOR UPDATE, so two managers clicking Accept on the same application do not
  -- both reach the membership insert.
  select * into v_app
    from public.service_applications
   where id = p_application_id
   for update;
  if not found then
    raise exception 'No such application.' using errcode = 'HB404';
  end if;

  if v_app.status <> 'pending' then
    raise exception 'This application has already been decided.'
      using errcode = 'HB409';
  end if;

  select * into v_department from public.departments where id = v_app.department_id;
  select * into v_provider
    from public.service_providers where id = v_app.service_provider_id;

  v_is_manager := public.can_manage_department(v_app.department_id);
  v_is_owner   := v_provider.profile_id = auth.uid();

  -- Withdrawal is always the opener's to make; accept and reject belong to the
  -- side that did not open it.
  if v_decision = 'withdrawn' then
    if not ((v_app.direction = 'applied' and v_is_owner)
            or (v_app.direction = 'invited' and v_is_manager)) then
      raise exception 'Only the side that opened this may withdraw it.'
        using errcode = 'HB403';
    end if;
  elsif v_app.direction = 'applied' then
    if not v_is_manager then
      raise exception 'Only the department may answer an application.'
        using errcode = 'HB403';
    end if;
  else
    if not v_is_owner then
      raise exception 'Only the invited person may answer an invitation.'
        using errcode = 'HB403';
    end if;
  end if;

  select id into v_actor
    from public.community_memberships
   where community_id = v_app.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null
   limit 1;

  if v_decision = 'accepted' then
    if exists (
      select 1 from public.blacklisted_service_providers
       where community_id = v_app.community_id
         and service_provider_id = v_app.service_provider_id
         and revoked_at is null
    ) then
      raise exception 'This person is blacklisted in this community.'
        using errcode = 'HB409';
    end if;

    if exists (
      select 1 from public.community_memberships
       where community_id = v_app.community_id
         and profile_id = v_provider.profile_id
         and status = 'active'
         and ended_at is null
    ) then
      raise exception 'This person already belongs to this community.'
        using errcode = 'HB409';
    end if;

    -- A security department hires security; everything else hires a worker.
    -- Both values have been in public.membership_role since the baseline and
    -- nothing has ever issued either one.
    v_role := case when v_department.kind = 'security' then 'security'
                   else 'worker' end;

    -- The terms: what this decision supplies, else what the invitation carried,
    -- else the default. A manager accepting an application names the terms
    -- here; a provider accepting an invitation accepts the ones already in the
    -- row, and cannot promote themselves by passing p_rank.
    if v_app.direction = 'applied' then
      v_rank := coalesce(nullif(btrim(coalesce(p_rank, '')), ''),
                         v_app.rank, 'member');
    else
      v_rank := coalesce(v_app.rank, 'member');
    end if;

    insert into public.community_memberships (
      community_id, profile_id, department_id, role, status, joined_at
    )
    values (
      v_app.community_id, v_provider.profile_id, v_app.department_id,
      v_role::public.membership_role, 'active', now()
    )
    returning id into v_membership;

    insert into public.staff_assignments (
      community_id, department_id, membership_id, service_provider_id,
      display_name, phone_e164, job_title, rank, shift, status,
      employment_type, started_at
    )
    values (
      v_app.community_id, v_app.department_id, v_membership, v_provider.id,
      v_provider.display_name, v_provider.phone_e164,
      coalesce(nullif(btrim(coalesce(p_job_title, '')), ''), v_app.job_title),
      v_rank,
      coalesce(nullif(btrim(coalesce(p_shift, '')), ''), v_app.shift),
      'active', 'staff', current_date
    )
    returning id into v_staff;
  end if;

  update public.service_applications
     set status                   = v_decision,
         rank                     = coalesce(v_rank, rank),
         job_title                = coalesce(
                                      nullif(btrim(coalesce(p_job_title, '')), ''),
                                      job_title),
         shift                    = coalesce(
                                      nullif(btrim(coalesce(p_shift, '')), ''),
                                      shift),
         decided_by_membership_id = v_actor,
         decided_at               = now(),
         decision_note            = nullif(btrim(coalesce(p_note, '')), ''),
         updated_at               = now()
   where id = v_app.id;

  -- Notify the side that did not decide. A hire, a rejection and a withdrawal
  -- are all things the other party has to hear about; this is the offer-shaped
  -- notification plan D9 permits, not a passive field change.
  --
  -- ONE SIDE OF THIS IS DELIBERATELY SILENT, and it is worth knowing rather
  -- than discovering. `notifications.recipient_membership_id` is not nullable
  -- and cannot be -- a notification belongs to somebody in a community. A
  -- service person who has been REJECTED holds no membership in that community
  -- by definition, so there is no row to address and nothing to send. The same
  -- is true of an invitation, which is why invite_service_provider sends
  -- nothing either.
  --
  -- Their applications screen is therefore a read and not a feed, and that is
  -- the whole of the mechanism: GET /worker/applications shows the decided row.
  -- An acceptance IS notified, because the membership the accept just created
  -- is the address it goes to -- the first notification a service person can
  -- receive is the one saying they were hired.
  if v_decision <> 'withdrawn' and v_app.direction = 'applied' then
    if v_membership is not null then
      perform public.notify_member(
        v_membership, 'service_application_' || v_decision,
        jsonb_build_object(
          'applicationId', v_app.id,
          'communityId', v_app.community_id,
          'departmentName', v_department.name));
    end if;
  elsif v_decision <> 'withdrawn' then
    perform public.notify_community_roles(
      v_app.community_id, array['admin', 'manager'],
      'service_invitation_' || v_decision,
      jsonb_build_object(
        'applicationId', v_app.id,
        'departmentId', v_app.department_id,
        'departmentName', v_department.name,
        'providerName', v_provider.display_name));
  end if;

  return coalesce(v_staff, v_app.id);
end;
$$;

-- Remove someone from a department's roster.
--
-- Deactivates, ends the membership, and stops there. 0019 A7 already refuses to
-- delete a roster row, because complaints record staff by name and a deleted
-- row turns a past assignment into an unexplained string. Ending the membership
-- is what actually removes their access; the row is what keeps the history
-- readable.
--
-- Reapplication is allowed afterwards. That is the whole difference between
-- this and the next function.
create or replace function public.remove_department_member(
  p_staff_id uuid,
  p_reason   text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_staff public.staff_assignments%rowtype;
begin
  select * into v_staff from public.staff_assignments where id = p_staff_id;
  if not found then
    raise exception 'No such roster entry.' using errcode = 'HB404';
  end if;

  if not public.can_manage_department(v_staff.department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  update public.staff_assignments
     set status     = 'inactive',
         is_active  = false,
         rank       = 'member',
         ended_at   = current_date,
         updated_at = now()
   where id = p_staff_id;

  if v_staff.membership_id is not null then
    update public.community_memberships
       set status     = 'ended',
           ended_at   = now(),
           updated_at = now()
     where id = v_staff.membership_id;

    perform public.notify_member(
      v_staff.membership_id, 'service_engagement_ended',
      jsonb_build_object(
        'departmentId', v_staff.department_id,
        'reason', nullif(btrim(coalesce(p_reason, '')), '')));
  end if;
end;
$$;

-- Remove, and bar from applying again.
--
-- The blacklist is per COMMUNITY, not per department: a community that will not
-- have someone back has decided that about the community, and letting them
-- reapply to the department next door would make the decision meaningless.
-- Reversible by design -- blacklisted_service_providers carries revoked_at --
-- because a permanent decision made in an afternoon still needs an undo.
create or replace function public.blacklist_service_provider(
  p_department_id       uuid,
  p_service_provider_id uuid,
  p_reason              text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_department public.departments%rowtype;
  v_actor      uuid;
  v_id         uuid;
  v_staff      uuid;
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  if coalesce(btrim(p_reason), '') = '' then
    raise exception 'A reason is required.' using errcode = '22004';
  end if;

  select * into v_department from public.departments where id = p_department_id;

  select id into v_actor
    from public.community_memberships
   where community_id = v_department.community_id
     and profile_id = auth.uid()
     and status = 'active'
     and ended_at is null
   limit 1;

  -- Remove them first, wherever in this community they are on a roster. A bar
  -- that leaves the person still working here is not a bar.
  for v_staff in
    select sa.id
      from public.staff_assignments sa
     where sa.community_id = v_department.community_id
       and sa.service_provider_id = p_service_provider_id
       and sa.status = 'active'
  loop
    perform public.remove_department_member(v_staff, btrim(p_reason));
  end loop;

  -- Any open negotiation is closed rather than left pending against someone who
  -- can no longer be hired.
  update public.service_applications
     set status                   = 'rejected',
         decided_by_membership_id = v_actor,
         decided_at               = now(),
         decision_note            = btrim(p_reason),
         updated_at               = now()
   where community_id = v_department.community_id
     and service_provider_id = p_service_provider_id
     and status = 'pending';

  insert into public.blacklisted_service_providers (
    community_id, service_provider_id, blacklisted_by_membership_id, reason
  )
  values (
    v_department.community_id, p_service_provider_id, v_actor, btrim(p_reason)
  )
  on conflict do nothing
  returning id into v_id;

  return v_id;
end;
$$;

grant execute on function public.apply_to_department(uuid, text) to authenticated;
grant execute on function public.invite_service_provider(
  uuid, uuid, text, text, text, text) to authenticated;
grant execute on function public.decide_service_application(
  uuid, text, text, text, text, text) to authenticated;
grant execute on function public.remove_department_member(uuid, text)
  to authenticated;
grant execute on function public.blacklist_service_provider(uuid, uuid, text)
  to authenticated;

-- ---------------------------------------------------------------------------
-- 8. Row security
--
-- Read policies only. Every write above is a definer function that checked its
-- own authorization, so there is deliberately no insert, update or delete
-- policy on either table -- the same posture as 0031 and 0034.
-- ---------------------------------------------------------------------------

alter table public.service_applications enable row level security;
alter table public.blacklisted_service_providers enable row level security;

drop policy if exists service_applications_read on public.service_applications;
create policy service_applications_read on public.service_applications
  for select to authenticated
  using (
    -- The department's side.
    public.is_community_admin(community_id)
    or public.can_manage_department(department_id)
    -- The provider's side. Their own negotiations, in every community, which is
    -- what makes one applications screen possible for someone who belongs to
    -- none of them.
    or exists (
      select 1 from public.service_providers p
       where p.id = service_provider_id
         and p.profile_id = auth.uid()
    )
  );

drop policy if exists blacklisted_providers_read
  on public.blacklisted_service_providers;
create policy blacklisted_providers_read on public.blacklisted_service_providers
  for select to authenticated
  using (
    -- Only the community that made the decision can read it. A provider is
    -- deliberately NOT shown their own blacklist rows: the reason is written by
    -- one party about another, and the applications screen already tells them
    -- the outcome without handing them the note.
    public.is_community_admin(community_id)
    or exists (
      select 1 from public.community_memberships m
       where m.community_id = blacklisted_service_providers.community_id
         and m.profile_id = auth.uid()
         and m.role = 'manager'
         and m.status = 'active'
         and m.ended_at is null
    )
  );

grant select on public.service_applications to authenticated;
grant select on public.blacklisted_service_providers to authenticated;
