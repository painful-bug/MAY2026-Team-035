-- HomeBandhu clean baseline. Apply only to a new Supabase project.
-- Google is the sole identity provider; profiles contain identity/contact data,
-- while every tenant permission is derived from an active membership.

create extension if not exists pgcrypto;
create extension if not exists citext;
create extension if not exists btree_gist;
create extension if not exists pg_trgm with schema extensions;

create type public.membership_role as enum ('resident','worker','security','manager','admin');
create type public.membership_status as enum ('pending','active','suspended','ended');
create type public.invite_status as enum ('issued','redeemed','revoked','expired');
create type public.residency_relationship as enum ('owner','tenant','family_member','caregiver','other');
create type public.complaint_status as enum ('open','acknowledged','in_progress','resolved','closed','cancelled');
create type public.visitor_status as enum ('expected','pending_approval','approved','denied','checked_in','checked_out','expired','cancelled');
create type public.booking_status as enum ('requested','approved','rejected','cancelled','completed','no_show');
create type public.invoice_status as enum ('draft','issued','partially_paid','paid','overdue','void');
create type public.payment_status as enum ('initiated','succeeded','failed','refunded');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text, display_email citext, phone_e164 varchar(20), avatar_media_id uuid,
  is_active boolean not null default true, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create unique index profiles_email_unique on public.profiles (display_email) where display_email is not null;

