-- 0005_tenant_rls_and_workflows.sql
--
-- RLS is scoped by community_memberships rather than a global profile role.
-- Browser clients can perform their ordinary owner-scoped reads and writes;
-- membership management, admin transfer, invite redemption, registration
-- approval, and payment recording remain trusted RPC/API workflows.

-- ---------------------------------------------------------------------------
-- Membership-aware authorization helpers
-- ---------------------------------------------------------------------------
create or replace function public.current_user_is_active_member(p_community_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.community_memberships cm
    where cm.community_id = p_community_id
      and cm.profile_id = auth.uid()
      and cm.status = 'active'
      and cm.ended_at is null
  );
$$;

create or replace function public.current_user_has_community_role(
  p_community_id uuid,
  p_roles public.membership_role[]
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.community_memberships cm
    where cm.community_id = p_community_id
      and cm.profile_id = auth.uid()
      and cm.status = 'active'
      and cm.ended_at is null
      and cm.role = any (p_roles)
  );
$$;

create or replace function public.current_user_owns_membership(
  p_membership_id uuid,
  p_community_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.community_memberships cm
    where cm.id = p_membership_id
      and cm.community_id = p_community_id
      and cm.profile_id = auth.uid()
      and cm.status = 'active'
      and cm.ended_at is null
  );
$$;

create or replace function public.current_user_is_active_unit_resident(p_unit_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.unit_residencies ur
    join public.community_memberships cm on cm.id = ur.membership_id
    where ur.unit_id = p_unit_id
      and ur.ended_at is null
      and cm.profile_id = auth.uid()
      and cm.status = 'active'
      and cm.ended_at is null
  );
$$;

create or replace function public.current_user_can_access_work_order(p_work_order_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.work_orders wo
    join public.complaints c on c.id = wo.complaint_id
    where wo.id = p_work_order_id
      and (
        public.current_user_owns_membership(c.raised_by_membership_id, c.community_id)
        or public.current_user_has_community_role(c.community_id, array['manager', 'admin']::public.membership_role[])
        or exists (
          select 1
          from public.work_order_assignments wa
          join public.staff_assignments sa on sa.id = wa.staff_assignment_id
          join public.community_memberships cm on cm.id = sa.membership_id
          where wa.work_order_id = wo.id
            and wa.unassigned_at is null
            and cm.profile_id = auth.uid()
            and cm.status = 'active'
            and cm.ended_at is null
        )
      )
  );
$$;

create or replace function public.current_user_can_access_complaint(p_complaint_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.complaints c
    where c.id = p_complaint_id
      and (
        public.current_user_owns_membership(c.raised_by_membership_id, c.community_id)
        or public.current_user_has_community_role(c.community_id, array['manager', 'admin']::public.membership_role[])
        or exists (
          select 1
          from public.work_orders wo
          join public.work_order_assignments wa on wa.work_order_id = wo.id
          join public.staff_assignments sa on sa.id = wa.staff_assignment_id
          join public.community_memberships cm on cm.id = sa.membership_id
          where wo.complaint_id = c.id
            and wa.unassigned_at is null
            and cm.profile_id = auth.uid()
            and cm.status = 'active'
            and cm.ended_at is null
        )
      )
  );
$$;

create or replace function public.current_user_can_access_visitor(p_visitor_request_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.visitor_access_requests var
    where var.id = p_visitor_request_id
      and (
        public.current_user_owns_membership(var.requested_by_membership_id, var.community_id)
        or public.current_user_is_active_unit_resident(var.unit_id)
        or public.current_user_has_community_role(var.community_id, array['security', 'manager', 'admin']::public.membership_role[])
      )
  );
$$;

create or replace function public.current_user_can_access_booking(p_booking_occurrence_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.amenity_booking_occurrences occurrence
    join public.amenity_booking_series series on series.id = occurrence.booking_series_id
    where occurrence.id = p_booking_occurrence_id
      and (
        public.current_user_owns_membership(series.booked_by_membership_id, series.community_id)
        or public.current_user_has_community_role(series.community_id, array['manager', 'admin']::public.membership_role[])
      )
  );
$$;

