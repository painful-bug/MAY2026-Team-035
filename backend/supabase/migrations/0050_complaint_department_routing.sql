-- ---------------------------------------------------------------------------
-- 0050 — Complaint department routing
--
-- Until now a complaint reached a department only once dispatch built a work
-- order from it (`work_orders.department_id`, 0036). Before that moment it
-- belonged to nobody, which is why `complaint.raised` was sent to *every*
-- admin and manager in the community: there was no better answer available.
--
-- This file gives a complaint a department from the moment it is raised.
--
-- THE ROUTING RULE (product owner, 2026-08-12), in precedence order:
--
--   1. The complaint's CATEGORY, matched to `complaint_categories` and followed
--      through `department_categories` (0019) to a department.
--   2. Failing that, the DEPARTMENT THE RESIDENT NAMED.
--   3. Failing that, nothing — the complaint waits in the admin's triage queue
--      and an admin allots it.
--
-- "Category wins over the resident's pick" is the ruling, and it is the right
-- way round: the category mapping is curated by an admin who knows how this
-- society is organised, and the resident is guessing. The resident's pick is
-- not decoration, though — it is what routes the cases the catalogue cannot,
-- which is exactly the "Other" category and anything nobody has mapped yet.
--
-- "Not sure" and "Other" are NOT special values anywhere in this file. They are
-- simply the two inputs that match nothing and fall through to the next rule.
-- Encoding them as sentinels would have put two more strings in the system that
-- every reader has to know about, to express something the absence of a match
-- already says.
--
-- AMBIGUITY GOES TO A HUMAN. `department_categories` has a composite primary
-- key, so one category may legally be attached to several departments. When it
-- is, this file routes to *nothing* rather than picking. A complaint sitting in
-- the triage queue is a visible question an admin answers in one click; a
-- complaint silently sent to whichever department claimed the category first is
-- an invisible wrong answer, and the only person who could notice is the
-- department that did not get it.
--
-- WHY `raise_complaint` IS DROPPED AND REBUILT RATHER THAN CORRECTED IN 0031.
-- This adds a parameter, which changes the signature. `create or replace` would
-- not replace anything -- it would create a second overload, and every existing
-- six-argument call would then fail as ambiguous rather than route badly, which
-- is a worse failure than the one being fixed. The README's correct-in-place
-- precedent is for corrections to what a file already meant; this is a change to
-- what it does, so it lands in its own numbered file. 0031 carries a pointer
-- forward so nobody reads its definition and believes it.
--
-- MIGRATION NUMBER. `0034`-`0049` was exhausted by `0049`; the range was
-- extended to `0050`-`0059` in this directory's README on the same day.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- 1. The column
-- ---------------------------------------------------------------------------

alter table public.complaints
  add column if not exists department_id uuid;

-- WHY NOT THE COMPOSITE (department_id, community_id) FK THAT WORK ORDERS USE.
--
-- `work_orders_department_tenant_fkey` (0036) pairs the two columns so a job
-- cannot point at another community's department, and takes `on delete cascade`
-- because a job *is* that department's work -- delete the department, the job
-- goes with it.
--
-- Neither half transfers. A complaint is the resident's, not the department's:
-- deleting a department must not delete the complaints it happened to be
-- holding. And the gentler-looking `on delete set null` is unavailable on a
-- multi-column constraint without nulling `community_id` too, which is
-- `not null` (0001:69) -- so it would refuse to delete the department at all.
--
-- Single column, `set null`, and the same-community check lives in the two
-- functions below that ever set this value. That is a weaker guarantee than a
-- constraint and it is stated here rather than hidden: nothing except those
-- functions may write this column, because `complaints` has no INSERT or UPDATE
-- RLS policy (the 0031 posture) and every writer is SECURITY DEFINER.
do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.complaints'::regclass
       and conname  = 'complaints_department_id_fkey'
  ) then
    alter table public.complaints
      add constraint complaints_department_id_fkey
      foreign key (department_id)
      references public.departments (id)
      on delete set null;
  end if;
