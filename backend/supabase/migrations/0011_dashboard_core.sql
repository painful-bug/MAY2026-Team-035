-- 0011_dashboard_core.sql
-- Departments, complaint categories, complaints, notices and community modules:
-- everything the ten admin dashboard surfaces read and write, minus money and
-- amenities (steps 7 and 8).
--
-- Depends on 0010_memberships.sql (community_memberships, unit_residencies,
-- set_updated_at(), current_community_ids()).
--
-- Numbering: 0004-0009 belong to the auth/security workstream. See
-- docs/ADMIN_DASHBOARD_BUILD_PLAN.md section 1.4.
--
-- ===========================================================================
-- ASSUMPTIONS MADE HERE, so they are visible in the schema and not just in a doc.
-- Each is cheap to reverse while this migration is unapplied.
--
--  A1  ROLE VOCABULARY (open decision 2) -- public.user_role is left exactly as
--      it is, uppercase. Staff rank and job title are plain text on
--      staff_assignments, NOT enum members, because they are department-local
--      descriptions ('Technician', 'Supervisor') and never appear in a JWT.
--      Reconciling user_role with the ERD's lowercase vocabulary stays a
--      separate mechanical change that this file does not prejudge.
--
--  A2  SLA TIE-BREAK (open decision 3, frontend agenda item 2) -- the frontend
--      puts slaHours on the DEPARTMENT, and lets two departments claim the same
--      category, so "which SLA applies" has no answer in the data. Interim rule:
--      an explicit complaint_categories.sla_hours override wins; otherwise the
--      LOWEST sla_hours among active claiming departments wins. Encoded once, in
--      resolve_category_sla_hours(), so replacing the rule is a one-function
--      change. This is a workaround, not an answer.
--
--  A3  URGENCY AFFECTS THE DUE DATE -- R9 says due_at is computed "from the
--      category SLA and urgency", but no multiplier was ever specified. Assumed
--      high = half the SLA, medium = the SLA, low = double. Invented, and needs a
--      product ruling. Isolated in complaint_due_at() for the same reason as A2.
--
--  A4  R1 IS DELIBERATELY NOT APPLIED HERE -- see the apartments note below.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- A4: why R1's partial unique indexes are NOT added to apartments
--
-- The build plan said R1 belonged on `apartments`, whose unique (association_id,
-- code) supposedly had the defect R1 describes. Reading the column, it does not.
--
-- R1 addresses a BLOCK-RELATIVE label -- '101' recurring in every building --
-- where a nullable building_id makes NULLs distinct and lets duplicates through.
-- But `apartments.code` is community-wide by construction: the frontend builds it
-- as `${tower}-${flatNumber}`, giving 'B-1204'. The block is already inside the
-- string, so uniqueness per community is exactly the correct rule, and replacing
-- it with R1's two partial indexes would LOOSEN a constraint that works today.
--
-- R1 becomes relevant only if the ERD's separate `unit_label` column is ever
-- introduced. Leaving the existing constraint alone.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Parent unique constraints for composite FKs (R4)
--
-- Same reasoning as 0010: a composite FK (child.x_id, child.community_id) ->
-- parent (id, community_id) makes a cross-tenant row impossible to INSERT rather
-- than merely forbidden by a policy. Each parent needs the matching unique key.
--
-- REQUIRES POSTGRES 15+ for `on delete set null (column)`.
--
-- Composite FKs and ON DELETE SET NULL interact badly, and every nullable
-- composite FK below is written to avoid it. Plain `on delete set null` nulls
-- EVERY column of the key -- including community_id, which is NOT NULL -- so
-- deleting a referenced parent would raise a not-null violation instead of
-- clearing the reference. `on delete set null (the_nullable_column)` nulls only
-- the pointer and leaves the tenant key intact, which is the intended behaviour.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- departments
-- ---------------------------------------------------------------------------
create table if not exists public.departments (
  id                 uuid primary key default gen_random_uuid(),
  community_id       uuid not null references public.associations(id) on delete cascade,
  name               text not null,
  description        text,
  -- R8: contact details and operating hours as columns, not tables. The frontend
  -- stores ONE window (operatingHours: {start, end}), not a weekly schedule, so a
  -- department_hours table would store data the product does not collect.
  contact_email      text,
  contact_phone_e164 text,
  opens_at           time,
  closes_at          time,
  -- The frontend's departments[].slaHours. See A2 for what happens when two
  -- departments claim one category.
  sla_hours          integer check (sla_hours is null or sla_hours > 0),
  -- 'security' departments carry shift-based staff; 'service' ones do not. This
  -- is the only observable behavioural difference in the seed data.
  kind               text not null default 'service',
  status             text not null default 'active',
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  constraint departments_kind_ck check (kind in ('service', 'security')),
  constraint departments_status_ck check (status in ('active', 'archived')),
  constraint departments_community_name_uq unique (community_id, name),
  constraint departments_id_community_uq unique (id, community_id)
);

