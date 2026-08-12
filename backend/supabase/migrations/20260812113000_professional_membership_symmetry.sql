-- ---------------------------------------------------------------------------
-- The separate-account rule, enforced in both directions
--
-- The service-professional contract says an existing resident, manager or
-- administrator is told to use a **separate account** to register as a
-- professional. Two guards enforced exactly that, and both looked the same way:
--
--   * `register_service_provider` refuses a profile that already holds an
--     active non-professional membership
--     (`20260811162409_service_professional_onboarding.sql:87-98`);
--   * the frontend routes an already-membered identity away from the
--     professional flow (`frontend/src/routes/authRoutes.js:90-94`).
--
-- Nothing watched the other direction. A professional who registered *first*
-- and then joined a community as a resident -- an email invite claimed, or an
-- access request approved -- ended up as one account holding both identities:
-- the state the contract forbids, reached in the order neither guard checked.
-- `enforce_professional_membership_mode` looked like it should catch this and
-- did not: it only refused worker<->security coexistence, so a `resident` row
-- on a professional account sailed through. Recorded in
-- `docs/potential issues/16`.
--
-- The product owner ruled on 2026-08-12: **a registered professional is assumed
-- not to live in any association.** The rule is identity separation, not
-- session routing, so the missing direction is a hole and it is closed here.
-- The casualty is explicit and accepted: a plumber who genuinely lives in an
-- apartment community keeps two accounts, one per identity.
--
-- ## Where the check goes, and why it is the trigger rather than each RPC
--
-- There are five places a membership is written -- `claim_email_invitation`
-- (`0001`), the founder RPC (`20260805144502`), `approve_access_request`
-- (`0001` and `20260730165410`), the hiring RPCs (`20260811162409`) and
-- `claim_staff_invitations` (`20260812090200`) -- and four of them are in
-- applied files. A guard repeated five times is a guard that will be four
-- places the sixth writer does not know about. The trigger already exists, it
-- already fires `before insert or update of role, status, ended_at`, and it is
-- already the thing that answers "may this account hold this membership".
--
-- ## Why this file copies the whole function body
--
-- `20260811162409` is applied (`backend/supabase/migrations/README.md`: the
-- hosted verification post-dates it). The body below was extracted mechanically
-- from that file, so the starting point is provably the applied text, and every
-- difference from it is marked `-- CHANGED` in place.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- 1. enforce_professional_membership_mode -- both directions
--
-- The new predicate is the exact mirror of the registration-time refusal:
--
--   registration refuses  when  a `service_providers` row is absent
--                               and an active membership with a role not in
--                               ('worker','security') exists;
--   this refuses          when  a `service_providers` row is present
--                               and the row being written is an active
--                               membership with a role not in
--                               ('worker','security').
--
-- Deliberately symmetric in three details. It reads `exists (…)` on
-- `service_providers` with no `status` filter, because registration does: a
-- paused or suspended provider is still an account that carries a professional
-- identity. It ignores rows that are not `active` with a null `ended_at`,
-- because registration does: an ended membership is not an identity anyone
-- holds. And `role not in ('worker','security')` rather than a positive list of
-- the other three, because `membership_role` has exactly five values
-- (`0001_baseline.sql:10`) and the professional half is the half this file is
-- about -- a sixth role added later should be refused by default, not admitted
-- by omission.
--
-- The errcode is `HBSEP` rather than `HB409`. Both are 409s (`app/core/
-- pg_errors.py`), so the shape matches the registration-time refusal, but a
-- client that must tell "you already belong here" apart from "this account is
-- the wrong kind of account" cannot do it from an HTTP status, and reading the
-- message text to find out is the string matching the custom SQLSTATEs exist to
-- avoid.
-- ---------------------------------------------------------------------------