end $$;

-- The department's own queue, and the admin's triage queue, are the same index
-- read two ways: `where department_id = $1` and `where department_id is null`.
create index if not exists complaints_department_idx
  on public.complaints (department_id, status, created_at desc);

comment on column public.complaints.department_id is
  'Which department owns this complaint. Null means nobody yet -- the admin''s '
  'triage queue. Set by resolve_complaint_department at raise time, and moved '
  'by an admin allotting or a manager accepting a change request.';

-- ---------------------------------------------------------------------------
-- 2. The rule, in one place
--
-- STABLE and no authorization check: it reads only the category catalogue and
-- the department list, decides nothing about who may see what, and is called
-- from inside three SECURITY DEFINER functions that have each already
-- authorized their caller. Making it a function rather than three copies of a
-- query is the point -- a routing rule that lives in three places is a routing
-- rule that will eventually disagree with itself.
-- ---------------------------------------------------------------------------

create or replace function public.resolve_complaint_department(
  p_community_id  uuid,
  p_category      text,
  p_department_id uuid default null
)
returns uuid
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_category text := lower(btrim(coalesce(p_category, '')));
  v_matches  uuid[];
  v_chosen   uuid;
begin
  -- 1. The category, if it names one department and only one.
  if v_category <> '' then
    select array_agg(distinct dc.department_id)
      into v_matches
      from public.complaint_categories cc
      join public.department_categories dc on dc.category_id = cc.id
      join public.departments d           on d.id = dc.department_id
     where cc.community_id = p_community_id
       and lower(btrim(cc.name)) = v_category
       and d.community_id = p_community_id
       and coalesce(d.status, 'active') = 'active';

    if coalesce(array_length(v_matches, 1), 0) = 1 then
      return v_matches[1];
    end if;

    -- Attached to several departments: ambiguous, and answering it here would
    -- be guessing. Returns null even when the resident named one of them --
    -- letting the resident break a tie between departments would quietly invert
    -- the precedence rule the whole function exists to express.
    if coalesce(array_length(v_matches, 1), 0) > 1 then
      return null;
    end if;
  end if;

  -- 2. The resident's own pick, if it is a real department of this community.
  --    Silently ignored when it is not, rather than raised: a stale id from a
  --    cached form should route the complaint to triage, not refuse to file it.
  if p_department_id is not null then
    select d.id into v_chosen
      from public.departments d
     where d.id = p_department_id
       and d.community_id = p_community_id
       and coalesce(d.status, 'active') = 'active';
    return v_chosen;
  end if;

  -- 3. Nobody. The admin's queue.
  return null;
end;
$$;

comment on function public.resolve_complaint_department(uuid, text, uuid) is
  'Which department owns a complaint: its category first, the resident''s pick '
  'second, nothing third. Null means the admin triage queue, and a category '
  'mapped to several departments deliberately returns null rather than guessing.';

grant execute on function public.resolve_complaint_department(uuid, text, uuid)
  to authenticated;

-- ---------------------------------------------------------------------------
-- 2b. Who to tell about a complaint
--
-- The replacement for `notify_community_staff` on anything complaint-shaped.
-- That helper means every admin **and every manager**, which is how the manager
-- of the plumbing department came to be told about lift complaints, comments on
-- them, and their resolutions -- each with a link to `/admin/complaints`, a
-- screen their portal has no route for.
--
-- Admins always; the owning department's manager when there is one. The manager
-- predicate is `community_memberships.department_id`, which is the same column
-- `_portal_for` reads to decide who gets `/manager` at all -- deliberately
-- mirrored, because if the audience and the portal ever disagree, somebody is
-- notified about a screen they cannot open.
--
-- **0031 calls this and is an earlier file.** plpgsql bodies are not resolved
-- until they run, and by then every migration has been applied, so a forward
-- reference is safe. It is also the smaller evil: the alternative was this loop
-- copied into four call sites, where the fifth author copies whichever one they
-- found.
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
    select m.id
      from public.community_memberships m
     where m.community_id  = v_complaint.community_id
       and m.department_id = v_complaint.department_id
       and m.role::text    = 'manager'
       and m.status        = 'active'
       and m.ended_at is null
       and (p_exclude_membership is null or m.id <> p_exclude_membership)
  loop
    perform public.notify_member(v_manager.id, p_kind, p_payload);
  end loop;
