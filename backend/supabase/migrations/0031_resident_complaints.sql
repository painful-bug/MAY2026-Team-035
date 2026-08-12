-- The resident half of complaints: the columns their form collects, the SLA
-- rule, the four writes they perform, and the notifications every complaint
-- write now emits.
--
-- docs/design/RESIDENT_BACKEND_DESIGN.md 3.2, 3.3, 5.2, 5.3, 9 step 4.
--
-- WHY THIS FILE IS 0031 AND NOT 0025
--
-- 0025 is the lowest unused number in this workstream's range, and it is the
-- wrong one. Section 7 of the design states one ordering constraint: **the
-- notification substrate comes before the feature migrations**, because every
-- feature RPC below calls `notify_member`. Migrations apply in filename order,
-- so a file numbered 0025 would run five files before the function it depends
-- on. Postgres would not complain -- a plpgsql body is not resolved against the
-- catalogue until it executes -- which is exactly what makes the mistake worth
-- naming: it would apply cleanly and fail at the first complaint.
--
-- The rule "allocate a number when the file is written" does not mean "take the
-- smallest free one". It means the number is chosen with the file in front of
-- you, and the constraint that decides it here is dependency order.
--
-- WHAT WAS ALREADY HERE
--
-- The baseline has all four complaint tables. `0019` added `department_id`,
-- `assigned_to_membership_id`, `assignee_label` and `due_at`; `0020` added
-- `progress_percent`, the timeline's `actor_label`, comment `visibility`, and
-- the two admin write RPCs. Every one of those columns exists for the **admin**
-- editor. Nothing in the schema records what the resident's own form collects,
-- which is finding 3.2.
--
-- THE SLA IS A PRODUCT RULE, AND IT WAS LIVING IN THE BROWSER
--
-- `getExpectedResolutionAt` in `createComplaintsSlice.js` encodes High 24h,
-- Medium 48h, Low 72h. In a store slice it is (a) trivially bypassable -- a
-- resident could send themselves a one-minute deadline -- and (b) invisible to
-- the admin portal, which computes its own `due_at`. Section 3.3. It moves into
-- `complaint_sla_hours` below and is applied on insert, so there is one rule,
-- one place, and the resident's expectation and the admin's deadline stop being
-- two independent numbers.
--
-- ROW SECURITY, WHICH `complaints` NEVER HAD
--
-- `0020` enabled RLS on `complaint_events` and `complaint_comments` and left the
-- parent table open. So today any authenticated user can read every complaint in
-- the project through PostgREST -- title, description, flat, and now the
-- resident's own feedback. That was tolerable while complaints were an
-- admin-only surface reached through an admin-guarded API. **This migration is
-- what puts a resident's grievances behind an endpoint they call themselves**,
-- so the policy lands in the same file. Same timing rule as `0028` and `0030`.
--
-- The policy is deliberately narrower than the one `0020` wrote for the child
-- tables. `is_community_member` would let every resident read every neighbour's
-- complaint, which is not what a complaint is. Admins see the queue; a resident
-- sees their own. The two child policies are tightened to match, because a
-- timeline is only as private as the row it hangs off.

-- ---------------------------------------------------------------------------
-- 1. The columns the resident's form collects
--
-- `priority` rather than `urgency`: the frontend's word is `urgency`, the
-- admin's existing column for the same idea is `priority` on `work_orders`, and
-- the schema should not carry two names for one concept. The wire keeps saying
-- `urgency` -- `app/domain/vocabularies.py` does that translation, as it does
-- for every other vocabulary that differs between the two.
--
-- `reopened_count` is a real column even though `0020` argued a reopen is
-- answerable by counting timeline events. Both are true: the event is the
-- record, the counter is what a list query can sort and filter on without a
-- correlated subquery per row.
-- ---------------------------------------------------------------------------

alter table public.complaints
  add column if not exists priority               text not null default 'low',
  add column if not exists location               text,
  add column if not exists expected_resolution_at timestamptz,
  add column if not exists reopened_count         integer not null default 0,
  add column if not exists resolution_rating      smallint,
  add column if not exists resident_feedback      text;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'complaints_priority_check'
  ) then
    alter table public.complaints
      add constraint complaints_priority_check
      check (priority in ('low', 'medium', 'high'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'complaints_resolution_rating_check'
  ) then
    alter table public.complaints
      add constraint complaints_resolution_rating_check
      check (resolution_rating is null or resolution_rating between 1 and 5);
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'complaints_reopened_count_check'
  ) then
    alter table public.complaints
      add constraint complaints_reopened_count_check
      check (reopened_count >= 0);
  end if;
