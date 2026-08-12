-- FastAPI performs tenant-scoped reads with the signed-in user's JWT. RLS
-- decides which rows that client may see, but PostgreSQL still requires the
-- authenticated role to have the underlying table privilege first.
--
-- Restrict this repair to tables that already have RLS enabled. Future tables
-- must opt in explicitly after enabling and defining their policies.
-- staff_assignments was the one legacy exception: its repositories and views
-- were written for RLS, but the table had never actually enabled it.
alter table public.staff_assignments enable row level security;

drop policy if exists staff_assignments_read on public.staff_assignments;
create policy staff_assignments_read on public.staff_assignments
  for select to authenticated
  using (
    public.is_community_member(community_id)
    or exists (
      select 1
        from public.service_providers p
       where p.id = staff_assignments.service_provider_id
         and p.profile_id = auth.uid()
    )
  );

drop policy if exists staff_assignments_admin_write
  on public.staff_assignments;
create policy staff_assignments_admin_write on public.staff_assignments
  for all to authenticated
  using (public.is_community_admin(community_id))
  with check (public.is_community_admin(community_id));

grant insert, update on public.staff_assignments to authenticated;

do $$
declare
  v_table regclass;
begin
  for v_table in
    select c.oid::regclass
      from pg_catalog.pg_class c
      join pg_catalog.pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public'
       and c.relkind in ('r', 'p')
       and c.relrowsecurity
  loop
    execute format('grant select on table %s to authenticated', v_table);
  end loop;
end
$$;

-- service_application_overview is a security-invoker view. An applicant may
-- read their service_applications row, so permit that same caller to read only
-- the joined community and department for their own application.
drop policy if exists communities_service_application_read
  on public.communities;
create policy communities_service_application_read on public.communities
  for select to authenticated
  using (
    exists (
      select 1
        from public.service_applications a
        join public.service_providers p on p.id = a.service_provider_id
       where a.community_id = communities.id
         and p.profile_id = auth.uid()
    )
  );

drop policy if exists departments_service_application_read
  on public.departments;
create policy departments_service_application_read on public.departments
  for select to authenticated
  using (
    exists (
      select 1
        from public.service_applications a
        join public.service_providers p on p.id = a.service_provider_id
       where a.department_id = departments.id
         and p.profile_id = auth.uid()
    )
  );
