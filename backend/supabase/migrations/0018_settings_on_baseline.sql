-- 0018 — community settings, billing settings and notice metadata, on the
-- clean baseline.
--
-- WHY THIS FILE EXISTS
--
-- Migrations 0010–0017 were written against the pre-baseline schema
-- (`associations`, `apartments`, `profiles.association_id`, a two-table amenity
-- booking model). `0001_baseline.sql` replaced all of it, so those files no
-- longer apply — they have been moved to `legacy-preauth/` and are kept for
-- reference only. See `legacy-preauth/README.md`.
--
-- This migration re-creates, on baseline tables, only what the endpoints that
-- survived the frontend wiring audit actually need:
--
--   GET/PUT /settings          -> public.community_settings
--   GET/PUT /billing-settings  -> public.community_billing_settings
--   POST /notices              -> public.notices.category, .urgency
--
-- Departments, complaints, money and amenities still need their SQL rebuilt the
-- same way. That work is scoped in `docs/RECONCILIATION_ADDENDUM.md`; those
-- endpoints exist and are tested at the contract level but will not run against
-- a baseline database until it lands.
--
-- Additive only. Nothing here alters or drops a baseline object; the two
-- `notices` columns are `add column if not exists`, and the SSE trigger block at
-- the end re-creates only triggers on tables this file introduces.

-- ---------------------------------------------------------------------------
-- set_updated_at() -- the baseline has no shared updated_at trigger function.
-- ---------------------------------------------------------------------------
-- The baseline declares `updated_at` on almost every table but never installs a
-- trigger to maintain it, so those columns only change when a writer remembers
-- to set them. Defined here (idempotently) because the two tables below need it;
-- deliberately NOT attached to any baseline table, since silently changing how
-- their rows behave is exactly the kind of edit this branch avoids.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- community_settings -- Settings screen toggles 3 and 4, plus tenancy config
-- ---------------------------------------------------------------------------
create table if not exists public.community_settings (
  community_id                 uuid primary key
                               references public.communities(id) on delete cascade,
  -- IANA name. Validated in save_community_settings against pg_timezone_names,
  -- not by a CHECK: a CHECK must be immutable and the timezone catalogue is
  -- loaded from the host, so it is not.
  timezone                     text not null default 'Asia/Kolkata',
  -- Null = derive from communities.community_type ('apartment' -> Flat,
  -- 'layout_villa' -> Villa). Null means "derive", not "unset".
  unit_label_singular          text,
  -- Per community, replacing the process-wide INVITE_TTL_HOURS env var. NOTE:
  -- `app/services/invitation_service.py` still reads the env var -- that file
  -- belongs to the auth workstream and is not edited here. DECISIONS_NEEDED C8.
  invite_ttl_hours             integer not null default 72,
  -- Reserved by the ERD for a subsystem that does not exist. Nothing reads it.
  visitor_code_ttl_minutes     integer not null default 120,
  -- Settings screen toggle 3. Nothing reads it; there is no visitor backend.
  require_visitor_preapproval  boolean not null default true,
  -- Settings screen toggle 4. Nothing reads it; there is no SMS provider. False
  -- by default on purpose -- this is the one flag that spends money per use.
  notice_sms_broadcast_enabled boolean not null default false,
  updated_by_membership_id     uuid references public.community_memberships(id)
                               on delete set null,
  version                      integer not null default 1,
  created_at                   timestamptz not null default now(),
  updated_at                   timestamptz not null default now(),
  -- Not a timezone validation -- just a rejection of the shapes that are never a
  -- timezone. The real check is in the RPC.
  constraint community_settings_timezone_ck
    check (length(timezone) between 3 and 64 and timezone !~ '\s'),
  -- 720 hours is 30 days. An invite that outlives a month is not a second
  -- factor, it is a permanent credential sitting in somebody's inbox.
  constraint community_settings_invite_ttl_ck
    check (invite_ttl_hours between 1 and 720),
  constraint community_settings_visitor_ttl_ck
    check (visitor_code_ttl_minutes between 5 and 1440),
  constraint community_settings_unit_label_ck
    check (unit_label_singular is null
           or length(trim(unit_label_singular)) between 1 and 24)
);

-- The composite FK to (id, community_id) that 0017 used is not available: the
-- baseline's community_memberships has no unique constraint on that pair. A
-- plain FK to the membership id is kept, and the RPC below checks that the
-- membership belongs to the community being written.