create or replace function public.current_user_can_access_invoice(p_invoice_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.invoices i
    where i.id = p_invoice_id
      and (
        public.current_user_is_active_unit_resident(i.liable_unit_id)
        or public.current_user_has_community_role(i.community_id, array['admin']::public.membership_role[])
      )
  );
$$;

revoke all on function public.current_user_is_active_member(uuid) from public;
revoke all on function public.current_user_has_community_role(uuid, public.membership_role[]) from public;
revoke all on function public.current_user_owns_membership(uuid, uuid) from public;
revoke all on function public.current_user_is_active_unit_resident(uuid) from public;
revoke all on function public.current_user_can_access_work_order(uuid) from public;
revoke all on function public.current_user_can_access_complaint(uuid) from public;
revoke all on function public.current_user_can_access_visitor(uuid) from public;
revoke all on function public.current_user_can_access_booking(uuid) from public;
revoke all on function public.current_user_can_access_invoice(uuid) from public;
grant execute on function public.current_user_is_active_member(uuid) to authenticated;
grant execute on function public.current_user_has_community_role(uuid, public.membership_role[]) to authenticated;
grant execute on function public.current_user_owns_membership(uuid, uuid) to authenticated;
grant execute on function public.current_user_is_active_unit_resident(uuid) to authenticated;
grant execute on function public.current_user_can_access_work_order(uuid) to authenticated;
grant execute on function public.current_user_can_access_complaint(uuid) to authenticated;
grant execute on function public.current_user_can_access_visitor(uuid) to authenticated;
grant execute on function public.current_user_can_access_booking(uuid) to authenticated;
grant execute on function public.current_user_can_access_invoice(uuid) to authenticated;

-- Keep the access-token hook useful for coarse FastAPI guards.  The value is
-- never used for tenant authorization: RLS and API services check membership.
create or replace function public.jwt_role()
returns text
language sql
stable
as $$
  select lower(coalesce(
    nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_role',
    ''
  ));
$$;

create or replace function public.is_admin()
returns boolean
language sql
stable
as $$
  select public.jwt_role() = 'admin';
$$;

create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  claims jsonb;
  effective_role text;
begin
  select upper(cm.role::text)
  into effective_role
  from public.community_memberships cm
  where cm.profile_id = (event ->> 'user_id')::uuid
    and cm.status = 'active'
    and cm.ended_at is null
  order by case cm.role
    when 'admin' then 1
    when 'manager' then 2
    when 'security' then 3
    when 'worker' then 4
    else 5
  end
  limit 1;

  claims := event -> 'claims';
  claims := jsonb_set(
    claims,
    '{user_role}',
    to_jsonb(coalesce(effective_role, 'RESIDENT'))
  );
  return jsonb_set(event, '{claims}', claims);
end;
$$;

-- ---------------------------------------------------------------------------
-- RLS activation and removal of global-admin policies from migrations 0001-3.
-- ---------------------------------------------------------------------------
drop policy if exists profiles_self_select on public.profiles;
drop policy if exists profiles_self_update on public.profiles;
drop policy if exists associations_member_read on public.communities;
drop policy if exists associations_admin_write on public.communities;
drop policy if exists units_member_read on public.buildings;
drop policy if exists units_admin_write on public.buildings;
drop policy if exists apartments_member_read on public.units;
drop policy if exists apartments_admin_write on public.units;
drop policy if exists invitations_admin_all on public.resident_invites;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'profiles', 'communities', 'buildings', 'units', 'community_registration_requests',
    'feature_catalog', 'community_features', 'departments', 'community_memberships',
    'community_admin_terms', 'unit_residencies', 'vendors', 'staff_assignments',
    'skills', 'staff_skills', 'worker_availability_rules', 'worker_unavailability',
    'resident_invites', 'access_requests', 'complaints', 'complaint_events',
    'work_orders', 'work_order_assignments', 'work_order_proposals', 'work_order_views',
    'work_order_completion_verifications', 'media_assets', 'work_order_attachments',
    'saved_visitors', 'visitor_access_requests', 'visitor_events', 'visitor_attachments',
    'amenities', 'amenity_rules', 'amenity_booking_series',
    'amenity_booking_occurrences', 'booking_guests', 'amenity_booking_charges',
    'amenity_financial_events', 'invoices', 'invoice_line_items', 'payments',
    'payment_events', 'notices', 'policies', 'policy_revisions', 'notifications',
    'notification_deliveries', 'audit_events'
  ] loop
    execute format('alter table public.%I enable row level security', table_name);
  end loop;
