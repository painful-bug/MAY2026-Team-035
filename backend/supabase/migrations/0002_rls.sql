-- 0002_rls.sql
-- Row-Level Security. RLS is the innermost enforcement layer: even if an API
-- guard were bypassed, Postgres itself restricts what each role's JWT can read
-- or write. The service-role key (used only by trusted backend operations)
-- bypasses these policies by design.
--
-- The current user's role comes from the `user_role` claim injected by the
-- access-token hook (0003); `auth.uid()` is the authenticated user's id.

-- Convenience: read the role claim from the JWT as text.
create or replace function public.jwt_role()
returns text
language sql
stable
as $$
  select coalesce(
    nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_role',
    ''
  );
$$;

create or replace function public.is_admin()
returns boolean
language sql
stable
as $$
  select public.jwt_role() = 'ADMIN';
$$;

-- ---------------------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------------------
alter table public.profiles enable row level security;

drop policy if exists profiles_self_select on public.profiles;
create policy profiles_self_select on public.profiles
  for select using (id = auth.uid() or public.is_admin());

drop policy if exists profiles_self_update on public.profiles;
create policy profiles_self_update on public.profiles
  for update using (id = auth.uid() or public.is_admin())
  with check (id = auth.uid() or public.is_admin());

-- ---------------------------------------------------------------------------
-- associations / units / apartments — readable by members of the association,
-- writable only by admins.
-- ---------------------------------------------------------------------------
alter table public.associations enable row level security;
alter table public.units enable row level security;
alter table public.apartments enable row level security;

drop policy if exists associations_member_read on public.associations;
create policy associations_member_read on public.associations
  for select using (
    public.is_admin()
    or id in (select association_id from public.profiles where id = auth.uid())
  );

drop policy if exists associations_admin_write on public.associations;
create policy associations_admin_write on public.associations
  for all using (public.is_admin()) with check (public.is_admin());

drop policy if exists units_member_read on public.units;
create policy units_member_read on public.units
  for select using (
    public.is_admin()
    or association_id in (select association_id from public.profiles where id = auth.uid())
  );

drop policy if exists units_admin_write on public.units;
create policy units_admin_write on public.units
  for all using (public.is_admin()) with check (public.is_admin());

drop policy if exists apartments_member_read on public.apartments;
create policy apartments_member_read on public.apartments
  for select using (
    public.is_admin()
    or association_id in (select association_id from public.profiles where id = auth.uid())
  );

drop policy if exists apartments_admin_write on public.apartments;
create policy apartments_admin_write on public.apartments
  for all using (public.is_admin()) with check (public.is_admin());

-- ---------------------------------------------------------------------------
-- invitations — only admins can see/manage them through a user-scoped client.
-- (The redeem flow runs under the service-role key, which bypasses RLS.)
-- ---------------------------------------------------------------------------
alter table public.invitations enable row level security;

drop policy if exists invitations_admin_all on public.invitations;
create policy invitations_admin_all on public.invitations
  for all using (public.is_admin()) with check (public.is_admin());
