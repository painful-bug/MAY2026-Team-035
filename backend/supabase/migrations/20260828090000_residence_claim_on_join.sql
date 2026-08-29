-- ---------------------------------------------------------------------------
-- 20260828090000_residence_claim_on_join.sql
--
-- The join flow never asks where the applicant lives.
--
-- Live testing (2026-08-27) surfaced the gap: the wire contract for a unit
-- exists end to end -- `access_requests.requested_unit_id`, the approve RPC's
-- `p_unit_id`, and a `unit_residencies` insert that fires when either is set --
-- but both ends send null. The join form has no unit field (the AUTH plan's §5
-- privacy invariant deliberately keeps a community's unit list away from
-- non-members, so the applicant-side picker was deferred), and the admin's
-- Accept button posts `{}`. Every self-service approval therefore mints a
-- membership with no residency: `membership.unit` renders '--' everywhere, and
-- `_has_active_residency` (backend/app/api/deps.py) 403s people who genuinely
-- live there. Nor could an admin repair it by hand: apartment communities carry
-- exactly one `units` row (the founder's own flat, seeded by `20260805144502`),
-- and there is no unit CRUD anywhere in the product.
--
-- The product owner's rulings (2026-08-27, plan-mode Q&A), verbatim in effect:
--
--   1. The applicant states their residence as **free text at request time** --
--      Tower/Block + Flat for `apartment`, Villa number for `layout_villa` --
--      stored on `access_requests`. No unit exposure to non-members; the
--      privacy invariant stands.
--   2. **Approval requires a unit**: the RPC refuses a resident approval
--      without one, so every approved resident gets a `unit_residencies` row.
--   3. The inventory gap is solved by **find-or-create at approval**: the admin
--      confirms or edits the claimed residence, and the RPC matches an existing
--      active unit in that community or creates it (with its building) inline.
--      No unit-management screen in this work.
--
-- WHAT IS IN HERE
--
--   1. Two text columns on `access_requests`: `requested_building_text` and
--      `requested_unit_text`, each null or a non-blank string of at most 120
--      characters. Two columns and not one so tower and flat stay separable --
--      the approval prefill feeds `normalize_unit_code(tower, flat)` on the
--      Python side, and a single concatenated field is how the documented
--      C-C-505 double-prefix hazard happens.
--   2. `approve_access_request` re-issued with two new trailing parameters,
--      `p_unit_code text` and `p_building_code text`. PostgREST cannot
--      dispatch overloads, so the old 4-argument signature is DROPPED first,
--      not left beside. The body is `20260730170036`'s verbatim -- the lock,
--      the reviewer check, the idempotent already-approved return, the
--      membership insert with its unique_violation fallback, the residency
--      insert with its swallow, the final update -- plus a unit-resolution
--      block and one gate:
--        * `coalesce(p_unit_id, requested_unit_id)` still wins when present,
--          with the same belongs-to-this-community-and-active validation.
--        * otherwise a non-blank `p_unit_code` is matched case-insensitively
--          against the community's units. Found but inactive is a refusal in
--          words (`HB422`); found active is used.
--        * not found is find-or-create, mirroring the founder RPC
--          (`20260805144502`): for `layout_villa` the building code defaults
--          to the unit code itself and each villa gets its own `buildings` row
--          (`building_type 'villa'`, `unit_type 'villa'`); for apartment the
--          building comes from `p_building_code` (`building_type 'block'`,
--          `unit_type 'flat'`). Both inserts are `on conflict do nothing` with
--          a re-select, so two admins approving into the same new tower race
--          safely against the unique constraints instead of each other.
--        * THE GATE (ruling 2): a resolution that still holds no unit refuses
--          the whole approval with a new SQLSTATE, `HBUNT`, before any row is
--          written -- a refused approval leaves no membership behind.
--      The `unit_residencies` insert loses its `if target_unit_id is not null`
--      guard: after the gate the condition is always true, and a guard that can
--      no longer be false is a sentence claiming something this function no
--      longer allows. `created_by_membership_id` stays in the insert -- it is a
--      hosted-only column (no migration here declares it), and this body is the
--      applied `20260730170036`'s, carried forward.
--   3. `pending_access_request_overview` re-issued with the same columns in
--      the same order, APPENDING `ar.requested_building_text`,
--      `ar.requested_unit_text` and `c.community_type` at the end --
--      `create or replace view` permits appending and nothing else, and the
--      admin queue needs the claim to prefill and the community type to label
--      Tower/Flat vs Villa.
--
-- WHAT IT IS NOT
--
-- No unit CRUD screen (ruling 3 solves the inventory gap at approval, not with
-- a new surface). No SSE payload change: the `access_requests` triggers from
-- `0024` fire on the UPDATE this function already does, and the admin queue
-- refetches through the view, which now carries the new fields. No change to
-- the invitation path -- `resident_invites.intended_unit_id` already works.
-- `requested_unit_id` keeps working too: a validated FK path invitations and a
-- future villa picker can use, and still the highest-precedence input. And the
-- `audit_events` insert that `20260730170036` dropped is NOT restored -- that
-- was a hosted-compat decision and it stands.
--
-- One new SQLSTATE, `HBUNT`, mapped in `app/core/pg_errors.py` in the same
-- commit ("approval refused for lack of a unit" is the admin's fixable
-- omission -- a 422 about the request body -- not HB422's generic validation
-- and not the 409 family). `HB422` here is unit-exists-but-inactive, already
-- mapped.
--
-- One transaction: the SQL editor wraps the paste, so a failure anywhere rolls
-- back everything. Idempotent: the columns are `add column if not exists`, the
-- constraint adds are guarded, and the function and view are drop-then-create /
-- `create or replace`.
--
-- Hand-applied by the owner in the Supabase SQL editor, like every file here.
-- Runbook section 31.
--
-- ROLLBACK:
--   * section 1: `alter table public.access_requests drop column
--     requested_building_text, drop column requested_unit_text;` (drops the
--     CHECKs with them) -- and only once the view below no longer selects them.
--   * section 2: `drop function public.approve_access_request(uuid, uuid,
--     uuid, public.residency_relationship, text, text);` then re-apply
--     `20260730170036`, which is this body without the resolution block.
--   * section 3: re-apply `0024` section 4 -- after section 1's rollback, or
--     `create or replace view` will refuse to drop the appended columns;
--     `drop view` first if rolling back the view alone.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. The claimed residence, as the applicant states it (ruling 1)
--
-- Free text, because the privacy invariant means the applicant cannot be shown
-- the unit list to pick from. Two columns so the admin-side prefill can feed
-- tower and flat into `normalize_unit_code` separately. The CHECKs are the
-- `rejection_reason` convention (`0001` line 57) with the blank-string refusal
-- added: a claim of '   ' is not a claim, and 120 characters is the
-- `location_label` / `designation` ceiling this schema already uses.
-- ---------------------------------------------------------------------------

alter table public.access_requests
  add column if not exists requested_building_text text,
  add column if not exists requested_unit_text     text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.access_requests'::regclass
       and conname  = 'access_requests_requested_building_text_check'
  ) then
    alter table public.access_requests
      add constraint access_requests_requested_building_text_check
      check (requested_building_text is null
             or (btrim(requested_building_text) <> ''
                 and char_length(requested_building_text) <= 120));
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.access_requests'::regclass
       and conname  = 'access_requests_requested_unit_text_check'
  ) then
    alter table public.access_requests
      add constraint access_requests_requested_unit_text_check
      check (requested_unit_text is null
             or (btrim(requested_unit_text) <> ''
                 and char_length(requested_unit_text) <= 120));
  end if;
