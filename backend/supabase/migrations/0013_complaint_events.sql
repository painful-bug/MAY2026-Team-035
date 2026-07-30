-- 0013_complaint_events.sql
-- The complaint timeline, the `location` column, and the RPCs that keep a status
-- change and its timeline entry in one transaction.
--
-- Depends on 0010-0012. Numbering: 0004-0009 belong to the auth/security
-- workstream (build plan 1.4).
--
-- ===========================================================================
-- TWO GAPS IN 0011 THAT ONLY SURFACED WHEN THE FRONTEND WAS READ CLOSELY
--
-- 1. complaint_events was never created. R9 resolved "management notes" with
--    "no column -- complaint_events already has note", but that table exists in
--    the ERD and NOT in any migration. The frontend keeps `comments[]` AND
--    `timeline[]` as separate things, and the admin's "Resident-visible Update"
--    box writes the timeline. So the table has to exist.
--
-- 2. complaints.location was missing. `raiseComplaint` stores
--    `location: complaintData.location || currentUser.flat` -- a free-text
--    "where in the building", distinct from the flat the complaint belongs to.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- complaints.location
-- ---------------------------------------------------------------------------
alter table public.complaints add column if not exists location text;

-- ---------------------------------------------------------------------------
-- complaint_events -- the timeline
--
-- APPEND-ONLY, and enforced as such: there is no UPDATE or DELETE policy below,
-- and no updated_at column. This is the distinction R9 drew between an audit
-- stream and a conversation, made structural rather than conventional. If an
-- event could be edited it would stop being evidence of what happened.
--
-- Shape mirrors the frontend's timeline entries
-- ({id, type, label, message, actor, createdAt}) so the DTO is a rename, not a
-- reconstruction.
-- ---------------------------------------------------------------------------
create table if not exists public.complaint_events (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.associations(id) on delete cascade,
  complaint_id        uuid not null,
  event_type          text not null,
  label               text not null,
  message             text,
  actor_membership_id uuid,
  -- Free text for the same reason as complaints.assignee_label: the actor may be
  -- 'Management' or a staff member with no account (C1).
  actor_label         text,
  created_at          timestamptz not null default now(),
  constraint complaint_events_type_ck check (event_type in (
    'raised', 'assigned', 'status', 'update', 'reopened', 'confirmed', 'comment'
  )),
  constraint complaint_events_complaint_fk
    foreign key (complaint_id, community_id)
    references public.complaints (id, community_id) on delete cascade,
  constraint complaint_events_actor_fk
    foreign key (actor_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (actor_membership_id)
);

create index if not exists complaint_events_complaint_idx
  on public.complaint_events (complaint_id, created_at);

-- ---------------------------------------------------------------------------
-- Revised SLA rule -- A3 RETRACTED
--
-- 0011 assumed due_at = category SLA x an urgency multiplier (high 0.5x, low 2x).
-- That multiplier was invented, and reading the frontend showed it was also
-- wrong: `createComplaintsSlice.js` already computes expectedResolutionAt from
-- urgency ALONE -- High 24h, Medium 48h, Low 72h -- ignoring the category.
--
-- So the product has TWO independent SLA systems that never meet:
--   * departments[].slaHours  -- 4 to 48 hours, per department
--   * hoursByUrgency          -- 24/48/72, per complaint urgency
-- They never collide today only because complaints do not reference departments
-- at all in the frontend.
--
-- Rule adopted here, in precedence order:
--   1. An explicit sla_hours override on the category.
--   2. The claiming department's sla_hours (lowest wins -- A2 unchanged).
--   3. The frontend's urgency table, as the default.
-- No multiplier: urgency already decides the fallback, and multiplying on top
-- would count it twice. Which of the two systems SHOULD win is a product
-- question -- see DECISIONS_NEEDED.md.
-- ---------------------------------------------------------------------------
create or replace function public.complaint_due_at(
  p_category_id uuid, p_urgency text, p_from timestamptz
)
returns timestamptz
language sql
stable
security definer
set search_path = public
as $$
  select p_from + (
    coalesce(
      public.resolve_category_sla_hours(p_category_id),
      -- The frontend's own table, reproduced exactly.
      case lower(coalesce(p_urgency, 'medium'))
        when 'high'   then 24
        when 'medium' then 48
        when 'low'    then 72
        else 48
      end
    )::float8
  ) * interval '1 hour';
$$;

-- ---------------------------------------------------------------------------
-- update_complaint
--
-- Applies a status/assignment/progress change AND writes its timeline entries in
-- ONE transaction. Same reasoning as migration 0012: PostgREST gives no
-- client-side transaction, so doing this from FastAPI would let a status change
-- land with no timeline entry -- an audit trail with holes in it, which is worse
-- than none because it looks complete.
--
-- NULL means "leave unchanged" for every parameter, so a caller may update one
-- field without reading and resending the rest.
--
-- SECURITY DEFINER: performs its own authorization, since RLS does not run.
-- ---------------------------------------------------------------------------
create or replace function public.update_complaint(
  p_complaint_id     uuid,
  p_status           text default null,
  p_assignee_label   text default null,
  p_assigned_to      uuid default null,
  p_progress_percent smallint default null,
  p_due_at           timestamptz default null,
  p_update_note      text default null,
  p_actor_membership uuid default null,
  p_actor_label      text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  c      public.complaints%rowtype;
  actor  text := coalesce(p_actor_label, 'Management');
begin
  select * into c from public.complaints where id = p_complaint_id for update;

  if not found then
    raise exception 'Complaint not found.' using errcode = 'HB404';
  end if;

  if not public.is_admin()
     or c.community_id not in (select public.current_community_ids()) then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;

  if p_status is not null and p_status not in
     ('pending', 'in_progress', 'resolved', 'closed', 'reopened') then
    raise exception 'Unknown status.' using errcode = 'HB409';
  end if;

  -- Assignment event first, matching the order the frontend appends them.
  if p_assignee_label is not null and p_assignee_label is distinct from c.assignee_label then
    insert into public.complaint_events
      (community_id, complaint_id, event_type, label, message, actor_membership_id, actor_label)
    values
      (c.community_id, c.id, 'assigned', 'Technician assigned',
       p_assignee_label || ' was assigned to this complaint.',
       p_actor_membership, actor);
  end if;

  if p_status is not null and p_status is distinct from c.status then
    insert into public.complaint_events
      (community_id, complaint_id, event_type, label, message, actor_membership_id, actor_label)
    values
      (c.community_id, c.id, 'status',
       case p_status
         when 'pending'     then 'Moved to pending'
         when 'in_progress' then 'Work started'
         when 'resolved'    then 'Marked resolved'
         when 'closed'      then 'Closed'
         when 'reopened'    then 'Complaint reopened'
       end,
       coalesce(nullif(btrim(p_update_note), ''),
                'The complaint status changed to ' || p_status || '.'),
       p_actor_membership, actor);
  elsif nullif(btrim(coalesce(p_update_note, '')), '') is not null then
    -- A note with no status change is still a timeline entry: it is the admin's
    -- "Resident-visible Update" box.
    insert into public.complaint_events
      (community_id, complaint_id, event_type, label, message, actor_membership_id, actor_label)
    values
      (c.community_id, c.id, 'update', 'Management update',
       btrim(p_update_note), p_actor_membership, actor);
  end if;

  update public.complaints
     set status           = coalesce(p_status, status),
         assignee_label   = coalesce(p_assignee_label, assignee_label),
         assigned_to_membership_id =
           coalesce(p_assigned_to, assigned_to_membership_id),
         assigned_by_membership_id = case
           when p_assignee_label is not null or p_assigned_to is not null
             then p_actor_membership else assigned_by_membership_id end,
         assigned_at = case
           when p_assignee_label is not null or p_assigned_to is not null
             then now() else assigned_at end,
         progress_percent = coalesce(p_progress_percent, progress_percent),
         due_at           = coalesce(p_due_at, due_at),
         -- Resolving stamps the time; moving off resolved clears it, so a
         -- reopened complaint does not keep claiming it was resolved.
         resolved_at = case
           when p_status = 'resolved' then now()
           when p_status is not null and p_status <> 'resolved' then null
           else resolved_at end
   where id = p_complaint_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- add_complaint_comment -- comment row + its timeline entry, atomically.
--
-- Readable by any member of the community (a resident must be able to talk to
-- management about their own complaint), so this one does NOT require admin.
-- Internal comments stay admin-only, enforced by the RLS policy from 0011.
-- ---------------------------------------------------------------------------
create or replace function public.add_complaint_comment(
  p_complaint_id     uuid,
  p_body             text,
  p_visibility       text default 'resident',
  p_author_membership uuid default null,
  p_author_label     text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  c          public.complaints%rowtype;
  comment_id uuid;
begin
  if nullif(btrim(coalesce(p_body, '')), '') is null then
    raise exception 'A comment cannot be empty.' using errcode = 'HB409';
  end if;

  if p_visibility not in ('resident', 'internal') then
    raise exception 'Unknown visibility.' using errcode = 'HB409';
  end if;

  select * into c from public.complaints where id = p_complaint_id;
  if not found then
    raise exception 'Complaint not found.' using errcode = 'HB404';
  end if;

  -- Membership of the community is the floor; only an admin may write an
  -- internal comment.
  if c.community_id not in (select public.current_community_ids())
     or (p_visibility = 'internal' and not public.is_admin()) then
    raise exception 'Not permitted for this complaint.' using errcode = 'HB403';
  end if;

  insert into public.complaint_comments
    (community_id, complaint_id, author_membership_id, author_label, body, visibility)
  values
    (c.community_id, p_complaint_id, p_author_membership, p_author_label,
     btrim(p_body), p_visibility)
  returning id into comment_id;

  -- Internal notes do not appear on the resident-visible timeline.
  if p_visibility = 'resident' then
    insert into public.complaint_events
      (community_id, complaint_id, event_type, label, message,
       actor_membership_id, actor_label)
    values
      (c.community_id, p_complaint_id, 'comment', 'New comment',
       btrim(p_body), p_author_membership, coalesce(p_author_label, 'Resident'));
  end if;

  -- Touch the complaint so unread-badge comparisons against read receipts work.
  update public.complaints set updated_at = now() where id = p_complaint_id;

  return comment_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------
revoke execute on function public.update_complaint(
  uuid, text, text, uuid, smallint, timestamptz, text, uuid, text
) from public, anon;
revoke execute on function public.add_complaint_comment(uuid, text, text, uuid, text)
  from public, anon;

grant execute on function public.update_complaint(
  uuid, text, text, uuid, smallint, timestamptz, text, uuid, text
) to authenticated;
grant execute on function public.add_complaint_comment(uuid, text, text, uuid, text)
  to authenticated;

-- ---------------------------------------------------------------------------
-- Row-Level Security
--
-- SELECT and INSERT only. There is deliberately NO update or delete policy:
-- that is what makes the timeline append-only, rather than merely documented as
-- append-only.
-- ---------------------------------------------------------------------------
alter table public.complaint_events enable row level security;

drop policy if exists complaint_events_member_read on public.complaint_events;
create policy complaint_events_member_read on public.complaint_events
  for select using (community_id in (select public.current_community_ids()));

drop policy if exists complaint_events_member_insert on public.complaint_events;
create policy complaint_events_member_insert on public.complaint_events
  for insert with check (community_id in (select public.current_community_ids()));

-- ---------------------------------------------------------------------------
-- Verification -- run after applying.
-- ---------------------------------------------------------------------------
-- The timeline is genuinely append-only (expect exactly the two policies above,
-- and no UPDATE or DELETE among them):
--   select policyname, cmd from pg_policies
--   where tablename = 'complaint_events';
--
-- Every complaint with a status other than its original has at least one event
-- (expect zero rows once the API is the only writer):
--   select c.id from public.complaints c
--   left join public.complaint_events e on e.complaint_id = c.id
--   where c.status <> 'pending' and e.id is null;
--
-- Due dates were computed (expect zero rows for complaints that have a category):
--   select id from public.complaints where category_id is not null and due_at is null;