end $$;

-- Identity and shared community directory.  Membership changes are deliberately
-- service/RPC-only; omitting write policies prevents privilege escalation.
create policy profiles_select_self on public.profiles
  for select using (id = auth.uid());

create policy communities_select_member on public.communities
  for select using (public.current_user_is_active_member(id));

create policy buildings_select_member on public.buildings
  for select using (public.current_user_is_active_member(community_id));

create policy units_select_member on public.units
  for select using (public.current_user_is_active_member(community_id));

create policy feature_catalog_select_authenticated on public.feature_catalog
  for select to authenticated using (is_active);

create policy community_features_select_member on public.community_features
  for select using (public.current_user_is_active_member(community_id));

create policy departments_select_member on public.departments
  for select using (public.current_user_is_active_member(community_id));

create policy memberships_select_same_community on public.community_memberships
  for select using (public.current_user_is_active_member(community_id));

create policy admin_terms_select_member on public.community_admin_terms
  for select using (public.current_user_is_active_member(community_id));

create policy unit_residencies_select_member on public.unit_residencies
  for select using (
    exists (
      select 1 from public.units u
      where u.id = unit_residencies.unit_id
        and public.current_user_is_active_member(u.community_id)
    )
  );

create policy vendors_select_manager_or_admin on public.vendors
  for select using (public.current_user_has_community_role(community_id, array['manager', 'admin']::public.membership_role[]));

create policy staff_assignments_select_member on public.staff_assignments
  for select using (
    exists (
      select 1 from public.community_memberships cm
      where cm.id = staff_assignments.membership_id
        and public.current_user_is_active_member(cm.community_id)
    )
  );

create policy skills_select_authenticated on public.skills
  for select to authenticated using (true);

create policy staff_skills_select_member on public.staff_skills
  for select using (
    exists (
      select 1
      from public.staff_assignments sa
      join public.community_memberships cm on cm.id = sa.membership_id
      where sa.id = staff_skills.staff_assignment_id
        and public.current_user_is_active_member(cm.community_id)
    )
  );

create policy availability_select_self_or_manager on public.worker_availability_rules
  for select using (
    exists (
      select 1
      from public.staff_assignments sa
      join public.community_memberships cm on cm.id = sa.membership_id
      where sa.id = worker_availability_rules.staff_assignment_id
        and (cm.profile_id = auth.uid() or public.current_user_has_community_role(cm.community_id, array['manager', 'admin']::public.membership_role[]))
    )
  );

create policy unavailability_select_self_or_manager on public.worker_unavailability
  for select using (
    exists (
      select 1
      from public.staff_assignments sa
      join public.community_memberships cm on cm.id = sa.membership_id
      where sa.id = worker_unavailability.staff_assignment_id
        and (cm.profile_id = auth.uid() or public.current_user_has_community_role(cm.community_id, array['manager', 'admin']::public.membership_role[]))
    )
  );

-- Onboarding and invitation rows are private administrative workflows.
create policy registration_requests_select_admin on public.community_registration_requests
  for select using (
    approved_community_id is not null
    and public.current_user_has_community_role(approved_community_id, array['admin']::public.membership_role[])
  );

create policy resident_invites_select_admin on public.resident_invites
  for select using (public.current_user_has_community_role(community_id, array['admin']::public.membership_role[]));

create policy access_requests_select_admin on public.access_requests
  for select using (public.current_user_has_community_role(community_id, array['admin']::public.membership_role[]));

-- Complaints: the reporter, assigned worker, and manager/admin can read them.
create policy complaints_select_authorized on public.complaints
  for select using (public.current_user_can_access_complaint(id));

create policy complaints_insert_resident on public.complaints
  for insert with check (
    public.current_user_owns_membership(raised_by_membership_id, community_id)
    and public.current_user_has_community_role(community_id, array['resident', 'admin']::public.membership_role[])
  );

