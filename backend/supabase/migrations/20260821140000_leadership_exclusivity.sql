-- ---------------------------------------------------------------------------
-- 20260821140000_leadership_exclusivity.sql
--
-- Three product rulings, 2026-08-21, enforced where they cannot be routed
-- around.
--
--   RULING 1  Leadership is invite-only and never from the marketplace pool.
--             A supervisor or a manager is NEVER a freelancer and is never
--             picked from servicemen. A profile that holds a
--             `service_providers` row must never hold a leadership roster row,
--             and a profile holding an active leadership membership must be
--             refused marketplace registration.
--
--   RULING 2  Leadership is exclusive to one community. At most ONE active
--             leadership membership per person, across every community, at any
--             time. Technicians may still serve several communities -- that is
--             untouched. Being invited to a *different* community after the
--             previous engagement has fully ended is legitimate and keeps
--             working.
--
--   RULING 3  Removal severs access completely. Once a supervisor or manager is
--             removed from a community and later invited to another, they must
--             not be able to see ANYTHING from the old one.
--
-- WHY THIS IS ONE FILE
--
-- Rulings 1 and 2 are the same sentence said twice -- *what may this account
-- hold* -- and ruling 3 is that sentence's consequence: if leadership can only
-- be held once, a second posting can only be reached by ending the first, and a
-- person who has ended one must stop reading it. Splitting them would put the
-- invariant in one migration and the reason it is survivable in another.
--
-- WHERE THE CHECKS GO, AND WHY MOSTLY IN TRIGGERS
--
-- `20260812113000` argued this and the argument has not changed: there are five
-- writers of `community_memberships` and four of `staff_assignments`, and a
-- guard repeated nine times is a guard that will be eight places the tenth
-- writer does not know about. `staff_assignments` additionally carries
-- `staff_assignments_admin_write` (`20260812200000` 1), a `for all` policy that
-- lets any community admin INSERT a roster row straight through PostgREST with
-- no RPC in the way at all. Nothing but a trigger stands in front of that.
--
-- So the invariants are triggers, and the RPCs additionally refuse early --
-- not for safety but for the sentence. A trigger fires from inside
-- `upsert_service_provider`, three frames below the caller, and the message a
-- registration form renders should say what to do about it.
--
-- ERRCODES
--
-- Two new ones, in the `HB` + three-free-characters shape `pg_errors.py`
-- describes and `HBSEP`/`HBUSE`/`HBLOC` already use. Both are 409s, like
-- `HB409`, because both answer *this account is the wrong kind of account*.
-- They are separate codes because a client that must tell "you are a
-- marketplace professional" apart from "you already lead somewhere else"
-- cannot do it from an HTTP status, and reading the message text to find out
-- is the string matching custom SQLSTATEs exist to avoid.
--
--   HBMKT  ruling 1 -- leadership and the marketplace are different populations
--   HBLED  ruling 2 -- leadership is held in one community at a time
--
-- WHAT THIS FILE DOES NOT DO
--
-- It repairs nothing. `20260812113000` 1b made the case and it holds here too:
-- which identity an account already holding both should keep is the account
-- holder's decision, not a migration's. Section 8 counts them and raises a
-- `notice` so whoever applies this sees it while they still have the context.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. Two predicates, written once
--
-- Both are `security definer` for the reason every predicate in this schema is:
-- they are called from RLS policies and from triggers on the very tables they
-- read, and a caller-visible read would answer the same question a second way
-- through RLS.
--
-- `leadership_profile` takes a roster row rather than a profile because both
-- callers have the row and only one of them has the profile: the trigger sees
-- `new`, and `new.membership_id` may be null (a typed-in roster name has no
-- account at all -- `staff_assignments_identity_check`, `0019` 258).
-- ---------------------------------------------------------------------------

create or replace function public.staff_assignment_profile(
  p_membership_id       uuid,
  p_service_provider_id uuid
)
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  -- The membership first: it is the identity leadership arrives with, and the
  -- provider column is null on every leadership row by construction. `coalesce`
  -- rather than a union so a row carrying both resolves to one answer.
  select coalesce(
    (select m.profile_id from public.community_memberships m
      where m.id = p_membership_id),
    (select p.profile_id from public.service_providers p
      where p.id = p_service_provider_id)
  );
$$;

comment on function public.staff_assignment_profile(uuid, uuid) is
  'Which person a roster row is, from its two nullable identity columns. Null '
  'for a typed-in name, which is an entry on a list and not an account.';

