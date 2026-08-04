-- ===========================================================================
-- Step 9 completed: the two settings views and the save RPC.
--
-- `0018_settings_on_baseline.sql` rebuilt the settings TABLES onto the baseline
-- but not the views that read them, which is why `GET`/`PUT /settings` were
-- still unrunnable after it. This finishes the job.
--
-- THIS FILE CLOSES CONFLICT C-11
--
-- The wiring audit deleted our three module endpoints because module selection
-- belongs to onboarding, which writes THEIR `community_features`. But the read
-- survived: `GET /settings` still reported modules from our own tables, so the
-- duplication the deletions were meant to remove was still there, one level
-- down.
--
-- `community_module_overview` is therefore built over their `feature_catalog`
-- and `community_features`. Ours are not rebuilt and `0017_settings.sql`'s
-- module tables are now permanently superseded -- there is exactly one place a
-- module's enabled state lives, and the onboarding workstream owns it.
--
-- What that costs: three columns of ours had no home in their catalogue, so they
-- are added to `feature_catalog` rather than kept in a parallel table. They are
-- editorial metadata about OUR backend -- whether an enabled module actually
-- does anything yet -- which is a fact about the code, not about the community.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Catalogue metadata
--
-- `sort_order` so the settings list matches the order the onboarding wizard
-- shows the same cards in. Their catalogue has no ordering column, so the list
-- would otherwise come back in whatever order the planner chose.
--
-- `backend_status` is the honest one. A community can switch on a module whose
-- backend does not exist, and the Settings screen should be able to say so
-- rather than implying the toggle did something. Values:
--   'live'    -- endpoints exist and are wired
--   'partial' -- endpoints exist, nothing calls them yet
--   'absent'  -- no backend at all
-- ---------------------------------------------------------------------------
alter table public.feature_catalog
  add column if not exists sort_order     integer not null default 0,
  add column if not exists backend_status text    not null default 'absent',
  add column if not exists backend_note   text;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'feature_catalog_backend_status_check'
  ) then
    alter table public.feature_catalog
      add constraint feature_catalog_backend_status_check
      check (backend_status in ('live', 'partial', 'absent'));
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- 2. community_module_overview
--
-- A CROSS JOIN, deliberately. The catalogue is the authority on which modules
-- exist; `community_features` only records the ones a community has an OPINION
-- about. A community that has never opened onboarding has no rows there at all,
-- and an inner join would report that it has no modules rather than that it has
-- ten at their defaults.
--
-- `is_default` is how the caller distinguishes "nobody has chosen" from "somebody
-- chose the same value the default happens to be" -- the two look identical in
-- `enabled` alone, and only the first should be silently changed by a change to
-- the catalogue default.
-- ---------------------------------------------------------------------------
drop view if exists public.community_module_overview;
create view public.community_module_overview
with (security_invoker = true) as
select
  c.id                                          as community_id,
  fc.code                                       as module_key,
  fc.name                                       as display_name,
  fc.description,
  fc.sort_order,
  fc.backend_status,
  fc.backend_note,
  fc.default_enabled,
  coalesce(cf.is_enabled, fc.default_enabled)   as enabled,
  (cf.community_id is null)                     as is_default,
  cf.updated_at,
  cf.updated_by_membership_id,
  pr.full_name                                  as updated_by_name
from public.communities c
cross join public.feature_catalog fc
left join public.community_features cf
       on cf.community_id = c.id
      and cf.feature_code = fc.code
left join public.community_memberships m on m.id = cf.updated_by_membership_id
left join public.profiles pr on pr.id = m.profile_id
where fc.is_active;

comment on view public.community_module_overview is
  'Every catalogue module with this community''s setting for it, defaulting from the catalogue. Reads their feature_catalog/community_features -- see C-11.';

