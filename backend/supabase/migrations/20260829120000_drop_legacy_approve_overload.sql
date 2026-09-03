-- ---------------------------------------------------------------------------
-- 20260829120000_drop_legacy_approve_overload.sql
--
-- A stray overload of `approve_access_request` exists on the hosted database
-- in NO migration in this tree:
--
--   approve_access_request(p_access_request_id uuid, p_profile_id uuid,
--     p_default_invoice_amount numeric, p_due_at timestamptz)
--
-- SECURITY DEFINER, returns uuid. In one call it approves an access request
-- and inserts a `community_membership`, a `unit_residencies` row, and an
-- ISSUED `maintenance` invoice numbered `'MNT-YYYYMMDD-<request uuid>'` --
-- prototype-era semantics that predate this repository's migration baseline
-- and were never captured here.
--
-- **Why it goes.** It is dead legacy code that, if ever invoked, writes real
-- membership, residency and invoice rows nobody asked for -- nothing in this
-- tree references `p_access_request_id`, `p_default_invoice_amount`,
-- `p_due_at` or the `MNT-` prefix (checked by grep across the repository).
-- The current backend calls the residency-shaped overload by its own named
-- parameters (`p_request_id`, `p_reviewer_profile_id`, ...), never this
-- one's. Dropping it also makes `approve_access_request` unambiguous by
-- signature, which is what runbook section 33's post-check (a) ("exactly
-- one row, pronargs = 6") assumes -- a database carrying both this stray and
-- `20260828090000_residence_claim_on_join.sql`'s 6-arg replacement reports
-- two rows there, not one.
--
-- **This file owns the stray alone.** It does not create, drop or reference
-- the 6-arg `(uuid, uuid, uuid, public.residency_relationship, text, text)`
-- signature `20260828090000` installs -- that file's business is its own,
-- and this one applies cleanly whether §33 has landed yet or not, and in
-- either order.
--
-- Idempotent: `drop function if exists` no-ops on a database that never had
-- the stray, or has already had it dropped. One transaction: the SQL editor
-- wraps the paste, so a failure anywhere rolls back everything.
--
-- Hand-applied by the owner in the Supabase SQL editor, like every file
-- here. Runbook section 34.
--
-- ROLLBACK: there is nothing to roll back to -- the dropped function is
-- hosted-only prototype code declared in no migration, so no `create` can
-- restore it from this tree. If the stray is ever needed again it must be
-- re-authored from the hosted `pg_get_functiondef` output before this file
-- was applied.
-- ---------------------------------------------------------------------------

drop function if exists public.approve_access_request(uuid, uuid, numeric, timestamptz);


-- ---------------------------------------------------------------------------
-- Proof, in the same transaction
--
-- The failure with no symptom here is a paste that silently no-ops against
-- the wrong signature while the stray survives. Read back rather than
-- assumed: `to_regprocedure` on the exact 4-arg (uuid, uuid, numeric,
-- timestamptz) shape must resolve to nothing once this statement has run.
-- ---------------------------------------------------------------------------

do $$
begin
  if to_regprocedure(
    'public.approve_access_request(uuid,uuid,numeric,timestamptz)'
  ) is not null then
    raise exception
      'the stray 4-arg approve_access_request(uuid,uuid,numeric,timestamptz) survived the drop';
  end if;

  raise notice
    'drop_legacy_approve_overload: the prototype 4-arg approve is gone; approve_access_request is unambiguous.';
end $$;


-- A dropped function IS a catalogue change: without the reload PostgREST
-- keeps answering for a signature that no longer exists until the next
-- restart.
notify pgrst, 'reload schema';