end $$;

comment on column public.access_requests.requested_building_text is
  'The tower/block the applicant claims to live in, as they typed it. Free '
  'text by ruling 1 (2026-08-27): non-members are never shown the unit list. '
  'Null for villa communities and for pre-migration requests.';
comment on column public.access_requests.requested_unit_text is
  'The flat or villa number the applicant claims, as they typed it. The '
  'approval flow prefills from it; the unit actually assigned is whatever the '
  'admin confirms.';


-- ---------------------------------------------------------------------------
-- 2. `approve_access_request` learns to resolve a unit (rulings 2 and 3)
--
-- The 4-argument signature is dropped, not overloaded: PostgREST refuses to
-- dispatch between overloads, so `POST /rpc/approve_access_request` would 300
-- with both in the catalogue. The body below is `20260730170036`'s -- the last
-- file to define this function, and the one the database is holding -- with
-- the unit-resolution block and the gate added between the existing
-- validation and the membership insert. The gate sits BEFORE the membership
-- insert deliberately: an approval refused for lack of a unit writes nothing,
-- so the admin retries with a unit and the request is still cleanly pending.
-- ---------------------------------------------------------------------------

drop function if exists public.approve_access_request(uuid, uuid, uuid, public.residency_relationship);

create function public.approve_access_request(
  p_request_id uuid,
  p_reviewer_profile_id uuid,
  p_unit_id uuid default null,
  p_relationship public.residency_relationship default null,
  p_unit_code text default null,
  p_building_code text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  request_row public.access_requests%rowtype;
  reviewer_membership_id uuid;
  resident_membership_id uuid;
  target_unit_id uuid := p_unit_id;
  v_unit_code text := nullif(btrim(coalesce(p_unit_code, '')), '');
  v_building_code text := nullif(btrim(coalesce(p_building_code, '')), '');
  v_unit_status text;
  v_community_type text;
  v_building_id uuid;
begin
  select * into request_row
  from public.access_requests
  where id = p_request_id
  for update;
  if request_row.id is null then
    raise exception 'Access request not found';
  end if;

  select id into reviewer_membership_id
  from public.community_memberships
  where profile_id = p_reviewer_profile_id
    and community_id = request_row.community_id
    and role = 'admin'
    and status = 'active'
    and ended_at is null
  limit 1;
  if reviewer_membership_id is null then
    raise exception 'Active administrator membership required';
  end if;

  if request_row.status = 'approved' then
    select id into resident_membership_id
    from public.community_memberships
    where community_id = request_row.community_id
      and profile_id = request_row.applicant_profile_id
      and role = 'resident'
      and status = 'active'
      and ended_at is null
    limit 1;
    return jsonb_build_object(
      'request_id', request_row.id,
      'membership_id', resident_membership_id,
      'status', 'approved'
    );
  end if;
  if request_row.status <> 'pending' then
    raise exception 'Access request is no longer pending';
  end if;

  if target_unit_id is null then
    target_unit_id := request_row.requested_unit_id;
  end if;
  if target_unit_id is not null and not exists (
    select 1 from public.units
    where id = target_unit_id
      and community_id = request_row.community_id
      and status = 'active'
  ) then
    raise exception 'Selected unit does not belong to this community';
  end if;

  -- Ruling 3: no id, but a code -- match it, or make it. Case-insensitive on
  -- the match (the Python side canonicalises case, but an admin typing 'c-505'
  -- at a community holding 'C-505' means the same flat), exact case on the
  -- create, so the community's own spelling is the one that sticks.
  if target_unit_id is null and v_unit_code is not null then
    select u.id, u.status into target_unit_id, v_unit_status
      from public.units u
     where u.community_id = request_row.community_id
       and upper(u.unit_code) = upper(v_unit_code)
     limit 1;

    if target_unit_id is not null and v_unit_status <> 'active' then
      raise exception 'Unit % exists in this community but is not active, so nobody can be placed in it.', v_unit_code
        using errcode = 'HB422';
    end if;

    if target_unit_id is null then
      select community_type into v_community_type
        from public.communities
       where id = request_row.community_id;

      -- The founder RPC's shape (`20260805144502`): a villa is its own
      -- building, so with no building given the villa code names both.
      if v_building_code is null and v_community_type = 'layout_villa' then
        v_building_code := v_unit_code;
      end if;

      if v_building_code is not null then
        insert into public.buildings (community_id, name, code, building_type)
        values (
          request_row.community_id,
          v_building_code,
          v_building_code,
          case when v_community_type = 'layout_villa' then 'villa' else 'block' end
        )
        on conflict (community_id, code) do nothing;

        select b.id into v_building_id
          from public.buildings b
         where b.community_id = request_row.community_id
           and b.code = v_building_code;
      end if;

      insert into public.units (community_id, building_id, unit_code, unit_type, status)
      values (
        request_row.community_id,
        v_building_id,
        v_unit_code,
        case when v_community_type = 'layout_villa' then 'villa' else 'flat' end,
        'active'
      )
      on conflict (community_id, unit_code) do nothing;

      select u.id into target_unit_id
        from public.units u
       where u.community_id = request_row.community_id
         and u.unit_code = v_unit_code;
    end if;
  end if;

  -- THE GATE (ruling 2). Before the membership insert, so a refused approval
  -- writes nothing: the admin supplies a unit and presses Accept again on a
  -- request that is still cleanly pending.
  if target_unit_id is null then
    raise exception 'Approving a resident requires a unit. Provide the flat or villa to place them in.'
      using errcode = 'HBUNT';
  end if;

  begin
    insert into public.community_memberships(
      community_id, profile_id, role, status, is_default_community
    ) values (
      request_row.community_id,
      request_row.applicant_profile_id,
      'resident',
      'active',
      not exists (
        select 1 from public.community_memberships
        where profile_id = request_row.applicant_profile_id
          and status = 'active'
          and ended_at is null
          and is_default_community
      )
    ) returning id into resident_membership_id;
  exception
    when unique_violation then
      resident_membership_id := null;
  end;

  if resident_membership_id is null then
    select id into resident_membership_id
    from public.community_memberships
    where community_id = request_row.community_id
      and profile_id = request_row.applicant_profile_id
      and role = 'resident'
      and status = 'active'
      and ended_at is null
    limit 1;
    if resident_membership_id is null then
      raise exception 'Applicant already has an incompatible membership';
    end if;
  end if;

  begin
    insert into public.unit_residencies(
      unit_id, membership_id, relationship_type, created_by_membership_id
    ) values (
      target_unit_id,
      resident_membership_id,
      coalesce(p_relationship, request_row.requested_relationship),
      reviewer_membership_id
    );
  exception
    when unique_violation then null;
  end;

  update public.access_requests
  set status = 'approved',
      reviewed_by_membership_id = reviewer_membership_id,
      reviewed_at = now(),
      rejection_reason = null,
      updated_at = now()
  where id = request_row.id;

  return jsonb_build_object(
    'request_id', request_row.id,
    'membership_id', resident_membership_id,
    'status', 'approved'
  );
end;
$$;

comment on function public.approve_access_request(uuid, uuid, uuid, public.residency_relationship, text, text) is
  'Approves a pending join request into a resident membership WITH a residency '
  '(ruling 2, 2026-08-27): p_unit_id/requested_unit_id win when present, else '
  'p_unit_code is matched case-insensitively or created with its building '
  '(ruling 3), and no unit at all is HBUNT -- a refusal that writes nothing.';


-- ---------------------------------------------------------------------------
-- 3. The admin queue's projection carries the claim (and the label to read it)
--
-- `0024` section 4's view, column for column and in the same order, with three
-- columns APPENDED: the two claim fields, and `community_type` so the card can
-- say Tower/Flat to an apartment admin and Villa to a layout one.
-- `create or replace view` permits exactly this -- appending -- and the static
-- test derives the old order from `0024`'s own text to prove nothing moved.
-- ---------------------------------------------------------------------------

create or replace view public.pending_access_request_overview
with (security_invoker = true) as
  select
    ar.id,
    ar.community_id,
    ar.applicant_name,
    ar.applicant_email::text as applicant_email,
    ar.applicant_phone_e164,
    ar.requested_relationship::text as requested_relationship,
    ar.status,
    ar.created_at,
    ar.requested_unit_id,
    u.unit_code as requested_unit_code,
    c.name as community_name,
    ar.requested_building_text,
    ar.requested_unit_text,
    c.community_type
  from public.access_requests ar
  join public.communities c on c.id = ar.community_id
  left join public.units u on u.id = ar.requested_unit_id
  where ar.status = 'pending';

comment on view public.pending_access_request_overview is
  'Pending join requests per community. Backs DashboardSnapshot.pendingRequests, which drives the admin sidebar badge. Since 20260828090000 also carries the applicant''s claimed residence (requested_building_text/requested_unit_text) and the community_type that labels it.';


-- ---------------------------------------------------------------------------
-- 4. The audience, re-stated on the new signature
--
-- The drop above took the old signature's ACL with it, so this is not a
-- restatement: a function created without a grant is callable by nobody, and
-- the backend calls this one through the service-role client only -- the
-- reviewer check inside the body is the authorisation, exactly as before.
-- ---------------------------------------------------------------------------

revoke all on function public.approve_access_request(uuid, uuid, uuid, public.residency_relationship, text, text)
  from public, anon, authenticated;
grant execute on function public.approve_access_request(uuid, uuid, uuid, public.residency_relationship, text, text)
  to service_role;


-- ---------------------------------------------------------------------------
-- 5. Proof, in the same transaction
--
-- The failure with no symptom here is a `create or replace view` that
-- reordered instead of appended, or a function drop that left the 4-argument
-- signature for PostgREST to trip over. Each is proved by inspection; a raise
-- rolls the whole paste back.
-- ---------------------------------------------------------------------------

do $$
declare
  v_tail text;
begin
  if to_regprocedure(
    'public.approve_access_request(uuid,uuid,uuid,public.residency_relationship,text,text)'
  ) is null then
    raise exception 'approve_access_request 6-arg signature missing';
  end if;
  if to_regprocedure(
    'public.approve_access_request(uuid,uuid,uuid,public.residency_relationship)'
  ) is not null then
    raise exception 'the old 4-arg approve_access_request survived the drop; PostgREST cannot dispatch overloads';
  end if;
  if position(
    'HBUNT'
    in pg_get_functiondef(
      'public.approve_access_request(uuid,uuid,uuid,public.residency_relationship,text,text)'::regprocedure)
  ) = 0 then
    raise exception 'approve_access_request holds no HBUNT gate';
  end if;

  if not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'access_requests'
       and column_name = 'requested_building_text'
  ) or not exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'access_requests'
       and column_name = 'requested_unit_text'
  ) then
    raise exception 'access_requests is missing a claimed-residence column';
  end if;
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.access_requests'::regclass
       and conname  = 'access_requests_requested_building_text_check'
  ) or not exists (
    select 1 from pg_constraint
     where conrelid = 'public.access_requests'::regclass
       and conname  = 'access_requests_requested_unit_text_check'
  ) then
    raise exception 'a claimed-residence CHECK is missing';
  end if;

  select string_agg(column_name, ',' order by ordinal_position) into v_tail
    from information_schema.columns
   where table_schema = 'public'
     and table_name = 'pending_access_request_overview'
     and ordinal_position > 11;
  if v_tail is distinct from 'requested_building_text,requested_unit_text,community_type' then
    raise exception 'pending_access_request_overview tail is %, not the three appended columns', v_tail;
  end if;

  raise notice
    'residence_claim_on_join: two claim columns, a 6-arg approve with the unit gate, and the view carries the claim.';
