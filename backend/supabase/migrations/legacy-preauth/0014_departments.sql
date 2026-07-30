-- 0014_departments.sql
-- Step 6: department and staff management.
--
-- Two read views that do the counting the dashboard needs, and four RPCs that
-- keep a department, its categories and its staff roster in one transaction.
--
-- Depends on 0010-0013. Numbering: 0004-0009 belong to the auth/security
-- workstream (build plan 1.4).
--
-- ===========================================================================
-- WHAT READING THE FRONTEND CHANGED ABOUT THE PLAN
--
-- 1. THE ARCHIVE RULE IN THE BUILD PLAN WAS WRONG. It said "a department cannot
--    be archived while it owns unresolved complaints". The frontend blocks
--    DELETION on that condition and offers deactivation as the escape hatch --
--    `Departments.jsx:569` renders a "Deactivate" button precisely when deletion
--    is refused. Guarding deactivation too would remove the only remaining
--    action and leave the admin stuck. So: DELETE is guarded, archiving is not.
--
-- 2. `head` IS A NAME, NOT A LINK. `departments[].head` is a plain string that
--    also appears in `staff[]` -- dept-plumbing's head 'Ramesh Kumar' is also
--    staff[0]. 0011 modelled the head as `staff_assignments.rank = 'head'` (R8),
--    which is the better shape, so the RPCs here reconcile the two: naming a head
--    PROMOTES the matching staff row, and creates one if no name matches. One
--    source of truth, and the frontend's field still round-trips exactly.
--
-- 3. THE TWO CATEGORY UIs DISAGREE. `Departments.jsx:22` offers a fixed checkbox
--    list of six (Plumbing, Electrical, Infrastructure, Cleaning, Security,
--    Others) while `CreateDepartment.jsx:79` is a FREE-TEXT box whose placeholder
--    is "e.g. Leaking pipes" -- a symptom, not a category. 0011 seeds five; there
--    is no 'Others'. Categories are therefore upserted BY NAME here, so both
--    screens work, and a typo becomes a new category rather than an error.
--    Raised as DECISIONS_NEEDED B9.
--
-- ===========================================================================
-- ASSUMPTIONS MADE HERE
--
--  A6  'Inactive' MAPS TO 'archived'. The frontend has two department states,
--      Active and Inactive; 0011's CHECK allows 'active' and 'archived'. Rather
--      than migrate the constraint, the wire mapping lives in
--      app/domain/vocabularies.py. The mapping is total and lossless in both
--      directions because each vocabulary has exactly two values. Whether the
--      column should simply say 'inactive' is DECISIONS_NEEDED D5 -- cosmetic,
--      and cheap either way while unapplied.
--
--  A7  REMOVING A STAFF MEMBER DEACTIVATES THE ROW, it does not delete it. The
--      frontend splices the array. But `complaints.assignee_label` records staff
--      by NAME (C1), so a deleted row turns a past assignment into an unexplained
--      string. Deactivation keeps the roster answerable. The partial head index
--      only constrains active rows, so a deactivated head frees the slot.
--
--  A8  A STAFF MEMBER'S ASSIGNMENT COUNT IS SCOPED TO THEIR DEPARTMENT, matching
--      `DepartmentDetail.jsx:452` which counts within `departmentComplaints`.
--      Work assigned to them under another department is not counted here.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- department_overview
--
-- Every number the departments screen shows, computed in one place. A VIEW and
-- not an RPC because a list endpoint needs filtering, ordering, paging and an
-- exact count, and PostgREST gives all four on a view for free -- an RPC would
-- have to reimplement them as parameters.
--
-- `security_invoker = true` (PG15+) makes the view run with the CALLER's rights,
-- so the RLS policies on departments/complaints/staff_assignments still decide
-- what is visible. Without it a view is a hole straight through RLS.
--
-- `search_text` exists so that one `ilike` reproduces the frontend's search,
-- which spans name, description, head, email, category names AND staff names
-- (Departments.jsx:163). Matching that with PostgREST `or` filters across three
-- embedded tables is not possible; precomputing the haystack is.
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
      where c.status in ('pending', 'in_progress', 'reopened')
    ) as active_complaint_count,
    count(*) filter (
      where c.status in ('resolved', 'closed')
    ) as resolved_complaint_count,
    -- "Overdue" means open AND past its deadline. A resolved complaint that took
    -- too long is a different metric and is deliberately not counted here, which
    -- is what Departments.jsx:141 does.
    count(*) filter (
      where c.status in ('pending', 'in_progress', 'reopened')
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
-- department_staff_overview
--
-- The staff roster plus each member''s open workload, which the department detail
-- screen renders next to their name.
--
-- The label match is `left(assignee_label, length(display_name)) = display_name`
-- and NOT `assignee_label ilike display_name || '%'`. A name is user-supplied, so
-- an ilike pattern would treat a '%' or '_' in it as a wildcard and silently
-- overcount. `left()` is an exact prefix test, which is what the frontend''s
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
     and c.status in ('pending', 'in_progress', 'reopened')
     and (
       (s.membership_id is not null and c.assigned_to_membership_id = s.membership_id)
       or (
         length(s.display_name) > 0
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
-- Internal helpers
--
-- Plain (SECURITY INVOKER) functions called only from the SECURITY DEFINER RPCs
-- below. Inside a definer function the effective user is already the owner, so
-- these run with the rights they need; EXECUTE is revoked from everyone else so
-- they cannot be called directly to bypass the authorization checks the RPCs do.
-- ---------------------------------------------------------------------------

-- Resolve a list of category NAMES to ids in one community, creating any that do
-- not exist yet (see note 3 in the header).
create or replace function public.upsert_category_names(
  p_community_id uuid,
  p_names        text[]
)
returns uuid[]
language plpgsql
set search_path = public
as $$
declare
  v_clean text[];
  v_ids   uuid[];
begin
  select array_agg(distinct btrim(n))
    into v_clean
    from unnest(coalesce(p_names, '{}'::text[])) as n
   where btrim(coalesce(n, '')) <> '';

  if v_clean is null then
    return '{}'::uuid[];
  end if;

  insert into public.complaint_categories (community_id, name)
  select p_community_id, n from unnest(v_clean) as n
  on conflict on constraint complaint_categories_community_name_uq do nothing;

  select array_agg(c.id)
    into v_ids
    from public.complaint_categories c
   where c.community_id = p_community_id
     and c.name = any (v_clean);

  return coalesce(v_ids, '{}'::uuid[]);
end;
$$;

-- Make department_categories match exactly the supplied set of names.
create or replace function public.sync_department_categories(
  p_department_id uuid,
  p_community_id  uuid,
  p_names         text[]
)
returns void
language plpgsql
set search_path = public
as $$
declare
  v_ids uuid[] := public.upsert_category_names(p_community_id, p_names);
begin
  delete from public.department_categories dc
   where dc.department_id = p_department_id
     and not (dc.category_id = any (v_ids));

  insert into public.department_categories (community_id, department_id, category_id)
  select p_community_id, p_department_id, cid from unnest(v_ids) as cid
  on conflict on constraint department_categories_uq do nothing;
end;
$$;

-- Promote the named staff member to head, demoting whoever held it.
--
-- The demotion is a SEPARATE statement that runs FIRST, because
-- staff_assignments_dept_head_uq is a non-deferrable partial unique index: a
-- single statement that promoted before demoting would violate it mid-way.
create or replace function public.apply_department_head(
  p_department_id uuid,
  p_community_id  uuid,
  p_head          text
)
returns void
language plpgsql
set search_path = public
as $$
declare
  v_head text := nullif(btrim(coalesce(p_head, '')), '');
  v_id   uuid;
begin
  update public.staff_assignments
     set rank = 'member'
   where department_id = p_department_id
     and rank = 'head'
     and status = 'active'
     and (v_head is null or lower(display_name) <> lower(v_head));

  if v_head is null then
    return;
  end if;

  select s.id into v_id
    from public.staff_assignments s
   where s.department_id = p_department_id
     and s.status = 'active'
     and lower(s.display_name) = lower(v_head)
   order by s.created_at
   limit 1;

  if v_id is null then
    -- A head who is not on the roster. The frontend allows exactly this: `head`
    -- is a free-text field independent of the staff rows. Creating the row keeps
    -- staff_assignments the single source of truth for who leads a department.
    insert into public.staff_assignments
      (community_id, department_id, display_name, rank, status)
    values
      (p_community_id, p_department_id, v_head, 'head', 'active');
  else
    update public.staff_assignments set rank = 'head' where id = v_id;
  end if;
end;
$$;

-- Reconcile a department's roster against a supplied array of staff objects:
--   [{"id": uuid|null, "name": text, "phone": text, "role": text,
--     "rank": text, "shift": text, "status": text}]
--
-- Rows whose id is supplied are updated in place; rows without an id are
-- inserted; ACTIVE rows the payload does not mention are DEACTIVATED, not
-- deleted (assumption A7).
create or replace function public.sync_department_staff(
  p_department_id uuid,
  p_community_id  uuid,
  p_staff         jsonb
)
returns void
language plpgsql
set search_path = public
as $$
declare
  v_keep uuid[];
  item   jsonb;
  v_id   uuid;
  v_name text;
begin
  if p_staff is null or jsonb_typeof(p_staff) <> 'array' then
    return;
  end if;

  -- Pass 1: update or insert everything the payload names.
  for item in select * from jsonb_array_elements(p_staff)
  loop
    v_name := nullif(btrim(coalesce(item->>'name', '')), '');
    if v_name is null then
      -- The create form keeps a blank staff row on screen at all times; a row
      -- with no name is UI scaffolding, not a person.
      continue;
    end if;

    v_id := null;
    if nullif(item->>'id', '') is not null then
      select s.id into v_id
        from public.staff_assignments s
       where s.id = (item->>'id')::uuid
         and s.department_id = p_department_id;

      if v_id is null then
        -- An id that belongs to another department (or to nothing) is a client
        -- bug, and silently inserting a duplicate would hide it.
        raise exception 'Staff member does not belong to this department.'
          using errcode = 'HB404';
      end if;
    end if;

    if v_id is null then
      insert into public.staff_assignments
        (community_id, department_id, display_name, phone_e164, job_title, rank, shift, status)
      values (
        p_community_id,
        p_department_id,
        v_name,
        nullif(btrim(coalesce(item->>'phone', '')), ''),
        nullif(btrim(coalesce(item->>'role', '')), ''),
        coalesce(nullif(item->>'rank', ''), 'member'),
        nullif(item->>'shift', ''),
        coalesce(nullif(item->>'status', ''), 'active')
      )
      returning id into v_id;
    else
      update public.staff_assignments s
         set display_name = v_name,
             phone_e164   = case when item ? 'phone'
                              then nullif(btrim(coalesce(item->>'phone', '')), '')
                              else s.phone_e164 end,
             job_title    = case when item ? 'role'
                              then nullif(btrim(coalesce(item->>'role', '')), '')
                              else s.job_title end,
             shift        = case when item ? 'shift'
                              then nullif(item->>'shift', '')
                              else s.shift end,
             status       = coalesce(nullif(item->>'status', ''), 'active')
       where s.id = v_id;
    end if;

    v_keep := array_append(v_keep, v_id);
  end loop;

  -- Pass 2: everyone else comes off the active roster.
  update public.staff_assignments
     set status = 'inactive',
         rank   = case when rank = 'head' then 'member' else rank end
   where department_id = p_department_id
     and status = 'active'
     and not (id = any (coalesce(v_keep, '{}'::uuid[])));
end;
$$;

revoke execute on function public.upsert_category_names(uuid, text[]) from public, anon, authenticated;
revoke execute on function public.sync_department_categories(uuid, uuid, text[]) from public, anon, authenticated;
revoke execute on function public.apply_department_head(uuid, uuid, text) from public, anon, authenticated;
revoke execute on function public.sync_department_staff(uuid, uuid, jsonb) from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- create_department
--
-- One transaction for what is otherwise four round trips (department, category
-- upsert, department_categories, staff). PostgREST has no client-side
-- transaction, so doing this from FastAPI would leave a department with no
-- categories the moment the second call failed.
--
-- The payload is jsonb rather than 15 parameters because the same shape is
-- reused by update_department, where PRESENCE of a key has to be distinguishable
-- from a null VALUE -- `p_patch ? 'description'` says "clear it", a missing key
-- says "leave it".
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
  v_id   uuid;
  v_name text := nullif(btrim(coalesce(p_payload->>'name', '')), '');
begin
  if not public.is_admin()
     or p_community_id not in (select public.current_community_ids()) then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;

  if v_name is null then
    raise exception 'Department name is required.' using errcode = 'HB409';
  end if;

  begin
    insert into public.departments (
      community_id, name, description, contact_email, contact_phone_e164,
      opens_at, closes_at, sla_hours, kind, status
    ) values (
      p_community_id,
      v_name,
      nullif(btrim(coalesce(p_payload->>'description', '')), ''),
      nullif(btrim(coalesce(p_payload->>'contact_email', '')), ''),
      nullif(btrim(coalesce(p_payload->>'contact_phone_e164', '')), ''),
      (nullif(p_payload->>'opens_at', ''))::time,
      (nullif(p_payload->>'closes_at', ''))::time,
      (nullif(p_payload->>'sla_hours', ''))::integer,
      coalesce(nullif(p_payload->>'kind', ''), 'service'),
      coalesce(nullif(p_payload->>'status', ''), 'active')
    )
    returning id into v_id;
  exception when unique_violation then
    -- departments_community_name_uq. Re-raised as HB409 so the API returns the
    -- frontend's own wording rather than a constraint name.
    raise exception 'A department with this name already exists.'
      using errcode = 'HB409';
  end;

  if p_payload ? 'categories' then
    perform public.sync_department_categories(
      v_id, p_community_id,
      (select array_agg(value) from jsonb_array_elements_text(p_payload->'categories'))
    );
  end if;

  if p_payload ? 'staff' then
    perform public.sync_department_staff(v_id, p_community_id, p_payload->'staff');
  end if;

  -- After the staff sync, so a head named in the same request can be promoted
  -- rather than duplicated.
  if p_payload ? 'head' then
    perform public.apply_department_head(v_id, p_community_id, p_payload->>'head');
  end if;

  return v_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- update_department -- partial, keyed on jsonb key presence.
-- ---------------------------------------------------------------------------
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
  d public.departments%rowtype;
begin
  select * into d from public.departments where id = p_department_id for update;

  if not found then
    raise exception 'Department not found.' using errcode = 'HB404';
  end if;

  if not public.is_admin()
     or d.community_id not in (select public.current_community_ids()) then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;

  if p_patch ? 'name'
     and nullif(btrim(coalesce(p_patch->>'name', '')), '') is null then
    raise exception 'Department name is required.' using errcode = 'HB409';
  end if;

  begin
    update public.departments x set
      name = case when p_patch ? 'name'
               then btrim(p_patch->>'name') else x.name end,
      description = case when p_patch ? 'description'
               then nullif(btrim(coalesce(p_patch->>'description', '')), '') else x.description end,
      contact_email = case when p_patch ? 'contact_email'
               then nullif(btrim(coalesce(p_patch->>'contact_email', '')), '') else x.contact_email end,
      contact_phone_e164 = case when p_patch ? 'contact_phone_e164'
               then nullif(btrim(coalesce(p_patch->>'contact_phone_e164', '')), '') else x.contact_phone_e164 end,
      opens_at = case when p_patch ? 'opens_at'
               then (nullif(p_patch->>'opens_at', ''))::time else x.opens_at end,
      closes_at = case when p_patch ? 'closes_at'
               then (nullif(p_patch->>'closes_at', ''))::time else x.closes_at end,
      sla_hours = case when p_patch ? 'sla_hours'
               then (nullif(p_patch->>'sla_hours', ''))::integer else x.sla_hours end,
      kind = case when p_patch ? 'kind'
               then coalesce(nullif(p_patch->>'kind', ''), x.kind) else x.kind end,
      status = case when p_patch ? 'status'
               then coalesce(nullif(p_patch->>'status', ''), x.status) else x.status end
    where x.id = p_department_id;
  exception when unique_violation then
    raise exception 'A department with this name already exists.'
      using errcode = 'HB409';
  end;

  if p_patch ? 'categories' then
    perform public.sync_department_categories(
      p_department_id, d.community_id,
      (select array_agg(value) from jsonb_array_elements_text(p_patch->'categories'))
    );
  end if;

  if p_patch ? 'staff' then
    perform public.sync_department_staff(p_department_id, d.community_id, p_patch->'staff');
  end if;

  if p_patch ? 'head' then
    perform public.apply_department_head(p_department_id, d.community_id, p_patch->>'head');
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- delete_department
--
-- Guarded by open complaints (header note 1). Deleting is a real DELETE: the
-- frontend promises "This permanently removes its configuration and staff
-- directory. Complaint records will remain available", and both halves are true
-- here -- department_categories and staff_assignments cascade, while
-- complaints.department_id is `on delete set null (department_id)` so resolved
-- complaints survive with the department reference cleared.
--
-- The count is taken inside the same transaction as the delete, so a complaint
-- raised between check and delete cannot slip through.
-- ---------------------------------------------------------------------------
create or replace function public.delete_department(p_department_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  d      public.departments%rowtype;
  v_open integer;
begin
  select * into d from public.departments where id = p_department_id for update;

  if not found then
    raise exception 'Department not found.' using errcode = 'HB404';
  end if;

  if not public.is_admin()
     or d.community_id not in (select public.current_community_ids()) then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;

  select count(*) into v_open
    from public.complaints c
   where c.department_id = p_department_id
     and c.status in ('pending', 'in_progress', 'reopened');

  if v_open > 0 then
    raise exception
      'Resolve or reassign % active complaint(s) before deleting this department.',
      v_open using errcode = 'HB409';
  end if;

  delete from public.departments where id = p_department_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- remove_department_staff -- deactivation, per A7.
-- ---------------------------------------------------------------------------
create or replace function public.remove_department_staff(p_staff_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  s public.staff_assignments%rowtype;
begin
  select * into s from public.staff_assignments where id = p_staff_id for update;

  if not found then
    raise exception 'Staff member not found.' using errcode = 'HB404';
  end if;

  if not public.is_admin()
     or s.community_id not in (select public.current_community_ids()) then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;

  update public.staff_assignments
     set status = 'inactive',
         rank   = case when rank = 'head' then 'member' else rank end
   where id = p_staff_id;
end;
$$;

revoke execute on function public.create_department(uuid, jsonb) from public, anon;
revoke execute on function public.update_department(uuid, jsonb) from public, anon;
revoke execute on function public.delete_department(uuid) from public, anon;
revoke execute on function public.remove_department_staff(uuid) from public, anon;
grant execute on function public.create_department(uuid, jsonb) to authenticated;
grant execute on function public.update_department(uuid, jsonb) to authenticated;
grant execute on function public.delete_department(uuid) to authenticated;
grant execute on function public.remove_department_staff(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- Verification -- run after applying.
-- ---------------------------------------------------------------------------
-- 1. The views exist and run as the caller. Expect security_invoker = true on
--    both; if either says false, RLS is being bypassed:
--      select c.relname, c.reloptions
--        from pg_class c join pg_namespace n on n.oid = c.relnamespace
--       where n.nspname = 'public'
--         and c.relname in ('department_overview', 'department_staff_overview');
--
-- 2. At most one active head per department. Expect zero rows:
--      select department_id, count(*) from public.staff_assignments
--       where rank = 'head' and status = 'active'
--       group by department_id having count(*) > 1;
--
-- 3. No department_categories row crosses a tenant boundary. Expect zero rows
--    (the composite FKs make this impossible, so a row here means a constraint
--    was dropped):
--      select dc.id from public.department_categories dc
--        join public.departments d on d.id = dc.department_id
--        join public.complaint_categories c on c.id = dc.category_id
--       where d.community_id <> c.community_id;
--
-- 4. Categories claimed by more than one department -- the rows where 0011's A2
--    SLA tie-break is load-bearing. Every row here is a case for the frontend
--    meeting:
--      select c.name, count(*) from public.department_categories dc
--        join public.complaint_categories c on c.id = dc.category_id
--       group by c.name having count(*) > 1;