create policy complaint_events_select_authorized on public.complaint_events
  for select using (public.current_user_can_access_complaint(complaint_id));

create policy work_orders_select_authorized on public.work_orders
  for select using (public.current_user_can_access_work_order(id));

create policy work_order_assignments_select_authorized on public.work_order_assignments
  for select using (public.current_user_can_access_work_order(work_order_id));

create policy work_order_proposals_select_authorized on public.work_order_proposals
  for select using (public.current_user_can_access_work_order(work_order_id));

create policy work_order_views_select_authorized on public.work_order_views
  for select using (public.current_user_can_access_work_order(work_order_id));

create policy work_order_verifications_select_authorized on public.work_order_completion_verifications
  for select using (public.current_user_can_access_work_order(work_order_id));

create policy media_assets_select_manager_or_admin on public.media_assets
  for select using (public.current_user_has_community_role(community_id, array['manager', 'admin']::public.membership_role[]));

create policy work_order_attachments_select_authorized on public.work_order_attachments
  for select using (public.current_user_can_access_work_order(work_order_id));

-- Visitors: residents have unit-scoped access; security has active operational
-- access; managers/admins can handle exceptions.
create policy saved_visitors_select_owner on public.saved_visitors
  for select using (public.current_user_owns_membership(created_by_membership_id, community_id));

create policy visitor_requests_select_authorized on public.visitor_access_requests
  for select using (public.current_user_can_access_visitor(id));

create policy visitor_requests_insert_resident on public.visitor_access_requests
  for insert with check (
    public.current_user_owns_membership(requested_by_membership_id, community_id)
    and public.current_user_is_active_unit_resident(unit_id)
  );

create policy visitor_events_select_authorized on public.visitor_events
  for select using (public.current_user_can_access_visitor(visitor_access_request_id));

create policy visitor_attachments_select_authorized on public.visitor_attachments
  for select using (public.current_user_can_access_visitor(visitor_access_request_id));

-- Amenities are community-visible, while reservations and their financial data
-- stay with the booking owner or authorised management.
create policy amenities_select_member on public.amenities
  for select using (public.current_user_is_active_member(community_id));

create policy amenity_rules_select_member on public.amenity_rules
  for select using (
    exists (
      select 1 from public.amenities a
      where a.id = amenity_rules.amenity_id
        and public.current_user_is_active_member(a.community_id)
    )
  );

create policy booking_series_select_authorized on public.amenity_booking_series
  for select using (
    public.current_user_owns_membership(booked_by_membership_id, community_id)
    or public.current_user_has_community_role(community_id, array['manager', 'admin']::public.membership_role[])
  );

create policy booking_series_insert_resident on public.amenity_booking_series
  for insert with check (
    public.current_user_owns_membership(booked_by_membership_id, community_id)
    and public.current_user_is_active_unit_resident(liable_unit_id)
  );

create policy booking_occurrences_select_authorized on public.amenity_booking_occurrences
  for select using (public.current_user_can_access_booking(id));

create policy booking_guests_select_authorized on public.booking_guests
  for select using (public.current_user_can_access_booking(booking_occurrence_id));

create policy booking_charges_select_authorized on public.amenity_booking_charges
  for select using (public.current_user_can_access_booking(booking_occurrence_id));

create policy amenity_events_select_authorized on public.amenity_financial_events
  for select using (public.current_user_can_access_booking(booking_occurrence_id));

create policy invoices_select_authorized on public.invoices
  for select using (public.current_user_can_access_invoice(id));

create policy invoice_items_select_authorized on public.invoice_line_items
  for select using (public.current_user_can_access_invoice(invoice_id));

create policy payments_select_authorized on public.payments
  for select using (public.current_user_can_access_invoice(invoice_id));

create policy payment_events_select_authorized on public.payment_events
  for select using (
    exists (
      select 1 from public.payments p
      where p.id = payment_events.payment_id
        and public.current_user_can_access_invoice(p.invoice_id)
    )
  );

-- Community communications and personal notification inboxes.
create policy notices_select_member on public.notices
  for select using (
    public.current_user_is_active_member(community_id)
    and (audience_role is null or public.current_user_has_community_role(community_id, array[audience_role]))
  );

