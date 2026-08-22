-- 20260823150000_hosted_invite_claim_names.sql
--
-- Resident email-invite redemption fails on the hosted project, and has since
-- the project was linked. `memberships_repository.claim_resident_invite`
-- (backend/app/repositories/memberships_repository.py 61) calls the RPC named
-- `claim_email_invitation`; the owner's read-only probe of 2026-08-23 (runbook
-- §22, probe (e)) found that hosted has **only**
-- `claim_resident_invite(p_invite_id uuid, p_profile_id uuid)`. PostgREST
-- answers PGRST202 for the missing name and `invitation_service`
-- (redeem_pending_invitation, ~111) turns that into the generic
-- "This invite could not be claimed." So the invitee sees a refusal with no
-- cause and there is nothing wrong with the invite.
--
-- The hosted project predates `0001_baseline.sql` -- that file was never
-- applied there -- and `0001_baseline.sql` 98 is where
-- `claim_email_invitation` comes from on a fresh database. Hosted's
-- `claim_resident_invite` carries the **identical** signature and return shape
-- `TABLE(membership_id uuid, community_id uuid, unit_id uuid)`, so this is a
-- naming divergence and nothing more.
--
-- Two names, one behaviour. Rewriting the backend to call
-- `claim_resident_invite` would break every fresh database, where only
-- `claim_email_invitation` exists; copying `0001`'s body forward would put two
-- independent definitions of the same transaction on two databases. So the
-- name the code calls is created on hosted as a **thin delegating wrapper**
-- over the function hosted already has. One implementation stays; only the
-- entry point is added.
--
-- Conditional and fresh-safe: the wrapper is created only where
-- `claim_resident_invite` exists *and* `claim_email_invitation` does not. On a
-- fresh database `0001` already made `claim_email_invitation` and nothing ever
-- makes `claim_resident_invite`, so both halves of the condition are false and
-- this file is a no-op. Re-running on hosted is a no-op too, for the same
-- reason -- the second run finds the wrapper it made.
--
-- Security posture is `0001_baseline.sql`'s, copied deliberately rather than
-- chosen: `security definer`, `set search_path = public`, `revoke all ... from
-- public, anon, authenticated`, `grant execute ... to service_role`
-- (`0001_baseline.sql` 98, 269, 275). Nothing later in this directory touches
-- that ACL -- `20260812113000` only mentions the function in a comment. Only
-- the backend's service client may claim an invite, then and now.
--
-- The delegating select names its columns through an alias rather than `select
-- *`: the wrapper's three OUT parameters are spelled exactly like the inner
-- function's three result columns, and a qualified reference cannot be
-- mistaken for a plpgsql variable whatever a future editor does to either
-- side.
--
-- Hand-applied by the owner in the Supabase SQL editor, like every file in
-- this directory. Runbook §24.

do $$
begin
  if to_regprocedure('public.claim_resident_invite(uuid,uuid)') is not null
     and to_regprocedure('public.claim_email_invitation(uuid,uuid)') is null then

    execute format(
      'create function public.claim_email_invitation(p_invite_id uuid, p_profile_id uuid) '
      'returns table(membership_id uuid, community_id uuid, unit_id uuid) '
      'language plpgsql security definer set search_path = public as %L',
      $body$
begin
  return query
    select claimed.membership_id, claimed.community_id, claimed.unit_id
      from public.claim_resident_invite(p_invite_id, p_profile_id) as claimed;
end
$body$
    );

    execute 'revoke all on function public.claim_email_invitation(uuid,uuid) from public, anon, authenticated';
    execute 'grant execute on function public.claim_email_invitation(uuid,uuid) to service_role';
  end if;
end;
$$;

-- A database that gained a function PostgREST has never seen still answers
-- PGRST202 until its schema cache turns over. Refresh it now rather than
-- waiting out the polling interval.
notify pgrst, 'reload schema';
