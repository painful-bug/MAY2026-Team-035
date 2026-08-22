-- ===========================================================================
-- Hosted schema drift: the work-order table's legacy NOT NULL columns.
--
-- WHAT THIS FIXES
--
-- `POST /api/v1/complaints/{id}/work-orders` fails 422 "Could not raise that
-- job." for every caller -- the supervisor's "Raise it" button in triage dies
-- on the spot, which is how it was found on 2026-08-22 in live testing. The
-- real error, captured through `app/core/pg_errors.py`'s server-side log:
--
--     SQLSTATE 23502: null value in column "title" of relation "work_orders"
--     violates not-null constraint
--
-- No repository migration has ever declared a `title` column on
-- `work_orders`. `0001_baseline.sql`:73 declares seven columns and
-- `0036_work_orders.sql`:113 adds thirteen more (plus `cancelled_by`,
-- `20260813101000`:5); `title` is in none of them, so `create_work_order`
-- (`0036`:654) rightly inserts no such value -- and the hosted table refuses
-- the row.
--
-- WHY THE COLUMN IS PRESENT
--
-- The same story `20260820120000_hosted_complaint_column_drift.sql` already
-- told for `complaints`: the linked project is **not** a `0001_baseline.sql`
-- project. Its `work_orders` is the pre-baseline hand-built table, and the
-- failing row shows four values no repository column accounts for. Every
-- migration from `0036` onward extends the table with `add column if not
-- exists`, so each applied cleanly around the legacy columns -- until an
-- insert met the one that is `not null` with no default.
--
-- WHAT THIS DOES
--
-- Drops NOT NULL on every `work_orders` column that (a) the repository has
-- never declared, (b) is NOT NULL on the hosted table, and (c) has no
-- default -- i.e. exactly the set that can reject an insert written against
-- the repository's schema. A sweep rather than `title` alone, because
-- `20260820120000` 3 taught the lesson: these constraints bite one behind
-- the other, and a file that fixed only the first reported success while the
-- second waited. Legacy columns that are nullable, or NOT NULL with a
-- default, block nothing and are left exactly as they are.
--
-- WHAT THIS IS NOT
--
-- No new semantics: work orders do not gain a title -- the job's subject is
-- its complaint, which is the repository's model. Every change is a widening
-- (no row accepted before is rejected after), it moves the hosted table
-- *towards* the repository's declaration, and re-running the file is a
-- no-op. Nothing is dropped, written, or redefined.
--
-- ROLLBACK: alter table public.work_orders alter column <name> set not null;
--   per column named in this file's NOTICEs, and only while every row still
--   has a value in it.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. The sweep
--
-- The protected list is the repository's full declaration of `work_orders`:
-- `0001_baseline.sql`:73 (id, community_id, complaint_id, status, priority,
-- created_at, updated_at), `0036_work_orders.sql`:113-128 (department_id,
-- supervisor_membership_id, skill_id, scheduled_start_at, scheduled_end_at,
-- subject_kind, location_text, latitude, longitude, failed_attempt_count,
-- resident_deadline_at, cancelled_reason) and
-- `20260813101000_offer_consent_and_force.sql`:5 (cancelled_by).
-- `tests/test_hosted_work_order_drift_migration.py` derives the same list
-- from those files' own text and fails if this one ever disagrees with them.
-- ---------------------------------------------------------------------------
do $$
declare
  v_column  record;
  v_dropped integer := 0;
begin
  for v_column in
    select c.column_name
      from information_schema.columns c
     where c.table_schema = 'public'
       and c.table_name   = 'work_orders'
       and c.is_nullable  = 'NO'
       and c.column_default is null
       and c.column_name not in (
         'id', 'community_id', 'complaint_id', 'status', 'priority',
         'created_at', 'updated_at',
         'department_id', 'supervisor_membership_id', 'skill_id',
         'scheduled_start_at', 'scheduled_end_at', 'subject_kind',
         'location_text', 'latitude', 'longitude', 'failed_attempt_count',
         'resident_deadline_at', 'cancelled_reason', 'cancelled_by'
       )
     order by c.column_name
  loop
    execute format(
      'alter table public.work_orders alter column %I drop not null',
      v_column.column_name
    );
    v_dropped := v_dropped + 1;
    raise notice 'work_orders.% was a legacy NOT NULL column; now nullable',
      v_column.column_name;
  end loop;

  if v_dropped = 0 then
    raise notice 'no legacy NOT NULL columns found on work_orders -- '
      'either already applied, or this is a baseline-built database';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- 2. Verification, in the same transaction as the change
--
-- The shape `20260820120000` 4 ends with: if the file claims to have fixed
-- something, it fails rather than reporting success.
-- ---------------------------------------------------------------------------
do $$
declare
  v_leftover text;
begin
  select string_agg(c.column_name, ', ' order by c.column_name)
    into v_leftover
    from information_schema.columns c
   where c.table_schema = 'public'
     and c.table_name   = 'work_orders'
     and c.is_nullable  = 'NO'
     and c.column_default is null
     and c.column_name not in (
       'id', 'community_id', 'complaint_id', 'status', 'priority',
       'created_at', 'updated_at',
       'department_id', 'supervisor_membership_id', 'skill_id',
       'scheduled_start_at', 'scheduled_end_at', 'subject_kind',
       'location_text', 'latitude', 'longitude', 'failed_attempt_count',
       'resident_deadline_at', 'cancelled_reason', 'cancelled_by'
     );

  if v_leftover is not null then
    raise exception 'work_orders still carries insert-blocking legacy '
      'NOT NULL columns: %', v_leftover;
  end if;
end $$;
