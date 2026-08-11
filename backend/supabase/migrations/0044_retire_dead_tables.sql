-- 0044_retire_dead_tables.sql
--
-- Two baseline tables die here, and the interesting thing about each is what
-- replaced it — recorded so the next reader does not think design work was
-- discarded.
--
-- `staff_skills` (0001) keyed a skill to a roster row. The search the product
-- actually asks — "which communities need my trades" — is asked by somebody who
-- is on no roster at all, which is exactly when a roster-keyed skill returns
-- nothing. `service_provider_skills` (0034, decision D2) keys the skill to the
-- person instead, and has been the only skills table anything reads since.
--
-- `vendors` (0001) modelled a service company outside the tenancy model. D1
-- ruled the other way: a service person is a `profiles` row with one global
-- `service_providers` record and a `worker` membership per community that hires
-- them, so every guard, RLS predicate and tenancy path that already exists
-- applies to them unchanged. Nothing ever wrote a vendors row; the only live
-- reference is `staff_assignments.vendor_id`, a column that has been null on
-- every row that could ever have existed, and it goes first because its foreign
-- key would otherwise block the table.
--
-- R16 in docs/CONFLICT_RESOLUTIONS.md parked both tables in 2026 and its
-- 2026-08-10 amendment announces this migration by name. No migration in this
-- directory has ever been applied to any database (README), so these drops
-- destroy no data anywhere; they exist so the first real apply builds the
-- schema the code was actually written against.

-- ---------------------------------------------------------------------------
-- 1. The dependent column first: its FK targets vendors.
-- ---------------------------------------------------------------------------

alter table public.staff_assignments
  drop column if exists vendor_id;

-- ---------------------------------------------------------------------------
-- 2. The two superseded tables.
-- ---------------------------------------------------------------------------

drop table if exists public.staff_skills;

drop table if exists public.vendors;
