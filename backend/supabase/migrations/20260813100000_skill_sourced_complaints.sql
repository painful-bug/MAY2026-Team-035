-- Complaint Engine v2: skill-sourced complaints.

alter table public.complaints
  add column if not exists skill_id uuid references public.skills(id) on delete set null;
comment on column public.complaints.skill_id is
  'The trade the resident filed under, from the global skills catalogue. '
  'category keeps the display-name snapshot; old rows have null here.';
create index if not exists complaints_skill_idx on public.complaints (skill_id);

-- CHANGED: an appended argument needs an exact old-signature drop, otherwise
-- Postgres creates an overload and old RPC calls stay bound to it.
drop function if exists public.resolve_complaint_department(uuid, text, uuid);
create function public.resolve_complaint_department(
  p_community_id uuid,
  p_category text,
  p_department_id uuid,
  p_skill_id uuid default null
) returns uuid
language plpgsql stable security definer set search_path = public
as $$
declare
  v_category text := lower(btrim(coalesce(p_category, '')));
  v_matches uuid[];
  v_chosen uuid;
  v_dept uuid;
  v_n integer;
begin
  -- CHANGED: skill ownership has precedence over every legacy route.
  if p_skill_id is not null then
    select min(d.id::text)::uuid, count(distinct d.id)
      into v_dept, v_n
      from public.department_skills ds
      join public.departments d on d.id = ds.department_id
     where ds.skill_id = p_skill_id
       and d.community_id = p_community_id and d.is_active;
    if v_n = 1 then return v_dept; end if;
    if v_n > 1 then return null; end if;

    select min(d.id::text)::uuid, count(distinct d.id)
      into v_dept, v_n
      from public.skills s
      join public.complaint_categories cc
        on cc.community_id = p_community_id
       and lower(btrim(cc.name)) in (lower(btrim(s.name)), lower(btrim(coalesce(s.category, ''))))
      join public.department_categories dc on dc.category_id = cc.id
      join public.departments d on d.id = dc.department_id and d.is_active
     where s.id = p_skill_id;
    if v_n = 1 then return v_dept; end if;
    if v_n > 1 then return null; end if;
  end if;

  if v_category <> '' then
    select array_agg(distinct dc.department_id) into v_matches
      from public.complaint_categories cc
      join public.department_categories dc on dc.category_id = cc.id
      join public.departments d on d.id = dc.department_id
     where cc.community_id = p_community_id
       and lower(btrim(cc.name)) = v_category
       and d.community_id = p_community_id and d.is_active;
    if coalesce(array_length(v_matches, 1), 0) = 1 then return v_matches[1]; end if;
    if coalesce(array_length(v_matches, 1), 0) > 1 then return null; end if;
  end if;

  if p_department_id is not null then
    select d.id into v_chosen from public.departments d
     where d.id = p_department_id and d.community_id = p_community_id and d.is_active;
    return v_chosen;
  end if;
  return null;
end;
$$;
grant execute on function public.resolve_complaint_department(uuid, text, uuid, uuid) to authenticated;

-- CHANGED: skill is server-validated and snapshots its name into category.
drop function if exists public.raise_complaint(uuid, text, text, text, text, text, uuid);
create function public.raise_complaint(
  p_membership_id uuid, p_title text, p_description text, p_category text,
  p_priority text default 'low', p_location text default null,
  p_department_id uuid default null, p_skill_id uuid default null
) returns uuid
language plpgsql security definer set search_path = public
as $$
declare
  v_community_id uuid;
  v_priority text := lower(coalesce(nullif(btrim(coalesce(p_priority, '')), ''), 'low'));
  v_title text := nullif(btrim(coalesce(p_title, '')), '');
  v_category text := nullif(btrim(coalesce(p_category, '')), '');
  v_department uuid;
  v_payload jsonb;
  v_id uuid;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'A complaint may only be raised for your own membership.' using errcode = 'HB403';
  end if;
  if v_title is null then raise exception 'A complaint needs a title.' using errcode = '23514'; end if;
  if v_priority not in ('low', 'medium', 'high') then
    raise exception 'Unknown complaint priority: %', p_priority using errcode = '22P02';
  end if;
  -- CHANGED: the client submits an id, never a mutable display string.
  if p_skill_id is not null then
    select s.name into v_category from public.skills s where s.id = p_skill_id and s.is_active;
    if v_category is null then raise exception 'No such trade.' using errcode = 'HB404'; end if;
  end if;
  if v_category is null then raise exception 'A complaint needs a category.' using errcode = '23514'; end if;
  select m.community_id into v_community_id from public.community_memberships m where m.id = p_membership_id;
  v_department := public.resolve_complaint_department(v_community_id, v_category, p_department_id, p_skill_id);
  insert into public.complaints (
    community_id, raised_by_membership_id, title, description, category, skill_id,
    status, priority, location, expected_resolution_at, due_at, department_id
  ) values (
    v_community_id, p_membership_id, v_title, nullif(btrim(coalesce(p_description, '')), ''),
    v_category, p_skill_id, 'open', v_priority, nullif(btrim(coalesce(p_location, '')), ''),
    now() + make_interval(hours => public.complaint_sla_hours(v_priority)),
    now() + make_interval(hours => public.complaint_sla_hours(v_priority)), v_department
  ) returning id into v_id;
  insert into public.complaint_events (complaint_id, actor_membership_id, event_type, payload)
  values (v_id, p_membership_id, 'raised', jsonb_build_object(
    'priority', v_priority, 'category', v_category, 'skill_id', p_skill_id,
    'department_id', v_department, 'department_chosen_by_resident', p_department_id));
  v_payload := jsonb_build_object('title', 'New complaint raised', 'body', v_title,
    'url', '/admin/complaints?complaint=' || v_id::text, 'complaint_id', v_id);
  perform public.notify_complaint_staff(v_id, 'complaint.raised', v_payload, p_membership_id);
  return v_id;
end;
$$;
grant execute on function public.raise_complaint(uuid, text, text, text, text, text, uuid, uuid) to authenticated;

do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'complaints' and column_name = 'skill_id') then
    raise exception 'complaints.skill_id missing';
  end if;
  if not exists (select 1 from pg_proc where pronamespace = 'public'::regnamespace and proname = 'raise_complaint' and pronargs = 8) then
    raise exception 'raise_complaint must have 8 arguments';
  end if;
end $$;
