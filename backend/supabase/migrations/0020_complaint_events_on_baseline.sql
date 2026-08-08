-- ===========================================================================
-- Step 5 rebuilt: complaint edits and their timeline, on the baseline schema.
--
-- This replaces the pre-baseline `0013_complaint_events.sql` (see `README.md`).
--
-- The baseline already has all four tables -- `complaints`, `complaint_events`,
-- `complaint_comments`, `complaint_read_state` -- so unlike departments this is
-- mostly a matter of columns and the two RPCs. `0019` already added
-- `department_id`, `assigned_to_membership_id`, `assignee_label` and `due_at` to
-- `complaints`, because the department views count on them.
--
-- WHY BOTH WRITES ARE RPCs
--
-- Each touches the complaint row AND its append-only timeline. PostgREST has no
-- client-side transaction, so doing it in the repository would let the edit land
-- with no record of who made it -- which is precisely the case the timeline
-- exists to answer.
--
-- WHAT `complaint_events.payload` IS FOR
--
-- The baseline models an event as `(event_type, payload jsonb)`, and their
-- `dashboard_repository.py:68` reads exactly that shape. The legacy schema used
-- typed `note` and `new_status` columns instead, and their line 66 still reads
-- those in its legacy branch. We write the baseline shape and put the same facts
-- inside `payload`, so their non-legacy read gets everything without either side
-- changing.
--
-- HOW A STATUS CHANGE IS RECORDED
--
-- `complaints.status` is the baseline ENUM `public.complaint_status`. It has no
-- 'reopened' member, so reopening stores 'open' -- see the note in
-- `app/domain/vocabularies.py`. The distinction is not lost: reopening writes a
-- `status_changed` event whose payload carries both the old and the new value,
-- so "how many times was this reopened" is answerable by counting events where
-- `from` was a terminal status. A column could not have answered that anyway,
-- since it only ever holds the latest value.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. The columns the complaint editor writes
--
-- `progress_percent` is a real column rather than a derived value because the
-- edit form sets it directly (a slider), and it does not follow from status:
-- an in-progress complaint may sit at 10% or 90%.
-- ---------------------------------------------------------------------------
alter table public.complaints
  add column if not exists progress_percent integer not null default 0;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'complaints_progress_percent_check'
  ) then
    alter table public.complaints
      add constraint complaints_progress_percent_check
      check (progress_percent between 0 and 100);
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- 2. Timeline and comment columns
--
-- `actor_label` and `author_label` sit beside the membership references for the
-- same reason `complaints.assignee_label` does: a department roster is a list of
-- typed names, and an action taken by "Ravi Kumar" who has no account has
-- nothing to point a foreign key at. The label is a snapshot of the display name
-- AT THE TIME OF THE EVENT, which is also what a timeline should show -- renaming
-- someone should not rewrite what the history says they were called.
--
-- `author_membership_id` becomes nullable for that same reason. The baseline
-- declares it `not null` because it assumes every comment has an account behind
-- it; an admin acting through the dashboard on behalf of an unlinked staff
-- member does not.
-- ---------------------------------------------------------------------------
alter table public.complaint_events
  add column if not exists actor_label text;

-- Some hosted projects recorded an older 0001 baseline that did not include
-- this table.  Create the baseline shape before extending it below.
create table if not exists public.complaint_comments (
  id uuid primary key default gen_random_uuid(),
  complaint_id uuid not null references public.complaints(id) on delete cascade,
  author_membership_id uuid not null references public.community_memberships(id),
  body text not null,
  created_at timestamptz not null default now()
);

alter table public.complaint_comments
  add column if not exists author_label text,
  add column if not exists visibility   text not null default 'public';

alter table public.complaint_comments alter column author_membership_id drop not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'complaint_comments_visibility_check'
  ) then
    alter table public.complaint_comments
      add constraint complaint_comments_visibility_check
      check (visibility in ('public', 'internal'));
  end if;

  -- Same identity rule as the staff roster: a comment must be attributable to
  -- someone, whether by reference or by name.
  if not exists (
    select 1 from pg_constraint where conname = 'complaint_comments_identity_check'
  ) then
    alter table public.complaint_comments
      add constraint complaint_comments_identity_check
      check (author_membership_id is not null
             or nullif(btrim(coalesce(author_label, '')), '') is not null);
  end if;
end $$;

create index if not exists complaint_events_complaint_idx
  on public.complaint_events (complaint_id, created_at desc);

create index if not exists complaint_comments_complaint_idx
  on public.complaint_comments (complaint_id, created_at desc);

