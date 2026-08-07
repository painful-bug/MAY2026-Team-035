-- The resident's visitor passes: the fields their form collects, the short
-- security code as a hash, the three decisions they can make, and the settings
-- key that has been sitting unread since 0018.
--
-- docs/design/RESIDENT_BACKEND_DESIGN.md 3.4, 5.4, 8 Q2, 9 step 5.
--
-- WHY THIS FILE IS 0032
--
-- Above 0030, because `decide_visitor_pass` calls `notify_member`, and
-- migrations apply in filename order. Same constraint that made the complaint
-- migration 0031 rather than 0025, and the same failure mode if it is ignored: a
-- plpgsql body is not resolved against the catalogue until it executes, so a
-- lower number would apply cleanly and fail at the first visitor.
--
-- WHAT WAS ALREADY HERE
--
-- More than anywhere else in this project. `visitor_requests` arrived in the
-- baseline with a `visitor_status` enum covering the whole lifecycle, a unique
-- `pass_hash`, `valid_from` / `valid_until`, and check-in/check-out timestamps.
-- That is a scheduled, time-boxed, hashed access credential. USER_STORIES.md
-- notes with some surprise that the schema reached US-3.1 without anyone aiming
-- for it (3.4).
--
-- What it lacks is what the resident's form collects: purpose, guest count, and
-- the short code they read aloud over the phone.
--
-- THE CODE IS A CREDENTIAL AND IS NEVER STORED
--
-- 5.4: store a hash, return the plaintext exactly once, never again. It admits a
-- stranger through a gate, so the rule that already governs `resident_invites`
-- governs it -- that table stores `token_hash` and `code_hash` and nothing
-- reversible.
--
-- Both hashes are computed **in Python and passed in as parameters**. The
-- plaintext never reaches the database at all, so there is no statement log, no
-- `pg_stat_statements` row and no replication stream in which it could appear.
-- That is stronger than generating it here and returning it, and it costs
-- nothing: this file never needs to read a code back.
--
-- The cost, stated plainly: a resident who loses the code cannot recover it and
-- must issue a new pass. That is the correct trade for a gate credential and it
-- is exactly how the invite flow already behaves.
--
-- UNIQUENESS: A DELIBERATE DEVIATION FROM 9
--
-- Section 9's schema sketch says `code_hash text unique`. Global uniqueness is
-- the wrong constraint and it would break in production. The code is six digits
-- because a resident reads it down a phone line; that is 900,000 values, so a
-- project-wide unique index starts colliding at a few hundred live passes
-- (birthday bound, not the naive one) and every collision is a retry loop on a
-- write path. Worse, it would be a cross-tenant collision: one community's pass
-- failing to issue because an unrelated community holds that number.
--
-- A code has to be unambiguous **where and when it is used** -- at one gate,
-- among the passes that could currently open it. So: partial unique index on
-- (community_id, code_hash) over live passes only.
--
-- That is only true if something retires a pass. An index predicate must be
-- IMMUTABLE, so it cannot ask the clock: `live` here means a *status*, and the
-- baseline's `expired` status is written by nothing. Left alone, a pass that
-- lapsed at six o'clock would hold its number for the life of the project and
-- the space would leak rather than recycle -- which would quietly undo the
-- argument above. Section 2's `expire_visitor_passes` is what makes the claim
-- true; it runs before each issue.
--
-- Collisions are still possible and the database refuses them rather than
-- de-duplicating: the plaintext is not here to compare. The caller re-mints
-- (`services/resident_visitor_passes_service.py`), which is the only place a
-- fresh code can come from.
--
-- THE SETTING THAT NOTHING READ
--
-- `community_settings.visitor_code_ttl_minutes` has existed since 0018 under the
-- comment "Reserved by the ERD for a subsystem that does not exist. Nothing
-- reads it." This migration is the reader. The admin's settings screen has been
-- writing that number for four sessions; a control that stores a value nothing
-- consults is worse than a missing control, because it looks like it worked.
--
-- `require_visitor_preapproval` still has no reader, and correctly so: it
-- governs whether the *gate* may admit someone with no pass, and no gate
-- software exists in this repository. That gap is recorded in API.md rather
-- than half-implemented here.

