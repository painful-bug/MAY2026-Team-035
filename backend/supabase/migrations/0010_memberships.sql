-- 0010_memberships.sql
-- Community memberships and unit residencies, in the shape the ERD defines.
--
-- MIGRATION NUMBERING
--   0004-0009 are RESERVED for the auth/security workstream (privilege escalation
--   in handle_new_user(), tenant-scoping of is_admin() -- see
--   docs/ADMIN_DASHBOARD_BUILD_PLAN.md section 1). That work is owned by another
--   developer and runs in parallel with this one. Dashboard migrations start at
--   0010 so the two streams can never collide on a filename.
--
-- WHY THIS LANDS BEFORE ANY DASHBOARD TABLE
--   Every dashboard table needs an actor foreign key -- raised_by, created_by,
--   assigned_to, approved_by. Pointed at `profiles`, all of them need repointing
--   when memberships arrive. Pointed at `community_memberships`, they never move.
--
-- WHY NO AUTH CODE CHANGES
--   `profiles.role` and `profiles.association_id` are KEPT, and become
--   compatibility columns maintained by trigger from the membership row. The
--   access token hook (0003), jwt_role(), is_admin() and every FastAPI
--   require_role() guard keep reading `profiles.role` and are untouched.
--
-- NAMING
--   The live schema and the ERD disagree on table names (see the build plan
--   section 0.2). New columns here use the ERD's vocabulary -- `community_id`,
--   `unit_id` -- while the foreign keys point at today's tables (`associations`,
--   `apartments`). When those tables are renamed by agreement, the foreign keys
--   follow automatically and nothing in this file changes.
--     community_id -> associations(id)   [ERD: communities]
--     unit_id      -> apartments(id)      [ERD: units -- a flat/home]
--   NOTE the live table `units` means a BLOCK, which is the opposite of the ERD's
--   `units`. This file never references it.

-- ---------------------------------------------------------------------------
-- Shared updated_at trigger (R3)
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Prerequisite unique constraint for composite foreign keys (R4)
--
-- A composite FK (child.unit_id, child.community_id) -> apartments (id, association_id)
-- makes it structurally impossible to attach a row to a flat in a different
-- community. Postgres requires a matching unique constraint on the parent.
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'apartments_id_association_uq'
      and conrelid = 'public.apartments'::regclass
  ) then
    alter table public.apartments
      add constraint apartments_id_association_uq unique (id, association_id);
  end if;
end$$;

-- ---------------------------------------------------------------------------
-- community_memberships
--
-- One row per (community, person). This is the actor other tables point at.
-- `role` reuses the existing public.user_role enum deliberately: the compat
-- trigger below copies it straight into profiles.role with no mapping, so the
-- JWT claim keeps its current vocabulary. Reconciling the enum with the ERD's
-- lowercase vocabulary is open decision 2 and is a separate, mechanical change.
-- ---------------------------------------------------------------------------
create table if not exists public.community_memberships (
  id           uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.associations(id) on delete cascade,
  profile_id   uuid not null references public.profiles(id) on delete cascade,
  role         public.user_role not null default 'RESIDENT',
  status       text not null default 'active',
  joined_at    timestamptz not null default now(),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint community_memberships_status_ck
    check (status in ('active', 'inactive', 'suspended')),
  constraint community_memberships_community_profile_uq
    unique (community_id, profile_id),
  -- parent key for child composite FKs (R4)
  constraint community_memberships_id_community_uq unique (id, community_id)
);

create index if not exists community_memberships_profile_idx
  on public.community_memberships (profile_id);
create index if not exists community_memberships_community_role_idx
  on public.community_memberships (community_id, role) where status = 'active';

