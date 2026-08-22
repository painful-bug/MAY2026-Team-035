-- ===========================================================================
-- Admin-raised complaints: `complaints.raised_via` and `admin_raise_complaint`.
--
-- HOW TO APPLY
--
-- Paste this whole file into the Supabase SQL editor (Dashboard -> SQL Editor
-- -> New query) and run it once. It is idempotent -- every statement is
-- guarded, so re-running it is a no-op -- and it ends with a verification block
-- that raises rather than reporting success if any part of it did not take.
-- Nothing here backfills or rewrites a row.
--
-- WHAT THIS ADDS, AND WHY
--
-- Product ruling, 2026-08-20: an admin is also a resident -- one
-- `community_memberships` row per person per community (`0001_baseline.sql`:45),
-- resident-ness being an active `unit_residencies` row rather than a role. So
-- the admin portal needs to raise complaints in two modes, and the two differ in
-- *who owns the raiser-side view*:
--
--   1. **On behalf of a resident.** The complaint belongs to that resident's
--      membership. It appears on their portal with the full chat, status and
--      timeline, and they keep the resident verbs -- confirm, reopen, cancel.
--   2. **Not attached to a residential unit** (an amenity, a common area). It
--      belongs to the admin's own membership and must appear on the admin
--      portal *only* -- never in the admin's own resident-portal "My
--      Complaints", which is a list of things that happened to them at home.
--
-- `raised_by_membership_id` alone cannot express that. In mode 1 it is the
-- resident and the row is theirs; in mode 2 it is the admin and the row is
-- emphatically not theirs *as a resident*. One column, two meanings, and the
-- resident list has no way to tell them apart -- which is why `raised_via`
-- exists and why its semantics are the **portal**, not the person:
--
--     'resident' -> shows in the raiser's resident-portal list
--     'admin'    -> admin portal only
--
-- An on-behalf complaint is therefore `'resident'`. That reads backwards until
-- you remember what the column answers: it is owned by the resident, so it
-- belongs on their list. **Provenance -- that an admin filed it -- lives in the
-- `raised` event's payload instead** (`on_behalf`), where it is history rather
-- than a filter, and where it cannot silently change which list the complaint
-- appears on.
--
-- WHAT THIS DOES NOT TOUCH
--
-- `raise_complaint` is not redefined. The resident's own path is unchanged and
-- keeps writing the column's default. The complaint -> supervisor -> work order
-- pipeline is unchanged: `admin_raise_complaint` mirrors the latest
-- `raise_complaint` (`20260813100000_skill_sourced_complaints.sql`) statement for
-- statement -- same skill validation, same `resolve_complaint_department`, same
-- SLA, same `notify_complaint_staff` -- so an admin-raised complaint enters the
-- same routing and the same queues as a resident-raised one.
--
-- HOSTED SCHEMA
--
-- The linked project is pre-baseline and carries legacy extra columns
-- (`complaints.unit_id`, `complaints.closed_at`;
-- `complaint_events.previous_status/new_status/note`) -- see
-- `docs/HOSTED_SCHEMA_DRIFT_COMPLAINTS.md`. All five are nullable, so the
-- inserts below, which name their columns explicitly and omit all five, are
-- legal there. **Apply `20260820120000_hosted_complaint_column_drift.sql`
-- first**: `admin_raise_complaint` writes `complaint_events.payload`, which that
-- file is what adds.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. complaints.raised_via
--
-- `not null default 'resident'`, so every existing row -- all of which were
-- raised from the resident portal, because until this file there was no other
-- way -- gets the value that is already true of it. No backfill statement is
-- needed and none is written: a default on `add column` is what fills them.
--
-- The CHECK is a named constraint added through a guarded DO block rather than
-- inline, because `add constraint` has no `if not exists`. Same shape as
-- `complaints_priority_check` (`0031`:80).
--
-- ROLLBACK: alter table public.complaints drop column raised_via;
--   (drops the constraint with it)
-- ---------------------------------------------------------------------------
alter table public.complaints
  add column if not exists raised_via text not null default 'resident';

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'complaints_raised_via_check'
  ) then
    alter table public.complaints
      add constraint complaints_raised_via_check
      check (raised_via in ('resident', 'admin'));
  end if;