create policy policies_select_manager_or_admin on public.policies
  for select using (public.current_user_has_community_role(community_id, array['manager', 'admin']::public.membership_role[]));

create policy policy_revisions_select_manager_or_admin on public.policy_revisions
  for select using (
    exists (
      select 1 from public.policies p
      where p.id = policy_revisions.policy_id
        and public.current_user_has_community_role(p.community_id, array['manager', 'admin']::public.membership_role[])
    )
  );

create policy notifications_select_recipient on public.notifications
  for select using (public.current_user_owns_membership(recipient_membership_id, community_id));

create policy notifications_mark_read on public.notifications
  for update using (public.current_user_owns_membership(recipient_membership_id, community_id))
  with check (public.current_user_owns_membership(recipient_membership_id, community_id));

create policy deliveries_select_recipient on public.notification_deliveries
  for select using (
    exists (
      select 1 from public.notifications n
      where n.id = notification_deliveries.notification_id
        and public.current_user_owns_membership(n.recipient_membership_id, n.community_id)
    )
  );

create policy audit_events_select_manager_or_admin on public.audit_events
  for select using (public.current_user_has_community_role(community_id, array['manager', 'admin']::public.membership_role[]));

-- ---------------------------------------------------------------------------
-- Privileged, transactionally-safe workflows.  These are not directly exposed
-- to anon/authenticated roles unless explicitly granted below.
-- ---------------------------------------------------------------------------
create or replace function public.transfer_community_admin(
  p_community_id uuid,
  p_successor_membership_id uuid,
  p_transfer_note text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  caller_membership_id uuid;
  previous_term public.community_admin_terms%rowtype;
  successor_previous_role public.membership_role;
begin
  select cm.id into caller_membership_id
  from public.community_memberships cm
  where cm.community_id = p_community_id
    and cm.profile_id = auth.uid()
    and cm.role = 'admin'
    and cm.status = 'active'
    and cm.ended_at is null;

  if caller_membership_id is null then
    raise exception 'Only the active community admin can transfer administration';
  end if;

  select * into previous_term
  from public.community_admin_terms
  where community_id = p_community_id and ended_at is null
  for update;

  if previous_term.id is null then
    raise exception 'Community has no active admin term';
  end if;

  select role into successor_previous_role
  from public.community_memberships
  where id = p_successor_membership_id
    and community_id = p_community_id
    and status = 'active'
    and ended_at is null
  for update;

  if successor_previous_role is null then
    raise exception 'Successor must be an active membership in the same community';
  end if;
  if p_successor_membership_id = caller_membership_id then
    raise exception 'Successor must be a different membership';
  end if;

  update public.community_admin_terms
  set ended_at = now(),
      transferred_by_membership_id = caller_membership_id,
      transfer_note = p_transfer_note
  where id = previous_term.id;

  update public.community_memberships
  set role = previous_term.role_before_term,
      updated_at = now()
  where id = caller_membership_id;

  update public.community_memberships
  set role = 'admin', updated_at = now()
  where id = p_successor_membership_id;

  insert into public.community_admin_terms (
    community_id, admin_membership_id, role_before_term, started_at,
    transferred_by_membership_id, transfer_note
  ) values (
    p_community_id, p_successor_membership_id, successor_previous_role, now(),
    caller_membership_id, p_transfer_note
  );
end;
$$;

create or replace function public.claim_resident_invite(
  p_invite_id uuid,
  p_profile_id uuid
)
returns table (
  membership_id uuid,
  community_id uuid,
  unit_id uuid
)
language plpgsql
security definer
set search_path = public
as $$
declare
  invite public.resident_invites%rowtype;
  created_membership_id uuid;
begin
  select * into invite
  from public.resident_invites
  where id = p_invite_id
  for update;

  if invite.id is null or invite.status <> 'issued' then
    raise exception 'Invite is not redeemable';
  end if;
  if invite.expires_at <= now() then
    update public.resident_invites set status = 'expired' where id = invite.id;
    raise exception 'Invite has expired';
  end if;
  if invite.intended_role <> 'resident' or invite.intended_unit_id is null then
    raise exception 'Invite is not a complete resident invite';
  end if;

  insert into public.community_memberships (
    community_id, profile_id, role, status, joined_at, is_default_community
  ) values (
    invite.community_id, p_profile_id, 'resident', 'active', now(), true
  ) returning id into created_membership_id;

  insert into public.unit_residencies (
    unit_id, membership_id, relationship_type, is_primary_contact, started_at
  ) values (
    invite.intended_unit_id, created_membership_id, 'tenant', false, current_date
  );

  update public.resident_invites
  set status = 'redeemed', redeemed_at = now(), redeemed_by_profile_id = p_profile_id
  where id = invite.id;

  return query select created_membership_id, invite.community_id, invite.intended_unit_id;
end;
$$;

create or replace function public.approve_access_request(
  p_access_request_id uuid,
  p_profile_id uuid,
  p_default_invoice_amount numeric(12, 2),
  p_due_at timestamptz
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  request_row public.access_requests%rowtype;
  approver_membership_id uuid;
  new_membership_id uuid;
  invoice_id uuid;
begin
  select * into request_row
  from public.access_requests
  where id = p_access_request_id
  for update;

  if request_row.id is null or request_row.status <> 'pending' then
    raise exception 'Access request is not pending';
  end if;
  if request_row.requested_unit_id is null then
    raise exception 'Access request needs a unit before approval';
  end if;

  select cm.id into approver_membership_id
  from public.community_memberships cm
  where cm.community_id = request_row.community_id
    and cm.profile_id = auth.uid()
    and cm.role = 'admin'
    and cm.status = 'active'
    and cm.ended_at is null;
  if approver_membership_id is null then
    raise exception 'Only the community admin can approve an access request';
  end if;

  insert into public.community_memberships (
    community_id, profile_id, role, status, joined_at, is_default_community
  ) values (
    request_row.community_id, p_profile_id, 'resident', 'active', now(), true
  ) returning id into new_membership_id;

  insert into public.unit_residencies (
    unit_id, membership_id, relationship_type, is_primary_contact, started_at,
    created_by_membership_id
  ) values (
    request_row.requested_unit_id, new_membership_id,
    request_row.requested_relationship, false, current_date, approver_membership_id
  );

  insert into public.invoices (
    community_id, liable_unit_id, invoice_number, invoice_type, status,
    issued_at, due_at, subtotal, tax_amount, total_amount, created_by_membership_id
  ) values (
    request_row.community_id, request_row.requested_unit_id,
    'MNT-' || to_char(now(), 'YYYYMMDD') || '-' || replace(p_access_request_id::text, '-', ''),
    'maintenance', 'issued', now(), p_due_at,
    p_default_invoice_amount, 0, p_default_invoice_amount, approver_membership_id
  ) returning id into invoice_id;

  update public.access_requests
  set status = 'approved', reviewed_by_membership_id = approver_membership_id,
      reviewed_at = now(), created_profile_id = p_profile_id
  where id = request_row.id;

  return invoice_id;
end;
$$;

revoke all on function public.claim_resident_invite(uuid, uuid) from public, anon, authenticated;
revoke all on function public.approve_access_request(uuid, uuid, numeric, timestamptz) from public, anon, authenticated;
revoke all on function public.transfer_community_admin(uuid, uuid, text) from public, anon;
grant execute on function public.transfer_community_admin(uuid, uuid, text) to authenticated;

-- Private Storage bucket.  All object keys must begin with the community UUID,
-- for example: <community-id>/complaints/<complaint-id>/<asset-id>.jpg.
insert into storage.buckets (id, name, public)
values ('community-media', 'community-media', false)
on conflict (id) do update set public = false;

drop policy if exists community_media_select on storage.objects;
drop policy if exists community_media_insert on storage.objects;
drop policy if exists community_media_delete on storage.objects;

create policy community_media_select on storage.objects
  for select to authenticated
  using (
    bucket_id = 'community-media'
    and public.current_user_is_active_member((storage.foldername(name))[1]::uuid)
  );

create policy community_media_insert on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'community-media'
    and public.current_user_is_active_member((storage.foldername(name))[1]::uuid)
  );

create policy community_media_delete on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'community-media'
    and public.current_user_has_community_role(
      (storage.foldername(name))[1]::uuid,
      array['manager', 'admin']::public.membership_role[]
    )
  );
