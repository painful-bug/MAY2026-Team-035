-- 0017_settings.sql
-- Community-wide settings, the feature-module registry, and the two billing
-- toggles the Settings screen shows.
--
-- Depends on 0010_memberships.sql, 0011_dashboard_core.sql (community_modules),
-- 0015_money.sql (community_billing_settings), 0016_amenities.sql
-- (assert_community_admin, current_membership_id).
-- Numbering: 0004-0009 belong to the auth/security workstream (build plan 1.4).
--
-- ===========================================================================
-- THE SETTINGS SCREEN CURRENTLY SAVES NOTHING AT ALL.
--
-- `pages/AdminDashboard/Settings.jsx` is 135 lines and holds its entire state in
-- four `useState` hooks. `handleSave` is:
--
--     const handleSave = () => { showToast('Admin Settings Saved Successfully'); };
--
-- There is no store slice, no service module, no persistence of any kind. An
-- admin toggles four switches, is told the settings were saved successfully, and
-- loses all four on the next render. This file is the first place any of those
-- four answers can be written down.
--
-- ===========================================================================
-- WHAT THE FOUR TOGGLES ACTUALLY ARE
--
-- They are not four settings of one kind. They are four different kinds of
-- thing, and putting them in one table would be the mistake:
--
--   1. "Automated Monthly Maintenance"  -> BILLING. Money configuration already
--      has a table (`community_billing_settings`, 0015) and an endpoint pair
--      (`GET`/`PUT /billing-settings`). It is extended below rather than
--      duplicated here. This is what the build plan means by "billing and late
--      fines are not settings".
--
--   2. "Late Payment Fine Charges"      -> BILLING, and a feature that does not
--      exist. See the block on late fees below.
--
--   3. "Gate Security App Pre-approvals" -> a VISITOR policy. Visitors are
--      frontend dummy data; no endpoint, table or module of ours reads this.
--      Stored anyway, because the alternative is that the screen keeps losing
--      the answer, and because the ERD already reserves
--      `community_settings.visitor_code_ttl_minutes` for the same subsystem.
--
--   4. "Urgent Notice SMS Broadcast"    -> a NOTIFICATION policy, and the only
--      toggle on the screen that would spend money every time it fired. There is
--      no SMS provider anywhere in this repository. It defaults to false, which
--      is the frontend's own default and the only safe one: a flag that sends
--      cellular SMS to every registered phone must not arrive switched on.
--
-- Nothing reads 3 or 4 yet. That is said plainly in API.md rather than implied,
-- because a settings screen whose switches do nothing is worse than one that
-- admits it.
--
-- ===========================================================================
-- THE MODULE TOGGLES HAVE NO SCREEN, AND THE ONBOARDING WIZARD PROMISES ONE.
--
-- `FeatureConfigurationPage.jsx` ends with, verbatim:
--
--     "These features can be changed later from the Admin Settings page."
--
-- The Admin Settings page has no module UI. It has the four toggles above and
-- nothing else. The ten module choices an admin makes during onboarding are
-- written to `onboardingStore` (a frontend store), used once by
-- `OnboardingSuccessPage` to render a summary, and never referenced again.
--
-- So the promise the wizard makes is kept by no screen. `GET /settings/modules`
-- and its two writes exist to make keeping it a rendering job. Frontend agenda
-- item 17.
--
-- ===========================================================================
-- NOTHING GATES ON A MODULE, AND THIS FILE DOES NOT START.
--
-- `AdminLayout.jsx` renders a fixed array of ten nav items. `ResidentLayout` and
-- `SecurityLayout` do the same. No route, screen, or store consults
-- `enabledModules`. Enabling or disabling a module changes nothing anywhere.
--
-- The tempting fix is to enforce it server-side: 403 every amenity endpoint when
-- `amenities-booking` is off. That is deliberately NOT done here, for two
-- reasons that only became visible once the seed data was read:
--
--   * `amenities-booking` is seeded DISABLED (it is `defaultEnabled: false` in
--     `onboardingModules.js`, and 0011 mirrors that file exactly). Enforcing
--     would 403 all twenty-two step-8 endpoints on every existing community, so
--     the first symptom of "we implemented module gating" would be "amenities
--     are broken".
--
--   * Six of the ten modules have no backend at all. Gating on a flag while six
--     flags gate nothing produces a rule that is true for four keys and
--     decorative for six -- which is harder to reason about than no rule.
--
-- What is done instead is to make the state honest: `module_catalogue.backend_status`
-- records, per module, whether anything actually implements it. An admin looking
-- at `GET /settings/modules` can see that Parking Management is enabled and that
-- nothing in the product will do anything about it. Enforcement is a product
-- decision, written up as DECISIONS_NEEDED A24.
--
-- ===========================================================================
-- THE ERD's `community_settings`, MINUS WHAT ALREADY HAS A HOME.
--
-- The ERD's table carries nine payload columns. Four of them are already
-- implemented elsewhere and are NOT repeated here:
--
--   | ERD column               | Where it actually lives                        |
--   |--------------------------|------------------------------------------------|
--   | enabled_modules jsonb    | `community_modules` table (0011). A jsonb array |
--   |                          | cannot record WHEN one module was switched off, |
--   |                          | or by whom, and both are audit questions.       |
--   | default_currency_code    | `community_billing_settings.currency_code`      |
--   | invoice_number_prefix    | `community_billing_settings.invoice_number_prefix` |
--   | version                  | kept, as the ERD has it                        |
--
-- The remaining five (`timezone`, `unit_label_singular`, `invite_ttl_hours`,
-- `visitor_code_ttl_minutes`, plus `version`) are created below, and two of the
-- Settings screen's toggles join them. DECISIONS_NEEDED D8.
--
-- One ERD comment is wrong in a way worth flagging: it says onboarding "selects
-- nine feature modules". `onboardingModules.js` has TEN. 0011 seeded ten. The
-- catalogue below has ten.
--
-- ===========================================================================
-- THIS FILE ANSWERS A10: THERE IS NOW A COMMUNITY TIMEZONE.
--
-- 0016 stores amenity occurrences as `booking_date date` + `starts_at time`
-- rather than `timestamptz`, with the note that there was "no community timezone
-- field anywhere to resolve 07:00 against". There is one now.
--
-- That does NOT reverse 0016's choice -- it vindicates it. A booking made for
-- 07:00 must still read 07:00 after somebody corrects the community's timezone,
-- which is only true if the wall-clock time is what was stored. What the field
-- unlocks is everything that needs an absolute instant: "remind me 30 minutes
-- before", overnight billing boundaries, "today" on a dashboard. All of those
-- currently mean "whatever the server thinks", and now have somewhere to look.
--
-- The timezone is validated against `pg_timezone_names` inside the RPC, not by a
-- CHECK constraint. A CHECK must be immutable and the timezone catalogue is not:
-- it is loaded from the host and changes between PostgreSQL releases. A CHECK
-- that appeared to validate it would be one that Postgres refuses to trust
-- during a restore.
--
-- ===========================================================================
-- WHY THIS FILE DOES NOT LET AN ADMIN RENAME THEIR COMMUNITY.
--
-- `GET /settings` reports the community name, type and status. There is no write
-- for them, and the reason is not that nobody would want one.
--
-- `associations` is the one table this build plan touches whose write policy is
-- the unscoped one from `0002_rls.sql`:
--
--     create policy associations_admin_write on public.associations
--       for all using (public.is_admin()) with check (public.is_admin());
--
-- No community clause. Build plan 1.2 documents it as high severity and the
-- auth/security workstream owns the fix. Every table this plan has added is
-- community-scoped from its first line precisely so that none of the sixty-five
-- endpoints so far depends on that policy. A rename endpoint would be the first
-- one that does -- so it waits for 1.2 to land rather than becoming the reason
-- 1.2 was urgent. DECISIONS_NEEDED C7.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- module_catalogue
--
-- Global, not per community: the ten keys are a contract with
-- `frontend/src/data/onboardingModules.js`, and a key that drifts from that file
-- silently disables a working feature. 0011 already copied the list into a seed;
-- this promotes it to a table so the display name, the description and -- the
-- part that is new -- whether anything actually implements it can be read back.
--
-- `backend_status` goes stale by design: every future build step that implements
-- a module is expected to update its row. That is a maintenance cost taken
-- knowingly, because the alternative is an admin with no way to tell an enabled
-- module from an inert one.
-- ---------------------------------------------------------------------------
create table if not exists public.module_catalogue (
  module_key      text primary key,
  display_name    text not null,
  description     text not null,
  sort_order      integer not null,
  -- Mirrors `defaultEnabled` in onboardingModules.js. Used when a community has
  -- no row for a key at all, which happens to every community the moment a new
  -- key is added to the catalogue.
  default_enabled boolean not null default false,
  -- 'implemented' -- endpoints exist and are documented in docs/API.md.
  -- 'partial'     -- some of it exists; the note says which part.
  -- 'none'        -- nothing in this repository implements it.
  backend_status  text not null default 'none',
  backend_note    text not null default '',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  constraint module_catalogue_status_ck
    check (backend_status in ('implemented', 'partial', 'none')),
  constraint module_catalogue_key_ck
    check (module_key ~ '^[a-z][a-z0-9-]{2,48}$')
);