drop trigger if exists community_settings_set_updated_at on public.community_settings;
create trigger community_settings_set_updated_at
  before update on public.community_settings
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- community_billing_settings -- Settings screen toggles 1 and 2, plus money config
-- ---------------------------------------------------------------------------
-- Separate from community_settings because these are money: they have their own
-- endpoint pair (`GET`/`PUT /billing-settings`) and their own writer. The
-- Settings screen renders all four switches on one card; that is a layout fact,
-- not a schema one.
create table if not exists public.community_billing_settings (
  community_id               uuid primary key
                             references public.communities(id) on delete cascade,
  currency_code              char(3) not null default 'INR',
  invoice_number_prefix      text not null default 'INV',
  -- Nullable on purpose: a community that has not told us its rate must not be
  -- billed at a number we invented.
  default_maintenance_amount numeric(12, 2),
  -- Capped at 28 so "the 30th" does not silently become "the 2nd of March"
  -- every February.
  maintenance_due_day        smallint not null default 15,
  default_tax_percent        numeric(5, 2) not null default 0,
  -- Consumed under a row lock when numbering invoices. A sequence would be
  -- simpler but is global, and two communities must not interleave numbers.
  next_invoice_seq           bigint not null default 1,
  -- Settings screen toggle 1: Automated Monthly Maintenance.
  auto_billing_enabled       boolean not null default false,
  auto_billing_day           smallint not null default 1,
  -- Settings screen toggle 2: Late Payment Fine Charges.
  late_fee_enabled           boolean not null default false,
  -- NULLABLE, and null means "not configured". The frontend's copy says a flat
  -- Rs.100 weekly fine; writing 100 here as a default would turn a number that
  -- appears in prose into a number the system charges people, with nobody
  -- having decided it.
  late_fee_amount            numeric(12, 2),
  late_fee_grace_days        smallint not null default 10,
  late_fee_period            text not null default 'weekly',
  version                    integer not null default 1,
  created_at                 timestamptz not null default now(),
  updated_at                 timestamptz not null default now(),
  constraint community_billing_settings_due_day_ck
    check (maintenance_due_day between 1 and 28),
  constraint community_billing_settings_amount_ck
    check (default_maintenance_amount is null or default_maintenance_amount >= 0),
  constraint community_billing_settings_tax_ck
    check (default_tax_percent >= 0 and default_tax_percent < 100),
  constraint community_billing_settings_prefix_ck
    check (invoice_number_prefix ~ '^[A-Za-z0-9-]{1,12}$'),
  constraint community_billing_settings_auto_day_ck
    check (auto_billing_day between 1 and 28),
  constraint community_billing_settings_late_grace_ck
    check (late_fee_grace_days between 0 and 90),
  constraint community_billing_settings_late_period_ck
    check (late_fee_period in ('daily', 'weekly', 'monthly')),
  -- The two cross-field rules that make a toggle unswitchable without the number
  -- it acts on. Without these the API returns 200 and the switch springs back on
  -- the next read -- the bug the Settings screen already has.
  constraint community_billing_settings_auto_needs_amount_ck
    check (not auto_billing_enabled or default_maintenance_amount is not null),
  constraint community_billing_settings_late_needs_amount_ck
    check (not late_fee_enabled or late_fee_amount is not null)
);

drop trigger if exists community_billing_settings_set_updated_at
  on public.community_billing_settings;
create trigger community_billing_settings_set_updated_at
  before update on public.community_billing_settings
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- notices.category / notices.urgency
-- ---------------------------------------------------------------------------
-- The Notices screen collects both (`addNotice({title, description, category,
-- urgency})`) and the baseline's notices table carries neither, so without these
-- two columns the admin sets values that are silently discarded.
--
-- `category` is free text, not an enum: an association's notice categories are
-- its own business, and a CHECK here would make "add a category" a migration.
alter table public.notices
  add column if not exists category text not null default 'General';

alter table public.notices
  add column if not exists urgency text not null default 'info';

do $$
begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.notices'::regclass
                    and conname = 'notices_urgency_ck') then
    alter table public.notices
      add constraint notices_urgency_ck
      check (urgency in ('info', 'important', 'urgent'));
  end if;

  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.notices'::regclass
                    and conname = 'notices_category_ck') then
    alter table public.notices
      add constraint notices_category_ck
      check (length(trim(category)) between 1 and 80);
  end if;