-- ---------------------------------------------------------------------------
-- 1. The columns the resident's form collects
--
-- `purpose` and `purpose_details` are two columns rather than one because the
-- form is a select plus a conditional free-text box ("Other"). Flattening them
-- at write time would make "Delivery" and a typed "Delivery" indistinguishable,
-- and the select is what any future grouping would count.
--
-- `guest_count` defaults to 1 and is checked, not trusted: the slice does
-- `Math.max(1, Number(...) || 1)` in the browser, which is a display default
-- rather than a constraint.
-- ---------------------------------------------------------------------------

alter table public.visitor_requests
  add column if not exists purpose         text,
  add column if not exists purpose_details text,
  add column if not exists guest_count     integer not null default 1,
  add column if not exists code_hash       text,
  add column if not exists decided_at      timestamptz,
  add column if not exists cancelled_at    timestamptz;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'visitor_requests_guest_count_check'
  ) then
    alter table public.visitor_requests
      add constraint visitor_requests_guest_count_check
      check (guest_count between 1 and 50);
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'visitor_requests_validity_check'
  ) then
    -- A window that ends before it starts is not a short pass, it is a pass that
    -- was never valid -- and it would read as "expired" on every screen that
    -- compares the two.
    alter table public.visitor_requests
      add constraint visitor_requests_validity_check
      check (valid_from is null or valid_until is null or valid_until > valid_from);
  end if;
end $$;

-- The resident's list: my passes, newest first.
create index if not exists visitor_requests_requested_by_created_idx
  on public.visitor_requests (requested_by_membership_id, created_at desc);

-- The gate's lookup, and the uniqueness argued for above. `where` makes it a
-- partial index: only a pass that could still open something occupies a number.
create unique index if not exists visitor_requests_live_code_idx
  on public.visitor_requests (community_id, code_hash)
  where code_hash is not null
    and status in ('expected', 'pending_approval', 'approved');

-- ---------------------------------------------------------------------------
-- 2. How long a pass stays valid
--
-- Reads `community_settings`, falling back to the same 120 minutes the column
-- defaults to. `coalesce` on a missing settings row rather than a join that
-- drops the pass: a community that has never opened the settings screen must
-- still be able to issue a visitor pass.
-- ---------------------------------------------------------------------------

create or replace function public.visitor_code_ttl_minutes(p_community_id uuid)
returns integer
language sql
stable
as $$
  select coalesce(
    (select cs.visitor_code_ttl_minutes
       from public.community_settings cs
      where cs.community_id = p_community_id),
    120
  );
$$;

comment on function public.visitor_code_ttl_minutes(uuid) is
  'Minutes a visitor pass stays valid for this community. The first reader of a settings column that has been written since 0018 and consulted by nothing.';

