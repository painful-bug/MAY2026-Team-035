-- ===========================================================================
-- Step 6 rebuilt: department and staff management, on the baseline schema.
--
-- This replaces `legacy-preauth/0014_departments.sql`, which was written against
-- `0001_init.sql` and cannot be applied. The reasoning it carries is preserved;
-- only the table and column names are retargeted. Read that file for the full
-- derivation of each number on the departments screen.
--
-- WHY THIS ONE MATTERS MOST
--
-- `dashboard_service.py:203` builds every department in the snapshot as
-- `{"staff": [], "categories": []}` -- hardcoded empty lists. `Departments.jsx`
-- and `DepartmentDetail.jsx` are built around staff rosters and per-department
-- complaint queues. Until this migration exists, the API has no source for
-- either, and the snapshot's empty arrays are indistinguishable from a genuinely
-- empty roster.
--
-- WHAT THE BASELINE ALREADY GIVES US
--
-- `departments`, `staff_assignments`, `skills`, `staff_skills` and `vendors` all
-- exist. They are thin -- `departments` is name/description/category/hours, and
-- `staff_assignments` is an employment record keyed to a membership. Everything
-- below is `alter table ... add column` on those, plus the two category tables
-- the baseline has no equivalent of, the two views the reads go through, and the
-- four RPCs the writes go through.
--
-- ASSUMPTIONS CARRIED FORWARD FROM 0014
--
--  A6  'Inactive' MAPS TO 'archived'. The frontend has two department states;
--      the stored vocabulary has two values. The mapping is total and lossless
--      in both directions and lives in `app/domain/vocabularies.py`.
--
--  A7  REMOVING A STAFF MEMBER DEACTIVATES THE ROW, it does not delete it.
--      `complaints.assignee_label` records staff by name, so a deleted row turns
--      a past assignment into an unexplained string. The partial head index only
--      constrains active rows, so a deactivated head frees the slot.
--
--  A8  A STAFF MEMBER'S ASSIGNMENT COUNT IS SCOPED TO THEIR DEPARTMENT, matching
--      `DepartmentDetail.jsx:452`. Work assigned to them under another
--      department is not counted here.
--
-- THREE BASELINE CONSTRAINTS THIS HAS TO RELAX, AND WHY
--
--  1. `staff_assignments.membership_id` is `not null` on the baseline, because
--     it models the employment record of a person who has an account. Our roster
--     is a list of NAMES typed into a form -- `Departments.jsx` collects
--     `{name, phone, role, shift}` and never asks for an account. Requiring a
--     membership would make the roster unfillable, so the column becomes
--     nullable and `display_name` carries the unlinked case.
--
--  2. `employment_type` is `not null` with no default, and nothing on the
--     department form supplies one. It gets a default of 'staff' rather than a
--     new required field on a screen we are not allowed to change.
--
--  3. `is_active` stays, and stays TRUTHFUL. Their `dashboard_repository.py:166`
--     selects it. We add `status` because two states need names rather than a
--     boolean, and a trigger keeps the pair consistent in both directions, so
--     neither reader has to know about the other's column.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 0. Two shared membership predicates
--
-- `0018_settings_on_baseline.sql` inlines this nine-line `exists` into every
-- policy, twice for the write policies. That was tolerable for two tables; the
-- rebuild adds roughly twenty more, and an inlined predicate that has to be
-- correct twenty times is a predicate that will eventually be wrong once.
--
-- SECURITY DEFINER because a policy ON `community_memberships` would otherwise
-- recurse: evaluating "may this caller read memberships" would consult the
-- policy that is asking. STABLE so the planner may call it once per query
-- rather than once per row.
--
-- `set search_path = public` matters more here than usual -- these run as the
-- owner, so a caller-controlled search_path could otherwise point
-- `community_memberships` at a temp table of their own making.
-- ---------------------------------------------------------------------------
create or replace function public.is_community_member(p_community_id uuid)
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
       and m.status = 'active'
       and m.ended_at is null
  );
$$;

create or replace function public.is_community_admin(p_community_id uuid)
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
       and m.role = 'admin'
       and m.status = 'active'
       and m.ended_at is null
  );
$$;

comment on function public.is_community_member(uuid) is
  'True when the caller holds an active membership in the community. Used by RLS policies.';
comment on function public.is_community_admin(uuid) is
  'True when the caller is an active admin of the community. Used by RLS policies and the write RPCs.';

