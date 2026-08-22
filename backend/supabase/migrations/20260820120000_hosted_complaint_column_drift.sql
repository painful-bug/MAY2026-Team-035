-- ===========================================================================
-- Hosted schema drift: the complaint engine's two missing baseline columns.
--
-- WHAT THIS FIXES
--
-- `POST /api/v1/complaints` fails 400 "Could not raise the complaint." The
-- real error, captured on 2026-08-20 through `app/core/pg_errors.py`:
--
--     SQLSTATE 42703: column "payload" of relation "complaint_events"
--     does not exist
--
-- `raise_complaint` (`20260813100000_skill_sourced_complaints.sql`:116) writes
-- `complaint_events (complaint_id, actor_membership_id, event_type, payload)`,
-- and the hosted table has no `payload`. Forty-five other insert sites across
-- twelve migrations write the same column, so this is not one endpoint.
--
-- WHY THE COLUMN IS ABSENT
--
-- The linked project is **not** a `0001_baseline.sql` project. It carries the
-- pre-baseline complaint schema — `complaint_events` still has the typed
-- `previous_status`, `new_status` and `note` columns that `0020`'s header
-- describes as "the legacy schema", plus `complaints.unit_id` and
-- `complaints.closed_at`, which the baseline has never declared.
--
-- Every migration from `0018` onward extends those tables with
-- `add column if not exists`, so each one applied cleanly. What none of them
-- adds is a column the *baseline* declares and nothing since has repeated:
-- `complaint_events.payload` (`0001`:70) and `complaints.aggregate_version`
-- (`0001`:69). Those two are the entire drift on this surface. Every RPC,
-- every argument list and every other column was probed present on the same
-- date — see `docs/HOSTED_SCHEMA_DRIFT_COMPLAINTS.md` for the evidence.
--
-- WHAT THIS IS NOT
--
-- No new semantics. Every statement below restates a declaration that already
-- exists in an applied repository migration; nothing here decides anything
-- about what a complaint means. No function is redefined, because no hosted
-- function was found stale: `raise_complaint` has its 8 arguments,
-- `resolve_complaint_department` its 4, `update_complaint` its 9, and all
-- thirty complaint-engine, dispatch and work-order RPCs that were probed are
-- present at the arity their latest migration gives them.
--
-- Safe on an empty surface: `complaints`, `complaint_events`,
-- `complaint_comments`, `work_orders` and `dispatch_tasks` all held 0 rows on
-- 2026-08-20, so no backfill is needed and no `not null` default rewrites data.
-- Idempotent regardless: re-running this file is a no-op.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. complaint_events.payload
--
-- Verbatim from `0001_baseline.sql`:70. `not null default '{}'::jsonb` is the
-- baseline's own declaration, and it is what lets the three writers that omit
-- the column entirely -- `on_complaint_resolved` and `dispatch_auto_close`
-- (`20260813104000_timers_v2.sql`:74, 92, 96) -- keep working.
--
-- The legacy `previous_status` / `new_status` / `note` columns are left where
-- they are. They are nullable, nothing in the repository writes them, and
-- `dashboard_repository.py`:67 still *reads* them in the legacy branch this
-- project takes (`visitor_access_requests` exists here, which is that branch's
-- feature test). Dropping them would break a read that works today.
--
-- ROLLBACK: alter table public.complaint_events drop column payload;
--   Safe only while nothing has written a timeline entry through it.
-- ---------------------------------------------------------------------------
alter table public.complaint_events
  add column if not exists payload jsonb not null default '{}'::jsonb;

-- ---------------------------------------------------------------------------
-- 2. complaints.aggregate_version
--
-- Verbatim from `0001_baseline.sql`:69. Four RPCs increment it on every write
-- and would each fail 42703 the moment they were called:
--
--   update_complaint                (`0031`:726)                  PATCH /complaints/{id}
--   reopen_complaint                (`20260812090300`:1099)       POST  /complaints/{id}/reopen
--   confirm_complaint_resolution    (`20260812090300`:1175)       POST  /complaints/{id}/resolution
--   add_complaint_comment           (`20260812090300`:1264)       POST  /complaints/{id}/comments
--
-- This is a second, independent break behind the first: fixing `payload`
-- alone leaves all four of those still failing.
--
-- ROLLBACK: alter table public.complaints drop column aggregate_version;
-- ---------------------------------------------------------------------------
alter table public.complaints
  add column if not exists aggregate_version integer not null default 1;

-- ---------------------------------------------------------------------------
-- 3. complaints.description may be null
--
-- The baseline declares `description text` -- nullable (`0001`:69). The hosted
-- column is `not null`, a legacy-only constraint no repository migration has
-- ever asked for.
--
-- It bites on the same endpoint as section 1, one statement earlier in the
-- same transaction. The API makes the field optional --
-- `resident_complaint_schemas.py`:168, `_optional_text(4000) = ""` -- and
-- `raise_complaint` writes `nullif(btrim(coalesce(p_description, '')), '')`,
-- which is null for the empty string the schema defaults to. A resident filing
-- a complaint with a title and no description gets a 23502 today. Nobody has
-- seen it yet only because section 1 fails first for everyone.
--
-- This is the one statement here that removes something rather than adding it.
-- It is still a widening -- no row that was accepted before is rejected after --
-- and it moves the hosted column *towards* the repository's declaration, not
-- away from it. The alternative direction (make description mandatory on the
-- wire) is a product question and is logged in
-- `docs/COMPLAINT_ENGINE_HANDOFF.md` §11 rather than decided here.
--
-- ROLLBACK: alter table public.complaints alter column description set not null;
--   Requires no null descriptions to exist by then.
-- ---------------------------------------------------------------------------
do $$
begin
  if exists (
    select 1 from information_schema.columns
     where table_schema = 'public'
       and table_name   = 'complaints'
       and column_name  = 'description'
       and is_nullable  = 'NO'
  ) then
    alter table public.complaints alter column description drop not null;
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- 4. Verification, in the same transaction as the change
--
-- The same shape `20260813100000` and `20260813103000` end with: if the file
-- claims to have fixed something, it fails rather than reporting success.
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'complaint_events'
       and column_name = 'payload'
  ) then
    raise exception 'complaint_events.payload still missing';
  end if;

  if not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'complaints'
       and column_name = 'aggregate_version'
  ) then
    raise exception 'complaints.aggregate_version still missing';
  end if;

  if exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'complaints'
       and column_name = 'description' and is_nullable = 'NO'
  ) then
    raise exception 'complaints.description is still not null';
  end if;
end $$;