drop trigger if exists departments_set_updated_at on public.departments;
create trigger departments_set_updated_at
  before update on public.departments
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- complaint_categories (R5)
--
-- R5 put department_id and sla_hours directly on the category (one owning
-- department). C2 overrules the first half: Departments.jsx:211 is a multi-select
-- and nothing stops two departments claiming 'Plumbing', so ownership moves to
-- the department_categories join table below. sla_hours SURVIVES as a nullable
-- OVERRIDE -- when set it ends the ambiguity for that category outright, which is
-- the escape hatch if the frontend meeting rules that categories may have two
-- owners after all.
-- ---------------------------------------------------------------------------
create table if not exists public.complaint_categories (
  id           uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.associations(id) on delete cascade,
  name         text not null,
  sla_hours    integer check (sla_hours is null or sla_hours > 0),
  status       text not null default 'active',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint complaint_categories_status_ck check (status in ('active', 'archived')),
  constraint complaint_categories_community_name_uq unique (community_id, name),
  constraint complaint_categories_id_community_uq unique (id, community_id)
);

drop trigger if exists complaint_categories_set_updated_at on public.complaint_categories;
create trigger complaint_categories_set_updated_at
  before update on public.complaint_categories
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- department_categories (C2)
--
-- The N:M the UI already emits. Building this shape is not an endorsement of it
-- -- it is the only shape that can store what Departments.jsx produces, given we
-- cannot change the frontend.
-- ---------------------------------------------------------------------------
create table if not exists public.department_categories (
  id            uuid primary key default gen_random_uuid(),
  community_id  uuid not null references public.associations(id) on delete cascade,
  department_id uuid not null,
  category_id   uuid not null,
  created_at    timestamptz not null default now(),
  constraint department_categories_uq unique (department_id, category_id),
  constraint department_categories_department_fk
    foreign key (department_id, community_id)
    references public.departments (id, community_id) on delete cascade,
  constraint department_categories_category_fk
    foreign key (category_id, community_id)
    references public.complaint_categories (id, community_id) on delete cascade
);

create index if not exists department_categories_category_idx
  on public.department_categories (category_id);

-- ---------------------------------------------------------------------------
-- staff_assignments (R8)
--
-- Staff are department members. Critically, a staff member MAY HAVE NO ACCOUNT:
-- the frontend records only name + phone (C1), so membership_id is nullable and
-- display_name always carries the name actually shown.
--
-- Two axes, deliberately separate columns:
--   rank      -- structural: member | supervisor | head. Drives the head rule.
--   job_title -- the exact string the frontend renders in staff[].role.
--
-- Why job_title is STORED and not derived from rank: the seed data proves the
-- mapping is not a function. dept-plumbing's head renders as 'Supervisor' and
-- dept-facilities' head renders as 'Manager' -- same rank, different label. Any
-- derivation rule would silently rewrite one of them. Storing the label costs one
-- column and keeps the rendered string exact, which is the whole point of R8's
-- split: two different things stop sharing one field, without losing either.
-- ---------------------------------------------------------------------------
create table if not exists public.staff_assignments (
  id            uuid primary key default gen_random_uuid(),
  community_id  uuid not null references public.associations(id) on delete cascade,
  department_id uuid not null,
  membership_id uuid,
  display_name  text not null,
  phone_e164    text,
  job_title     text,
  rank          text not null default 'member',
  shift         text,
  status        text not null default 'active',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  constraint staff_assignments_rank_ck check (rank in ('member', 'supervisor', 'head')),
  constraint staff_assignments_status_ck check (status in ('active', 'inactive')),
  constraint staff_assignments_shift_ck
    check (shift is null or shift in ('Day', 'Evening', 'Night')),
  constraint staff_assignments_department_fk
    foreign key (department_id, community_id)
    references public.departments (id, community_id) on delete cascade,
  constraint staff_assignments_membership_fk
    foreign key (membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (membership_id)
);

create index if not exists staff_assignments_department_idx
  on public.staff_assignments (department_id) where status = 'active';
create index if not exists staff_assignments_membership_idx
  on public.staff_assignments (membership_id) where membership_id is not null;

-- R8: at most one head per department. Partial, so archived/former heads are
-- unconstrained history.
create unique index if not exists staff_assignments_dept_head_uq
  on public.staff_assignments (department_id) where rank = 'head' and status = 'active';

drop trigger if exists staff_assignments_set_updated_at on public.staff_assignments;
create trigger staff_assignments_set_updated_at
  before update on public.staff_assignments
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- SLA resolution (A2) and due-date computation (A3)
--
-- Both rules live in one function each so that replacing them after the frontend
-- meeting touches one place, not every call site.
-- ---------------------------------------------------------------------------
create or replace function public.resolve_category_sla_hours(p_category_id uuid)
returns integer
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    -- 1. An explicit override on the category always wins.
    (select c.sla_hours
       from public.complaint_categories c
      where c.id = p_category_id and c.sla_hours is not null),
    -- 2. Otherwise the strictest claiming department (A2 interim rule).
    (select min(d.sla_hours)
       from public.department_categories dc
       join public.departments d on d.id = dc.department_id
      where dc.category_id = p_category_id
        and d.status = 'active'
        and d.sla_hours is not null)
  );
