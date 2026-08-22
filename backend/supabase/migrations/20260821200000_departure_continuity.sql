-- ---------------------------------------------------------------------------
-- 20260821200000_departure_continuity.sql
--
-- The complaint chain survives a supervisor's removal.
--
-- THE GAP, IN ONE SENTENCE
--
-- `work_orders.supervisor_membership_id` (`0036` 1, stamped at `0036` 742) is
-- the address five notification kinds are delivered to -- `work_order.no_candidates`
-- (`20260812120000`), `work_order.resident_accepted` / `_declined` (`0036`),
-- `work_order.accepted`, `work_order.completed` and `work_order.failed` (`0039`)
-- -- and nothing anywhere re-points it when the person it names stops being a
-- supervisor. After `remove_department_member` (`0045` 8) the roster row is
-- `inactive` and the membership is `ended`, and every one of those five messages
-- is still written to the departed person, by `notify_member`, keyed to a
-- membership that no longer exists. `20260821140000` 8 made that row invisible
-- to the reader as well, so the department's live jobs now report their progress
-- into a mailbox nobody can open. The complaint is not lost -- complaints are
-- department-pooled and stay so -- but everything *downstream* of it goes quiet.
--
-- THE PRODUCT OWNER'S RULINGS, 2026-08-21
--
--   1. Complaints stay department-pooled. `complaints.assigned_to_membership_id`
--      stays the dead column it is; nothing here writes or reads it.
--   2. Removal continuity is **work-order re-stamping**: live work orders
--      supervised by the departing person are re-pointed at a remaining active
--      supervisor of the same department, and failing that at its manager.
--   3. When the removed supervisor was the department's last, the manager is
--      told they are covering the queue (and the manager's Complaints screen
--      says so while it is true). No new workspace is built: a manager already
--      passes every supervisor guard -- `can_manage_department` implies
--      `can_supervise_department` (`0036` 435) -- and `/manager/complaints` is a
--      strict superset of the supervisor's screen.
--   5. The always-zero "open complaints" roster count is replaced by a number
--      somebody actually writes.
--   7. Supervisors are notified when a complaint is raised. Recorded as done in
--      `docs/CHANGE_LOG.md` (ruling R18) and never implemented:
--      `notify_complaint_staff` reaches admins and the department's manager only.
--   9. Serviceman release mechanics are untouched. `release_staff_commitments`,
--      `claim_dispatch_batch` and the dispatch engine are not mentioned in this
--      file.
--
-- WHY A TRIGGER AND NOT A CHANGE TO `remove_department_member`
--
-- Removal has four entry paths -- the direct `remove_department_member`
-- (`hiring_repository.remove_member`), the immediate approval inside
-- `decide_staff_departure` (`0045` 1032), the timekeeper's
-- `dispatch_departure_removal` (`0045` 1127, which runs with **no session**),
-- and `blacklist_service_provider` (`0043` 1266) -- and a fifth that is not an
-- RPC at all: `staff_assignments_admin_write` is `for all to authenticated`
-- with direct grants (`20260812200000` 26-31), so an admin can flip
-- `status = 'inactive'` straight through PostgREST. Every one of those five ends
-- at the same `update public.staff_assignments set status = 'inactive'`, and the
-- first four reach it through `remove_department_member`'s own update. One
-- `after update` trigger on that column therefore covers all five with one
-- implementation, and `20260821140000` 2 already chose triggers over RPC edits
-- for exactly the bypass reason. `remove_department_member` is consequently
-- **not redeclared here**: an 80-line body copied forward to gain a `perform`
-- would cover four paths instead of five and would put this file in the way of
-- the next person who needs to change removal.
--
-- The trigger fires `after` rather than `before` on purpose. By then the row is
-- already `inactive` in the snapshot the successor search reads, so
-- "a remaining active supervisor" excludes the departing person by construction
-- rather than by an `id <> old.id` that a later edit could drop.
--
-- WHAT IS DELIBERATELY *NOT* HERE
--
--   * No new column, no new table. Re-stamping writes an existing column with an
--     existing meaning.
--   * No new SQLSTATE. Nothing in this file refuses anything, so there is
--     nothing to map in `backend/app/core/pg_errors.py`.
--   * `claim_staff_invitations` is not touched. The claim-pass gap ruling 8
--     names is Python-side -- `auth_service._claim_staff_invitations` was called
--     only on the membership-less path -- and is fixed there.
--   * Residents and workers are unaffected by re-stamping *by construction*:
--     no resident-facing or worker-facing read returns a supervisor's identity
--     (`resident_complaints_service.py` 194/226, `20260813105000` 34-63), so a
--     job changing hands upward is invisible to them. Nothing here has to hide
--     it.
--
-- IDEMPOTENT. Every statement tolerates its own effect already being present;
-- the recovery from a half-applied hand-run is to run the file again. The
-- backfill in section 8 re-stamps only rows that are still orphaned, so a second
-- run reports zero.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. Who inherits the supervision of a department
--
-- The target rule, in one function, so the trigger and the backfill cannot
-- drift into two answers.
--
--   1. A remaining **active supervisor** of the same department whose membership
--      is still live. Where there is more than one, the one already supervising
--      the fewest live jobs -- a departure should not land entirely on whoever
--      happens to sort first. `created_at` then `id` break the remaining tie, so
--      the choice is deterministic and a re-run of the backfill is a no-op.
--   2. Otherwise the department's **manager**, in three widening steps: the
--      roster row that holds `rank = 'manager'`, then a `manager` membership
--      pinned to this department, then a `manager` membership pinned to none --
--      which `can_manage_department` reads as "manages any", so they can in fact
--      open the job.
--   3. Otherwise null, and the caller leaves the work orders alone. A wrong
--      address is worse than a stale one: the stale one at least names the
--      person the department remembers assigning it to.
--
-- Community admins are **not** a step. An admin is not on the department's
-- roster and `supervisor_membership_id` is the department's own answer to "whose
-- job is this"; the admin's route to it is the department screen, which does not
-- need this column to find anything. They are told about the takeover in section
-- 4 all the same.
-- ---------------------------------------------------------------------------