end $$;

comment on column public.complaints.raised_via is
  'Which portal owns the raiser-side view of this complaint. '
  '''resident'' = it appears in raised_by_membership_id''s resident-portal list; '
  '''admin'' = admin portal only. A complaint an admin filed on a resident''s '
  'behalf is ''resident'' -- it is theirs. That an admin filed it is recorded in '
  'the raised event''s payload, not here.';

-- ---------------------------------------------------------------------------
-- 2. admin_raise_complaint
--
-- The exact-signature drop is the lesson of `20260813100000`:12 -- a plain
-- `create or replace` after an argument list changes leaves an overload behind
-- and old PostgREST calls stay bound to it. This function is new, so today the
-- drop is a no-op; it is here so that editing this file and re-running it stays
-- safe rather than becoming the next overload.
--
-- **Three checks before anything is written**, in the order a caller can fail
-- them:
--
-- `is_own_membership(p_actor_membership_id)` -- the same guard `raise_complaint`
-- opens with (`20260813100000`:92) and for the same reason: a SECURITY DEFINER
-- function that trusts a caller-supplied membership id is one that lets anyone
-- file a complaint in somebody else's name. The API resolves this id from the
-- session, but the API is not what makes it true.
--
-- The actor must be an **active admin**. `require_admin` in FastAPI already
-- checks it; this checks it again where the row is, because the RPC is callable
-- by any authenticated user and an endpoint guard is not a database guard.
--
-- `p_for_membership_id`, when given, must be an active, non-ended membership
-- **in the actor's own community**. Cross-community is refused rather than
-- ignored: silently filing it into the admin's own community would hand a
-- complaint to a management team that has never heard of the person it names.
-- Note what is *not* checked -- that the target holds an active
-- `unit_residencies` row. An admin filing on behalf of somebody is stating that
-- this person's home has a problem, and a membership mid-move or awaiting its
-- residency row is exactly the case where they need somebody to file for them.
--
-- The ownership split is the whole of the new behaviour, and it is two lines:
--
--     raised_by_membership_id = coalesce(p_for_membership_id, p_actor_membership_id)
--     raised_via              = 'admin' when p_for_membership_id is null else 'resident'
--
-- The `raised` event's `actor_membership_id` is **always the admin**, in both
-- modes. The timeline records who acted; the row records whose complaint it is.
-- Writing the resident there would forge a history entry -- the one thing an
-- append-only timeline exists to prevent.
-- ---------------------------------------------------------------------------
drop function if exists public.admin_raise_complaint(
  uuid, text, text, text, text, text, uuid, uuid, uuid
);
create function public.admin_raise_complaint(
  p_actor_membership_id uuid,
  p_title               text,
  p_description         text,
  p_category            text,
  p_priority            text default 'low',
  p_location            text default null,
  p_department_id       uuid default null,
  p_skill_id            uuid default null,
  p_for_membership_id   uuid default null
) returns uuid
language plpgsql security definer set search_path = public
as $$
declare
  v_community_id uuid;
  v_priority text := lower(coalesce(nullif(btrim(coalesce(p_priority, '')), ''), 'low'));
  v_title text := nullif(btrim(coalesce(p_title, '')), '');
  v_category text := nullif(btrim(coalesce(p_category, '')), '');
  v_owner uuid;
  v_raised_via text;
  v_department uuid;
  v_payload jsonb;
  v_id uuid;
