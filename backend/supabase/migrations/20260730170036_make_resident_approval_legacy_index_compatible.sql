-- The legacy and fresh schemas use different partial predicates for active
-- membership uniqueness.  Catching unique_violation is predicate-agnostic and
-- preserves the same race-safe, idempotent approval semantics in both.
create or replace function public.approve_access_request(
  p_request_id uuid,
  p_reviewer_profile_id uuid,
  p_unit_id uuid default null,
  p_relationship public.residency_relationship default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  request_row public.access_requests%rowtype;
  reviewer_membership_id uuid;
  resident_membership_id uuid;
  target_unit_id uuid := p_unit_id;
begin
  select * into request_row
  from public.access_requests
  where id = p_request_id
  for update;
  if request_row.id is null then
    raise exception 'Access request not found';
  end if;

  select id into reviewer_membership_id
  from public.community_memberships
  where profile_id = p_reviewer_profile_id
    and community_id = request_row.community_id
    and role = 'admin'
    and status = 'active'
    and ended_at is null
  limit 1;
  if reviewer_membership_id is null then
    raise exception 'Active administrator membership required';
  end if;

  if request_row.status = 'approved' then
    select id into resident_membership_id
    from public.community_memberships
    where community_id = request_row.community_id
      and profile_id = request_row.applicant_profile_id
      and role = 'resident'
      and status = 'active'
      and ended_at is null
    limit 1;
    return jsonb_build_object(
      'request_id', request_row.id,
      'membership_id', resident_membership_id,
      'status', 'approved'
    );
  end if;
  if request_row.status <> 'pending' then
    raise exception 'Access request is no longer pending';
  end if;

  if target_unit_id is null then
    target_unit_id := request_row.requested_unit_id;
  end if;
  if target_unit_id is not null and not exists (
    select 1 from public.units
    where id = target_unit_id
      and community_id = request_row.community_id
      and status = 'active'
  ) then
    raise exception 'Selected unit does not belong to this community';
  end if;

  begin
    insert into public.community_memberships(
      community_id, profile_id, role, status, is_default_community
    ) values (
      request_row.community_id,
      request_row.applicant_profile_id,
      'resident',
      'active',
      not exists (
        select 1 from public.community_memberships
        where profile_id = request_row.applicant_profile_id
          and status = 'active'
          and ended_at is null
          and is_default_community
      )
    ) returning id into resident_membership_id;
  exception
    when unique_violation then
      resident_membership_id := null;
  end;

  if resident_membership_id is null then
    select id into resident_membership_id
    from public.community_memberships
    where community_id = request_row.community_id
      and profile_id = request_row.applicant_profile_id
      and role = 'resident'
      and status = 'active'
      and ended_at is null
    limit 1;
    if resident_membership_id is null then
      raise exception 'Applicant already has an incompatible membership';
    end if;
  end if;

  if target_unit_id is not null then
    begin
      insert into public.unit_residencies(
        unit_id, membership_id, relationship_type, created_by_membership_id
      ) values (
        target_unit_id,
        resident_membership_id,
        coalesce(p_relationship, request_row.requested_relationship),
        reviewer_membership_id
      );
    exception
      when unique_violation then null;
    end;
  end if;

  update public.access_requests
  set status = 'approved',
      reviewed_by_membership_id = reviewer_membership_id,
      reviewed_at = now(),
      rejection_reason = null,
      updated_at = now()
  where id = request_row.id;

  return jsonb_build_object(
    'request_id', request_row.id,
    'membership_id', resident_membership_id,
    'status', 'approved'
  );
end;
$$;

revoke all on function public.approve_access_request(uuid, uuid, uuid, public.residency_relationship)
  from public, anon, authenticated;
grant execute on function public.approve_access_request(uuid, uuid, uuid, public.residency_relationship)
  to service_role;

notify pgrst, 'reload schema';