create or replace function public.department_supervision_successor(
  p_department_id      uuid,
  p_exclude_membership uuid default null
)
returns uuid
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_community uuid;
  v_target    uuid;
begin
  if p_department_id is null then
    return null;
  end if;

  select d.community_id into v_community
    from public.departments d where d.id = p_department_id;
  if v_community is null then
    return null;
  end if;

  -- (1) A remaining supervisor, least loaded first.
  select sa.membership_id into v_target
    from public.staff_assignments sa
    join public.community_memberships m on m.id = sa.membership_id
   where sa.department_id = p_department_id
     and sa.status        = 'active'
     and sa.rank          = 'supervisor'
     and sa.membership_id is not null
     and (p_exclude_membership is null or sa.membership_id <> p_exclude_membership)
     and m.status   = 'active'
     and m.ended_at is null
   order by (
     select count(*)
       from public.work_orders w
      where w.supervisor_membership_id = sa.membership_id
        and w.department_id            = p_department_id
        and w.status not in ('completed', 'cancelled', 'failed')
   ), sa.created_at, sa.id
   limit 1;
  if v_target is not null then
    return v_target;
  end if;

  -- (2a) The department's head, by roster rank.
  select sa.membership_id into v_target
    from public.staff_assignments sa
    join public.community_memberships m on m.id = sa.membership_id
   where sa.department_id = p_department_id
     and sa.status        = 'active'
     and sa.rank          = 'manager'
     and sa.membership_id is not null
     and (p_exclude_membership is null or sa.membership_id <> p_exclude_membership)
     and m.status   = 'active'
     and m.ended_at is null
   order by sa.created_at, sa.id
   limit 1;
  if v_target is not null then
    return v_target;
  end if;

  -- (2b) and (2c) The manager membership, this department's first. The same
  -- `community_memberships.department_id` predicate `_portal_for` reads to
  -- decide who gets `/manager` at all, deliberately mirrored: a supervision
  -- inherited by somebody whose portal has no screen for it is not inherited.
  select m.id into v_target
    from public.community_memberships m
   where m.community_id = v_community
     and m.role::text   = 'manager'
     and m.status       = 'active'
     and m.ended_at is null
     and (m.department_id is null or m.department_id = p_department_id)
     and (p_exclude_membership is null or m.id <> p_exclude_membership)
   -- `nulls last` is load-bearing, not decoration. `m.department_id is null`
   -- makes the comparison NULL, and `desc` alone is `desc nulls first` in
   -- PostgreSQL -- which would rank the manages-any manager *above* the one
   -- actually pinned to this department, exactly reversing 2b and 2c.
   order by (m.department_id = p_department_id) desc nulls last, m.created_at, m.id
   limit 1;

  return v_target;