begin
  if not public.is_own_membership(p_actor_membership_id) then
    raise exception 'A complaint may only be raised from your own membership.' using errcode = 'HB403';
  end if;

  select m.community_id into v_community_id
    from public.community_memberships m
   where m.id = p_actor_membership_id
     and m.role::text = 'admin'
     and m.status = 'active'
     and m.ended_at is null;
  if v_community_id is null then
    raise exception 'Only a community admin may raise a complaint from the admin portal.' using errcode = 'HB403';
  end if;

  if p_for_membership_id is not null and not exists (
    select 1 from public.community_memberships m
     where m.id = p_for_membership_id
       and m.community_id = v_community_id
       and m.status = 'active'
       and m.ended_at is null
  ) then
    raise exception 'That member does not belong to this community.' using errcode = 'HB403';
  end if;

  if v_title is null then raise exception 'A complaint needs a title.' using errcode = '23514'; end if;
  if v_priority not in ('low', 'medium', 'high') then
    raise exception 'Unknown complaint priority: %', p_priority using errcode = '22P02';
  end if;
  -- Same rule as `raise_complaint`: the client submits an id, never a mutable
  -- display string, and the trade's current name is snapshotted into category.
  if p_skill_id is not null then
    select s.name into v_category from public.skills s where s.id = p_skill_id and s.is_active;
    if v_category is null then raise exception 'No such trade.' using errcode = 'HB404'; end if;
  end if;
  if v_category is null then raise exception 'A complaint needs a category.' using errcode = '23514'; end if;

  v_owner := coalesce(p_for_membership_id, p_actor_membership_id);
  v_raised_via := case when p_for_membership_id is null then 'admin' else 'resident' end;

  v_department := public.resolve_complaint_department(v_community_id, v_category, p_department_id, p_skill_id);
  insert into public.complaints (
    community_id, raised_by_membership_id, title, description, category, skill_id,
    status, priority, location, expected_resolution_at, due_at, department_id, raised_via
  ) values (
    v_community_id, v_owner, v_title, nullif(btrim(coalesce(p_description, '')), ''),
    v_category, p_skill_id, 'open', v_priority, nullif(btrim(coalesce(p_location, '')), ''),
    now() + make_interval(hours => public.complaint_sla_hours(v_priority)),
    now() + make_interval(hours => public.complaint_sla_hours(v_priority)), v_department, v_raised_via
  ) returning id into v_id;

  insert into public.complaint_events (complaint_id, actor_membership_id, event_type, payload)
  values (v_id, p_actor_membership_id, 'raised', jsonb_build_object(
    'priority', v_priority, 'category', v_category, 'skill_id', p_skill_id,
    'department_id', v_department, 'department_chosen_by_resident', p_department_id,
    'on_behalf', p_for_membership_id is not null));

  v_payload := jsonb_build_object('title', 'New complaint raised', 'body', v_title,
    'url', '/admin/complaints?complaint=' || v_id::text, 'complaint_id', v_id);
  perform public.notify_complaint_staff(v_id, 'complaint.raised', v_payload, p_actor_membership_id);
  return v_id;
end;
$$;

comment on function public.admin_raise_complaint(uuid, text, text, text, text, text, uuid, uuid, uuid) is
  'Raise a complaint from the admin portal, either on a resident''s behalf '
  '(p_for_membership_id -- the complaint becomes theirs, raised_via = resident) '
  'or unattached to any unit (raised_via = admin, admin portal only). Same '
  'routing, SLA and notifications as raise_complaint; the raised event''s actor '
  'is always the admin.';