$$;

-- Which department a complaint is routed to. Same tie-break as the SLA, so the
-- department that owns the deadline is the department that owns the complaint.
create or replace function public.resolve_category_department(p_category_id uuid)
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select dc.department_id
    from public.department_categories dc
    join public.departments d on d.id = dc.department_id
   where dc.category_id = p_category_id
     and d.status = 'active'
   order by d.sla_hours nulls last, d.created_at
   limit 1;
$$;

create or replace function public.complaint_due_at(p_category_id uuid, p_urgency text, p_from timestamptz)
returns timestamptz
language sql
stable
security definer
set search_path = public
as $$
  -- A3: the urgency multiplier is invented and needs a product ruling.
  -- The float8 casts are load-bearing: Postgres defines interval * float8 but has
  -- no numeric * interval operator, and unqualified 0.5 is numeric.
  select case
    when public.resolve_category_sla_hours(p_category_id) is null then null
    else p_from + (
      public.resolve_category_sla_hours(p_category_id)::float8
      * case lower(coalesce(p_urgency, 'medium'))
          when 'high' then 0.5::float8
          when 'low'  then 2.0::float8
          else 1.0::float8
        end
    ) * interval '1 hour'
  end;
$$;

-- ---------------------------------------------------------------------------
-- complaints (R9)
--
-- Assignment lives HERE, not on work_orders. The ERD routes assignment through
-- work_orders; the frontend assigns a complaint straight to a person and has no
-- work-order UI at all. Under the resolution principle the frontend owns this
-- truth. work_orders stays the phase-2 dispatch path (R16). This is a conscious
-- duplication of one concept and is worth naming as a cost.
-- ---------------------------------------------------------------------------
create table if not exists public.complaints (
  id                        uuid primary key default gen_random_uuid(),
  community_id              uuid not null references public.associations(id) on delete cascade,
  title                     text not null,
  description               text,
  -- Nullable: a complaint outlives the person who raised it. Their membership may
  -- be deleted when they move out; the complaint and its history must not vanish.
  raised_by_membership_id   uuid,
  raised_by_label           text,
  unit_id                   uuid,
  category_id               uuid,
  -- Stored, not derived. Re-resolving the department on every read would make an
  -- edit to the category mapping retroactively rewrite where past complaints went.
  department_id             uuid,
  status                    text not null default 'pending',
  urgency                   text not null default 'medium',
  progress_percent          smallint not null default 0,
  -- C1: the frontend's assignee is a free-text input (Complaints.jsx:175), so the
  -- label is authoritative and the FK is a nullable enrichment for when the
  -- assignee was actually picked from staff. Not the other way round.
  assignee_label            text,
  assigned_to_membership_id uuid,
  assigned_by_membership_id uuid,
  assigned_at               timestamptz,
  due_at                    timestamptz,
  reopen_count              integer not null default 0,
  last_reopened_at          timestamptz,
  resolved_at               timestamptz,
  resolution_rating         smallint,
  resolution_feedback       text,
  resolution_confirmed_at   timestamptz,
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now(),
  constraint complaints_status_ck
    check (status in ('pending', 'in_progress', 'resolved', 'closed', 'reopened')),
  constraint complaints_urgency_ck check (urgency in ('low', 'medium', 'high')),
  constraint complaints_progress_ck check (progress_percent between 0 and 100),
  constraint complaints_rating_ck
    check (resolution_rating is null or resolution_rating between 1 and 5),
  constraint complaints_id_community_uq unique (id, community_id),
  constraint complaints_unit_fk
    foreign key (unit_id, community_id)
    references public.apartments (id, association_id)
    on delete set null (unit_id),
  constraint complaints_category_fk
    foreign key (category_id, community_id)
    references public.complaint_categories (id, community_id)
    on delete set null (category_id),
  constraint complaints_department_fk
    foreign key (department_id, community_id)
    references public.departments (id, community_id)
    on delete set null (department_id),
  constraint complaints_raised_by_fk
    foreign key (raised_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (raised_by_membership_id),
  constraint complaints_assigned_to_fk
    foreign key (assigned_to_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (assigned_to_membership_id)
);

create index if not exists complaints_community_status_idx
  on public.complaints (community_id, status, created_at desc);
create index if not exists complaints_department_idx on public.complaints (department_id);
create index if not exists complaints_unit_idx on public.complaints (unit_id);
create index if not exists complaints_raised_by_idx on public.complaints (raised_by_membership_id);
-- Drives the "breaching SLA" tile without scanning resolved history.
create index if not exists complaints_due_idx
  on public.complaints (community_id, due_at)
  where status in ('pending', 'in_progress', 'reopened');

drop trigger if exists complaints_set_updated_at on public.complaints;
create trigger complaints_set_updated_at
  before update on public.complaints
  for each row execute function public.set_updated_at();

-- Fill department_id and due_at at INSERT when the caller did not supply them.
create or replace function public.complaints_apply_routing()
returns trigger
language plpgsql
as $$
begin
  if new.category_id is not null then
    if new.department_id is null then
      new.department_id := public.resolve_category_department(new.category_id);
    end if;
    if new.due_at is null then
      new.due_at := public.complaint_due_at(new.category_id, new.urgency, coalesce(new.created_at, now()));
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists complaints_apply_routing on public.complaints;
create trigger complaints_apply_routing
  before insert on public.complaints
  for each row execute function public.complaints_apply_routing();

-- ---------------------------------------------------------------------------
-- complaint_comments (R9)
--
-- Separate from the complaint_events audit stream on purpose. Events are append
-- only, machine-generated and never edited -- a management note fits that. A
-- resident/management conversation does not: it needs authorship, visibility and
-- eventually edit and delete. Collapsing the two yields either a leaky audit log
-- or a useless one.
-- ---------------------------------------------------------------------------
create table if not exists public.complaint_comments (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.associations(id) on delete cascade,
  complaint_id        uuid not null,
  author_membership_id uuid,
  author_label        text,
  body                text not null,
  -- 'internal' comments are never returned to a resident-scoped caller.
  visibility          text not null default 'resident',
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  deleted_at          timestamptz,
  constraint complaint_comments_visibility_ck check (visibility in ('resident', 'internal')),
  constraint complaint_comments_complaint_fk
    foreign key (complaint_id, community_id)
    references public.complaints (id, community_id) on delete cascade,
  constraint complaint_comments_author_fk
    foreign key (author_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (author_membership_id)
);

create index if not exists complaint_comments_complaint_idx
  on public.complaint_comments (complaint_id, created_at) where deleted_at is null;

drop trigger if exists complaint_comments_set_updated_at on public.complaint_comments;
create trigger complaint_comments_set_updated_at
  before update on public.complaint_comments
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- complaint_read_receipts (R9) -- drives the unread-updates badge.
-- ---------------------------------------------------------------------------
create table if not exists public.complaint_read_receipts (
  community_id  uuid not null references public.associations(id) on delete cascade,
  complaint_id  uuid not null,
  membership_id uuid not null,
  last_read_at  timestamptz not null default now(),
  primary key (complaint_id, membership_id),
  constraint complaint_read_receipts_complaint_fk
    foreign key (complaint_id, community_id)
    references public.complaints (id, community_id) on delete cascade,
  constraint complaint_read_receipts_membership_fk
    foreign key (membership_id, community_id)
    references public.community_memberships (id, community_id) on delete cascade
);

-- ---------------------------------------------------------------------------
-- complaint_attachments (R9) -- same shape as the existing *_attachments tables,
-- so this adds a table but no new concept. storage_path points at Supabase
-- Storage; the bytes never live in Postgres.
-- ---------------------------------------------------------------------------
create table if not exists public.complaint_attachments (
  id                    uuid primary key default gen_random_uuid(),
  community_id          uuid not null references public.associations(id) on delete cascade,
  complaint_id          uuid not null,
  storage_path          text not null,
  attachment_type       text not null default 'photo',
  content_type          text,
  size_bytes            bigint,
  uploaded_by_membership_id uuid,
  created_at            timestamptz not null default now(),
  constraint complaint_attachments_type_ck
    check (attachment_type in ('photo', 'document', 'resolution_proof')),
  constraint complaint_attachments_complaint_fk
    foreign key (complaint_id, community_id)
    references public.complaints (id, community_id) on delete cascade
);

create index if not exists complaint_attachments_complaint_idx
  on public.complaint_attachments (complaint_id);

-- ---------------------------------------------------------------------------
-- notices
--
-- notices.category stays FREE TEXT, unlike complaint categories. The difference
-- is behavioural: a complaint category routes to a department and carries an SLA,
-- so it must be a row. A notice category ('Maintenance', 'Celebration', ...) is a
-- display label with nothing attached to it. Making it a table would add a join
-- and a seeding step to buy nothing.
-- ---------------------------------------------------------------------------
create table if not exists public.notices (
  id                     uuid primary key default gen_random_uuid(),
  community_id           uuid not null references public.associations(id) on delete cascade,
  title                  text not null,
  body                   text,
  category               text,
  urgency                text not null default 'info',
  status                 text not null default 'published',
  published_at           timestamptz not null default now(),
  expires_at             timestamptz,
  created_by_membership_id uuid,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),
  constraint notices_urgency_ck check (urgency in ('info', 'low', 'medium', 'high')),
  constraint notices_status_ck check (status in ('draft', 'published', 'archived')),
  constraint notices_dates_ck check (expires_at is null or expires_at >= published_at),
  constraint notices_created_by_fk
    foreign key (created_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (created_by_membership_id)
);

create index if not exists notices_community_published_idx
  on public.notices (community_id, published_at desc) where status = 'published';

drop trigger if exists notices_set_updated_at on public.notices;
create trigger notices_set_updated_at
  before update on public.notices
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- community_modules (R10)
--
-- A table rather than communities.enabled_modules jsonb, because the Settings
-- screen needs to toggle one module without rewriting the whole set, and because
-- a per-row updated_at is what tells us when a module was switched off.
-- Ten rows per community.
-- ---------------------------------------------------------------------------
create table if not exists public.community_modules (
  community_id            uuid not null references public.associations(id) on delete cascade,
  module_key              text not null,
  enabled                 boolean not null default false,
  updated_by_membership_id uuid,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),
  primary key (community_id, module_key),
  constraint community_modules_updated_by_fk
    foreign key (updated_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (updated_by_membership_id)
);

drop trigger if exists community_modules_set_updated_at on public.community_modules;
create trigger community_modules_set_updated_at
  before update on public.community_modules
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Seeding
--
-- Every existing community gets the frontend's fixed category list and the ten
-- module rows. Idempotent. The category names are exactly the strings the
-- frontend posts, so the API's string -> id lookup never misses (R5).
-- ---------------------------------------------------------------------------
insert into public.complaint_categories (community_id, name)
select a.id, v.name
from public.associations a
cross join (values
  ('Plumbing'), ('Electrical'), ('Infrastructure'), ('Cleaning'), ('Security')
) as v(name)
on conflict on constraint complaint_categories_community_name_uq do nothing;

-- Module keys and defaults mirror frontend/src/data/onboardingModules.js exactly.
-- A key that drifts from that file silently disables a working feature, so this
-- list is a copy of a contract, not a guess.
insert into public.community_modules (community_id, module_key, enabled)
select a.id, v.module_key, v.enabled
from public.associations a
cross join (values
  ('resident-management',      true),
  ('visitor-management',       true),
  ('complaint-management',     true),
  ('maintenance-billing',      true),
  ('notice-board',             true),
  ('amenities-booking',        false),
  ('security-gate-management', false),
  ('parking-management',       false),
  ('staff-management',         false),
  ('community-marketplace',    false)
) as v(module_key, enabled)
on conflict (community_id, module_key) do nothing;

-- ---------------------------------------------------------------------------
-- Row-Level Security
--
-- Same pattern as 0010: community-scoped from the first line, never bare
-- is_admin(). Reads are open to any member of the community; writes are admin
-- only AND scoped. complaint_comments adds one extra rule -- internal comments
-- are invisible to non-admins.
-- ---------------------------------------------------------------------------
alter table public.departments             enable row level security;
alter table public.complaint_categories    enable row level security;
alter table public.department_categories   enable row level security;
alter table public.staff_assignments       enable row level security;
alter table public.complaints              enable row level security;
alter table public.complaint_comments      enable row level security;
alter table public.complaint_read_receipts enable row level security;
alter table public.complaint_attachments   enable row level security;
alter table public.notices                 enable row level security;
alter table public.community_modules       enable row level security;

do $$
declare
  t text;
begin
  foreach t in array array[
    'departments', 'complaint_categories', 'department_categories',
    'staff_assignments', 'complaints', 'complaint_attachments',
    'notices', 'community_modules'
  ]
  loop
    execute format('drop policy if exists %I on public.%I', t || '_member_read', t);
    execute format(
      'create policy %I on public.%I for select using (community_id in (select public.current_community_ids()))',
      t || '_member_read', t);

    execute format('drop policy if exists %I on public.%I', t || '_admin_write', t);
    execute format(
      'create policy %I on public.%I for all '
      'using (public.is_admin() and community_id in (select public.current_community_ids())) '
      'with check (public.is_admin() and community_id in (select public.current_community_ids()))',
      t || '_admin_write', t);
  end loop;
end$$;

-- complaint_comments: internal comments are admin-only. Written out rather than
-- generated because it is the one table whose read rule is not the common one.
drop policy if exists complaint_comments_member_read on public.complaint_comments;
create policy complaint_comments_member_read on public.complaint_comments
  for select using (
    community_id in (select public.current_community_ids())
    and (visibility = 'resident' or public.is_admin())
    and deleted_at is null
  );

drop policy if exists complaint_comments_admin_write on public.complaint_comments;
create policy complaint_comments_admin_write on public.complaint_comments
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

-- Read receipts are per-person: you may only see and write your own.
drop policy if exists complaint_read_receipts_own on public.complaint_read_receipts;
create policy complaint_read_receipts_own on public.complaint_read_receipts
  for all
  using (
    community_id in (select public.current_community_ids())
    and membership_id in (
      select id from public.community_memberships where profile_id = auth.uid()
    )
  )
  with check (
    community_id in (select public.current_community_ids())
    and membership_id in (
      select id from public.community_memberships where profile_id = auth.uid()
    )
  );

revoke execute on function public.resolve_category_sla_hours(uuid) from public, anon;
revoke execute on function public.resolve_category_department(uuid) from public, anon;
revoke execute on function public.complaint_due_at(uuid, text, timestamptz) from public, anon;
grant execute on function public.resolve_category_sla_hours(uuid) to authenticated;
grant execute on function public.resolve_category_department(uuid) to authenticated;
grant execute on function public.complaint_due_at(uuid, text, timestamptz) to authenticated;

-- ---------------------------------------------------------------------------
-- Verification -- run after applying.
-- ---------------------------------------------------------------------------
-- Every community has 5 categories and 10 modules (expect one row per community,
-- all counts 5 and 10):
--   select a.id, count(distinct c.id) as cats, count(distinct m.module_key) as mods
--   from public.associations a
--   left join public.complaint_categories c on c.community_id = a.id
--   left join public.community_modules m on m.community_id = a.id
--   group by a.id;
--
-- Categories claimed by more than one department -- these are the rows where A2's
-- tie-break is actually load-bearing. Expect zero until departments are created;
-- any row here is a case to raise at the frontend meeting:
--   select c.name, count(*) from public.department_categories dc
--   join public.complaint_categories c on c.id = dc.category_id
--   group by c.name having count(*) > 1;
--
-- No department has two active heads (expect zero rows; the partial unique index
-- should make this impossible, so a row here means the index is missing):
--   select department_id, count(*) from public.staff_assignments
--   where rank = 'head' and status = 'active'
--   group by department_id having count(*) > 1;