drop trigger if exists community_memberships_set_updated_at on public.community_memberships;
create trigger community_memberships_set_updated_at
  before update on public.community_memberships
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- unit_residencies
--
-- Residency, not role, is what grants resident capabilities (R17c). A person is
-- a resident of a flat for a period; the membership carries the role.
-- ---------------------------------------------------------------------------
create table if not exists public.unit_residencies (
  id            uuid primary key default gen_random_uuid(),
  community_id  uuid not null references public.associations(id) on delete cascade,
  unit_id       uuid not null,
  membership_id uuid not null,
  relationship  text not null default 'resident',
  is_primary    boolean not null default false,
  start_date    date not null default current_date,
  end_date      date,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  constraint unit_residencies_relationship_ck
    check (relationship in ('owner', 'tenant', 'family', 'resident')),
  constraint unit_residencies_dates_ck
    check (end_date is null or end_date >= start_date),
  -- Composite FKs: a residency cannot point at a flat or a membership belonging
  -- to a different community. Not enforceable by convention -- only by the key.
  constraint unit_residencies_unit_fk
    foreign key (unit_id, community_id)
    references public.apartments (id, association_id) on delete cascade,
  constraint unit_residencies_membership_fk
    foreign key (membership_id, community_id)
    references public.community_memberships (id, community_id) on delete cascade
);

create index if not exists unit_residencies_unit_idx
  on public.unit_residencies (unit_id) where end_date is null;
create index if not exists unit_residencies_membership_idx
  on public.unit_residencies (membership_id);

-- At most one CURRENT residency per (flat, person). Partial on end_date is null
-- so history is unconstrained -- someone may live in the same flat twice.
create unique index if not exists unit_residencies_active_uq
  on public.unit_residencies (unit_id, membership_id) where end_date is null;

-- At most one CURRENT primary resident per flat. This is the row that owns the
-- flat's billing contact and the "head of household" display.
create unique index if not exists unit_residencies_primary_uq
  on public.unit_residencies (unit_id) where is_primary and end_date is null;

drop trigger if exists unit_residencies_set_updated_at on public.unit_residencies;
create trigger unit_residencies_set_updated_at
  before update on public.unit_residencies
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Compatibility trigger: keep profiles.role / profiles.association_id in sync
--
-- This is what makes the migration free of auth-code changes. The membership row
-- is the source of truth; profiles.role is a projection of it that the access
-- token hook already knows how to read.
--
-- Composes with the parallel fix to handle_new_user(): that function owns the
-- INSERT (defaulting every new profile to RESIDENT), this trigger owns every
-- subsequent change. Different moments, no overlap.
-- ---------------------------------------------------------------------------
create or replace function public.sync_profile_from_membership()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  fallback public.community_memberships%rowtype;
begin
  if tg_op = 'DELETE' then
    -- Another membership may remain (a person can belong to more than one
    -- community). Project the most recent one rather than blanking the profile.
    select * into fallback
    from public.community_memberships
    where profile_id = old.profile_id and status = 'active'
    order by joined_at desc, created_at desc
    limit 1;

    if found then
      update public.profiles
         set role = fallback.role,
             association_id = fallback.community_id,
             updated_at = now()
       where id = old.profile_id;
    else
      update public.profiles
         set role = 'RESIDENT',
             association_id = null,
             updated_at = now()
       where id = old.profile_id;
    end if;
    return old;
  end if;

  -- Only project ACTIVE memberships. A suspended membership must not keep
  -- handing out its role in the JWT.
  if new.status = 'active' then
    update public.profiles
       set role = new.role,
           association_id = new.community_id,
           updated_at = now()
     where id = new.profile_id
       and (role is distinct from new.role
            or association_id is distinct from new.community_id);
  else
    select * into fallback
    from public.community_memberships
    where profile_id = new.profile_id and status = 'active' and id <> new.id
    order by joined_at desc, created_at desc
    limit 1;

    update public.profiles
       set role = coalesce(fallback.role, 'RESIDENT'),
           association_id = fallback.community_id,
           updated_at = now()
     where id = new.profile_id;
  end if;

  return new;
end;
$$;

drop trigger if exists community_memberships_sync_profile on public.community_memberships;
create trigger community_memberships_sync_profile
  after insert or update of role, status, community_id or delete
  on public.community_memberships
  for each row execute function public.sync_profile_from_membership();

-- ---------------------------------------------------------------------------
-- Backfill from the existing profiles columns
--
-- Runs BEFORE the RLS policies below so it is not filtered by them, and is
-- idempotent so re-applying the migration is safe.
-- ---------------------------------------------------------------------------

-- 1. Memberships, from profiles.role + profiles.association_id.
--    The sync trigger fires and writes back the same values it read: a no-op,
--    because the update is guarded by `is distinct from`.
insert into public.community_memberships (community_id, profile_id, role, status, joined_at)
select p.association_id,
       p.id,
       p.role,
       case when lower(coalesce(p.status, 'Active')) = 'active' then 'active' else 'inactive' end,
       p.created_at