end;
$$;

comment on function public.notify_complaint_staff(uuid, text, jsonb, uuid) is
  'Tell the community''s admins and the complaint''s own department manager. '
  'Replaces notify_community_staff on complaint events, which told every '
  'manager in the community about every complaint.';

revoke all on function public.notify_complaint_staff(uuid, text, jsonb, uuid)
  from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- 3. raise_complaint, rebuilt
--
-- Same body as 0031 plus two things: the department is resolved and stored, and
-- the notification stops going to every manager in the community.
--
-- THE AUDIENCE CHANGE IS THE POINT OF THIS SECTION. `notify_community_staff`
-- means every admin *and every manager*, so the manager of the plumbing
-- department was told about a lift complaint, and the link went to
-- `/admin/complaints`, which their portal does not have a route for -- so the
-- click bounced them silently to their own overview. Two defects, one cause:
-- there was no department on the complaint, so there was nobody better to tell.
-- Now there is.
-- ---------------------------------------------------------------------------

drop function if exists public.raise_complaint(uuid, text, text, text, text, text);

create or replace function public.raise_complaint(
  p_membership_id uuid,
  p_title         text,
  p_description   text,
  p_category      text,
  p_priority      text default 'low',
  p_location      text default null,
  p_department_id uuid default null
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
  v_department   uuid;
  v_payload      jsonb;
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

  v_department := public.resolve_complaint_department(
    v_community_id, v_category, p_department_id
  );

  insert into public.complaints (
    community_id, raised_by_membership_id, title, description, category,
    status, priority, location, expected_resolution_at, due_at, department_id
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
    now() + make_interval(hours => public.complaint_sla_hours(v_priority)),
    v_department
  )
  returning id into v_id;

  -- `due_at` above is set to the same instant deliberately. It is the admin
  -- queue's column and 0019 left it nullable with nothing populating it; a
  -- resident's expectation and an admin's deadline starting out equal is the
  -- whole point of section 3.3. An admin may still move `due_at` afterwards,
  -- and that divergence is a decision someone made rather than two formulas.

  -- The routing decision is in the timeline, not just in the column. Somebody
  -- asking "why did this go to Plumbing?" a week later can read the answer, and
  -- `department_id` being null here is the record that nobody could tell.
  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_id, p_membership_id, 'raised',
    jsonb_build_object(
      'priority', v_priority,
      'category', v_category,
      'department_id', v_department,
      'department_chosen_by_resident', p_department_id
    )
  );

  v_payload := jsonb_build_object(
    'title', 'New complaint raised',
    'body',  v_title,
    'url',   '/admin/complaints?complaint=' || v_id::text,
    'complaint_id', v_id
  );

  -- The community's admins, and the owning department's manager if the routing
  -- rule found one. Not every manager, which is what `notify_community_staff`
  -- meant and why the plumbing manager was hearing about lifts.
  --
  -- Supervisors are deliberately not notified even though they act on the
  -- complaint. Their signal is the work order dispatch creates, which already
  -- notifies them (`0037`); a second notification for the same event would
  -- double every departmental job in the bell.
  perform public.notify_complaint_staff(
    v_id, 'complaint.raised', v_payload, p_membership_id
  );

  return v_id;
end;
$$;

