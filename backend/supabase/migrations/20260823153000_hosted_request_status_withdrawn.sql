-- 20260823153000_hosted_request_status_withdrawn.sql
--
-- Withdrawing a join request fails on the hosted project. The endpoint is
-- `POST /access-requests/{id}/withdraw`
-- (backend/app/api/v1/routers/access_requests.py 43-51); the write is
-- `access_requests_repository` (~75-87) setting `status = 'withdrawn'` by way
-- of `access_request_service` (~251); and the list filter already accepts the
-- word (routers/access_requests.py 56). The owner's read-only probe of
-- 2026-08-23 (runbook §22, probe (f)) found that `access_requests.status` on
-- hosted is not text at all -- it is the enum `public.request_status`, whose
-- four labels are `{pending, approved, rejected, cancelled}`. Postgres answers
-- 22P02, `invalid input value for enum request_status: "withdrawn"`, and the
-- applicant cannot take their own request back.
--
-- The hosted project predates `0001_baseline.sql`, which was never applied
-- there. On a fresh database `0001_baseline.sql` 57 declares the column as
-- `status text not null default 'pending' check (status in ('pending',
-- 'approved','rejected','withdrawn'))` -- text with a check, and **no enum
-- type of that name exists anywhere in this directory**. So `withdrawn` is a
-- value the application has always been entitled to write; the enum is a
-- pre-baseline artefact that never learned it.
--
-- The label is added rather than the column retyped. Retyping
-- `access_requests.status` from the enum to text on hosted would rewrite a
-- live table, drop the enum's own guarantee, and leave hosted's shape
-- depending on the order two databases were built in. Adding the fifth label
-- is one catalogue row, widening only: every value the enum accepted before it
-- accepts after.
--
-- Conditional and fresh-safe: the `alter type` runs only where the enum type
-- exists. On a fresh database it does not, so this file is a no-op there; on
-- hosted the `if not exists` makes a second run a no-op as well.
--
-- **On the idiom.** `alter type ... add value` was refused inside any
-- transaction block -- and therefore inside any `do` body -- before
-- PostgreSQL 12. Since 12 it is allowed there, with the single remaining rule
-- that the new label may not be *used* until the transaction commits (reading
-- `pg_enum`, which the verification below does, is not a use of the value).
-- Every Supabase project runs a version well past that line, so the guarded
-- `do` block is safe as a single SQL-editor paste and is the idiom chosen
-- here: it is the only one that can be conditional, and being conditional is
-- what keeps the file a no-op on a fresh database. Nothing in this file reads
-- or writes the new label as a value, so the remaining rule is not in play. If
-- this were ever pasted into a pre-12 server it would fail loudly on the
-- `alter type` with nothing half-done; the fallback there is the bare
-- statement outside a transaction, and it is written out in runbook §25.
--
-- Hand-applied by the owner in the Supabase SQL editor, like every file in
-- this directory. Runbook §25.

do $$
begin
  if exists (
    select 1
      from pg_type t
      join pg_namespace n on n.oid = t.typnamespace
     where n.nspname = 'public'
       and t.typname = 'request_status'
       and t.typtype = 'e'
  ) then
    execute 'alter type public.request_status add value if not exists ''withdrawn''';
  end if;
end;
$$;

-- Where the enum exists it now carries the label the application writes.
do $$
begin
  if exists (
    select 1
      from pg_type t
      join pg_namespace n on n.oid = t.typnamespace
     where n.nspname = 'public'
       and t.typname = 'request_status'
       and t.typtype = 'e'
  ) and not exists (
    select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      join pg_namespace n on n.oid = t.typnamespace
     where n.nspname = 'public'
       and t.typname = 'request_status'
       and e.enumlabel = 'withdrawn'
  ) then
    raise exception 'public.request_status exists but still has no withdrawn label';
  end if;
end;
$$;