drop trigger if exists module_catalogue_set_updated_at on public.module_catalogue;
create trigger module_catalogue_set_updated_at
  before update on public.module_catalogue
  for each row execute function public.set_updated_at();

-- Ten rows. Keys, names, descriptions and defaults are copied from
-- onboardingModules.js; `backend_status` reflects build steps 1-9 as shipped.
insert into public.module_catalogue
  (module_key, display_name, description, sort_order, default_enabled,
   backend_status, backend_note)
values
  ('resident-management', 'Resident Management',
   'Manage residents and their profiles.', 1, true,
   'implemented', 'Build step 4. GET/PATCH/DELETE /residents, /admins, /registrations.'),
  ('visitor-management', 'Visitor Management',
   'Approve and track visitors.', 2, true,
   'none', 'Visitors are frontend dummy data. No table, endpoint or migration.'),
  ('complaint-management', 'Complaint Management',
   'Residents can raise complaints.', 3, true,
   'implemented', 'Build step 5. Complaints, comments, attachments, read receipts.'),
  ('maintenance-billing', 'Maintenance & Billing',
   'Track maintenance payments and dues.', 4, true,
   'partial', 'Build step 7. Invoices and payments exist; no screen can bill anybody (agenda item 12), and nothing runs billing on a schedule.'),
  ('notice-board', 'Notice Board',
   'Publish announcements.', 5, true,
   'partial', 'Table and RLS from build step 3 (0011). No notice endpoints yet.'),
  ('amenities-booking', 'Amenities Booking',
   'Book clubhouse, gym, pool, etc.', 6, false,
   'implemented', 'Build step 8. Twenty-two endpoints. Note this module is seeded DISABLED, mirroring onboardingModules.js.'),
  ('security-gate-management', 'Security & Gate Management',
   'Gate entry and security logs.', 7, false,
   'none', 'No backend. The Settings screen''s gate pre-approval toggle is stored but read by nothing.'),
  ('parking-management', 'Parking Management',
   'Manage resident and visitor parking.', 8, false,
   'none', 'No backend, no frontend screen, no ERD table.'),
  ('staff-management', 'Staff Management',
   'Manage housekeeping, electricians, plumbers, etc.', 9, false,
   'implemented', 'Build step 6. Departments and staff assignments.'),
  ('community-marketplace', 'Community Marketplace',
   'Residents can buy, sell, and exchange items.', 10, false,
   'none', 'No backend, no frontend screen, no ERD table.')
