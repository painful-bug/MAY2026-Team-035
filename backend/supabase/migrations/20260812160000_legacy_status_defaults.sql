-- The hosted database predates 0001_baseline.sql: its legacy tooling created
-- the status columns with title-cased defaults ('Active').
-- 20260730163759_normalize_community_statuses.sql normalized the existing
-- communities ROWS and added the canonical check constraint, but left the
-- column DEFAULT untouched — so any insert that relies on the default now
-- violates communities_status_canonical. create_founder_community is exactly
-- such an insert (it never names status), which means no community can be
-- created at all:
--
--   new row for relation "communities" violates check constraint
--   "communities_status_canonical" ... Failing row contains (..., Active, ...)
--
-- On a database created from 0001_baseline.sql these statements are no-ops
-- (the default is already 'active'); on the legacy-provisioned hosted
-- database they are the fix.
alter table public.communities
  alter column status set default 'active';

-- units shares both the legacy tooling and the founder-RPC insert path, but
-- got neither the row normalization nor a canonical constraint on 2026-07-30.
-- A title-cased unit status fails silently instead of loudly: the baseline's
-- unit-belongs-to-community check (0001_baseline.sql, resident invites and
-- access requests) filters on the unit's status = 'active', so an 'Active'
-- unit is invisible to resident onboarding. Normalize any such rows and fix
-- the default the same way.
update public.units
set status = lower(btrim(status))
where status is distinct from lower(btrim(status));

alter table public.units
  alter column status set default 'active';

do $$
declare
  v_default text;
begin
  select column_default into v_default
  from information_schema.columns
  where table_schema = 'public'
    and table_name = 'communities'
    and column_name = 'status';
  raise notice 'communities.status default is now %', v_default;
end $$;
