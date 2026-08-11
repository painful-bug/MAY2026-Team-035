-- 0049_staff_provisioning.sql
--
-- How a manager or a supervisor comes to exist.
--
-- THE RULING THIS FILE IMPLEMENTS
--
-- "There is no registration process for the manager or supervisor. The manager
-- is created by the admin and the OAuth goes through based on the manager email
-- that is given in the creation process. The supervisor is either created by the
-- admin or the manager and there is no registration process but only through the
-- creation of the same by either of them. The servicemen (of technician rank in
-- the hierarchy) are the only ones in the whole service section who have a
-- registration process of their own."
--
-- So the service section now has exactly two ways in, and they are not
-- symmetrical:
--
--   servicemen   register themselves (service_providers, 0034), apply or are
--                invited (service_applications, 0035), and a manager decides.
--                Untouched by this file.
--   leadership   does not register at all. An admin types a name and an email;
--                that person signs in with Google and is already a manager.
--
-- THE PROBLEM THAT MAKES THIS A MIGRATION RATHER THAN AN ENDPOINT
--
-- resolve_session (auth_service.py) finds a membership by profile_id. At the
-- moment an admin creates a manager there IS no profile: that person has never
-- signed in, and Supabase mints the profile row on first sign-in. There is
-- nothing to attach a membership to.
--
-- So the provisioning is stored against the EMAIL and claimed on first sign-in.
-- staff_invitations is that store, and claim_staff_invitations is the claim.
--
-- WHY NOT resident_invites
--
-- resident_invites already binds an email, already carries intended_role, and
-- membership_role already contains 'manager'. Reusing it was the obvious move
-- and it is the wrong one, for one reason: resident_invites requires a token
-- AND a code (both NOT NULL, both UNIQUE), and redeem checks the email on top.
-- The token is a deliberate second factor and the rule is that it stays
-- mandatory. Widening that table to make the token optional would weaken the
-- resident flow to serve a different flow's requirement -- so leadership gets
-- its own table and the resident rule is untouched.
--
-- THE TRADE-OFF, STATED PLAINLY
--
-- Email alone is one factor. Whoever controls that mailbox at first sign-in
-- becomes the manager of that department. There is no code to intercept and no
-- link to forward, so the exposure is narrower than a mailed token -- but it is
-- real, and the admin typing the address correctly is the only check. This is
-- the instruction, recorded rather than softened. See
-- docs/design/STAFF_PROVISIONING_DESIGN.md.
--
-- WHAT THE MEMBERSHIP ROLE IS, AND WHY IT IS NOT STORED HERE
--
-- rank and role are separate axes (D3), so the invitation stores the RANK and
-- the role is derived at claim time from the department's kind -- the same
-- derivation decide_service_application does at 0035 918-922:
--
--   rank        department kind    membership role   lands in
--   manager     service            manager           /manager
--   manager     security           manager           /security-manager
--   supervisor  service            worker            /worker
--   supervisor  security           security          /security-manager
--
-- Deriving rather than storing means a department that changes kind between the
-- invitation and the sign-in cannot mint a membership pointing at the wrong
-- portal.
--
-- 'member' IS NOT A VALID RANK HERE, on purpose. That rank is reached only by
-- hiring a registered service provider, which is the whole point of removing
-- typed-in technicians from the department form.

-- ---------------------------------------------------------------------------
-- 1. The table
-- ---------------------------------------------------------------------------

