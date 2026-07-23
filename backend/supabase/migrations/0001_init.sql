-- 0001_init.sql
-- Core schema for HomeBandhu: role enum, community structure, profiles, and the
-- invitation carrier for admin-initiated resident registration.
--
-- Apply with the Supabase CLI (`supabase db push`) or paste into the SQL editor.

-- ---------------------------------------------------------------------------
-- Roles
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'user_role') then
    create type public.user_role as enum (
      'RESIDENT', 'MANAGER', 'TECHNICIAN', 'SECURITY', 'ADMIN'
    );
  end if;
end$$;

-- ---------------------------------------------------------------------------
-- Community structure
-- ---------------------------------------------------------------------------
create table if not exists public.associations (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  community_type text not null default 'apartment',
  status        text not null default 'Active',
  created_at    timestamptz not null default now()
);

-- A "unit" is a block (apartment community) or a villa (layout community).
create table if not exists public.units (
  id             uuid primary key default gen_random_uuid(),
  association_id uuid not null references public.associations(id) on delete cascade,
  name           text not null,
  kind           text not null default 'block',
  coordinates    jsonb,
  created_at     timestamptz not null default now()
);

-- A flat/home. `code` is the human identifier used across the app (e.g. B-1204).
create table if not exists public.apartments (
  id             uuid primary key default gen_random_uuid(),
  association_id uuid not null references public.associations(id) on delete cascade,
  unit_id        uuid references public.units(id) on delete set null,
  code           text not null,
  unique (association_id, code)
);

-- ---------------------------------------------------------------------------
-- Profiles — one row per auth.users row, carrying role + community placement.
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id             uuid primary key references auth.users(id) on delete cascade,
  role           public.user_role not null default 'RESIDENT',
  full_name      text,
  phone          text,
  apartment_id   text,
  association_id uuid references public.associations(id) on delete set null,
  status         text not null default 'Active',
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index if not exists profiles_apartment_id_idx on public.profiles (apartment_id);
create index if not exists profiles_association_id_idx on public.profiles (association_id);

-- Auto-create a profile whenever a new auth user is created. Role/apartment are
-- seeded from user_metadata when present (the invite-redeem flow sets these),
-- otherwise a plain RESIDENT profile is created.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, role, full_name, phone, apartment_id)
  values (
    new.id,
    coalesce((new.raw_user_meta_data ->> 'role')::public.user_role, 'RESIDENT'),
    new.raw_user_meta_data ->> 'full_name',
    new.phone,
    new.raw_user_meta_data ->> 'apartment_id'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Invitations — the carrier for the resident magic-link + typable-code flow.
-- Only hashes of the link token and the code are stored; plaintext is shown to
-- the admin exactly once at creation time.
-- ---------------------------------------------------------------------------
create table if not exists public.invitations (
  id             uuid primary key default gen_random_uuid(),
  token_hash     text not null unique,
  code_hash      text not null,
  phone          text not null,
  apartment_id   text not null,
  role           public.user_role not null default 'RESIDENT',
  association_id uuid references public.associations(id) on delete cascade,
  full_name      text,
  created_by     uuid references auth.users(id) on delete set null,
  expires_at     timestamptz not null,
  redeemed_at    timestamptz,
  created_at     timestamptz not null default now()
);

create index if not exists invitations_phone_idx on public.invitations (phone);
create index if not exists invitations_code_hash_idx on public.invitations (code_hash);