end $$;


-- A changed signature IS a catalogue change: without the reload PostgREST
-- keeps answering for the 4-argument shape it remembers, and the approve
-- button 404s until the next restart.
notify pgrst, 'reload schema';


-- ---------------------------------------------------------------------------
-- Post-checks, to be run AFTER the transaction commits
--
-- Comment-only on purpose: these belong in the SQL editor's next tab, not in
-- the apply. Every one is a GUARD-FREE structural inspection -- no `auth.uid()`
-- (the editor has none; this RPC is service-role-only anyway, and calling it
-- would write real rows). Runbook section 31 carries them too.
--
--   -- (a) One approve_access_request, with six arguments, security definer,
--   --     granted to service_role only. Expect exactly one row.
--   select p.oid::regprocedure           as signature,
--          p.pronargs                    as args,
--          p.prosecdef                   as security_definer,
--          array_to_string(p.proacl, ', ') as acl
--     from pg_proc p
--     join pg_namespace n on n.oid = p.pronamespace
--    where n.nspname = 'public'
--      and p.proname = 'approve_access_request';
--
--   -- (b) The two claim columns and their CHECKs. Expect two rows each.
--   select column_name, data_type, is_nullable
--     from information_schema.columns
--    where table_schema = 'public' and table_name = 'access_requests'
--      and column_name in ('requested_building_text', 'requested_unit_text');
--   select conname, pg_get_constraintdef(oid)
--     from pg_constraint
--    where conrelid = 'public.access_requests'::regclass
--      and conname like 'access_requests_requested_%_text_check';
--
--   -- (c) The view's tail is the three appended columns, in this order, and
--   --     nothing before them moved. Expect 14 rows, positions 12-14 being
--   --     requested_building_text, requested_unit_text, community_type.
--   select ordinal_position, column_name
--     from information_schema.columns
--    where table_schema = 'public'
--      and table_name = 'pending_access_request_overview'
--    order by ordinal_position;
--
--   -- (d) Nobody has claimed a residence yet, which is what day one looks
--   --     like. Expect zero until the join form ships.
--   select count(*) as requests_with_a_claim
--     from public.access_requests
--    where requested_unit_text is not null;
-- ---------------------------------------------------------------------------