from public.profiles p
where p.association_id is not null
on conflict on constraint community_memberships_community_profile_uq do nothing;

-- 2. Flats referenced by profiles.apartment_id (free text, e.g. 'B-1204') that
--    have no apartments row yet. The frontend never had a flat-creation step, so
--    these are created on first reference -- the same find-or-create rule the API
--    will use (see FRONTEND_MEETING_AGENDA.md, "not on this list").
insert into public.apartments (association_id, code)
select distinct p.association_id, trim(p.apartment_id)
from public.profiles p
where p.association_id is not null
  and nullif(trim(coalesce(p.apartment_id, '')), '') is not null
on conflict (association_id, code) do nothing;

-- 3. Residencies. is_primary is granted to ONE person per flat -- the earliest
--    created -- because unit_residencies_primary_uq permits only one. Flagging
--    every occupant primary would make the index reject all but the first and
--    silently drop the rest.
insert into public.unit_residencies (community_id, unit_id, membership_id, relationship, is_primary, start_date)
select m.community_id,
       a.id,
       m.id,
       'resident',
       row_number() over (partition by a.id order by p.created_at, p.id) = 1,
       p.created_at::date
from public.community_memberships m
join public.profiles p on p.id = m.profile_id
join public.apartments a
  on a.association_id = m.community_id
 and a.code = trim(p.apartment_id)
where m.role = 'RESIDENT'
  and nullif(trim(coalesce(p.apartment_id, '')), '') is not null
on conflict do nothing;

-- ---------------------------------------------------------------------------
-- Row-Level Security
--
-- These policies are scoped by community from the outset. They deliberately do
-- NOT reuse bare is_admin(), which today grants every admin access to every
-- community (build plan section 1.2). That finding therefore does not propagate
-- into these tables while the parallel fix is in flight.
--
-- current_community_ids() is intentionally named differently from the
-- current_association_id() proposed in section 1.2, so the two migration streams
-- cannot collide on a function name. When that helper lands, these policies can
-- adopt it in a one-line mechanical change.
-- ---------------------------------------------------------------------------
create or replace function public.current_community_ids()
returns setof uuid
language sql
stable
security definer
set search_path = public
as $$
  -- security definer: these tables have RLS, and a policy that queried them
  -- directly would recurse. Runs as owner, so it reads underneath RLS.
  select community_id
    from public.community_memberships
   where profile_id = auth.uid() and status = 'active'
  union
  select association_id
    from public.profiles
   where id = auth.uid() and association_id is not null;
$$;

revoke execute on function public.current_community_ids() from public, anon;
grant execute on function public.current_community_ids() to authenticated;

alter table public.community_memberships enable row level security;
alter table public.unit_residencies enable row level security;

drop policy if exists community_memberships_member_read on public.community_memberships;
create policy community_memberships_member_read on public.community_memberships
  for select using (community_id in (select public.current_community_ids()));

drop policy if exists community_memberships_admin_write on public.community_memberships;
create policy community_memberships_admin_write on public.community_memberships
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

drop policy if exists unit_residencies_member_read on public.unit_residencies;
create policy unit_residencies_member_read on public.unit_residencies
  for select using (community_id in (select public.current_community_ids()));

drop policy if exists unit_residencies_admin_write on public.unit_residencies;
create policy unit_residencies_admin_write on public.unit_residencies
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

-- ---------------------------------------------------------------------------
-- Verification -- run after applying. Each should return zero rows.
-- ---------------------------------------------------------------------------
-- Every placed profile has a membership:
--   select p.id from public.profiles p
--   left join public.community_memberships m on m.profile_id = p.id
--   where p.association_id is not null and m.id is null;
--
-- profiles.role agrees with the active membership:
--   select p.id, p.role, m.role from public.profiles p
--   join public.community_memberships m
--     on m.profile_id = p.id and m.status = 'active'
--   where p.role is distinct from m.role;
--
-- No resident with a flat code was dropped by the residency backfill:
--   select p.id, p.apartment_id from public.profiles p
--   join public.community_memberships m on m.profile_id = p.id and m.role = 'RESIDENT'
--   left join public.unit_residencies r on r.membership_id = m.id
--   where nullif(trim(coalesce(p.apartment_id, '')), '') is not null and r.id is null;