grant execute on function public.admin_raise_complaint(uuid, text, text, text, text, text, uuid, uuid, uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 3. complaint_overview, recreated to carry raised_via
--
-- Verbatim from `0031`:246-297 -- which is still the latest definition of this
-- view; nothing between it and this file redeclares it -- with one column added
-- beside `raised_by_membership_id`, the column it qualifies. The resident list
-- filters on it (`resident_complaints_repository.list_mine`), and PostgREST can
-- only filter on a column the view exposes.
--
-- `drop view` then `create view` rather than `create or replace view`: the
-- replace form cannot insert a column in the middle of the list, only append,
-- and appending would put `raised_via` after `is_unread` where nobody reading
-- the projection would find it next to the field it modifies.
--
-- The `comment on` and the `grant` are restated for exactly that reason -- a
-- dropped view takes both with it. (Contrast `create or replace function`,
-- which keeps the oid and therefore keeps both; see
-- `20260812120000_work_order_notification_urls.sql`, which deliberately restates
-- neither.)
--
-- ROLLBACK: re-run `0031`:245-302.
-- ---------------------------------------------------------------------------
drop view if exists public.complaint_overview;
create view public.complaint_overview
with (security_invoker = true) as
select
  c.id,
  c.community_id,
  c.raised_by_membership_id,
  -- CHANGED: the only line this file adds to `0031`'s definition.
  c.raised_via,
  c.title,
  c.description,
  c.category,
  c.status,
  c.priority,
  c.location,
  c.progress_percent,
  c.assignee_label,
  c.expected_resolution_at,
  c.reopened_count,
  c.resolution_rating,
  c.resident_feedback,
  c.created_at,
  c.updated_at,
  c.resolved_at,
  (
    c.expected_resolution_at is not null
    and c.expected_resolution_at < now()
    and c.status not in ('resolved', 'closed', 'cancelled')
  ) as is_overdue,
  coalesce(cm.comment_count, 0) as comment_count,
  greatest(
    c.updated_at,
    coalesce(cm.last_comment_at, c.updated_at)
  ) as last_activity_at,
  (
    rs.last_read_at is null
    or rs.last_read_at < greatest(
         c.updated_at,
         coalesce(cm.last_comment_at, c.updated_at)
       )
  ) as is_unread
from public.complaints c
left join lateral (
  select count(*)::integer as comment_count,
         max(cc.created_at) as last_comment_at
    from public.complaint_comments cc
   where cc.complaint_id = c.id
     and cc.visibility = 'public'
) cm on true
left join lateral (
  select max(rs0.last_read_at) as last_read_at
    from public.complaint_read_state rs0
   where rs0.complaint_id = c.id
     and public.is_own_membership(rs0.membership_id)
) rs on true;

comment on view public.complaint_overview is
  'Resident-facing complaint projection: the row, its SLA state, and whether the person who raised it has seen the latest change.';

grant select on public.complaint_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 4. Verification, in the same transaction as the change
--
-- The shape `20260813100000`, `20260813103000` and `20260820120000` all end
-- with: if the file claims to have done something, it fails rather than
-- reporting success.
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'complaints'
       and column_name = 'raised_via' and is_nullable = 'NO'
  ) then
    raise exception 'complaints.raised_via missing or nullable';
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'complaints_raised_via_check'
  ) then
    raise exception 'complaints_raised_via_check missing';
  end if;

  if not exists (
    select 1 from pg_proc
     where pronamespace = 'public'::regnamespace
       and proname = 'admin_raise_complaint' and pronargs = 9
  ) then
    raise exception 'admin_raise_complaint must have 9 arguments';
  end if;

  -- The resident's own path is untouched: `20260813100000`'s 8-argument
  -- `raise_complaint` must still be there. Deliberately *not* asserted as the
  -- only overload: the repository's history is clean (`20260812090300`:271
  -- drops the 6-argument signature exactly, `20260813100000`:75 the 7-argument
  -- one), but the hosted project predates the baseline and its function set has
  -- only been probed through PostgREST, which lists one entry per name and
  -- cannot see an overload -- so a count assertion here could fail on a
  -- database this file has no business failing on. The open check is logged as
  -- Q12.2 in `docs/COMPLAINT_ENGINE_HANDOFF.md`.
  if not exists (
    select 1 from pg_proc
     where pronamespace = 'public'::regnamespace
       and proname = 'raise_complaint' and pronargs = 8
  ) then
    raise exception 'raise_complaint is no longer the 8-argument function';
  end if;

  if not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'complaint_overview'
       and column_name = 'raised_via'
  ) then
    raise exception 'complaint_overview does not expose raised_via';
  end if;
end $$;
