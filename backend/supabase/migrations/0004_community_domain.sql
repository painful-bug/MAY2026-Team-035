-- 0004_community_domain.sql
--
-- HomeBandhu's original three migrations establish Supabase Auth, a simple
-- association/apartment model, and one-time resident invitations.  This
-- forward-only migration evolves that baseline into the tenant-safe domain
-- model used by the application.  It deliberately retains a few
-- `legacy_*` profile columns until a post-deployment data audit confirms that
-- every historic row was backfilled; no resident data is discarded here.

create extension if not exists btree_gist;
create extension if not exists citext;

-- ---------------------------------------------------------------------------
-- Canonical tenancy names.  Postgres updates foreign-key dependencies when a
-- referenced table or column is renamed.
-- ---------------------------------------------------------------------------
alter table public.associations rename to communities;
alter table public.units rename to buildings;
alter table public.apartments rename to units;
alter table public.invitations rename to resident_invites;

alter table public.buildings rename column association_id to community_id;
alter table public.buildings rename column kind to building_type;
alter table public.units rename column association_id to community_id;
alter table public.units rename column unit_id to building_id;
alter table public.units rename column code to unit_code;
alter table public.resident_invites rename column association_id to community_id;

-- Preserve the old profile placement temporarily while membership rows are
-- populated below.  Runtime code must use the new membership/residency tables.
alter table public.profiles rename column role to legacy_role;
alter table public.profiles rename column phone to phone_e164;
alter table public.profiles rename column apartment_id to legacy_unit_code;
alter table public.profiles rename column association_id to legacy_community_id;
alter table public.profiles add column if not exists display_email citext;
alter table public.profiles add column if not exists is_active boolean not null default true;
alter table public.profiles add column if not exists avatar_media_id uuid;
update public.profiles set is_active = lower(status) = 'active';

-- The old trigger wrote role and apartment columns.  New users are identities;
-- a trusted workflow creates their membership and residency deliberately.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, phone_e164, display_email)
  values (
    new.id,
    new.raw_user_meta_data ->> 'full_name',
    new.phone,
    new.email
  )
  on conflict (id) do update
    set full_name = coalesce(excluded.full_name, public.profiles.full_name),
        phone_e164 = coalesce(excluded.phone_e164, public.profiles.phone_e164),
        display_email = coalesce(excluded.display_email, public.profiles.display_email),
        updated_at = now();
  return new;
end;
$$;

update public.profiles p
set display_email = u.email
from auth.users u
where p.id = u.id and p.display_email is null and u.email is not null;

create unique index if not exists profiles_phone_e164_unique
  on public.profiles (phone_e164) where phone_e164 is not null;

