-- ===========================================================================
-- 0040_security_operations.sql — the gate
--
-- `security` has been a `membership_role` since `0001` and a `departments.kind`
-- since `0035`. A guard is hired by `decide_service_application`, holds skills,
-- books leave and appears on the same calendar as a plumber — D11 reused every
-- one of those verbatim, and none of it needed a line of new code.
--
-- What D11 did **not** reuse is the work itself. A guard's shift is a post
-- occupied for a window, not a job dispatched to an address, and a gate register
-- is not a complaint. So `work_orders` is the wrong table for all of it and this
-- file is the right one: five tables, a reconcile log, and the twelve functions
-- that write them.
--
-- Closes `US-3.3` (digital registers), `US-3.4` (the tanker log), `US-3.5`
-- (offline fallback) and `US-3.6` (downloadable reports) — four stories that have
-- read **Backend: None** since they were written. It also finishes `US-3.1`,
-- which was not the plan; see below.
--
--
-- THE GUARD HERE IS THE OPPOSITE OF `0039`'s, AND THAT IS THE POINT
--
-- `0039` takes no identity anywhere, because a worker's surface is deliberately
-- cross-community. This one is the mirror image. **A gate belongs to one
-- society.** A register entry, a shift, a post and an incident are each a fact
-- about exactly one community, and `is_community_security(uuid)` (`0032`:239)
-- has been sitting here since the visitor passes shipped, doing precisely the
-- check every read policy below wants.
--
-- So this file goes back to the house shape: read policies keyed on
-- `is_community_security(community_id) or is_community_admin(community_id)`, and
-- every write function taking the caller's **membership id** and deriving the
-- community from it. Not taking a community id — `ADMIN_DASHBOARD_DESIGN.md` §10
-- on why a community id in a request body is a tenancy hole with a plausible
-- excuse — and not resolving it from `auth.uid()` alone either, because a guard
-- who works two societies has two, and the API has to say which gate it is
-- standing at.
--
-- `is_own_membership(uuid)` (`0019`) is what makes that safe: the membership id
-- is checked to be the caller's own before anything is derived from it, so it
-- names a gate rather than granting access to one.
--
--
-- TWO LEVELS OF PERMISSION, BECAUSE A ROSTER IS NOT A REGISTER
--
-- `gate_community_for(membership)` — a guard on duty. Records movements, logs
-- tankers, files incidents, verifies credentials. Role `security`, `admin` or
-- `manager`.
--
-- `gate_admin_community_for(membership)` — decides where posts are and who
-- stands at them. Role `admin` or `manager`, **or** a `security` membership whose
-- roster row is ranked `manager` or `supervisor` (D3: rank and role are separate
-- axes, so a security manager is a `security` membership and not a `manager`
-- one).
--
-- Two predicates rather than one because the alternative is a system in which
-- every guard can rewrite the shift roster, and the alternative to *that* is a
-- system in which the security manager cannot log a tanker.
--
--
-- `US-3.5` NEEDED SOMETHING THAT DID NOT EXIST
--
-- The plan gives this step an offline bundle and a reconcile endpoint — an
-- offline *fallback* with nothing to fall back from. `USER_STORIES.md` US-3.1
-- says so in print: *"nothing verifies a code at the gate"*. `0032` mints
-- `code_hash` and `pass_hash`, stores them, and never reads either back.
--
-- So `verify_gate_credential` is built first and the offline pair sits on top of
-- it. One function answers *may this person in*, online and on replay, so the two
-- paths cannot drift into two different answers.
--
-- **It also checks them out, and it admits a group.** Presenting the same
-- credential again admits the next guest named on the pass, and once everybody
-- is inside it is the way out. `visitor_requests.guest_count` has existed since
-- `0032` and nothing has ever read it — so the obvious first-scan-in,
-- second-scan-out implementation would have admitted one guest of a
-- two-hundred-guest function and turned the rest away, which is the exact
-- failure `US-3.1` describes. One `count(*)` over the event log the admissions
-- already write.
--
--
-- THE OFFLINE BUNDLE IS NOT SIGNED, AND PLAN D13 SAID IT WOULD BE
--
-- A signature the device verifies against a key the device holds is theatre. The
-- same attacker who can edit `localStorage` can delete the check beside it,
-- because both are JavaScript on their machine.
--
-- What is actually load-bearing is that **an offline admission is provisional
-- until reconciled**. `reconcile_offline_entry` re-runs the real verification
-- against the live pass and records the server's own verdict beside the device's
-- claim, so a fabricated entry becomes a flagged row in an audit log rather than
-- an admitted guest. The bundle therefore carries an expiry and a community scope
-- and no signature.
--
-- Honest about what the bundle is: a list of live `code_hash` values for one
-- community, and a six-digit code hashed with SHA-256 is a 10^6 search space, so
-- the hashing obscures nothing from anybody holding the file. That is acceptable
-- precisely here and nowhere else — the gate device is *already* authorised to
-- admit those visitors, so the bundle tells the guard what the guard's job is.
-- It is why the read is security-and-admin only and why it is time-boxed.
--
--
-- IDEMPOTENCY LIVES IN TWO PLACES FOR TWO DIFFERENT REASONS
--
-- Each register table carries a nullable `source_client_id` with a partial unique
-- index, so a queued material entry replayed twice is one row.
--
-- `offline_reconcile_log` exists for the gate admissions, whose replay outcome is
-- a **verdict** rather than a row. There is nothing in `visitor_requests` a
-- unique index could hang off — the same pass is legitimately used again on the
-- way out — and the answer *this code was not valid at that time* has to be
-- recorded somewhere or the reconcile silently swallows it.
--
--
-- WHAT THIS FILE DELIBERATELY DOES NOT DO
--
-- * **No `security_snapshot`.** Every screen this serves is a list with a date
--   range; a snapshot would be a seventh read assembled from six that already
--   exist.
-- * **No notification on a register write.** Nobody needs a push saying a tanker
--   arrived. An *incident* notifies, because that is the one entry here somebody
--   is waiting for.
-- * **No retention or deletion policy**, which sounds like a gap in `US-3.6` and
--   is not: nothing this project writes is ever aged out, so long-term retention
--   is the existing behaviour and the story's real ask is the download.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Where a guard stands
--
-- Deactivated, never deleted. A post that is gone still names the place a
-- register entry was recorded two years ago, and `US-3.6` is a story about
-- reading records that old.
-- ---------------------------------------------------------------------------

create table if not exists public.security_posts (
  id            uuid primary key default gen_random_uuid(),
  community_id  uuid not null references public.communities(id) on delete cascade,
  department_id uuid,
  name          text not null,
  location_text text,
  latitude      numeric(9,6),
  longitude     numeric(9,6),
  is_active     boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

do $$
begin
  -- The house cross-tenant foreign key: a post may only name a department in its
  -- own community. `on delete cascade` for the reason `0036` §1 had to learn the
  -- hard way (§4.14) -- a composite `set null` nulls *every* column in the pair,
  -- and `community_id` is `not null`.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.security_posts'::regclass
       and conname  = 'security_posts_department_tenant_fkey'
  ) then
    alter table public.security_posts
      add constraint security_posts_department_tenant_fkey
      foreign key (department_id, community_id)
      references public.departments (id, community_id) on delete cascade;
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.security_posts'::regclass
       and conname  = 'security_posts_name_check'
  ) then
    alter table public.security_posts
      add constraint security_posts_name_check
      check (length(btrim(name)) between 1 and 120);
  end if;