end;
$$;

-- NOTE for the dashboard workstream: `dashboard_service.py:202` projects notices
-- as {id, title, description, date, createdAt} and drops these two columns, so
-- the values round-trip through POST /notices but do not reach the UI. Adding
-- them to that projection is a one-line change owned by that workstream.

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------
-- Both tables carry RLS with an admin-only write policy and a member-visible
-- read policy, resolved through community_memberships rather than a JWT claim --
-- the baseline installs no custom access-token hook, so `auth.jwt()` carries no
-- role and any policy reading one would be a policy that always fails.
--
-- This is the narrow, table-local answer to conflict C-1 (addendum §2): it does
-- not change how any baseline table is guarded, it only means these two tables
-- are safe whether reached by a service-role client or a user-scoped one.
alter table public.community_settings enable row level security;
alter table public.community_billing_settings enable row level security;

drop policy if exists community_settings_member_read on public.community_settings;
create policy community_settings_member_read
  on public.community_settings for select
  using (exists (
    select 1 from public.community_memberships m
     where m.community_id = community_settings.community_id
       and m.profile_id = auth.uid()
       and m.status = 'active'
       and m.ended_at is null
  ));

drop policy if exists community_settings_admin_write on public.community_settings;
create policy community_settings_admin_write
  on public.community_settings for all
  using (exists (
    select 1 from public.community_memberships m
     where m.community_id = community_settings.community_id
       and m.profile_id = auth.uid()
       and m.role = 'admin'
       and m.status = 'active'
       and m.ended_at is null
  ))
  with check (exists (
    select 1 from public.community_memberships m
     where m.community_id = community_settings.community_id
       and m.profile_id = auth.uid()
       and m.role = 'admin'
       and m.status = 'active'
       and m.ended_at is null
  ));

drop policy if exists billing_settings_member_read on public.community_billing_settings;
create policy billing_settings_member_read
  on public.community_billing_settings for select
  using (exists (
    select 1 from public.community_memberships m
     where m.community_id = community_billing_settings.community_id
       and m.profile_id = auth.uid()
       and m.status = 'active'
       and m.ended_at is null
  ));

drop policy if exists billing_settings_admin_write on public.community_billing_settings;
create policy billing_settings_admin_write
  on public.community_billing_settings for all
  using (exists (
    select 1 from public.community_memberships m
     where m.community_id = community_billing_settings.community_id
       and m.profile_id = auth.uid()
       and m.role = 'admin'
       and m.status = 'active'
       and m.ended_at is null
  ))
  with check (exists (
    select 1 from public.community_memberships m
     where m.community_id = community_billing_settings.community_id
       and m.profile_id = auth.uid()
       and m.role = 'admin'
       and m.status = 'active'
       and m.ended_at is null
  ));

-- ---------------------------------------------------------------------------
-- Seed a row per existing community
-- ---------------------------------------------------------------------------
-- So `GET /settings` and `GET /billing-settings` return defaults rather than 404
-- for a community created before this migration.
insert into public.community_settings (community_id)
select c.id from public.communities c
on conflict (community_id) do nothing;

insert into public.community_billing_settings (community_id)
select c.id from public.communities c
on conflict (community_id) do nothing;

-- ---------------------------------------------------------------------------
-- Extend the shared SSE outbox over the tables this migration adds
-- ---------------------------------------------------------------------------
-- `0007_dashboard_realtime_outbox.sql` installs `emit_dashboard_sse_event()` on
-- twelve tables. Both tables below have a `community_id`, which is all that
-- function needs, so a write to either now refreshes every connected client the
-- same way a write to complaints or invoices does.
--
-- Guarded on the function existing: on a fresh baseline project 0007 may not have
-- been applied, and a missing trigger is better than a failed migration.
do $$
declare
  target text;
begin
  if to_regprocedure('public.emit_dashboard_sse_event()') is null then
    raise notice
      'emit_dashboard_sse_event() not found; skipping SSE triggers for settings';
    return;
  end if;

  foreach target in array array[
    'community_settings', 'community_billing_settings'
  ] loop
    execute format('drop trigger if exists dashboard_sse_%I on public.%I',
                   target, target);
    execute format(
      'create trigger dashboard_sse_%I after insert or update or delete '
      'on public.%I for each row execute function '
      'public.emit_dashboard_sse_event()',
      target, target
    );
  end loop;
end;
$$;