create table public.communities (
  id uuid primary key default gen_random_uuid(), name text not null, community_type text not null check (community_type in ('apartment','layout_villa')),
  status text not null default 'active' check (status = lower(btrim(status)) and length(btrim(status)) > 0), address_line1 text not null, address_line2 text, city text not null, state text not null, postal_code text not null, country_code char(2) not null default 'IN' check (country_code ~ '^[A-Z]{2}$'), timezone text not null default 'Asia/Kolkata',
  active_admin_membership_id uuid, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.buildings (
  id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade,
  name text not null, code text not null, building_type text not null default 'block', map_x numeric(8,5), map_y numeric(8,5), created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(community_id,code)
);
create table public.units (
  id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade,
  building_id uuid references public.buildings(id) on delete set null, unit_code text not null, unit_type text not null default 'flat', floor_number text, map_x numeric(8,5), map_y numeric(8,5), status text not null default 'active', created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(community_id,unit_code)
);
create table public.feature_catalog (code text primary key, name text not null, description text not null default '', default_enabled boolean not null default false, is_active boolean not null default true);
create table public.community_features (community_id uuid not null references public.communities(id) on delete cascade, feature_code text not null references public.feature_catalog(code), is_enabled boolean not null, updated_by_membership_id uuid, updated_at timestamptz not null default now(), primary key(community_id,feature_code));

create table public.departments (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, name text not null, description text, category text, hours jsonb not null default '{}'::jsonb, manager_membership_id uuid, is_active boolean not null default true, created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(community_id,name));
create table public.community_memberships (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, profile_id uuid not null references public.profiles(id) on delete cascade, department_id uuid references public.departments(id) on delete set null, role public.membership_role not null, status public.membership_status not null default 'pending', joined_at timestamptz not null default now(), ended_at timestamptz, is_default_community boolean not null default false, created_at timestamptz not null default now(), updated_at timestamptz not null default now(), check ((status='ended') = (ended_at is not null)));
create unique index memberships_active_person_community on public.community_memberships(community_id,profile_id) where ended_at is null;
create unique index memberships_one_default on public.community_memberships(profile_id) where is_default_community and status='active' and ended_at is null;
alter table public.communities add foreign key (active_admin_membership_id) references public.community_memberships(id) on delete restrict;
alter table public.departments add foreign key (manager_membership_id) references public.community_memberships(id) on delete set null;
alter table public.community_features add foreign key (updated_by_membership_id) references public.community_memberships(id) on delete set null;
create table public.community_admin_terms (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, admin_membership_id uuid not null references public.community_memberships(id) on delete restrict, designation text check (designation is null or length(designation) between 1 and 120), started_at timestamptz not null default now(), ended_at timestamptz, transferred_by_membership_id uuid references public.community_memberships(id) on delete set null, transfer_note text);
create unique index community_admin_one_active on public.community_admin_terms(community_id) where ended_at is null;
create table public.unit_residencies (id uuid primary key default gen_random_uuid(), unit_id uuid not null references public.units(id) on delete cascade, membership_id uuid not null references public.community_memberships(id) on delete cascade, relationship_type public.residency_relationship not null, is_primary_contact boolean not null default false, started_at date not null default current_date, ended_at date, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create unique index residencies_active_member_unit on public.unit_residencies(unit_id,membership_id) where ended_at is null;

create table public.resident_invites (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, intended_unit_id uuid references public.units(id) on delete restrict, invitee_email citext not null, invitee_phone_e164 varchar(20), invitee_name text, intended_role public.membership_role not null default 'resident', token_hash text not null unique, code_hash text not null unique, status public.invite_status not null default 'issued', expires_at timestamptz not null, redeemed_at timestamptz, redeemed_by_profile_id uuid references public.profiles(id) on delete set null, created_by_membership_id uuid references public.community_memberships(id) on delete set null, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create unique index invites_one_open_email on public.resident_invites(community_id,invitee_email) where status='issued';
create table public.access_requests (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, requested_unit_id uuid references public.units(id) on delete set null, applicant_profile_id uuid not null references public.profiles(id) on delete cascade, applicant_name text not null, applicant_email citext not null, applicant_phone_e164 varchar(20), requested_relationship public.residency_relationship not null default 'tenant', status text not null default 'pending' check (status in ('pending','approved','rejected','withdrawn')), reviewed_by_membership_id uuid references public.community_memberships(id) on delete set null, reviewed_at timestamptz, rejection_reason text check (rejection_reason is null or length(rejection_reason) <= 500), created_at timestamptz not null default now(), updated_at timestamptz not null default now(), check ((status = 'pending' and reviewed_by_membership_id is null and reviewed_at is null) or (status in ('approved','rejected') and reviewed_by_membership_id is not null and reviewed_at is not null) or status = 'withdrawn'));
create unique index access_requests_one_pending_per_profile_community on public.access_requests(community_id,applicant_profile_id) where status='pending';
create table public.blacklisted_residents (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, profile_id uuid not null references public.profiles(id) on delete cascade, blacklisted_by_membership_id uuid not null references public.community_memberships(id) on delete restrict, reason text not null check (length(btrim(reason)) between 3 and 500), created_at timestamptz not null default now(), revoked_at timestamptz, revoked_by_membership_id uuid references public.community_memberships(id) on delete set null);
create unique index blacklisted_residents_one_active_per_community_profile on public.blacklisted_residents(community_id,profile_id) where revoked_at is null;
create index communities_active_name_trgm on public.communities using gin (lower(name) extensions.gin_trgm_ops) where status='active';
create table public.vendors (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, name text not null, contact_name text, phone_e164 varchar(20), email citext, service_category text, status text not null default 'active', created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table public.staff_assignments (id uuid primary key default gen_random_uuid(), membership_id uuid not null references public.community_memberships(id) on delete cascade, department_id uuid references public.departments(id) on delete set null, vendor_id uuid references public.vendors(id) on delete set null, employment_type text not null, designation text, started_at date not null default current_date, ended_at date, is_active boolean not null default true, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table public.skills (id uuid primary key default gen_random_uuid(), name text not null unique, category text, description text);
create table public.staff_skills (staff_assignment_id uuid references public.staff_assignments(id) on delete cascade, skill_id uuid references public.skills(id) on delete restrict, proficiency_level smallint, primary key(staff_assignment_id,skill_id));
create table public.worker_availability_rules (id uuid primary key default gen_random_uuid(), staff_assignment_id uuid not null references public.staff_assignments(id) on delete cascade, weekday smallint not null check(weekday between 0 and 6), start_time time not null, end_time time not null, effective_from date not null default current_date, effective_to date);
create table public.worker_unavailability (id uuid primary key default gen_random_uuid(), staff_assignment_id uuid not null references public.staff_assignments(id) on delete cascade, starts_at timestamptz not null, ends_at timestamptz not null, reason text);

create table public.complaints (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, raised_by_membership_id uuid not null references public.community_memberships(id), category text not null, title text not null, description text, status public.complaint_status not null default 'open', aggregate_version integer not null default 1, created_at timestamptz not null default now(), updated_at timestamptz not null default now(), resolved_at timestamptz);
create table public.complaint_events (id uuid primary key default gen_random_uuid(), complaint_id uuid not null references public.complaints(id) on delete cascade, actor_membership_id uuid references public.community_memberships(id), event_type text not null, payload jsonb not null default '{}'::jsonb, created_at timestamptz not null default now());
create table public.complaint_comments (id uuid primary key default gen_random_uuid(), complaint_id uuid not null references public.complaints(id) on delete cascade, author_membership_id uuid not null references public.community_memberships(id), body text not null, created_at timestamptz not null default now());
create table public.complaint_read_state (complaint_id uuid references public.complaints(id) on delete cascade, membership_id uuid references public.community_memberships(id) on delete cascade, last_read_at timestamptz not null default now(), primary key(complaint_id,membership_id));
create table public.work_orders (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, complaint_id uuid references public.complaints(id) on delete set null, status text not null default 'open', priority text not null default 'normal', created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table public.work_order_assignments (id uuid primary key default gen_random_uuid(), work_order_id uuid not null references public.work_orders(id) on delete cascade, staff_assignment_id uuid references public.staff_assignments(id) on delete set null, assigned_at timestamptz not null default now(), ended_at timestamptz);

create table public.visitor_requests (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, requested_by_membership_id uuid not null references public.community_memberships(id), visitor_name text not null, visitor_phone_e164 varchar(20), status public.visitor_status not null default 'expected', pass_hash text unique, valid_from timestamptz, valid_until timestamptz, approved_by_membership_id uuid references public.community_memberships(id), checked_in_at timestamptz, checked_out_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table public.visitor_events (id uuid primary key default gen_random_uuid(), visitor_request_id uuid not null references public.visitor_requests(id) on delete cascade, actor_membership_id uuid references public.community_memberships(id), event_type text not null, created_at timestamptz not null default now());
create table public.amenities (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, name text not null, description text, booking_rules jsonb not null default '{}'::jsonb, is_active boolean not null default true, created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(community_id,name));
create table public.amenity_operating_hours (id uuid primary key default gen_random_uuid(), amenity_id uuid not null references public.amenities(id) on delete cascade, weekday smallint not null, opens_at time not null, closes_at time not null);
create table public.amenity_maintenance_blocks (id uuid primary key default gen_random_uuid(), amenity_id uuid not null references public.amenities(id) on delete cascade, starts_at timestamptz not null, ends_at timestamptz not null, reason text);
create table public.amenity_bookings (id uuid primary key default gen_random_uuid(), amenity_id uuid not null references public.amenities(id) on delete cascade, community_id uuid not null references public.communities(id) on delete cascade, booked_by_membership_id uuid not null references public.community_memberships(id), starts_at timestamptz not null, ends_at timestamptz not null, status public.booking_status not null default 'requested', aggregate_version integer not null default 1, created_at timestamptz not null default now(), updated_at timestamptz not null default now(), exclude using gist (amenity_id with =, tstzrange(starts_at,ends_at,'[)') with &&) where (status in ('requested','approved')));
create table public.booking_charges (id uuid primary key default gen_random_uuid(), booking_id uuid not null references public.amenity_bookings(id) on delete cascade, amount numeric(12,2) not null, kind text not null, status text not null default 'pending', created_at timestamptz not null default now());
create table public.booking_refunds (id uuid primary key default gen_random_uuid(), booking_charge_id uuid not null references public.booking_charges(id) on delete cascade, amount numeric(12,2) not null, reason text, created_at timestamptz not null default now());

create table public.invoices (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, membership_id uuid not null references public.community_memberships(id), status public.invoice_status not null default 'draft', due_at timestamptz, total_amount numeric(12,2) not null default 0, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table public.invoice_line_items (id uuid primary key default gen_random_uuid(), invoice_id uuid not null references public.invoices(id) on delete cascade, description text not null, amount numeric(12,2) not null);
create table public.payments (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, invoice_id uuid references public.invoices(id) on delete set null, provider text not null default 'offline', provider_reference text, amount numeric(12,2) not null, status public.payment_status not null default 'initiated', idempotency_key text, created_at timestamptz not null default now(), unique(community_id,idempotency_key));
create table public.payment_events (id uuid primary key default gen_random_uuid(), payment_id uuid not null references public.payments(id) on delete cascade, event_type text not null, payload jsonb not null default '{}'::jsonb, created_at timestamptz not null default now());
create table public.notices (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, author_membership_id uuid references public.community_memberships(id), title text not null, body text not null, published_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table public.notifications (id uuid primary key default gen_random_uuid(), recipient_membership_id uuid not null references public.community_memberships(id) on delete cascade, kind text not null, payload jsonb not null default '{}'::jsonb, read_at timestamptz, created_at timestamptz not null default now());
create table public.member_activity (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, membership_id uuid references public.community_memberships(id), event_type text not null, payload jsonb not null default '{}'::jsonb, created_at timestamptz not null default now());
create table public.audit_events (id uuid primary key default gen_random_uuid(), community_id uuid references public.communities(id) on delete cascade, actor_membership_id uuid references public.community_memberships(id), action text not null, payload jsonb not null default '{}'::jsonb, created_at timestamptz not null default now());
create table public.media (id uuid primary key default gen_random_uuid(), community_id uuid not null references public.communities(id) on delete cascade, storage_path text not null unique, mime_type text not null, byte_size bigint not null, uploaded_by_membership_id uuid references public.community_memberships(id), created_at timestamptz not null default now());
create table public.idempotency_records (community_id uuid not null references public.communities(id) on delete cascade, key text not null, request_hash text not null, response jsonb, created_at timestamptz not null default now(), primary key(community_id,key));
create table public.rate_limit_buckets (bucket text primary key, count integer not null default 0, window_ends_at timestamptz not null);
create table public.sse_events (id bigint generated always as identity primary key, community_id uuid not null references public.communities(id) on delete cascade, topic text not null, payload jsonb not null, created_at timestamptz not null default now());

create or replace function public.claim_email_invitation(p_invite_id uuid, p_profile_id uuid) returns table(membership_id uuid, community_id uuid, unit_id uuid) language plpgsql security definer set search_path=public as $$
declare invite public.resident_invites%rowtype; member uuid;
begin
  select * into invite from public.resident_invites where id=p_invite_id for update;
  if invite.id is null or invite.status <> 'issued' or invite.expires_at <= now() then raise exception 'Invite is not redeemable'; end if;
  insert into public.community_memberships(community_id,profile_id,role,status,is_default_community)
  values(
    invite.community_id,
    p_profile_id,
    invite.intended_role,
    'active',
    not exists(
      select 1 from public.community_memberships
      where profile_id=p_profile_id and status='active' and ended_at is null
        and is_default_community
    )
  ) returning id into member;
  if invite.intended_unit_id is not null then insert into public.unit_residencies(unit_id,membership_id,relationship_type) values(invite.intended_unit_id,member,'tenant'); end if;
  update public.resident_invites set status='redeemed', redeemed_at=now(), redeemed_by_profile_id=p_profile_id where id=invite.id;
  insert into public.audit_events(community_id,actor_membership_id,action,payload) values(invite.community_id,member,'invitation.redeemed',jsonb_build_object('invite_id',invite.id));
  return query select member,invite.community_id,invite.intended_unit_id;
end $$;

create or replace function public.create_founder_community(p_payload jsonb) returns jsonb language plpgsql security definer set search_path=public as $$
declare
  community uuid;
  building uuid;
  selected_building uuid;
  unit uuid;
  member uuid;
  existing_community uuid;
  item jsonb;
  founder_profile uuid := (p_payload->>'founder_profile_id')::uuid;
  founder_structure text := p_payload->'admin_profile'->>'founderStructureId';
  unit_code text := btrim(p_payload->'admin_profile'->>'unitNumber');
  type_value text := p_payload->>'community_type';
begin
  perform pg_advisory_xact_lock(hashtext(founder_profile::text));
  select m.community_id, m.id into existing_community, member
    from public.community_memberships m
   where m.profile_id=founder_profile and m.status='active' and m.ended_at is null
   order by m.is_default_community desc limit 1;
  if existing_community is not null then
    select id into unit from public.units u join public.unit_residencies r on r.unit_id=u.id where r.membership_id=member and r.ended_at is null limit 1;
    return jsonb_build_object(
      'community', jsonb_build_object(
        'id', existing_community,
        'name', (select name from public.communities where id=existing_community),
        'communityType', (select community_type from public.communities where id=existing_community),
        'enabledModules', coalesce((select jsonb_agg(feature_code order by feature_code) from public.community_features where community_id=existing_community and is_enabled), '[]'::jsonb),
        'unitType', case when (select community_type from public.communities where id=existing_community)='apartment' then 'Blocks' else 'Villas' end,
        'unitCount', (select count(*) from public.units where community_id=existing_community)
      ),
      'admin', jsonb_build_object(
        'id', founder_profile,
        'fullName', (select full_name from public.profiles where id=founder_profile),
        'role', 'Admin',
        'unitNumber', (select unit_code from public.units where id=unit),
        'phone', (select phone_e164 from public.profiles where id=founder_profile)
      )
    );
  end if;
  if type_value not in ('apartment','layout_villa') or unit_code = '' then raise exception 'Invalid founder community payload'; end if;
  if type_value='apartment' and jsonb_array_length(coalesce(p_payload->'blocks','[]'::jsonb)) not between 1 and 10 then raise exception 'Apartment communities require one to ten blocks'; end if;
  if type_value='layout_villa' and jsonb_array_length(coalesce(p_payload->'villas','[]'::jsonb)) not between 1 and 50 then raise exception 'Villa communities require one to fifty villas'; end if;
  insert into public.profiles(id,full_name,display_email,phone_e164)
  values(founder_profile,p_payload->'admin_profile'->>'fullName',(p_payload->>'founder_email')::citext,nullif(p_payload->'admin_profile'->>'phone',''))
  on conflict(id) do update set full_name=excluded.full_name,display_email=excluded.display_email,phone_e164=coalesce(excluded.phone_e164,public.profiles.phone_e164),updated_at=now();
  insert into public.communities(name,community_type,address_line1,address_line2,city,state,postal_code,country_code)
  values(p_payload->>'name',type_value,p_payload->>'address_line1',nullif(p_payload->>'address_line2',''),p_payload->>'city',p_payload->>'state',p_payload->>'postal_code',p_payload->>'country_code') returning id into community;
  if type_value='apartment' then
    for item in select * from jsonb_array_elements(p_payload->'blocks') loop
      insert into public.buildings(community_id,name,code,building_type,map_x,map_y)
      values(community,item->>'name',item->>'id','block',(p_payload->'block_locations'->(item->>'id')->>'x')::numeric,(p_payload->'block_locations'->(item->>'id')->>'y')::numeric)
      returning id into building;
      if founder_structure is null or founder_structure=item->>'id' then selected_building := building; end if;
    end loop;
    if selected_building is null then raise exception 'Founder block is invalid'; end if;
    insert into public.units(community_id,building_id,unit_code,unit_type) values(community,selected_building,unit_code,'flat') returning id into unit;
  else
    for item in select * from jsonb_array_elements(p_payload->'villas') loop
      insert into public.buildings(community_id,name,code,building_type,map_x,map_y)
      values(community,item->>'name',item->>'id','villa',(p_payload->'villa_locations'->(item->>'id')->>'x')::numeric,(p_payload->'villa_locations'->(item->>'id')->>'y')::numeric)
      returning id into building;
      insert into public.units(community_id,building_id,unit_code,unit_type,map_x,map_y)
      values(community,building,case when founder_structure=item->>'id' then unit_code else item->>'name' end,'villa',(p_payload->'villa_locations'->(item->>'id')->>'x')::numeric,(p_payload->'villa_locations'->(item->>'id')->>'y')::numeric)
      returning id into unit;
      if founder_structure is null or founder_structure=item->>'id' then selected_building := building; end if;
    end loop;
    select u.id into unit from public.units u where u.community_id=community and u.building_id=selected_building limit 1;
    if unit is null then raise exception 'Founder villa is invalid'; end if;
  end if;
  insert into public.community_memberships(community_id,profile_id,role,status,is_default_community) values(community,founder_profile,'admin','active',true) returning id into member;
  insert into public.unit_residencies(unit_id,membership_id,relationship_type,is_primary_contact) values(unit,member,'owner',true);
  insert into public.community_admin_terms(community_id,admin_membership_id,designation) values(community,member,nullif(p_payload->'admin_profile'->>'designation',''));
  update public.communities set active_admin_membership_id=member where id=community;
  insert into public.community_features(community_id,feature_code,is_enabled) select community,value,true from jsonb_array_elements_text(coalesce(p_payload->'enabled_features','[]'::jsonb)) value join public.feature_catalog f on f.code=value and f.is_active on conflict do nothing;
  insert into public.audit_events(community_id,actor_membership_id,action,payload) values(community,member,'community.created',jsonb_build_object('founder_profile_id',founder_profile,'community_type',type_value));
  return jsonb_build_object('community',jsonb_build_object('id',community,'name',p_payload->>'name','communityType',type_value,'enabledModules',coalesce(p_payload->'enabled_features','[]'::jsonb),'unitType',case when type_value='apartment' then 'Blocks' else 'Villas' end,'unitCount',case when type_value='apartment' then jsonb_array_length(p_payload->'blocks') else jsonb_array_length(p_payload->'villas') end),'admin',jsonb_build_object('id',founder_profile,'fullName',p_payload->'admin_profile'->>'fullName','role','Admin','unitNumber',unit_code,'phone',p_payload->'admin_profile'->>'phone));
end $$;

create or replace function public.search_joinable_communities(p_query text, p_limit integer default 10, p_profile_id uuid default null) returns table(id uuid,name text,community_type text,city text,state text) language sql stable security definer set search_path=public, extensions as $$
  select c.id,c.name,c.community_type,c.city,c.state from public.communities c
  where c.status='active' and length(btrim(p_query)) between 2 and 100 and lower(c.name) % lower(btrim(p_query))
    and not exists(select 1 from public.blacklisted_residents b where b.community_id=c.id and b.profile_id=p_profile_id and b.revoked_at is null)
  order by case when lower(c.name) like lower(btrim(p_query)) || '%' then 0 else 1 end, similarity(lower(c.name),lower(btrim(p_query))) desc,c.name,c.id
  limit least(greatest(coalesce(p_limit,10),1),20)
$$;

create or replace function public.approve_access_request(p_request_id uuid,p_reviewer_profile_id uuid,p_unit_id uuid default null,p_relationship public.residency_relationship default null) returns jsonb language plpgsql security definer set search_path=public as $$
declare request_row public.access_requests%rowtype; reviewer uuid; member uuid; target_unit uuid := p_unit_id;
begin
  select * into request_row from public.access_requests where id=p_request_id for update;
  if request_row.id is null then raise exception 'Access request not found'; end if;
  select id into reviewer from public.community_memberships where profile_id=p_reviewer_profile_id and community_id=request_row.community_id and role='admin' and status='active' and ended_at is null limit 1;
  if reviewer is null then raise exception 'Active administrator membership required'; end if;
  if request_row.status='approved' then select id into member from public.community_memberships where community_id=request_row.community_id and profile_id=request_row.applicant_profile_id and role='resident' and status='active' and ended_at is null limit 1; return jsonb_build_object('request_id',request_row.id,'membership_id',member,'status','approved'); end if;
  if request_row.status <> 'pending' then raise exception 'Access request is no longer pending'; end if;
  if target_unit is null then target_unit := request_row.requested_unit_id; end if;
  if target_unit is not null and not exists(select 1 from public.units where id=target_unit and community_id=request_row.community_id and status='active') then raise exception 'Selected unit does not belong to this community'; end if;
  insert into public.community_memberships(community_id,profile_id,role,status,is_default_community) values(request_row.community_id,request_row.applicant_profile_id,'resident','active',not exists(select 1 from public.community_memberships where profile_id=request_row.applicant_profile_id and status='active' and ended_at is null and is_default_community)) on conflict (community_id,profile_id) where ended_at is null do nothing returning id into member;
  if member is null then select id into member from public.community_memberships where community_id=request_row.community_id and profile_id=request_row.applicant_profile_id and role='resident' and status='active' and ended_at is null limit 1; if member is null then raise exception 'Applicant already has an incompatible membership'; end if; end if;
  if target_unit is not null then insert into public.unit_residencies(unit_id,membership_id,relationship_type) values(target_unit,member,coalesce(p_relationship,request_row.requested_relationship)) on conflict (unit_id,membership_id) where ended_at is null do nothing; end if;
  update public.access_requests set status='approved',reviewed_by_membership_id=reviewer,reviewed_at=now(),rejection_reason=null,updated_at=now() where id=request_row.id;
  insert into public.audit_events(community_id,actor_membership_id,action,payload) values(request_row.community_id,reviewer,'access_request.approved',jsonb_build_object('access_request_id',request_row.id,'membership_id',member));
  return jsonb_build_object('request_id',request_row.id,'membership_id',member,'status','approved');
end $$;

create or replace function public.blacklist_access_request(p_request_id uuid,p_reviewer_profile_id uuid,p_reason text) returns jsonb language plpgsql security definer set search_path=public as $$
declare request_row public.access_requests%rowtype; reviewer uuid;
begin
  select * into request_row from public.access_requests where id=p_request_id for update;
  if request_row.id is null or request_row.status <> 'pending' then raise exception 'Access request is no longer pending'; end if;
  select id into reviewer from public.community_memberships where profile_id=p_reviewer_profile_id and community_id=request_row.community_id and role='admin' and status='active' and ended_at is null limit 1;
  if reviewer is null then raise exception 'Administrator access is required'; end if;
  insert into public.blacklisted_residents(community_id,profile_id,blacklisted_by_membership_id,reason)
  values(request_row.community_id,request_row.applicant_profile_id,reviewer,left(btrim(p_reason),500))
  on conflict (community_id,profile_id) where revoked_at is null do update set reason=excluded.reason,blacklisted_by_membership_id=excluded.blacklisted_by_membership_id;
  update public.access_requests set status='rejected',reviewed_by_membership_id=reviewer,reviewed_at=now(),rejection_reason=left(btrim(p_reason),500),updated_at=now() where id=request_row.id;
  insert into public.audit_events(community_id,actor_membership_id,action,payload) values(request_row.community_id,reviewer,'access_request.blacklisted',jsonb_build_object('access_request_id',request_row.id));
  return jsonb_build_object('request_id',request_row.id,'status','rejected','blacklisted',true);
end $$;

create or replace function public.reject_access_request(p_request_id uuid,p_reviewer_profile_id uuid,p_reason text) returns jsonb language plpgsql security definer set search_path=public as $$
declare request_row public.access_requests%rowtype; reviewer uuid;
begin
  select * into request_row from public.access_requests where id=p_request_id for update;
  if request_row.id is null then raise exception 'Access request not found'; end if;
  select id into reviewer from public.community_memberships where profile_id=p_reviewer_profile_id and community_id=request_row.community_id and role='admin' and status='active' and ended_at is null limit 1;
  if reviewer is null then raise exception 'Active administrator membership required'; end if;
  if request_row.status='rejected' then return jsonb_build_object('request_id',request_row.id,'status','rejected'); end if;
  if request_row.status <> 'pending' then raise exception 'Access request is no longer pending'; end if;
  update public.access_requests set status='rejected',reviewed_by_membership_id=reviewer,reviewed_at=now(),rejection_reason=left(btrim(p_reason),500),updated_at=now() where id=request_row.id;
  insert into public.audit_events(community_id,actor_membership_id,action,payload) values(request_row.community_id,reviewer,'access_request.rejected',jsonb_build_object('access_request_id',request_row.id));
  return jsonb_build_object('request_id',request_row.id,'status','rejected');
end $$;

alter table public.profiles enable row level security;
alter table public.communities enable row level security;
alter table public.community_memberships enable row level security;
alter table public.units enable row level security;
alter table public.resident_invites enable row level security;
alter table public.access_requests enable row level security;
alter table public.blacklisted_residents enable row level security;
create policy profiles_self on public.profiles for select using (id=auth.uid());
create policy memberships_self on public.community_memberships for select using (profile_id=auth.uid());
create policy communities_member on public.communities for select using (exists(select 1 from public.community_memberships m where m.community_id=id and m.profile_id=auth.uid() and m.status='active' and m.ended_at is null));
create policy units_member on public.units for select using (exists(select 1 from public.community_memberships m where m.community_id=units.community_id and m.profile_id=auth.uid() and m.status='active' and m.ended_at is null));
create policy invites_admin on public.resident_invites for select using (exists(select 1 from public.community_memberships m where m.community_id=resident_invites.community_id and m.profile_id=auth.uid() and m.role='admin' and m.status='active' and m.ended_at is null));
create policy access_requests_applicant_read on public.access_requests for select using (applicant_profile_id=auth.uid());
create policy access_requests_admin_read on public.access_requests for select using (exists(select 1 from public.community_memberships m where m.community_id=access_requests.community_id and m.profile_id=auth.uid() and m.role='admin' and m.status='active' and m.ended_at is null));
revoke all on function public.claim_email_invitation(uuid,uuid) from public, anon, authenticated;
revoke all on function public.create_founder_community(jsonb) from public, anon, authenticated;
revoke all on function public.search_joinable_communities(text,integer,uuid) from public, anon, authenticated;
revoke all on function public.approve_access_request(uuid,uuid,uuid,public.residency_relationship) from public, anon, authenticated;
revoke all on function public.reject_access_request(uuid,uuid,text) from public, anon, authenticated;
revoke all on function public.blacklist_access_request(uuid,uuid,text) from public, anon, authenticated;
grant execute on function public.claim_email_invitation(uuid,uuid) to service_role;
grant execute on function public.create_founder_community(jsonb) to service_role;
grant execute on function public.search_joinable_communities(text,integer,uuid) to service_role;
grant execute on function public.approve_access_request(uuid,uuid,uuid,public.residency_relationship) to service_role;
grant execute on function public.reject_access_request(uuid,uuid,text) to service_role;
grant execute on function public.blacklist_access_request(uuid,uuid,text) to service_role;

insert into public.feature_catalog(code,name,description,default_enabled) values
 ('resident-management','Resident Management','Resident accounts',true),('visitor-management','Visitor Management','Visitor approvals',true),('complaint-management','Complaint Management','Complaints and work',true),('maintenance-billing','Maintenance and Billing','Invoices and payments',true),('notice-board','Notice Board','Community notices',true),('amenities-booking','Amenities Booking','Shared amenities',false),('security-gate-management','Security and Gate Management','Gate operations',false),('parking-management','Parking Management','Parking',false),('staff-management','Staff Management','Departments and staff',false),('community-marketplace','Community Marketplace','Marketplace',false)
on conflict(code) do nothing;