on conflict (module_key) do update
  set display_name    = excluded.display_name,
      description     = excluded.description,
      sort_order      = excluded.sort_order,
      default_enabled = excluded.default_enabled,
      backend_status  = excluded.backend_status,
      backend_note    = excluded.backend_note;

-- Backfill any community that is missing a module row, so the catalogue and the
-- per-community table agree even for communities created between 0011 and now.
insert into public.community_modules (community_id, module_key, enabled)
select a.id, c.module_key, c.default_enabled
  from public.associations a
 cross join public.module_catalogue c
on conflict (community_id, module_key) do nothing;

-- ---------------------------------------------------------------------------
-- community_settings
--
-- Lazily created: a community that has never saved settings has no row, and
-- `community_settings_overview` reports the defaults for it. Same pattern as
-- `community_billing_settings` in 0015 -- a screen asking what the settings are
-- should not have to know whether anybody has ever saved them.
--
-- `unit_label_singular` is NULLABLE and null means "derive it", rather than being
-- populated with 'Flat' at insert time. The ERD says the value is derived from
-- community_type; making it a stored default would mean a community that switches
-- type keeps a label that is now wrong, and nothing would ever notice. Null is
-- overridable -- a community that calls them "Apartments" or "Homes" can say so.
-- ---------------------------------------------------------------------------
create table if not exists public.community_settings (
  community_id                 uuid primary key
                               references public.associations(id) on delete cascade,
  -- IANA name. Validated in save_community_settings against pg_timezone_names;
  -- see the header for why this is not a CHECK.
  timezone                     text not null default 'Asia/Kolkata',
  -- Null = derive from community_type. See above.
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
  updated_by_membership_id     uuid,
  version                      integer not null default 1,
  created_at                   timestamptz not null default now(),
  updated_at                   timestamptz not null default now(),
  constraint community_settings_updated_by_fk
    foreign key (updated_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (updated_by_membership_id),
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

drop trigger if exists community_settings_set_updated_at on public.community_settings;
create trigger community_settings_set_updated_at
  before update on public.community_settings
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- community_billing_settings -- the two billing toggles from the Settings screen
--
-- Added to 0015's table rather than to `community_settings`, because they are
-- money and money already has a home, an endpoint pair and an RLS policy. The
-- Settings screen renders them next to the other two; that is a layout fact, not
-- a schema one.
--
-- The two cross-field constraints are the point of this block. A toggle that can
-- be switched on without the number it needs is a toggle that produces either
-- nothing or a guess, and 0015 already refused to guess a maintenance amount
-- (`run_maintenance_billing` raises rather than inventing one). The same rule is
-- enforced here one level earlier: you cannot turn automated billing ON until a
-- rate exists, and you cannot turn late fees ON until an amount exists.
-- ---------------------------------------------------------------------------
alter table public.community_billing_settings
  add column if not exists auto_billing_enabled boolean not null default false;

-- Day of month the scheduled run would use. Capped at 28 for the same reason
-- `maintenance_due_day` is: "the 30th" must not become "the 2nd of March" every
-- February. The frontend's copy says the 1st, which is the default.
alter table public.community_billing_settings
  add column if not exists auto_billing_day smallint not null default 1;

alter table public.community_billing_settings
  add column if not exists late_fee_enabled boolean not null default false;

-- NULLABLE, and null means "not configured". The frontend's copy says a flat
-- Rs.100 weekly fine, but writing 100 in here as a default would repeat exactly
-- the mistake A13 is about: a number that appears in prose becoming a number the
-- system charges people, with nobody having decided it.
alter table public.community_billing_settings
  add column if not exists late_fee_amount numeric(12, 2);

alter table public.community_billing_settings
  add column if not exists late_fee_grace_days smallint not null default 10;

alter table public.community_billing_settings
  add column if not exists late_fee_period text not null default 'weekly';

do $$
begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.community_billing_settings'::regclass
                    and conname = 'community_billing_settings_auto_day_ck') then
    alter table public.community_billing_settings
      add constraint community_billing_settings_auto_day_ck
      check (auto_billing_day between 1 and 28);
  end if;

  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.community_billing_settings'::regclass
                    and conname = 'community_billing_settings_late_grace_ck') then
    alter table public.community_billing_settings
      add constraint community_billing_settings_late_grace_ck
      check (late_fee_grace_days between 0 and 90);
  end if;

  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.community_billing_settings'::regclass
                    and conname = 'community_billing_settings_late_period_ck') then
    alter table public.community_billing_settings
      add constraint community_billing_settings_late_period_ck
      check (late_fee_period in ('weekly', 'monthly', 'once'));
  end if;

  -- The two cross-field rules. Backstops: the trigger below raises them first,
  -- with a message that names the field to set. These hold against direct SQL.
  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.community_billing_settings'::regclass
                    and conname = 'community_billing_settings_auto_needs_rate_ck') then
    alter table public.community_billing_settings
      add constraint community_billing_settings_auto_needs_rate_ck
      check (not auto_billing_enabled or default_maintenance_amount is not null);
  end if;

  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.community_billing_settings'::regclass
                    and conname = 'community_billing_settings_late_needs_amount_ck') then
    alter table public.community_billing_settings
      add constraint community_billing_settings_late_needs_amount_ck
      check (not late_fee_enabled
             or (late_fee_amount is not null and late_fee_amount > 0));
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- billing_settings_guard -- turns the two cross-field CHECKs into messages.
--
-- A raw CHECK violation reaches the API as SQLSTATE 23514 and the constraint
-- name. "community_billing_settings_auto_needs_rate_ck" is not something to show
-- an admin, and mapping constraint names to sentences in Python means the
-- sentence lives a long way from the rule. HB409 with the field named travels
-- through `app/core/pg_errors.py` as a 409 with a usable message.
-- ---------------------------------------------------------------------------
create or replace function public.billing_settings_guard()
returns trigger
language plpgsql
as $$
begin
  if new.auto_billing_enabled and new.default_maintenance_amount is null then
    raise exception
      'Automated monthly maintenance needs a maintenance amount. Set defaultMaintenanceAmount first.'
      using errcode = 'HB409';
  end if;

  if new.late_fee_enabled
     and (new.late_fee_amount is null or new.late_fee_amount <= 0) then
    raise exception
      'Late payment fines need a fine amount above zero. Set lateFeeAmount first.'
      using errcode = 'HB409';
  end if;

  return new;
