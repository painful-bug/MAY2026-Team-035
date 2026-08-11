-- Fix the self-reference in 0033's unit_residencies SELECT policy.
-- A policy is evaluated while reading its own relation, so querying that relation
-- from the policy makes PostgreSQL recurse indefinitely (42P17).

create or replace function public.is_current_unit_resident(p_unit_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select p_unit_id is not null and exists (
    select 1
      from public.unit_residencies r
      join public.community_memberships m on m.id = r.membership_id
     where r.unit_id = p_unit_id
       and r.ended_at is null
       and m.profile_id = auth.uid()
       and m.status = 'active'
       and m.ended_at is null
  );
$$;

comment on function public.is_current_unit_resident(uuid) is
  'True when the caller has an active, current residency in the supplied unit. Keeps residency RLS from querying itself.';

revoke all on function public.is_current_unit_resident(uuid) from public, anon;
grant execute on function public.is_current_unit_resident(uuid) to authenticated;

drop policy if exists unit_residencies_read on public.unit_residencies;
create policy unit_residencies_read on public.unit_residencies
  for select to authenticated
  using (
    public.is_own_membership(membership_id)
    or public.is_current_unit_resident(unit_id)
    or exists (
      select 1 from public.community_memberships m
       where m.id = unit_residencies.membership_id
         and public.is_community_admin(m.community_id)
    )
  );