-- ---------------------------------------------------------------------------
-- 3. community_settings_overview
--
-- One row per community, whether or not it has ever saved settings. The view
-- left-joins the settings row and fills in the defaults, so
-- `GET /settings` never has to distinguish "no row" from "no community" --
-- `has_saved_settings` carries that, and a missing row here means the community
-- itself is gone.
--
-- `unit_label_singular` is DERIVED when unset: an apartment community calls them
-- Flats, a villa layout calls them Villas. Null in the table means "derive",
-- not "unset", so the view resolves it and `unit_label_is_derived` says whether
-- it did.
--
-- `modules_enabled_without_backend` is the number this screen exists to
-- surface: modules a community has switched ON that do nothing. It is the
-- honest counterpart to a settings page full of working-looking toggles.
-- ---------------------------------------------------------------------------
drop view if exists public.community_settings_overview;
create view public.community_settings_overview
with (security_invoker = true) as
select
  c.id                          as community_id,
  c.name                        as community_name,
  c.community_type,
  c.status                      as community_status,
  c.created_at                  as community_created_at,

  coalesce(cs.timezone, c.timezone, 'Asia/Kolkata')  as timezone,
  coalesce(
    cs.unit_label_singular,
    case c.community_type when 'apartment' then 'Flat' else 'Villa' end
  )                             as unit_label_singular,
  (cs.unit_label_singular is null)                   as unit_label_is_derived,

  coalesce(cs.invite_ttl_hours, 72)                  as invite_ttl_hours,
  coalesce(cs.visitor_code_ttl_minutes, 120)         as visitor_code_ttl_minutes,
  coalesce(cs.require_visitor_preapproval, true)     as require_visitor_preapproval,
  coalesce(cs.notice_sms_broadcast_enabled, false)   as notice_sms_broadcast_enabled,

  (cs.community_id is not null) as has_saved_settings,
  coalesce(cs.version, 0)       as version,
  cs.updated_at                 as settings_updated_at,
  pr.full_name                  as settings_updated_by_name,

  -- The billing half of the Settings screen. Kept on this row because the
  -- screen shows one form, even though the storage is split -- money already had
  -- a home before settings did.
  coalesce(bs.auto_billing_enabled, false)   as auto_billing_enabled,
  coalesce(bs.auto_billing_day, 1)           as auto_billing_day,
  coalesce(bs.late_fee_enabled, false)       as late_fee_enabled,
  bs.late_fee_amount,
  coalesce(bs.late_fee_grace_days, 10)       as late_fee_grace_days,
  coalesce(bs.late_fee_period, 'weekly')     as late_fee_period,
  bs.default_maintenance_amount,

  coalesce(mo.modules_total, 0)                    as modules_total,
  coalesce(mo.modules_enabled, 0)                  as modules_enabled,
  coalesce(mo.modules_enabled_without_backend, 0)  as modules_enabled_without_backend
from public.communities c
left join public.community_settings cs         on cs.community_id = c.id
left join public.community_billing_settings bs on bs.community_id = c.id
left join public.community_memberships m       on m.id = cs.updated_by_membership_id
left join public.profiles pr                   on pr.id = m.profile_id
left join lateral (
  select
    count(*)                                                as modules_total,
    count(*) filter (where v.enabled)                       as modules_enabled,
    count(*) filter (where v.enabled and v.backend_status = 'absent')
                                                            as modules_enabled_without_backend
    from public.community_module_overview v
   where v.community_id = c.id
) mo on true;

comment on view public.community_settings_overview is
  'One settings snapshot per community, defaults filled in. has_saved_settings distinguishes a default row from a saved one.';

grant select on public.community_module_overview   to authenticated;
grant select on public.community_settings_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 4. save_community_settings
--
-- Creates the row on first use, so a community that has never opened the screen
-- does not 404 on its first save.
--
-- The timezone is validated against `pg_timezone_names` HERE rather than by a
-- CHECK constraint, because a CHECK must be immutable and the timezone
-- catalogue is loaded from the host. A bad zone is a `22023`, not a row that
-- silently makes every timestamp on the screen wrong.
--
-- An empty `unit_label_singular` is stored as NULL, not as ''. Null means
-- "derive from the community type", which is what clearing the field means; ''
-- would mean "this community calls its homes nothing at all".
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
  v_timezone   text;
  v_membership uuid;
begin
  if not public.is_community_admin(p_community_id) then
    raise exception 'Only an admin of this community may change its settings.'
      using errcode = '42501';
  end if;

  if p_payload ? 'timezone' then
    v_timezone := btrim(coalesce(p_payload ->> 'timezone', ''));
    if v_timezone = '' then
      raise exception 'A timezone is required.' using errcode = '22023';
    end if;
    if not exists (select 1 from pg_timezone_names where name = v_timezone) then
      raise exception 'Unknown timezone: %', v_timezone using errcode = '22023';
    end if;
  end if;

  -- Who is doing this, recorded so the screen can say when and by whom.
  select id into v_membership
    from public.community_memberships
   where community_id = p_community_id
     and profile_id = auth.uid()
     and status = 'active'
   limit 1;

  insert into public.community_settings (community_id)
  values (p_community_id)
  on conflict (community_id) do nothing;

  update public.community_settings
     set timezone                     = coalesce(v_timezone, timezone),
         unit_label_singular          = case when p_payload ? 'unit_label_singular'
                                             then nullif(btrim(coalesce(p_payload ->> 'unit_label_singular', '')), '')
                                             else unit_label_singular end,
         invite_ttl_hours             = case when p_payload ? 'invite_ttl_hours'
                                             then (p_payload ->> 'invite_ttl_hours')::integer
                                             else invite_ttl_hours end,
         visitor_code_ttl_minutes     = case when p_payload ? 'visitor_code_ttl_minutes'
                                             then (p_payload ->> 'visitor_code_ttl_minutes')::integer
                                             else visitor_code_ttl_minutes end,
         require_visitor_preapproval  = case when p_payload ? 'require_visitor_preapproval'
                                             then (p_payload ->> 'require_visitor_preapproval')::boolean
                                             else require_visitor_preapproval end,
         notice_sms_broadcast_enabled = case when p_payload ? 'notice_sms_broadcast_enabled'
                                             then (p_payload ->> 'notice_sms_broadcast_enabled')::boolean
                                             else notice_sms_broadcast_enabled end,
         updated_by_membership_id     = coalesce(v_membership, updated_by_membership_id),
         version                      = version + 1,
         updated_at                   = now()
   where community_id = p_community_id;