grant execute on function public.is_community_member(uuid) to authenticated;
grant execute on function public.is_community_admin(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 1. Departments: the columns the screen needs
-- ---------------------------------------------------------------------------
alter table public.departments
  add column if not exists contact_email      citext,
  add column if not exists contact_phone_e164 varchar(20),
  add column if not exists opens_at           time,
  add column if not exists closes_at          time,
  add column if not exists sla_hours          integer,
  add column if not exists kind               text,
  add column if not exists status             text not null default 'active';

-- Named separately so re-running the migration does not fail on a duplicate.
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'departments_status_check'
  ) then
    alter table public.departments
      add constraint departments_status_check
      check (status in ('active', 'archived'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'departments_kind_check'
  ) then
    alter table public.departments
      add constraint departments_kind_check
      check (kind is null or kind in ('internal', 'vendor', 'hybrid'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'departments_sla_hours_check'
  ) then
    alter table public.departments
      add constraint departments_sla_hours_check
      check (sla_hours is null or sla_hours between 1 and 8760);
  end if;
end $$;

-- The composite target that lets child rows prove tenancy without a join.
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'departments_id_community_id_key'
  ) then
    alter table public.departments
      add constraint departments_id_community_id_key unique (id, community_id);
  end if;
end $$;

-- `status` and `is_active` say the same thing to two different readers. Writing
-- either one updates the other, so neither can drift and neither reader has to
-- learn about the other's column.
create or replace function public.sync_department_status()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'INSERT' then
    if new.status is distinct from 'active' then
      new.is_active := (new.status = 'active');
    else
      new.status := case when new.is_active then 'active' else 'archived' end;
    end if;
    return new;
  end if;

  if new.status is distinct from old.status then
    new.is_active := (new.status = 'active');
  elsif new.is_active is distinct from old.is_active then
    new.status := case when new.is_active then 'active' else 'archived' end;
  end if;
  return new;
end $$;

drop trigger if exists departments_sync_status on public.departments;
create trigger departments_sync_status
  before insert or update on public.departments
  for each row execute function public.sync_department_status();

-- ---------------------------------------------------------------------------
-- 2. Staff assignments: a roster of names, not only of accounts
-- ---------------------------------------------------------------------------
alter table public.staff_assignments
  add column if not exists community_id  uuid,
  add column if not exists display_name  text,
  add column if not exists phone_e164    varchar(20),
  add column if not exists job_title     text,
  add column if not exists rank          text not null default 'member',
  add column if not exists shift         text,
  add column if not exists status        text not null default 'active';

alter table public.staff_assignments alter column membership_id drop not null;
alter table public.staff_assignments alter column employment_type set default 'staff';

-- Existing rows predate community_id; derive it from the membership they hang
-- off before the column is made mandatory.
update public.staff_assignments s
   set community_id = m.community_id
  from public.community_memberships m
 where s.membership_id = m.id
   and s.community_id is null;

-- Rows with neither a membership nor a department cannot be placed in a
-- community, and there is nothing sensible to guess. They are left null and the
-- column stays nullable rather than failing the migration on legacy data.
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'staff_assignments_status_check'
  ) then
    alter table public.staff_assignments
      add constraint staff_assignments_status_check
      check (status in ('active', 'inactive'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'staff_assignments_rank_check'
  ) then
    alter table public.staff_assignments
      add constraint staff_assignments_rank_check
      check (rank in ('head', 'member'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'staff_assignments_shift_check'
  ) then
    alter table public.staff_assignments
      add constraint staff_assignments_shift_check
      check (shift is null or shift in ('Morning', 'Evening', 'Night', 'Full Day'));
  end if;

  -- A roster entry has to be identifiable: either it points at a member, or it
  -- carries a typed name. A row with neither is unnameable on the screen.
  if not exists (
    select 1 from pg_constraint where conname = 'staff_assignments_identity_check'
  ) then
    alter table public.staff_assignments
      add constraint staff_assignments_identity_check
      check (membership_id is not null or nullif(btrim(coalesce(display_name, '')), '') is not null);
  end if;

  -- Cross-tenant rows become unrepresentable rather than merely forbidden: the
  -- department and the row must agree on the community.
  if not exists (
    select 1 from pg_constraint where conname = 'staff_assignments_department_tenant_fkey'
  ) then
    alter table public.staff_assignments
      add constraint staff_assignments_department_tenant_fkey
      foreign key (department_id, community_id)
      references public.departments (id, community_id)
      on delete cascade;
  end if;
end $$;

-- At most one active head per department. Partial, so a deactivated head frees
-- the slot immediately (A7).
create unique index if not exists staff_assignments_one_active_head
  on public.staff_assignments (department_id)
  where rank = 'head' and status = 'active';

create index if not exists staff_assignments_department_idx
  on public.staff_assignments (department_id, status);

create index if not exists staff_assignments_community_idx
  on public.staff_assignments (community_id);

-- ---------------------------------------------------------------------------
-- 3. Complaints: the four columns the department screens read
--
-- The baseline models a complaint as raised-by + category + status. The
-- departments screens additionally need to know which department owns it, when
-- it is due, and who is working on it.
--
-- `assignee_label` is a plain string beside the membership reference because the
-- roster is a list of typed names (see the note above) -- an assignment to
-- "Ravi Kumar" who has no account has nothing to point a foreign key at.
-- ---------------------------------------------------------------------------
alter table public.complaints
  add column if not exists department_id             uuid references public.departments(id) on delete set null,
  add column if not exists assigned_to_membership_id uuid references public.community_memberships(id) on delete set null,
  add column if not exists assignee_label            text,
  add column if not exists due_at                    timestamptz;

create index if not exists complaints_department_idx
  on public.complaints (department_id, status);

-- ---------------------------------------------------------------------------
-- 4. Complaint categories
--
-- The baseline stores `complaints.category` as free text and `departments.category`
-- likewise. The departments screen needs a department to CLAIM a set of
-- categories, which is a many-to-many the baseline has no table for.
--
-- Category names are per-community and case-insensitively unique: "Plumbing" and
-- "plumbing" typed into the free-text form on two different days are one
-- category, not two.
-- ---------------------------------------------------------------------------
create table if not exists public.complaint_categories (
  id           uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  name         text not null check (length(btrim(name)) between 1 and 80),
  created_at   timestamptz not null default now()
);

create unique index if not exists complaint_categories_community_name_key
  on public.complaint_categories (community_id, lower(btrim(name)));

create table if not exists public.department_categories (
  department_id uuid not null references public.departments(id) on delete cascade,
  category_id   uuid not null references public.complaint_categories(id) on delete cascade,
  created_at    timestamptz not null default now(),
  primary key (department_id, category_id)
);

create index if not exists department_categories_category_idx
  on public.department_categories (category_id);

-- ---------------------------------------------------------------------------
-- 5. department_overview
--
-- Every number the departments screen shows, computed in one place. A VIEW and
-- not an RPC because a list endpoint needs filtering, ordering, paging and an
-- exact count, and PostgREST gives all four on a view for free.
--
-- `security_invoker = true` makes the view run with the CALLER's rights, so the
-- RLS policies on departments/complaints/staff_assignments still decide what is
-- visible. Without it a view is a hole straight through RLS.
--
-- `search_text` exists so that one `ilike` reproduces the frontend's search,
-- which spans name, description, head, email, category names AND staff names
-- (Departments.jsx:163). Matching that with PostgREST `or` filters across three
-- embedded tables is not possible; precomputing the haystack is.
--
-- The status filters use the BASELINE's `complaint_status` enum
-- ('open','acknowledged','in_progress','resolved','closed','cancelled'), not
-- 0014's ('pending','in_progress','reopened',...). `cancelled` is counted as
-- neither active nor resolved: it was withdrawn, so it is not work outstanding
-- and it is not work done.
-- ---------------------------------------------------------------------------
drop view if exists public.department_overview;
create view public.department_overview
with (security_invoker = true) as
select
  d.id,
  d.community_id,
  d.name,
  d.description,
  d.contact_email,
  d.contact_phone_e164,
  d.opens_at,
  d.closes_at,
  d.sla_hours,
  d.kind,
  d.status,
  d.created_at,
  d.updated_at,
  head.display_name                              as head_name,
  head.id                                        as head_staff_id,
  coalesce(st.staff_count, 0)                    as staff_count,
  coalesce(cx.active_complaint_count, 0)         as active_complaint_count,
  coalesce(cx.resolved_complaint_count, 0)       as resolved_complaint_count,
  coalesce(cx.overdue_complaint_count, 0)        as overdue_complaint_count,
  coalesce(cat.category_ids, '{}'::uuid[])       as category_ids,
  coalesce(cat.category_names, '{}'::text[])     as category_names,
  lower(concat_ws(' ',
    d.name,
    d.description,
    d.contact_email,
    head.display_name,
    array_to_string(coalesce(cat.category_names, '{}'::text[]), ' '),
    st.staff_names
  ))                                             as search_text
from public.departments d
left join lateral (
  select s.id, s.display_name
    from public.staff_assignments s
   where s.department_id = d.id
     and s.rank = 'head'
     and s.status = 'active'
   limit 1
) head on true
left join lateral (
  select count(*) as staff_count,
         string_agg(s.display_name, ' ') as staff_names
    from public.staff_assignments s
   where s.department_id = d.id
     and s.status = 'active'
) st on true
left join lateral (
  select
    count(*) filter (
      where c.status in ('open', 'acknowledged', 'in_progress')
    ) as active_complaint_count,
    count(*) filter (
      where c.status in ('resolved', 'closed')
    ) as resolved_complaint_count,
    -- "Overdue" means open AND past its deadline. A resolved complaint that took
    -- too long is a different metric and is deliberately not counted here, which
    -- is what Departments.jsx:141 does.
    count(*) filter (
      where c.status in ('open', 'acknowledged', 'in_progress')
        and c.due_at is not null
        and c.due_at < now()
    ) as overdue_complaint_count
    from public.complaints c
   where c.department_id = d.id
) cx on true
left join lateral (
  select array_agg(cc.id   order by cc.name) as category_ids,
         array_agg(cc.name order by cc.name) as category_names
    from public.department_categories dc
    join public.complaint_categories cc on cc.id = dc.category_id
   where dc.department_id = d.id
) cat on true;

comment on view public.department_overview is
  'Departments with staff, category and complaint counts. Runs as the caller (security_invoker), so RLS applies.';

-- ---------------------------------------------------------------------------
-- 6. department_staff_overview
--
-- The staff roster plus each member's open workload, which the department detail
-- screen renders next to their name.
--
-- The label match is `left(assignee_label, length(display_name)) = display_name`
-- and NOT `assignee_label ilike display_name || '%'`. A name is user-supplied, so
-- an ilike pattern would treat a '%' or '_' in it as a wildcard and silently
-- overcount. `left()` is an exact prefix test, which is what the frontend's
-- `startsWith` actually means.
-- ---------------------------------------------------------------------------
drop view if exists public.department_staff_overview;
create view public.department_staff_overview
with (security_invoker = true) as
select
  s.id,
  s.community_id,
  s.department_id,
  s.membership_id,
  s.display_name,
  s.phone_e164,
  s.job_title,
  s.rank,
  s.shift,
  s.status,
  s.created_at,
  s.updated_at,
  coalesce(a.active_assignment_count, 0) as active_assignment_count
from public.staff_assignments s
left join lateral (
  select count(*) as active_assignment_count
    from public.complaints c
   where c.department_id = s.department_id
     and c.status in ('open', 'acknowledged', 'in_progress')
     and (
       (s.membership_id is not null and c.assigned_to_membership_id = s.membership_id)
       or (
         s.display_name is not null
         and length(s.display_name) > 0
         and c.assignee_label is not null
         and left(c.assignee_label, length(s.display_name)) = s.display_name
       )
     )
) a on true;

comment on view public.department_staff_overview is
  'Staff assignments with the number of open complaints each member holds in that department.';

grant select on public.department_overview to authenticated;
grant select on public.department_staff_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 7. Internal helpers
--
-- Plain (SECURITY INVOKER) functions called only from the SECURITY DEFINER RPCs
-- below. Inside a definer function the effective user is already the owner, so
-- these run with the rights they need; EXECUTE is revoked from everyone else so
-- they cannot be called directly to bypass the authorization the RPCs do.
-- ---------------------------------------------------------------------------

-- Resolve a set of category NAMES to ids, creating the ones that do not exist.
-- The frontend collects categories as free text (`useState([''])`), so a name
-- arriving for the first time is normal input, not an error.
create or replace function public.upsert_category_names(
  p_community_id uuid,
  p_names        text[]
)
returns uuid[]
language plpgsql
as $$
declare
  v_ids  uuid[] := '{}';
  v_name text;
  v_id   uuid;
begin
  if p_names is null then
    return v_ids;
  end if;

  foreach v_name in array p_names loop
    v_name := btrim(v_name);
    continue when v_name = '';

    select id into v_id
      from public.complaint_categories
     where community_id = p_community_id
       and lower(btrim(name)) = lower(v_name)
     limit 1;

    if v_id is null then
      insert into public.complaint_categories (community_id, name)
      values (p_community_id, v_name)
      returning id into v_id;
    end if;

    v_ids := array_append(v_ids, v_id);
  end loop;

  return v_ids;
end $$;

revoke all on function public.upsert_category_names(uuid, text[]) from public, anon, authenticated;

-- Make department_categories match exactly the supplied set of names.
create or replace function public.sync_department_categories(
  p_department_id uuid,
  p_community_id  uuid,
  p_names         text[]
)
returns void
language plpgsql
as $$
declare
  v_ids uuid[];
begin
  v_ids := public.upsert_category_names(p_community_id, p_names);

  delete from public.department_categories
   where department_id = p_department_id
     and not (category_id = any(v_ids));

  insert into public.department_categories (department_id, category_id)
  select p_department_id, unnest(v_ids)
  on conflict do nothing;
end $$;

revoke all on function public.sync_department_categories(uuid, uuid, text[]) from public, anon, authenticated;

-- Promote the named staff member to head, demoting whoever held it.
--
-- The demotion is a SEPARATE statement that runs FIRST, because
-- `staff_assignments_one_active_head` is a unique index and a single UPDATE
-- touching both rows would violate it mid-statement.
create or replace function public.apply_department_head(
  p_department_id uuid,
  p_head_name     text
)
returns void
language plpgsql
as $$
declare
  v_name text := btrim(coalesce(p_head_name, ''));
  v_id   uuid;
begin
  update public.staff_assignments
     set rank = 'member'
   where department_id = p_department_id
     and rank = 'head';

  if v_name = '' then
    return;
  end if;

  select id into v_id
    from public.staff_assignments
   where department_id = p_department_id
     and status = 'active'
     and lower(btrim(display_name)) = lower(v_name)
   limit 1;

  if v_id is not null then
    update public.staff_assignments set rank = 'head' where id = v_id;
  end if;
end $$;

revoke all on function public.apply_department_head(uuid, text) from public, anon, authenticated;

-- Reconcile a roster against the supplied array of members.
--
-- Rows whose id is supplied are updated in place; rows without an id are
-- inserted; active rows that were not mentioned are DEACTIVATED rather than
-- deleted (A7).
--
-- Key PRESENCE means "change this". A member object that omits `phone` leaves
-- the stored number alone, which is why every field is read with a
-- `? ` containment test rather than `->>` alone -- `->>` cannot distinguish an
-- absent key from an explicit null, and the two mean opposite things here.
create or replace function public.sync_department_staff(
  p_department_id uuid,
  p_community_id  uuid,
  p_staff         jsonb
)
returns void
language plpgsql
as $$
declare
  v_member    jsonb;
  v_seen      uuid[] := '{}';
  v_id        uuid;
  v_name      text;
begin
  if p_staff is null or jsonb_typeof(p_staff) <> 'array' then
    return;
  end if;

  for v_member in select * from jsonb_array_elements(p_staff) loop
    v_name := btrim(coalesce(v_member ->> 'name', ''));
    continue when v_name = '';

    v_id := nullif(v_member ->> 'id', '')::uuid;

    if v_id is not null then
      update public.staff_assignments
         set display_name = v_name,
             phone_e164   = case when v_member ? 'phone'  then nullif(btrim(coalesce(v_member ->> 'phone', '')), '') else phone_e164 end,
             job_title    = case when v_member ? 'role'   then nullif(btrim(coalesce(v_member ->> 'role', '')), '')  else job_title  end,
             shift        = case when v_member ? 'shift'  then nullif(btrim(coalesce(v_member ->> 'shift', '')), '') else shift      end,
             status       = case when v_member ? 'status' then coalesce(nullif(btrim(coalesce(v_member ->> 'status', '')), ''), status) else status end,
             updated_at   = now()
       where id = v_id
         and department_id = p_department_id;
    else
      insert into public.staff_assignments (
        community_id, department_id, display_name, phone_e164, job_title,
        shift, status, employment_type
      )
      values (
        p_community_id,
        p_department_id,
        v_name,
        nullif(btrim(coalesce(v_member ->> 'phone', '')), ''),
        nullif(btrim(coalesce(v_member ->> 'role', '')), ''),
        nullif(btrim(coalesce(v_member ->> 'shift', '')), ''),
        coalesce(nullif(btrim(coalesce(v_member ->> 'status', '')), ''), 'active'),
        'staff'
      )
      returning id into v_id;
    end if;

    v_seen := array_append(v_seen, v_id);
  end loop;

  -- Anyone active but unmentioned has been removed from the form's list.
  update public.staff_assignments
     set status = 'inactive',
         rank   = 'member',
         is_active = false,
         updated_at = now()
   where department_id = p_department_id
     and status = 'active'
     and not (id = any(v_seen));
end $$;

revoke all on function public.sync_department_staff(uuid, uuid, jsonb) from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- 8. The write RPCs
--
-- Every write goes through one of these because creating a department touches
-- four tables and PostgREST has no client-side transaction: doing it in the
-- repository would leave a department with no categories the first time the
-- second call failed.
--
-- SECURITY DEFINER with an explicit admin check, and `set search_path = public`
-- so a caller cannot shadow a referenced table with a temp one.
-- ---------------------------------------------------------------------------
create or replace function public.create_department(
  p_community_id uuid,
  p_payload      jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  if not public.is_community_admin(p_community_id) then
    raise exception 'Only an admin of this community may create a department.'
      using errcode = '42501';
  end if;

  insert into public.departments (
    community_id, name, description, contact_email, contact_phone_e164,
    opens_at, closes_at, sla_hours, kind, status
  )
  values (
    p_community_id,
    btrim(p_payload ->> 'name'),
    nullif(btrim(coalesce(p_payload ->> 'description', '')), ''),
    nullif(btrim(coalesce(p_payload ->> 'contact_email', '')), '')::citext,
    nullif(btrim(coalesce(p_payload ->> 'contact_phone_e164', '')), ''),
    (nullif(p_payload ->> 'opens_at', ''))::time,
    (nullif(p_payload ->> 'closes_at', ''))::time,
    (nullif(p_payload ->> 'sla_hours', ''))::integer,
    nullif(btrim(coalesce(p_payload ->> 'kind', '')), ''),
    coalesce(nullif(btrim(coalesce(p_payload ->> 'status', '')), ''), 'active')
  )
  returning id into v_id;

  if p_payload ? 'categories' then
    perform public.sync_department_categories(
      v_id,
      p_community_id,
      array(select jsonb_array_elements_text(p_payload -> 'categories'))
    );
  end if;

  if p_payload ? 'staff' then
    perform public.sync_department_staff(v_id, p_community_id, p_payload -> 'staff');
  end if;

  -- After the roster exists, so the named head has a row to be promoted.
  if p_payload ? 'head' then
    perform public.apply_department_head(v_id, p_payload ->> 'head');
  end if;

  return v_id;
end $$;

create or replace function public.update_department(
  p_department_id uuid,
  p_patch         jsonb
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
begin
  select community_id into v_community_id
    from public.departments where id = p_department_id;

  if v_community_id is null then
    raise exception 'Department not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may update a department.'
      using errcode = '42501';
  end if;

  -- Key presence means "change this"; an absent key leaves the column alone.
  update public.departments
     set name               = case when p_patch ? 'name'               then btrim(p_patch ->> 'name')                                          else name               end,
         description        = case when p_patch ? 'description'        then nullif(btrim(coalesce(p_patch ->> 'description', '')), '')          else description        end,
         contact_email      = case when p_patch ? 'contact_email'      then nullif(btrim(coalesce(p_patch ->> 'contact_email', '')), '')::citext else contact_email     end,
         contact_phone_e164 = case when p_patch ? 'contact_phone_e164' then nullif(btrim(coalesce(p_patch ->> 'contact_phone_e164', '')), '')   else contact_phone_e164 end,
         opens_at           = case when p_patch ? 'opens_at'           then (nullif(p_patch ->> 'opens_at', ''))::time                          else opens_at           end,
         closes_at          = case when p_patch ? 'closes_at'          then (nullif(p_patch ->> 'closes_at', ''))::time                         else closes_at          end,
         sla_hours          = case when p_patch ? 'sla_hours'          then (nullif(p_patch ->> 'sla_hours', ''))::integer                      else sla_hours          end,
         kind               = case when p_patch ? 'kind'               then nullif(btrim(coalesce(p_patch ->> 'kind', '')), '')                 else kind               end,
         status             = case when p_patch ? 'status'             then coalesce(nullif(btrim(coalesce(p_patch ->> 'status', '')), ''), status) else status         end,
         updated_at         = now()
   where id = p_department_id;

  if p_patch ? 'categories' then
    perform public.sync_department_categories(
      p_department_id,
      v_community_id,
      array(select jsonb_array_elements_text(p_patch -> 'categories'))
    );
  end if;

  if p_patch ? 'staff' then
    perform public.sync_department_staff(p_department_id, v_community_id, p_patch -> 'staff');
  end if;

  if p_patch ? 'head' then
    perform public.apply_department_head(p_department_id, p_patch ->> 'head');
  end if;
end $$;

-- Refuses while the department still owns work. Deleting it would orphan
-- complaints onto a null department, which reads on screen as "unassigned" and
-- silently loses the routing an admin set up.
create or replace function public.delete_department(p_department_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_open         integer;
begin
  select community_id into v_community_id
    from public.departments where id = p_department_id;

  if v_community_id is null then
    raise exception 'Department not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may delete a department.'
      using errcode = '42501';
  end if;

  select count(*) into v_open
    from public.complaints
   where department_id = p_department_id
     and status in ('open', 'acknowledged', 'in_progress');

  if v_open > 0 then
    raise exception 'This department still has % open complaint(s).', v_open
      using errcode = '23503';
  end if;

  delete from public.departments where id = p_department_id;
end $$;

-- Deactivation, not deletion (A7).
create or replace function public.remove_department_staff(p_staff_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
begin
  select community_id into v_community_id
    from public.staff_assignments where id = p_staff_id;

  if v_community_id is null then
    raise exception 'Staff member not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may change a roster.'
      using errcode = '42501';
  end if;

  update public.staff_assignments
     set status     = 'inactive',
         rank       = 'member',
         is_active  = false,
         updated_at = now()
   where id = p_staff_id;
end $$;

grant execute on function public.create_department(uuid, jsonb)  to authenticated;
grant execute on function public.update_department(uuid, jsonb)  to authenticated;
grant execute on function public.delete_department(uuid)         to authenticated;
grant execute on function public.remove_department_staff(uuid)   to authenticated;

-- ---------------------------------------------------------------------------
-- 9. Row-level security
--
-- Reads: any active member of the community. Writes: admins only, and only
-- through the RPCs above -- the direct-write policies exist because
-- `insert_staff_member` and `update_staff_member` write `staff_assignments`
-- straight, which is safe because they touch one table and have nothing partial
-- to protect.
-- ---------------------------------------------------------------------------
alter table public.complaint_categories  enable row level security;
alter table public.department_categories enable row level security;

drop policy if exists complaint_categories_read on public.complaint_categories;
create policy complaint_categories_read on public.complaint_categories
  for select to authenticated
  using (public.is_community_member(community_id));

drop policy if exists complaint_categories_write on public.complaint_categories;
create policy complaint_categories_write on public.complaint_categories
  for all to authenticated
  using (public.is_community_admin(community_id))
  with check (public.is_community_admin(community_id));

drop policy if exists department_categories_read on public.department_categories;
create policy department_categories_read on public.department_categories
  for select to authenticated
  using (exists (
    select 1 from public.departments d
     where d.id = department_id
       and public.is_community_member(d.community_id)
  ));

drop policy if exists department_categories_write on public.department_categories;
create policy department_categories_write on public.department_categories
  for all to authenticated
  using (exists (
    select 1 from public.departments d
     where d.id = department_id
       and public.is_community_admin(d.community_id)
  ))
  with check (exists (
    select 1 from public.departments d
     where d.id = department_id
       and public.is_community_admin(d.community_id)
  ));

-- ---------------------------------------------------------------------------
-- 10. SSE outbox
--
-- 0007 established that every write fires a trigger which writes `sse_events`,
-- which pushes `dashboard.refresh`, which makes the frontend re-snapshot. That
-- is what lets our write endpoints update the UI without our API needing a
-- matching read. Departments and rosters join that mechanism here.
-- ---------------------------------------------------------------------------
drop trigger if exists departments_sse on public.departments;
create trigger departments_sse
  after insert or update or delete on public.departments
  for each row execute function public.emit_dashboard_sse_event();

drop trigger if exists staff_assignments_sse on public.staff_assignments;
create trigger staff_assignments_sse
  after insert or update or delete on public.staff_assignments
  for each row execute function public.emit_dashboard_sse_event();