end $$;

create unique index if not exists security_posts_live_name_idx
  on public.security_posts (community_id, lower(btrim(name)))
  where is_active;

comment on table public.security_posts is
  'A place a guard is stationed. Deactivated rather than deleted, because old register entries still name it.';

-- ---------------------------------------------------------------------------
-- 2. Who is standing there
--
-- `work_order_assignments` with the nouns changed, and the resemblance is not
-- accidental: a guard cannot be at two posts at once for exactly the reason a
-- plumber cannot be at two addresses, so it is the same GiST exclusion
-- constraint over the same `tstzrange`, requiring the same `btree_gist` the
-- baseline already installs and already depends on (`0001`:7, `0001`:81).
--
-- THE PARTIAL PREDICATE IS WHERE THE TWO DIFFER, AND IT HAS TO
--
-- `work_order_assignments_no_overlap` covers only `accepted` rows, because the
-- dispatcher offers one slot to five workers and exactly one takes it -- so
-- constraining offers would defeat the point of offering. Nobody offers a shift
-- to five guards. There is no equivalent state here, so the predicate is
-- everything except `cancelled`: a *completed* shift still occupied that guard's
-- evening, and a new one written over it is a rota error rather than a
-- historical curiosity.
-- ---------------------------------------------------------------------------

create table if not exists public.security_shifts (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.communities(id) on delete cascade,
  department_id       uuid,
  post_id             uuid references public.security_posts(id) on delete set null,
  staff_assignment_id uuid not null references public.staff_assignments(id) on delete cascade,
  starts_at           timestamptz not null,
  ends_at             timestamptz not null,
  status              text not null default 'scheduled',
  notes               text,
  created_by_membership_id uuid references public.community_memberships(id) on delete set null,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.security_shifts'::regclass
       and conname  = 'security_shifts_department_tenant_fkey'
  ) then
    alter table public.security_shifts
      add constraint security_shifts_department_tenant_fkey
      foreign key (department_id, community_id)
      references public.departments (id, community_id) on delete cascade;
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.security_shifts'::regclass
       and conname  = 'security_shifts_status_check'
  ) then
    alter table public.security_shifts
      add constraint security_shifts_status_check
      check (status in ('scheduled', 'active', 'completed', 'cancelled', 'missed'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.security_shifts'::regclass
       and conname  = 'security_shifts_window_check'
  ) then
    alter table public.security_shifts
      add constraint security_shifts_window_check
      check (ends_at > starts_at);
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.security_shifts'::regclass
       and conname  = 'security_shifts_no_overlap'
  ) then
    alter table public.security_shifts
      add constraint security_shifts_no_overlap
      exclude using gist (
        staff_assignment_id with =,
        tstzrange(starts_at, ends_at, '[)') with &&
      ) where (status <> 'cancelled');
  end if;
end $$;

create index if not exists security_shifts_community_window_idx
  on public.security_shifts (community_id, starts_at desc);

comment on table public.security_shifts is
  'A guard at a post for a window. The exclusion constraint is the same one work_order_assignments carries, and for the same reason.';

-- ---------------------------------------------------------------------------
-- 3. The inward/outward register — US-3.3
--
-- Two CHECKs the story implies and the plan did not name. A return date on a
-- non-returnable item is a contradiction, and so is a return; recording either
-- would produce a "still out" report that quietly disagrees with itself.
-- ---------------------------------------------------------------------------

create table if not exists public.material_movements (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.communities(id) on delete cascade,
  direction           text not null,
  description         text not null,
  quantity            numeric(12,2),
  unit                text,
  is_returnable       boolean not null default false,
  expected_return_at  timestamptz,
  returned_at         timestamptz,
  carrier_name        text,
  vehicle_number      text,
  unit_id             uuid references public.units(id) on delete set null,
  post_id             uuid references public.security_posts(id) on delete set null,
  notes               text,
  recorded_by_membership_id uuid references public.community_memberships(id) on delete set null,
  recorded_at         timestamptz not null default now(),
  source_client_id    text,
  created_at          timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.material_movements'::regclass
       and conname  = 'material_movements_direction_check'
  ) then
    alter table public.material_movements
      add constraint material_movements_direction_check
      check (direction in ('inward', 'outward'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.material_movements'::regclass
       and conname  = 'material_movements_description_check'
  ) then
    alter table public.material_movements
      add constraint material_movements_description_check
      check (length(btrim(description)) between 1 and 500);
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.material_movements'::regclass
       and conname  = 'material_movements_returnable_check'
  ) then
    alter table public.material_movements
      add constraint material_movements_returnable_check
      check (
        is_returnable
        or (expected_return_at is null and returned_at is null)
      );
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.material_movements'::regclass
       and conname  = 'material_movements_quantity_check'
  ) then
    alter table public.material_movements
      add constraint material_movements_quantity_check
      check (quantity is null or quantity > 0);
  end if;
end $$;

create index if not exists material_movements_community_recorded_idx
  on public.material_movements (community_id, recorded_at desc);

-- Still out: the report the returnable column exists for.
create index if not exists material_movements_outstanding_idx
  on public.material_movements (community_id, expected_return_at)
  where is_returnable and returned_at is null;

create unique index if not exists material_movements_source_client_idx
  on public.material_movements (community_id, source_client_id)
  where source_client_id is not null;

comment on table public.material_movements is
  'Inward and outward material, returnable or not. US-3.3, replacing the paper register.';

-- ---------------------------------------------------------------------------
-- 4. The tanker log — US-3.4
--
-- A separate table rather than a `kind` on the one above (plan D12), and the
-- reading confirms it: the two share not one column past the bookkeeping.
-- ---------------------------------------------------------------------------

create table if not exists public.water_tanker_logs (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.communities(id) on delete cascade,
  supplier_name       text,
  tanker_number       text not null,
  volume_litres       integer,
  driver_name         text,
  driver_phone_e164   varchar(20),
  arrived_at          timestamptz not null default now(),
  departed_at         timestamptz,
  post_id             uuid references public.security_posts(id) on delete set null,
  notes               text,
  recorded_by_membership_id uuid references public.community_memberships(id) on delete set null,
  source_client_id    text,
  created_at          timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.water_tanker_logs'::regclass
       and conname  = 'water_tanker_logs_number_check'
  ) then
    alter table public.water_tanker_logs
      add constraint water_tanker_logs_number_check
      check (length(btrim(tanker_number)) between 1 and 40);
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.water_tanker_logs'::regclass
       and conname  = 'water_tanker_logs_volume_check'
  ) then
    alter table public.water_tanker_logs
      add constraint water_tanker_logs_volume_check
      check (volume_litres is null or volume_litres > 0);
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.water_tanker_logs'::regclass
       and conname  = 'water_tanker_logs_window_check'
  ) then
    alter table public.water_tanker_logs
      add constraint water_tanker_logs_window_check
      check (departed_at is null or departed_at >= arrived_at);
  end if;