grant execute on function public.visitor_code_ttl_minutes(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 2b. The status nothing ever wrote
--
-- `visitor_status` has carried `expired` since the baseline and no code path in
-- this project has ever set it. Two things depend on it being real:
--
--   * the partial unique index above, whose whole justification is that a dead
--     pass releases its number; and
--   * the resident's list, where a pass that lapsed last Tuesday should not sit
--     in `Expected` forever.
--
-- `now()` cannot appear in an index predicate, so the transition has to be a
-- write. This is the cheapest honest place for it: bounded to one community,
-- driven off the index that already exists, and run at the moment it matters --
-- immediately before a code is issued into that community's live set.
--
-- Not a trigger and not a cron job. A trigger cannot fire on the passage of
-- time, and a scheduled sweep would be a second deployment artifact for a
-- correctness property one statement can hold. The cost is that a pass lapses
-- lazily: between sweeps `is_lapsed` on the view is what tells the truth, which
-- is why that column exists.
-- ---------------------------------------------------------------------------

create or replace function public.expire_visitor_passes(p_community_id uuid)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count integer;
begin
  update public.visitor_requests
     set status     = 'expired',
         updated_at = now()
   where community_id = p_community_id
     and status in ('expected', 'pending_approval', 'approved')
     and valid_until is not null
     and valid_until < now();

  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

comment on function public.expire_visitor_passes(uuid) is
  'Settle this community''s lapsed passes into `expired`, releasing their codes. Run before each issue; nothing else writes that status.';

grant execute on function public.expire_visitor_passes(uuid) to authenticated;
grant execute on function public.expire_visitor_passes(uuid) to service_role;

-- ---------------------------------------------------------------------------
-- 2c. Is the caller this community's gate?
--
-- `0019` introduced `is_community_member` and `is_community_admin` over an
-- argument this file had already broken by the time it reached section 8: "a
-- predicate copied and pasted is correct twenty times and will eventually be
-- wrong once". The `security` clause was written inline in one policy and
-- omitted from the neighbouring one -- which is that failure, arriving in the
-- same migration that quoted the warning.
--
-- Same shape as its two siblings, for the same reasons: SECURITY DEFINER so a
-- policy on `community_memberships` cannot recurse into itself, STABLE so the
-- planner calls it once per query, and a pinned `search_path` because it runs
-- as the owner.
-- ---------------------------------------------------------------------------

create or replace function public.is_community_security(p_community_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.community_memberships m
     where m.community_id = p_community_id
       and m.profile_id = auth.uid()
       and m.role = 'security'
       and m.status = 'active'
       and m.ended_at is null
  );
$$;

comment on function public.is_community_security(uuid) is
  'True when the caller is active security staff for the community. Used by the visitor policies -- the gate sees passes it neither raised nor owns.';

grant execute on function public.is_community_security(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 3. Fan-out by role
--
-- `notify_community_staff` (0031) notifies admins and managers, which is the
-- right audience for a complaint and the wrong one for a gate: security is the
-- role that needs to know a pass was approved, and it is not in that list.
--
-- Rather than write a second loop, the general function is introduced here and
-- 0031's is replaced by a one-line delegation. Two copies of a fan-out loop is
-- how one of them ends up filtering on `status = 'active'` and the other does
-- not -- and the one that forgets is the one that notifies people who left the
-- community.
-- ---------------------------------------------------------------------------

create or replace function public.notify_community_roles(
  p_community_id       uuid,
  p_roles              text[],
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
    raise exception 'notify_community_roles requires a community'
      using errcode = '22004';
  end if;

  for v_row in
    select m.id
      from public.community_memberships m
     where m.community_id = p_community_id
       and m.role::text = any (p_roles)
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

comment on function public.notify_community_roles(uuid, text[], text, jsonb, uuid) is
  'Notify every active member of a community holding one of these roles.';

grant execute on function public.notify_community_roles(uuid, text[], text, jsonb, uuid) to authenticated;
grant execute on function public.notify_community_roles(uuid, text[], text, jsonb, uuid) to service_role;

-- 0031's function, now a named audience over the general one. The name is what
-- carries the meaning -- "the same people the dashboard topic reaches" -- so it
-- stays rather than being replaced at its call sites.
create or replace function public.notify_community_staff(
  p_community_id       uuid,
  p_kind               text,
  p_payload            jsonb default '{}'::jsonb,
  p_exclude_membership uuid default null
)
returns integer
language sql
security definer
set search_path = public
as $$
  select public.notify_community_roles(
    p_community_id, array['admin', 'manager'], p_kind, p_payload,
    p_exclude_membership
  );
$$;

-- ---------------------------------------------------------------------------
-- 4. visitor_pass_overview: the resident's projection
--
-- `security_invoker`, so section 7's policy decides what a caller sees.
--
-- `is_current` is what splits the two tabs the frontend has: a pass still ahead
-- of the resident (`?view=current`) against one that is finished with
-- (`?view=history`). It is computed here rather than as a status list in Python
-- so the split cannot drift from the transitions in section 6.
--
-- **`checked_in` is current**, and it is worth saying why, because the first
-- version of this view left it out. The prototype's own predicate is
-- `['Checked Out', 'Rejected'].includes(status) || date < today`
-- (`Visitors.jsx`), which keeps a guest who is inside the building on the front
-- tab -- correctly: that is the one pass the resident might actually need to
-- look at. Filing them under *History* while they are sitting in the living
-- room is the kind of wrong an expiry rule produces when it is applied to a
-- state that expiry does not describe.
--
-- So the clock only constrains the states where a visitor has **not arrived**.
-- Once they are through the gate, the window has done its job and the status is
-- the whole answer.
--
-- **`code_hash` and `pass_hash` are not selected.** Not because a hash is
-- dangerous to show -- it is not -- but because a column that never leaves the
-- database cannot be leaked by a later `select *`, and neither has any reader on
-- this surface.
-- ---------------------------------------------------------------------------

drop view if exists public.visitor_pass_overview;
create view public.visitor_pass_overview
with (security_invoker = true) as
select
  v.id,
  v.community_id,
  v.requested_by_membership_id,
  v.visitor_name,
  v.visitor_phone_e164,
  v.purpose,
  v.purpose_details,
  v.guest_count,
  v.status,
  v.valid_from,
  v.valid_until,
  v.approved_by_membership_id,
  v.checked_in_at,
  v.checked_out_at,
  v.decided_at,
  v.cancelled_at,
  v.created_at,
  v.updated_at,
  (
    (
      v.status in ('expected', 'pending_approval', 'approved')
      and (v.valid_until is null or v.valid_until >= now())
    )
    or v.status = 'checked_in'
  ) as is_current,
  (
    v.status in ('expected', 'pending_approval', 'approved')
    and v.valid_until is not null
    and v.valid_until < now()
  ) as is_lapsed
from public.visitor_requests v;

comment on view public.visitor_pass_overview is
  'Resident-facing visitor pass projection. Carries neither hash: no reader on this surface has any use for one.';

grant select on public.visitor_pass_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 5. create_visitor_pass
--
-- Both hashes arrive as parameters; see the header. The validity window is the
-- resident's expected arrival plus the community's TTL, so `valid_from` is a
-- time they chose and `valid_until` is a policy they did not.
--
-- The TTL runs from the arrival **or from now, whichever is later**. The form
-- floors the date at today but not the time, so a resident pre-approving at four
-- for a guest they said would come at nine gets a window that closed hours ago:
-- a pass born expired, with no error, that the next sweep would immediately
-- retire. `greatest` means the code always lives for the full TTL from the
-- moment it was minted, which is what a TTL on a credential means.
--
-- Status is `expected`, never `approved`: a pre-approved visitor has not been
-- approved by anyone, they have been announced. `approved` is what a resident's
-- answer to a gate request produces, and collapsing the two would lose the
-- distinction between "the resident arranged this" and "the resident was asked
-- and said yes" -- which is precisely the distinction a gate log needs.
-- ---------------------------------------------------------------------------

create or replace function public.create_visitor_pass(
  p_membership_id   uuid,
  p_visitor_name    text,
  p_purpose         text,
  p_purpose_details text,
  p_guest_count     integer,
  p_expected_at     timestamptz,
  p_pass_hash       text,
  p_code_hash       text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_name         text := nullif(btrim(coalesce(p_visitor_name, '')), '');
  v_purpose      text := nullif(btrim(coalesce(p_purpose, '')), '');
  v_guests       integer := coalesce(p_guest_count, 1);
  v_from         timestamptz := coalesce(p_expected_at, now());
  v_id           uuid;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'A visitor pass may only be created for your own membership.'
      using errcode = '42501';
  end if;

  if v_name is null then
    raise exception 'A visitor pass needs a visitor name.' using errcode = '23514';
  end if;

  if v_purpose is null then
    raise exception 'A visitor pass needs a purpose.' using errcode = '23514';
  end if;

  if p_pass_hash is null or p_code_hash is null then
    raise exception 'A visitor pass needs both of its hashes.'
      using errcode = '22004';
  end if;

  select m.community_id into v_community_id
    from public.community_memberships m
   where m.id = p_membership_id;

  -- Before the code is minted into this community's live set, not after: the
  -- unique index below is what a lapsed pass would collide with, and a number
  -- held by a pass nobody can use is the one collision with no reason to exist.
  perform public.expire_visitor_passes(v_community_id);

  insert into public.visitor_requests (
    community_id, requested_by_membership_id, visitor_name, purpose,
    purpose_details, guest_count, status, pass_hash, code_hash,
    valid_from, valid_until
  )
  values (
    v_community_id,
    p_membership_id,
    v_name,
    v_purpose,
    nullif(btrim(coalesce(p_purpose_details, '')), ''),
    v_guests,
    'expected',
    p_pass_hash,
    p_code_hash,
    v_from,
    greatest(v_from, now()) + make_interval(
      mins => public.visitor_code_ttl_minutes(v_community_id)
    )
  )
  returning id into v_id;

  insert into public.visitor_events (visitor_request_id, actor_membership_id, event_type)
  values (v_id, p_membership_id, 'created');

  -- No notification. The resident announcing their own guest is not news to
  -- anybody yet: security learns about the pass when it is presented, and an
  -- admin does not act on visitors at all. The first notification in this
  -- lifecycle is the gate asking a resident to approve someone -- which is
  -- written by software this repository does not contain (see section 6).

  return v_id;
end;
$$;

comment on function public.create_visitor_pass(uuid, text, text, text, integer, timestamptz, text, text) is
  'Pre-approve a visitor for your own membership. Takes both hashes; the plaintext code never reaches the database.';

grant execute on function public.create_visitor_pass(uuid, text, text, text, integer, timestamptz, text, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 6. decide_visitor_pass
--
-- One function for approve, reject and cancel, because they are one operation
-- with three arguments: the resident is settling a pass, and the invariant that
-- matters -- which states may be left, and which may never be -- is identical
-- for all three. Three functions would be three copies of that invariant.
--
-- **`checked_in` is terminal** (8 Q2, PO, 2026-08-04). Once the guest is through
-- the gate, "cancel" is a physical-world operation and no database write
-- performs it. Letting the pass flip back would produce a record that disagrees
-- with what happened, and the record is the only thing anybody will have later.
-- The refusal is here rather than in the service, for the same reason as 5.2:
-- the invariant belongs next to the data, where every future caller meets it.
--
-- `approve` and `reject` act on `pending_approval` -- a row raised by the gate
-- when someone arrives unannounced. **No endpoint in this repository creates
-- one.** The security app does, and it does not exist yet. That is stated here
-- rather than papered over: these two branches are correct and, today,
-- unreachable from our own API. They are built now because the notification they
-- answer (`visitor.approval_requested`) is US-2.1's recorded pain point, and
-- because a resident's reply arriving before the thing it replies to would be
-- the wrong order to build them in.
-- ---------------------------------------------------------------------------

create or replace function public.decide_visitor_pass(
  p_pass_id  uuid,
  p_decision text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row      public.visitor_requests%rowtype;
  v_decision text := lower(coalesce(btrim(p_decision), ''));
  v_status   public.visitor_status;
  v_actor    uuid;
  -- Spelled out rather than built by appending 'ed'. That trick gives
  -- `approveed`, and it would have given it to both the timeline event type and
  -- the notification kind -- one of which is matched on by a client.
  v_past     text;
begin
  select * into v_row from public.visitor_requests where id = p_pass_id;

  if v_row.id is null then
    raise exception 'Visitor pass not found.' using errcode = 'P0002';
  end if;

  if not public.is_own_membership(v_row.requested_by_membership_id) then
    raise exception 'Only the resident who holds a visitor pass may decide it.'
      using errcode = '42501';
  end if;

  v_actor := v_row.requested_by_membership_id;

  -- The used-pass refusal comes first and has its own code, so a client can tell
  -- "too late, they are already inside" from "that is not a state you can do
  -- this from". The first is a fact about the world; the second is a bug in the
  -- caller.
  if v_row.status in ('checked_in', 'checked_out') then
    raise exception 'This visitor pass has already been used.'
      using errcode = 'HBUSE';
  end if;

  if v_decision = 'cancel' then
    if v_row.status not in ('expected', 'pending_approval', 'approved') then
      raise exception 'This visitor pass can no longer be cancelled.'
        using errcode = '23514';
    end if;
    v_status := 'cancelled';
    v_past   := 'cancelled';
  elsif v_decision in ('approve', 'reject') then
    if v_row.status <> 'pending_approval' then
      raise exception 'Only a pass awaiting your approval can be decided.'
        using errcode = '23514';
    end if;
    v_status := case when v_decision = 'approve' then 'approved' else 'denied' end;
    v_past   := case when v_decision = 'approve' then 'approved' else 'rejected' end;
  else
    raise exception 'Unknown visitor decision: %', p_decision
      using errcode = '22P02';
  end if;

  update public.visitor_requests
     set status                    = v_status,
         approved_by_membership_id = case when v_status = 'approved'
                                          then v_actor
                                          else approved_by_membership_id end,
         decided_at                = case when v_decision in ('approve', 'reject')
                                          then now() else decided_at end,
         cancelled_at              = case when v_status = 'cancelled'
                                          then now() else cancelled_at end,
         updated_at                = now()
   where id = p_pass_id;

  insert into public.visitor_events (visitor_request_id, actor_membership_id, event_type)
  values (p_pass_id, v_actor, v_past);

  -- Security is the audience, not the admins. A gate that is not told a pass was
  -- approved is a gate that turns the visitor away while the resident watches
  -- the app say `Approved` -- and admins are included only because a community
  -- with nobody holding the `security` role would otherwise be told nothing at
  -- all.
  --
  -- The visitor's name travels; the code never does. 10.8's one hard rule.
  perform public.notify_community_roles(
    v_row.community_id,
    array['security', 'admin'],
    'visitor.' || v_past,
    jsonb_build_object(
      'title', case v_decision
                 when 'approve' then 'A visitor was approved'
                 when 'reject'  then 'A visitor was rejected'
                 else 'A visitor pass was cancelled' end,
      'body',  v_row.visitor_name,
      'url',   '/security/visitors?pass=' || p_pass_id::text,
      'pass_id', p_pass_id
    ),
    v_actor
  );
end;
$$;

comment on function public.decide_visitor_pass(uuid, text) is
  'Approve, reject or cancel your own visitor pass. Refuses any transition out of checked_in.';

grant execute on function public.decide_visitor_pass(uuid, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 7. The module catalogue stops saying there is no visitor backend
--
-- `0022` set these to `absent` with the note "No visitor backend. The two
-- visitor settings are stored but nothing reads them." Half of that is now false
-- and half is still exactly true, so they stop sharing a row.
--
-- `visitor-management` becomes `partial`: a resident can do everything they do,
-- and the gate can do nothing. `security-gate-management` stays `absent` -- it
-- is the missing half, not a partially built one, and rounding it up because a
-- neighbouring feature moved is how a status board stops being worth reading.
--
-- THE CODES ARE THE BASELINE'S, WHICH IS NOT WHAT 0022 GUESSED
--
-- `feature_catalog` holds ten hyphenated codes, seeded once in `0001`:
-- `visitor-management`, `security-gate-management`, `complaint-management` and
-- so on. `0022` wrote `('visitors', 'visitor_management', 'security')`, and this
-- file copied that list. Every one of those updates matches zero rows.
--
-- Nothing failed, which is the whole problem: `update ... where code in (...)`
-- reports success on an empty match, so `0022`'s six statements have been
-- silently no-ops since they were written, and every module has been sitting at
-- the column default -- `sort_order = 0`, `backend_status = 'absent'`. The
-- Settings screen would have reported that this backend does not exist. `0022`
-- is corrected in place (it has never been applied); this file uses the real
-- codes.
-- ---------------------------------------------------------------------------

update public.feature_catalog set backend_status = 'partial',
  backend_note = 'Resident visitor passes exist (0032). Nothing serves the gate: no check-in, no code verification, and no way to raise an approval request.'
 where code = 'visitor-management';

update public.feature_catalog set backend_status = 'absent',
  backend_note = 'No gate software. require_visitor_preapproval is stored and still has no reader, because the rule it expresses belongs entirely here.'
 where code = 'security-gate-management';

-- ---------------------------------------------------------------------------
-- 8. Row-level security
--
-- `visitor_requests` and `visitor_events` have had none since the baseline, so
-- today every authenticated user in the project can read every visitor row --
-- names, phone numbers and which flat is expecting whom. Tolerable only while
-- nothing served them; this migration is what stops that being true, so the
-- policy lands in the same file. Fourth migration this rule has produced --
-- 0028, 0030, 0031 and this one.
--
-- Three audiences, and `security` is the one that makes this different from
-- complaints: the gate has to see a pass it never raised and does not own. It
-- gets the community's passes and neither hash, because the view is what it
-- reads and the view carries no hash column.
--
-- **Three on both tables.** The first version of this section spelled the
-- `security` clause out by hand in the pass policy and left it out of the event
-- policy, so a gate could read a pass and not the log of what had been done to
-- it -- and that log is the only record of a check-in. Section 2c's helper is
-- what makes the two say the same thing, which is `0019`'s argument for the
-- other two helpers.
--
-- No insert, update or delete policy. Every write is a SECURITY DEFINER function
-- that does its own authorization -- which is the only way the row, its event
-- and its notification can be guaranteed to happen together.
-- ---------------------------------------------------------------------------

alter table public.visitor_requests enable row level security;
alter table public.visitor_events   enable row level security;

drop policy if exists visitor_requests_read on public.visitor_requests;
create policy visitor_requests_read on public.visitor_requests
  for select to authenticated
  using (
    public.is_own_membership(requested_by_membership_id)
    or public.is_community_admin(community_id)
    or public.is_community_security(community_id)
  );

drop policy if exists visitor_events_read on public.visitor_events;
create policy visitor_events_read on public.visitor_events
  for select to authenticated
  using (exists (
    select 1 from public.visitor_requests v
     where v.id = visitor_request_id
       and (
         public.is_own_membership(v.requested_by_membership_id)
         or public.is_community_admin(v.community_id)
         or public.is_community_security(v.community_id)
       )
  ));