end $$;

grant execute on function public.save_community_settings(uuid, jsonb) to authenticated;

-- ---------------------------------------------------------------------------
-- 5. Seed the catalogue's backend status
--
-- Recorded as data rather than prose because the Settings screen renders it.
-- These are the ten modules `onboardingModules.js` offers. Anything already in
-- the catalogue keeps its name and default; only our three columns are set.
--
-- 'live' is claimed for nothing, because nothing is: every module below is
-- either unwired on the frontend or unbuilt on the backend. That is the point
-- of the column.
--
-- CORRECTED 2026-08-04, AND WHY IT NEEDED CORRECTING
--
-- This section originally guessed at the codes -- `('complaints',
-- 'complaint_management')`, `('visitors', 'visitor_management', 'security')` and
-- so on. The catalogue does not hold any of those. `0001` seeds exactly ten,
-- all hyphenated, and they are the ones written below.
--
-- So every statement here matched zero rows. Nothing failed and nothing warned:
-- an `update ... where` that selects nothing is a success. All ten modules would
-- have sat at the column defaults -- `sort_order = 0` and, worse,
-- `backend_status = 'absent'` -- and the Settings screen, whose entire purpose
-- is to stop a toggle implying a backend that is not there, would have reported
-- that none of this backend exists. The one screen built to be honest about
-- what is missing would have been the one lying.
--
-- Edited in place rather than repaired in a later migration: this file has never
-- been applied to any database, and a fix-up migration would leave the wrong
-- statement here for the next reader to copy -- which is how `0032` inherited
-- it.
--
-- All ten are listed now. The header has always claimed to seed the ten modules
-- `onboardingModules.js` offers; four of them were never mentioned.
-- ---------------------------------------------------------------------------
update public.feature_catalog set sort_order = 1, backend_status = 'partial',
  backend_note = 'Endpoints exist; the Complaints screen still calls a local store.'
 where code = 'complaint-management';

update public.feature_catalog set sort_order = 2, backend_status = 'partial',
  backend_note = 'Endpoints exist; the Amenities screens still call a local store.'
 where code = 'amenities-booking';

update public.feature_catalog set sort_order = 3, backend_status = 'partial',
  backend_note = 'POST /notices exists; the snapshot serves the reads.'
 where code = 'notice-board';

update public.feature_catalog set sort_order = 4, backend_status = 'partial',
  backend_note = 'Invoicing and payment endpoints exist, but nothing creates a maintenance run.'
 where code = 'maintenance-billing';

update public.feature_catalog set sort_order = 5, backend_status = 'partial',
  backend_note = 'Department and staff endpoints exist; the snapshot stubs staff as empty.'
 where code = 'staff-management';

update public.feature_catalog set sort_order = 6, backend_status = 'absent',
  backend_note = 'No visitor backend. The two visitor settings are stored but nothing reads them.'
 where code = 'visitor-management';

update public.feature_catalog set sort_order = 7, backend_status = 'absent',
  backend_note = 'No gate software. require_visitor_preapproval is stored and nothing reads it.'
 where code = 'security-gate-management';

update public.feature_catalog set sort_order = 8, backend_status = 'partial',
  backend_note = 'GET /residents and the invitation endpoints exist; nothing edits a resident.'
 where code = 'resident-management';

update public.feature_catalog set sort_order = 9, backend_status = 'absent',
  backend_note = 'No parking backend. The schema has no parking tables either.'
 where code = 'parking-management';

update public.feature_catalog set sort_order = 10, backend_status = 'absent',
  backend_note = 'No marketplace backend. The schema has no marketplace tables either.'
 where code = 'community-marketplace';