-- ---------------------------------------------------------------------------
-- 3. update_complaint
--
-- Applies a partial edit and writes one timeline event per FIELD THAT ACTUALLY
-- CHANGED, not one per field submitted. The edit form posts its whole state, so
-- recording every submitted field would fill the timeline with "status: open ->
-- open" on every save.
--
-- A null parameter means "not supplied". That is unambiguous here in a way it is
-- not for the department RPCs, because none of these columns is meaningfully
-- settable to null by the editor: clearing an assignee is done by sending an
-- empty string, which `nullif` below turns into a real null.
--
-- `aggregate_version` is incremented on every write. The baseline declares it
-- and nothing has been maintaining it; a client that wants optimistic
-- concurrency now has a value that actually moves.
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

  -- Cast once, so an invalid status fails here with a clear message rather than
  -- inside the UPDATE with a bare 22P02.
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

  -- One event per field that actually moved.
  if v_new_status is not null and v_new_status is distinct from v_old.status then
    insert into public.complaint_events
      (complaint_id, actor_membership_id, actor_label, event_type, payload)
    values (
      p_complaint_id, p_actor_membership, p_actor_label, 'status_changed',
      jsonb_build_object('from', v_old.status::text, 'to', v_new_status::text)
    );
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

  -- A note is always recorded when supplied: it is the admin's own words, and
  -- unlike the fields above it has no previous value to be unchanged from.
  if nullif(btrim(coalesce(p_update_note, '')), '') is not null then
    insert into public.complaint_events
      (complaint_id, actor_membership_id, actor_label, event_type, payload)
    values (
      p_complaint_id, p_actor_membership, p_actor_label, 'note_added',
      jsonb_build_object('note', btrim(p_update_note))
    );
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- 4. add_complaint_comment
--
-- Returns the new comment's id so the caller can echo it without a second read.
--
-- An internal comment is still written to the timeline, because the timeline is
-- admin-facing. What `visibility` controls is whether the RESIDENT sees it, and
-- that is enforced by the RLS policy below rather than by omitting the row.
-- ---------------------------------------------------------------------------
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
  v_visibility   text := coalesce(nullif(btrim(coalesce(p_visibility, '')), ''), 'public');
  v_id           uuid;
begin
  select community_id into v_community_id
    from public.complaints where id = p_complaint_id;

  if v_community_id is null then
    raise exception 'Complaint not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_member(v_community_id) then
    raise exception 'Only a member of this community may comment.'
      using errcode = '42501';
  end if;

  -- Only staff may leave an internal note; a resident marking their own comment
  -- internal would hide it from the people meant to act on it.
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

  return v_id;
end $$;

grant execute on function public.update_complaint(uuid, text, text, uuid, integer, timestamptz, text, uuid, text) to authenticated;
grant execute on function public.add_complaint_comment(uuid, text, text, uuid, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 5. Row-level security
--
-- The baseline leaves these three tables unguarded. Enabling RLS here is safe
-- for the service-role client (which bypasses it) and necessary for the
-- user-scoped one.
--
-- The comment read policy is the one that carries weight: an internal comment is
-- visible to admins only, which is the whole point of the flag.
-- ---------------------------------------------------------------------------
alter table public.complaint_events   enable row level security;
alter table public.complaint_comments enable row level security;

drop policy if exists complaint_events_read on public.complaint_events;
create policy complaint_events_read on public.complaint_events
  for select to authenticated
  using (exists (
    select 1 from public.complaints c
     where c.id = complaint_id
       and public.is_community_member(c.community_id)
  ));

drop policy if exists complaint_comments_read on public.complaint_comments;
create policy complaint_comments_read on public.complaint_comments
  for select to authenticated
  using (exists (
    select 1 from public.complaints c
     where c.id = complaint_id
       and public.is_community_member(c.community_id)
       and (visibility = 'public' or public.is_community_admin(c.community_id))
  ));

-- Writes go through the two SECURITY DEFINER RPCs above, which do their own
-- authorization. No direct-insert policy is granted, so the only way to add a
-- timeline entry is through the function that also updates the complaint.

-- ---------------------------------------------------------------------------
-- 6. SSE outbox
-- ---------------------------------------------------------------------------
drop trigger if exists complaints_sse on public.complaints;
create trigger complaints_sse
  after insert or update or delete on public.complaints
  for each row execute function public.emit_dashboard_sse_event();

drop trigger if exists complaint_comments_sse on public.complaint_comments;
create trigger complaint_comments_sse
  after insert or update or delete on public.complaint_comments
  for each row execute function public.emit_dashboard_sse_event();