end $$;

create index if not exists water_tanker_logs_community_arrived_idx
  on public.water_tanker_logs (community_id, arrived_at desc);

create unique index if not exists water_tanker_logs_source_client_idx
  on public.water_tanker_logs (community_id, source_client_id)
  where source_client_id is not null;

comment on table public.water_tanker_logs is
  'One water tanker at the gate. US-3.4.';

-- ---------------------------------------------------------------------------
-- 5. Incidents
--
-- The form already exists and already writes to nothing.
-- `SecurityDashboard.jsx:166` collects a type, a location and details, and
-- `logIncident` appends an interpolated *string* to an activity feed -- the same
-- defect `DECISIONS_NEEDED` B2 names on the complaint assignee, one surface over.
--
-- `category` is stored in snake case and rendered from the wire vocabulary in
-- `app/domain/vocabularies.py`, the seam §5.8 and §4.6 both used. `other` is in
-- the set on purpose: a closed vocabulary with no escape hatch is a form people
-- work around by picking the nearest wrong option, which is worse than an
-- honest bucket.
-- ---------------------------------------------------------------------------

create table if not exists public.security_incidents (
  id            uuid primary key default gen_random_uuid(),
  community_id  uuid not null references public.communities(id) on delete cascade,
  category      text not null default 'other',
  severity      text not null default 'medium',
  status        text not null default 'open',
  summary       text not null,
  details       text,
  location_text text,
  post_id       uuid references public.security_posts(id) on delete set null,
  occurred_at   timestamptz not null default now(),
  resolved_at   timestamptz,
  reported_by_membership_id uuid references public.community_memberships(id) on delete set null,
  source_client_id text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.security_incidents'::regclass
       and conname  = 'security_incidents_category_check'
  ) then
    alter table public.security_incidents
      add constraint security_incidents_category_check
      check (category in (
        'security_concern', 'medical_emergency', 'fire_alarm',
        'unauthorised_access', 'property_damage', 'other'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.security_incidents'::regclass
       and conname  = 'security_incidents_severity_check'
  ) then
    alter table public.security_incidents
      add constraint security_incidents_severity_check
      check (severity in ('low', 'medium', 'high', 'critical'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.security_incidents'::regclass
       and conname  = 'security_incidents_status_check'
  ) then
    alter table public.security_incidents
      add constraint security_incidents_status_check
      check (status in ('open', 'acknowledged', 'resolved'));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.security_incidents'::regclass
       and conname  = 'security_incidents_summary_check'
  ) then
    alter table public.security_incidents
      add constraint security_incidents_summary_check
      check (length(btrim(summary)) between 1 and 300);
  end if;
end $$;

create index if not exists security_incidents_community_occurred_idx
  on public.security_incidents (community_id, occurred_at desc);

create unique index if not exists security_incidents_source_client_idx
  on public.security_incidents (community_id, source_client_id)
  where source_client_id is not null;

comment on table public.security_incidents is
  'An operational event worth a record. Replaces the interpolated string SecurityDashboard.jsx appends to an activity feed.';

-- ---------------------------------------------------------------------------
-- 6. What the gate did while it was offline
--
-- One row per queued admission, keyed by the id the device generated, holding
-- both the device's claim and the server's own verdict. That pairing is the
-- whole point: an entry the server would have refused is not silently dropped
-- and not silently accepted -- it is a row somebody can be asked about.
-- ---------------------------------------------------------------------------

create table if not exists public.offline_reconcile_log (
  id               uuid primary key default gen_random_uuid(),
  community_id     uuid not null references public.communities(id) on delete cascade,
  source_client_id text not null,
  credential_hash  text,
  claimed_at       timestamptz not null,
  claimed_verdict  text,
  server_verdict   text not null,
  visitor_request_id uuid references public.visitor_requests(id) on delete set null,
  detail           text,
  submitted_by_membership_id uuid references public.community_memberships(id) on delete set null,
  submitted_at     timestamptz not null default now()
);

create unique index if not exists offline_reconcile_log_source_client_idx
  on public.offline_reconcile_log (community_id, source_client_id);

create index if not exists offline_reconcile_log_community_idx
  on public.offline_reconcile_log (community_id, submitted_at desc);

comment on table public.offline_reconcile_log is
  'One offline gate admission, replayed. Holds the device claim and the server verdict side by side so a disagreement is auditable.';

-- ---------------------------------------------------------------------------
-- 7. The two permission levels
--
-- Both take a membership id and return its community, raising rather than
-- returning null, so a caller can write `v_community := gate_community_for(...)`
-- and be done. `is_own_membership` is checked first in both: the id names a gate,
-- it does not grant access to one.
-- ---------------------------------------------------------------------------

create or replace function public.gate_community_for(p_membership_id uuid)
returns uuid
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_row public.community_memberships%rowtype;
begin
  select * into v_row
    from public.community_memberships
   where id = p_membership_id
     and status = 'active'
     and ended_at is null;

  if not found or not public.is_own_membership(p_membership_id) then
    raise exception 'You are not on duty in this community.' using errcode = 'HB403';
  end if;

  if v_row.role not in ('security', 'admin', 'manager') then
    raise exception 'Only gate staff may record this.' using errcode = 'HB403';
  end if;

  return v_row.community_id;
end;
$$;

comment on function public.gate_community_for(uuid) is
  'The community a guard is on duty in, or HB403. Every register write starts here.';

create or replace function public.gate_admin_community_for(p_membership_id uuid)
returns uuid
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_row public.community_memberships%rowtype;
begin
  select * into v_row
    from public.community_memberships
   where id = p_membership_id
     and status = 'active'
     and ended_at is null;

  if not found or not public.is_own_membership(p_membership_id) then
    raise exception 'You are not on duty in this community.' using errcode = 'HB403';
  end if;

  -- A security *manager* holds a `security` membership with a roster rank, not a
  -- `manager` membership -- D3 made rank and role separate axes and this is the
  -- first place that distinction has to be honoured rather than described.
  if v_row.role in ('admin', 'manager') then
    return v_row.community_id;
  end if;

  if v_row.role = 'security' and exists (
    select 1 from public.staff_assignments s
     where s.membership_id = p_membership_id
       and s.status = 'active'
       and s.rank in ('manager', 'supervisor')
  ) then
    return v_row.community_id;
  end if;

  raise exception 'Only a security manager may change the roster.'
    using errcode = 'HB403';
end;
$$;

comment on function public.gate_admin_community_for(uuid) is
  'The community whose posts and shifts this membership may change, or HB403. Admins, managers, and security staff ranked manager or supervisor.';

-- ---------------------------------------------------------------------------
-- 8. Reads
--
-- Views only where there is a join. `security_posts` is read straight through
-- its policy: a view that selects every column of one table adds a synonym and
-- nothing else.
-- ---------------------------------------------------------------------------

drop view if exists public.security_shift_overview;
create view public.security_shift_overview
with (security_invoker = true) as
select
  s.id,
  s.community_id,
  s.department_id,
  s.post_id,
  p.name                as post_name,
  s.staff_assignment_id,
  sa.display_name       as guard_name,
  sa.phone_e164         as guard_phone_e164,
  sa.job_title          as guard_job_title,
  sa.rank               as guard_rank,
  s.starts_at,
  s.ends_at,
  s.status,
  s.notes,
  s.created_at,
  s.updated_at
from public.security_shifts s
left join public.security_posts p    on p.id  = s.post_id
left join public.staff_assignments sa on sa.id = s.staff_assignment_id;

comment on view public.security_shift_overview is
  'A shift with the guard and the post named. security_invoker, so the shift policy decides what is visible.';

drop view if exists public.material_movement_overview;
create view public.material_movement_overview
with (security_invoker = true) as
select
  m.id,
  m.community_id,
  m.direction,
  m.description,
  m.quantity,
  m.unit,
  m.is_returnable,
  m.expected_return_at,
  m.returned_at,
  m.carrier_name,
  m.vehicle_number,
  m.unit_id,
  u.unit_code,
  m.post_id,
  p.name  as post_name,
  m.notes,
  m.recorded_by_membership_id,
  m.recorded_at,
  m.source_client_id,
  -- Derived rather than stored, for the reason `0031` derives `is_overdue`: a
  -- stored flag needs somebody to flip it at midnight and is wrong until they do.
  (m.is_returnable and m.returned_at is null) as is_outstanding,
  (m.is_returnable and m.returned_at is null
    and m.expected_return_at is not null
    and m.expected_return_at < now())         as is_overdue
from public.material_movements m
left join public.units u          on u.id = m.unit_id
left join public.security_posts p on p.id = m.post_id;

comment on view public.material_movement_overview is
  'A register entry with the flat and post named, and the two returnable flags derived.';

drop view if exists public.water_tanker_log_overview;
create view public.water_tanker_log_overview
with (security_invoker = true) as
select
  t.id,
  t.community_id,
  t.supplier_name,
  t.tanker_number,
  t.volume_litres,
  t.driver_name,
  t.driver_phone_e164,
  t.arrived_at,
  t.departed_at,
  t.post_id,
  p.name as post_name,
  t.notes,
  t.recorded_by_membership_id,
  t.source_client_id,
  (t.departed_at is null) as is_on_site
from public.water_tanker_logs t
left join public.security_posts p on p.id = t.post_id;

comment on view public.water_tanker_log_overview is
  'A tanker entry with its post named.';

drop view if exists public.security_incident_overview;
create view public.security_incident_overview
with (security_invoker = true) as
select
  i.id,
  i.community_id,
  i.category,
  i.severity,
  i.status,
  i.summary,
  i.details,
  i.location_text,
  i.post_id,
  p.name as post_name,
  i.occurred_at,
  i.resolved_at,
  i.reported_by_membership_id,
  coalesce(nullif(btrim(pr.full_name), ''), 'Security') as reported_by_name,
  i.source_client_id,
  i.created_at,
  i.updated_at
from public.security_incidents i
left join public.security_posts p on p.id = i.post_id
left join public.community_memberships m on m.id = i.reported_by_membership_id
left join public.profiles pr on pr.id = m.profile_id;

comment on view public.security_incident_overview is
  'An incident with its post and reporter named. The reporter falls back to "Security" rather than to null.';

-- ---------------------------------------------------------------------------
-- 9. Posts and shifts
-- ---------------------------------------------------------------------------

create or replace function public.upsert_security_post(
  p_membership_id uuid,
  p_post_id       uuid,
  p_name          text,
  p_location_text text default null,
  p_department_id uuid default null,
  p_latitude      numeric default null,
  p_longitude     numeric default null,
  p_is_active     boolean default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_admin_community_for(p_membership_id);
  v_name      text := nullif(btrim(coalesce(p_name, '')), '');
  v_id        uuid;
begin
  if p_post_id is null then
    if v_name is null then
      raise exception 'A post needs a name.' using errcode = '22004';
    end if;
    insert into public.security_posts
      (community_id, department_id, name, location_text, latitude, longitude,
       is_active)
    values (v_community, p_department_id, v_name, p_location_text,
            p_latitude, p_longitude, coalesce(p_is_active, true))
    returning id into v_id;
    return v_id;
  end if;

  -- The tenancy check is a predicate on the UPDATE rather than a SELECT first.
  -- One statement, and a post in another community is indistinguishable from one
  -- that does not exist -- which is the answer we want to give either way.
  update public.security_posts
     set name          = coalesce(v_name, name),
         location_text = coalesce(p_location_text, location_text),
         department_id = coalesce(p_department_id, department_id),
         latitude      = coalesce(p_latitude, latitude),
         longitude     = coalesce(p_longitude, longitude),
         is_active     = coalesce(p_is_active, is_active),
         updated_at    = now()
   where id = p_post_id
     and community_id = v_community
  returning id into v_id;

  if v_id is null then
    raise exception 'No such post.' using errcode = 'HB404';
  end if;
  return v_id;
end;
$$;

comment on function public.upsert_security_post(uuid, uuid, text, text, uuid, numeric, numeric, boolean) is
  'Create a post, or change one. A null post id creates; everything else is coalesced, so a partial edit never blanks a field it did not mention.';

create or replace function public.schedule_security_shift(
  p_membership_id       uuid,
  p_staff_assignment_id uuid,
  p_starts_at           timestamptz,
  p_ends_at             timestamptz,
  p_post_id             uuid default null,
  p_notes               text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_admin_community_for(p_membership_id);
  v_staff     public.staff_assignments%rowtype;
  v_id        uuid;
begin
  if p_starts_at is null or p_ends_at is null or p_ends_at <= p_starts_at then
    raise exception 'A shift ends after it starts.' using errcode = '22004';
  end if;

  select * into v_staff
    from public.staff_assignments
   where id = p_staff_assignment_id
     and community_id = v_community
     and status = 'active';
  if not found then
    raise exception 'No such staff member in this community.' using errcode = 'HB404';
  end if;

  if p_post_id is not null and not exists (
    select 1 from public.security_posts
     where id = p_post_id and community_id = v_community
  ) then
    raise exception 'No such post.' using errcode = 'HB404';
  end if;

  -- Checked by name before the constraint refuses by number, the same pairing
  -- `assign_work_order` uses (§4.13). The exclusion constraint underneath is
  -- still the guarantee; this is the sentence a person can act on.
  if exists (
    select 1 from public.security_shifts
     where staff_assignment_id = p_staff_assignment_id
       and status <> 'cancelled'
       and tstzrange(starts_at, ends_at, '[)')
           && tstzrange(p_starts_at, p_ends_at, '[)')
  ) then
    raise exception '% is already on a shift during that time.',
      coalesce(nullif(btrim(v_staff.display_name), ''), 'That guard')
      using errcode = 'HB409';
  end if;

  insert into public.security_shifts
    (community_id, department_id, post_id, staff_assignment_id,
     starts_at, ends_at, notes, created_by_membership_id)
  values (v_community, v_staff.department_id, p_post_id, p_staff_assignment_id,
          p_starts_at, p_ends_at, nullif(btrim(coalesce(p_notes, '')), ''),
          p_membership_id)
  returning id into v_id;

  -- The guard is told, if they have an account. A roster name typed in by an
  -- admin has no membership and therefore no address -- the same wall `0035`
  -- ran into with rejections, and the same honest answer: notify who can be
  -- notified rather than pretend.
  if v_staff.membership_id is not null then
    perform public.notify_member(
      v_staff.membership_id,
      'shift.scheduled',
      jsonb_build_object(
        'title', 'You are on the roster',
        'body',  to_char(p_starts_at, 'DD Mon HH24:MI') || ' to '
                 || to_char(p_ends_at, 'HH24:MI'),
        'url',   '/security/shifts'
      )
    );
  end if;

  return v_id;
end;
$$;

comment on function public.schedule_security_shift(uuid, uuid, timestamptz, timestamptz, uuid, text) is
  'Put a guard on a post for a window. Refuses an overlap by name before the exclusion constraint refuses it by number.';

create or replace function public.update_security_shift(
  p_membership_id uuid,
  p_shift_id      uuid,
  p_status        text default null,
  p_starts_at     timestamptz default null,
  p_ends_at       timestamptz default null,
  p_post_id       uuid default null,
  p_notes         text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row       public.security_shifts%rowtype;
  v_status    text := nullif(btrim(lower(coalesce(p_status, ''))), '');
  v_community uuid;
  v_is_own    boolean;
begin
  select * into v_row from public.security_shifts where id = p_shift_id;
  if not found then
    raise exception 'No such shift.' using errcode = 'HB404';
  end if;

  -- A guard may start and end **their own** shift -- `SecurityLayout.jsx` has
  -- offered "End Shift & Logout" since before this table existed. Everything
  -- else on a shift is the roster, and the roster is the manager's.
  v_is_own := exists (
    select 1 from public.staff_assignments s
     where s.id = v_row.staff_assignment_id
       and s.membership_id is not null
       and public.is_own_membership(s.membership_id)
  );

  if v_is_own and v_status in ('active', 'completed')
     and p_starts_at is null and p_ends_at is null and p_post_id is null then
    v_community := public.gate_community_for(p_membership_id);
  else
    v_community := public.gate_admin_community_for(p_membership_id);
  end if;

  if v_row.community_id <> v_community then
    raise exception 'No such shift.' using errcode = 'HB404';
  end if;

  if p_post_id is not null and not exists (
    select 1 from public.security_posts
     where id = p_post_id and community_id = v_community
  ) then
    raise exception 'No such post.' using errcode = 'HB404';
  end if;

  update public.security_shifts
     set status     = coalesce(v_status, status),
         starts_at  = coalesce(p_starts_at, starts_at),
         ends_at    = coalesce(p_ends_at, ends_at),
         post_id    = coalesce(p_post_id, post_id),
         notes      = coalesce(nullif(btrim(coalesce(p_notes, '')), ''), notes),
         updated_at = now()
   where id = p_shift_id;
end;
$$;

comment on function public.update_security_shift(uuid, uuid, text, timestamptz, timestamptz, uuid, text) is
  'Change a shift. A guard may start and end their own; every other edit is the security manager''s.';

-- ---------------------------------------------------------------------------
-- 10. The registers
-- ---------------------------------------------------------------------------

create or replace function public.record_material_movement(
  p_membership_id     uuid,
  p_direction         text,
  p_description       text,
  p_quantity          numeric default null,
  p_unit              text default null,
  p_is_returnable     boolean default false,
  p_expected_return_at timestamptz default null,
  p_carrier_name      text default null,
  p_vehicle_number    text default null,
  p_unit_id           uuid default null,
  p_post_id           uuid default null,
  p_notes             text default null,
  p_recorded_at       timestamptz default null,
  p_source_client_id  text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_direction text := lower(btrim(coalesce(p_direction, '')));
  v_client    text := nullif(btrim(coalesce(p_source_client_id, '')), '');
  v_id        uuid;
begin
  if v_direction not in ('inward', 'outward') then
    raise exception 'A movement is inward or outward.' using errcode = '22004';
  end if;

  -- Replay returns the original row rather than raising. A gate device coming
  -- back online does not want to hear that its queue is a conflict; it wants the
  -- id it would have had.
  if v_client is not null then
    select id into v_id
      from public.material_movements
     where community_id = v_community and source_client_id = v_client;
    if v_id is not null then
      return v_id;
    end if;
  end if;

  insert into public.material_movements
    (community_id, direction, description, quantity, unit, is_returnable,
     expected_return_at, carrier_name, vehicle_number, unit_id, post_id, notes,
     recorded_by_membership_id, recorded_at, source_client_id)
  values (
    v_community, v_direction, btrim(p_description), p_quantity,
    nullif(btrim(coalesce(p_unit, '')), ''), coalesce(p_is_returnable, false),
    case when coalesce(p_is_returnable, false) then p_expected_return_at end,
    nullif(btrim(coalesce(p_carrier_name, '')), ''),
    nullif(btrim(coalesce(p_vehicle_number, '')), ''),
    p_unit_id, p_post_id, nullif(btrim(coalesce(p_notes, '')), ''),
    p_membership_id, coalesce(p_recorded_at, now()), v_client)
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.record_material_movement(uuid, text, text, numeric, text, boolean, timestamptz, text, text, uuid, uuid, text, timestamptz, text) is
  'One register entry. Idempotent on source_client_id, so a queued offline entry replayed twice is one row.';

create or replace function public.mark_material_returned(
  p_membership_id uuid,
  p_movement_id   uuid,
  p_returned_at   timestamptz default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_row       public.material_movements%rowtype;
begin
  select * into v_row
    from public.material_movements
   where id = p_movement_id and community_id = v_community;
  if not found then
    raise exception 'No such register entry.' using errcode = 'HB404';
  end if;

  if not v_row.is_returnable then
    raise exception 'That entry was not recorded as returnable.'
      using errcode = 'HB409';
  end if;

  -- Idempotent, not an error. The second guard to press *returned* is telling
  -- the truth, and the row already says so.
  if v_row.returned_at is not null then
    return;
  end if;

  update public.material_movements
     set returned_at = coalesce(p_returned_at, now())
   where id = p_movement_id;
end;
$$;

comment on function public.mark_material_returned(uuid, uuid, timestamptz) is
  'The returnable item came back. Idempotent.';

create or replace function public.record_water_tanker(
  p_membership_id    uuid,
  p_tanker_number    text,
  p_supplier_name    text default null,
  p_volume_litres    integer default null,
  p_driver_name      text default null,
  p_driver_phone_e164 text default null,
  p_arrived_at       timestamptz default null,
  p_departed_at      timestamptz default null,
  p_post_id          uuid default null,
  p_notes            text default null,
  p_source_client_id text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_number    text := nullif(btrim(upper(coalesce(p_tanker_number, ''))), '');
  v_client    text := nullif(btrim(coalesce(p_source_client_id, '')), '');
  v_id        uuid;
begin
  if v_number is null then
    raise exception 'A tanker needs its number.' using errcode = '22004';
  end if;

  if v_client is not null then
    select id into v_id
      from public.water_tanker_logs
     where community_id = v_community and source_client_id = v_client;
    if v_id is not null then
      return v_id;
    end if;
  end if;

  insert into public.water_tanker_logs
    (community_id, supplier_name, tanker_number, volume_litres, driver_name,
     driver_phone_e164, arrived_at, departed_at, post_id, notes,
     recorded_by_membership_id, source_client_id)
  values (
    v_community, nullif(btrim(coalesce(p_supplier_name, '')), ''), v_number,
    p_volume_litres, nullif(btrim(coalesce(p_driver_name, '')), ''),
    nullif(btrim(coalesce(p_driver_phone_e164, '')), ''),
    coalesce(p_arrived_at, now()), p_departed_at, p_post_id,
    nullif(btrim(coalesce(p_notes, '')), ''), p_membership_id, v_client)
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.record_water_tanker(uuid, text, text, integer, text, text, timestamptz, timestamptz, uuid, text, text) is
  'One tanker at the gate. The number is stored upper-cased, because a plate read twice by two guards is one vehicle.';

create or replace function public.update_water_tanker(
  p_membership_id uuid,
  p_log_id        uuid,
  p_departed_at   timestamptz default null,
  p_volume_litres integer default null,
  p_notes         text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_row       public.water_tanker_logs%rowtype;
begin
  select * into v_row
    from public.water_tanker_logs
   where id = p_log_id and community_id = v_community;
  if not found then
    raise exception 'No such tanker entry.' using errcode = 'HB404';
  end if;

  if p_departed_at is not null and p_departed_at < v_row.arrived_at then
    raise exception 'A tanker cannot leave before it arrived.'
      using errcode = '22004';
  end if;

  update public.water_tanker_logs
     set departed_at   = coalesce(p_departed_at, departed_at),
         volume_litres = coalesce(p_volume_litres, volume_litres),
         notes         = coalesce(nullif(btrim(coalesce(p_notes, '')), ''), notes)
   where id = p_log_id;
end;
$$;

comment on function public.update_water_tanker(uuid, uuid, timestamptz, integer, text) is
  'Record the departure, or correct the volume. Never blanks a field it was not given.';

create or replace function public.record_security_incident(
  p_membership_id    uuid,
  p_summary          text,
  p_category         text default 'other',
  p_severity         text default 'medium',
  p_details          text default null,
  p_location_text    text default null,
  p_post_id          uuid default null,
  p_occurred_at      timestamptz default null,
  p_source_client_id text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_summary   text := nullif(btrim(coalesce(p_summary, '')), '');
  v_severity  text := lower(btrim(coalesce(p_severity, 'medium')));
  v_client    text := nullif(btrim(coalesce(p_source_client_id, '')), '');
  v_id        uuid;
  v_payload   jsonb;
  v_manager   record;
begin
  if v_summary is null then
    raise exception 'Say what happened.' using errcode = '22004';
  end if;

  if v_client is not null then
    select id into v_id
      from public.security_incidents
     where community_id = v_community and source_client_id = v_client;
    if v_id is not null then
      return v_id;
    end if;
  end if;

  insert into public.security_incidents
    (community_id, category, severity, summary, details, location_text,
     post_id, occurred_at, reported_by_membership_id, source_client_id)
  values (
    v_community, coalesce(nullif(btrim(lower(coalesce(p_category, ''))), ''), 'other'),
    v_severity, v_summary, nullif(btrim(coalesce(p_details, '')), ''),
    nullif(btrim(coalesce(p_location_text, '')), ''), p_post_id,
    coalesce(p_occurred_at, now()), p_membership_id, v_client)
  returning id into v_id;

  -- The one register write that notifies. A tanker arriving is a record;
  -- something going wrong at the gate at 2am is a message, and `high` or
  -- `critical` is the line between the two.
  --
  -- **Corrected 2026-08-12.** This read `array['admin', 'manager']`, which is
  -- every manager in the community -- so the plumbing department's manager was
  -- told about a gate incident, and the link went to `/admin/security/incidents`,
  -- which their portal has no route for. Two separate wrongs with one cause: the
  -- audience was picked by role alone, and only *some* managers have this screen.
  --
  -- The audience is now the same predicate `_portal_for` uses to decide who sees
  -- `/security-manager` at all (`auth_service.py:271` -- the membership's own
  -- `department_id`, resolved to `departments.kind`). Deliberately mirrored rather
  -- than approximated: if the two ever disagree, somebody is notified about a
  -- screen they cannot open, which is exactly the bug being fixed here.
  --
  -- A manager whose membership carries no `department_id` is therefore excluded,
  -- even though `can_manage_department` would let them manage the security
  -- department. That manager routes to `/manager`, which has no incidents screen,
  -- so notifying them would recreate the defect. No path here mints one --
  -- `staff_invitations.department_id` and `hire_service_applicant` both require a
  -- department -- so this excludes a row nothing creates.
  if v_severity in ('high', 'critical') then
    v_payload := jsonb_build_object(
      'title', 'Security incident reported',
      'body',  v_summary,
      'url',   '/admin/security/incidents'
    );

    perform public.notify_community_roles(
      v_community, array['admin'], 'security.incident', v_payload
    );

    for v_manager in
      select m.id
        from public.community_memberships m
        join public.departments d on d.id = m.department_id
       where m.community_id = v_community
         and m.role::text   = 'manager'
         and m.status       = 'active'
         and m.ended_at is null
         and d.kind         = 'security'
    loop
      perform public.notify_member(v_manager.id, 'security.incident', v_payload);
    end loop;
  end if;

  return v_id;
end;
$$;

comment on function public.record_security_incident(uuid, text, text, text, text, text, uuid, timestamptz, text) is
  'File an incident. High and critical ones notify the community''s admins and its security-department managers; the rest are a record.';

create or replace function public.update_security_incident(
  p_membership_id uuid,
  p_incident_id   uuid,
  p_status        text default null,
  p_severity      text default null,
  p_details       text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_status    text := nullif(btrim(lower(coalesce(p_status, ''))), '');
  v_row       public.security_incidents%rowtype;
begin
  select * into v_row
    from public.security_incidents
   where id = p_incident_id and community_id = v_community;
  if not found then
    raise exception 'No such incident.' using errcode = 'HB404';
  end if;

  update public.security_incidents
     set status      = coalesce(v_status, status),
         severity    = coalesce(nullif(btrim(lower(coalesce(p_severity, ''))), ''), severity),
         details     = coalesce(nullif(btrim(coalesce(p_details, '')), ''), details),
         resolved_at = case
                         when v_status = 'resolved' then coalesce(resolved_at, now())
                         when v_status is not null then null
                         else resolved_at
                       end,
         updated_at  = now()
   where id = p_incident_id;
end;
$$;

comment on function public.update_security_incident(uuid, uuid, text, text, text) is
  'Acknowledge or resolve an incident. Moving it back off resolved clears the timestamp, so the column never outlives the status.';

-- ---------------------------------------------------------------------------
-- 11. The gate itself
--
-- The credential never arrives in plaintext. Python hashes it with the same
-- `hash_secret` that minted `code_hash` and `pass_hash` in the first place
-- (`app/core/tokens.py`), so this function compares hash to hash and the code a
-- visitor read off their phone is never in a query log.
--
-- Matching either column is deliberate: the QR carries the token and the manual
-- field carries the six digits, and the gate should not have to tell the API
-- which one it just read.
-- ---------------------------------------------------------------------------

create or replace function public.verify_gate_credential(
  p_membership_id uuid,
  p_hash          text,
  p_at            timestamptz default null
)
returns table (
  verdict          text,
  detail           text,
  pass_id          uuid,
  visitor_name     text,
  guest_count      integer,
  unit_code        text,
  resident_name    text,
  valid_from       timestamptz,
  valid_until      timestamptz
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_hash      text := nullif(btrim(coalesce(p_hash, '')), '');
  v_at        timestamptz := coalesce(p_at, now());
  v_row       public.visitor_requests%rowtype;
  v_verdict   text;
  v_detail    text;
  v_unit      text;
  v_resident  text;
  v_admitted  bigint;
begin
  if v_hash is null then
    raise exception 'No credential was presented.' using errcode = '22004';
  end if;

  select * into v_row
    from public.visitor_requests v
   where v.community_id = v_community
     and (v.code_hash = v_hash or v.pass_hash = v_hash)
   order by v.created_at desc
   limit 1
   for update;

  if not found then
    return query select
      'not_found'::text,
      'That code is not recognised at this gate.'::text,
      null::uuid, null::text, null::integer, null::text, null::text,
      null::timestamptz, null::timestamptz;
    return;
  end if;

  select u.unit_code,
         coalesce(nullif(btrim(pr.full_name), ''), 'A resident')
    into v_unit, v_resident
    from public.community_memberships m
    left join public.profiles pr on pr.id = m.profile_id
    left join public.unit_residencies ur
           on ur.membership_id = m.id and ur.ended_at is null
    left join public.units u on u.id = ur.unit_id
   where m.id = v_row.requested_by_membership_id
   limit 1;

  -- Order matters. A cancelled pass inside its window and a valid pass outside
  -- it are different refusals, and a guard standing in front of somebody needs
  -- to be told which -- "not yet valid" sends them away for an hour, "cancelled"
  -- sends them away.
  if v_row.status in ('cancelled', 'denied') then
    v_verdict := 'refused';
    v_detail  := 'That pass was cancelled.';
  elsif v_row.status = 'pending_approval' then
    v_verdict := 'refused';
    v_detail  := 'The resident has not approved this visitor yet.';
  elsif v_row.valid_from is not null and v_at < v_row.valid_from then
    v_verdict := 'not_yet_valid';
    v_detail  := 'That pass is not valid yet.';
  elsif v_row.valid_until is not null and v_at > v_row.valid_until then
    v_verdict := 'expired';
    v_detail  := 'That pass has expired.';
  elsif v_row.status = 'checked_out' then
    v_verdict := 'refused';
    v_detail  := 'That visit is already closed.';
  elsif v_row.status = 'checked_in' then
    -- WHY THIS BRANCH COUNTS RATHER THAN SIMPLY CHECKING OUT
    --
    -- `US-3.1` is about a pass that admits *many* guests over one window: a
    -- function with two hundred people arriving over an evening, on one code.
    -- `visitor_requests.guest_count` has existed since `0032` and nothing has
    -- ever read it, so the obvious implementation -- first scan in, second scan
    -- out -- would admit exactly one guest of that two hundred and turn the
    -- rest away, which is the failure the story exists to describe.
    --
    -- So the arrivals are counted from the event log, which is already written
    -- once per admission. While the group is still arriving the scan admits;
    -- once everyone named on the pass is inside, the next scan is the way out.
    -- That is why there is no separate check-out endpoint: at a barrier there
    -- is one action, and it is *scan*.
    select count(*) into v_admitted
      from public.visitor_events
     where visitor_request_id = v_row.id and event_type = 'checked_in';

    if v_admitted < coalesce(v_row.guest_count, 1) then
      insert into public.visitor_events (visitor_request_id, actor_membership_id, event_type)
      values (v_row.id, p_membership_id, 'checked_in');
      v_verdict := 'admitted';
      v_detail  := 'Admitted. ' || (v_admitted + 1)::text || ' of '
                   || coalesce(v_row.guest_count, 1)::text || '.';
    else
      update public.visitor_requests
         set status = 'checked_out', checked_out_at = v_at, updated_at = now()
       where id = v_row.id;
      insert into public.visitor_events (visitor_request_id, actor_membership_id, event_type)
      values (v_row.id, p_membership_id, 'checked_out');
      v_verdict := 'departed';
      v_detail  := 'Checked out.';
    end if;
  else
    update public.visitor_requests
       set status = 'checked_in', checked_in_at = v_at, updated_at = now()
     where id = v_row.id;
    insert into public.visitor_events (visitor_request_id, actor_membership_id, event_type)
    values (v_row.id, p_membership_id, 'checked_in');
    v_verdict := 'admitted';
    v_detail  := 'Admitted.';

    perform public.notify_member(
      v_row.requested_by_membership_id,
      'visitor.checked_in',
      jsonb_build_object(
        'title', 'Your visitor has arrived',
        'body',  v_row.visitor_name,
        'url',   '/resident/visitors'
      )
    );
  end if;

  return query select
    v_verdict, v_detail, v_row.id, v_row.visitor_name,
    coalesce(v_row.guest_count, 1), v_unit, v_resident,
    v_row.valid_from, v_row.valid_until;
end;
$$;

comment on function public.verify_gate_credential(uuid, text, timestamptz) is
  'May this person in. Admits on the first scan and checks out on the second; never sees a plaintext code.';

-- ---------------------------------------------------------------------------
-- 12. Offline
--
-- The bundle is what the gate caches; the reconcile is what makes it safe.
-- ---------------------------------------------------------------------------

create or replace function public.gate_offline_bundle(
  p_membership_id uuid,
  p_hours         integer default 12
)
returns table (
  pass_id      uuid,
  code_hash    text,
  pass_hash    text,
  visitor_name text,
  guest_count  integer,
  unit_code    text,
  valid_from   timestamptz,
  valid_until  timestamptz
)
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_hours     integer := least(greatest(coalesce(p_hours, 12), 1), 48);
begin
  return query
  select v.id, v.code_hash, v.pass_hash, v.visitor_name,
         coalesce(v.guest_count, 1), u.unit_code, v.valid_from, v.valid_until
    from public.visitor_requests v
    left join public.community_memberships m on m.id = v.requested_by_membership_id
    left join public.unit_residencies ur
           on ur.membership_id = m.id and ur.ended_at is null
    left join public.units u on u.id = ur.unit_id
   where v.community_id = v_community
     and v.status in ('expected', 'approved', 'checked_in')
     and v.code_hash is not null
     -- Overlaps the window rather than starts inside it: a pass valid all day
     -- belongs in the bundle a guard downloads at noon.
     and (v.valid_until is null or v.valid_until > now())
     and (v.valid_from  is null or v.valid_from  < now() + make_interval(hours => v_hours))
   order by v.valid_from nulls first;
end;
$$;

comment on function public.gate_offline_bundle(uuid, integer) is
  'The passes a gate may need while disconnected, capped at 48 hours. Hashes only -- there is no plaintext code anywhere in this database to hand out.';

create or replace function public.reconcile_offline_entry(
  p_membership_id    uuid,
  p_source_client_id text,
  p_hash             text,
  p_claimed_at       timestamptz,
  p_claimed_verdict  text default null
)
returns table (
  source_client_id text,
  server_verdict   text,
  detail           text,
  was_replay       boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_client    text := nullif(btrim(coalesce(p_source_client_id, '')), '');
  v_existing  public.offline_reconcile_log%rowtype;
  v_result    record;
begin
  if v_client is null then
    raise exception 'Every queued entry needs a client id.' using errcode = '22004';
  end if;

  -- The replay branch, and the reason this table exists. Re-running the
  -- verification would check the visitor *out* on the second submission of the
  -- same entry, because a second scan is a departure. So the recorded verdict is
  -- returned untouched.
  select * into v_existing
    from public.offline_reconcile_log
   where community_id = v_community and offline_reconcile_log.source_client_id = v_client;
  if found then
    return query select v_client, v_existing.server_verdict, v_existing.detail, true;
    return;
  end if;

  select * into v_result
    from public.verify_gate_credential(
           p_membership_id, p_hash, coalesce(p_claimed_at, now()));

  insert into public.offline_reconcile_log
    (community_id, source_client_id, credential_hash, claimed_at,
     claimed_verdict, server_verdict, visitor_request_id, detail,
     submitted_by_membership_id)
  values (
    v_community, v_client, nullif(btrim(coalesce(p_hash, '')), ''),
    coalesce(p_claimed_at, now()),
    nullif(btrim(lower(coalesce(p_claimed_verdict, ''))), ''),
    v_result.verdict, v_result.pass_id, v_result.detail, p_membership_id);

  return query select v_client, v_result.verdict, v_result.detail, false;
end;
$$;

comment on function public.reconcile_offline_entry(uuid, text, text, timestamptz, text) is
  'Replay one admission recorded while disconnected. Idempotent on the device''s own id, and records the server verdict beside the device''s claim.';

-- ---------------------------------------------------------------------------
-- 13. RLS — read policies only
--
-- The posture `0031`, `0034`, `0035`, `0036`, `0038` and `0039` all take: no
-- insert, update or delete policy exists on any table in this file. Every write
-- is one of the functions above, and each checks its own caller.
-- ---------------------------------------------------------------------------

alter table public.security_posts        enable row level security;
alter table public.security_shifts       enable row level security;
alter table public.material_movements    enable row level security;
alter table public.water_tanker_logs     enable row level security;
alter table public.security_incidents    enable row level security;
alter table public.offline_reconcile_log enable row level security;

drop policy if exists security_posts_read on public.security_posts;
create policy security_posts_read on public.security_posts
  for select to authenticated
  using (
    public.is_community_security(community_id)
    or public.is_community_admin(community_id)
  );

drop policy if exists security_shifts_read on public.security_shifts;
create policy security_shifts_read on public.security_shifts
  for select to authenticated
  using (
    public.is_community_security(community_id)
    or public.is_community_admin(community_id)
    -- A guard reads their own roster wherever they hold it. Without this a
    -- security membership in one community could not see a shift in another,
    -- which is the cross-community case `0039` exists for.
    or public.is_own_staff_assignment(staff_assignment_id)
  );

drop policy if exists material_movements_read on public.material_movements;
create policy material_movements_read on public.material_movements
  for select to authenticated
  using (
    public.is_community_security(community_id)
    or public.is_community_admin(community_id)
  );

drop policy if exists water_tanker_logs_read on public.water_tanker_logs;
create policy water_tanker_logs_read on public.water_tanker_logs
  for select to authenticated
  using (
    public.is_community_security(community_id)
    or public.is_community_admin(community_id)
  );

drop policy if exists security_incidents_read on public.security_incidents;
create policy security_incidents_read on public.security_incidents
  for select to authenticated
  using (
    public.is_community_security(community_id)
    or public.is_community_admin(community_id)
  );

-- The reconcile log is an audit surface, so it is the admin's rather than the
-- gate's: the person whose entries are being checked is not the person the check
-- is for.
drop policy if exists offline_reconcile_log_read on public.offline_reconcile_log;
create policy offline_reconcile_log_read on public.offline_reconcile_log
  for select to authenticated
  using (public.is_community_admin(community_id));

-- ---------------------------------------------------------------------------
-- 14. Grants
--
-- To `authenticated` and never `anon`, and every function below checks its own
-- caller through one of the two predicates in section 7 -- which is what makes
-- the grant safe rather than the grant itself. §4.15 is the worked example of
-- getting this wrong.
-- ---------------------------------------------------------------------------

grant execute on function public.gate_community_for(uuid) to authenticated;
grant execute on function public.gate_admin_community_for(uuid) to authenticated;
grant execute on function public.upsert_security_post(uuid, uuid, text, text, uuid, numeric, numeric, boolean) to authenticated;
grant execute on function public.schedule_security_shift(uuid, uuid, timestamptz, timestamptz, uuid, text) to authenticated;
grant execute on function public.update_security_shift(uuid, uuid, text, timestamptz, timestamptz, uuid, text) to authenticated;
grant execute on function public.record_material_movement(uuid, text, text, numeric, text, boolean, timestamptz, text, text, uuid, uuid, text, timestamptz, text) to authenticated;
grant execute on function public.mark_material_returned(uuid, uuid, timestamptz) to authenticated;
grant execute on function public.record_water_tanker(uuid, text, text, integer, text, text, timestamptz, timestamptz, uuid, text, text) to authenticated;
grant execute on function public.update_water_tanker(uuid, uuid, timestamptz, integer, text) to authenticated;
grant execute on function public.record_security_incident(uuid, text, text, text, text, text, uuid, timestamptz, text) to authenticated;
grant execute on function public.update_security_incident(uuid, uuid, text, text, text) to authenticated;
grant execute on function public.verify_gate_credential(uuid, text, timestamptz) to authenticated;
grant execute on function public.gate_offline_bundle(uuid, integer) to authenticated;
grant execute on function public.reconcile_offline_entry(uuid, text, text, timestamptz, text) to authenticated;