comment on function public.raise_complaint(
  uuid, text, text, text, text, text, uuid) is
  'File a complaint and route it: category first, the resident''s named '
  'department second, the admin triage queue third. Notifies the community''s '
  'admins and the owning department''s manager -- not every manager, who cannot '
  'all open it.';

-- ---------------------------------------------------------------------------
-- 4. Allotting and moving
--
-- Two callers, two authorizations, one function:
--
--   UNROUTED complaint -> an ADMIN allots it. This is the "category was Other,
--   so send it to the admin who can allot it to the department of his
--   choosing" half of the ruling.
--
--   ROUTED complaint -> the CURRENT department's manager moves it out. Not the
--   receiving department's manager: authorizing on the destination would let
--   the manager of B reach into A and take A's work, which is the same
--   authorize-on-the-wrong-end mistake `department_hiring.py` warns about.
--   An admin passes `can_manage_department` for every department, so they can
--   still move anything.
-- ---------------------------------------------------------------------------

create or replace function public.assign_complaint_department(
  p_membership_id uuid,
  p_complaint_id  uuid,
  p_department_id uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_complaint record;
  v_target    record;
  v_payload   jsonb;
  v_manager   record;
begin
  select c.id, c.community_id, c.department_id, c.title
    into v_complaint
    from public.complaints c
   where c.id = p_complaint_id;

  if v_complaint.id is null then
    raise exception 'No such complaint.' using errcode = 'HB404';
  end if;

  if not public.is_own_membership(p_membership_id) then
    raise exception 'That is not your membership.' using errcode = 'HB403';
  end if;

  if v_complaint.department_id is null then
    if not public.is_community_admin(v_complaint.community_id) then
      raise exception 'Only an administrator may allot an unrouted complaint.'
        using errcode = 'HB403';
    end if;
  elsif not public.can_manage_department(v_complaint.department_id) then
    raise exception 'You do not manage the department holding this complaint.'
      using errcode = 'HB403';
  end if;

  select d.id, d.name, d.community_id
    into v_target
    from public.departments d
   where d.id = p_department_id
     and d.community_id = v_complaint.community_id;

  if v_target.id is null then
    raise exception 'No such department in this community.' using errcode = 'HB404';
  end if;

  if v_target.id = v_complaint.department_id then
    return;   -- already there; a no-op is kinder than a 409 on a double click
  end if;

  update public.complaints
     set department_id = v_target.id,
         updated_at    = now()
   where id = p_complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    p_complaint_id, p_membership_id, 'department_assigned',
    jsonb_build_object(
      'from_department_id', v_complaint.department_id,
      'to_department_id',   v_target.id,
      'to_department_name', v_target.name
    )
  );

  v_payload := jsonb_build_object(
    'title', 'A complaint was assigned to your department',
    'body',  v_complaint.title,
    'url',   '/admin/complaints?complaint=' || p_complaint_id::text,
    'complaint_id', p_complaint_id
  );

  for v_manager in
    select m.id
      from public.community_memberships m
     where m.community_id  = v_complaint.community_id
       and m.department_id = v_target.id
       and m.role::text    = 'manager'
       and m.status        = 'active'
       and m.ended_at is null
       and m.id <> p_membership_id
  loop
    perform public.notify_member(v_manager.id, 'complaint.assigned', v_payload);
  end loop;
end;
$$;

comment on function public.assign_complaint_department(uuid, uuid, uuid) is
  'Allot an unrouted complaint (admins) or move a routed one out (the holding '
  'department''s manager, or an admin). Notifies the receiving manager.';

grant execute on function public.assign_complaint_department(uuid, uuid, uuid)
  to authenticated;

-- ---------------------------------------------------------------------------
-- 5. "This isn't ours"
--
-- A supervisor cannot move a complaint themselves. They raise a request and
-- their manager decides -- which is the ruling, and it is also the only shape
-- that works: a supervisor who could move work out of their own department
-- could empty it, and the department receiving it would have no say either way.
--
-- `to_department_id` is nullable on purpose. "This is not plumbing" is a useful
-- thing for a supervisor to say even when they have no idea whose it is; the
-- manager can accept it into the triage queue by deciding with no destination.
-- ---------------------------------------------------------------------------