create table if not exists public.staff_invitations (
  id uuid primary key default gen_random_uuid(),
  community_id  uuid not null references public.communities(id) on delete cascade,
  department_id uuid not null references public.departments(id) on delete cascade,
  invitee_email citext not null,
  invitee_name  text not null,
  invitee_phone_e164 varchar(20),
  rank          text not null,
  job_title     text,
  status        text not null default 'pending',
  claimed_by_profile_id uuid references public.profiles(id) on delete set null,
  claimed_at    timestamptz,
  created_by_membership_id uuid not null
    references public.community_memberships(id) on delete restrict,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'staff_invitations_rank_check'
  ) then
    alter table public.staff_invitations
      add constraint staff_invitations_rank_check
      check (rank in ('manager', 'supervisor'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'staff_invitations_status_check'
  ) then
    alter table public.staff_invitations
      add constraint staff_invitations_status_check
      check (status in ('pending', 'claimed', 'revoked'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'staff_invitations_claim_check'
  ) then
    -- A claimed row must say who claimed it and when; a pending one must not
    -- pretend to. Without this, a half-written claim is indistinguishable from
    -- a live invitation and would be claimed again by the next sign-in.
    alter table public.staff_invitations
      add constraint staff_invitations_claim_check
      check (
        (status = 'claimed'
         and claimed_by_profile_id is not null and claimed_at is not null)
        or (status <> 'claimed'
            and claimed_by_profile_id is null and claimed_at is null)
      );
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'staff_invitations_name_check'
  ) then
    alter table public.staff_invitations
      add constraint staff_invitations_name_check
      check (length(btrim(invitee_name)) between 1 and 120);
  end if;
end $$;

-- One open invitation per email per community. Mirrors
-- `invites_one_open_email` on resident_invites: two pending rows for one
-- address would both be claimed by one sign-in, and the second would fail on
-- the membership uniqueness check having already half-run.
create unique index if not exists staff_invitations_one_open_email
  on public.staff_invitations (community_id, invitee_email)
  where status = 'pending';

create index if not exists staff_invitations_pending_email_idx
  on public.staff_invitations (invitee_email) where status = 'pending';

create index if not exists staff_invitations_department_idx
  on public.staff_invitations (department_id);

comment on table public.staff_invitations is
  'A manager or supervisor an administrator has created but who has not signed '
  'in yet. Claimed by email on first sign-in -- there is no registration flow '
  'for leadership, and no token: see 0049''s header for the trade-off.';

alter table public.staff_invitations enable row level security;

drop policy if exists staff_invitations_read on public.staff_invitations;
create policy staff_invitations_read on public.staff_invitations
  for select to authenticated
  using (public.is_community_member(community_id));

-- No write policy. Every write below is a definer function that checks
-- can_manage_department first -- the 0031 posture.

grant select on public.staff_invitations to authenticated;

-- ---------------------------------------------------------------------------
-- 2. Reads
-- ---------------------------------------------------------------------------

create or replace function public.department_staff_invitations(
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
  created_at    timestamptz
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
      s.created_at
      from public.staff_invitations s
     where s.department_id = p_department_id
       and (p_status is null or s.status = p_status)
     order by s.created_at desc;
end;
$$;

comment on function public.department_staff_invitations(uuid, text) is
  'Leadership invited into this department, claimed or not. Admins and the '
  'department''s manager only.';

grant execute on function public.department_staff_invitations(uuid, text)
  to authenticated;

-- ---------------------------------------------------------------------------
-- 3. Writes
-- ---------------------------------------------------------------------------

-- Create a manager or a supervisor.
--
-- Who may: an admin of the community, or the department's manager -- which is
-- exactly can_manage_department. That predicate is what lets a MANAGER create a
-- SUPERVISOR without being an admin, which the ruling requires. It also lets a
-- manager create a second manager; the partial unique index
-- staff_assignments_one_active_manager (0035) is what refuses the second one at
-- claim time, and refusing it there rather than here is deliberate: an
-- invitation is not yet a roster row, and two invitations racing to be claimed
-- is a database question, not an API one.
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

  -- Already a member of this community, under any role. The claim would fail on
  -- the same check, so offering the invitation would be offering a dead end --
  -- the same reasoning search_hireable_service_providers uses to hide people
  -- who already belong (0035 601-608).
  -- `display_email`, not `email`: that is the column name on profiles, and it
  -- is citext, so this comparison is case-insensitive without a lower() that
  -- would defeat the index. `upsert_profile` writes the GoTrue identity's email
  -- into it on first sign-in (profiles_repository.py:52), which is the same
  -- value claim_staff_invitations matches on below.
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
  'manager create a supervisor.';

grant execute on function public.invite_staff_member(
  uuid, text, text, text, text, text) to authenticated;

-- Withdraw one that has not been claimed.
--
-- Revoked rather than deleted: an invitation that was issued and withdrawn is a
-- thing that happened, and the row is the only record of who issued it.
create or replace function public.revoke_staff_invitation(p_invitation_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_department uuid;
  v_status     text;
begin
  select s.department_id, s.status into v_department, v_status
    from public.staff_invitations s
   where s.id = p_invitation_id;

  if v_department is null then
    raise exception 'No such invitation.' using errcode = 'HB404';
  end if;

  if not public.can_manage_department(v_department) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  if v_status = 'claimed' then
    raise exception 'That invitation has already been claimed.'
      using errcode = 'HB409';
  end if;

  update public.staff_invitations
     set status = 'revoked', updated_at = now()
   where id = p_invitation_id;
end;
$$;

comment on function public.revoke_staff_invitation(uuid) is
  'Withdraw an unclaimed invitation. Revoked rather than deleted -- who issued '
  'it and when is worth keeping.';

grant execute on function public.revoke_staff_invitation(uuid) to authenticated;

-- Correct one that has not been claimed.
--
-- WHY THIS EXISTS
--
-- The invitation binds an email and nothing else: whoever next signs in with
-- that address becomes the department's manager. The product owner's ruling on
-- 2026-08-12 was to keep it that way and let a mistyped address be corrected
-- when somebody notices, rather than add a second factor. This is the "when
-- somebody notices" half; the pending list is the "notices" half.
--
-- A typo therefore fails *silently* until it is corrected -- nobody claims, and
-- the invitation sits pending. That is recorded honestly in
-- docs/design/STAFF_PROVISIONING_DESIGN.md rather than dressed up.
--
-- WHAT MAY CHANGE, AND WHAT MAY NOT
--
-- Email, name, phone, job title and rank may all change. They are all things an
-- admin can get wrong at the keyboard, and choosing `supervisor` when you meant
-- `manager` is the same class of mistake as mistyping a domain.
--
-- The DEPARTMENT may not. It is the authorization target: can_manage_department
-- is checked against the invitation's current department, so allowing a move
-- would let the manager of department A mint staff into department B without B's
-- manager ever being asked. Moving an invitation is revoke-and-reissue, under the
-- authority of whoever manages where it is going.
--
-- NULL means "leave alone", so a caller patching only the email cannot blank the
-- job title by omission. Empty string means "clear it" for the two nullable
-- fields. Email and name have no clear -- an invitation without them binds
-- nothing and names nobody.
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
  v_row   public.staff_invitations%rowtype;
  v_email citext;
  v_name  text;
  v_rank  text;
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

  -- Both non-pending states are terminal, and they fail differently on purpose:
  -- a claimed invitation has already become a membership and a roster row, so
  -- editing the email here would change nothing about who got in.
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

  -- The same two collisions invite_staff_member checks, re-checked because the
  -- email is changing. The second one is also enforced by
  -- staff_invitations_one_open_email, but a unique-violation surfaces to the API
  -- as an unhandled 500; catching it here gives the admin the sentence that tells
  -- them what to do.
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
         updated_at         = now()
   where id = p_invitation_id;
end;
$$;

comment on function public.update_staff_invitation(
  uuid, text, text, text, text, text) is
  'Correct an unclaimed invitation -- the answer to a mistyped email, which is '
  'the one way this single-factor path fails. The department cannot change: it '
  'is what can_manage_department authorizes against.';

grant execute on function public.update_staff_invitation(
  uuid, text, text, text, text, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 4. The claim
--
-- Called once per sign-in, by resolve_session, for a profile that has no
-- membership. Everything about it is shaped by that:
--
--   IDEMPOTENT      a second call finds nothing pending and returns zero rows.
--                   resolve_session runs on every session read, not just the
--                   first.
--   NO AUTH CHECK   there is nothing to check. The caller is the API process
--                   acting for a profile whose email GoTrue has verified; the
--                   email is the authorization, and it must never come from a
--                   client-supplied value. The Python side passes only
--                   verified_identity(access_token).email.
--   EXECUTE REVOKED from authenticated -- see the grant at the bottom. A
--                   signed-in user calling this with somebody else's email
--                   would admit themselves; only the service role may.
-- ---------------------------------------------------------------------------

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

    -- Derived, never stored -- see the header's table. A manager runs a
    -- department whatever its kind; a supervisor is a senior member of the
    -- workforce, so they take the workforce role and _portal_for reads their
    -- rank to decide where they land.
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
  'caller who could choose it could admit themselves.';

-- The one function in this file authenticated users may not call.
revoke all on function public.claim_staff_invitations(uuid, text)
  from public, anon, authenticated;