end $$;

-- The resident list: my complaints, newest first. The admin queue is served by
-- `complaints_department_idx` from 0019, which leads on a column a resident
-- never filters by.
create index if not exists complaints_raised_by_created_idx
  on public.complaints (raised_by_membership_id, created_at desc);

-- ---------------------------------------------------------------------------
-- 2. The SLA rule
--
-- Immutable and total: an unrecognised priority reads as medium rather than
-- raising, because a complaint that cannot be filed because someone typed
-- `urgent` is a worse outcome than a complaint with a 48-hour deadline. The
-- CHECK above is what actually keeps the column to three values; this function
-- is what keeps the rule readable.
-- ---------------------------------------------------------------------------

create or replace function public.complaint_sla_hours(p_priority text)
returns integer
language sql
immutable
as $$
  select case lower(coalesce(btrim(p_priority), ''))
           when 'high'   then 24
           when 'medium' then 48
           when 'low'    then 72
           else 48
         end;
$$;

comment on function public.complaint_sla_hours(text) is
  'Hours until a complaint of this priority is expected to be resolved. The rule from RESIDENT_BACKEND_DESIGN.md 3.3, moved out of the browser.';

grant execute on function public.complaint_sla_hours(text) to authenticated;

-- ---------------------------------------------------------------------------
-- 3. Fan-out to the people who act on complaints
--
-- `notify_member` writes to one recipient, which is right for it: the substrate
-- should not know what a community is. But a resident raising a complaint has to
-- reach whoever is on duty, and that is a set.
--
-- Admins *and* managers, matching the audience `0028` gave `dashboard.refresh`.
-- The two lists must not drift: a manager who sees the complaint appear on the
-- dashboard but never gets a notification is worse than one who gets neither,
-- because only one of those looks like a delivery bug.
--
-- `p_exclude_membership` keeps an admin who raised a complaint themselves from
-- being told about it. Self-notification is not a rounding error -- it is the
-- badge on the bell counting your own actions back at you.
-- ---------------------------------------------------------------------------