revoke all on function public.staff_assignment_profile(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.staff_assignment_profile(uuid, uuid)
  to authenticated;

-- Where this person currently leads, or null.
--
-- "Currently" is spelled with all three conditions on purpose, and they are the
-- three `can_supervise_department` (`0036` 435) already uses: the roster row is
-- active, the membership behind it is active, and the membership has not
-- ended. Any predicate here that disagreed with that one would create a person
-- who leads for the purposes of this guard and does not for the purposes of
-- authorisation, or the reverse -- and one of those two is a hole.
create or replace function public.active_leadership_community(p_profile_id uuid)
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select sa.community_id
    from public.staff_assignments sa
    join public.community_memberships m on m.id = sa.membership_id
   where m.profile_id = p_profile_id
     and sa.status = 'active'
     and sa.rank in ('manager', 'supervisor')
     and m.status = 'active'
     and m.ended_at is null
   order by sa.started_at nulls last
   limit 1;
$$;

comment on function public.active_leadership_community(uuid) is
  'The one community this person currently manages or supervises, or null. '
  'Ruling 2 (2026-08-21) says there is at most one; this is the predicate the '
  'trigger, the invite RPC and the claim all ask.';

revoke all on function public.active_leadership_community(uuid)
  from public, anon, authenticated;
grant execute on function public.active_leadership_community(uuid) to authenticated;


-- ---------------------------------------------------------------------------
-- 2. The roster invariant (rulings 1 and 2)
--
-- `before insert or update` on `staff_assignments`, and it judges only rows
-- that are *becoming* live leadership. Everything else returns immediately,
-- including `remove_department_member`'s own update -- which sets
-- `rank = 'member'` and `status = 'inactive'` in one statement (`0043` 1083),
-- so the row it writes is not leadership and is not active and fails the first
-- test twice over.
--
-- THE `id <> new.id` CLAUSE
--
-- Column defaults are evaluated before a `before insert` trigger fires, so
-- `new.id` is already the uuid the row will have; without excluding it, an
-- UPDATE of an existing leadership row -- a job title correction, a shift
-- change -- would find itself and refuse. The `is null` arm is defensive
-- against a future path that supplies the id later.
-- ---------------------------------------------------------------------------

create or replace function public.enforce_leadership_exclusivity()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_profile uuid;
begin
  if new.rank not in ('manager', 'supervisor') or new.status <> 'active' then
    return new;
  end if;

  v_profile := public.staff_assignment_profile(
    new.membership_id, new.service_provider_id);

  -- A typed-in name on a roster. There is no account, so there is no identity
  -- to be exclusive about and nothing to check.
  if v_profile is null then
    return new;
  end if;

  -- Ruling 1. Both halves of "is this a marketplace professional" are asked:
  -- the column on the row being written, and the account behind it. The first
  -- catches `decide_service_application` hiring a candidate at supervisor rank
  -- -- which `20260811162409` 786 permits, `p_rank` being caller-supplied on
  -- the `applied` branch -- and the second catches a leadership row minted for
  -- an account that registered in the marketplace separately.
  --
  -- No `status` filter on `service_providers`, matching
  -- `register_service_provider` and `20260812113000`: a paused or suspended
  -- provider still carries a professional identity.
  if new.service_provider_id is not null
     or exists (select 1 from public.service_providers
                 where profile_id = v_profile) then
    raise exception
      'A manager or supervisor is never hired out of the marketplace. This account is registered as a service professional, so it cannot also hold a leadership post; invite somebody who is not a registered provider, or hire this person at technician rank.'
      using errcode = 'HBMKT';
  end if;

  -- Ruling 2. Any community, including this one under a second department.
  if exists (
    select 1
      from public.staff_assignments sa
      join public.community_memberships m on m.id = sa.membership_id
     where m.profile_id = v_profile
       and (new.id is null or sa.id <> new.id)
       and sa.status = 'active'
       and sa.rank in ('manager', 'supervisor')
       and m.status = 'active'
       and m.ended_at is null
  ) then
    raise exception
      'This person already manages or supervises a community. Leadership is held in one community at a time -- end the existing posting before starting another.'
      using errcode = 'HBLED';
  end if;

  return new;
end;
$$;

comment on function public.enforce_leadership_exclusivity() is
  'Rulings 1 and 2 of 2026-08-21 inside the database: a registered service '
  'provider may never hold a manager or supervisor roster row (HBMKT), and '
  'nobody holds two active ones at once (HBLED). A trigger rather than nine '
  'copies in nine writers -- and the only thing standing in front of '
  'staff_assignments_admin_write, which is a for-all policy with no RPC in it.';

drop trigger if exists staff_assignments_leadership_exclusivity
  on public.staff_assignments;
create trigger staff_assignments_leadership_exclusivity
  before insert or update of rank, status, membership_id, service_provider_id
  on public.staff_assignments
  for each row execute function public.enforce_leadership_exclusivity();

revoke all on function public.enforce_leadership_exclusivity()
  from public, anon, authenticated;


-- ---------------------------------------------------------------------------
-- 3. The same rule from the marketplace side (ruling 1)
--
-- `register_service_provider` refuses below, but registration is not the only
-- writer of `service_providers`: `upsert_service_provider` is granted to
-- `authenticated` in its own right and `PATCH /service-providers/me` reaches
-- it. So the invariant is a trigger on the table and the RPC's refusal is the
-- readable sentence in front of it -- the same division section 2's header
-- describes.
--
-- `before insert` plus `update of profile_id`: an existing provider row cannot
-- belong to a leader, because section 2 refuses the leadership row, so the only
-- ways in are a new row and a row changing hands.
-- ---------------------------------------------------------------------------

create or replace function public.enforce_provider_not_leadership()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.profile_id is not null
     and public.active_leadership_community(new.profile_id) is not null then
    raise exception
      'You manage or supervise a community, and leadership is not part of the marketplace. A manager or supervisor is placed by an administrator, never matched by distance and trade, so there is no professional profile for you to register.'
      using errcode = 'HBMKT';
  end if;
  return new;
end;
$$;

comment on function public.enforce_provider_not_leadership() is
  'The marketplace half of ruling 1: an account that currently leads a '
  'community may not acquire a service_providers row. Mirrors '
  'enforce_leadership_exclusivity, which closes the same door from the roster '
  'side.';

drop trigger if exists service_providers_not_leadership
  on public.service_providers;
create trigger service_providers_not_leadership
  before insert or update of profile_id
  on public.service_providers
  for each row execute function public.enforce_provider_not_leadership();

revoke all on function public.enforce_provider_not_leadership()
  from public, anon, authenticated;


-- ---------------------------------------------------------------------------
-- 4. Registration refuses out loud
--
-- `register_service_provider` from `20260821113000` 3, copied whole so that the
-- starting point is provably the text that file installs, with every difference
-- marked `-- CHANGED` in place. `20260812113000` set that convention and the
-- reason still applies: a partial edit to a function body that exists in
-- another file is a diff nobody can review.
--
-- `create or replace` rather than `drop`+`create`: the signature is unchanged,
-- so the grant and the `revoke` survive. They are reissued anyway, for the same
-- reason `20260812113000` reissues its own -- this is the file a reader finds
-- first if they ask who may call it.
-- ---------------------------------------------------------------------------

create or replace function public.register_service_provider(
  p_display_name text,
  p_headline text,
  p_phone_e164 text,
  p_latitude numeric,
  p_longitude numeric,
  p_service_radius_km numeric,
  p_skill_ids uuid[],
  p_location_label text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_provider uuid;
begin
  if auth.uid() is null then
    raise exception 'Sign in required.' using errcode = '42501';
  end if;
  if p_display_name is null or length(btrim(p_display_name)) not between 2 and 120 then
    raise exception 'A name between 2 and 120 characters is required.' using errcode = '22004';
  end if;
  if p_latitude is null or p_longitude is null then
    raise exception 'Your location is required.' using errcode = 'HBLOC';
  end if;
  if p_latitude not between -90 and 90 or p_longitude not between -180 and 180 then
    raise exception 'Your location is invalid.' using errcode = 'HBLOC';
  end if;
  if coalesce(p_service_radius_km, 15) not between 1 and 500 then
    raise exception 'Service radius must be between 1 and 500 kilometres.' using errcode = '22004';
  end if;

  -- CHANGED: ruling 1, refused here rather than three frames down inside
  -- `upsert_service_provider`, so the form has a sentence to render. Placed
  -- before the separate-account check below because it is the more specific
  -- answer: a supervisor holds a `worker` membership, which that check
  -- deliberately permits, so without this they would fall through it and be
  -- stopped by the trigger with a message written for a different reader.
  if public.active_leadership_community(auth.uid()) is not null then
    raise exception
      'You manage or supervise a community, and leadership is not part of the marketplace. A manager or supervisor is placed by an administrator, never matched by distance and trade, so there is no professional profile for you to register.'
      using errcode = 'HBMKT';
  end if;

  if not exists (
    select 1 from public.service_providers where profile_id = auth.uid()
  ) and exists (
    select 1
      from public.community_memberships
     where profile_id = auth.uid()
       and role not in ('worker', 'security')
       and status = 'active'
       and ended_at is null
  ) then
    raise exception 'Use a separate account for your professional profile.' using errcode = 'HB409';
  end if;

  v_provider := public.upsert_service_provider(
    btrim(p_display_name), p_headline, null, p_phone_e164,
    p_latitude, p_longitude, coalesce(p_service_radius_km, 15),
    p_location_label
  );
  perform public.set_service_provider_skills(p_skill_ids);
  return v_provider;
end;
$$;

comment on function public.register_service_provider(
  text, text, text, numeric, numeric, numeric, uuid[], text) is
  'Atomically creates or repairs the signed-in professional profile and full '
  'active skill set. Refuses existing non-professional members on first '
  'registration, and refuses anyone who currently manages or supervises a '
  'community (HBMKT, ruling 1 of 2026-08-21). The location label is optional; '
  'the coordinates are not.';

revoke all on function public.register_service_provider(
  text, text, text, numeric, numeric, numeric, uuid[], text) from public, anon;
grant execute on function public.register_service_provider(
  text, text, text, numeric, numeric, numeric, uuid[], text) to authenticated;


-- ---------------------------------------------------------------------------
-- 5. The invitation refuses early, and the claim refuses survivably
--
-- These are the two halves of one entry point and they cannot be guarded the
-- same way, because they run in incompatible places.
--
-- INVITE TIME is an admin pressing a button. It has a screen, an error toast
-- and a person who can act on the answer, so it refuses loudly. What it can
-- check is bounded: an address with no profile behind it yet is the ordinary
-- case for leadership -- the whole design is that the person has never signed
-- in -- so a refusal here is possible only for an address that already names
-- somebody.
--
-- CLAIM TIME runs inside `resolve_session`, on a service client, with nobody
-- watching, on every membership-less session read. `_claim_staff_invitations`
-- (`auth_service.py` 322) swallows every exception it raises, deliberately:
-- claiming is an enhancement to a session that is already valid. So an
-- exception here would not refuse the invitation, it would abandon the whole
-- claim -- silently, including any *legitimate* invitation later in the loop --
-- and the person would be told nothing on a screen that looks fine.
--
-- THE CLAIM-TIME DESIGN, STATED PLAINLY
--
-- The offending invitation is SKIPPED and MARKED, never claimed and never
-- failed:
--
--   * the loop `continue`s, exactly as it already does for somebody who is
--     already a member of that community (`20260812090200` 575-583);
--   * `status` stays `pending`, so the admin's existing verbs still work --
--     `update_staff_invitation` can correct the address and
--     `revoke_staff_invitation` can withdraw it. A fourth status would have
--     been a terminal state for a situation that is not terminal: the invitee
--     may leave their other community tomorrow;
--   * `blocked_reason` and `blocked_at` record what happened, so the pending
--     list stops reading as "still waiting for them to sign in" -- which would
--     be a lie, because they have signed in and were turned away;
--   * the department is notified once, on the transition into blocked, so the
--     signal does not depend on somebody opening the right tab. Once, not on
--     every session read: `blocked_at is null` is the edge.
--
-- The session read survives untouched. Every other pending invitation for that
-- email is still considered, and `claim_staff_invitations` still returns
-- normally.
-- ---------------------------------------------------------------------------

alter table public.staff_invitations
  add column if not exists blocked_reason text,
  add column if not exists blocked_at     timestamptz;

comment on column public.staff_invitations.blocked_reason is
  'Why the invitee signed in and was not admitted: they are a registered '
  'marketplace provider, or they already lead another community. Null on every '
  'ordinary invitation. The row stays pending -- the situation is not terminal '
  'and the admin''s correct and withdraw verbs both still apply.';

comment on column public.staff_invitations.blocked_at is
  'When blocked_reason was first written. The edge the one-off notification '
  'fires on, so a claim retried on every session read does not re-notify.';

-- `department_staff_invitations` from `20260812090200` 2 with two columns
-- added. `create or replace` cannot change a `returns table` signature, so the
-- function is dropped first; the grant is reissued below because dropping takes
-- it with the function.
drop function if exists public.department_staff_invitations(uuid, text);

create function public.department_staff_invitations(
  p_department_id uuid,
  p_status        text default null
)
returns table (
  id            uuid,
  department_id uuid,
  invitee_email text,
  invitee_name  text,
  invitee_phone_e164 varchar,
  rank          text,
  job_title     text,
  status        text,
  claimed_at    timestamptz,
  created_at    timestamptz,
  -- CHANGED: the two new ones.
  blocked_reason text,
  blocked_at     timestamptz
)
language plpgsql
stable
security definer
set search_path = public
as $$
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  return query
    select
      s.id, s.department_id, s.invitee_email::text, s.invitee_name,
      s.invitee_phone_e164, s.rank, s.job_title, s.status, s.claimed_at,
      s.created_at, s.blocked_reason, s.blocked_at
      from public.staff_invitations s
     where s.department_id = p_department_id
       and (p_status is null or s.status = p_status)
     order by s.created_at desc;
end;
$$;

comment on function public.department_staff_invitations(uuid, text) is
  'Leadership invited into this department, claimed or not. Admins and the '
  'department''s manager only. Carries blocked_reason when the invitee signed '
  'in and the exclusivity rules turned them away.';

grant execute on function public.department_staff_invitations(uuid, text)
  to authenticated;

-- `invite_staff_member` from `20260812090200` 3, copied whole with the new
-- refusals marked `-- CHANGED`.
create or replace function public.invite_staff_member(
  p_department_id uuid,
  p_email         text,
  p_name          text,
  p_rank          text,
  p_phone         text default null,
  p_job_title     text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email      citext := lower(btrim(coalesce(p_email, '')))::citext;
  v_name       text   := btrim(coalesce(p_name, ''));
  v_rank       text   := lower(btrim(coalesce(p_rank, '')));
  v_department record;
  v_actor      uuid;
  v_id         uuid;
  v_invitee    uuid;  -- CHANGED
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  if v_email = '' or position('@' in v_email::text) = 0 then
    raise exception 'A valid email address is required.' using errcode = 'HB422';
  end if;

  if v_name = '' then
    raise exception 'A name is required.' using errcode = 'HB422';
  end if;

  if v_rank not in ('manager', 'supervisor') then
    raise exception 'Rank must be manager or supervisor.' using errcode = 'HB422';
  end if;

  select d.id, d.community_id, d.kind into v_department
    from public.departments d
   where d.id = p_department_id;

  select m.id into v_actor
    from public.community_memberships m
   where m.community_id = v_department.community_id
     and m.profile_id = auth.uid()
     and m.status = 'active'
     and m.ended_at is null
   limit 1;

  if exists (
    select 1
      from public.community_memberships m
      join public.profiles p on p.id = m.profile_id
     where m.community_id = v_department.community_id
       and p.display_email = v_email
       and m.status = 'active'
       and m.ended_at is null
  ) then
    raise exception 'That person already belongs to this community.'
      using errcode = 'HB409';
  end if;

  -- CHANGED: rulings 1 and 2, refused now rather than at the claim.
  --
  -- **An address with no profile is not an error and is not checked.** That is
  -- the ordinary case here -- leadership has no registration flow, so the
  -- invitee usually has never signed in -- and it is why the claim keeps its
  -- own copy of both rules rather than trusting this one. The two checks are
  -- deliberately duplicated, once where there is a screen and once where there
  -- is authority, which is `20260812090200`'s own reason for re-checking
  -- collisions in `update_staff_invitation`.
  --
  -- `display_email` is citext, so the comparison is case-insensitive without a
  -- `lower()` that would defeat the index, and it is the column
  -- `upsert_profile` writes the GoTrue identity's email into -- the same value
  -- the claim matches on.
  select p.id into v_invitee
    from public.profiles p
   where p.display_email = v_email
   limit 1;

  if v_invitee is not null then
    if exists (select 1 from public.service_providers
                where profile_id = v_invitee) then
      raise exception
        'That address belongs to a registered service professional. A manager or supervisor is never hired out of the marketplace -- invite somebody who is not a registered provider.'
        using errcode = 'HBMKT';
    end if;

    if public.active_leadership_community(v_invitee) is not null then
      raise exception
        'That person already manages or supervises another community. Leadership is held in one community at a time, so they would have to leave that posting before taking this one.'
        using errcode = 'HBLED';
    end if;
  end if;

  insert into public.staff_invitations (
    community_id, department_id, invitee_email, invitee_name,
    invitee_phone_e164, rank, job_title, created_by_membership_id
  )
  values (
    v_department.community_id, p_department_id, v_email, v_name,
    nullif(btrim(coalesce(p_phone, '')), ''), v_rank,
    nullif(btrim(coalesce(p_job_title, '')), ''), v_actor
  )
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.invite_staff_member(
  uuid, text, text, text, text, text) is
  'Create a manager or supervisor who will be admitted by email on first '
  'sign-in. Admins and the department''s manager -- which is what lets a '
  'manager create a supervisor. Refuses an address that already names a '
  'registered provider (HBMKT) or somebody who already leads elsewhere '
  '(HBLED); an address with no account yet can only be checked at claim time.';

grant execute on function public.invite_staff_member(
  uuid, text, text, text, text, text) to authenticated;

-- `update_staff_invitation` from `20260812090200` 3. The email may change, so
-- the two new refusals are re-asked against the new address for exactly the
-- reason the two old ones are.
create or replace function public.update_staff_invitation(
  p_invitation_id uuid,
  p_email         text default null,
  p_name          text default null,
  p_rank          text default null,
  p_phone         text default null,
  p_job_title     text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row     public.staff_invitations%rowtype;
  v_email   citext;
  v_name    text;
  v_rank    text;
  v_invitee uuid;  -- CHANGED
begin
  select * into v_row
    from public.staff_invitations
   where id = p_invitation_id;

  if v_row.id is null then
    raise exception 'No such invitation.' using errcode = 'HB404';
  end if;

  if not public.can_manage_department(v_row.department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  if v_row.status = 'claimed' then
    raise exception 'That invitation has already been claimed.'
      using errcode = 'HB409';
  end if;

  if v_row.status <> 'pending' then
    raise exception 'That invitation has been withdrawn.' using errcode = 'HB409';
  end if;

  v_email := coalesce(lower(btrim(p_email))::citext, v_row.invitee_email);
  v_name  := coalesce(btrim(p_name), v_row.invitee_name);
  v_rank  := coalesce(lower(btrim(p_rank)), v_row.rank);

  if v_email::text = '' or position('@' in v_email::text) = 0 then
    raise exception 'A valid email address is required.' using errcode = 'HB422';
  end if;

  if v_name = '' then
    raise exception 'A name is required.' using errcode = 'HB422';
  end if;

  if v_rank not in ('manager', 'supervisor') then
    raise exception 'Rank must be manager or supervisor.' using errcode = 'HB422';
  end if;

  if exists (
    select 1
      from public.community_memberships m
      join public.profiles p on p.id = m.profile_id
     where m.community_id = v_row.community_id
       and p.display_email = v_email
       and m.status = 'active'
       and m.ended_at is null
  ) then
    raise exception 'That person already belongs to this community.'
      using errcode = 'HB409';
  end if;

  if exists (
    select 1
      from public.staff_invitations s
     where s.community_id  = v_row.community_id
       and s.invitee_email = v_email
       and s.status        = 'pending'
       and s.id           <> p_invitation_id
  ) then
    raise exception 'Somebody has already been invited at that address.'
      using errcode = 'HB409';
  end if;

  -- CHANGED: the same two rulings `invite_staff_member` now refuses. Correcting
  -- an address onto a registered provider must fail the same way typing it in
  -- the first place does, or the correction verb is a way around the guard.
  select p.id into v_invitee
    from public.profiles p
   where p.display_email = v_email
   limit 1;

  if v_invitee is not null then
    if exists (select 1 from public.service_providers
                where profile_id = v_invitee) then
      raise exception
        'That address belongs to a registered service professional. A manager or supervisor is never hired out of the marketplace -- invite somebody who is not a registered provider.'
        using errcode = 'HBMKT';
    end if;

    if public.active_leadership_community(v_invitee) is not null then
      raise exception
        'That person already manages or supervises another community. Leadership is held in one community at a time, so they would have to leave that posting before taking this one.'
        using errcode = 'HBLED';
    end if;
  end if;

  update public.staff_invitations
     set invitee_email      = v_email,
         invitee_name       = v_name,
         rank               = v_rank,
         invitee_phone_e164 = case
           when p_phone is null then invitee_phone_e164
           else nullif(btrim(p_phone), '')
         end,
         job_title          = case
           when p_job_title is null then job_title
           else nullif(btrim(p_job_title), '')
         end,
         -- CHANGED: a corrected invitation is a fresh question. Whatever the
         -- old address was turned away for is not necessarily true of the new
         -- one, and leaving the reason behind would leave the pending list
         -- accusing the wrong person.
         blocked_reason     = null,
         blocked_at         = null,
         updated_at         = now()
   where id = p_invitation_id;
end;
$$;

comment on function public.update_staff_invitation(
  uuid, text, text, text, text, text) is
  'Correct an unclaimed invitation -- the answer to a mistyped email, which is '
  'the one way this single-factor path fails, and to an address the exclusivity '
  'rules turned away. The department cannot change: it is what '
  'can_manage_department authorizes against. Clears any blocked_reason, since '
  'a new address is a new question.';

grant execute on function public.update_staff_invitation(
  uuid, text, text, text, text, text) to authenticated;

-- `claim_staff_invitations` from `20260812090200` 4, copied whole. Everything
-- the header of that section says about it still holds: idempotent, no auth
-- check because the verified email IS the authorization, and execute revoked
-- from `authenticated`.
create or replace function public.claim_staff_invitations(
  p_profile_id uuid,
  p_email      text
)
returns table (
  membership_id uuid,
  community_id  uuid,
  department_id uuid,
  role          text,
  rank          text
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email citext := lower(btrim(coalesce(p_email, '')))::citext;
  v_row   record;
  v_kind  text;
  v_role  text;
  v_membership uuid;
  v_block text;      -- CHANGED
  v_department text; -- CHANGED
begin
  if p_profile_id is null or v_email = '' then
    return;
  end if;

  for v_row in
    select s.*
      from public.staff_invitations s
     where s.invitee_email = v_email
       and s.status = 'pending'
     order by s.created_at
  loop
    select d.kind into v_kind
      from public.departments d
     where d.id = v_row.department_id;

    -- Already a member of that community: leave the invitation pending rather
    -- than claiming it into a membership that cannot be created. An admin
    -- looking at the department sees it still outstanding, which is true.
    if exists (
      select 1 from public.community_memberships m
       where m.community_id = v_row.community_id
         and m.profile_id = p_profile_id
         and m.status = 'active'
         and m.ended_at is null
    ) then
      continue;
    end if;

    -- CHANGED: rulings 1 and 2, skipped rather than raised. See section 5's
    -- header for why an exception here would abandon the whole claim silently.
    --
    -- Re-asked per iteration on purpose: this loop is the one place two
    -- leadership postings can be created in one statement, and the second one
    -- must see the first. The insert below is visible to this read within the
    -- transaction, so an email invited to two communities takes the older
    -- invitation -- `order by s.created_at` -- and is blocked on the newer,
    -- which is the outcome ruling 2 describes.
    v_block := null;

    if exists (select 1 from public.service_providers
                where profile_id = p_profile_id) then
      v_block :=
        'They signed in with an account that is registered as a marketplace service professional. Leadership is invite-only and is never held by a registered provider, so this invitation was not applied.';
    elsif public.active_leadership_community(p_profile_id) is not null then
      v_block :=
        'They signed in, but already manage or supervise another community. Leadership is held in one community at a time, so this invitation was not applied.';
    end if;

    if v_block is not null then
      -- The notification fires on the transition only. This function runs on
      -- every membership-less session read, and a blocked person keeps signing
      -- in.
      if v_row.blocked_at is null then
        select d.name into v_department
          from public.departments d where d.id = v_row.department_id;

        perform public.notify_department_leadership(
          v_row.department_id, 'staff_invitation.blocked',
          jsonb_build_object(
            'title', coalesce(v_row.invitee_name, 'Someone')
                     || ' could not be admitted',
            'body', v_block,
            'url', '/admin/departments/' || v_row.department_id::text,
            'invitationId', v_row.id,
            'departmentId', v_row.department_id,
            'departmentName', v_department));
      end if;

      update public.staff_invitations
         set blocked_reason = v_block,
             blocked_at     = coalesce(blocked_at, now()),
             updated_at     = now()
       where id = v_row.id;

      continue;
    end if;

    -- Derived, never stored -- see `20260812090200`'s header table.
    if v_row.rank = 'manager' then
      v_role := 'manager';
    elsif v_kind = 'security' then
      v_role := 'security';
    else
      v_role := 'worker';
    end if;

    insert into public.community_memberships (
      community_id, profile_id, department_id, role, status, joined_at
    )
    values (
      v_row.community_id, p_profile_id, v_row.department_id,
      v_role::public.membership_role, 'active', now()
    )
    returning id into v_membership;

    insert into public.staff_assignments (
      community_id, department_id, membership_id, display_name, phone_e164,
      job_title, rank, status, employment_type, started_at
    )
    values (
      v_row.community_id, v_row.department_id, v_membership,
      v_row.invitee_name, v_row.invitee_phone_e164, v_row.job_title,
      v_row.rank, 'active', 'staff', current_date
    );

    update public.staff_invitations
       set status = 'claimed',
           claimed_by_profile_id = p_profile_id,
           claimed_at = now(),
           -- CHANGED: an invitation that finally landed is not blocked.
           blocked_reason = null,
           blocked_at = null,
           updated_at = now()
     where id = v_row.id;

    membership_id := v_membership;
    community_id  := v_row.community_id;
    department_id := v_row.department_id;
    role          := v_role;
    rank          := v_row.rank;
    return next;
  end loop;
end;
$$;

comment on function public.claim_staff_invitations(uuid, text) is
  'Turn every pending invitation for this verified email into a membership and '
  'a roster row. Called by resolve_session on a profile with no membership. '
  'Idempotent. Service role only -- the email IS the authorization, so a '
  'caller who could choose it could admit themselves. An invitation the '
  '2026-08-21 exclusivity rulings refuse is skipped and marked with a '
  'blocked_reason, never raised: this runs inside a session read whose caller '
  'swallows exceptions, so raising would abandon every other invitation too.';

revoke all on function public.claim_staff_invitations(uuid, text)
  from public, anon, authenticated;


-- ---------------------------------------------------------------------------
-- 6. Ruling 3: what a roster row still being *theirs* means
--
-- `is_own_staff_assignment` (`0036` 464) asks "is this roster row the caller",
-- and it asks it with no reference to time. So it stays true forever: a
-- supervisor removed from a community on Monday still satisfies it on Tuesday,
-- and it is the predicate behind
--
--   my_worker_job                      the worker calendar and job list
--   my_worker_unavailability            their leave
--   my_worker_availability_rule         their working week
--   can_read_work_order                 every job they were ever assigned
--   staff_departures_read               the departure that removed them
--   security_shifts_read                their old gate rota
--   eight worker action RPCs (`0039`)   accept, decline, start, complete…
--
-- which is most of what ruling 3 says must go dark. It is not a leadership
-- defect -- it is every departed worker -- but the ruling is what makes it
-- something to fix rather than something to note.
--
-- THE FIX IS THE PREDICATE, NOT SEVEN CALL SITES
--
-- Same argument as everywhere else in this file. Editing `my_worker_job`'s
-- `where` clause would leave `can_read_work_order` open, and the next view is
-- written by somebody reading `0036` rather than this.
--
-- WHAT "STILL THEIRS" NOW MEANS
--
-- The roster row is active, and -- on the membership arm -- the membership
-- behind it is active and unended. Those are `can_supervise_department`'s three
-- conditions, so the two predicates now agree about who is present, which
-- matters: `worker_availability_rules_read` calls both in one policy.
--
-- The provider arm keeps no membership condition, because a marketplace
-- professional's identity is their provider row and `remove_department_member`
-- deactivates the roster row it is attached to (`0043` 1083), which the first
-- condition already catches.
--
-- THE COST, STATED PLAINLY
--
-- A departed worker loses their own history: last month's completed jobs
-- disappear from their calendar along with the community. That is what "removal
-- severs access completely" means, and it is the ruling rather than an
-- oversight. The record itself is untouched -- the department still reads every
-- one of those rows.
-- ---------------------------------------------------------------------------

create or replace function public.is_own_staff_assignment(p_staff_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
      from public.staff_assignments sa
      left join public.community_memberships m on m.id = sa.membership_id
      left join public.service_providers p     on p.id = sa.service_provider_id
     where sa.id = p_staff_id
       and sa.status = 'active'
       and (
         (m.profile_id = auth.uid()
          and m.status = 'active'
          and m.ended_at is null)
         or p.profile_id = auth.uid()
       )
  );
$$;

comment on function public.is_own_staff_assignment(uuid) is
  'True when this roster row belongs to the caller **and is still live** -- by '
  'an active membership, or by their service provider record. The active tests '
  'are ruling 3 of 2026-08-21: a person removed from a community stops reading '
  'its jobs, calendar, leave and departures on the spot. Matches '
  'can_supervise_department''s conditions, which one policy asks beside it.';

grant execute on function public.is_own_staff_assignment(uuid) to authenticated;


-- ---------------------------------------------------------------------------
-- 7. Ruling 3: the mailbox
--
-- `dm_threads_read` and `dm_messages_read` (`0046` 6) are keyed on nothing but
-- the two participant columns. A thread is created only between two people
-- `dm_pair_allowed` accepts -- both active members of one community -- but the
-- policy never asks that again, so a supervisor removed from community A keeps
-- reading every thread they ever held there, forever, including the manager's
-- side of their own departure. This is the leak ruling 3 is most concrete
-- about.
--
-- `is_community_member` is the added condition, and it is the same predicate
-- `dm_pair_allowed` was already built on, so the write rule and the read rule
-- now say the same thing. Both ends of every thread resolve through a
-- membership by construction -- `open_direct_thread` refuses a pair
-- `dm_pair_allowed` refuses, and `open_work_order_thread` (`0046` 339-352)
-- finds both participants *through* `community_memberships` -- so this narrows
-- nothing that was legitimately open.
--
-- The thread and its messages are not deleted. The other participant still
-- reads the whole conversation; what ends is one side's access to it.
-- ---------------------------------------------------------------------------

drop policy if exists dm_threads_read on public.dm_threads;
create policy dm_threads_read on public.dm_threads
  for select to authenticated
  using (
    (participant_a_profile_id = auth.uid()
     or participant_b_profile_id = auth.uid())
    and public.is_community_member(community_id)
  );

drop policy if exists dm_messages_read on public.dm_messages;
create policy dm_messages_read on public.dm_messages
  for select to authenticated
  using (
    exists (
      select 1 from public.dm_threads t
       where t.id = dm_messages.thread_id
         and (t.participant_a_profile_id = auth.uid()
              or t.participant_b_profile_id = auth.uid())
         and public.is_community_member(t.community_id)
    )
  );


-- ---------------------------------------------------------------------------
-- 8. Ruling 3: the feed
--
-- THIS OVERTURNS SOMETHING ALREADY WRITTEN, AND NAMES IT
--
-- `0041`'s header, "THE RULE THIS OVERTURNS, STATED PLAINLY", overturned
-- `0030`'s membership-scoped notification read and said why: "A worker removed
-- from one community would lose that community's rows out of a feed that is
-- otherwise theirs… A notification is a copy of something the person was
-- already told, and every inbox in the world retains those."
--
-- Ruling 3 of 2026-08-21 says the opposite for the case it is about, in as many
-- words: a removed supervisor "must not be able to see ANYTHING from the old
-- community — engagements, complaints, conversations/messages, calendar,
-- notifications". `docs/design/README.md` requires the reversal to be named
-- rather than quietly performed, so it is named here.
--
-- WHY IT IS NOT SCOPED TO LEADERSHIP, THOUGH THE RULING IS
--
-- Because it cannot be. `remove_department_member` sets `rank = 'member'` on
-- the row it deactivates (`0043` 1086), so after a removal there is nothing
-- left in the database that says the person was ever a supervisor. A policy
-- conditional on rank would be a policy conditional on a value that has already
-- been erased. The rule is therefore uniform, which is also the more honest
-- shape: "your feed carries the communities you are in" is a sentence, and
-- "your feed carries the communities you are in unless you used to run one" is
-- not.
--
-- WHAT SURVIVES, AND WHY THAT MATTERS MORE THAN IT LOOKS
--
-- A notification with **no** membership is addressed to the person and is not
-- about any community, so it stays. That is the whole population `0041` added
-- the profile column for -- a service professional who has registered and not
-- been hired -- and it is now also the escape hatch for the one message a
-- departure must not swallow.
--
-- `remove_department_member` ends the membership and *then* tells the person
-- they were removed (`0043` 1105-1119), through `notify_member`, keyed to the
-- membership it just ended. Under the policy alone that farewell would be
-- written and instantly invisible: the one notification a removed person most
-- needs, lost to the rule meant to protect them. So `notify_member` learns the
-- distinction -- a message to a membership that is no longer active is a
-- message to the *person*, and is written without a community. No caller
-- changes, no signature changes, and the twenty-odd ordinary call sites are
-- unaffected because their memberships are active.
-- ---------------------------------------------------------------------------

create or replace function public.membership_is_live(p_membership_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select p_membership_id is null
      or exists (
           select 1 from public.community_memberships m
            where m.id = p_membership_id
              and m.status = 'active'
              and m.ended_at is null
         );
$$;

comment on function public.membership_is_live(uuid) is
  'True for an active, unended membership -- and for null, which means "not '
  'about a community at all". Written as a definer function because the '
  'notifications read policy asks it, and an inline subquery there would be '
  'answered through community_memberships'' own RLS.';

revoke all on function public.membership_is_live(uuid)
  from public, anon, authenticated;
grant execute on function public.membership_is_live(uuid) to authenticated;

drop policy if exists notifications_read_own on public.notifications;
create policy notifications_read_own
  on public.notifications
  for select
  to authenticated
  using (
    recipient_profile_id = auth.uid()
    and public.membership_is_live(recipient_membership_id)
  );

-- `notify_member` from `0041` 2, copied whole, with the fallback marked.
create or replace function public.notify_member(
  p_membership_id uuid,
  p_kind text,
  p_payload jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  new_id     uuid;
  v_profile  uuid;
  v_live     boolean;  -- CHANGED
begin
  if p_membership_id is null then
    raise exception 'notify_member requires a recipient membership'
      using errcode = '22004';
  end if;

  if coalesce(btrim(p_kind), '') = '' then
    raise exception 'notify_member requires a kind' using errcode = '22004';
  end if;

  -- CHANGED: the membership's liveness comes back with its profile, in the one
  -- read that was already being done.
  select m.profile_id, (m.status = 'active' and m.ended_at is null)
    into v_profile, v_live
    from public.community_memberships m
   where m.id = p_membership_id;

  -- A membership that does not exist is a caller bug, not a silent no-op: the
  -- row would satisfy the check constraint through its membership column and
  -- then be unreadable by anyone, because the policy asks about the profile.
  if v_profile is null then
    raise exception 'notify_member was given a membership that does not exist'
      using errcode = '23503';
  end if;

  insert into public.notifications (
    recipient_membership_id, recipient_profile_id, kind, payload
  )
  values (
    -- CHANGED: see section 8's header. Telling somebody they have been removed
    -- is the one message that arrives after the membership has ended, and
    -- keying it to that membership would file it under a community the reader
    -- can no longer open. It is a message to the person.
    case when v_live then p_membership_id else null end,
    v_profile, btrim(p_kind), coalesce(p_payload, '{}'::jsonb)
  )
  returning id into new_id;

  return new_id;
end;
$$;

comment on function public.notify_member(uuid, text, jsonb) is
  'Write one notification about one community, in the caller''s transaction. '
  'Resolves the recipient profile itself so ownership has a single predicate. '
  'A message to a membership that has already ended is filed against the '
  'person and no community, so the "you were removed" farewell survives the '
  'ruling-3 feed scoping that hides the rest.';

revoke all on function public.notify_member(uuid, text, jsonb)
  from public, anon, authenticated;
grant execute on function public.notify_member(uuid, text, jsonb) to service_role;


-- ---------------------------------------------------------------------------
-- 9. What already breaks the rules is reported, never repaired
--
-- `20260812113000` 1b's argument, applied to three new questions. A `before`
-- trigger judges the row being written, so an account that already holds two
-- leaderships -- or a leadership and a provider profile -- keeps both until
-- something updates one of them, and then that update fails, possibly in a
-- queue job, with nothing on screen to connect it to this file.
--
-- Ending one of them here is not caution avoided, it is a question a migration
-- cannot answer: which community loses its supervisor, and which identity a
-- person keeps, are somebody's job and somebody's account. A notice puts the
-- counts in the deploy log while whoever runs this still has the context.
--
-- All three are expected to be zero.
-- ---------------------------------------------------------------------------

do $$
declare
  v_provider_leaders integer;
  v_double_leaders   integer;
  v_dm_orphans       integer;
begin
  select count(*) into v_provider_leaders
    from public.staff_assignments sa
   where sa.status = 'active'
     and sa.rank in ('manager', 'supervisor')
     and (
       sa.service_provider_id is not null
       or exists (
            select 1
              from public.community_memberships m
              join public.service_providers p on p.profile_id = m.profile_id
             where m.id = sa.membership_id
          )
     );

  select count(*) into v_double_leaders
    from (
      select m.profile_id
        from public.staff_assignments sa
        join public.community_memberships m on m.id = sa.membership_id
       where sa.status = 'active'
         and sa.rank in ('manager', 'supervisor')
         and m.status = 'active'
         and m.ended_at is null
       group by m.profile_id
      having count(*) > 1
    ) doubled;

  select count(*) into v_dm_orphans
    from public.dm_threads t
   where not exists (
           select 1 from public.community_memberships m
            where m.community_id = t.community_id
              and m.profile_id in (t.participant_a_profile_id,
                                   t.participant_b_profile_id)
              and m.status = 'active'
              and m.ended_at is null
         );

  if v_provider_leaders > 0 then
    raise notice
      'leadership exclusivity: % active manager/supervisor roster row(s) belong to accounts that are also registered service providers (ruling 1). They are left as they are -- which identity to keep is the account holder''s decision -- but any update to their rank, status or identity columns will now be refused.',
      v_provider_leaders;
  end if;

  if v_double_leaders > 0 then
    raise notice
      'leadership exclusivity: % person(s) hold more than one active leadership posting (ruling 2). Left as they are -- which community loses its supervisor is not a migration''s decision -- but no further leadership row can be written for them.',
      v_double_leaders;
  end if;

  if v_dm_orphans > 0 then
    raise notice
      'leadership exclusivity: % direct-message thread(s) have neither participant still active in the thread''s community. Nobody could read them under the ruling-3 policies in section 7. Nothing is deleted; this is the count of what has gone dark.',
      v_dm_orphans;
  end if;
end;
$$;


-- ---------------------------------------------------------------------------
-- 10. Post-apply verification
--
-- Run these in the SQL Editor after this file. They are also reproduced in
-- `docs/plans/MIGRATION_APPLY_RUNBOOK.md` 14. Nothing below runs as part of the
-- migration; the block above is the only thing that executes.
--
--   -- (a) Both triggers exist and fire before the write.
--   select tgname, tgtype
--     from pg_trigger
--    where tgname in ('staff_assignments_leadership_exclusivity',
--                     'service_providers_not_leadership');
--   -- expect: two rows.
--
--   -- (b) The two new columns exist.
--   select column_name, data_type
--     from information_schema.columns
--    where table_schema = 'public' and table_name = 'staff_invitations'
--      and column_name in ('blocked_reason', 'blocked_at');
--   -- expect: two rows.
--
--   -- (c) Exactly one department_staff_invitations, returning twelve columns.
--   select pr.pronargs, array_length(pr.proallargtypes, 1) as out_columns
--     from pg_proc pr
--    where pr.pronamespace = 'public'::regnamespace
--      and pr.proname = 'department_staff_invitations';
--   -- expect: one row, pronargs = 2, out_columns = 14 (2 in + 12 out).
--
--   -- (d) Nobody holds two active leaderships.
--   select m.profile_id, count(*)
--     from public.staff_assignments sa
--     join public.community_memberships m on m.id = sa.membership_id
--    where sa.status = 'active' and sa.rank in ('manager', 'supervisor')
--      and m.status = 'active' and m.ended_at is null
--    group by m.profile_id having count(*) > 1;
--   -- expect: zero rows.
--
--   -- (e) No active leader also holds a provider profile.
--   select sa.id, sa.community_id, sa.rank
--     from public.staff_assignments sa
--     join public.community_memberships m on m.id = sa.membership_id
--     join public.service_providers p on p.profile_id = m.profile_id
--    where sa.status = 'active' and sa.rank in ('manager', 'supervisor')
--      and m.status = 'active' and m.ended_at is null;
--   -- expect: zero rows.
--
--   -- (f) The guard actually refuses. Run as a community admin, in a
--   --     transaction you roll back, against a real provider-held profile:
--   --   begin;
--   --   update public.staff_assignments set rank = 'supervisor'
--   --    where id = '<a roster row with a service_provider_id>';
--   --   -- expect: ERROR, SQLSTATE HBMKT
--   --   rollback;
--
--   -- (g) The four read predicates carry their new conditions.
--   select proname, prosrc ~ 'status' as has_status_test
--     from pg_proc
--    where pronamespace = 'public'::regnamespace
--      and proname in ('is_own_staff_assignment', 'membership_is_live');
--   -- expect: both true.
--
--   select polname, pg_get_expr(polqual, polrelid) as predicate
--     from pg_policy
--    where polname in ('dm_threads_read', 'dm_messages_read',
--                      'notifications_read_own');
--   -- expect: three rows; the first two mention is_community_member, the
--   --         third mentions membership_is_live.
-- ---------------------------------------------------------------------------