end;
$$;

drop trigger if exists community_billing_settings_guard
  on public.community_billing_settings;
create trigger community_billing_settings_guard
  before insert or update on public.community_billing_settings
  for each row execute function public.billing_settings_guard();

-- ---------------------------------------------------------------------------
-- update_billing_settings -- replaced, not extended.
--
-- Reproduced in full from 0015 with six keys added. A settings patch that
-- silently ignores a key the caller sent is worse than one that fails: the API
-- would return 200 and the toggle would spring back on the next read, which is
-- the exact bug the current frontend has. Same signature, so 0015's grants
-- survive the replace.
-- ---------------------------------------------------------------------------
create or replace function public.update_billing_settings(
  p_community_id uuid,
  p_patch        jsonb
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.assert_billing_admin(p_community_id);
  perform public.ensure_billing_settings(p_community_id);

  update public.community_billing_settings x
     set currency_code = case when p_patch ? 'currency_code'
           then upper(p_patch ->> 'currency_code') else x.currency_code end,
         invoice_number_prefix = case when p_patch ? 'invoice_number_prefix'
           then upper(p_patch ->> 'invoice_number_prefix') else x.invoice_number_prefix end,
         -- Key PRESENCE, not value: `{"default_maintenance_amount": null}` clears
         -- the rate, an absent key leaves it alone. Matches the API's
         -- model_dump(exclude_unset=True).
         default_maintenance_amount = case when p_patch ? 'default_maintenance_amount'
           then (p_patch ->> 'default_maintenance_amount')::numeric
           else x.default_maintenance_amount end,
         maintenance_due_day = case when p_patch ? 'maintenance_due_day'
           then (p_patch ->> 'maintenance_due_day')::smallint else x.maintenance_due_day end,
         default_tax_percent = case when p_patch ? 'default_tax_percent'
           then (p_patch ->> 'default_tax_percent')::numeric else x.default_tax_percent end,
         -- 0017 additions.
         auto_billing_enabled = case when p_patch ? 'auto_billing_enabled'
           then (p_patch ->> 'auto_billing_enabled')::boolean else x.auto_billing_enabled end,
         auto_billing_day = case when p_patch ? 'auto_billing_day'
           then (p_patch ->> 'auto_billing_day')::smallint else x.auto_billing_day end,
         late_fee_enabled = case when p_patch ? 'late_fee_enabled'
           then (p_patch ->> 'late_fee_enabled')::boolean else x.late_fee_enabled end,
         late_fee_amount = case when p_patch ? 'late_fee_amount'
           then (p_patch ->> 'late_fee_amount')::numeric else x.late_fee_amount end,
         late_fee_grace_days = case when p_patch ? 'late_fee_grace_days'
           then (p_patch ->> 'late_fee_grace_days')::smallint else x.late_fee_grace_days end,
         late_fee_period = case when p_patch ? 'late_fee_period'
           then lower(p_patch ->> 'late_fee_period') else x.late_fee_period end,
         version = x.version + 1
   where x.community_id = p_community_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- community_settings_overview
--
-- One read for the whole screen: the community's identity, its preferences with
-- defaults filled in for a community that has never saved any, the billing
-- toggles (read-only here -- `PUT /billing-settings` is the only writer), and
-- three module counts.
--
-- `security_invoker = true` so the view is filtered by the CALLER's RLS rather
-- than the view owner's. Without it a view over `associations` would show every
-- community in the database to anybody who can select from it.
--
-- ADMIN-ONLY BY CONSEQUENCE: the billing columns come from
-- `community_billing_settings`, whose only policy is admin. A resident selecting
-- this view would get the COALESCE defaults for those six columns rather than an
-- error -- false, 1, 'weekly' -- which reads as data and is not. `GET /settings`
-- is admin-only for that reason; anything a resident needs from here (timezone,
-- unit label) belongs on a narrower view.
-- ---------------------------------------------------------------------------
create or replace view public.community_settings_overview
with (security_invoker = true) as
select
  a.id                                            as community_id,
  a.name                                          as community_name,
  a.community_type,
  a.status                                        as community_status,
  a.created_at                                    as community_created_at,

  coalesce(s.timezone, 'Asia/Kolkata')            as timezone,
  -- Derived unless overridden. 'apartment' -> Flat, anything else -> Villa,
  -- matching the ERD's own note and the two values in COMMUNITY_TYPES.
  coalesce(
    nullif(trim(s.unit_label_singular), ''),
    case when a.community_type = 'apartment' then 'Flat' else 'Villa' end
  )                                               as unit_label_singular,
  (nullif(trim(s.unit_label_singular), '') is null) as unit_label_is_derived,
  coalesce(s.invite_ttl_hours, 72)                as invite_ttl_hours,
  coalesce(s.visitor_code_ttl_minutes, 120)       as visitor_code_ttl_minutes,
  coalesce(s.require_visitor_preapproval, true)   as require_visitor_preapproval,
  coalesce(s.notice_sms_broadcast_enabled, false) as notice_sms_broadcast_enabled,
  -- Lets the API say "these are defaults, nobody has saved yet" instead of
  -- implying an admin chose them.
  (s.community_id is not null)                    as has_saved_settings,
  coalesce(s.version, 0)                          as version,
  s.updated_at                                    as settings_updated_at,
  p.full_name                                     as settings_updated_by_name,

  -- Billing, read-only. Sourced here so one GET renders the whole settings card;
  -- writes stay on `PUT /billing-settings` so money has exactly one writer.
  coalesce(b.auto_billing_enabled, false)         as auto_billing_enabled,
  coalesce(b.auto_billing_day, 1)                 as auto_billing_day,
  coalesce(b.late_fee_enabled, false)             as late_fee_enabled,
  b.late_fee_amount                               as late_fee_amount,
  coalesce(b.late_fee_grace_days, 10)             as late_fee_grace_days,
  coalesce(b.late_fee_period, 'weekly')           as late_fee_period,
  b.default_maintenance_amount                    as default_maintenance_amount,

  (select count(*) from public.module_catalogue)  as modules_total,
  (select count(*)
     from public.module_catalogue c
     left join public.community_modules m
            on m.community_id = a.id and m.module_key = c.module_key
    where coalesce(m.enabled, c.default_enabled)) as modules_enabled,
  -- The number worth putting on a screen: modules an admin has switched on that
  -- nothing in the product implements.
  (select count(*)
     from public.module_catalogue c
     left join public.community_modules m
            on m.community_id = a.id and m.module_key = c.module_key
    where coalesce(m.enabled, c.default_enabled)
      and c.backend_status = 'none')              as modules_enabled_without_backend
from public.associations a
left join public.community_settings s        on s.community_id = a.id
left join public.community_billing_settings b on b.community_id = a.id
left join public.community_memberships mm    on mm.id = s.updated_by_membership_id
left join public.profiles p                  on p.id = mm.profile_id;

-- ---------------------------------------------------------------------------
-- community_module_overview
--
-- The CATALOGUE drives this join, not `community_modules`. A community missing a
-- row for a key -- which happens to every community the moment an eleventh
-- module is added -- reads as that key's default rather than disappearing from
-- the list. A settings screen that silently omits a module is a screen that
-- cannot be used to turn it on.
-- ---------------------------------------------------------------------------
create or replace view public.community_module_overview
with (security_invoker = true) as
select
  a.id                                     as community_id,
  c.module_key,
  c.display_name,
  c.description,
  c.sort_order,
  c.backend_status,
  c.backend_note,
  c.default_enabled,
  coalesce(m.enabled, c.default_enabled)   as enabled,
  -- True when nobody has ever set this key for this community.
  (m.community_id is null)                 as is_default,
  m.updated_at                             as updated_at,
  m.updated_by_membership_id,
  p.full_name                              as updated_by_name
from public.associations a
cross join public.module_catalogue c
left join public.community_modules m
       on m.community_id = a.id and m.module_key = c.module_key
left join public.community_memberships mm on mm.id = m.updated_by_membership_id
left join public.profiles p on p.id = mm.profile_id;

-- ---------------------------------------------------------------------------
-- save_community_settings
--
-- Lazy upsert plus the timezone check. Every key is optional; an absent key
-- leaves the stored value alone, and `unit_label_singular: null` explicitly
-- clears the override and goes back to deriving it -- distinct from omitting the
-- key, exactly as `default_maintenance_amount` behaves in 0015.
-- ---------------------------------------------------------------------------
create or replace function public.save_community_settings(
  p_community_id uuid,
  p_payload      jsonb
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_actor    uuid;
  v_timezone text;
begin
  perform public.assert_community_admin(p_community_id);
  v_actor := public.current_membership_id(p_community_id);

  if p_payload ? 'timezone' then
    v_timezone := trim(p_payload ->> 'timezone');
    if v_timezone is null or v_timezone = '' then
      raise exception 'A timezone is required.' using errcode = 'HB409';
    end if;
    -- Case-insensitive because 'asia/kolkata' is the same zone and a form field
    -- will eventually send it. The stored value is the catalogue's spelling.
    select n.name into v_timezone
      from pg_timezone_names n
     where lower(n.name) = lower(v_timezone)
     limit 1;
    if v_timezone is null then
      raise exception
        'Unknown timezone. Use an IANA name such as Asia/Kolkata.'
        using errcode = 'HB409';
    end if;
  end if;

  insert into public.community_settings (community_id)
  values (p_community_id)
  on conflict (community_id) do nothing;

  update public.community_settings x
     set timezone = coalesce(v_timezone, x.timezone),
         -- Key presence: null clears the override, absent leaves it.
         unit_label_singular = case when p_payload ? 'unit_label_singular'
           then nullif(trim(p_payload ->> 'unit_label_singular'), '')
           else x.unit_label_singular end,
         invite_ttl_hours = case when p_payload ? 'invite_ttl_hours'
           then (p_payload ->> 'invite_ttl_hours')::integer
           else x.invite_ttl_hours end,
         visitor_code_ttl_minutes = case when p_payload ? 'visitor_code_ttl_minutes'
           then (p_payload ->> 'visitor_code_ttl_minutes')::integer
           else x.visitor_code_ttl_minutes end,
         require_visitor_preapproval = case when p_payload ? 'require_visitor_preapproval'
           then (p_payload ->> 'require_visitor_preapproval')::boolean
           else x.require_visitor_preapproval end,
         notice_sms_broadcast_enabled = case when p_payload ? 'notice_sms_broadcast_enabled'
           then (p_payload ->> 'notice_sms_broadcast_enabled')::boolean
           else x.notice_sms_broadcast_enabled end,
         updated_by_membership_id = coalesce(v_actor, x.updated_by_membership_id),
         version = x.version + 1
   where x.community_id = p_community_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- set_community_module -- one key at a time.
--
-- 0011's comment on `community_modules` gives the reason this exists as well as
-- the bulk write: "the Settings screen needs to toggle one module without
-- rewriting the whole set". Two admins toggling two different modules at the
-- same moment must not undo each other, and with a single-key write they do not.
-- ---------------------------------------------------------------------------
create or replace function public.set_community_module(
  p_community_id uuid,
  p_module_key   text,
  p_enabled      boolean
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_actor uuid;
  v_key   text;
begin
  perform public.assert_community_admin(p_community_id);
  v_actor := public.current_membership_id(p_community_id);

  select c.module_key into v_key
    from public.module_catalogue c
   where c.module_key = lower(trim(p_module_key));

  if v_key is null then
    raise exception 'Unknown module.' using errcode = 'HB404';
  end if;

  if p_enabled is null then
    raise exception 'enabled is required.' using errcode = 'HB409';
  end if;

  insert into public.community_modules
    (community_id, module_key, enabled, updated_by_membership_id)
  values (p_community_id, v_key, p_enabled, v_actor)
  on conflict (community_id, module_key) do update
    set enabled                  = excluded.enabled,
        updated_by_membership_id = excluded.updated_by_membership_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- set_community_modules -- the whole set, from an array of enabled keys.
--
-- The shape the onboarding wizard already produces: `enabledModules` is an array
-- of the keys that are on, and every other key is off by omission. Keys are ALL
-- validated before anything is written, so one typo in a ten-element array does
-- not leave a community half-configured.
-- ---------------------------------------------------------------------------
create or replace function public.set_community_modules(
  p_community_id uuid,
  p_module_keys  text[]
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_actor uuid;
  v_keys  text[];
  v_bad   text;
begin
  perform public.assert_community_admin(p_community_id);
  v_actor := public.current_membership_id(p_community_id);

  -- An empty array is legitimate (every module off). A null one is a caller that
  -- forgot the field, and would silently disable everything.
  if p_module_keys is null then
    raise exception 'moduleKeys is required.' using errcode = 'HB409';
  end if;

  select array_agg(distinct lower(trim(k))) into v_keys
    from unnest(p_module_keys) as k
   where nullif(trim(k), '') is not null;
  v_keys := coalesce(v_keys, '{}'::text[]);

  select k into v_bad
    from unnest(v_keys) as k
   where not exists (select 1 from public.module_catalogue c where c.module_key = k)
   limit 1;

  if v_bad is not null then
    raise exception 'Unknown module: %.', v_bad using errcode = 'HB404';
  end if;

  -- Every catalogue key is written, not just the listed ones -- otherwise a key
  -- dropped from the array would keep its old value instead of turning off.
  insert into public.community_modules
    (community_id, module_key, enabled, updated_by_membership_id)
  select p_community_id, c.module_key, c.module_key = any(v_keys), v_actor
    from public.module_catalogue c
  on conflict (community_id, module_key) do update
    set enabled                  = excluded.enabled,
        updated_by_membership_id = excluded.updated_by_membership_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- Grants. The three write RPCs assert admin internally and are callable by any
-- authenticated role; `anon` is not one.
-- ---------------------------------------------------------------------------
revoke execute on function public.save_community_settings(uuid, jsonb) from public, anon;
revoke execute on function public.set_community_module(uuid, text, boolean) from public, anon;
revoke execute on function public.set_community_modules(uuid, text[]) from public, anon;

grant execute on function public.save_community_settings(uuid, jsonb) to authenticated;
grant execute on function public.set_community_module(uuid, text, boolean) to authenticated;
grant execute on function public.set_community_modules(uuid, text[]) to authenticated;

-- Supabase's default privileges normally cover new public tables, but the read
-- grant on `module_catalogue` is load-bearing in a way the others are not: it is
-- the driving side of both views, and without SELECT the views return nothing
-- rather than failing loudly.
grant select on public.module_catalogue to authenticated;
grant select on public.community_settings to authenticated;

-- ---------------------------------------------------------------------------
-- Row-Level Security
--
-- `module_catalogue` has a read policy and NO WRITE POLICY AT ALL. It is a copy
-- of a frontend contract, seeded by migration; nothing at runtime has any
-- business editing it, and a table nobody can write is a table nobody can
-- corrupt. Adding a module means adding a migration, which is the correct amount
-- of friction for changing a contract.
--
-- `community_settings` reads are open to every member, not just admins: a
-- resident's booking form needs the timezone, and the unit label appears on
-- every screen that says "Flat" or "Villa". None of the columns is sensitive.
-- ---------------------------------------------------------------------------
alter table public.module_catalogue enable row level security;
alter table public.community_settings enable row level security;

drop policy if exists module_catalogue_read on public.module_catalogue;
create policy module_catalogue_read on public.module_catalogue
  for select to authenticated using (true);

drop policy if exists community_settings_member_read on public.community_settings;
create policy community_settings_member_read on public.community_settings
  for select using (community_id in (select public.current_community_ids()));

drop policy if exists community_settings_admin_all on public.community_settings;
create policy community_settings_admin_all on public.community_settings
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

-- ---------------------------------------------------------------------------
-- Verification -- run after applying. Each returns zero rows unless noted.
-- ---------------------------------------------------------------------------
-- Both views are security_invoker (expect two rows, both 'true'):
--   select c.relname, (select option_value from pg_options_to_table(c.reloptions)
--                       where option_name = 'security_invoker')
--   from pg_class c
--   where c.relname in ('community_settings_overview', 'community_module_overview');
--
-- The catalogue matches frontend/src/data/onboardingModules.js (expect ten rows,
-- and compare the keys by eye against that file):
--   select module_key, default_enabled, backend_status from public.module_catalogue
--   order by sort_order;
--
-- Every community has a row for every catalogue key (the backfill above):
--   select a.id, c.module_key
--   from public.associations a
--   cross join public.module_catalogue c
--   left join public.community_modules m
--          on m.community_id = a.id and m.module_key = c.module_key
--   where m.community_id is null;
--
-- No community_modules row references a key the catalogue does not have. This
-- CAN return rows -- there is deliberately no FK, because 0011 seeded the keys
-- before the catalogue existed and a stale key should be visible rather than
-- block the migration:
--   select m.community_id, m.module_key
--   from public.community_modules m
--   left join public.module_catalogue c on c.module_key = m.module_key
--   where c.module_key is null;
--
-- No community has automated billing on without a rate, or late fees on without
-- an amount (the CHECKs should make both impossible):
--   select community_id from public.community_billing_settings
--   where (auto_billing_enabled and default_maintenance_amount is null)
--      or (late_fee_enabled and coalesce(late_fee_amount, 0) <= 0);
--
-- Every stored timezone is one PostgreSQL recognises (the RPC should make this
-- impossible; direct SQL can still break it):
--   select s.community_id, s.timezone from public.community_settings s
--   where not exists (select 1 from pg_timezone_names n where n.name = s.timezone);
--
-- The overview's module counts agree with a direct count (expect one row per
-- community, each pair matching):
--   select o.community_id, o.modules_enabled,
--          (select count(*) from public.community_module_overview v
--            where v.community_id = o.community_id and v.enabled)
--   from public.community_settings_overview o;
--
-- Every community that has saved settings has a derivable unit label (expect one
-- row per community, none of them null or empty):
--   select community_id, unit_label_singular, unit_label_is_derived
--   from public.community_settings_overview;
