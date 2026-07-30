-- 0012_people.sql
-- Registration requests, the admin designation, profiles.email, and the RPCs
-- that make multi-table people operations atomic.
--
-- Depends on 0010_memberships.sql and 0011_dashboard_core.sql.
-- Numbering: 0004-0009 belong to the auth/security workstream (build plan 1.4).
--
-- ===========================================================================
-- WHY THERE ARE FUNCTIONS IN HERE AND NOT JUST TABLES
--
-- PostgREST -- which is what supabase-py speaks -- has NO client-side
-- transaction. Each .table(...).insert()/.update() is its own statement and its
-- own transaction. So any operation spanning two tables from FastAPI is *not*
-- atomic, and a failure halfway leaves the database inconsistent.
--
-- Approving a registration is exactly that shape: mark the request approved AND
-- create the invitation. A crash between them either loses the invite (a request
-- approved that nobody can act on) or double-approves. The only way to get
-- atomicity through PostgREST is to put the whole operation in one Postgres
-- function and call it via RPC. That is what the three functions below are for.
--
-- The build plan's step 4 line -- "approve creates residency AND first invoice in
-- one transaction" -- is the same requirement; the invoice half arrives with the
-- money tables in step 7 and slots into approve_registration_request() then.
--
-- SECURITY NOTE: these are SECURITY DEFINER, so RLS does NOT protect them. Each
-- one therefore performs its OWN authorization check as its first act. A
-- SECURITY DEFINER function without an explicit check is a hole with an API in
-- front of it.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Custom SQLSTATEs so the API can map failures to HTTP codes without matching
-- on message text, which would break the first time someone rewords a message.
--   HB403 - caller is not permitted
--   HB404 - the row does not exist
--   HB409 - the row exists but is not in a state that allows the operation
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- profiles.email
--
-- The Residents screen renders an email address, and `profiles` had nowhere to
-- put one -- it lives in auth.users, which needs the service-role key to read,
-- so the API was returning null for it.
--
-- Backfilled here from auth.users because this migration runs as the table owner
-- and can read the auth schema. KEEPING it in sync for NEW users belongs in
-- handle_new_user(), which is owned by the auth/security workstream -- so it is
-- NOT edited here. Until they add it, the API writes the address on the paths it
-- controls. Listed as a coordination item in the build plan.
-- ---------------------------------------------------------------------------
alter table public.profiles add column if not exists email text;

create index if not exists profiles_email_idx on public.profiles (lower(email))
  where email is not null;

update public.profiles p
   set email = u.email
  from auth.users u
 where u.id = p.id
   and p.email is null
   and u.email is not null;

-- ---------------------------------------------------------------------------
-- community_memberships.designation
--
-- The frontend offers President / Secretary / Treasurer / Committee Member /
-- Association Manager / Other (frontend/src/data/adminDesignations.js). This is
-- a THIRD axis, distinct from both `role` (what the system permits) and staff
-- `job_title` (what a worker does) -- it is the office a person holds in the
-- residents' association. Free text with no check constraint: the list is a
-- frontend display vocabulary that will grow, and a constraint would turn every
-- addition into a migration.
-- ---------------------------------------------------------------------------
alter table public.community_memberships add column if not exists designation text;