create table if not exists public.complaint_department_requests (
  id                         uuid primary key default gen_random_uuid(),
  complaint_id               uuid not null
    references public.complaints(id) on delete cascade,
  from_department_id         uuid
    references public.departments(id) on delete set null,
  to_department_id           uuid
    references public.departments(id) on delete set null,
  requested_by_membership_id uuid not null
    references public.community_memberships(id),
  reason                     text,
  status                     text not null default 'pending'
    check (status in ('pending', 'accepted', 'rejected')),
  decided_by_membership_id   uuid
    references public.community_memberships(id),
  decided_at                 timestamptz,
  created_at                 timestamptz not null default now()
);

-- One open request per complaint. Two supervisors disagreeing about where a
-- complaint belongs is a conversation, not two rows racing a manager's inbox.
create unique index if not exists complaint_department_requests_one_open
  on public.complaint_department_requests (complaint_id) where status = 'pending';

create index if not exists complaint_department_requests_from_idx
  on public.complaint_department_requests (from_department_id, status, created_at desc);

alter table public.complaint_department_requests enable row level security;

drop policy if exists complaint_department_requests_read
  on public.complaint_department_requests;
create policy complaint_department_requests_read
  on public.complaint_department_requests for select
  using (public.can_supervise_department(from_department_id));

comment on table public.complaint_department_requests is
  'A supervisor saying a complaint belongs to another department, and the '
  'manager''s answer. No INSERT/UPDATE policy: both writes are RPCs below.';

create or replace function public.request_complaint_department_change(
  p_membership_id    uuid,
  p_complaint_id     uuid,
  p_to_department_id uuid default null,
  p_reason           text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_complaint record;
  v_id        uuid;
  v_manager   record;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'That is not your membership.' using errcode = 'HB403';
  end if;

  select c.id, c.community_id, c.department_id, c.title
    into v_complaint
    from public.complaints c
   where c.id = p_complaint_id;

  if v_complaint.id is null then
    raise exception 'No such complaint.' using errcode = 'HB404';
  end if;

  -- Nothing to move it out of. An unrouted complaint is the admin's to allot,
  -- and there is no manager whose inbox this request would land in.
  if v_complaint.department_id is null then
    raise exception 'That complaint has not been assigned to a department yet.'
      using errcode = 'HB409';
  end if;

  if not public.can_supervise_department(v_complaint.department_id) then
    raise exception 'You do not work on this department''s complaints.'
      using errcode = 'HB403';
  end if;

  if p_to_department_id is not null
     and not exists (
       select 1 from public.departments d
        where d.id = p_to_department_id
          and d.community_id = v_complaint.community_id
     ) then
    raise exception 'No such department in this community.' using errcode = 'HB404';
  end if;

  if p_to_department_id = v_complaint.department_id then
    raise exception 'That complaint is already with that department.'
      using errcode = 'HB409';
  end if;

  insert into public.complaint_department_requests (
    complaint_id, from_department_id, to_department_id,
    requested_by_membership_id, reason
  )
  values (
    p_complaint_id, v_complaint.department_id, p_to_department_id,
    p_membership_id, nullif(btrim(coalesce(p_reason, '')), '')
  )
  returning id into v_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    p_complaint_id, p_membership_id, 'department_change_requested',
    jsonb_build_object(
      'request_id', v_id,
      'to_department_id', p_to_department_id,
      'reason', nullif(btrim(coalesce(p_reason, '')), '')
    )
  );

  -- The manager of the department that currently holds it -- the one person who
  -- can answer. `_portal_for`'s predicate again, for the same reason.
  for v_manager in
    select m.id
      from public.community_memberships m
     where m.community_id  = v_complaint.community_id
       and m.department_id = v_complaint.department_id
       and m.role::text    = 'manager'
       and m.status        = 'active'
       and m.ended_at is null
  loop
    perform public.notify_member(
      v_manager.id,
      'complaint.department_change_requested',
      jsonb_build_object(
        'title', 'A supervisor says a complaint is not yours',
        'body',  v_complaint.title,
        'url',   '/admin/complaints?complaint=' || p_complaint_id::text,
        'complaint_id', p_complaint_id
      )
    );
  end loop;

  return v_id;