-- ---------------------------------------------------------------------------
-- Domain enums
-- ---------------------------------------------------------------------------
do $$ begin
  create type public.membership_role as enum (
    'resident', 'worker', 'security', 'manager', 'admin'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.membership_status as enum (
    'pending', 'active', 'suspended', 'ended'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.residency_relationship as enum (
    'owner', 'tenant', 'family_member', 'caregiver', 'other'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.request_status as enum (
    'pending', 'approved', 'rejected', 'cancelled'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.invite_status as enum (
    'issued', 'redeemed', 'revoked', 'expired'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.complaint_status as enum (
    'open', 'acknowledged', 'in_progress', 'resolved', 'closed', 'cancelled'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.visitor_status as enum (
    'expected', 'pending_approval', 'approved', 'denied', 'checked_in',
    'checked_out', 'expired', 'cancelled'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.booking_status as enum (
    'requested', 'approved', 'rejected', 'cancelled', 'completed', 'no_show'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.invoice_status as enum (
    'draft', 'issued', 'partially_paid', 'paid', 'overdue', 'void'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.payment_status as enum (
    'initiated', 'succeeded', 'failed', 'refunded'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.media_status as enum (
    'pending', 'active', 'quarantined', 'deleted'
  );
exception when duplicate_object then null;
end $$;

-- ---------------------------------------------------------------------------
-- Community structure and feature configuration
-- ---------------------------------------------------------------------------
alter table public.communities
  add column if not exists address_line1 text,
  add column if not exists city text,
  add column if not exists state text,
  add column if not exists postal_code text,
  add column if not exists timezone text not null default 'Asia/Kolkata',
  add column if not exists updated_at timestamptz not null default now();

alter table public.buildings
  add column if not exists code text,
  add column if not exists map_x numeric(8, 5),
  add column if not exists map_y numeric(8, 5),
  add column if not exists updated_at timestamptz not null default now();
update public.buildings set code = coalesce(code, name);
alter table public.buildings alter column code set not null;
create unique index if not exists buildings_community_code_unique
  on public.buildings (community_id, code);

alter table public.units
  add column if not exists unit_type text not null default 'flat',
  add column if not exists floor_number text,
  add column if not exists map_x numeric(8, 5),
  add column if not exists map_y numeric(8, 5),
  add column if not exists status text not null default 'active',
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

create table public.community_registration_requests (
  id uuid primary key default gen_random_uuid(),
  requested_name text not null,
  requested_community_type text not null check (requested_community_type in ('apartment', 'layout_villa')),
  contact_full_name text not null,
  contact_email citext not null,
  contact_phone_e164 varchar(20) not null,
  requested_address text,
  otp_verified_at timestamptz,
  status public.request_status not null default 'pending',
  review_note text,
  reviewed_at timestamptz,
  approved_community_id uuid unique references public.communities(id) on delete set null,
  submitted_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.feature_catalog (
  code text primary key,
  name text not null,
  description text not null,
  default_enabled boolean not null default false,
  is_active boolean not null default true
);

insert into public.feature_catalog (code, name, description, default_enabled) values
  ('resident-management', 'Resident Management', 'Manage residents and their profiles.', true),
  ('visitor-management', 'Visitor Management', 'Approve and track visitors.', true),
  ('complaint-management', 'Complaint Management', 'Residents can raise complaints.', true),
  ('maintenance-billing', 'Maintenance and Billing', 'Track maintenance payments and dues.', true),
  ('notice-board', 'Notice Board', 'Publish announcements.', true),
  ('amenities-booking', 'Amenities Booking', 'Book shared facilities.', false),
  ('security-gate-management', 'Security and Gate Management', 'Track gate entry and security logs.', false),
  ('parking-management', 'Parking Management', 'Manage resident and visitor parking.', false),
  ('staff-management', 'Staff Management', 'Manage operational staff.', false),
  ('community-marketplace', 'Community Marketplace', 'Resident buy, sell, and exchange listings.', false)
on conflict (code) do update
  set name = excluded.name,
      description = excluded.description,
      default_enabled = excluded.default_enabled;

create table public.community_features (
  community_id uuid not null references public.communities(id) on delete cascade,
  feature_code text not null references public.feature_catalog(code),
  is_enabled boolean not null,
  updated_by_membership_id uuid,
  updated_at timestamptz not null default now(),
  primary key (community_id, feature_code)
);

-- ---------------------------------------------------------------------------
-- Membership, residency, and staffing
-- ---------------------------------------------------------------------------
create table public.departments (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  name text not null,
  description text,
  manager_membership_id uuid,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (community_id, name)
);

create table public.community_memberships (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  department_id uuid references public.departments(id) on delete set null,
  role public.membership_role not null,
  status public.membership_status not null default 'pending',
  joined_at timestamptz not null default now(),
  ended_at timestamptz,
  is_default_community boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((status = 'ended') = (ended_at is not null))
);

create unique index community_memberships_one_active_per_community
  on public.community_memberships (community_id, profile_id)
  where status in ('pending', 'active', 'suspended') and ended_at is null;

create unique index community_memberships_one_active_resident
  on public.community_memberships (profile_id)
  where role = 'resident' and status = 'active' and ended_at is null;

create unique index community_memberships_one_default
  on public.community_memberships (profile_id)
  where is_default_community and status = 'active' and ended_at is null;

create table public.community_admin_terms (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  admin_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  role_before_term public.membership_role not null default 'resident',
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  transferred_by_membership_id uuid references public.community_memberships(id) on delete set null,
  transfer_note text,
  created_at timestamptz not null default now(),
  check (ended_at is null or ended_at >= started_at)
);

create unique index community_admin_terms_one_active_admin
  on public.community_admin_terms (community_id)
  where ended_at is null;

create table public.unit_residencies (
  id uuid primary key default gen_random_uuid(),
  unit_id uuid not null references public.units(id) on delete cascade,
  membership_id uuid not null references public.community_memberships(id) on delete cascade,
  relationship_type public.residency_relationship not null,
  is_primary_contact boolean not null default false,
  started_at date not null default current_date,
  ended_at date,
  nominated_successor_residency_id uuid references public.unit_residencies(id) on delete set null,
  created_by_membership_id uuid references public.community_memberships(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (ended_at is null or ended_at >= started_at)
);

create unique index unit_residencies_one_active_primary_contact
  on public.unit_residencies (unit_id)
  where is_primary_contact and ended_at is null;

create unique index unit_residencies_one_active_membership_unit
  on public.unit_residencies (unit_id, membership_id)
  where ended_at is null;

create table public.vendors (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  name text not null,
  contact_name text,
  phone_e164 varchar(20),
  email citext,
  service_category text,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.staff_assignments (
  id uuid primary key default gen_random_uuid(),
  membership_id uuid not null references public.community_memberships(id) on delete cascade,
  department_id uuid references public.departments(id) on delete set null,
  vendor_id uuid references public.vendors(id) on delete set null,
  employment_type text not null check (employment_type in ('internal', 'vendor')),
  designation text,
  started_at date not null default current_date,
  ended_at date,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (ended_at is null or ended_at >= started_at)
);

create table public.skills (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  category text,
  description text
);

create table public.staff_skills (
  staff_assignment_id uuid not null references public.staff_assignments(id) on delete cascade,
  skill_id uuid not null references public.skills(id) on delete restrict,
  proficiency_level smallint check (proficiency_level between 1 and 5),
  is_primary boolean not null default false,
  primary key (staff_assignment_id, skill_id)
);

create table public.worker_availability_rules (
  id uuid primary key default gen_random_uuid(),
  staff_assignment_id uuid not null references public.staff_assignments(id) on delete cascade,
  weekday smallint not null check (weekday between 0 and 6),
  start_time time not null,
  end_time time not null,
  effective_from date not null default current_date,
  effective_to date,
  created_at timestamptz not null default now(),
  check (end_time > start_time),
  check (effective_to is null or effective_to >= effective_from)
);

create table public.worker_unavailability (
  id uuid primary key default gen_random_uuid(),
  staff_assignment_id uuid not null references public.staff_assignments(id) on delete cascade,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  reason text,
  created_at timestamptz not null default now(),
  check (ends_at > starts_at)
);

alter table public.departments
  add constraint departments_manager_membership_fkey
  foreign key (manager_membership_id) references public.community_memberships(id) on delete set null;

alter table public.community_features
  add constraint community_features_updated_by_membership_fkey
  foreign key (updated_by_membership_id) references public.community_memberships(id) on delete set null;

-- ---------------------------------------------------------------------------
-- Identity onboarding: resident self-registration and one-time invitations
-- ---------------------------------------------------------------------------
alter table public.resident_invites
  rename column phone to invitee_phone_e164;
alter table public.resident_invites
  rename column full_name to invitee_name;
alter table public.resident_invites
  rename column created_by to legacy_created_by_profile_id;
alter table public.resident_invites
  rename column apartment_id to legacy_unit_code;
alter table public.resident_invites
  rename column role to legacy_role;
alter table public.resident_invites
  add column if not exists intended_unit_id uuid references public.units(id) on delete restrict,
  add column if not exists invitee_email citext,
  add column if not exists intended_role public.membership_role not null default 'resident',
  add column if not exists status public.invite_status not null default 'issued',
  add column if not exists redeemed_by_profile_id uuid references public.profiles(id) on delete set null,
  add column if not exists created_by_membership_id uuid references public.community_memberships(id) on delete set null,
  add column if not exists updated_at timestamptz not null default now();

update public.resident_invites ri
set intended_unit_id = u.id
from public.units u
where ri.intended_unit_id is null
  and u.community_id = ri.community_id
  and u.unit_code = ri.legacy_unit_code;

update public.resident_invites
set intended_role = case legacy_role::text
  when 'TECHNICIAN' then 'worker'::public.membership_role
  when 'SECURITY' then 'security'::public.membership_role
  when 'MANAGER' then 'manager'::public.membership_role
  when 'ADMIN' then 'admin'::public.membership_role
  else 'resident'::public.membership_role
end,
status = case
  when redeemed_at is not null then 'redeemed'::public.invite_status
  when expires_at <= now() then 'expired'::public.invite_status
  else 'issued'::public.invite_status
end;

create unique index resident_invites_one_active_phone
  on public.resident_invites (community_id, invitee_phone_e164)
  where status = 'issued';

create unique index resident_invites_code_hash_unique
  on public.resident_invites (code_hash);

create index resident_invites_intended_unit_idx
  on public.resident_invites (intended_unit_id);

create table public.access_requests (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  requested_unit_id uuid references public.units(id) on delete set null,
  applicant_name text not null,
  applicant_email citext,
  applicant_phone_e164 varchar(20) not null,
  requested_relationship public.residency_relationship not null default 'tenant',
  status public.request_status not null default 'pending',
  reviewed_by_membership_id uuid references public.community_memberships(id) on delete set null,
  reviewed_at timestamptz,
  rejection_reason text,
  created_profile_id uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index access_requests_one_open_phone
  on public.access_requests (community_id, applicant_phone_e164)
  where status = 'pending';

-- ---------------------------------------------------------------------------
-- Complaints and work orders
-- ---------------------------------------------------------------------------
create table public.complaints (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  unit_id uuid references public.units(id) on delete set null,
  raised_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  title text not null,
  description text not null,
  category text not null,
  priority text not null default 'low',
  status public.complaint_status not null default 'open',
  progress_percent smallint not null default 0 check (progress_percent between 0 and 100),
  resolved_at timestamptz,
  closed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.complaint_events (
  id uuid primary key default gen_random_uuid(),
  complaint_id uuid not null references public.complaints(id) on delete cascade,
  actor_membership_id uuid references public.community_memberships(id) on delete set null,
  event_type text not null,
  previous_status public.complaint_status,
  new_status public.complaint_status,
  note text,
  created_at timestamptz not null default now()
);

create table public.work_orders (
  id uuid primary key default gen_random_uuid(),
  complaint_id uuid not null references public.complaints(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  title text not null,
  description text,
  status text not null default 'open',
  scheduled_start_at timestamptz,
  scheduled_end_at timestamptz,
  completed_at timestamptz,
  created_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (scheduled_end_at is null or scheduled_start_at is null or scheduled_end_at > scheduled_start_at)
);

create table public.work_order_assignments (
  id uuid primary key default gen_random_uuid(),
  work_order_id uuid not null references public.work_orders(id) on delete cascade,
  staff_assignment_id uuid not null references public.staff_assignments(id) on delete restrict,
  assigned_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  assignment_status text not null default 'assigned',
  assigned_at timestamptz not null default now(),
  unassigned_at timestamptz,
  unique (work_order_id, staff_assignment_id)
);

create table public.work_order_proposals (
  id uuid primary key default gen_random_uuid(),
  work_order_id uuid not null references public.work_orders(id) on delete cascade,
  proposed_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  proposed_start_at timestamptz,
  proposed_end_at timestamptz,
  proposed_amount numeric(12, 2),
  currency char(3) not null default 'INR',
  status text not null default 'proposed',
  responded_by_membership_id uuid references public.community_memberships(id) on delete set null,
  responded_at timestamptz,
  note text,
  created_at timestamptz not null default now(),
  check (proposed_end_at is null or proposed_start_at is null or proposed_end_at > proposed_start_at)
);

create table public.work_order_views (
  id uuid primary key default gen_random_uuid(),
  work_order_id uuid not null references public.work_orders(id) on delete cascade,
  membership_id uuid not null references public.community_memberships(id) on delete cascade,
  viewed_at timestamptz not null default now(),
  unique (work_order_id, membership_id)
);

create table public.work_order_completion_verifications (
  id uuid primary key default gen_random_uuid(),
  work_order_id uuid not null references public.work_orders(id) on delete cascade,
  verified_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  outcome text not null,
  rating smallint check (rating between 1 and 5),
  note text,
  verified_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Shared private media and visitor/security operations
-- ---------------------------------------------------------------------------
create table public.media_assets (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  uploaded_by_membership_id uuid references public.community_memberships(id) on delete set null,
  storage_bucket text not null,
  storage_path text not null unique,
  mime_type text not null,
  byte_size bigint not null check (byte_size >= 0),
  status public.media_status not null default 'pending',
  created_at timestamptz not null default now()
);

alter table public.profiles
  add constraint profiles_avatar_media_fkey
  foreign key (avatar_media_id) references public.media_assets(id) on delete set null;

create table public.work_order_attachments (
  work_order_id uuid not null references public.work_orders(id) on delete cascade,
  media_asset_id uuid not null references public.media_assets(id) on delete cascade,
  attached_by_membership_id uuid references public.community_memberships(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (work_order_id, media_asset_id)
);

create table public.saved_visitors (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  created_by_membership_id uuid not null references public.community_memberships(id) on delete cascade,
  full_name text not null,
  phone_e164 varchar(20),
  default_purpose text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.visitor_access_requests (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  unit_id uuid not null references public.units(id) on delete restrict,
  requested_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  saved_visitor_id uuid references public.saved_visitors(id) on delete set null,
  visitor_name text not null,
  visitor_phone_e164 varchar(20),
  purpose text not null,
  expected_from timestamptz not null,
  expected_until timestamptz,
  gate_code_hash text,
  status public.visitor_status not null default 'expected',
  decided_by_membership_id uuid references public.community_memberships(id) on delete set null,
  decided_at timestamptz,
  checked_in_by_membership_id uuid references public.community_memberships(id) on delete set null,
  checked_in_at timestamptz,
  checked_out_by_membership_id uuid references public.community_memberships(id) on delete set null,
  checked_out_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (expected_until is null or expected_until > expected_from)
);

create table public.visitor_events (
  id uuid primary key default gen_random_uuid(),
  visitor_access_request_id uuid not null references public.visitor_access_requests(id) on delete cascade,
  actor_membership_id uuid references public.community_memberships(id) on delete set null,
  event_type text not null,
  occurred_at timestamptz not null default now(),
  note text
);

create table public.visitor_attachments (
  visitor_access_request_id uuid not null references public.visitor_access_requests(id) on delete cascade,
  media_asset_id uuid not null references public.media_assets(id) on delete cascade,
  attached_by_membership_id uuid references public.community_memberships(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (visitor_access_request_id, media_asset_id)
);

-- ---------------------------------------------------------------------------
-- Amenities, bookings, invoices, and payments
-- ---------------------------------------------------------------------------
create table public.amenities (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  name text not null,
  category text not null,
  location text,
  capacity integer check (capacity is null or capacity > 0),
  booking_mode text not null default 'slot',
  approval_required boolean not null default false,
  status text not null default 'active',
  hourly_rate numeric(12, 2) not null default 0 check (hourly_rate >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (community_id, name)
);

create table public.amenity_rules (
  id uuid primary key default gen_random_uuid(),
  amenity_id uuid not null references public.amenities(id) on delete cascade,
  minimum_duration_minutes integer check (minimum_duration_minutes is null or minimum_duration_minutes > 0),
  maximum_duration_minutes integer check (maximum_duration_minutes is null or maximum_duration_minutes > 0),
  minimum_lead_minutes integer check (minimum_lead_minutes is null or minimum_lead_minutes >= 0),
  maximum_advance_days integer check (maximum_advance_days is null or maximum_advance_days >= 0),
  cancellation_cutoff_minutes integer check (cancellation_cutoff_minutes is null or cancellation_cutoff_minutes >= 0),
  max_guests integer check (max_guests is null or max_guests >= 0),
  effective_from timestamptz not null default now(),
  effective_to timestamptz,
  created_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  check (effective_to is null or effective_to > effective_from)
);

create table public.amenity_booking_series (
  id uuid primary key default gen_random_uuid(),
  amenity_id uuid not null references public.amenities(id) on delete restrict,
  community_id uuid not null references public.communities(id) on delete cascade,
  booked_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  liable_unit_id uuid not null references public.units(id) on delete restrict,
  recurrence_rule text,
  status public.booking_status not null default 'requested',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.amenity_booking_occurrences (
  id uuid primary key default gen_random_uuid(),
  booking_series_id uuid not null references public.amenity_booking_series(id) on delete cascade,
  amenity_id uuid not null references public.amenities(id) on delete restrict,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  status public.booking_status not null default 'requested',
  approval_by_membership_id uuid references public.community_memberships(id) on delete set null,
  approved_at timestamptz,
  cancellation_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (ends_at > starts_at)
);

alter table public.amenity_booking_occurrences
  add constraint amenity_booking_occurrences_no_approved_overlap
  exclude using gist (
    amenity_id with =,
    tstzrange(starts_at, ends_at, '[)') with &&
  ) where (status = 'approved');

create table public.booking_guests (
  id uuid primary key default gen_random_uuid(),
  booking_occurrence_id uuid not null references public.amenity_booking_occurrences(id) on delete cascade,
  guest_name text not null,
  guest_phone_e164 varchar(20),
  created_at timestamptz not null default now()
);

create table public.amenity_booking_charges (
  id uuid primary key default gen_random_uuid(),
  booking_occurrence_id uuid not null references public.amenity_booking_occurrences(id) on delete cascade,
  charge_type text not null,
  description text,
  amount numeric(12, 2) not null check (amount >= 0),
  currency char(3) not null default 'INR',
  created_at timestamptz not null default now()
);

create table public.amenity_financial_events (
  id uuid primary key default gen_random_uuid(),
  booking_occurrence_id uuid not null references public.amenity_booking_occurrences(id) on delete cascade,
  event_type text not null,
  amount numeric(12, 2) not null,
  currency char(3) not null default 'INR',
  actor_membership_id uuid references public.community_memberships(id) on delete set null,
  reference text,
  created_at timestamptz not null default now()
);

create table public.invoices (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  liable_unit_id uuid not null references public.units(id) on delete restrict,
  booking_occurrence_id uuid references public.amenity_booking_occurrences(id) on delete set null,
  invoice_number text not null,
  invoice_type text not null,
  status public.invoice_status not null default 'draft',
  issued_at timestamptz not null default now(),
  due_at timestamptz not null,
  subtotal numeric(12, 2) not null default 0 check (subtotal >= 0),
  tax_amount numeric(12, 2) not null default 0 check (tax_amount >= 0),
  total_amount numeric(12, 2) not null check (total_amount >= 0),
  created_by_membership_id uuid references public.community_memberships(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (community_id, invoice_number),
  check (due_at >= issued_at)
);

create table public.invoice_line_items (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoices(id) on delete cascade,
  amenity_booking_charge_id uuid references public.amenity_booking_charges(id) on delete set null,
  description text not null,
  quantity numeric(10, 2) not null default 1 check (quantity > 0),
  unit_amount numeric(12, 2) not null check (unit_amount >= 0),
  total_amount numeric(12, 2) not null check (total_amount >= 0),
  created_at timestamptz not null default now()
);

create table public.payments (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoices(id) on delete restrict,
  payer_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  amount numeric(12, 2) not null check (amount > 0),
  currency char(3) not null default 'INR',
  method text not null,
  provider_reference text unique,
  status public.payment_status not null default 'initiated',
  paid_at timestamptz,
  recorded_by_membership_id uuid references public.community_memberships(id) on delete set null,
  created_at timestamptz not null default now()
);

create table public.payment_events (
  id uuid primary key default gen_random_uuid(),
  payment_id uuid not null references public.payments(id) on delete cascade,
  actor_membership_id uuid references public.community_memberships(id) on delete set null,
  event_type text not null,
  payload jsonb,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Notices, policy revisions, notifications, and audit
-- ---------------------------------------------------------------------------
create table public.notices (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  author_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  title text not null,
  body text not null,
  audience_role public.membership_role,
  published_at timestamptz,
  expires_at timestamptz,
  status text not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (expires_at is null or published_at is null or expires_at > published_at)
);

create table public.policies (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  title text not null,
  status text not null default 'draft',
  current_revision_id uuid,
  created_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.policy_revisions (
  id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.policies(id) on delete cascade,
  revision_number integer not null check (revision_number > 0),
  body text not null,
  change_summary text,
  authored_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  published_at timestamptz,
  created_at timestamptz not null default now(),
  unique (policy_id, revision_number)
);

alter table public.policies
  add constraint policies_current_revision_fkey
  foreign key (current_revision_id) references public.policy_revisions(id) on delete set null;

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  recipient_membership_id uuid not null references public.community_memberships(id) on delete cascade,
  notification_type text not null,
  title text not null,
  body text not null,
  payload jsonb,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.notification_deliveries (
  id uuid primary key default gen_random_uuid(),
  notification_id uuid not null references public.notifications(id) on delete cascade,
  channel text not null,
  status text not null,
  provider_message_id text,
  attempted_at timestamptz not null default now(),
  delivered_at timestamptz,
  failure_reason text
);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  actor_membership_id uuid references public.community_memberships(id) on delete set null,
  action text not null,
  entity_type text not null,
  entity_id uuid,
  before_data jsonb,
  after_data jsonb,
  request_id uuid,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Backfill the original global profile placement into the new model.
-- ---------------------------------------------------------------------------
insert into public.community_memberships (
  community_id, profile_id, role, status, joined_at, is_default_community
)
select
  p.legacy_community_id,
  p.id,
  case p.legacy_role::text
    when 'TECHNICIAN' then 'worker'::public.membership_role
    when 'SECURITY' then 'security'::public.membership_role
    when 'MANAGER' then 'manager'::public.membership_role
    when 'ADMIN' then 'admin'::public.membership_role
    else 'resident'::public.membership_role
  end,
  case when p.is_active then 'active'::public.membership_status else 'suspended'::public.membership_status end,
  p.created_at,
  true
from public.profiles p
where p.legacy_community_id is not null
  and not exists (
    select 1 from public.community_memberships cm
    where cm.community_id = p.legacy_community_id and cm.profile_id = p.id
      and cm.ended_at is null
  );

-- Existing demo data can contain several admins.  Keep the earliest one as
-- the active admin and demote later records to manager before enforcing terms.
with ranked_admins as (
  select id,
         row_number() over (partition by community_id order by joined_at, id) as position
  from public.community_memberships
  where role = 'admin' and status = 'active' and ended_at is null
)
update public.community_memberships cm
set role = 'manager', updated_at = now()
from ranked_admins ranked
where cm.id = ranked.id and ranked.position > 1;

insert into public.community_admin_terms (
  community_id, admin_membership_id, role_before_term, started_at
)
select cm.community_id, cm.id, 'resident'::public.membership_role, cm.joined_at
from public.community_memberships cm
where cm.role = 'admin' and cm.status = 'active' and cm.ended_at is null
  and not exists (
    select 1 from public.community_admin_terms term
    where term.community_id = cm.community_id and term.ended_at is null
  );

insert into public.unit_residencies (
  unit_id, membership_id, relationship_type, is_primary_contact, started_at
)
select ranked.unit_id,
       ranked.membership_id,
       ranked.relationship_type,
       ranked.position = 1,
       ranked.started_at
from (
  select
    u.id as unit_id,
    cm.id as membership_id,
    case when cm.role = 'admin' then 'owner'::public.residency_relationship else 'tenant'::public.residency_relationship end as relationship_type,
    cm.joined_at::date as started_at,
    row_number() over (partition by u.id order by cm.joined_at, cm.id) as position
  from public.community_memberships cm
  join public.profiles p on p.id = cm.profile_id
  join public.units u
    on u.community_id = cm.community_id and u.unit_code = p.legacy_unit_code
  where cm.role in ('resident', 'admin') and cm.status = 'active'
    and p.legacy_unit_code is not null
) ranked
where not exists (
  select 1 from public.unit_residencies ur
  where ur.unit_id = ranked.unit_id and ur.membership_id = ranked.membership_id and ur.ended_at is null
);

insert into public.community_features (community_id, feature_code, is_enabled)
select c.id, fc.code, fc.default_enabled
from public.communities c
cross join public.feature_catalog fc
on conflict (community_id, feature_code) do nothing;

-- ---------------------------------------------------------------------------
-- Cross-table integrity and common timestamps
-- ---------------------------------------------------------------------------
create or replace function public.validate_community_admin_term()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1
    from public.community_memberships cm
    where cm.id = new.admin_membership_id
      and cm.community_id = new.community_id
      and cm.role = 'admin'
      and cm.status = 'active'
      and cm.ended_at is null
  ) then
    raise exception 'An active admin term must reference an active admin membership in the same community';
  end if;
  return new;
end;
$$;

create trigger community_admin_terms_validate
before insert or update on public.community_admin_terms
for each row execute function public.validate_community_admin_term();

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'profiles', 'communities', 'buildings', 'units',
    'community_registration_requests', 'community_features', 'departments',
    'community_memberships', 'unit_residencies', 'vendors', 'staff_assignments',
    'resident_invites', 'access_requests', 'complaints', 'work_orders',
    'saved_visitors', 'visitor_access_requests', 'amenities', 'amenity_booking_series',
    'amenity_booking_occurrences', 'invoices', 'notices', 'policies'
  ] loop
    execute format('drop trigger if exists %I on public.%I', table_name || '_set_updated_at', table_name);
    execute format(
      'create trigger %I before update on public.%I for each row execute function public.set_updated_at()',
      table_name || '_set_updated_at', table_name
    );
  end loop;
end $$;

create index community_memberships_profile_idx on public.community_memberships (profile_id, community_id)
  where status = 'active' and ended_at is null;
create index unit_residencies_membership_idx on public.unit_residencies (membership_id)
  where ended_at is null;
create index complaints_community_status_idx on public.complaints (community_id, status, created_at desc);
create index visitor_access_requests_community_status_idx on public.visitor_access_requests (community_id, status, expected_from desc);
create index invoices_unit_status_idx on public.invoices (liable_unit_id, status, due_at);
create index notifications_recipient_idx on public.notifications (recipient_membership_id, read_at, created_at desc);

comment on column public.profiles.legacy_role is
  'Transitional copy of the pre-membership role. Do not use for authorization.';
comment on column public.profiles.legacy_community_id is
  'Transitional copy of the pre-membership community. Do not use for authorization.';
comment on column public.profiles.legacy_unit_code is
  'Transitional copy of the pre-membership unit code. Retain until backfill audit is complete.';