create or replace function public.enforce_professional_membership_mode()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  -- CHANGED: the other half of the separate-account rule. This runs before the
  -- early return below, which exists precisely to ignore the roles it refuses.
  if new.role not in ('worker', 'security')
     and new.status = 'active'
     and new.ended_at is null
     and exists (select 1 from public.service_providers where profile_id = new.profile_id) then
    raise exception 'This account is registered as a service professional. Use a separate account to join a community as a resident, manager or administrator.'
      using errcode = 'HBSEP';
  end if;

  if new.role not in ('worker', 'security')
     or new.status <> 'active'
     or new.ended_at is not null
     or not exists (select 1 from public.service_providers where profile_id = new.profile_id) then
    return new;
  end if;

  if exists (
    select 1 from public.community_memberships m
     where m.profile_id = new.profile_id
       and m.id <> new.id
       and m.role in ('worker', 'security')
       and m.role <> new.role
       and m.status = 'active'
       and m.ended_at is null
  ) then
    raise exception 'A professional account cannot mix worker and security memberships.' using errcode = 'HB409';
  end if;
  return new;
end;
$$;

comment on function public.enforce_professional_membership_mode() is
  'The separate-account rule inside the database, both ways: a registered '
  'service professional may not hold a resident, manager or administrator '
  'membership (HBSEP), and may not hold worker and security memberships at '
  'the same time (HB409). Mirrors register_service_provider''s refusal, which '
  'closes the same door from the other side.';

-- `create or replace function` keeps the trigger binding and the ACL, so
-- neither is re-declared. The revoke is re-issued because it costs nothing and
-- this is the file a reader will find first if they ask who may call it.
revoke all on function public.enforce_professional_membership_mode() from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- 1b. Rows that already break the rule are reported, never repaired
--
-- A `before` trigger judges the row being written, so an account that already
-- holds both identities keeps them until something updates its `role`, `status`
-- or `ended_at` -- and then that update fails, possibly in a queue job, with
-- nothing on screen to connect it to this file.
--
-- The temptation is to end those memberships here. This does not, and the
-- reason is not caution: **which identity to keep is not a question a migration
-- can answer.** Ending the membership evicts a household from its own community
-- portal; deleting the `service_providers` row destroys hiring history and the
-- applications attached to it. Both are somebody's account, and somebody has to
-- ask them. A notice puts the count in the deploy log, where whoever runs this
-- sees it while they still have the context to act on it.
--
-- Expected to be zero: the state has been reachable for a day, and the
-- professional base is a handful of accounts.
-- ---------------------------------------------------------------------------

do $$
declare
  v_count integer;
begin
  select count(*) into v_count
    from public.community_memberships m
    join public.service_providers p on p.profile_id = m.profile_id
   where m.role not in ('worker', 'security')
     and m.status = 'active'
     and m.ended_at is null;

  if v_count > 0 then
    raise notice
      'separate-account rule: % existing membership(s) are held by accounts that are also registered service providers. They are left as they are -- which identity to keep is the account holder''s decision, not this migration''s -- but any update to their role, status or ended_at will now be refused.',
      v_count;
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- 2. Ride-along: a comment that outlived its function body
--
-- `0034:531` still describes `search_serviceable_communities` as it was when
-- that file wrote it -- "communities with no coordinates sort last rather than
-- being hidden". `20260811162409` replaced the body with a radius-bounded one
-- whose `where` clause reads `c.location is not null` and whose `order by` is a
-- distance with no `nulls last` (…162409:405,419), so a community without
-- coordinates is now hidden, which is the opposite of what the catalogue says.
--
-- A `comment on` is not executable, so this is documentation drift rather than
-- a defect -- but it is documentation a reader gets from `\df+` in the database
-- itself, where there is no migration file beside it to correct the record.
-- Re-issued against the body that is actually installed. No function is
-- redefined here.
-- ---------------------------------------------------------------------------

comment on function public.search_serviceable_communities(text, integer, integer) is
  'Communities within the calling service person''s own service radius that '
  'have a department needing one of their active skills, have not blacklisted '
  'them, and do not already employ them; a professional already working as a '
  'worker or as a guard sees only departments of the matching kind. Ordered by '
  'distance, nearest first. A community with no coordinates is excluded, not '
  'sorted last: the search is radius-bounded, and there is no distance at which '
  'to bound a community that has not said where it is.';