end;
$$;

comment on function public.request_complaint_department_change(
  uuid, uuid, uuid, text) is
  'A supervisor asking their manager to move a complaint elsewhere. The '
  'destination is optional -- "not ours" is worth saying without knowing whose.';

grant execute on function public.request_complaint_department_change(
  uuid, uuid, uuid, text) to authenticated;

create or replace function public.decide_complaint_department_change(
  p_membership_id    uuid,
  p_request_id       uuid,
  p_decision         text,
  p_to_department_id uuid default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_request  record;
  v_decision text := lower(btrim(coalesce(p_decision, '')));
  v_target   uuid;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'That is not your membership.' using errcode = 'HB403';
  end if;

  if v_decision not in ('accept', 'reject') then
    raise exception 'Decision must be accept or reject.' using errcode = 'HB422';
  end if;

  select r.*, c.community_id
    into v_request
    from public.complaint_department_requests r
    join public.complaints c on c.id = r.complaint_id
   where r.id = p_request_id;

  if v_request.id is null then
    raise exception 'No such request.' using errcode = 'HB404';
  end if;

  if v_request.status <> 'pending' then
    raise exception 'That request has already been decided.' using errcode = 'HB409';
  end if;

  -- The manager of the department being asked to give the complaint up. Not the
  -- supervisor who raised it, even though can_supervise_department would admit
  -- them -- the whole point of the request is that somebody else answers it.
  if not public.can_manage_department(v_request.from_department_id) then
    raise exception 'Only this department''s manager may answer that request.'
      using errcode = 'HB403';
  end if;

  update public.complaint_department_requests
     set status                   = case when v_decision = 'accept'
                                         then 'accepted' else 'rejected' end,
         decided_by_membership_id = p_membership_id,
         decided_at               = now(),
         to_department_id         = coalesce(p_to_department_id, to_department_id)
   where id = p_request_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_request.complaint_id, p_membership_id, 'department_change_' || v_decision || 'ed',
    jsonb_build_object('request_id', p_request_id)
  );

  if v_decision = 'accept' then
    v_target := coalesce(p_to_department_id, v_request.to_department_id);

    if v_target is null then
      -- Accepted with nowhere to send it: back to the admin's triage queue,
      -- which is the honest state. "Not ours, and I do not know whose" is a
      -- legitimate answer and this is what it looks like.
      update public.complaints
         set department_id = null, updated_at = now()
       where id = v_request.complaint_id;

      insert into public.complaint_events
        (complaint_id, actor_membership_id, event_type, payload)
      values (
        v_request.complaint_id, p_membership_id, 'department_assigned',
        jsonb_build_object(
          'from_department_id', v_request.from_department_id,
          'to_department_id',   null
        )
      );

      perform public.notify_community_roles(
        v_request.community_id, array['admin'], 'complaint.unassigned',
        jsonb_build_object(
          'title', 'A complaint needs a department',
          'body',  'A manager returned it for reassignment.',
          -- The triage queue, not the complaints screen. This notification says
          -- "nobody owns this", and the screen that answers that is the one
          -- listing everything nobody owns.
          'url',   '/admin/complaint-triage',
          'complaint_id', v_request.complaint_id
        )
      );
    else
      -- assign_complaint_department re-checks that the caller manages the
      -- department the complaint is leaving, which is exactly what was just
      -- established -- so the move, its timeline entry and the receiving
      -- manager's notification all come from the one place that does them.
      perform public.assign_complaint_department(
        p_membership_id, v_request.complaint_id, v_target
      );
    end if;
  end if;

  -- The supervisor who asked, either way. A request that is silently rejected
  -- is a request they will raise again next week.
  perform public.notify_member(
    v_request.requested_by_membership_id,
    'complaint.department_change_decided',
    jsonb_build_object(
      'title', case when v_decision = 'accept'
                    then 'Your department change was accepted'
                    else 'Your department change was declined' end,
      'body',  'The complaint you flagged has been answered.',
      'url',   '/admin/complaints?complaint=' || v_request.complaint_id::text,
      'complaint_id', v_request.complaint_id
    )
  );
