-- Residents may close their own checked-in visit, including an expired entry
-- window. The whole pass/group leaves together; this does not count departures
-- per guest. Apply before deploying the resident checkout endpoint.
create or replace function public.checkout_visitor_pass(
  p_membership_id uuid,
  p_pass_id uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.visitor_requests%rowtype;
  v_community uuid;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'An active membership is required.' using errcode = 'HB403';
  end if;

  select community_id into v_community
    from public.community_memberships where id = p_membership_id;

  -- Match ownership before locking; another resident's pass is indistinguishable
  -- from a missing one. The lock also serializes against verify_gate_credential.
  select * into v_row
    from public.visitor_requests
   where id = p_pass_id
     and requested_by_membership_id = p_membership_id
     and community_id = v_community
   for update;
  if not found then
    raise exception 'Visitor pass not found.' using errcode = 'HB404';
  end if;

  -- Retrying after a lost response or a concurrent gate checkout is a no-op.
  if v_row.status = 'checked_out' then
    return;
  end if;
  if v_row.status <> 'checked_in' then
    raise exception 'Only a checked-in visit can be checked out.' using errcode = 'HB409';
  end if;

  update public.visitor_requests
     set status = 'checked_out', checked_out_at = clock_timestamp(), updated_at = now()
   where id = p_pass_id;
  insert into public.visitor_events (visitor_request_id, actor_membership_id, event_type)
  values (p_pass_id, p_membership_id, 'checked_out');

  perform public.notify_community_roles(
    v_community, array['security', 'admin'], 'visitor.checked_out',
    jsonb_build_object(
      'title', 'Resident recorded visitor checkout',
      'body', v_row.visitor_name,
      'url', '/security',
      'pass_id', p_pass_id
    ),
    p_membership_id
  );
end;
$$;

comment on function public.checkout_visitor_pass(uuid, uuid) is
  'Close your own checked-in visitor group. Idempotent, audited, and allowed after entry expiry.';
revoke all on function public.checkout_visitor_pass(uuid, uuid) from public, anon;
grant execute on function public.checkout_visitor_pass(uuid, uuid) to authenticated;