-- ---------------------------------------------------------------------------
-- registration_requests
--
-- Self-signup requests awaiting admin approval. Only the ADMIN-FACING half is
-- built here (list / approve / reject) -- submitting a request is part of
-- registration, which is explicitly out of scope for this workstream.
-- ---------------------------------------------------------------------------
create table if not exists public.registration_requests (
  id                        uuid primary key default gen_random_uuid(),
  community_id              uuid not null references public.associations(id) on delete cascade,
  full_name                 text not null,
  email                     text,
  phone                     text not null,
  -- Normalised to the full flat code ('C-505'), never tower + number separately.
  -- The frontend stores these two ways in two places; see the API layer's
  -- normalisation and FRONTEND_MEETING_AGENDA.md item 8.
  requested_unit_code       text not null,
  status                    text not null default 'pending',
  reviewed_by_membership_id uuid,
  reviewed_at               timestamptz,
  rejection_reason          text,
  invitation_id             uuid references public.invitations(id) on delete set null,
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now(),
  constraint registration_requests_status_ck
    check (status in ('pending', 'approved', 'rejected')),
  constraint registration_requests_reviewer_fk
    foreign key (reviewed_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (reviewed_by_membership_id)
);

-- One OPEN request per phone per community. Partial, so a rejected applicant may
-- apply again and the history of both attempts survives.
create unique index if not exists registration_requests_open_uq
  on public.registration_requests (community_id, phone) where status = 'pending';

create index if not exists registration_requests_pending_idx
  on public.registration_requests (community_id, created_at desc) where status = 'pending';

drop trigger if exists registration_requests_set_updated_at on public.registration_requests;
create trigger registration_requests_set_updated_at
  before update on public.registration_requests
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- approve_registration_request
--
-- Marks the request approved and mints an invitation, atomically.
--
-- WHY AN INVITATION RATHER THAN AN ACTIVE ACCOUNT: the frontend's acceptRequest()
-- creates a fully Active resident immediately. We cannot, and should not -- the
-- standing ruling is that the invite token is a mandatory second factor. An
-- approved applicant receives an invite they redeem; approval alone does not
-- hand out an account. The admin still sees the request leave the pending list,
-- which is what the screen actually reacts to.
--
-- The token/code are minted and hashed by the API (app/core/tokens.py); only
-- their digests cross this boundary, so plaintext secrets never enter a query
-- log or a database backup.
-- ---------------------------------------------------------------------------
create or replace function public.approve_registration_request(
  p_request_id             uuid,
  p_token_hash             text,
  p_code_hash              text,
  p_expires_at             timestamptz,
  p_reviewer_membership_id uuid,
  p_created_by             uuid
)
returns table (invitation_id uuid, phone text, unit_code text, full_name text)
language plpgsql
security definer
set search_path = public
as $$
declare
  req public.registration_requests%rowtype;
  new_invitation_id uuid;
begin
  -- FOR UPDATE: two admins clicking Approve at the same moment must serialise,
  -- or both pass the status check and two invitations get minted for one flat.
  select * into req
    from public.registration_requests
   where id = p_request_id
   for update;

  if not found then
    raise exception 'Registration request not found.' using errcode = 'HB404';
  end if;

  -- Authorization, explicitly: SECURITY DEFINER means RLS did not run.
  -- auth.uid() and the JWT claims are request-scoped and still reflect the
  -- real caller here, so is_admin() is meaningful.
  if not public.is_admin()
     or req.community_id not in (select public.current_community_ids()) then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;

  if req.status <> 'pending' then
    raise exception 'This request has already been reviewed.' using errcode = 'HB409';
  end if;

  -- Find-or-create the flat: the frontend has no flat-creation step, so a
  -- request may name a unit that does not exist yet.
  insert into public.apartments (association_id, code)
  values (req.community_id, req.requested_unit_code)
  on conflict (association_id, code) do nothing;

  insert into public.invitations (
    token_hash, code_hash, phone, apartment_id, role,
    association_id, full_name, created_by, expires_at
  )
  values (
    p_token_hash, p_code_hash, req.phone, req.requested_unit_code, 'RESIDENT',
    req.community_id, req.full_name, p_created_by, p_expires_at
  )
  returning id into new_invitation_id;

  update public.registration_requests
     set status = 'approved',
         reviewed_by_membership_id = p_reviewer_membership_id,
         reviewed_at = now(),
         invitation_id = new_invitation_id
   where id = p_request_id;

  return query
    select new_invitation_id, req.phone, req.requested_unit_code, req.full_name;
end;
$$;

-- ---------------------------------------------------------------------------
-- reject_registration_request -- single table, but kept an RPC for the same
-- authorization and compare-and-set guarantees as approve.
-- ---------------------------------------------------------------------------
create or replace function public.reject_registration_request(
  p_request_id             uuid,
  p_reason                 text,
  p_reviewer_membership_id uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  req public.registration_requests%rowtype;
begin
  select * into req
    from public.registration_requests
   where id = p_request_id
   for update;

  if not found then
    raise exception 'Registration request not found.' using errcode = 'HB404';
  end if;

  if not public.is_admin()
     or req.community_id not in (select public.current_community_ids()) then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;

  if req.status <> 'pending' then
    raise exception 'This request has already been reviewed.' using errcode = 'HB409';
  end if;

  update public.registration_requests
     set status = 'rejected',
         rejection_reason = p_reason,
         reviewed_by_membership_id = p_reviewer_membership_id,
         reviewed_at = now()
   where id = p_request_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- deactivate_membership
--
-- "Remove resident" is a DEACTIVATION, not a delete. The frontend drops the user
-- from an array; a real backend must not, because complaints, invoices and
-- payments reference the membership and a hard delete would either cascade them
-- away or fail. Deactivating also ends the open residency so the flat reads as
-- vacant.
--
-- Two tables, so it is an RPC for the atomicity reason at the top of this file.
-- The trigger from 0010 then projects the change onto profiles.role.
-- ---------------------------------------------------------------------------
create or replace function public.deactivate_membership(p_membership_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  mem public.community_memberships%rowtype;
begin
  select * into mem
    from public.community_memberships
   where id = p_membership_id
   for update;

  if not found then
    raise exception 'Member not found.' using errcode = 'HB404';
  end if;

  if not public.is_admin()
     or mem.community_id not in (select public.current_community_ids()) then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;

  -- An admin removing themselves would lock the community out of its own
  -- dashboard, and there is no recovery path in the product.
  if mem.profile_id = auth.uid() then
    raise exception 'You cannot remove your own membership.' using errcode = 'HB409';
  end if;

  update public.unit_residencies
     set end_date = current_date, is_primary = false
   where membership_id = p_membership_id
     and end_date is null;

  update public.community_memberships
     set status = 'inactive'
   where id = p_membership_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- Grants. anon must not reach any of these -- every one is an admin operation.
-- ---------------------------------------------------------------------------
revoke execute on function
  public.approve_registration_request(uuid, text, text, timestamptz, uuid, uuid)
  from public, anon;
revoke execute on function
  public.reject_registration_request(uuid, text, uuid) from public, anon;
revoke execute on function public.deactivate_membership(uuid) from public, anon;

grant execute on function
  public.approve_registration_request(uuid, text, text, timestamptz, uuid, uuid)
  to authenticated;
grant execute on function
  public.reject_registration_request(uuid, text, uuid) to authenticated;
grant execute on function public.deactivate_membership(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------
alter table public.registration_requests enable row level security;

drop policy if exists registration_requests_admin_read on public.registration_requests;
create policy registration_requests_admin_read on public.registration_requests
  for select using (
    public.is_admin() and community_id in (select public.current_community_ids())
  );

drop policy if exists registration_requests_admin_write on public.registration_requests;
create policy registration_requests_admin_write on public.registration_requests
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

-- ---------------------------------------------------------------------------
-- Verification -- run after applying.
-- ---------------------------------------------------------------------------
-- Emails backfilled (expect the count of auth users that have an address):
--   select count(*) from public.profiles where email is not null;
--
-- No community has two pending requests for one phone (expect zero rows; the
-- partial unique index should make this impossible):
--   select community_id, phone, count(*) from public.registration_requests
--   where status = 'pending' group by community_id, phone having count(*) > 1;
--
-- Every reviewed request has a reviewer and a timestamp (expect zero rows):
--   select id from public.registration_requests
--   where status <> 'pending' and (reviewed_at is null or reviewed_by_membership_id is null);