end;
$$;

comment on function public.decide_complaint_department_change(
  uuid, uuid, text, uuid) is
  'The manager''s answer. Accepting with no destination returns the complaint '
  'to the admin triage queue, which is what "not ours, and I do not know '
  'whose" honestly means.';

grant execute on function public.decide_complaint_department_change(
  uuid, uuid, text, uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 6. The reads
--
-- Two queues and one pending list, as SECURITY DEFINER functions with the
-- authorization inside, matching the rest of this workstream. A view with
-- `security_invoker` would have to express "manages or supervises this
-- department" as an RLS predicate on `complaints`, and `complaints` is the
-- resident surface's table -- widening its policies to serve a staff screen is
-- how a resident ends up able to read the whole community's complaints.
-- ---------------------------------------------------------------------------

create or replace function public.department_complaints(
  p_department_id uuid,
  p_status        text default null
)
returns table (
  id            uuid,
  title         text,
  description   text,
  category      text,
  status        text,
  priority      text,
  location      text,
  created_at    timestamptz,
  due_at        timestamptz,
  resolved_at   timestamptz,
  raised_by     text,
  unit_code     text,
  open_request_id uuid
)
language plpgsql
stable
security definer
set search_path = public
as $$
begin
  if not public.can_supervise_department(p_department_id) then
    raise exception 'You do not work on this department''s complaints.'
      using errcode = 'HB403';
  end if;

  return query
    select
      c.id,
      c.title,
      c.description,
      c.category,
      c.status::text,
      c.priority,
      c.location,
      c.created_at,
      c.due_at,
      c.resolved_at,
      coalesce(p.full_name, 'A resident'),
      u.unit_code,
      r.id
    from public.complaints c
    left join public.community_memberships m on m.id = c.raised_by_membership_id
    left join public.profiles p              on p.id = m.profile_id
    -- The unit hangs off the membership through a residency, not off the
    -- membership row: `community_memberships` has no `unit_id`, and somebody
    -- can have lived in more than one flat. `ended_at is null` is the current
    -- one, and the unique index `residencies_active_member_unit` guarantees
    -- there is at most one, so this join cannot duplicate a complaint.
    left join public.unit_residencies ur
           on ur.membership_id = m.id and ur.ended_at is null
    left join public.units u                 on u.id = ur.unit_id
    left join public.complaint_department_requests r
           on r.complaint_id = c.id and r.status = 'pending'
   where c.department_id = p_department_id
     and (p_status is null or c.status::text = p_status)
   order by c.created_at desc;
end;
$$;

comment on function public.department_complaints(uuid, text) is
  'One department''s complaints, for its manager and its supervisors. Carries '
  'the id of any open change request so the screen knows not to offer a second.';

grant execute on function public.department_complaints(uuid, text) to authenticated;

create or replace function public.unassigned_complaints(p_community_id uuid)
returns table (
  id          uuid,
  title       text,
  description text,
  category    text,
  status      text,
  priority    text,
  created_at  timestamptz,
  raised_by   text,
  unit_code   text
)
language plpgsql
stable
security definer
set search_path = public
as $$
begin
  if not public.is_community_admin(p_community_id) then
    raise exception 'Only an administrator sees the triage queue.'
      using errcode = 'HB403';
  end if;

  return query
    select
      c.id, c.title, c.description, c.category, c.status::text, c.priority,
      c.created_at,
      coalesce(p.full_name, 'A resident'),
      u.unit_code
    from public.complaints c
    left join public.community_memberships m on m.id = c.raised_by_membership_id
    left join public.profiles p              on p.id = m.profile_id
    left join public.unit_residencies ur
           on ur.membership_id = m.id and ur.ended_at is null
    left join public.units u                 on u.id = ur.unit_id
   where c.community_id  = p_community_id
     and c.department_id is null
     and c.status::text <> 'resolved'
   order by c.created_at;
end;
$$;

comment on function public.unassigned_complaints(uuid) is
  'The admin''s triage queue: complaints no category and no resident pick could '
  'route. Resolved ones are excluded -- a complaint that was answered without '
  'ever being allotted needs nothing.';

grant execute on function public.unassigned_complaints(uuid) to authenticated;

-- Every department in the community, named.
--
-- **Why this exists at all.** `GET /departments` is admin-only, so a manager
-- deciding where to move a complaint, or a supervisor naming where they think it
-- belongs, had no way to learn any department's name or id. Without this the
-- destination control is a box you type a UUID into, which is not a control.
--
-- Deliberately the three columns a picker needs and nothing else. The admin's
-- list carries roster counts, categories, hours and skills; handing all of that
-- to every signed-in member so a dropdown can be drawn would be widening a read
-- to serve a widget.
--
-- Any active member may call it, which is wider than the rest of this file and
-- is the honest level: department names are on notices and on the complaint a
-- resident already sees. The authorization that matters is on the *writes*.
create or replace function public.community_departments(p_community_id uuid)
returns table (id uuid, name text, kind text)
language plpgsql
stable
security definer
set search_path = public
as $$
begin
  if not exists (
    select 1
      from public.community_memberships m
     where m.community_id = p_community_id
       and m.profile_id   = auth.uid()
       and m.status       = 'active'
       and m.ended_at is null
  ) then
    raise exception 'You do not belong to this community.' using errcode = 'HB403';
  end if;

  return query
    select d.id, d.name, d.kind
      from public.departments d
     where d.community_id = p_community_id
       and coalesce(d.status, 'active') = 'active'
     order by lower(d.name);
end;
$$;

comment on function public.community_departments(uuid) is
  'Id, name and kind of every active department, for a picker. Any active '
  'member; the admin list stays admin-only because it carries more.';

grant execute on function public.community_departments(uuid) to authenticated;

create or replace function public.department_change_requests(
  p_department_id uuid
)
returns table (
  id                 uuid,
  complaint_id       uuid,
  complaint_title    text,
  to_department_id   uuid,
  to_department_name text,
  requested_by       text,
  reason             text,
  created_at         timestamptz
)
language plpgsql
stable
security definer
set search_path = public
as $$
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'Only this department''s manager sees its change requests.'
      using errcode = 'HB403';
  end if;

  return query
    select
      r.id, r.complaint_id, c.title, r.to_department_id, d.name,
      coalesce(p.full_name, 'A supervisor'), r.reason, r.created_at
    from public.complaint_department_requests r
    join public.complaints c                  on c.id = r.complaint_id
    left join public.departments d            on d.id = r.to_department_id
    left join public.community_memberships m  on m.id = r.requested_by_membership_id
    left join public.profiles p               on p.id = m.profile_id
   where r.from_department_id = p_department_id
     and r.status = 'pending'
   order by r.created_at;
end;
$$;

comment on function public.department_change_requests(uuid) is
  'Open "this is not ours" requests waiting on this department''s manager.';

grant execute on function public.department_change_requests(uuid) to authenticated;