create or replace function public.notify_community_staff(
  p_community_id       uuid,
  p_kind               text,
  p_payload            jsonb default '{}'::jsonb,
  p_exclude_membership uuid default null
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_sent integer := 0;
  v_row  record;
begin
  if p_community_id is null then
    raise exception 'notify_community_staff requires a community'
      using errcode = '22004';
  end if;

  for v_row in
    select m.id
      from public.community_memberships m
     where m.community_id = p_community_id
       and m.role in ('admin', 'manager')
       and m.status = 'active'
       and m.ended_at is null
       and (p_exclude_membership is null or m.id <> p_exclude_membership)
  loop
    perform public.notify_member(v_row.id, p_kind, p_payload);
    v_sent := v_sent + 1;
  end loop;

  return v_sent;
end;
$$;

comment on function public.notify_community_staff(uuid, text, jsonb, uuid) is
  'Notify every active admin and manager of a community. Same audience as the dashboard SSE topic.';

-- Same correction as `notify_member` in 0030: every caller is a SECURITY DEFINER
-- function, so the EXECUTE check falls to the definer and the grant to
-- `authenticated` bought nothing while letting any signed-in user broadcast a
-- notification of their own composition to a whole community's staff.
revoke all on function public.notify_community_staff(uuid, text, jsonb, uuid)
  from public, anon, authenticated;
grant execute on function public.notify_community_staff(uuid, text, jsonb, uuid) to service_role;

-- ---------------------------------------------------------------------------
-- 4. complaint_overview: the resident's projection
--
-- `security_invoker`, like every view in this schema, so the policy in section
-- 10 decides what a caller sees rather than the view's owner.
--
-- Three things are computed here rather than in Python:
--
-- `is_unread` -- whether the complaint has moved since this caller last opened
-- it. It is per-caller, which is why it cannot live on the row: two people read
-- the same complaint at different times. `complaint_read_state` has existed
-- since the baseline and has never been written to by anything.
--
-- The read-state join matches **the caller's own rows**, not the raiser's. An
-- earlier draft joined on `raised_by_membership_id`, which is the same thing on
-- the only surface that reads this view today and stops being the same thing the
-- moment anything else does: `mark_complaint_read` deliberately writes a row per
-- membership so an admin opening a complaint cannot clear the resident's marker,
-- and a view keyed to the raiser would ignore every row it wrote. `max()` over a
-- lateral rather than a plain join, because a user with two memberships must not
-- turn one complaint into two rows in a list.
--
-- `is_overdue` -- past its expected resolution and not yet resolved. The same
-- shape `department_overview` already uses for its overdue count, so the two
-- screens cannot disagree about what overdue means.
--
-- `comment_count` and `last_activity_at` -- what a list row shows. Aggregating
-- here means the list is one query rather than one plus N.
-- ---------------------------------------------------------------------------

drop view if exists public.complaint_overview;
create view public.complaint_overview
with (security_invoker = true) as
select
  c.id,
  c.community_id,
  c.raised_by_membership_id,
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
-- 5. raise_complaint
--
-- The membership id is a parameter and is checked against `is_own_membership`,
-- the pattern `0030`'s subscription writes established. A SECURITY DEFINER
-- function that trusts a caller-supplied membership id is one that lets anyone
-- file a complaint in someone else's name.
--
-- The insert, the SLA, the timeline entry and the staff notification are one
-- transaction. A complaint that exists with no timeline is a complaint whose
-- history starts with a gap, and a complaint nobody was told about is one that
-- sits in a queue no one refreshed.
-- ---------------------------------------------------------------------------

create or replace function public.raise_complaint(
  p_membership_id uuid,
  p_title         text,
  p_description   text,
  p_category      text,
  p_priority      text default 'low',
  p_location      text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_priority     text := lower(coalesce(nullif(btrim(coalesce(p_priority, '')), ''), 'low'));
  v_title        text := nullif(btrim(coalesce(p_title, '')), '');
  v_category     text := nullif(btrim(coalesce(p_category, '')), '');
  v_id           uuid;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'A complaint may only be raised for your own membership.'
      using errcode = '42501';
  end if;

  if v_title is null then
    raise exception 'A complaint needs a title.' using errcode = '23514';
  end if;

  if v_category is null then
    raise exception 'A complaint needs a category.' using errcode = '23514';
  end if;

  if v_priority not in ('low', 'medium', 'high') then
    raise exception 'Unknown complaint priority: %', p_priority
      using errcode = '22P02';
  end if;

  select m.community_id into v_community_id
    from public.community_memberships m
   where m.id = p_membership_id;

  insert into public.complaints (
    community_id, raised_by_membership_id, title, description, category,
    status, priority, location, expected_resolution_at, due_at
  )
  values (
    v_community_id,
    p_membership_id,
    v_title,
    nullif(btrim(coalesce(p_description, '')), ''),
    v_category,
    'open',
    v_priority,
    nullif(btrim(coalesce(p_location, '')), ''),
    now() + make_interval(hours => public.complaint_sla_hours(v_priority)),
    now() + make_interval(hours => public.complaint_sla_hours(v_priority))
  )
  returning id into v_id;

  -- `due_at` above is set to the same instant deliberately. It is the admin
  -- queue's column and 0019 left it nullable with nothing populating it; a
  -- resident's expectation and an admin's deadline starting out equal is the
  -- whole point of section 3.3. An admin may still move `due_at` afterwards,
  -- and that divergence is a decision someone made rather than two formulas.

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_id, p_membership_id, 'raised',
    jsonb_build_object('priority', v_priority, 'category', v_category)
  );

  perform public.notify_community_staff(
    v_community_id,
    'complaint.raised',
    jsonb_build_object(
      'title', 'New complaint raised',
      'body',  v_title,
      'url',   '/admin/complaints?complaint=' || v_id::text,
      'complaint_id', v_id
    ),
    p_membership_id
  );

  return v_id;
end;
$$;

comment on function public.raise_complaint(uuid, text, text, text, text, text) is
  'Raise a complaint for your own membership. Computes the SLA, opens the timeline, and notifies the community staff.';

grant execute on function public.raise_complaint(uuid, text, text, text, text, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 6. reopen_complaint
--
-- From `resolved` or `closed`, and only by the person who raised it. Not from
-- `cancelled`: the other two are the association saying the work is done, which
-- is a claim a resident may disagree with, while a cancelled complaint was
-- withdrawn or ruled out and reopening it is filing it again. Both of the
-- accepted statuses render as `Resolved` on the wire, so the distinction is
-- invisible from the resident's side -- which is why the error message below
-- says `resolved` and means both.
--
-- The reason
-- is required: reopening without one gives the admin a complaint that came back
-- with no statement of what is still wrong, which is the thing the timeline
-- exists to prevent.
--
-- The SLA clock restarts from now. A reopened complaint carrying its original
-- deadline would be overdue the instant it reopened, which reads as a failure
-- nobody committed.
--
-- `resolution_rating` and `resident_feedback` are cleared. They described a
-- resolution that is no longer being claimed, and leaving a four-star rating on
-- a complaint the resident just said is not fixed would be a record that
-- contradicts itself.
-- ---------------------------------------------------------------------------

create or replace function public.reopen_complaint(
  p_complaint_id uuid,
  p_reason       text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row    public.complaints%rowtype;
  v_reason text := nullif(btrim(coalesce(p_reason, '')), '');
begin
  select * into v_row from public.complaints where id = p_complaint_id;

  if v_row.id is null then
    raise exception 'Complaint not found.' using errcode = 'P0002';
  end if;

  if not public.is_own_membership(v_row.raised_by_membership_id) then
    raise exception 'Only the resident who raised a complaint may reopen it.'
      using errcode = '42501';
  end if;

  if v_row.status not in ('resolved', 'closed') then
    -- The message says "resolved" and the check accepts `closed` as well
    -- because both render as `Resolved` on the wire (`vocabularies.py`). A
    -- message naming a status the resident's screen never shows would be
    -- describing a state they cannot see themselves in.
    raise exception 'Only a resolved complaint can be reopened.'
      using errcode = '23514';
  end if;

  if v_reason is null then
    raise exception 'Reopening a complaint needs a reason.' using errcode = '23514';
  end if;

  update public.complaints
     set status                 = 'open',
         progress_percent       = 0,
         resolved_at            = null,
         resolution_rating      = null,
         resident_feedback      = null,
         reopened_count         = reopened_count + 1,
         expected_resolution_at = now()
           + make_interval(hours => public.complaint_sla_hours(priority)),
         aggregate_version      = aggregate_version + 1,
         updated_at             = now()
   where id = p_complaint_id;

  -- Two events, because two things happened. `0020`'s reader counts reopenings
  -- by looking for a `status_changed` whose `from` is terminal, and that query
  -- must keep working; the `reopened` event is what carries the resident's
  -- reason.
  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values
    (p_complaint_id, v_row.raised_by_membership_id, 'status_changed',
     jsonb_build_object('from', v_row.status::text, 'to', 'open')),
    (p_complaint_id, v_row.raised_by_membership_id, 'reopened',
     jsonb_build_object('reason', v_reason));

  perform public.notify_community_staff(
    v_row.community_id,
    'complaint.reopened',
    jsonb_build_object(
      'title', 'A complaint was reopened',
      'body',  v_row.title,
      'url',   '/admin/complaints?complaint=' || p_complaint_id::text,
      'complaint_id', p_complaint_id
    ),
    v_row.raised_by_membership_id
  );
end;
$$;

comment on function public.reopen_complaint(uuid, text) is
  'Reopen your own resolved complaint with a reason. Restarts the SLA and notifies the community staff.';

grant execute on function public.reopen_complaint(uuid, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 7. confirm_complaint_resolution
--
-- `resolved` is what the admin says; `closed` is what the resident agrees. That
-- is the distinction the baseline's enum already carries and nothing has been
-- using -- `update_complaint` treats the two as one terminal state. Here they
-- stop being synonyms: only a resident's confirmation closes a complaint.
--
-- The rating is required and the feedback is not. A rating with no comment is a
-- complete answer; a comment with no rating is not the thing US-2.6 asks for.
-- ---------------------------------------------------------------------------

create or replace function public.confirm_complaint_resolution(
  p_complaint_id uuid,
  p_rating       smallint,
  p_feedback     text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.complaints%rowtype;
begin
  select * into v_row from public.complaints where id = p_complaint_id;

  if v_row.id is null then
    raise exception 'Complaint not found.' using errcode = 'P0002';
  end if;

  if not public.is_own_membership(v_row.raised_by_membership_id) then
    raise exception 'Only the resident who raised a complaint may confirm it.'
      using errcode = '42501';
  end if;

  if v_row.status <> 'resolved' then
    raise exception 'Only a resolved complaint can be confirmed.'
      using errcode = '23514';
  end if;

  if p_rating is null or p_rating < 1 or p_rating > 5 then
    raise exception 'A resolution rating must be between 1 and 5.'
      using errcode = '23514';
  end if;

  update public.complaints
     set status            = 'closed',
         resolution_rating = p_rating,
         resident_feedback = nullif(btrim(coalesce(p_feedback, '')), ''),
         resolved_at       = coalesce(resolved_at, now()),
         progress_percent  = 100,
         aggregate_version = aggregate_version + 1,
         updated_at        = now()
   where id = p_complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    p_complaint_id, v_row.raised_by_membership_id, 'resolution_confirmed',
    jsonb_build_object(
      'rating', p_rating,
      'feedback', nullif(btrim(coalesce(p_feedback, '')), '')
    )
  );

  perform public.notify_community_staff(
    v_row.community_id,
    'complaint.resolution_confirmed',
    jsonb_build_object(
      'title', 'A resident confirmed a resolution',
      'body',  v_row.title,
      'url',   '/admin/complaints?complaint=' || p_complaint_id::text,
      'complaint_id', p_complaint_id
    ),
    v_row.raised_by_membership_id
  );
end;
$$;

comment on function public.confirm_complaint_resolution(uuid, smallint, text) is
  'Confirm the resolution of your own complaint with a 1-5 rating. Moves resolved to closed.';

grant execute on function public.confirm_complaint_resolution(uuid, smallint, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 8. mark_complaint_read
--
-- `complaint_read_state` has been in the baseline since the beginning with
-- nothing writing to it. This is the writer. Any member may mark a complaint
-- they can see as read -- the row is per membership, so an admin marking one
-- read cannot clear a resident's marker.
-- ---------------------------------------------------------------------------

create or replace function public.mark_complaint_read(
  p_complaint_id  uuid,
  p_membership_id uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'A read marker may only be set for your own membership.'
      using errcode = '42501';
  end if;

  select c.community_id into v_community_id
    from public.complaints c where c.id = p_complaint_id;

  if v_community_id is null then
    raise exception 'Complaint not found.' using errcode = 'P0002';
  end if;

  insert into public.complaint_read_state (complaint_id, membership_id, last_read_at)
  values (p_complaint_id, p_membership_id, now())
  on conflict (complaint_id, membership_id)
  do update set last_read_at = now();
end;
$$;

comment on function public.mark_complaint_read(uuid, uuid) is
  'Record that this membership has seen the current state of a complaint. Clears the unread marker on complaint_overview.';

grant execute on function public.mark_complaint_read(uuid, uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 9. The retrofit: the admin's writes start telling the resident
--
-- `update_complaint` and `add_complaint_comment` are `0020`'s, unchanged in what
-- they write. What they gain is the notification -- which is the half of step 4
-- the endpoints below cannot provide, because the events a resident most needs
-- to hear about are the ones an *admin* causes.
--
-- Section 7 of the design says a notification retrofitted onto a working write
-- path is how you get an event that fires for some callers and not others. That
-- is precisely why this is a `create or replace` on the existing functions
-- rather than a trigger or a second code path: there is one writer per action,
-- and the notification is inside it.
--
-- Both bodies below are `0020`'s verbatim except for the marked blocks. They are
-- reproduced in full because `create or replace` has no partial form -- a
-- function is replaced whole or not at all.
-- ---------------------------------------------------------------------------

create or replace function public.update_complaint(
  p_complaint_id     uuid,
  p_status           text,
  p_assignee_label   text,
  p_assigned_to      uuid,
  p_progress_percent integer,
  p_due_at           timestamptz,
  p_update_note      text,
  p_actor_membership uuid,
  p_actor_label      text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_old          public.complaints%rowtype;
  v_new_status   public.complaint_status;
begin
  select * into v_old from public.complaints where id = p_complaint_id;

  if v_old.id is null then
    raise exception 'Complaint not found.' using errcode = 'P0002';
  end if;

  v_community_id := v_old.community_id;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may edit a complaint.'
      using errcode = '42501';
  end if;

  if p_status is not null then
    begin
      v_new_status := p_status::public.complaint_status;
    exception when invalid_text_representation then
      raise exception 'Unknown complaint status: %', p_status using errcode = '22P02';
    end;
  end if;

  update public.complaints
     set status                    = coalesce(v_new_status, status),
         assignee_label            = case when p_assignee_label is not null
                                          then nullif(btrim(p_assignee_label), '')
                                          else assignee_label end,
         assigned_to_membership_id = coalesce(p_assigned_to, assigned_to_membership_id),
         progress_percent          = coalesce(p_progress_percent, progress_percent),
         due_at                    = coalesce(p_due_at, due_at),
         resolved_at               = case
                                       when v_new_status in ('resolved', 'closed')
                                            and resolved_at is null then now()
                                       when v_new_status is not null
                                            and v_new_status not in ('resolved', 'closed')
                                            then null
                                       else resolved_at
                                     end,
         aggregate_version         = aggregate_version + 1,
         updated_at                = now()
   where id = p_complaint_id;

  if v_new_status is not null and v_new_status is distinct from v_old.status then
    insert into public.complaint_events
      (complaint_id, actor_membership_id, actor_label, event_type, payload)
    values (
      p_complaint_id, p_actor_membership, p_actor_label, 'status_changed',
      jsonb_build_object('from', v_old.status::text, 'to', v_new_status::text)
    );

    -- >>> 0031: tell the resident their complaint moved.
    --
    -- Only on a status change, and only to the person who raised it. An
    -- assignee changing or a progress bar moving from 40% to 45% is not
    -- something to buzz a phone for; a resident who is notified about
    -- everything stops reading notifications, which costs more than the ones
    -- they miss.
    --
    -- `resolved` gets its own kind because it is the one status change that
    -- asks the resident to do something next -- confirm it, or reopen it.
    if v_old.raised_by_membership_id is distinct from p_actor_membership then
      perform public.notify_member(
        v_old.raised_by_membership_id,
        case when v_new_status = 'resolved'
             then 'complaint.resolved'
             else 'complaint.status_changed' end,
        jsonb_build_object(
          'title', case when v_new_status = 'resolved'
                        then 'Your complaint was resolved'
                        else 'Your complaint was updated' end,
          'body',  v_old.title,
          'url',   '/resident/complaints?complaint=' || p_complaint_id::text,
          'complaint_id', p_complaint_id,
          'status', v_new_status::text
        )
      );
    end if;
    -- <<< 0031
  end if;

  if p_assignee_label is not null
     and nullif(btrim(p_assignee_label), '') is distinct from v_old.assignee_label then
    insert into public.complaint_events
      (complaint_id, actor_membership_id, actor_label, event_type, payload)
    values (
      p_complaint_id, p_actor_membership, p_actor_label, 'assigned',
      jsonb_build_object(
        'from', v_old.assignee_label,
        'to',   nullif(btrim(p_assignee_label), '')
      )
    );
  end if;

  if p_progress_percent is not null
     and p_progress_percent is distinct from v_old.progress_percent then
    insert into public.complaint_events
      (complaint_id, actor_membership_id, actor_label, event_type, payload)
    values (
      p_complaint_id, p_actor_membership, p_actor_label, 'progress_changed',
      jsonb_build_object('from', v_old.progress_percent, 'to', p_progress_percent)
    );
  end if;

  if p_due_at is not null and p_due_at is distinct from v_old.due_at then
    insert into public.complaint_events
      (complaint_id, actor_membership_id, actor_label, event_type, payload)
    values (
      p_complaint_id, p_actor_membership, p_actor_label, 'due_date_changed',
      jsonb_build_object('from', v_old.due_at, 'to', p_due_at)
    );
  end if;

  if nullif(btrim(coalesce(p_update_note, '')), '') is not null then
    insert into public.complaint_events
      (complaint_id, actor_membership_id, actor_label, event_type, payload)
    values (
      p_complaint_id, p_actor_membership, p_actor_label, 'note_added',
      jsonb_build_object('note', btrim(p_update_note))
    );
  end if;
end $$;

create or replace function public.add_complaint_comment(
  p_complaint_id      uuid,
  p_body              text,
  p_visibility        text,
  p_author_membership uuid,
  p_author_label      text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_raised_by    uuid;
  v_title        text;
  v_visibility   text := coalesce(nullif(btrim(coalesce(p_visibility, '')), ''), 'public');
  v_id           uuid;
begin
  select c.community_id, c.raised_by_membership_id, c.title
    into v_community_id, v_raised_by, v_title
    from public.complaints c where c.id = p_complaint_id;

  if v_community_id is null then
    raise exception 'Complaint not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_member(v_community_id) then
    raise exception 'Only a member of this community may comment.'
      using errcode = '42501';
  end if;

  if v_visibility = 'internal' and not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin may leave an internal comment.'
      using errcode = '42501';
  end if;

  if nullif(btrim(coalesce(p_body, '')), '') is null then
    raise exception 'A comment cannot be empty.' using errcode = '23514';
  end if;

  insert into public.complaint_comments
    (complaint_id, author_membership_id, author_label, body, visibility)
  values
    (p_complaint_id, p_author_membership, p_author_label, btrim(p_body), v_visibility)
  returning id into v_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, actor_label, event_type, payload)
  values (
    p_complaint_id, p_author_membership, p_author_label, 'comment_added',
    jsonb_build_object('comment_id', v_id, 'visibility', v_visibility)
  );

  update public.complaints
     set aggregate_version = aggregate_version + 1,
         updated_at        = now()
   where id = p_complaint_id;

  -- >>> 0031: tell the other party a comment landed.
  --
  -- An **internal** comment notifies nobody. The whole point of the flag is
  -- that the resident does not see it, and a notification saying "new comment
  -- on your complaint" that leads to a thread where nothing new is visible is a
  -- worse leak than showing the comment would have been -- it tells the
  -- resident something was said about them and refuses to say what.
  --
  -- The comment body is not copied into the payload. `notifications_service`
  -- renders exactly `title`, `body` and `url`, and `body` here is the complaint
  -- title -- the thing the resident already knows -- so a push on a locked
  -- screen never carries someone else's words about them.
  if v_visibility = 'public' then
    if v_raised_by is distinct from p_author_membership then
      perform public.notify_member(
        v_raised_by,
        'complaint.commented',
        jsonb_build_object(
          'title', 'New comment on your complaint',
          'body',  v_title,
          'url',   '/resident/complaints?complaint=' || p_complaint_id::text,
          'complaint_id', p_complaint_id
        )
      );
    else
      -- The resident commented. Staff hear about it instead, otherwise a
      -- resident chasing their own complaint is talking into an empty room.
      perform public.notify_community_staff(
        v_community_id,
        'complaint.commented',
        jsonb_build_object(
          'title', 'New comment on a complaint',
          'body',  v_title,
          'url',   '/admin/complaints?complaint=' || p_complaint_id::text,
          'complaint_id', p_complaint_id
        ),
        p_author_membership
      );
    end if;
  end if;
  -- <<< 0031

  return v_id;
end $$;

grant execute on function public.update_complaint(uuid, text, text, uuid, integer, timestamptz, text, uuid, text) to authenticated;
grant execute on function public.add_complaint_comment(uuid, text, text, uuid, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 10. Row-level security
--
-- The parent table, at last, and the two child policies tightened to agree with
-- it. `0020` wrote `is_community_member` for the children when complaints were
-- an admin surface; with residents reading their own complaints through this
-- API, that predicate would let any resident read any neighbour's timeline by
-- asking PostgREST directly.
--
-- No insert, update or delete policy on any of the three. Every write above is a
-- SECURITY DEFINER function that does its own authorization, which is the only
-- way the SLA rule, the timeline entry and the notification can be guaranteed to
-- happen together.
-- ---------------------------------------------------------------------------

alter table public.complaints            enable row level security;
alter table public.complaint_read_state  enable row level security;

drop policy if exists complaints_read on public.complaints;
create policy complaints_read on public.complaints
  for select to authenticated
  using (
    public.is_community_admin(community_id)
    or public.is_own_membership(raised_by_membership_id)
  );

drop policy if exists complaint_read_state_read on public.complaint_read_state;
create policy complaint_read_state_read on public.complaint_read_state
  for select to authenticated
  using (public.is_own_membership(membership_id));

drop policy if exists complaint_events_read on public.complaint_events;
create policy complaint_events_read on public.complaint_events
  for select to authenticated
  using (exists (
    select 1 from public.complaints c
     where c.id = complaint_id
       and (
         public.is_community_admin(c.community_id)
         or public.is_own_membership(c.raised_by_membership_id)
       )
  ));

drop policy if exists complaint_comments_read on public.complaint_comments;
create policy complaint_comments_read on public.complaint_comments
  for select to authenticated
  using (exists (
    select 1 from public.complaints c
     where c.id = complaint_id
       and (
         public.is_community_admin(c.community_id)
         or public.is_own_membership(c.raised_by_membership_id)
       )
       and (visibility = 'public' or public.is_community_admin(c.community_id))
  ));