end;
$$;

comment on function public.department_supervision_successor(uuid, uuid) is
  'Who takes over a department''s supervision: the least loaded remaining active supervisor, else its manager, else nobody. The one place the target rule is written.';


-- ---------------------------------------------------------------------------
-- 2. Re-stamping itself
--
-- Scoped to the department, and to work orders that are still live. A completed
-- or cancelled job needs no supervisor: nothing more will be said about it, and
-- rewriting history to name somebody who was not there is a worse record than
-- one that names somebody who has left.
--
-- `w.department_id = p_department_id` is the scope rather than
-- `supervisor_membership_id` alone, because a membership can appear on more than
-- one department's work: an admin membership that raised jobs in two departments
-- would otherwise have all of them handed to the first department to lose them.
-- ---------------------------------------------------------------------------

create or replace function public.restamp_department_supervision(
  p_department_id  uuid,
  p_from_membership uuid
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_target  uuid;
  v_moved   integer := 0;
begin
  if p_department_id is null or p_from_membership is null then
    return 0;
  end if;

  if not exists (
    select 1 from public.work_orders w
     where w.supervisor_membership_id = p_from_membership
       and w.department_id            = p_department_id
       and w.status not in ('completed', 'cancelled', 'failed')
  ) then
    return 0;
  end if;

  v_target := public.department_supervision_successor(
    p_department_id, p_from_membership);
  if v_target is null then
    return 0;
  end if;

  update public.work_orders w
     set supervisor_membership_id = v_target,
         updated_at               = now()
   where w.supervisor_membership_id = p_from_membership
     and w.department_id            = p_department_id
     and w.status not in ('completed', 'cancelled', 'failed');

  get diagnostics v_moved = row_count;
  return v_moved;
end;
$$;

comment on function public.restamp_department_supervision(uuid, uuid) is
  'Re-point one department''s live work orders away from a membership that has stopped supervising them. Returns how many moved; 0 when there is nothing to move or nobody to move it to.';


-- ---------------------------------------------------------------------------
-- 3. A roster count somebody actually writes (ruling 5)
--
-- `department_staff_overview.active_assignment_count` (`0045` 1450) counts
-- complaints by `assigned_to_membership_id` or by a prefix match on
-- `assignee_label`. Ruling 1 keeps the first column dead and no frontend has
-- ever written the second, so the number has been a constant zero on every row
-- of every roster since the view was written -- rendered as "0 open complaints"
-- on the hiring screen and the employee page.
--
-- What replaces it is the number the same person actually holds: the live work
-- orders they supervise. It is meaningful only for leadership, and it says so by
-- being zero for everybody else rather than by being absent -- a member's real
-- number is `open_commitment_count`, which is already on the same row.
--
-- `security definer` for the reason `0043` 245 gives about
-- `staff_open_commitment_count`: the view is `security_invoker`, so a count
-- computed inline would be filtered by the reader's own RLS on `work_orders` and
-- would under-report for exactly the readers who need it. A count leaks nothing
-- but a number against a roster id the caller already holds.
-- ---------------------------------------------------------------------------

create or replace function public.staff_supervised_work_order_count(p_staff_id uuid)
returns integer
language sql
stable
security definer
set search_path = public
as $$
  select coalesce((
    select count(*)
      from public.staff_assignments s
      join public.work_orders w
        on w.supervisor_membership_id = s.membership_id
       and w.department_id            = s.department_id
     where s.id = p_staff_id
       and s.membership_id is not null
       and s.rank in ('manager', 'supervisor')
       and w.status not in ('completed', 'cancelled', 'failed')
  ), 0)::integer;
$$;

comment on function public.staff_supervised_work_order_count(uuid) is
  'Live work orders one roster row supervises. Zero for a non-leadership row, which is the truth and not a placeholder -- their number is staff_open_commitment_count.';

revoke all on function public.department_supervision_successor(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.department_supervision_successor(uuid, uuid)
  to service_role;

revoke all on function public.restamp_department_supervision(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.restamp_department_supervision(uuid, uuid)
  to service_role;

revoke all on function public.staff_supervised_work_order_count(uuid)
  from public, anon, authenticated;
grant execute on function public.staff_supervised_work_order_count(uuid)
  to authenticated;


-- ---------------------------------------------------------------------------
-- 4. The edge: a roster row stops leading
--
-- One trigger, two jobs.
--
-- **Re-stamp**, always. The `when` clause is the whole condition: the row was a
-- live `manager`/`supervisor` with a membership, and after the write it is not
-- one any more -- deactivated, demoted, or re-pointed at a different membership.
-- `remove_department_member` sets `status` and `rank` in a single update, so
-- that is one fire and not two.
--
-- **Tell the manager**, on the last-supervisor edge only. Ruling 3: the
-- department's complaint queue is now the manager's, and they should be told
-- rather than discover it. `notify_department_leadership` (`0043` 6) is reused
-- rather than a new recipient loop -- with zero supervisors left its audience is
-- exactly "the community's admins plus this department's manager", which is
-- precisely the set of people now covering. The url is written `/admin/complaints`
-- because `frontend/src/features/notifications/portalUrl.js` rewrites that path
-- to `/manager/complaints` for a manager reader; that rewrite is the house answer
-- to "SQL does not know who will read this".
--
-- The notice is confined to `kind = 'service'` departments. A security
-- department's manager lands in `/security-manager`, which has no complaints
-- screen at all and is not meant to -- gate work arrives as incidents and shifts.
-- Sending them a link that redirects home is the failure `portalUrl.js` exists to
-- prevent. Re-stamping is *not* so confined: a work order is a work order.
-- ---------------------------------------------------------------------------

create or replace function public.carry_department_supervision()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_moved       integer;
  v_left        integer;
  v_department  record;
begin
  v_moved := public.restamp_department_supervision(
    old.department_id, old.membership_id);

  if old.rank <> 'supervisor' then
    return null;
  end if;

  select d.id, d.name, d.kind, d.community_id into v_department
    from public.departments d where d.id = old.department_id;
  if v_department.id is null or v_department.kind <> 'service' then
    return null;
  end if;

  select count(*) into v_left
    from public.staff_assignments sa
    join public.community_memberships m on m.id = sa.membership_id
   where sa.department_id = old.department_id
     and sa.status        = 'active'
     and sa.rank          = 'supervisor'
     and m.status         = 'active'
     and m.ended_at is null;

  if v_left > 0 then
    return null;
  end if;

  perform public.notify_department_leadership(
    old.department_id, 'department.supervision_uncovered',
    jsonb_build_object(
      'title', 'You are covering '
               || coalesce(v_department.name, 'a department')
               || '''s complaint queue',
      'body', coalesce(old.display_name, 'Its last supervisor')
              || ' has left, and no supervisor remains. Complaints routed here '
              || 'stay with you until a new supervisor is invited.'
              || case when v_moved > 0
                   then ' ' || v_moved || ' live job(s) moved across.'
                   else '' end,
      'url', '/admin/complaints',
      'departmentId', old.department_id,
      'staffId', old.id,
      'restampedCount', v_moved),
    old.membership_id);

  return null;
end;
$$;

comment on function public.carry_department_supervision() is
  'After a roster row stops leading: re-stamp its live work orders onto whoever inherits them, and — when it was the department''s last supervisor — tell the manager they now cover the queue.';

drop trigger if exists staff_assignments_carry_supervision on public.staff_assignments;
create trigger staff_assignments_carry_supervision
  after update of rank, status, membership_id
  on public.staff_assignments
  for each row
  when (
    old.membership_id is not null
    and old.status = 'active'
    and old.rank in ('manager', 'supervisor')
    and (
      new.status <> 'active'
      or new.rank not in ('manager', 'supervisor')
      or new.membership_id is distinct from old.membership_id
    )
  )
  execute function public.carry_department_supervision();

revoke all on function public.carry_department_supervision()
  from public, anon, authenticated;


-- ---------------------------------------------------------------------------
-- 5. Supervisors are told when a complaint is raised (ruling 7 / R18)
--
-- `notify_complaint_staff` (`20260812090300` 2b), copied forward whole under the
-- house convention (`20260812113000` 1) with one changed region. It is the
-- helper behind every complaint-shaped event -- `raise_complaint`
-- (`20260813100000`), `admin_raise_complaint` (`20260820150000`),
-- `job.force_assigned` and `job.all_declined` (`20260813101000`),
-- `complaint.job_cancelled_by_resident` (`20260813103000`) and
-- `job.fallback_started` (`20260813104000`) -- so widening it here is what makes
-- R18 true for the raise **and** for the reopen the ruling names beside it,
-- rather than for one call site somebody remembered.
--
-- The audience it could not express before is the same one `0043` 6 wrote
-- `notify_department_leadership` for: **a supervisor is a rank on a roster row in
-- one department, not a membership role**, so no `role`-based helper reaches
-- them. The predicate below is that helper's, narrowed to this complaint's
-- department.
--
-- `distinct`, and `m.role <> 'admin'`. The admins were already told by the
-- `notify_community_roles` call above, and an admin who also sits on this
-- department's roster as its supervisor satisfies both arms -- being told twice
-- about one complaint reads as a bug in the app (`0043` 416, same argument).
-- ---------------------------------------------------------------------------

create or replace function public.notify_complaint_staff(
  p_complaint_id       uuid,
  p_kind               text,
  p_payload            jsonb,
  p_exclude_membership uuid default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_complaint record;
  v_manager   record;
begin
  select c.community_id, c.department_id into v_complaint
    from public.complaints c
   where c.id = p_complaint_id;

  if v_complaint.community_id is null then
    return;
  end if;

  perform public.notify_community_roles(
    v_complaint.community_id, array['admin'], p_kind, p_payload,
    p_exclude_membership
  );

  if v_complaint.department_id is null then
    return;
  end if;

  for v_manager in
    -- CHANGED (20260821200000): was managers only, by membership role. The
    -- department's supervisors are added by roster rank, which is the only way
    -- to name them; `distinct` and the `admin` exclusion keep the two arms from
    -- telling one person twice.
    select distinct m.id
      from public.community_memberships m
     where m.community_id  = v_complaint.community_id
       and m.status        = 'active'
       and m.ended_at is null
       and m.role::text   <> 'admin'
       and (p_exclude_membership is null or m.id <> p_exclude_membership)
       and (
         (m.department_id = v_complaint.department_id and m.role::text = 'manager')
         or exists (
              select 1
                from public.staff_assignments sa
               where sa.department_id = v_complaint.department_id
                 and sa.membership_id = m.id
                 and sa.status        = 'active'
                 and sa.rank in ('manager', 'supervisor')
            )
       )
  loop
    perform public.notify_member(v_manager.id, p_kind, p_payload);
  end loop;
end;
$$;

comment on function public.notify_complaint_staff(uuid, text, jsonb, uuid) is
  'Tell the community''s admins, the complaint''s own department manager, and — since 2026-08-21, ruling R18 — that department''s supervisors, who are a roster rank and so reachable by no role-based helper.';

revoke all on function public.notify_complaint_staff(uuid, text, jsonb, uuid)
  from public, anon, authenticated;


-- ---------------------------------------------------------------------------
-- 6. The roster view stops reporting a constant (ruling 5)
--
-- `0045` 12's definition, recreated with `active_assignment_count` replaced by
-- `supervised_work_order_count`. Every other column is carried over unchanged --
-- the recreate is for one column, and a view that comes back *slightly*
-- different is the failure nobody notices.
--
-- Recreating a view drops its grants (`0042` 4, `0045` 12, same note); the grant
-- is reissued below.
-- ---------------------------------------------------------------------------

drop view if exists public.department_staff_overview;
create view public.department_staff_overview
with (security_invoker = true) as
select
  s.id,
  s.community_id,
  s.department_id,
  s.membership_id,
  s.service_provider_id,
  s.display_name,
  s.phone_e164,
  s.job_title,
  s.rank,
  s.shift,
  s.status,
  s.created_at,
  s.updated_at,
  -- CHANGED (20260821200000): was `coalesce(a.active_assignment_count, 0)` over
  -- a lateral that counted complaints by two columns nothing writes.
  public.staff_supervised_work_order_count(s.id) as supervised_work_order_count,
  public.staff_open_commitment_count(s.id)       as open_commitment_count,
  dep.status       as departure_status,
  dep.effective_at as departure_effective_at
from public.staff_assignments s
left join lateral (
  select d.status,
         coalesce(d.effective_at, d.requested_effective_at) as effective_at
    from public.staff_departures d
   where d.staff_assignment_id = s.id
     and (d.status = 'pending'
          or (d.status = 'approved'
              and d.effective_at is not null
              and d.effective_at > now()))
   order by d.created_at desc
   limit 1
) dep on true;

comment on view public.department_staff_overview is
  'Staff assignments with the live work they supervise, the items booked in their name, the provider behind the row, and — when they are on their way out — the departure''s status and date.';

grant select on public.department_staff_overview to authenticated;


-- ---------------------------------------------------------------------------
-- 7. Backfill: work orders already pointing at somebody who has left
--
-- Every removal before this file ran left its live work orders addressed to an
-- ended membership. Those are the rows whose five notification kinds are already
-- being written into a mailbox nobody can open, so they are repaired to the same
-- rule the trigger uses, and the count is reported.
--
-- This is a mechanical repair and not a decision: the column's meaning does not
-- change, the target rule is the one section 1 just wrote, and a row with no
-- successor is left exactly as it is. Product-owner approved, 2026-08-21.
-- Expected count on the hosted database: at or near zero.
--
-- "Has left" is `membership_is_live` (`20260821140000` 8) said the long way,
-- because that function is the one the feed policy asks -- if it says the row is
-- not live, the supervisor cannot read the notification, which is the whole
-- defect being repaired.
-- ---------------------------------------------------------------------------

do $$
declare
  v_row       record;
  v_moved     integer;
  v_total     integer := 0;
  v_stranded  integer := 0;
  v_orphaned  integer := 0;
begin
  for v_row in
    select w.department_id, w.supervisor_membership_id, count(*) as jobs
      from public.work_orders w
     where w.supervisor_membership_id is not null
       and w.status not in ('completed', 'cancelled', 'failed')
       and not public.membership_is_live(w.supervisor_membership_id)
     group by w.department_id, w.supervisor_membership_id
  loop
    v_orphaned := v_orphaned + v_row.jobs;

    if v_row.department_id is null then
      -- No department, so section 1 has nothing to search. Counted, not guessed.
      v_stranded := v_stranded + v_row.jobs;
      continue;
    end if;

    v_moved := public.restamp_department_supervision(
      v_row.department_id, v_row.supervisor_membership_id);
    v_total    := v_total + v_moved;
    v_stranded := v_stranded + (v_row.jobs - v_moved);
  end loop;

  if v_orphaned = 0 then
    raise notice
      'departure_continuity: no live work order was addressed to an ended membership. Nothing to repair.';
  else
    raise notice
      'departure_continuity: % live work order(s) were addressed to an ended membership; % re-stamped, % left in place because the department has nobody to inherit them.',
      v_orphaned, v_total, v_stranded;
  end if;
end $$;


-- ---------------------------------------------------------------------------
-- 8. Post-apply verification
--
-- Run these in the SQL Editor after this file. They are also reproduced in
-- `docs/plans/MIGRATION_APPLY_RUNBOOK.md` 16. Nothing below runs as part of the
-- migration; the block in section 7 is the only thing that executes.
--
--   -- (a) The trigger exists, fires after, and watches all three columns.
--   select tgname, pg_get_triggerdef(oid) as definition
--     from pg_trigger
--    where tgrelid = 'public.staff_assignments'::regclass
--      and tgname  = 'staff_assignments_carry_supervision';
--   -- expect: one row, "AFTER UPDATE OF rank, status, membership_id".
--
--   -- (b) No live work order is addressed to an ended membership any more.
--   select count(*) as orphaned
--     from public.work_orders w
--    where w.supervisor_membership_id is not null
--      and w.status not in ('completed', 'cancelled', 'failed')
--      and not public.membership_is_live(w.supervisor_membership_id);
--   -- expect: 0, or exactly the "left in place" number section 7 printed.
--
--   -- (c) The roster view reports the new column and not the old one.
--   select column_name
--     from information_schema.columns
--    where table_schema = 'public' and table_name = 'department_staff_overview'
--    order by ordinal_position;
--   -- expect: supervised_work_order_count present, active_assignment_count gone.
--
--   -- (d) The complaint audience reaches supervisors.
--   select prosrc like '%sa.rank in (''manager'', ''supervisor'')%' as reaches_supervisors
--     from pg_proc
--    where pronamespace = 'public'::regnamespace
--      and proname = 'notify_complaint_staff';
--   -- expect: true.
-- ---------------------------------------------------------------------------
